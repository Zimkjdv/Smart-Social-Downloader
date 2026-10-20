"""Run synthetic dependency/transport regressions and emit a bounded safe report.

This opt-in maintainer command never loads production state or browser profiles.
Hooks are scoped to this process's tests, not installed in the application.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import gc
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import ssl
import sys
import sysconfig
import tempfile
import threading
import time
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.version import __version__

SSL_WARNING = "ssl.OP_NO_SSL*/ssl.OP_NO_TLS* options are deprecated"
SUITES = ("tests.test_media", "tests.test_network", "tests.test_streams",
          "tests.test_browser_media", "tests.test_api_sources", "tests.test_http_server")
HTTP_CASES = ("tests.test_http_server.HttpServerTests.test_complete_requests_and_extension_cors_keep_working",
              "tests.test_http_server.HttpServerTests.test_rejected_post_with_delayed_body_retains_403")
PACKAGES = ("yt-dlp", "gallery-dl", "requests", "urllib3", "playwright", "pyee", "pycryptodomex")


def environment() -> dict:
    packages = {}
    for name in PACKAGES:
        try:
            value = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            value = "missing"
        packages[name] = value if re.fullmatch(r"[\w.+!\-]{1,80}", value) else "unavailable"
    return {"python": platform.python_version(), "platform": sys.platform,
            "openssl": ssl.OPENSSL_VERSION, "packages": packages}


def origin(filename) -> str:
    """Export source identity, never an absolute path or arbitrary temp name."""
    try:
        path = Path(filename).resolve()
        paths = sysconfig.get_paths()
        roots = [("dependency", Path(paths[key]).resolve()) for key in ("purelib", "platlib")]
        roots += [("project", ROOT), ("stdlib", Path(paths["stdlib"]).resolve())]
        for label, root in roots:
            if path.is_relative_to(root):
                relative = path.relative_to(root).as_posix()
                if label == "project" and relative.split("/", 1)[0] not in {"ssdl", "tests", "tools"}:
                    return "external"
                if path.suffix == ".py" and re.fullmatch(r"[\w./\-]{1,240}", relative):
                    return label + ":" + relative
                return "external"
    except (OSError, ValueError, TypeError):
        pass
    return "external"


def type_name(value) -> str:
    allowed = {"Warning", "UserWarning", "RuntimeWarning", "DeprecationWarning", "PendingDeprecationWarning",
               "ResourceWarning", "FutureWarning", "ImportWarning", "SyntaxWarning", "UnicodeWarning",
               "AssertionError", "OSError", "ConnectionAbortedError", "ConnectionResetError", "BrokenPipeError",
               "TimeoutError", "RuntimeError", "ValueError", "TypeError", "ImportError", "ModuleNotFoundError"}
    name = getattr(value, "__name__", "")
    return name if name in allowed else "other"


class Collector:
    def __init__(self, environment: dict, *, max_events=256):
        if type(max_events) is not int or not 1 <= max_events <= 1024:
            raise ValueError("Invalid event budget")
        self.environment = environment
        self.max_events, self.dropped = max_events, 0
        self.events = []
        self.observed_during = "between_tests"
        self._lock = threading.RLock()  # GC/finalizers may emit a nested warning.

    def record(self, **event):
        event["observed_during"] = self.observed_during
        with self._lock:
            for previous in self.events:
                if all(previous[key] == value for key, value in event.items()):
                    previous["count"] += 1
                    return
            if len(self.events) >= self.max_events:
                self.dropped += 1
                return
            self.events.append({**event, "count": 1})

    @property
    def passed(self):
        return not self.dropped and all(event["reviewed"] for event in self.events)

    def warning(self, message, category, filename, lineno, file=None, line=None):
        location = origin(filename)
        text = str(message)[:2000]  # Only compared; never included in output.
        code = "python_warning"
        if category is DeprecationWarning and text == SSL_WARNING:
            code = "ssl_options_deprecated"
        elif issubclass(category, ResourceWarning):
            code = ("socket_resource_warning" if text.startswith(("unclosed <socket.socket", "unclosed <ssl.SSLSocket"))
                    else "resource_warning")
        reviewed = (code == "ssl_options_deprecated" and location == "dependency:urllib3/util/ssl_.py"
                    and self.environment.get("python", "").startswith("3.12.")
                    and self.environment.get("packages", {}).get("gallery-dl") == "1.32.16"
                    and self.environment.get("packages", {}).get("urllib3") == "2.8.0")
        self.record(kind="warning", code=code, category=type_name(category), origin=location,
                    line=lineno if type(lineno) is int and 0 <= lineno <= 1_000_000 else 0, reviewed=reviewed)

    def exception(self, error, traceback=None, *, kind="exception"):
        if not isinstance(error, BaseException):
            self.record(kind=kind, code="unknown_exception", category="other", origin="external", line=0, reviewed=False)
            return
        pending, visited = [(error, traceback)], set()
        while pending and len(visited) < 8:
            value, trace = pending.pop()
            if id(value) in visited:
                continue
            visited.add(id(value))
            winerror, number = getattr(value, "winerror", None), getattr(value, "errno", None)
            winerror = winerror if type(winerror) is int and 0 <= winerror <= 65535 else None
            number = number if type(number) is int and 0 <= number <= 65535 else None
            for _ in range(32):
                if trace is None or trace.tb_next is None:
                    break
                trace = trace.tb_next
            self.record(kind=kind, code="windows_connection_aborted" if winerror == 10053 or number == 10053 else "test_exception",
                        category=type_name(type(value)), origin=origin(trace.tb_frame.f_code.co_filename) if trace else "external",
                        line=trace.tb_lineno if trace else 0, winerror=winerror, errno=number, reviewed=False)
            for nested in (value.__cause__, value.__context__, getattr(value, "reason", None)):
                if isinstance(nested, BaseException):
                    pending.append((nested, nested.__traceback__))

    @contextmanager
    def capture(self):
        previous_unraisable, previous_thread = sys.unraisablehook, threading.excepthook
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            warnings.showwarning = self.warning
            sys.unraisablehook = lambda args: self.exception(args.exc_value, args.exc_traceback, kind="unraisable")
            threading.excepthook = lambda args: self.exception(args.exc_value, args.exc_traceback, kind="thread_exception")
            try:
                yield
            finally:
                sys.unraisablehook, threading.excepthook = previous_unraisable, previous_thread


class Result(unittest.TestResult):
    def __init__(self, collector):
        super().__init__()
        self.collector = collector

    def startTest(self, test):
        super().startTest(test)
        # Subtest parameters/reasons are never exported.
        name = test.id()
        self.collector.observed_during = name if re.fullmatch(r"[\w.<>]{1,240}", name) else "fixture"

    def stopTest(self, test):
        gc.collect()  # Observe delayed finalization before moving to another case.
        self.collector.observed_during = "between_tests"
        super().stopTest(test)

    def addError(self, test, err):
        self.errors.append((test, "recorded"))
        self.collector.exception(err[1], err[2])

    def addFailure(self, test, err):
        self.failures.append((test, "recorded"))
        self.collector.exception(err[1], err[2])

    def addSubTest(self, test, subtest, err):
        if err is not None:
            (self.addFailure if issubclass(err[0], test.failureException) else self.addError)(test, err)

    def addSkip(self, test, reason):
        self.skipped.append((test, "skipped"))

    def addExpectedFailure(self, test, err):
        self.expectedFailures.append((test, "recorded"))
        self.collector.exception(err[1], err[2])


class DiscardOutput:
    def write(self, value):
        return len(value)
    def flush(self):
        pass


def build_suite(http_repeats=30):
    if type(http_repeats) is not int or not 1 <= http_repeats <= 100:
        raise ValueError("HTTP repetitions must be between 1 and 100")
    names = list(SUITES) + list(HTTP_CASES) * http_repeats
    return unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)


def run_checks(suite, collector) -> dict:
    started = time.monotonic()
    result = Result(collector)
    with collector.capture(), redirect_stdout(DiscardOutput()), redirect_stderr(DiscardOutput()):
        if not isinstance(suite, unittest.TestSuite):
            suite = suite()  # Include dependency-import warnings during loading.
        suite.run(result)
        collector.observed_during = "suite_cleanup"
        gc.collect()
    return {"schema": 1, "complete": True, "app_version": __version__, "environment": collector.environment,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "passed": result.wasSuccessful() and not result.skipped and not result.expectedFailures and collector.passed,
            "tests": {"run": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
                      "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                      "unexpected_successes": len(result.unexpectedSuccesses)},
            "observations": collector.events, "dropped_events": collector.dropped}


def write_report(path: Path, report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="ssdl-fault-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(report, indent=2) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-repeats", type=int, choices=range(1, 101), default=30, metavar="1..100")
    parser.add_argument("--report", type=Path, help="Optional JSON result; raw messages/paths are excluded")
    options = parser.parse_args(arguments)
    try:
        # A crash or interruption must not leave an earlier successful receipt.
        if options.report:
            write_report(options.report, {"schema": 1, "passed": False, "complete": False, "code": "check_incomplete"})
        report = run_checks(lambda: build_suite(options.http_repeats), Collector(environment()))
        if options.report:
            write_report(options.report, report)
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    except Exception:
        print("Dependency fault check could not complete; no successful result was recorded.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Dependency fault check interrupted; no successful result was recorded.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
