from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch

from ssdl import environment
from ssdl.config import configured_port


class EnvironmentTests(unittest.TestCase):
    def test_javascript_minimum_versions_and_broken_executables(self):
        for name, version, expected in (("node", "v22.0.0", "ok"), ("node", "v21.9.0", "warning"),
                                       ("deno", "deno 2.3.0", "ok"), ("deno", "deno 2.2.9", "warning"),
                                       ("node", None, "warning")):
            with self.subTest(name=name, version=version), patch.object(environment.shutil, "which", side_effect=lambda key: key if key == name else None), patch.object(environment, "_command", return_value=version):
                self.assertEqual(environment._runtime_check()["status"], expected)

    def test_invalid_ffmpeg_and_dependency_conflict_are_required_failures(self):
        with patch.object(environment.shutil, "which", return_value="fixture"), patch.object(environment, "_command", return_value=None):
            self.assertEqual(environment._ffmpeg_check()["status"], "error")
            self.assertEqual(environment._pip_check()["status"], "error")

    def test_command_timeout_is_bounded_and_does_not_echo_stderr(self):
        with patch.object(environment.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 1)):
            self.assertIsNone(environment._command(["fixture"], timeout=1))

    def test_background_recheck_is_single_and_snapshot_is_independent(self):
        entered, release = threading.Event(), threading.Event()
        def inspect(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {"phase": "complete", "busy": False, "checks": []}
        diagnostics = environment.EnvironmentDiagnostics(Path("."), 8877)
        with patch.object(environment, "inspect_environment", side_effect=inspect) as work:
            self.assertTrue(diagnostics.refresh()["busy"])
            self.assertTrue(entered.wait(1))
            self.assertTrue(diagnostics.refresh()["busy"])
            diagnostics.snapshot()["checks"].append({"id": "mutated"})
            self.assertEqual(diagnostics.snapshot()["checks"], [])
            release.set()
            diagnostics._thread.join(timeout=2)
            self.assertEqual(work.call_count, 1)
            self.assertFalse(diagnostics.snapshot()["busy"])

    def test_port_validation_default_custom_and_invalid(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(configured_port(), 8765)
        for value, expected in (("8877", 8877), ("80", 80), ("65535", 65535)):
            with patch.dict("os.environ", {"SSDL_PORT": value}):
                self.assertEqual(configured_port(), expected)
        for value in ("", "0", "65536", "8.5", "invalid"):
            with patch.dict("os.environ", {"SSDL_PORT": value}), self.assertRaises(RuntimeError):
                configured_port()
