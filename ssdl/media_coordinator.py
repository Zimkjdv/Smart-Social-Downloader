"""Download routing, generic discovery and complete-source manifest reuse."""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from .media_manifest import MediaManifest
from .video_quality import validate_video_quality
from .web_media import WebMediaDiscovery, WebMediaError, MAX_ATTEMPTS, validate_target, diagnostic_error
from .media_contracts import DownloadError, original_image_url, source_key, _same_output_directory, x_post_id
from . import media_engines as engines, video_adapter as video, gallery_adapter as gallery
from . import image_adapter as images, x_account_media as x_media



def download_web_media(url: str, output_dir: Path, emit, *, force=False, video_quality="best", selected_media="",
                       dynamic_capture=False, browser=None, _dynamic_only=False, _attempt_budget=MAX_ATTEMPTS) -> dict:
    discovery = WebMediaDiscovery(url, emit, embed_supported=lambda candidate:
        any(extractor.suitable(candidate) for extractor in video._embed_extractors()))
    attempts = quality_errors = 0
    used_dynamic = False
    try:
        from .media_selection import SelectionRequired, choice
        groups = {}
        for candidate in (() if _dynamic_only else discovery.discover()):
            if candidate.kind == "embed" and not any(extractor.suitable(candidate.url) for extractor in video._embed_extractors()):
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
            if candidate.kind == "embed" and not any(extractor.suitable(candidate.url) for extractor in video._embed_extractors()):
                continue  # Unknown embeds are parsed by the discovery iterator next.
            if attempts >= _attempt_budget:
                discovery.notes.append("Media attempt limit reached")
                break
            attempts += 1
            emit({"status_text": "正在下載通用解析找到的媒體"})
            try:
                validate_target(candidate.url)
                return video.download_video(candidate.url, output_dir, emit, force=force,
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


def _download_source(url: str, output_dir: Path, emit, *, force=False, x_cookie_file="", x_cookies=None,
             image_history_file: Path | None = None, known_jobs=(), video_quality="best", selected_media="",
             dynamic_capture=False, browser=None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if original_image_url(url):
        return images.download_image(url, output_dir, emit, force=force, history_file=image_history_file, known_jobs=known_jobs)
    if engines.gallery_extractor:
        # gallery-dl holds process-wide configuration; this app serializes downloads.
        with gallery.GALLERY_LOCK:
            # Only load a selected X credential file when this job is for X.
            is_x = (urlparse(url).hostname or "").lower().removeprefix("www.").removeprefix("mobile.") in {"x.com", "twitter.com"}
            gallery.configure_gallery(output_dir, force=force, x_cookie_file=x_cookie_file if is_x else "", x_cookies=x_cookies if is_x else None,
                              video_quality=video_quality)
            post_id = x_post_id(url)
            if post_id and not (x_cookie_file or x_cookies):
                return x_media.download_x_public(url, post_id, output_dir, emit, video_quality=video_quality)
            if is_x and not (x_cookie_file or x_cookies):
                raise DownloadError("X 帳號頁或非貼文連結需要登入；請按「連接 Chrome 登入」，或改貼單篇貼文網址。", code="x_login_required")
            extractor = engines.gallery_extractor.find(url)
            if extractor and extractor.category != "ytdl":
                return gallery.download_gallery(extractor, output_dir, emit, video_quality=video_quality)
    elif (urlparse(url).hostname or "").lower().removeprefix("www.") in {"x.com", "twitter.com"}:
        raise DownloadError("X 貼文的圖片與影片需要圖片下載引擎，請重新執行 start.bat。")
    try:
        return video.download_video(url, output_dir, emit, force=force, video_quality=video_quality, selected_media=selected_media)
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
