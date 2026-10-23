"""gallery-dl configuration, paced transfers and per-file progress."""
from __future__ import annotations
import logging
import os
import re
import threading
import warnings
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse
from .request_policy import RateLimited, REQUEST_INTERVAL
from .diagnostics import redact_text
from .video_quality import install_video_quality, validate_video_quality, video_format, select_video_variant, rendition_dimensions
from .media_contracts import platform_folder, DownloadError, x_cookie_values, _relative_files
from . import media_engines as engines, request_policy
from .media_engines import STREAM_INTEGRITY_OPTIONS

# gallery-dl configuration is process-wide; orchestration holds this lock.
GALLERY_LOCK = threading.Lock()

def configure_gallery(output_dir: Path, *, force=False, x_cookie_file="", x_cookies=None, video_quality="best", pixiv_refresh_token="") -> None:
    # Use the app's own settings, without loading external configs or postprocessors.
    engines.gallery_config.clear()
    for key, value in {"base-directory": str(output_dir), "fallback": False, "postprocessors": [], "timeout": 25, "retries": 3, "skip": not force,
                       "async": False, "sleep-request": REQUEST_INTERVAL}.items():
        engines.gallery_config.set(("extractor",), key, value)
    for key, value in {"size": ["orig"], "videos": True, "previews": False, "conversations": False, "quoted": False, "ratelimit": "abort", "retries-api": 3}.items():
        engines.gallery_config.set(("extractor", "twitter"), key, value)
    if pixiv_refresh_token:
        # Each download has its own child process. Never persist OAuth cache bytes.
        engines.gallery_config.set(("cache",), "file", ":memory:")
        for key, value in {"refresh-token": pixiv_refresh_token, "include": "artworks", "ugoira": "original",
                           "sanity": False, "max-posts": 0, "directory": ["pixiv", "{user[id]}"],
                           "filename": "{id}_p{num}.{extension}"}.items():
            engines.gallery_config.set(("extractor", "pixiv"), key, value)
    if x_cookies or x_cookie_file:
        engines.gallery_config.set(("extractor", "twitter"), "cookies", dict(x_cookies) if x_cookies else x_cookie_values(x_cookie_file))
        engines.gallery_config.set(("extractor", "twitter"), "cookies-update", False)
    engines.gallery_config.set(("downloader", "http"), "progress", .5)
    engines.gallery_config.set(("downloader", "ytdl"), "format", video_format(video_quality))
    engines.gallery_config.set(("downloader", "ytdl"), "raw-options", {
        **STREAM_INTEGRITY_OPTIONS,
        "format": video_format(video_quality), "ffmpeg_location": engines.ffmpeg_path(),
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
    def secure_session():
        request_policy.POLICY.wrap_session(extr.session, emit)
        if extr.category == "pixiv" and not getattr(extr.session, "_ssdl_pixiv_scope", False):
            send = extr.session.send
            def scoped_send(request, *args, **kwargs):
                if (urlparse(request.url).hostname or "").lower() not in {"app-api.pixiv.net", "oauth.secure.pixiv.net"}:
                    request.headers.pop("Authorization", None)
                return send(request, *args, **kwargs)
            extr.session.send = scoped_send
            extr.session._ssdl_pixiv_scope = True

    original_init_session = extr._init_session

    def init_session():
        original_init_session()
        secure_session()

    extr._init_session = init_session
    original_initialize = extr.initialize

    def initialize():
        if extr.session is not None:
            secure_session()
        return original_initialize()

    extr.initialize = initialize


def download_gallery(extractor, output_dir: Path, emit, *, video_quality="best") -> dict:
    paths, messages = [], []
    downloaded_paths, skipped_paths = set(), set()
    title = ""
    thread_id = threading.get_ident()
    resources, owned_engines = ExitStack(), set()

    def close_engine(engine):
        try:
            engine.close()
        except Exception:
            messages.append("下載引擎的網路資源未能正常關閉；請重新啟動工具。")
            warnings.warn("Delegated engine cleanup failed", ResourceWarning, stacklevel=2)

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

    class CaptureJob(engines.gallery_job.DownloadJob):
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
                    if id(downloader) not in owned_engines:
                        owned_engines.add(id(downloader))
                        resources.callback(close_engine, downloader)
                    install_video_quality(downloader)
                    request_policy.POLICY.wrap_yt_dlp(downloader, emit)
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
        try:
            resources.close()
        finally:
            root_logger.removeHandler(handler)
    files = _relative_files(paths, output_dir)
    if status:
        detail = next((message for message in reversed(messages) if re.search(r"\b429\b|rate[ _-]?limit", message, re.I)),
                      messages[-1] if messages else "平台無法提供可下載媒體；可能需要登入或內容已失效。")
        pixiv_login = extractor.category == "pixiv" and any(part in detail.lower() for part in
            ("authentication", "refresh token", "refresh-token"))
        raise DownloadError("Pixiv 登入已失效，請重新授權。" if pixiv_login else detail, files,
                            code="pixiv_login_required" if pixiv_login else "download_failed")
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
