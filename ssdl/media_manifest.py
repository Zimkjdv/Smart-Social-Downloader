"""Verified source-to-file manifests, scoped to the original download root."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time


def file_entries(root: Path, files) -> list[dict]:
    root = root.resolve()
    entries, seen = [], set()
    if not isinstance(files, (list, tuple)) or not files:
        raise ValueError("Empty manifest")
    for name in files:
        if not isinstance(name, str) or Path(name).is_absolute() or name.endswith((".part", ".tmp", ".ytdl")):
            raise ValueError("Invalid media path")
        path = (root / name).resolve()
        key = os.path.normcase(str(path))
        if key in seen or not path.is_relative_to(root) or (root / name).is_symlink() or not path.is_file():
            raise ValueError("Invalid media file")
        stat = path.stat()
        if stat.st_size <= 0:
            raise ValueError("Empty media file")
        entries.append({"name": name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
        seen.add(key)
    return entries


def verify_entries(root: Path, entries, *, allow_legacy=False) -> bool:
    try:
        if not isinstance(entries, list) or not entries:
            return False
        current = file_entries(root, [item["name"] for item in entries])
        return all(type(old["size"]) is int and old["size"] == new["size"] and
                   ((allow_legacy and "mtime_ns" not in old) or
                    type(old.get("mtime_ns")) is int and old["mtime_ns"] == new["mtime_ns"])
                   for old, new in zip(entries, current))
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return False


class MediaManifest:
    def __init__(self, filename: Path, root: Path):
        filename.parent.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.scope = os.path.normcase(str(self.root))
        self.connection = sqlite3.connect(str(filename), timeout=5)
        try:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS media (
                directory TEXT NOT NULL, source TEXT NOT NULL, metadata TEXT NOT NULL,
                PRIMARY KEY (directory, source))""")
            self.connection.commit()
        except Exception:
            self.connection.close()
            raise

    @staticmethod
    def key(source):
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def lookup(self, source, *, verify=True):
        row = self.connection.execute("SELECT metadata FROM media WHERE directory=? AND source=?",
                                      (self.scope, self.key(source))).fetchone()
        if not row:
            return None
        try:
            value = json.loads(row[0])
            if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or value.get("complete") is not True:
                return None
            if any(not isinstance(value.get(key, ""), str) for key in ("title", "quality", "engine", "media_id")):
                return None
            if not isinstance(value["entries"], list) or not value["entries"]:
                return None
            seen = set()
            for entry in value["entries"]:
                if (not isinstance(entry, dict) or not isinstance(entry.get("name"), str)
                        or Path(entry["name"]).is_absolute()
                        or not (self.root / entry["name"]).resolve().is_relative_to(self.root)
                        or type(entry.get("size")) is not int or entry["size"] <= 0
                        or type(entry.get("mtime_ns")) is not int):
                    return None
                path = os.path.normcase(str((self.root / entry["name"]).resolve()))
                if path in seen or entry["name"].endswith((".part", ".tmp", ".ytdl")):
                    return None
                seen.add(path)
            if verify and not verify_entries(self.root, value["entries"]):
                return None
            return value
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            return None

    def record(self, source, result):
        entries = file_entries(self.root, result["files"])
        metadata = {"version": 1, "complete": True, "recorded_at": time.time(),
                    "title": str(result.get("title", "")), "quality": str(result.get("quality", "")),
                    "engine": str(result.get("engine", "")), "media_id": str(result.get("media_id", "")),
                    "video_quality": str(result.get("video_quality", "best")),
                    "selected_media": str(result.get("selected_media", "")),
                    "entries": entries}
        self.connection.execute("INSERT OR REPLACE INTO media VALUES (?, ?, ?)",
            (self.scope, self.key(source), json.dumps(metadata, ensure_ascii=False)))
        self.connection.commit()

    def promote(self, source, legacy, *, video_quality="best", selected_media=""):
        """Copy trusted old evidence unchanged, then recheck the original files.

        Restatting into a new record would bless a file modified after the old
        lookup. Keep the old size/mtime evidence, without replacing a record
        published by another writer while this source was being checked.
        """
        value = self.lookup(legacy)
        if (not value or value.get("video_quality", "best") != video_quality
                or value.get("selected_media", "") != selected_media):
            return None
        self.connection.execute("INSERT OR IGNORE INTO media VALUES (?, ?, ?)",
            (self.scope, self.key(source), json.dumps(value, ensure_ascii=False)))
        self.connection.commit()
        return self.lookup(source)

    def close(self):
        self.connection.close()
