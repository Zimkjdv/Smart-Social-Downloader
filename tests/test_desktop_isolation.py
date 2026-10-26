"""The normal HTTP application and refusal paths need no GUI installation."""
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zlib
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class DesktopIsolationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'native acceptance fixture is Windows-only')
    def test_generated_png_is_valid_for_strict_native_decoders(self):
        from tests.helpers.webview_matrix import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root / 'media target 圖片'
            with patch.dict(os.environ, {'SSDL_DOWNLOAD_DIR':str(media)}):
                prepare(root)
            data = (media / '中文 image.png').read_bytes()
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
            offset = 8
            while offset < len(data):
                size = struct.unpack('>I', data[offset:offset + 4])[0]
                chunk = data[offset + 4:offset + 8 + size]
                checksum = struct.unpack('>I', data[offset + 8 + size:offset + 12 + size])[0]
                self.assertEqual(zlib.crc32(chunk) & 0xffffffff, checksum, chunk[:4])
                offset += size + 12
            self.assertEqual(offset, len(data))

    def test_core_http_runs_with_all_gui_imports_forbidden(self):
        script = r'''
import importlib.abc, sys, tempfile, threading, http.client
from pathlib import Path
class NoGUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'webview', 'clr', 'pythonnet', 'System'}:
            raise AssertionError('GUI dependency reached ordinary HTTP')
sys.meta_path.insert(0, NoGUI())
from ssdl.app import create_app, Server
import ssdl.desktop_control, desktop.pywebview_app
with tempfile.TemporaryDirectory() as folder:
    with create_app(Path(folder), download_dir=Path(folder)) as app:
        with Server(('127.0.0.1', 0), app.Handler) as server:
            app.PORT = server.server_port
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request('GET', '/api/state')
                response = connection.getresponse()
                assert response.status == 200
                assert b'jobs' in response.read()
            finally:
                connection.close(); server.shutdown(); thread.join(timeout=5)
            assert not thread.is_alive()
assert not any(name.split('.')[0] in {'webview','clr','pythonnet','System'} for name in sys.modules)
'''
        result = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=ROOT,
            capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_failed_runtime_reports_repair_instead_of_silently_selecting_another_engine(self):
        from desktop import pywebview_app as shell
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(shell.backend, "DATA", Path(folder)), \
             patch.object(shell, "run", side_effect=ImportError("WebView2 unavailable")), \
             patch.object(shell.logging, "basicConfig"), patch.object(shell.logging, "exception"), \
             patch("builtins.print") as printed, \
             patch("ctypes.windll", SimpleNamespace(user32=SimpleNamespace(MessageBoxW=Mock())), create=True) as native:
            self.assertEqual(shell.main(), 1)
            if os.name == "nt":
                message = native.user32.MessageBoxW.call_args.args[1]
            else:
                message = printed.call_args.args[0]
            self.assertIn("WebView2 Runtime", message)
            self.assertIn("desktop.bat", message)
            self.assertIn("data/desktop.log", message)

    def test_gui_helpers_refuse_unowned_source_before_importing_gui_or_starting_children(self):
        env = {key:value for key,value in os.environ.items() if not key.upper().startswith("SSDL_")}
        for helper, arguments in (("webview_smoke.py", ["--token", "0" * 32]), ("webview_backend.py", []),
                                  ("webview_startup.py", ["--token", "0" * 32, "--mode", "conflict"])):
            with self.subTest(helper=helper):
                result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tests/helpers" / helper), *arguments],
                    cwd=ROOT, env=env, input=b"run\n", capture_output=True, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"Invalid installation fixture receipt", result.stderr)
                self.assertNotIn(b"No module named 'webview'", result.stderr)
