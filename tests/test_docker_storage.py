"""Backup/restore regressions with real tar files, media and SQLite manifests."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from ssdl.image_history import ImageHistory

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "docker" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DockerStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-storage-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        runtime = load_module("ssdl_storage_test_runtime", "runtime.py")
        with patch.dict(sys.modules, {"runtime": runtime}):
            self.storage = load_module("ssdl_storage_test", "storage.py")
        self.data, self.media, self.backups = (self.root / name for name in ("data", "media", "backups"))
        for path in (self.data, self.media, self.backups):
            path.mkdir()
        self.storage.VOLUMES = {"data": self.data, "media": self.media}
        self.storage.BACKUPS = self.backups

    def platform_io(self):
        stack = ExitStack()
        if os.name == "nt":
            # Linux open flags/directory fsync are covered by the real container gate.
            stack.enter_context(patch.object(self.storage, "open_regular", lambda path: path.open("rb")))
            stack.enter_context(patch.object(self.storage, "sync_directory", lambda path: None))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_restored_media_remains_reusable_by_its_original_sqlite_manifest(self):
        original = self.media / "original.bin"
        original.write_bytes(b"synthetic complete original")
        timestamp = 1_700_000_000_123456700  # Exactly representable on Windows NTFS too.
        os.utime(original, ns=(timestamp, timestamp))
        timestamp = original.stat().st_mtime_ns
        history = ImageHistory(self.data / "image-history.sqlite3", self.media)
        try:
            history.record("https://example.invalid/one", {"files": ["original.bin"]})
            self.assertIsNotNone(history.lookup("https://example.invalid/one"))
        finally:
            history.close()

        with self.platform_io():
            self.storage.backup()
            archive = next(self.backups.glob("ssdl-*.tar"))
            self.storage.VOLUMES = {name: self.root / (name + "-restored") for name in ("data", "media")}
            for path in self.storage.VOLUMES.values():
                path.mkdir()
            self.storage.restore(archive.name)
        recovered = self.storage.VOLUMES["media"] / original.name
        self.assertEqual(recovered.read_bytes(), original.read_bytes())
        self.assertEqual(recovered.stat().st_mtime_ns, timestamp)
        history = ImageHistory(self.storage.VOLUMES["data"] / "image-history.sqlite3", self.storage.VOLUMES["media"])
        try:
            # A restored installation uses the fixed /downloads scope. Simulate
            # that same scope while using separate native temporary directories.
            history.connection.execute("UPDATE images SET directory=?", (history.scope,))
            history.connection.commit()
            self.assertIsNotNone(history.lookup("https://example.invalid/one"))
        finally:
            history.close()

    def test_timestamp_metadata_preserves_nanoseconds_and_accepts_legacy_seconds(self):
        entry = tarfile.TarInfo("media/original.bin")
        entry.mtime = 1_700_000_000
        self.assertEqual(self.storage.member_mtime_ns(entry), 1_700_000_000_000000000)
        for value in ("1700000000123456789", "-123456789"):
            entry.pax_headers["SSDL.mtime_ns"] = value
            self.assertEqual(self.storage.member_mtime_ns(entry), int(value))
        for value in ("not-a-time", "1.25", "9" * 100, str(2**63)):
            entry.pax_headers["SSDL.mtime_ns"] = value
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.storage.member_mtime_ns(entry)
        entry.pax_headers.clear()
        for value in (float("nan"), float("inf"), 10**30):
            entry.mtime = value
            with self.assertRaises(RuntimeError):
                self.storage.member_mtime_ns(entry)

    def test_timestamp_loss_on_destination_refuses_promotion(self):
        original = self.media / "original.bin"
        original.write_bytes(b"synthetic bytes")
        os.utime(original, ns=(1_700_000_000_123456700, 1_700_000_000_123456700))
        with self.platform_io():
            self.storage.backup()
            archive = next(self.backups.glob("ssdl-*.tar"))
            self.storage.VOLUMES = {name: self.root / (name + "-restored") for name in ("data", "media")}
            for path in self.storage.VOLUMES.values():
                path.mkdir()
            with patch.object(self.storage.os, "utime", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "cannot preserve"):
                    self.storage.restore(archive.name)
        self.assertTrue(all(not list(path.iterdir()) for path in self.storage.VOLUMES.values()))
