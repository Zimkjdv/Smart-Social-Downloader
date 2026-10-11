import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ssdl.persistence import StateStore, validate_state, SCHEMA_VERSION


def payload(status="completed"):
    return {"jobs": [{"id": "fixture", "url": "https://example.org/post", "status": status,
                      "created_at": 100, "platform": "Web", "files": [], "warnings": []}],
            "queue": [], "paused": False, "safe_queue": {}, "job_starts": []}


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-state-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.store = StateStore(self.path)

    def test_legacy_is_migrated_without_mutating_input(self):
        value = payload()
        self.path.write_text(json.dumps(value), encoding="utf8")
        self.assertEqual(self.store.load()["schema_version"], SCHEMA_VERSION)
        self.assertNotIn("schema_version", value)

    def test_last_good_backup_recovers_corruption(self):
        self.assertTrue(self.store.save(payload("completed")))
        self.assertTrue(self.store.save(payload("failed")))
        self.path.write_text("{broken", encoding="utf8")
        recovered = StateStore(self.path)
        self.assertEqual(recovered.load()["jobs"][0]["status"], "completed")
        self.assertTrue(recovered.status()["recovered"])
        self.assertTrue(recovered.save(payload()))
        damaged = list(self.path.parent.glob("state.corrupt-*.json"))
        self.assertEqual(len(damaged), 1)
        self.assertEqual(damaged[0].read_text(), "{broken")
        self.assertEqual(json.loads(self.store.backup.read_text())["jobs"][0]["status"], "completed")

    def test_failed_replace_retains_previous_state_and_can_retry(self):
        self.store.save(payload())
        original = Path.replace
        def replace(path, target):
            if target == self.path:
                raise PermissionError("synthetic disk failure")
            return original(path, target)
        with patch.object(Path, "replace", replace):
            self.assertFalse(self.store.save(payload("failed")))
        self.assertFalse(self.store.status()["healthy"])
        self.assertEqual(json.loads(self.path.read_text())["jobs"][0]["status"], "completed")
        self.assertFalse(list(self.path.parent.glob("*.tmp")))
        self.assertTrue(self.store.save(payload("failed")))
        self.assertTrue(self.store.status()["healthy"])

    def test_missing_primary_uses_backup(self):
        self.store.save(payload())
        self.store.save(payload("failed"))
        self.path.unlink()
        self.assertEqual(StateStore(self.path).load()["jobs"][0]["status"], "completed")

    def test_future_schema_is_preserved_and_writes_blocked(self):
        future = {**payload(), "schema_version": 999}
        self.path.write_text(json.dumps(future), encoding="utf8")
        self.assertIsNone(self.store.load())
        self.assertTrue(self.store.status()["blocked"])
        self.assertFalse(self.store.save(payload()))
        self.assertEqual(json.loads(self.path.read_text())["schema_version"], 999)

    def test_future_backup_blocks_writes_with_missing_or_corrupt_primary(self):
        for primary in (None, "{broken"):
            with self.subTest(primary=primary):
                self.path.unlink(missing_ok=True)
                if primary is not None:
                    self.path.write_text(primary, encoding="utf8")
                future = json.dumps({**payload(), "schema_version": 999})
                self.store.backup.write_text(future, encoding="utf8")
                store = StateStore(self.path)
                self.assertIsNone(store.load())
                self.assertTrue(store.status()["blocked"])
                self.assertFalse(store.save(payload()))
                self.assertEqual(store.backup.read_text(), future)
                self.assertEqual(self.path.read_text() if self.path.exists() else None, primary)

    def test_future_backup_is_protected_even_when_primary_is_valid(self):
        self.assertTrue(self.store.save(payload()))
        original = self.path.read_bytes()
        future = json.dumps({**payload(), "schema_version": 999})
        self.store.backup.write_text(future, encoding="utf8")
        self.assertFalse(self.store.save(payload("failed")))
        self.assertTrue(self.store.status()["blocked"])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.backup.read_text(), future)

    def test_invalid_jobs_are_rejected_before_partial_restore(self):
        for bad in ({"jobs": "bad"}, {**payload(), "queue": "bad"},
                    {**payload(), "jobs": [{**payload()["jobs"][0], "created_at": float("nan")}]},
                    {**payload(), "jobs": [{**payload()["jobs"][0], "files": [123]}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_state(bad)
        bad = {**payload(), "jobs": [{**payload()["jobs"][0], "attempts": None}]}
        with self.assertRaises(ValueError):
            validate_state(bad)
        self.assertEqual(validate_state({**payload(), "jobs": [{**payload()["jobs"][0], "size_bytes": None}]})["schema_version"], SCHEMA_VERSION)

    def test_unrecoverable_input_remains_available(self):
        self.path.write_text("broken", encoding="utf8")
        self.assertIsNone(self.store.load())
        self.assertFalse(self.store.status()["healthy"])
        self.assertTrue(self.store.save(payload()))
        self.assertEqual(next(self.path.parent.glob("state.corrupt-*.json")).read_text(), "broken")
