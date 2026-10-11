"""Bounded discovery of media exposed in ordinary HTML and player JSON.

This module has no site-specific rules and does not execute page scripts.
Discovered streams are handed to the existing video download engine.
"""
from __future__ import annotations

import http.cookiejar
import base64
import binascii
import ipaddress
import json
import re
import socket
import time
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urljoin, urlparse, urlunparse
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from .request_policy import POLICY, RateLimited
from .diagnostics import redact_text, redact_url
from .video_quality import source_dimensions
from .media_selection import selection_id

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_PAGES = 6
MAX_DEPTH = 2
MAX_CANDIDATES = 12
MAX_ATTEMPTS = 6
SCAN_SECONDS = 60
USER_AGENT = "Mozilla/5.0 SmartSocialDownloader/1.1"
MEDIA_EXTENSIONS = {"m3u8", "mpd", "mp4", "webm", "mkv", "mov", "m4v", "flv", "ogv", "mp3", "m4a", "aac", "ogg", "opus", "wav", "flac"}
MANIFEST_TYPES = {"application/vnd.apple.mpegurl", "application/x-mpegurl", "application/dash+xml"}


class WebMediaError(RuntimeError):
    def __init__(self, message, *, code="web_media_not_found", detail=""):
        super().__init__(message)
        self.code = code
        self.detail = detail or message


def public_url(value: str, base="") -> str | None:
    """Resolve URLs without changing signed query strings or accepting local URLs."""
    if not isinstance(value, str) or len(value) > 8192:
        return None
    value = re.sub(r"&(?:amp|quot|apos|lt|gt|#\d+|#x[0-9a-fA-F]+);", lambda match: unescape(match[0]), value.strip()).replace("\\/", "/")
    if not value:
        return None
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match[1], 16)), value)
    # Plain URL encodings used in player data; this never evaluates a script.
    for _ in range(2):
        if re.match(r"https?%3a", value, re.I):
            value = unquote(value)
        elif value.startswith(("aHR0cD", "aHR0cH")):
            try:
                decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True).decode("utf-8")
            except (ValueError, binascii.Error):
                break
            if not decoded.startswith(("http://", "https://")):
                break
            value = decoded
        else:
            break
    if any(ord(char) <= 32 or ord(char) == 127 for char in value):
        return None
    try:
        parsed = urlparse(urljoin(base, value))
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password
                or host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost")):
            return None
        parsed.port  # Validate malformed ports as well as the hostname.
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
        return urlunparse(parsed._replace(fragment=""))
    except (ValueError, UnicodeError):
        return None


def validate_target(url: str) -> None:
    if not public_url(url):
        raise WebMediaError("網頁媒體來源網址無效或不是公開網址。", code="web_media_invalid_url")
    parsed = urlparse(url)
    # Also check discovered hostnames before requesting or downloading them.
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise WebMediaError("網頁媒體來源網址無效或不是公開網址。", code="web_media_invalid_url")


