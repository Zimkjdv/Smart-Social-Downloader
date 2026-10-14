"""Measure real persistence and loopback APIs using disposable synthetic history only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import cProfile
import http.client
import json
import math
from pathlib import Path
import platform
import pstats
import queue
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ssdl.app import create_app
from ssdl.http_api import ApiHandler
from ssdl.http_server import BoundedHTTPServer

WORKLOADS = {"small": (20, 0), "account": (200, 5000), "large": (200, 20000)}
TIMEOUT = 120


def synthetic_jobs(count, account_files):
    """No URLs are fetched and no listed media files are created."""
    jobs = {}
    for index in range(count):
        profile = bool(account_files and index >= count - 20)
        files = [f"twitter/example{index}/media-{number:012d}.jpg"
                 for number in range(account_files if profile else 1)]
        key = f"{index:032x}"
        jobs[key] = {"id": key, "url": f"https://example.org/post/{index}",
                     "platform": "X", "status": "completed", "title": "Synthetic media",
                     "created_at": index, "mode": "x_profile" if profile else "url",
                     "files": files, "warnings": [], "error_detail": ""}
    # Stop measures acknowledgement of a running job, not actual engine shutdown.
    active_id = next(reversed(jobs))
    jobs[active_id].update(status="active", stop_requested=False)
    return jobs, active_id


def distribution(samples):
    ordered = sorted(samples)
    if not ordered:
        raise ValueError("At least one sample is required")
    return {"samples_ms": [round(value, 3) for value in samples], "n": len(samples),
            "median_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3)}


class ObservedLock:
    """Time acquisition of the same RLock used by the real app/condition."""
    def __init__(self):
        self.raw = threading.RLock()
        self.local = threading.local()
        self.arrival = None
        self._release_save = self.raw._release_save
        self._acquire_restore = self.raw._acquire_restore
        self._is_owned = self.raw._is_owned

    def acquire(self, *args, **kwargs):
        metric = getattr(self.local, "metric", None)
        if metric is not None and self.arrival is not None:
            self.arrival.set()
        started = time.perf_counter()
        acquired = self.raw.acquire(*args, **kwargs)
        if metric is not None and acquired:
            metric["lock_wait_ms"] += (time.perf_counter() - started) * 1000
        return acquired

    def release(self):
        self.raw.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


class SilentService:
    """Injected local metadata; never scan storage, generate previews or restore login."""
    def status(self):
        return {"connected": False, "phase": "benchmark"}

    def snapshot(self, *args):
        return {"status": "empty", "total_bytes": 0}

    def shutdown(self):
        pass


@contextmanager
def isolated_app():
    with tempfile.TemporaryDirectory(prefix="ssdl-persistence-bench-") as directory, ExitStack() as stack:
        root = Path(directory).resolve()
        # The application factory is used, but start() is deliberately never called.
        app = stack.enter_context(create_app(root, download_dir=root / "downloads",
            auth=SilentService(), storage=SilentService(), environment=SilentService(),
            thumbnails=SilentService()))
        stack.enter_context(patch("ssdl.app_context.media.engine_status", return_value={
            "video": True, "images": True, "ffmpeg": True, "video_version": "synthetic"}))
        stack.enter_context(patch("ssdl.app_context.browser_capture_available", return_value=False))
        app.lock = ObservedLock()
        app.condition = threading.Condition(app.lock)
        metrics = queue.Queue()

        class Handler(ApiHandler):
            def log_message(self, *args):
                pass

            def probe(self, callback):
                metric = {"lock_wait_ms": 0.0}
                app.lock.local.metric = metric
                try:
                    callback(self)
                finally:
                    del app.lock.local.metric
                    metrics.put(metric)

            def do_GET(self):
                self.probe(ApiHandler.do_GET)

            def do_POST(self):
                self.probe(ApiHandler.do_POST)

        Handler.app = app
        server = BoundedHTTPServer(("127.0.0.1", 0), Handler)
        # Own and join all handler threads before deleting the temporary state.
        server.daemon_threads = False
        app.PORT = server.server_port
        errors = []
        server.handle_error = lambda *args: errors.append("HTTP handler failed")
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        try:
            thread.start()
            yield app, metrics
        finally:
            if thread.is_alive():
                server.shutdown()
            server.server_close()
            if thread.ident is not None:
                thread.join(TIMEOUT)
            if thread.is_alive() or errors or server.active_connections:
                raise RuntimeError("Benchmark HTTP service did not finish cleanly")


def save(app, captures=None):
    started = time.perf_counter()
    with app.condition:
        capture_started = time.perf_counter()
        generation = app._save_locked()
        captured = (time.perf_counter() - capture_started) * 1000
    saved = app._wait_saved(generation)
    if captures is not None:
        captures.append(captured)
    if not saved or not app._persistence_status()["healthy"]:
        raise RuntimeError("Synthetic state could not be saved; no measurement is valid")
    return (time.perf_counter() - started) * 1000


def request(app, metrics, operation):
    body = None
    path = "/api/summary"
    if operation == "pause":
        path, body = "/api/pause", {"paused": True}
    elif operation == "cancel":
        path, body = f"/api/jobs/{app.state.active_id}/stop", {}
    elif operation != "summary":
        raise ValueError("Unknown benchmark operation")
    client = http.client.HTTPConnection("127.0.0.1", app.PORT, timeout=TIMEOUT)
    started = time.perf_counter()
    try:
        client.request("GET" if body is None else "POST", path,
            None if body is None else json.dumps(body),
            {"Origin": f"http://127.0.0.1:{app.PORT}", "Content-Type": "application/json"})
        response = client.getresponse()
        payload = json.loads(response.read())
        elapsed = (time.perf_counter() - started) * 1000
        if response.status != 200 or not payload["persistence"]["healthy"]:
            raise RuntimeError("Benchmark API failed; timings must not be used")
        if operation == "pause" and payload["paused"] is not True:
            raise RuntimeError("Pause acknowledgement is incorrect")
        if operation == "cancel" and payload["active_job"]["stop_requested"] is not True:
            raise RuntimeError("Stop acknowledgement is incorrect")
        return {"http_ms": elapsed, **metrics.get(timeout=TIMEOUT)}
    finally:
        client.close()


def contended_request(app, metrics, operation):
    ready, arrival = threading.Event(), threading.Event()
    writer_samples, errors = [], []
    app.lock.arrival = arrival

    def writer():
        try:
            with app.condition:
                ready.set()
                # Gate starts work when the actual handler reaches this lock.
                # No artificial sleep is included in the timed save.
                if not arrival.wait(30):
                    raise RuntimeError("Benchmark handler never reached the queue lock")
                started = time.perf_counter()
                generation = app._save_locked()
                capture_ms = (time.perf_counter() - started) * 1000
            if not app._wait_saved(generation):
                raise RuntimeError("Synthetic state could not be saved")
            writer_samples.append({"writer_save_ms": (time.perf_counter() - started) * 1000,
                                   "writer_capture_ms": capture_ms})
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=writer, name="synthetic-state-writer")
    thread.start()
    try:
        if not ready.wait(30):
            raise RuntimeError("Benchmark writer did not acquire the queue lock")
        result = request(app, metrics, operation)
    finally:
        arrival.set()  # Release a gated writer even when a request fails.
        thread.join(TIMEOUT)
        app.lock.arrival = None
    if thread.is_alive():
        raise RuntimeError("Benchmark writer did not finish")
    if errors:
        raise RuntimeError("Benchmark writer failed") from errors[0]
    result.update(writer_samples[0])
    return result


def phase_profile(app):
    """Separate instrumented run: cumulative rows overlap; never sum them."""
    profile = cProfile.Profile()
    original = app.STATE_WRITER._save
    # Profile the real writer thread, not the caller merely waiting on a barrier.
    with patch.object(app.STATE_WRITER, "_save", side_effect=lambda snapshot: profile.runcall(original, snapshot)):
        elapsed = save(app)
    rows = {}
    for (filename, _line, name), (_primitive, calls, own, cumulative, _callers) in pstats.Stats(profile).stats.items():
        phase = None
        if Path(filename).name == "diagnostics.py" and name == "redact_fields":
            phase = "redact"
        elif Path(filename).name == "persistence.py" and name in {"validate_state", "_read", "_atomic"}:
            phase = name
        elif Path(filename).name == "__init__.py" and name == "dumps":
            phase = "json_dumps"
        elif ".fsync" in name:
            phase = "fsync"
        elif name == "<method 'encode' of 'str' objects>":
            phase = "utf8_encode"
        if phase:
            rows[phase] = {"calls": calls, "own_ms": round(own * 1000, 3),
                           "cumulative_ms": round(cumulative * 1000, 3)}
    return {"save_ms": round(elapsed, 3), "phases": rows}


def snapshot_memory(app):
    """Separate allocation run; excludes existing immutable strings and writer I/O."""
    tracemalloc.start()
    try:
        with app.condition:
            snapshot = app._REPOSITORY.snapshot_locked()
        retained, peak = tracemalloc.get_traced_memory()
        del snapshot
        return {"retained_bytes": retained, "peak_bytes": peak}
    finally:
        tracemalloc.stop()


def measure_case(name, repeats):
    count, account_files = WORKLOADS[name]
    with isolated_app() as (app, metrics):
        app.state.jobs, app.state.active_id = synthetic_jobs(count, account_files)
        cold = save(app)  # No primary/backup yet.
        save(app)  # Warm up and establish both files before steady-state samples.
        captures = []
        steady = [save(app, captures) for _ in range(repeats)]
        profiled = phase_profile(app)
        memory = snapshot_memory(app)
        operations = {}
        for operation in ("summary", "pause", "cancel"):
            samples = {}
            for mode in ("uncontended", "contended"):
                values = []
                for _ in range(repeats):
                    with app.condition:
                        if operation == "pause":
                            app.state.paused = False
                        app.state.jobs[app.state.active_id]["stop_requested"] = False
                    values.append(contended_request(app, metrics, operation) if mode == "contended"
                                  else request(app, metrics, operation))
                samples[mode] = {key: distribution([item[key] for item in values]) for key in values[0]}
            operations[operation] = samples
        primary = app.STATE_STORE._read(app.STATE_FILE)
        backup = app.STATE_STORE._read(app.STATE_STORE.backup)
        if primary["paused"] is not True or primary["jobs"][-1]["stop_requested"] is not True:
            raise RuntimeError("Acknowledged pause/stop was not persisted")
        if len(primary["jobs"]) != count or len(backup["jobs"]) != count:
            raise RuntimeError("Synthetic history changed unexpectedly")
        return {"workload": name, "jobs": count,
                "file_paths": sum(len(job["files"]) for job in app.state.jobs.values()),
                "state_bytes": app.STATE_FILE.stat().st_size,
                "cold_save_ms": round(cold, 3), "steady_save": distribution(steady),
                "snapshot_capture": distribution(captures),
                "snapshot_allocation": memory,
                "profiled_save": profiled, "operations": operations,
                "verified": {"primary_valid": True, "backup_valid": True,
                             "pause_saved": True, "stop_request_saved": True}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", action="append", choices=WORKLOADS,
                        help="Repeat to select workloads; default: small, account, large")
    parser.add_argument("--repeats", type=int, default=5, help="Samples per operation (1-20, default 5)")
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be between 1 and 20")
    cases = []
    for name in args.workload or WORKLOADS:
        print(f"Measuring {name} ({args.repeats} samples per operation)...", file=sys.stderr, flush=True)
        cases.append(measure_case(name, args.repeats))
    print(json.dumps({"format_version": 2, "environment": {"os": platform.system(),
        "python": platform.python_version()}, "repeats": args.repeats,
        "scope": "Synthetic temporary state; immutable capture, real writer durable barriers and loopback APIs; no download worker",
        "percentile": "Nearest-rank p95; five samples means the maximum, not a stable tail estimate",
        "profiling": "Separate cProfile run adds overhead; cumulative phases overlap and must not be summed",
        "cases": cases}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
