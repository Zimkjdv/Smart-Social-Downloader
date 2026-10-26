"""Native control probes admitted only in receipt-owned installation copies."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def run(root, token, action):
    from tests.helpers.install_runner import verify_receipt
    verify_receipt(root, token)
    if os.environ.get("SSDL_DESKTOP_FIXTURE_TOKEN") != token:
        raise ValueError("Missing supervisor fixture admission")
    from ssdl import desktop_service as service
    if root != service.ROOT:
        raise ValueError("Supervisor fixture root mismatch")
    if action == "secondary":
        with service.WindowSession() as window:
            if window.primary:
                raise AssertionError("Repeated window acquired ownership")
        return 0
    stale = None
    if service.RECORD.exists():
        stale = json.loads(service.RECORD.read_text(encoding="utf-8")).get("instance")
    result = service.ensure_backend()
    expected = "attached" if action == "attached" else "started"
    if result["ownership"] != expected or service.backend_status()["instance"] != result["instance"]:
        raise AssertionError("Supervisor ownership/identity mismatch")
    if action != "attached" and result["instance"] == stale:
        raise AssertionError("Stale record was attached after backend exit")
    if action == "crash":
        # The outer receipt-owned Job Object deliberately closes after this
        # helper exits. It owns the whole child tree; never terminate by PID.
        return 0
    with service.WindowSession() as window:
        if not window.primary:
            raise AssertionError("First fixture window failed to acquire ownership")
        subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                        "secondary", "--token", token], cwd=root, check=True, timeout=15,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        if not window.consume_focus() or window.consume_focus():
            raise AssertionError("Repeated window did not deliver one focus event")
    if service.backend_status()["instance"] != result["instance"]:
        raise AssertionError("Closing window controls changed the backend")
    attached = service.ensure_backend()
    try:
        service.stop_owned(attached)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Attached shell stopped a backend")
    if action == "cold":
        service.stop_owned(result)
        replacement = service.ensure_backend()
        if replacement["instance"] == result["instance"]:
            raise AssertionError("Restart reused the retired instance identity")
        try:
            service.stop_owned(result)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Stale shell stopped a replacement backend")
        if service.backend_status()["instance"] != replacement["instance"]:
            raise AssertionError("Replacement backend was changed")
        service.stop_owned(replacement)
    (root / "data" / ("supervisor-" + action + ".json")).write_text(json.dumps(
        {"format_version": 1, "identity": True, "ownership": True, "single_window_focus": True,
         "window_close_continues": True, "attached_stop_refused": True}), encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("attached", "cold", "crash", "secondary"))
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    return run(root, args.token, args.action)


if __name__ == "__main__":
    raise SystemExit(main())
