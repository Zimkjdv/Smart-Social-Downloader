"""User-triggered X session connection through normal Chrome.

Only X session cookies are retained. Secrets never enter API responses or logs.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
import math


COOKIE_NAMES = {"auth_token", "ct0", "twid"}
X_DOMAINS = {"x.com", "twitter.com"}
EXTENSION_ID = "echfdpjnnbmemndlfcfjgdkdkeklldid"
EXTENSION_ORIGIN = "chrome-extension://" + EXTENSION_ID


class AuthError(RuntimeError):
    pass


def chrome_executable() -> Path | None:
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        folder = os.environ.get(variable)
        if folder:
            candidate = Path(folder) / "Google/Chrome/Application/chrome.exe"
            if candidate.is_file():
                return candidate
    return None


def _dpapi(data: bytes, *, decrypt=False) -> bytes:
    if os.name != "nt":
        raise AuthError("Chrome 自動登入目前支援 Windows。")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        error_code = ctypes.get_last_error()
        raise AuthError(f"Windows 無法使用登入資料加密（錯誤 {error_code}）。請關閉目前服務，從一般 Windows 桌面執行 start.bat，再重新連接 X。")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def _valid_cookie_fields(cookie) -> bool:
    if not isinstance(cookie, dict):
        return False
    for field, maximum in (("domain", 253), ("name", 128), ("value", 8192)):
        value = cookie.get(field)
        if not isinstance(value, str) or not 0 < len(value) <= maximum or re.search(r"[\x00-\x1f\x7f]", value):
            return False
    expires = cookie.get("expires", 0)
    # Bound the numeric value before conversion: huge JSON integers can overflow
    # math.isfinite, and bool is not a Cookie expiration timestamp.
    return (type(expires) in (int, float) and 0 <= expires <= 253402300799
            and math.isfinite(expires))


def _select_x_session(cookies: list[dict]) -> tuple[dict, float]:
    now = time.time()
    for domain in ("x.com", "twitter.com"):
        selected = {}
        expiry = 0
        for cookie in cookies:
            if not _valid_cookie_fields(cookie):
                continue
            cookie_domain = cookie.get("domain", "")
            if cookie_domain.lstrip(".").lower() != domain:
                continue
            name, value = cookie.get("name"), cookie.get("value")
            expires = cookie.get("expires", 0)
            if name not in COOKIE_NAMES:
                continue
            if expires > 0 and expires <= now:
                continue
            selected[name] = value
            if name == "auth_token":
                expiry = expires if expires > 0 else 0
        if selected.get("auth_token"):
            return selected, expiry
    return {}, 0


def _existing_chrome_session() -> tuple[dict, float]:
    from gallery_dl.cookies import load_cookies_chromium

    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data"
    if not root.is_dir():
        return {}, 0
    profile = "Default"
    try:
        data = json.loads((root / "Local State").read_text(encoding="utf-8"))
        last_used = data.get("profile", {}).get("last_used", "Default")
        if re.fullmatch(r"Default|Profile \d+", last_used):
            profile = last_used
    except (OSError, ValueError, TypeError):
        pass
    # The engine applies the domain filter in SQL before decrypting any cookies.
    for domain in ("x.com", "twitter.com"):
        try:
            entries = load_cookies_chromium("chrome", profile=str(root / profile), domain=domain)
            cookies = [{"domain": item.domain, "name": item.name, "value": item.value,
                        "expires": item.expires or 0} for item in entries]
            selected, expiry = _select_x_session(cookies)
            if selected:
                return selected, expiry
        except Exception:
            # Chrome can lock its database or use app-bound encryption. Use its API.
            continue
    return {}, 0


class XAuthManager:
    def __init__(self, directory: Path, *, port=8765, restore=True):
        self.directory = directory
        self.secret_file = directory / "x-auth.bin"
        self.origin = f"http://127.0.0.1:{port}"
        self.extension_directory = directory.parent / "chrome-extension"
        self._challenge = ""
        self._challenge_expires = 0
        self.on_connected = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._values = {}
        self._expires = 0
        self._state = {"phase": "idle", "connected": False, "busy": False,
                       "message": "尚未連接 X 登入", "source": ""}
        self._restored = False
        self._closed = False
        if restore:
            self.restore()

    def restore(self):
        """Restore once, explicitly called during application startup."""
        with self._lock:
            if self._closed:
                raise AuthError("登入連接已關閉，請重新啟動下載工具。")
            if not self._restored:
                self._restore()
                self._restored = True

    def _restore(self):
        if not self.secret_file.is_file():
            return
        try:
            saved = json.loads(_dpapi(self.secret_file.read_bytes(), decrypt=True))
            values = saved["cookies"]
            expiry = float(saved["expires_at"])
            if expiry <= time.time() or not values.get("auth_token"):
                raise ValueError("expired")
            self._values = {name: value for name, value in values.items() if name in COOKIE_NAMES}
            self._expires = expiry
            self._state.update(phase="connected", connected=True,
                               message="已載入本機保存的 X 登入狀態", source=saved.get("source", "Chrome"))
        except Exception:
            self._state.update(phase="expired", message="保存的 X 登入狀態無法使用，請重新連接。")

    def status(self) -> dict:
        with self._lock:
            if self._challenge and self._challenge_expires <= time.time():
                self._challenge = ""
                self._state.update(phase="failed", busy=False, message="Chrome 連接已逾時，請再次按連接按鈕。")
            if self._values and self._expires <= time.time():
                self._values = {}
                self._state.update(phase="expired", connected=False, message="X 登入已到期，請重新連接。")
            return {**self._state, "chrome_available": chrome_executable() is not None}

    def cookies(self) -> dict:
        with self._lock:
            self.status()
            return dict(self._values)

    def connect(self) -> dict:
        with self._lock:
            if self._closed:
                raise AuthError("登入連接已關閉，請重新啟動下載工具。")
            if self._thread and self._thread.is_alive():
                return self.status()
            if not chrome_executable():
                raise AuthError("找不到 Google Chrome，請先安裝 Chrome，或使用進階 Cookie 檔案設定。")
            # Detect restricted-process DPAPI failures before requesting cookies
            # or opening another Chrome pairing tab. No session data is used.
            try:
                _dpapi(b"Smart Social Downloader session storage check")
            except AuthError as exc:
                self._challenge = ""
                self._challenge_expires = 0
                self._state.update(phase="failed", busy=False, message=str(exc))
                raise
            self._stop = threading.Event()
            self._state.update(phase="connecting", busy=True, message="正在連接 Chrome 的 X 登入狀態…")
            self._thread = threading.Thread(target=self._connect, args=(self._stop,),
                                            name="x-login", daemon=True)
            self._thread.start()
            return self.status()

    def disconnect(self):
        with self._lock:
            self._stop.set()
            self._challenge = ""
            try:
                self.secret_file.unlink(missing_ok=True)
            except OSError:
                # Do not report a still-saved session as successfully disconnected,
                # or leave connected=True with an empty in-memory cookie set.
                self._state.update(phase="failed", connected=bool(self._values), busy=False,
                                   message="無法移除保存的登入狀態，請稍後重試。")
                raise AuthError("無法移除保存的登入狀態，請稍後重試。")
            self._values = {}
            self._expires = 0
            self._state.update(phase="idle", connected=False, busy=False,
                               message="已停用 X 登入連接", source="")

    def shutdown(self):
        with self._lock:
            self._closed = True
            self._stop.set()
            self._challenge = ""
            self._challenge_expires = 0
            thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=8)

    def _open_chrome(self, url: str):
        executable = chrome_executable()
        if not executable:
            raise AuthError("找不到 Google Chrome，請先安裝 Chrome。")
        # Use the user's normal browser/profile. No debugging or automation flags.
        subprocess.Popen([str(executable), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def open_x(self):
        self._open_chrome("https://x.com/home")

    def open_extensions(self):
        self._open_chrome("chrome://extensions/")

    def prepare_extension(self, *, stop=None) -> str:
        with self._lock:
            if self._closed:
                raise AuthError("登入連接已關閉，請重新啟動下載工具。")
            if stop is not None:
                if stop is not self._stop or stop.is_set():
                    raise AuthError("連接已取消。")
            else:
                self._stop.set()
                self._stop = threading.Event()
            try:
                _dpapi(b"Smart Social Downloader session storage check")
            except AuthError as exc:
                self._challenge = ""
                self._state.update(phase="failed", busy=False, message=str(exc))
                raise
            self._challenge = secrets.token_urlsafe(32)
            self._challenge_expires = time.time() + 600
            self._state.update(phase="waiting", busy=False,
                               message="請在一般 Chrome 中使用 X 連接器，連接已登入的 X。首次需載入連接器，設定頁有安裝步驟。")
            return self._challenge

    def accept_extension(self, token, cookies):
        with self._lock:
            if (not isinstance(token, str) or len(token) != 43 or not token.isascii()
                    or not self._challenge or self._challenge_expires <= time.time()
                    or not secrets.compare_digest(token, self._challenge)):
                raise AuthError("此連接已到期或已使用，請在工具頁重新按「連接 Chrome 登入」。")
            if not isinstance(cookies, list) or not 0 < len(cookies) <= 12 or not all(_valid_cookie_fields(item) for item in cookies):
                raise AuthError("X 登入資料格式不正確。")
            values, expiry = _select_x_session(cookies)
            if not values:
                raise AuthError("此 Chrome 尚未登入 X。請在一般 Chrome 確認 X 已登入，再連接。")
            stop = self._stop
            self._challenge = ""
        # The callback acquires the queue lock; never invoke it with the auth lock held.
        try:
            if not self._remember(values, expiry, "Chrome 本機連接器", stop):
                raise AuthError("連接已取消，請重新連接。")
        except (AuthError, OSError) as exc:
            message = str(exc) if isinstance(exc, AuthError) else "無法保存 X 登入狀態，請確認 data 資料夾可寫入，再重新連接。"
            self._update(stop, phase="failed", busy=False, message=message)
            raise AuthError(message) from exc

    def _remember(self, values: dict, expiry: float, source: str, stop: threading.Event) -> bool:
        with self._lock:
            if stop.is_set():
                return False
            expiry = expiry or time.time() + 30 * 86400
            payload = json.dumps({"cookies": values, "expires_at": expiry, "source": source}).encode()
            encrypted = _dpapi(payload)
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.secret_file.with_suffix(".bin.tmp")
            temporary.write_bytes(encrypted)
            temporary.replace(self.secret_file)
            self._values, self._expires = dict(values), expiry
            self._challenge = ""
            self._state.update(phase="connected", connected=True, busy=False,
                               message="Chrome 的 X 登入狀態已連接；失敗的 X 項目將自動重試。", source=source)
        if self.on_connected and not stop.is_set():
            self.on_connected()
        return True

    def _update(self, stop, **fields):
        with self._lock:
            if stop is self._stop and not stop.is_set():
                self._state.update(fields)

    def _connect(self, stop: threading.Event):
        try:
            values, expiry = _existing_chrome_session()
            if values:
                self._remember(values, expiry, "Chrome 現有登入", stop)
                return
            if stop.is_set():
                return
            token = self.prepare_extension(stop=stop)
            if not stop.is_set():
                self._open_chrome(self.origin + "/chrome-connect#token=" + token + "&connect=1")
        except AuthError as exc:
            self._update(stop, phase="failed", busy=False, message=str(exc))
        except Exception:
            self._update(stop, phase="failed", busy=False, message="無法連接 Chrome，請使用 Chrome 連接器或進階 Cookie 檔案設定。")
