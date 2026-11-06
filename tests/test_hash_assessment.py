"""Synthetic assessment checks without enabling runtime content deduplication."""
from pathlib import Path
import tempfile
import unittest

from tools import measure_hashing


class HashAssessmentTests(unittest.TestCase):
    def test_streaming_hash_and_benchmark_contract(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "owned"
            report = measure_hashing.accept(root, large_mib=1, small_files=2, rounds=1)
            self.assertTrue(report["passed"])
            self.assertTrue(all(report["checks"].values()))
            self.assertEqual(report["large"]["bytes"], 1024 * 1024)
            self.assertEqual(report["small"]["bytes"], 8192)
            self.assertNotIn(str(root), str(report))

    def test_existing_directory_is_never_reused(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            sentinel = root / "preserve"
            sentinel.write_bytes(b"owned sentinel")
            with self.assertRaises(FileExistsError):
                measure_hashing.accept(root)
            self.assertEqual(sentinel.read_bytes(), b"owned sentinel")

    def test_invalid_sizes_are_rejected_before_creating_files(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "absent"
            for values in ({"large_mib": 0}, {"small_files": 4097}, {"rounds": True}):
                with self.subTest(values=values), self.assertRaises(ValueError):
                    measure_hashing.accept(root, **values)
                self.assertFalse(root.exists())
