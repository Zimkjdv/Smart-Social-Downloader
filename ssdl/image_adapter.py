"""Original image bytes and verified direct-image history."""
from __future__ import annotations
import hashlib
import mimetypes
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request
from .image_history import ImageHistory
from .media_contracts import platform_directory, DownloadError, original_image_url, paced_urlopen, _image_source_key, source_key, _same_output_directory



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
