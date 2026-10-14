"""Encode UTF-8 JSON with a byte budget before writing any external bytes."""
from __future__ import annotations

import json


class JSONBudgetError(ValueError):
    def __init__(self, limit, observed_bytes):
        super().__init__("JSON exceeds byte budget")
        self.limit = limit
        # Encoding stops here: this is a lower bound, not a total size.
        self.observed_bytes = observed_bytes


def encode_json(value, limit, *, indent=None):
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, indent=indent,
                               separators=None if indent is not None else (",", ":"))
    result = bytearray()
    fragments, characters = [], 0

    def append(text):
        encoded = text.encode("utf-8")
        observed = len(result) + len(encoded)
        if observed > limit:
            raise JSONBudgetError(limit, observed)
        result.extend(encoded)

    for fragment in encoder.iterencode(value):
        # The JSON encoder can still allocate a large escaped string; this
        # bounds encoded output, not the input object or total process memory.
        for offset in range(0, len(fragment), 16384):
            piece = fragment[offset:offset + 16384]
            fragments.append(piece)
            characters += len(piece)
            if characters >= 16384:
                append("".join(fragments))
                fragments.clear()
                characters = 0
    if fragments:
        append("".join(fragments))
    return result
