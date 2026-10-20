"""Offline ownership contracts for real Windows CTRL+C installation acceptance."""
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import console_runner as console, install_runner
from tools import check_installation as installation


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory(prefix="ssdl-console-unit-"))
        self.root = Path(temporary).resolve()
        self.token = "a" * 32

    def test_gate_rejects_a_shared_or_missing_console_before_child_creation(self):
        for pids in (set(), {os.getpid(), 123456789}):
            with self.subTest(pids=pids), patch.object(console, "kernel"), \
                 patch.object(console, "console_pids", return_value=pids), \
                 patch.object(console.subprocess, "call") as child:
                with self.assertRaisesRegex(OSError, "shared or missing"):
                    console.gate(self.root, self.token)
                child.assert_not_called()
                self.assertFalse((self.root / ".ssdl-console-owner").exists())

    def test_console_membership_must_be_complete_and_nonempty(self):
        api = Mock()
        for count in (0, 129):
            api.GetConsoleProcessList.return_value = count
            with self.assertRaisesRegex(OSError, "console membership"):
                console.console_pids(api)
        def members(buffer, capacity):
            self.assertEqual(capacity, 128)
            buffer[0], buffer[1] = 101, 102
            return 2
        api.GetConsoleProcessList.side_effect = members
        self.assertEqual(console.console_pids(api), {101, 102})

    def test_admitted_gate_uses_a_handler_without_inheritable_sigint_ignore(self):
        with patch.object(console, "kernel"), patch.object(console, "console_pids", return_value={os.getpid()}), \
             patch.object(console.signal, "signal") as handler, patch.object(console.subprocess, "call", return_value=0) as child:
            self.assertEqual(console.gate(self.root, self.token), 0)
        self.assertEqual(handler.call_args.args[0], signal.SIGINT)
        self.assertTrue(callable(handler.call_args.args[1]))
        self.assertNotEqual(handler.call_args.args[1], signal.SIG_IGN)
        owner = json.loads((self.root / ".ssdl-console-owner").read_text(encoding="ascii"))
        self.assertEqual(owner, {"pid": os.getpid(), "parent": os.getppid(), "token": self.token})
        self.assertIn(str(self.root / ".venv/Scripts/python.exe"), child.call_args.args[0])

    def test_owner_rejects_wrong_token_caller_console_and_unknown_members(self):
        owner = {"pid": 111, "parent": 222, "token": self.token}
        path = self.root / ".ssdl-console-owner"
        path.write_text(json.dumps(owner), encoding="ascii")
        for pids, token in (({111, 333}, "b" * 32), ({111, 222, 333}, self.token),
                            ({111, 333, 999}, self.token), ({333}, self.token)):
            with self.subTest(pids=pids), patch.object(console, "console_pids", return_value=pids), \
                 patch.object(console.os, "getpid", return_value=333), patch.object(console.os, "getppid", return_value=444):
                with self.assertRaisesRegex(OSError, "outside the admitted"):
                    console.check_owner(self.root, token, Mock())
        with patch.object(console, "console_pids", return_value={111, 333, 444}), \
             patch.object(console.os, "getpid", return_value=333), patch.object(console.os, "getppid", return_value=444):
            self.assertEqual(console.check_owner(self.root, self.token, Mock()), owner)

    def test_invalid_worker_receipts_cannot_open_any_process(self):
        for pids in (None, "12", [1], [1, 1], [True, 2], [0, 2], [[], 2]):
            with self.subTest(pids=pids), patch.object(console, "kernel") as api:
                with self.assertRaises(ValueError):
                    with console.watch_processes(pids):
                        self.fail("Invalid process receipt was admitted")
                api.assert_not_called()

    def test_watcher_closes_handles_on_partial_open_and_surviving_process(self):
        api = Mock()
        api.OpenProcess.side_effect = [11, None]
        with patch.object(console, "kernel", return_value=api):
            with self.assertRaisesRegex(OSError, "before interrupt"):
                with console.watch_processes([101, 102]):
                    self.fail("Worker already exited")
        api.CloseHandle.assert_called_once_with(11)
        api.reset_mock()
        api.OpenProcess.side_effect = [11, 12]
        api.WaitForSingleObject.side_effect = [0, 258]
        with patch.object(console, "kernel", return_value=api):
            with self.assertRaisesRegex(OSError, "survived graceful"):
                with console.watch_processes([101, 102]) as stopped:
                    stopped()
        self.assertEqual([call.args for call in api.CloseHandle.call_args_list], [(11,), (12,)])

    def test_watcher_requires_signalled_handles_without_terminating_by_pid(self):
        api = Mock()
        api.OpenProcess.side_effect = [11, 12]
        api.WaitForSingleObject.return_value = 0
        with patch.object(console, "kernel", return_value=api):
            with console.watch_processes([101, 102]) as stopped:
                stopped()
        self.assertEqual([call.args for call in api.OpenProcess.call_args_list], [(0x00100000, False, 101), (0x00100000, False, 102)])
        api.TerminateProcess.assert_not_called()
        self.assertEqual(api.CloseHandle.call_count, 2)

    def test_import_and_invalid_receipt_never_start_a_service_or_worker(self):
        helper = self.root / "tests/helpers/console_runner.py"
        with patch.object(console, "__file__", str(helper)), patch.object(sys, "path", list(sys.path)), \
             patch.object(console, "service") as service, patch.object(console, "worker") as worker:
            for action in ("service", "worker"):
                with self.assertRaises(ValueError):
                    console.main([action, "--token", self.token])
            service.assert_not_called()
            worker.assert_not_called()

    def service_case(self, command, generated=True):
        from ssdl import app as entry
        (self.root / "data").mkdir(exist_ok=True)
        api = Mock()
        api.GenerateConsoleCtrlEvent.return_value = generated
        original = Mock(return_value=SimpleNamespace())
        def main():
            entry.create_app()
            return 0
        with patch.object(console, "kernel", return_value=api), patch.object(console, "check_owner"), \
             patch.object(console.signal, "signal"), patch.object(sys, "stdin", io.StringIO(command)), \
             patch.object(entry, "create_app", original), patch.object(entry, "main", side_effect=main), \
             patch.object(install_runner, "closed_status", return_value={"closed": True, "durable": True, "threads_stopped": True}):
            if command == "interrupt\n" and generated:
                self.assertEqual(console.service(self.root, self.token), 0)
            else:
                with self.assertRaisesRegex(RuntimeError, "did not close normally"):
                    console.service(self.root, self.token)
            self.assertIs(entry.create_app, original)
        return api, json.loads((self.root / "data/console-closed.json").read_text(encoding="utf-8"))

    def test_missing_admission_never_generates_an_event_or_reports_success(self):
        api, status = self.service_case("not-an-interrupt\n")
        api.GenerateConsoleCtrlEvent.assert_not_called()
        self.assertFalse(status["ctrl_c"])
        self.assertTrue(status["control_stopped"])

    def test_rejected_native_signal_cannot_pass_closure_acceptance(self):
        api, status = self.service_case("interrupt\n", generated=False)
        api.GenerateConsoleCtrlEvent.assert_called_once_with(0, 0)
        self.assertFalse(status["ctrl_c"])

    def test_native_ctrl_c_is_explicit_and_entry_factory_is_restored(self):
        api, status = self.service_case("interrupt\n")
        api.GenerateConsoleCtrlEvent.assert_called_once_with(0, 0)
        self.assertTrue(status["ctrl_c"])
        self.assertEqual(status["exit_code"], 0)

    @unittest.skipUnless(os.name == "nt", "Windows launch flags")
    def test_console_command_is_hidden_and_separate_before_admission(self):
        process, group = Mock(), Mock()
        process.poll.return_value = 0
        with patch.object(installation.subprocess, "Popen", return_value=process) as launched, \
             patch.object(installation, "ProcessGroup", return_value=group):
            with installation.command(self.root, self.token, "console", {}, self.root / "phase.log"):
                options = launched.call_args.kwargs
                self.assertEqual(options["creationflags"], subprocess.CREATE_NEW_CONSOLE)
                self.assertEqual(options["startupinfo"].wShowWindow, subprocess.SW_HIDE)
                self.assertTrue(options["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW)
                process.stdin.write.assert_called_once_with(b"run\n")

    def test_created_response_is_only_accepted_when_explicitly_requested(self):
        response = Mock(status=201)
        response.read.return_value = b'{"added":[]}'
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(installation.http.client, "HTTPConnection", return_value=connection):
            with self.assertRaises(installation.AcceptanceError):
                installation.request(43210, "/api/jobs", {"urls": []})
            self.assertEqual(installation.request(43210, "/api/jobs", {"urls": []}, expected_status=201), {"added": []})
        self.assertEqual(connection.close.call_count, 2)
