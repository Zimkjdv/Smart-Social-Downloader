"""N06 acceptance: no import-time restore, independent instances and owned shutdown."""
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from ssdl import app as entry
from ssdl.app_context import AppContext
from ssdl.x_auth import XAuthManager, AuthError


class AppContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ssdl-context-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def context(self, name="one", **services):
        context = entry.create_app(self.root / name, **services)
        self.addCleanup(context.close)
        return context

    def test_fresh_import_and_construction_do_not_restore_or_start_threads(self):
        script = """
from pathlib import Path
import sys
from unittest.mock import patch
with patch('ssdl.x_auth.XAuthManager._restore', side_effect=AssertionError('auth restore during import')), \\
     patch('ssdl.persistence.StateStore.load', side_effect=AssertionError('history read during import')), \\
     patch('threading.Thread.start', side_effect=AssertionError('thread during import')):
    from ssdl.app import create_app
    with create_app(Path(sys.argv[1])) as app:
        assert app.X_AUTH.status()['connected'] is False
        assert not app.STATE_FILE.exists()
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.root)], capture_output=True,
                                text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "data").exists())

    def test_instances_have_independent_state_services_handlers_and_locks(self):
        first, second = self.context("first"), self.context("second")
        self.assertIsInstance(first, AppContext)
        first.state.paused = True
        first.state.queue.append("synthetic")
        first.state.job_starts.append(time.time())
        first.POLICY.ensure_cooldown(platform="X")
        for field in ("state", "lock", "condition", "POLICY", "STORAGE", "X_AUTH", "STATE_STORE",
                      "THUMBNAILS", "ENVIRONMENT", "DATABASES", "Handler"):
            self.assertIsNot(getattr(first, field), getattr(second, field), field)
        self.assertIs(first.Handler.app, first)
        self.assertIs(second.Handler.app, second)
        self.assertFalse(second.state.paused)
        self.assertFalse(second.state.queue)
        self.assertFalse(second.state.job_starts)
        self.assertEqual(second.POLICY.snapshot("X")["cooldown_seconds"], 0)
        first.close()
        self.assertFalse(second.state.shutdown.is_set())

    def test_start_is_idempotent_and_restore_happens_before_worker(self):
        context = self.context(auth=Mock(), environment=Mock())
        events = []
        with patch.object(context, "_load_saved_state", side_effect=lambda: events.append("history")), \
             patch.object(context.X_AUTH, "restore", side_effect=lambda: events.append("auth")), \
             patch.object(context, "_worker", side_effect=lambda: events.append("worker")):
            context.start()
            context.state.worker_thread.join(timeout=2)
            context.start()
        self.assertEqual(events, ["history", "auth", "worker"])
        self.assertEqual(context.ENVIRONMENT.refresh.call_count, 1)

    def test_close_without_start_does_not_read_or_write_history(self):
        context = self.context()
        with patch.object(context.STATE_STORE, "load") as loaded, \
             patch.object(context.STATE_STORE, "save") as saved, \
             patch.object(context.X_AUTH, "restore") as restored:
            context.close()
            context.close()
            loaded.assert_not_called()
            saved.assert_not_called()
            restored.assert_not_called()
        self.assertFalse((context.ROOT / "data").exists())
        with self.assertRaises(RuntimeError):
            context.start()

    def test_binding_failure_does_not_restore_or_migrate_history(self):
        context = self.context()
        with patch.object(entry, "create_app", return_value=context), \
             patch.object(entry, "Server", side_effect=OSError("owned fixture port busy")), \
             patch.object(context, "start") as started, patch("builtins.print"):
            self.assertEqual(entry.main(), 1)
        started.assert_not_called()
        self.assertFalse((context.ROOT / "data").exists())

    def test_start_close_and_new_instance_preserve_queue_quota_and_settings(self):
        context = self.context(auth=Mock(), environment=Mock())
        context.state.paused = True
        context.state.jobs["fixture"] = {"id": "fixture", "url": "https://example.org/movie", "status": "queued",
                                         "created_at": time.time(), "platform": "Web", "files": []}
        context.state.queue.append("fixture")
        context.state.hourly_job_limit = 80
        context.state.job_starts.append(time.time())
        context._save_locked()
        context.start()
        context.close()
        self.assertFalse(context.state.worker_thread.is_alive())
        recovered = self.context(auth=Mock(), environment=Mock())
        recovered.start()
        self.assertTrue(recovered.state.paused)
        self.assertEqual(list(recovered.state.queue), ["fixture"])
        self.assertEqual(recovered.state.hourly_job_limit, 80)
        self.assertEqual(recovered._quota_locked()["used"], 1)
        self.assertNotEqual(context.state.state_instance, recovered.state.state_instance)

    def test_close_stops_owned_helpers_without_restarting_scans(self):
        context = self.context()
        with patch("ssdl.environment.inspect_environment", return_value={"phase": "complete", "busy": False}):
            context.ENVIRONMENT.refresh()
            context.STORAGE.snapshot(self.root)
            context.THUMBNAILS.status()
            context.close()
        for service in (context.ENVIRONMENT, context.STORAGE, context.THUMBNAILS):
            self.assertFalse(service._thread.is_alive())
        with patch.object(threading.Thread, "start") as started:
            context.ENVIRONMENT.refresh()
            context.STORAGE.snapshot(self.root)
            context.THUMBNAILS.status()
        started.assert_not_called()

    def test_auth_restore_is_explicit_and_idempotent(self):
        with patch.object(XAuthManager, "_restore") as restored:
            auth = XAuthManager(self.root, restore=False)
            self.addCleanup(auth.shutdown)
            restored.assert_not_called()
            auth.restore()
            auth.restore()
        restored.assert_called_once()

    def test_connection_callback_cannot_enqueue_after_shutdown(self):
        context = self.context()
        context.close()
        context.state.jobs["fixture"] = {"id": "fixture", "status": "failed", "platform": "X"}
        with patch.object(context, "_save_locked") as saved:
            context._retry_failed_x()
        self.assertFalse(context.state.queue)
        saved.assert_not_called()

    def test_closing_one_running_instance_leaves_the_other_worker_alive(self):
        first = self.context("first", auth=Mock(), environment=Mock())
        second = self.context("second", auth=Mock(), environment=Mock())
        first.start()
        second.start()
        first.close()
        self.assertFalse(first.state.worker_thread.is_alive())
        self.assertTrue(second.state.worker_thread.is_alive())
        self.assertFalse(second.state.shutdown.is_set())
        second.close()
        self.assertFalse(second.state.worker_thread.is_alive())

    def test_closed_auth_manager_cannot_restart_pairing_or_restore(self):
        auth = XAuthManager(self.root, restore=False)
        auth.shutdown()
        with patch("ssdl.x_auth._dpapi") as encrypted, patch.object(auth, "_restore") as restored:
            for action in (auth.connect, auth.prepare_extension, auth.restore):
                with self.assertRaises(AuthError):
                    action()
        encrypted.assert_not_called()
        restored.assert_not_called()

    def test_worker_start_failure_can_be_closed_without_masking_the_error(self):
        context = self.context(auth=Mock(), environment=Mock())
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("synthetic thread startup failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic thread startup failure"):
                context.start()
        self.assertIsNone(context.state.worker_thread)
        self.assertFalse(context._started)
        context.close()
        self.assertFalse(context.STATE_FILE.exists())

    def test_helper_start_failures_can_be_closed_without_joining_unstarted_threads(self):
        context = self.context()
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("synthetic thread startup failure")), \
             patch("ssdl.x_auth.chrome_executable", return_value=Path("synthetic-chrome")), \
             patch("ssdl.x_auth._dpapi", return_value=b"synthetic"):
            for action in (context.ENVIRONMENT.refresh, lambda: context.STORAGE.snapshot(self.root),
                           context.THUMBNAILS.status, context.X_AUTH.connect):
                with self.assertRaisesRegex(RuntimeError, "synthetic thread startup failure"):
                    action()
            context.close()
        for service in (context.ENVIRONMENT, context.STORAGE, context.THUMBNAILS, context.X_AUTH):
            self.assertTrue(service._stop.is_set())
            self.assertFalse(service._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
