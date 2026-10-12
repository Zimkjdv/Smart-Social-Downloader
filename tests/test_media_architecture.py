"""N06 adapter boundaries and synthetic X scan/archive acceptance."""
import ast
from http.client import HTTPMessage
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from ssdl import media, media_contracts as contracts, media_engines as engines
from ssdl import media_coordinator as coordinator, image_adapter, gallery_adapter as gallery
from ssdl import video_adapter, x_account_media as x_media, request_policy
from tools.package_source import source_files


class MediaBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ssdl-adapters-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "fixture.mp4").write_bytes(b"synthetic-complete-media")
        self.result = {"files": ["fixture.mp4"], "title": "fixture", "quality": "source", "warnings": []}

    def test_facade_keeps_shared_entry_points_and_error_identity(self):
        for name, owner in (("download", coordinator), ("download_web_media", coordinator),
                            ("download_video", video_adapter), ("download_gallery", gallery),
                            ("download_image", image_adapter), ("download_x_account", x_media),
                            ("download_x_public", x_media), ("source_key", contracts),
                            ("error_info", contracts), ("DownloadError", contracts),
                            ("engine_status", engines), ("ffmpeg_path", engines)):
            self.assertIs(getattr(media, name), getattr(owner, name), name)
        for owner in (coordinator, video_adapter, gallery, image_adapter, x_media):
            self.assertIs(owner.DownloadError, contracts.DownloadError)
        self.assertIs(media._gallery_lock, gallery.GALLERY_LOCK)

    def test_implementations_do_not_import_the_facade_and_ship_in_source_archive(self):
        modules = (contracts, engines, coordinator, video_adapter, gallery, image_adapter, x_media)
        root = Path(media.__file__).resolve().parents[1]
        included = set(source_files(root))
        for module in modules:
            path = Path(module.__file__).resolve()
            self.assertIn(path, included)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, {"ssdl.media", "media"}, str(path))
                    if node.module in {None, "ssdl"}:
                        self.assertNotIn("media", {name.name for name in node.names}, str(path))
                elif isinstance(node, ast.Import):
                    self.assertNotIn("ssdl.media", {name.name for name in node.names}, str(path))

    def test_replaced_child_policy_reaches_shared_transport_and_429_backoff(self):
        policy = Mock()
        policy.limit.return_value = 180
        headers = HTTPMessage()
        headers["Retry-After"] = "180"
        error = HTTPError("https://cdn.example/media", 429, "synthetic limit", headers, None)
        with patch.object(request_policy, "POLICY", policy), patch.object(contracts, "urlopen", side_effect=error):
            with self.assertRaises(request_policy.RateLimited):
                contracts.paced_urlopen("https://cdn.example/media")
        policy.before_request.assert_called_once()
        policy.limit.assert_called_once_with("180")

    def test_unsupported_video_uses_generic_fallback_but_partial_files_never_do(self):
        with patch.object(engines, "gallery_extractor", None), \
             patch.object(video_adapter, "download_video", side_effect=media.DownloadError("unsupported", code="unsupported_url")), \
             patch.object(coordinator, "download_web_media", return_value=dict(self.result)) as fallback:
            result = media.download("https://example.org/page", self.root, lambda event: None,
                                    video_quality="720", dynamic_capture=True)
        self.assertEqual(result["video_quality"], "720")
        self.assertEqual(fallback.call_args.kwargs["video_quality"], "720")
        self.assertTrue(fallback.call_args.kwargs["dynamic_capture"])
        for code in ("unsupported_url", "rate_limited", "unsafe_target", "download_failed"):
            with self.subTest(code=code), patch.object(engines, "gallery_extractor", None), \
                 patch.object(video_adapter, "download_video", side_effect=media.DownloadError("partial", ["fixture.mp4"], code=code)), \
                 patch.object(coordinator, "download_web_media") as fallback:
                with self.assertRaises(media.DownloadError):
                    media.download("https://example.org/page", self.root, lambda event: None)
                fallback.assert_not_called()

    def test_direct_images_bypass_gallery_video_and_keep_original_quality(self):
        with patch.object(image_adapter, "download_image", return_value=dict(self.result)) as images, \
             patch.object(gallery, "configure_gallery") as configured, \
             patch.object(video_adapter, "download_video") as video:
            result = media.download("https://example.org/image.png", self.root, lambda event: None, video_quality="720")
        self.assertEqual(result["video_quality"], "best")
        images.assert_called_once()
        configured.assert_not_called()
        video.assert_not_called()

    def test_gallery_routing_holds_shared_lock_and_never_sends_x_login_to_other_platforms(self):
        extractor = SimpleNamespace(category="reddit")
        def transfer(*args, **kwargs):
            self.assertTrue(gallery.GALLERY_LOCK.locked())
            return dict(self.result)
        with patch.object(engines, "gallery_extractor", SimpleNamespace(find=Mock(return_value=extractor))), \
             patch.object(gallery, "configure_gallery") as configured, \
             patch.object(gallery, "download_gallery", side_effect=transfer) as downloaded:
            media.download("https://reddit.com/synthetic", self.root, lambda event: None,
                           x_cookie_file="synthetic-only", x_cookies={"auth_token": "synthetic-only"}, video_quality="720")
        self.assertEqual(configured.call_args.kwargs["x_cookie_file"], "")
        self.assertIsNone(configured.call_args.kwargs["x_cookies"])
        self.assertEqual(downloaded.call_args.kwargs["video_quality"], "720")
        self.assertFalse(gallery.GALLERY_LOCK.locked())

    def test_public_x_post_routes_to_x_service_and_profile_requires_login(self):
        find = Mock()
        with patch.object(engines, "gallery_extractor", SimpleNamespace(find=find)), \
             patch.object(gallery, "configure_gallery"), \
             patch.object(x_media, "download_x_public", return_value=dict(self.result)) as public:
            media.download("https://x.com/example/status/1234567890", self.root, lambda event: None)
            self.assertEqual(public.call_args.args[1], "1234567890")
            with self.assertRaises(media.DownloadError) as failure:
                media.download("https://x.com/example", self.root, lambda event: None)
        self.assertEqual(failure.exception.code, "x_login_required")
        find.assert_not_called()


