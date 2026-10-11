import base64
import re
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ssdl import media


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZGQAAAAASUVORK5CYII=")
VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"source-video-payload-and-metadata" * 20
PAYLOADS = {"/one.png": (PNG, "image/png"), "/two.png": (PNG + b"source-metadata", "image/png"), "/video.mp4": (VIDEO, "video/mp4")}


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload, mime = PAYLOADS[self.path]
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_x_image_urls_request_original_without_changing_format(self):
        for url, extension in [
            ("https://pbs.twimg.com/media/sample.jpg:large", "jpg"),
            ("https://pbs.twimg.com/media/sample?format=png&name=small", "png"),
        ]:
            with self.subTest(url=url):
                normalized = media.original_image_url(url)
                query = parse_qs(urlparse(normalized).query)
                self.assertEqual(query["name"], ["orig"])
                self.assertEqual(query["format"], [extension])

    def test_direct_image_preserves_all_source_bytes(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-media-") as directory:
            output = Path(directory)
            result = media.download_image(self.base + "/two.png", output, lambda event: None)
            self.assertEqual((output / result["files"][0]).read_bytes(), PAYLOADS["/two.png"][0])

    @unittest.skipIf(media.gallery_job is None, "gallery-dl is not installed")
    def test_native_gallery_saves_every_photo_and_video_unchanged(self):
        from gallery_dl.extractor.common import Extractor
        from gallery_dl.extractor.message import Message

        base = self.base

        class FixtureExtractor(Extractor):
            category = "fixture"
            subcategory = "post"
            directory_fmt = ("fixture",)
            filename_fmt = "{num}.{extension}"

            def items(self):
                metadata = {"content": "Mixed media post", "count": 3}
                yield Message.Directory, "", dict(metadata)
                for number, path in enumerate(PAYLOADS, 1):
                    yield Message.Url, base + path, {**metadata, "num": number, "extension": Path(path).suffix[1:]}

        with tempfile.TemporaryDirectory(prefix="ssdl-gallery-") as directory:
            output = Path(directory)
            media.configure_gallery(output)
            extractor = FixtureExtractor(re.match(".*", base))
            result = media.download_gallery(extractor, output, lambda event: None)
            self.assertEqual(len(result["files"]), 3)
            for name, source in zip(result["files"], PAYLOADS.values()):
                self.assertEqual((output / name).read_bytes(), source[0])

    @unittest.skipIf(media.gallery_extractor is None, "gallery-dl is not installed")
    def test_x_extractor_selects_orig_photos_and_highest_bitrate_video(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-x-") as directory:
            media.configure_gallery(Path(directory))
            extractor = media.gallery_extractor.find("https://x.com/example/status/1234567890")
            extractor.initialize()
            source_media = [
                {"type": "photo", "media_url_https": "https://pbs.twimg.com/media/example.jpg", "original_info": {"width": 2048, "height": 1365}},
                {"type": "video", "original_info": {"width": 1920, "height": 1080}, "video_info": {"variants": [
                    {"bitrate": 256000, "url": "https://video.twimg.com/low.mp4"},
                    {"bitrate": 2176000, "url": "https://video.twimg.com/high.mp4"},
                    {"url": "https://video.twimg.com/playlist.m3u8"},
                ]}},
            ]
            files = []
            extractor._extract_media({"id_str": "1234567890"}, source_media, files)
            self.assertEqual(len(files), 2)  # Video preview is not saved as a photo.
            self.assertIn("name=orig", files[0]["url"])
            self.assertEqual(list(files[0]["_fallback"]), [])
            self.assertEqual(files[1]["url"], "https://video.twimg.com/high.mp4")
            self.assertFalse(media.gallery_config.get(("extractor",), "fallback"))

    @unittest.skipIf(media.yt_dlp is None, "yt-dlp is not installed")
    def test_video_selection_prefers_high_quality_split_streams(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-video-") as directory:
            options = media.video_options(Path(directory), lambda event: None, [])
            options["no_warnings"] = True
            with media.yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.process_ie_result({
                    "id": "quality-fixture", "title": "Quality fixture", "extractor": "fixture", "webpage_url": "https://example.com/watch",
                    "formats": [
                        {"format_id": "combined720", "url": "https://example.com/combined.mp4", "ext": "mp4", "width": 1280, "height": 720, "vcodec": "avc1", "acodec": "aac"},
                        {"format_id": "video1080", "url": "https://example.com/video.mp4", "ext": "mp4", "width": 1920, "height": 1080, "vcodec": "avc1", "acodec": "none"},
                        {"format_id": "audio", "url": "https://example.com/audio.m4a", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128},
                    ],
                }, download=False)
            self.assertEqual([item["format_id"] for item in info["requested_formats"]], ["video1080", "audio"])
            self.assertEqual(options["postprocessors"], [])


if __name__ == "__main__":
    unittest.main()
