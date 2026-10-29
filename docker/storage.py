"""Offline full-volume backup/restore. Never overwrite an existing installation."""
from contextlib import ExitStack
from datetime import datetime, timezone
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import uuid

from runtime import LOCK_NAME, RESTORE_MARKER, VOLUMES, storage_locks

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ssdl.version import __version__

BACKUPS = Path("/backups")
MANIFEST = "ssdl-backup.json"
MAX_MEMBERS = 200_000


def sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def open_regular(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    stream = os.fdopen(descriptor, "rb")
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        stream.close()
        raise RuntimeError("Only ordinary, unlinked files can be backed up or restored.")
    return stream


def digest(stream):
    checksum = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        checksum.update(chunk)
    return checksum.hexdigest()


def member_mtime_ns(member):
    value = member.pax_headers.get("SSDL.mtime_ns")
    if value is not None:
        if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]{1,19}", value):
            raise RuntimeError("Invalid backup file timestamp.")
        timestamp = int(value)
    else:
        # Older archives have only second-resolution header times. Preserve
        # what they contain; lost nanoseconds cannot safely be reconstructed.
        if not isinstance(member.mtime, (int, float)) or not math.isfinite(member.mtime):
            raise RuntimeError("Invalid backup file timestamp.")
        timestamp = int(member.mtime * 1_000_000_000)
    if not -(2**63) <= timestamp < 2**63:
        raise RuntimeError("Unsupported backup file timestamp.")
    return timestamp


