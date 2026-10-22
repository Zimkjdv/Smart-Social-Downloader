"""Host Chrome decodes invented media served by a disposable Docker project."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit

from .check_docker import decode_json, ordinary, require
from .docker_interaction_acceptance import json_request
from .docker_service_acceptance import Fixtures, available_port

STAGES = ("chrome_runtime", "file_picker_image", "keyboard_file_picker", "h264_playback_seek",
          "reload_retains_state", "renamed_file_rejection", "browser_reader_recovery")


def local_request(url, origin, method):
    """Keep the fresh browser context on this fixture's exact loopback origin."""
    parsed = urlsplit(url)
    return (parsed.scheme == "http" and parsed.netloc == urlsplit(origin).netloc
            and not parsed.username and not parsed.password and method in {"GET", "HEAD"})


def wait_element(page, selector, condition):
    # Keep polling in the driver: native sandboxed documents can block the page's
    # JS polling task even though debugger-driven element evaluation still works.
    element = page.locator(selector)
    element.wait_for(state="attached")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if element.evaluate(condition):
            return
        page.wait_for_timeout(50)
    require(False, "browser_media_condition_timeout")


def image_decoded(page):
    wait_element(page, "img", "image => image.complete && image.naturalWidth === 1 && image.naturalHeight === 1")


def play_video(page):
    # Exercise the native Chrome media document, including decoded frames and seek.
    # Muted playback follows ordinary autoplay policy; no policy-disabling flags.
    wait_element(page, "video", "v => v.readyState >= 2")
    require(page.locator("video").evaluate("v => v.videoWidth === 64 && v.videoHeight === 64 && !v.error"),
            "browser_video_metadata_failed")
    # Do not await play(): a stalled media promise must hit the driver deadline.
    page.locator("video").evaluate("v => { v.muted = true; void v.play().catch(() => {}); }")
    wait_element(page, "video", "v => !v.error && v.currentTime > 0.1 && v.getVideoPlaybackQuality().totalVideoFrames > 0")
    page.locator("video").evaluate("v => { v.pause(); v.currentTime = v.duration / 2; }")
    wait_element(page, "video", "v => !v.seeking && !v.error && Math.abs(v.currentTime - v.duration / 2) < 0.1")
    page.locator("video").evaluate("v => { void v.play().catch(() => {}); }")
    wait_element(page, "video", "v => v.ended === true")


