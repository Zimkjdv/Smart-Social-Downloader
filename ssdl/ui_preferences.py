"""Versioned, shell-neutral presentation preferences; no WebView profile copying."""
import json
import os
from pathlib import Path
import tempfile
import threading


def validate(value):
    if (not isinstance(value, dict) or set(value) - {"schema", "language", "page_size"}
            or type(value.get("schema")) is not int or value["schema"] != 1
            or value.get("language") not in {"en", "zh-Hant"}
            or type(value.get("page_size")) is not int or value["page_size"] not in {10, 20, 50}):
        raise ValueError("Invalid UI preferences")
    return dict(value)


class UIPreferences:
    def __init__(self, filename):
        self.filename = Path(filename)
        self.lock = threading.Lock()

    def read(self):
        with self.lock:
            try:
                with self.filename.open("rb") as stream:
                    raw = stream.read(4097)
                if len(raw) > 4096:
                    raise ValueError()
                return validate(json.loads(raw))
            except FileNotFoundError:
                return None

    def save(self, value):
        value = validate(value)
        with self.lock:
            self.filename.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.filename.parent, prefix=".ui-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(json.dumps(value).encode("utf-8")); stream.flush(); os.fsync(stream.fileno())
                temporary.replace(self.filename)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return value
