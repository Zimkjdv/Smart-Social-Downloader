"""Opt-in actual WebView2 smoke, only inside a receipt-owned source copy."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import subprocess
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True)
    parser.add_argument("--expect-profile", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from tests.helpers.install_runner import verify_receipt
    verify_receipt(root, args.token)
    if os.environ.get("SSDL_DESKTOP_FIXTURE_TOKEN") != args.token or sys.stdin.readline().strip() != "run":
        raise ValueError("Missing GUI smoke admission")
    report = {"schema": 1, "passed": False, "scope": "receipt-owned-real-webview2"}
    (root / "data").mkdir(exist_ok=True)
    try:
        import webview
        from webview.platforms.winforms import _is_chromium
        if not _is_chromium():
            report["error_code"] = "webview2_runtime_missing"
            raise RuntimeError("Microsoft Edge WebView2 Runtime / .NET 4.6.2 or later is required")
    except ImportError:
        report["error_code"] = "desktop_dependencies_missing"
        raise
    finally:
        (root / "data/webview-smoke.json").write_text(json.dumps(report), encoding="utf-8")
    import webbrowser
    pages = []
    webbrowser.open = lambda url: pages.append(url) or True
    from desktop import pywebview_app as shell
    from ssdl import desktop_service as backend
    from ssdl.desktop_control import probe_service
    original_create = webview.create_window
    original_ensure = backend.ensure_backend
    if args.matrix:
        from tests.helpers.webview_matrix import prepare
        if not args.expect_profile:
            prepare(root)
        original_popen = subprocess.Popen
        def fixture_process(command, *values, **options):
            if command == [sys.executable, "-X", "utf8", "-u", "-m", "ssdl.desktop_service"]:
                command = [sys.executable, "-X", "utf8", "-u", str(root / "tests/helpers/webview_backend.py")]
            return original_popen(command, *values, **options)
        subprocess.Popen = fixture_process
    owned = []
    errors = []
    def ensure(*args, **kwargs):
        service = original_ensure(*args, **kwargs)
        owned.append(service)
        return service
    backend.ensure_backend = ensure
    if args.matrix and args.expect_profile:
        # The window must attach to a pre-existing independently started service.
        ensure()
    drove = threading.Event()
    def create(*window_args, **kwargs):
        window = original_create(*window_args, **kwargs)
        focus = threading.Event()
        original_show = window.show
        def shown():
            original_show()
            focus.set()
        window.show = shown
        def drive():
            if not owned or not shell.NavigationPolicy.trusted(kwargs["js_api"]._policy, window.get_current_url()) or drove.is_set():
                return
            drove.set()
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if window.evaluate_js("typeof lastResponse !== 'undefined' && !!lastResponse && desktop.capabilities.pickDirectory"):
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError("Dashboard/bridge did not become ready")
                expected = ["copy_text", "describe", "open_external", "pick_directory", "save_text", "stop_backend"]
                if window.evaluate_js("Object.keys(window.pywebview.api).sort()") != expected:
                    raise AssertionError("Bridge exposed unexpected methods")
                subprocess.run([sys.executable, "-X", "utf8", "-m", "desktop.pywebview_app"],
                    cwd=root, check=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
                if not focus.wait(5) or backend.backend_status()["instance"] != owned[0]["instance"]:
                    raise AssertionError("Repeat GUI launch did not reuse/focus the original window and backend")
                persisted = window.evaluate_js("localStorage.getItem('ssdl.desktop.smoke') === 'persisted'")
                if persisted != args.expect_profile:
                    raise AssertionError("Dedicated profile persistence mismatch")
                if args.expect_profile and not window.evaluate_js("I18n.locale === localStorage.getItem('ssdl.desktop.smoke.locale') && state.pageSize === 10"):
                    raise AssertionError("Application language/page-size preferences did not persist")
                window.evaluate_js("localStorage.setItem('ssdl.desktop.smoke','persisted'); document.querySelector('#language-toggle').click();")
                window.evaluate_js("localStorage.setItem('ssdl.desktop.smoke.locale', I18n.locale); const choice=document.querySelector('#jobs-page-size'); choice.value='10'; choice.dispatchEvent(new Event('change',{bubbles:true}));")
                if window.evaluate_js("document.querySelector('#desktop-bar').hidden || document.querySelector('#download-dir-pick').hidden"):
                    raise AssertionError("Native controls remained hidden")
                window.evaluate_js("window.smokeSaved = false; api('/api/pause',{method:'POST',body:JSON.stringify({paused:true})}).then(v=>{render(v);window.smokeSaved=v.paused;});")
                while not window.evaluate_js("window.smokeSaved"):
                    if time.monotonic() > deadline:
                        raise AssertionError("Shared HTTP write did not finish")
                    time.sleep(.1)
                initial = window.get_current_url()
                window.load_url(owned[0]["origin"] + "/chrome-connect")
                time.sleep(.3)
                if window.get_current_url() != initial or not window.evaluate_js("desktop.capabilities.pickDirectory"):
                    raise AssertionError("Untrusted document navigation was not blocked safely")
                window.evaluate_js("window.smokeBridge = false; window.pywebview.api.describe().then(v=>{window.smokeBridge=v.version===1;});")
                while not window.evaluate_js("window.smokeBridge"):
                    if time.monotonic() > deadline:
                        raise AssertionError("Bridge unavailable after refused navigation")
                    time.sleep(.1)
                if args.matrix:
                    from tests.helpers.webview_matrix import Driver, exercise, require, wait
                    from tools.check_installation import request
                    driver = Driver(window)
                    if args.expect_profile:
                        require(window.evaluate_js("desktop.ownership === 'attached' && !desktop.capabilities.stopBackend && document.querySelector('#desktop-stop').disabled"), "gui_attached_ownership_failed")
                        require(driver.call("desktop.stopBackend()")["status"] == "unsupported", "gui_attached_stop_allowed")
                        backend.stop_owned(owned[0])
                        wait(lambda: window.evaluate_js("document.querySelector('#queue-banner').dataset.phase === 'offline'"), "gui_backend_exit_not_reported")
                        restored = ensure()
                        require(restored["instance"] != owned[0]["instance"], "gui_backend_restart_reused_identity")
                        snapshot = request(restored["port"], "/api/summary")
                        require(snapshot["total_jobs"] == 33 and snapshot["counts"]["queued"] == 1 and snapshot["counts"]["active"] == 0,
                            "gui_restart_history_or_queue_lost")
                        report["matrix"] = {"attached_stop_refused": True, "backend_exit_offline": True, "restart_history_and_queue_preserved": True}
                    else:
                        report["matrix"] = exercise(window, root, owned[0])
                        keys = request(owned[0]["port"], "/api/jobs", {"urls":["https://example.org/gui-active"]}, expected_status=201)["added"]
                        require(len(keys) == 1, "gui_active_job_not_added")
                        request(owned[0]["port"], "/api/pause", {"paused":False})
                        wait(lambda: (root / ".ssdl-console-worker").is_file() and request(owned[0]["port"], "/api/summary")["counts"]["active"] == 1,
                            "gui_synthetic_worker_not_active", 30)
                    # The matrix changes language too; record the actual final preference.
                    window.evaluate_js("localStorage.setItem('ssdl.desktop.smoke.locale', I18n.locale)")
                from System import Func, Object
                from System.IO import FileMode, FileStream
                from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
                image = FileStream(str(root / "data/webview-smoke.png"), FileMode.Create)
                try:
                    task = window.native.Invoke(Func[Object](lambda: window.native.webview.CoreWebView2.CapturePreviewAsync(
                        CoreWebView2CapturePreviewImageFormat.Png, image)))
                    if not task.Wait(10000):
                        raise AssertionError("WebView2 capture deadline")
                finally:
                    image.Close()
                report.update(renderer="edgechromium", bridge_allowlist=True, dashboard=True,
                    shared_http_write=True, navigation_guard=True, profile_persisted=persisted,
                    dedicated_profile=True, screenshot=True, device_pixel_ratio=window.evaluate_js("devicePixelRatio"),
                    application_preferences=True, repeat_launch_focus=True)
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))
            finally:
                # Programmatic fixture teardown; operator confirmation is D04.
                window.confirm_close = False
                window.destroy()
        window.events.loaded += drive
        return window
    webview.create_window = create
    try:
        code = shell.run()
        if errors:
            raise AssertionError(errors[0])
        if code or not drove.is_set() or not owned:
            raise AssertionError("Native GUI did not finish its smoke checks")
        current = backend.backend_status()
        probe_service(current, root)
        report["window_closed_backend_alive"] = True
        if args.matrix and not args.expect_profile:
            from tools.check_installation import request
            from tests.helpers.webview_matrix import require
            require(request(current["port"], "/api/summary")["counts"]["active"] == 1, "gui_close_stopped_active_download")
            report["window_closed_active_download_alive"] = True
        descriptor = next(item for item in reversed(owned) if item["instance"] == current["instance"] and item["ownership"] == "started")
        backend.stop_owned(descriptor)
        if args.matrix:
            from tests.helpers.webview_matrix import require
            require(all(json.loads((root / "data/desktop-closed.json").read_text()).values()), "gui_shutdown_not_durable")
            require((Path(os.environ["SSDL_DOWNLOAD_DIR"]) / "console-partial.part").read_bytes() == b"synthetic partial bytes", "gui_partial_lost")
        expected_pages = ["https://example.org/desktop-fixture"] if args.matrix and not args.expect_profile else []
        if pages != expected_pages:
            raise AssertionError("GUI smoke had unexpected external dispatches")
        report.update(owned_shutdown=True, external_pages_intercepted=len(pages), passed=True)
    finally:
        (root / "data/webview-smoke.json").write_text(json.dumps(report), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
