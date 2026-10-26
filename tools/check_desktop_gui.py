"""Opt-in real Windows WebView2 smoke using current installed optional packages.

Owns temporary sources, two GUI sessions/profile and backend child trees.
--matrix adds synthetic media, shared Chrome UI and backend lifecycle checks.
Physical keys, OS dialogs/display scaling and real accounts remain manual gates.
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


def run_helper(command, root, env, log, timeout):
    with log.open("wb") as output:
        process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.PIPE,
            stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        group = None
        try:
            group = ProcessGroup(process)
            process.stdin.write(b"run\n"); process.stdin.flush()
            code = process.wait(timeout=timeout)
        finally:
            if group is not None:
                group.close()
            elif process.poll() is None:
                process.kill()  # This admitted gate has not spawned anything yet.
            process.stdin.close()
            process.wait(timeout=15)
    if code:
        print(log.read_text(encoding="utf-8", errors="replace")[-6000:], file=sys.stderr)
        receipt = root / "data/webview-smoke.json"
        failure = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
        raise RuntimeError(failure.get("error_code", "gui_acceptance_failed"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "data/desktop-gui.json")
    parser.add_argument("--screenshot", type=Path, default=ROOT / "data/desktop-preview.png")
    parser.add_argument("--keep-workspace", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--startup-only", choices=("concurrent", "conflict"))
    parser.add_argument("--artifacts-dir", type=Path)
    args = parser.parse_args(argv)
    if args.matrix and args.startup_only:
        parser.error("Choose --matrix or --startup-only")
    if os.name != "nt":
        parser.error("Real GUI smoke requires Windows and optional desktop packages")
    for path, suffix in ((args.report, ".json"), (args.screenshot, ".png")):
        if path.suffix.lower() != suffix or path.resolve().is_relative_to(ROOT) and not path.resolve().is_relative_to(ROOT / "data"):
            parser.error("Outputs must be appropriate artifacts outside sources or inside data")
        path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.artifacts_dir or ROOT / "data" / ("desktop-gui-artifacts-" + uuid.uuid4().hex[:8])
    if artifacts.resolve().is_relative_to(ROOT) and not artifacts.resolve().is_relative_to(ROOT / "data"):
        parser.error("Artifacts must be outside sources or inside data")
    if artifacts.exists():
        parser.error("Artifacts directory must be new so evidence cannot be stale")
    result = {"schema": 1, "passed": False, "scope": "current-dependencies-real-windows-webview2", "sessions": []}
    args.report.write_text(json.dumps(result), encoding="utf-8")
    try:
        # WebView2 may release profile locks after its parent process exits.
        # Preserve a busy remainder and report it; cleanup cannot mask a check.
        with tempfile.TemporaryDirectory(prefix="ssdl-webview-", delete=not args.keep_workspace,
                                         ignore_cleanup_errors=True) as name:
            workspace = Path(name).resolve()
            if args.keep_workspace:
                print("Owned GUI workspace:", workspace, flush=True)
            files = create_archive(ROOT, workspace / "source.zip")
            root = extract_verified(workspace / "source.zip", workspace / "GUI source 圖片", ROOT, files)
            token = uuid.uuid4().hex
            (root / ".ssdl-install-fixture").write_text(token, encoding="ascii")
            env = environment(workspace, free_port())
            env["SSDL_DESKTOP_FIXTURE_TOKEN"] = token
            (root / "data").mkdir(exist_ok=True)
            for expect_profile in (() if args.startup_only else (False, True)):
                command = [sys.executable, "-X", "utf8", "-u", str(root / "tests/helpers/webview_smoke.py"), "--token", token]
                if expect_profile:
                    command.append("--expect-profile")
                if args.matrix:
                    command.append("--matrix")
                run_helper(command, root, env, workspace / "gui.log", 240 if args.matrix else 100)
                receipt = json.loads((root / "data/webview-smoke.json").read_text(encoding="utf-8"))
                if receipt.get("passed") is not True:
                    raise RuntimeError("Incomplete native GUI receipt")
                result["sessions"].append(receipt)
                if args.matrix and not expect_profile:
                    shutil.copytree(root / "data/gui-matrix", artifacts)
                    result["artifacts"] = sorted(path.name for path in artifacts.iterdir())
            if not args.startup_only:
                shutil.copyfile(root / "data/webview-smoke.png", args.screenshot)
            if args.matrix or args.startup_only:
                artifacts.mkdir(exist_ok=True)
                result["startup"] = []
                for mode in ((args.startup_only,) if args.startup_only else ("concurrent", "conflict")):
                    run_helper([sys.executable, "-X", "utf8", "-u", str(root / "tests/helpers/webview_startup.py"),
                        "--token", token, "--mode", mode], root, env, workspace / (mode + ".log"), 180)
                    receipt = json.loads((root / "data" / ("gui-" + mode + ".json")).read_text())
                    if receipt.get("passed") is not True:
                        raise RuntimeError("Incomplete native startup receipt")
                    result["startup"].append(receipt)
                if (root / "data/startup-conflict.png").is_file():
                    shutil.copyfile(root / "data/startup-conflict.png", artifacts / "webview-port-conflict.png")
                result["artifacts"] = sorted(path.name for path in artifacts.iterdir())
            if args.matrix:
                result["manual_pending"] = ["physical-keys-focus", "windows-display-dpi-100-125-150-200",
                    "native-folder-save-dialogs", "native-close-stop-confirmations", "os-file-associations",
                    "ordinary-chrome-real-account-callback"]
            result["source_files"] = len(files)
        result["workspace_cleanup"] = "retained" if workspace.exists() else "removed"
        result["passed"] = True
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result["error_code"] = str(error) if str(error) in {"webview2_runtime_missing", "desktop_dependencies_missing"} else "gui_acceptance_failed"
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(type(error).__name__ + ": native GUI smoke did not pass", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
