"""Shared local-service configuration for the launcher and backend."""
from __future__ import annotations

import os
import re

DEFAULT_PORT = 8765


def configured_port() -> int:
    value = os.environ.get("SSDL_PORT", str(DEFAULT_PORT)).strip()
    if not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
        raise RuntimeError("SSDL_PORT must be a whole number from 1 to 65535.")
    return int(value)
