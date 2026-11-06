from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools.package_source import ROOT_FILES, create_archive, source_files
from tools.check_source_archive import extract_verified, run_checks


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ssdl-release-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
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

    def write_source(self, name, contents="source fixture\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def test_nested_code_tests_and_helpers_follow_the_explicit_review_boundaries(self):
        allowed = ("ssdl/nested/__init__.py", "ssdl/nested/service.py", "tests/__init__.py",
                   "tests/unit/__init__.py", "tests/unit/test_nested.py", "tests/unit/ui.test.cjs",
                   "tests/helpers/__init__.py", "tests/helpers/nested/fixture.py")
        excluded = ("ssdl/__pycache__/cached.py", "ssdl/data/private.py", "tests/downloads/test_secret.py",
                    "tests/unit/private-export.txt", "tests/unreviewed_helper.py", "other/test_hidden.py",
                    ".venv/test_hidden.py", "tests/.private/test_hidden.py")
        for name in (*allowed, *excluded):
            self.write_source(name)
        selected = {path.relative_to(self.root).as_posix() for path in source_files(self.root)}
        self.assertEqual(selected, set(ROOT_FILES) | set(allowed))

    def test_linked_parent_is_rejected_even_when_it_resolves_inside_root(self):
        source = self.write_source("ssdl/nested/service.py")
        original = Path.lstat
        def metadata(path, *args, **kwargs):
            if path == source.parent:
                return SimpleNamespace(st_mode=stat.S_IFDIR,
                                       st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return original(path, *args, **kwargs)
        # Portable Windows junction fault: do not need symlink privileges in CI.
        with patch.object(Path, "lstat", metadata):
            with self.assertRaisesRegex(ValueError, "Linked source path"):
                source_files(self.root)

    def test_extraction_imports_and_discovers_nested_helpers_without_checkout(self):
        for name in ("tests/__init__.py", "tests/helpers/__init__.py", "tests/unit/__init__.py"):
            self.write_source(name, "")
        self.write_source("tests/helpers/value.py", "VALUE = 42\n")
        self.write_source("tests/unit/test_sample.py", "import unittest\nfrom tests.helpers.value import VALUE\n"
                          "class Sample(unittest.TestCase):\n"
                          "    def test_value(self): self.assertEqual(VALUE, 42)\n")
        archive = self.root / "dist/source.zip"
        files = create_archive(self.root, archive)
        destination = self.root / "unpacked"
        extracted = extract_verified(archive, destination, self.root, files)
        result = subprocess.run([sys.executable, "-E", "-s", "-m", "unittest", "discover",
                                 "-s", "tests", "-t", ".", "-v"], cwd=extracted,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 1 test", result.stderr)

    def test_extraction_rejects_unexpected_duplicate_and_changed_source(self):
        archive = self.root / "dist/source.zip"
        files = create_archive(self.root, archive)
        with zipfile.ZipFile(archive, "a") as zipped:
            zipped.writestr("../private.txt", b"private sentinel")
        with self.assertRaisesRegex(ValueError, "allowlist"):
            extract_verified(archive, self.root / "unpacked", self.root, files)
        self.assertFalse((self.root / "unpacked").exists())
        files = create_archive(self.root, archive)
        self.write_source("README.md", "changed after packaging\n")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            extract_verified(archive, self.root / "unpacked", self.root, files)
        files = create_archive(self.root, archive)
        with zipfile.ZipFile(archive, "a") as zipped, self.assertWarns(UserWarning):
            zipped.writestr("smart-social-downloader/README.md", b"duplicate")
        with self.assertRaisesRegex(ValueError, "allowlist"):
            extract_verified(archive, self.root / "unpacked", self.root, files)

    def test_acceptance_commands_use_extracted_cwd_and_stop_after_a_failure(self):
        with patch("tools.check_source_archive.subprocess.run") as run:
            run_checks(self.root)
        self.assertEqual(run.call_count, 4)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs, {"cwd": self.root, "check": True})
        self.assertIn("-E", run.call_args_list[0].args[0])
        self.assertIn("-t", run.call_args_list[1].args[0])
        self.assertEqual(run.call_args_list[3].args[0][-1], "tools/check_dependency_faults.py")
        with patch("tools.check_source_archive.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, "fixture")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                run_checks(self.root)
        run.assert_called_once()

    def test_extraction_normalizes_the_same_root_alias_as_packaging(self):
        (self.root / "alias-part").mkdir()
        alias = self.root / "alias-part" / ".."
        archive = self.root / "dist/source.zip"
        files = create_archive(alias, archive)
        extracted = extract_verified(archive, self.root / "unpacked", alias, files)
        self.assertEqual((extracted / "README.md").read_bytes(), (self.root / "README.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
