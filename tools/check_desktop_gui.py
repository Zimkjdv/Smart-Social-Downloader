"""Opt-in real Windows WebView2 smoke using current installed optional packages.

Owns temporary sources, two GUI sessions/profile and backend child trees. This
is not a clean Windows installation or the full D04 interaction/DPI matrix.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.process_group import ProcessGroup
from tools.check_installation import environment
from tools.check_desktop import free_port
from tools.package_source import create_archive
from tools.check_source_archive import extract_verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "data/desktop-gui.json")
    parser.add_argument("--screenshot", type=Path, default=ROOT / "data/desktop-preview.png")
    parser.add_argument("--keep-workspace", action="store_true")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("Real GUI smoke requires Windows and optional desktop packages")
    for path, suffix in ((args.report, ".json"), (args.screenshot, ".png")):
        if path.suffix.lower() != suffix or path.resolve().is_relative_to(ROOT) and not path.resolve().is_relative_to(ROOT / "data"):
            parser.error("Outputs must be appropriate artifacts outside sources or inside data")
        path.parent.mkdir(parents=True, exist_ok=True)
    result = {"schema": 1, "passed": False, "scope": "current-dependencies-real-windows-webview2", "sessions": []}
    args.report.write_text(json.dumps(result), encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory(prefix="ssdl-webview-", delete=not args.keep_workspace) as name:
            workspace = Path(name).resolve()
            if args.keep_workspace:
                print("Owned GUI workspace:", workspace, flush=True)
            files = create_archive(ROOT, workspace / "source.zip")
            root = extract_verified(workspace / "source.zip", workspace / "GUI source 圖片", ROOT, files)
            token = uuid.uuid4().hex
            (root / ".ssdl-install-fixture").write_text(token, encoding="ascii")
            env = environment(workspace, free_port())
            env["SSDL_DESKTOP_FIXTURE_TOKEN"] = token
            for expect_profile in (False, True):
                command = [sys.executable, "-X", "utf8", "-u", str(root / "tests/helpers/webview_smoke.py"), "--token", token]
                if expect_profile:
                    command.append("--expect-profile")
                with (workspace / "gui.log").open("wb") as output:
                    process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.PIPE,
                        stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                    group = None
                    try:
                        group = ProcessGroup(process)
                        process.stdin.write(b"run\n"); process.stdin.flush()
                        code = process.wait(timeout=100)
                    finally:
                        if group is not None:
                            group.close()
                        elif process.poll() is None:
                            process.kill()  # This admitted gate has not spawned anything yet.
                        process.stdin.close()
                        process.wait(timeout=15)
                if code:
                    print((workspace / "gui.log").read_text(encoding="utf-8", errors="replace")[-6000:], file=sys.stderr)
                    raise RuntimeError("Native WebView2 smoke failed")
                receipt = json.loads((root / "data/webview-smoke.json").read_text(encoding="utf-8"))
                if receipt.get("passed") is not True:
                    raise RuntimeError("Incomplete native GUI receipt")
                result["sessions"].append(receipt)
            shutil.copyfile(root / "data/webview-smoke.png", args.screenshot)
            result["source_files"] = len(files)
        result["passed"] = True
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(type(error).__name__ + ": native GUI smoke did not pass", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
