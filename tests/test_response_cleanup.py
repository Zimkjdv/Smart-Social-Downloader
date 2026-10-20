"""Preserve readable error responses until release or owned engine closure."""
import gc
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import warnings

from ssdl.request_policy import RequestPolicy


class ResponseCleanupTests(unittest.TestCase):
    def engine(self, error):
        engine = SimpleNamespace(urlopen=Mock(side_effect=error), add_close_hook=Mock())
        policy = RequestPolicy()
        policy.before_request = Mock()
        policy.wrap_yt_dlp(engine)
        return engine

    def error(self, payload=b"readable error body", status=404):
        from yt_dlp.networking.common import Response
        from yt_dlp.networking.exceptions import HTTPError
        response = Response(io.BytesIO(payload), "https://public.example/media", {}, status=status)
        response.close = Mock(wraps=response.close)
        return HTTPError(response)

    def test_error_remains_readable_until_engine_close_and_closes_once(self):
        error = self.error()
        engine = self.engine(error)
        for _ in range(2):
            with self.assertRaises(type(error)) as caught:
                engine.urlopen("https://public.example/media")
            self.assertIs(caught.exception, error)
        self.assertEqual(error.response.read(), b"readable error body")
        error.response.close.assert_not_called()
        self.assertEqual(engine.add_close_hook.call_count, 1)
        close = engine.add_close_hook.call_args.args[0]
        close()
        close()
        error.response.close.assert_called_once()

    def test_releasing_error_closes_response_without_retaining_exception(self):
        from yt_dlp.networking.exceptions import HTTPError
        response = self.error().response
        engine = SimpleNamespace(add_close_hook=Mock())
        def opened(url):
            raise HTTPError(response)
        engine.urlopen = opened
        policy = RequestPolicy()
        policy.before_request = Mock()
        policy.wrap_yt_dlp(engine)
        with self.assertRaises(HTTPError):
            engine.urlopen("https://public.example/media")
        gc.collect()
        response.close.assert_called_once()

    def test_close_failure_is_visible_and_does_not_stop_other_cleanup(self):
        first, second = self.error(), self.error()
        first.response.close.side_effect = OSError("secret-path")
        engine = self.engine([first, second])
        with self.assertRaises(type(first)):
            engine.urlopen("https://public.example/media")
        original = engine.urlopen
        with self.assertRaises(type(second)):
            engine.urlopen("https://public.example/media")
        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always", ResourceWarning)
            engine.add_close_hook.call_args.args[0]()
        self.assertEqual(len(records), 1)
        self.assertNotIn("secret-path", str(records[0].message))
        second.response.close.assert_called_once()
        self.assertIs(engine.urlopen, original)

    def test_rate_limit_still_closes_immediately_and_keeps_cooldown(self):
        from ssdl.request_policy import RateLimited
        error = self.error(status=429)
        engine = self.engine(error)
        with self.assertRaises(RateLimited):
            engine.urlopen("https://public.example/media")
        error.response.close.assert_called_once()

    def test_delegated_job_closes_owned_engines_once_and_preserves_borrowed_session(self):
        from ssdl import gallery_adapter as gallery
        for mode in ("success", "failure", "prepare_failure"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="ssdl-engine-close-") as directory:
                root = Path(directory)
                output = root / "fixture.mp4"
                output.write_bytes(b"original")
                engine = Mock()
                borrowed_session = Mock()
                extractor = SimpleNamespace(url="https://public.example/post", category="fixture", directory_fmt=(),
                                            session=borrowed_session)
                class Job:
                    def __init__(self, extractor, parent=None):
                        self.extractor = extractor
                        self.downloader = SimpleNamespace(_prepare=Mock())
                    def get_downloader(self, scheme):
                        return self.downloader
                    def run(self):
                        downloader = self.get_downloader("ytdl")
                        downloader._prepare(engine)
                        downloader._prepare(engine)
                        if mode == "failure":
                            from ssdl.request_policy import RateLimited
                            raise RateLimited("fixture")
                        self.out.success(str(output))
                        return 0
                with patch.object(gallery.engines.gallery_job, "DownloadJob", Job), patch.object(gallery, "_pace_gallery"), \
                     patch.object(gallery.request_policy.POLICY, "wrap_yt_dlp"), \
                     patch.object(gallery, "install_video_quality", side_effect=RuntimeError("fixture") if mode == "prepare_failure" else None):
                    if mode == "success":
                        self.assertEqual(gallery.download_gallery(extractor, root, lambda event: None)["files"], ["fixture.mp4"])
                    elif mode == "failure":
                        with self.assertRaises(gallery.DownloadError) as failure:
                            gallery.download_gallery(extractor, root, lambda event: None)
                        self.assertEqual(failure.exception.code, "rate_limited")
                    else:
                        with self.assertRaisesRegex(RuntimeError, "fixture"):
                            gallery.download_gallery(extractor, root, lambda event: None)
                engine.close.assert_called_once()
                borrowed_session.close.assert_not_called()
