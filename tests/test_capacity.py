"""Synthetic byte boundaries, account scans and preservation; no live sessions."""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ssdl import ipc, persistence
from ssdl.json_budget import encode_json, JSONBudgetError
from ssdl.state_writer import StateWriter, freeze_snapshot, thaw_snapshot, SAVE_ERROR
from tools import measure_capacity as bench
from tools.package_source import source_files


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-capacity-test-")
        self.addCleanup(self.temp.cleanup)
        self.store = persistence.StateStore(Path(self.temp.name) / "state.json")

    def test_encoder_matches_json_and_counts_utf8_bytes_at_exact_boundary(self):
        value = {"files": ["圖\\片.jpg", '"quoted"', "emoji 😀"], "nested": {"yes": True, "no": None}}
        for indent in (None, 2):
            expected = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=indent,
                                  separators=None if indent else (",", ":")).encode("utf-8")
            self.assertEqual(encode_json(value, len(expected), indent=indent), expected)
            with self.assertRaises(JSONBudgetError) as failure:
                encode_json(value, len(expected) - 1, indent=indent)
            self.assertGreater(failure.exception.observed_bytes, len(expected) - 1)

    def test_encoder_stops_near_limit_without_encoding_entire_large_value(self):
        with self.assertRaises(JSONBudgetError) as failure:
            encode_json({"padding": "圖" * 1000000}, 4096)
        self.assertLessEqual(failure.exception.observed_bytes, 4096 + 3 * 32768)

    def test_invalid_json_never_writes_partial_ipc(self):
        for value in ({"bad": float("nan")}, {"bad": object()}, {"bad": "\ud800"}):
            stream = io.BytesIO()
            with self.subTest(value=type(value["bad"])), self.assertRaises(ipc.ProtocolError):
                ipc.write_message(stream, value)
            self.assertEqual(stream.getvalue(), b"")

    def test_capacity_failure_preserves_primary_backup_and_can_retry(self):
        with patch.object(persistence, "MAX_STATE_BYTES", 4096):
            self.assertTrue(self.store.save({"jobs": []}))
            self.assertTrue(self.store.save({"jobs": [], "paused": True}))
            originals = [path.read_bytes() for path in (self.store.filename, self.store.backup)]
            self.assertFalse(self.store.save({"jobs": [], "padding": "圖" * 5000}))
            status = self.store.status()
            self.assertEqual(status["error_code"], "state_too_large")
            self.assertFalse(status["blocked"])
            self.assertFalse(status["attempted_bytes_exact"])
            self.assertGreater(status["attempted_bytes"], 4096)
            self.store.record_failure(preserve=True)
            self.assertEqual(self.store.status()["error"], persistence.CAPACITY_ERROR)
            self.assertEqual([path.read_bytes() for path in (self.store.filename, self.store.backup)], originals)
            self.assertFalse(list(self.store.filename.parent.glob("*.tmp")))
            self.assertTrue(self.store.save({"jobs": []}))
            self.assertEqual(self.store.status()["error_code"], "")
            self.assertTrue(self.store.status()["healthy"])
            self.assertFalse(self.store.status()["capacity_warning"])

    def test_oversize_primary_or_backup_blocks_overwrites_even_without_load(self):
        for oversized in ("primary", "backup"):
            for load_first in (False, True):
                with self.subTest(oversized=oversized, load_first=load_first), patch.object(persistence, "MAX_STATE_BYTES", 4096):
                    self.store.filename.write_bytes(b"x" * (4097 if oversized == "primary" else 1))
                    self.store.backup.write_bytes(b"x" * (4097 if oversized == "backup" else 1))
                    originals = [path.read_bytes() for path in (self.store.filename, self.store.backup)]
                    store = persistence.StateStore(self.store.filename)
                    if load_first:
                        self.assertIsNone(store.load())
                    self.assertFalse(store.save({"jobs": []}))
                    self.assertTrue(store.status()["blocked"])
                    self.assertEqual(store.status()["error_code"], "state_read_too_large")
                    self.assertEqual([path.read_bytes() for path in (store.filename, store.backup)], originals)
                    self.assertFalse(list(store.filename.parent.glob("state.corrupt-*")))

    def test_bounded_read_detects_growth_after_stat(self):
        contents = io.BytesIO(b"x" * 5000)
        path = SimpleNamespace(stat=lambda: SimpleNamespace(st_size=100), open=lambda mode: contents)
        with patch.object(persistence, "MAX_STATE_BYTES", 4096), self.assertRaises(JSONBudgetError) as failure:
            self.store._read(path)
        self.assertEqual(failure.exception.observed_bytes, 4097)

    def test_near_capacity_is_visible_after_save_and_restore(self):
        value = {"jobs": [], "schema_version": persistence.SCHEMA_VERSION, "padding": ""}
        value["padding"] = "x" * (900 - len(encode_json(value, 1000, indent=2)))
        with patch.object(persistence, "MAX_STATE_BYTES", 1000):
            store = persistence.StateStore(self.store.filename)
            self.assertTrue(store.save(value))
            self.assertEqual(store.status()["saved_bytes"], 900)
            self.assertTrue(store.status()["capacity_warning"])
            restored = persistence.StateStore(self.store.filename)
            self.assertIsNotNone(restored.load())
            self.assertEqual(restored.status()["saved_bytes"], 900)
            self.assertTrue(restored.status()["capacity_warning"])

    def test_writer_preserves_specific_capacity_error_and_recovers_next_generation(self):
        writer = StateWriter(lambda value: self.store.save(thaw_snapshot(value)),
                             lambda: self.store.record_failure(preserve=True))
        try:
            with patch.object(persistence, "MAX_STATE_BYTES", 4096):
                generation = writer.submit(freeze_snapshot({"jobs": [], "padding": "x" * 5000}))
                self.assertFalse(writer.wait(generation))
                self.assertEqual(self.store.status()["error_code"], "state_too_large")
                generation = writer.submit(freeze_snapshot({"jobs": []}))
                self.assertTrue(writer.wait(generation))
                self.assertTrue(self.store.status()["healthy"])
                self.store.record_failure()
                self.assertEqual(self.store.status()["error"], SAVE_ERROR)
        finally:
            writer.close()

    def test_scan_probe_uses_real_plan_and_throttles_cached_progress(self):
        with patch.object(bench.account.time, "monotonic", return_value=10):
            report = bench.measure_scan(2000)
        self.assertEqual(report["files"], 4000)
        self.assertEqual(report["progress_events"], 3)
        self.assertEqual(report["file_references_in_progress"], 8000)
        self.assertGreater(report["plan_bytes"], 100000)
        self.assertTrue(report["cleanup_verified"])

    def test_ipc_probe_and_scaled_boundary_preserve_capacity_contract(self):
        report = bench.measure_ipc(20)
        self.assertTrue(report["roundtrip_verified"])
        report = bench.measure_limits(4096)
        for key in ("exact_limit_accepted", "limit_plus_one_rejected", "no_partial_ipc",
                    "primary_backup_preserved", "smaller_retry_verified"):
            self.assertTrue(report[key])

    def test_capacity_tool_is_in_reviewed_source_package(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn(root / "tools" / "measure_capacity.py", source_files(root))


if __name__ == "__main__":
    unittest.main()
