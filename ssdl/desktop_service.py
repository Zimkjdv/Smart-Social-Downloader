"""Windows desktop service ownership without PID-based process termination."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import webbrowser
from contextlib import contextmanager

from .desktop_control import probe_service, read_record, scope_key, validate_identity

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
        self.prefix = "Local\\SSDL.Desktop." + scope_key(ROOT) + "."
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

    def owner_running(self):
        owner = self.keep(self.api.CreateMutexW(None, False, self.prefix + "owner"))
        result = self.api.WaitForSingleObject(owner, 0)
        if result == 258:
            return True
        if result not in (0, 0x80):
            raise ctypes.WinError(ctypes.get_last_error())
        self.api.ReleaseMutex(owner)
        return False

    def close(self):
        for handle in reversed(self.handles):
            self.api.CloseHandle(handle)
        self.handles.clear()


@contextmanager
def launch_guard(controls):
    launch = controls.keep(controls.api.CreateMutexW(None, False, controls.prefix + "launch"))
    acquired = controls.api.WaitForSingleObject(launch, 60_000)
    if acquired not in (0, 0x80):
        raise RuntimeError("Another startup is still in progress. Retry shortly.")
    try:
        yield
    finally:
        controls.api.ReleaseMutex(launch)


def verified_service(controls):
    ready = controls.open_event("ready")
    stopping = controls.open_event("stop")
    if (not controls.owner_running() or not ready or not controls.signalled(ready)
            or stopping and controls.signalled(stopping)):
        raise RuntimeError("This project's background service is not ready or is stopping.")
    return probe_service(read_record(RECORD, ROOT), ROOT)


def backend_status():
    controls = Controls()
    try:
        with launch_guard(controls):
            return {**verified_service(controls), "ownership": "attached"}
    finally:
        controls.close()


def open_page(service=None):
    value = validate_identity(service if service is not None else backend_status(), ROOT)
    url = value["origin"] + "/"
    print("Background service ready:", url)
    if os.environ.get("SSDL_NONINTERACTIVE"):
        return
    try:
        opened = webbrowser.open(url)
    except OSError:
        opened = False
    if not opened:
        print("Open this URL in your browser.")


def ensure_backend(check_environment=None, *, timeout=60):
    """Start/attach without showing UI; only a newly started instance is owned.

    The caller can supply the existing launcher's environment preflight. GUI
    callers omit it so missing engines can be repaired from the diagnostics UI.
    """
    controls = Controls()
    try:
        with launch_guard(controls):
            running = controls.owner_running()
            stopping = controls.open_event("stop")
            if running and stopping and controls.signalled(stopping):
                raise RuntimeError("The background service is stopping. Wait for stop.bat to finish, then start again.")
            ready = controls.open_event("ready")
            if running and ready and controls.signalled(ready):
                return {**verified_service(controls), "ownership": "attached"}
            process = None
            if not running:
                if check_environment is not None:
                    check_environment()
                DATA.mkdir(parents=True, exist_ok=True)
                if LOG.is_file() and LOG.stat().st_size > 2 * 1024 * 1024:
                    LOG.replace(DATA / "background.previous.log")
                with LOG.open("ab", buffering=0) as output:
                    process = subprocess.Popen([sys.executable, "-X", "utf8", "-u", "-m", "ssdl.desktop_service"],
                        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if ready is None:
                    ready = controls.open_event("ready")
                if ready and controls.signalled(ready) and controls.owner_running():
                    try:
                        service = verified_service(controls)
                        return {**service, "ownership": "started" if process is not None else "attached"}
                    except RuntimeError:
                        # A stale event/record may still be disappearing while
                        # a new child acquires ownership and publishes identity.
                        pass
                if process is not None and process.poll() is not None:
                    raise RuntimeError("Background startup failed. See data/background.log. Another service may own the port.")
                if process is None and not controls.owner_running():
                    raise RuntimeError("The background service exited before becoming ready. See data/background.log.")
                time.sleep(0.2)
            raise RuntimeError("Startup is still pending. See data/background.log; use stop.bat before retrying if necessary.")
    finally:
        controls.close()


def start(check_environment):
    service = ensure_backend(check_environment)
    open_page(service)
    return 0


def request_stop(controls, *, instance=None):
    suffix = "." + instance if instance is not None else ""
    request = controls.open_event("stop" + suffix, modify=True)
    if not request or not controls.owner_running():
        if instance is not None:
            raise RuntimeError("The owned backend has exited. No replacement service was stopped.")
        print("No background service owned by this project is running. Foreground services are stopped with Ctrl+C.")
        return 0
    done = controls.open_event("done" + suffix)
    if not done:
        raise RuntimeError("Service startup/cleanup is in progress. Run stop.bat again shortly.")
    controls.signal(request)
    print("Stopping background service and preserving queue state...")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if controls.signalled(done) and (instance is not None or not controls.owner_running()):
            print("Background service stopped.")
            return 0
        time.sleep(0.2)
    raise RuntimeError("Shutdown is still in progress. Check data/background.log and retry stop.bat. No process was forcibly killed.")


def stop():
    """Explicit operator stop, including a pending/older project-owned service."""
    controls = Controls()
    try:
        with launch_guard(controls):
            return request_stop(controls)
    finally:
        controls.close()


def stop_owned(service):
    """A shell cannot stop an attached or replacement instance by mistake."""
    expected = validate_identity(service, ROOT)
    if service.get("ownership") != "started":
        raise RuntimeError("This shell attached to an existing service; use stop.bat for an explicit operator stop.")
    controls = Controls()
    try:
        with launch_guard(controls):
            if verified_service(controls) != expected:
                raise RuntimeError("The owned backend was replaced. No service was stopped.")
            return request_stop(controls, instance=expected["instance"])
    finally:
        controls.close()


class WindowSession:
    """One shell window per scope; a repeated launch requests focus, not a backend.

    Acquire and close on the GUI main thread (Windows mutex ownership). The
    GUI may consume the focus event on another thread. Closing never stops work.
    """
    def __init__(self):
        self.controls = Controls()
        self.primary = False
        self.mutex = self.focus = None

    def __enter__(self):
        try:
            self.mutex = self.controls.keep(self.controls.api.CreateMutexW(None, False, self.controls.prefix + "window"))
            acquired = self.controls.api.WaitForSingleObject(self.mutex, 0)
            if acquired not in (0, 0x80, 258):
                raise ctypes.WinError(ctypes.get_last_error())
            self.primary = acquired != 258
            self.focus = self.controls.event("window-focus")
            if not self.primary:
                self.controls.signal(self.focus)
            return self
        except BaseException:
            self.close()
            raise

    def consume_focus(self):
        if self.primary and self.focus and self.controls.signalled(self.focus):
            self.controls.api.ResetEvent(self.focus)
            return True
        return False

    def close(self):
        if self.primary:
            self.controls.api.ReleaseMutex(self.mutex)
            self.primary = False
        self.controls.close()

    def __exit__(self, *exception):
        self.close()


def run():
    from .app import main
    controls = Controls()
    mutex = ready = done = instance_request = instance_done = None
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
            if controls.signalled(request) or instance_request and controls.signalled(instance_request):
                controls.api.ResetEvent(ready)
                return True
            return False

        def started(service):
            nonlocal instance_request, instance_done
            validate_identity(service, ROOT)
            instance_request = controls.event("stop." + service["instance"])
            instance_done = controls.event("done." + service["instance"])
            temporary = RECORD.with_suffix(".tmp")
            temporary.write_text(json.dumps({**service, "pid": os.getpid()}), encoding="utf-8")
            temporary.replace(RECORD)
            controls.signal(ready)

        return main(stop_requested=stopping, on_service_ready=started)
    finally:
        if owned:
            if ready:
                controls.api.ResetEvent(ready)
            try:
                RECORD.unlink(missing_ok=True)
            finally:
                if done:
                    controls.signal(done)
                if instance_done:
                    controls.signal(instance_done)
                controls.api.ReleaseMutex(mutex)
        controls.close()


if __name__ == "__main__":
    raise SystemExit(run())
