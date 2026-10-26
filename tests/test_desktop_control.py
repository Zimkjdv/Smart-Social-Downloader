"""Portable JSON/HTTP supervisor contracts; no GUI dependency or real sessions."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from ssdl import desktop_control as control
from ssdl import desktop_service as desktop
from tests.helpers.app import IsolatedApp


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.value = control.identity(self.root, 43210, "a" * 32, api_ready=True, ui_ready=True)

    @contextmanager
    def endpoint(self, change=lambda value: value, *, trickle=False):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                value = {**owner.value, "port": self.server.server_port,
                         "origin": f"http://127.0.0.1:{self.server.server_port}"}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                data = json.dumps(change(value)).encode()
                try:
                    if trickle:
                        for byte in data:
                            self.wfile.write(bytes([byte])); self.wfile.flush()
                            time.sleep(.03)
                    else:
                        self.wfile.write(data)
                except (OSError, ValueError):
                    pass
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield {**self.value, "port": server.server_port, "origin": f"http://127.0.0.1:{server.server_port}"}
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_identity_round_trip_and_public_ready_metadata_exclude_paths_and_secrets(self):
        with self.endpoint() as value:
            self.assertEqual(control.probe_service(value, self.root), value)
            record = self.root / "record.json"
            record.write_text(json.dumps({**value, "pid": 12345}), encoding="utf-8")
            self.assertEqual(control.read_record(record, self.root), value)
        self.assertNotIn(str(self.root), json.dumps(value))

    def test_record_rejects_foreign_scope_version_origin_and_boolean_numbers(self):
        for values in ({"scope": "b" * 32}, {"instance": "invalid"}, {"format_version": True},
                       {"port": True}, {"origin": "https://foreign.example"}, {"api_contract": True},
                       {"app_version": "future"}, {"api_ready": False}, {"ui_ready": False}):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                control.validate_identity({**self.value, **values}, self.root)
        record = self.root / "record.json"
        for data in (b"[]", b"{}", b"x" * 4097, b"\xff"):
            record.write_bytes(data)
            with self.assertRaises(RuntimeError):
                control.read_record(record, self.root)

    def test_an_arbitrary_200_or_replacement_instance_is_not_a_backend(self):
        for change in (lambda value: {}, lambda value: {**value, "instance": "b" * 32},
                       lambda value: {**value, "scope": "b" * 32}):
            with self.endpoint(change) as value, self.assertRaises(RuntimeError):
                control.probe_service(value, self.root)

    def test_trickle_body_cannot_extend_identity_deadline(self):
        with self.endpoint(trickle=True) as value:
            start = time.monotonic()
            with self.assertRaises(RuntimeError):
                control.probe_service(value, self.root, timeout=.15)
            self.assertLess(time.monotonic() - start, .8)

    def test_ui_readiness_survives_unhealthy_engines_and_origin_guard_still_applies(self):
        fixture = self.enterContext(IsolatedApp())
        app = fixture.app
        app.STATIC = Path(__file__).resolve().parents[1] / "static"
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(app, "PORT", server.server_port), patch.object(app, "_started", True), \
                 patch.object(app.Handler, "log_message"):
                def get(path, headers=None):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    try:
                        connection.request("GET", path, headers=headers or {})
                        response = connection.getresponse()
                        return response.status, json.loads(response.read())
                    finally:
                        connection.close()
                self.assertEqual(get("/api/health")[0], 503)
                status, value = get("/api/identity")
                self.assertEqual(status, 200)
                self.assertTrue(value["api_ready"] and value["ui_ready"])
                self.assertEqual(get("/api/identity", {"Origin": "null"})[0], 403)
                self.assertEqual(get("/api/identity", {"Origin": "https://foreign.example"})[0], 403)
                app.state.shutdown.set()
                self.assertEqual(get("/api/identity")[0], 503)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_cli_emits_single_versioned_json_without_backend_or_browser_output(self):
        output = io.StringIO()
        with patch.object(desktop, "ensure_backend", return_value={**self.value, "ownership": "started"}), \
             patch("sys.stdout", output):
            self.assertEqual(control.main(["ensure"]), 0)
        self.assertEqual(json.loads(output.getvalue())["result"]["instance"], "a" * 32)
        output = io.StringIO()
        with patch.object(desktop, "backend_status", side_effect=RuntimeError("private-detail")), patch("sys.stdout", output):
            self.assertEqual(control.main(["status"]), 1)
        self.assertEqual(json.loads(output.getvalue()), {"format_version": 1, "ok": False, "error_code": "backend_control_failed"})
        self.assertNotIn("private-detail", output.getvalue())
