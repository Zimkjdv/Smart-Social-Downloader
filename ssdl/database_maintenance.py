"""Owned, explicit SQLite diagnostics/backups/VACUUM; never prune dedup rows."""
from __future__ import annotations

from contextlib import closing
import copy
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time
import uuid

DATABASES = {"images": ("image-history.sqlite3", "images"),
             "media": ("media-manifest.sqlite3", "media"),
             "profiles": ("x-profiles.sqlite3", "posts")}
OPERATION_SECONDS = 120
BUSY_MILLISECONDS = 1000
MESSAGES = {
    "database_busy": "資料庫維護正在進行，請稍後再試。",
    "database_pause_required": "請先暫停佇列，並等待目前下載結束，再備份或整理資料庫。",
    "database_closed": "資料庫維護已關閉，請重新啟動工具。",
    "database_path_blocked": "資料庫路徑不是一般檔案或資料夾，已停止操作。",
    "database_locked": "資料庫正在使用中，請稍後重新檢查。",
    "database_invalid": "資料庫無法通過完整性檢查；原檔保留，請查看備份與修復說明。",
    "database_schema": "資料庫結構無法辨識，已保留原檔並停止整理。",
    "database_io": "資料庫操作失敗，請檢查磁碟空間與存取權限。",
    "database_error": "資料庫操作未完成；原檔與已完成的備份保留。",
    "database_timeout": "資料庫操作超過時間限制，請稍後再試。",
    "database_cancelled": "資料庫維護已取消，已完成的備份保留。",
}


class MaintenanceError(RuntimeError):
    def __init__(self, code):
        super().__init__(MESSAGES[code])
        self.code = code


def error_code(exc):
    if isinstance(exc, MaintenanceError):
        return exc.code
    number = getattr(exc, "sqlite_errorcode", 0) & 255
    if number in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        return "database_locked"
    if number in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB}:
        return "database_invalid"
    return "database_io" if isinstance(exc, OSError) else "database_error"


