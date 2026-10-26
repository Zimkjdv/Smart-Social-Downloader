"""Shared local-service configuration for the launcher and backend."""
from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_PORT = 8765


def configured_port() -> int:
    value = os.environ.get("SSDL_PORT", str(DEFAULT_PORT)).strip()
    if not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
        raise RuntimeError("SSDL_PORT must be a whole number from 1 to 65535.")
    return int(value)


def configured_cache_directory(root: Path) -> Path:
    """Keep native previews compatible; containers can mount a separate cache."""
    value = os.environ.get("SSDL_CACHE_DIR")
    if value is None:
        from .runtime_paths import paths
        return paths().cache if root.resolve() == paths().home else root / 'data'
    if not value.strip() or not Path(value).expanduser().is_absolute():
        raise RuntimeError("SSDL_CACHE_DIR must be an absolute directory.")
    # Do not resolve links: ThumbnailCache must still be able to reject them.
    return Path(value).expanduser().absolute()


def resolve_download_directory(value, *, media_root: Path | None = None) -> Path:
    directory = Path(value).expanduser().resolve()
    if media_root is not None and not directory.is_relative_to(media_root):
        raise ValueError("下載位置必須位於容器的 /downloads 持久化資料夾內。")
    return directory


def configured_media_root() -> Path | None:
    value = os.environ.get("SSDL_MEDIA_ROOT")
    if value is None:
        return None
    if not value.strip() or not Path(value).expanduser().is_absolute():
        raise RuntimeError("SSDL_MEDIA_ROOT must be an absolute directory.")
    return Path(value).expanduser().resolve()
