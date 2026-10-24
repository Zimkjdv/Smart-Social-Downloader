"""Pixiv OAuth lifecycle using only invented exchanges and disposable keys."""
import base64
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
import os
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from ssdl import pixiv_auth
from ssdl.app import create_app
from ssdl.session_storage import AuthError
from tests.helpers.pixiv_auth import AuthFixture, TOKEN, NEXT_TOKEN, CODE


class PixivAuthTests(unittest.TestCase):
    def test_custom_port_pairing_and_pkce_claim_are_bound_and_single_use(self):
        with AuthFixture() as fixture:
            result, ticket = fixture.begin()
            self.assertEqual(urlsplit(result["pairing_url"]).netloc, "127.0.0.1:18991")
            self.assertFalse(result["opened"])
            claimed = fixture.auth.claim(ticket)
            query = parse_qs(urlsplit(claimed["authorization_url"]).query)
            expected = base64.urlsafe_b64encode(hashlib.sha256(fixture.auth._pending[0].encode()).digest()).rstrip(b"=").decode()
            self.assertEqual(query["code_challenge"], [expected])
            self.assertEqual(query["code_challenge_method"], ["S256"])
            with self.assertRaises(AuthError):
                fixture.auth.claim(ticket)
            fixture.exchange.assert_not_called()

    def test_wrong_unclaimed_and_obsolete_tickets_do_not_exchange(self):
        with AuthFixture() as fixture:
            _, first = fixture.begin()
            with self.assertRaises(AuthError):
                fixture.auth.connect(ticket=first, code=CODE)
            _, current = fixture.begin()
            for ticket in (first, "x" * 43, "bad", None):
                with self.subTest(ticket_type=type(ticket).__name__), self.assertRaises(AuthError):
                    fixture.auth.claim(ticket)
            fixture.auth.claim(current)
            fixture.exchange.assert_not_called()

    def test_expired_pairing_clears_pending_and_rejects_callback(self):
        with AuthFixture() as fixture:
            with patch.object(pixiv_auth.time, "monotonic", return_value=1000):
                _, ticket = fixture.begin()
                fixture.auth.claim(ticket)
            with patch.object(pixiv_auth.time, "monotonic", return_value=1601):
                state = fixture.auth.status()
                self.assertFalse(state["pending"])
                self.assertEqual(state["attempt_phase"], "expired")
                with self.assertRaises(AuthError):
                    fixture.auth.connect(ticket=ticket, code=CODE)
            fixture.exchange.assert_not_called()

    def test_success_uses_stdin_only_and_persists_encrypted_refresh_token(self):
        with AuthFixture() as fixture:
            connected = Mock()
            fixture.auth.on_connected = connected
            self.assertTrue(fixture.connect()["connected"])
            call = fixture.exchange.call_args
            values = json.loads(call.kwargs["input"])
            self.assertEqual(values["code"], CODE)
            self.assertNotIn(CODE, repr(call.args))
            self.assertNotIn(values["verifier"], repr(call.args))
            self.assertNotIn(TOKEN.encode(), fixture.auth.path.read_bytes())
            self.assertNotIn(TOKEN, repr(fixture.auth.status()))
            connected.assert_called_once()
            restored = fixture.manager()
            restored.restore()
            self.assertEqual(restored.token(), TOKEN)

    def test_failed_exchange_keeps_previous_session_and_consumes_attempt(self):
        with AuthFixture() as fixture:
            fixture.connect()
            saved = fixture.auth.path.read_bytes()
            _, ticket = fixture.begin()
            fixture.auth.claim(ticket)
            fixture.exchange.return_value = SimpleNamespace(returncode=1, stdout=b"{}")
            with self.assertRaises(AuthError):
                fixture.auth.connect(ticket=ticket, code=CODE)
            self.assertEqual(fixture.auth.token(), TOKEN)
            self.assertEqual(fixture.auth.path.read_bytes(), saved)
            count = fixture.exchange.call_count
            with self.assertRaises(AuthError):
                fixture.auth.connect(ticket=ticket, code=CODE)
            self.assertEqual(fixture.exchange.call_count, count)
            self.assertEqual(fixture.auth.status()["attempt_phase"], "failed")

    def test_disconnect_during_exchange_rejects_late_result(self):
        with AuthFixture() as fixture:
            connected = Mock()
            fixture.auth.on_connected = connected
            _, ticket = fixture.begin()
            fixture.auth.claim(ticket)
            def late(*args, **kwargs):
                with self.assertRaises(AuthError):
                    fixture.auth.begin()
                fixture.auth.disconnect()
                return fixture.response(TOKEN)
            fixture.exchange.side_effect = late
            with self.assertRaises(AuthError):
                fixture.auth.connect(ticket=ticket, code=CODE)
            self.assertFalse(fixture.auth.path.exists())
            self.assertFalse(fixture.auth.status()["busy"])
            self.assertFalse(fixture.auth.status()["connected"])
            connected.assert_not_called()

    def test_wrong_key_and_corrupt_payload_preserve_original_file(self):
        with AuthFixture() as fixture:
            fixture.connect()
            saved = fixture.auth.path.read_bytes()
            other = fixture.root / "wrong-key.bin"
            other.write_bytes(b"k" * 32)
            with patch.dict(os.environ, SSDL_X_KEY_FILE=str(other)):
                wrong = fixture.manager()
                wrong.restore()
                self.assertEqual(wrong.status()["phase"], "expired")
                self.assertFalse(wrong.status()["connected"])
            self.assertEqual(fixture.auth.path.read_bytes(), saved)
            good = fixture.manager()
            good.restore()
            self.assertEqual(good.token(), TOKEN)
            fixture.auth.path.write_bytes(b"synthetic unreadable payload")
            good = fixture.manager()
            good.restore()
            self.assertEqual(fixture.auth.path.read_bytes(), b"synthetic unreadable payload")
            self.assertFalse(good.status()["connected"])

    def test_memory_mode_never_saves_or_restores_credentials(self):
        with AuthFixture(memory=True) as fixture:
            self.assertTrue(fixture.connect()["connected"])
            self.assertEqual(fixture.auth.status()["storage_mode"], "memory")
            self.assertFalse(fixture.auth.path.exists())
            restored = fixture.manager()
            restored.restore()
            self.assertFalse(restored.status()["connected"])

    def test_rejected_current_token_does_not_reappear_after_restart(self):
        with AuthFixture() as fixture:
            fixture.connect()
            fixture.auth.invalidate(TOKEN)
            self.assertFalse(fixture.auth.status()["connected"])
            restored = fixture.manager()
            restored.restore()
            self.assertFalse(restored.status()["connected"])
            self.assertEqual(restored.status()["phase"], "expired")
            self.assertNotIn(TOKEN, fixture.auth.storage.load(fixture.auth.path).decode())
            fixture.exchange.return_value = fixture.response(NEXT_TOKEN)
            fixture.connect()
            restored = fixture.manager()
            restored.restore()
            self.assertEqual(restored.token(), NEXT_TOKEN)

    def test_old_failure_does_not_invalidate_a_newly_connected_session(self):
        with AuthFixture() as fixture:
            fixture.connect()
            fixture.exchange.return_value = fixture.response(NEXT_TOKEN)
            fixture.connect()
            fixture.auth.invalidate(TOKEN)
            self.assertEqual(fixture.auth.token(), NEXT_TOKEN)
            restored = fixture.manager()
            restored.restore()
            self.assertEqual(restored.token(), NEXT_TOKEN)

    def test_save_failure_keeps_old_session_and_unlocks_future_attempts(self):
        with AuthFixture() as fixture:
            fixture.connect()
            saved = fixture.auth.path.read_bytes()
            fixture.exchange.return_value = fixture.response(NEXT_TOKEN)
            with patch.object(fixture.auth.storage, "save", side_effect=OSError("synthetic write denied")):
                with self.assertRaises(AuthError):
                    fixture.connect()
            self.assertEqual(fixture.auth.token(), TOKEN)
            self.assertEqual(fixture.auth.path.read_bytes(), saved)
            self.assertFalse(fixture.auth.status()["busy"])
            self.assertTrue(fixture.connect()["connected"])

    def test_invalidation_storage_failures_do_not_terminate_the_queue(self):
        with AuthFixture() as fixture:
            fixture.connect()
            with patch.object(fixture.auth.storage, "save", side_effect=OSError("synthetic write denied")):
                fixture.auth.invalidate(TOKEN)
            self.assertFalse(fixture.auth.path.exists())
            fixture.connect()
            before = fixture.auth.path.read_bytes()
            with patch.object(fixture.auth.storage, "save", side_effect=AuthError("synthetic encryption unavailable")), \
                 patch.object(type(fixture.auth.path), "unlink", side_effect=PermissionError), \
                 self.assertLogs("root", level="WARNING") as captured:
                fixture.auth.invalidate(TOKEN)
            self.assertFalse(fixture.auth.status()["connected"])
            self.assertEqual(fixture.auth.path.read_bytes(), before)
            self.assertNotIn(TOKEN, repr(captured.output))

    def test_callback_parser_accepts_only_supported_exact_hosts_and_one_code(self):
        self.assertEqual(pixiv_auth.callback_code("pixiv://account/login?code=" + CODE), CODE)
        for value in ("https://evil.example/callback?code=" + CODE,
                      "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback?code=" + CODE + "&code=OTHER",
                      "https://app-api.pixiv.net:0/web/v1/users/auth/pixiv/callback?code=" + CODE):
            with self.subTest(value_type="synthetic callback"), self.assertRaises(AuthError):
                pixiv_auth.callback_code(value)


class PixivAuthApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = self.enterContext(AuthFixture())
        self.app = create_app(self.fixture.root, download_dir=self.fixture.root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.Handler)
        self.app.PORT = self.server.server_port
        self.fixture.auth = self.fixture.manager(port=self.server.server_port)
        self.app.PIXIV_AUTH = self.fixture.auth
        self.enterContext(patch.object(self.app.Handler, "log_message"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.app.close()

    def post(self, path, data, headers=None):
        values = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.app.PORT}"}
        values.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.app.PORT, timeout=5)
        try:
            connection.request("POST", path, body=json.dumps(data), headers=values)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def extension_headers(self):
        return {"Origin": self.app.EXTENSION_ORIGIN, "X-SSDL-Extension": self.app.EXTENSION_ID}

    def test_claim_and_callback_require_connector_source_and_correct_host(self):
        _, ticket = self.fixture.begin()
        for headers in ({}, {"Origin": "https://foreign.example"},
                        {"Origin": self.app.EXTENSION_ORIGIN, "X-SSDL-Extension": "wrong"},
                        dict(self.extension_headers(), Host="127.0.0.1:1")):
            with self.subTest(source_type="rejected"), patch.object(self.fixture.auth, "claim", wraps=self.fixture.auth.claim) as claim:
                self.assertEqual(self.post("/api/auth/pixiv/claim", {"ticket": ticket}, headers)[0], 403)
                claim.assert_not_called()
        self.assertEqual(self.post("/api/auth/pixiv/claim", {"ticket": ticket}, self.extension_headers())[0], 200)
        status, data = self.post("/api/auth/pixiv/callback", {"ticket": ticket, "code": CODE}, self.extension_headers())
        self.assertEqual(status, 200)
        self.assertTrue(data["pixiv_auth"]["connected"])
        self.assertNotIn(TOKEN, repr(data))

    def test_foreign_begin_disconnect_and_wrong_callback_shape_are_rejected(self):
        for action in ("begin", "disconnect", "connect"):
            self.assertEqual(self.post("/api/auth/pixiv/" + action, {}, {"Origin": "https://foreign.example"})[0], 403)
        _, ticket = self.fixture.begin()
        self.assertEqual(self.post("/api/auth/pixiv/claim", {"ticket": ticket}, self.extension_headers())[0], 200)
        self.assertEqual(self.post("/api/auth/pixiv/callback", {"ticket": ticket, "code": CODE, "extra": True}, self.extension_headers())[0], 400)
        self.fixture.exchange.assert_not_called()

    def test_cancelled_api_callback_cannot_reconnect(self):
        status, result = self.post("/api/auth/pixiv/begin", {})
        self.assertEqual(status, 200)
        ticket = parse_qs(urlsplit(result["pairing_url"]).fragment)["ticket"][0]
        self.assertEqual(self.post("/api/auth/pixiv/claim", {"ticket": ticket}, self.extension_headers())[0], 200)
        self.assertEqual(self.post("/api/auth/pixiv/disconnect", {})[0], 200)
        self.assertEqual(self.post("/api/auth/pixiv/callback", {"ticket": ticket, "code": CODE}, self.extension_headers())[0], 400)
        self.fixture.exchange.assert_not_called()
