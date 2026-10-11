"""Save the media bytes exposed by a platform, without image or video re-encoding."""
from __future__ import annotations

import hashlib
import http.cookiejar
import json
import logging
import math
import mimetypes
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .request_policy import POLICY, RateLimited, REQUEST_INTERVAL
from .x_profiles import normalize_account, ProfileArchive
from .image_history import ImageHistory
from .media_manifest import MediaManifest
from .diagnostics import redact_text
from .video_quality import (install_video_quality, enrich_video_formats, video_quality_text,
                            validate_video_quality, video_format, select_video_variant, rendition_dimensions)
from .web_media import (WebMediaDiscovery, WebMediaError, MediaCandidate, MAX_ATTEMPTS,
                       USER_AGENT, validate_target, diagnostic_error)

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from gallery_dl import config as gallery_config, extractor as gallery_extractor, job as gallery_job
    from gallery_dl.version import __version__ as gallery_version
except ImportError:
    gallery_config = gallery_extractor = gallery_job = None
    gallery_version = ""

BEST_VIDEO_FORMAT = "bv*+ba/b"
STREAM_INTEGRITY_OPTIONS = {"skip_unavailable_fragments": False, "fragment_retries": 3}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}
_gallery_lock = threading.Lock()

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


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return None


def engine_status() -> dict:
    return {
        "video": yt_dlp is not None,
        "images": gallery_job is not None,
        "ffmpeg": ffmpeg_path() is not None,
        "video_version": getattr(getattr(yt_dlp, "version", None), "__version__", ""),
        "image_version": gallery_version,
    }


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
    POLICY.before_request(emit)
    try:
        return urlopen(request, timeout=timeout)
    except HTTPError as exc:
        if exc.code == 429:
            seconds = POLICY.limit(exc.headers.get("Retry-After"))
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


def download_image(url: str, output_dir: Path, emit, *, force=False,
                   history_file: Path | None = None, known_jobs=()) -> dict:
    original = original_image_url(url) or url
    is_x_image = (urlparse(original).hostname or "").lower() == "pbs.twimg.com"
    quality = "X 原尺寸圖片（orig）" if is_x_image else "圖片直連原格式 · 保留來源內容"
    source_key = _image_source_key(original)
    archive, remembered = None, None
    warnings = []
    try:
        if history_file is not None:
            try:
                archive = ImageHistory(history_file, output_dir)
                remembered = archive.lookup(source_key, verify=False)
                cached = archive.lookup(source_key) if not force else None
                if not cached and not force:
                    for old in known_jobs:
                        old_source = original_image_url(str(old.get("url", "")))
                        files = old.get("files", [])
                        if (not old_source or _image_source_key(old_source) != source_key
                                or not _same_output_directory(old, output_dir) or len(files) != 1
                                or type(old.get("size_bytes")) is not int or old["size_bytes"] <= 0):
                            continue
                        path = (output_dir / files[0]).resolve()
                        if (Path(files[0]).is_absolute() or not path.is_relative_to(output_dir.resolve()) or not path.is_file()
                                or path.stat().st_size != old["size_bytes"]):
                            continue
                        archive.record(source_key, {"title": old.get("title", ""),
                            "quality": old.get("quality") or quality, "files": files})
                        cached = archive.lookup(source_key)
                        break
                if cached:
                    emit({"title": cached["title"], "files": cached["files"], "quality": cached["quality"],
                          "status_text": "已略過，檔案已存在", "downloaded_bytes": cached["size_bytes"],
                          "total_bytes": cached["size_bytes"]})
                    return {**cached, "skipped": True}
            except (OSError, ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error):
                warnings.append("無法讀取已下載圖片紀錄，本次會重新下載。")
        result = _download_image_bytes(original, output_dir, emit, quality, remembered)
        if archive is not None:
            try:
                archive.record(source_key, result)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                warnings.append("檔案已保存，但無法更新已下載紀錄；下次可能重新下載。")
        result["warnings"].extend(warnings)
        return result
    finally:
        if archive is not None:
            archive.close()


def _download_image_bytes(original: str, output_dir: Path, emit, quality: str, remembered=None) -> dict:
    request = Request(original, headers={"User-Agent": "Mozilla/5.0 SmartSocialDownloader/1.1", "Accept-Encoding": "identity"})
    emit({"title": "正在下載圖片來源檔", "quality": quality})
    with paced_urlopen(request, timeout=25, emit=emit) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise DownloadError("此網址未回傳圖片檔，請貼上圖片或貼文的完整網址。")
        parsed = urlparse(original)
        extension = mimetypes.guess_extension(content_type) or ".img"
        if extension == ".jpe":
            extension = ".jpg"
        source_name = Path(unquote(parsed.path)).stem or "image"
        source_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", source_name).strip(" .")[:90] or "image"
        folder = platform_directory(original, output_dir).relative_to(output_dir.resolve())
        filename = str(folder / f"{source_name} [{hashlib.sha256(original.encode()).hexdigest()[:10]}]{extension}")
        if (remembered and Path(remembered["files"][0]).parent == folder
                and Path(remembered["files"][0]).suffix.lower() == extension):
            filename = remembered["files"][0]
        destination = output_dir / filename
        partial = destination.with_name(destination.name + ".part")
        root = output_dir.resolve()
        if not destination.resolve().is_relative_to(root) or not partial.resolve().is_relative_to(root):
            raise DownloadError("檔案路徑不在此項目的下載資料夾內。")
        destination.parent.mkdir(parents=True, exist_ok=True)
        total_header = response.headers.get("Content-Length", "")
        total = int(total_header) if total_header.isdigit() else None
        downloaded = 0
        started = time.monotonic()
        with partial.open("wb") as target:
            while chunk := response.read(128 * 1024):
                # Deliberately copy bytes; no imaging library or encoder is involved.
                target.write(chunk)
                downloaded += len(chunk)
                elapsed = max(time.monotonic() - started, .001)
                emit({"filename": filename, "total_bytes": total, "downloaded_bytes": downloaded, "speed": downloaded / elapsed})
        if not downloaded or (total is not None and downloaded != total):
            raise DownloadError("圖片下載不完整，請重試。")
        partial.replace(destination)
    return {"title": source_name, "files": [filename], "quality": quality, "warnings": []}