@unittest.skipIf(engines.gallery_extractor is None, "gallery-dl is required")
class XAccountBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ssdl-account-adapter-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.archive = self.root / "data" / "archive.sqlite3"
        self.events, self.transfers = [], []
        self.gate, self.checkpoint = Mock(), Mock()
        self.policy = Mock()

    def sync(self, *, count=2, partial=False, incomplete=False):
        from gallery_dl.extractor.common import Message
        metadata = {"tweet_id": "1234567890", "author": {"name": "example"}, "user": {"name": "example"}, "count": count}
        def items():
            yield Message.Directory, "", dict(metadata)
            for number in range(1, count + (0 if incomplete else 1)):
                yield Message.Url, f"https://cdn.example/synthetic-{number}.jpg", {**metadata, "num": number, "extension": "jpg"}
        timeline = SimpleNamespace(category="twitter", subcategory="timeline", items=items, status=0,
                                   session=Mock(), initialize=Mock(), _init_session=Mock())
        def download(snapshot, root, emit):
            self.assertTrue(gallery.GALLERY_LOCK.locked())
            files = []
            for kind, url, data in snapshot.items():
                if kind != Message.Url:
                    continue
                name = str(Path("twitter") / "example" / f"{data['tweet_id']}_{data['num']}.jpg")
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"synthetic-original-media")
                files.append(name)
                self.transfers.append(name)
                emit({"files": list(files), "downloaded_bytes": 0})
                if partial:
                    raise media.DownloadError("synthetic partial failure", files, code="network")
            return {"files": files, "downloaded_file_count": len(files)}
        with patch.object(engines, "gallery_extractor", SimpleNamespace(find=Mock(return_value=timeline))), \
             patch.object(gallery, "download_gallery", side_effect=download), \
             patch.object(request_policy, "POLICY", self.policy):
            return media.download_x_account("https://x.com/example", self.root, self.events.append,
                archive_file=self.archive, before_post=self.gate, checkpoint=self.checkpoint,
                x_cookies={"auth_token": "synthetic-session"})

    def test_complete_scan_then_download_archive_reuse_and_missing_file_refetch(self):
        first = self.sync()
        self.assertEqual(len(first["files"]), 2)
        self.assertEqual(len(self.transfers), 2)
        complete = next(event for event in self.events if event.get("profile_scan_complete"))
        self.assertEqual(complete["profile_total_files"], 2)
        self.assertEqual(complete["profile_downloaded_files"], 0)
        self.policy.job_completed.assert_called_once()
        self.policy.wrap_session.assert_called()
        self.gate.assert_called_once()
        self.events.clear()
        second = self.sync()
        self.assertEqual(second["files"], first["files"])
        self.assertEqual(len(self.transfers), 2)
        self.assertEqual(self.events[-1]["profile_skipped"], 1)
        (self.root / first["files"][0]).rename(self.root / "moved-synthetic.jpg")
        self.events.clear()
        third = self.sync()
        self.assertEqual(len(third["files"]), 2)
        self.assertEqual(len(self.transfers), 3)
        self.assertEqual(self.transfers[-1], first["files"][0])
        self.assertTrue((self.root / "moved-synthetic.jpg").is_file())
        self.assertFalse(gallery.GALLERY_LOCK.locked())
        self.assertFalse(list(self.archive.parent.glob("x-scan-*")))

    def test_partial_download_preserves_files_error_and_does_not_mark_post_complete(self):
        with self.assertRaises(media.DownloadError) as failure:
            self.sync(partial=True)
        self.assertEqual(failure.exception.code, "network")
        self.assertEqual(len(failure.exception.files), 1)
        self.assertNotEqual(self.events[-1]["profile_stage"], "done")
        self.assertFalse(gallery.GALLERY_LOCK.locked())
        self.assertFalse(list(self.archive.parent.glob("x-scan-*")))
        result = self.sync()
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(len(self.transfers), 3)

    def test_incomplete_scan_never_starts_downloads(self):
        with self.assertRaises(media.DownloadError):
            self.sync(incomplete=True)
        self.assertFalse(self.transfers)
        self.gate.assert_not_called()
        self.assertFalse(self.events[-1]["profile_scan_complete"])
        self.assertFalse(gallery.GALLERY_LOCK.locked())


if __name__ == "__main__":
    unittest.main()
