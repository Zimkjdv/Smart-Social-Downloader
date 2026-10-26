"""GUI boundary contracts run without importing pywebview/.NET or showing UI."""
import base64
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from desktop.pywebview_app import NativeActions, NavigationPolicy, WebViewGuard


class Event:
    def __init__(self, *handlers): self.handlers = list(handlers)
    def __iadd__(self, handler): self.handlers.append(handler); return self
    def __isub__(self, handler): self.handlers.remove(handler); return self
    def fire(self, sender, args):
        for handler in list(self.handlers): handler(sender, args)


class DesktopGUIContracts(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.policy = NavigationPolicy()
        self.policy.service = {"origin": "http://127.0.0.1:43210", "ownership": "started"}
        self.url = self.policy.service["origin"] + "/?shell=pywebview"
        self.window = Mock()
        self.window.get_current_url.return_value = self.url
        self.opener = Mock(return_value=True)
        self.api = NativeActions(self.window, SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=1, SAVE=2)),
                                 self.policy, opener=self.opener)

    def test_bridge_allowlist_has_no_business_objects_or_arbitrary_dispatch(self):
        names = {key for key in dir(self.api) if not key.startswith("_")}
        self.assertEqual(names, {"describe", "open_external", "pick_directory", "save_text", "copy_text", "stop_backend"})
        self.assertEqual(self.api.describe()["version"], 1)
        self.policy.service["ownership"] = "attached"
        self.assertFalse(self.api.describe()["capabilities"]["stopBackend"])
        self.assertEqual(self.api.stop_backend()["status"], "unsupported")

    def test_origin_navigation_and_external_scheme_policy(self):
        self.assertTrue(self.policy.trusted(self.url))
        for value in ("https://foreign.example", self.url.replace(":43210", ":43211"),
                      self.url.replace("/?shell=pywebview", "/chrome-connect"), "file:///app/index.html", "about:blank"):
            self.assertFalse(self.policy.navigation(value))
        for value in ("javascript:alert(1)", "file:///app/private", "https://user:secret@example.org/", "https://example.org/\n"):
            self.assertEqual(self.api.open_external(value)["status"], "error")
        self.opener.assert_not_called()
        self.assertEqual(self.api.open_external("/chrome-connect")["status"], "completed")
        self.opener.assert_called_once_with("http://127.0.0.1:43210/chrome-connect")

    def test_only_host_registered_loading_html_can_navigate_without_backend_identity(self):
        policy = NavigationPolicy()
        content = '<!doctype html><body>Startup failed</body>'
        uri = 'data:text/html;charset=utf-8;base64,' + base64.b64encode(content.encode()).decode()
        policy.allow_loading_html(content)
        self.assertTrue(policy.navigation(uri))
        self.assertFalse(policy.trusted(uri))
        self.assertFalse(policy.navigation(uri + 'A'))
        self.assertFalse(policy.navigation('data:text/html,<script>untrusted()</script>'))
        policy.service = self.policy.service
        self.assertFalse(policy.navigation(uri))
        self.assertFalse(policy.navigation('about:blank'))

    def test_external_document_or_closed_window_cannot_use_native_actions(self):
        self.window.get_current_url.return_value = "https://foreign.example/"
        self.assertEqual(self.api.describe()["status"], "error")
        self.assertEqual(self.api.pick_directory()["status"], "error")
        self.assertEqual(self.api.copy_text("synthetic")["status"], "error")
        self.assertEqual(self.api.save_text({"filename": "report.json", "text": "{}"})["status"], "error")
        self.api._closed = True
        self.assertEqual(self.api.open_external("https://example.org")["status"], "cancelled")
        self.window.create_file_dialog.assert_not_called()

    def test_pairing_fallback_uses_ordinary_chrome_instead_of_the_default_browser(self):
        api = NativeActions(self.window, None, self.policy)
        with patch("desktop.pywebview_app.chrome_executable", return_value=Path("chrome.exe")), \
             patch("desktop.pywebview_app.subprocess.Popen") as opened, \
             patch("desktop.pywebview_app.webbrowser.open") as default:
            self.assertEqual(api.open_external("/pixiv-connect#ticket=synthetic")["status"], "completed")
            self.assertEqual(opened.call_args.args[0], ["chrome.exe", "http://127.0.0.1:43210/pixiv-connect#ticket=synthetic"])
            default.assert_not_called()

    def test_picker_cancellation_selection_and_concurrent_dialog_refusal(self):
        self.window.create_file_dialog.return_value = None
        self.assertEqual(self.api.pick_directory()["status"], "cancelled")
        self.window.create_file_dialog.return_value = [str(self.root)]
        self.assertEqual(self.api.pick_directory(), {"status": "completed", "path": str(self.root)})
        self.api._dialog.acquire()
        try:
            self.assertEqual(self.api.pick_directory()["status"], "blocked")
        finally:
            self.api._dialog.release()

    def test_text_export_uses_selected_path_and_leaves_no_temporary_file(self):
        target = self.root / "診斷 report.json"
        self.window.create_file_dialog.return_value = [str(target)]
        value = {"filename": "ssdl-diagnostics.json", "text": '{"test":"中文"}', "mimeType": "application/json"}
        self.assertEqual(self.api.save_text(value)["status"], "completed")
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"test": "中文"})
        self.assertEqual(list(self.root.iterdir()), [target])
        self.assertEqual(self.api.save_text({**value, "filename": "../other.json"})["status"], "error")
        self.window.create_file_dialog.return_value = None
        self.assertEqual(self.api.save_text(value)["status"], "cancelled")
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"test": "中文"})

    def test_stop_requires_confirmation_and_uses_only_the_owned_descriptor(self):
        with patch("desktop.pywebview_app.backend.stop_owned") as stopped:
            self.window.create_confirmation_dialog.return_value = False
            self.assertEqual(self.api.stop_backend()["status"], "cancelled")
            stopped.assert_not_called()
            self.window.create_confirmation_dialog.return_value = True
            self.assertEqual(self.api.stop_backend()["status"], "completed")
            stopped.assert_called_once_with(self.policy.service)

    def test_native_guard_blocks_frames_popups_and_foreign_bridge_messages(self):
        implementation = SimpleNamespace(on_navigation_start=Mock(), on_navigation_completed=Mock(),
            on_script_notify=Mock(), on_new_window_request=Mock(), url=self.url)
        core = SimpleNamespace(Source=self.url, NewWindowRequested=Event(implementation.on_new_window_request), FrameNavigationStarting=Event())
        native = SimpleNamespace(NavigationStarting=Event(implementation.on_navigation_start),
            NavigationCompleted=Event(implementation.on_navigation_completed), CoreWebView2=core,
            CoreWebView2InitializationCompleted=Event(), WebMessageReceived=Event(implementation.on_script_notify))
        self.window.native = SimpleNamespace(webview=native, browser=implementation)
        self.window.events = SimpleNamespace(before_load=Mock(), _pywebviewready=Mock(), loaded=Mock())
        guard = WebViewGuard(self.window, self.policy, self.api)
        guard.install()
        native.CoreWebView2InitializationCompleted.fire(native, SimpleNamespace(IsSuccess=True))
        self.assertTrue(guard.ready.is_set()); self.assertFalse(guard.failed)
        wrong = SimpleNamespace(Uri=self.url.replace("/?shell=pywebview", "/chrome-connect"), Cancel=False, NavigationId=7)
        native.NavigationStarting.fire(native, wrong)
        self.assertTrue(wrong.Cancel)
        native.NavigationCompleted.fire(native, SimpleNamespace(NavigationId=7))
        self.assertEqual(implementation.url, self.url)
        implementation.on_navigation_completed.assert_not_called()
        self.window.events._pywebviewready.set.assert_called_once()
        frame = SimpleNamespace(Cancel=False)
        core.FrameNavigationStarting.fire(core, frame)
        self.assertTrue(frame.Cancel)
        native.WebMessageReceived.fire(native, SimpleNamespace(Source="https://foreign.example"))
        implementation.on_script_notify.assert_not_called()
        native.WebMessageReceived.fire(native, SimpleNamespace(Source=self.url))
        implementation.on_script_notify.assert_called_once()
        popup = SimpleNamespace(Uri="javascript:alert(1)", Handled=False, IsUserInitiated=True)
        core.NewWindowRequested.fire(core, popup)
        self.assertTrue(popup.Handled); self.opener.assert_not_called()
