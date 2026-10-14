"""P2 contracts and fault simulations against an isolated app context."""
from contextlib import ExitStack
from collections import deque
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import test_queue_auth as queue_fixture
from ssdl import media, thumbnails
from ssdl.download_stats import DownloadStats
from ssdl.job_views import job_summary, job_page, file_page
from ssdl.media_selection import SelectionRequired, choice
from ssdl.request_policy import RequestPolicy
from ssdl.video_quality import VIDEO_QUALITIES


class P2AppTests(unittest.TestCase):
    setUp = queue_fixture.QueueAndAuthTests.setUp

    def prepare(self):
        values = {"ROOT": self.root, "_dynamic_capture": False, "_no_progress_timeout": 300,
                  "X_AUTH": Mock(), "ENVIRONMENT": Mock(), "THUMBNAILS": Mock()}
        for key, value in values.items():
            target, name = (self.app.state, key[1:]) if key.startswith("_") else (self.app, key)
            self.stack.enter_context(patch.object(target, name, value))
        self.app.X_AUTH.status.return_value = {"connected": False, "busy": False, "phase": "idle"}
        self.app.X_AUTH.cookies.return_value = {}
        self.app.THUMBNAILS.snapshot.return_value = {"status": "unavailable"}
        self.app.THUMBNAILS.status.return_value = {"ready": True}
        self.app.ENVIRONMENT.snapshot.return_value = {}
        self.app.STORAGE.snapshot.return_value = {"ready": True}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.Handler)
        self.stack.enter_context(patch.object(self.app, "PORT", self.server.server_port))
        self.stack.enter_context(patch.object(self.app.Handler, "log_message"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        def stop():
            self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.addCleanup(stop)
        # All URL validation in this suite is synthetic; network guard tests are separate.
        self.stack.enter_context(patch.object(self.app, "_valid_url", side_effect=lambda url: (True, url)))

    def request(self, path, body=None, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            headers = {"Origin": origin or f"http://127.0.0.1:{self.server.server_port}", "Content-Type": "application/json"}
            connection.request("POST" if body is not None else "GET", path,
                               body=json.dumps(body) if body is not None else None, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_unknown_job_routes_cannot_remove_existing_rows(self):
        self.prepare()
        code, result = self.request("/api/jobs", {"urls": ["https://example.org/page"]})
        self.assertEqual(code, 201)
        key = result["added"][0]
        for path in (f"/api/jobs/unknown/{key}", f"/api/jobs/{key}/details", f"/api/jobs/{key}/files"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path, {})[0], 404)
                self.assertIn(key, self.app.state.jobs)
                self.assertIn(key, self.app.state.queue)
        self.assertEqual(self.request(f"/api/jobs/{key}", {})[0], 200)
        self.assertNotIn(key, self.app.state.jobs)

    def test_pause_requires_explicit_boolean_without_saving_invalid_input(self):
        self.prepare()
        with patch.object(self.app, "_save_locked", return_value=0) as save:
            for starting in (False, True):
                self.app.state.paused = starting
                for body in ({}, *({"paused": value} for value in ("false", "true", 0, 1, None, [], {}))):
                    with self.subTest(starting=starting, body=body):
                        self.assertEqual(self.request("/api/pause", body)[0], 400)
                        self.assertIs(self.app.state.paused, starting)
                        save.assert_not_called()
            for value in (True, False):
                self.assertEqual(self.request("/api/pause", {"paused": value})[0], 200)
                self.assertIs(self.app.state.paused, value)
            self.assertEqual(save.call_count, 2)

    def test_connector_rejects_malformed_cookies_and_keeps_session_and_ticket(self):
        self.prepare()
        from ssdl import x_auth
        auth = x_auth.XAuthManager(self.root / "auth")
        self.stack.enter_context(patch.object(self.app, "X_AUTH", auth))
        self.stack.enter_context(patch.object(x_auth, "_dpapi", return_value=b"encrypted-fixture"))
        valid = {"domain": ".x.com", "name": "auth_token", "value": "synthetic-session", "expires": 0}
        auth.accept_extension(auth.prepare_extension(), [valid])
        saved = auth.secret_file.read_bytes()
        old_values = auth.cookies()
        token = auth.prepare_extension()
        invalid = [None, {}, [], [None], [valid] * 13, [valid, {**valid, "name": []}]]
        for field, values in {
            "name": ([], {}, None, "n" * 129),
            "domain": ([], {}, None, "d" * 254),
            "value": ([], {}, None, "v" * 8193, "invalid\nvalue"),
            "expires": ([], {}, None, True, -1, 10 ** 400),
        }.items():
            invalid.extend([{**valid, field: value}] for value in values)
        for cookies in invalid:
            with self.subTest(cookies_type=type(cookies).__name__):
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
                try:
                    connection.request("POST", "/api/auth/x/extension", json.dumps({"cookies": cookies}), {
                        "Content-Type": "application/json", "Origin": self.app.EXTENSION_ORIGIN,
                        "X-SSDL-Extension": self.app.EXTENSION_ID, "Authorization": "Bearer " + token,
                    })
                    response = connection.getresponse()
                    body = response.read().decode()
                    self.assertEqual(response.status, 400)
                    self.assertEqual(json.loads(body), {"error": "X 登入資料格式不正確。"})
                    self.assertNotIn(valid["value"], body)
                finally:
                    connection.close()
                self.assertEqual(auth.cookies(), old_values)
                self.assertTrue(auth.status()["connected"])
                self.assertEqual(auth.secret_file.read_bytes(), saved)
                self.assertEqual(auth._challenge, token)
        auth.accept_extension(token, [valid])
        self.assertEqual(auth._challenge, "")
        auth.accept_extension(auth.prepare_extension(), [valid])

    def test_state_snapshots_have_monotonic_scoped_sequence(self):
        self.prepare()
        _, first = self.request("/api/state")
        _, second = self.request("/api/summary")
        self.assertRegex(first["state_instance"], r"^[a-f0-9]{32}$")
        self.assertEqual(first["state_instance"], second["state_instance"])
        self.assertGreater(second["state_sequence"], first["state_sequence"])

    def test_quality_api_all_values_images_profiles_retry_and_invalid_types(self):
        self.prepare()
        for value in VIDEO_QUALITIES:
            code, result = self.request("/api/jobs", {"urls": ["https://example.org/page"], "video_quality": value})
            self.assertEqual(code, 201)
            key = result["added"][0]
            self.assertEqual(self.app.state.jobs[key]["video_quality"], value)
            self.app.state.jobs[key].update(status="failed", output_dir=str(self.root))
            self.app.state.queue.remove(key)
            code, result = self.request("/api/jobs", {"urls": ["https://example.org/page"], "video_quality": value})
            self.assertEqual(result["reused"], [key])
            self.assertEqual(self.app.state.jobs[key]["video_quality"], value)
        code, result = self.request("/api/jobs", {"urls": ["https://example.org/photo.png"], "video_quality": "720"})
        self.assertEqual(self.app.state.jobs[result["added"][0]]["video_quality"], "best")
        for value in (720, True, {}, "auto"):
            self.assertEqual(self.request("/api/jobs", {"urls": ["https://example.org/page"], "video_quality": value})[0], 400)
        self.assertEqual(self.request("/api/jobs", {"urls": ["@fixture"], "mode": "x_profile", "video_quality": "720"})[0], 400)
        code, result = self.request("/api/jobs", {"urls": ["https://example.org/default"]})
        self.assertEqual(self.app.state.jobs[result["added"][0]]["video_quality"], "best")

    def test_choice_api_validates_id_state_origin_and_persists_without_urls(self):
        self.prepare()
        options = [choice("a" * 24, "A", "https://cdn.example/a.mp4"), choice("b" * 24, "B", "https://cdn.example/b.mp4")]
        self.app.state.jobs["pick"] = {"id": "pick", "url": "https://example.org/page", "status": "selecting",
                                  "platform": "Web", "created_at": 1, "files": [], "selection_options": options,
                                  "video_quality": "720"}
        self.app._save_locked()
        self.app.state.jobs.clear(); self.app._load_saved_state()
        self.assertEqual(self.app.state.jobs["pick"]["status"], "selecting")
        self.assertEqual(list(self.app.state.queue), [])
        path = "/api/jobs/pick/select-media"
        self.assertEqual(self.request(path, {"selection_id": "a" * 24}, "https://outside.example")[0], 403)
        for identifier in ("https://cdn.example/a.mp4", "f" * 24, 1):
            self.assertEqual(self.request(path, {"selection_id": identifier})[0], 400)
        self.assertEqual(self.request(path, {"selection_id": "b" * 24})[0], 200)
        self.assertEqual(self.app.state.jobs["pick"]["selected_media"], "b" * 24)
        self.assertEqual(self.app.state.jobs["pick"]["video_quality"], "720")
        self.assertEqual(list(self.app.state.queue), ["pick"])
        self.assertEqual(self.request(path, {"selection_id": "b" * 24})[0], 409)
        self.assertNotIn("cdn.example/b.mp4", self.app.STATE_FILE.read_text(encoding="utf-8"))

    def test_selecting_releases_worker_and_propagates_dynamic_quality(self):
        self.prepare()
        queue_fixture.QueueAndAuthTests.jobs(self)
        self.app.state.dynamic_capture = True
        self.app.state.jobs["0"]["video_quality"] = "720"
        seen = []
        def run(payload, *args, **kwargs):
            seen.append(payload)
            if len(seen) == 1:
                raise SelectionRequired([choice("a" * 24, "A"), choice("b" * 24, "B")])
            self.app.state.shutdown.set()
            return {"files": [], "quality": "fixture", "title": "done"}
        with patch.object(self.app, "run_job", run):
            self.app._worker_loop()
        self.assertEqual(len(seen), 2)
        self.assertTrue(seen[0]["dynamic_capture"])
        self.assertEqual(seen[0]["video_quality"], "720")
        self.assertEqual(self.app.state.jobs["0"]["status"], "selecting")
        self.assertEqual(self.app.state.jobs["1"]["status"], "completed")
        self.assertIsNone(self.app.state.active_id)

    def test_cooling_platform_is_skipped_without_reordering_its_jobs(self):
        self.prepare()
        for key, url in [("x1", "https://x.com/a/status/1"), ("x2", "https://x.com/a/status/2"), ("y", "https://youtu.be/fixture")]:
            self.app.state.jobs[key] = {"id": key, "url": url, "platform": "X" if key.startswith("x") else "YouTube",
                                  "status": "queued", "created_at": 1, "files": []}
            self.app.state.queue.append(key)
        self.app.POLICY.limit(180, platform="X")
        def run(payload, *args, **kwargs):
            self.assertEqual(payload["url"], "https://youtu.be/fixture")
            self.app.state.shutdown.set()
            return {"files": [], "quality": "fixture", "title": "done"}
        with patch.object(self.app, "run_job", run):
            self.app._worker_loop()
        self.assertEqual(list(self.app.state.queue), ["x1", "x2"])
        self.assertEqual(self.app._quota_locked()["used"], 1)
        saved = self.app.POLICY.snapshot()
        restored = RequestPolicy(); restored.restore(saved)
        self.assertGreaterEqual(restored.snapshot("X")["cooldown_seconds"], 179)
        self.assertEqual(restored.snapshot("YouTube")["cooldown_seconds"], 0)
        restored.configure("global")
        self.assertGreaterEqual(restored.snapshot("YouTube")["cooldown_seconds"], 179)
        restored.configure("platform")
        self.assertGreaterEqual(restored.snapshot("YouTube")["cooldown_seconds"], 179)

    def test_dynamic_setting_persists_and_missing_dependency_is_rejected(self):
        self.prepare()
        body = {"download_dir": str(self.root), "dynamic_capture": True}
        with patch.object(self.app, "browser_capture_available", return_value=False):
            self.assertEqual(self.request("/api/settings", body)[0], 400)
        self.assertFalse(self.app.state.dynamic_capture)
        with patch.object(self.app, "browser_capture_available", return_value=True):
            self.assertEqual(self.request("/api/settings", body)[0], 200)
        self.app.state.dynamic_capture = False
        self.app._load_saved_state()
        self.assertTrue(self.app.state.dynamic_capture)
        body["dynamic_capture"] = "true"
        self.assertEqual(self.request("/api/settings", body)[0], 400)

    def test_state_summary_and_file_detail_routes_are_bounded_and_validate_parameters(self):
        self.prepare()
        for n in range(25):
            self.app.state.jobs[str(n)] = {"id": str(n), "url": f"https://example.org/{n}", "platform": "Web",
                "title": "Fixture", "status": "completed", "created_at": n, "files": [f"{i}.jpg" for i in range(250)],
                "warnings": ["warning fixture"], "error_detail": "detail fixture"}
        code, result = self.request("/api/state?page=2&page_size=20")
        self.assertEqual((code, len(result["jobs"]), result["jobs_page"]["page"]), (200, 5, 2))
        self.assertEqual(len(result["jobs"][0]["files"]), 20)
        code, result = self.request("/api/summary")
        self.assertEqual((code, result["jobs"], result["total_jobs"]), (200, [], 25))
        code, result = self.request("/api/jobs/0/files?offset=100&limit=100")
        self.assertEqual((code, len(result["files"]), result["next_offset"]), (200, 100, 200))
        self.assertEqual(self.request("/api/jobs/0/details")[1]["error_detail"], "detail fixture")
        for query in ("offset=-1", "limit=101", "offset=no", "limit=0"):
            self.assertEqual(self.request("/api/jobs/0/files?" + query)[0], 400)
        self.assertEqual(self.request("/api/jobs/missing/files")[0], 404)
        self.assertEqual(self.request("/api/jobs/0/files", origin="https://outside.example")[0], 403)
        self.assertEqual(len(self.app.state.jobs["0"]["files"]), 250)


class P2StorageTests(unittest.TestCase):
    def test_pagination_filters_and_bounded_file_views_do_not_change_history(self):
        jobs = [{"id": str(n), "created_at": n, "platform": "X" if n % 2 else "YouTube", "title": "FIXTURE",
                 "url": "https://example.org/", "status": "completed", "files": [f"{i}.jpg" for i in range(500)],
                 "warnings": ["fixture"], "error_detail": "private detail"} for n in range(200)]
        page, info = job_page(jobs, page=999, page_size=50, platform="X", search="fixture")
        self.assertEqual((len(page), info["page"], info["page_count"], info["total"]), (50, 2, 2, 100))
        summary = job_summary(jobs[0])
        self.assertEqual((len(summary["files"]), summary["file_count"], summary["warning_count"]), (20, 500, 1))
        self.assertNotIn("error_detail", summary)
        files = file_page(jobs[0], offset=450, limit=999)
        self.assertEqual(len(files["files"]), 50)
        self.assertIsNone(files["next_offset"])
        self.assertEqual(files["limit"], 100)
        self.assertEqual(len(jobs[0]["files"]), 500)
        self.assertEqual(job_page([], page=9)[1]["page"], 1)

    def test_capacity_replacement_overlay_background_scan_and_deleted_rescan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); source = root / "a.mp4"; source.write_bytes(b"a" * 10)
            stats = DownloadStats(); stats._directory = root; stats._generation = 1
            stats._scan(root, 1)
            source.write_bytes(b"a" * 20)
            stats.record_files(root, ["a.mp4", "a.mp4", "../outside.mp4"])
            stats.record_files(root, ["a.mp4"])
            self.assertEqual((stats._stats["total_bytes"], stats._stats["file_count"]), (20, 1))
            # A file updated after enumeration must overlay the background result.
            original_scan = os.scandir
            def scanning(path):
                source.write_bytes(b"a" * 30)
                stats.record_files(root, ["a.mp4"])
                return original_scan(path)
            stats._refreshing = True
            with patch("ssdl.download_stats.os.scandir", scanning):
                stats._scan(root, 1)
            self.assertEqual(stats._stats["total_bytes"], 30)
            source.unlink(); stats._scan(root, 1)
            self.assertEqual(stats._stats["file_count"], 0)

    def test_thumbnail_budget_age_clear_and_delete_failure_preserve_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); cache = thumbnails.ThumbnailCache(root, lambda: None)
            source = root / "original.png"; source.write_bytes(b"original")
            other = root / "custom.jpg"; other.write_bytes(b"keep")
            for n in range(3):
                path = root / (f"{n:064x}.jpg"); path.write_bytes(b"\xff\xd8" + b"x" * 10)
                os.utime(path, (time.time() - (100 if n == 0 else n),) * 2)
            with patch.object(thumbnails, "CACHE_FILES", 1), patch.object(thumbnails, "CACHE_AGE_SECONDS", 50):
                cache._maintain()
            self.assertEqual(len(cache._disk), 1)
            cache._clear_requested = True
            with patch.object(Path, "unlink", side_effect=PermissionError("fixture locked")):
                cache._maintain()
            self.assertTrue(cache._maintenance_error)
            cache._clear_requested = True; cache._maintain()
            self.assertEqual(cache._disk, {})
            self.assertEqual(source.read_bytes(), b"original")
            self.assertEqual(other.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
