"""Synthetic Chrome pages only; no personal browser profile or platform traffic."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock, MagicMock, patch

from ssdl import browser_media as capture
from ssdl import web_media, media
from ssdl import media_coordinator, video_adapter
from ssdl.request_policy import RateLimited, RequestPolicy
from ssdl.network import public_network


class CaptureBoundaryTests(unittest.TestCase):
    def test_startup_exhausting_budget_reports_timeout(self):
        driver = Mock()
        context = driver.runtime.chromium.launch.return_value.new_context.return_value
        context.new_page.return_value.frames = []
        context.cookies.return_value = []
        scanner = capture.BrowserMediaDiscovery("https://public.example/page", lambda event: None, driver, seconds=1)
        with patch.object(capture, "chrome_executable", return_value="chrome"), \
             patch.object(capture.time, "monotonic", side_effect=[0, 0, 2, 2, 2]):
            with self.assertRaises(web_media.WebMediaError) as failure:
                scanner.discover()
        self.assertEqual(failure.exception.code, "browser_capture_timeout")
        driver.runtime.chromium.launch.return_value.close.assert_called_once()

    def test_late_browser_callback_preserves_rate_limit(self):
        driver = Mock()
        context = driver.runtime.chromium.launch.return_value.new_context.return_value
        context.new_page.return_value.frames = []
        scanner = capture.BrowserMediaDiscovery("https://public.example/page", lambda event: None, driver, seconds=1)
        error = RateLimited("synthetic HTTP 429")
        def pending_callback():
            scanner.fatal = error
            return []
        context.cookies.side_effect = pending_callback
        with patch.object(capture, "chrome_executable", return_value="chrome"), \
             patch.object(capture.time, "monotonic", side_effect=[0, 0, 2, 2]):
            with self.assertRaises(RateLimited) as failure:
                scanner.discover()
        self.assertIs(failure.exception, error)

    def test_unlabelled_static_sources_preserve_query_identity(self):
        parser = web_media.PlayerHTML("https://public.example/page")
        parser.feed("<script>let a='/stream.mp4?id=A';let b='/stream.mp4?id=B';</script>")
        parser.close()
        items = parser.finish()
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item.group for item in items}), 2)

    def test_missing_dependency_has_actionable_error(self):
        scanner = capture.BrowserMediaDiscovery("https://public.example/page", lambda event: None, None)
        with self.assertRaises(web_media.WebMediaError) as failure:
            scanner.discover()
        self.assertEqual(failure.exception.code, "browser_capture_unavailable")
        self.assertIn("browser-setup", str(failure.exception))

    def test_record_is_bounded_and_sensitive_headers_never_reach_candidate(self):
        scanner = capture.BrowserMediaDiscovery("https://public.example/page", lambda event: None, None)
        for number in range(20):
            scanner.record(f"https://cdn.example/{number}.mp4", scanner.url,
                           {"authorization": "synthetic-token", "cookie": "synthetic-cookie", "referer": scanner.url})
        self.assertEqual(len(scanner.records), web_media.MAX_CANDIDATES)
        self.assertEqual(next(iter(scanner.records.values()))[1], {"Referer": scanner.url})

    def test_resource_bytes_are_counted_even_when_oversize_and_budget_failure_stops_capture(self):
        scanner = capture.BrowserMediaDiscovery("https://public.example/page", lambda event: None, None)
        scanner.deadline = float("inf")
        response = MagicMock(code=200, headers={"Content-Type": "application/javascript"})
        response.__enter__.return_value = response
        response.read.return_value = b"xxxx"
        with patch.object(scanner.opener, "open", return_value=response), \
             patch.object(web_media.POLICY, "before_request"), patch.object(capture, "MAX_RESOURCE_BYTES", 3):
            with self.assertRaises(web_media.WebMediaError) as failure:
                scanner.fetch(scanner.url, {})
        self.assertEqual(failure.exception.code, "browser_capture_budget")
        self.assertEqual(scanner.total_bytes, 4)
        route = Mock(request=Mock(url=scanner.url, method="GET", resource_type="script"))
        route.request.frame = Mock(url=scanner.url, parent_frame=None)
        with patch.object(scanner, "fetch", side_effect=failure.exception):
            scanner.route(route)
        self.assertIs(scanner.fatal, failure.exception)
        route.abort.assert_called_once()

    def test_non_http_private_post_and_budget_requests_are_aborted_without_fetch(self):
        scanner = capture.BrowserMediaDiscovery("https://public.example/page", lambda event: None, None)
        scanner.deadline = float("inf")
        for url, method in (("http://127.0.0.1/private", "GET"), ("file:///private", "GET"),
                            ("https://public.example/api", "POST")):
            route = Mock(request=Mock(url=url, method=method))
            with patch.object(scanner, "fetch") as fetched:
                scanner.route(route)
            route.abort.assert_called_once()
            fetched.assert_not_called()
        scanner.requests = capture.MAX_REQUESTS
        route = Mock()
        scanner.route(route)
        route.abort.assert_called_once()

    def test_dynamic_fallback_is_opt_in_and_preserves_quality_selection(self):
        item = web_media.MediaCandidate("https://cdn.example/movie-720p.mp4", "https://public.example/page",
                                       group="a" * 24, height=720)
        with patch.object(media.WebMediaDiscovery, "discover", return_value=iter(())), \
             patch.object(capture.BrowserMediaDiscovery, "discover", return_value=[item]) as dynamic, \
             patch.object(media_coordinator, "validate_target"), \
             patch.object(video_adapter, "download_video", return_value={"files": ["fixture.mp4"], "quality": "720p"}) as downloaded:
            with self.assertRaises(media.DownloadError):
                media.download_web_media("https://public.example/page", None, lambda event: None)
            dynamic.assert_not_called()
            result = media.download_web_media("https://public.example/page", None, lambda event: None,
                dynamic_capture=True, browser=capture.BrowserDriver(), video_quality="720")
            self.assertEqual(result["quality"], "720p")
            self.assertEqual(downloaded.call_args.kwargs["video_quality"], "720")
            self.assertEqual(downloaded.call_args.kwargs["candidate"].height, 720)

    def test_static_multiple_players_prompt_before_browser_capture(self):
        items = [web_media.MediaCandidate("https://cdn.example/a.mp4", "https://public.example/", group="a" * 24),
                 web_media.MediaCandidate("https://cdn.example/b.mp4", "https://public.example/", group="b" * 24)]
        from ssdl.media_selection import SelectionRequired
        with patch.object(media.WebMediaDiscovery, "discover", return_value=items), \
             patch.object(capture.BrowserMediaDiscovery, "discover") as dynamic:
            with self.assertRaises(SelectionRequired):
                media.download_web_media("https://public.example/page", None, lambda event: None, dynamic_capture=True)
        dynamic.assert_not_called()

    def test_static_failure_uses_dynamic_once_and_partial_files_stop_fallback(self):
        item = web_media.MediaCandidate("https://cdn.example/a.mp4", "https://public.example/", group="a" * 24)
        with patch.object(media.WebMediaDiscovery, "discover", return_value=[item]), \
             patch.object(capture.BrowserMediaDiscovery, "discover", return_value=[item]) as dynamic, \
             patch.object(media_coordinator, "validate_target"), \
             patch.object(video_adapter, "download_video", side_effect=[media.DownloadError("static failed"), {"files": ["a.mp4"]}]) as download:
            self.assertEqual(media.download_web_media("https://public.example/page", None, lambda event: None,
                                                     dynamic_capture=True)["files"], ["a.mp4"])
            self.assertEqual((dynamic.call_count, download.call_count), (1, 2))
        with patch.object(media.WebMediaDiscovery, "discover", return_value=[item]), \
             patch.object(capture.BrowserMediaDiscovery, "discover") as dynamic, patch.object(media_coordinator, "validate_target"), \
             patch.object(video_adapter, "download_video", side_effect=media.DownloadError("partial", ["part.mp4"])):
            with self.assertRaises(media.DownloadError):
                media.download_web_media("https://public.example/page", None, lambda event: None, dynamic_capture=True)
        dynamic.assert_not_called()


@unittest.skipUnless(capture.available(), "optional Playwright and Google Chrome are required")
class ChromeCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reached = []
        cls.fixture = tempfile.TemporaryDirectory(prefix="ssdl-browser-bytes-")
        cls.video = Path(cls.fixture.name) / "sample.mp4"
        subprocess.run([media.ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "color=c=blue:s=640x360:r=5", "-t", "0.4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cls.video)],
            check=True, capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.reached.append(self.path)
                status, mime, body = 200, "text/html", b""
                if self.path == "/player.js":
                    mime = "application/javascript"
                    body = b"fetch('/api/config').then(r=>r.json()).then(c=>{let v=document.createElement('video');v.id='main';v.src=c.src;document.body.append(v);v.load();});"
                elif self.path == "/api/config":
                    mime, body = "application/json", b'{"src":"/movie-720p.mp4?signature=synthetic"}'
                elif self.path.startswith("/movie-"):
                    self.send_error(500, "Discovery must not transfer media bytes")
                    return
                elif self.path == "/playable-360p.mp4":
                    mime, body = "video/mp4", cls.video.read_bytes()
                elif self.path == "/download":
                    body = b"<body><script>let v=document.createElement('video');v.id='main';v.src='/playable-360p.mp4';document.body.append(v);v.load();</script>"
                elif self.path == "/opaque":
                    mime, body = "application/vnd.apple.mpegurl", b"#EXTM3U\n"
                elif self.path == "/cookie":
                    if "gate=fixture" not in self.headers.get("Cookie", ""):
                        self.send_error(403)
                        return
                    mime, body = "application/dash+xml", b"<MPD/>"
                elif self.path == "/redirect-private":
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{cls.server.server_port}/private")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                elif self.path == "/limited":
                    self.send_response(429)
                    self.send_header("Retry-After", "180")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                elif self.path == "/dynamic":
                    body = b"<title>Dynamic fixture</title><script src='/player.js'></script>"
                elif self.path == "/hls":
                    body = b"<title>HLS fixture</title><script>fetch('/opaque')</script>"
                elif self.path == "/query-multi":
                    body = b"<script>fetch('/stream.mp4?id=A');fetch('/stream.mp4?id=B')</script>"
                elif self.path == "/session":
                    body = b"<script>document.cookie='gate=fixture; path=/';fetch('/cookie')</script>"
                elif self.path == "/unsafe":
                    body = f"<script>fetch('/redirect-private');fetch('http://127.0.0.1:{cls.server.server_port}/private');new WebSocket('ws://127.0.0.1:{cls.server.server_port}/private')</script>".encode()
                elif self.path == "/429":
                    body = b"<script>fetch('/limited')</script>"
                elif self.path == "/multi":
                    body = b"<body><script>for(let i=0;i<2;i++){let v=document.createElement('video');v.id='p'+i;v.src='/movie-'+(i?'1080':'720')+'p.mp4';document.body.append(v);v.load();}</script>"
                else:
                    body = b"<title>No media</title>"
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.fixture.cleanup()

    @contextmanager
    def fixture_transport(self):
        # Initialize local driver IPC before testing the checked HTTP transport.
        with capture.browser_driver(True) as driver:
            real_connect = socket.socket.connect
            def resolve(host, port, *args):
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
            def fixture_connect(sock, address):
                return real_connect(sock, ("127.0.0.1", self.server.server_port))
            with patch.object(socket, "getaddrinfo", resolve), patch.object(socket.socket, "connect", fixture_connect), \
                 patch.object(web_media.POLICY, "before_request"):
                with public_network():
                    yield driver

    def scan(self, path):
        self.reached.clear()
        with self.fixture_transport() as driver:
            scanner = capture.BrowserMediaDiscovery(f"http://public.example:{self.server.server_port}" + path,
                                                   lambda event: None, driver, seconds=30)
            return scanner, scanner.discover()

    def test_runtime_script_fetch_and_dom_quality_are_captured_without_media_transfer(self):
        scanner, items = self.scan("/dynamic")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].height, 720)
        self.assertIn("signature=synthetic", items[0].url)
        self.assertIn("/api/config", self.reached)
        self.assertFalse(any(path.startswith("/movie-") for path in self.reached))
        self.assertNotIn("signature=synthetic", scanner.diagnostics())

    def test_extensionless_hls_and_javascript_cookie_dash_are_captured(self):
        for path, suffix in (("/hls", "/opaque"), ("/session", "/cookie")):
            with self.subTest(path=path):
                scanner, items = self.scan(path)
                self.assertEqual(len(items), 1)
                self.assertTrue(items[0].url.endswith(suffix))
                if path == "/session":
                    self.assertTrue(any(item.name == "gate" for item in scanner.cookies))

    def test_redirect_loopback_and_websocket_cannot_reach_private_fixture(self):
        with self.assertRaises(web_media.WebMediaError):
            self.scan("/unsafe")
        self.assertIn("/redirect-private", self.reached)
        self.assertNotIn("/private", self.reached)

    def test_429_propagates_and_requests_backoff(self):
        with patch.object(web_media.POLICY, "limit", return_value=180) as limited:
            with self.assertRaises(RateLimited):
                self.scan("/429")
        limited.assert_called_once_with("180")

    def test_two_dynamic_players_keep_independent_groups(self):
        scanner, items = self.scan("/multi")
        self.assertEqual(len({item.group for item in items}), 2, [(item.url, item.group, item.height) for item in items])
        self.assertEqual({item.height for item in items}, {720, 1080})

    def test_network_only_sources_with_same_path_keep_query_identity(self):
        scanner, items = self.scan("/query-multi")
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item.group for item in items}), 2)
        self.assertEqual({item.url.rsplit("?", 1)[1] for item in items}, {"id=A", "id=B"})

    def test_captured_url_downloads_original_bytes_via_existing_quality_engine(self):
        self.reached.clear()
        with tempfile.TemporaryDirectory(prefix="ssdl-browser-output-") as folder, self.fixture_transport() as driver:
            url = f"http://public.example:{self.server.server_port}/download"
            scanner = capture.BrowserMediaDiscovery(url, lambda event: None, driver, seconds=30)
            items = scanner.discover()
            self.assertNotIn("/playable-360p.mp4", self.reached)
            with patch.object(media.WebMediaDiscovery, "discover", return_value=iter(())), \
                 patch.object(capture.BrowserMediaDiscovery, "discover", return_value=items), \
                 patch.object(media.POLICY, "before_request"):
                result = media.download_web_media(url, Path(folder), lambda event: None, video_quality="360",
                                                 dynamic_capture=True, browser=driver)
            saved = Path(folder) / result["files"][0]
            self.assertEqual(saved.read_bytes(), self.video.read_bytes())
            self.assertIn("quality-360p", result["files"][0])
            decoded = subprocess.run([media.ffmpeg_path(), "-v", "error", "-i", str(saved), "-f", "null", "-"],
                capture_output=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(decoded.returncode, 0)

    def test_infinite_javascript_is_stopped_by_parent_capture_deadline(self):
        from ssdl.job_runtime import run_job
        started = time.monotonic()
        # Use the same CLI path as runtime tests; tests/ is not a package.
        command = [sys.executable, "-X", "utf8", "-u", str(Path(__file__).with_name("test_fixture_runner.py"))]
        with self.assertRaises(media.DownloadError) as failure:
            run_job({"mode": "browser_hang"}, lambda event: None, lambda **kwargs: None, lambda: False,
                    RequestPolicy(), command=command, no_progress_timeout=10)
        self.assertEqual(failure.exception.code, "browser_capture_timeout")
        self.assertLess(time.monotonic() - started, 8)


if __name__ == "__main__":
    unittest.main()
