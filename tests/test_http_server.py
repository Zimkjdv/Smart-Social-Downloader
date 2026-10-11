"""Owned loopback fixtures for input deadlines, framing and bounded admission."""
import http.client
import json
import socket
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ssdl.http_api import ApiHandler
from ssdl.http_server import BoundedHTTPServer
from ssdl.x_auth import AuthError, EXTENSION_ID, EXTENSION_ORIGIN


class HttpServerTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(PORT=0, EXTENSION_ID=EXTENSION_ID, EXTENSION_ORIGIN=EXTENSION_ORIGIN,
                                   AuthError=AuthError, X_AUTH=Mock(), state=SimpleNamespace(paused=False),
                                   condition=threading.Condition(), _save_locked=Mock(),
                                   redact_text=lambda value: value, redact_fields=lambda value: value)
        self.app._state = Mock(side_effect=lambda *args, **kwargs: {"paused": self.app.state.paused})
        handler = type("FixtureHandler", (ApiHandler,), {"app": self.app, "log_message": Mock()})
        self.server = BoundedHTTPServer(("127.0.0.1", 0), handler, max_connections=2,
                                        read_seconds=0.35, write_seconds=0.2)
        self.app.PORT = self.server.server_port
        self.server.handle_error = Mock()
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.sockets = []
        self.addCleanup(self.stop)

    def stop(self):
        for connection in self.sockets:
            connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.wait_active(0)
        self.assertFalse(self.thread.is_alive())
        self.server.handle_error.assert_not_called()

    def connect(self):
        connection = socket.create_connection(("127.0.0.1", self.app.PORT), timeout=2)
        self.sockets.append(connection)
        return connection

    def wait_active(self, number):
        deadline = time.monotonic() + 2
        while self.server.active_connections != number and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(self.server.active_connections, number)

    def headers(self, *, path="/api/pause", extra="Content-Length: 100\r\n"):
        return (f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.app.PORT}\r\n"
                f"Origin: http://127.0.0.1:{self.app.PORT}\r\n{extra}\r\n").encode()

    def response(self, connection):
        response = http.client.HTTPResponse(connection)
        response.begin()
        body = response.read()
        return response.status, dict(response.getheaders()), json.loads(body)

    def normal_request(self, path="/api/state", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.app.PORT, timeout=2)
        try:
            connection.request("GET" if body is None else "POST", path,
                               None if body is None else json.dumps(body), headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_partial_header_is_closed_and_releases_connection(self):
        connection = self.connect()
        start = time.monotonic()
        connection.sendall(b"GET /api/state HTTP/1.1\r\nHost: ")
        self.wait_active(1)
        self.assertEqual(connection.recv(100), b"")
        self.assertLess(time.monotonic() - start, 1.5)
        self.wait_active(0)
        self.app._state.assert_not_called()
        self.assertEqual(self.normal_request()[0], 200)

    def test_partial_body_returns_408_without_mutation(self):
        connection = self.connect()
        connection.sendall(self.headers() + b"{")
        status, _, body = self.response(connection)
        self.assertEqual(status, 408)
        self.assertEqual(body, {"error": "請求讀取逾時，請重新操作。"})
        self.app._save_locked.assert_not_called()
        self.assertFalse(self.app.state.paused)
        self.wait_active(0)
        self.assertEqual(self.normal_request()[0], 200)

    def test_trickle_header_cannot_extend_absolute_deadline(self):
        connection = self.connect()
        connection.sendall(b"GET /api/state HTTP/1.1\r\nX-Trickle: ")
        start = time.monotonic()
        for _ in range(6):
            try:
                connection.sendall(b"a")
            except ConnectionError:
                break
            time.sleep(0.04)
        self.wait_active(0)
        self.assertLess(time.monotonic() - start, 0.55)
        try:
            self.assertEqual(connection.recv(100), b"")
        except ConnectionError:
            pass  # Windows may reset instead of returning EOF after deadline.
        self.app._state.assert_not_called()

    def test_body_shares_header_deadline_even_with_trickle(self):
        connection = self.connect()
        connection.sendall(self.headers()[:-2])
        time.sleep(0.20)
        connection.sendall(b"\r\n{")
        start = time.monotonic()
        for _ in range(3):
            try:
                connection.sendall(b" ")
            except ConnectionError:
                break
            time.sleep(0.04)
        self.assertEqual(self.response(connection)[0], 408)
        self.wait_active(0)
        self.assertLess(time.monotonic() - start, 0.3)
        self.app._save_locked.assert_not_called()

    def test_content_length_and_transfer_encoding_are_unambiguous(self):
        invalid = ("", "Content-Length: -1\r\n", "Content-Length: +2\r\n", "Content-Length: abc\r\n",
                   "Content-Length: 100001\r\n", "Content-Length: 9999999999999999999\r\n",
                   "Content-Length: 2\r\nContent-Length: 2\r\n", "Content-Length: 2, 2\r\n",
                   "Content-Length: 2\r\nTransfer-Encoding: chunked\r\n")
        for extra in invalid:
            with self.subTest(extra=extra):
                connection = self.connect()
                connection.sendall(self.headers(extra=extra) + b"{}")
                self.assertEqual(self.response(connection)[0], 400)
                connection.close()
                self.wait_active(0)
        self.app._save_locked.assert_not_called()
        self.assertEqual(self.normal_request("/api/pause", {"paused": True})[0], 200)
        self.assertTrue(self.app.state.paused)

    def test_bad_json_is_generic_and_does_not_echo_payload(self):
        for payload in (b"[]", b'{"paused":NaN}', b'{"paused":Infinity}', b'{"paused":"\xff"}',
                        b"[" * 1100 + b"]" * 1100, b'{"private-sentinel":'):
            with self.subTest(payload_size=len(payload)):
                connection = self.connect()
                connection.sendall(self.headers(extra=f"Content-Length: {len(payload)}\r\n") + payload)
                status, _, body = self.response(connection)
                self.assertEqual(status, 400)
                self.assertEqual(body, {"error": "請求格式不正確"})
                connection.close()
                self.wait_active(0)
        self.app._save_locked.assert_not_called()

    def test_eof_and_client_disconnect_release_capacity(self):
        connection = self.connect()
        connection.sendall(self.headers() + b"{")
        connection.shutdown(socket.SHUT_WR)
        self.assertEqual(self.response(connection)[0], 400)
        self.wait_active(0)
        for payload in (b"GET /api/state HTTP/1.1\r\n", self.headers() + b"{"):
            connection = self.connect()
            connection.sendall(payload)
            self.wait_active(1)
            connection.shutdown(socket.SHUT_RDWR)
            connection.close()
            self.wait_active(0)
        self.app._save_locked.assert_not_called()
        self.assertEqual(self.normal_request()[0], 200)

    def test_overload_returns_503_before_handling_and_then_recovers(self):
        waiting = [self.connect(), self.connect()]
        for connection in waiting:
            connection.sendall(b"GET /api/state HTTP/1.1\r\n")
        self.wait_active(2)
        rejected = self.connect()
        status, headers, body = self.response(rejected)
        self.assertEqual(status, 503)
        self.assertEqual(headers["Retry-After"], "1")
        self.assertEqual(body, {"error": "本機服務忙碌，請稍後重試。"})
        self.assertEqual(self.server.active_connections, 2)
        self.app._state.assert_not_called()
        waiting[0].close()
        self.wait_active(1)
        self.assertEqual(self.normal_request()[0], 200)
        self.assertEqual(self.app._state.call_count, 1)

    def test_shutdown_releases_owned_partial_connections_promptly(self):
        self.server.read_seconds = 10
        connection = self.connect()
        connection.sendall(b"GET /api/state HTTP/1.1\r\n")
        self.wait_active(1)
        start = time.monotonic()
        self.server.shutdown()
        self.server.server_close()
        self.wait_active(0)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_complete_requests_and_extension_cors_keep_working(self):
        self.assertEqual(self.normal_request()[0], 200)
        self.assertEqual(self.normal_request("/api/pause", {"paused": True})[2], {"paused": True})
        self.assertEqual(self.normal_request("/api/pause", {"paused": False})[2], {"paused": False})
        self.app.X_AUTH.prepare_extension.return_value = "fixture-ticket"
        headers = {"Origin": EXTENSION_ORIGIN, "X-SSDL-Extension": EXTENSION_ID}
        status, returned, body = self.normal_request("/api/auth/x/prepare", {}, headers)
        self.assertEqual(status, 200)
        self.assertEqual(returned["Access-Control-Allow-Origin"], EXTENSION_ORIGIN)
        self.assertEqual(body["token"], "fixture-ticket")
        headers["Authorization"] = "Bearer fixture-ticket"
        self.assertEqual(self.normal_request("/api/auth/x/extension", {"cookies": []}, headers)[0], 200)
        self.app.X_AUTH.accept_extension.assert_called_once_with("fixture-ticket", [])
        headers["Origin"] = "https://untrusted.example"
        self.assertEqual(self.normal_request("/api/pause", {"paused": True}, headers)[0], 403)
        self.assertFalse(self.app.state.paused)

    def test_write_timeout_releases_slot_without_handler_error(self):
        entered, release = threading.Event(), threading.Event()
        writes = Mock()
        def send_timeout(handler):
            def timed_out(payload):
                writes(payload)
                self.assertEqual(handler.connection.gettimeout(), self.server.write_seconds)
                raise TimeoutError("synthetic blocked writer")
            # Use an explicit fault instead of assuming Windows loopback buffers
            # cannot absorb a large unread response before the observer runs.
            with patch.object(handler.wfile, "write", side_effect=timed_out):
                entered.set()
                release.wait(timeout=2)
                handler._send(200, b"fixture", "application/octet-stream")
        self.server.RequestHandlerClass.do_GET = send_timeout
        self.addCleanup(release.set)
        connection = self.connect()
        connection.sendall(f"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1:{self.app.PORT}\r\n\r\n".encode())
        self.assertTrue(entered.wait(timeout=1))
        self.wait_active(1)
        release.set()
        self.wait_active(0)
        self.assertEqual(writes.call_count, 1)


if __name__ == "__main__":
    unittest.main()
