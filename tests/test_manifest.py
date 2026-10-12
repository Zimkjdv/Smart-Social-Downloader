import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ssdl import media_coordinator
from ssdl import media
from ssdl.media_manifest import file_entries, verify_entries


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-manifest-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "downloads"
        self.root.mkdir()
        self.path = Path(self.temp.name) / "manifest.sqlite3"
        self.url = "https://example.org/post"
        self.calls = []

    def source(self, url, root, emit, **kwargs):
        self.calls.append(kwargs)
        path = root / "example.org" / f"Title{len(self.calls)}.mp4"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"complete-source-payload")
        return {"title": f"Title{len(self.calls)}", "quality": "source", "files": [str(path.relative_to(root))],
                "warnings": [], "engine": "fixture", "media_id": "stable-id"}

    def download(self, **kwargs):
        with patch.object(media_coordinator, "_download_source", self.source):
            return media.download(self.url, self.root, lambda event: None, manifest_file=self.path, **kwargs)

    def test_verified_source_does_not_run_engine_twice(self):
        first = self.download()
        second = self.download()
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(second["skipped"])
        self.assertEqual(first["files"], second["files"])

    def test_moved_renamed_deleted_and_changed_files_are_refetched(self):
        for change in ("move", "rename", "delete", "change"):
            with self.subTest(change=change):
                result = self.download(force=True)
                path = self.root / result["files"][0]
                if change in {"move", "rename"}:
                    path.rename(path.with_name("moved-" + change + ".mp4"))
                elif change == "delete":
                    path.unlink()
                else:
                    path.write_bytes(b"changed")
                count = len(self.calls)
                updated = self.download()
                self.assertEqual(len(self.calls), count + 1)
                self.assertEqual(updated["files"], result["files"])
                self.assertEqual(path.read_bytes(), b"complete-source-payload")

    def test_force_and_new_directory_do_not_skip(self):
        self.download()
        self.download(force=True)
        self.root = Path(self.temp.name) / "other"
        self.root.mkdir()
        self.download()
        self.assertEqual(len(self.calls), 3)

    def test_same_size_changed_mtime_is_not_complete(self):
        result = self.download()
        path = self.root / result["files"][0]
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000))
        self.download()
        self.assertEqual(len(self.calls), 2)

    def test_complete_legacy_row_can_seed_manifest(self):
        old = self.source(self.url, self.root, lambda event: None)
        old.update(url=self.url, output_dir=str(self.root), size_bytes=22)
        old["size_bytes"] = sum((self.root / name).stat().st_size for name in old["files"])
        result = self.download(known_jobs=[old])
        self.assertTrue(result["skipped"])
        self.assertEqual(len(self.calls), 1)

    def test_manifest_rejects_partial_outside_and_empty_files(self):
        for name in ("../outside.mp4", "unfinished.mp4.part", "empty.mp4"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"" if name == "empty.mp4" else b"bytes")
            with self.subTest(name=name), self.assertRaises(ValueError):
                file_entries(self.root, [name])
        self.assertFalse(verify_entries(self.root, [{"name": "absent.mp4", "size": 2, "mtime_ns": 1}]))

    def test_youtube_link_variants_share_stable_identity(self):
        urls = ["https://youtu.be/AbcD1234_-x", "https://www.youtube.com/watch?v=AbcD1234_-x&t=3",
                "https://youtube.com/shorts/AbcD1234_-x?feature=share"]
        self.assertEqual(len({media.source_key(url) for url in urls}), 1)
        self.assertNotEqual(media.source_key(urls[0]), media.source_key("https://youtube.com/watch?v=XbcD1234_-x"))
