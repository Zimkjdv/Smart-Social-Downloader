"""Real headless Chrome UI, with a synthetic API and no personal state."""
import copy
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
import time
import unittest
from urllib.parse import parse_qs, urlparse

from ssdl.browser_media import available, browser_driver
from ssdl.job_views import job_page, job_summary
from ssdl.video_quality import VIDEO_QUALITIES

ROOT = Path(__file__).resolve().parents[1]


class BrowserFixtureServer(ThreadingHTTPServer):
    # Chrome fetches the deferred scripts/styles in parallel. Keep the fixture's
    # listen backlog aligned with the application instead of the default five.
    request_queue_size = 64


def environment():
    return {"phase": "complete", "busy": False, "ready": True, "checked_at": 1,
            "status": "ok", "errors": 0, "warnings": 0, "port": 8765, "checks": []}


@unittest.skipUnless(available(), "optional Playwright and Google Chrome are required")
class BrowserUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs, cls.writes, cls.settings = [], [], {}
        class Handler(BaseHTTPRequestHandler):
            def send_json(self, value, code=200):
                self.send_bytes(json.dumps(value).encode(), "application/json", code)
            def send_bytes(self, value, mime, code=200):
                self.send_response(code); self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(value))); self.end_headers(); self.wfile.write(value)
            def state(self):
                params = parse_qs(urlparse(self.path).query)
                view = {key: params.get(key, [default])[0] for key, default in
                        [("status", "all"), ("platform", "all"), ("search", "")]}
                view.update(page=int(params.get("page", [1])[0]), page_size=int(params.get("page_size", [20])[0]))
                page, pagination = job_page(cls.jobs, **view)
                return {"jobs": [job_summary(job) for job in page], "jobs_page": pagination,
                    "total_jobs": len(cls.jobs), "platforms": ["Web"], "active_job": None,
                    "counts": {name: sum(job["status"] == name for job in cls.jobs) for name in
                               ["queued", "active", "completed", "failed", "selecting"]},
                    "paused": cls.paused, "ready": True, "download_dir": "fixture-downloads", "x_cookie_file": "",
                    "databases": cls.database_report,
                    "x_auth": {"connected": False, "busy": False, "phase": "idle", **cls.x_storage},
                    "safe_queue": {"enabled": True, "phase": "idle", "cooldown_mode": "platform"},
                    "rate_limit": {"used": cls.rate_used, "limit": 40}, "storage": {"ready": True},
                    "environment": environment(), "persistence": {"healthy": True, "error": "", "blocked": False},
                    "worker": {"alive": True, "phase": "idle"}, "no_progress_timeout": 300,
                    "dynamic_capture": cls.settings.get("dynamic_capture", False), "browser_capture_available": True,
                    "app_version": "fixture", "thumbnail_cache": {"ready": True}}
            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/api/jobs/missing/content":
                    time.sleep(.25)
                    return self.send_json({"error": "synthetic missing file"}, 404)
                if path == "/api/environment": return self.send_json(environment())
                if path == "/api/ui-preferences": return self.send_json({"preferences": cls.preferences})
                if path == "/api/databases": return self.send_json(cls.database_report)
                if path.startswith("/api/jobs/") and path.endswith("/files"):
                    params = parse_qs(urlparse(self.path).query)
                    offset, limit = int(params.get("offset", [0])[0]), int(params.get("limit", [100])[0])
                    job = next(job for job in cls.jobs if job["id"] == path.split("/")[3])
                    files = job.get("files", [])
                    end = min(len(files), offset + limit)
                    return self.send_json({"job_id": job["id"], "total": len(files), "offset": offset,
                        "limit": limit, "next_offset": end if end < len(files) else None,
                        "files": [{"index": index, "filename": files[index]} for index in range(offset, end)]})
                if path.startswith("/api/"): return self.send_json(self.state())
                if path in {"/", "/chrome-connect"}:
                    filename = "index.html" if path == "/" else "chrome-connect.html"
                    return self.send_bytes((ROOT / "static" / filename).read_bytes(), "text/html")
                candidate = ROOT / path.lstrip("/")
                if path.startswith("/static/") and candidate.resolve().parent == ROOT / "static" and candidate.is_file():
                    return self.send_bytes(candidate.read_bytes(), "text/css" if candidate.suffix == ".css" else "application/javascript")
                self.send_error(404)
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                path = urlparse(self.path).path; cls.writes.append((path, payload))
                if path == "/api/ui-preferences":
                    cls.preferences = payload
                    return self.send_json({"preferences": cls.preferences})
                if path == "/api/databases":
                    cls.database_report.update(revision=cls.database_report["revision"] + 1, ready=True,
                        phase="complete", operation=payload["action"], backup_name="backup-20261015-000000-aaaaaaaaaaaa", backup_bytes=4096)
                    return self.send_json(cls.database_report, 202)
                if path == "/api/jobs":
                    key = str(len(cls.jobs) + 1)
                    cls.jobs.append({"id": key, "url": payload["urls"][0], "title": "Fixture " + key,
                                     "platform": "Web", "status": "queued", "created_at": len(cls.jobs) + 1,
                                     "files": [], "video_quality": payload["video_quality"]})
                    return self.send_json({"added": [key], "reused": [], "already_pending": [], "rejected": [], "state": self.state()}, 201)
                if path == "/api/settings": cls.settings.update(payload)
                if path == "/api/rate/reset":
                    previous = cls.rate_used; cls.rate_used = 0
                    return self.send_json({"previous_used": previous, "state": self.state()})
                if path.endswith("/select-media"):
                    job = next(job for job in cls.jobs if job["id"] == path.split("/")[3])
                    job.update(status="queued", selected_media=payload["selection_id"])
                    job.pop("selection_options")
                return self.send_json(self.state())
            def log_message(self, *args): pass
        cls.server = BrowserFixtureServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.driver_context = browser_driver(True); cls.driver = cls.driver_context.__enter__()
        cls.browser = cls.driver.runtime.chromium.launch(headless=True, channel="chrome")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.driver_context.__exit__(None, None, None)
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def setUp(self):
        self.jobs.clear(); self.writes.clear(); self.settings.clear()
        type(self).preferences = None
        type(self).x_storage = {}
        type(self).rate_used = 3
        type(self).paused = False
        type(self).database_report = {"instance": "a" * 32, "revision": 0, "ready": False, "busy": False,
            "phase": "idle", "operation": "", "checked_at": 0, "entries": [], "total_bytes": 0,
            "reclaimable_bytes": 0, "backup_name": "", "backup_bytes": 0, "error_code": "", "result_code": ""}
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        self.addCleanup(self.context.close)
        self.page = self.context.new_page(); self.errors = []
        self.asset_failures = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("requestfailed", lambda request: self.record_asset_failure(
            request, request.failure))
        self.page.on("response", lambda response: self.record_asset_failure(
            response.request, f"HTTP {response.status}") if response.status >= 400 else None)

    def record_asset_failure(self, request, error):
        path = urlparse(request.url).path
        if request.resource_type in {"script", "stylesheet"} and path.startswith("/static/"):
            self.asset_failures.append(f"{path}: {error}")

    def load(self):
        self.page.goto(f"http://127.0.0.1:{self.server.server_port}/")
        self.wait_for_snapshot()

    def wait_for_snapshot(self):
        # goto/reload wait for deferred scripts. Fail on the underlying resource
        # or JS error before evaluating a global whose script may never load.
        self.assertEqual(self.asset_failures, [], "Dashboard assets failed to load")
        self.assert_no_errors()
        self.assertTrue(self.page.evaluate("typeof lastResponse !== 'undefined'"),
                        "Dashboard bootstrap did not declare lastResponse")
        self.page.wait_for_function("lastResponse !== null")
        self.assert_no_errors()

    def assert_no_errors(self):
        self.assertEqual(self.errors, [])

    def test_fixture_accepts_browser_connection_burst_before_serving(self):
        # Exercise the real listener with pending connections, without relying
        # on CPU scheduling to make a browser resource load fail intermittently.
        with type(self.server)(("127.0.0.1", 0), BaseHTTPRequestHandler) as server, ExitStack() as sockets:
            for _ in range(8):
                sockets.enter_context(socket.create_connection(server.server_address, timeout=.5))

    def test_missing_bootstrap_asset_fails_with_resource_diagnostic(self):
        self.page.route("**/static/ui_state.js", lambda route: route.abort())
        with self.assertRaisesRegex(AssertionError, "/static/ui_state.js"):
            self.load()

    def test_bootstrap_script_exception_is_reported_before_snapshot_wait(self):
        self.page.route("**/static/ui_state.js", lambda route: route.fulfill(
            content_type="application/javascript", body="throw new Error('fixture bootstrap exception');"))
        with self.assertRaisesRegex(AssertionError, "fixture bootstrap exception"):
            self.load()

    def test_every_quality_submitted_and_profile_mode_restores_video_draft(self):
        self.load(); page = self.page
        self.assertEqual(page.locator("#video-quality").input_value(), "best")
        for value in VIDEO_QUALITIES:
            page.locator("#video-quality").select_option(value)
            page.locator("#url-input").fill(f"https://example.org/{value}")
            with page.expect_response(lambda response: response.request.method == "POST" and urlparse(response.url).path == "/api/jobs"):
                page.locator("#add-jobs").click()
            page.wait_for_function("!document.querySelector('#add-jobs').disabled")
            self.assertEqual(self.writes[-1][1]["video_quality"], value)
        page.locator("#video-quality").select_option("720")
        page.locator('[data-download-mode="x_profile"]').click()
        self.assertFalse(page.locator("#video-quality-controls").is_visible())
        page.locator("#url-input").fill("@fixture")
        with page.expect_response(lambda response: response.request.method == "POST" and urlparse(response.url).path == "/api/jobs"):
            page.locator("#add-jobs").click()
        self.assertEqual(self.writes[-1][1]["video_quality"], "best")
        page.wait_for_function("!document.querySelector('#add-jobs').disabled")
        page.locator('[data-download-mode="urls"]').click()
        self.assertEqual(page.locator("#video-quality").input_value(), "720")
        self.assert_no_errors()

    def test_batch_rejections_show_original_inputs_and_retry_only_those_items(self):
        self.load()
        page = self.page
        snapshot = page.evaluate("lastResponse")
        accepted = "https://example.org/accepted"
        shared_prefix = "https://example.org/" + "a" * 140
        rejected = [shared_prefix + "-first", shared_prefix + "-last"]
        items = [
            {"input_index": 0, "url": shared_prefix[:120], "error": "網址過長"},
            {"input_index": 2, "url": shared_prefix[:120], "error": "不接受本機網址"},
        ]
        route_pattern = "**/api/jobs*"
        page.route(route_pattern, lambda route: route.fulfill(status=201, json={
            "added": ["accepted"], "reused": [], "already_pending": [], "rejected": items, "state": snapshot,
        }))
        draft = page.locator("#url-input")
        draft.fill("\n".join([rejected[0], accepted, rejected[1]]))
        page.locator("#add-jobs").click()
        details = page.locator("#batch-rejections")
        details.locator("summary").wait_for(state="visible")
        self.assertEqual(details.locator("li code").all_text_contents(), rejected)
        self.assertEqual(details.locator("li p").all_text_contents(), ["網址過長", "不接受本機網址"])
        page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        summary = details.locator("summary")
        summary.focus()
        page.keyboard.press("Enter")
        self.assertFalse(details.locator("li").first.is_visible())
        page.keyboard.press("Enter")
        page.locator("#language-toggle").click()
        self.assertEqual(summary.inner_text(), "Items not added")
        self.assertEqual(details.locator("li p").all_text_contents(), ["The URL is too long", "Local URLs are not accepted"])

        summary.focus()
        page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("document.activeElement.id"), "edit-rejected-inputs")
        page.keyboard.press("Enter")
        self.assertEqual(page.evaluate("document.activeElement.id"), "url-input")
        self.assertEqual(draft.input_value(), "\n".join(rejected))
        corrected = ["https://example.org/corrected-first", "https://example.org/corrected-last"]
        draft.fill("\n".join(corrected))
        page.unroute(route_pattern)
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  urlparse(response.url).path == "/api/jobs") as reply:
            page.locator("#add-jobs").click()
        self.assertEqual(reply.value.request.post_data_json["urls"], corrected)
        page.wait_for_function("!document.querySelector('#add-jobs').disabled")
        self.assertEqual(draft.input_value(), "")
        self.assertFalse(details.is_visible())
        self.assert_no_errors()

    def test_entire_batch_rejection_preserves_new_draft_when_switching_modes(self):
        self.load()
        page = self.page
        snapshot = page.evaluate("lastResponse")
        held = []
        page.route("**/api/jobs*", lambda route: held.append(route))
        draft = page.locator("#url-input")
        submitted = "missing-scheme"
        draft.fill(submitted)
        with page.expect_request(lambda request: request.method == "POST" and urlparse(request.url).path == "/api/jobs"):
            page.locator("#add-jobs").click()
        draft.fill("new draft")
        page.locator('[data-download-mode="pixiv_profile"]').click()
        draft.fill("4321")
        held[0].fulfill(status=201, json={
            "added": [], "reused": [], "already_pending": [], "state": snapshot,
            "rejected": [{"input_index": 0, "url": submitted, "error": "網址格式不正確"}],
        })
        page.wait_for_function("!document.querySelector('#add-jobs').disabled")
        self.assertEqual(draft.input_value(), "4321")
        self.assertFalse(page.locator("#batch-rejections").is_visible())
        page.locator('[data-download-mode="urls"]').click()
        self.assertEqual(draft.input_value(), "new draft")
        self.assertEqual(page.locator("#batch-rejection-list li code").inner_text(), submitted)
        self.assertTrue(page.locator("#rejected-draft-changed").is_visible())
        self.assertFalse(page.locator("#edit-rejected-inputs").is_visible())
        self.assert_no_errors()

    def test_settings_draft_language_tabs_keyboard_and_focus_return(self):
        self.load(); page = self.page
        page.locator("#settings-open").click()
        page.locator("#download-dir").fill("fixture-draft")
        page.locator("#dynamic-capture").check()
        page.locator("#settings-tab-general").focus(); page.keyboard.press("ArrowRight")
        self.assertEqual(page.locator("#settings-tab-pixiv").get_attribute("aria-selected"), "true")
        page.keyboard.press("ArrowRight")
        self.assertEqual(page.locator("#settings-tab-x").get_attribute("aria-selected"), "true")
        page.keyboard.press("ArrowRight")
        self.assertEqual(page.locator("#settings-tab-diagnostics").get_attribute("aria-selected"), "true")
        page.locator("#settings-tab-general").click()
        self.assertEqual(page.locator("#download-dir").input_value(), "fixture-draft")
        self.assertTrue(page.locator("#dynamic-capture").is_checked())
        page.locator("#settings-save").focus(); page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("document.activeElement.id"), "settings-close")
        self.assertTrue(page.locator("main").evaluate("el => Boolean(el.closest('[inert]'))"))
        page.keyboard.press("Escape")
        page.wait_for_function("document.activeElement.id === 'settings-open'")
        page.locator("#language-toggle").click()
        self.assertEqual(page.locator("#settings-open").get_attribute("aria-label"), "Download settings")
        page.locator("#settings-open").click()
        page.locator("#settings-modal").wait_for(state="visible")
        self.assertEqual(page.locator("#dynamic-capture").is_checked(), False)
        page.locator("#dynamic-capture").check()
        with page.expect_response(lambda response: response.request.method == "POST" and urlparse(response.url).path == "/api/settings"):
            page.locator("#settings-save").click()
        self.assertTrue(self.settings["dynamic_capture"])
        page.wait_for_function("document.querySelector('#settings-modal').classList.contains('hidden')")
        self.assert_no_errors()

    def test_player_selection_narrow_view_keyed_rows_pagination_and_refresh(self):
        self.jobs.extend({"id": str(n), "title": "Fixture " + str(n), "url": f"https://example.org/{n}",
                          "platform": "Web", "status": "completed", "created_at": n, "files": []} for n in range(25))
        job = self.jobs[-1]; job.update(status="selecting", selection_options=[
            {"id": "a" * 24, "title": "A", "host": "cdn.example", "variants": 2, "kind": "video"},
            {"id": "b" * 24, "title": "B", "host": "cdn.example", "variants": 1, "kind": "video"}])
        self.load(); page = self.page
        page.evaluate("window.savedRow = document.querySelector('tr[data-job-id=\"24\"]'); window.savedCell = savedRow.children[0]")
        page.evaluate("refresh()")
        self.assertTrue(page.evaluate("savedRow === document.querySelector('tr[data-job-id=\"24\"]') && savedCell === savedRow.children[0]"))
        trigger = page.locator('[data-select-media="24"]'); trigger.click()
        page.locator("#media-selection-close").focus(); page.keyboard.press("Shift+Tab")
        self.assertEqual(page.evaluate("document.activeElement.id"), "media-selection-cancel")
        page.keyboard.press("Escape")
        page.wait_for_function("document.activeElement.matches('[data-select-media=\"24\"]')")
        trigger.click()
        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/select-media")):
            page.locator('[data-selection-id="' + "b" * 24 + '"]').click()
        page.wait_for_function("document.querySelector('#media-selection-modal').classList.contains('hidden')")
        self.assertEqual(job["selected_media"], "b" * 24)
        page.locator("#jobs-page-size").select_option("10")
        page.wait_for_function("state.pageSize === 10 && state.jobs.length === 10")
        page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        page.reload(); self.wait_for_snapshot()
        self.assertEqual(page.locator("#jobs-page-size").input_value(), "10")
        self.assertEqual(job["status"], "queued")
        self.assert_no_errors()

    def test_preferences_save_after_back_forward_cache_restore(self):
        type(self).preferences = {"schema": 1, "language": "zh-Hant", "page_size": 20}
        # Playwright disables the back/forward cache by default.
        browser = self.driver.runtime.chromium.launch(
            headless=True, channel="chrome", ignore_default_args=["--disable-back-forward-cache"])
        self.addCleanup(browser.close)
        page = browser.new_page()
        page.add_init_script("addEventListener('pageshow', event => { window.fromHistoryCache = event.persisted; });")
        origin = f"http://127.0.0.1:{self.server.server_port}"
        with page.expect_response("**/api/ui-preferences"):
            page.goto(origin)
        page.wait_for_function("lastResponse !== null")
        page.goto(origin + "/chrome-connect")
        page.go_back(wait_until="commit")
        self.assertTrue(page.evaluate("window.fromHistoryCache"), "Dashboard was not restored from Chrome's cache")
        page.go_forward(wait_until="commit")
        page.go_back(wait_until="commit")
        self.assertTrue(page.evaluate("window.fromHistoryCache"), "Dashboard was not restored a second time")

        def preference_saved(response):
            return urlparse(response.url).path == "/api/ui-preferences" and response.request.method == "POST"

        with page.expect_response(preference_saved, timeout=3000) as language:
            page.locator("#language-toggle").click()
        self.assertEqual(language.value.request.post_data_json["language"], "en")
        with page.expect_response(preference_saved, timeout=3000) as page_size:
            page.locator("#jobs-page-size").select_option("50")
        self.assertEqual(page_size.value.request.post_data_json["page_size"], 50)

        fresh = browser.new_page()
        fresh.goto(origin)
        fresh.wait_for_function("document.documentElement.lang === 'en' && state.pageSize === 50")
        self.assertEqual(fresh.locator("#jobs-page-size").input_value(), "50")

        # Hold a write open so reload can exercise cancellation without waiting
        # for the real HTTP deadline or changing the preferences in the fixture.
        page.evaluate("""() => {
            const fetchFromServer = window.fetch;
            window.fetch = (path, options) => {
                if (path.split('?')[0] !== '/api/ui-preferences' || options.method !== 'POST') {
                    return fetchFromServer(path, options);
                }
                window.preferenceWritePending = true;
                return new Promise((resolve, reject) => {
                    options.signal.addEventListener('abort', () => {
                        sessionStorage.setItem('preference-write-aborted', 'true');
                        reject(options.signal.reason);
                    }, {once: true});
                });
            };
        }""")
        page.locator("#jobs-page-size").select_option("10")
        page.wait_for_function("window.preferenceWritePending")
        page.reload()
        self.assertEqual(page.evaluate("sessionStorage.getItem('preference-write-aborted')"), "true")

    def test_x_login_storage_copy_reflects_reported_mode(self):
        page = self.page

        def setup_response(route):
            route.fulfill(json={"extension_dir": "", "extension_id": "fixture", **self.x_storage})

        page.route("**/api/auth/x/setup", setup_response)
        for mode, chinese, english in (
            (None, "保存方式會依目前設定顯示", "The storage method is shown for your configuration"),
            ("dpapi", "同一 Windows 使用者", "same Windows user"),
            ("memory", "服務重啟後需重新連接", "Reconnect after a service restart"),
            ("aes-gcm", "相同金鑰與資料目錄", "the same key and data directory"),
        ):
            with self.subTest(mode=mode):
                type(self).x_storage = {} if mode is None else {"storage_mode": mode}
                for path, selector in (("/", "#x-storage-copy"), ("/chrome-connect", "#session-storage-copy")):
                    page.goto(f"http://127.0.0.1:{self.server.server_port}{path}")
                    if path == "/":
                        self.wait_for_snapshot()
                        page.locator("#settings-open").click()
                        page.locator("#settings-tab-x").click()
                    for language, copy in (("zh-Hant", chinese), ("en", english)):
                        page.evaluate("(language) => I18n.change(language, false)", language)
                        page.locator(selector).filter(has_text=copy).wait_for(state="visible")
                self.assert_no_errors()

    def test_advanced_cookie_field_is_reachable_from_summary_with_keyboard(self):
        self.load(); page = self.page
        page.locator("#settings-open").click()
        page.locator("#settings-tab-x").click()
        summary = page.locator("#settings-panel-x .advanced-cookies > summary")
        summary.focus(); page.keyboard.press("Enter"); page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("document.activeElement.id"), "x-cookie-file")
        page.keyboard.press("Shift+Tab")
        self.assertEqual(page.evaluate("document.activeElement.tagName"), "SUMMARY")
        page.keyboard.press("Escape")
        page.wait_for_function("document.activeElement.id === 'settings-open'")
        self.assert_no_errors()

    def test_rate_dialog_cancels_without_writing_and_confirm_updates_usage_once(self):
        self.load(); page = self.page
        page.locator("#top-rate").click()
        self.assertTrue(page.locator("#rate-confirm-dialog").evaluate("el => el.open"))
        page.locator("#rate-confirm-cancel").click()
        self.assertFalse([entry for entry in self.writes if entry[0] == "/api/rate/reset"])
        page.locator("#top-rate").click()
        with page.expect_response(lambda response: response.request.method == "POST" and urlparse(response.url).path == "/api/rate/reset"):
            page.locator("#rate-confirm-submit").click()
        page.wait_for_function("!document.querySelector('#rate-confirm-dialog').open")
        self.assertEqual(page.locator("#top-rate-used").inner_text(), "0")
        self.assertEqual(len([entry for entry in self.writes if entry[0] == "/api/rate/reset"]), 1)
        page.wait_for_function("document.activeElement.id === 'top-rate'")
        self.assert_no_errors()

    def test_file_picker_pages_and_opens_exact_file_without_repeating_the_action(self):
        files = [f"web/synthetic-{index}.png" for index in range(120)]
        self.jobs.append({"id": "files", "title": "Synthetic album", "url": "https://example.org/album",
                          "platform": "Web", "status": "completed", "created_at": 1, "files": files})
        self.load(); page = self.page
        page.locator('.row-icon-button[data-open-media="files"]').click()
        choices = page.locator("#file-picker-list .file-choice:not(#file-picker-more)")
        page.wait_for_function("document.querySelectorAll('#file-picker-list .file-choice:not(#file-picker-more)').length === 100")
        page.locator("#file-picker-more").click()
        page.wait_for_function("document.querySelectorAll('#file-picker-list .file-choice:not(#file-picker-more)').length === 120")
        with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/open-file")):
            choices.nth(100).click()
        page.wait_for_function("document.querySelector('#file-picker-modal').classList.contains('hidden')")
        opened = [entry for entry in self.writes if entry[0].endswith("/open-file")]
        self.assertEqual(opened, [("/api/jobs/files/open-file", {"file_index": 100, "filename": files[100]})])
        self.assert_no_errors()

    def test_every_fixed_locale_key_matches_and_html_keys_exist(self):
        self.load()
        result = self.page.evaluate("""() => {
            const locales = window.SSDLMessages;
            const invalid = Object.entries(locales).filter(([key, value]) =>
                Object.keys(value).sort().join(',') !== 'en,zh-Hant' ||
                typeof value.en !== 'string' || typeof value['zh-Hant'] !== 'string').map(([key]) => key);
            const missing = [...document.querySelectorAll('*')].flatMap(el => [...el.attributes]
                .filter(attr => attr.name.startsWith('data-i18n-') && !locales[attr.value]).map(attr => attr.value));
            return {count: Object.keys(locales).length, invalid, missing};
        }""")
        self.assertGreater(result['count'], 610)
        self.assertEqual(result['invalid'], [])
        self.assertEqual(result['missing'], [])
        self.assert_no_errors()

    def test_missing_media_gate_waits_for_navigation_from_reserved_blank_page(self):
        from tools.docker_browser_acceptance import check_missing_media
        self.jobs.append({"id": "missing", "title": "Synthetic missing file", "url": "https://example.org/album",
                          "platform": "Web", "status": "completed", "created_at": 1, "files": ["missing.png"]})
        self.load(); page = self.page
        page.evaluate("state.fileActions = 'browser'")
        with page.expect_popup() as opened:
            page.locator('.row-icon-button[data-open-media="missing"]').click()
        popup = opened.value
        try:
            check_missing_media(self.context, popup, f"http://127.0.0.1:{self.server.server_port}")
        finally:
            popup.close()
        self.assert_no_errors()

    def test_desktop_adapter_exports_diagnostics_as_a_real_browser_download(self):
        self.load(); page = self.page
        report = {"format_version": 1, "created_at": 1, "counts": {}, "jobs": [], "environment": environment()}
        page.route("**/api/diagnostics*", lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(report)))
        page.locator("#settings-open").click()
        page.locator("#settings-tab-diagnostics").click()
        with page.expect_download() as downloading:
            page.locator("#diagnostics-export").click()
        download = downloading.value
        self.assertEqual(download.suggested_filename, "ssdl-diagnostics.json")
        self.assertEqual(json.loads(Path(download.path()).read_text(encoding="utf-8")), report)
        self.assert_no_errors()

    def test_browser_media_uses_detached_tab_without_native_action_post(self):
        filename = "web/中文 synthetic.png"
        self.jobs.append({"id": "preview", "title": "Synthetic preview", "url": "https://example.org/album",
                          "platform": "Web", "status": "completed", "created_at": 1, "files": [filename]})
        self.load(); page = self.page
        page.evaluate("state.fileActions = 'browser'")
        self.context.route("**/api/jobs/preview/content?*", lambda route: route.fulfill(
            content_type="text/html", body="<title>Synthetic preview</title>"))
        with page.expect_popup() as opened:
            page.locator('.row-icon-button[data-open-media="preview"]').click()
        popup = opened.value
        popup.wait_for_url("**/api/jobs/preview/content?*")
        self.assertIsNone(popup.evaluate("window.opener"))
        query = parse_qs(urlparse(popup.url).query)
        self.assertEqual(query, {"file_index": ["0"], "filename": [filename]})
        self.assertFalse([path for path, _ in self.writes if path.endswith("/open-file")])
        popup.close()
        self.assert_no_errors()

    def test_database_confirmation_nested_in_settings_cancels_and_submits_once(self):
        type(self).paused = True
        self.load(); page = self.page
        page.locator("#settings-open").click()
        page.locator("#settings-tab-diagnostics").click()
        page.locator("#database-compact").click()
        self.assertTrue(page.locator("#database-confirm-dialog").evaluate("el => el.open"))
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('#database-confirm-dialog').open")
        page.wait_for_function("document.activeElement.id === 'database-compact'")
        self.assertFalse([entry for entry in self.writes if entry[0] == "/api/databases"])
        page.locator("#database-compact").click()
        with page.expect_response(lambda response: response.request.method == "POST" and urlparse(response.url).path == "/api/databases"):
            page.locator("#database-confirm-submit").click()
        page.wait_for_function("document.querySelector('#database-backup-result').textContent.includes('backup-20261015')")
        self.assertEqual([entry for entry in self.writes if entry[0] == "/api/databases"],
                         [("/api/databases", {"action": "compact", "confirmed": True})])
        page.locator("#language-toggle").evaluate("el => el.click()")
        self.assertIn("Latest backup", page.locator("#database-backup-result").inner_text())
        self.assert_no_errors()


if __name__ == "__main__": unittest.main()
