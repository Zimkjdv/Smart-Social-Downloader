"""Windows desktop service ownership without PID-based process termination."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RECORD = DATA / "background-service.json"
LOG = DATA / "background.log"


class Controls:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Background desktop mode requires Windows. Use python tools/manage.py start here.")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateMutexW", [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("CreateEventW", [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("OpenEventW", [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("SetEvent", [wintypes.HANDLE], wintypes.BOOL),
            ("ResetEvent", [wintypes.HANDLE], wintypes.BOOL),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
            ("WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            ("ReleaseMutex", [wintypes.HANDLE], wintypes.BOOL),
        ):
            method = getattr(self.api, name)
            method.argtypes, method.restype = args, result
        identity = hashlib.sha256(os.path.normcase(str(ROOT)).encode()).hexdigest()[:32]
        self.prefix = "Local\\SSDL.Desktop." + identity + "."
        self.handles = []

    def keep(self, handle):
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handles.append(handle)
        return handle

    def event(self, name):
        return self.keep(self.api.CreateEventW(None, True, False, self.prefix + name))

    def open_event(self, name, *, modify=False):
        handle = self.api.OpenEventW(0x100000 | (2 if modify else 0), False, self.prefix + name)
        if not handle:
            error = ctypes.get_last_error()
            if error == 2:
                return None
            raise ctypes.WinError(error)
        return self.keep(handle)

    def signalled(self, handle):
        result = self.api.WaitForSingleObject(handle, 0)
        if result not in (0, 258):
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    def signal(self, handle):
        if not self.api.SetEvent(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        for handle in reversed(self.handles):
            self.api.CloseHandle(handle)
        self.handles.clear()


def open_page():
    value = json.loads(RECORD.read_text(encoding="utf-8"))
    port = value.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise RuntimeError("Invalid background service record. Stop the service and start again.")
    url = f"http://127.0.0.1:{port}/"
    print("Background service ready:", url)
    if os.environ.get("SSDL_NONINTERACTIVE"):
        return
    try:
        opened = webbrowser.open(url)
    except OSError:
        opened = False
    if not opened:
        print("Open this URL in your browser.")


def start(check_environment):
    controls = Controls()
    launch = None
    owned = False
    try:
        # Serialize launchers as well as service ownership: a losing child can
        # exit before the winner publishes readiness during simultaneous starts.
        launch = controls.keep(controls.api.CreateMutexW(None, False, controls.prefix + "launch"))
        result = controls.api.WaitForSingleObject(launch, 60_000)
        if result not in (0, 0x80):
            raise RuntimeError("Another startup is still in progress. Retry start.bat shortly.")
        owned = True
        ready = controls.open_event("ready")
        if ready and controls.signalled(ready):
            open_page()
            return 0
        stopping = controls.open_event("stop")
        if stopping and controls.signalled(stopping):
            raise RuntimeError("The background service is stopping. Wait for stop.bat to finish, then start again.")
        check_environment()
        DATA.mkdir(parents=True, exist_ok=True)
        if LOG.is_file() and LOG.stat().st_size > 2 * 1024 * 1024 and not stopping:
            LOG.replace(DATA / "background.previous.log")
        with LOG.open("ab", buffering=0) as output:
            process = subprocess.Popen([sys.executable, "-X", "utf8", "-u", "-m", "ssdl.desktop_service"],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if ready is None:
                ready = controls.open_event("ready")
            if ready and controls.signalled(ready):
                open_page()
                return 0
            if process.poll() is not None:
                raise RuntimeError("Background startup failed. See data/background.log. A foreground service may already own the port.")
            time.sleep(0.2)
        raise RuntimeError("Startup is still pending. See data/background.log; use stop.bat before retrying if necessary.")
    finally:
        if owned:
            controls.api.ReleaseMutex(launch)
        controls.close()


def stop():
    controls = Controls()
    try:
        request = controls.open_event("stop", modify=True)
        if not request:
            print("No background service owned by this project is running. Foreground services are stopped with Ctrl+C.")
            return 0
        done = controls.open_event("done")
        if not done:
            raise RuntimeError("Service startup/cleanup is in progress. Run stop.bat again shortly.")
        controls.signal(request)
        print("Stopping background service and preserving queue state...")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if controls.signalled(done):
                print("Background service stopped.")
                return 0
            time.sleep(0.2)
        raise RuntimeError("Shutdown is still in progress. Check data/background.log and retry stop.bat. No process was forcibly killed.")
    finally:
        controls.close()


def run():
    from .app import main
    controls = Controls()
    mutex = ready = done = None
    owned = False
    try:
        mutex = controls.keep(controls.api.CreateMutexW(None, False, controls.prefix + "owner"))
        result = controls.api.WaitForSingleObject(mutex, 0)
        if result not in (0, 0x80):  # Include acquisition of an abandoned mutex.
            return 1
        owned = True
        done = controls.event("done")
        controls.api.ResetEvent(done)
        request = controls.event("stop")
        controls.api.ResetEvent(request)
        ready = controls.event("ready")
        controls.api.ResetEvent(ready)

        def stopping():
            if controls.signalled(request):
                controls.api.ResetEvent(ready)
                return True
            return False

        def started(port):
            temporary = RECORD.with_suffix(".tmp")
            temporary.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
            temporary.replace(RECORD)
            controls.signal(ready)

        return main(stop_requested=stopping, on_ready=started)
    finally:
        if owned:
            if ready:
                controls.api.ResetEvent(ready)
            try:
                RECORD.unlink(missing_ok=True)
            finally:
                if done:
                    controls.signal(done)
                controls.api.ReleaseMutex(mutex)
        controls.close()


if __name__ == "__main__":
    raise SystemExit(run())
