"""Build and accept a disposable Linux image, without mounting personal state.

Uses only public runtime source, synthetic context canaries and network-disabled
runtime checks. A missing/unhealthy Docker engine fails rather than skips.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ("isolation", "dependencies", "javascript", "ffmpeg_merge", "thumbnail", "image_privacy", "optional_browser")
ROOT_INPUTS = ("Dockerfile", ".dockerignore", "requirements.lock.txt", "app.py", "LICENSE", "THIRD_PARTY_NOTICES.md")
INPUTS = {"ssdl": ("*.py",), "static": ("*.js", "*.html", "*.css"),
          "chrome-extension": ("manifest.json", "README.md", "*.js", "*.html"),
          "docker": ("entrypoint.py", "runtime.py", "storage.py", "healthcheck.py", "session_key.py", "debian.sources")}
VERSION_NAMES = {"python", "node", "ffmpeg", "yt-dlp", "gallery-dl", "yt-dlp-ejs", "imageio-ffmpeg", "pycryptodomex"}
PRIVATE_PATTERNS = (rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                    rb"(?m)^# Netscape HTTP Cookie File",
                    rb"(?i)[a-z]:[\\/](?:Users|Documents and Settings)[\\/](?!Public[\\/])[^\s\"'<>]+")


class GateError(Exception):
    """Only fixed categorical messages may enter the public receipt."""


def require(condition, code):
    if not condition:
        raise GateError(code)


def ordinary(path: Path, root: Path):
    require(path.resolve().is_relative_to(root.resolve()), "unsafe_source")
    for part in (path, *path.parents):
        metadata = part.lstat()
        require(not stat.S_ISLNK(metadata.st_mode)
                and not getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
                "unsafe_source")
        if part == root:
            break


def runtime_sources(root: Path) -> dict[str, bytes]:
    paths = [root / name for name in ROOT_INPUTS]
    for folder, patterns in INPUTS.items():
        directory = root / folder
        ordinary(directory, root)
        for pattern in patterns:
            paths.extend(directory.glob(pattern))  # Shallow source boundaries only.
    files = {}
    for path in sorted(set(paths)):
        ordinary(path, root)
        require(path.is_file() and path.stat().st_size <= 2_000_000, "unsafe_source")
        data = path.read_bytes()
        require(not any(re.search(pattern, data) for pattern in PRIVATE_PATTERNS), "private_source_content")
        files[path.relative_to(root).as_posix()] = data
    require(len(files) <= 300 and sum(map(len, files.values())) <= 16_000_000, "source_limit")
    return files


def stage_sources(files: dict[str, bytes], stage: Path, marker: str):
    for name, data in files.items():
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # These are invented values, never copied from a user's working folders.
    for name in ("data/history.json", "downloads/example.mp4", ".git/config", ".venv/pyvenv.cfg",
                 ".secrets/x-session.key", ".env", "cookies.txt", "auth.bin", "private.pem",
                 "ssdl/data/history.json", "ssdl/cookies.json", "ssdl/private.key",
                 "ssdl/__pycache__/cached.pyc", "static/.env", "chrome-extension/cookies.json"):
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(marker, encoding="ascii")


def fingerprint(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode() + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def base_versions(dockerfile: bytes) -> dict[str, str]:
    content = dockerfile.decode("utf-8")
    result = {}
    for name, alias, suffix in (("python", "runtime", "slim-bookworm"), ("node", "node_runtime", "bookworm-slim")):
        match = re.search(rf"(?m)^FROM ({name}:(\d+\.\d+\.\d+)-{suffix}@sha256:[0-9a-f]{{64}}) AS {alias}\s*$", content)
        require(match is not None, "unreviewed_base")
        result[name] = match.group(2)
        result[name + "_image"] = match.group(1)
    return result


def audit_dockerfile(original: bytes, files: dict[str, bytes], python_image: str) -> bytes:
    # Docker may keep these two transport control files out of COPY; every other
    # public input is required. Any unlisted path (including a canary) must fail.
    script = ("import pathlib; "
              "found={p.relative_to('/context').as_posix() for p in pathlib.Path('/context').rglob('*') if p.is_file()}; "
              f"allowed=set({sorted(files)!r}); "
              "assert found <= allowed; assert allowed-{'Dockerfile','.dockerignore'} <= found")
    addition = (f"\nFROM {python_image} AS ssdl_context_audit\nWORKDIR /context\nCOPY . .\n"
                + "RUN " + json.dumps(["python", "-c", script]) + "\n")
    return original + addition.encode()


class Docker:
    def __init__(self, executable: str, config: Path, host: str | None):
        self.prefix = [executable, "--config", str(config)]
        if host:
            self.prefix += ["--host", host]

    def run(self, args, *, timeout=30, data=None, cwd=None, check=True, env=None):
        # Build output stays in disposable storage, never a shareable receipt.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(self.prefix + list(args), input=data, stdout=output, stderr=subprocess.STDOUT,
                                    timeout=timeout, cwd=cwd, check=False, env=env)
            size = output.tell()
            require(size <= 32 * 1024 * 1024, "docker_output_limit")
            output.seek(max(0, size - 128 * 1024))
            contents = output.read().decode("utf-8", errors="replace").strip()
        if check:
            require(result.returncode == 0, "docker_command_failed")
        return result.returncode, contents


def decode_json(value):
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        raise GateError("invalid_docker_response") from None


def validate_probe(value, receipt, expected):
    result = decode_json(value)
    require(isinstance(result, dict), "invalid_probe_receipt")
    required = {"format_version", "receipt", "passed", "checks", "versions"}
    require(set(result) == (required if result.get("passed") is True else required | {"error_code"}), "invalid_probe_receipt")
    require(type(result["format_version"]) is int and result["format_version"] == 1
            and result["receipt"] == receipt and type(result["passed"]) is bool
            and isinstance(result["checks"], list), "incomplete_probe")
    count = len(result["checks"])
    require(result["checks"] == list(CHECKS[:count]) and count <= len(CHECKS), "incomplete_probe")
    if result["passed"]:
        require(count == len(CHECKS), "incomplete_probe")
    else:
        require(count < len(CHECKS) and result["error_code"] == CHECKS[count] + "_failed", "invalid_probe_error")
    versions = result["versions"]
    require(isinstance(versions, dict) and set(versions) <= VERSION_NAMES
            and all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9.+!~_-]{1,100}", v) for v in versions.values()), "invalid_probe_versions")
    if result["passed"]:
        require(set(versions) == VERSION_NAMES, "invalid_probe_versions")
    require(all(versions[name] == expected[name] for name in ("python", "node") if name in versions), "unexpected_runtime_version")
    return result


def clean_container(docker, name, receipt):
    code, value = docker.run(["container", "inspect", "--format", "{{json .Config.Labels}}", name], check=False)
    if code:
        # --rm normally removed it. Distinguish absence from a broken daemon.
        _, names = docker.run(["container", "ls", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"])
        require(not names, "container_cleanup_failed")
        return
    labels = decode_json(value)
    require(isinstance(labels, dict) and labels.get("ssdl.acceptance") == receipt, "container_ownership_mismatch")
    docker.run(["container", "rm", "--force", name])


def run_gate(docker, root, report, *, service_gate=None):
    phase = "engine"
    receipt = uuid.uuid4().hex
    name = "ssdl-acceptance-" + receipt
    images = []
    container_attempted = False
    try:
        print("Docker acceptance: checking Linux engine", file=sys.stderr, flush=True)
        _, output = docker.run(["info", "--format", "{{json .}}"])
        info = decode_json(output)
        require(isinstance(info, dict) and info.get("OSType") == "linux"
                and re.fullmatch(r"[0-9][A-Za-z0-9.+_-]{0,79}", info.get("ServerVersion", ""))
                and not info.get("ServerErrors"), "linux_engine_unavailable")
        report["engine_version"] = info["ServerVersion"]
        phase = "source"
        files = runtime_sources(root)
        versions = base_versions(files["Dockerfile"])
        probe_path = root / "tools/docker_runtime_probe.py"
        ordinary(probe_path, root)
        require(probe_path.stat().st_size <= 64 * 1024, "probe_limit")
        probe = probe_path.read_bytes()
        report.update(source_sha256=fingerprint(files), probe_sha256=hashlib.sha256(probe).hexdigest())
        marker = "ssdl-canary-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix="ssdl-docker-source-") as directory:
            stage = Path(directory)
            stage_sources(files, stage, marker)
            phase = "context"
            print("Docker acceptance: building synthetic context audit", file=sys.stderr, flush=True)
            (stage / "Dockerfile").write_bytes(audit_dockerfile(files["Dockerfile"], files, versions["python_image"]))
            audit_tag = "ssdl-context-acceptance:" + receipt
            images.append(audit_tag)
            docker.run(["build", "--platform", "linux/amd64", "--target", "ssdl_context_audit", "--tag", audit_tag, "."],
                       timeout=900, cwd=stage)
            report["checks"].append("context_allowlist")
            phase = "build"
            print("Docker acceptance: building runtime image", file=sys.stderr, flush=True)
            (stage / "Dockerfile").write_bytes(files["Dockerfile"])
            tag = "ssdl-runtime-acceptance:" + receipt
            images.append(tag)
            docker.run(["build", "--platform", "linux/amd64", "--target", "runtime", "--tag", tag, "."], timeout=900, cwd=stage)
            _, identity = docker.run(["image", "inspect", "--format", "{{.Id}}", tag])
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", identity), "invalid_image_identity")
            report["image_id"] = identity
            report["checks"].append("image_build")
            phase = "runtime"
            print("Docker acceptance: running isolated media/runtime probe", file=sys.stderr, flush=True)
            container_attempted = True
            args = ["run", "--rm", "--name", name, "--label", "ssdl.acceptance=" + receipt,
                    "--platform", "linux/amd64", "--network", "none", "--read-only", "--user", "10001:10001",
                    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "128",
                    "--memory", "768m", "--cpus", "2", "--no-healthcheck",
                    "--tmpfs", "/work:rw,nosuid,nodev,noexec,size=256m,uid=10001,gid=10001,mode=0700",
                    "--env", "HOME=/work/home", "--env", "XDG_CACHE_HOME=/work/cache",
                    "--env", "SSDL_CACHE_DIR=/work/cache", "--env", "SSDL_DOCKER_ACCEPTANCE=" + receipt,
                    "--env", "SSDL_CONTEXT_CANARY=" + marker,
                    "--env", "SSDL_EXPECT_PYTHON=" + versions["python"], "--env", "SSDL_EXPECT_NODE=" + versions["node"],
                    "--entrypoint", "python", "-i", tag, "-"]
            code, output = docker.run(args, timeout=240, data=probe, check=False)
            result = validate_probe(output, receipt, versions)
            report["checks"].extend(result["checks"])
            report["versions"] = result["versions"]
            if not result["passed"]:
                report["probe_error"] = result["error_code"]
            require(code == 0 and result["passed"], "runtime_probe_failed")
            if service_gate is not None:
                phase = "service"
                service_gate(docker, tag, receipt, root, report)
            report["passed"] = True
            report["complete"] = True
    except Exception:
        # No platform URLs, command output, paths or raw exception strings.
        report.update(passed=False, complete=False, code=phase + "_failed")
    finally:
        try:
            if container_attempted:
                clean_container(docker, name, receipt)
            for tag in reversed(images):
                docker.run(["image", "rm", tag], check=False)  # Own random tags only; never prune layers/volumes.
        except (GateError, OSError, subprocess.SubprocessError):
            report.update(passed=False, complete=False, code="cleanup_failed")
    return report


def write_report(path: Path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.is_symlink() and not path.is_dir(), "unsafe_report")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def docker_executable():
    found = shutil.which("docker")
    if found:
        return found
    installed = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Docker/Docker/resources/bin/docker.exe"
    return str(installed) if installed.is_file() else "docker"


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default=docker_executable(), help="Docker CLI executable")
    parser.add_argument("--host", help="Explicit Docker engine endpoint, if needed")
    parser.add_argument("--service", action="store_true", help="Also accept disposable Compose storage/network/recovery")
    parser.add_argument("--interaction", action="store_true", help="Also accept service, invented login and browser media HTTP")
    parser.add_argument("--report", type=Path, default=ROOT / "data/docker-runtime.json")
    args = parser.parse_args(arguments)
    report = {"schema": 1, "passed": False, "complete": False, "code": "check_incomplete", "checks": [],
              "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "gate_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        # Restrict output to JSON, away from all shipped source files.
        require(args.report.suffix.lower() == ".json" and
                (not args.report.resolve().is_relative_to(ROOT) or args.report.resolve().is_relative_to(ROOT / "data")), "unsafe_report")
        write_report(args.report, report)  # A failed/crashed attempt cannot leave stale success.
        with tempfile.TemporaryDirectory(prefix="ssdl-docker-cli-") as config:
            # Never read personal registry credentials or mutate a saved context.
            plugins = Path(args.docker).resolve().parent.parent / "cli-plugins"
            if plugins.is_dir():
                (Path(config) / "config.json").write_text(json.dumps({"cliPluginsExtraDirs": [str(plugins)]}), encoding="utf-8")
            docker = Docker(args.docker, Path(config), args.host)
            if args.service or args.interaction:
                sys.path.insert(0, str(ROOT))
                # Script and package callers must share the same exception type.
                sys.modules.setdefault("tools.check_docker", sys.modules[__name__])
                from tools.docker_service_acceptance import run_checks
                def service_gate(*values):
                    run_checks(*values)
                    if args.interaction:
                        from tools.docker_interaction_acceptance import run_checks as interaction_checks
                        interaction_checks(*values)
                report = run_gate(docker, ROOT, report, service_gate=service_gate)
            else:
                report = run_gate(docker, ROOT, report)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if report["passed"]:
            report.pop("code", None)
        write_report(args.report, report)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["passed"] else 1
    except KeyboardInterrupt:
        print("Docker acceptance interrupted; no successful receipt recorded.", file=sys.stderr)
        return 130
    except (GateError, OSError, ValueError):
        print("Docker acceptance could not complete; no successful receipt recorded.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
