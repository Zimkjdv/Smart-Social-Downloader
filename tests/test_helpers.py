"""The reusable fixture owns its context, overrides and temporary storage."""
import random
import unittest
from unittest.mock import Mock, patch

from tests.helpers.app import IsolatedApp, seed_jobs


class FixtureTests(unittest.TestCase):
    def test_instances_and_seeded_jobs_are_independent_without_global_patches(self):
        original = random.uniform
        with IsolatedApp() as first, IsolatedApp() as second:
            self.assertIs(random.uniform, original)
            self.assertNotEqual(first.root, second.root)
            self.assertIsNot(first.app.state, second.app.state)
            self.assertEqual(seed_jobs(first.app, 3), ["0", "1", "2"])
            self.assertEqual(list(first.app.state.queue), ["0", "1", "2"])
            self.assertFalse(second.app.state.jobs)
            self.assertEqual(first.app.JOB_DELAY_MIN, 0)
            self.assertTrue(first.app.STATE_FILE.is_relative_to(first.root))
            self.assertTrue(second.app.STATE_FILE.is_relative_to(second.root))
        self.assertFalse(first.root.exists())
        self.assertFalse(second.root.exists())

    def test_exception_stops_owned_workers_and_restores_service_override(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic test failure"):
            with IsolatedApp() as fixture:
                app = fixture.app
                original = app.ENVIRONMENT
                replacement = Mock()
                fixture.stack.enter_context(patch.object(app, "ENVIRONMENT", replacement))
                app.state.paused = True
                app.start()
                raise RuntimeError("synthetic test failure")
        self.assertTrue(app._closed)
        self.assertFalse(app.state.worker_thread.is_alive())
        replacement.shutdown.assert_called_once()
        self.assertIs(app.ENVIRONMENT, original)
        self.assertTrue(original._stop.is_set())
        self.assertFalse(fixture.root.exists())

    def test_setup_failure_removes_the_owned_temporary_directory(self):
        from tests.helpers import app as helpers
        temporary = helpers.tempfile.TemporaryDirectory
        created = []
        def record(*args, **kwargs):
            result = temporary(*args, **kwargs)
            created.append(result.name)
            return result
        with patch.object(helpers.tempfile, "TemporaryDirectory", side_effect=record), \
             patch.object(helpers, "create_app", side_effect=RuntimeError("synthetic setup failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic setup failure"):
                with IsolatedApp():
                    self.fail("Setup should fail before entering")
        from pathlib import Path
        self.assertEqual(len(created), 1)
        self.assertFalse(Path(created[0]).exists())
