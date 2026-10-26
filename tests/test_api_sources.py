import http.client
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from ssdl.app import create_app
import tempfile


class ApiSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="ssdl-api-")
        cls.app = create_app(Path(cls.temporary.name))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.app.Handler)
        cls.port_patch = patch.object(cls.app, "PORT", cls.server.server_port)
        cls.port_patch.start()
        cls.log_patch = patch.object(cls.app.Handler, "log_message")
        cls.log_patch.start()
        cls.state_patch = patch.object(cls.app, "_state", return_value={"jobs": [{"title": "private-history-sentinel"}]})
        cls.state_mock = cls.state_patch.start()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.state_patch.stop()
        cls.log_patch.stop()
        cls.port_patch.stop()
        cls.app.close()
        cls.temporary.cleanup()

    def request(self, path, headers=None, *, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()

    def test_local_readers_and_browser_requests_are_allowed(self):
        port = self.server.server_port
        for headers in ({}, {"Origin": f"http://127.0.0.1:{port}", "Sec-Fetch-Site": "same-origin"},
                        {"Host": f"localhost:{port}", "Origin": f"http://localhost:{port}"}):
            with self.subTest(headers=headers):
                status, body = self.request("/api/state", headers)
                self.assertEqual(status, 200)
                self.assertIn("private-history-sentinel", body)
        status, body = self.request("/api/auth/x/setup")
        self.assertEqual(status, 200)
        self.assertIn("extension_id", json.loads(body))

    def test_untrusted_get_is_rejected_before_reading_private_state(self):
        for path in ("/api/state", "/api/identity", "/api/environment", "/api/diagnostics", "/api/auth/x/setup", "/api/jobs/nonexistent/thumbnail", "/api/future-route"):
            for headers in ({"Host": "untrusted.example"}, {"Origin": "https://untrusted.example"},
                            {"Sec-Fetch-Site": "cross-site"}, {"Origin": "null"},
                            {"Origin": "http://[malformed"}, {"Origin": self.app.EXTENSION_ORIGIN}):
                with self.subTest(path=path, headers=headers):
                    before = self.state_mock.call_count
                    status, body = self.request(path, headers)
                    self.assertEqual(status, 403)
                    self.assertEqual(json.loads(body), {"error": "僅允許本機操作"})
                    self.assertEqual(self.state_mock.call_count, before)
                    self.assertNotIn(str(Path.cwd()), body)

    def test_extension_pairing_post_keeps_its_narrow_authorization(self):
        headers = {"Origin": self.app.EXTENSION_ORIGIN,
                   "X-SSDL-Extension": self.app.EXTENSION_ID, "Sec-Fetch-Site": "cross-site",
                   "Content-Type": "application/json"}
        with patch.object(self.app.X_AUTH, "prepare_extension", return_value="fixture-challenge"):
            status, body = self.request("/api/auth/x/prepare", headers, method="POST", body="{}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["token"], "fixture-challenge")
        status, body = self.request("/api/queue/pause", headers, method="POST", body="{}")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
