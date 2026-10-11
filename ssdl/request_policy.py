"""Shared pacing for downloader HTTP calls; no credentials or URLs are retained."""
from __future__ import annotations

import math
import threading
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

JOB_DELAY_MIN = 3
JOB_DELAY_MAX = 8
REQUEST_INTERVAL = 1.0
JOB_RATE_LIMIT = 40
JOB_RATE_WINDOW = 3600
COOLDOWN_BASE = 60
COOLDOWN_MAX = 900


def platform_key(url):
    host = (urlparse(url).hostname or "").lower().removeprefix("www.").removeprefix("mobile.")
    families = {"X": ("x.com", "twitter.com", "twimg.com"),
                "YouTube": ("youtube.com", "youtu.be", "googlevideo.com"),
                "Instagram": ("instagram.com",), "Facebook": ("facebook.com", "fb.watch"),
                "TikTok": ("tiktok.com",), "Douyin": ("douyin.com",),
                "Threads": ("threads.net", "threads.com")}
    return next((name for name, domains in families.items()
                 if any(host == domain or host.endswith("." + domain) for domain in domains)), host or "global")


class RateLimited(RuntimeError):
    code = "rate_limited"


class RequestPolicy:
    def __init__(self):
        self._lock = threading.Lock()
        self._next_request = 0.0
        self._cooldown = 0.0
        self._strikes = 0
        self._platforms = {}
        self.mode = "platform"

    def configure(self, mode):
        if not isinstance(mode, str) or mode not in {"global", "platform"}:
            raise ValueError("平台冷卻模式不正確")
        with self._lock:
            # Switching modes preserves existing deadlines; it never resets a cooldown.
            if mode == "global" and self.mode != mode:
                self._cooldown = max([self._cooldown, *(item[0] for item in self._platforms.values())])
                self._strikes = max([self._strikes, *(item[1] for item in self._platforms.values())])
            self.mode = mode

    def snapshot(self, platform=None) -> dict:
        with self._lock:
            now = time.monotonic()
            self._platforms = {key: value for key, value in self._platforms.items() if value[0] > now or value[1]}
            deadline, strikes = self._cooldown, self._strikes
            if self.mode == "platform" and platform is not None:
                local = self._platforms.get(platform, (0, 0))
                deadline, strikes = max(deadline, local[0]), max(strikes, local[1])
            elif self.mode == "platform" and self._platforms:
                deadline = max(deadline, *(item[0] for item in self._platforms.values()))
            remaining = max(0.0, deadline - now)
            return {"cooldown_until": time.time() + remaining if remaining else 0,
                    "cooldown_seconds": math.ceil(remaining), "strikes": strikes,
                    "cooldown_mode": self.mode,
                    "global_cooldown_until": time.time() + max(0, self._cooldown - now) if self._cooldown > now else 0,
                    "platform_cooldowns": {key: {"cooldown_until": time.time() + max(0, value[0] - now),
                        "cooldown_seconds": math.ceil(max(0, value[0] - now)), "strikes": value[1]}
                        for key, value in self._platforms.items()}}

    def restore(self, saved) -> None:
        if not isinstance(saved, dict):
            return
        try:
            deadline = float(saved.get("global_cooldown_until", saved.get("cooldown_until", 0)))
            strikes = int(saved.get("strikes", 0))
        except (ValueError, TypeError, OverflowError):
            return
        if not math.isfinite(deadline):
            return
        with self._lock:
            self._cooldown = time.monotonic() + max(0, min(86400, deadline - time.time()))
            self._strikes = max(0, min(10, strikes))
            mode = saved.get("cooldown_mode")
            self.mode = mode if isinstance(mode, str) and mode in {"global", "platform"} else "platform"
            platforms = saved.get("platform_cooldowns")
            for key, item in list((platforms if isinstance(platforms, dict) else {}).items())[:200]:
                if not isinstance(key, str) or len(key) > 253 or not isinstance(item, dict):
                    continue
                try:
                    until, count = float(item.get("cooldown_until", 0)), int(item.get("strikes", 0))
                    if math.isfinite(until):
                        self._platforms[key] = (time.monotonic() + max(0, min(86400, until - time.time())), max(0, min(10, count)))
                except (ValueError, TypeError, OverflowError):
                    continue

    def before_request(self, emit=None, *, cancelled=None, platform=None) -> None:
        announced = False
        while True:
            if cancelled and cancelled():
                from .media import DownloadError
                raise DownloadError("下載已停止；已保存檔案保留，可重新下載。", code="download_cancelled")
            with self._lock:
                now = time.monotonic()
                local = self._platforms.get(platform, (0, 0))[0] if self.mode == "platform" else 0
                deadline = max(self._cooldown, local)
                delay = max(self._next_request, deadline) - now
                if delay <= 0:
                    self._next_request = now + REQUEST_INTERVAL
                    return
                cooling = deadline > now
            if emit and not announced and delay > .15:
                emit({"status_text": f"限流冷卻，等待 {math.ceil(delay)} 秒" if cooling else "安全請求間隔等待中"})
                announced = True
            # Short waits re-check any cooldown added by another request.
            time.sleep(min(delay, .5))

    def limit(self, retry_after=None, *, platform=None) -> int:
        seconds = 0.0
        if retry_after is not None:
            try:
                seconds = float(retry_after)
            except (ValueError, TypeError):
                try:
                    date = parsedate_to_datetime(str(retry_after))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    seconds = date.timestamp() - time.time()
                except (ValueError, TypeError, OverflowError):
                    pass
        if not math.isfinite(seconds):
            seconds = 0.0
        with self._lock:
            grouped = self.mode == "platform" and platform is not None
            deadline, strikes = self._platforms.get(platform, (0, 0)) if grouped else (self._cooldown, self._strikes)
            strikes = min(10, strikes + 1)
            backoff = min(COOLDOWN_MAX, COOLDOWN_BASE * 2 ** (strikes - 1))
            duration = max(backoff, min(86400, max(0, seconds)))
            deadline = max(deadline, time.monotonic() + duration)
            if grouped:
                self._platforms[platform] = (deadline, strikes)
            else:
                self._cooldown, self._strikes = deadline, strikes
            return math.ceil(deadline - time.monotonic())

    def ensure_cooldown(self, *, platform=None) -> None:
        if not self.snapshot(platform)["cooldown_seconds"]:
            self.limit(platform=platform)

    def job_completed(self, *, platform=None) -> None:
        with self._lock:
            if self.mode == "platform" and platform is not None:
                if platform in self._platforms:
                    self._platforms[platform] = (self._platforms[platform][0], 0)
            else:
                self._strikes = 0

    def wrap_session(self, session, emit=None) -> None:
        """Pace this requests session, including its media and redirect sends."""
        if getattr(session, "_ssdl_paced", False):
            return
        original = session.send

        def send(*args, **kwargs):
            self.before_request(emit)
            response = original(*args, **kwargs)
            if response.status_code == 429:
                seconds = self.limit(response.headers.get("Retry-After"))
                response.close()
                raise RateLimited(f"HTTP 429: 平台限制請求次數，安全佇列冷卻 {seconds} 秒。")
            return response

        session.send = send
        session._ssdl_paced = True

    def wrap_yt_dlp(self, downloader, emit=None) -> None:
        """Wrap only this engine instance, without changing global library classes."""
        if getattr(downloader, "_ssdl_paced", False):
            return
        original = downloader.urlopen

        def urlopen(*args, **kwargs):
            self.before_request(emit)
            try:
                return original(*args, **kwargs)
            except Exception as exc:
                if getattr(exc, "status", getattr(exc, "code", None)) == 429:
                    response = getattr(exc, "response", None)
                    headers = getattr(exc, "headers", None) or getattr(response, "headers", {})
                    seconds = self.limit(headers.get("Retry-After") if headers else None)
                    if response is not None:
                        response.close()
                    raise RateLimited(f"HTTP 429: 平台限制請求次數，安全佇列冷卻 {seconds} 秒。") from exc
                raise

        downloader.urlopen = urlopen
        downloader._ssdl_paced = True


POLICY = RequestPolicy()
