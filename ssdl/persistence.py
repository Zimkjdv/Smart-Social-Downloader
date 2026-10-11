"""Versioned state, atomic writes, and a validated last-good backup."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from .video_quality import validate_video_quality
from .media_selection import validate_choices

SCHEMA_VERSION = 2


class FutureState(ValueError):
    pass


def _history_url(value):
    """Validate syntax offline; DNS and reachability are download concerns."""
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise ValueError("Invalid history URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Invalid history URL")
    parsed.port  # Reject malformed ports as well as malformed host brackets.


def _path_text(value):
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Invalid history path")


def _pacing_state(saved):
    if not isinstance(saved, dict):
        raise ValueError("Invalid pacing state")
    for key in ("cooldown_until", "global_cooldown_until", "next_job_at"):
        if key in saved and (type(saved[key]) not in {int, float} or not math.isfinite(saved[key]) or saved[key] < 0):
            raise ValueError("Invalid pacing deadline")
    if "strikes" in saved and (type(saved["strikes"]) is not int or saved["strikes"] < 0):
        raise ValueError("Invalid pacing count")
    if "cooldown_mode" in saved and saved["cooldown_mode"] not in ("global", "platform"):
        raise ValueError("Invalid pacing mode")
    platforms = saved.get("platform_cooldowns", {})
    if not isinstance(platforms, dict) or len(platforms) > 200:
        raise ValueError("Invalid platform pacing")
    for name, entry in platforms.items():
        if not isinstance(name, str) or not name or len(name) > 253 or not isinstance(entry, dict):
            raise ValueError("Invalid platform pacing")
        # Platform entries have deadlines/counts, never another platform map.
        if "platform_cooldowns" in entry:
            raise ValueError("Invalid nested platform pacing")
        _pacing_state(entry)


def validate_state(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Invalid state object")
    version = payload.get("schema_version", 0)
    if type(version) is not int or version < 0:
        raise ValueError("Invalid schema version")
    if version > SCHEMA_VERSION:
        raise FutureState("State was saved by a newer application")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or len(jobs) > 200:
        raise ValueError("Invalid jobs")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("Invalid job")
        if any(not isinstance(job.get(key), str) or not job[key] for key in ("id", "url", "status")):
            raise ValueError("Invalid job identity")
        _history_url(job["url"])
        if job["id"] in seen or job["status"] not in {"queued", "active", "completed", "failed", "selecting"}:
            raise ValueError("Invalid job status")
        seen.add(job["id"])
        created = job.get("created_at")
        if type(created) not in {int, float} or not math.isfinite(created) or created < 0:
            raise ValueError("Invalid job date")
        for key in ("files", "warnings"):
            if key in job and (not isinstance(job[key], list) or any(not isinstance(item, str) for item in job[key])):
                raise ValueError("Invalid job files/messages")
        for name in job.get("files", []):
            _path_text(name)
        for key in ("title", "platform", "output_dir"):
            if key in job and not isinstance(job[key], str):
                raise ValueError("Invalid job metadata")
        if "output_dir" in job:
            _path_text(job["output_dir"])
        if "video_quality" in job:
            validate_video_quality(job["video_quality"])
        selected = job.get("selected_media", "")
        if not isinstance(selected, str) or selected and (len(selected) != 24 or any(char not in "0123456789abcdef" for char in selected)):
            raise ValueError("Invalid media selection")
        if job["status"] == "selecting":
            validate_choices(job.get("selection_options"))
        for key in ("attempts", "retry_count", "size_bytes", "profile_total_files", "profile_completed_files"):
            if key in {"attempts", "retry_count", "profile_completed_files"} and key in job and job[key] is None:
                raise ValueError("Invalid job count")
            if key in job and job[key] is not None and (type(job[key]) is not int or job[key] < 0):
                raise ValueError("Invalid job count")
        for key in ("updated_at", "started_at", "finished_at", "elapsed_seconds", "progress"):
            if key in job and job[key] is not None and (type(job[key]) not in {int, float} or not math.isfinite(job[key]) or job[key] < 0):
                raise ValueError("Invalid job progress")
        for key in ("force_download", "stop_requested", "remove_when_finished"):
            if key in job and type(job[key]) is not bool:
                raise ValueError("Invalid job flag")
    queue = payload.get("queue", [])
    if not isinstance(queue, list) or any(not isinstance(item, str) for item in queue):
        raise ValueError("Invalid queue")
    for key in ("download_dir", "x_cookie_file"):
        if key in payload:
            _path_text(payload[key])
    if "paused" in payload and type(payload["paused"]) is not bool:
        raise ValueError("Invalid pause state")
    if "dynamic_capture" in payload and type(payload["dynamic_capture"]) is not bool:
        raise ValueError("Invalid dynamic capture setting")
    if not isinstance(payload.get("job_starts", []), list) or not isinstance(payload.get("safe_queue", {}), dict):
        raise ValueError("Invalid pacing state")
    _pacing_state(payload.get("safe_queue", {}))
    result = copy.deepcopy(payload)
    result["schema_version"] = SCHEMA_VERSION
    return result


class StateStore:
    def __init__(self, filename: Path):
        self.filename = filename
        self.backup = filename.with_suffix(filename.suffix + ".bak")
        self._lock = threading.RLock()
        self._invalid_primary = False
        self._status = {"healthy": True, "schema_version": SCHEMA_VERSION,
                        "last_saved_at": 0, "error": "", "recovered": False,
                        "backup_available": self.backup.is_file(), "blocked": False}

    def status(self):
        with self._lock:
            return dict(self._status)

    def _read(self, path):
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("State too large")
        return validate_state(json.loads(path.read_text(encoding="utf-8-sig")))

    def _block_future(self):
        self._status.update(healthy=False, blocked=True,
            error="紀錄來自較新版本，請使用相容版本；目前不覆寫原紀錄。")

    def load(self, normalize=None):
        with self._lock:
            if not self.filename.exists() and not self.backup.exists():
                return None
            try:
                payload = self._read(self.filename)
                result = normalize(payload) if normalize else payload
                self._invalid_primary = False
                self._status.update(healthy=True, blocked=False)
                return result
            except FutureState:
                self._block_future()
                return None
            except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                self._invalid_primary = True
                try:
                    payload = self._read(self.backup)
                    result = normalize(payload) if normalize else payload
                except FutureState:
                    self._block_future()
                    return None
                except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                    self._status.update(healthy=False,
                        error="下載紀錄無法讀取，且沒有有效備份；原檔保留，請查看排錯說明。")
                    if normalize:
                        self._status["blocked"] = True
                    return None
                self._status.update(healthy=True, blocked=False, recovered=True, backup_available=True,
                    error="已從最後有效備份恢復；損壞紀錄會另行保留。")
                return result

    def restore_failed(self):
        """Never auto-save an app snapshot that could not be fully reconstructed."""
        with self._lock:
            self._status.update(healthy=False, blocked=True,
                error="下載紀錄無法完整恢復；原檔與備份保留，請修復紀錄後重新啟動。")

    @staticmethod
    def _atomic(path, contents):
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, payload):
        with self._lock:
            if self._status["blocked"]:
                return False
            try:
                payload = validate_state(payload)
                contents = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
                if len(contents) > 64 * 1024 * 1024:
                    raise ValueError("State too large")
                # A backup may be the only newer-version history left. Check it
                # before replacing either file, including saves without load().
                try:
                    self._read(self.backup)
                except FutureState:
                    self._block_future()
                    return False
                except (OSError, ValueError, TypeError, KeyError):
                    pass
                self.filename.parent.mkdir(parents=True, exist_ok=True)
                if self.filename.is_file():
                    try:
                        self._read(self.filename)
                        if self._invalid_primary:
                            raise ValueError("Primary failed application normalization")
                    except FutureState:
                        self._block_future()
                        return False
                    except (ValueError, TypeError, KeyError):
                        # Preserve the damaged input before replacing it; never
                        # copy it over the validated last-good backup.
                        damaged = self.filename.with_name(f"state.corrupt-{time.time_ns()}.json")
                        self._atomic(damaged, self.filename.read_bytes())
                    else:
                        self._atomic(self.backup, self.filename.read_bytes())
                self._atomic(self.filename, contents)
                self._invalid_primary = False
                self._status.update(healthy=True, last_saved_at=time.time(),
                                    backup_available=self.backup.is_file())
                if not self._status["recovered"]:
                    self._status["error"] = ""
                return True
            except (OSError, ValueError, TypeError, KeyError):
                self._status.update(healthy=False, error="本機紀錄保存失敗，變更目前只在記憶體中；請檢查磁碟權限與空間後重新嘗試保存。")
                return False