def exercise_browser(browser, project, move_media, report):
    """Drive shipped UI and native media documents; retain categorical evidence only."""
    origin = f"http://127.0.0.1:{project['port']}"
    require(project["host_port"] == project["port"], "browser_port_mismatch")
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", browser.version), "invalid_chrome_version")
    report["browser_version"] = browser.version
    report["browser_mode"] = "isolated_chrome_automated"
    current = STAGES[0]
    def passed():
        report["browser_checks"].append(current)
        print("Docker browser acceptance: " + current, file=sys.stderr, flush=True)
    context = browser.new_context(service_workers="block", accept_downloads=False, viewport={"width": 1440, "height": 1000})
    try:
        context.set_default_timeout(15_000)
        context.route("**/*", lambda route: route.continue_() if local_request(
            route.request.url, origin, route.request.method) else route.abort())
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda _: errors.append(True))  # No raw page/error content in receipts.
        page.goto(origin, wait_until="domcontentloaded")
        row = page.locator('tr[data-job-id="fixture-media"]')
        row.wait_for()
        require(row.locator("[data-open-folder]").count() == 1, "browser_job_missing")
        passed()
        current = STAGES[1]
        row.locator("[data-open-folder]").click()
        picker = page.locator("#file-picker-modal")
        choices = picker.locator(".file-choice")
        choices.filter(has_text="fixture/original.png").wait_for()
        with page.expect_popup() as popup:
            choices.filter(has_text="fixture/original.png").click()
        image = popup.value
        image_decoded(image)
        image.close()
        passed()
        current = STAGES[2]
        # Explicitly focus the action before entering the real dialog by keyboard.
        folder = row.locator("[data-open-folder]")
        folder.focus()
        folder.press("Enter")
        choices.filter(has_text="fixture/original.png").wait_for()
        require(page.locator("#file-picker-close").evaluate("e => e === document.activeElement"),
                "picker_initial_focus_failed")
        page.locator("#file-picker-close").press("Tab")
        require(choices.first.evaluate("e => e === document.activeElement"), "picker_tab_focus_failed")
        with page.expect_popup() as popup:
            choices.first.press("Enter")
        image = popup.value
        image_decoded(image)
        image.close()
        passed()
        current = STAGES[3]
        row.locator(".row-icon-button[data-open-media]").click()
        choice = choices.filter(has_text="fixture/video.mp4")
        choice.wait_for()
        with page.expect_popup() as popup:
            choice.click()
        video = popup.value
        play_video(video)
        video.close()
        passed()
        current = STAGES[4]
        code, before = json_request(project, "/api/jobs/fixture-media/details")
        require(code == 200 and before["status"] == "completed", "browser_state_unavailable")
        page.reload(wait_until="domcontentloaded")
        row.wait_for()
        page.locator("#status-refresh").click()
        code, after = json_request(project, "/api/jobs/fixture-media/details")
        require(code == 200 and (after["status"], after["file_count"]) ==
                (before["status"], before["file_count"]), "browser_reload_changed_job")
        passed()
        current = STAGES[5]
        move_media()
        row.locator("[data-open-folder]").click()
        missing = choices.filter(has_text="fixture/moved.jpg")
        missing.wait_for()
        with page.expect_popup() as popup:
            missing.click()
        missing_page = popup.value
        # Chrome may render a native HTTP error page. Inspect only categorical status.
        missing_page.wait_for_load_state("domcontentloaded")
        require(local_request(missing_page.url, origin, "GET"), "browser_error_navigation_escaped")
        response = context.request.get(missing_page.url)
        require(response.status == 404, "browser_missing_original_served")
        response.dispose()
        missing_page.close()
        passed()
        current = STAGES[6]
        code, details = json_request(project, "/api/jobs/fixture-media/details")
        require(code == 200 and details["status"] == "completed"
                and json_request(project, "/api/health")[0] == 200 and not errors,
                "browser_ui_or_reader_failed")
        row.locator("[data-open-folder]").click()
        choices.filter(has_text="fixture/original.png").wait_for()
        with page.expect_popup() as popup:
            choices.filter(has_text="fixture/original.png").click()
        image = popup.value
        image_decoded(image)
        image.close()
        passed()
        require(report["browser_checks"] == list(STAGES), "incomplete_browser_acceptance")
    except Exception:
        report["browser_error"] = current + "_failed"
        raise
    finally:
        context.close()


def run_checks(docker, image, receipt, root, report, *, headed=False):
    sources = ("tools/docker_browser_acceptance.py", "tools/docker_interaction_probe.py")
    for name in sources:
        ordinary(root / name, root)
    report["browser_sources_sha256"] = hashlib.sha256(b"".join((root / name).read_bytes() for name in sources)).hexdigest()
    report["browser_checks"] = []
    report["browser_error"] = "chrome_runtime_failed"
    # Host-only optional dependency; never install Chrome/Playwright in the image.
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix="ssdl-browser-ui-") as directory:
        fixtures = Fixtures(docker, image, receipt, root, Path(directory))
        probe = (root / "tools/docker_interaction_probe.py").read_bytes()
        def action(container, name):
            fixtures.state(container)
            code, content = docker.run(["exec", "-i", "--user", "10001:10001", container, "python", "-", name],
                                       data=probe, timeout=60, check=False)
            require(code == 0, "browser_fixture_failed")
            result = decode_json(content)
            require(isinstance(result, dict) and set(result) == {"receipt", "result"}
                    and result["receipt"] == receipt and isinstance(result["result"], dict), "invalid_browser_receipt")
        try:
            group = fixtures.group("browser")
            helper = fixtures.helper(group)
            action(helper, "seed-media")
            project = fixtures.project(group, fixtures.volume("browser-backups"), available_port(), suffix="browser")
            fixtures.up(project)
            with sync_playwright() as runtime:
                browser = runtime.chromium.launch(channel="chrome", headless=not headed, timeout=30_000)
                try:
                    exercise_browser(browser, project, lambda: action(helper, "move-media"), report)
                finally:
                    browser.close()
            fixtures.stop(project)
            report.pop("browser_error", None)
        finally:
            fixtures.cleanup()