def video_options(output_dir: Path, emit, paths: list, *, force=False, video_quality="best") -> dict:
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise DownloadError("需要安裝 FFmpeg 才能保存最高畫質影音。請重新執行 start.bat 更新下載引擎。")

    def progress(data):
        info = data.get("info_dict") or {}
        quality = video_quality_text(info)
        emit({
            "title": info.get("title", ""), "quality": quality,
            "filename": Path(data["filename"]).name if data.get("filename") else "",
            "total_bytes": data.get("total_bytes") or data.get("total_bytes_estimate"),
            "downloaded_bytes": data.get("downloaded_bytes", 0),
            "speed": data.get("speed"), "eta": data.get("eta"),
            "status_text": "合併影音中（保留編碼）" if data.get("status") == "finished" else "下載中",
        })

    return {
        **STREAM_INTEGRITY_OPTIONS,
        "format": video_format(video_quality),
        "format_sort": ["res"],
        "ffmpeg_location": ffmpeg,
        "outtmpl": str(output_dir / "%(title).120B [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "ignoreerrors": False,
        "continuedl": not force,
        "overwrites": bool(force),
        "retries": 3,
        "concurrent_fragment_downloads": 1,
        "hls_prefer_native": True,
        "sleep_interval_requests": REQUEST_INTERVAL,
        "retry_sleep_functions": {"http": lambda n: min(30, 2 ** n),
                                  "fragment": lambda n: min(30, 2 ** n)},
        "socket_timeout": 25,
        "fixup": "never",
        "postprocessors": [],
        "js_runtimes": {"deno": {}, "node": {}},
        "progress_hooks": [progress],
        "post_hooks": [paths.append],
        "postprocessor_hooks": [lambda event: emit({"stage": "postprocessing", "status_text": "合併影音中（保留編碼）"})],
    }


def _video_error_code(exc) -> str:
    """Classify the original extractor exception, including yt-dlp's wrapper."""
    pending, visited = [exc], set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, RateLimited):
            return "rate_limited"
        if getattr(current, "code", None) == "unsafe_target":
            return "unsafe_target"
        if yt_dlp is not None and isinstance(current, yt_dlp.utils.UnsupportedError):
            return "unsupported_url"
        for name in ("__cause__", "__context__", "cause"):
            cause = getattr(current, name, None)
            if isinstance(cause, BaseException):
                pending.append(cause)
        original = getattr(current, "exc_info", None)
        if isinstance(original, tuple) and len(original) > 1 and isinstance(original[1], BaseException):
            pending.append(original[1])
    return "unsupported_url" if re.search(r"Unsupported URL:|No suitable extractor.*found for URL", str(exc), re.I) else "download_failed"


def download_video(url: str, output_dir: Path, emit, *, force=False,
                   source_url="", candidate: MediaCandidate | None = None, cookies=None, video_quality="best", selected_media="") -> dict:
    if yt_dlp is None:
        raise DownloadError("尚未安裝影片下載引擎，請執行 start.bat。")
    paths, warnings = [], []
    reported_existing = transferred = False

    class CaptureDownloader(yt_dlp.YoutubeDL):
        def process_ie_result(self, ie_result, download=True, extra_info=None):
            if ie_result.get("_type", "video") == "video":
                enrich_video_formats(ie_result, candidate)
            if candidate and ie_result.get("_type", "video") == "video":
                ie_result = dict(ie_result)
                if candidate.title:
                    ie_result["title"] = candidate.title
                ie_result["webpage_url"] = source_url
                if candidate.kind == "media":
                    # Query parameters can identify content or rendition. Without
                    # a provider-specific contract even a token may be semantic;
                    # prefer a new file to incorrectly skipping different media.
                    resource = urlunparse(urlparse(url)._replace(fragment=""))
                    key = source_key(source_url) + "\n" + resource
                    ie_result["id"] = "web-" + hashlib.sha256(key.encode()).hexdigest()[:12]
            return super().process_ie_result(ie_result, download, extra_info)

        def report_file_already_downloaded(self, filename):
            nonlocal reported_existing
            reported_existing = True
            return super().report_file_already_downloaded(filename)

        def dl(self, *args, **kwargs):
            nonlocal transferred
            result = super().dl(*args, **kwargs)
            transferred = transferred or bool(result[1])
            return result

    class Logger:
        def debug(self, message):
            pass

        def warning(self, message):
            warnings.append(redact_text(message, limit=1000))

        def error(self, message):
            pass

    directory = platform_directory(source_url or url, output_dir)
    if video_quality != "best":
        directory = directory / f"quality-{validate_video_quality(video_quality)}p"
    if selected_media:
        directory = directory / f"media-{selected_media}"

    def video_progress(event):
        if event.get("filename"):
            event = {**event, "filename": str(directory.relative_to(output_dir.resolve()) / event["filename"])}
        emit(event)

    options = video_options(directory, video_progress, paths, force=force, video_quality=video_quality)
    options["logger"] = Logger()
    if candidate:
        options["http_headers"] = {"User-Agent": USER_AGENT, "Referer": candidate.referer, **candidate.headers}
        options["playlistend"] = 1
        # Different alternatives must never append to each other's partial file.
        options["continuedl"] = False
    with CaptureDownloader(options) as downloader:
        install_video_quality(downloader, selected_media, allow_selection=True, select_single=candidate is None)
        POLICY.wrap_yt_dlp(downloader, emit)
        if cookies is not None:
            for cookie in cookies:
                downloader.cookiejar.set_cookie(cookie)
        try:
            target = yt_dlp.utils.smuggle_url(url, {"referer": candidate.referer}) if candidate and candidate.kind == "media" else url
            info = downloader.extract_info(target, download=True)
        except Exception as exc:
            from .media_selection import SelectionRequired
            if isinstance(exc, SelectionRequired):
                raise
            if video_quality != "best" and "Requested format is not available" in str(exc):
                raise DownloadError("平台未提供符合畫質上限的影片，或沒有回報解析度；請改選最高畫質。",
                                    _relative_files(paths, output_dir), code="quality_unavailable", detail=str(exc)) from exc
            raise DownloadError(str(exc), _relative_files(paths, output_dir), code=_video_error_code(exc)) from exc
    files = _relative_files(paths, output_dir)
    if not files:
        raise DownloadError("沒有取得可保存的影片檔案。")
    quality = video_quality_text(info)
    skipped = reported_existing and not transferred and not (info or {}).get("__real_download")
    return {"title": (info or {}).get("title", ""), "files": files, "quality": quality,
            "warnings": warnings, "skipped": skipped, "engine": "yt-dlp",
            "media_id": str((info or {}).get("id", ""))}


