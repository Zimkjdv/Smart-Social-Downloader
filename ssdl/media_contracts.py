"""Shared source identity, paths, errors and checked download transport."""
from __future__ import annotations
import hashlib
import http.cookiejar
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from .request_policy import RateLimited
from .diagnostics import redact_text
from . import request_policy

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}

_PLATFORM_DOMAINS = {
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com", "ytimg.com", "googlevideo.com"),
    "twitter": ("x.com", "twitter.com", "t.co", "twimg.com"),
    "tiktok": ("tiktok.com",), "douyin": ("douyin.com", "iesdouyin.com"),
    "instagram": ("instagram.com", "cdninstagram.com"),
    "threads": ("threads.net", "threads.com"),
    "facebook": ("facebook.com", "fb.watch", "fbcdn.net"),
    "pinterest": ("pinterest.com", "pin.it", "pinimg.com"),
    "reddit": ("reddit.com", "redd.it", "redditmedia.com", "redditstatic.com"),
    "vimeo": ("vimeo.com", "vimeocdn.com"),
    "twitch": ("twitch.tv", "twitchcdn.net"),
    "bilibili": ("bilibili.com", "b23.tv", "bilivideo.com", "hdslb.com"),
}

def platform_folder(url: str, category="") -> str:
    """Use a stable Windows-safe platform name across the download engines."""
    name = str(category or "").lower()
    if name in {"", "generic", "ytdl"}:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        name = next((folder for folder, domains in _PLATFORM_DOMAINS.items()
                     if any(host == domain or host.endswith("." + domain) for domain in domains)), host or "web")
    name = {"x": "twitter", "抖音": "douyin"}.get(name, name)
    name = re.sub(r'[^\w.-]', "_", name).strip(" .")[:80] or "web"
    if re.fullmatch(r"con|prn|aux|nul|com[0-9]|lpt[0-9]", name.split(".", 1)[0], re.I):
        name = "site_" + name
    return name


def platform_directory(url: str, output_dir: Path) -> Path:
    root = output_dir.resolve()
    directory = root / platform_folder(url)
    if not directory.resolve().is_relative_to(root):
        raise DownloadError("檔案路徑不在此項目的下載資料夾內。")
    return directory


class DownloadError(RuntimeError):
    def __init__(self, message, files=(), *, code="download_failed", detail=""):
        super().__init__(message)
        self.files = list(files)
        self.code = code if isinstance(code, str) else "download_failed"
        self.detail = detail or message


def error_info(exc) -> dict:
    """Keep an actionable explanation separate from the engine's diagnostic text."""
    detail = str(getattr(exc, "detail", None) or exc).strip()[:2000]
    code = getattr(exc, "code", "download_failed")
    if not isinstance(code, str):
        code = "download_failed"
    message = str(exc).strip()[:500] or "下載失敗，請重試。"
    lowered = detail.lower()
    if "guest_token" in lowered:
        code = "x_guest_auth"
        message = "X 訪客驗證未回傳 guest_token。請按「連接 Chrome 登入」，完成登入後重試。"
    elif code == "rate_limited" or re.search(r"\b429\b|rate[ _-]?limit", lowered):
        code, message = "rate_limited", "平台限制請求次數，安全佇列已進入冷卻；請稍後再按重新下載。"
    elif code == "unsupported_url" or (code == "download_failed" and "unsupported url" in lowered):
        code, message = "unsupported_url", "下載引擎不支援此網址；可按重新下載嘗試通用網頁解析。"
    elif code == "download_failed":
        if any(text in lowered for text in ("login", "sign in", "authentication", "cookies", "unauthorized", "401")):
            code, message = "login_required", "平台要求登入或登入已失效；X 連結可按「連接 Chrome 登入」後重試。"
        elif "403" in lowered or "forbidden" in lowered:
            code, message = "access_denied", "平台拒絕存取。請確認內容權限；X 連結可按「連接 Chrome 登入」後重試。"
        elif "404" in lowered or "not found" in lowered or "deleted" in lowered:
            code, message = "not_found", "平台找不到這則內容。請確認網址與貼文是否仍存在。"
        elif isinstance(exc, URLError) or "timed out" in lowered or "connection" in lowered:
            code, message = "network", "網路連線失敗或逾時，請確認連線後重試。"
    if code.startswith("x_"):
        message = message.replace("可在設定加入 X Cookie 後重試", "可按「連接 Chrome 登入」後重試")
    return {"error": redact_text(message, limit=500), "error_detail": redact_text(detail, limit=2000), "error_code": code}


