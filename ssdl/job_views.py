"""Bounded API views; persisted jobs retain their full file history."""
from __future__ import annotations

import math

PAGE_SIZES = (10, 20, 50)
FILE_PREVIEW_LIMIT = 20
JOB_FIELDS = frozenset((
    "id", "url", "platform", "title", "status", "status_text", "created_at", "updated_at",
    "mode", "account", "filename", "output_dir", "quality", "video_quality", "progress", "speed", "eta",
    "size", "size_bytes", "elapsed_seconds", "downloaded_bytes", "total_bytes", "started_at",
    "finished_at", "attempts", "retry_count", "skipped_download", "error", "error_code",
    "remove_when_finished", "stop_requested", "profile_stage", "profile_posts", "profile_skipped",
    "profile_downloaded_posts", "profile_wait_seconds", "profile_scan_complete",
    "profile_scanned_posts", "profile_scanned_files", "profile_total_posts", "profile_total_files",
    "profile_existing_files", "profile_downloaded_files", "profile_completed_files",
    "profile_files_to_download", "skipped_file_count", "downloaded_file_count",
    "selected_media", "selection_options",
))


def job_summary(job: dict) -> dict:
    result = {key: value for key, value in job.items() if key in JOB_FIELDS}
    files = job.get("files") or []
    result.update(files=list(files[:FILE_PREVIEW_LIMIT]), file_count=len(files),
                  files_complete=len(files) <= FILE_PREVIEW_LIMIT,
                  warning_count=len(job.get("warnings") or []))
    return result


def job_page(jobs, *, page=1, page_size=20, status="all", platform="all", search=""):
    page_size = page_size if page_size in PAGE_SIZES else 20
    status = status if status in {"all", "queued", "active", "completed", "failed", "selecting"} else "all"
    needle = search[:300].strip().casefold()
    visible = [job for job in jobs if (status == "all" or job["status"] == status)
               and (platform == "all" or job["platform"] == platform)
               and (not needle or needle in " ".join(str(job.get(key) or "") for key in
                                                    ("title", "url", "platform", "filename")).casefold())]
    visible.sort(key=lambda job: (job["created_at"], job["id"]), reverse=True)
    pages = max(1, math.ceil(len(visible) / page_size))
    page = max(1, min(page, pages))
    return visible[(page - 1) * page_size:page * page_size], {
        "page": page, "page_size": page_size, "page_count": pages, "total": len(visible),
        "status": status, "platform": platform, "search": search[:300],
    }


def file_page(job: dict, *, offset=0, limit=100) -> dict:
    files = job.get("files") or []
    offset = max(0, min(offset, len(files)))
    limit = max(1, min(limit, 100))
    end = min(len(files), offset + limit)
    return {"job_id": job["id"], "total": len(files), "offset": offset, "limit": limit,
            "next_offset": end if end < len(files) else None,
            "files": [{"index": index, "filename": files[index]} for index in range(offset, end)]}
