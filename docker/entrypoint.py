"""Container-only listener and termination handling; desktop defaults stay local."""
from pathlib import Path
import os
import signal
import sys

from runtime import prepare_storage, storage_locks

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ssdl.app import main


def terminate(signum, frame):
    # Route Docker stop through the existing app/server context-manager cleanup.
    raise KeyboardInterrupt


if __name__ == "__main__":
    os.umask(0o077)
    signal.signal(signal.SIGTERM, terminate)
    try:
        prepare_storage()
        with storage_locks():
            code = main(bind_host="0.0.0.0")
    except (OSError, RuntimeError) as exc:
        print(f"Container storage startup failed: {exc}", file=sys.stderr)
        code = 1
    raise SystemExit(code)
