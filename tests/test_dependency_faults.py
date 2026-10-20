"""Fault-tracking contracts use only synthetic exceptions and owned sockets."""
import gc
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings

from tools import check_dependency_faults as faults


class DependencyFaultTests(unittest.TestCase):
    def collector(self, **kwargs):
        environment = {"python": "3.12.10", "packages": {"gallery-dl": "1.32.16", "urllib3": "2.8.0"}}
        return faults.Collector(environment, **kwargs)

    def ssl_warning(self, collector, *, message=faults.SSL_WARNING, origin="dependency:urllib3/util/ssl_.py"):
        with patch.object(faults, "origin", return_value=origin):
            collector.warning(message, DeprecationWarning, "unused", 288)

    def test_ssl_exception_requires_exact_message_origin_and_reviewed_versions(self):
        collector = self.collector()
        self.ssl_warning(collector)
        self.assertTrue(collector.passed)
        self.assertEqual(collector.events[0]["code"], "ssl_options_deprecated")
        self.assertTrue(collector.events[0]["reviewed"])
        for change in ("message", "origin", "version", "python"):
            with self.subTest(change=change):
                collector = self.collector()
                if change == "version":
                    collector.environment["packages"]["gallery-dl"] = "1.32.17"
                if change == "python":
                    collector.environment["python"] = "3.13.0"
                self.ssl_warning(collector, message="new warning" if change == "message" else faults.SSL_WARNING,
                                 origin="project:ssdl/media.py" if change == "origin" else "dependency:urllib3/util/ssl_.py")
                self.assertFalse(collector.passed)

    def test_warning_capture_restores_hooks_filters_and_bounds_storms(self):
        collector = self.collector(max_events=2)
        before = (warnings.showwarning, list(warnings.filters), sys.unraisablehook, threading.excepthook)
        with collector.capture():
            for line in (1, 1, 2, 3):
                collector.warning("secret=fixture", UserWarning, __file__, line)
        self.assertEqual(warnings.showwarning, before[0])
        self.assertEqual(warnings.filters, before[1])
        self.assertIs(sys.unraisablehook, before[2])
        self.assertIs(threading.excepthook, before[3])
        self.assertEqual(len(collector.events), 2)
        self.assertEqual(collector.events[0]["count"], 2)
        self.assertEqual(collector.dropped, 1)
        self.assertFalse(collector.passed)

    def test_real_unclosed_socket_is_detected_and_never_allowlisted(self):
        collector = self.collector()
        with collector.capture():
            connection = socket.socket()
            del connection
            gc.collect()
        self.assertFalse(collector.passed)
        self.assertTrue(any(event["code"] == "socket_resource_warning" for event in collector.events))
        self.assertTrue(all(not event["reviewed"] for event in collector.events))

    def test_wrapped_windows_abort_has_structured_codes_without_secret_text(self):
        collector = self.collector()
        error = ConnectionAbortedError(10053, "Cookie: fixture-sensitive; https://secret.example/private")
        error.winerror = 10053
        wrapper = RuntimeError("password=fixture-sensitive")
        wrapper.__cause__ = error
        error.__context__ = wrapper  # Cycles must terminate.
        collector.exception(wrapper)
        contents = json.dumps(collector.events)
        self.assertIn("windows_connection_aborted", contents)
        self.assertIn("10053", contents)
        self.assertNotIn("fixture-sensitive", contents)
        self.assertNotIn("secret.example", contents)
        self.assertFalse(collector.passed)

    def test_exception_thread_and_unraisable_hooks_record_failures(self):
        collector = self.collector()
        with collector.capture():
            sys.unraisablehook(SimpleNamespace(exc_value=ValueError("private"), exc_traceback=None))
            thread = threading.Thread(target=lambda: (_ for _ in ()).throw(OSError("private")))
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertFalse(collector.passed)
        self.assertEqual({event["kind"] for event in collector.events}, {"unraisable", "thread_exception"})

    def test_import_warnings_and_unknown_unraisable_values_fail_closed(self):
        collector = self.collector()
        def load():
            warnings.warn("private", UserWarning)
            sys.unraisablehook(SimpleNamespace(exc_value=None, exc_traceback=None))
            return unittest.TestSuite()
        report = faults.run_checks(load, collector)
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["observations"]), 2)

    def test_interruption_and_crash_replace_old_success_with_incomplete_receipt(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-fault-failure-") as directory:
            target = Path(directory) / "report.json"
            for exception, code in ((RuntimeError("private"), 2), (KeyboardInterrupt(), 130)):
                target.write_text('{"passed": true}', encoding="utf-8")
                with patch.object(faults, "run_checks", side_effect=exception), \
                     patch.object(faults, "environment", return_value={}), patch("sys.stderr", new_callable=io.StringIO):
                    self.assertEqual(faults.main(["--report", str(target)]), code)
                self.assertFalse(json.loads(target.read_text(encoding="utf-8"))["complete"])
                self.assertFalse(list(Path(directory).glob("*.tmp")))

    def test_runner_preserves_subtest_failure_skip_and_later_success(self):
        class Fixture(unittest.TestCase):
            def test_failure(self):
                with self.subTest(secret="private"):
                    raise ConnectionAbortedError(10053, "private")
            @unittest.skip("private reason")
            def test_skip(self):
                pass
            def test_success(self):
                pass
        report = faults.run_checks(unittest.defaultTestLoader.loadTestsFromTestCase(Fixture), self.collector())
        self.assertEqual(report["tests"]["run"], 3)
        self.assertEqual(report["tests"]["errors"], 1)
        self.assertEqual(report["tests"]["skipped"], 1)
        self.assertFalse(report["passed"])
        self.assertNotIn("private", json.dumps(report))

    def test_failing_attempt_is_not_erased_by_a_later_success(self):
        calls = []
        class Fixture(unittest.TestCase):
            def runTest(self):
                calls.append(True)
                if len(calls) == 1:
                    raise ConnectionAbortedError(10053, "injected failure")
        report = faults.run_checks(unittest.TestSuite([Fixture(), Fixture()]), self.collector())
        self.assertFalse(report["passed"])
        self.assertEqual(report["tests"]["run"], 2)
        self.assertEqual(report["tests"]["errors"], 1)

    def test_suite_has_fixed_transport_media_and_browser_cases_and_exact_http_repeats(self):
        seen = []
        def loaded(name):
            seen.append(name)
            return unittest.TestSuite()
        with patch.object(faults.unittest.defaultTestLoader, "loadTestsFromName", side_effect=loaded):
            faults.build_suite(3)
        self.assertTrue(set(faults.SUITES).issubset(seen))
        for name in faults.HTTP_CASES:
            self.assertEqual(seen.count(name), 3)
        with self.assertRaises(ValueError):
            faults.build_suite(0)

    def test_origins_exclude_external_paths_and_reports_do_not_copy_raw_messages(self):
        self.assertEqual(faults.origin(Path(__file__)), "project:tests/test_dependency_faults.py")
        self.assertEqual(faults.origin(Path(tempfile.gettempdir()) / "private" / "cookies.txt"), "external")
        collector = self.collector()
        collector.warning("auth_token=private; password=private", UserWarning, "private path", 1)
        self.assertNotIn("private", json.dumps(collector.events))

    def test_main_writes_report_on_failure_and_has_stable_error_output(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-fault-report-") as directory:
            target = Path(directory) / "report.json"
            failed = {"passed": False, "tests": {"run": 1}, "observations": []}
            with patch.object(faults, "run_checks", return_value=failed), patch.object(faults, "build_suite"), \
                 patch.object(faults, "environment", return_value={}), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(faults.main(["--report", str(target)]), 1)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), failed)
            with patch.object(faults, "run_checks", side_effect=OSError("private-path")), \
                 patch.object(faults, "build_suite"), patch.object(faults, "environment", return_value={}), \
                 patch("sys.stderr", new_callable=io.StringIO) as output:
                self.assertEqual(faults.main([]), 2)
            self.assertNotIn("private-path", output.getvalue())


if __name__ == "__main__":
    unittest.main()
