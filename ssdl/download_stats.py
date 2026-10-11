"""Cached on-disk media totals, independent of the removable download history."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff",
    ".heic", ".heif", ".jxl", ".svg", ".ico", ".mp4", ".mkv", ".webm", ".mov",
    ".m4v", ".avi", ".flv", ".wmv", ".mpeg", ".mpg", ".ts", ".m2ts", ".3gp",
    ".ogv", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav", ".weba",
}


class DownloadStats:
    RESCAN_SECONDS = 600

    def __init__(self):
        self._lock = threading.Lock()
        self._directory = None
        self._generation = 0
        self._refreshing = False
        self._refreshed = 0.0
        self._stats = self._empty()
        self._files = {}
        self._scan_updates = {}
        self._checked_at = 0

    @staticmethod
    def _empty():
        return {"ready": False, "total_bytes": 0, "file_count": 0, "partial": False}

    def invalidate(self):
        with self._lock:
            self._generation += 1
            self._refreshed = 0

    def rescan(self, directory: Path):
        self.invalidate()
        return self.snapshot(directory)

    def snapshot(self, directory: Path) -> dict:
        directory = directory.resolve()
        with self._lock:
            if directory != self._directory:
                self._directory = directory
                self._generation += 1
                self._refreshed = 0
                self._stats = self._empty()
                self._files = {}
                self._scan_updates = {}
                self._checked_at = 0
            if not self._refreshing and (not self._refreshed or time.monotonic() - self._refreshed >= self.RESCAN_SECONDS):
                self._refreshing = True
                self._scan_updates = {}
                threading.Thread(target=self._scan, args=(directory, self._generation),
                                 name="download-folder-stats", daemon=True).start()
            return {**self._stats, "refreshing": self._refreshing, "checked_at": self._checked_at,
                    "rescan_seconds": self.RESCAN_SECONDS}

    def record_files(self, directory: Path, files):
        """Apply replacements once per job; concurrent scan results receive an overlay."""
        try:
            directory = directory.resolve()
        except (OSError, ValueError, RuntimeError):
            return
        with self._lock:
            if directory != self._directory:
                return
            generation = self._generation
        updates = {}
        for raw in files:
            if not isinstance(raw, str):
                continue
            try:
                path = (directory / raw).resolve()
                if not path.is_relative_to(directory) or path.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                info = path.stat()
                updates[str(path)] = info.st_size if path.is_file() else None
            except (OSError, ValueError, RuntimeError):
                continue
        with self._lock:
            if generation != self._generation or directory != self._directory:
                return
            if self._refreshing:
                self._scan_updates.update(updates)
            for path, size in updates.items():
                previous = self._files.get(path)
                if previous is not None:
                    self._stats["total_bytes"] -= previous
                    self._stats["file_count"] -= 1
                if size is None:
                    self._files.pop(path, None)
                else:
                    self._files[path] = size
                    self._stats["total_bytes"] += size
                    self._stats["file_count"] += 1

    def _scan(self, directory, generation):
        files = {}
        partial = False
        pending = [directory]
        while pending:
            # Discard a scan if the user changes the download directory.
            with self._lock:
                stale = generation != self._generation
                if stale:
                    self._refreshing = False
                    directory = self._directory
            if stale:
                self.snapshot(directory)
                return
            current = pending.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_symlink():
                                continue
                            info = entry.stat(follow_symlinks=False)
                            # Windows junctions/reparse points can leave the selected folder.
                            if getattr(info, "st_file_attributes", 0) & 0x400:
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                pending.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in MEDIA_EXTENSIONS:
                                files[str(Path(entry.path).resolve())] = info.st_size
                        except OSError:
                            partial = True
            except FileNotFoundError:
                continue
            except OSError:
                partial = True
        with self._lock:
            if generation == self._generation:
                for path, size in self._scan_updates.items():
                    if size is None:
                        files.pop(path, None)
                    else:
                        files[path] = size
                self._files = files
                self._stats = {"ready": True, "total_bytes": sum(files.values()), "file_count": len(files), "partial": partial}
                self._refreshed = time.monotonic()
                self._checked_at = time.time()
                self._scan_updates = {}
            self._refreshing = False
            directory = self._directory
            stale = generation != self._generation
        if stale:
            self.snapshot(directory)


STORAGE = DownloadStats()