@lru_cache(maxsize=1)
def _embed_extractors():
    from yt_dlp.extractor import gen_extractor_classes
    return tuple(extractor for extractor in gen_extractor_classes() if extractor.ie_key() != "Generic")


def download_web_media(url: str, output_dir: Path, emit, *, force=False, video_quality="best", selected_media="",
                       dynamic_capture=False, browser=None, _dynamic_only=False, _attempt_budget=MAX_ATTEMPTS) -> dict:
    discovery = WebMediaDiscovery(url, emit, embed_supported=lambda candidate:
        any(extractor.suitable(candidate) for extractor in _embed_extractors()))
    attempts = quality_errors = 0
    used_dynamic = False
    try:
        from .media_selection import SelectionRequired, choice
        groups = {}
        for candidate in (() if _dynamic_only else discovery.discover()):
            if candidate.kind == "embed" and not any(extractor.suitable(candidate.url) for extractor in _embed_extractors()):
                continue
            groups.setdefault(candidate.group, []).append(candidate)
        if dynamic_capture and (_dynamic_only or not groups or selected_media and selected_media not in groups):
            from .browser_media import BrowserMediaDiscovery
            discovery = BrowserMediaDiscovery(url, emit, browser, cookies=discovery.cookies)
            groups, used_dynamic = {}, True
            for candidate in discovery.discover():
                groups.setdefault(candidate.group, []).append(candidate)
        if len(groups) > 1 or selected_media and selected_media not in groups:
            if selected_media not in groups:
                if not groups:
                    raise DownloadError("選擇的播放器已變更，請重新解析網址。", code="media_selection_changed")
                raise SelectionRequired([choice(identifier, items[0].title, items[0].url,
                    variants=len(items), kind=items[0].kind) for identifier, items in groups.items()])
        candidates = groups.get(selected_media, next(iter(groups.values()), []))
        for candidate in candidates:
            if candidate.kind == "embed" and not any(extractor.suitable(candidate.url) for extractor in _embed_extractors()):
                continue  # Unknown embeds are parsed by the discovery iterator next.
            if attempts >= _attempt_budget:
                discovery.notes.append("Media attempt limit reached")
                break
            attempts += 1
            emit({"status_text": "正在下載通用解析找到的媒體"})
            try:
                validate_target(candidate.url)
                return download_video(candidate.url, output_dir, emit, force=force,
                                      source_url=url, candidate=candidate, cookies=discovery.cookies, video_quality=video_quality,
                                      selected_media=selected_media)
            except DownloadError as exc:
                if exc.code == "rate_limited" or exc.files:
                    raise
                if exc.code == "quality_unavailable":
                    quality_errors += 1
                discovery.notes.append(diagnostic_error(exc))
            except (OSError, WebMediaError) as exc:
                discovery.notes.append(diagnostic_error(exc))
    except WebMediaError as exc:
        raise DownloadError(str(exc), code=exc.code, detail=discovery.diagnostics() + "\n" + exc.detail) from exc
    except HTTPError as exc:
        raise DownloadError(str(exc), detail=discovery.diagnostics() + "\n" + diagnostic_error(exc)) from exc
    except (URLError, OSError) as exc:
        raise DownloadError("網路連線失敗或逾時，請確認連線後重試。", code="network",
                            detail=discovery.diagnostics() + "\n" + diagnostic_error(exc)) from exc
    except ValueError as exc:
        raise DownloadError("網頁回傳的播放器資料無法解析。", code="web_media_invalid_response",
                            detail=discovery.diagnostics() + "\n" + diagnostic_error(exc)) from exc
    if dynamic_capture and not used_dynamic and attempts < _attempt_budget:
        return download_web_media(url, output_dir, emit, force=force, video_quality=video_quality,
            selected_media=selected_media, dynamic_capture=True, browser=browser, _dynamic_only=True,
            _attempt_budget=_attempt_budget - attempts)
    if attempts and quality_errors == attempts:
        raise DownloadError("平台未提供符合畫質上限的影片，或沒有回報解析度；請改選最高畫質。",
                            code="quality_unavailable", detail=discovery.diagnostics())
    if attempts:
        raise DownloadError("已找到媒體來源，但目前無法下載。請查看詳細原因。", code="web_media_failed", detail=discovery.diagnostics())
    raise DownloadError("通用解析未找到可下載的媒體來源；頁面可能需要動態播放或登入。",
                        code="web_media_not_found", detail=discovery.diagnostics())


def configure_gallery(output_dir: Path, *, force=False, x_cookie_file="", x_cookies=None, video_quality="best") -> None:
    # Use the app's own settings, without loading external configs or postprocessors.
    gallery_config.clear()
    for key, value in {"base-directory": str(output_dir), "fallback": False, "postprocessors": [], "timeout": 25, "retries": 3, "skip": not force,
                       "async": False, "sleep-request": REQUEST_INTERVAL}.items():
        gallery_config.set(("extractor",), key, value)
    for key, value in {"size": ["orig"], "videos": True, "previews": False, "conversations": False, "quoted": False, "ratelimit": "abort", "retries-api": 3}.items():
        gallery_config.set(("extractor", "twitter"), key, value)
    if x_cookies or x_cookie_file:
        gallery_config.set(("extractor", "twitter"), "cookies", dict(x_cookies) if x_cookies else x_cookie_values(x_cookie_file))
        gallery_config.set(("extractor", "twitter"), "cookies-update", False)
    gallery_config.set(("downloader", "http"), "progress", .5)
    gallery_config.set(("downloader", "ytdl"), "format", video_format(video_quality))
    gallery_config.set(("downloader", "ytdl"), "raw-options", {
        **STREAM_INTEGRITY_OPTIONS,
        "format": video_format(video_quality), "ffmpeg_location": ffmpeg_path(),
        "format_sort": ["res"],
        "fixup": "never", "postprocessors": [], "ignoreerrors": False,
        "overwrites": bool(force), "continuedl": not force,
        "js_runtimes": {"deno": {}, "node": {}},
        "concurrent_fragment_downloads": 1, "hls_prefer_native": True,
        "sleep_interval_requests": REQUEST_INTERVAL,
    })


