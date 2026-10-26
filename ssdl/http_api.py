"""Local HTTP routes and origin validation, with an injected application context."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app_context import AppContext
import json
import io
import mimetypes
import os
import stat
import time
import uuid
import zipfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from .http_server import DeadlineReader, READ_SECONDS, WRITE_SECONDS
from .database_maintenance import MaintenanceError
from .local_media import serve_job_media
from .session_storage import host_browser_required
from . import platform_actions


class RequestFormatError(ValueError):
    """A public, payload-free request validation message."""


class ApplicationClosedError(RuntimeError):
    pass


class ApiHandler(BaseHTTPRequestHandler):
    app: AppContext  # Bound by the composition root before serving requests.
    server_version = "SmartSocialDownloader/1.0"

    def setup(self):
        super().setup()
        self.rfile.close()
        self._input = DeadlineReader(self.connection, getattr(self.server, "read_seconds", READ_SECONDS))
        self.rfile = io.BufferedReader(self._input)
        self.connection.settimeout(getattr(self.server, "write_seconds", WRITE_SECONDS))

    def handle(self):
        try:
            super().handle()
        except OSError as exc:
            # A disconnected local client must not leave a handler/slot behind.
            # Windows may report a plain OSError when shutdown closes a socket
            # during a buffered read, rather than ConnectionResetError.
            if not isinstance(exc, (ConnectionError, TimeoutError)) and self.connection.fileno() != -1:
                raise
            self.close_connection = True

    def parse_request(self):
        parsed = super().parse_request()
        # One request per connection keeps input deadlines and framing explicit.
        self.close_connection = True
        if parsed:
            self._input.remaining()
        return parsed

    def log_message(self, format: str, *args) -> None:
        if urlparse(self.path).path.startswith("/api/jobs/") and urlparse(self.path).path.endswith("/content"):
            print("[%s] Local media response" % self.log_date_time_string())
            return
        if getattr(self, "command", None) == "GET" and urlparse(self.path).path in {"/api/state", "/api/summary", "/api/jobs", "/api/health"} and len(args) > 1 and args[1] == "200":
            return
        print("[%s] %s" % (self.log_date_time_string(), self.app.redact_text(format % args)))

    def _view(self):
        try:
            query = parse_qs(urlparse(self.path).query, max_num_fields=20)
        except ValueError:
            query = {}
        def integer(name, default, maximum=1_000_000):
            raw = query.get(name, [str(default)])[0]
            return min(int(raw), maximum) if raw.isascii() and raw.isdigit() and len(raw) <= 7 else default
        return {"page": max(1, integer("page", 1)), "page_size": integer("page_size", 20),
                "status": query.get("status", ["all"])[0],
                "platform": query.get("platform", ["all"])[0][:100],
                "search": query.get("search", [""])[0][:300]}

    def _state(self):
        return self.app._state(self._view())

    def _send(self, status: int, body: bytes, content_type: str, *, cache_control="no-store", etag=None) -> None:
        self.connection.settimeout(getattr(self.server, "write_seconds", WRITE_SECONDS))
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", cache_control)
        if etag:
            self.send_header("ETag", etag)
        if self._extension_request():
            self.send_header("Access-Control-Allow-Origin", self.app.EXTENSION_ORIGIN)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-SSDL-Extension")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(self.app.redact_fields(data), ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _body_length(self) -> int:
        lengths = self.headers.get_all("Content-Length", [])
        if (self.headers.get_all("Transfer-Encoding") or len(lengths) != 1
                or not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0]) > 6):
            raise RequestFormatError("請求內容大小不正確")
        length = int(lengths[0])
        if length <= 0 or length > 100_000:
            raise RequestFormatError("請求內容大小不正確")
        return length

    def _read_json(self) -> dict:
        length = self._body_length()
        self._input.remaining()
        payload = self.rfile.read(length)
        self._body_read = True
        self._input.remaining()
        if len(payload) != length:
            raise RequestFormatError("請求內容不完整，請重新操作。")
        def reject_constant(_value):
            raise RequestFormatError("請求格式不正確")
        value = json.loads(payload.decode("utf-8"), parse_constant=reject_constant)
        if not isinstance(value, dict):
            raise RequestFormatError("請求格式不正確")
        return value

    def _discard_rejected_body(self) -> int:
        """Avoid closing over an unread, bounded POST body after responding.

        No JSON parsing or application access; never accept ambiguous framing,
        exceed 100 KB or extend the original absolute input deadline.
        """
        if self._body_read:
            return 0
        try:
            remaining = self._body_length()
        except RequestFormatError:
            return 0
        discarded = 0
        self._input.deadline = min(self._input.deadline, time.monotonic() + 0.1)
        try:
            while remaining:
                self._input.remaining()
                chunk = self.rfile.read1(min(remaining, 65_536))
                if not chunk:
                    break
                discarded += len(chunk)
                remaining -= len(chunk)
        except (OSError, ValueError):
            pass  # Timed out/disconnected/shutting down: still close this request.
        return discarded

    def _local_request(self) -> bool:
        allowed = {f"127.0.0.1:{self.app.PORT}", f"localhost:{self.app.PORT}", f"[::1]:{self.app.PORT}"}
        if self.app.PORT == 80:
            allowed.update({"127.0.0.1", "localhost", "[::1]"})
        if len(self.headers.get_all("Host", [])) != 1 or self.headers.get("Host", "").lower() not in allowed:
            return False
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            return False
        if len(self.headers.get_all("Origin", [])) > 1:
            return False
        origin = self.headers.get("Origin")
        if origin:
            try:
                parsed = urlparse(origin)
            except ValueError:
                return False
            return parsed.scheme == "http" and parsed.netloc.lower() in allowed and not parsed.path and not parsed.query and not parsed.fragment
        return True

    def _extension_request(self) -> bool:
        hosts = {f"127.0.0.1:{self.app.PORT}"}
        if self.app.PORT == 80:
            hosts.add("127.0.0.1")
        return (len(self.headers.get_all("Host", [])) == 1
                and len(self.headers.get_all("Origin", [])) <= 1
                and self.headers.get("Host", "").lower() in hosts
                and (self.headers.get("Origin") == self.app.EXTENSION_ORIGIN if self.command == "OPTIONS"
                     else self.headers.get("Origin") in {None, self.app.EXTENSION_ORIGIN})
                and (self.command == "OPTIONS" or self.headers.get("X-SSDL-Extension") == self.app.EXTENSION_ID)
                and urlparse(self.path).path in {"/api/auth/x/extension", "/api/auth/x/prepare",
                                                 "/api/auth/pixiv/claim", "/api/auth/pixiv/callback"})

    def do_OPTIONS(self) -> None:
        if self._extension_request():
            return self._send(204, b"", "text/plain")
        return self._json(403, {"error": "不允許的來源"})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        # Guard before looking up any job, session metadata, or local path.
        # New read-only API routes inherit the same policy automatically.
        if path.startswith("/api/") and not self._local_request():
            return self._json(403, {"error": "僅允許本機操作"})
        if path.startswith("/api/jobs/") and path.endswith("/content"):
            return serve_job_media(self)
        if path == "/api/health":
            health = self.app.health()
            return self._json(200 if health["status"] == "healthy" else 503, health)
        if path == "/api/identity":
            identity = self.app.identity()
            return self._json(200 if identity["api_ready"] and identity["ui_ready"] else 503, identity)
        if path.startswith("/api/jobs/") and path.endswith("/thumbnail"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/thumbnail")
            with self.app.lock:
                stored = self.app.state.jobs.get(job_id)
                job = dict(stored) if stored else None
                directory = self.app.state.download_dir
            if not job:
                return self._json(404, {"error": "找不到這個下載項目"})
            preview = self.app.THUMBNAILS.snapshot(job, directory)
            requested = parse_qs(urlparse(self.path).query).get("key", [""])[0]
            if preview["status"] != "ready" or requested != preview.get("key"):
                return self._send(404, b"", "image/jpeg")
            etag = f'"{preview["key"]}"'
            if self.headers.get("If-None-Match") == etag:
                return self._send(304, b"", "image/jpeg", cache_control="private, max-age=86400", etag=etag)
            content = self.app.THUMBNAILS.read(preview["key"])
            if content is None:
                return self._send(404, b"", "image/jpeg")
            return self._send(200, content, "image/jpeg", cache_control="private, max-age=86400", etag=etag)
        if path == "/api/summary":
            return self._json(200, self.app._state(summary_only=True))
        if path == "/api/databases":
            return self._json(200, self.app.DATABASES.status())
        if path.startswith("/api/jobs/") and path.endswith(("/files", "/details")):
            job_id, kind = path.removeprefix("/api/jobs/").rsplit("/", 1)
            with self.app.lock:
                job = self.app.state.jobs.get(job_id)
                if not job:
                    return self._json(404, {"error": "找不到這個下載項目"})
                if kind == "details":
                    result = {**self.app.job_summary(job), "warnings": list(job.get("warnings") or []),
                              "error_detail": job.get("error_detail", "")}
                else:
                    try:
                        query = parse_qs(urlparse(self.path).query, max_num_fields=20)
                        offset = int(query.get("offset", ["0"])[0])
                        limit = int(query.get("limit", ["100"])[0])
                        if offset < 0 or not 1 <= limit <= 100:
                            raise ValueError()
                    except ValueError:
                        return self._json(400, {"error": "檔案分頁參數不正確"})
                    result = self.app.file_page(job, offset=offset, limit=limit)
            return self._json(200, result)
        if path in {"/api/state", "/api/jobs"}:
            return self._json(200, self._state())
        if path == "/api/environment":
            return self._json(200, self.app.ENVIRONMENT.snapshot())
        if path == "/api/diagnostics":
            return self._json(200, self.app._diagnostics())
        if path == "/api/auth/pixiv/status":
            return self._json(200, {"pixiv_auth": self.app.PIXIV_AUTH.status()})
        if path == "/api/auth/x/setup":
            auth = self.app.X_AUTH.status()
            return self._json(200, {"extension_dir": "" if host_browser_required() else str(self.app.X_AUTH.extension_directory),
                                    "extension_id": self.app.EXTENSION_ID, "port": self.app.PORT,
                                    "origin": self.app.X_AUTH.origin, "host_browser": host_browser_required(),
                                    "storage_mode": auth.get("storage_mode", "dpapi" if os.name == "nt" else "memory"),
                                    "persistent": auth.get("persistent", os.name == "nt")})
        if path == "/api/auth/x/connector":
            buffer = io.BytesIO()
            try:
                base = self.app.ROOT / "chrome-extension"
                if base.resolve() != base or base.is_symlink():
                    raise ValueError("linked source")
                with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name in ("manifest.json", "background.js", "connect.js", "popup.html", "popup.js", "README.md"):
                        target = base / name
                        metadata = target.lstat()
                        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                                or metadata.st_size > 256 * 1024
                                or getattr(metadata, "st_file_attributes", 0) & 0x400):
                            raise ValueError("unsafe source")
                        descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
                        with os.fdopen(descriptor, "rb") as source:
                            opened = os.fstat(source.fileno())
                            if (not stat.S_ISREG(opened.st_mode)
                                    or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)):
                                raise ValueError("changed source")
                            content = source.read(256 * 1024 + 1)
                        if len(content) > 256 * 1024:
                            raise ValueError("source too large")
                        archive.writestr("chrome-extension/" + name, content)
            except (OSError, ValueError):
                return self._json(400, {"error": "無法建立連接器下載檔，請確認公開來源檔案完整。"})
            return self._send(200, buffer.getvalue(), "application/zip")
        if path == "/" or path == "/index.html":
            target = self.app.STATIC / "index.html"
        elif path == "/chrome-connect":
            target = self.app.STATIC / "chrome-connect.html"
        elif path == "/pixiv-connect":
            target = self.app.STATIC / "pixiv-connect.html"
        elif path.startswith("/static/"):
            relative = unquote(path.removeprefix("/static/"))
            target = (self.app.STATIC / relative).resolve()
            if self.app.STATIC.resolve() not in target.parents:
                return self._json(403, {"error": "不允許的檔案路徑"})
        else:
            return self._json(404, {"error": "找不到頁面"})
        if not target.is_file():
            return self._json(404, {"error": "找不到檔案"})
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))

    def do_POST(self) -> None:
        self._body_read = False
        try:
            self._post()
        except ApplicationClosedError:
            self._json(503, {"error": "本機服務正在關閉，請重新啟動後再操作。"})
        finally:
            self._discard_rejected_body()

    def do_HEAD(self) -> None:
        if urlparse(self.path).path.startswith("/api/jobs/") and urlparse(self.path).path.endswith("/content"):
            return self.do_GET()
        return self._send(405, b"", "text/plain")

    @contextmanager
    def _mutation(self):
        with self.app.condition:
            if getattr(self.app, "_closed", False):
                raise ApplicationClosedError()
            yield

    def _post(self) -> None:
        if not (self._local_request() or self._extension_request()):
            return self._json(403, {"error": "僅允許本機操作"})
        if getattr(self.app, "_closed", False):
            raise ApplicationClosedError()
        path = urlparse(self.path).path
        try:
            data = self._read_json()
        except TimeoutError:
            return self._json(408, {"error": "請求讀取逾時，請重新操作。"})
        except RequestFormatError as exc:
            return self._json(400, {"error": str(exc)})
        except (ValueError, UnicodeError, RecursionError):
            return self._json(400, {"error": "請求格式不正確"})

        if path.startswith("/api/auth/pixiv/"):
            if path in {"/api/auth/pixiv/claim", "/api/auth/pixiv/callback"}:
                if not self._extension_request():
                    return self._json(403, {"error": "僅允許 Chrome 連接器操作"})
                try:
                    if path.endswith("/claim") and set(data) == {"ticket"}:
                        return self._json(200, self.app.PIXIV_AUTH.claim(data["ticket"]))
                    if path.endswith("/callback") and set(data) == {"ticket", "code"}:
                        return self._json(200, {"pixiv_auth": self.app.PIXIV_AUTH.connect(**data)})
                except self.app.AuthError as exc:
                    return self._json(400, {"error": self.app.redact_text(str(exc)).replace("X 登入", "Pixiv 登入")})
                return self._json(400, {"error": "請求格式不正確"})
            if not self._local_request():
                return self._json(403, {"error": "僅允許本機操作"})
            try:
                if path == "/api/auth/pixiv/begin" and (not data or data == {"manual": True}):
                    return self._json(200, self.app.PIXIV_AUTH.begin(manual=bool(data.get("manual"))))
                if path == "/api/auth/pixiv/connect" and set(data) in ({"code"}, {"refresh_token"}):
                    return self._json(200, {"pixiv_auth": self.app.PIXIV_AUTH.connect(**data)})
                if path == "/api/auth/pixiv/disconnect" and not data:
                    return self._json(200, {"pixiv_auth": self.app.PIXIV_AUTH.disconnect()})
            except self.app.AuthError as exc:
                return self._json(400, {"error": self.app.redact_text(str(exc))})
            except OSError:
                return self._json(400, {"error": "Pixiv 登入無法保存或清除，請檢查儲存權限。"})
            return self._json(400, {"error": "Pixiv 登入操作參數不正確。"})

        if path == "/api/environment/refresh":
            return self._json(202, self.app.ENVIRONMENT.refresh())

        if path == "/api/databases":
            action = data.get("action")
            if not isinstance(action, str) or action not in {"refresh", "backup", "compact"} or set(data) - {"action", "confirmed"}:
                return self._json(400, {"error": "資料庫操作參數不正確。"})
            if action == "compact" and data.get("confirmed") is not True:
                return self._json(400, {"error": "請先確認資料庫整理操作。"})
            try:
                with self._mutation():
                    if action != "refresh" and (not self.app.state.paused or self.app.state.active_id is not None
                            or any(job["status"] == "active" for job in self.app.state.jobs.values())):
                        raise MaintenanceError("database_pause_required")
                    result = self.app.DATABASES.request(action)
            except MaintenanceError as exc:
                return self._json(409, {"error": str(exc), "error_code": exc.code})
            return self._json(202, result)

        if path == "/api/storage/rescan":
            self.app.STORAGE.rescan(self.app.state.download_dir)
            return self._json(202, self._state())

        if path == "/api/thumbnails/clear":
            self.app.THUMBNAILS.clear()
            return self._json(202, self._state())

        if path == "/api/state/save":
            with self._mutation():
                generation = self.app._save_locked()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path == "/api/auth/x/prepare":
            if not self._extension_request():
                return self._json(403, {"error": "請透過 Chrome 連接器操作"})
            try:
                token = self.app.X_AUTH.prepare_extension()
            except self.app.AuthError as exc:
                return self._json(400, {"error": str(exc)})
            return self._json(200, {"token": token})

        if path == "/api/auth/x/extension":
            if not self._extension_request():
                return self._json(403, {"error": "請透過 Chrome 連接器操作"})
            authorization = self.headers.get("Authorization", "")
            token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
            try:
                self.app.X_AUTH.accept_extension(token, data.get("cookies"))
            except self.app.AuthError as exc:
                return self._json(400, {"error": str(exc)})
            return self._json(200, {"connected": True, "message": "X 登入已連接，失敗項目將自動重試。"})

        if path == "/api/auth/x/connect":
            try:
                result = self.app.X_AUTH.connect()
            except self.app.AuthError as exc:
                return self._json(400, {"error": str(exc)})
            response = self._state()
            if isinstance(result, dict) and result.get("pairing_url"):
                response["pairing_url"] = result["pairing_url"]
            return self._json(202, response)

        if path in {"/api/auth/x/login", "/api/auth/x/open-extensions"}:
            if host_browser_required():
                return self._json(400, {"error": "請在目前的 Chrome 開啟 X，或在網址列輸入 chrome://extensions 管理連接器。"})
            try:
                if path.endswith("/login"):
                    self.app.X_AUTH.open_x()
                else:
                    self.app.X_AUTH.open_extensions()
            except (self.app.AuthError, OSError) as exc:
                return self._json(400, {"error": str(exc)})
            return self._json(200, self._state())

        if path == "/api/auth/x/disconnect":
            try:
                self.app.X_AUTH.disconnect()
            except self.app.AuthError as exc:
                return self._json(400, {"error": str(exc)})
            with self._mutation():
                # Stopping login also stops a legacy Cookie-file login if one was selected.
                self.app.state.x_cookie_file = ""
                generation = self.app._save_locked()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path == "/api/jobs":
            raw_urls = data.get("urls", [])
            mode = data.get("mode", "urls")
            if not isinstance(mode, str) or mode not in {"urls", "x_profile", "pixiv_profile"}:
                return self._json(400, {"error": "下載模式不正確"})
            try:
                requested_quality = self.app.validate_video_quality(data.get("video_quality", "best"))
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            if mode in self.app.PROFILE_MODES and requested_quality != "best":
                return self._json(400, {"error": "作者媒體模式使用原圖／最高畫質。"})
            if not isinstance(raw_urls, list) or not raw_urls:
                return self._json(400, {"error": "請先貼上至少一個網址"})
            if len(raw_urls) > self.app.MAX_URLS_PER_REQUEST:
                return self._json(400, {"error": f"一次最多加入 {self.app.MAX_URLS_PER_REQUEST} 個網址"})
            accepted, rejected = [], []
            seen = set()
            for raw in raw_urls:
                if not isinstance(raw, str):
                    rejected.append({"url": "", "error": "網址格式不正確"})
                    continue
                if mode in self.app.PROFILE_MODES:
                    try:
                        normalizer = self.app.normalize_pixiv_account if mode == "pixiv_profile" else self.app.normalize_account
                        result, account = normalizer(raw)
                    except ValueError as exc:
                        rejected.append({"url": raw[:120], "error": str(exc)})
                        continue
                else:
                    okay, result = self.app._valid_url(raw)
                    if not okay:
                        rejected.append({"url": raw[:120], "error": result})
                        continue
                    profile = self.app.account_from_url(result)
                    account = profile[1] if profile else ""
                    if profile:
                        result = profile[0]
                if account and requested_quality != "best":
                    rejected.append({"url": result, "error": "作者媒體模式使用原圖／最高畫質。"})
                    continue
                identity = self.app.media.source_key(result)
                if identity in seen:
                    continue
                seen.add(identity)
                accepted.append((result, account))
            with self._mutation():
                pending_accounts = {(job.get("mode"), job.get("account")) for job in self.app.state.jobs.values()
                    if job.get("mode") in self.app.PROFILE_MODES and job["status"] in {"queued", "active"}}
                ready = []
                already_pending = []
                for url, account in accepted:
                    if account and (self.app.profile_mode(url), account) in pending_accounts:
                        rejected.append({"url": url, "error": "此作者已有等待中或下載中的工作。"})
                        continue
                    identity = self.app.media.source_key(url)
                    preference = "best" if account or self.app.media.original_image_url(url) else requested_quality
                    matches = sorted((job for job in self.app.state.jobs.values()
                        if self.app.media.source_key(job["url"]) == identity and job.get("video_quality", "best") == preference),
                        key=lambda item: item["created_at"], reverse=True)
                    pending = next((job for job in matches if job["status"] in {"queued", "selecting"}
                        or (job["status"] == "active" and self.app.media._same_output_directory(job, self.app.state.download_dir))), None)
                    if pending:
                        already_pending.append(pending["id"])
                        continue
                    reusable = next((job for job in matches if job["status"] in {"completed", "failed"}
                        and self.app.media._same_output_directory(job, self.app.state.download_dir)), None)
                    ready.append((url, account, reusable, preference))
                accepted = ready
                if len(self.app.state.jobs) + sum(existing is None for _, _, existing, _ in accepted) > self.app.MAX_JOBS:
                    return self._json(429, {"error": f"佇列最多保留 {self.app.MAX_JOBS} 個項目，請先清除已完成項目"})
                created, reused = [], []
                for url, account, existing, preference in accepted:
                    if existing is not None:
                        existing.update(url=url, mode=self.app.profile_mode(url) if account else "urls", account=account, video_quality=preference)
                        self.app._retry_locked(existing)
                        if not account:
                            existing["status_text"] = "等待檢查已下載檔案"
                        reused.append(existing["id"])
                        continue
                    job_id = uuid.uuid4().hex[:12]
                    job = {
                        "id": job_id,
                        "url": url,
                        "mode": self.app.profile_mode(url) if account else "urls",
                        "account": account,
                        "platform": self.app._platform(url),
                        "title": (("Pixiv · " + account) if self.app.profile_mode(url) == "pixiv_profile" else f"@{account}") if account else "等待下載",
                        "status": "queued",
                        "status_text": "等待中",
                        "progress": 0,
                        "speed": "",
                        "eta": "",
                        "size": "",
                        "size_bytes": None,
                        "elapsed_seconds": None,
                        "started_at": None,
                        "finished_at": None,
                        "filename": "",
                        "files": [],
                        "quality": "原尺寸圖片 / 最高可用影片" if preference == "best" else "原尺寸圖片 · 保留來源編碼",
                        "video_quality": preference,
                        "warnings": [],
                        "error": "",
                        "error_detail": "",
                        "error_code": "",
                        "attempts": 0,
                        "retry_count": 0,
                        "created_at": time.time(),
                        "updated_at": time.time(),
                    }
                    if account:
                        job.update(profile_posts=0, profile_skipped=0, profile_downloaded_posts=0,
                                   profile_stage="queued", profile_wait_seconds=0, stop_requested=False)
                        job.update(self.app._PROFILE_COUNT_DEFAULTS)
                    self.app.state.jobs[job_id] = job
                    self.app.state.queue.append(job_id)
                    created.append(job_id)
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(201, {"added": created, "reused": reused,
                "already_pending": already_pending, "rejected": rejected, "state": self._state()})

        if path == "/api/pause":
            paused = data.get("paused")
            if type(paused) is not bool:
                return self._json(400, {"error": "暫停設定必須是 true 或 false。"})
            with self._mutation():
                self.app.state.paused = paused
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path.startswith("/api/jobs/") and path.endswith("/select-media"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/select-media")
            with self._mutation():
                job = self.app.state.jobs.get(job_id)
                if not job:
                    return self._json(404, {"error": "找不到這個下載項目"})
                if job["status"] != "selecting":
                    return self._json(409, {"error": "媒體選擇已更新，請重新整理狀態。"})
                selected = data.get("selection_id")
                if not isinstance(selected, str) or selected not in {item["id"] for item in job.get("selection_options", [])}:
                    return self._json(400, {"error": "請選擇清單中的媒體。"})
                job["selected_media"] = selected
                job.pop("selection_options", None)
                self.app._retry_locked(job)
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path == "/api/rate/reset":
            with self._mutation():
                previous_used = self.app._quota_locked()["used"]
                self.app.state.job_starts.clear()
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, {"reset": True, "previous_used": previous_used, "state": self._state()})

        if path == "/api/downloads/open":
            with self.app.lock:
                directory = self.app.state.download_dir
            try:
                directory.mkdir(parents=True, exist_ok=True)
                platform_actions.open_path(directory)
            except platform_actions.UnsupportedPlatformError:
                return self._json(400, {"error": "目前僅支援在 Windows 開啟資料夾"})
            except OSError as exc:
                return self._json(400, {"error": f"無法開啟下載資料夾：{exc}"})
            return self._json(200, {"opened": True})

        if path == "/api/settings":
            dynamic_capture = data.get("dynamic_capture", self.app.state.dynamic_capture)
            if type(dynamic_capture) is not bool:
                return self._json(400, {"error": "動態媒體捕捉設定不正確。"})
            if dynamic_capture and not self.app.browser_capture_available():
                return self._json(400, {"error": "動態捕捉需要選配 Playwright 與一般 Chrome；請執行 python tools/manage.py browser-setup。"})
            cooldown_mode = data.get("cooldown_mode", self.app.POLICY.mode)
            if not isinstance(cooldown_mode, str) or cooldown_mode not in {"global", "platform"}:
                return self._json(400, {"error": "平台冷卻模式不正確"})
            raw_dir = data.get("download_dir")
            if not isinstance(raw_dir, str) or not raw_dir.strip() or len(raw_dir) > 2000:
                return self._json(400, {"error": "請輸入有效的下載資料夾路徑"})
            raw_limit = data.get("hourly_job_limit", self.app.state.hourly_job_limit)
            raw_timeout = data.get("no_progress_timeout", self.app.state.no_progress_timeout)
            if type(raw_timeout) is not int or not 30 <= raw_timeout <= 3600:
                return self._json(400, {"error": "無進度期限必須是 30～3600 秒的整數。"})
            if type(raw_limit) is not int or not 1 <= raw_limit <= 1000:
                return self._json(400, {"error": "每小時工作上限請輸入 1～1000 的整數"})
            raw_cookie = data.get("x_cookie_file", self.app.state.x_cookie_file)
            if not isinstance(raw_cookie, str) or len(raw_cookie) > 2000:
                return self._json(400, {"error": "X Cookie 路徑格式不正確"})
            cookie_file = raw_cookie.strip()
            try:
                if cookie_file:
                    cookie_file = str(Path(cookie_file).expanduser().resolve())
                    self.app.media.x_cookie_values(cookie_file)
            except (OSError, RuntimeError, ValueError) as exc:
                return self._json(400, {"error": str(exc)})
            try:
                target_dir = self.app.resolve_download_directory(raw_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                if not target_dir.is_dir():
                    raise ValueError("指定路徑不是資料夾")
            except (OSError, RuntimeError, ValueError) as exc:
                return self._json(400, {"error": f"無法使用此資料夾：{exc}"})
            with self._mutation():
                self.app.state.download_dir = target_dir
                self.app.state.x_cookie_file = cookie_file
                self.app.state.hourly_job_limit = raw_limit
                self.app.state.no_progress_timeout = raw_timeout
                self.app.state.dynamic_capture = dynamic_capture
                self.app.POLICY.configure(cooldown_mode)
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path == "/api/jobs/clear-done":
            with self._mutation():
                removed = [job_id for job_id, job in self.app.state.jobs.items() if job["status"] == "completed"]
                for job_id in removed:
                    self.app.state.jobs.pop(job_id, None)
                generation = self.app._save_locked()
            self.app._wait_saved(generation)
            return self._json(200, {"removed": len(removed), "state": self._state()})

        if path == "/api/jobs/clear-all":
            with self._mutation():
                removed = [job_id for job_id in self.app.state.jobs if job_id != self.app.state.active_id]
                for job_id in removed:
                    self.app.state.jobs.pop(job_id, None)
                self.app.state.queue.clear()
                active = self.app.state.jobs.get(self.app.state.active_id)
                if active:
                    active["remove_when_finished"] = True
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, {"removed": len(removed), "pending_active": bool(active), "state": self._state()})

        if path == "/api/jobs/retry-failed":
            with self._mutation():
                failed = [job for job in self.app.state.jobs.values() if job["status"] == "failed"]
                retried = sum(self.app._retry_locked(job) for job in sorted(failed, key=lambda item: item["created_at"]))
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, {"retried": retried, "state": self._state()})

        if path.startswith("/api/jobs/") and path.endswith(("/open-file", "/open-folder")):
            parts = path.removeprefix("/api/jobs/").rsplit("/", 1)
            if len(parts) != 2:
                return self._json(404, {"error": "找不到這個下載項目"})
            job_id, action = parts
            index = data.get("file_index", 0)
            with self.app.lock:
                job = self.app.state.jobs.get(job_id)
                if not job:
                    return self._json(404, {"error": "找不到這個下載項目"})
                files = list(job.get("files", []))
                directory = job.get("output_dir") or str(self.app.state.download_dir)
            if type(index) is not int or not 0 <= index < len(files):
                return self._json(400, {"error": "此項目尚無檔案，或選擇的檔案已更新"})
            if data.get("filename") != files[index]:
                return self._json(409, {"error": "檔案清單已更新，請重新選擇要開啟的檔案"})
            try:
                root = self.app.resolve_download_directory(directory)
                target = (root / files[index]).resolve()
                if not target.is_relative_to(root):
                    return self._json(403, {"error": "檔案路徑不在此項目的下載資料夾內"})
                if not target.is_file():
                    return self._json(404, {"error": "找不到檔案，可能已被移動或刪除"})
                if action == "open-file" and target.suffix.lower() not in self.app.MEDIA_EXTENSIONS:
                    return self._json(400, {"error": "此檔案不是支援的圖片、影片或音訊格式"})
                if host_browser_required():
                    if action == "open-folder":
                        return self._json(400, {"error": "請使用網頁中的工作檔案清單；容器無法開啟主機檔案總管。"})
                    return self._json(200, {"opened": True, "browser": True,
                        "url": f"/api/jobs/{job_id}/content?file_index={index}&filename=" + quote(files[index], safe="")})
                platform_actions.open_path(target if action == "open-file" else target.parent)
            except platform_actions.UnsupportedPlatformError:
                return self._json(400, {"error": "目前僅支援在 Windows 開啟檔案與資料夾"})
            except (OSError, ValueError, TypeError, RuntimeError):
                return self._json(400, {"error": "無法開啟檔案或資料夾，請確認檔案存在且已設定預設開啟程式"})
            return self._json(200, {"opened": True})

        if path.startswith("/api/jobs/") and path.endswith("/retry"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/retry")
            with self._mutation():
                job = self.app.state.jobs.get(job_id)
                if not job:
                    return self._json(404, {"error": "找不到這個項目"})
                if job["status"] not in {"failed", "completed"}:
                    return self._json(409, {"error": "此項目已在佇列或下載中，請等處理完成"})
                if not self.app._retry_locked(job, force=True):
                    return self._json(409, {"error": "此作者已有等待中或下載中的工作。"})
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path.startswith("/api/jobs/") and path.endswith("/stop"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/stop")
            with self._mutation():
                job = self.app.state.jobs.get(job_id)
                if not job:
                    return self._json(404, {"error": "找不到這個下載項目"})
                if job["status"] != "active":
                    return self._json(409, {"error": "只有進行中的下載可以停止。"})
                job.update(stop_requested=True, status_text="正在停止，保留已下載檔案", updated_at=time.time())
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        if path.startswith("/api/jobs/") and path.removeprefix("/api/jobs/") and "/" not in path.removeprefix("/api/jobs/"):
            job_id = path.removeprefix("/api/jobs/")
            with self._mutation():
                job = self.app.state.jobs.get(job_id)
                if not job:
                    return self._json(404, {"error": "找不到這個項目"})
                if job["status"] == "active":
                    return self._json(409, {"error": "下載進行中，完成後才能移除此項目"})
                self.app.state.jobs.pop(job_id, None)
                try:
                    self.app.state.queue.remove(job_id)
                except ValueError:
                    pass
                generation = self.app._save_locked()
                self.app.condition.notify_all()
            self.app._wait_saved(generation)
            return self._json(200, self._state())

        return self._json(404, {"error": "找不到 API"})
