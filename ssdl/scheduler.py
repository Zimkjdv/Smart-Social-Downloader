"""Serial queue scheduling and download lifecycle.

The injected app context owns shared state; this module never imports app.
"""
from __future__ import annotations
import json
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


class QueueScheduler:
    def __init__(self, app):
        self.app = app

    def known_jobs(self, job, output_dir, profile):
        """Only migrate history relevant to this source/quality and output root."""
        if job.get("force_download") and not profile:
            return []
        identity = self.app.media.source_key(job["url"])
        preference = job.get("video_quality", "best")
        selection = job.get("selected_media", "")
        candidates = (stored for stored in self.app._jobs.values()
                      if stored["status"] == "completed" and stored.get("mode") != "x_profile")
        result = []
        for stored in (*candidates, job.get("last_success")):
            if not isinstance(stored, dict) or not self.app.media._same_output_directory(stored, output_dir):
                continue
            try:
                if profile:
                    url = stored.get("url", "")
                    if not self.app.media.x_post_id(url):
                        continue
                    author = urlparse(url).path.strip("/").split("/")[0].lower()
                    if author not in {profile[1], "i"}:
                        continue
                    if stored.get("video_quality", "best") != "best" or stored.get("selected_media"):
                        continue
                elif (self.app.media.source_key(stored.get("url", "")) != identity
                      or stored.get("video_quality", "best") != preference
                      or (stored.get("selected_media") or "") != selection):
                    continue
            except (ValueError, TypeError, AttributeError):
                continue
            files = stored.get("files")
            if not isinstance(files, list) or any(not isinstance(name, str) for name in files):
                continue
            result.append({key: stored.get(key) for key in
                ("url", "output_dir", "size_bytes", "title", "quality", "video_quality", "selected_media")} |
                {"files": list(files)})
        return result

    def quota_locked(self) -> dict:
        now = time.time()
        while self.app._job_starts and self.app._job_starts[0] <= now - self.app.JOB_RATE_WINDOW:
            self.app._job_starts.popleft()
        used = len(self.app._job_starts)
        limited = used >= self.app._hourly_job_limit
        release_index = used - self.app._hourly_job_limit if limited else 0
        reset_at = self.app._job_starts[release_index] + self.app.JOB_RATE_WINDOW if self.app._job_starts else 0
        reset_in = max(0, math.ceil(reset_at - now))
        return {"used": used, "limit": self.app._hourly_job_limit, "window_seconds": self.app.JOB_RATE_WINDOW,
                "remaining": max(0, self.app._hourly_job_limit - used), "limited": limited,
                "wait_seconds": reset_in if limited else 0,
                "reset_in": reset_in, "reset_at": reset_at}

    def progress_hook(self, job_id: str):
        stats_file_count = 0
        def update(data: dict) -> None:
            nonlocal stats_file_count
            stats_files = []
            stats_directory = None
            with self.app._lock:
                job = self.app._jobs.get(job_id)
                if not job:
                    return
                title = data.get("title")
                is_profile = job.get("mode") == "x_profile"
                if title and not is_profile:
                    job["title"] = title[:180]
                filename = data.get("filename")
                if filename:
                    job["filename"] = Path(filename).name
                if "downloaded_bytes" in data:
                    total = data.get("total_bytes")
                    downloaded = data.get("downloaded_bytes") or 0
                    job["progress"] = round(min(99, downloaded * 100 / total)) if total else None
                    speed = data.get("speed")
                    job["speed"] = f"{self.app._format_bytes(speed)}/s" if speed else ""
                    eta = data.get("eta")
                    job["eta"] = f"{int(eta) // 60}:{int(eta) % 60:02d}" if isinstance(eta, (int, float)) and eta >= 0 else ""
                    job["size"] = self.app._format_bytes(total)
                    job["downloaded_bytes"] = downloaded
                    job["total_bytes"] = total
                    job["size_bytes"] = total if isinstance(total, (int, float)) and total >= 0 else downloaded
                    job["status_text"] = "下載中"
                if data.get("status_text"):
                    job["status_text"] = data["status_text"]
                if data.get("quality"):
                    job["quality"] = data["quality"]
                if "files" in data:
                    job["files"] = data["files"]
                job["updated_at"] = time.time()
                if is_profile:
                    for key in ("profile_posts", "profile_skipped", "profile_downloaded_posts", "profile_stage", *self.app._PROFILE_COUNT_DEFAULTS):
                        if key in data:
                            job[key] = data[key]
                    total_files = job.get("profile_total_files")
                    completed_files = job.get("profile_completed_files", 0)
                    job["progress"] = round(min(99, completed_files * 100 / total_files)) if (
                        job.get("profile_scan_complete") and isinstance(total_files, int) and total_files > 0) else None
                    if "aggregate_bytes" in data:
                        job["size_bytes"] = data["aggregate_bytes"]
                        job["size"] = self.app._format_bytes(data["aggregate_bytes"])
                    if data.get("profile_post_finished") or (data.get("profile_scan_finished") and data.get("profile_files_to_download")):
                        self.app._next_job_at = time.time() + random.uniform(self.app.JOB_DELAY_MIN, self.app.JOB_DELAY_MAX)
                        self.app._save_locked()
                    if data.get("profile_post_finished"):
                        files = job.get("files") or []
                        stats_files = files[stats_file_count:] if len(files) >= stats_file_count else files[:]
                        stats_file_count = len(files)
                        stats_directory = Path(job.get("output_dir") or self.app._download_dir)
                    if job.get("stop_requested"):
                        job["status_text"] = "正在停止，保留已下載檔案"
                job["updated_at"] = time.time()
            if stats_files and stats_directory:
                self.app.STORAGE.record_files(stats_directory, stats_files)
        return update

    def profile_gate(self, job_id: str, *, start_post=False) -> None:
        """Wait at a post boundary; every new account post consumes shared hourly quota."""
        with self.app._condition:
            while True:
                job = self.app._jobs.get(job_id)
                if self.app._shutdown.is_set() or not job or job.get("stop_requested") or job.get("remove_when_finished"):
                    raise self.app.media.DownloadError("帳號下載已停止；已保存的檔案保留，可按同步繼續。", code="profile_stopped")
                quota = self.app._quota_locked()
                cooling = self.app.POLICY.snapshot(self.app.platform_key(job["url"]))["cooldown_seconds"] if start_post else 0
                wait = max(0, math.ceil(self.app._next_job_at - time.time()), cooling, quota["wait_seconds"]) if start_post else 0
                if not self.app._paused and not wait:
                    downloading = start_post or job.get("profile_scan_complete", False)
                    job["profile_stage"] = "downloading" if downloading else "scanning"
                    job["profile_wait_seconds"] = 0
                    job["status_text"] = "下載帳號媒體中" if downloading else "正在掃描 X 帳號媒體清單"
                    if start_post:
                        self.app._job_starts.append(time.time())
                        self.app._save_locked()
                    return
                stage = "paused" if self.app._paused else "cooldown" if cooling else "quota" if quota["limited"] else "waiting"
                job.update(profile_stage=stage, profile_wait_seconds=wait, speed="", eta="",
                           status_text="帳號下載已暫停" if self.app._paused else "帳號下載等待每小時額度" if stage == "quota" else
                           f"限流冷卻，等待 {wait} 秒" if stage == "cooldown" else f"安全延時，等待 {wait} 秒")
                self.app._condition.wait(timeout=.5)

    def job_cancelled(self, job_id):
        with self.app._lock:
            job = self.app._jobs.get(job_id)
            return self.app._shutdown.is_set() or not job or bool(job.get("stop_requested"))

    def worker_health(self, value):
        with self.app._lock:
            self.app._worker_status.update(value)

    def worker(self) -> None:
        """Recover the scheduler itself if preparation fails outside a job try/finally."""
        while not self.app._shutdown.is_set():
            try:
                self.app._worker_health({"phase": "idle", "pid": None, "no_progress_seconds": 0})
                self.app._worker_loop()
            except Exception as exc:
                with self.app._condition:
                    current = self.app._jobs.get(self.app._active_id)
                    if current:
                        current.update(status="failed", status_text="下載失敗",
                                       **self.app.media.error_info(exc), finished_at=time.time())
                    self.app._active_id = self.app._active_started_monotonic = None
                    self.app._worker_status.update(phase="recovering", pid=None)
                    self.app._save_locked()
                    self.app._condition.notify_all()
                time.sleep(.5)

    def worker_loop(self) -> None:
        while not self.app._shutdown.is_set():
            with self.app._condition:
                while self.app._paused or not self.app._queue:
                    if self.app._shutdown.is_set():
                        return
                    self.app._condition.wait(timeout=.5)
                if not self.app._next_job_at:
                    self.app._next_job_at = time.time() + random.uniform(self.app.JOB_DELAY_MIN, self.app.JOB_DELAY_MAX)
                    self.app._save_locked()
                # Preserve order within a platform; let other platforms proceed during its cooldown.
                eligible = next((key for key in self.app._queue if key in self.app._jobs and not
                    self.app.POLICY.snapshot(self.app.platform_key(self.app._jobs[key]["url"]))["cooldown_seconds"]), None)
                if eligible is None:
                    self.app._condition.wait(timeout=.5)
                    continue
                head = self.app._jobs.get(eligible, {})
                profile_head = self.app.account_from_url(head.get("url", "")) is not None
                wait_seconds = max(self.app._next_job_at - time.time(), self.app.POLICY.snapshot(self.app.platform_key(head["url"]))["cooldown_seconds"],
                                   0 if profile_head else self.app._quota_locked()["wait_seconds"])
                if wait_seconds > 0:
                    self.app._condition.wait(timeout=min(wait_seconds, .5))
                    continue
                job_id = eligible
                self.app._queue.remove(job_id)
                job = self.app._jobs.get(job_id)
                if not job:
                    continue
                self.app._active_id = job_id
                job["status"] = "active"
                job["status_text"] = "正在連線"
                job["updated_at"] = time.time()
                job["attempts"] = job.get("attempts", 0) + 1
                job["started_at"] = time.time()
                self.app._active_started_monotonic = time.monotonic()
                job.update(finished_at=None, elapsed_seconds=0, size_bytes=None,
                           downloaded_bytes=0, total_bytes=None, size="")
                output_dir = self.app._download_dir
                cookie_file = self.app._x_cookie_file
                force = job.get("force_download", False)
                timeout = self.app._no_progress_timeout
                dynamic_capture = self.app._dynamic_capture
                job["stop_requested"] = False
                profile = self.app.account_from_url(job["url"])
                known_jobs = self.known_jobs(job, output_dir, profile)
                previous_files = job.get("files", ()) if self.app.media._same_output_directory(job, output_dir) else ()
                job["output_dir"] = str(output_dir)
                job["skipped_download"] = False
                if profile:
                    job.update(mode="x_profile", account=profile[1], stop_requested=False,
                               profile_stage="scanning", profile_posts=0, profile_skipped=0,
                               profile_downloaded_posts=0, profile_wait_seconds=0, progress=None)
                    job.update(self.app._PROFILE_COUNT_DEFAULTS)
                else:
                    self.app._job_starts.append(job["started_at"])
                self.app._save_locked()

            try:
                x_cookies = self.app.X_AUTH.cookies() if job["platform"] == "X" else {}
                result = self.app.run_job({"url": job["url"], "output_dir": str(output_dir), "cookie_file": cookie_file,
                    "x_cookies": x_cookies, "profile": bool(profile), "force": force,
                    "archive_file": str(self.app.ROOT / "data" / "x-profiles.sqlite3"),
                    "image_history_file": str(self.app.ROOT / "data" / "image-history.sqlite3"),
                    "manifest_file": str(self.app.ROOT / "data" / "media-manifest.sqlite3"),
                    "video_quality": job.get("video_quality", "best"),
                    "dynamic_capture": dynamic_capture,
                    "selected_media": job.get("selected_media", ""), "policy_platform": self.app.platform_key(job["url"]),
                    "previous_files": list(previous_files), "known_jobs": known_jobs},
                    self.app._progress_hook(job_id), lambda start_post=False: self.app._profile_gate(job_id, start_post=start_post),
                    lambda: self.app._job_cancelled(job_id), self.app.POLICY, self.app._worker_health, no_progress_timeout=timeout)
                final_size = self.app._file_total_bytes(result["files"], output_dir)
                if profile and not result["files"]:
                    final_size = 0
                with self.app._lock:
                    current = self.app._jobs.get(job_id)
                    if current:
                        if result.get("title"):
                            current["title"] = str(result["title"])[:180]
                        current["files"] = result["files"]
                        current["filename"] = result["files"][0] if result["files"] else ""
                        current["quality"] = result["quality"]
                        current["warnings"] = result.get("warnings", [])
                        current["progress"] = 100
                        current["status"] = "completed"
                        current["skipped_download"] = bool(result.get("skipped"))
                        current["skipped_file_count"] = result.get("skipped_file_count", 0)
                        current["downloaded_file_count"] = result.get("downloaded_file_count", 0)
                        current.pop("last_success", None)
                        current["status_text"] = "帳號媒體同步完成" if profile else "已略過，檔案已存在" if result.get("skipped") else "已完成"
                        if profile:
                            current.update(profile_stage="done", profile_wait_seconds=0)
                        current.update(error="", error_detail="", error_code="", speed="", eta="")
                        current["size_bytes"] = final_size
                        current["size"] = self.app._format_bytes(final_size)
                        current["updated_at"] = time.time()
                self.app.POLICY.job_completed(platform=self.app.platform_key(job["url"]))
            except self.app.SelectionRequired as exc:
                with self.app._lock:
                    current = self.app._jobs.get(job_id)
                    if current:
                        current.update(status="selecting", status_text="請選擇要下載的媒體", selection_options=exc.options,
                                       error="", error_code="", error_detail="", progress=0, speed="", eta="",
                                       updated_at=time.time())
            except Exception as exc:
                failure = self.app.media.error_info(exc)
                if failure["error_code"] == "rate_limited":
                    self.app.POLICY.ensure_cooldown(platform=self.app.platform_key(job["url"]))
                with self.app._lock:
                    saved_files = list(getattr(exc, "files", None) or job.get("files", []))
                saved_size = self.app._file_total_bytes(saved_files, output_dir)
                with self.app._lock:
                    current = self.app._jobs.get(job_id)
                    if current:
                        current["status"] = "failed"
                        stopped = failure["error_code"] in {"profile_stopped", "download_cancelled"}
                        current["status_text"] = "已停止" if stopped else "下載失敗"
                        current.update(failure, speed="", eta="")
                        current["size_bytes"] = saved_size
                        current["size"] = self.app._format_bytes(saved_size)
                        if getattr(exc, "files", None):
                            current["files"] = exc.files
                            current["filename"] = exc.files[0]
                            current["status_text"] = "已停止" if stopped else "部分下載失敗"
                        if profile:
                            current.update(profile_stage="stopped" if stopped else "failed",
                                           profile_wait_seconds=0)
                        current["updated_at"] = time.time()
                        if self.app._shutdown.is_set() and not current.get("stop_requested"):
                            current.update(status="queued", status_text="服務重啟，等待重試",
                                           error="", error_detail="", error_code="")
                            if job_id not in self.app._queue:
                                self.app._queue.appendleft(job_id)
            finally:
                # Update only this job's saved files, rather than traversing the whole tree.
                self.app.STORAGE.record_files(output_dir, list(job.get("files") or []))
                with self.app._condition:
                    current = self.app._jobs.get(job_id)
                    if current and self.app._active_started_monotonic is not None:
                        current["elapsed_seconds"] = round(max(0, time.monotonic() - self.app._active_started_monotonic), 2)
                        current["finished_at"] = time.time()
                    if current and current.get("remove_when_finished"):
                        self.app._jobs.pop(job_id, None)
                    if self.app._active_id == job_id:
                        self.app._active_id = None
                        self.app._active_started_monotonic = None
                    self.app._next_job_at = time.time() + random.uniform(self.app.JOB_DELAY_MIN, self.app.JOB_DELAY_MAX)
                    self.app._save_locked()
                    self.app._condition.notify_all()
