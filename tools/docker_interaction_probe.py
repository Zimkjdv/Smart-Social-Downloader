"""Synthetic login/media fixture actions; never installed in the application image."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time

DATA, MEDIA, KEYS = map(Path, ("/app/data", "/downloads", "/keys"))
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=")
SLOW_BYTES = 16 * 1024 * 1024


def require(condition):
    if not condition:
        raise RuntimeError("fixture condition failed")


def main(action):
    require(sys.platform == "linux" and re.fullmatch(r"[0-9a-f]{32}", os.environ.get("SSDL_DOCKER_ACCEPTANCE", "")))
    sys.path[:0] = ["/app", "/app/docker"]
    os.umask(0o077)
    if action == "init-keys":
        require(os.getuid() == 0 and os.path.ismount(KEYS) and not any(KEYS.iterdir()))
        os.chown(KEYS, 10001, 10001)
        KEYS.chmod(0o700)
        return {}
    require(os.getuid() == 10001)
    if action == "key-info":
        key = KEYS / "x-session.key"
        info = key.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 10001
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size == 32)
        key.rename(KEYS / "x_session_key")
        return {}
    if action in {"wrong-key", "missing-key", "recover-key"}:
        key, retained = KEYS / "x_session_key", KEYS / "retained.key"
        if action == "wrong-key":
            require(not retained.exists())
            key.rename(retained)
            key.write_bytes(secrets.token_bytes(32))
        elif action == "missing-key":
            key.unlink()
        else:
            retained.rename(key)
        return {}
    if action == "session-info":
        session = DATA / "x-auth.bin"
        if not session.exists():
            return {"exists": False}
        from ssdl.session_storage import MAGIC
        content = session.read_bytes()
        require(content.startswith(MAGIC) and b"ssdl-invented-session" not in content
                and stat.S_IMODE(session.stat().st_mode) == 0o600)
        return {"exists": True, "sha256": hashlib.sha256(content).hexdigest()}
    if action == "cipher-contract":
        from ssdl.session_storage import AuthError, SessionStorage
        storage = SessionStorage(windows_protect=None)
        value = b"ssdl-invented-session"
        encrypted = storage.seal(value)
        require(storage.mode == "aes-gcm" and storage.unseal(encrypted) == value
                and encrypted != storage.seal(value))
        for broken in (encrypted[:-1], encrypted[:-1] + bytes([encrypted[-1] ^ 1]), b"invalid"):
            try:
                storage.unseal(broken)
            except AuthError:
                continue
            raise RuntimeError("unauthenticated ciphertext accepted")
        return {}
    if action == "seed-media":
        from ssdl.persistence import StateStore
        require(not any(name.name not in {".ssdl.lock"} for name in MEDIA.iterdir()))
        folder = MEDIA / "fixture"
        folder.mkdir()
        (folder / "original.png").write_bytes(PNG)
        (folder / "moved.jpg").write_bytes(PNG)
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(folder / "video.mp4")], check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with (folder / "slow.mp4").open("wb") as output:
            for _ in range(SLOW_BYTES // 65536):
                output.write(b"s" * 65536)
        (folder / "escape.mp4").symlink_to("/app/LICENSE")
        now = time.time()
        files = ["fixture/" + name for name in ("original.png", "video.mp4", "slow.mp4", "moved.jpg", "escape.mp4")]
        job = {"id": "fixture-media", "url": "https://example.invalid/media.mp4", "status": "completed",
               "title": "Invented media", "created_at": now, "updated_at": now, "platform": "direct",
               "files": files, "output_dir": "/downloads", "progress": 100, "video_quality": "best"}
        require(StateStore(DATA / "state.json").save({"jobs": [job], "queue": [], "paused": True,
                "download_dir": "/downloads", "hourly_job_limit": 40, "x_cookie_file": ""}))
        return {"files": files, "png_sha256": hashlib.sha256(PNG).hexdigest(), "png_size": len(PNG),
                "video_sha256": hashlib.sha256((folder / "video.mp4").read_bytes()).hexdigest()}
    if action == "move-media":
        (MEDIA / "fixture/moved.jpg").rename(MEDIA / "fixture/renamed.jpg")
        return {}
    raise RuntimeError("unknown fixture action")


if __name__ == "__main__":
    try:
        result = main(sys.argv[1])
        print(json.dumps({"receipt": os.environ["SSDL_DOCKER_ACCEPTANCE"], "result": result}))
    except Exception:
        print('{"fixture_error":true}')
        raise SystemExit(1)
