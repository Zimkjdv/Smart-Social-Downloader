"""Shared, portable author directory names for Pixiv originals."""
from __future__ import annotations

import re
import unicodedata

from .media_contracts import DownloadError


def author_folder(user: dict) -> str:
    """Keep the display name readable and the numeric author ID unambiguous."""
    account = str(user.get("id", "")) if isinstance(user, dict) else ""
    if not re.fullmatch(r"[1-9][0-9]{0,19}", account):
        raise DownloadError("Pixiv 未提供有效的作者資料。", code="pixiv_invalid_media")
    name = user.get("name")
    name = unicodedata.normalize("NFC", name) if isinstance(name, str) else ""
    # Use the same portable segment on Windows and Linux. Do not let a display
    # name create nested paths, include controls or hide the ID with bidi marks.
    name = re.sub(r'[\\/<>:"|?*\x00-\x1f\x7f\ud800-\udfff\u202a-\u202e\u2066-\u2069]', "_", name)
    name = name.strip().strip(". ")
    # Bound UTF-8 bytes rather than characters so multibyte names fit a Linux
    # directory segment too; the ID suffix is never truncated.
    name = name.encode("utf-8")[:160].decode("utf-8", errors="ignore").rstrip(". ") or "Pixiv"
    return f"{name}({account})"
