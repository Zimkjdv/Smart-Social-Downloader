"""X account scan plans and public-post media with verified archives."""
from __future__ import annotations
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse
from urllib.request import Request
from urllib.error import HTTPError
from .x_profiles import normalize_account, ProfileArchive
from .video_quality import select_video_variant
from .media_contracts import DownloadError, original_image_url, paced_urlopen, _same_output_directory, x_post_id
from . import media_engines as engines, gallery_adapter as gallery, request_policy



def download_x_account(url: str, output_dir: Path, emit, *, archive_file: Path,
                       before_post, checkpoint, x_cookie_file="", x_cookies=None,
                       previous_files=(), known_jobs=()) -> dict:
    """Scan a complete visible media manifest before downloading its missing files."""
    if engines.gallery_extractor is None:
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
    last_report = 0.0
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
        nonlocal last_report
        now = time.monotonic()
        if not force and now - last_report < .5:
            return
        last_report = now
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
        with gallery.GALLERY_LOCK:
            gallery.configure_gallery(output_dir, x_cookie_file=x_cookie_file, x_cookies=x_cookies)
            # Media timeline followed by historical search; exclude other authors' media.
            for key, value in {"retweets": False, "quoted": False, "conversations": False,
                               "text-tweets": False, "cards": False, "articles": False,
                               "replies": True, "pinned": False, "logout": False}.items():
                engines.gallery_config.set(("extractor", "twitter"), key, value)
            engines.gallery_config.set(("extractor", "twitter", "timeline"), "strategy", "media")
            # Verified files are removed from snapshots; the remaining assets must be fetched.
            engines.gallery_config.set(("extractor", "twitter", "account-post"), "skip", False)
            extr = engines.gallery_extractor.find(f"https://x.com/{account}/timeline")
            if not extr or extr.category != "twitter" or extr.subcategory != "timeline":
                raise DownloadError("目前的 X 引擎不支援帳號媒體，請重新執行 start.bat 更新。")
            archive = ProfileArchive(archive_file, output_dir, account)
            # Keep large account manifests on disk; this file closes/deletes on every exit.
            manifest = tempfile.TemporaryFile(mode="w+", encoding="utf-8", prefix="x-scan-",
                                              suffix=".jsonl", dir=archive_file.parent)
            gallery._pace_gallery(extr, emit)
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
                        result = gallery.download_gallery(PostSnapshot(metadata, missing), output_dir, file_progress)
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
                    request_policy.POLICY.job_completed()
                else:
                    skipped += 1
                processed += 1
                # Cached posts need no durable quota checkpoint. Throttle their
                # aggregate list just like scan progress; ready/done and newly
                # downloaded posts still force a full checkpoint.
                report("downloading", force=not was_cached, status_text="下載帳號媒體中", profile_post_finished=not was_cached)
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
    if engines.yt_dlp is None or engines.gallery_job is None:
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

    result = gallery.download_gallery(PublicPostExtractor(re.match(".*", url)), output_dir, emit, video_quality=video_quality)
    if len(result["files"]) != len(files):
        raise DownloadError("部分 X 媒體未能儲存，請重試。", result["files"])
    result["warnings"].append("使用 X 公開嵌入資料；僅能保存此端點提供的媒體，登入後可能有更多內容。")
    return result
