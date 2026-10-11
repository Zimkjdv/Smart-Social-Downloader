from __future__ import annotations

import json
import sys
import mimetypes
import os
import math
import random
import socket
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from . import media
from .x_auth import XAuthManager, AuthError, EXTENSION_ID, EXTENSION_ORIGIN
from .request_policy import POLICY, JOB_DELAY_MIN, JOB_DELAY_MAX, REQUEST_INTERVAL, JOB_RATE_LIMIT, JOB_RATE_WINDOW
from .download_stats import STORAGE, MEDIA_EXTENSIONS
from .thumbnails import ThumbnailCache
from .x_profiles import normalize_account, account_from_url
from .config import configured_port
from .version import APP_NAME, __version__
from .browser_media import available as browser_capture_available
from .environment import EnvironmentDiagnostics
from .persistence import StateStore
from .diagnostics import redact_text, redact_fields
from .job_runtime import run_job, NO_PROGRESS_SECONDS
from .network import validate_url as validate_media_url, NetworkBlocked
from .job_views import job_summary, job_page, file_page
from .video_quality import validate_video_quality
from .media_selection import SelectionRequired, validate_choices
from .request_policy import platform_key


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
DEFAULT_DOWNLOADS = ROOT / "downloads"
PORT = configured_port()
ENVIRONMENT = EnvironmentDiagnostics(ROOT, PORT)
MAX_URLS_PER_REQUEST = 30
MAX_JOBS = 200
STATE_FILE = ROOT / "data" / "state.json"
STATE_STORE = StateStore(STATE_FILE)
X_AUTH = XAuthManager(ROOT / "data", port=PORT)
THUMBNAILS = ThumbnailCache(ROOT / "data" / "thumbnails", media.ffmpeg_path)

_lock = threading.RLock()
_condition = threading.Condition(_lock)
_jobs: dict[str, dict] = {}
_queue: deque[str] = deque()
_paused = False
_active_id: str | None = None
_active_started_monotonic: float | None = None
_download_dir = Path(os.environ.get("SSDL_DOWNLOAD_DIR", str(DEFAULT_DOWNLOADS))).expanduser().resolve()
_x_cookie_file = ""
_next_job_at = 0.0
_job_starts: deque[float] = deque()
_PROFILE_COUNT_DEFAULTS = {
    "profile_scan_complete": False, "profile_scanned_posts": 0, "profile_scanned_files": 0,
    "profile_total_posts": None, "profile_total_files": None,
    "profile_existing_files": 0, "profile_downloaded_files": 0,
    "profile_completed_files": 0, "profile_files_to_download": None,
}
_hourly_job_limit = JOB_RATE_LIMIT
_no_progress_timeout = NO_PROGRESS_SECONDS
_dynamic_capture = False
_state_instance = uuid.uuid4().hex
_state_sequence = 0
_worker_thread = None
_shutdown = threading.Event()
_worker_status = {"phase": "idle", "pid": None, "no_progress_seconds": 0,
                  "no_progress_limit": NO_PROGRESS_SECONDS}

from .scheduler import QueueScheduler
_SCHEDULER = QueueScheduler(sys.modules[__name__])
_quota_locked = _SCHEDULER.quota_locked
_progress_hook = _SCHEDULER.progress_hook
_profile_gate = _SCHEDULER.profile_gate
_job_cancelled = _SCHEDULER.job_cancelled
_worker_health = _SCHEDULER.worker_health
_worker = _SCHEDULER.worker
_worker_loop = _SCHEDULER.worker_loop

from .state_repository import StateRepository
_REPOSITORY = StateRepository(sys.modules[__name__])
_save_locked = _REPOSITORY.save_locked
_file_total_bytes = _REPOSITORY.file_total_bytes
_merge_completed_duplicates_locked = _REPOSITORY.merge_completed_duplicates_locked
_load_saved_state = _REPOSITORY.load_saved_state


def _retry_locked(job: dict, *, force=False) -> bool:
    if job.get("mode") == "x_profile" and any(
            other["id"] != job["id"] and other.get("mode") == "x_profile"
            and other.get("account") == job.get("account") and other["status"] in {"queued", "active"}
            for other in _jobs.values()):
        return False
    if job["status"] == "completed" and job.get("mode") != "x_profile":
        job["last_success"] = {key: job.get(key) for key in
            ("url", "output_dir", "size_bytes", "title", "quality", "video_quality", "selected_media")}
        job["last_success"]["files"] = list(job.get("files") or [])
    job.update(status="queued", status_text="等待重新下載", progress=0, speed="", eta="", size="",
               error="", error_detail="", error_code="", warnings=[], updated_at=time.time(),
               retry_count=job.get("retry_count", 0) + 1, force_download=force)
    job.update(started_at=None, finished_at=None, elapsed_seconds=None,
               size_bytes=None, total_bytes=None, downloaded_bytes=0)
    if job.get("mode") == "x_profile":
        # Account retries synchronize; they never overwrite the entire account archive.
        job.update(force_download=False, stop_requested=False, profile_stage="queued",
                   profile_posts=0, profile_skipped=0, profile_downloaded_posts=0,
                   profile_wait_seconds=0)
        job.update(_PROFILE_COUNT_DEFAULTS)
    # Keep existing successful files until the engine reports the current result.
    if job["id"] not in _queue:
        _queue.append(job["id"])
    return True