def _pace_gallery(extr, emit, video_quality="best"):
    if video_quality != "best" and extr.category == "twitter" and hasattr(extr, "_extract_media"):
        extract_media = extr._extract_media

        def limited_media(tweet, entities, files):
            limited = []
            for item in entities:
                info = item.get("video_info")
                if info:
                    variants = [variant for variant in info.get("variants", [])
                                if variant.get("content_type") == "video/mp4"]
                    if len(variants) == 1:
                        variants = [{**variants[0], "height": (item.get("original_info") or {}).get("height")}]
                    try:
                        selected = select_video_variant(variants, video_quality)
                    except ValueError as exc:
                        raise DownloadError(str(exc), code="quality_unavailable") from exc
                    dimensions = rendition_dimensions(selected.get("url", ""))
                    item = {**item, "video_info": {**info, "variants": [selected]},
                            "original_info": {**(item.get("original_info") or {}), **dimensions}}
                limited.append(item)
            return extract_media(tweet, limited, files)

        extr._extract_media = limited_media
    original_init_session = extr._init_session

    def init_session():
        original_init_session()
        POLICY.wrap_session(extr.session, emit)

    extr._init_session = init_session
    original_initialize = extr.initialize

    def initialize():
        if extr.session is not None:
            POLICY.wrap_session(extr.session, emit)
        return original_initialize()

    extr.initialize = initialize


def download_gallery(extractor, output_dir: Path, emit, *, video_quality="best") -> dict:
    paths, messages = [], []
    downloaded_paths, skipped_paths = set(), set()
    title = ""
    thread_id = threading.get_ident()

    class CaptureLogs(logging.Handler):
        def emit(self, record):
            if record.thread == thread_id and record.levelno >= logging.WARNING:
                messages.append(redact_text(record.getMessage(), limit=1000))

    class Output:
        def start(self, path):
            emit({"filename": Path(path).name, "downloaded_bytes": 0, "total_bytes": None, "status_text": "下載原尺寸媒體"})

        def progress(self, total, downloaded, speed):
            emit({"total_bytes": total, "downloaded_bytes": downloaded, "speed": speed})

        def success(self, path):
            paths.append(path)
            downloaded_paths.add(os.path.normcase(str(Path(path).resolve())))
            emit({"files": _relative_files(paths, output_dir), "status_text": "媒體檔案已儲存"})

        def skip(self, path):
            if Path(path).is_file():
                paths.append(path)
                skipped_paths.add(os.path.normcase(str(Path(path).resolve())))
                emit({"files": _relative_files(paths, output_dir), "status_text": "已略過，檔案已存在"})

    class CaptureJob(gallery_job.DownloadJob):
        def __init__(self, url, parent=None):
            super().__init__(url, parent)
            self.out = Output()
            # Retain account/album subfolders, ensuring a platform is always first.
            folder = platform_folder(self.extractor.url, self.extractor.category)
            parts = tuple(self.extractor.directory_fmt or ())
            if parts and (parts[0] == "{category}" or parts[0].lower() == folder):
                parts = parts[1:]
            self.extractor.directory_fmt = ((folder, *parts) if video_quality == "best"
                else (folder, f"quality-{validate_video_quality(video_quality)}p", *parts))
            # Attach before initialize() so platform-specific _init() calls are paced too.
            _pace_gallery(self.extractor, emit, video_quality)

        def handle_url(self, url, metadata):
            video_extensions = {"mp4", "webm", "mkv", "mov", "m4v", "flv", "ogv"}
            extension = str(metadata.get("extension") or Path(urlparse(url).path).suffix.lstrip(".")).lower()
            if video_quality != "best" and not url.startswith("ytdl:") and extension in video_extensions:
                height = rendition_dimensions(url).get("height") or metadata.get("height")
                if type(height) not in {int, float} or not 0 < height <= int(video_quality):
                    raise DownloadError("平台未提供符合畫質上限的影片，或沒有回報解析度；請改選最高畫質。",
                                        _relative_files(paths, output_dir), code="quality_unavailable")
            return super().handle_url(url, metadata)

        def get_downloader(self, scheme):
            instance = super().get_downloader(scheme)
            if instance and scheme == "ytdl" and not getattr(instance, "_ssdl_paced", False):
                original_prepare = instance._prepare

                def prepare(downloader):
                    install_video_quality(downloader)
                    POLICY.wrap_yt_dlp(downloader, emit)
                    return original_prepare(downloader)

                instance._prepare = prepare
                instance._ssdl_paced = True
            return instance

        def handle_directory(self, metadata):
            nonlocal title
            content = metadata.get("title") or metadata.get("content") or metadata.get("description")
            if content:
                title = str(content).replace("\n", " ")[:180]
            super().handle_directory(metadata)
            quality_label = ("平台提供的最高可用版本 · 保留原格式" if video_quality == "best"
                             else f"原尺寸圖片 / 影片上限 {video_quality}p · 保留原格式")
            emit({"title": title, "quality": quality_label, "file_count": metadata.get("count")})

    handler = CaptureLogs()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        downloader = CaptureJob(extractor)
        status = downloader.run()
    except RateLimited as exc:
        raise DownloadError(str(exc), _relative_files(paths, output_dir), code="rate_limited") from exc
    finally:
        root_logger.removeHandler(handler)
    files = _relative_files(paths, output_dir)
    if status:
        detail = next((message for message in reversed(messages) if re.search(r"\b429\b|rate[ _-]?limit", message, re.I)),
                      messages[-1] if messages else "平台無法提供可下載媒體；可能需要登入或內容已失效。")
        raise DownloadError(detail, files)
    if not files:
        raise DownloadError("貼文內沒有可取得的媒體檔案，或平台要求登入。")
    is_twitter = extractor.category == "twitter"
    quality = "X 圖片 orig / 影片最高位元率 · 保留原格式" if is_twitter else "平台提供的最高可用版本 · 保留原格式"
    if video_quality != "best":
        quality = f"原尺寸圖片 / 影片上限 {video_quality}p · 保留原格式"
    return {"title": title, "files": files, "quality": quality, "warnings": messages,
            "skipped": bool(skipped_paths) and not downloaded_paths,
            "skipped_file_count": len(skipped_paths - downloaded_paths),
            "downloaded_file_count": len(downloaded_paths), "engine": "gallery-dl"}


