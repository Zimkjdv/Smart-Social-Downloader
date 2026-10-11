"""Optional, ephemeral JavaScript discovery with fail-closed browser networking.

All browser HTTP resources are fulfilled through checked Python transport; the
browser itself uses a dead-end proxy, blocked service workers and WebSockets.
No normal Chrome profile is reused; no HAR, trace or persistent profile is kept.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import http.cookiejar
import importlib.util
import time
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

from .media_selection import selection_id
from .network import public_network, validate_url
from .web_media import (MediaCandidate, PlayerHTML, WebMediaError, public_url,
                        media_extension, media_type, MAX_CANDIDATES, diagnostic_error)
from .x_auth import chrome_executable

CAPTURE_SECONDS = 45
MAX_REQUESTS = 40
MAX_RESOURCE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_DOCUMENTS = 6
STREAM_EXTENSIONS = {"m3u8", "mpd", "mp4", "webm", "m4v", "mov", "mkv", "mp3", "m4a", "ogg", "opus", "wav", "flac"}
SAFE_DOWNLOAD_HEADERS = {"user-agent", "referer", "origin"}


def available():
    return importlib.util.find_spec("playwright") is not None and chrome_executable() is not None


@dataclass
class BrowserDriver:
    runtime: object = None
    error: str = ""


@contextmanager
def browser_driver(enabled=False):
    """Create the event loop before the child installs its public socket guard.

