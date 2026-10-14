"""Child entry: credentials use an anonymous pipe, never argv or diagnostics."""
from __future__ import annotations

import io
from pathlib import Path
import sys
import threading
import time
from .ipc import read_message, write_message, MessageTooLarge, CAPACITY_ERROR


def send_failure(send, data):
    """An oversized result's error must not resend the same oversized files."""
    try:
        send("error", data=data)
    except MessageTooLarge:
        send("error", data={"error": CAPACITY_ERROR, "error_code": "worker_message_too_large"})


def main():
    stream = sys.stdout.buffer
    class SilentOutput(io.TextIOBase):
        def write(self, value):
            return len(value)
    sys.stdout = SilentOutput()  # Discard library output without retaining it.
    lock = threading.Lock()
    rpc_lock = threading.Lock()
    last_activity = 0.0

    def send(kind, **values):
        with lock:
            write_message(stream, {"type": kind, **values})

    payload = read_message(sys.stdin.buffer)
    from . import media, request_policy, web_media
    from .network import public_network
    from .diagnostics import redact_fields
    from .media_selection import SelectionRequired
    from .browser_media import browser_driver

    def rpc(operation, value=None):
        with rpc_lock:
            send("rpc", operation=operation, value=value, id=1)
            response = read_message(sys.stdin.buffer)
            if response.get("error"):
                raise media.DownloadError(response["error"], code=response.get("code", "download_failed"))
            return response.get("value")

    class RemotePolicy(request_policy.RequestPolicy):
        def before_request(self, emit=None, **kwargs):
            rpc("request")

        def limit(self, retry_after=None):
            return rpc("limit", retry_after)

        def snapshot(self):
            return rpc("snapshot")

        def job_completed(self):
            rpc("completed")

        def ensure_cooldown(self):
            if not self.snapshot()["cooldown_seconds"]:
                self.limit()

    shared = RemotePolicy()
    media.POLICY = web_media.POLICY = request_policy.POLICY = shared

    def activity():
        nonlocal last_activity
        now = time.monotonic()
        if now - last_activity >= .5:
            last_activity = now
            send("activity")

    def emit(data):
        send("progress", data=redact_fields(data))

    try:
        with browser_driver(payload.get("dynamic_capture") is True and not payload.get("profile")) as browser, public_network(activity):
            output = Path(payload["output_dir"])
            common = {"x_cookie_file": payload.get("cookie_file", ""), "x_cookies": payload.get("x_cookies", {}),
                      "known_jobs": payload.get("known_jobs", ())}
            if payload.get("profile"):
                result = media.download_x_account(payload["url"], output, emit, **common,
                    archive_file=Path(payload["archive_file"]), previous_files=payload.get("previous_files", ()),
                    before_post=lambda: rpc("before_post"), checkpoint=lambda: rpc("checkpoint"))
            else:
                result = media.download(payload["url"], output, emit, **common, force=payload.get("force", False),
                    image_history_file=Path(payload["image_history_file"]), manifest_file=Path(payload["manifest_file"]),
                    video_quality=payload.get("video_quality", "best"), selected_media=payload.get("selected_media", ""),
                    dynamic_capture=payload.get("dynamic_capture") is True, browser=browser)
        send("result", data=redact_fields(result))
    except SelectionRequired as exc:
        try:
            send("selection", options=exc.options)
        except MessageTooLarge:
            send_failure(send, {"error": CAPACITY_ERROR, "error_code": "worker_message_too_large"})
    except MessageTooLarge:
        send_failure(send, {"error": CAPACITY_ERROR, "error_code": "worker_message_too_large"})
    except Exception as exc:
        send_failure(send, {**media.error_info(exc), "files": getattr(exc, "files", [])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
