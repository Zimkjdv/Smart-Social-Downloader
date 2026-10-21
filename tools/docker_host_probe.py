"""Receipt-guarded actions on newly created host bind mounts only."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile

KEYS, BACKUPS = Path('/keys'), Path('/backups')
MARKER = '.ssdl-acceptance'


def require(value):
    if not value:
        raise RuntimeError('fixture condition failed')


def roots():
    for directory in (KEYS, BACKUPS):
        require(os.path.ismount(directory) and not directory.is_symlink()
                and (directory / MARKER).read_text() == os.environ['SSDL_DOCKER_ACCEPTANCE'])
    return KEYS, BACKUPS


def main(action):
    require(sys.platform == 'linux' and re.fullmatch(r'[0-9a-f]{32}', os.environ.get('SSDL_DOCKER_ACCEPTANCE', '')))
    sys.path[:0] = ['/app', '/app/docker']
    os.umask(0o077)
    if action in {'initialize', 'return-owner'}:
        require(os.getuid() == 0)
        for directory in roots():
            if action == 'initialize':
                require({path.name for path in directory.iterdir()} == {MARKER})
                if os.environ.get('SSDL_HOST_POSIX') == '1':
                    os.chown(directory, 10001, 10001)
                    directory.chmod(0o700)
            else:
                uid, gid = map(int, sys.argv[2:4])
                require(0 <= uid < 2**31 and 0 <= gid < 2**31)
                files = list(directory.iterdir())
                require(len(files) <= 8)
                for path in files:
                    info = path.lstat()
                    if path.name == 'absent.key' and stat.S_ISDIR(info.st_mode) and not any(path.iterdir()):
                        path.rmdir()  # Desktop can create an empty source directory for a missing secret.
                        continue
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                            and (path.name in {MARKER, 'x-session.key'}
                                 or re.fullmatch(r'ssdl-[A-Za-z0-9-]+\.tar(?:\.sha256)?', path.name)))
                    if os.environ.get('SSDL_HOST_POSIX') == '1':
                        os.chown(path, uid, gid)
                if os.environ.get('SSDL_HOST_POSIX') == '1':
                    os.chown(directory, uid, gid)
        return {}
    require(os.getuid() == 10001)
    if action == 'secret-readonly':
        path = Path('/run/secrets/x_session_key')
        require(path.is_file() and len(path.read_bytes()) == 32)
        try:
            descriptor = os.open(path, os.O_WRONLY)
        except OSError:
            return {'readonly': True}
        os.close(descriptor)
        raise RuntimeError('runtime key is writable')
    roots()
    key = KEYS / 'x-session.key'
    if action == 'missing-key':
        absent = KEYS / 'absent.key'
        require(not absent.is_symlink())
        if not absent.exists():
            return {'kind': 'absent'}
        require(absent.is_dir() and not any(absent.iterdir()))
        return {'kind': 'directory'}
    if action == 'session-hash':
        session = Path('/app/data/x-auth.bin').read_bytes()
        from ssdl.session_storage import MAGIC
        require(session.startswith(MAGIC))
        return {'sha256': hashlib.sha256(session).hexdigest()}
    if action == 'key-info':
        content = key.read_bytes()
        info = key.stat()
        require(len(content) == 32 and stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        if os.environ.get('SSDL_HOST_POSIX') == '1':
            require(info.st_uid == info.st_gid == 10001 and stat.S_IMODE(info.st_mode) == 0o600)
            for directory in roots():
                info = directory.stat()
                require(info.st_uid == info.st_gid == 10001 and stat.S_IMODE(info.st_mode) == 0o700)
        return {'sha256': hashlib.sha256(content).hexdigest()}
    if action == 'archive':
        from ssdl.session_storage import MAGIC
        archives = list(BACKUPS.glob('ssdl-*.tar'))
        require(len(archives) == 1)
        archive = archives[0]
        require(re.fullmatch(r'ssdl-[A-Za-z0-9-]+\.tar', archive.name) and archive.stat().st_size < 4 * 1024 * 1024)
        content = archive.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        require((BACKUPS / (archive.name + '.sha256')).read_text().strip() == checksum
                and key.read_bytes() not in content)
        with tarfile.open(archive) as source:
            names = source.getnames()
            require('data/x-auth.bin' in names and not any('x-session.key' in name for name in names))
            with source.extractfile('data/x-auth.bin') as saved:
                require(saved.read(len(MAGIC)) == MAGIC)
        if os.environ.get('SSDL_HOST_POSIX') == '1':
            for path in (archive, BACKUPS / (archive.name + '.sha256')):
                info = path.stat()
                require(info.st_uid == info.st_gid == 10001 and stat.S_IMODE(info.st_mode) == 0o600)
        return {'archive': archive.name, 'sha256': checksum}
    raise RuntimeError('unknown fixture action')


if __name__ == '__main__':
    try:
        print(json.dumps({'receipt': os.environ.get('SSDL_DOCKER_ACCEPTANCE'), 'result': main(sys.argv[1])}))
    except Exception:
        print('{"fixture_error":true}')
        raise SystemExit(1)
