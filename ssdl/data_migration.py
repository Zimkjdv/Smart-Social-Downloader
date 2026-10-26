"""Explicit offline import/rollback. Original media and source data are never moved."""
from __future__ import annotations
import argparse
from contextlib import contextmanager, ExitStack, closing
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import time
import uuid

FILES = ("state.json", "state.json.bak", "x-auth.bin", "pixiv-session.bin",
         "image-history.sqlite3", "media-manifest.sqlite3", "x-profiles.sqlite3", "ui-preferences.json")


def plain(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("Linked migration paths are not supported.")
    return path.resolve()


def snapshot(directory):
    result = {}
    for name in FILES:
        for suffix in ("", "-wal") if name.endswith('.sqlite3') else ("",):
            p = directory / (name + suffix)
            if p.exists():
                plain(p)
                if not p.is_file():
                    raise ValueError("Migration input must be a regular file.")
                result[p.name] = (p.stat().st_size, p.stat().st_mtime_ns)
    return result


@contextmanager
def offline(*homes):
    """Hold the same launch/window locks that every desktop host uses."""
    if os.name != 'nt':
        raise RuntimeError("Migration requires Windows; encrypted sessions are user/machine specific.")
    from .desktop_service import Controls, launch_guard
    from .desktop_control import scope_key
    from .config import configured_port
    from .data_access import writer_lease
    with ExitStack() as stack:
        for home in sorted(set(homes), key=str):
            controls = Controls(home)
            stack.callback(controls.close)
            stack.enter_context(launch_guard(controls))
            if controls.owner_running():
                raise RuntimeError("Stop the source and destination background services before importing data.")
            stack.enter_context(writer_lease(home))
            window = controls.keep(controls.api.CreateMutexW(None, False, controls.prefix + 'window'))
            if controls.api.WaitForSingleObject(window, 0) not in (0, 0x80):
                raise RuntimeError("Close the source and destination windows before importing data.")
            stack.callback(controls.api.ReleaseMutex, window)
            ports = {configured_port()}
            record = home / 'data/background-service.json'
            try:
                v = json.loads(record.read_text(encoding='utf-8'))
                if type(v.get('port')) is int and 1 <= v['port'] <= 65535:
                    ports.add(v['port'])
            except (OSError, ValueError):
                pass
            for port in ports:
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                try:
                    connection.request('GET', '/api/identity')
                    reply = connection.getresponse()
                    v = json.loads(reply.read(4097))
                    if v.get('scope') == scope_key(home):
                        raise RuntimeError("A foreground service still uses this data. Stop it before importing.")
                except (OSError, ValueError, http.client.HTTPException):
                    pass
                finally:
                    connection.close()
        yield


def _write(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush(); os.fsync(output.fileno())
    temporary.replace(path)


def _copy_data(source, target):
    target.mkdir()
    before = snapshot(source)
    if not before:
        raise ValueError("No supported history/session files were found in the selected data directory.")
    if shutil.disk_usage(target.parent).free < sum(v[0] for v in before.values()) * 2 + 16 * 1024 * 1024:
        raise OSError("Insufficient free space for a verified import and rollback.")
    hashes = {}
    for name in FILES:
        original, copied = source / name, target / name
        if name not in before:
            continue
        if name.endswith('.sqlite3'):
            start = time.monotonic()
            def progress(*_):
                if time.monotonic() - start > 120:
                    raise TimeoutError("Database import exceeded its deadline.")
            with closing(sqlite3.connect(original.as_uri() + '?mode=ro', uri=True, timeout=2)) as src, closing(sqlite3.connect(copied)) as dst:
                src.backup(dst, pages=1024, progress=progress, sleep=.05)
                if dst.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise ValueError("Imported database integrity check failed.")
        else:
            from .session_storage import MAX_SESSION_BYTES
            limit = (64 * 1024 * 1024 if name.startswith('state.') else
                     4096 if name == 'ui-preferences.json' else MAX_SESSION_BYTES)
            if original.stat().st_size > limit:
                raise ValueError("Migration input exceeds its size limit.")
            shutil.copy2(original, copied)
            if name.startswith('state.'):
                from .persistence import validate_state
                validate_state(json.loads(copied.read_text(encoding='utf-8')))
            elif name == 'ui-preferences.json':
                from .ui_preferences import validate
                validate(json.loads(copied.read_text(encoding='utf-8')))
            else:
                # Preserve encrypted bytes, but reject another Windows user's sessions.
                from .session_storage import SessionStorage
                from .x_auth import _dpapi
                SessionStorage(windows_protect=_dpapi).load(copied)
        hashes[name] = hashlib.sha256(copied.read_bytes()).hexdigest()
    if snapshot(source) != before:
        raise RuntimeError("Source data changed during import; destination was not replaced.")
    return hashes


def migrate(source, home):
    source, home = plain(source), plain(home)
    if home == source or home.is_relative_to(source) or source.is_relative_to(home):
        raise ValueError("Source and destination must be separate directories.")
    home.mkdir(parents=True, exist_ok=True)
    data = plain(home / 'data')
    with offline(source, home):
        identifier = uuid.uuid4().hex
        staging = home / ('.import-' + identifier)
        backup = home / 'data-backups' / identifier
        plain(backup)
        backup.mkdir(parents=True)
        receipt = {'schema': 1, 'id': identifier, 'phase': 'prepared', 'before_exists': data.exists()}
        # Staging and backups are retained on error for inspection; never delete source data.
        receipt['files'] = _copy_data(plain(source / 'data'), staging)
        _write(backup / 'migration.json', receipt)
        moved = False
        installed = False
        try:
            if data.exists():
                plain(data)
                data.replace(backup / 'data')
                moved = True
            staging.replace(data)
            installed = True
            receipt['phase'] = 'committed'
            _write(backup / 'migration.json', receipt)
        except BaseException:
            if installed:
                data.replace(backup / 'failed-import')
            if moved:
                (backup / 'data').replace(data)
            raise
        return {'ok': True, 'backup': identifier, 'files': sorted(receipt['files'])}


def rollback(identifier, home):
    if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
        raise ValueError("Choose a valid migration backup ID.")
    home = plain(home)
    with offline(home):
        backup = plain(home / 'data-backups' / identifier)
        receipt = json.loads((backup / 'migration.json').read_text(encoding='utf-8'))
        if receipt.get('schema') != 1 or receipt.get('id') != identifier or receipt.get('phase') not in {'committed','prepared'}:
            raise ValueError("Backup is incomplete or was already restored.")
        data, before, after = plain(home / 'data'), plain(backup / 'data'), backup / 'after-data'
        if receipt.get('before_exists') and not before.is_dir() or after.exists():
            raise ValueError("Backup is incomplete or was already restored.")
        if data.exists():
            data.replace(after)
        try:
            if receipt['before_exists']:
                before.replace(data)
            else:
                data.mkdir()
        except BaseException:
            if after.exists():
                after.replace(data)
            raise
        receipt['phase'] = 'rolled-back'
        _write(backup / 'migration.json', receipt)
        return {'ok': True, 'restored': identifier, 'newer_data_preserved': after.exists()}


def main(argv=None):
    from .runtime_paths import paths
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('migrate', 'rollback'))
    parser.add_argument('source_or_backup')
    args = parser.parse_args(argv)
    result = migrate(Path(args.source_or_backup), paths().home) if args.action == 'migrate' else rollback(args.source_or_backup, paths().home)
    print(json.dumps(result))
    return 0
