"""Opt-in native Windows background lifecycle acceptance in disposable sources."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_installation import (AcceptanceError, command, environment, ready,
    request, verify_scope, wait_success, assert_port_closed, fingerprint)
from tools.package_source import create_archive
from tools.check_source_archive import extract_verified


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def fixture(root, token):
    from tests.helpers.install_runner import verify_receipt
    verify_receipt(root, token)
    hook = root / ".venv/Lib/site-packages/ssdl_desktop_acceptance.pth"
    # Refuse to replace another hook, even in an admitted disposable venv.
    with hook.open("x", encoding="utf-8") as output:
        output.write("import sys; sys.path.insert(0, " + repr(str(root)) + "); "
                     "from pathlib import Path; from tests.helpers.desktop_fixture import bootstrap; "
                     "bootstrap(Path(" + repr(str(root)) + "), " + repr(token) + ")\n")
    try:
        yield
    finally:
        hook.unlink()


def stopped(root, port):
    receipt = root / "data/desktop-closed.json"
    status = json.loads(receipt.read_text(encoding="utf-8"))
    if not all(status.get(key) is True for key in
               ("closed", "threads_stopped", "durable", "pixiv_thread_stopped", "no_console")):
        raise AcceptanceError("Background close was not hidden, joined and durable")
    if (root / "data/background-service.json").exists():
        raise AcceptanceError("Graceful stop left the running service record")
    assert_port_closed(port)
    # Each shutdown needs its own evidence; never accept a previous close.
    receipt.unlink()


def accept(root, token, workspace, inherited):
    """Use only a receipt-owned source/venv supplied by installation acceptance."""
    from tests.helpers.install_runner import verify_receipt
    from tests.helpers.console_runner import watch_processes
    verify_receipt(root, token)
    env = dict(inherited, SSDL_DESKTOP_FIXTURE_TOKEN=token, SSDL_PORT=str(free_port()))
    # Exercise the real automatic browser branch, recording only its URL dispatch.
    env.pop("SSDL_NONINTERACTIVE", None)
    port, media = int(env["SSDL_PORT"]), Path(env["SSDL_DOWNLOAD_DIR"])
    phases = []
    def phase(name):
        phases.append(name)
        print("Desktop acceptance: " + name, flush=True)
    def batch(action, *, values=env, project=root, receipt=token, expected=0):
        with command(project, receipt, action, values, workspace / (action + ".log")) as process:
            code = process.wait(timeout=75)
            if (code == 0) != (expected == 0):
                raise AcceptanceError("Desktop batch " + action + " returned an unexpected exit code")
    def check_pages(expected):
        pages = [json.loads(line) for line in (root / "desktop-pages.jsonl").read_text(encoding="utf-8").splitlines()]
        if pages != expected:
            raise AcceptanceError("Browser dispatch did not use the running service port")
    url = f"http://127.0.0.1:{port}/"

    with fixture(root, token):
        # Keep each launcher's owned Job Object open until graceful stop has
        # independently passed; fallback cleanup cannot masquerade as success.
        with command(root, token, "start", env, workspace / "start.log") as process:
            ready(process, port, media, background=True)
            wait_success(process, "background batch exit", timeout=75)
            first_pid = json.loads((root / "data/background-service.json").read_text())["pid"]
            check_pages([url])
            phase("custom-port-hidden-start-and-browser-dispatch")
            request(port, "/api/pause", {"paused": True})
            request(port, "/api/jobs/clear-all", {})
            batch("start", values=dict(env, SSDL_PORT="0", SSDL_DOWNLOAD_DIR=str(workspace / "wrong-media")))
            if json.loads((root / "data/background-service.json").read_text())["pid"] != first_pid:
                raise AcceptanceError("Repeated start replaced the running service")
            check_pages([url, url])
            phase("repeat-start-keeps-original-port-and-process")
            batch("supervisor-attached")
            verify_scope(request(port, "/api/summary"), media)
            if not all(json.loads((root / "data/supervisor-attached.json").read_text()).values()):
                raise AcceptanceError("Attached supervisor evidence is incomplete")
            check_pages([url, url])
            phase("supervisor-identity-attached-stop-refusal-and-window-focus")

            # A separate source root has distinct native controls. Share only
            # dependency imports through a fixture venv, never mutable app data.
            archive = workspace / "desktop-source.zip"
            files = create_archive(root, archive)
            other = extract_verified(archive, workspace / "second project 圖片", root, files)
            other_token = uuid.uuid4().hex
            (other / ".ssdl-install-fixture").write_text(other_token, encoding="ascii")
            venv.EnvBuilder(with_pip=False).create(other / ".venv")
            site = other / ".venv/Lib/site-packages"
            (site / "fixture-dependencies.pth").write_text(str(root / ".venv/Lib/site-packages") + "\n", encoding="utf-8")
            shutil.copy2(root / ".venv/ssdl-setup.json", other / ".venv/ssdl-setup.json")
            other_env = dict(environment(workspace, free_port()), SSDL_DESKTOP_FIXTURE_TOKEN=other_token,
                             SSDL_DOWNLOAD_DIR=str(workspace / "second media"))
            other_port = int(other_env["SSDL_PORT"])
            with fixture(other, other_token):
                batch("stop", project=other, receipt=other_token, values=other_env)
                verify_scope(request(port, "/api/summary"), media)
                with command(other, other_token, "start", other_env, workspace / "second-start.log") as second:
                    ready(second, other_port, Path(other_env["SSDL_DOWNLOAD_DIR"]), background=True)
                    wait_success(second, "second project launch", timeout=75)
                    batch("stop", project=other, receipt=other_token, values=other_env)
                    stopped(other, other_port)
                    verify_scope(request(port, "/api/summary"), media)
            phase("separate-project-stop-isolation")

            # Synthetic transport owns a real helper tree and partial file.
            worker_receipt = root / ".ssdl-console-worker"
            worker_receipt.unlink(missing_ok=True)
            baseline = request(port, "/api/summary")
            quota = baseline["rate_limit"]["used"]
            keys = request(port, "/api/jobs", {"urls": ["https://example.org/desktop-a", "https://example.org/desktop-b"]}, expected_status=201)["added"]
            if len(keys) != 2:
                raise AcceptanceError("Desktop synthetic jobs were not admitted")
            request(port, "/api/pause", {"paused": False})
            deadline = time.monotonic() + 30
            while True:
                try:
                    workers = json.loads(worker_receipt.read_text(encoding="ascii"))
                    if workers.get("token") != token:
                        raise AcceptanceError("Worker receipt is outside desktop scope")
                    break
                except (OSError, ValueError):
                    if time.monotonic() >= deadline:
                        raise AcceptanceError("Desktop synthetic worker did not start")
                    time.sleep(.1)
            state = request(port, "/api/pause", {"paused": True})
            if state["counts"]["active"] != 1 or state["counts"]["queued"] != 1:
                raise AcceptanceError("Desktop active/pending queue differs")
            with watch_processes(workers["pids"]) as exited:
                batch("stop")
                stopped(root, port)
                exited()
            phase("active-stop-joins-workers-and-preserves-partial")
        partial = media / "console-partial.part"
        if partial.read_bytes() != b"synthetic partial bytes":
            raise AcceptanceError("Graceful desktop stop changed partial bytes")
        saved = fingerprint(root / "data/state.json")
        batch("stop")
        if fingerprint(root / "data/state.json") != saved:
            raise AcceptanceError("Idle stop changed saved state")
        phase("idempotent-stop")

        # Two real simultaneous cold batch starts must both succeed, without
        # spawning a second service or racing log rotation.
        (root / "data/background.log").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        with command(root, token, "start", env, workspace / "parallel-a.log") as a, \
             command(root, token, "start", env, workspace / "parallel-b.log") as b:
            ready(a, port, media, background=True)
            wait_success(a, "concurrent launcher A", timeout=75)
            wait_success(b, "concurrent launcher B", timeout=75)
            restored = request(port, "/api/state")
            if (not restored["paused"] or restored["counts"]["queued"] != 2
                    or restored["counts"]["active"] != 0 or {j["id"] for j in restored["jobs"]} != set(keys)
                    or sorted(j["attempts"] for j in restored["jobs"]) != [0, 1]
                    or restored["rate_limit"]["used"] != quota + 1
                    or restored["hourly_job_limit"] != baseline["hourly_job_limit"]
                    or partial.read_bytes() != b"synthetic partial bytes"):
                raise AcceptanceError("Desktop queue/quota/partial recovery differs")
            check_pages([url] * 4)
            if (root / "data/background.previous.log").stat().st_size != 2 * 1024 * 1024 + 1:
                raise AcceptanceError("Cold-start log rotation failed")
            batch("stop")
            stopped(root, port)
        phase("concurrent-start-log-rotation-and-durable-restart")

        before = fingerprint(root / "data/state.json")
        with command(root, token, "foreground", env, workspace / "foreground.log") as foreground:
            ready(foreground, port, media)
            batch("start", expected=1)
            batch("stop")
            if foreground.poll() is not None:
                raise AcceptanceError("Background stop terminated a foreground service")
            verify_scope(request(port, "/api/summary"), media)
            # D05's data writer lease refuses this same-scope foreground
            # instance before socket binding. Require that specific diagnostic.
            if "Another backend or data migration already uses this data directory." not in (root / "data/background.log").read_text(encoding="utf-8"):
                raise AcceptanceError("Foreground data-scope conflict did not produce the writer-lease diagnostic")
        assert_port_closed(port)
        if fingerprint(root / "data/state.json") != before:
            raise AcceptanceError("Failed background launch changed durable state")
        phase("foreground-data-scope-conflict-log-and-no-foreign-stop")

        # Kill only a deliberately owned fixture tree by closing its Job Object,
        # then require cold startup to reject the retired record/identity.
        with command(root, token, "supervisor-crash", env, workspace / "supervisor-crash.log") as owned:
            wait_success(owned, "owned abrupt-exit setup", timeout=75)
            verify_scope(request(port, "/api/summary"), media)
        assert_port_closed(port)
        batch("supervisor-cold")
        stopped(root, port)
        check_pages([url] * 4)
        if not all(json.loads((root / "data/supervisor-cold.json").read_text()).values()):
            raise AcceptanceError("Cold supervisor evidence is incomplete")
        phase("supervisor-abrupt-exit-restart-and-owned-instance-stop")

    return {"passed": True, "phases": phases, "scope": "receipt-owned-native-windows-source-copies",
            "transport": "synthetic-owned-worker-tree", "browser": "recorded-webbrowser-open-dispatch",
            "foreground_cleanup": "owned-job-object-only"}


def main(argv=None):
    import argparse
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--keep-workspace", action="store_true", help="Retain only owned synthetic diagnostics")
    args = parser.parse_args(argv)
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        parser.error("Requires native Windows and Python 3.12")
    try:
        with tempfile.TemporaryDirectory(prefix="ssdl-desktop-", dir=args.work_dir,
                                         delete=not args.keep_workspace) as name:
            workspace = Path(name).resolve()
            if args.keep_workspace:
                print("Owned desktop workspace: " + str(workspace), flush=True)
            files = create_archive(ROOT, workspace / "source.zip")
            root = extract_verified(workspace / "source.zip", workspace / "fresh source 圖片", ROOT, files)
            token = uuid.uuid4().hex
            (root / ".ssdl-install-fixture").write_text(token, encoding="ascii")
            env = environment(workspace, free_port())
            with command(root, token, "setup", env, workspace / "setup.log") as process:
                wait_success(process, "fresh desktop setup")
            report = accept(root, token, workspace, env)
        if args.report:
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report), flush=True)
        return 0
    except (AcceptanceError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Desktop acceptance failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
