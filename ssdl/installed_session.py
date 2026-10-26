"""Named objects shared with Inno Setup; never terminate a user's process."""
from contextlib import contextmanager
import ctypes
import os

RUNNING = "Local\\SSDL.InstalledApplication"
UPDATING = "Local\\SSDL.Installation.Active"


@contextmanager
def installed_session():
    if os.name != "nt":
        yield
        return
    from .desktop_service import Controls
    controls = Controls()
    api = controls.api
    api.OpenMutexW.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_wchar_p]
    api.OpenMutexW.restype = ctypes.c_void_p
    def updating():
        handle = api.OpenMutexW(0x100000, False, UPDATING)
        if handle:
            api.CloseHandle(handle)
            return True
        error = ctypes.get_last_error()
        if error != 2:
            raise ctypes.WinError(error)
        return False
    try:
        if updating():
            raise RuntimeError("Installation is in progress. Wait for Setup to finish.")
        controls.keep(api.CreateMutexW(None, False, RUNNING))
        if updating():
            raise RuntimeError("Installation is in progress. Wait for Setup to finish.")
        yield
    finally:
        controls.close()