def download_x_account(url: str, output_dir: Path, emit, *, archive_file: Path,
                       before_post, checkpoint, x_cookie_file="", x_cookies=None,
                       previous_files=(), known_jobs=()) -> dict:
    """Scan a complete visible media manifest before downloading its missing files."""
    if gallery_extractor is None:
        raise DownloadError("請重新執行 start.bat 安裝 X 下載引擎。")
    if not (x_cookie_file or x_cookies):
        raise DownloadError("下載 X 帳號媒體需要登入，請先按「連接 Chrome 登入」。", code="x_login_required")
    from gallery_dl.extractor.common import Extractor, Message

    _, account = normalize_account(url)
    output_dir.mkdir(parents=True, exist_ok=True)
    root = output_dir.resolve()
    known_posts = {}
    for old in known_jobs:
        post_id = x_post_id(str(old.get("url", "")))
        if post_id and _same_output_directory(old, root):
            known_posts.setdefault(post_id, []).append(old)
    saved = {}
    for name in previous_files:
        try:
            target = (root / name).resolve()
            if target.is_relative_to(root) and target.is_file():
                saved[name] = target.stat().st_size
        except (OSError, ValueError, TypeError, RuntimeError):
            continue
    processed = skipped = downloaded_posts = 0
    scanned_posts = scanned_files = existing_files = downloaded_files = 0
    total_posts = total_files = None
    scan_complete = False
    last_scan_report = 0.0
    saved_total = sum(saved.values())
    pending_files = {}
    messages = []
    thread_id = threading.get_ident()
    quality = "X 圖片 orig / 影片最高位元率 · 保留原格式"

    def remember(entries):
        nonlocal saved_total
        for entry in entries:
            name, size = entry["name"], entry["size"]
            saved_total += size - saved.get(name, 0)
            saved[name] = size

    def report(stage="scanning", *, force=True, **extra):
        nonlocal last_scan_report
        if stage == "scanning" and not force:
            now = time.monotonic()
            if now - last_scan_report < .5:
                return
            last_scan_report = now
        emit({"files": list(saved), "aggregate_bytes": saved_total,
              "downloaded_bytes": 0,
              "profile_posts": processed, "profile_skipped": skipped,
              "profile_downloaded_posts": downloaded_posts, "profile_stage": stage,
              "profile_scanned_posts": scanned_posts, "profile_scanned_files": scanned_files,
              "profile_scan_complete": scan_complete,
              "profile_total_posts": total_posts, "profile_total_files": total_files,
              "profile_existing_files": existing_files, "profile_downloaded_files": downloaded_files,
              "profile_completed_files": existing_files + downloaded_files,
              "profile_files_to_download": max(0, (total_files if scan_complete else scanned_files) - existing_files),
              "quality": quality, **extra})

    def file_progress(data):
        # A post's title/file list must not replace the account's aggregate record.
        for name in data.get("files", ()):
            target = (root / name).resolve()
            if target.is_relative_to(root) and target.is_file():
                pending_files[name] = target.stat().st_size
        data = {key: value for key, value in data.items() if key not in {"title", "files", "file_count"}}
        data["aggregate_bytes"] = saved_total + sum(size - saved.get(name, 0) for name, size in pending_files.items()) + (data.get("downloaded_bytes") or 0)
        data["profile_downloaded_files"] = downloaded_files + len(pending_files)
        data["profile_completed_files"] = existing_files + downloaded_files + len(pending_files)
        emit({**data, "profile_stage": "downloading"})

    class CaptureLogs(logging.Handler):
        def emit(self, record):
            if record.thread == thread_id and record.levelno >= logging.WARNING:
                text = record.getMessage()[:300]
                if text not in messages and len(messages) < 100:
                    messages.append(text)

    class PostSnapshot(Extractor):
        category = "twitter"
        subcategory = "account-post"
        # Asset URLs need no login cookies; the authenticated timeline owns the X session.
        cookies_domain = None
        directory_fmt = ("twitter", "{user[name]}")
        filename_fmt = "{tweet_id}_{num}.{extension}"

        def __init__(self, metadata, assets):
            super().__init__(re.match(".*", url))
            self.metadata, self.assets = metadata, assets

        def items(self):
            yield Message.Directory, "", dict(self.metadata)
            for asset_url, asset_metadata in self.assets:
                yield Message.Url, asset_url, dict(asset_metadata)

    archive = manifest = None

    def existing_entries(post_id, names):
        entries = archive.lookup(post_id, len(names), names)
        if entries is not None:
            return entries
        kept = archive.reusable_files(post_id, names, known_posts.get(post_id, ()))
        if len(kept) == len(names):
            return archive.record(post_id, [entry["name"] for entry in kept], len(names))
        return kept

    def verify_plan(plan):
        nonlocal existing_files, saved_total
        names = plan["names"]
        kept = existing_entries(str(plan["metadata"]["tweet_id"]), names)
        existing_files += len(kept) - plan["existing"]
        plan["existing"] = len(kept)
        remember(kept)
        kept_keys = {os.path.normcase(str(root / entry["name"])) for entry in kept}
        missing = [asset for name, asset in zip(names, plan["assets"])
                   if os.path.normcase(str(root / name)) not in kept_keys]
        for name in names:
            if name in saved and os.path.normcase(str(root / name)) not in kept_keys:
                saved_total -= saved.pop(name)
        return kept, missing

    handler = CaptureLogs()
    logger = logging.getLogger()
    logger.addHandler(handler)
    try:
        with _gallery_lock:
            configure_gallery(output_dir, x_cookie_file=x_cookie_file, x_cookies=x_cookies)
            # Media timeline followed by historical search; exclude other authors' media.
            for key, value in {"retweets": False, "quoted": False, "conversations": False,
                               "text-tweets": False, "cards": False, "articles": False,
                               "replies": True, "pinned": False, "logout": False}.items():
                gallery_config.set(("extractor", "twitter"), key, value)
            gallery_config.set(("extractor", "twitter", "timeline"), "strategy", "media")
            # Verified files are removed from snapshots; the remaining assets must be fetched.
            gallery_config.set(("extractor", "twitter", "account-post"), "skip", False)
            extr = gallery_extractor.find(f"https://x.com/{account}/timeline")
            if not extr or extr.category != "twitter" or extr.subcategory != "timeline":
                raise DownloadError("目前的 X 引擎不支援帳號媒體，請重新執行 start.bat 更新。")
            archive = ProfileArchive(archive_file, output_dir, account)
            # Keep large account manifests on disk; this file closes/deletes on every exit.
            manifest = tempfile.TemporaryFile(mode="w+", encoding="utf-8", prefix="x-scan-",
                                              suffix=".jsonl", dir=archive_file.parent)
            _pace_gallery(extr, emit)
            checkpoint()
            extr.initialize()
            original_send = extr.session.send

            def send(*args, **kwargs):
                checkpoint()
                return original_send(*args, **kwargs)

            extr.session.send = send
            report(status_text="正在掃描 X 帳號媒體清單")
            metadata, assets, expected = None, [], 0
            seen = set()
            for kind, asset_url, data in extr.items():
                if kind == Message.Directory:
                    checkpoint()
                    if metadata is not None:
                        raise DownloadError("X 回傳的貼文媒體清單不完整，請稍後同步重試。")
                    author = str((data.get("author") or {}).get("name") or "")
                    post_id = str(data.get("tweet_id", ""))
                    eligible = (author.lower() == account and post_id.isdigit()
                                and not data.get("retweet_id") and not data.get("quote_id")
                                and post_id not in seen)
                    metadata = dict(data) if eligible else None
                    assets = []
                    expected = data.get("count", 0) if eligible else 0
                    if eligible:
                        seen.add(post_id)
                    continue
                if kind != Message.Url or metadata is None:
                    continue
                if type(expected) is not int or expected <= 0:
                    raise DownloadError("X 回傳的貼文媒體清單不完整，請稍後同步重試。")
                assets.append((asset_url, dict(data)))
                if len(assets) < expected:
                    continue
                post_id = str(metadata["tweet_id"])
                expected_files = []
                user_name = str((metadata.get("user") or {}).get("name") or account)
                if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", user_name) or user_name.lower() != account:
                    raise DownloadError("X 回傳的貼文媒體清單不完整，請稍後同步重試。")
                for _, info in assets:
                    number, extension = info.get("num"), info.get("extension", "")
                    if type(number) is not int or number <= 0 or not re.fullmatch(r"[A-Za-z0-9]{1,8}", str(extension)):
                        expected_files = []
                        break
                    expected_files.append(str(Path("twitter") / user_name / f"{post_id}_{number}.{extension}"))
                if (len(expected_files) != expected or len(assets) != expected
                        or len({os.path.normcase(name) for name in expected_files}) != expected):
                    raise DownloadError("X 回傳的貼文媒體清單不完整，請稍後同步重試。")
                kept = existing_entries(post_id, expected_files)
                remember(kept)
                scanned_posts += 1
                scanned_files += expected
                existing_files += len(kept)
                # Dates are informational here; snapshots name files using tweet_id/num/extension.
                manifest.write(json.dumps({"metadata": metadata, "assets": assets,
                    "names": expected_files, "existing": len(kept)}, ensure_ascii=False, default=str) + "\n")
                report(force=False, status_text="正在掃描 X 帳號媒體清單")
                metadata, assets, expected = None, [], 0
            if metadata is not None:
                raise DownloadError("X 回傳的貼文媒體清單不完整，請稍後同步重試。")
            if extr.status:
                raise DownloadError(messages[-1] if messages else "X 帳號媒體解析未完成，請稍後同步重試。")
            checkpoint()
            scan_complete = True
            total_posts, total_files = scanned_posts, scanned_files
            report("ready", status_text="掃描完成，準備下載帳號媒體", profile_scan_finished=True)
            manifest.seek(0)
            for line in manifest:
                checkpoint()
                plan = json.loads(line)
                metadata, assets, expected_files = plan["metadata"], plan["assets"], plan["names"]
                post_id, expected = str(metadata["tweet_id"]), len(expected_files)
                # Verify again: files can be moved, renamed or deleted while scanning.
                kept, missing = verify_plan(plan)
                if missing:
                    report("downloading", status_text="下載帳號媒體中")
                    before_post()
                    # Quota/cooldown waits can be long; verify after the wait as well.
                    kept, missing = verify_plan(plan)
                    report("downloading", status_text="下載帳號媒體中")
                was_cached = not missing
                if missing:
                    pending_files.clear()
                    try:
                        result = download_gallery(PostSnapshot(metadata, missing), output_dir, file_progress)
                        remember([{"name": name, "size": (root / name).stat().st_size}
                                  for name in result["files"]])
                        merged = [entry["name"] for entry in kept] + result["files"]
                        archive.record(post_id, merged, expected)
                    except Exception as exc:
                        completed = []
                        for name in getattr(exc, "files", ()):
                            target = (root / name).resolve()
                            if target.is_relative_to(root) and target.is_file() and target.stat().st_size > 0:
                                completed.append({"name": name, "size": target.stat().st_size})
                        remember(completed)
                        downloaded_files += len(completed)
                        raise
                    downloaded_files += result.get("downloaded_file_count", len(result["files"]))
                    downloaded_posts += 1
                    POLICY.job_completed()
                else:
                    skipped += 1
                processed += 1
                report("downloading", status_text="下載帳號媒體中", profile_post_finished=not was_cached)
            report("done")
    except Exception as exc:
        report("downloading" if scan_complete else "scanning")
        code = getattr(exc, "code", "download_failed")
        raise DownloadError(str(exc), list(saved), code=code,
                            detail=getattr(exc, "detail", None) or str(exc)) from exc
    finally:
        logger.removeHandler(handler)
        if manifest is not None:
            manifest.close()
        if archive is not None:
            archive.close()
    messages.append("已處理 X 目前可存取的媒體；平台可能未提供完整歷史內容。")
    if not processed:
        messages.append("此帳號目前沒有可取得的媒體，或 X 未提供可見內容。")
    return {"title": f"@{account}", "files": list(saved), "quality": quality, "warnings": messages}


