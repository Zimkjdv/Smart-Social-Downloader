"""Explicitly installed only in receipt-owned desktop acceptance venvs."""
import ctypes
import json
import os
from pathlib import Path
import sys
import webbrowser


def bootstrap(root, token):
    # site.py ignores ordinary .pth exceptions and continues startup. Abort
    # instead of accidentally running a fixture with real media transport.
    try:
        install(root, token)
    except Exception:
        raise SystemExit("Desktop fixture initialization refused") from None


def install(root, token):
    from tests.helpers.install_runner import verify_receipt, closed_status
    verify_receipt(root, token)
    if os.environ.get("SSDL_DESKTOP_FIXTURE_TOKEN") != token:
        raise ValueError("Missing desktop fixture admission")
    from ssdl import app as entry
    from ssdl.job_runtime import run_job
    # Python can process the venv site directory twice during site startup.
    if getattr(entry.create_app, "_desktop_fixture_root", None) == root:
        return
    original = entry.create_app

    def record_page(url):
        with (root / "desktop-pages.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps(url) + "\n")
        return True

    webbrowser.open = record_page

    def create():
        app = original(root)
        def synthetic(*args, **kwargs):
            return run_job(*args, **kwargs, command=[sys.executable, "-I", "-u",
                str(root / "tests/helpers/console_runner.py"), "worker", "--token", token])
        app.run_job = synthetic
        close = app.close
        def closed():
            close()
            result = closed_status(app)
            thread = getattr(app.PIXIV_AUTH, "_thread", None)
            result["pixiv_thread_stopped"] = not (thread and thread.is_alive())
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.GetConsoleWindow.restype = ctypes.c_void_p
            result["no_console"] = not api.GetConsoleWindow()
            (root / "data/desktop-closed.json").write_text(json.dumps(result), encoding="utf-8")
        app.close = closed
        return app

    create._desktop_fixture_root = root
    entry.create_app = create