def x_cookie_values(filename: str) -> dict:
    """Read only the explicitly selected file and retain only X session cookies."""
    path = Path(filename).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise DownloadError("X Cookie 檔案不存在或過大。請選擇 Netscape 格式的 cookies.txt。", code="x_cookies_invalid")
    jar = http.cookiejar.MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=False)
    except (OSError, http.cookiejar.LoadError) as exc:
        raise DownloadError("無法讀取 X Cookie；請使用 Netscape 格式的 cookies.txt。", code="x_cookies_invalid") from exc
    values = {cookie.name: cookie.value for cookie in jar
              if cookie.domain.lstrip(".").lower() in {"x.com", "twitter.com"}
              and cookie.name in {"auth_token", "ct0", "twid"}}
    if not values.get("auth_token"):
        raise DownloadError("Cookie 檔案沒有有效的 X 登入 auth_token。請登入 X 後重新匯出。", code="x_cookies_invalid")
    return values


def original_image_url(url: str) -> str | None:
    """Request X's orig asset rather than a resized CDN preview."""
    parsed = urlparse(url)
    path = parsed.path
    if (parsed.hostname or "").lower() == "pbs.twimg.com" and path.startswith("/media/"):
        # Both the old .jpg:large and newer ?format=jpg&name=small URL styles exist.
        path = re.sub(r":(?:orig|large|medium|small|thumb|\d+x\d+)$", "", path)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        suffix = Path(path).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            query.setdefault("format", suffix[1:])
            path = path[:-len(suffix)]
        if "format" not in query:
            return None
        query["name"] = "orig"
        return urlunparse(parsed._replace(path=path, query=urlencode(query), fragment=""))
    if Path(path).suffix.lower() in IMAGE_EXTENSIONS:
        return url
    return None


def _relative_files(paths, output_dir: Path) -> list[str]:
    result = []
    for raw in paths:
        target = Path(raw).resolve()
        if target.is_file() and target.is_relative_to(output_dir.resolve()):
            name = str(target.relative_to(output_dir.resolve()))
            if name not in result:
                result.append(name)
    return result


def paced_urlopen(request, *, timeout=25, emit=None):
    request_policy.POLICY.before_request(emit)
    try:
        return urlopen(request, timeout=timeout)
    except HTTPError as exc:
        if exc.code == 429:
            seconds = request_policy.POLICY.limit(exc.headers.get("Retry-After"))
            exc.close()
            raise RateLimited(f"HTTP 429: 平台限制請求次數，安全佇列冷卻 {seconds} 秒。") from exc
        raise


def _image_source_key(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() == "pbs.twimg.com":
        parsed = parsed._replace(query=urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True))))
    normalized = urlunparse(parsed._replace(fragment=""))
    return hashlib.sha256(normalized.encode()).hexdigest()


def source_key(url: str) -> str:
    """Identify a queue source; preserve meaningful parameters on other platforms."""
    post_id = x_post_id(url)
    if post_id:
        return "x-post:" + post_id
    image_url = original_image_url(url)
    if image_url:
        return "image:" + _image_source_key(image_url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com":
        parts = parsed.path.strip("/").split("/")
        video_id = parse_qs(parsed.query).get("v", [None])[0] if parsed.path == "/watch" else (
            parts[1] if len(parts) == 2 and parts[0] in {"shorts", "live", "embed"} else None)
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return "youtube:" + video_id
    return "url:" + urlunparse(parsed._replace(fragment=""))


def _same_output_directory(record: dict, root: Path) -> bool:
    try:
        return bool(record.get("output_dir")) and os.path.normcase(str(Path(record["output_dir"]).resolve())) == os.path.normcase(str(root.resolve()))
    except (OSError, ValueError, TypeError, RuntimeError):
        return False


def x_post_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        return None
    match = re.fullmatch(r"/(?:[^/]+|i/web)/status/(\d+)(?:/(?:photo|video)/\d+)?/?", parsed.path)
    return match[1] if match else None
