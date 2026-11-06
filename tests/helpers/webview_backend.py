"""Synthetic transport/OS dispatch in an admitted, copied GUI fixture only."""
import json
import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from tests.helpers.install_runner import verify_receipt
    token = os.environ.get("SSDL_DESKTOP_FIXTURE_TOKEN", "")
    verify_receipt(root, token)
    from tests.helpers.desktop_fixture import install
    install(root, token)
    # Keep HTTP job/file validation and actual filesystem IO, replacing only
    # the irreversible OS application dispatch. Never touch real associations.
    def opened(path):
        with (root / "data/gui-file-actions.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps({"name": Path(path).name, "directory": Path(path).is_dir()}) + "\n")
    os.startfile = opened
    from ssdl.desktop_service import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
