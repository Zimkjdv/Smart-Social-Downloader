"""Pixiv PKCE setup and encrypted refresh-token ownership, outside saved queue state."""
import base64
import hashlib
import json
import logging
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse

from .runtime_paths import paths, module_command
from .session_storage import AuthError, SessionStorage, host_browser_required
from .x_auth import _dpapi, chrome_executable


def token_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._~\-]{20,4096}", value):
        raise AuthError("Pixiv Refresh Token 格式不正確。")
    return value


def callback_code(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise AuthError("請貼上這次 Pixiv 授權的回呼網址或 code。")
    value = value.strip()
    if "://" in value:
        try:
            url = urlparse(value)
            allowed = ((url.scheme == "https" and url.hostname == "app-api.pixiv.net"
                        and url.path == "/web/v1/users/auth/pixiv/callback")
                       or (url.scheme == "pixiv" and url.netloc == "account" and url.path == "/login"))
            query = parse_qs(url.query, max_num_fields=12)
            if not allowed or url.username or url.password or url.port is not None or len(query.get("code", [])) != 1:
                raise ValueError
            value = query["code"][0]
        except (ValueError, UnicodeError):
            raise AuthError("Pixiv 回呼網址不正確，請重新授權。") from None
    if not re.fullmatch(r"[A-Za-z0-9._~\-]{5,512}", value):
        raise AuthError("Pixiv 授權 code 格式不正確。")
    return value


class PixivAuthManager:
    def __init__(self, directory, *, storage=None, port=8765):
        self.path = Path(directory) / "pixiv-session.bin"
        self.storage = storage or SessionStorage(windows_protect=_dpapi)
        self.lock = threading.RLock()
        self._token = ""
        self._pending = None
        self._epoch = 0
        self._busy = False
        self._phase = "disconnected"
        self.origin = f"http://127.0.0.1:{port}"
        self._ticket = ""
        self._claimed = False
        self._attempt_phase = "idle"
        self.on_connected = lambda: None

    def status(self):
        with self.lock:
            if self._pending and time.monotonic() >= self._pending[1]:
                self._pending = None
                self._ticket = ""
                self._attempt_phase = "expired"
            return {"connected": bool(self._token), "busy": self._busy, "phase": self._phase,
                    "pending": self._pending is not None, "persistent": self.storage.persistent,
                    "storage_mode": self.storage.mode, "attempt_phase": self._attempt_phase}

    def restore(self):
        if not self.storage.persistent or not self.path.exists():
            return
        try:
            value = json.loads(self.storage.load(self.path))
            if not isinstance(value, dict) or value.get("service") != "pixiv":
                raise ValueError
            if value.get("expired") is True:
                with self.lock:
                    self._phase = "expired"
                return
            token = token_value(value["refresh_token"])
        except (OSError, ValueError, KeyError, TypeError, AuthError):
            with self.lock:
                self._phase = "expired"
            return  # Preserve an unreadable original; never fall back to plaintext.
        with self.lock:
            self._token, self._phase = token, "connected"

    def token(self):
        with self.lock:
            if not self._token:
                raise AuthError("下載 Pixiv 需要登入，請先在設定完成 Pixiv 授權。")
            return self._token

    def begin(self, *, manual=False):
        with self.lock:
            if self._busy:
                raise AuthError("Pixiv 登入處理中，請稍候。")
            # Fail before asking the user to authorize if persistence is unavailable.
            try:
                self.storage.check()
            except AuthError as exc:
                raise AuthError(str(exc).replace("X 登入", "Pixiv 登入")) from None
            self._epoch += 1
            verifier = secrets.token_urlsafe(32)
            self._pending = (verifier, time.monotonic() + 600, self._epoch)
            self._ticket = "" if manual else secrets.token_urlsafe(32)
            self._claimed = False
            self._attempt_phase = "waiting"
            pairing_url = self.origin + "/pixiv-connect#ticket=" + self._ticket if not manual else ""
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        url = "https://app-api.pixiv.net/web/v1/login?" + urlencode(
            {"client": "pixiv-android", "code_challenge": challenge, "code_challenge_method": "S256"})
        opened = False
        if not host_browser_required():
            try:
                executable = chrome_executable()
                if executable:
                    subprocess.Popen([str(executable), url if manual else pairing_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    opened = True
            except OSError:
                pass  # The visible link remains usable in ordinary host Chrome.
        return {**({"authorization_url": url} if manual else {"pairing_url": pairing_url}),
                "expires_in": 600, "opened": opened}

    def _check_ticket(self, ticket):
        if (not isinstance(ticket, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", ticket) or not self._ticket or not self._pending
                or time.monotonic() >= self._pending[1] or not secrets.compare_digest(ticket, self._ticket)):
            raise AuthError("Pixiv 連接已過期，請從下載工具重新按一鍵連接。")

    def claim(self, ticket):
        with self.lock:
            self._check_ticket(ticket)
            if self._claimed or self._busy:
                raise AuthError("Pixiv 連接已啟動，請勿重複使用連接頁。")
            self._claimed = True
            self._attempt_phase = "authorizing"
            verifier = self._pending[0]
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            return {"authorization_url": "https://app-api.pixiv.net/web/v1/login?" + urlencode(
                {"client": "pixiv-android", "code_challenge": challenge, "code_challenge_method": "S256"})}

    def connect(self, *, code=None, refresh_token=None, ticket=None):
        if (code is None) == (refresh_token is None):
            raise AuthError("請選擇授權 code 或 Refresh Token 其中一種方式。")
        with self.lock:
            if ticket is not None:
                self._check_ticket(ticket)
                if not self._claimed or code is None:
                    raise AuthError("Pixiv 連接尚未啟動，請重新連接。")
            if self._busy:
                raise AuthError("Pixiv 登入處理中，請稍候。")
            if code is not None:
                parsed = callback_code(code)
                if not self._pending or time.monotonic() >= self._pending[1]:
                    self._pending = None
                    self._ticket = ""
                    self._attempt_phase = "expired"
                    raise AuthError("Pixiv 授權已過期，請重新開啟授權頁。")
                values = {"grant": "authorization_code", "code": parsed, "verifier": self._pending[0]}
                self._pending = None  # Codes/verifiers are single use, including failed exchanges.
            else:
                values = {"grant": "refresh_token", "refresh_token": token_value(refresh_token)}
            self._pending = None
            self._ticket = ""
            epoch = self._epoch
            self._busy = True
            self._attempt_phase = "exchanging"
        try:
            result = subprocess.run(module_command('ssdl.pixiv_auth_exchange'),
                input=json.dumps(values).encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=paths().home, timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode or len(result.stdout) > 16 * 1024:
                raise AuthError("Pixiv 授權失敗或 code 已過期，請重新授權；既有登入仍保留。")
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                raise AuthError("Pixiv 授權回應格式不正確，請重新授權。")
            token = token_value(value.get("refresh_token"))
            with self.lock:
                if self._epoch != epoch:
                    raise AuthError("Pixiv 授權已取消，請重新連接。")
                self.storage.save(self.path, json.dumps({"service": "pixiv", "refresh_token": token}).encode())
                self._token, self._phase = token, "connected"
                self._attempt_phase = "connected"
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, AuthError) as exc:
            with self.lock:
                if self._epoch == epoch:
                    self._attempt_phase = "failed"
            if isinstance(exc, AuthError):
                raise AuthError(str(exc).replace("X 登入", "Pixiv 登入")) from None
            raise AuthError("Pixiv 授權無法完成，請確認連線後重新授權。") from None
        finally:
            with self.lock:
                self._busy = False
        self.on_connected()
        return self.status()

    def invalidate(self, expected_token):
        with self.lock:
            if expected_token and self._token == expected_token:
                self._token, self._phase = "", "expired"
                if self.storage.persistent:
                    try:
                        # Keep the expiry across restart without retaining the
                        # rejected refresh token. A new connection replaces it.
                        self.storage.save(self.path, json.dumps({"service": "pixiv", "expired": True}).encode())
                    except (OSError, AuthError):
                        try:
                            self.path.unlink(missing_ok=True)
                        except OSError:
                            # Do not terminate the queue because cleanup failed.
                            logging.warning("Pixiv 登入已失效，但無法清除保存紀錄；請檢查儲存權限並重新連接。")

    def disconnect(self):
        with self.lock:
            self._epoch += 1
            self._pending = None
            self._ticket = ""
            self._attempt_phase = "cancelled"
            # Keep a connected state if removing the saved credential fails.
            self.path.unlink(missing_ok=True)
            self._token, self._phase = "", "disconnected"
        return self.status()

    def shutdown(self):
        with self.lock:
            self._epoch += 1
            self._pending = None
            self._ticket = ""
            self._attempt_phase = "cancelled"
            self._token = ""