def x_post_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        return None
    match = re.fullmatch(r"/(?:[^/]+|i/web)/status/(\d+)(?:/(?:photo|video)/\d+)?/?", parsed.path)
    return match[1] if match else None


def x_public_media(payload: dict, post_id: str, *, video_quality="best") -> list[dict]:
    """Select every main-post asset, never a video preview or a quoted post."""
    if "tombstone" in payload or not payload:
        raise DownloadError(
            "X 未向訪客提供這則貼文。可能需要登入，或內容已失效；可在設定加入 X Cookie 後重試。",
            code="x_public_unavailable", detail="X public embed returned a tombstone or empty response; no public media was provided.")
    if str(payload.get("id_str", "")) != post_id:
        raise DownloadError("X 回傳的貼文編號不符，請重試。", code="x_invalid_response")
    entries = payload.get("mediaDetails")
    if not isinstance(entries, list) or not entries:
        raise DownloadError("X 公開資料未提供媒體。請按「連接 Chrome 登入」後重試。", code="x_no_public_media")
    files = []
    for number, item in enumerate(entries, 1):
        kind = item.get("type")
        if kind == "photo":
            source = original_image_url(item.get("media_url_https", ""))
            if not source or (urlparse(source).hostname or "").lower() != "pbs.twimg.com":
                raise DownloadError("X 未提供原尺寸圖片網址。", code="x_original_unavailable")
            extension = dict(parse_qsl(urlparse(source).query)).get("format", "jpg")
        elif kind in {"video", "animated_gif"}:
            variants = (item.get("video_info") or {}).get("variants") or []
            candidates = [value for value in variants if
                          value.get("content_type") == "video/mp4" or
                          urlparse(value.get("url", "")).path.lower().endswith(".mp4")]
            if not candidates:
                raise DownloadError("X 未提供可保存的影片來源版本。請按「連接 Chrome 登入」後重試。", code="x_original_unavailable")
            if len(candidates) == 1:
                candidates = [{**candidates[0], "height": (item.get("original_info") or {}).get("height")}]
            try:
                best = select_video_variant(candidates, video_quality)
            except ValueError as exc:
                raise DownloadError(str(exc), code="quality_unavailable") from exc
            source, extension = best["url"], "mp4"
            if (urlparse(source).hostname or "").lower() != "video.twimg.com":
                raise DownloadError("X 影片來源網域不符。", code="x_invalid_response")
        else:
            raise DownloadError("X 回傳了尚未支援的媒體類型，請連接 Chrome 登入後重試。", code="x_unsupported_media")
        files.append({"url": source, "num": number, "extension": extension, "type": kind})
    return files


