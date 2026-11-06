"""Session storage: Windows DPAPI, external-key AES-GCM, or memory only."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import stat
import tempfile

MAGIC = b"SSDL-X1\x00"
MAX_SESSION_BYTES = 256 * 1024


class AuthError(RuntimeError):
    pass


def host_browser_required() -> bool:
    return os.environ.get("SSDL_CONTAINER") == "1" or os.name != "nt"


class SessionStorage:
    """No secret values or key paths are returned by the public description."""
    def __init__(self, *, windows_protect):
        self._windows_protect = windows_protect
        configured = os.environ.get("SSDL_X_KEY_FILE")
        self.mode = "aes-gcm" if configured is not None else "memory" if host_browser_required() else "dpapi"
        self._key_path = configured
        self._key_value = None

    @property
    def persistent(self):
        return self.mode != "memory"

    def _key(self):
        if self._key_value is None:
            value = self._key_path
            if not value or not Path(value).is_absolute():
                raise AuthError("X 登入金鑰設定無效；請掛載獨立的 32 位元組金鑰檔案。")
            if os.environ.get("SSDL_CONTAINER") == "1" and value != "/run/secrets/x_session_key":
                raise AuthError("容器的 X 登入金鑰必須使用獨立的 Docker secret 掛載。")
            try:
                with self._read_regular(Path(value)) as source:
                    key = source.read(33)
                if len(key) != 32:
                    raise ValueError("key length")
                self._key_value = key
            except (OSError, ValueError):
                raise AuthError("無法讀取 X 登入金鑰；請確認掛載、權限及 32 位元組長度。") from None
        return self._key_value

    @staticmethod
    def _read_regular(path):
        if path.is_symlink():
            raise ValueError("linked file")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        stream = os.fdopen(descriptor, "rb")
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            stream.close()
            raise ValueError("not a regular file")
        return stream

    def seal(self, payload):
        if self.mode == "dpapi":
            return self._windows_protect(payload)
        if self.mode == "memory":
            raise AuthError("目前登入僅保留於記憶體，不會寫入磁碟。")
        try:
            from Cryptodome.Cipher import AES
            cipher = AES.new(self._key(), AES.MODE_GCM, nonce=secrets.token_bytes(12), mac_len=16)
            cipher.update(MAGIC)
            encrypted, tag = cipher.encrypt_and_digest(payload)
            return MAGIC + cipher.nonce + tag + encrypted
        except ImportError:
            raise AuthError("缺少登入加密依賴，請重新建置映像或恢復基準套件。") from None

    def unseal(self, payload):
        if self.mode == "dpapi":
            return self._windows_protect(payload, decrypt=True)
        if self.mode == "memory":
            raise AuthError("目前登入僅保留於記憶體；重新連接即可使用。")
        try:
            from Cryptodome.Cipher import AES
            if not payload.startswith(MAGIC) or len(payload) < len(MAGIC) + 28:
                raise ValueError("format")
            offset = len(MAGIC)
            cipher = AES.new(self._key(), AES.MODE_GCM, nonce=payload[offset:offset + 12], mac_len=16)
            cipher.update(MAGIC)
            return cipher.decrypt_and_verify(payload[offset + 28:], payload[offset + 12:offset + 28])
        except (ImportError, ValueError):
            raise AuthError("保存的 X 登入無法解密；請使用原金鑰或重新連接，原檔會保留。") from None

    def check(self):
        if self.persistent:
            self.seal(b"Smart Social Downloader session storage check")

    def load(self, path):
        with self._read_regular(path) as source:
            content = source.read(MAX_SESSION_BYTES + 1)
        if len(content) > MAX_SESSION_BYTES:
            raise AuthError("保存的 X 登入資料過大，請重新連接。")
        return self.unseal(content)

    def save(self, path, payload):
        if not self.persistent:
            return
        encrypted = self.seal(payload)
        if len(encrypted) > MAX_SESSION_BYTES:
            raise AuthError("X 登入資料過大，未保存新的登入。")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".x-auth-", suffix=".tmp", dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(encrypted)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
