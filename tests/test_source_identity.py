"""Conservative Pixiv identity and file-verified legacy manifest promotion."""
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from ssdl import media_coordinator
from ssdl.media_contracts import pixiv_artwork_id, source_key
from ssdl.media_manifest import MediaManifest


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="ssdl-identity-")))
        self.media = self.root / "media"
        self.media.mkdir()
        self.database = self.root / "data/manifest.sqlite3"
        self.calls = []
        self._source_route = media_coordinator._download_source
        self.enterContext(patch.object(media_coordinator, "_download_source", side_effect=self.source))

    def source(self, url, root, emit, **options):
        self.calls.append(options)
        artwork = pixiv_artwork_id(url) or "100"
        name = str(Path("pixiv") / f"original-{artwork}-{len(self.calls)}.png")
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"synthetic complete original")
        return {"files": [name], "title": "Synthetic artwork", "engine": "gallery-dl",
                "media_id": artwork, "quality": "original", "warnings": []}

    def download(self, url, **options):
        return media_coordinator.download(url, self.media, lambda value: None,
                                          manifest_file=self.database, **options)

    def seed_legacy(self, url, *, quality="best", selection="", stored_quality=None):
        result = self.source(url, self.media, lambda value: None)
        result.update(video_quality=stored_quality or quality, selected_media=selection)
        key = "url:" + url.split("#", 1)[0]
        if quality != "best":
            key += "\nvideo_quality=" + quality
        if selection:
            key += "\nselected_media=" + selection
        archive = MediaManifest(self.database, self.media)
        try:
            archive.record(key, result)
        finally:
            archive.close()
        return result, key

    def test_reviewed_whole_work_variants_have_one_identity(self):
        urls = ("https://www.pixiv.net/artworks/100", "http://pixiv.net/artworks/100/",
                "https://www.pixiv.net/en/artworks/100?utm_source=share#view",
                "https://pixiv.net/i/100", "https://www.pixiv.net/member_illust.php?mode=medium&illust_id=100",
                "https://www.pixiv.net/member_illust.php?illust_id=100&utm_medium=share",
                "https://www.pixiv.net/member_illust.php?illust_id=%31%30%30")
        self.assertEqual({source_key(url) for url in urls}, {"pixiv-artwork:100"})
        self.assertNotEqual(source_key(urls[0]), source_key("https://www.pixiv.net/artworks/101"))
        first = self.download(urls[0])
        before = (self.media / first["files"][0]).stat().st_mtime_ns
        for url in urls[1:]:
            self.assertTrue(self.download(url)["skipped"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((self.media / first["files"][0]).stat().st_mtime_ns, before)

    def test_unknown_queries_and_unreviewed_forms_keep_url_identity(self):
        base = "https://www.pixiv.net"
        for url in (base + "/artworks/100?page=1", base + "/artworks/100?token=SIGNED",
                    base + "/artworks/100?download=1", base + "/ja/artworks/100",
                    base + "/artworks/unlisted/private", base + "/users/100", base + "/artworks/0100",
                    base + "/member_illust.php?illust_id=100&illust_id=101",
                    base + "/member_illust.php?illust_id=100&mode=manga",
                    "https://www.pixiv.net:0/artworks/100", "https://www.pixiv.net:443/artworks/100",
                    "https://www.pixiv.net:/artworks/100", "https://@www.pixiv.net/artworks/100",
                    "https://user@www.pixiv.net/artworks/100", "https://evil.example/artworks/100",
                    base + "/artworks/100?" + "&".join("utm_source=x" for _ in range(65))):
            with self.subTest(form="unreviewed URL"):
                self.assertIsNone(pixiv_artwork_id(url))
                self.assertTrue(source_key(url).startswith("url:"))
        self.assertNotEqual(source_key(base + "/artworks/100?page=1"), source_key(base + "/artworks/100?page=2"))

    def test_quality_and_selected_media_have_independent_completion_records(self):
        base, variant = "https://www.pixiv.net/artworks/100", "https://pixiv.net/en/artworks/100"
        self.download(base)
        self.download(base, video_quality="720")
        self.download(base, video_quality="720", selected_media="a" * 24)
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(self.download(variant)["skipped"])
        self.assertTrue(self.download(variant, video_quality="720")["skipped"])
        self.assertTrue(self.download(variant, video_quality="720", selected_media="a" * 24)["skipped"])
        self.assertEqual(len(self.calls), 3)

    def test_exact_legacy_key_is_verified_promoted_and_preserved(self):
        url = "https://www.pixiv.net/en/artworks/100?utm_source=old"
        result, legacy = self.seed_legacy(url)
        path = self.media / result["files"][0]
        before = path.stat().st_mtime_ns
        self.assertTrue(self.download(url)["skipped"])
        self.assertTrue(self.download("https://pixiv.net/i/100")["skipped"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(path.stat().st_mtime_ns, before)
        archive = MediaManifest(self.database, self.media)
        try:
            self.assertIsNotNone(archive.lookup(legacy))
            self.assertIsNotNone(archive.lookup("pixiv-artwork:100"))
        finally:
            archive.close()

    def test_legacy_preference_suffixes_remain_separate(self):
        url = "https://www.pixiv.net/en/artworks/100"
        self.seed_legacy(url, quality="720", selection="a" * 24)
        self.assertTrue(self.download(url, video_quality="720", selected_media="a" * 24)["skipped"])
        self.assertEqual(len(self.calls), 1)
        self.download(url, video_quality="720")
        self.download(url)
        self.assertEqual(len(self.calls), 3)

    def test_invalid_or_moved_legacy_files_are_refetched_not_promoted(self):
        for index, change in enumerate(("missing", "moved", "mtime", "size"), 100):
            with self.subTest(change=change):
                url = "https://www.pixiv.net/artworks/" + str(index)
                old, _ = self.seed_legacy(url)
                path = self.media / old["files"][0]
                if change == "missing":
                    path.unlink()
                elif change == "moved":
                    target = path.with_name("moved-" + path.name)
                    self.assertTrue(target.resolve().is_relative_to(self.media.resolve()))
                    path.rename(target)
                elif change == "mtime":
                    value = path.stat()
                    os.utime(path, ns=(value.st_atime_ns, value.st_mtime_ns + 1000000))
                else:
                    path.write_bytes(b"modified")
                before = len(self.calls)
                new = self.download(url)
                self.assertEqual(len(self.calls), before + 1)
                self.assertTrue(self.calls[-1]["force"])
                self.assertEqual(new["files"], old["files"])
                if change == "moved":
                    self.assertTrue(target.exists())

    def test_explicit_force_and_new_root_do_not_reuse_legacy_files(self):
        url = "https://www.pixiv.net/en/artworks/100"
        old, _ = self.seed_legacy(url)
        self.download(url, force=True)
        self.assertEqual(len(self.calls), 2)
        original = self.media / old["files"][0]
        before = original.read_bytes()
        self.media = self.root / "new-media"
        self.media.mkdir()
        self.download(url)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(original.read_bytes(), before)

    def test_known_history_variant_can_seed_canonical_manifest(self):
        old_url = "https://www.pixiv.net/en/artworks/100?utm_source=old"
        old = self.source(old_url, self.media, lambda value: None)
        old.update(url=old_url, output_dir=str(self.media), size_bytes=(self.media / old["files"][0]).stat().st_size)
        result = self.download("https://pixiv.net/i/100", known_jobs=[old])
        self.assertTrue(result["skipped"])
        self.assertEqual(len(self.calls), 1)

    def test_legacy_metadata_must_match_requested_preference(self):
        url = "https://www.pixiv.net/artworks/100"
        self.seed_legacy(url, stored_quality="720")
        self.download(url)
        self.assertEqual(len(self.calls), 2)

    def test_unknown_query_variants_and_unanchored_legacy_hashes_are_not_guessed(self):
        base = "https://www.pixiv.net/artworks/100"
        self.download(base + "?page=1")
        self.download(base + "?page=2")
        self.assertEqual(len(self.calls), 2)
        self.seed_legacy("https://www.pixiv.net/en/artworks/101?utm_source=forgotten")
        self.download("https://www.pixiv.net/artworks/101")
        self.assertEqual(len(self.calls), 4)

    def test_file_change_during_promotion_keeps_original_verification_evidence(self):
        url = "https://www.pixiv.net/artworks/100"
        old, legacy = self.seed_legacy(url)
        target = self.media / old["files"][0]
        original = MediaManifest.lookup
        injected = []
        def changed(archive, key, *, verify=True):
            value = original(archive, key, verify=verify)
            if key == legacy and verify and value and not injected:
                stat = target.stat()
                os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000))
                injected.append(True)
            return value
        with patch.object(MediaManifest, "lookup", changed):
            result = self.download(url)
        self.assertEqual(injected, [True])
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(result.get("skipped", False))

    def test_reviewed_variants_route_gallery_through_canonical_whole_work_url(self):
        # Call the real routing function, not this fixture's transport replacement.
        route = self._source_route
        for url in ("http://pixiv.net/i/100", "https://www.pixiv.net/member_illust.php?illust_id=%31%30%30"):
            with self.subTest(form="reviewed route"), \
                 patch.object(media_coordinator.gallery, "configure_gallery"), \
                 patch.object(media_coordinator.engines.gallery_extractor, "find", return_value=SimpleNamespace(category="pixiv")) as find, \
                 patch.object(media_coordinator.gallery, "download_gallery", return_value={"synthetic": True}):
                result = route(url, self.media, lambda value: None, pixiv_refresh_token="SYNTHETIC_PIXIV_TOKEN")
                find.assert_called_once_with("https://www.pixiv.net/artworks/100")
                self.assertTrue(result["synthetic"])

    def test_missing_canonical_file_does_not_fall_back_to_another_legacy_copy(self):
        url = "https://www.pixiv.net/artworks/100"
        current = self.download(url)
        old, _ = self.seed_legacy(url)
        original = self.media / current["files"][0]
        moved = original.with_name("moved-" + original.name)
        self.assertTrue(moved.resolve().is_relative_to(self.media.resolve()))
        original.rename(moved)
        result = self.download(url)
        self.assertEqual(len(self.calls), 3)
        self.assertFalse(result.get("skipped", False))
        self.assertEqual(result["files"], current["files"])
        self.assertTrue(moved.exists())
        self.assertTrue((self.media / old["files"][0]).exists())

    def test_promotion_does_not_overwrite_another_writers_canonical_record(self):
        url = "https://www.pixiv.net/artworks/100"
        _, legacy = self.seed_legacy(url)
        current = self.source(url, self.media, lambda value: None)
        original = MediaManifest.lookup
        injected = []
        def published(archive, key, *, verify=True):
            value = original(archive, key, verify=verify)
            if key == legacy and verify and value and not injected:
                other = MediaManifest(self.database, self.media)
                try:
                    other.record("pixiv-artwork:100", current)
                finally:
                    other.close()
                injected.append(True)
            return value
        with patch.object(MediaManifest, "lookup", published):
            result = self.download(url)
        self.assertEqual(injected, [True])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["files"], current["files"])
        self.assertEqual(len(self.calls), 2)