def media_extension(url: str) -> str:
    return urlparse(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[-1].lower()


def media_type(value: str) -> bool:
    value = value.lower().split(";", 1)[0].strip()
    return value.startswith(("video/", "audio/")) or value in MANIFEST_TYPES


def diagnostic_url(url: str) -> str:
    """Diagnostics keep the resource path, but never its signed query or credentials."""
    return redact_url(url)[:250]


def diagnostic_error(error) -> str:
    return redact_text(error, limit=450)


@dataclass(frozen=True)
class MediaCandidate:
    url: str
    referer: str
    title: str = ""
    kind: str = "media"
    priority: int = 0
    height: int = 0
    group: str = ""
    headers: dict = field(default_factory=dict, compare=False, repr=False)


class PlayerHTML(HTMLParser):
    def __init__(self, url: str):
        super().__init__(convert_charrefs=True)
        self.url = self.base = url
        self.title = ""
        self._title_parts = []
        self._in_title = False
        self._media_depth = 0
        self._script = None
        self._scripts = []
        self._meta = {}
        self.sources = []
        self.embeds = []
        self._players = 0
        self._group = ""

    def add(self, raw, *, priority=2, height=0, trusted=False, kind="media", group=""):
        url = public_url(raw, self.base)
        if not url:
            return
        if kind == "embed":
            if url not in self.embeds and len(self.embeds) < MAX_PAGES:
                self.embeds.append(url)
            # Player wrappers sometimes put the actual media URL in a query value.
            for _, value in parse_qsl(urlparse(url).query)[:20]:
                nested = public_url(value)
                if nested and media_extension(nested) in MEDIA_EXTENSIONS:
                    self.add(nested, priority=3, group=group or selection_id(self.url, f"embed:{len(self.embeds) - 1}"))
            return
        if not trusted and media_extension(url) not in MEDIA_EXTENSIONS:
            return
        try:
            height = int(height or 0)
        except (ValueError, TypeError):
            height = 0
        height = height or source_dimensions(url).get("height", 0)
        candidate = MediaCandidate(url, self.url, priority=priority, height=height,
                                   group=group or self._group or selection_id(self.url, f"literal:{url}"))
        existing = next((item for item in self.sources if item.url == url), None)
        if existing:
            if (priority, height) > (existing.priority, existing.height):
                self.sources[self.sources.index(existing)] = candidate
        elif len(self.sources) < MAX_CANDIDATES:
            self.sources.append(candidate)
        else:
            lowest = min(self.sources, key=lambda item: (item.priority, item.height))
            if (priority, height) > (lowest.priority, lowest.height):
                self.sources[self.sources.index(lowest)] = candidate

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "base" and attrs.get("href"):
            self.base = public_url(attrs["href"], self.url) or self.base
        elif tag == "title":
            self._in_title = True
        elif tag in {"video", "audio"}:
            self._media_depth += 1
            self._group = selection_id(self.url, f"{tag}:{attrs.get('id') or self._players}")
            self._players += 1
            self.add(attrs.get("src") or attrs.get("data-src"), priority=4, trusted=True)
        elif tag == "source" and self._media_depth:
            self.add(attrs.get("src") or attrs.get("data-src"), priority=4, trusted=True,
                     height=source_dimensions("", attrs).get("height", 0))
        elif tag == "iframe" and str(attrs.get("height", "")) != "0":
            self.add(attrs.get("src") or attrs.get("data-src"), kind="embed")
        elif tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content"):
                self._meta[key] = attrs["content"]
        elif tag == "script" and not attrs.get("src") and len(self._scripts) < 64:
            self._script = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in {"video", "audio", "script", "title"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in {"video", "audio"}:
            self._media_depth = max(0, self._media_depth - 1)
            if not self._media_depth:
                self._group = ""
        elif tag == "script" and self._script is not None:
            self._scripts.append("".join(self._script)[:512_000])
            self._script = None

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
        if self._script is not None:
            self._script.append(data)

    def inspect_json(self, payload):
        stack, budget = [(payload, 0, "", "root")], 4096
        while stack and budget:
            value, depth, group, location = stack.pop()
            budget -= 1
            if depth > 20:
                continue
            if isinstance(value, dict):
                types = value.get("@type", [])
                types = [types] if isinstance(types, str) else types
                video_object = isinstance(types, list) and "VideoObject" in types
                if video_object or isinstance(value.get("sources"), (list, dict)):
                    group = selection_id(self.url, f"json:{location}")
                if video_object:
                    if not self.title and isinstance(value.get("name"), str):
                        self.title = value["name"]
                    self.add(value.get("contentUrl"), priority=4, trusted=True, group=group)
                    self.add(value.get("embedUrl"), kind="embed")
                mime = value.get("type") or value.get("mimeType") or ""
                trusted = isinstance(mime, str) and media_type(mime)
                label = str(value.get("label") or value.get("quality") or "")
                resolution = re.search(r"\b(\d{3,4})p?\b", label)
                height = value.get("height") or (resolution[1] if resolution else 0)
                for key in ("src", "file", "url", "contentUrl", "sources"):
                    self.add(value.get(key), priority=2, height=height, trusted=trusted or (video_object and key == "contentUrl"), group=group)
                for key, child in reversed(list(value.items())[:4096]):
                    if key.lower() not in {"poster", "thumbnail", "thumbnailurl", "image", "advertising", "ads", "adtag"}:
                        stack.append((child, depth + 1, group, f"{location}.{key}"))
            elif isinstance(value, list):
                stack.extend((child, depth + 1, group, f"{location}[{index}]") for index, child in reversed(list(enumerate(value[:4096]))))
            elif isinstance(value, str):
                self.add(value, priority=1, group=group or selection_id(self.url, f"json:{location}"))

    def finish(self, json_body=""):
        self.title = re.sub(r"\s+", " ", self._meta.get("og:title") or self._meta.get("twitter:title") or "".join(self._title_parts)).strip()[:180]
        for key in ("og:video", "og:video:url", "og:video:secure_url", "twitter:player:stream"):
            raw = self._meta.get(key)
            if raw:
                trusted = media_type(self._meta.get("og:video:type", "")) or key == "twitter:player:stream"
                url = public_url(raw, self.base)
                if url:
                    self.add(url, priority=3, trusted=trusted,
                             kind="media" if trusted or media_extension(url) in MEDIA_EXTENSIONS else "embed")
        self.add(self._meta.get("twitter:player"), kind="embed")
        decoder = json.JSONDecoder()
        for script in ([json_body] if json_body else []) + self._scripts:
            # Read JSON script bodies and JSON values inside ordinary assignments;
            # never evaluate JavaScript or require a specific player variable name.
            offset = attempts = 0
            json_ranges = []
            while attempts < 64:
                match = re.search(r"[\[{]", script[offset:])
                if not match:
                    break
                start = offset + match.start()
                attempts += 1
                try:
                    payload, length = decoder.raw_decode(script[start:])
                    self.inspect_json(payload)
                    offset = start + length
                    json_ranges.append((start, offset))
                except (ValueError, RecursionError):
                    offset = start + 1
            # Non-JSON JS settings (e.g. unquoted keys) may still expose literal URLs.
            for match in re.finditer(r'''(["'])([^"'\r\n]{1,8192})\1''', script):
                if any(start <= match.start() < end for start, end in json_ranges):
                    continue  # Keep the structured parser's poster/advertising exclusions.
                raw = match[2]
                if match[1] == '"':
                    try:
                        raw = json.loads(match[0])
                    except ValueError:
                        continue
                self.add(raw, priority=1)
        return sorted(self.sources, key=lambda item: (item.priority, media_extension(item.url) in {"m3u8", "mpd"}, item.height), reverse=True)


class WebMediaDiscovery:
    def __init__(self, url: str, emit, *, embed_supported=None):
        self.url, self.emit = url, emit
        self.embed_supported = embed_supported or (lambda url: False)
        self.cookies = http.cookiejar.CookieJar()
        self.pages = self.candidates = 0
        self.notes = []
        self.title = ""
        self.deadline = time.monotonic() + SCAN_SECONDS

        class Redirects(HTTPRedirectHandler):
            def redirect_request(handler, request, fp, code, message, headers, new_url):
                validate_target(new_url)
                POLICY.before_request(emit)
                return super().redirect_request(request, fp, code, message, headers, new_url)

        self.opener = build_opener(Redirects(), HTTPCookieProcessor(self.cookies))

    def fetch(self, url: str, referer: str):
        validate_target(url)
        POLICY.before_request(self.emit)
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity", "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
        if referer:
            headers["Referer"] = referer
        try:
            response = self.opener.open(Request(url, headers=headers), timeout=15)
        except HTTPError as exc:
            if exc.code == 429:
                seconds = POLICY.limit(exc.headers.get("Retry-After"))
                exc.close()
                raise RateLimited(f"HTTP 429: 平台限制請求次數，安全佇列冷卻 {seconds} 秒。") from exc
            exc.close()
            raise
        with response:
            final_url = response.geturl()
            content_type = response.headers.get_content_type()
            if media_type(content_type):
                return final_url, None, ""
            chunks, size = [], 0
            while time.monotonic() < self.deadline:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_PAGE_BYTES:
                    raise WebMediaError("網頁內容過大，通用解析已停止；請改貼播放器或媒體網址。", code="web_page_too_large")
                chunks.append(chunk)
            else:
                raise WebMediaError("通用網頁解析已逾時；請改貼播放器或媒體網址。", code="web_media_timeout")
            data = b"".join(chunks)
            if data.lstrip().startswith((b"#EXTM3U", b"<MPD", b"<?xml")) and (
                    b"#EXTM3U" in data[:30] or b"<MPD" in data[:1000]):
                return final_url, None, ""
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = data.decode(charset, errors="replace")
            except LookupError:
                text = data.decode("utf-8", errors="replace")
            return final_url, text, content_type

    def discover(self):
        pending = deque([(self.url, "", 0, "")])
        visited, yielded = set(), set()
        while pending and self.pages < MAX_PAGES and self.candidates < MAX_CANDIDATES:
            if time.monotonic() >= self.deadline:
                self.notes.append("Discovery time limit reached")
                break
            url, referer, depth, parent_group = pending.popleft()
            if url in visited:
                continue
            visited.add(url)
            self.pages += 1
            self.emit({"status_text": "正在解析嵌入播放器" if depth else "正在使用通用網頁解析"})
            try:
                final_url, text, content_type = self.fetch(url, referer)
            except RateLimited:
                raise
            except (HTTPError, URLError, OSError, ValueError, WebMediaError) as exc:
                if depth == 0:
                    raise
                self.notes.append(f"{diagnostic_url(url)}: {diagnostic_error(exc)}")
                continue
            if final_url != url and final_url in visited:
                continue
            visited.add(final_url)
            if text is None:
                sources = [MediaCandidate(final_url, referer, self.title)]
                embeds = []
            else:
                parser = PlayerHTML(final_url)
                parser.feed(text)
                parser.close()
                sources = parser.finish(text if content_type == "application/json" or content_type.endswith("+json") else "")
                embeds = parser.embeds if depth < MAX_DEPTH else []
                self.title = self.title or parser.title
            if self.title:
                self.emit({"title": self.title})
            # A wrapper with several independent players must not collapse them
            # into the parent's iframe group. A single player's renditions can.
            inherit_group = parent_group if len({source.group for source in sources}) <= 1 else ""
            for source in sources:
                identity = (source.url, "media")
                if identity in yielded or self.candidates >= MAX_CANDIDATES:
                    continue
                yielded.add(identity)
                self.candidates += 1
                paused_at = time.monotonic()
                yield MediaCandidate(source.url, source.referer, self.title, height=source.height,
                                     priority=source.priority, group=inherit_group or source.group or selection_id(final_url, "direct"))
                self.deadline += time.monotonic() - paused_at
            for index, embed in enumerate(embeds):
                if embed not in visited:
                    group = selection_id(final_url, f"embed:{index}")
                    if not self.embed_supported(embed):
                        pending.append((embed, final_url, depth + 1, group))
                    # First let platform extractors handle a recognized embedded player.
                    identity = (embed, "embed")
                    if identity not in yielded and self.candidates < MAX_CANDIDATES:
                        yielded.add(identity)
                        self.candidates += 1
                        paused_at = time.monotonic()
                        yield MediaCandidate(embed, final_url, self.title, kind="embed", group=group)
                        self.deadline += time.monotonic() - paused_at

    def diagnostics(self) -> str:
        return (f"Generic web media discovery: pages={self.pages}, candidates={self.candidates}.\n" + "\n".join(self.notes))[:2000]
