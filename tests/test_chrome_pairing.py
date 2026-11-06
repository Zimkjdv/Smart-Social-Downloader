"""Harness boundaries only; mocks do not establish real Chrome acceptance."""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import check_chrome_pairing as gate


class ChromePairingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.report = self.root / "receipt.json"

    def test_explicit_custom_port_and_report_boundary(self):
        with patch.object(gate, "ROOT", self.root):
            self.assertEqual(gate.validate(8877, self.root / "data/receipt.json"), self.root / "data/receipt.json")
            for port in (True, 0, 8765, 65536, "8877"):
                with self.subTest(port=port), self.assertRaises(ValueError):
                    gate.validate(port, self.root / "data/receipt.json")
            for path in (self.root / "receipt.json", self.root / "data/receipt.txt", self.root / "data/../outside.json"):
                with self.assertRaises(ValueError):
                    gate.validate(8877, path)

    def test_fixture_normalizes_temporary_directory_spelling(self):
        # CI TEMP can use a Windows 8.3 alias. Exercise this same assertion
        # through a real, equivalent lexical spelling without requiring 8.3.
        create_temporary = tempfile.TemporaryDirectory
        class AlternateSpelling:
            def __init__(self):
                self.scope = create_temporary()

            def __enter__(self):
                root = Path(self.scope.__enter__()).resolve()
                marker = root / "alternate-spelling"
                marker.mkdir()
                if not root.is_dir():
                    raise AssertionError("Temporary scope disappeared before validation")
                return str(marker / "..")

            def __exit__(self, *error):
                return self.scope.__exit__(*error)

        case = ChromePairingTests("test_explicit_custom_port_and_report_boundary")
        result = unittest.TestResult()
        with patch.object(tempfile, "TemporaryDirectory", AlternateSpelling):
            case.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.errors, "Fixture failed before reaching its boundary assertion")
        self.assertTrue(result.wasSuccessful(), "Equivalent temporary path spelling broke the boundary contract")

    def test_main_requires_real_login_opt_in_before_storage(self):
        with patch.object(gate, "SessionStorage") as storage, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as error:
                gate.main([])
        self.assertEqual(error.exception.code, 2)
        storage.assert_not_called()

    def test_snapshot_does_not_read_or_publish_session_material(self):
        state = {"phase": "connected", "connected": True, "busy": False, "storage_mode": "dpapi",
                 "cookies": "SYNTHETIC_SECRET", "refresh_token": "SYNTHETIC_SECRET", "message": "SYNTHETIC_SECRET"}
        x = Mock(secret_file=self.root / "x-auth.bin")
        pixiv = Mock(path=self.root / "pixiv-session.bin")
        x.status.return_value = pixiv.status.return_value = state
        result = gate.snapshot(SimpleNamespace(X_AUTH=x, PIXIV_AUTH=pixiv))
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(result))
        x.cookies.assert_not_called()
        pixiv.token.assert_not_called()
        self.assertTrue(result["x"]["connected"])

    def test_operator_notes_are_explicit_and_not_arbitrary_transcripts(self):
        session = gate.PairingSession(self.root, 8877, self.report)
        session.command("note connector-reloaded-1.2.0")
        self.assertEqual(json.loads(self.report.read_text())["operator_notes"], ["connector-reloaded-1.2.0"])
        for command in ("note SYNTHETIC_SECRET", "note", "expire-now", "prepare-x", "set-port 8765"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                session.command(command)
        self.assertNotIn("SYNTHETIC_SECRET", self.report.read_text())

    def test_expiry_preparation_keeps_ticket_private_and_uses_real_deadline(self):
        session = gate.PairingSession(self.root, 8877, self.report)
        session.app = Mock()
        session.app.X_AUTH.prepare_extension.return_value = "SYNTHETIC_PRIVATE_TICKET"
        with patch.object(gate.time, "monotonic", return_value=100):
            self.assertEqual(session.command("prepare-x"), {"waiting": True, "seconds": 600})
        session.app.X_AUTH.prepare_extension.assert_called_once_with()
        self.assertEqual(session.expiry_started, 100)
        self.assertNotIn("SYNTHETIC_PRIVATE_TICKET", self.report.read_text())

    def test_busy_exchange_refuses_restart_but_final_cleanup_cancels_it(self):
        session = gate.PairingSession(self.root, 8877, self.report)
        app, server, thread = Mock(), Mock(), Mock()
        app.PIXIV_AUTH.status.return_value = {"busy": True}
        session.app, session.server, session.thread = app, server, thread
        with self.assertRaises(ValueError):
            session.offline()
        server.shutdown.assert_not_called()
        order = []
        server.shutdown.side_effect = lambda: order.append("stop_accepting")
        app.close.side_effect = lambda: order.append("cancel_save")
        server.server_close.side_effect = lambda: order.append("close_sockets")
        session.offline(force=True)
        self.assertEqual(order, ["stop_accepting", "cancel_save", "close_sockets"])
        self.assertIsNone(session.app)
