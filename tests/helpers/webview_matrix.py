"""Real WebView2 / isolated Chrome checks. No real accounts or OS dialog clicks."""
import base64
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode


def require(value, code):
    if not value:
        raise AssertionError(code)


def wait(check, code, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.05)
    raise AssertionError(code)


def prepare(root):
    """Called before any backend starts, after receipt/process admission."""
    from ssdl.media import ffmpeg_path
    from ssdl.persistence import StateStore
    media = Path(os.environ["SSDL_DOWNLOAD_DIR"])
    media.mkdir(parents=True, exist_ok=True)
    (media / "中文 image.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZGQAAAAASUVORK5CYII="))
    subprocess.run([ffmpeg_path(), "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(media / "中文 video.mp4")],
        check=True, capture_output=True, timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    jobs = [{"id": "gui-media", "url": "https://example.org/synthetic", "status": "completed",
        "title": "中文 media fixture", "platform": "Web", "created_at": 500,
        "files": ["中文 image.png", "中文 video.mp4"], "output_dir": str(media)},
        {"id": "gui-error", "url": "https://example.org/synthetic-error", "status": "failed",
        "title": "Synthetic failure", "platform": "Web", "created_at": 499,
        "error": "Synthetic GUI failure", "error_detail": "Synthetic diagnostics only", "files": []}]
    jobs += [{"id": f"gui-{i}", "url": f"https://example.org/synthetic/{i}", "status": "completed",
        "title": f"中文 row {i}", "platform": "Web", "created_at": i, "files": []} for i in range(30)]
    require(StateStore(root / "data/state.json").save({"schema_version": 2, "jobs": jobs, "queue": [],
        "paused": True, "download_dir": str(media)}), "gui_fixture_seed_failed")


class Driver:
    def __init__(self, window):
        self.window = window

    def js(self, script):
        return self.window.evaluate_js(script)

    def call(self, expression):
        # Sequential operations, bounded even when renderer/native promises hang.
        self.js("window.__d04 = {pending:true}; Promise.resolve().then(()=> (" + expression +
            ")).then(value => {window.__d04={value};},()=>{window.__d04={failed:true};});")
        wait(lambda: not self.js("window.__d04.pending === true"), "gui_action_deadline")
        value = self.js("window.__d04")
        require(not value.get("failed"), "gui_action_rejected")
        return value.get("value")

    def capture(self, path):
        from System import Func, Object
        task = self.window.native.Invoke(Func[Object](lambda:
            self.window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
                "Page.captureScreenshot", '{"format":"png","captureBeyondViewport":false}')))
        require(task.Wait(10000), "gui_capture_deadline")
        path.write_bytes(base64.b64decode(json.loads(str(task.Result))["data"]))

    def metrics(self, scale):
        from System import Func, Object
        value = json.dumps({"width": 1280, "height": 800, "deviceScaleFactor": scale, "mobile": False})
        task = self.window.native.Invoke(Func[Object](lambda:
            self.window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
                "Emulation.setDeviceMetricsOverride", value)))
        require(task.Wait(10000), "gui_metrics_deadline")
        wait(lambda: self.js("innerWidth === 1280 && innerHeight === 800 && Math.abs(devicePixelRatio - " +
            str(scale) + ") < .01"), "gui_metrics_not_applied")


def view_checks(js, capture, name, folder):
    """Identical user-facing business flow, supplied a renderer driver."""
    require(js("lastResponse.total_jobs === 32 && document.querySelector('[data-job-id=gui-media]') !== null"),
            name + "_jobs_not_rendered")
    checks = []
    for language in ("zh-Hant", "en"):
        js("if (I18n.language !== " + json.dumps(language) + ") document.querySelector('#language-toggle').click();")
        js("document.querySelector('#settings-open').focus(); document.querySelector('#settings-open').click();")
        wait(lambda: js("!document.querySelector('#settings-modal').classList.contains('hidden') && !document.querySelector('#settings-open').disabled"),
             name + "_settings_not_open")
        require(js("document.querySelector('#download-dir').value.includes('media target 圖片')"), name + "_unicode_path_lost")
        # Scripted keyboard event tests the actual focus trap, not physical keys.
        require(js("""(() => {const modal=document.querySelector('#settings-modal');
            const first=modal.querySelector('button'); first.focus();
            first.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));
            return document.activeElement.id==='settings-save';})()"""), name + "_focus_trap_failed")
        capture(folder / (name + "-settings-" + language + ".png"))
        js("document.querySelector('#settings-close').click();")
        require(js("document.activeElement.id === 'settings-open'"), name + "_focus_return_failed")
        js("document.querySelector('[data-detail=gui-error]').click();")
        wait(lambda: js("!document.querySelector('#error-modal').classList.contains('hidden')"), name + "_error_missing")
        require(js("document.querySelector('#error-diagnostic').textContent === 'Synthetic diagnostics only'"), name + "_error_details_lost")
        capture(folder / (name + "-error-" + language + ".png"))
        js("document.querySelector('#error-close').click();")
        checks.append(language)
    require(js("(() => {window.scrollTo(0,document.documentElement.scrollHeight); return scrollY > 0;})()"), name + "_scroll_failed")
    js("window.scrollTo(0,0)")
    return checks


