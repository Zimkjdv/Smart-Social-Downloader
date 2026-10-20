"""Local, job-scoped media streaming; no arbitrary filesystem browsing."""
import os
from pathlib import Path
import re
import stat
from urllib.parse import parse_qs, quote_from_bytes, urlparse
from .http_server import WRITE_SECONDS

MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif",
              ".webp": "image/webp", ".avif": "image/avif", ".bmp": "image/bmp",
              ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
              ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".wav": "audio/wav",
              ".flac": "audio/flac", ".opus": "audio/ogg"}


def open_saved_file(directory, name, *, media_root=None):
    root = Path(directory).resolve()
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("path")
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or media_root is not None and not target.is_relative_to(media_root):
        raise ValueError("path")
    if os.name == "posix":
        anchor = media_root if media_root is not None else root
        parts = target.relative_to(anchor).parts
        if not parts:
            raise ValueError("path")
        descriptor = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = following
            file_descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        finally:
            os.close(descriptor)
    else:
        file_descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    stream = os.fdopen(file_descriptor, "rb")
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise ValueError("not a regular file")
    return stream, target


def byte_range(value, total):
    if value is None:
        return 0, total - 1, False
    match = re.fullmatch(r"bytes=([0-9]{0,20})-([0-9]{0,20})", value)
    if not match or not any(match.groups()) or not total:
        raise ValueError("range")
    start, end = match.groups()
    if not start:
        suffix = int(end)
        if not suffix:
            raise ValueError("range")
        return max(0, total - suffix), total - 1, True
    first, last = int(start), min(int(end), total - 1) if end else total - 1
    if first > last:
        raise ValueError("range")
    return first, last, True


def serve_job_media(handler):
    app = handler.app
    try:
        query = parse_qs(urlparse(handler.path).query, max_num_fields=3)
        if set(query) != {"file_index", "filename"} or any(len(values) != 1 for values in query.values()):
            raise ValueError("query")
        index_text = query["file_index"][0]
        if not re.fullmatch(r"[0-9]{1,7}", index_text):
            raise ValueError("index")
        index = int(index_text)
        job_id = urlparse(handler.path).path.removeprefix("/api/jobs/").removesuffix("/content")
        selection = None
        failure = None
        with app.lock:
            job = app.state.jobs.get(job_id)
            if not job:
                failure = (404, "找不到這個下載項目")
            else:
                files = job.get("files") or []
                if index >= len(files) or files[index] != query["filename"][0]:
                    failure = (409, "檔案清單已更新，請重新選擇要開啟的檔案")
                else:
                    selection = (files[index], job.get("output_dir") or app.state.download_dir)
        if failure:
            return handler._json(failure[0], {"error": failure[1]})
        name, raw_directory = selection
        directory = app.resolve_download_directory(raw_directory)
        if Path(name).suffix.lower() not in app.MEDIA_EXTENSIONS:
            return handler._json(400, {"error": "此檔案不是支援的圖片、影片或音訊格式"})
    except (ValueError, TypeError, RuntimeError, OSError):
        return handler._json(400, {"error": "不允許的檔案路徑"})
    if not app.MEDIA_READS.acquire(blocking=False):
        return handler._json(503, {"error": "媒體讀取忙碌，請稍後再試。"})
    headers_sent = False
    try:
        stream, target = open_saved_file(directory, name, media_root=app.MEDIA_ROOT)
        with stream:
            handler.connection.settimeout(getattr(handler.server, "write_seconds", WRITE_SECONDS))
            total = os.fstat(stream.fileno()).st_size
            range_headers = handler.headers.get_all("Range", [])
            try:
                if len(range_headers) > 1:
                    raise ValueError("range")
                requested = None if handler.headers.get("If-Range") else handler.headers.get("Range")
                first, last, partial = byte_range(requested, total)
            except ValueError:
                headers_sent = True
                handler.send_response(416)
                handler.send_header("Content-Range", f"bytes */{total}")
                handler.send_header("Content-Length", "0")
                handler.send_header("Cache-Control", "no-store")
                handler.end_headers()
                return
            mime = MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
            disposition = "inline" if mime != "application/octet-stream" else "attachment"
            filename = quote_from_bytes(target.name.encode("utf-8", "replace"), safe="")
            headers_sent = True
            handler.send_response(206 if partial else 200)
            handler.send_header("Content-Type", mime)
            handler.send_header("Content-Length", str(max(0, last - first + 1)))
            handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.send_header("Content-Security-Policy", "sandbox; default-src 'none'; media-src 'self'; img-src 'self'; style-src 'unsafe-inline'")
            handler.send_header("Content-Disposition", f"{disposition}; filename=media{target.suffix.lower()}; filename*=UTF-8''{filename}")
            if partial:
                handler.send_header("Content-Range", f"bytes {first}-{last}/{total}")
            handler.end_headers()
            if handler.command == "HEAD":
                return
            stream.seek(first)
            remaining = max(0, last - first + 1)
            while remaining:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    handler.close_connection = True
                    return
                handler.wfile.write(chunk)
                remaining -= len(chunk)
    except (OSError, ValueError, RuntimeError):
        if not headers_sent:
            return handler._json(404, {"error": "找不到檔案，可能已被移動或刪除"})
        handler.close_connection = True
    finally:
        app.MEDIA_READS.release()
