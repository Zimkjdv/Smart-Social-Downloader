"""X account URL normalization and a local, file-verified download history."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from .media_manifest import file_entries, verify_entries


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}\Z")
_RESERVED = {"home", "i", "search", "explore", "settings", "notifications", "messages",
             "compose", "login", "logout", "signup", "intent", "share", "tos", "privacy",
             "hashtag", "download", "about", "who_to_follow"}


def normalize_account(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if value.startswith("@"):
        handle = value[1:]
    elif "://" not in value and _HANDLE.fullmatch(value):
        handle = value
    else:
        try:
            parsed = urlparse(value)
            host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("mobile.")
            parts = parsed.path.strip("/").split("/")
            if (parsed.scheme not in {"https", "http"} or host not in {"x.com", "twitter.com"}
                    or parsed.username or parsed.password or parsed.port is not None
                    or len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"media", "timeline"})):
                raise ValueError
            handle = parts[0]
        except (ValueError, UnicodeError):
            raise ValueError("請輸入 X 帳號首頁、媒體頁網址或 @帳號。") from None
    if not _HANDLE.fullmatch(handle) or handle.lower() in _RESERVED:
        raise ValueError("X 帳號名稱需為 1～15 個英文字母、數字或底線。")
    handle = handle.lower()
    return f"https://x.com/{handle}", handle


def account_from_url(url: str) -> tuple[str, str] | None:
    # Automatic recognition applies to account URLs, never to bare text in URL mode.
    if "://" not in url:
        return None
    try:
        return normalize_account(url)
    except ValueError:
        return None


class ProfileArchive:
    """Remember complete posts, scoped to the account and exact output directory."""
    def __init__(self, filename: Path, output_dir: Path, account: str):
        filename.parent.mkdir(parents=True, exist_ok=True)
        self.root = output_dir.resolve()
        self.scope = os.path.normcase(str(self.root))
        self.account = account.lower()
        self.connection = sqlite3.connect(str(filename), timeout=15)
        try:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS posts (
                directory TEXT NOT NULL, account TEXT NOT NULL, post_id TEXT NOT NULL,
                files TEXT NOT NULL, PRIMARY KEY (directory, account, post_id))""")
            self.connection.commit()
        except sqlite3.Error:
            self.connection.close()
            raise

    def lookup(self, post_id: str, expected: int, expected_files=None) -> list[dict] | None:
        row = self.connection.execute(
            "SELECT files FROM posts WHERE directory=? AND account=? AND post_id=?",
            (self.scope, self.account, post_id)).fetchone()
        if not row:
            return None
        try:
            entries = json.loads(row[0])
            if not isinstance(entries, list) or len(entries) != expected or not entries:
                return None
            names = {os.path.normcase(str(self.root / entry["name"])) for entry in entries}
            if len(names) != expected:
                return None
            if expected_files is not None and names != {
                    os.path.normcase(str(self.root / name)) for name in expected_files}:
                return None
            if not verify_entries(self.root, entries, allow_legacy=True):
                return None
            return entries
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            return None

    def record(self, post_id: str, files: list[str], expected: int) -> list[dict]:
        if (len(files) != expected or not files
                or len({os.path.normcase(str(self.root / name)) for name in files}) != expected):
            raise ValueError("X 貼文媒體未完整保存，請稍後同步重試。")
        entries = file_entries(self.root, files)
        self.connection.execute("INSERT OR REPLACE INTO posts VALUES (?, ?, ?, ?)",
            (self.scope, self.account, post_id, json.dumps(entries, ensure_ascii=False)))
        self.connection.commit()
        return entries

    def reusable_files(self, post_id: str, expected_files: list[str], candidates) -> list[dict]:
        wanted = {os.path.normcase(str(self.root / name)) for name in expected_files}
        row = self.connection.execute("SELECT files FROM posts WHERE directory=? AND account=? AND post_id=?",
                                      (self.scope, self.account, post_id)).fetchone()
        if row:
            valid = []
            try:
                entries = json.loads(row[0])
                if not isinstance(entries, list):
                    return []
                seen = set()
                for entry in entries:
                    try:
                        path = (self.root / entry["name"]).resolve()
                        key = os.path.normcase(str(self.root / entry["name"]))
                        if (key not in wanted or key in seen or Path(entry["name"]).is_absolute()
                                or not path.is_relative_to(self.root) or not path.is_file()):
                            continue
                        stat = path.stat()
                        if type(entry["size"]) is not int or stat.st_size <= 0 or stat.st_size != entry["size"]:
                            continue
                        if "mtime_ns" in entry and stat.st_mtime_ns != entry["mtime_ns"]:
                            continue
                        valid.append({"name": entry["name"], "size": stat.st_size})
                        seen.add(key)
                    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                        continue
                return valid
            except (ValueError, TypeError):
                return []
        for candidate in candidates:
            try:
                files, total = candidate["files"], candidate["size_bytes"]
                keys = {os.path.normcase(str(self.root / name)) for name in files}
                if not files or not keys.issubset(wanted) or len(keys) != len(files) or type(total) is not int or total <= 0:
                    continue
                entries = []
                for name in files:
                    path = (self.root / name).resolve()
                    if Path(name).is_absolute() or not path.is_relative_to(self.root) or not path.is_file():
                        break
                    entries.append({"name": name, "size": path.stat().st_size})
                if len(entries) == len(files) and all(entry["size"] > 0 for entry in entries) and sum(entry["size"] for entry in entries) == total:
                    return entries
            except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                continue
        return []

    def close(self):
        self.connection.close()
