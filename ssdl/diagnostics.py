"""Redact diagnostic text before storing, displaying, logging, or exporting it."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

REDACTED = "[REDACTED]"
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_SECRET = r"(?:auth_token|ct0|twid|authorization|cookie|set-cookie|password|passwd|access[_-]?token|refresh[_-]?token|csrf[_-]?token|token|secret|api[_-]?key|signature|sig)"


def redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if ":" in host:
            host = "[" + host + "]"
        if parsed.port:
            host += ":" + str(parsed.port)
        return urlunsplit((parsed.scheme, host, parsed.path,
                           "[REDACTED]" if parsed.query else "", ""))
    except (ValueError, UnicodeError):
        return "[URL]"


def redact_text(value, *, limit=4000) -> str:
    text = str(value or "")[:20000]
    # Header lines may contain many semicolon-separated values. Redact the
    # whole value before the narrower JSON / key-value substitutions.
    text = re.sub(r"(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+",
                  lambda match: match[1] + REDACTED, text)
    text = _URL.sub(lambda match: redact_url(match[0]), text)
    text = re.sub(r"(?i)([\"']?" + _SECRET + r"[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)",
                  lambda match: match[1] + REDACTED, text)
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer " + REDACTED, text)
    # Local paths belong in file controls, never in shareable diagnostics.
    text = re.sub(r"(?i)(?<![a-z0-9_])(?:[a-z]:[\\/]|\\\\[^\\\s]+\\|/(?:home|Users|tmp|private|mnt)/)[^\r\n\"'<>]*", "[PATH]", text)
    return text[:limit]


def redact_fields(value):
    """Sanitize diagnostic fields without changing operational URLs/file paths."""
    if isinstance(value, dict):
        return {key: ([redact_text(item, limit=1000) for item in item_value]
                      if key == "warnings" and isinstance(item_value, list) else
                      redact_text(item_value) if key in {"error", "error_detail", "message"} else
                      redact_fields(item_value)) for key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_fields(item) for item in value]
    return value