def download_x_public(url: str, post_id: str, output_dir: Path, emit, *, video_quality="best") -> dict:
    if yt_dlp is None or gallery_job is None:
        raise DownloadError("請重新執行 start.bat 安裝 X 下載引擎。")
    from yt_dlp.jsinterp import js_number_to_string
    from gallery_dl.extractor.common import Extractor
    from gallery_dl.extractor.message import Message

    emit({"status_text": "讀取 X 公開貼文"})
    # Same token calculation used by yt-dlp's official Twitter syndication extractor.
    token = js_number_to_string((int(post_id) / 1e15) * math.pi, 36).translate(str.maketrans("", "", "0."))
    endpoint = "https://cdn.syndication.twimg.com/tweet-result?" + urlencode({"id": post_id, "token": token})
    try:
        with paced_urlopen(Request(endpoint, headers={"User-Agent": "Googlebot"}), timeout=25, emit=emit) as response:
            payload = json.loads(response.read(5_000_001))
    except HTTPError as exc:
        raise DownloadError(f"X 公開資料端點回傳 HTTP {exc.code}，請稍後重試或設定登入 Cookie。",
                            code="x_public_http", detail=f"Public embed HTTP {exc.code}") from exc
    except (ValueError, TypeError) as exc:
        raise DownloadError("X 回傳的公開資料格式不正確，請稍後重試。", code="x_invalid_response") from exc
    if not isinstance(payload, dict):
        raise DownloadError("X 回傳的公開資料格式不正確。", code="x_invalid_response")
    files = x_public_media(payload, post_id, video_quality=video_quality)
    user = (payload.get("user") or {}).get("screen_name") or "unknown"
    metadata = {"user": {"name": user}, "tweet_id": post_id,
                "content": payload.get("text") or f"X 貼文 {post_id}", "count": len(files)}

    class PublicPostExtractor(Extractor):
        category = "twitter"
        subcategory = "public-post"
        directory_fmt = ("twitter", "{user[name]}")
        filename_fmt = "{tweet_id}_{num}.{extension}"

        def items(self):
            yield Message.Directory, "", dict(metadata)
            for item in files:
                yield Message.Url, item["url"], {**metadata, **item}

    result = download_gallery(PublicPostExtractor(re.match(".*", url)), output_dir, emit, video_quality=video_quality)
    if len(result["files"]) != len(files):
        raise DownloadError("部分 X 媒體未能儲存，請重試。", result["files"])
    result["warnings"].append("使用 X 公開嵌入資料；僅能保存此端點提供的媒體，登入後可能有更多內容。")
    return result