def _retry_failed_x() -> None:
    with _condition:
        failed = [job for job in _jobs.values() if job["status"] == "failed" and job["platform"] == "X"
                  and job.get("error_code") not in {"profile_stopped", "download_cancelled"}
                  and not job.get("stop_requested")]
        for job in sorted(failed, key=lambda item: item["created_at"]):
            _retry_locked(job)
        _save_locked()
        _condition.notify_all()


X_AUTH.on_connected = _retry_failed_x


def _platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    root = ".".join(labels[-2:]) if len(labels) > 1 else host
    names = {
        "youtube.com": "YouTube", "youtu.be": "YouTube",
        "tiktok.com": "TikTok", "douyin.com": "抖音",
        "instagram.com": "Instagram", "threads.net": "Threads",
        "facebook.com": "Facebook", "fb.watch": "Facebook",
        "x.com": "X", "twitter.com": "X", "pinterest.com": "Pinterest",
        "pin.it": "Pinterest", "reddit.com": "Reddit", "vimeo.com": "Vimeo",
        "twitch.tv": "Twitch", "bilibili.com": "Bilibili", "b23.tv": "Bilibili",
    }
    for domain, name in names.items():
        if host == domain or host.endswith("." + domain):
            return name
    return root or "網頁媒體"


def _valid_url(raw: str) -> tuple[bool, str]:
    value = raw.strip()
    if len(value) > 5000:
        return False, "網址過長"
    try:
        parsed = urlparse(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or not parsed.netloc:
            return False, "請輸入以 http:// 或 https:// 開頭的網址"
        if parsed.username is not None or parsed.password is not None:
            return False, "網址不可包含帳號或密碼"
        host_lower = host.lower().rstrip(".")
        if host_lower in {"localhost", "localhost.localdomain"} or host_lower.endswith(".localhost"):
            return False, "不接受本機網址"
        # Reject literal non-public IP addresses. Hostnames remain supported for platform links.
        import ipaddress
        try:
            address = ipaddress.ip_address(host_lower)
            if not address.is_global:
                return False, "不接受內部或非公開 IP 位址"
        except ValueError:
            pass
        try:
            validate_media_url(value)
        except NetworkBlocked as exc:
            return False, str(exc)
        return True, value
    except (ValueError, UnicodeError):
        return False, "網址格式不正確"


def _state(view=None, *, summary_only=False) -> dict:
    global _state_sequence
    with _lock:
        _state_sequence += 1
        selected, pagination = ([], None) if summary_only else job_page(_jobs.values(), **(view or {}))
        sources = [dict(item) for item in selected] if not summary_only else []
        jobs = [job_summary(item) for item in sources]
        counts = {"queued": 0, "active": 0, "completed": 0, "failed": 0, "selecting": 0}
        for item in _jobs.values():
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        active = _jobs.get(_active_id, {})
        active_job = job_summary(active) if active else None
        for job in [*jobs, *([active_job] if active_job else [])]:
            if job["id"] == _active_id and _active_started_monotonic is not None:
                job["elapsed_seconds"] = round(max(0, time.monotonic() - _active_started_monotonic), 2)
        engines = media.engine_status()
        pacing = POLICY.snapshot()
        quota = _quota_locked()
        queued_cooldowns = [POLICY.snapshot(platform_key(_jobs[key]["url"]))["cooldown_seconds"]
                            for key in _queue if key in _jobs]
        queue_cooling = min(queued_cooldowns, default=0)
        relevant_cooling = POLICY.snapshot(platform_key(active["url"]))["cooldown_seconds"] if active else queue_cooling
        pacing["cooldown_seconds"] = relevant_cooling
        pacing["cooldown_until"] = time.time() + relevant_cooling if relevant_cooling else 0
        wait_seconds = max(0, math.ceil(_next_job_at - time.time()), queue_cooling, quota["wait_seconds"])
        profile_phase = active.get("profile_stage") if active.get("mode") == "x_profile" else None
        phase = (profile_phase if profile_phase in {"paused", "waiting", "quota", "cooldown"} else
                 "active" if _active_id else "paused" if _paused else
                 "cooldown" if counts["queued"] and queue_cooling else
                 "quota" if counts["queued"] and quota["limited"] else
                 "waiting" if counts["queued"] and wait_seconds else
                 "ready" if counts["queued"] else "selection" if counts["selecting"] else "idle")
        payload = {
            "state_instance": _state_instance,
            "state_sequence": _state_sequence,
            "jobs": jobs,
            "total_jobs": len(_jobs),
            "platforms": sorted({item["platform"] for item in _jobs.values()}),
            "active_job": active_job,
            "counts": counts,
            "paused": _paused,
            "active_id": _active_id,
            "download_dir": str(_download_dir),
            "x_cookie_file": _x_cookie_file,
            "x_auth": X_AUTH.status(),
            "ready": all(engines[key] for key in ("video", "images", "ffmpeg")),
            "app_version": __version__,
            "version": engines["video_version"],  # Legacy API field: yt-dlp version.
            "engines": engines,
            "environment": ENVIRONMENT.snapshot(),
            "persistence": STATE_STORE.status(),
            "worker": {**_worker_status, "alive": bool(_worker_thread and _worker_thread.is_alive())},
            "no_progress_timeout": _no_progress_timeout,
            "dynamic_capture": _dynamic_capture,
            "browser_capture_available": browser_capture_available(),
            "quality_mode": "original",
            "rate_limit": quota,
            "hourly_job_limit": _hourly_job_limit,
            "storage": STORAGE.snapshot(_download_dir),
            "thumbnail_cache": THUMBNAILS.status(),
            "safe_queue": {**pacing, "enabled": True, "workers": 1, "phase": phase,
                           "delay_min": JOB_DELAY_MIN, "delay_max": JOB_DELAY_MAX,
                           "request_interval": REQUEST_INTERVAL, "wait_seconds": wait_seconds,
                           "next_job_at": _next_job_at},
        }
        directory = _download_dir
        if not summary_only:
            payload["jobs_page"] = pagination
    # Source file metadata and preview generation do not hold the download queue lock.
    for job, source in zip(jobs, sources):
        preview = THUMBNAILS.snapshot(source, directory)
        job["thumbnail_status"] = preview["status"]
        job["thumbnail_kind"] = preview.get("kind", "")
        job["thumbnail_url"] = (f'/api/jobs/{job["id"]}/thumbnail?key={preview["key"]}'
                                if preview["status"] == "ready" else "")
    return payload


def _diagnostics() -> dict:
    """An intentionally small export: no history URLs, paths, or credentials."""
    with _lock:
        counts = {name: sum(job["status"] == name for job in _jobs.values())
                  for name in ("queued", "active", "completed", "failed")}
        result = {"format_version": 1, "app_version": __version__, "created_at": time.time(), "counts": counts,
                  "environment": ENVIRONMENT.snapshot(), "persistence": STATE_STORE.status(),
                  "worker": dict(_worker_status), "rate_limit": _quota_locked(),
                  "x_auth": {key: X_AUTH.status().get(key) for key in ("connected", "phase")},
                  "jobs": [{"id": job["id"], "platform": job["platform"], "status": job["status"],
                            "error_code": job.get("error_code", ""), "error": job.get("error", ""),
                            "error_detail": job.get("error_detail", ""), "warnings": job.get("warnings", [])}
                           for job in _jobs.values()]}
    def scrub(value):
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items()}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return redact_text(value) if isinstance(value, str) else value
    return scrub(result)


