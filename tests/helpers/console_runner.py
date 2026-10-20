"""Receipt-gated Windows console/worker fixtures; imports never start services."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def kernel():
    if os.name != "nt":
        raise OSError("Windows console acceptance requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetConsoleProcessList.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    api.GetConsoleProcessList.restype = wintypes.DWORD
    api.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    return api


def console_pids(api):
    values = (wintypes.DWORD * 128)()
    count = api.GetConsoleProcessList(values, len(values))
    if not 0 < count <= len(values):
        raise OSError("Cannot establish owned console membership")
    return set(values[:count])


def gate(root, token):
    """Called only after the base interpreter has joined its owner's Job Object."""
    api = kernel()
    # Before any child launch, a CREATE_NEW_CONSOLE base process must be alone.
    # Never send CTRL_C into a shared terminal or attach to somebody else's one.
    if console_pids(api) != {os.getpid()}:
        raise OSError("Refusing a shared or missing console")
    owner = {"pid": os.getpid(), "parent": os.getppid(), "token": token}
    (root / ".ssdl-console-owner").write_text(json.dumps(owner), encoding="ascii")
    # Do not use SIG_IGN: the Windows ignore-Ctrl+C attribute is inheritable.
    signal.signal(signal.SIGINT, lambda *_: None)
    return subprocess.call([str(root / ".venv/Scripts/python.exe"), "-I", "-X", "utf8", "-u",
                            str(Path(__file__).resolve()), "service", "--token", token], cwd=root)


def check_owner(root, token, api):
    owner = json.loads((root / ".ssdl-console-owner").read_text(encoding="ascii"))
    pids = console_pids(api)
    if (not isinstance(owner, dict) or owner.get("token") != token or type(owner.get("pid")) is not int
            or type(owner.get("parent")) is not int or owner["pid"] not in pids
            or owner["parent"] in pids or os.getpid() not in pids
            or not pids.issubset({owner["pid"], os.getpid(), os.getppid()})):
        raise OSError("Console is outside the admitted fixture scope")
    return owner


@contextmanager
def watch_processes(pids):
    """Hold real process handles so PID reuse cannot masquerade as cleanup."""
    if (type(pids) is not list or len(pids) != 2
            or any(type(pid) is not int or pid <= 0 for pid in pids) or len(set(pids)) != 2):
        raise ValueError("Invalid owned worker receipt")
    api, handles = kernel(), []
    try:
        for pid in pids:
            handle = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE; never terminate by PID.
            if not handle:
                raise OSError("Owned worker exited before interrupt acceptance")
            handles.append(handle)
        def stopped():
            if any(api.WaitForSingleObject(handle, 5000) != 0 for handle in handles):
                raise OSError("Owned worker tree survived graceful console exit")
        yield stopped
    finally:
        for handle in handles:
            api.CloseHandle(handle)


def worker(root, token):
    from ssdl.ipc import read_message, write_message
    payload = read_message(sys.stdin.buffer)  # The supervisor admits us before any helper creation.
    target = Path(payload["output_dir"]).resolve()
    if target != Path(os.environ["SSDL_DOWNLOAD_DIR"]).resolve():
        raise ValueError("Worker media target differs from the admitted fixture")
    target.mkdir(parents=True, exist_ok=True)
    (target / "console-partial.part").write_bytes(b"synthetic partial bytes")
    child = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(300)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    (root / ".ssdl-console-worker").write_text(json.dumps({"token": token, "pids": [os.getpid(), child.pid]}), encoding="ascii")
    write_message(sys.stdout.buffer, {"type": "progress", "data": {"status_text": "Synthetic console acceptance", "downloaded_bytes": 7}})
    time.sleep(300)
    return 1  # This fixture must be cancelled through the real worker supervisor.


def service(root, token):
    from ssdl import app as entry
    from ssdl.job_runtime import run_job
    from tests.helpers.install_runner import closed_status
    api = kernel()
    check_owner(root, token, api)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    original = entry.create_app
    captured = []
    def create():
        app = original(root)
        # Replace only media transport with a pipe-speaking synthetic worker.
        # The entry point, scheduler, process ownership, writer and close are real.
        def synthetic(*args, **kwargs):
            return run_job(*args, **kwargs, command=[sys.executable, "-I", "-u", str(Path(__file__).resolve()),
                                                   "worker", "--token", token])
        app.run_job = synthetic
        captured.append(app)
        return app
    entry.create_app = create
    sent, errors = [], []
    def interrupt():
        try:
            if sys.stdin.readline().strip() != "interrupt":
                raise ValueError("Missing console interrupt admission")
            check_owner(root, token, api)
            # CTRL_C cannot target a process group. This console was created
            # exclusively for our admitted gate/children, never the caller's console.
            if not api.GenerateConsoleCtrlEvent(0, 0):
                raise OSError("Windows refused the owned CTRL_C_EVENT")
            sent.append(True)
        except (OSError, ValueError) as error:
            errors.append(type(error).__name__)
    control = threading.Thread(target=interrupt, name="fixture-console-control", daemon=True)
    control.start()
    try:
        code = entry.main()  # Exercise the shipped KeyboardInterrupt path.
    finally:
        entry.create_app = original
    control.join(timeout=5)
    result = closed_status(captured[0]) if captured else {}
    result.update(ctrl_c=sent == [True] and not errors, control_stopped=not control.is_alive(), exit_code=code)
    (root / "data/console-closed.json").write_text(json.dumps(result), encoding="utf-8")
    if code != 0 or not all(result.get(key) is True for key in
                            ("closed", "threads_stopped", "durable", "ctrl_c", "control_stopped")):
        raise RuntimeError("Console entry did not close normally")
    return code


def main(argv=None):
    import argparse
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from tests.helpers.install_runner import verify_receipt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("service", "worker"))
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    verify_receipt(root, args.token)
    return service(root, args.token) if args.action == "service" else worker(root, args.token)


if __name__ == "__main__":
    raise SystemExit(main())
