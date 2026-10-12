"""Optional engine availability and shared source-preserving defaults."""
from __future__ import annotations
import shutil
from functools import lru_cache

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
