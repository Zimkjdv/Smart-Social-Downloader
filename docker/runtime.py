"""Fixed container storage boundaries and cooperative exclusive ownership."""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import stat
import tempfile

VOLUMES = {"data": Path("/app/data"), "media": Path("/downloads")}
CACHE = Path("/app/cache")
LOCK_NAME = ".ssdl.lock"
RESTORE_MARKER = ".ssdl-restore-incomplete"


def require_volume(directory: Path) -> None:
    if (directory.is_symlink() or directory.resolve() != directory
            or not directory.is_dir() or not os.path.ismount(directory)):
        raise RuntimeError(f"Mount a dedicated writable volume at {directory} before starting.")


@contextmanager
def storage_locks():
    """Downloader and offline maintenance must own both volumes, in one order."""
    import fcntl

    with ExitStack() as stack:
        for directory in VOLUMES.values():
            require_volume(directory)
            descriptor = os.open(directory / LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            stream = stack.enter_context(os.fdopen(descriptor, "r+b"))
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise RuntimeError("Storage lock is not a private regular file.")
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Storage is in use. Stop the downloader and other maintenance containers first.") from None
            if (os.path.lexists(directory / RESTORE_MARKER)
                    or any(path.name.startswith(".ssdl-restore-") for path in directory.iterdir())):
                raise RuntimeError("An interrupted restore needs recovery; use fresh volumes and the complete backup.")
        yield


def prepare_storage() -> None:
    expected = {"SSDL_CACHE_DIR": CACHE, "XDG_CACHE_HOME": CACHE,
                "SSDL_DOWNLOAD_DIR": VOLUMES["media"], "SSDL_MEDIA_ROOT": VOLUMES["media"]}
    if any(os.environ.get(name) != str(path) for name, path in expected.items()):
        raise RuntimeError("Container storage settings must match the documented data/cache/media mounts.")
    for directory in (*VOLUMES.values(), CACHE):
        require_volume(directory)
        # Check effective access as the non-root application user, without chown.
        with tempfile.TemporaryFile(prefix=".ssdl-write-", dir=directory) as stream:
            stream.write(b"ssdl")
            stream.flush()
            os.fsync(stream.fileno())
