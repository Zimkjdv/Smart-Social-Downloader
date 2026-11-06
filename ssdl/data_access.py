"""Windows writer lease shared by foreground/background and migration."""
from contextlib import contextmanager
import os


@contextmanager
def writer_lease(home):
    if os.name != 'nt':
        yield
        return
    from .desktop_service import Controls
    controls=Controls(home)
    acquired=False
    try:
        handle=controls.keep(controls.api.CreateMutexW(None,False,controls.prefix+'writer'))
        acquired=controls.api.WaitForSingleObject(handle,0) in (0,0x80)
        if not acquired:
            raise RuntimeError('Another backend or data migration already uses this data directory.')
        yield
    finally:
        if acquired:controls.api.ReleaseMutex(handle)
        controls.close()
