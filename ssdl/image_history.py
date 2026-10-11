"""Remember complete direct images at their original paths, without searching moved files."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from .media_manifest import file_entries, verify_entries


class ImageHistory:
    def __init__(self, filename: Path, directory: Path):
        filename.parent.mkdir(parents=True, exist_ok=True)
        self.root = directory.resolve()
        self.scope = os.path.normcase(str(self.root))
        self.connection = sqlite3.connect(str(filename), timeout=15)
        try:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS images (
                directory TEXT NOT NULL, source_key TEXT NOT NULL, metadata TEXT NOT NULL,
                PRIMARY KEY (directory, source_key))""")
            self.connection.commit()
        except sqlite3.Error:
            self.connection.close()
            raise

    def lookup(self, source_key: str, *, verify=True) -> dict | None:
        row = self.connection.execute("SELECT metadata FROM images WHERE directory=? AND source_key=?",
                                      (self.scope, source_key)).fetchone()
        if not row:
            return None
        try:
            metadata = json.loads(row[0])
            entries = metadata["entries"]
            if not isinstance(entries, list) or len(entries) != 1:
                return None
            entry = entries[0]
            name = entry["name"]
            if not isinstance(name, str) or Path(name).is_absolute():
                return None
            path = (self.root / name).resolve()
            if (not path.is_relative_to(self.root) or type(entry["size"]) is not int
                    or entry["size"] <= 0):
                return None
            if verify:
                if not verify_entries(self.root, entries):
                    return None
            return {"title": str(metadata.get("title", "")), "files": [name],
                    "quality": str(metadata.get("quality", "")), "warnings": [],
                    "size_bytes": entry["size"]}
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            return None

    def record(self, source_key: str, result: dict) -> None:
        files = result.get("files", [])
        if len(files) != 1:
            raise ValueError("invalid image record")
        name = files[0]
        metadata = {"title": result.get("title", ""), "quality": result.get("quality", ""),
                    "entries": file_entries(self.root, files)}
        self.connection.execute("INSERT OR REPLACE INTO images VALUES (?, ?, ?)",
            (self.scope, source_key, json.dumps(metadata, ensure_ascii=False)))
        self.connection.commit()

    def close(self):
        self.connection.close()
