"""Explicit application state, dependencies and lifecycle; construction performs no restore."""
from __future__ import annotations

import math
import os
import random
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from . import media
from .browser_media import available as browser_capture_available
from .config import configured_port, configured_cache_directory, configured_media_root, resolve_download_directory
from .diagnostics import redact_text, redact_fields
from .download_stats import DownloadStats, MEDIA_EXTENSIONS
from .database_maintenance import DatabaseMaintenance
from .environment import EnvironmentDiagnostics
from .http_api import ApiHandler
from .job_runtime import run_job, NO_PROGRESS_SECONDS
from .job_views import job_summary, job_page, file_page
from .media_selection import SelectionRequired
from .network import validate_url as validate_media_url, NetworkBlocked
from .persistence import StateStore
from .request_policy import RequestPolicy, JOB_DELAY_MIN, JOB_DELAY_MAX, REQUEST_INTERVAL, JOB_RATE_LIMIT, JOB_RATE_WINDOW, platform_key
from .scheduler import QueueScheduler
from .state_repository import StateRepository
from .state_writer import StateWriter, thaw_snapshot, SAVE_ERROR
from .thumbnails import ThumbnailCache
from .version import __version__
from .video_quality import validate_video_quality
from .x_auth import XAuthManager, AuthError, EXTENSION_ID, EXTENSION_ORIGIN
from .profiles import normalize_account, normalize_pixiv_account, account_from_url, profile_mode, PROFILE_MODES
from .pixiv_auth import PixivAuthManager
from .session_storage import host_browser_required


@dataclass
class AppState:
    """Mutable queue state; AppContext.condition protects every mutation."""
    download_dir: Path
    jobs: dict[str, dict] = field(default_factory=dict)
    queue: deque[str] = field(default_factory=deque)
    paused: bool = False
    active_id: str | None = None
    active_started_monotonic: float | None = None
    x_cookie_file: str = ""
    next_job_at: float = 0.0
    job_starts: deque[float] = field(default_factory=deque)
    hourly_job_limit: int = JOB_RATE_LIMIT
    no_progress_timeout: int = NO_PROGRESS_SECONDS
    dynamic_capture: bool = False
    state_instance: str = field(default_factory=lambda: uuid.uuid4().hex)
    state_sequence: int = 0
    worker_thread: threading.Thread | None = None
    shutdown: threading.Event = field(default_factory=threading.Event)
    worker_status: dict = field(default_factory=lambda: {"phase": "idle", "pid": None,
        "no_progress_seconds": 0, "no_progress_limit": NO_PROGRESS_SECONDS})