class DatabaseMaintenance:
    def __init__(self, data_directory: Path):
        self.directory = data_directory.absolute()
        self.backups = self.directory / "database-backups"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._status = {"ready": False, "busy": False, "phase": "idle", "operation": "",
            "instance": uuid.uuid4().hex, "revision": 0,
            "checked_at": 0, "entries": [], "total_bytes": 0, "reclaimable_bytes": 0,
            "backup_name": "", "backup_bytes": 0, "error_code": "", "result_code": ""}

    def status(self):
        with self._lock:
            return copy.deepcopy(self._status)

    def path_for(self, key):
        """The downloader and maintenance share one fixed filename catalogue."""
        return self.directory / DATABASES[key][0]

    def blocks_downloads(self):
        with self._lock:
            return self._status["busy"] and self._status["operation"] in {"backup", "compact"}

    def request(self, action):
        if action not in {"refresh", "backup", "compact"}:
            raise ValueError("Invalid maintenance action")
        with self._lock:
            if self._stop.is_set():
                raise MaintenanceError("database_closed")
            if self._status["busy"]:
                raise MaintenanceError("database_busy")
            self._status.update(busy=True, operation=action, phase="running", error_code="", result_code="")
            self._status["revision"] += 1
            self._thread = threading.Thread(target=self._run, args=(action,), name="database-maintenance", daemon=True)
            try:
                self._thread.start()
            except Exception:
                self._status.update(busy=False, phase="failed", error_code="database_error")
                self._status["revision"] += 1
                raise MaintenanceError("database_error") from None
        return self.status()

    def _guard(self):
        if self._stop.is_set():
            raise MaintenanceError("database_cancelled")
        if time.monotonic() >= self._deadline:
            raise MaintenanceError("database_timeout")

    @staticmethod
    def _ordinary(path, *, directory=False):
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
                or not directory and info.st_nlink > 1):
            raise MaintenanceError("database_path_blocked")
        return True

    def _path(self, filename):
        self._ordinary(self.directory, directory=True)
        path = self.directory / filename
        exists = self._ordinary(path)
        sidecars = False
        for suffix in ("-wal", "-shm", "-journal"):
            sidecars = self._ordinary(path.with_name(path.name + suffix)) or sidecars
        if sidecars and not exists:
            raise MaintenanceError("database_invalid")
        return path if exists else None

    def _connect(self, path, *, write=False):
        self._guard()
        connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True,
                                     timeout=BUSY_MILLISECONDS / 1000)
        try:
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.set_progress_handler(lambda: int(self._stop.is_set() or time.monotonic() >= self._deadline), 1000)
        except Exception:
            connection.close()
            raise
        return connection

    def _check(self, connection):
        self._guard()
        if connection.execute("PRAGMA quick_check(1)").fetchall() != [("ok",)]:
            raise MaintenanceError("database_invalid")

    def _inspect(self, key):
        filename, table = DATABASES[key]
        entry = {"id": key, "filename": filename, "status": "missing", "error_code": "",
                 "size_bytes": 0, "wal_bytes": 0, "shm_bytes": 0, "journal_bytes": 0,
                 "page_count": 0, "page_size": 0, "free_pages": 0, "reclaimable_bytes": 0,
                 "records": None, "schema_ok": False, "compacted": False, "checkpoint_busy": False}
        self._guard()
        path = self._path(filename)
        if path is None:
            return entry
        for name, suffix in (("size_bytes", ""), ("wal_bytes", "-wal"), ("shm_bytes", "-shm"), ("journal_bytes", "-journal")):
            candidate = path.with_name(path.name + suffix)
            if self._ordinary(candidate):
                entry[name] = candidate.stat().st_size
        try:
            with closing(self._connect(path)) as connection:
                self._check(connection)
                for name in ("page_count", "page_size"):
                    entry[name] = connection.execute("PRAGMA " + name).fetchone()[0]
                entry["free_pages"] = connection.execute("PRAGMA freelist_count").fetchone()[0]
                # Only count the known actual table, never a view or arbitrary SQL.
                entry["schema_ok"] = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
                if entry["schema_ok"]:
                    entry["records"] = connection.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0]
        except (sqlite3.Error, MaintenanceError) as exc:
            self._guard()
            entry.update(status="error", error_code=error_code(exc))
            return entry
        entry.update(status="ok", reclaimable_bytes=entry["free_pages"] * entry["page_size"])
        return entry

    def _backup(self, entries):
        # Publish a whole set only after every present database was copied and
        # checked. SQLite backup includes committed WAL data; never raw-copy it.
        if not any(item["status"] != "missing" for item in entries):
            return "", 0
        self._ordinary(self.directory, directory=True)
        self.backups.mkdir(exist_ok=True)
        self._ordinary(self.backups, directory=True)
        name = "backup-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:12]
        pending = self.backups / (".pending-" + uuid.uuid4().hex)
        pending.mkdir()
        try:
            for item in entries:
                if item["status"] == "missing":
                    continue
                path = self._path(item["filename"])
                if path is None:
                    raise MaintenanceError("database_io")
                target = pending / item["filename"]
                with closing(self._connect(path)) as source, closing(sqlite3.connect(target)) as destination:
                    destination.execute("PRAGMA trusted_schema=OFF")
                    destination.set_progress_handler(lambda: int(self._stop.is_set() or time.monotonic() >= self._deadline), 1000)
                    source.backup(destination, pages=256, progress=lambda *args: self._guard(), sleep=.05)
                    self._check(destination)
                with target.open("r+b") as stream:
                    os.fsync(stream.fileno())
            self._guard()
            size = sum(path.stat().st_size for path in pending.iterdir())
            pending.rename(self.backups / name)
            return name, size
        finally:
            # Only remove fixed files in this owned staging directory. No
            # recursive traversal and no cleanup of published/user backups.
            if pending.exists() and self._ordinary(pending, directory=True):
                for filename, _ in DATABASES.values():
                    for suffix in ("", "-journal", "-wal", "-shm"):
                        owned = pending / (filename + suffix)
                        if self._ordinary(owned):
                            owned.unlink()
                pending.rmdir()

    def _compact(self, item):
        path = self._path(item["filename"])
        if path is None:
            raise MaintenanceError("database_io")
        with closing(self._connect(path, write=True)) as connection:
            self._check(connection)
            connection.execute("VACUUM")  # No DELETE, expiry or stale-row pruning.
            self._check(connection)
            checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        result = self._inspect(item["id"])
        result.update(compacted=True, checkpoint_busy=bool(checkpoint[0]))
        return result

    def _run(self, action):
        entries, failure = [], ""
        backup_name, backup_bytes = "", 0
        self._deadline = time.monotonic() + OPERATION_SECONDS
        try:
            for key, (filename, _) in DATABASES.items():
                try:
                    entries.append(self._inspect(key))
                except Exception as exc:
                    self._guard()
                    entries.append({"id": key, "filename": filename, "status": "error", "error_code": error_code(exc)})
            if action != "refresh":
                failed = next((item for item in entries if item["status"] == "error"), None)
                if failed:
                    raise MaintenanceError(failed["error_code"])
                if action == "compact" and any(item["status"] == "ok" and not item["schema_ok"] for item in entries):
                    raise MaintenanceError("database_schema")
                backup_name, backup_bytes = self._backup(entries)
                if backup_name:
                    with self._lock:
                        self._status.update(backup_name=backup_name, backup_bytes=backup_bytes)
                        self._status["revision"] += 1
                if action == "compact":
                    for index, item in enumerate(entries):
                        if item["status"] == "missing":
                            continue
                        try:
                            entries[index] = self._compact(item)
                        except Exception as exc:
                            self._guard()
                            item.update(status="error", error_code=error_code(exc))
            failure = next((item["error_code"] for item in entries if item["status"] == "error"), "")
        except Exception as exc:
            try:
                self._guard()
            except MaintenanceError as interrupted:
                exc = interrupted
            failure = error_code(exc)
        finally:
            total = sum(sum(item.get(key, 0) for key in ("size_bytes", "wal_bytes", "shm_bytes", "journal_bytes")) for item in entries)
            with self._lock:
                self._status.update(ready=True, busy=False, entries=entries, checked_at=time.time(), total_bytes=total,
                    reclaimable_bytes=sum(item.get("reclaimable_bytes", 0) for item in entries), error_code=failure,
                    phase="cancelled" if failure == "database_cancelled" else "partial" if failure else "complete",
                    result_code="database_no_files" if not failure and all(item["status"] == "missing" for item in entries) else "")
                self._status["revision"] += 1

    def shutdown(self):
        with self._lock:
            self._stop.set()
            thread = self._thread
        if thread and thread.ident is not None and thread is not threading.current_thread():
            thread.join()
