"""Disposable synthetic account scan, IPC and state capacity probes; no platform traffic."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import io
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ssdl import ipc, persistence, x_account_media as account
from ssdl.json_budget import encode_json


def timed(callback):
    began = time.perf_counter()
    result = callback()
    return result, round((time.perf_counter() - began) * 1000, 3)


def measure_scan(posts):
    """Real planner/temporary JSONL; simulated all-cached file verification."""
    from gallery_dl.extractor.common import Message

    def items():
        for number in range(posts):
            data = {"tweet_id": str(1000000000000000000 + number), "author": {"name": "example"},
                    "user": {"name": "example"}, "count": 2}
            yield Message.Directory, "", data
            for index in (1, 2):
                yield Message.Url, "https://cdn.example/synthetic.jpg", {**data, "num": index, "extension": "jpg"}

    class CachedArchive:
        def __init__(self, *args): pass
        def lookup(self, post, expected, names):
            return [{"name": name, "size": 100} for name in names]
        def close(self): pass

    timeline = SimpleNamespace(category="twitter", subcategory="timeline", items=items, status=0,
                               session=Mock(), initialize=Mock(), _init_session=Mock())
    counters = {"progress_events": 0, "file_references_in_progress": 0, "plan_bytes": 0}
    handles, ready_at = [], None
    temporary_file = tempfile.TemporaryFile

    def capture_plan(*args, **kwargs):
        stream = temporary_file(*args, **kwargs)
        handles.append(stream)
        return stream

    def emit(event):
        nonlocal ready_at
        counters["progress_events"] += 1
        counters["file_references_in_progress"] += len(event.get("files", ()))
        if event.get("profile_stage") == "ready":
            ready_at = time.perf_counter()
            handles[-1].flush()
            counters["plan_bytes"] = os.fstat(handles[-1].fileno()).st_size

    with tempfile.TemporaryDirectory(prefix="ssdl-capacity-scan-") as directory, ExitStack() as stack:
        root = Path(directory)
        (root / "data").mkdir()
        stack.enter_context(patch.object(account.engines, "gallery_extractor", SimpleNamespace(find=lambda url: timeline)))
        stack.enter_context(patch.object(account.engines, "gallery_config", Mock()))
        stack.enter_context(patch.object(account.gallery, "configure_gallery"))
        stack.enter_context(patch.object(account.gallery, "_pace_gallery"))
        transfer = stack.enter_context(patch.object(account.gallery, "download_gallery", side_effect=AssertionError("Unexpected transfer")))
        stack.enter_context(patch.object(account.request_policy, "POLICY", Mock()))
        stack.enter_context(patch.object(account, "ProfileArchive", CachedArchive))
        stack.enter_context(patch.object(account.tempfile, "TemporaryFile", capture_plan))
        gate = Mock(side_effect=AssertionError("Cached post charged quota"))
        began = time.perf_counter()
        result = account.download_x_account("https://x.com/example", root / "downloads", emit,
            archive_file=root / "data" / "archive.sqlite3", before_post=gate, checkpoint=lambda: None,
            x_cookies={"auth_token": "synthetic-session"})
        ended = time.perf_counter()
        assert ready_at is not None and len(result["files"]) == posts * 2
        assert not transfer.called and not gate.called and all(stream.closed for stream in handles)
        assert not list(root.rglob("*.jpg"))
    return {"posts": posts, "files": posts * 2, "scan_ms": round((ready_at - began) * 1000, 3),
            "cached_verify_ms": round((ended - ready_at) * 1000, 3), **counters,
            "cleanup_verified": True, "verification": "Simulated archive hits; no media stat or SQLite costs",
            "progress": "Count file references only; do not serialize every progress message"}


def measure_ipc(files):
    value = {"files": [f"twitter/example/{number:012d}-" + "圖" * 64 + ".jpg" for number in range(files)]}
    logical = len(encode_json(value, ipc.MAX_MESSAGE_BYTES))
    with tempfile.TemporaryFile(mode="w+b") as stream:
        _, encode_write_ms = timed(lambda: ipc.write_message(stream, value))
        wire_bytes = stream.tell()
        stream.seek(0)
        decoded, decode_read_ms = timed(lambda: ipc.read_message(stream))
    assert decoded == value
    return {"files": files, "logical_bytes": logical, "wire_bytes": wire_bytes,
            "encode_write_ms": encode_write_ms, "decode_read_ms": decode_read_ms, "roundtrip_verified": True}


def measure_limits(limit):
    """Use the real budget by default; tests can inject a small equivalent boundary."""
    value = {"padding": ""}
    value["padding"] = "x" * (limit - len(encode_json(value, limit)))
    with patch.object(ipc, "MAX_MESSAGE_BYTES", limit), tempfile.TemporaryFile(mode="w+b") as stream:
        _, ipc_exact_ms = timed(lambda: ipc.write_message(stream, value))
        stream.seek(0)
        assert ipc.read_message(stream) == value
        value["padding"] += "x"
        rejected = io.BytesIO()
        try:
            ipc.write_message(rejected, value)
        except ipc.MessageTooLarge:
            assert not rejected.getvalue()
        else:
            raise AssertionError("IPC allowed limit + 1")
    del value
    with tempfile.TemporaryDirectory(prefix="ssdl-capacity-state-") as directory, \
            patch.object(persistence, "MAX_STATE_BYTES", limit):
        store = persistence.StateStore(Path(directory) / "state.json")
        state = {"jobs": [], "schema_version": persistence.SCHEMA_VERSION, "padding": ""}
        state["padding"] = "x" * (limit - len(encode_json(state, limit, indent=2)))
        ok, state_exact_ms = timed(lambda: store.save(state))
        assert ok and store.filename.stat().st_size == limit
        assert store.save(state) and store.backup.stat().st_size == limit
        def fingerprint(path):
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").digest()
        original = [fingerprint(path) for path in (store.filename, store.backup)]
        state["padding"] += "x"
        ok, state_over_ms = timed(lambda: store.save(state))
        assert not ok and store.status()["error_code"] == "state_too_large"
        assert store.filename.stat().st_size == store.backup.stat().st_size == limit
        assert [fingerprint(path) for path in (store.filename, store.backup)] == original
        assert store.load()["padding"] == state["padding"][:-1]
        assert store._read(store.backup)["padding"] == state["padding"][:-1]
        assert not list(store.filename.parent.glob("*.tmp"))
        # Saving a smaller record recovers capacity without losing the original
        # last-good record (which becomes the validated backup).
        assert store.save({"jobs": []}) and store.status()["healthy"]
    return {"limit_bytes": limit, "ipc_exact_ms": ipc_exact_ms, "state_exact_ms": state_exact_ms,
            "state_over_ms": state_over_ms, "exact_limit_accepted": True, "limit_plus_one_rejected": True,
            "no_partial_ipc": True, "primary_backup_preserved": True, "smaller_retry_verified": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts", type=int, default=5000, help="Synthetic cached posts, 1-100000")
    parser.add_argument("--files", type=int, default=90000, help="IPC filenames, 1-200000")
    parser.add_argument("--full-limits", action="store_true", help="Probe actual 64 MiB instead of the default 1 MiB")
    args = parser.parse_args(argv)
    if not 1 <= args.posts <= 100000 or not 1 <= args.files <= 200000:
        parser.error("--posts or --files is outside the supported range")
    print("Measuring isolated synthetic capacity...", file=sys.stderr, flush=True)
    report = {"format_version": 1, "environment": {"os": platform.system(), "python": platform.python_version()},
              "scope": "Temporary synthetic records; real JSONL, chunked IPC and durable state; simulated archive verification; no network/login",
              "scan": measure_scan(args.posts), "ipc": measure_ipc(args.files),
              "limits": measure_limits(persistence.MAX_STATE_BYTES if args.full_limits else 1024 * 1024)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
