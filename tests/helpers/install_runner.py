"""Receipt-gated child for disposable installation acceptance only.

Wait for admission before spawning anything, so the owner can attach its process
group first. Ordinary imports and invalid receipts never construct an app.
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

RECEIPT = ".ssdl-install-fixture"


def verify_receipt(root, token):
    receipt = root / RECEIPT
    if (not re.fullmatch(r"[0-9a-f]{32}", token) or receipt.is_symlink() or not receipt.is_file()
            or receipt.stat().st_size != 32
            or not hmac.compare_digest(receipt.read_text(encoding="ascii"), token)):
        raise ValueError("Invalid installation fixture receipt")


def closed_status(app):
    services = (app.X_AUTH, app.THUMBNAILS, app.STORAGE, app.ENVIRONMENT, app.DATABASES, app.STATE_WRITER)
    threads = [app.state.worker_thread, *(getattr(service, "_thread", None) for service in services)]
    status = app.STATE_WRITER.status()
    result = {"closed": app._closed, "threads_stopped": all(not t or not t.is_alive() for t in threads),
              "durable": not status["pending"] and status["writer_closed"]}
    return result


def lifecycle(root):
    sys.path.insert(0, str(root))
    from ssdl.app import create_app, Server
    app = create_app(root)
    with app:
        with Server(("127.0.0.1", app.PORT), app.Handler) as server:
            app.start()
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
            thread.start()
            try:
                if sys.stdin.readline().strip() != "stop":
                    raise ValueError("Missing owned lifecycle stop")
            finally:
                server.shutdown()
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("Owned server did not stop")
    result = closed_status(app)
    (root / "data/install-closed.json").write_text(json.dumps(result), encoding="utf-8")
    if not all(result.values()):
        raise RuntimeError("Owned lifecycle did not close durably")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "start", "stop", "foreground", "update", "lifecycle", "service", "browser", "restore-probe", "inventory", "console", "supervisor-attached", "supervisor-cold", "supervisor-crash"))
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        verify_receipt(root, args.token)
        if args.action == "service":
            return lifecycle(root)
        if sys.stdin.readline().strip() != "run":
            raise ValueError("Missing owned process admission")
        if args.action == "console":
            sys.path.insert(0, str(root))
            from tests.helpers.console_runner import gate
            return gate(root, args.token)
        if args.action == "lifecycle":
            # Launch the venv redirector only after the real base interpreter
            # was attached to the owner's Job Object and admitted.
            return subprocess.call([str(root / ".venv/Scripts/python.exe"), "-I", "-X", "utf8", "-u",
                                    str(Path(__file__).resolve()), "service", "--token", args.token], cwd=root)
        if args.action.startswith("supervisor-"):
            command = [str(root / ".venv/Scripts/python.exe"), "-X", "utf8", "-u",
                       str(root / "tests/helpers/desktop_supervisor.py"), args.action.removeprefix("supervisor-"),
                       "--token", args.token]
        elif args.action == "inventory":
            script = ("import importlib.metadata as m,json,re,sys; from pathlib import Path; "
                      "assert sys.version_info[:2]==(3,12); "
                      "assert Path(sys.prefix).resolve()==Path('.venv').resolve(); "
                      "print(json.dumps({re.sub('[-_.]+','-',d.metadata['Name'].lower()):d.version for d in m.distributions()}))")
            command = [str(root / ".venv/Scripts/python.exe"), "-I", "-c", script]
        elif args.action == "restore-probe":
            command = [str(root / ".venv/Scripts/python.exe"), "-m", "pip", "install",
                       "--disable-pip-version-check", "--no-deps", "idna==3.10"]
        elif args.action == "foreground":
            command = [str(root / ".venv/Scripts/python.exe"), "-X", "utf8", "tools/manage.py", "start"]
        elif args.action == "browser":
            command = [str(root / ".venv/Scripts/python.exe"), "-X", "utf8", "tools/manage.py", "browser-setup"]
        else:
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", args.action + ".bat"]
        return subprocess.call(command, cwd=root, stdin=subprocess.DEVNULL)
    except (ValueError, OSError) as error:
        print(type(error).__name__ + ": invalid installation fixture or command", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
