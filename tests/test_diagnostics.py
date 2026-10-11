import json
import unittest
from unittest.mock import patch

from ssdl.diagnostics import redact_text, redact_fields
from ssdl.app import create_app
from pathlib import Path
import tempfile


class DiagnosticTests(unittest.TestCase):
    def test_headers_json_urls_and_paths_remove_synthetic_secrets(self):
        private = "C:" + "\\Users\\" + "Example User\\Downloads\\one.mp4"
        source = '\n'.join(["Cookie: auth_token=SYNTHETIC_COOKIE; ct0=SYNTHETIC_CSRF",
            "Authorization: Bearer SYNTHETIC_AUTH", "{'auth_token': 'SYNTHETIC_JSON'}",
            "https://user:SYNTHETIC_PASS@example.org/video?id=3&signature=SYNTHETIC_SIG#token=secret",
            private])
        output = redact_text(source)
        for secret in ("SYNTHETIC_COOKIE", "SYNTHETIC_CSRF", "SYNTHETIC_AUTH", "SYNTHETIC_JSON", "SYNTHETIC_PASS", "SYNTHETIC_SIG", "Example User"):
            self.assertNotIn(secret, output)
        self.assertIn("example.org/video", output)
        self.assertIn("[PATH]", output)

    def test_operational_file_controls_keep_paths_but_errors_are_redacted(self):
        value = {"download_dir": "D:\\Media", "files": ["youtube/one.mp4"],
                 "error": "token=SYNTHETIC_VALUE", "warnings": ["https://example.org/file?sig=SYNTHETIC_SIG"]}
        safe = redact_fields(value)
        self.assertEqual(safe["download_dir"], value["download_dir"])
        self.assertEqual(safe["files"], value["files"])
        self.assertNotIn("SYNTHETIC", safe["error"] + safe["warnings"][0])

    def test_export_omits_history_urls_paths_and_auth_values(self):
        temporary = tempfile.TemporaryDirectory(prefix="ssdl-diagnostic-")
        self.addCleanup(temporary.cleanup)
        app = create_app(Path(temporary.name))
        self.addCleanup(app.close)
        job = {"id": "fixture", "platform": "Web", "status": "failed", "url": "https://private.example/SENTINEL_SOURCE",
               "files": ["SENTINEL_FILE.mp4"], "output_dir": "SENTINEL_DIRECTORY",
               "error": "auth_token=SENTINEL_SECRET"}
        with patch.object(app.state, "jobs", {"fixture": job}), patch.object(app.X_AUTH, "status", return_value={"connected": False, "phase": "idle", "cookies": "SENTINEL_COOKIE"}):
            output = json.dumps(app._diagnostics())
        for value in ("SENTINEL_SOURCE", "SENTINEL_FILE", "SENTINEL_DIRECTORY", "SENTINEL_SECRET", "SENTINEL_COOKIE"):
            self.assertNotIn(value, output)
