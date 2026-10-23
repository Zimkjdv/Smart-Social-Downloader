"""Install, check, update, or start the app without reading user state."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.environment import inspect_environment
from ssdl.version import APP_NAME, __version__
ENVIRONMENT = ROOT / ".venv"
ENV_PYTHON = ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MARKER = ENVIRONMENT / "ssdl-setup.json"


def check_environment() -> dict:
    report = inspect_environment(ROOT)
    for item in report["checks"]:
        value = item["version"] or (item["detail"] if item["id"] in {"port", "javascript"}
                                    else "available" if item["status"] == "ok" else "needs attention")
        print(f'[{item["status"].upper()}] {item["id"]}: {value}')
        if item["status"] != "ok":
            if item["id"] == "javascript":
                print("  YouTube: install Node.js 22+ or Deno 2.3+, add it to PATH, then restart.")
            elif item["id"] == "session_storage":
                print("  X login: run start.bat from your normal Windows desktop.")
            elif item["id"] == "chrome":
                print("  X login: install regular Chrome, or use an X cookie file.")
            elif item["id"] == "browser_capture":
                print("  Optional JavaScript capture: python tools/manage.py browser-setup; install regular Chrome.")
            elif item["id"] == "port":
                print("  SSDL_PORT must be a whole number from 1 to 65535.")
            else:
                print("  Run setup.bat to restore the baseline environment.")
    if not report["ready"]:
        raise RuntimeError("The base environment needs repair. Run setup.bat before starting.")
    print("Environment ready." if not report["warnings"] else "Base environment ready; optional features need attention. See Settings > Environment diagnostics.")
    return report


def install(*, update=False) -> int:
    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 or newer is required.")
    if not ENV_PYTHON.is_file():
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
    requirement = ROOT / ("requirements.txt" if update else "requirements.lock.txt")
    command = [str(ENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check"]
    if update:
        command.append("--upgrade")
    subprocess.run([*command, "-r", str(requirement)], check=True, cwd=ROOT)
    subprocess.run([str(ENV_PYTHON), str(Path(__file__).resolve()), "check"], check=True, cwd=ROOT)
    temporary = MARKER.with_suffix(".tmp")
    temporary.write_text(json.dumps({"setup_version": 1, "mode": "updated" if update else "locked"}), encoding="utf-8")
    temporary.replace(MARKER)
    print("Setup complete. Run start.bat to open the local service.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument("action", choices=("setup", "update", "check", "start", "start-background", "stop", "browser-setup"))
    action = parser.parse_args(argv).action
    try:
        if action in {"setup", "update"}:
            return install(update=action == "update")
        if action in {"start-background", "stop"}:
            from ssdl.desktop_service import start, stop
            return start(check_environment) if action == "start-background" else stop()
        if action == "browser-setup":
            if not ENV_PYTHON.is_file():
                raise RuntimeError("Run setup.bat first to create the project environment.")
            subprocess.run([str(ENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check",
                            "-r", str(ROOT / "requirements-browser.txt")], check=True, cwd=ROOT)
            subprocess.run([str(ENV_PYTHON), "-m", "pip", "check"], check=True, cwd=ROOT)
            print("Optional capture installed. Use existing Google Chrome; restart the service, then enable it in Settings > General.")
            return 0
        check_environment()
        if action == "start":
            return subprocess.call([sys.executable, "-X", "utf8", str(ROOT / "app.py")], cwd=ROOT)
        return 0
    except (ImportError, OSError,
            RuntimeError, subprocess.SubprocessError) as exc:
        print("Environment check/setup failed:", str(exc), file=sys.stderr)
        print("Run setup.bat to repair the tested environment, or update.bat to update engines.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
