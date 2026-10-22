"""Real Chrome/native media documents against the shipped HTTP handler."""
import http.client
from http.server import ThreadingHTTPServer
import subprocess
import threading
import unittest
from unittest.mock import patch

from ssdl import browser_media, media
from tests.helpers.app import IsolatedApp
from tools.docker_browser_acceptance import local_request, play_video


class MediaServerFixture:
    def setUp(self):
        fixture = self.enterContext(IsolatedApp())
        self.app, self.root = fixture.app, fixture.root
        self.file = self.root / "original.mp4"
        self.file.write_bytes(b"invented original")
        self.app.state.jobs["fixture"] = {"id": "fixture", "status": "completed", "files": [self.file.name],
                                           "output_dir": str(self.root)}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.Handler)
        self.enterContext(patch.object(self.app, "PORT", self.server.server_port))
        self.enterContext(patch.object(self.app.Handler, "log_message"))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        def close():
            self.server.shutdown()
            thread.join(timeout=3)
            self.server.server_close()
        self.addCleanup(close)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.path = "/api/jobs/fixture/content?file_index=0&filename=original.mp4"

    def request(self, *, headers=None, path=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("GET", path or self.path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()


class LocalMediaPolicyTests(MediaServerFixture, unittest.TestCase):
    def test_media_retains_origin_without_allowing_script_or_foreign_sources(self):
        code, headers, body = self.request(headers={"Origin": self.origin, "Sec-Fetch-Site": "same-origin"})
        self.assertEqual((code, body), (200, b"invented original"))
        policy = headers["Content-Security-Policy"]
        self.assertEqual(policy.split(";")[0], "sandbox allow-same-origin")
        self.assertNotIn("allow-scripts", policy)
        self.assertIn("default-src 'none'", policy)
        self.assertIn("media-src 'self'", policy)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_opaque_and_untrusted_origins_remain_rejected(self):
        for origin in ("null", "https://untrusted.invalid"):
            with self.subTest(origin=origin):
                self.assertEqual(self.request(headers={"Origin": origin})[0], 403)

    def test_active_document_formats_never_become_inline_media(self):
        for name in ("active.html", "active.svg"):
            (self.root / name).write_text("<script>throw Error('synthetic')</script>")
            self.app.state.jobs["fixture"]["files"] = [name]
            with self.subTest(name=name):
                code, headers, _ = self.request(path=self.path.replace("original.mp4", name))
                if name.endswith(".html"):
                    self.assertEqual(code, 400)
                else:
                    self.assertEqual(code, 200)
                    self.assertEqual(headers["Content-Type"], "application/octet-stream")
                    self.assertTrue(headers["Content-Disposition"].startswith("attachment;"))
                    self.assertEqual(headers["Content-Security-Policy"].split(";")[0], "sandbox")


@unittest.skipUnless(browser_media.available(), "optional Playwright and Google Chrome are required")
class ChromeMediaPlaybackTests(MediaServerFixture, unittest.TestCase):
    def test_native_mp4_document_decodes_plays_and_seeks(self):
        from playwright.sync_api import sync_playwright
        self.file.unlink()
        subprocess.run([media.ffmpeg_path(), "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(self.file)],
                       check=True, capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel="chrome", headless=True)
            try:
                context = browser.new_context(service_workers="block", accept_downloads=False)
                context.set_default_timeout(5000)
                context.route("**/*", lambda route: route.continue_() if local_request(
                    route.request.url, self.origin, route.request.method) else route.abort())
                page = context.new_page()
                response = page.goto(self.origin + self.path, wait_until="domcontentloaded")
                self.assertEqual(response.status, 200)
                play_video(page)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
