"""Shell-neutral backend identity and a bounded JSON control CLI.

Imports are portable; Windows controls are loaded only by a control action.
Business jobs/settings/auth remain on HTTP. This exposes no HTTP shutdown API.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading

from .version import __version__

CONTROL_VERSION = 1
API_CONTRACT = 1


def scope_key(root: Path) -> str:
    # Preserve the original Windows control namespace; data-root migration is D05.
    return hashlib.sha256(os.path.normcase(str(root.resolve())).encode()).hexdigest()[:32]


def identity(root: Path, port: int, instance: str, *, api_ready: bool, ui_ready: bool) -> dict:
    return {"format_version": CONTROL_VERSION, "service": "ssdl", "instance": instance,
            "scope": scope_key(root), "app_version": __version__, "api_contract": API_CONTRACT,
            "origin": f"http://127.0.0.1:{port}", "port": port,
            "api_ready": api_ready, "ui_ready": ui_ready}


def validate_identity(value, root: Path) -> dict:
    if (not isinstance(value, dict) or value.get("format_version") != CONTROL_VERSION
            or type(value.get("format_version")) is not int
            or value.get("service") != "ssdl" or value.get("scope") != scope_key(root)
            or value.get("app_version") != __version__
            or type(value.get("api_contract")) is not int or value["api_contract"] != API_CONTRACT
            or not isinstance(value.get("instance"), str) or not re.fullmatch(r"[a-f0-9]{32}", value["instance"])
            or type(value.get("port")) is not int or not 1 <= value["port"] <= 65535
            or value.get("origin") != f'http://127.0.0.1:{value["port"]}'
            or value.get("api_ready") is not True or value.get("ui_ready") is not True):
        raise RuntimeError("Background service identity/version is incompatible. Stop it explicitly and start again.")
    return {key: value[key] for key in ("format_version", "service", "instance", "scope", "app_version",
                                      "api_contract", "origin", "port", "api_ready", "ui_ready")}


def read_record(path: Path, root: Path) -> dict:
    try:
        with path.open("rb") as source:
            raw = source.read(4097)
        if len(raw) > 4096:
            raise ValueError()
        return validate_identity(json.loads(raw), root)
    except (OSError, ValueError, TypeError, RecursionError):
        raise RuntimeError("Background service record is missing or invalid. Stop it explicitly and start again.") from None


def probe_service(record: dict, root: Path, *, timeout=2) -> dict:
    """Exact loopback connection, no proxy/redirect, bounded payload and wait."""
    expected = validate_identity(record, root)
    connection = http.client.HTTPConnection("127.0.0.1", expected["port"], timeout=timeout)
    timer = None
    try:
        connection.connect()
        transport = connection.sock
        def expire():
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        connection.request("GET", "/api/identity")
        with connection.getresponse() as response:
            content = response.read(4097)
            if response.status != 200 or len(content) > 4096 or not response.getheader("Content-Type", "").startswith("application/json"):
                raise ValueError()
            actual = validate_identity(json.loads(content), root)
        if actual != expected:
            raise ValueError()
        return actual
    except (OSError, ValueError, TypeError, http.client.HTTPException, RecursionError):
        raise RuntimeError("The recorded backend did not confirm its identity. No service was attached or stopped.") from None
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        connection.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("ensure", "status", "stop-owned", "stop"))
    action = parser.parse_args(argv).action
    try:
        from . import desktop_service
        with redirect_stdout(sys.stderr):
            if action == "ensure":
                result = desktop_service.ensure_backend()
            elif action == "status":
                result = desktop_service.backend_status()
            elif action == "stop-owned":
                payload = sys.stdin.buffer.read(4097)
                if len(payload) > 4096:
                    raise ValueError()
                desktop_service.stop_owned(json.loads(payload))
                result = {"stopped": True}
            else:
                desktop_service.stop()
                result = {"stopped": True}
        print(json.dumps({"format_version": CONTROL_VERSION, "ok": True, "result": result}))
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, RecursionError):
        print(json.dumps({"format_version": CONTROL_VERSION, "ok": False, "error_code": "backend_control_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