class AppContext:
    """One application's queue, services and callbacks, independent of other instances.

    Instantiate explicitly, bind the HTTP port, then start(). close() is idempotent;
    a closed context cannot be restarted. Create a new instance instead.
    """
    MAX_URLS_PER_REQUEST = 30
    MAX_JOBS = 200
    JOB_DELAY_MIN, JOB_DELAY_MAX = JOB_DELAY_MIN, JOB_DELAY_MAX
    JOB_RATE_LIMIT, JOB_RATE_WINDOW = JOB_RATE_LIMIT, JOB_RATE_WINDOW
    NO_PROGRESS_SECONDS = NO_PROGRESS_SECONDS
    MEDIA_EXTENSIONS = MEDIA_EXTENSIONS
    EXTENSION_ID, EXTENSION_ORIGIN = EXTENSION_ID, EXTENSION_ORIGIN
    AuthError, SelectionRequired = AuthError, SelectionRequired
    media, random = media, random
    run_job = staticmethod(run_job)
    platform_key = staticmethod(platform_key)
    PROFILE_MODES = PROFILE_MODES
    account_from_url = staticmethod(account_from_url)
    normalize_pixiv_account = staticmethod(normalize_pixiv_account)
    profile_mode = staticmethod(profile_mode)
    normalize_account = staticmethod(normalize_account)
    browser_capture_available = staticmethod(browser_capture_available)
    file_page, job_summary = staticmethod(file_page), staticmethod(job_summary)
    redact_text, redact_fields = staticmethod(redact_text), staticmethod(redact_fields)
    validate_video_quality = staticmethod(validate_video_quality)
    _PROFILE_COUNT_DEFAULTS = {
        "profile_scan_complete": False, "profile_scanned_posts": 0, "profile_scanned_files": 0,
        "profile_total_posts": None, "profile_total_files": None,
        "profile_existing_files": 0, "profile_downloaded_files": 0,
        "profile_completed_files": 0, "profile_files_to_download": None,
    }

    def __init__(self, root: Path, *, port: int | None = None, download_dir: Path | None = None,
                 policy: RequestPolicy | None = None, storage: DownloadStats | None = None,
                 auth: XAuthManager | None = None, state_store: StateStore | None = None,
                 environment: EnvironmentDiagnostics | None = None,
                 thumbnails: ThumbnailCache | None = None):
        self.ROOT = root.resolve()
        self.STATIC = self.ROOT / "static"
        self.DEFAULT_DOWNLOADS = self.ROOT / "downloads"
        self.PORT = configured_port() if port is None else port
        self.MEDIA_ROOT = configured_media_root()
        self.CACHE_DIRECTORY = configured_cache_directory(self.ROOT)
        self.STATE_STORE: StateStore = state_store if state_store is not None else StateStore(self.ROOT / "data" / "state.json")
        self.STATE_FILE = self.STATE_STORE.filename
        self.X_AUTH: XAuthManager = auth if auth is not None else XAuthManager(self.ROOT / "data", port=self.PORT, restore=False)
        self.PIXIV_AUTH = PixivAuthManager(self.ROOT / "data")
        self.ENVIRONMENT: EnvironmentDiagnostics = environment if environment is not None else EnvironmentDiagnostics(self.ROOT, self.PORT)
        self.THUMBNAILS: ThumbnailCache = thumbnails if thumbnails is not None else ThumbnailCache(self.CACHE_DIRECTORY / "thumbnails", media.ffmpeg_path)
        self.STORAGE: DownloadStats = storage if storage is not None else DownloadStats()
        self.POLICY: RequestPolicy = policy if policy is not None else RequestPolicy()
        selected_dir = download_dir if download_dir is not None else Path(os.environ.get("SSDL_DOWNLOAD_DIR", str(self.DEFAULT_DOWNLOADS)))
        self.state: AppState = AppState(self.resolve_download_directory(selected_dir))
        self.lock = threading.RLock()
        self.MEDIA_READS = threading.BoundedSemaphore(4)
        self.condition = threading.Condition(self.lock)
        self.DATABASES = DatabaseMaintenance(self.ROOT / "data")
        self._lifecycle_lock = threading.RLock()
        self._started = False
        self._closed = False
        self.STATE_WRITER: StateWriter = StateWriter(
            lambda snapshot: self.STATE_STORE.save(self.redact_fields(thaw_snapshot(snapshot))),
            lambda: self.STATE_STORE.record_failure(preserve=True))
        self._SCHEDULER = QueueScheduler(self)
        self._REPOSITORY = StateRepository(self)
        self._quota_locked = self._SCHEDULER.quota_locked
        self._progress_hook = self._SCHEDULER.progress_hook
        self._profile_gate = self._SCHEDULER.profile_gate
        self._job_cancelled = self._SCHEDULER.job_cancelled
        self._worker_health = self._SCHEDULER.worker_health
        self._worker = self._SCHEDULER.worker
        self._worker_loop = self._SCHEDULER.worker_loop
        self._save_locked = self._REPOSITORY.save_locked
        self._file_total_bytes = self._REPOSITORY.file_total_bytes
        self._merge_completed_duplicates_locked = self._REPOSITORY.merge_completed_duplicates_locked
        self._load_saved_state = self._REPOSITORY.load_saved_state
        self.X_AUTH.on_connected = self._retry_failed_x
        self.PIXIV_AUTH.on_connected = lambda: self._retry_failed_platform("Pixiv")
        self.Handler = type("Handler", (ApiHandler,), {"app": self})

    def start(self) -> None:
        """Restore only after the caller has successfully bound the HTTP port."""
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("Application context is closed")
            if self._started:
                return
            self._load_saved_state()
            self.X_AUTH.restore()
            self.PIXIV_AUTH.restore()
            self.ENVIRONMENT.refresh()
            self.STATE_WRITER.start()
            self.state.worker_thread = threading.Thread(target=self._worker, name="download-queue", daemon=True)
            try:
                self.state.worker_thread.start()
            except BaseException:
                self.state.worker_thread = None
                raise
            self._started = True

    def close(self) -> None:
        """Stop work, preserve queue state, then close instance-owned helpers."""
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            self.state.shutdown.set()
            with self.condition:
                self.condition.notify_all()
            try:
                self.X_AUTH.shutdown()
                self.PIXIV_AUTH.shutdown()
                self.DATABASES.shutdown()
                worker = self.state.worker_thread
                if worker and worker.is_alive() and worker is not threading.current_thread():
                    worker.join()
                self.THUMBNAILS.shutdown()
                self.STORAGE.shutdown()
                self.ENVIRONMENT.shutdown()
                if self._started and not (worker and worker.is_alive()):
                    with self.condition:
                        generation = self._save_locked()
                    self._wait_saved(generation)
            finally:
                self.STATE_WRITER.close()

    def _wait_saved(self, generation: int) -> bool:
        if self.lock._is_owned():
            raise RuntimeError("Durability barriers must not hold the queue lock")
        return self.STATE_WRITER.wait(generation)

    def _persistence_status(self):
        status = self.STATE_STORE.status()
        writer = self.STATE_WRITER.status()
        if writer["failed_generation"] > writer["saved_generation"]:
            status.update(healthy=False, error=status.get("error") or SAVE_ERROR)
        return {**status, **writer}

    def resolve_download_directory(self, value) -> Path:
        return resolve_download_directory(value, media_root=self.MEDIA_ROOT)

    def health(self) -> dict:
        """Small cached readiness snapshot; never enumerate jobs, paths or cookies."""
        persistence = self._persistence_status()
        environment = self.ENVIRONMENT.snapshot()
        worker = self.state.worker_thread
        checks = {
            "application": self._started and not self._closed and not self.state.shutdown.is_set(),
            "worker": worker is not None and worker.is_alive(),
            "persistence": persistence["healthy"] and not persistence.get("blocked", False),
            "dependencies": environment.get("phase") == "complete" and environment.get("ready") is True,
        }
        return {"service": "ssdl", "status": "healthy" if all(checks.values()) else "unhealthy", "checks": checks}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


    def _retry_locked(self, job: dict, *, force=False) -> bool:
        if job.get("mode") in self.PROFILE_MODES and any(
                other["id"] != job["id"] and other.get("mode") == job.get("mode")
                and other.get("account") == job.get("account") and other["status"] in {"queued", "active"}
                for other in self.state.jobs.values()):
            return False
        if job["status"] == "completed" and job.get("mode") not in self.PROFILE_MODES:
            job["last_success"] = {key: job.get(key) for key in
                ("url", "output_dir", "size_bytes", "title", "quality", "video_quality", "selected_media")}
            job["last_success"]["files"] = list(job.get("files") or [])
        job.update(status="queued", status_text="等待重新下載", progress=0, speed="", eta="", size="",
                   error="", error_detail="", error_code="", warnings=[], updated_at=time.time(),
                   retry_count=job.get("retry_count", 0) + 1, force_download=force)
        job.update(started_at=None, finished_at=None, elapsed_seconds=None,
                   size_bytes=None, total_bytes=None, downloaded_bytes=0)
        if job.get("mode") in self.PROFILE_MODES:
            # Account retries synchronize; they never overwrite the entire account archive.
            job.update(force_download=False, stop_requested=False, profile_stage="queued",
                       profile_posts=0, profile_skipped=0, profile_downloaded_posts=0,
                       profile_wait_seconds=0)
            job.update(self._PROFILE_COUNT_DEFAULTS)
        # Keep existing successful files until the engine reports the current result.
        if job["id"] not in self.state.queue:
            self.state.queue.append(job["id"])
        return True


    def _retry_failed_x(self) -> None:
        self._retry_failed_platform("X")

    def _retry_failed_platform(self, platform) -> None:
        with self.condition:
            if self.state.shutdown.is_set():
                return
            failed = [job for job in self.state.jobs.values() if job["status"] == "failed" and job["platform"] == platform
                      and job.get("error_code") not in {"profile_stopped", "download_cancelled"}
                      and not job.get("stop_requested")]
            for job in sorted(failed, key=lambda item: item["created_at"]):
                self._retry_locked(job)
            generation = self._save_locked()
            self.condition.notify_all()
        self._wait_saved(generation)


    def _platform(self, url: str) -> str:
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
            "x.com": "X", "twitter.com": "X", "pixiv.net": "Pixiv", "pinterest.com": "Pinterest",
            "pin.it": "Pinterest", "reddit.com": "Reddit", "vimeo.com": "Vimeo",
            "twitch.tv": "Twitch", "bilibili.com": "Bilibili", "b23.tv": "Bilibili",
        }
        for domain, name in names.items():
            if host == domain or host.endswith("." + domain):
                return name
        return root or "網頁媒體"


    def _valid_url(self, raw: str) -> tuple[bool, str]:
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


    def _state(self, view=None, *, summary_only=False) -> dict:
        with self.lock:
            self.state.state_sequence += 1
            selected, pagination = ([], None) if summary_only else job_page(self.state.jobs.values(), **(view or {}))
            sources = [dict(item) for item in selected] if not summary_only else []
            jobs = [job_summary(item) for item in sources]
            counts = {"queued": 0, "active": 0, "completed": 0, "failed": 0, "selecting": 0}
            for item in self.state.jobs.values():
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            active = self.state.jobs.get(self.state.active_id, {})
            active_job = job_summary(active) if active else None
            for job in [*jobs, *([active_job] if active_job else [])]:
                if job["id"] == self.state.active_id and self.state.active_started_monotonic is not None:
                    job["elapsed_seconds"] = round(max(0, time.monotonic() - self.state.active_started_monotonic), 2)
            engines = media.engine_status()
            pacing = self.POLICY.snapshot()
            quota = self._quota_locked()
            queued_cooldowns = [self.POLICY.snapshot(platform_key(self.state.jobs[key]["url"]))["cooldown_seconds"]
                                for key in self.state.queue if key in self.state.jobs]
            queue_cooling = min(queued_cooldowns, default=0)
            relevant_cooling = self.POLICY.snapshot(platform_key(active["url"]))["cooldown_seconds"] if active else queue_cooling
            pacing["cooldown_seconds"] = relevant_cooling
            pacing["cooldown_until"] = time.time() + relevant_cooling if relevant_cooling else 0
            wait_seconds = max(0, math.ceil(self.state.next_job_at - time.time()), queue_cooling, quota["wait_seconds"])
            profile_phase = active.get("profile_stage") if active.get("mode") in self.PROFILE_MODES else None
            phase = (profile_phase if profile_phase in {"paused", "waiting", "quota", "cooldown"} else
                     "active" if self.state.active_id else "paused" if self.state.paused else
                     "cooldown" if counts["queued"] and queue_cooling else
                     "quota" if counts["queued"] and quota["limited"] else
                     "waiting" if counts["queued"] and wait_seconds else
                     "ready" if counts["queued"] else "selection" if counts["selecting"] else "idle")
            payload = {
                "state_instance": self.state.state_instance,
                "state_sequence": self.state.state_sequence,
                "jobs": jobs,
                "total_jobs": len(self.state.jobs),
                "platforms": sorted({item["platform"] for item in self.state.jobs.values()}),
                "active_job": active_job,
                "counts": counts,
                "paused": self.state.paused,
                "active_id": self.state.active_id,
                "download_dir": str(self.state.download_dir),
                "x_cookie_file": self.state.x_cookie_file,
                "x_auth": self.X_AUTH.status(),
                "pixiv_auth": self.PIXIV_AUTH.status(),
                "file_actions": "browser" if host_browser_required() else "desktop",
                "ready": all(engines[key] for key in ("video", "images", "ffmpeg")),
                "app_version": __version__,
                "version": engines["video_version"],  # Legacy API field: yt-dlp version.
                "engines": engines,
                "environment": self.ENVIRONMENT.snapshot(),
                "persistence": self._persistence_status(),
                "worker": {**self.state.worker_status, "alive": bool(self.state.worker_thread and self.state.worker_thread.is_alive())},
                "no_progress_timeout": self.state.no_progress_timeout,
                "dynamic_capture": self.state.dynamic_capture,
                "browser_capture_available": browser_capture_available(),
                "quality_mode": "original",
                "rate_limit": quota,
                "hourly_job_limit": self.state.hourly_job_limit,
                "storage": self.STORAGE.snapshot(self.state.download_dir),
                "thumbnail_cache": self.THUMBNAILS.status(),
                "databases": self.DATABASES.status(),
                "safe_queue": {**pacing, "enabled": True, "workers": 1, "phase": phase,
                               "delay_min": JOB_DELAY_MIN, "delay_max": JOB_DELAY_MAX,
                               "request_interval": REQUEST_INTERVAL, "wait_seconds": wait_seconds,
                               "next_job_at": self.state.next_job_at},
            }
            directory = self.state.download_dir
            if not summary_only:
                payload["jobs_page"] = pagination
        # Source file metadata and preview generation do not hold the download queue lock.
        for job, source in zip(jobs, sources):
            preview = self.THUMBNAILS.snapshot(source, directory)
            job["thumbnail_status"] = preview["status"]
            job["thumbnail_kind"] = preview.get("kind", "")
            job["thumbnail_url"] = (f'/api/jobs/{job["id"]}/thumbnail?key={preview["key"]}'
                                    if preview["status"] == "ready" else "")
        return payload


    def _diagnostics(self) -> dict:
        """An intentionally small export: no history URLs, paths, or credentials."""
        with self.lock:
            counts = {name: sum(job["status"] == name for job in self.state.jobs.values())
                      for name in ("queued", "active", "completed", "failed")}
            result = {"format_version": 1, "app_version": __version__, "created_at": time.time(), "counts": counts,
                      "environment": self.ENVIRONMENT.snapshot(), "persistence": self._persistence_status(),
                      "databases": self.DATABASES.status(),
                      "worker": dict(self.state.worker_status), "rate_limit": self._quota_locked(),
                      "x_auth": {key: self.X_AUTH.status().get(key) for key in ("connected", "phase")},
                      "jobs": [{"id": job["id"], "platform": job["platform"], "status": job["status"],
                                "error_code": job.get("error_code", ""), "error": job.get("error", ""),
                                "error_detail": job.get("error_detail", ""), "warnings": job.get("warnings", [])}
                               for job in self.state.jobs.values()]}
        def scrub(value):
            if isinstance(value, dict):
                return {key: scrub(item) for key, item in value.items()}
            if isinstance(value, list):
                return [scrub(item) for item in value]
            return redact_text(value) if isinstance(value, str) else value
        return scrub(result)


    def _format_bytes(self, value) -> str:
        if not isinstance(value, (int, float)) or value < 0:
            return ""
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
        return ""
