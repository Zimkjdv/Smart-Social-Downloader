"""Native filesystem and real archive acceptance for Pixiv author directories."""
from pathlib import Path
import unittest
from unittest.mock import Mock

from ssdl.media_contracts import DownloadError
from ssdl.pixiv_paths import author_folder
from tests.helpers.pixiv import PixivFixture


class PixivPathTests(unittest.TestCase):
    def test_portable_names_create_real_files_and_preserve_numeric_suffix(self):
        for name in ("作者名稱", 'a/b\\c:d*e?f"g<h>i|j\x00\u202ehide', "名字" * 200, "A" * 400,
                     "CON", ".  ", "cafe\u0301", None):
            with self.subTest(name=name), PixivFixture() as fixture:
                folder = author_folder({"id": 123, "name": name})
                self.assertTrue(folder.endswith("(123)"))
                self.assertLessEqual(len(folder.encode("utf-8")), 165)
                self.assertFalse(any(character in folder for character in '/\\<>:"|?*\x00\u202e'))
                result = fixture.sync(name=name)
                self.assertEqual(result["title"], "Pixiv · " + folder)
                self.assertTrue(all(Path(item).parts[1] == folder for item in result["files"]))
                before = fixture.signature(result["files"])
                again = fixture.sync(name=name)
                self.assertEqual(again["downloaded_file_count"], 0)
                self.assertEqual(fixture.signature(result["files"]), before)

    def test_invalid_author_ids_are_rejected(self):
        for account in (None, "", 0, "0123", "../123", True, "1" * 21):
            with self.subTest(account=account), self.assertRaises(DownloadError) as caught:
                author_folder({"id": account, "name": "作者"})
            self.assertEqual(caught.exception.code, "pixiv_invalid_media")

    def test_same_name_different_authors_have_distinct_folders_and_archive_scopes(self):
        with PixivFixture() as fixture:
            first = fixture.sync(name="同名", account="123")
            before = fixture.signature(first["files"])
            second = fixture.sync(name="同名", account="456")
            self.assertTrue(set(first["files"]).isdisjoint(second["files"]))
            self.assertEqual(second["downloaded_file_count"], 2)
            self.assertEqual(fixture.signature(first["files"]), before)

    def test_complete_legacy_numeric_and_named_folders_are_reused_after_rename(self):
        for folder in ("123", "舊作者名(123)"):
            with self.subTest(folder=folder), PixivFixture() as fixture:
                names = fixture.seed(folder)
                before, quota = fixture.signature(names), Mock()
                result = fixture.sync(name="新作者名", before_post=quota)
                self.assertEqual(set(result["files"]), set(names))
                self.assertEqual(result["skipped_file_count"], 2)
                self.assertEqual(result["downloaded_file_count"], 0)
                self.assertEqual(fixture.signature(names), before)
                quota.assert_not_called()
                self.assertFalse((fixture.root / "pixiv/新作者名(123)").exists())

    def test_partial_legacy_work_keeps_verified_page_and_fills_current_folder(self):
        for folder in ("123", "舊作者名(123)"):
            with self.subTest(folder=folder), PixivFixture() as fixture:
                names = fixture.seed(folder, pages=(0,))
                before = fixture.signature(names)
                result = fixture.sync(name="新作者名")
                self.assertEqual(result["downloaded_file_count"], 1)
                self.assertEqual(result["skipped_file_count"], 1)
                self.assertEqual(fixture.transferred, [str(Path("pixiv/新作者名(123)/100_p1.png"))])
                self.assertEqual(fixture.signature(names), before)
                again = fixture.sync(name="再次更名")
                self.assertEqual(again["downloaded_file_count"], 0)
                self.assertEqual(set(again["files"]), set(result["files"]))

    def test_unrecorded_or_wrong_author_folder_never_proves_completion(self):
        for recorded, folder in ((False, "作者(123)"), (True, "別人(456)")):
            with self.subTest(recorded=recorded, folder=folder), PixivFixture() as fixture:
                old = fixture.seed(folder, record=recorded)
                result = fixture.sync()
                self.assertEqual(result["downloaded_file_count"], 2)
                if "456" in folder:
                    self.assertTrue(set(old).isdisjoint(result["files"]))

    def test_changed_root_refetches_and_leaves_old_media_unchanged(self):
        with PixivFixture() as fixture:
            original = fixture.sync()
            before = fixture.signature(original["files"])
            other = fixture.workspace / "different root 圖片"
            other.mkdir()
            result = fixture.sync(root=other)
            self.assertEqual(result["downloaded_file_count"], 2)
            self.assertTrue(all((other / name).is_file() for name in result["files"]))
            self.assertEqual(fixture.signature(original["files"]), before)

    def test_whole_author_folder_relocation_refetches_at_recorded_location(self):
        with PixivFixture() as fixture:
            original = fixture.sync()
            folder = fixture.root / "pixiv/作者(123)"
            moved = fixture.root / "pixiv/moved-author"
            # Both resolved targets belong to this fresh fixture's media root.
            self.assertTrue(folder.resolve().is_relative_to(fixture.root.resolve()))
            self.assertTrue(moved.resolve().is_relative_to(fixture.root.resolve()))
            folder.rename(moved)
            preserved = {path.name: path.read_bytes() for path in moved.iterdir()}
            result = fixture.sync()
            self.assertEqual(result["downloaded_file_count"], 2)
            self.assertEqual(set(result["files"]), set(original["files"]))
            self.assertEqual({path.name: path.read_bytes() for path in moved.iterdir()}, preserved)

    def test_file_lost_during_quota_wait_is_rechecked_before_transfer(self):
        with PixivFixture() as fixture:
            retained = fixture.seed("123", pages=(0,))[0]
            def remove_page():
                (fixture.root / retained).unlink()
            result = fixture.sync(before_post=remove_page)
            self.assertEqual(result["downloaded_file_count"], 2)
            self.assertEqual(result["skipped_file_count"], 0)
