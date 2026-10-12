"""yt-dlp extraction, quality selection, fragment integrity and progress."""
from __future__ import annotations
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from .request_policy import RateLimited, REQUEST_INTERVAL
from .diagnostics import redact_text
from .video_quality import install_video_quality, enrich_video_formats, video_quality_text, validate_video_quality, video_format
from .web_media import MediaCandidate, USER_AGENT
from .media_contracts import platform_directory, DownloadError, _relative_files, source_key
from . import media_engines as engines, request_policy
from .media_engines import STREAM_INTEGRITY_OPTIONS



def video_options(output_dir: Path, emit, paths: list, *, force=False, video_quality="best") -> dict:
    ffmpeg = engines.ffmpeg_path()
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
        if engines.yt_dlp is not None and isinstance(current, engines.yt_dlp.utils.UnsupportedError):
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
    if engines.yt_dlp is None:
        raise DownloadError("尚未安裝影片下載引擎，請執行 start.bat。")
    paths, warnings = [], []
    reported_existing = transferred = False

    class CaptureDownloader(engines.yt_dlp.YoutubeDL):
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
        request_policy.POLICY.wrap_yt_dlp(downloader, emit)
        if cookies is not None:
            for cookie in cookies:
                downloader.cookiejar.set_cookie(cookie)
        try:
            target = engines.yt_dlp.utils.smuggle_url(url, {"referer": candidate.referer}) if candidate and candidate.kind == "media" else url
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
