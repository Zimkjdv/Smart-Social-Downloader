"""Stable download entry points; implementations live in focused backend modules.

Adapters and orchestration import shared contracts directly, never this facade.
Library aliases below remain available for existing engine diagnostics.
"""
from .media_contracts import (
    DownloadError, error_info, platform_folder, platform_directory, original_image_url,
    source_key, x_post_id, x_cookie_values, paced_urlopen,
    _relative_files, _image_source_key, _same_output_directory, IMAGE_EXTENSIONS,
)
from .media_engines import (
    ffmpeg_path, engine_status, yt_dlp, gallery_config, gallery_extractor, gallery_job,
    gallery_version, BEST_VIDEO_FORMAT, STREAM_INTEGRITY_OPTIONS,
)
from .video_adapter import video_options, download_video, _video_error_code, _embed_extractors
from .gallery_adapter import configure_gallery, download_gallery, _pace_gallery, GALLERY_LOCK as _gallery_lock
from .image_adapter import download_image, _download_image_bytes
from .x_account_media import download_x_account, download_x_public, x_public_media
from .pixiv_profiles import download_pixiv_account
from .media_coordinator import download, download_web_media, _download_source
from .request_policy import POLICY, RateLimited, REQUEST_INTERVAL
from .web_media import WebMediaDiscovery, WebMediaError, MediaCandidate, MAX_ATTEMPTS, USER_AGENT, validate_target, diagnostic_error

__all__ = (
    "DownloadError", "error_info", "platform_folder", "platform_directory", "source_key",
    "original_image_url", "x_post_id", "x_cookie_values", "ffmpeg_path", "engine_status",
    "download", "download_video", "download_gallery", "download_image", "download_web_media",
    "download_x_account", "download_pixiv_account", "download_x_public", "x_public_media", "configure_gallery", "video_options",
)
