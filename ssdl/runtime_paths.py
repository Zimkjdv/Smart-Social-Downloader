"""Resource locations and writable scope, shared by every process/desktop host."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


@dataclass(frozen=True)
class RuntimePaths:
    resources: Path
    home: Path
    cache: Path
    profile: Path
    downloads: Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def paths() -> RuntimePaths:
    resources = Path(__file__).resolve().parents[1]
    selected = os.environ.get("SSDL_HOME")
    if selected is not None:
        if not selected.strip() or not Path(selected).expanduser().is_absolute():
            raise RuntimeError("SSDL_HOME must be an absolute writable data directory.")
        home = Path(selected).expanduser().resolve()
    elif frozen():
        local = os.environ.get("LOCALAPPDATA", "")
        if not local or not Path(local).is_absolute():
            raise RuntimeError("LOCALAPPDATA is unavailable; set SSDL_HOME explicitly.")
        home = (Path(local) / "Smart Social Downloader").resolve()
    else:
        home = resources
    if frozen() and (home == resources or home.is_relative_to(resources)
                     or home.is_relative_to(Path(sys.executable).resolve().parent)):
        raise RuntimeError("Installed data must be outside the application directory.")
    if frozen():
        for key in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432'):
            value = os.environ.get(key)
            if value and home.is_relative_to(Path(value).resolve()):
                raise RuntimeError('Installed data cannot be stored in Program Files.')
    separate = home != resources
    cache = home / ("cache" if separate else "data")
    return RuntimePaths(resources, home, cache, cache / "webview2", home / "downloads")


_ROLES = {"ssdl.desktop_service": "backend", "ssdl.desktop_control": "control",
          "ssdl.job_runner": "worker", "ssdl.pixiv_auth_exchange": "pixiv-exchange"}


def module_command(module: str, *arguments: str) -> list[str]:
    """Only registered roles can start another bundled interpreter."""
    if module not in _ROLES:
        raise ValueError("Unregistered runtime role")
    if frozen():
        executable = Path(sys.executable).resolve().parent / "ssdl-runtime.exe"
        return [str(executable), "--role", _ROLES[module], *arguments]
    locations = paths()
    if locations.home != locations.resources:
        return [sys.executable, "-X", "utf8", "-u",
                str(locations.resources / "desktop/frozen_entry.py"), "--role", _ROLES[module], *arguments]
    return [sys.executable, "-X", "utf8", "-u", "-m", module, *arguments]


def prepare_environment() -> None:
    """Bundled tools take precedence without altering the user's system PATH."""
    if frozen():
        tools = paths().resources / "tools-runtime"
        os.environ["PATH"] = str(tools) + os.pathsep + os.environ.get("PATH", "")
        os.environ["IMAGEIO_FFMPEG_EXE"] = str(tools / "ffmpeg.exe")