def _format_bytes(value) -> str:
    if not isinstance(value, (int, float)) or value < 0:
        return ""
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return ""


from .http_api import ApiHandler
from .http_server import BoundedHTTPServer as Server

class Handler(ApiHandler):
    app = sys.modules[__name__]


def main() -> int:
    global _worker_thread
    _shutdown.clear()
    try:
        with Server(("127.0.0.1", PORT), Handler) as server:
            # Do not migrate/write state when another service owns the port.
            _load_saved_state()
            ENVIRONMENT.refresh()
            print(f"{APP_NAME} v{__version__}: http://127.0.0.1:{PORT}")
            print(f"儲存位置: {_download_dir}")
            if not _state()["ready"]:
                print("尚未安裝完整下載引擎；請執行 setup.bat。")
            _worker_thread = threading.Thread(target=_worker, name="download-queue", daemon=True)
            _worker_thread.start()
            server.serve_forever()
    except KeyboardInterrupt:
        print("\n下載工具已停止。")
    except OSError as exc:
        print(f"無法啟動服務：連接埠 {PORT} 可能已有下載工具執行。請先關閉原服務。({type(exc).__name__})")
        return 1
    finally:
        _shutdown.set()
        with _condition:
            _condition.notify_all()
        if _worker_thread:
            _worker_thread.join(timeout=5)
        X_AUTH.shutdown()
        THUMBNAILS.shutdown()
    return 0
