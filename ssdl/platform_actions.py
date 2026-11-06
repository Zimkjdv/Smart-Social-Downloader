"""Dispatch authorized local paths through OS file associations, without a shell.

Callers own job identity, media type and directory containment checks. This is
not an arbitrary-path browser/bridge API.
"""
from __future__ import annotations

import os
from pathlib import Path


class UnsupportedPlatformError(OSError):
    """The host has no supported file-association dispatcher."""


def open_path(target: Path) -> None:
    """Open a validated file or directory using Windows file associations."""
    if os.name != "nt":
        raise UnsupportedPlatformError("Native file actions require Windows")
    os.startfile(str(target))
