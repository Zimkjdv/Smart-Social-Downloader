"""Bounded supervision of one isolated download, with cancellable shared gates."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from .diagnostics import redact_fields
from .media import DownloadError
from .process_group import ProcessGroup
from .ipc import read_message, write_message, ProtocolError, MessageTooLarge, MAX_FRAME_BYTES, CAPACITY_ERROR

from .runtime_paths import paths, module_command

NO_PROGRESS_SECONDS = 300
MAX_MESSAGE = MAX_FRAME_BYTES  # Compatibility name: maximum wire frame, not logical message.


def run_job(payload, emit, gate, cancelled, policy, health=lambda value: None, *,
            no_progress_timeout=NO_PROGRESS_SECONDS, command=None):
    root = paths().home
    process = subprocess.Popen(command or module_command('ssdl.job_runner'),
        cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        bufsize=65536,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
    group, events = None, queue.Queue(maxsize=128)
    ending = threading.Event()
    last_progress = time.monotonic()
    last_signature = None
    merging = False
    last_cpu = 0.0
    last_health = 0.0
    capture_deadline = None

    def read_events():
        try:
            while not ending.is_set():
                event = read_message(process.stdout)
                if event is None:
                    break
                if isinstance(event, dict):
                    while not ending.is_set():
                        try:
                            events.put(event, timeout=.2)
                            break
                        except queue.Full:
                            pass
        except (ProtocolError, OSError) as exc:
            if not ending.is_set():
                try:
                    events.put({"type": "message_too_large" if isinstance(exc, MessageTooLarge) else "protocol_error"}, timeout=.2)
                except queue.Full:
                    pass
        finally:
            if not ending.is_set():
                try:
                    events.put({"type": "eof"}, timeout=.2)
                except queue.Full:
                    pass

    reader = threading.Thread(target=read_events, name="job-events", daemon=True)
    def write_payload():
        try:
            write_message(process.stdin, payload)
        except ProtocolError as exc:
            if not ending.is_set():
                try:
                    events.put({"type": "message_too_large" if isinstance(exc, MessageTooLarge) else "protocol_error"}, timeout=.2)
                except queue.Full:
                    pass
        except (OSError, ValueError, queue.Full):
            if not ending.is_set():
                try:
                    events.put({"type": "eof"}, timeout=.2)
                except queue.Full:
                    pass
    writer = threading.Thread(target=write_payload, name="job-input", daemon=True)
    try:
        # The child waits for its first input before importing engines or
        # creating any helper process, eliminating the process-group race.
        group = ProcessGroup(process)
        reader.start()
        writer.start()
        while True:
            now = time.monotonic()
            if cancelled():
                raise DownloadError("下載已停止；已保存檔案保留，可重新下載。", code="download_cancelled")
            if capture_deadline is not None and now >= capture_deadline:
                raise DownloadError("動態媒體捕捉已逾時；已停止隔離瀏覽器，後續佇列會繼續。", code="browser_capture_timeout")
            if merging:
                cpu = group.cpu_time()
                if cpu > last_cpu + .01:
                    last_progress = now
                last_cpu = cpu
            if now - last_progress > no_progress_timeout:
                raise DownloadError("下載長時間沒有進度，已停止此工作；可重試，後續佇列會繼續。", code="download_stalled")
            if now - last_health > 1:
                health({"phase": "merging" if merging else "running", "pid": process.pid,
                        "last_progress_at": time.time() - (now - last_progress),
                        "no_progress_seconds": round(now - last_progress, 1),
                        "no_progress_limit": no_progress_timeout})
                last_health = now
            try:
                event = events.get(timeout=.2)
            except queue.Empty:
                continue
            kind = event.get("type")
            if kind == "progress" and isinstance(event.get("data"), dict):
                data = redact_fields(event["data"])
                signature = json.dumps(data, sort_keys=True, ensure_ascii=True)
                if signature != last_signature:
                    last_progress, last_signature = time.monotonic(), signature
                merging = "合併" in str(data.get("status_text", "")) or data.get("stage") == "postprocessing"
                if data.get("stage") == "browser_capture":
                    seconds = data.get("capture_timeout", 45)
                    seconds = min(45, max(1, seconds)) if type(seconds) in {int, float} else 45
                    # A child cannot extend an already running capture by repeating an event.
                    capture_deadline = min(capture_deadline or float("inf"), time.monotonic() + seconds)
                elif data.get("stage") == "browser_capture_finished":
                    capture_deadline = None
                emit(data)
            elif kind == "activity":
                last_progress = time.monotonic()
            elif kind == "rpc":
                operation, value = event.get("operation"), None
                health({"phase": "waiting", "pid": process.pid, "wait_reason": operation,
                        "no_progress_seconds": 0, "no_progress_limit": no_progress_timeout})
                try:
                    if operation in {"checkpoint", "before_post"}:
                        gate(start_post=operation == "before_post")
                    elif operation == "request":
                        policy.before_request(emit, cancelled=lambda: cancelled() or (
                            capture_deadline is not None and time.monotonic() >= capture_deadline),
                            platform=payload.get("policy_platform"))
                    elif operation == "limit":
                        value = policy.limit(event.get("value"), platform=payload.get("policy_platform"))
                    elif operation == "snapshot":
                        value = policy.snapshot(payload.get("policy_platform"))
                    elif operation == "completed":
                        policy.job_completed(platform=payload.get("policy_platform"))
                    else:
                        raise DownloadError("下載工作通訊格式不正確。", code="worker_protocol")
                    response = {"id": event.get("id"), "value": value}
                except DownloadError as exc:
                    response = {"id": event.get("id"), "error": str(exc), "code": exc.code}
                write_message(process.stdin, response)
                last_progress = time.monotonic()  # Deliberate queue waits are exempt.
            elif kind == "result" and isinstance(event.get("data"), dict):
                return redact_fields(event["data"])
            elif kind == "selection":
                from .media_selection import SelectionRequired
                raise SelectionRequired(redact_fields(event.get("options")))
            elif kind == "error":
                data = redact_fields(event.get("data", {}))
                raise DownloadError(data.get("error", "下載工作失敗。"), data.get("files", ()),
                                    code=data.get("error_code", "download_failed"), detail=data.get("error_detail", ""))
            elif kind == "message_too_large":
                raise DownloadError(CAPACITY_ERROR, code="worker_message_too_large")
            elif kind == "protocol_error":
                raise DownloadError("下載工作通訊不完整或格式錯誤，請重試；後續佇列會繼續。", code="worker_protocol")
            elif kind == "eof":
                raise DownloadError("下載程序已中斷，後續佇列會繼續；可重新下載。", code="worker_exited")
    finally:
        ending.set()
        if group is not None:
            group.close()
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        for stream in (process.stdin, process.stdout):
            if stream:
                stream.close()
        if reader.is_alive():
            reader.join(timeout=1)
        if writer.is_alive():
            writer.join(timeout=1)
        health({"phase": "idle", "pid": None, "no_progress_seconds": 0, "no_progress_limit": no_progress_timeout})
