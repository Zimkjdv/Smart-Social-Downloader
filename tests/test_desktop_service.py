"""Offline contracts; native end-to-end cases run only in check_desktop."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ssdl import desktop_service as desktop
from tests.helpers import desktop_fixture
from tools import check_desktop as acceptance


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def test_existing_service_is_opened_under_launch_mutex_before_environment_check(self):
        controls = Mock(prefix="fixture.")
        controls.keep.return_value = "launch"
        controls.api.WaitForSingleObject.return_value = 0
        controls.open_event.return_value = "ready"
        controls.signalled.return_value = True
        check = Mock()
        with patch.object(desktop, "Controls", return_value=controls), patch.object(desktop, "open_page") as opened:
            self.assertEqual(desktop.start(check), 0)
        opened.assert_called_once()
        check.assert_not_called()
        controls.api.WaitForSingleObject.assert_called_once_with("launch", 60_000)
        controls.api.ReleaseMutex.assert_called_once_with("launch")
        controls.close.assert_called_once()

    def test_launcher_timeout_does_not_release_unowned_mutex_or_spawn(self):
        controls = Mock(prefix="fixture.")
        controls.api.WaitForSingleObject.return_value = 258
        with patch.object(desktop, "Controls", return_value=controls), patch.object(desktop.subprocess, "Popen") as spawned:
            with self.assertRaisesRegex(RuntimeError, "Another startup"):
                desktop.start(Mock())
        controls.api.ReleaseMutex.assert_not_called()
        controls.close.assert_called_once()
        spawned.assert_not_called()

    def test_environment_failure_releases_owned_launch_mutex(self):
        controls = Mock(prefix="fixture.")
        controls.keep.return_value = "launch"
        controls.api.WaitForSingleObject.return_value = 0x80
        controls.open_event.return_value = None
        with patch.object(desktop, "Controls", return_value=controls):
            with self.assertRaisesRegex(RuntimeError, "fixture environment"):
                desktop.start(Mock(side_effect=RuntimeError("fixture environment")))
        controls.api.ReleaseMutex.assert_called_once_with("launch")
        controls.close.assert_called_once()

    def test_page_uses_recorded_port_and_browser_failure_remains_recoverable(self):
        record = self.root / "record.json"
        record.write_text(json.dumps({"port": 43210}), encoding="utf-8")
        with patch.object(desktop, "RECORD", record), patch.dict(desktop.os.environ, {}, clear=True), \
             patch.object(desktop.webbrowser, "open", side_effect=OSError) as opened, patch("builtins.print") as printed:
            desktop.open_page()
        opened.assert_called_once_with("http://127.0.0.1:43210/")
        self.assertIn("Open this URL in your browser.", str(printed.call_args_list))
        record.write_text('{"port": true}', encoding="utf-8")
        with patch.object(desktop, "RECORD", record), self.assertRaises(RuntimeError):
            desktop.open_page()

    def test_noninteractive_mode_suppresses_browser_dispatch(self):
        record = self.root / "record.json"
        record.write_text('{"port": 43210}', encoding="utf-8")
        with patch.object(desktop, "RECORD", record), patch.dict(desktop.os.environ, SSDL_NONINTERACTIVE="1"), \
             patch.object(desktop.webbrowser, "open") as opened, patch("builtins.print"):
            desktop.open_page()
        opened.assert_not_called()

    def test_fixture_hook_requires_matching_receipt_and_explicit_admission(self):
        token = "a" * 32
        with self.assertRaises(ValueError):
            with acceptance.fixture(self.root, token):
                self.fail("Unowned hook admitted")
        (self.root / ".ssdl-install-fixture").write_text(token, encoding="ascii")
        site = self.root / ".venv/Lib/site-packages"
        site.mkdir(parents=True)
        hook = site / "ssdl_desktop_acceptance.pth"
        with acceptance.fixture(self.root, token):
            self.assertIn(token, hook.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                with acceptance.fixture(self.root, token):
                    self.fail("Existing hook replaced")
        self.assertFalse(hook.exists())
        with patch.dict(desktop_fixture.os.environ, {}, clear=True), patch.object(desktop_fixture.webbrowser, "open") as opened:
            with self.assertRaisesRegex(ValueError, "admission"):
                desktop_fixture.install(self.root, token)
        opened.assert_not_called()

    def test_fixture_hook_is_idempotent_and_bootstrap_fails_closed(self):
        from ssdl import app as entry
        token = "a" * 32
        (self.root / ".ssdl-install-fixture").write_text(token, encoding="ascii")
        with patch.object(entry, "create_app", lambda: None), patch.object(desktop_fixture.webbrowser, "open"), \
             patch.dict(desktop_fixture.os.environ, SSDL_DESKTOP_FIXTURE_TOKEN=token):
            desktop_fixture.install(self.root, token)
            first = entry.create_app
            desktop_fixture.install(self.root, token)
            self.assertIs(entry.create_app, first)
        with patch.object(desktop_fixture, "install", side_effect=ValueError("private fixture detail")):
            with self.assertRaises(SystemExit) as caught:
                desktop_fixture.bootstrap(self.root, token)
            self.assertNotIn("private", str(caught.exception))

    def test_shutdown_requires_fresh_durable_evidence_before_port_assertion(self):
        data = self.root / "data"
        data.mkdir()
        receipt = data / "desktop-closed.json"
        status = dict.fromkeys(("closed", "threads_stopped", "durable", "pixiv_thread_stopped", "no_console"), True)
        with patch.object(acceptance, "assert_port_closed") as closed:
            receipt.write_text(json.dumps(dict(status, durable=False)), encoding="utf-8")
            with self.assertRaises(acceptance.AcceptanceError):
                acceptance.stopped(self.root, 43210)
            closed.assert_not_called()
            receipt.write_text(json.dumps(status), encoding="utf-8")
            acceptance.stopped(self.root, 43210)
            closed.assert_called_once_with(43210)
            self.assertFalse(receipt.exists())
            with self.assertRaises(FileNotFoundError):
                acceptance.stopped(self.root, 43210)
