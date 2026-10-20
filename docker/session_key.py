"""Create an external session key once; never print or overwrite key material."""
import os
from pathlib import Path
import secrets


def main():
    target = Path("/keys/x-session.key")
    if not os.path.ismount(target.parent) or target.parent.is_symlink():
        raise RuntimeError("Mount a private existing key directory at /keys.")
    os.umask(0o077)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(secrets.token_bytes(32))
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    print("Session key created. Keep a separate private backup; the key is not included in data/media snapshots.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError):
        print("Key creation stopped. Check the directory mount, UID 10001 permissions and whether a key already exists. Existing keys are never overwritten.")
        raise SystemExit(1)
