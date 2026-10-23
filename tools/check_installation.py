"""Accept Windows source installation in a disposable source copy and new venv.

Downloads dependencies into the owned copy/cache. Never uses production state,
an ordinary Chrome profile or real media. This is not a bare Windows OS test.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.process_group import ProcessGroup
from ssdl.version import __version__
from tools.package_source import create_archive
from tools.check_source_archive import extract_verified


class AcceptanceError(RuntimeError):
    pass


def environment(workspace, port):
    result = {key: value for key, value in os.environ.items()
              if not key.upper().startswith(("PYTHON", "PIP_", "SSDL_")) and key.upper() != "VIRTUAL_ENV"}
    result.update(SSDL_PORT=str(port), SSDL_NONINTERACTIVE="1",
                  SSDL_DOWNLOAD_DIR=str(workspace / "media target 圖片"),
                  PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1",
                  PIP_CONFIG_FILE=os.devnull, PIP_INDEX_URL="https://pypi.org/simple",
                  PIP_CACHE_DIR=str(workspace / "pip-cache"), PIP_DISABLE_PIP_VERSION_CHECK="1",
                  TEMP=str(workspace), TMP=str(workspace))
    return result


def pinned_versions(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([\w.-]+)(?:\[[\w,.-]+\])?==([\w.+-]+)", line.strip())
        if not match:
            raise AcceptanceError("Acceptance needs reviewed exact requirement pins")
        name = re.sub(r"[-_.]+", "-", match[1].lower())
        if name in result:
            raise AcceptanceError("Duplicate baseline requirement")
        result[name] = match[2]
    if not result:
        raise AcceptanceError("Empty baseline requirements")
    return result


def verify_versions(actual, expected):
    if any(actual.get(name) != version for name, version in expected.items()):
        raise AcceptanceError("Installed versions differ from the requested pinned baseline")


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def command(root, token, action, env, log):
    # A Windows venv executable can spawn its redirector child before Python
    # code runs. Gate the real base interpreter, then launch all venv children
    # inside its already attached Job Object.
    python = Path(getattr(sys, "_base_executable", sys.executable))
    process = None
    group = None
    with log.open("wb") as output:
        try:
            console_options = {}
            if action == "console":
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = subprocess.SW_HIDE
                console_options = {"creationflags": subprocess.CREATE_NEW_CONSOLE, "startupinfo": startup}
            process = subprocess.Popen([str(python), "-I", "-S", "-u", str(root / "tests/helpers/install_runner.py"),
                                        action, "--token", token], cwd=root, env=env,
                                       stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT, **console_options)
            # Child is receipt-gated and cannot spawn helpers before admission.
            group = ProcessGroup(process)
            process.stdin.write(b"run\n")
            process.stdin.flush()
            yield process
        finally:
            if group is not None:
                group.close()
            if process is not None:
                if process.poll() is None:
                    try:
                        process.kill()  # Only the owned gate, if job attachment failed.
                    except ProcessLookupError:
                        pass
                process.wait(timeout=15)
                try:
                    process.stdin.close()
                except OSError:
                    pass


def wait_success(process, phase, timeout=300):
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise AcceptanceError(phase + " timed out") from error
    if code:
        raise AcceptanceError(f"{phase} exited with code {code}")


def request(port, path, data=None, *, expected_status=200):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        body = None if data is None else json.dumps(data)
        connection.request("GET" if data is None else "POST", path, body,
                           {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"})
        response = connection.getresponse()
        payload = response.read(1_000_001)
        if response.status != expected_status or len(payload) > 1_000_000:
            raise AcceptanceError("Installed HTTP request failed")
        return json.loads(payload)
    finally:
        connection.close()


def verify_scope(state, media):
    if (state.get("app_version") != __version__ or
            Path(state.get("download_dir", "")).resolve() != media.resolve()):
        raise AcceptanceError("Refusing an HTTP service outside the owned installation scope")


def ready(process, port, media, *, seconds=90, background=False):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if process.poll() is not None and (not background or process.returncode != 0):
            raise AcceptanceError("Installed service exited before readiness")
        try:
            state = request(port, "/api/summary")
            verify_scope(state, media)  # Must pass before any mutation.
            if state.get("ready") and state.get("environment", {}).get("phase") == "complete":
                if not state["environment"].get("ready"):
                    failed = [item["id"] for item in state["environment"].get("checks", [])
                              if item.get("required") and item.get("status") != "ok"]
                    raise AcceptanceError("Installed environment diagnostics failed: " + ", ".join(failed))
                return state
        except (ConnectionError, TimeoutError, http.client.HTTPException):
            pass
        time.sleep(0.1)
    raise AcceptanceError("Installed service readiness timed out")


def inventory(root, env):
    log = root / ".ssdl-inventory.log"
    token = (root / ".ssdl-install-fixture").read_text(encoding="ascii")
    with command(root, token, "inventory", env, log) as process:
        wait_success(process, "fresh venv inventory", timeout=30)
    return json.loads(log.read_text(encoding="utf-8"))


def verify_saved(state, media):
    verify_scope(state, media)
    if not state.get("paused") or state.get("hourly_job_limit") != 73 or state.get("counts", {}).get("all", 0):
        raise AcceptanceError("Saved installation settings did not survive restart")


def assert_port_closed(port):
    until = time.monotonic() + 10
    while time.monotonic() < until:
        try:
            # Closed loopback probes can time out in Windows test environments.
            # Exclusive rebind proves our port is reusable without interpreting
            # a connection timeout as evidence that the listener disappeared.
            with socket.socket() as probe:
                if os.name == "nt":
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind(("127.0.0.1", port))
            return
        except OSError:
            pass
        time.sleep(0.1)
    raise AcceptanceError("Owned service port did not close")


def accept(workspace, *, browser=False):
    archive = workspace / "source.zip"
    files = create_archive(ROOT, archive)
    # Exercise spaces and Unicode without renaming/reusing any existing folder.
    root = extract_verified(archive, workspace / "fresh source 圖片", ROOT, files)
    token = uuid.uuid4().hex
    (root / ".ssdl-install-fixture").write_text(token, encoding="ascii")
    if (root / ".venv").exists() or (root / "data").exists():
        raise AcceptanceError("Source extraction is not fresh")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = environment(workspace, port)
    media = Path(env["SSDL_DOWNLOAD_DIR"])
    phases = []
    log = workspace / "phase.log"
    def action(name):
        print("Installation acceptance: " + name, flush=True)
        with command(root, token, name, env, log) as process:
            wait_success(process, name)
        phases.append(name)

    try:
        action("setup")
        marker = root / ".venv/ssdl-setup.json"
        if json.loads(marker.read_text(encoding="utf-8"))["mode"] != "locked":
            raise AcceptanceError("Setup marker was not published")
        config = (root / ".venv/pyvenv.cfg").read_text(encoding="utf-8").lower()
        if "include-system-site-packages = false" not in config:
            raise AcceptanceError("Installed venv includes system site packages")
        baseline = pinned_versions(root / "requirements.lock.txt")
        initial = inventory(root, env)
        verify_versions(initial, baseline)
        offline = dict(env, PIP_NO_INDEX="1", PIP_FIND_LINKS=str(workspace / "empty-index"))
        (workspace / "empty-index").mkdir()
        media.mkdir(parents=True, exist_ok=True)
        sentinel = media / "fixture-preserved.jpg"
        sentinel.write_bytes(b"synthetic installation media sentinel")
        media_hash = fingerprint(sentinel)
        marker_hash = fingerprint(marker)
        print("Installation acceptance: offline start.bat", flush=True)
        with command(root, token, "start", offline, log) as process:
            first = ready(process, port, media, background=True)
            installed_python = next(item["version"] for item in first["environment"]["checks"] if item["id"] == "python")
            request(port, "/api/pause", {"paused": True})
            state = request(port, "/api/settings", {"download_dir": str(media), "hourly_job_limit": 73})
            verify_saved(state, media)
        # Batch launcher cleanup is intentionally forced, scoped to its Job
        # Object. Graceful app close is tested separately through the fixture.
        print("Installation acceptance: batch cleanup", flush=True)
        assert_port_closed(port)
        if fingerprint(marker) != marker_hash or inventory(root, env) != initial:
            raise AcceptanceError("Offline startup changed the installed environment")
        phases.append("offline-start-batch-owned-cleanup")

        def graceful():
            with command(root, token, "lifecycle", offline, log) as process:
                verify_saved(ready(process, port, media), media)
                process.stdin.write(b"stop\n")
                process.stdin.flush()
                wait_success(process, "graceful lifecycle", timeout=45)
            closed = json.loads((root / "data/install-closed.json").read_text(encoding="utf-8"))
            if not all(closed.get(key) is True for key in ("closed", "threads_stopped", "durable")):
                raise AcceptanceError("Installed lifecycle did not close durably")
            assert_port_closed(port)
        print("Installation acceptance: graceful restart", flush=True)
        graceful()
        phases.append("graceful-restart")
        print("Installation acceptance: missing-marker auto setup", flush=True)
        marker.unlink()  # Only this fresh fixture's marker, never an existing installation.
        with command(root, token, "start", env, log) as process:
            verify_saved(ready(process, port, media, background=True), media)
        assert_port_closed(port)
        if json.loads(marker.read_text(encoding="utf-8"))["mode"] != "locked":
            raise AcceptanceError("Automatic setup did not restore the missing marker")
        verify_versions(inventory(root, env), baseline)
        graceful()
        phases.append("missing-marker-auto-setup")
        saved_hash = fingerprint(root / "data/state.json")
        action("update")
        updated = inventory(root, env)
        if json.loads(marker.read_text(encoding="utf-8"))["mode"] != "updated":
            raise AcceptanceError("Update marker was not published")
        # Even when today's --upgrade resolves to the same versions, require
        # setup to replace one genuinely different package in this fresh venv.
        if baseline.get("idna") in {None, "3.10"}:
            raise AcceptanceError("Review the fixed IDNA restoration probe for this baseline")
        action("restore-probe")
        if inventory(root, env).get("idna") != "3.10":
            raise AcceptanceError("Restoration probe did not change the isolated dependency")
        action("setup")
        verify_versions(inventory(root, env), baseline)
        if json.loads(marker.read_text(encoding="utf-8"))["mode"] != "locked":
            raise AcceptanceError("Baseline restore marker was not published")
        if fingerprint(root / "data/state.json") != saved_hash or fingerprint(sentinel) != media_hash:
            raise AcceptanceError("Package maintenance changed saved state or original media")
        if browser:
            action("browser")
            verify_versions(inventory(root, env), pinned_versions(root / "requirements-browser.txt"))
            verify_versions(inventory(root, env), baseline)
        graceful()
        phases.append("restored-graceful-restart")
        # Send actual CTRL_C_EVENT only inside a new, hidden console whose
        # membership the receipt-gated base interpreter checks before spawning.
        from tests.helpers.console_runner import watch_processes
        closed_file = root / "data/console-closed.json"
        def interrupt_console(process):
            process.stdin.write(b"interrupt\n")
            process.stdin.flush()
            wait_success(process, "CTRL+C entry shutdown", timeout=45)
            closed = json.loads(closed_file.read_text(encoding="utf-8"))
            if closed.get("exit_code") != 0 or not all(closed.get(key) is True for key in
                    ("closed", "threads_stopped", "durable", "ctrl_c", "control_stopped")):
                raise AcceptanceError("Console entry did not shut down durably")
            assert_port_closed(port)
        print("Installation acceptance: idle CTRL+C", flush=True)
        closed_file.unlink(missing_ok=True)
        with command(root, token, "console", offline, log) as process:
            verify_saved(ready(process, port, media), media)
            interrupt_console(process)  # Assert success before fallback Job Object cleanup.
        phases.append("idle-console-ctrl-c")
        print("Installation acceptance: active worker CTRL+C", flush=True)
        closed_file.unlink(missing_ok=True)
        worker_receipt = root / ".ssdl-console-worker"
        worker_receipt.unlink(missing_ok=True)
        with command(root, token, "console", offline, log) as process:
            verify_saved(ready(process, port, media), media)
            added = request(port, "/api/jobs", {"urls": ["https://example.org/console-a", "https://example.org/console-b"]}, expected_status=201)
            keys = added.get("added", [])
            if len(keys) != 2:
                raise AcceptanceError("Console fixture jobs were not added")
            request(port, "/api/pause", {"paused": False})
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise AcceptanceError("Synthetic console worker did not become active")
                try:
                    if worker_receipt.stat().st_size > 4096:
                        raise AcceptanceError("Invalid console worker receipt size")
                    workers = json.loads(worker_receipt.read_text(encoding="ascii"))
                    if workers.get("token") != token:
                        raise AcceptanceError("Invalid console worker receipt")
                    break
                except (OSError, ValueError):
                    time.sleep(.1)
            state = request(port, "/api/pause", {"paused": True})
            if state["counts"]["active"] != 1 or state["counts"]["queued"] != 1:
                raise AcceptanceError("Active/pending console jobs differ from fixture scope")
            with watch_processes(workers["pids"]) as stopped:
                interrupt_console(process)
                stopped()  # Require worker + grandchild exit before the outer job closes.
        if (media / "console-partial.part").read_bytes() != b"synthetic partial bytes":
            raise AcceptanceError("CTRL+C removed or changed partial fixture data")
        phases.append("active-console-ctrl-c-owned-tree")
        print("Installation acceptance: console restart recovery", flush=True)
        closed_file.unlink(missing_ok=True)
        with command(root, token, "console", offline, log) as process:
            state = ready(process, port, media)
            verify_scope(state, media)
            restored = request(port, "/api/state")
            if (not restored["paused"] or restored["hourly_job_limit"] != 73
                    or restored["counts"]["queued"] != 2 or restored["counts"]["active"] != 0
                    or {job["id"] for job in restored["jobs"]} != set(keys)
                    or sorted(job["attempts"] for job in restored["jobs"]) != [0, 1]
                    or restored["rate_limit"]["used"] != 1):
                raise AcceptanceError("Interrupted jobs/settings/quota did not recover exactly")
            interrupt_console(process)
        phases.append("console-restart-durable-queue")
        if fingerprint(sentinel) != media_hash:
            raise AcceptanceError("Console lifecycle changed original fixture media")
        print("Installation acceptance: invalid-port rejection", flush=True)
        saved_hash = fingerprint(root / "data/state.json")
        with command(root, token, "start", dict(offline, SSDL_PORT="0"), log) as process:
            try:
                code = process.wait(timeout=45)
            except subprocess.TimeoutExpired as error:
                raise AcceptanceError("Invalid-port batch launch hung") from error
            if code == 0:
                raise AcceptanceError("Invalid-port batch launch was accepted")
        if fingerprint(root / "data/state.json") != saved_hash:
            raise AcceptanceError("Failed launch changed saved state")
        phases.append("invalid-port-noninteractive-rejection")
        return {"passed": True, "python": installed_python, "bootstrap_python": sys.version.split()[0], "source_files": len(files),
                "phases": phases, "baseline": baseline,
                "updated_core": {key: updated.get(key) for key in baseline},
                "restore_probe": {"package": "idna", "temporary": "3.10", "restored": baseline["idna"]},
                "browser_installed": browser, "scope": "fresh-source-and-venv-on-existing-windows",
                "batch_stop": "owned-forced-cleanup", "app_close": "receipt-gated-graceful-fixture",
                "console_close": "real-ctrl-c-in-owned-hidden-console"}
    except Exception:
        if log.exists():
            tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
            print(tail.replace(str(workspace), "<temporary>"), file=sys.stderr)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, help="Existing parent for owned temporary files")
    parser.add_argument("--report", type=Path, help="Write a path-free JSON result after success")
    parser.add_argument("--browser", action="store_true", help="Also install/verify optional browser pins")
    parser.add_argument("--keep-workspace", action="store_true", help="Keep synthetic files/logs for local diagnosis")
    args = parser.parse_args(argv)
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        parser.error("This acceptance requires Windows and Python 3.12")
    try:
        with tempfile.TemporaryDirectory(prefix="ssdl-installation-", dir=args.work_dir,
                                         delete=not args.keep_workspace) as temporary:
            if args.keep_workspace:
                print("Owned diagnostic workspace: " + str(Path(temporary).resolve()), flush=True)
            report = accept(Path(temporary).resolve(), browser=args.browser)
        if args.report:
            args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True), flush=True)
        return 0
    except (AcceptanceError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("Installation acceptance failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