def backup():
    name = datetime.now(timezone.utc).strftime("ssdl-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12] + ".tar"
    destination = BACKUPS / name
    pending = BACKUPS / (name + ".partial")
    manifest = {"format": "ssdl-volumes", "schema_version": 1, "app_version": __version__,
                "created_at": datetime.now(timezone.utc).isoformat(), "volumes": list(VOLUMES)}
    count = 0

    def add_path(archive, path, relative):
        nonlocal count
        count += 1
        if count > MAX_MEMBERS:
            raise RuntimeError("Backup exceeds the supported member count.")
        metadata = path.lstat()
        entry = tarfile.TarInfo(relative)
        entry.mtime = int(metadata.st_mtime)
        if stat.S_ISDIR(metadata.st_mode):
            entry.type, entry.mode = tarfile.DIRTYPE, 0o700
            archive.addfile(entry)
            archive.members.clear()
            with os.scandir(path) as children:
                for child in children:
                    if path in VOLUMES.values() and child.name == LOCK_NAME:
                        continue
                    add_path(archive, Path(child.path), relative + "/" + child.name)
        elif stat.S_ISREG(metadata.st_mode):
            with open_regular(path) as source:
                before = os.fstat(source.fileno())
                if (before.st_dev, before.st_ino) != (metadata.st_dev, metadata.st_ino):
                    raise RuntimeError("Storage changed during backup; stop external writers.")
                entry.size, entry.mode = before.st_size, 0o600
                entry.pax_headers["SSDL.mtime_ns"] = str(before.st_mtime_ns)
                archive.addfile(entry, source)
                archive.members.clear()
                after = os.fstat(source.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise RuntimeError("Storage changed during backup; stop external writers.")
        else:
            raise RuntimeError("Links and special files are not supported in volume backups.")

    try:
        with pending.open("xb") as output:
            with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
                encoded = json.dumps(manifest).encode("utf-8")
                entry = tarfile.TarInfo(MANIFEST)
                entry.size, entry.mode = len(encoded), 0o600
                archive.addfile(entry, io.BytesIO(encoded))
                for label, directory in VOLUMES.items():
                    add_path(archive, directory, label)
            output.flush()
            os.fsync(output.fileno())
        with open_regular(pending) as source:
            checksum = digest(source)
        # The random name is never reused. A backup is complete only with its sidecar.
        if destination.exists():
            raise RuntimeError("Backup name collision; retry with a new snapshot.")
        pending.rename(destination)
        with (BACKUPS / (name + ".sha256")).open("x", encoding="ascii") as output:
            output.write(checksum + "\n")
            output.flush()
            os.fsync(output.fileno())
        sync_directory(BACKUPS)
    finally:
        pending.unlink(missing_ok=True)
    print(f"Backup complete: {name} + {name}.sha256 ({count} entries; cache excluded).")


def restore(name):
    if not re.fullmatch(r"ssdl-[A-Za-z0-9-]+\.tar", name):
        raise RuntimeError("Choose a generated ssdl-*.tar filename inside /backups.")
    with open_regular(BACKUPS / (name + ".sha256")) as sidecar:
        checksum = sidecar.read(66).decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise RuntimeError("Missing or invalid SHA-256 sidecar.")
    for directory in VOLUMES.values():
        if any(path.name != LOCK_NAME for path in directory.iterdir()):
            raise RuntimeError("Restore requires empty data AND media volumes. Existing files are never overwritten.")
    with open_regular(BACKUPS / name) as source, ExitStack() as stack:
        if digest(source) != checksum:
            raise RuntimeError("Backup checksum mismatch; nothing was restored.")
        source.seek(0)
        stages = {label: Path(stack.enter_context(tempfile.TemporaryDirectory(prefix=".ssdl-restore-", dir=directory)))
                  for label, directory in VOLUMES.items()}
        seen = set()
        roots = set()
        with tarfile.open(fileobj=source, mode="r:") as archive:
            first = archive.next()
            if first is None or first.name != MANIFEST or not first.isfile() or not 0 < first.size <= 4096:
                raise RuntimeError("Unrecognized backup manifest.")
            with archive.extractfile(first) as metadata:
                manifest = json.loads(metadata.read())
            archive.members.clear()
            if (not isinstance(manifest, dict) or manifest.get("format") != "ssdl-volumes"
                    or manifest.get("schema_version") != 1 or manifest.get("volumes") != list(VOLUMES)
                    or manifest.get("app_version") != __version__):
                raise RuntimeError("Restore with the original application's version and supported backup format first.")
            # Manual extraction ignores archive ownership, permissions and links.
            # Stream members, rather than caching the full tar table in memory.
            while member := archive.next():
                archive.members.clear()
                path = PurePosixPath(member.name)
                parts = path.parts
                if (not parts or path.is_absolute() or ".." in parts or "\\" in member.name
                        or len(member.name) > 2000 or str(path) != member.name.rstrip("/")
                        or parts[0] not in stages or str(path) in seen
                        or not (member.isdir() or member.isfile()) or member.sparse
                        or len(parts) > 1 and (parts[1] in {LOCK_NAME, RESTORE_MARKER}
                                              or parts[1].startswith(".ssdl-restore-"))):
                    raise RuntimeError("Unsafe or duplicate backup member; nothing was promoted.")
                seen.add(str(path))
                if len(seen) > MAX_MEMBERS:
                    raise RuntimeError("Backup exceeds the supported member count.")
                if len(parts) == 1:
                    if not member.isdir():
                        raise RuntimeError("Invalid volume root in backup.")
                    roots.add(parts[0])
                    continue
                target = stages[parts[0]].joinpath(*parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if member.isdir():
                    target.mkdir(exist_ok=True, mode=0o700)
                else:
                    mtime_ns = member_mtime_ns(member)
                    with archive.extractfile(member) as content, target.open("xb") as output:
                        shutil.copyfileobj(content, output, 1024 * 1024)
                        output.flush()
                        os.utime(target, ns=(mtime_ns, mtime_ns))
                        if target.stat().st_mtime_ns != mtime_ns:
                            raise RuntimeError("Destination cannot preserve the backup file timestamp.")
                        os.fsync(output.fileno())
            if roots != set(VOLUMES):
                raise RuntimeError("Backup is missing a volume root.")
        source.seek(0)
        if digest(source) != checksum:
            raise RuntimeError("Backup changed during restore; nothing was promoted.")
        for stage in stages.values():
            for directory, _, _ in os.walk(stage, topdown=False):
                sync_directory(directory)
        # Only validated, complete content reaches the final paths. A crash during
        # multi-volume promotion leaves a marker that blocks application startup.
        marker = VOLUMES["data"] / RESTORE_MARKER
        with marker.open("xb") as output:
            output.write(b"Restore promotion in progress. Recover from the complete backup into fresh volumes.\n")
            output.flush()
            os.fsync(output.fileno())
        sync_directory(VOLUMES["data"])
        for label, stage in stages.items():
            for path in stage.iterdir():
                destination = VOLUMES[label] / path.name
                if destination.exists():
                    raise RuntimeError("Destination changed during restore; recovery is required.")
                path.rename(destination)
            sync_directory(VOLUMES[label])
        # Retire empty staging directories before clearing the crash marker.
        for label, stage in stages.items():
            stage.rmdir()
            sync_directory(VOLUMES[label])
        marker.unlink()
        sync_directory(VOLUMES["data"])
    print("Restore complete. Cache will be regenerated; start the matching application image.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup", help="Snapshot data and media while the downloader is stopped.")
    command = commands.add_parser("restore", help="Restore into two empty volumes only.")
    command.add_argument("archive", help="Generated filename in /backups; matching .sha256 required.")
    options = parser.parse_args()
    os.umask(0o077)
    try:
        if BACKUPS.is_symlink() or not BACKUPS.is_dir() or not os.path.ismount(BACKUPS):
            raise RuntimeError("Mount an existing private backup directory at /backups.")
        with storage_locks():
            if options.command == "backup":
                backup()
            else:
                restore(options.archive)
    except RuntimeError as exc:
        # These are fixed operational messages, never archive member contents.
        print(f"Storage operation stopped: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, tarfile.TarError, RecursionError):
        # Do not expose archived filenames, paths, credentials or exception data.
        print("Storage operation failed. Stop all writers, check permissions, free space, backup integrity and empty restore targets. Original volumes and completed backups are retained.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
