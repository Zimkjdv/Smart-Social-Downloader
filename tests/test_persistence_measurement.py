"""Portable acceptance for the isolated N07 measurement harness, without speed thresholds."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from ssdl.persistence import validate_state
from tools import measure_persistence as bench
from tools.package_source import source_files


class PersistenceMeasurementTests(unittest.TestCase):
    def test_synthetic_history_counts_and_offline_validation(self):
        jobs, active_id = bench.synthetic_jobs(200, 50)
        saved = validate_state({"jobs": list(jobs.values())})
        self.assertEqual(len(saved["jobs"]), 200)
        self.assertEqual(sum(len(job["files"]) for job in saved["jobs"]), 1180)
        self.assertEqual(sum(job["status"] == "active" for job in saved["jobs"]), 1)
        self.assertEqual(jobs[active_id]["status"], "active")
        self.assertTrue(all(job["url"].startswith("https://example.org/") for job in jobs.values()))

    def test_statistics_use_nearest_rank_and_reject_empty_samples(self):
        result = bench.distribution([5, 2, 1, 4, 3])
        self.assertEqual(result["median_ms"], 3)
        self.assertEqual(result["p95_ms"], 5)
        self.assertEqual(result["n"], 5)
        with self.assertRaises(ValueError):
            bench.distribution([])

    def test_real_save_and_apis_return_verified_path_free_report(self):
        created = []
        factory = bench.create_app

        def capture(*args, **kwargs):
            app = factory(*args, **kwargs)
            created.append(app)
            return app

        with patch.object(bench, "create_app", side_effect=capture):
            result = bench.measure_case("small", 1)
        self.assertEqual(result["jobs"], 20)
        self.assertEqual(result["file_paths"], 20)
        self.assertTrue(all(result["verified"].values()))
        self.assertGreater(result["state_bytes"], 0)
        self.assertEqual(set(result["operations"]), {"summary", "pause", "cancel"})
        for values in result["operations"].values():
            self.assertEqual(values["uncontended"]["http_ms"]["n"], 1)
            self.assertEqual(values["contended"]["writer_save_ms"]["n"], 1)
            self.assertGreaterEqual(values["contended"]["lock_wait_ms"]["median_ms"], 0)
        phases = result["profiled_save"]["phases"]
        self.assertEqual(phases["_read"]["calls"], 2)
        self.assertEqual(phases["validate_state"]["calls"], 3)
        self.assertEqual(phases["_atomic"]["calls"], 2)
        self.assertEqual(phases["fsync"]["calls"], 2)
        self.assertIn("json_dumps", phases)
        self.assertIn("redact", phases)
        app = created[0]
        self.assertFalse(app._started)
        self.assertIsNone(app.state.worker_thread)
        self.assertFalse(app.ROOT.exists())
        encoded = json.dumps(result)
        self.assertNotIn(str(app.ROOT), encoded)
        self.assertNotIn("ssdl-persistence-bench-", encoded)

    def test_contention_gate_observes_real_handler_before_timed_save(self):
        with bench.isolated_app() as (app, metrics):
            app.state.jobs, app.state.active_id = bench.synthetic_jobs(2, 0)
            bench.save(app)
            original = app._save_locked
            observations = []

            def observed_save():
                observations.append((app.lock.arrival.is_set(), app.lock.raw._is_owned()))
                original()

            with patch.object(app, "_save_locked", side_effect=observed_save):
                result = bench.contended_request(app, metrics, "summary")
            self.assertEqual(observations, [(True, True)])
            self.assertGreaterEqual(result["writer_save_ms"], 0)

    def test_failed_save_cannot_produce_successful_measurements(self):
        with bench.isolated_app() as (app, _):
            app.state.jobs, app.state.active_id = bench.synthetic_jobs(2, 0)
            with patch.object(app.STATE_STORE, "_atomic", side_effect=OSError("synthetic disk failure")):
                with self.assertRaisesRegex(RuntimeError, "could not be saved"):
                    bench.save(app)

    def test_writer_failure_releases_gate_and_owned_threads(self):
        with bench.isolated_app() as (app, metrics):
            app.state.jobs, app.state.active_id = bench.synthetic_jobs(2, 0)
            bench.save(app)
            root = app.ROOT
            with patch.object(app, "_save_locked", side_effect=RuntimeError("synthetic writer failure")):
                with self.assertRaisesRegex(RuntimeError, "writer failed"):
                    bench.contended_request(app, metrics, "summary")
            self.assertIsNone(app.lock.arrival)
            self.assertFalse(any(thread.name == "synthetic-state-writer" for thread in threading.enumerate()))
        self.assertFalse(root.exists())

    def test_observed_lock_retains_condition_wait_notify_contract(self):
        lock = bench.ObservedLock()
        condition = threading.Condition(lock)
        waiting = threading.Event()
        completed = threading.Event()
        results = []

        def waiter():
            with condition:
                waiting.set()
                results.append(condition.wait_for(completed.is_set, timeout=5))

        thread = threading.Thread(target=waiter)
        thread.start()
        try:
            self.assertTrue(waiting.wait(5))
            with condition:
                completed.set()
                condition.notify_all()
        finally:
            with condition:
                completed.set()
                condition.notify_all()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, [True])

    def test_measurement_tool_is_in_reviewed_source_package(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn(root / "tools" / "measure_persistence.py", source_files(root))


if __name__ == "__main__":
    unittest.main()
