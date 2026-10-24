"""Opt-in, operator-driven ordinary-Chrome pairing on an isolated Windows service.

The browser and installed connector are real. No Cookie/OAuth transport, DPAPI,
clock, permission, or auth handler is mocked. This never opens privileged Chrome
pages or controls browser installation. The operator completes those UI steps.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.app import create_app
from ssdl.http_server import BoundedHTTPServer
from ssdl.session_storage import SessionStorage
from ssdl.x_auth import _dpapi
from tools.package_source import SOURCE_GLOBS, _safe_path

AUTH_ROUTES = frozenset("/api/auth/" + name for name in (
    "x/prepare", "x/extension", "x/connect", "x/disconnect",
    "pixiv/begin", "pixiv/claim", "pixiv/callback", "pixiv/connect", "pixiv/disconnect"))


def validate(port, report):
    if type(port) is not int or not 1 <= port <= 65535 or port == 8765:
        raise ValueError("Use an explicit non-default port")
    report = report.resolve()
    if report.suffix != ".json" or not report.is_relative_to((ROOT / "data").resolve()):
        raise ValueError("Report must be a JSON file under data")
    return report


def snapshot(app):
    """Only allowlisted metadata leaves this process; never return session values."""
    result = {}
    for name, manager, path in (("x", app.X_AUTH, app.X_AUTH.secret_file),
                                ("pixiv", app.PIXIV_AUTH, app.PIXIV_AUTH.path)):
        state = manager.status()
        result[name] = {key: state[key] for key in
                       ("connected", "busy", "phase", "pending", "attempt_phase", "storage_mode") if key in state}
        result[name]["encrypted_file_present"] = path.is_file()
    return result


def write_report(report, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                         dir=report.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
        temporary.replace(report)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class PairingSession:
    def __init__(self, root, port, report):
        self.root, self.port, self.report = root, port, report
        self.app = self.server = self.thread = None
        self.lock = threading.Lock()
        self.evidence = {"schema": 1, "mode": "ordinary_chrome_operator", "closed": False,
                         "port": port, "events": [], "operator_notes": []}
        self.expiry_started = None

    def save(self):
        with self.lock:
            write_report(self.report, self.evidence)

    def event(self, name, **fields):
        with self.lock:
            self.evidence["events"].append({"event": name,
                "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields})
        self.save()

    def online(self):
        if self.app is not None:
            raise ValueError("Service is already online")
        app = create_app(self.root, port=self.port, download_dir=self.root / "downloads")
        owner = self
        class Handler(app.Handler):
            def log_message(self, *args):
                pass  # Never write request headers, URLs, tickets or payloads.

            def _json(self, code, value):
                path = urlparse(self.path).path
                if self.command == "POST" and path in AUTH_ROUTES:
                    agent = re.search(r"Chrome/([0-9.]+)", self.headers.get("User-Agent", ""))
                    owner.event("auth_http", route=path, status=code,
                                extension_origin=self.headers.get("Origin") == app.EXTENSION_ORIGIN,
                                extension_id=self.headers.get("X-SSDL-Extension") == app.EXTENSION_ID,
                                chrome_version=agent[1] if agent else "")
                return super()._json(code, value)

            def do_POST(self):
                path = urlparse(self.path).path
                if path.startswith("/api/jobs"):
                    return self._json(403, {"error": "Pairing acceptance does not run downloads"})
                return super().do_POST()
        try:
            server = BoundedHTTPServer(("127.0.0.1", self.port), Handler)
            app.start()
        except BaseException:
            if "server" in locals():
                server.server_close()
            app.close()
            raise
        self.app, self.server = app, server
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()
        self.event("online", state=snapshot(app))

    def offline(self, *, force=False):
        if self.app is None:
            return
        app, server, thread = self.app, self.server, self.thread
        if not force and (app.PIXIV_AUTH.status()["busy"] or app.X_AUTH.status()["busy"]):
            raise ValueError("Wait for the current authorization exchange")
        server.shutdown()
        app.close()  # Cancel late exchange/save before the temporary scope is removed.
        server.server_close()
        thread.join(timeout=5)
        self.app = self.server = self.thread = None
        self.event("offline")

    def command(self, command):
        if command == "status":
            state = snapshot(self.app) if self.app else {"online": False}
            if self.expiry_started is not None:
                state["real_expiry_elapsed_seconds"] = round(time.monotonic() - self.expiry_started, 1)
            self.event("status", state=state)
            return state
        if command in {"online", "offline", "restart"}:
            if command != "online":
                self.offline()
            if command != "offline":
                self.online()
            return {"online": self.app is not None}
        if command == "prepare-x" and self.app is not None:
            self.app.X_AUTH.prepare_extension()  # Keep the 600-second ticket private.
            self.expiry_started = time.monotonic()
            self.event("real_expiry_started", seconds=600)
            return {"waiting": True, "seconds": 600}
        if command.startswith("note "):
            note = command[5:]
            if note not in {"connector-reloaded-1.2.0", "permissions-reviewed", "port-configured",
                            "chrome-restarted", "port-restored"}:
                raise ValueError("Unknown operator note")
            self.evidence["operator_notes"].append(note)
            self.save()
            return {"noted": note}
        raise ValueError("Unknown command or offline service")


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--report", type=Path, default=ROOT / "data/chrome-pairing.json")
    parser.add_argument("--allow-real-login", action="store_true",
                        help="Allow the installed connector to save real login into the temporary DPAPI scope")
    args = parser.parse_args(arguments)
    if not args.allow_real_login:
        parser.error("--allow-real-login explicitly opts into ordinary-Chrome login acceptance")
    report = validate(args.port, args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    write_report(report, {"schema": 1, "mode": "ordinary_chrome_operator", "closed": False,
                          "phase": "preflight", "port": args.port})
    if os.name != "nt" or os.environ.get("SSDL_CONTAINER") == "1" or "SSDL_X_KEY_FILE" in os.environ:
        parser.error("Run under the ordinary Windows user with native DPAPI")
    storage = SessionStorage(windows_protect=_dpapi)
    probe = os.urandom(32)
    if storage.mode != "dpapi" or storage.unseal(storage.seal(probe)) != probe:
        raise ValueError("Native DPAPI check failed")
    with tempfile.TemporaryDirectory(prefix="ssdl-chrome-pairing-") as temporary:
        root = Path(temporary).resolve()
        for folder in ("static", "chrome-extension"):
            (root / folder).mkdir()
            for pattern in SOURCE_GLOBS[folder]:
                for source in (ROOT / folder).glob(pattern):
                    _safe_path(source, ROOT)
                    (root / folder / source.name).write_bytes(source.read_bytes())
        session = PairingSession(root, args.port, report)
        session.evidence["dpapi_roundtrip"] = True
        try:
            session.online()
            print(json.dumps({"ready": True, "url": f"http://127.0.0.1:{args.port}/",
                              "dpapi_roundtrip": True}), flush=True)
            print("Commands: status, prepare-x, offline, online, restart, note <step>, stop", flush=True)
            for line in sys.stdin:
                command = line.strip()
                if command == "stop":
                    break
                try:
                    print(json.dumps(session.command(command)), flush=True)
                except ValueError:
                    print(json.dumps({"command_rejected": True}), flush=True)
        finally:
            session.offline(force=True)
    # Scope removal includes temporary encrypted sessions; report has metadata only.
    session.evidence.update(closed=True, temporary_scope_removed=not root.exists())
    session.save()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError):
        print("Pairing acceptance stopped; verify the Windows user, DPAPI and custom port.", file=sys.stderr)
        raise SystemExit(1)