def exercise(window, root, service):
    """Uses actual WebView2, bridge, filesystem, HTTP, codecs and fresh Chrome."""
    from playwright.sync_api import sync_playwright
    driver = Driver(window)
    result = {"system_device_pixel_ratio": driver.js("devicePixelRatio"), "checks": [],
        "dialog_evidence": "injected-native-dialog-results", "keyboard_evidence": "scripted-dom-events",
        "scale_evidence": "cdp-render-emulation-not-windows-display-settings"}
    from System import Func, Object, Action
    result["webview2_version"] = str(window.native.Invoke(Func[Object](lambda:
        window.native.webview.CoreWebView2.Environment.BrowserVersionString)))
    artifacts = root / "data/gui-matrix"
    artifacts.mkdir(exist_ok=True)
    driver.metrics(1)
    result["webview_languages"] = view_checks(driver.js, driver.capture, "webview", artifacts)
    result["checks"].append("shared-jobs-settings-errors-locales-focus-scroll")
    for scale in (1, 1.25, 1.5, 2):
        driver.metrics(scale)
        require(driver.js("document.querySelector('.app-shell').getBoundingClientRect().right <= innerWidth + 1"),
                "gui_horizontal_overflow")
        driver.capture(artifacts / ("webview-render-" + str(scale) + ".png"))
    result["render_scales"] = [1, 1.25, 1.5, 2]
    driver.metrics(1)
    # Native clipboard is restored without retaining or reporting its contents.
    from System.Windows.Forms import Clipboard
    previous = window.native.Invoke(Func[Object](Clipboard.GetDataObject))
    try:
        require(driver.call("desktop.copyText('SSDL synthetic 中文 clipboard')")["status"] == "completed", "gui_clipboard_write_failed")
        require(window.native.Invoke(Func[Object](Clipboard.GetText)) == "SSDL synthetic 中文 clipboard", "gui_clipboard_mismatch")
    finally:
        window.native.Invoke(Action(lambda: Clipboard.SetDataObject(previous, True) if previous is not None else Clipboard.Clear()))
    result["checks"].append("native-clipboard-roundtrip-restored")
    # Exercise the real JS/native bridge; OS dialog selections are injected and
    # explicitly not evidence of operating Windows' dialog widgets.
    dialog = window.create_file_dialog
    try:
        selected = str(Path(os.environ["SSDL_DOWNLOAD_DIR"]))
        window.create_file_dialog = lambda *a, **kw: None
        require(driver.call("desktop.pickDirectory()")["status"] == "cancelled", "gui_picker_cancel_failed")
        window.create_file_dialog = lambda *a, **kw: [selected]
        require(driver.call("desktop.pickDirectory()")["path"] == selected, "gui_picker_selection_failed")
        target = artifacts / "中文 report.json"
        window.create_file_dialog = lambda *a, **kw: [str(target)]
        require(driver.call("desktop.saveText({filename:'report.json',text:'{\"synthetic\":\"中文\"}',mimeType:'application/json'})")["status"] == "completed", "gui_export_failed")
        require(json.loads(target.read_text(encoding="utf-8")) == {"synthetic": "中文"}, "gui_export_corrupt")
    finally:
        window.create_file_dialog = dialog
    result["checks"].append("bridge-picker-cancel-selection-utf8-export")
    for action in ("open-file", "open-folder"):
        require(driver.call("api('/api/jobs/gui-media/" + action + "',{method:'POST',body:JSON.stringify({file_index:0,filename:'中文 image.png'})})")["opened"],
            "gui_file_action_failed")
    require(driver.call("api('/api/jobs/gui-media/open-file',{method:'POST',body:JSON.stringify({file_index:0,filename:'other.png'})}).then(()=>false,()=>true)"),
        "gui_stale_file_selection_allowed")
    dispatches = [json.loads(line) for line in (root / "data/gui-file-actions.jsonl").read_text().splitlines()]
    require(dispatches == [{"name":"中文 image.png", "directory":False},
        {"name":"media target 圖片", "directory":True}], "gui_file_dispatch_bypassed_validation")
    require(driver.call("desktop.openExternal('https://example.org/desktop-fixture')")["status"] == "completed", "gui_external_dispatch_failed")
    require(driver.call("desktop.openExternal('file:///private')")["status"] == "error", "gui_external_scheme_allowed")
    result["checks"].append("validated-file-folder-and-external-dispatch-intercepted")
    paths = ["/api/jobs/gui-media/content?" + urlencode({"file_index": i, "filename": name})
        for i, name in enumerate(("中文 image.png", "中文 video.mp4"))]
    require(driver.call("fetch(" + json.dumps(paths[1]) + ",{headers:{Range:'bytes=0-31'}}).then(async r=>({status:r.status,bytes:(await r.arrayBuffer()).byteLength,range:r.headers.get('Content-Range')}))") ==
        {"status": 206, "bytes": 32, "range": "bytes 0-31/" + str((Path(os.environ["SSDL_DOWNLOAD_DIR"]) / "中文 video.mp4").stat().st_size)}, "gui_range_failed")
    require(driver.call("new Promise(resolve=>{const img=new Image();img.onload=()=>resolve(img.naturalWidth===1);img.onerror=()=>resolve(false);img.src=" + json.dumps(paths[0]) + ";})"), "gui_image_decode_failed")
    driver.js("window.__d04Video=document.createElement('video'); __d04Video.muted=true; __d04Video.src=" + json.dumps(paths[1]) + "; document.body.append(__d04Video); void __d04Video.play().catch(()=>{});")
    try:
        wait(lambda: driver.js("__d04Video.videoWidth===64 && __d04Video.currentTime>.1 && __d04Video.getVideoPlaybackQuality().totalVideoFrames>0"), "gui_video_did_not_decode")
        driver.js("__d04Video.pause(); __d04Video.currentTime=1;")
        wait(lambda: driver.js("!__d04Video.seeking && !__d04Video.error && Math.abs(__d04Video.currentTime-1)<.1"), "gui_video_seek_failed")
    finally:
        driver.js("__d04Video.pause(); __d04Video.removeAttribute('src'); __d04Video.load(); __d04Video.remove();")
    result["checks"].append("webview-image-video-frames-seek-range")
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome", headless=True)
        try:
            context = browser.new_context(viewport={"width":1280,"height":800}, accept_downloads=True)
            context.set_default_timeout(15000)
            # Local synthetic data only; fail closed on network destinations.
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(service["origin"] + "/") else route.abort())
            page = context.new_page()
            page.goto(service["origin"])
            page.wait_for_function("typeof lastResponse !== 'undefined' && lastResponse !== null")
            result["chrome_languages"] = view_checks(page.evaluate, lambda p: page.screenshot(path=str(p)), "chrome", artifacts)
            require(page.evaluate("desktop.kind === 'browser' && !desktop.capabilities.pickDirectory"), "browser_acquired_native_capabilities")
            with page.expect_download() as download:
                page.evaluate("void desktop.saveText({filename:'report.json',text:'{\"synthetic\":true}',mimeType:'application/json'})")
            exported = download.value
            require(exported.suggested_filename == "report.json", "browser_blob_name_failed")
            require(json.loads(Path(exported.path()).read_text(encoding="utf-8")) == {"synthetic": True}, "browser_blob_contents_failed")
            from tools.docker_browser_acceptance import play_video
            page.goto(service["origin"] + paths[1], wait_until="domcontentloaded")
            play_video(page)
            require(page.evaluate("typeof window.SSDLDesktopPywebview === 'undefined'"), "media_document_received_bridge")
            result["chrome_version"] = browser.version
        finally:
            browser.close()
    result["checks"].append("isolated-chrome-shared-ui-blob-native-video-document")
    return result
