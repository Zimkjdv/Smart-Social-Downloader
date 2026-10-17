"""Small offline contracts for the real, opt-in Windows installation harness."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from tests.helpers import install_runner
from tools import check_installation as acceptance, manage


class InstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory(prefix="ssdl-install-unit-"))
        self.root = Path(temporary).resolve()

    def test_environment_is_isolated_without_mutating_the_parent(self):
        values = {"PYTHONPATH": "fixture-private", "PIP_EXTRA_INDEX_URL": "fixture-registry",
                  "SSDL_DOWNLOAD_DIR": "fixture-data", "VIRTUAL_ENV": "fixture-venv", "PATH": "fixture-path"}
        with patch.dict(os.environ, values):
            result = acceptance.environment(self.root, 43210)
            self.assertEqual(os.environ["PYTHONPATH"], "fixture-private")
        self.assertNotIn("PYTHONPATH", result)
        self.assertNotIn("PIP_EXTRA_INDEX_URL", result)
        self.assertNotIn("VIRTUAL_ENV", result)
        self.assertEqual(result["PIP_INDEX_URL"], "https://pypi.org/simple")
        self.assertEqual(result["SSDL_PORT"], "43210")
        self.assertEqual(result["PATH"], "fixture-path")
        self.assertTrue(Path(result["SSDL_DOWNLOAD_DIR"]).is_relative_to(self.root))

    def test_pin_parser_handles_extras_and_normalizes_names(self):
        path = self.root / "requirements.txt"
        path.write_text("# reviewed pins\n\nyt-dlp[default]==2026.8.19\ntyping_extensions==4.16.0\n", encoding="utf-8")
        self.assertEqual(acceptance.pinned_versions(path), {"yt-dlp": "2026.8.19", "typing-extensions": "4.16.0"})
        for contents in ("package>=1", "package==1\npackage==2", "# empty\n"):
            path.write_text(contents, encoding="utf-8")
            with self.subTest(contents=contents), self.assertRaises(acceptance.AcceptanceError):
                acceptance.pinned_versions(path)

    def test_baseline_restore_checks_pins_without_claiming_extras_are_removed(self):
        acceptance.verify_versions({"package": "1", "extra": "2"}, {"package": "1"})
        for actual in ({}, {"package": "2"}):
            with self.assertRaises(acceptance.AcceptanceError):
                acceptance.verify_versions(actual, {"package": "1"})

    def test_receipt_rejects_missing_wrong_and_non_ascii_tokens(self):
        token = "a" * 32
        with self.assertRaises(ValueError):
            install_runner.verify_receipt(self.root, token)
        (self.root / install_runner.RECEIPT).write_text(token, encoding="ascii")
        install_runner.verify_receipt(self.root, token)
        for invalid in ("b" * 32, "a", "圖" * 32):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                install_runner.verify_receipt(self.root, invalid)

    def test_child_cannot_spawn_before_owned_admission(self):
        helper = self.root / "tests/helpers/install_runner.py"
        token = "a" * 32
        (self.root / install_runner.RECEIPT).write_text(token, encoding="ascii")
        with patch.object(install_runner, "__file__", str(helper)), patch.object(install_runner.sys, "stdin", io.StringIO("")), \
             patch.object(install_runner.subprocess, "call") as called, patch("builtins.print"):
            self.assertEqual(install_runner.main(["setup", "--token", token]), 2)
        called.assert_not_called()

    def test_group_attachment_failure_cleans_only_the_owned_gate(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(acceptance.subprocess, "Popen", return_value=process), \
             patch.object(acceptance, "ProcessGroup", side_effect=OSError("fixture attach failure")):
            with self.assertRaisesRegex(OSError, "fixture attach failure"):
                with acceptance.command(self.root, "a" * 32, "setup", {}, self.root / "phase.log"):
                    self.fail("Admission should fail")
        process.stdin.write.assert_not_called()
        process.kill.assert_called_once()
        process.wait.assert_called_once()
        process.stdin.close.assert_called_once()

    def test_group_is_attached_before_child_admission(self):
        events = []
        process, group = Mock(), Mock()
        process.poll.return_value = 0
        process.stdin.write.side_effect = lambda value: events.append("run")
        def attach(child):
            self.assertIs(child, process)
            events.append("attach")
            return group
        with patch.object(acceptance.subprocess, "Popen", return_value=process) as launched, \
             patch.object(acceptance, "ProcessGroup", side_effect=attach):
            with acceptance.command(self.root, "a" * 32, "setup", {}, self.root / "phase.log"):
                self.assertEqual(events, ["attach", "run"])
                self.assertEqual(launched.call_args.args[0][0], str(Path(getattr(sys, "_base_executable", sys.executable))))
                self.assertIn("-S", launched.call_args.args[0])
        group.close.assert_called_once()
        process.kill.assert_not_called()

    def test_command_timeouts_and_exit_errors_are_explicit(self):
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("synthetic-private-command", 1)
        with self.assertRaisesRegex(acceptance.AcceptanceError, "setup timed out") as caught:
            acceptance.wait_success(process, "setup", timeout=1)
        self.assertNotIn("private-command", str(caught.exception))
        process.wait.side_effect = None
        process.wait.return_value = 7
        with self.assertRaisesRegex(acceptance.AcceptanceError, "setup exited with code 7"):
            acceptance.wait_success(process, "setup")

    def test_foreign_readiness_is_rejected_before_any_mutation(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(acceptance, "request", return_value={"download_dir": "foreign"}) as requested:
            with self.assertRaisesRegex(acceptance.AcceptanceError, "outside the owned"):
                acceptance.ready(process, 43210, self.root)
        requested.assert_called_once_with(43210, "/api/summary")

    def test_port_reuse_requires_a_successful_exclusive_bind(self):
        probe = Mock()
        probe.bind.side_effect = [OSError("fixture port busy"), None]
        socket = MagicMock()
        socket.__enter__.return_value = probe
        with patch.object(acceptance.socket, "socket", return_value=socket), \
             patch.object(acceptance.time, "sleep"):
            acceptance.assert_port_closed(43210)
        self.assertEqual(probe.bind.call_count, 2)
        probe.bind.assert_called_with(("127.0.0.1", 43210))

    def installer(self):
        directory = self.root / ".venv"
        python = directory / "Scripts/python.exe"
        python.parent.mkdir(parents=True)
        python.write_bytes(b"synthetic interpreter")
        self.enterContext(patch.multiple(manage, ROOT=self.root, ENVIRONMENT=directory,
                                        ENV_PYTHON=python, MARKER=directory / "ssdl-setup.json"))
        return directory / "ssdl-setup.json"

    def test_install_and_update_publish_marker_only_after_environment_check(self):
        marker = self.installer()
        for update, mode in ((False, "locked"), (True, "updated")):
            with self.subTest(update=update), patch.object(manage.subprocess, "run") as run, patch("builtins.print"):
                self.assertEqual(manage.install(update=update), 0)
                self.assertEqual(run.call_count, 2)
                self.assertEqual("--upgrade" in run.call_args_list[0].args[0], update)
                self.assertEqual(run.call_args_list[1].args[0][-1], "check")
                self.assertEqual(json.loads(marker.read_text(encoding="utf-8"))["mode"], mode)

    def test_failed_update_preserves_the_previous_success_marker(self):
        marker = self.installer()
        marker.write_text('{"mode":"locked"}', encoding="utf-8")
        before = marker.read_bytes()
        with patch.object(manage.subprocess, "run", side_effect=[Mock(), subprocess.CalledProcessError(1, "check")]):
            with self.assertRaises(subprocess.CalledProcessError):
                manage.install(update=True)
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse(marker.with_suffix(".tmp").exists())

    def test_start_route_checks_environment_without_installing_packages(self):
        with patch.object(manage, "check_environment") as checked, patch.object(manage, "install") as install, \
             patch.object(manage.subprocess, "call", return_value=0) as called:
            self.assertEqual(manage.main(["start"]), 0)
        checked.assert_called_once()
        install.assert_not_called()
        self.assertEqual(called.call_args.args[0][-1], str(manage.ROOT / "app.py"))