Windows asyncio's private wakeup sockets are local IPC, not media connections.
Starting the driver here avoids weakening public_network to permit loopback.
"""
    driver, manager = BrowserDriver(), None
    if enabled:
        try:
            from playwright.sync_api import sync_playwright
            manager = sync_playwright().start()
            driver.runtime = manager
        except Exception:
            driver.error = "動態捕捉無法啟動；請執行 python tools/manage.py browser-setup，並安裝一般 Chrome。"
    try:
        yield driver
    finally:
        if manager is not None:
            try:
                manager.stop()
            except Exception:
                pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Browser follows the Location through a new checked route.


@dataclass
class Resource:
    status: int
    headers: dict
    body: bytes = b""


class BrowserMediaDiscovery:
    def __init__(self, url, emit, driver, *, cookies=None, seconds=CAPTURE_SECONDS):
        self.url, self.emit, self.driver = url, emit, driver
        self.cookies = cookies if cookies is not None else http.cookiejar.CookieJar()
        self.opener = build_opener(_NoRedirect(), HTTPCookieProcessor(self.cookies))
        self.seconds = min(CAPTURE_SECONDS, max(1, seconds))
        self.deadline = 0
        self.requests = self.total_bytes = self.documents = 0
        self.records = {}
        self.notes = []
        self.fatal = None
        self.title = ""

    def fetch(self, url, headers):
        """Never use route.fetch/continue: those bypass the numeric socket guard."""
        from .web_media import POLICY
        validate_url(url)
        POLICY.before_request(self.emit)
        if time.monotonic() >= self.deadline:
            raise WebMediaError("動態媒體捕捉已逾時。", code="browser_capture_timeout")
        forwarded = {name: value for name, value in headers.items()
                     if name.lower() not in {"host", "content-length", "connection", "accept-encoding"}}
        forwarded["Accept-Encoding"] = "identity"
        timeout = min(5, max(.1, self.deadline - time.monotonic()))
        with public_network():
            try:
                response = self.opener.open(Request(url, headers=forwarded), timeout=timeout)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.code
                if status == 429:
                    from .request_policy import RateLimited
                    seconds = POLICY.limit(response.headers.get("Retry-After"))
                    raise RateLimited(f"HTTP 429: 平台限制請求次數，安全佇列冷卻 {seconds} 秒。")
                response_headers = dict(response.headers.items())
                mime = response.headers.get("Content-Type", "")
                # Stop at headers: do not download video bytes during discovery.
                if media_type(mime) and 200 <= status < 300:
                    return Resource(status, response_headers)
                chunks, size = [], 0
                while time.monotonic() < self.deadline:
                    chunk = response.read(min(64 * 1024, MAX_RESOURCE_BYTES + 1 - size))
                    if not chunk:
                        break
                    size += len(chunk)
                    self.total_bytes += len(chunk)
                    if size > MAX_RESOURCE_BYTES or self.total_bytes > MAX_TOTAL_BYTES:
                        raise WebMediaError("動態網頁資源超過解析上限。", code="browser_capture_budget")
                    chunks.append(chunk)
                else:
                    raise WebMediaError("動態媒體捕捉已逾時。", code="browser_capture_timeout")
                return Resource(status, response_headers, b"".join(chunks))

    def record(self, url, owner, headers):
        if len(self.records) >= MAX_CANDIDATES or url in self.records:
            return
        clean = {key.title(): value[:8192] for key, value in headers.items()
                 if key.lower() in SAFE_DOWNLOAD_HEADERS and isinstance(value, str)}
        self.records[url] = (owner, clean)

    def route(self, route):
        request = route.request
        self.requests += 1
        if self.fatal or time.monotonic() >= self.deadline or self.requests > MAX_REQUESTS:
            route.abort()
            return
        try:
            url = public_url(request.url)
            if not url or request.method not in {"GET", "HEAD"}:
                route.abort()
                return
            validate_url(url)
            try:
                frame = request.frame
                owner = public_url(frame.url) or self.url
                depth, ancestor = 0, frame.parent_frame
                while ancestor is not None and depth <= 2:
                    depth, ancestor = depth + 1, ancestor.parent_frame
            except Exception:
                owner, depth = self.url, 0
            if depth > 2:
                route.abort()
                return
            headers = request.all_headers()
            if media_extension(url) in STREAM_EXTENSIONS:
                self.record(url, owner, headers)
                route.abort()
                return
            if request.resource_type == "document":
                self.documents += 1
                if self.documents > MAX_DOCUMENTS:
                    route.abort()
                    return
            if request.resource_type in {"image", "font", "texttrack"}:
                route.abort()
                return
            # Segments, keys and browser downloads are not discovery resources.
            if media_extension(url) in {"ts", "m4s", "key"}:
                route.abort()
                return
            response = self.fetch(url, headers)
            lower = {key.lower(): value for key, value in response.headers.items()}
            if media_type(lower.get("content-type", "")) and 200 <= response.status < 300:
                self.record(url, owner, headers)
                route.abort()
                return
            if 300 <= response.status < 400 and lower.get("location"):
                validate_url(urljoin(url, lower["location"]))
            cleaned = {key: value for key, value in response.headers.items()
                       if key.lower() not in {"content-length", "content-encoding", "transfer-encoding", "connection"}}
            route.fulfill(status=response.status, headers=cleaned, body=response.body)
        except Exception as exc:
            from .request_policy import RateLimited
            if isinstance(exc, RateLimited):
                self.fatal = exc
            elif isinstance(exc, WebMediaError) and exc.code in {"browser_capture_budget", "browser_capture_timeout"}:
                self.fatal = exc
            elif len(self.notes) < 12:
                self.notes.append(diagnostic_error(exc))
            route.abort()

    def discover(self):
        if not self.driver or not self.driver.runtime or not chrome_executable():
            raise WebMediaError("動態捕捉需要選配 Playwright 與一般 Chrome；請執行 python tools/manage.py browser-setup。",
                                code="browser_capture_unavailable")
        self.deadline = time.monotonic() + self.seconds
        browser = None
        dom_candidates = {}
        try:
            self.emit({"status_text": "正在使用隔離 Chrome 捕捉動態媒體", "stage": "browser_capture",
                       "capture_timeout": self.seconds})
            browser = self.driver.runtime.chromium.launch(headless=True, channel="chrome", timeout=8000,
                proxy={"server": "http://127.0.0.1:9", "bypass": "<-loopback>"},
                args=["--disable-quic", "--disable-background-networking", "--disable-extensions",
                      "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                      "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
            context = browser.new_context(service_workers="block", accept_downloads=False)
            initial_cookies = [{"name": item.name, "value": item.value, "domain": item.domain,
                "path": item.path or "/", "secure": item.secure, "httpOnly": item.has_nonstandard_attr("HttpOnly")}
                for item in list(self.cookies)[:100] if not item.is_expired()]
            if initial_cookies:
                context.add_cookies(initial_cookies)
            context.set_default_timeout(3000)
            context.route("**/*", self.route)
            # Do not connect_to_server: sockets remain local to the disposable page.
            # Sync close() inside this callback can deadlock the driver on Windows.
            context.route_web_socket("**/*", lambda ws: None)
            context.on("page", lambda page: page.on("download", lambda item: item.cancel()))
            page = context.new_page()
            page.on("popup", lambda popup: popup.close())
            try:
                page.goto(self.url, wait_until="domcontentloaded", timeout=int(self.seconds * 1000))
            except Exception:
                pass  # A media navigation is intentionally aborted once recorded.
            observed_at = None
            while time.monotonic() < self.deadline and self.requests <= MAX_REQUESTS and not self.fatal:
                for frame in page.frames[:MAX_DOCUMENTS]:
                    try:
                        frame.evaluate("""() => { for (const el of document.querySelectorAll('video, audio')) {
                            el.muted = true; const result = el.play(); if (result) result.catch(() => {});
                        } }""")
                    except Exception:
                        pass
                page.wait_for_timeout(250)
                if self.records:
                    observed_at = observed_at or time.monotonic()
                    if time.monotonic() - observed_at >= 2:
                        break
            if self.fatal:
                raise self.fatal
            for frame in page.frames[:MAX_DOCUMENTS]:
                owner = public_url(frame.url)
                if not owner:
                    continue
                try:
                    # Bound the snapshot inside the renderer, before IPC transfer.
                    html = frame.evaluate("() => document.documentElement.outerHTML.slice(0, 1048576)")
                    parser = PlayerHTML(owner)
                    parser.feed(html)
                    parser.close()
                    self.title = self.title or parser.title
                    for item in parser.finish():
                        if media_extension(item.url) in STREAM_EXTENSIONS:
                            dom_candidates[item.url] = item
                except Exception:
                    pass
            # Cookies are ephemeral and domain scoped; never use Chrome profiles.
            for item in context.cookies():
                if len(self.cookies) >= 100 or len(item.get("value", "")) > 8192:
                    break
                self.cookies.set_cookie(http.cookiejar.Cookie(0, item["name"], item["value"], None, False,
                    item["domain"], True, item["domain"].startswith("."), item["path"], True,
                    item["secure"], int(item["expires"]) if item["expires"] > 0 else None,
                    item["expires"] <= 0, None, None, {}, False))
            result = []
            for source in dom_candidates.values():
                if source.priority >= 3:
                    self.record(source.url, source.referer, {})
            for url, (owner, headers) in self.records.items():
                source = dom_candidates.get(url)
                # Unlabelled resources can identify different media in the query.
                # Only DOM/JSON player groups justify treating them as renditions.
                group = source.group if source else selection_id(owner, "network:" + url)
                result.append(MediaCandidate(url, headers.get("Referer", owner), self.title,
                    height=source.height if source else 0, priority=5, group=group, headers=headers))
            if not result:
                code = "browser_capture_budget" if self.requests > MAX_REQUESTS else "browser_media_not_found"
                raise WebMediaError("動態捕捉沒有找到可下載的影音來源；頁面可能需要登入、操作或使用不支援的傳輸。",
                                    code=code, detail=self.diagnostics())
            return sorted(result, key=lambda item: (media_extension(item.url) in {"m3u8", "mpd"}, item.height), reverse=True)
        except WebMediaError:
            raise
        except Exception as exc:
            from .request_policy import RateLimited
            if isinstance(exc, RateLimited):
                raise
            raise WebMediaError("隔離 Chrome 無法完成動態捕捉；請重新安裝選配套件或查看診斷。",
                                code="browser_capture_failed", detail=diagnostic_error(exc)) from exc
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            self.emit({"stage": "browser_capture_finished"})

    def diagnostics(self):
        return (f"Dynamic discovery: requests={self.requests}, candidates={len(self.records)}, bytes={self.total_bytes}.\n"
                + "\n".join(self.notes))[:2000]
