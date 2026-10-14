"""N07 deterministic durability, failure, lifecycle and concurrent API acceptance."""
import ast
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from ssdl.app import create_app
from ssdl.persistence import SCHEMA_VERSION
from ssdl.state_writer import StateWriter, freeze_snapshot, thaw_snapshot
from tools import measure_persistence as bench


class StateWriterTests(unittest.TestCase):
    def writer(self, save, **options):
        writer = StateWriter(save, Mock(), **options)
        self.addCleanup(writer.close)
        return writer

    def test_construction_is_passive_start_and_close_are_idempotent(self):
        with patch.object(threading.Thread, "start") as started:
            writer = self.writer(lambda value: True)
        started.assert_not_called()
        writer.start()
        thread = writer._thread
        writer.start()
        self.assertIs(writer._thread, thread)
        self.assertTrue(writer.close())
        self.assertTrue(writer.close())
        self.assertFalse(thread.is_alive())
        with self.assertRaises(RuntimeError):
            writer.submit(freeze_snapshot({}))
        with self.assertRaises(RuntimeError):
            writer.start()

    def test_snapshot_freezes_nested_lists_and_shares_only_immutable_values(self):
        filename = "synthetic" * 10 + ".jpg"
        original = {"jobs": [{"files": [filename], "last_success": {"files": ["old.jpg"]},
                              "selection_options": [{"id": "one", "urls": ["https://example.org/one"]}]}],
                    "safe_queue": {"platform_cooldowns": {"example.org": {"strikes": 1}}}}
        snapshot = freeze_snapshot(original)
        original["jobs"][0]["files"].append("new.jpg")
        original["jobs"][0]["last_success"]["files"][0] = "moved.jpg"
        original["jobs"][0]["selection_options"][0]["urls"].clear()
        original["safe_queue"]["platform_cooldowns"]["example.org"]["strikes"] = 99
        self.assertIs(snapshot["jobs"][0]["files"][0], filename)
        restored = thaw_snapshot(snapshot)
        self.assertEqual(restored["jobs"][0]["files"], [filename])
        self.assertEqual(restored["jobs"][0]["last_success"]["files"], ["old.jpg"])
        self.assertEqual(restored["jobs"][0]["selection_options"][0]["urls"], ["https://example.org/one"])
        self.assertEqual(restored["safe_queue"]["platform_cooldowns"]["example.org"]["strikes"], 1)
        with self.assertRaises(TypeError):
            snapshot["jobs"][0]["status"] = "changed"
        with self.assertRaises(TypeError):
            freeze_snapshot({object(): "invalid key"})

    def test_one_inflight_and_only_latest_pending_generation_are_written(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        writes = []

        def save(snapshot):
            writes.append(thaw_snapshot(snapshot)["number"])
            if len(writes) == 1:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("fixture gate expired")
            return True

        writer = self.writer(save)
        first = writer.submit(freeze_snapshot({"number": 1}))
        self.assertTrue(entered.wait(5))
        middle = writer.submit(freeze_snapshot({"number": 2}), checkpoint=True)
        latest = writer.submit(freeze_snapshot({"number": 3}), checkpoint=True)
        self.assertEqual(writer._inflight, first)
        self.assertEqual(writer._pending[0], latest)
        self.assertEqual(writer.status()["coalesced"], 1)
        release.set()
        self.assertTrue(writer.wait(latest))
        self.assertTrue(writer.wait(middle))
        self.assertEqual(writes, [1, 3])

    def test_checkpoint_deadline_is_not_extended_and_barrier_flushes_it(self):
        writes = []
        writer = self.writer(lambda value: writes.append(thaw_snapshot(value)) or True, checkpoint_seconds=60)
        writer.submit(freeze_snapshot({"number": 1}), checkpoint=True)
        due = writer._due
        latest = writer.submit(freeze_snapshot({"number": 2}), checkpoint=True)
        self.assertEqual(writer._due, due)
        self.assertEqual(writer.status()["writes"], 0)
        self.assertTrue(writer.wait(latest))
        self.assertEqual(writes, [{"number": 2}])

    def test_checkpoint_eventually_flushes_without_a_critical_caller(self):
        saved = threading.Event()
        writer = self.writer(lambda value: saved.set() or True, checkpoint_seconds=.02)
        generation = writer.submit(freeze_snapshot({}), checkpoint=True)
        self.assertTrue(saved.wait(5))
        self.assertTrue(writer.wait(generation))

    def test_failed_write_stays_dirty_without_busy_retry_and_recovers(self):
        writes = []

        def save(snapshot):
            writes.append(thaw_snapshot(snapshot))
            return len(writes) > 1

        writer = self.writer(save)
        first = writer.submit(freeze_snapshot({"number": 1}))
        self.assertFalse(writer.wait(first))
        self.assertTrue(writer._retry_required)
        self.assertTrue(writer.status()["pending"])
        self.assertEqual(writer.status()["writes"], 1)
        latest = writer.submit(freeze_snapshot({"number": 2}))
        self.assertTrue(writer.wait(latest))
        self.assertTrue(writer.wait(first))
        self.assertFalse(writer.status()["pending"])
        self.assertEqual(writes, [{"number": 1}, {"number": 2}])

    def test_unexpected_save_exception_is_a_visible_generation_failure(self):
        writer = self.writer(Mock(side_effect=RuntimeError("synthetic failure")))
        generation = writer.submit(freeze_snapshot({}))
        self.assertFalse(writer.wait(generation))
        self.assertEqual(writer.status()["failed_generation"], generation)
        writer._failed.assert_called()
        self.assertFalse(writer.close())

    def test_close_flushes_delayed_checkpoint_and_rejects_new_submissions(self):
        writes = []
        writer = self.writer(lambda value: writes.append(thaw_snapshot(value)) or True, checkpoint_seconds=60)
        generation = writer.submit(freeze_snapshot({"paused": True}), checkpoint=True)
        self.assertTrue(writer.close())
        self.assertEqual(writer.status()["saved_generation"], generation)
        self.assertEqual(writes, [{"paused": True}])

    def test_invalid_barrier_generation_is_rejected(self):
        writer = self.writer(lambda value: True)
        for value in (True, -1, 1, "0", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                writer.wait(value)

    def test_invalid_intervals_and_mutable_submissions_are_rejected(self):
        for value in (True, -1, 61, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                StateWriter(lambda value: True, Mock(), checkpoint_seconds=value)
        writer = self.writer(lambda value: True)
        with self.assertRaises(TypeError):
            writer.submit({"jobs": []})
        self.assertFalse(writer.status()["writer_running"])


class WriterApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ssdl-writer-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def app(self, name="one"):
        app = create_app(self.root / name, auth=Mock(), environment=Mock(), storage=Mock(), thumbnails=Mock())
        self.addCleanup(app.close)
        return app

    def test_barrier_never_waits_with_queue_lock_held(self):
        app = self.app()
        with app.condition:
            generation = app._save_locked()
            with self.assertRaisesRegex(RuntimeError, "must not hold"):
                app._wait_saved(generation)
        self.assertTrue(app._wait_saved(generation))

    def test_close_joins_lazy_writer_and_flushes_latest_checkpoint(self):
        app = self.app()
        app.STATE_WRITER._checkpoint_seconds = 60
        with app.condition:
            app.state.paused = True
            app._save_locked(checkpoint=True)
        thread = app.STATE_WRITER._thread
        self.assertFalse(app.STATE_FILE.exists())
        app.close()
        self.assertFalse(thread.is_alive())
        self.assertTrue(app.STATE_STORE._read(app.STATE_FILE)["paused"])
        self.assertFalse(app.STATE_WRITER.status()["pending"])

    def test_capture_failure_remains_unhealthy_after_an_older_write_succeeds(self):
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        original = app.STATE_STORE._atomic

        def gated(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture gate expired")
            original(*args)

        with patch.object(app.STATE_STORE, "_atomic", side_effect=gated):
            try:
                with app.condition:
                    first = app._save_locked()
                self.assertTrue(entered.wait(5))
                with app.condition:
                    app.state.jobs["bad"] = {"not_json": object()}
                    failed = app._save_locked()
                self.assertFalse(app._wait_saved(failed))
                release.set()
                self.assertTrue(app._wait_saved(first))
                self.assertFalse(app._persistence_status()["healthy"])
                with app.condition:
                    app.state.jobs.clear()
                    latest = app._save_locked()
                self.assertTrue(app._wait_saved(latest))
                self.assertTrue(app._persistence_status()["healthy"])
            finally:
                release.set()

    def test_two_instances_can_save_while_one_store_is_blocked(self):
        first, second = self.app("first"), self.app("second")
        entered, release = threading.Event(), threading.Event()
        original = first.STATE_STORE._atomic

        def gated(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture gate expired")
            original(*args)

        with patch.object(first.STATE_STORE, "_atomic", side_effect=gated):
            try:
                with first.condition:
                    generation = first._save_locked()
                self.assertTrue(entered.wait(5))
                second.state.paused = True
                second._save_locked()
                self.assertTrue(second.STATE_STORE._read(second.STATE_FILE)["paused"])
                self.assertEqual(first.STATE_WRITER.status()["saved_generation"], 0)
                release.set()
                self.assertTrue(first._wait_saved(generation))
            finally:
                release.set()

    def test_future_backup_is_protected_through_save_retry_and_close(self):
        app = self.app()
        app.STATE_FILE.parent.mkdir(parents=True)
        app.STATE_FILE.write_text(json.dumps({"jobs": []}), encoding="utf-8")
        app.STATE_STORE.backup.write_text(json.dumps({"jobs": [], "schema_version": SCHEMA_VERSION + 1}), encoding="utf-8")
        primary, backup = app.STATE_FILE.read_bytes(), app.STATE_STORE.backup.read_bytes()
        app._save_locked()
        self.assertTrue(app._persistence_status()["blocked"])
        self.assertFalse(app._persistence_status()["healthy"])
        app._save_locked()
        app.close()
        self.assertEqual(app.STATE_FILE.read_bytes(), primary)
        self.assertEqual(app.STATE_STORE.backup.read_bytes(), backup)

    def test_corrupt_primary_is_preserved_without_clobbering_good_backup(self):
        app = self.app()
        app.STATE_FILE.parent.mkdir(parents=True)
        app.STATE_FILE.write_bytes(b"synthetic corrupt history")
        app.STATE_STORE.backup.write_text(json.dumps({"jobs": [], "paused": False}), encoding="utf-8")
        backup = app.STATE_STORE.backup.read_bytes()
        app.state.paused = True
        app._save_locked()
        self.assertTrue(app.STATE_STORE._read(app.STATE_FILE)["paused"])
        self.assertEqual(app.STATE_STORE.backup.read_bytes(), backup)
        preserved = list(app.STATE_FILE.parent.glob("state.corrupt-*.json"))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_bytes(), b"synthetic corrupt history")

    def test_success_after_recovered_write_failure_restores_recovery_notice(self):
        app = self.app()
        app.STATE_FILE.parent.mkdir(parents=True)
        app.STATE_FILE.write_bytes(b"synthetic corrupt history")
        app.STATE_STORE.backup.write_text(json.dumps({"jobs": []}), encoding="utf-8")
        app._load_saved_state()
        self.assertTrue(app._persistence_status()["recovered"])
        with patch.object(app.STATE_STORE, "_atomic", side_effect=OSError("synthetic disk failure")):
            app._save_locked()
        self.assertFalse(app._persistence_status()["healthy"])
        app._save_locked()
        status = app._persistence_status()
        self.assertTrue(status["healthy"])
        self.assertIn("恢復", status["error"])
        self.assertNotIn("保存失敗", status["error"])

    def test_worker_stop_during_start_barrier_does_not_launch_download(self):
        app = self.app()
        key = "one"
        app.state.jobs[key] = {"id": key, "url": "https://example.org/movie", "platform": "Web",
                               "status": "queued", "created_at": time.time(), "files": []}
        app.state.queue.append(key)
        entered, release = threading.Event(), threading.Event()
        original = app.STATE_STORE._atomic

        def gated(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture gate expired")
            original(*args)

        with patch.object(app.STATE_STORE, "_atomic", side_effect=gated), \
             patch.object(app.random, "uniform", return_value=0), patch.object(app, "run_job") as run:
            thread = threading.Thread(target=app._worker_loop)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with app.condition:
                    app.state.jobs[key]["stop_requested"] = True
                    app.state.shutdown.set()
                    app.condition.notify_all()
                release.set()
                thread.join(5)
                self.assertFalse(thread.is_alive())
                run.assert_not_called()
                self.assertEqual(app.state.jobs[key]["error_code"], "download_cancelled")
            finally:
                app.state.shutdown.set()
                release.set()
                thread.join(5)

    def test_all_api_mutation_barriers_are_outside_protected_sections(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "ssdl/http_api.py").read_text(encoding="utf-8"))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_post")
        waits = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and ast.unparse(node.func) == "self.app._wait_saved"]
        self.assertEqual(len(waits), 13)
        for node in ast.walk(method):
            if isinstance(node, ast.With):
                self.assertFalse(any(item in waits for item in ast.walk(node)))

    def test_profile_pause_or_stop_during_quota_barrier_does_not_recharge(self):
        for stop in (False, True):
            with self.subTest(stop=stop):
                app = self.app("stop" if stop else "pause")
                key = "account"
                app.state.jobs[key] = {"id": key, "url": "https://example.org/account", "platform": "X",
                    "status": "active", "created_at": 1, "files": [], "mode": "x_profile"}
                app.state.hourly_job_limit = 1
                entered, release, returned = threading.Event(), threading.Event(), threading.Event()
                original = app.STATE_STORE._atomic
                errors = []

                def gated(*args):
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError("fixture gate expired")
                    original(*args)

                def post():
                    try:
                        app._profile_gate(key, start_post=True)
                    except Exception as exc:
                        errors.append(exc)
                    finally:
                        returned.set()

                with patch.object(app.STATE_STORE, "_atomic", side_effect=gated):
                    thread = threading.Thread(target=post)
                    thread.start()
                    try:
                        self.assertTrue(entered.wait(5))
                        with app.condition:
                            app.state.paused = not stop
                            app.state.jobs[key]["stop_requested"] = stop
                        release.set()
                        self.assertTrue(app._wait_saved(app.STATE_WRITER.status()["generation"]))
                        if not stop:
                            self.assertFalse(returned.is_set())
                            with app.condition:
                                app.state.paused = False
                                app.condition.notify_all()
                        self.assertTrue(returned.wait(5))
                        self.assertEqual(len(app.state.job_starts), 1)
                        if stop:
                            self.assertEqual(len(errors), 1)
                            self.assertEqual(app.media.error_info(errors[0])["error_code"], "profile_stopped")
                        else:
                            self.assertFalse(errors)
                    finally:
                        release.set()
                        with app.condition:
                            app.state.shutdown.set()
                            app.condition.notify_all()
                        thread.join(5)
                    self.assertFalse(thread.is_alive())

    def test_close_waits_for_owned_io_and_joins_writer_before_returning(self):
        app = self.app()
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        original = app.STATE_STORE._atomic

        def gated(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture gate expired")
            original(*args)

        with patch.object(app.STATE_STORE, "_atomic", side_effect=gated):
            with app.condition:
                app.state.paused = True
                app._save_locked()
            self.assertTrue(entered.wait(5))
            thread = threading.Thread(target=lambda: (app.close(), returned.set()))
            thread.start()
            try:
                self.assertFalse(returned.is_set())
                self.assertTrue(app.STATE_STORE.status()["healthy"])
                release.set()
                self.assertTrue(returned.wait(5))
                self.assertFalse(app.STATE_WRITER._thread.is_alive())
                self.assertTrue(app.STATE_STORE._read(app.STATE_FILE)["paused"])
            finally:
                release.set()
                thread.join(5)
            self.assertFalse(thread.is_alive())


class WriterApiTests(unittest.TestCase):
    def request(self, app, path, body=None):
        client = http.client.HTTPConnection("127.0.0.1", app.PORT, timeout=5)
        try:
            client.request("GET" if body is None else "POST", path, None if body is None else json.dumps(body),
                           {"Origin": f"http://127.0.0.1:{app.PORT}", "Content-Type": "application/json"})
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def test_summary_and_cancel_checks_remain_responsive_during_critical_io(self):
        for operation in ("pause", "cancel"):
            with self.subTest(operation=operation), bench.isolated_app() as (app, _):
                app.state.jobs, app.state.active_id = bench.synthetic_jobs(2, 0)
                entered, release, returned = threading.Event(), threading.Event(), threading.Event()
                original = app.STATE_STORE._atomic
                responses, errors = [], []

                def gated(*args):
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError("fixture gate expired")
                    original(*args)

                def mutate():
                    try:
                        path = "/api/pause" if operation == "pause" else f"/api/jobs/{app.state.active_id}/stop"
                        responses.append(self.request(app, path, {"paused": True} if operation == "pause" else {}))
                    except Exception as exc:
                        errors.append(exc)
                    finally:
                        returned.set()

                with patch.object(app.STATE_STORE, "_atomic", side_effect=gated):
                    thread = threading.Thread(target=mutate)
                    thread.start()
                    try:
                        self.assertTrue(entered.wait(5))
                        self.assertFalse(returned.is_set())
                        code, summary = self.request(app, "/api/summary")
                        self.assertEqual(code, 200)
                        self.assertTrue(summary["persistence"]["pending"])
                        if operation == "cancel":
                            self.assertTrue(app._job_cancelled(app.state.active_id))
                        self.assertFalse(returned.is_set())
                        release.set()
                        self.assertTrue(returned.wait(5))
                        self.assertFalse(errors)
                        self.assertEqual(responses[0][0], 200)
                        self.assertFalse(responses[0][1]["persistence"]["pending"])
                        saved = app.STATE_STORE._read(app.STATE_FILE)
                        self.assertTrue(saved["paused"] if operation == "pause" else saved["jobs"][-1]["stop_requested"])
                    finally:
                        release.set()
                        thread.join(5)
                    self.assertFalse(thread.is_alive())

    def test_failed_api_save_warns_then_manual_retry_persists_state(self):
        with bench.isolated_app() as (app, _):
            with patch.object(app.STATE_STORE, "_atomic", side_effect=OSError("synthetic disk failure")):
                code, response = self.request(app, "/api/pause", {"paused": True})
            self.assertEqual(code, 200)
            self.assertFalse(response["persistence"]["healthy"])
            self.assertTrue(response["persistence"]["pending"])
            self.assertTrue(response["persistence"]["error"])
            code, response = self.request(app, "/api/state/save", {})
            self.assertEqual(code, 200)
            self.assertTrue(response["persistence"]["healthy"])
            self.assertFalse(response["persistence"]["pending"])
            self.assertTrue(app.STATE_STORE._read(app.STATE_FILE)["paused"])

    def test_closed_app_rejects_new_and_already_admitted_mutations(self):
        with bench.isolated_app() as (app, _):
            app.close()
            code, _ = self.request(app, "/api/pause", {"paused": True})
            self.assertEqual(code, 503)
            self.assertFalse(app.state.paused)
            self.assertFalse(app.STATE_FILE.exists())
            handler = object.__new__(app.Handler)
            from ssdl.http_api import ApplicationClosedError
            with self.assertRaises(ApplicationClosedError), handler._mutation():
                app.state.paused = True
            self.assertFalse(app.state.paused)


if __name__ == "__main__":
    unittest.main()