def _download_source(url: str, output_dir: Path, emit, *, force=False, x_cookie_file="", x_cookies=None,
             image_history_file: Path | None = None, known_jobs=(), video_quality="best", selected_media="",
             dynamic_capture=False, browser=None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if original_image_url(url):
        return download_image(url, output_dir, emit, force=force, history_file=image_history_file, known_jobs=known_jobs)
    if gallery_extractor:
        # gallery-dl holds process-wide configuration; this app serializes downloads.
        with _gallery_lock:
            # Only load a selected X credential file when this job is for X.
            is_x = (urlparse(url).hostname or "").lower().removeprefix("www.").removeprefix("mobile.") in {"x.com", "twitter.com"}
            configure_gallery(output_dir, force=force, x_cookie_file=x_cookie_file if is_x else "", x_cookies=x_cookies if is_x else None,
                              video_quality=video_quality)
            post_id = x_post_id(url)
            if post_id and not (x_cookie_file or x_cookies):
                return download_x_public(url, post_id, output_dir, emit, video_quality=video_quality)
            if is_x and not (x_cookie_file or x_cookies):
                raise DownloadError("X 帳號頁或非貼文連結需要登入；請按「連接 Chrome 登入」，或改貼單篇貼文網址。", code="x_login_required")
            extractor = gallery_extractor.find(url)
            if extractor and extractor.category != "ytdl":
                return download_gallery(extractor, output_dir, emit, video_quality=video_quality)
    elif (urlparse(url).hostname or "").lower().removeprefix("www.") in {"x.com", "twitter.com"}:
        raise DownloadError("X 貼文的圖片與影片需要圖片下載引擎，請重新執行 start.bat。")
    try:
        return download_video(url, output_dir, emit, force=force, video_quality=video_quality, selected_media=selected_media)
    except DownloadError as exc:
        generic_empty = dynamic_capture and exc.code == "download_failed" and re.search(
            r"No video formats found|Unable to extract (?:video|media) (?:url|URL)|No media found", str(exc), re.I)
        if (exc.code != "unsupported_url" and not generic_empty) or exc.files:
            raise
    return download_web_media(url, output_dir, emit, force=force, video_quality=video_quality,
                              selected_media=selected_media, dynamic_capture=dynamic_capture, browser=browser)


def download(url: str, output_dir: Path, emit, *, force=False, x_cookie_file="", x_cookies=None,
             image_history_file: Path | None = None, known_jobs=(), manifest_file: Path | None = None, video_quality="best", selected_media="",
             dynamic_capture=False, browser=None) -> dict:
    """Skip only a complete verified source manifest; keep expected paths fixed."""
    video_quality = validate_video_quality(video_quality)
    if original_image_url(url):
        video_quality = "best"
    archive, remembered, warnings = None, None, []
    source = source_key(url) + (f"\nvideo_quality={video_quality}" if video_quality != "best" else "")
    if selected_media:
        source += f"\nselected_media={selected_media}"
    try:
        if manifest_file is not None:
            try:
                archive = MediaManifest(manifest_file, output_dir)
                remembered = archive.lookup(source, verify=False)
                cached = archive.lookup(source) if not force else None
                if not remembered and not force:
                    for old in known_jobs:
                        if (not _same_output_directory(old, output_dir) or source_key(str(old.get("url", ""))) != source_key(url)
                                or old.get("video_quality", "best") != video_quality
                                or (old.get("selected_media") or "") != selected_media
                                or type(old.get("size_bytes")) is not int or old["size_bytes"] <= 0):
                            continue
                        from .media_manifest import file_entries
                        try:
                            entries = file_entries(output_dir, old.get("files", []))
                            if sum(entry["size"] for entry in entries) != old["size_bytes"]:
                                continue
                            archive.record(source, old)
                            remembered = cached = archive.lookup(source)
                            break
                        except (OSError, ValueError, TypeError, KeyError):
                            continue
                if cached:
                    files = [entry["name"] for entry in cached["entries"]]
                    size = sum(entry["size"] for entry in cached["entries"])
                    result = {"title": cached["title"], "quality": cached["quality"], "files": files,
                              "warnings": [], "skipped": True, "skipped_file_count": len(files),
                              "downloaded_file_count": 0, "engine": cached.get("engine", ""),
                              "video_quality": video_quality,
                              "media_id": cached.get("media_id", "")}
                    emit({**result, "status_text": "已略過，檔案已存在", "downloaded_bytes": size, "total_bytes": size})
                    return result
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error):
                warnings.append("無法讀取媒體保存紀錄，本次會重新檢查來源。")
        # A changed/missing recorded file must not be accepted solely because
        # an extractor sees the same filename. Re-fetch that source explicitly.
        actual_force = force or manifest_file is not None
        result = _download_source(url, output_dir, emit, force=actual_force,
            x_cookie_file=x_cookie_file, x_cookies=x_cookies,
            image_history_file=image_history_file, known_jobs=known_jobs, video_quality=video_quality, selected_media=selected_media,
            dynamic_capture=dynamic_capture, browser=browser)
        result["video_quality"] = video_quality
        result["selected_media"] = selected_media
        from .media_manifest import file_entries
        try:
            file_entries(output_dir, result.get("files"))
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise DownloadError("下載結果沒有完整且有效的媒體檔案，請重新下載。",
                                code="incomplete_files") from exc
        if remembered and not result.get("skipped"):
            # Only a single stable media ID may restore an older title-based
            # filename. An album's ordering is not a reliable per-file identity.
            old_files = [entry["name"] for entry in remembered["entries"]]
            new_files = result["files"]
            if (len(old_files) == len(new_files) == 1 and remembered.get("media_id")
                    and remembered["media_id"] == result.get("media_id")
                    and remembered.get("engine") == result.get("engine")
                    and Path(old_files[0]).suffix == Path(new_files[0]).suffix):
                root = output_dir.resolve()
                for new, old in zip(new_files, old_files):
                    target = (root / old).resolve()
                    if not target.is_relative_to(root) or Path(old).is_absolute():
                        raise DownloadError("檔案路徑不在此項目的下載資料夾內。")
                    if new != old:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        (root / new).replace(target)
                result["files"] = old_files
        if archive is not None:
            try:
                archive.record(source, result)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error):
                warnings.append("檔案已保存，但媒體紀錄保存失敗；下次可能重新下載。")
        result.setdefault("warnings", []).extend(warnings)
        return result
    finally:
        if archive is not None:
            archive.close()
