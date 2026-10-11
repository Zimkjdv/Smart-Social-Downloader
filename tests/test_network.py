from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import URLError

from ssdl.network import NetworkBlocked, checked_addresses, public_address, public_network, validate_url


class NetworkTests(unittest.TestCase):
    def test_literal_private_credentials_and_non_http_are_rejected(self):
        for value in ("http://127.0.0.1/x", "http://[::1]/", "http://10.0.0.2/", "http://169.254.169.254/",
                      "http://localhost/", "http://localhost./", "file:///secret", "ftp://example.org/a",
                      "https://user:pass@example.org/file", "http://[::ffff:127.0.0.1]/"):
            with self.subTest(value=value), self.assertRaises(NetworkBlocked):
                validate_url(value)
        self.assertEqual(validate_url("https://example.org/a?signature=opaque"), "example.org")

    def test_mixed_dns_and_rebinding_are_rejected_at_actual_resolution(self):
        public = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        private = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        self.assertEqual(checked_addresses(lambda *args: [public], "example.org", 443), [public])
        with self.assertRaises(NetworkBlocked):
            checked_addresses(lambda *args: [public, private], "example.org", 443)
        resolver = lambda *args: [private]
        with patch.object(socket, "getaddrinfo", resolver), public_network():
            with socket.socket() as connection, self.assertRaises(NetworkBlocked):
                connection.connect(("example.org", 443))

    def test_connect_receives_checked_numeric_address(self):
        numeric = ("93.184.216.34", 443)
        with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", numeric)]), \
             patch.object(socket.socket, "connect") as connect, public_network():
            with socket.socket() as connection:
                connection.connect(("example.org", 443))
            self.assertEqual(connect.call_args.args[1], numeric)

    def test_redirect_cannot_reach_loopback(self):
        reached = []
        class Fixture(BaseHTTPRequestHandler):
            def do_GET(self):
                reached.append(self.path)
                self.send_response(302 if self.path == "/redirect" else 200)
                if self.path == "/redirect":
                    self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/private")
                self.send_header("Content-Length", "0")
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        real_connect = socket.socket.connect
        def resolve(host, port, *args):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        def fixture_connect(sock, address):
            return real_connect(sock, ("127.0.0.1", server.server_port))
        try:
            with patch.object(socket, "getaddrinfo", resolve), patch.object(socket.socket, "connect", fixture_connect), public_network():
                with self.assertRaises((NetworkBlocked, URLError)):
                    urlopen(f"http://public.example:{server.server_port}/redirect", timeout=3)
            self.assertEqual(reached, ["/redirect"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_external_ffmpeg_downloads_are_rejected_but_native_is_available(self):
        from yt_dlp.downloader.external import FFmpegFD
        from ssdl import media
        with public_network(), self.assertRaises(NetworkBlocked):
            FFmpegFD.real_download(None, "unused", {})
        self.assertTrue(media.video_options.__name__)
        self.assertTrue(public_address("93.184.216.34"))
        self.assertFalse(public_address("::ffff:10.0.0.1"))

    def test_hls_keys_fragments_and_dash_resources_use_same_url_policy(self):
        import requests
        import yt_dlp
        urls = ["http://127.0.0.1/fragment.ts", "http://169.254.169.254/key.bin", "http://[::1]/audio.m4s"]
        with public_network(), yt_dlp.YoutubeDL({"quiet": True}) as downloader:
            for url in urls:
                with self.subTest(url=url):
                    with self.assertRaises(NetworkBlocked):
                        downloader.urlopen(url)
                    prepared = requests.Request("GET", url).prepare()
                    with self.assertRaises(NetworkBlocked):
                        requests.Session().send(prepared)
