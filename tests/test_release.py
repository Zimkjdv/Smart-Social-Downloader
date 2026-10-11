from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_source import ROOT_FILES, create_archive, source_files


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ssdl-release-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ROOT_FILES:
            (self.root / name).write_text("source fixture\n", encoding="utf-8")

    def test_archive_excludes_runtime_and_arbitrarily_named_private_exports(self):
        for name in ("data/state.json", "data/x-auth.bin", "downloads/movie.mp4", ".venv/secret",
                     "my-private-export.txt", "static/cookies.json", "chrome-extension/private.bin"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture-private-sentinel", encoding="utf-8")
        archive = self.root / "dist/source.zip"
        create_archive(self.root, archive)
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(len(zipped.namelist()), len(ROOT_FILES))
            self.assertFalse(any(b"fixture-private-sentinel" in zipped.read(name) for name in zipped.namelist()))

    def test_source_with_personal_path_is_rejected_without_echoing_path(self):
        private = "C:" + "/Users/" + "Example/private-file"
        (self.root / "README.md").write_text(private, encoding="utf-8")
        with self.assertRaises(ValueError) as error:
            source_files(self.root)
        self.assertIn("README.md", str(error.exception))
        self.assertNotIn(private, str(error.exception))

    def test_cookie_export_in_allowed_source_is_rejected(self):
        (self.root / "README.md").write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            source_files(self.root)


if __name__ == "__main__":
    unittest.main()
