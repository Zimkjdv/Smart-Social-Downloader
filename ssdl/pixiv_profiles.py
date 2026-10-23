"""Scan Pixiv originals completely, then download only file-verified missing pages."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from urllib.parse import urlparse

from . import gallery_adapter as gallery, media_engines as engines, request_policy
from .diagnostics import redact_text
from .media_manifest import verify_entries
from .media_contracts import DownloadError
from .profiles import normalize_pixiv_account
from .x_profiles import ProfileArchive

QUALITY = "Pixiv 原圖／動圖原始影格 · 保留原格式"


def original_asset(url, data, account, artwork):
    parsed = urlparse(url)
    number, extension = data.get("num"), str(data.get("extension", "")).lower()
    if (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".pximg.net")
            or parsed.username or parsed.password or parsed.port is not None
            or not parsed.path.startswith("/img-original/") or type(number) is not int or number < 0
            or extension not in {"jpg", "jpeg", "png", "gif", "webp"} or str(data.get("id")) != artwork):
        raise DownloadError("Pixiv 未提供完整原圖清單；不使用預覽圖代替原檔。", code="pixiv_invalid_media")
    name = str(Path("pixiv") / account / f"{artwork}_p{number}.{extension}")
    metadata = {"id": artwork, "num": number, "extension": extension, "author_id": account,
                "_http_adjust_extension": False}
    return name, (url, metadata)


def download_pixiv_account(url, output_dir, emit, *, archive_file, refresh_token, before_post, checkpoint,
                           previous_files=(), known_jobs=()):
    if not refresh_token:
        raise DownloadError("請先在設定完成 Pixiv 授權。", code="pixiv_login_required")
    if engines.gallery_extractor is None:
        raise DownloadError("缺少 Pixiv 下載引擎，請恢復基準依賴。")
    from gallery_dl.extractor.common import Extractor, Message
    _, account = normalize_pixiv_account(url)
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    saved = {}
    saved_total = 0
    posts = skipped = downloaded_posts = downloaded_files = scanned = scanned_files = existing_files = 0
    unavailable = 0
    complete = False
    last_report = 0.0
    archive = manifest = None
    warnings = []

    def remember(entries):
        nonlocal saved_total
        for item in entries:
            saved_total += item["size"] - saved.get(item["name"], 0)
            saved[item["name"]] = item["size"]

    def report(stage="scanning", *, force=True, **extra):
        nonlocal last_report
        now = time.monotonic()
        if not force and now - last_report < .5:
            return
        last_report = now
        emit({"files": list(saved), "aggregate_bytes": saved_total, "downloaded_bytes": 0,
              "profile_posts": posts, "profile_skipped": skipped, "profile_downloaded_posts": downloaded_posts,
              "profile_stage": stage, "profile_scan_complete": complete, "profile_scanned_posts": scanned,
              "profile_scanned_files": scanned_files, "profile_total_posts": scanned if complete else None,
              "profile_total_files": scanned_files if complete else None, "profile_existing_files": existing_files,
              "profile_downloaded_files": downloaded_files, "profile_completed_files": existing_files + downloaded_files,
              "profile_files_to_download": max(0, scanned_files - existing_files), "quality": QUALITY, **extra})

    def verify(plan):
        nonlocal existing_files, saved_total
        kept = archive.lookup(plan["id"], len(plan["names"]), plan["names"])
        if kept is None:
            kept = archive.reusable_files(plan["id"], plan["names"], ())
        kept = [item for item in kept if verify_entries(root, [item], allow_legacy=True)]
        existing_files += len(kept) - plan["existing"]
        plan["existing"] = len(kept)
        names = {os.path.normcase(item["name"]) for item in kept}
        for name in plan["names"]:
            if os.path.normcase(name) not in names:
                saved_total -= saved.pop(name, 0)
        remember(kept)
        return kept, [asset for name, asset in zip(plan["names"], plan["assets"]) if os.path.normcase(name) not in names]

    class Snapshot(Extractor):
        category, subcategory = "pixiv", "account-artwork"
        cookies_domain = None
        directory_fmt = ("pixiv", "{author_id}")
        filename_fmt = "{id}_p{num}.{extension}"

        def __init__(self, assets):
            super().__init__(re.match(".*", url))
            self.assets = assets
            self.session.headers["Referer"] = "https://www.pixiv.net/"

        def items(self):
            yield Message.Directory, "", self.assets[0][1]
            for asset_url, metadata in self.assets:
                checkpoint()
                yield Message.Url, asset_url, dict(metadata)

    owner = threading.get_ident()
    class CaptureLogs(logging.Handler):
        def emit(self, record):
            if record.thread == owner and record.levelno >= logging.WARNING and len(warnings) < 50:
                value = redact_text(record.getMessage().replace(refresh_token, "[REDACTED]"), limit=400)
                if value not in warnings:
                    warnings.append(value)
    handler = CaptureLogs()
    logging.getLogger().addHandler(handler)
    try:
        with gallery.GALLERY_LOCK:
            gallery.configure_gallery(root, pixiv_refresh_token=refresh_token)
            for key, value in {"skip": False, "directory": ["pixiv", "{author_id}"],
                               "filename": "{id}_p{num}.{extension}"}.items():
                engines.gallery_config.set(("extractor", "pixiv", "account-artwork"), key, value)
            extractor = engines.gallery_extractor.find(f"https://www.pixiv.net/users/{account}/artworks")
            if not extractor or extractor.category != "pixiv" or extractor.subcategory != "artworks":
                raise DownloadError("目前的 Pixiv 引擎不支援作者作品，請更新引擎。")
            archive = ProfileArchive(Path(archive_file), root, "pixiv:" + account)
            remember(archive.verified_files(previous_files))
            manifest = tempfile.TemporaryFile(mode="w+", encoding="utf-8", dir=Path(archive_file).parent,
                                              prefix="pixiv-scan-", suffix=".jsonl")
            gallery._pace_gallery(extractor, emit)
            checkpoint()
            extractor.initialize()
            send = extractor.session.send
            def paced_send(*args, **kwargs):
                checkpoint()
                return send(*args, **kwargs)
            extractor.session.send = paced_send
            report(status_text="正在掃描 Pixiv 作者作品清單")
            seen = set()
            plan = None
            expected = 0
            for kind, asset_url, data in extractor.items():
                checkpoint()
                if kind == Message.Directory:
                    if plan is not None:
                        raise DownloadError("Pixiv 作品頁數不完整，請稍後同步重試。")
                    artwork = str(data.get("id", ""))
                    expected = data.get("count", 0)
                    if (not artwork.isdigit() or str((data.get("user") or {}).get("id")) != account
                            or type(expected) is not int or expected < 0 or expected > 100000):
                        raise DownloadError("Pixiv 作者或作品頁數不一致，已停止以避免保存錯誤內容。", code="pixiv_invalid_media")
                    if expected == 0:
                        # The extractor reports zero pages for inaccessible/deleted
                        # works or unavailable original animation frames.
                        unavailable += 1
                        continue
                    duplicate = artwork in seen
                    seen.add(artwork)
                    plan = {"id": artwork, "assets": [], "names": [], "existing": 0, "duplicate": duplicate}
                elif kind == Message.Url:
                    if plan is None:
                        raise DownloadError("Pixiv 原圖清單不完整。", code="pixiv_invalid_media")
                    name, asset = original_asset(asset_url, data, account, plan["id"])
                    if name in plan["names"]:
                        raise DownloadError("Pixiv 回傳了重複頁碼。", code="pixiv_invalid_media")
                    plan["names"].append(name)
                    plan["assets"].append(asset)
                    if len(plan["assets"]) == expected:
                        if plan["duplicate"]:
                            plan = None
                            continue
                        kept, _ = verify(plan)
                        scanned += 1
                        scanned_files += expected
                        manifest.write(json.dumps(plan, ensure_ascii=False) + "\n")
                        report(force=False, status_text="正在掃描 Pixiv 作者作品清單")
                        plan = None
                else:
                    raise DownloadError("Pixiv 回傳未知清單類型，請更新引擎後重試。", code="pixiv_invalid_media")
            if plan is not None or extractor.status:
                raise DownloadError("Pixiv 作者清單未完整取得，請稍後同步重試。", code="pixiv_scan_incomplete")
            complete = True
            report("ready", profile_scan_finished=True, status_text="掃描完成，準備下載帳號媒體")
            manifest.seek(0)
            for line in manifest:
                checkpoint()
                plan = json.loads(line)
                kept, missing = verify(plan)
                if missing:
                    before_post()
                    kept, missing = verify(plan)  # Recheck after quota/cooldown/pause waits.
                if missing:
                    pending = {}
                    def progress(data):
                        for name in data.get("files", ()):
                            path = (root / name).resolve()
                            if path.is_relative_to(root) and path.is_file():
                                pending[name] = path.stat().st_size
                        # Persist verified successful pages even if this work is
                        # interrupted. Full lookup still checks the fresh total/names.
                        partial_names = [entry["name"] for entry in kept] + list(pending)
                        if partial_names:
                            archive.record(plan["id"], partial_names, len(partial_names))
                        filtered = {key: value for key, value in data.items() if key not in {"title", "files", "file_count"}}
                        filtered.update(profile_stage="downloading", quality=QUALITY,
                            files=list(saved) + [name for name in pending if name not in saved],
                            profile_downloaded_files=downloaded_files + len(pending),
                            profile_completed_files=existing_files + downloaded_files + len(pending),
                            aggregate_bytes=saved_total + sum(pending.values()) + (data.get("downloaded_bytes") or 0))
                        emit(filtered)
                    try:
                        result = gallery.download_gallery(Snapshot(missing), root, progress)
                        names = [item["name"] for item in kept] + result["files"]
                        if (len(names) != len(plan["names"]) or {os.path.normcase(name) for name in names}
                                != {os.path.normcase(name) for name in plan["names"]}):
                            raise DownloadError("Pixiv 作品媒體未完整保存，請稍後同步重試。", result["files"],
                                                code="pixiv_incomplete_media")
                        remember(archive.record(plan["id"], names, len(plan["names"])))
                        downloaded_files += len(result["files"])
                        downloaded_posts += 1
                        request_policy.POLICY.job_completed()
                    except Exception as exc:
                        recovered = []
                        for name in dict.fromkeys([*pending, *getattr(exc, "files", ())]):
                            path = (root / name).resolve()
                            if path.is_relative_to(root) and path.is_file() and path.stat().st_size > 0:
                                recovered.append(name)
                        # A partial work is never recorded as a successful complete work.
                        if recovered:
                            partial_names = [item["name"] for item in kept] + recovered
                            remember(archive.record(plan["id"], partial_names, len(partial_names)))
                        raise
                else:
                    skipped += 1
                posts += 1
                report("downloading", profile_post_finished=bool(missing), status_text="下載帳號媒體中")
                if missing:
                    checkpoint()
            report("done", status_text="帳號媒體同步完成")
    except Exception as exc:
        code = getattr(exc, "code", "download_failed")
        if "Authentication" in type(exc).__name__ or any(part in str(exc).lower() for part in
                ("refresh token", "refresh-token", "authenticationerror")):
            code = "pixiv_login_required"
        message = "Pixiv 登入已失效，請重新授權。" if code == "pixiv_login_required" else redact_text(
            str(exc).replace(refresh_token, "[REDACTED]").replace("X 貼文", "Pixiv 作品"))
        raise DownloadError(message, list(saved), code=code) from exc
    finally:
        logging.getLogger().removeHandler(handler)
        if manifest is not None:
            manifest.close()
        if archive is not None:
            archive.close()
    if not scanned:
        warnings.append("這位作者目前沒有帳號可存取的圖片作品。")
    if unavailable:
        warnings.append(f"{unavailable} 個作品未提供可取得的原圖，已略過；其他可取得原圖仍正常處理。")
    warnings.append("已同步 Pixiv 目前允許此登入帳號取得的原圖；動圖以原始影格保存。")
    return {"title": "Pixiv · " + account, "files": list(saved), "quality": QUALITY, "warnings": warnings,
            "engine": "gallery-dl", "skipped": downloaded_files == 0 and bool(saved),
            "skipped_file_count": existing_files, "downloaded_file_count": downloaded_files}
