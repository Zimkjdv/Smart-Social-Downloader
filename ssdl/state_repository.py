"""Atomic history storage and migration.

The injected app context owns shared state; this module never imports app.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import replace

if TYPE_CHECKING:
    from .app_context import AppContext
import os
import math
import time
from collections import deque
from pathlib import Path
from .state_writer import freeze_snapshot


class StateRepository:
    def __init__(self, app: AppContext):
        self.app = app

    def save_locked(self, *, checkpoint=False) -> int:
        """Capture under the queue lock; callers wait for the returned generation outside it.

        Explicit calls without the lock retain synchronous save behavior. Cookie
        values are never part of a snapshot. Writer construction starts no thread.
        """
        if not self.app.lock._is_owned():
            with self.app.condition:
                generation = self.save_locked(checkpoint=checkpoint)
            if not checkpoint:
                self.app._wait_saved(generation)
            return generation
        try:
            snapshot = self.snapshot_locked()
        except (ValueError, TypeError, RecursionError):
            self.app.STATE_STORE.record_failure()
            return self.app.STATE_WRITER.reject_snapshot()
        return self.app.STATE_WRITER.submit(snapshot, checkpoint=checkpoint)

    def snapshot_locked(self):
        """Immutable operational state; caller owns the queue condition."""
        payload = {"jobs": list(self.app.state.jobs.values()), "queue": list(self.app.state.queue), "paused": self.app.state.paused,
                   "download_dir": str(self.app.state.download_dir), "x_cookie_file": self.app.state.x_cookie_file,
                   "safe_queue": {**self.app.POLICY.snapshot(), "next_job_at": self.app.state.next_job_at},
                   "job_starts": list(self.app.state.job_starts), "hourly_job_limit": self.app.state.hourly_job_limit,
                   "no_progress_timeout": self.app.state.no_progress_timeout, "dynamic_capture": self.app.state.dynamic_capture}
        return freeze_snapshot(payload)

    def file_total_bytes(self, files, directory: Path) -> int | None:
        if not files or not isinstance(files, (list, tuple)):
            return None
        try:
            root = directory.resolve()
            total = 0
            seen = set()
            for raw in files:
                if not isinstance(raw, str):
                    return None
                target = (root / raw).resolve()
                if not target.is_relative_to(root) or not target.is_file():
                    return None
                if target not in seen:
                    seen.add(target)
                    total += target.stat().st_size
            return total
        except (OSError, ValueError, RuntimeError):
            return None

    def merge_completed_duplicates_locked(self) -> None:
        """Consolidate verified rows for the same source, folder and exact file set."""
        kept, duplicates = {}, []
        for job in sorted(self.app.state.jobs.values(), key=lambda item: item["created_at"], reverse=True):
            if job["status"] != "completed" or job.get("mode") == "x_profile" or not job.get("output_dir"):
                continue
            files = job.get("files", [])
            try:
                root = Path(job["output_dir"]).resolve()
                size = self.app._file_total_bytes(files, root)
                if size is None or size <= 0 or size != job.get("size_bytes"):
                    continue
                key = (self.app.media.source_key(job["url"]), job.get("video_quality", "best"), job.get("selected_media", ""), os.path.normcase(str(root)),
                       tuple(sorted({os.path.normcase(str(root / name)) for name in files})))
            except (OSError, ValueError, TypeError, RuntimeError):
                continue
            if key in kept:
                duplicates.append((job, kept[key]))
            else:
                kept[key] = job
        if not duplicates:
            return
        # Keep the original state recoverable before changing historical records.
        backup = self.app.STATE_FILE.with_name(f"state.before-row-dedup-{time.time_ns()}.json")
        try:
            backup.write_bytes(self.app.STATE_FILE.read_bytes())
        except OSError:
            print("無法備份原清單，暫時保留重複紀錄。")
            return
        for duplicate, retained in duplicates:
            retained["attempts"] = retained.get("attempts", 0) + duplicate.get("attempts", 0)
            retained["retry_count"] = retained.get("retry_count", 0) + duplicate.get("retry_count", 0) + 1
            self.app.state.jobs.pop(duplicate["id"], None)
        print(f"已合併 {len(duplicates)} 個指向相同檔案的完成紀錄，下載檔案保留。")

    def _prepare_state(self, payload):
        """Reconstruct a candidate without touching live jobs, settings or policy."""
        from .request_policy import RequestPolicy

        directory = self.app.state.download_dir
        if payload.get("download_dir"):
            directory = Path(payload["download_dir"]).expanduser().resolve()
        jobs = {}
        for stored in payload["jobs"][:self.app.MAX_JOBS]:
            if stored.get("remove_when_finished"):
                continue
            item = self.app.redact_fields(stored)
            if "platform" not in item:
                item["platform"] = self.app._platform(item["url"])
            item.setdefault("title", "等待下載")
            item.setdefault("video_quality", "best")
            item.setdefault("selected_media", "")
            if item["status"] == "active" and item.get("stop_requested"):
                item.update(status="failed", status_text="已停止", profile_stage="stopped",
                            error="下載已停止；已保存檔案保留，可重新下載。",
                            error_code="download_cancelled", error_detail="", speed="", eta="")
            if item["status"] == "active":
                item.update(status="queued", status_text="服務重啟，等待重試", speed="", eta="", progress=0,
                            started_at=None, finished_at=None, elapsed_seconds=None,
                            size_bytes=None, total_bytes=None, downloaded_bytes=0, size="")
            if item["status"] == "failed":
                item.update(self.app.media.error_info(self.app.media.DownloadError(
                    item.get("error", "下載失敗"), code=item.get("error_code", "download_failed"),
                    detail=item.get("error_detail", ""))))
            if item["status"] in {"completed", "failed"}:
                if item.get("size_bytes") is None:
                    output = Path(item.get("output_dir") or directory).expanduser().resolve()
                    item["size_bytes"] = self.app._file_total_bytes(item.get("files"), output)
                    item["size"] = self.app._format_bytes(item["size_bytes"])
                    if item["size_bytes"] is not None and not item.get("output_dir"):
                        item["output_dir"] = str(output)
                if item.get("elapsed_seconds") is None:
                    started, ended = item.get("started_at"), item.get("updated_at")
                    if (isinstance(started, (int, float)) and isinstance(ended, (int, float))
                            and math.isfinite(started) and math.isfinite(ended) and 0 < started <= ended):
                        item["elapsed_seconds"] = round(ended - started, 2)
                        item["finished_at"] = ended
            jobs[item["id"]] = item
        queued = [key for key, item in jobs.items() if item["status"] == "queued"]
        queue = deque(dict.fromkeys([key for key in payload.get("queue", []) if key in queued] + queued))
        now = time.time()
        starts = deque(sorted(value for value in payload.get("job_starts", [])
            if type(value) in {int, float} and math.isfinite(value)
            and now - self.app.JOB_RATE_WINDOW < value <= now + 1))
        policy = RequestPolicy()
        saved_policy = payload.get("safe_queue", {})
        policy.restore(saved_policy)
        next_job = min(now + self.app.JOB_DELAY_MAX, max(0, saved_policy.get("next_job_at", 0)))
        limit = payload.get("hourly_job_limit", self.app.JOB_RATE_LIMIT)
        timeout = payload.get("no_progress_timeout", self.app.NO_PROGRESS_SECONDS)
        state = replace(self.app.state, jobs=jobs, queue=queue, paused=payload.get("paused", False),
                        download_dir=directory, x_cookie_file=payload.get("x_cookie_file", ""),
                        hourly_job_limit=limit if type(limit) is int and 1 <= limit <= 1000 else self.app.JOB_RATE_LIMIT,
                        no_progress_timeout=timeout if type(timeout) is int and 30 <= timeout <= 3600 else self.app.NO_PROGRESS_SECONDS,
                        dynamic_capture=payload.get("dynamic_capture") is True,
                        job_starts=starts, next_job_at=next_job)
        return state, policy

    def load_saved_state(self) -> None:
        try:
            # Startup normally has generation zero; explicit fixture/recovery
            # reloads must not race a previously submitted checkpoint.
            if not self.app._wait_saved(self.app.STATE_WRITER.status()["generation"]):
                return
            with self.app.condition:
                ready = self.app.STATE_STORE.load(normalize=self._prepare_state)
                if ready is None:
                    return
                # All potentially failing work completed before any live field changes.
                self.app.state, self.app.POLICY = ready
                self.app._merge_completed_duplicates_locked()
                generation = self.app._save_locked()
            self.app._wait_saved(generation)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            self.app.STATE_STORE.restore_failed()
            print(f"無法讀取已保存下載清單：{type(exc).__name__}")
