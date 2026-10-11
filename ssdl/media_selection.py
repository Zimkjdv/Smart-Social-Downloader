"""Bounded, credential-free player choices shared by extraction and the queue."""
from __future__ import annotations

import hashlib
from urllib.parse import urlparse

MAX_CHOICES = 12


def selection_id(owner: str, marker: str) -> str:
    # Query signatures are deliberately excluded; ordinal/DOM markers identify players.
    parsed = urlparse(owner)
    return hashlib.sha256(f"{parsed.netloc.lower()}{parsed.path}\n{marker}".encode()).hexdigest()[:24]


def choice(identifier, title, url="", *, variants=1, kind="video"):
    return {"id": identifier, "title": str(title or "")[:180],
            "host": (urlparse(url).hostname or "")[:253],
            "variants": max(1, min(100, int(variants))), "kind": kind}


def validate_choices(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_CHOICES:
        raise ValueError("Invalid media choices")
    for item in value:
        if (not isinstance(item, dict) or set(item) != {"id", "title", "host", "variants", "kind"}
                or not isinstance(item["id"], str) or len(item["id"]) != 24
                or any(char not in "0123456789abcdef" for char in item["id"])
                or not all(isinstance(item[key], str) for key in ("title", "host", "kind"))
                or len(item["title"]) > 180 or len(item["host"]) > 253
                or item["kind"] not in {"video", "audio", "embed", "media"}
                or type(item["variants"]) is not int or not 1 <= item["variants"] <= 100):
            raise ValueError("Invalid media choice")
    if len({item["id"] for item in value}) != len(value):
        raise ValueError("Duplicate media choice")
    return value


class SelectionRequired(RuntimeError):
    code = "media_selection_required"

    def __init__(self, options):
        super().__init__("此網頁有多個媒體，請先選擇要下載的播放器。")
        self.options = validate_choices(options)
        self.files = []
