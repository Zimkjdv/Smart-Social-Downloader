"""Receipt-owned native window cold-start/conflict acceptance, never PID cleanup."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading


def window_probe(root, slot, conflict=False):
    import webview
    from desktop import pywebview_app as shell
    from ssdl import desktop_service as backend
    from tests.helpers.webview_matrix import Driver, require, wait
    create, ensure = webview.create_window, backend.ensure_backend
    services, errors = [], []
    drove = threading.Event()
    def captured(*args, **kwargs):
        value = ensure(*args, **kwargs)
        services.append(value)
        return value
    backend.ensure_backend = captured
    def created(*args, **kwargs):
        window = create(*args, **kwargs)
        def drive():
            if drove.is_set():
                return
            drove.set()
            try:
                if conflict:
                    # Loading/error HTML intentionally has no privileged bridge,
                    # so it cannot signal pywebview's bridge-based loaded event.
                    from System import Func, Object
                    def raw_text():
                        task = window.native.Invoke(Func[Object](lambda:
                            window.native.webview.CoreWebView2.ExecuteScriptAsync("document.body.innerText")
                            if window.native.webview.CoreWebView2 is not None else None))
                        if task is None:
                            return ""
                        require(task.Wait(5000), "gui_error_script_deadline")
                        return json.loads(str(task.Result)) or ""
                    wait(lambda: "Another service may own the port" in raw_text(),
                        "gui_port_conflict_not_visible", 45)
                    require(kwargs["js_api"].describe().get("status") == "error", "gui_error_document_has_native_powers")
                else:
                    wait(lambda: bool(services) and window.get_current_url() == services[0]["origin"] + "/?shell=pywebview",
                        "gui_concurrent_navigation_failed", 45)
                    wait(lambda: window.evaluate_js("typeof lastResponse !== 'undefined' && !!lastResponse && desktop.capabilities.pickDirectory"),
                        "gui_concurrent_dashboard_failed")
                    # Hold the primary mutex until the contender has exited;
                    # CPU scheduling must not turn this into two serial windows.
                    other = "b" if slot == "a" else "a"
                    wait(lambda: (root / "data" / ("startup-" + other + ".json")).is_file(),
                         "gui_concurrent_contender_did_not_exit", 30)
                Driver(window).capture(root / "data" / ("startup-" + slot + ".png"))
            except Exception as error:
                errors.append(str(error))
            finally:
                window.confirm_close = False
                window.destroy()
        if conflict:
            window.events.before_show += lambda: threading.Thread(target=drive, daemon=True).start()
        else:
            window.events.loaded += drive
        return window
    webview.create_window = created
    code = shell.run()
    require(not errors, errors[0] if errors else "gui_startup_failed")
    require(code == (1 if conflict else 0), "gui_startup_wrong_result")
    if conflict:
        require(drove.is_set() and not services, "gui_conflict_claimed_service")
    result = {"primary": drove.is_set(), "service": services[0] if services else None}
    (root / "data" / ("startup-" + slot + ".json")).write_text(json.dumps(result), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True)
    parser.add_argument("--mode", choices=("concurrent", "conflict", "window"), required=True)
    parser.add_argument("--slot", default="main")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from tests.helpers.install_runner import verify_receipt
    verify_receipt(root, args.token)
    if os.environ.get("SSDL_DESKTOP_FIXTURE_TOKEN") != args.token or sys.stdin.readline().strip() != "run":
        raise ValueError("Missing GUI startup admission")
    from tests.helpers.webview_matrix import require
    from ssdl import desktop_service as backend
    if args.mode == "window":
        window_probe(root, args.slot)
        return 0
    report = {"passed": False, "mode": args.mode}
    target = root / "data" / ("gui-" + args.mode + ".json")
    try:
        if args.mode == "conflict":
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", int(os.environ["SSDL_PORT"])))
                listener.listen(4)
                window_probe(root, "conflict", conflict=True)
                with socket.create_connection(listener.getsockname(), timeout=3):
                    pass
                report["foreign_listener_survived"] = True
        else:
            children = []
            try:
                for slot in ("a", "b"):
                    children.append(subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                        "--token", args.token, "--mode", "window", "--slot", slot], cwd=root,
                        stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW))
                # Both gated processes exist before either is allowed to claim.
                for child in children:
                    child.stdin.write(b"run\n"); child.stdin.flush(); child.stdin.close()
                for child in children:
                    require(child.wait(timeout=80) == 0, "gui_concurrent_child_failed")
                records = [json.loads((root / "data" / ("startup-" + slot + ".json")).read_text()) for slot in ("a", "b")]
                require(sum(item["primary"] for item in records) == 1, "gui_concurrent_multiple_windows")
                owner = next(item["service"] for item in records if item["primary"])
                require(backend.backend_status()["instance"] == owner["instance"], "gui_concurrent_backend_changed")
                backend.stop_owned(owner)
                report.update(one_primary_window=True, one_verified_backend=True, graceful_stop=True)
            finally:
                # The outer admitted Job Object owns timeout cleanup, never PIDs.
                for child in children:
                    if child.stdin and not child.stdin.closed:
                        child.stdin.close()
        report["passed"] = True
        return 0
    finally:
        target.write_text(json.dumps(report), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
