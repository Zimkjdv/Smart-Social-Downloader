from collections import Counter
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import gc
import warnings
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from ssdl import video_adapter
from ssdl import media
from ssdl.web_media import MediaCandidate
from ssdl.network import public_network


@unittest.skipIf(media.yt_dlp is None or not media.ffmpeg_path(), "yt-dlp and FFmpeg are required")
class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix="ssdl-stream-fixture-")
        cls.root = Path(cls.fixture.name)
        inputs = [media.ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "lavfi", "-i", "testsrc=size=32x32:rate=10", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                  "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "10", "-sc_threshold", "0", "-c:a", "aac"]
        for folder, format_options, filename in (
            ("hls", ["-f", "hls", "-hls_time", "1", "-hls_playlist_type", "vod"], "playlist.m3u8"),
            ("dash", ["-f", "dash", "-seg_duration", "1"], "manifest.mpd"),
            ("direct", [], "sample.mp4"),
        ):
            (cls.root / folder).mkdir()
            subprocess.run([*inputs, *format_options, str(cls.root / folder / filename)], check=True,
                           capture_output=True, timeout=30, cwd=cls.root / folder,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        cls.unavailable = set()
        cls.requests = Counter()
        fixture_root = cls.root

        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_payload(head=True)

            def do_GET(self):
                self.send_payload()

            def send_payload(self, head=False):
                parsed = urlparse(self.path)
                cls.requests[parsed.path] += 1
                path = fixture_root / parsed.path.lstrip("/")
                if parsed.path == "/stream":
                    path = fixture_root / "direct/sample.mp4"
                if parsed.path in cls.unavailable or not path.is_file():
                    self.send_error(404)
                    return
                payload = path.read_bytes()
                if parsed.path == "/stream":
                    payload += parse_qs(parsed.query).get("id", ["A"])[0].encode()
                mime = {".m3u8": "application/vnd.apple.mpegurl", ".mpd": "application/dash+xml",
                        ".ts": "video/mp2t"}.get(path.suffix, "video/mp4")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if not head:
                    self.wfile.write(payload)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.fixture.cleanup()

    def setUp(self):
        self.unavailable.clear()
        self.requests.clear()
        self.output = tempfile.TemporaryDirectory(prefix="ssdl-stream-output-")
        self.addCleanup(self.output.cleanup)
        self.directory = Path(self.output.name)
        original_options = media.video_options

        def fast_options(*args, **kwargs):
            options = original_options(*args, **kwargs)
            options["sleep_interval_requests"] = 0
            options["retry_sleep_functions"] = {"http": lambda n: 0, "fragment": lambda n: 0}
            options["no_warnings"] = True
            return options

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(video_adapter, "video_options", side_effect=fast_options))
        self.stack.enter_context(patch.object(media.POLICY, "before_request"))

    def download(self, path, **kwargs):
        return media.download_video(self.base + path, self.directory, lambda event: None, **kwargs)

    @contextmanager
    def public_fixture(self):
        """Only the test's checked public numeric connect is routed to a fixture."""
        original_connect = socket.socket.connect
        def resolve(host, port, *args):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        def connect(sock, address):
            return original_connect(sock, ("127.0.0.1", self.server.server_port))
        with patch.object(socket, "getaddrinfo", resolve), patch.object(socket.socket, "connect", connect), public_network():
            yield f"http://public.example:{self.server.server_port}"

    def test_guarded_native_hls_and_dash_are_playable(self):
        for filename in ("/hls/playlist.m3u8", "/dash/manifest.mpd"):
            with self.subTest(filename=filename), self.public_fixture() as base:
                result = media.download_video(base + filename, self.directory, lambda event: None)
            self.assert_playable(result)

    def test_guarded_hls_rejects_private_fragment_and_key_before_transfer(self):
        private = f"http://127.0.0.1:{self.server.server_port}/private"
        for kind, contents in (
            ("fragment", "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\n" + private + "\n#EXT-X-ENDLIST\n"),
            ("key", '#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXT-X-KEY:METHOD=AES-128,URI="' + private + '"\n#EXTINF:1,\nhls/playlist0.ts\n#EXT-X-ENDLIST\n'),
        ):
            (self.root / "private-hls.m3u8").write_text(contents, encoding="utf-8")
            with self.subTest(kind=kind), self.public_fixture() as base, self.assertRaises(media.DownloadError) as failure:
                media.download_video(base + "/private-hls.m3u8", self.directory, lambda event: None, force=True)
            self.assertEqual(failure.exception.code, "unsafe_target")
            self.assertEqual(self.requests["/private"], 0)
            self.assertFalse(list(self.directory.rglob("private-hls*.mp4")))

    def test_guarded_dash_rejects_private_initialization_before_transfer(self):
        text = (self.root / "dash/manifest.mpd").read_text(encoding="utf-8")
        text = re.sub(r'initialization="[^"]+"', 'initialization="http://127.0.0.1:' + str(self.server.server_port) + '/private"', text)
        (self.root / "private-dash.mpd").write_text(text, encoding="utf-8")
        with self.public_fixture() as base, self.assertRaises(media.DownloadError) as failure:
            media.download_video(base + "/private-dash.mpd", self.directory, lambda event: None, force=True)
        self.assertEqual(failure.exception.code, "unsafe_target")
        self.assertEqual(self.requests["/private"], 0)

    def assert_playable(self, result):
        self.assertTrue(result["files"])
        for filename in result["files"]:
            subprocess.run([media.ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-xerror",
                            "-i", str(self.directory / filename), "-f", "null", "-"],
                           check=True, capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_query_content_and_renditions_do_not_collide_or_skip(self):
        names = []
        for query in ("id=A", "id=B", "id=A&quality=1080", "id=A&token=changed"):
            url = self.base + "/stream?" + query
            candidate = MediaCandidate(url=url, referer=self.base + "/watch", title="Same title")
            result = self.download("/stream?" + query, candidate=candidate, source_url=self.base + "/watch")
            names.extend(result["files"])
            self.assertFalse(result["skipped"])
        self.assertEqual(len(set(names)), 4)
        url = self.base + "/stream?id=A"
        same = self.download("/stream?id=A", candidate=MediaCandidate(url, self.base + "/watch", title="Same title"),
                             source_url=self.base + "/watch")
        self.assertTrue(same["skipped"])
        self.assertEqual(same["files"], [names[0]])
        self.assertNotEqual((self.directory / names[0]).read_bytes(), (self.directory / names[1]).read_bytes())

    def test_hls_missing_later_fragment_fails_then_recovers(self):
        segments = sorted((self.root / "hls").glob("*.ts"))
        self.assertGreaterEqual(len(segments), 3)
        missing = "/hls/" + segments[1].name
        self.unavailable.add(missing)
        with self.assertRaises(media.DownloadError):
            self.download("/hls/playlist.m3u8")
        self.assertGreaterEqual(self.requests[missing], 2)
        self.unavailable.clear()
        self.assert_playable(self.download("/hls/playlist.m3u8"))

    def test_dash_missing_audio_fragment_fails_then_recovers(self):
        audio = sorted((self.root / "dash").glob("chunk-stream1-*.m4s"))
        self.assertGreaterEqual(len(audio), 3)
        missing = "/dash/" + audio[1].name
        self.unavailable.add(missing)
        with self.assertRaises(media.DownloadError):
            self.download("/dash/manifest.mpd")
        self.assertGreaterEqual(self.requests[missing], 2)
        self.unavailable.clear()
        self.assert_playable(self.download("/dash/manifest.mpd"))

    def test_dash_merge_failure_is_not_completed(self):
        from yt_dlp.postprocessor.ffmpeg import FFmpegMergerPP
        from yt_dlp.utils import PostProcessingError
        with patch.object(FFmpegMergerPP, "run", side_effect=PostProcessingError("fixture merge failure")):
            with self.assertRaises(media.DownloadError):
                self.download("/dash/manifest.mpd")

    @unittest.skipIf(media.gallery_job is None, "gallery-dl is required")
    def test_gallery_delegated_hls_cannot_complete_with_a_missing_fragment(self):
        from gallery_dl.extractor.common import Extractor
        from gallery_dl.extractor.message import Message
        url = self.base + "/hls/playlist.m3u8"

        class StreamExtractor(Extractor):
            category = "fixture"
            subcategory = "stream"
            directory_fmt = ("fixture",)
            filename_fmt = "{num}.{extension}"

            def items(self):
                yield Message.Directory, "", {"title": "Stream fixture"}
                yield Message.Url, "ytdl:" + url, {"extension": "mp4", "num": 1, "_ytdl_manifest": "hls"}

        media.configure_gallery(self.directory)
        options = dict(media.gallery_config.get(("downloader", "ytdl"), "raw-options"))
        options.update(sleep_interval_requests=0, retry_sleep_functions={"fragment": lambda n: 0})
        media.gallery_config.set(("downloader", "ytdl"), "raw-options", options)
        media.gallery_config.set(("downloader", "ytdl"), "retries", 0)
        missing = "/hls/" + sorted((self.root / "hls").glob("*.ts"))[1].name
        self.unavailable.add(missing)
        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always", ResourceWarning)
            with self.assertRaises(media.DownloadError):
                media.download_gallery(StreamExtractor(re.match(".*", url)), self.directory, lambda event: None)
            gc.collect()
        self.assertFalse([item for item in records if issubclass(item.category, ResourceWarning)])
        self.assertGreaterEqual(self.requests[missing], 2)


if __name__ == "__main__":
    unittest.main()
