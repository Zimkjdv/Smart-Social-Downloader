"""Explicit bundled process roles. Internal roles never fall through to a GUI."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys


def main(argv=None, *, gui=False):
    from .runtime_paths import paths, frozen, prepare_environment
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=not gui,
        choices=("gui", "backend", "control", "worker", "pixiv-exchange", "diagnose", "migrate", "rollback"),
        default="gui" if gui else None)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if gui and args.role not in {"gui", "migrate", "rollback"}:
        parser.error("Use ssdl-runtime.exe for command-line operations.")
    if args.role not in {"control", "migrate", "rollback"} and args.arguments:
        parser.error("This role accepts no arguments.")
    # Windowless Python has no stdio; the console runtime retains binary pipes.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    for name in ('stdin', 'stdout', 'stderr'):
        stream = getattr(sys, name)
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    from .installed_session import installed_session
    try:
        prepare_environment()
        home = paths().home
        home.mkdir(parents=True, exist_ok=True)
        active = installed_session() if frozen() and args.role in {"gui", "backend", "migrate", "rollback"} else nullcontext()
        with active:
            if args.role == "gui":
                if os.environ.get('SSDL_FROZEN_PROBE_TOKEN'):
                    from desktop.frozen_probe import install
                    install()
                from desktop.pywebview_app import main as start_gui
                return start_gui()
            if args.role == "backend":
                from .desktop_service import run
                return run()
            if args.role == "control":
                from .desktop_control import main as control
                return control(args.arguments)
            if args.role == "worker":
                from .job_runner import main as worker
                return worker()
            if args.role == "pixiv-exchange":
                from .pixiv_auth_exchange import main as exchange
                return exchange()
            if args.role == "diagnose":
                from .environment import inspect_environment
                print(json.dumps(inspect_environment(home), ensure_ascii=False))
                return 0
            if gui:
                from desktop.migration_gui import run as wizard
                return wizard(args.role)
            from .data_migration import main as migration
            return migration([args.role, *args.arguments])
    except Exception as error:
        if not gui and not isinstance(error, (OSError, RuntimeError, ValueError)):
            raise
        if gui:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "Smart Social Downloader", 0x10)
        else:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
