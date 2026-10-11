"""Generate small local previews without modifying or fetching source media."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff",
    ".heic", ".heif", ".jxl", ".ico",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv",
    ".mpeg", ".mpg", ".ts", ".m2ts", ".3gp", ".ogv",
}
SINGLE_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".jxl", ".ico"}
MAX_PREVIEW_BYTES = 2_000_000
CACHE_BYTES = 128 * 1024 * 1024
CACHE_FILES = 1000
CACHE_AGE_SECONDS = 30 * 86400
CACHE_MAINTENANCE_SECONDS = 300


class ThumbnailCache:
    def __init__(self, directory: Path, ffmpeg: Callable[[], str | None]):
        # Preserve the configured path so a pre-existing junction is rejected too.
        self.directory = directory.absolute()
        self._ffmpeg = ffmpeg
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}
        self._pending = queue.Queue()
        self._thread = None
        self._stop = threading.Event()
        self._process: subprocess.Popen | None = None
        self._sources = {}
        self._disk = {}
        self._touched = {}
        self._disk_ready = False
        self._last_maintenance = 0
        self._clear_requested = False
        self._maintaining = False
        self._maintenance_error = False

    def _start_locked(self):
        if self._thread is None and not self._stop.is_set():
            self._thread = threading.Thread(target=self._worker, name="media-previews", daemon=True)
            self._thread.start()

    def status(self):
        with self._lock:
            self._start_locked()
            return {"ready": self._disk_ready, "total_bytes": sum(item[0] for item in self._disk.values()),
                    "file_count": len(self._disk), "max_bytes": CACHE_BYTES, "max_files": CACHE_FILES,
                    "max_age_days": CACHE_AGE_SECONDS // 86400,
                    "clearing": self._clear_requested or self._maintaining,
                    "partial": self._maintenance_error}

    def clear(self):
        with self._lock:
            if self._clear_requested or self._stop.is_set():
                return
            self._clear_requested = True
            self._start_locked()
            self._pending.put((None, None))

    def _safe_directory(self):
        try:
            return (self.directory.resolve() == self.directory and not self.directory.is_symlink()
                    and not (getattr(self.directory.stat(), "st_file_attributes", 0) & 0x400))
        except OSError:
            return not self.directory.exists()

    def _maintain(self):
        """Prune only cache-owned JPEG names in this directory, never source media."""
        now = time.time()
        with self._lock:
            clear = self._clear_requested
            scan = not self._disk_ready or now - self._last_maintenance >= CACHE_MAINTENANCE_SECONDS or clear
            over_limit = len(self._disk) > CACHE_FILES or sum(item[0] for item in self._disk.values()) > CACHE_BYTES
            if not scan and not over_limit:
                return
            self._clear_requested = False
            self._maintaining = True
            records = dict(self._disk)
            protected = {key for key, entry in self._entries.items() if entry["status"] == "pending"}
        failed = False
        try:
            if not self._safe_directory():
                raise OSError("unsafe cache directory")
            if scan:
                records = {}
                if self.directory.exists():
                    with os.scandir(self.directory) as entries:
                        for entry in entries:
                            if not re.fullmatch(r"[a-f0-9]{64}\.jpg", entry.name):
                                continue
                            info = entry.stat(follow_symlinks=False)
                            if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400 or not entry.is_file(follow_symlinks=False):
                                continue
                            records[entry.name[:-4]] = (info.st_size, info.st_mtime)
                with self._lock:
                    for key, (size, accessed) in list(records.items()):
                        if key in self._disk:
                            records[key] = (size, max(accessed, self._disk[key][1]))
            if clear:
                with self._lock:
                    self._entries = {key: entry for key, entry in self._entries.items() if entry["status"] == "pending"}
            total = sum(item[0] for item in records.values())
            for key, (size, accessed) in sorted(records.items(), key=lambda item: item[1][1]):
                if key in protected:
                    continue
                if not (clear or now - accessed >= CACHE_AGE_SECONDS or len(records) > CACHE_FILES or total > CACHE_BYTES):
                    continue
                path = self._cache_file(key)
                try:
                    if path.is_symlink() or path.resolve().parent != self.directory:
                        continue
                    path.unlink(missing_ok=True)
                    total -= size
                    records.pop(key)
                    with self._lock:
                        self._entries.pop(key, None)
                        self._touched.pop(key, None)
                except OSError:
                    failed = True
        except OSError:
            failed = True
        finally:
            with self._lock:
                self._disk = records
                self._disk_ready = not failed
                self._maintenance_error = failed
                self._last_maintenance = now
                self._maintaining = False

    @staticmethod
    def _source(job: dict, default_directory: Path):
        # Active files may still be changing. Preview only saved terminal results.
        if job.get("status") not in {"completed", "failed"}:
            return None
        files = job.get("files")
        if not isinstance(files, (list, tuple)):
            return None
        try:
            root = Path(job.get("output_dir") or default_directory).resolve()
            for raw in files:
                if not isinstance(raw, str):
                    continue
                candidate = (root / raw).resolve()
                suffix = candidate.suffix.lower()
                if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS or not candidate.is_relative_to(root):
                    continue
                try:
                    info = candidate.stat()
                    if candidate.is_file() and info.st_size > 0:
                        return candidate, info.st_size, info.st_mtime_ns, suffix in VIDEO_EXTENSIONS
                except OSError:
                    continue
        except (OSError, TypeError, ValueError, RuntimeError):
            pass
        return None

    def _cache_file(self, key: str) -> Path:
        return self.directory / f"{key}.jpg"

    def _ready(self, path: Path) -> bool:
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(self.directory):
                return False
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_PREVIEW_BYTES:
                return False
            with path.open("rb") as handle:
                return handle.read(2) == b"\xff\xd8"
        except (OSError, ValueError, RuntimeError):
            return False

    def snapshot(self, job: dict, default_directory: Path) -> dict:
        identity = (job.get("id"), job.get("status"), job.get("updated_at"), job.get("output_dir"),
                    str(default_directory), len(job.get("files") or []))
        with self._lock:
            cached_source = self._sources.get(job.get("id"))
        source_valid = cached_source and cached_source[0] == identity and time.monotonic() - cached_source[1] < 30
        source = cached_source[2] if source_valid else self._source(job, default_directory)
        with self._lock:
            if len(self._sources) >= 256 and job.get("id") not in self._sources:
                self._sources.pop(next(iter(self._sources)))
            self._sources[job.get("id")] = (identity, cached_source[1] if source_valid else time.monotonic(), source)
        if not source:
            return {"status": "unavailable"}
        path, size, modified, video = source
        signature = json.dumps(["preview-v1", str(path), size, modified], ensure_ascii=False).encode("utf-8")
        key = hashlib.sha256(signature).hexdigest()
        cached = self._cache_file(key)
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry["status"] == "ready" and not self._ready(cached):
                self._entries.pop(key)
                entry = None
            if entry is None:
                # Bound memory while keeping generated JPEGs reusable across restarts.
                if len(self._entries) >= 512:
                    old = next((name for name, item in self._entries.items() if item["status"] != "pending"), None)
                    if old:
                        self._entries.pop(old)
                entry = {"status": "ready" if self._ready(cached) else "pending", "key": key,
                         "kind": "video" if video else "image"}
                self._entries[key] = entry
                if entry["status"] == "pending" and not self._stop.is_set():
                    self._pending.put((key, source))
                    self._start_locked()
            return dict(entry)

    def read(self, key: str) -> bytes | None:
        # Only keys issued by snapshot() are accepted; callers never supply a path.
        with self._lock:
            entry = self._entries.get(key)
            if not entry or entry["status"] != "ready":
                return None
        path = self._cache_file(key)
        try:
            if self._ready(path):
                with path.open("rb") as handle:
                    data = handle.read(MAX_PREVIEW_BYTES + 1)
                if len(data) <= MAX_PREVIEW_BYTES:
                    now = time.time()
                    with self._lock:
                        previous = self._touched.get(key, 0)
                        if now - previous >= 60:
                            self._touched[key] = now
                        self._disk[key] = (len(data), now)
                    if now - previous >= 60:
                        try:
                            os.utime(path, (now, now))
                        except OSError:
                            pass
                    return data
        except OSError:
            pass
        return None

    def _generate(self, key: str, source) -> bool:
        path, size, modified, video = source
        executable = self._ffmpeg()
        if not executable:
            return False
        if not self._safe_directory():
            return False
        self.directory.mkdir(parents=True, exist_ok=True)
        cached = self._cache_file(key)
        temporary = self.directory / f"{key}.tmp.jpg"
        try:
            # Avoid opening a visible FFmpeg console on Windows.
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            for seek in ("1", "0") if video else ("0",):
                if self._stop.is_set():
                    return False
                command = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                           "-max_alloc", "134217728", "-threads", "1", "-filter_threads", "1",
                           "-protocol_whitelist", "file,pipe"]
                if video:
                    command += ["-ss", seek]
                elif path.suffix.lower() in SINGLE_IMAGE_FORMATS:
                    # A '%' in a downloaded filename is a literal, not an image sequence.
                    command += ["-f", "image2", "-pattern_type", "none"]
                command += ["-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn", "-frames:v", "1",
                            "-vf", "scale=256:256:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
                            "-c:v", "mjpeg", "-q:v", "4", "-threads", "1", "-f", "image2", "-update", "1", str(temporary)]
                with self._lock:
                    if self._stop.is_set():
                        return False
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL, creationflags=flags)
                    self._process = process
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                finally:
                    with self._lock:
                        if self._process is process:
                            self._process = None
                if process.returncode == 0 and self._ready(temporary):
                    # A retry or external edit must not publish a stale preview.
                    latest = path.stat()
                    if latest.st_size != size or latest.st_mtime_ns != modified:
                        return False
                    temporary.replace(cached)
                    return True
                temporary.unlink(missing_ok=True)
            return False
        finally:
            temporary.unlink(missing_ok=True)

    def _worker(self):
        while not self._stop.is_set():
            self._maintain()
            try:
                item = self._pending.get(timeout=60)
            except queue.Empty:
                continue
            if item is None:
                return
            key, source = item
            if key is None:
                continue
            try:
                ready = self._generate(key, source)
            except Exception:
                # Preview failures never change the download result or retry the source URL.
                ready = False
            with self._lock:
                if key in self._entries:
                    self._entries[key]["status"] = "ready" if ready else "failed"
                if ready:
                    try:
                        self._disk[key] = (self._cache_file(key).stat().st_size, time.time())
                    except OSError:
                        pass

    def shutdown(self):
        self._stop.set()
        self._pending.put(None)
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.kill()
                except OSError:
                    pass
