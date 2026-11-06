"""Receipt-gated synthetic storage actions, streamed only into disposable fixtures."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import time

DATA, MEDIA, CACHE, BACKUPS = map(Path, ("/app/data", "/downloads", "/app/cache", "/backups"))
ORIGINAL = b"ssdl synthetic original bytes\0" * 4096
PARTIAL = b"ssdl synthetic partial bytes\0" * 32
PRIVATE = b"ssdl invented private history\0"


def databases(action):
    from ssdl.image_history import ImageHistory
    from ssdl.media_manifest import MediaManifest
    from ssdl.x_profiles import ProfileArchive
    result = {"files": ["fixture/original.bin"], "title": "Synthetic upgrade record", "quality": "original"}
    for kind, filename in ((ImageHistory, "image-history.sqlite3"), (MediaManifest, "media-manifest.sqlite3"),
                           (ProfileArchive, "x-profiles.sqlite3")):
        store = kind(DATA / filename, MEDIA, *(["fixture"] if kind is ProfileArchive else []))
        try:
            if action == "seed-databases":
                if kind is ProfileArchive:
                    store.record("1234567890", result["files"], 1)
                else:
                    store.record("https://example.invalid/upgrade", result)
            found = (store.lookup("1234567890", 1) if kind is ProfileArchive
                     else store.lookup("https://example.invalid/upgrade"))
            require(found and store.connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)])
        finally:
            store.close()
    return {"databases_verified": 3}


def require(condition):
    if not condition:
        raise RuntimeError("fixture condition failed")


def inventory():
    result = hashlib.sha256()
    count = 0
    for label, root in (("data", DATA), ("media", MEDIA)):
        for path in sorted(root.rglob("*")):
            require(not path.is_symlink())
            if not path.is_file() or path.name == ".ssdl.lock":
                continue
            require(path.stat().st_size <= 4 * 1024 * 1024)
            result.update((label + "/" + path.relative_to(root).as_posix()).encode() + b"\0")
            result.update(hashlib.sha256(path.read_bytes()).digest())
            count += 1
    return {"sha256": result.hexdigest(), "files": count}


def seed():
    from ssdl.persistence import StateStore
    require(not any(path.name not in {".ssdl.lock", "state.json", "state.json.bak"} for path in DATA.iterdir()))
    if (DATA / "state.json").exists():
        require(StateStore(DATA / "state.json")._read(DATA / "state.json")["jobs"] == [])
    (MEDIA / "fixture").mkdir()
    (MEDIA / "fixture/original.bin").write_bytes(ORIGINAL)
    (MEDIA / "fixture/incomplete.part").write_bytes(PARTIAL)
    (DATA / "fixture-private.bin").write_bytes(PRIVATE)
    (CACHE / "excluded-cache.bin").write_bytes(b"disposable cache")
    now = time.time()
    jobs = [{"id": "fixture-completed", "url": "https://example.invalid/completed.bin", "status": "completed",
             "created_at": now, "updated_at": now, "title": "Synthetic original", "platform": "direct",
             "files": ["fixture/original.bin"], "output_dir": "/downloads", "size_bytes": len(ORIGINAL),
             "video_quality": "best", "progress": 100},
            {"id": "fixture-queued", "url": "https://example.invalid/pending.bin", "status": "queued",
             "created_at": now + 1, "title": "Synthetic pending", "platform": "direct", "files": [],
             "video_quality": "best", "progress": 0}]
    require(StateStore(DATA / "state.json").save({"jobs": jobs, "queue": ["fixture-queued"], "paused": True,
            "download_dir": "/downloads", "hourly_job_limit": 73, "x_cookie_file": ""}))
    databases("seed-databases")
    return verify()


def verify():
    from ssdl.persistence import StateStore
    state = StateStore(DATA / "state.json")._read(DATA / "state.json")
    require(state["paused"] is True and state["hourly_job_limit"] == 73
            and state["queue"] == ["fixture-queued"] and len(state["jobs"]) == 2)
    require((MEDIA / "fixture/original.bin").read_bytes() == ORIGINAL
            and (MEDIA / "fixture/incomplete.part").read_bytes() == PARTIAL
            and (DATA / "fixture-private.bin").read_bytes() == PRIVATE)
    databases("verify-databases")
    return {"verified": True, "original_sha256": hashlib.sha256(ORIGINAL).hexdigest()}


def archive_info():
    paths = list(BACKUPS.glob("ssdl-*.tar"))
    require(len(paths) == 1)
    path = paths[0]
    require(path.stat().st_size <= 4 * 1024 * 1024)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    require((BACKUPS / (path.name + ".sha256")).read_text().strip() == digest)
    with tarfile.open(path) as archive:
        names = set(archive.getnames())
        require({"ssdl-backup.json", "data/state.json", "data/fixture-private.bin", "media/fixture/original.bin",
                 "media/fixture/incomplete.part"} <= names)
        require(all("cache" not in name and ".ssdl.lock" not in name and ".ssdl-restore-" not in name for name in names))
    return {"archive": path.name, "sha256": digest}


def main():
    receipt = os.environ.get("SSDL_DOCKER_ACCEPTANCE", "")
    require(re.fullmatch(r"[0-9a-f]{32}", receipt) is not None and sys.platform == "linux")
    action = sys.argv[1]
    os.umask(0o077)
    sys.path[:0] = ["/app", "/app/docker"]
    if action == "init-backups":
        require(os.getuid() == 0 and os.path.ismount(BACKUPS) and not any(BACKUPS.iterdir()))
        os.chown(BACKUPS, 10001, 10001)
        os.chmod(BACKUPS, 0o700)
        return {"initialized": True}
    if action == "import-owned":
        require(os.getuid() == 0 and os.path.ismount(BACKUPS)
                and re.fullmatch(r"ssdl-[A-Za-z0-9-]+\.tar", sys.argv[2]) is not None)
        for suffix in ("", ".sha256"):
            target = BACKUPS / (sys.argv[2] + suffix)
            info = target.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 4 * 1024 * 1024)
            os.chown(target, 10001, 10001)
            os.chmod(target, 0o600)
        return {"ownership_set": True}
    require(os.getuid() == 10001)
    if action == "hold":
        time.sleep(900)
        return {}
    if action == "permissions":
        from runtime import prepare_storage
        prepare_storage()
        for directory, mode in ((DATA, 0o700), (CACHE, 0o700), (MEDIA, 0o750)):
            info = directory.stat()
            require(info.st_uid == info.st_gid == 10001 and stat.S_IMODE(info.st_mode) == mode)
        return {"uid": 10001, "modes_verified": True}
    if action in {"seed", "verify", "inventory", "archive-info"}:
        return {"seed": seed, "verify": verify, "inventory": inventory, "archive-info": archive_info}[action]()
    if action == "verify-databases":
        return databases(action)
    if action == "cache-empty":
        require(not (CACHE / "excluded-cache.bin").exists())
        return {"cache_excluded": True}
    if action == "deny-writes":
        os.chmod(DATA, 0o500)
        return {"write_denied": True}
    if action == "allow-writes":
        os.chmod(DATA, 0o700)
        return {"write_restored": True}
    if action == "empty":
        require(all(not any(path.name != ".ssdl.lock" for path in root.iterdir()) for root in (DATA, MEDIA)))
        return {"empty": True}
    if action == "corrupt":
        original = archive_info()["archive"]
        name = "ssdl-corrupt-" + receipt + ".tar"
        payload = bytearray((BACKUPS / original).read_bytes())
        payload[0] ^= 1
        (BACKUPS / name).write_bytes(payload)
        shutil.copyfile(BACKUPS / (original + ".sha256"), BACKUPS / (name + ".sha256"))
        return {"archive": name}
    if action == "interrupt-restore":
        import storage
        original_sync = storage.sync_directory
        def interrupt(directory):
            original_sync(directory)
            if directory == DATA and (DATA / storage.RESTORE_MARKER).exists() and (DATA / "state.json").exists():
                os._exit(75)  # Actual abrupt process exit after first-volume promotion.
        storage.sync_directory = interrupt
        sys.argv = ["storage.py", "restore", sys.argv[2]]
        raise SystemExit(storage.main())
    if action == "interrupted":
        require((DATA / ".ssdl-restore-incomplete").is_file()
                and (DATA / "state.json").is_file()
                and any(MEDIA.glob(".ssdl-restore-*")))
        return {"interruption_retained": True}
    raise RuntimeError("unknown fixture action")


if __name__ == "__main__":
    try:
        print(json.dumps({"receipt": os.environ.get("SSDL_DOCKER_ACCEPTANCE"), "result": main()}, sort_keys=True))
    except Exception:
        print('{"fixture_error":true}')
        raise SystemExit(1)
