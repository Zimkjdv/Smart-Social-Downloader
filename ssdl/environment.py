"""Bounded local diagnostics shared by setup, startup, and the web interface.

No network requests, cookie inspection, history access, or package installation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import importlib
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

from .config import configured_port
from .x_auth import AuthError, _dpapi, chrome_executable


def _check(key, name, status, detail, *, version="", required=False, hint="") -> dict:
    return {"id": key, "name": name, "status": status, "detail": detail,
            "version": version, "required": required, "hint": hint}


def _command(arguments, timeout=6) -> str | None:
    try:
        result = subprocess.run(arguments, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return result.stdout[:4096] if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _ffmpeg_check() -> dict:
    executable = shutil.which("ffmpeg")
    if not executable:
        try:
            import imageio_ffmpeg
            executable = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, OSError, RuntimeError):
            pass
    output = _command([executable, "-version"]) if executable else None
    match = re.search(r"^ffmpeg version ([^\s]+)", output or "")
    return _check("ffmpeg", "FFmpeg", "ok" if match else "error",
                  "可執行，支援影片合併與縮圖。" if match else "找不到可執行的 FFmpeg。",
                  version=match.group(1) if match else "", required=True,
                  hint="" if match else "執行 setup.bat；若 PATH 中已有失效的 FFmpeg，請修正後重新啟動服務。")


def _runtime_check() -> dict:
    found = []
    supported = False
    for name, minimum in (("deno", (2, 3, 0)), ("node", (22, 0, 0))):
        executable = shutil.which(name)
        output = _command([executable, "--version"], timeout=3) if executable else None
        match = re.search(r"^(?:deno\s+|v)(\d+)\.(\d+)\.(\d+)", output or "")
        if match:
            version = tuple(map(int, match.groups()))
            usable = version >= minimum
            supported |= usable
            found.append(f"{name} {'.'.join(match.groups())}" + ("" if usable else " (unsupported)"))
        elif executable:
            found.append(f"{name} (version unavailable)")
    return _check("javascript", "JavaScript 執行環境", "ok" if supported else "warning",
                  "; ".join(found) or "未找到 Node.js 或 Deno。",
                  hint="" if supported else "YouTube 需要 Node.js 22+ 或 Deno 2.3+；安裝並加入 PATH 後，重新啟動服務。")


def _pip_check() -> dict:
    output = _command([sys.executable, "-m", "pip", "check"], timeout=8)
    return _check("dependencies", "套件相依性", "ok" if output is not None else "error",
                  "套件相依性一致。" if output is not None else "相依性檢查失敗或逾時。",
                  required=True, hint="" if output is not None else "執行 setup.bat 恢復基準套件；更新引擎前請先停止服務。")


def inspect_environment(root: Path, *, port: int | None = None) -> dict:
    checks = [_check("python", "Python", "ok" if sys.version_info >= (3, 12) else "error",
                     "需要 Python 3.12 或更新版本。", version=sys.version.split()[0], required=True)]
    for package, module, required in (("yt-dlp", "yt_dlp", True),
                                      ("gallery-dl", "gallery_dl", True),
                                      ("imageio-ffmpeg", "imageio_ffmpeg", True),
                                      ("yt-dlp-ejs", "yt_dlp_ejs", False)):
        version = ""
        try:
            importlib.import_module(module)
            version = importlib.metadata.version(package)
        except Exception:
            pass
        checks.append(_check(package, package, "ok" if version else "error" if required else "warning",
                             "已安裝。" if version else "未安裝或無法載入。", version=version,
                             required=required, hint="" if version else "執行 setup.bat 安裝基準套件，或停止服務後執行 update.bat。"))
    # Independent local commands have individual time limits and never hold the
    # queue lock. Only a manual recheck starts another inspection in the server.
    with ThreadPoolExecutor(max_workers=3) as executor:
        checks.extend(executor.map(lambda check: check(), (_ffmpeg_check, _runtime_check, _pip_check)))
    is_venv = Path(sys.prefix).resolve() == (root / ".venv").resolve()
    checks.append(_check("venv", "專案虛擬環境", "ok" if is_venv else "warning",
                         "使用專案 .venv。" if is_venv else "目前未使用專案 .venv。",
                         hint="" if is_venv else "請使用 setup.bat 與 start.bat，避免使用其他 Python 環境。"))
    chrome = chrome_executable() is not None
    try:
        browser_version = importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        browser_version = ""
    checks.append(_check("browser_capture", "動態媒體捕捉（選配）", "ok" if browser_version and chrome else "warning",
                         "選配套件與 Chrome 已就緒。" if browser_version and chrome else "尚未安裝選配套件或 Chrome；不影響一般下載。",
                         version=browser_version, hint="啟用前執行 python tools/manage.py browser-setup；需一般 Chrome，使用隔離暫時工作階段。"))
    checks.append(_check("chrome", "Google Chrome", "ok" if chrome else "warning",
                         "已找到 Chrome；連接器需在已登入 X 的個人檔案載入。" if chrome else "未找到 Google Chrome。",
                         hint="" if chrome else "安裝一般 Chrome，或使用進階 X Cookie 檔案設定。"))
    encryption = False
    if os.name == "nt":
        try:
            sample = b"Smart Social Downloader environment diagnostic"
            encryption = _dpapi(_dpapi(sample), decrypt=True) == sample
        except (AuthError, OSError):
            pass
    checks.append(_check("session_storage", "X 登入加密保存", "ok" if encryption else "warning",
                         "Windows 加密與解密可用。" if encryption else "目前環境無法使用 Windows 登入資料加密。",
                         hint="" if encryption else "從一般 Windows 桌面執行 start.bat，再重新連接 X。"))
    try:
        selected_port = configured_port() if port is None else port
        checks.append(_check("port", "本機連接埠", "ok", f"http://127.0.0.1:{selected_port}",
                             hint="Chrome 連接器須設定相同連接埠；預設為 8765。", required=True))
    except RuntimeError:
        selected_port = None
        checks.append(_check("port", "本機連接埠", "error", "SSDL_PORT 設定無效。",
                             required=True, hint="SSDL_PORT 必須是 1～65535 的整數。"))
    errors = sum(item["status"] == "error" for item in checks)
    warnings = sum(item["status"] == "warning" for item in checks)
    return {"phase": "complete", "busy": False, "checked_at": time.time(),
            "ready": not any(item["required"] and item["status"] != "ok" for item in checks),
            "status": "error" if errors else "warning" if warnings else "ok",
            "errors": errors, "warnings": warnings, "port": selected_port, "checks": checks}


class EnvironmentDiagnostics:
    def __init__(self, root: Path, port: int):
        self.root, self.port = root, port
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self._report = {"phase": "idle", "busy": False, "checked_at": 0,
                        "ready": False, "status": "warning", "errors": 0,
                        "warnings": 0, "port": port, "checks": []}

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._report)

    def refresh(self) -> dict:
        with self._lock:
            if not self._stop.is_set() and not self._report["busy"]:
                self._report.update(phase="checking", busy=True)
                self._thread = threading.Thread(target=self._inspect, name="environment-check", daemon=True)
                self._thread.start()
            return copy.deepcopy(self._report)

    def _inspect(self):
        try:
            report = inspect_environment(self.root, port=self.port)
        except Exception:
            report = {"phase": "complete", "busy": False, "checked_at": time.time(),
                      "ready": False, "status": "error", "errors": 1, "warnings": 0,
                      "port": self.port, "checks": [_check("diagnostic", "環境診斷", "error",
                      "無法完成環境診斷。", hint="請重新檢查，或從一般 Windows 桌面重新啟動 start.bat。")]}
        with self._lock:
            if not self._stop.is_set():
                self._report = report

    def shutdown(self):
        with self._lock:
            self._stop.set()
            thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=15)
