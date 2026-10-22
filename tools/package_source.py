"""Create a reviewed source-only ZIP; runtime folders are never traversed."""
from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.version import __version__

ROOT_FILES = (".gitignore", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "README_CN.md",
              "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md", "ROADMAP.md", "requirements.txt",
              "requirements.lock.txt", "requirements-browser.txt", "start.bat", "setup.bat", "update.bat",
              "app.py", "Dockerfile", "compose.yaml", "compose.login.yaml", ".dockerignore")
SOURCE_GLOBS = {"static": ("*.js", "*.css", "*.html"),
                "docker": ("entrypoint.py", "runtime.py", "storage.py", "healthcheck.py", "session_key.py", "debian.sources"),
                "chrome-extension": ("*.js", "*.html", "manifest.json", "README.md"),
                "tools": ("manage.py", "package_source.py", "check_source_archive.py", "check_workflows.py", "check_installation.py", "check_dependency_faults.py", "check_docker.py", "docker_runtime_probe.py", "docker_service_acceptance.py", "docker_storage_probe.py", "docker_interaction_acceptance.py", "docker_interaction_probe.py", "docker_host_acceptance.py", "docker_host_probe.py", "docker_browser_acceptance.py", "measure_state.py", "measure_persistence.py", "measure_capacity.py"),
                "docs": ("*.md",), "docs/images": ("dashboard-preview.svg",),
                ".github/ISSUE_TEMPLATE": ("*.yml", "*.yaml"),
                ".github": ("pull_request_template.md", "dependabot.yml"),
                ".github/workflows": ("*.yml", "*.yaml")}
# Recursive review boundaries, never a recursive search of the workspace.
# Test helpers may have ordinary module names; test suites retain name filters.
SOURCE_TREES = {"ssdl": ("*.py",), "tests": ("__init__.py", "test_*.py", "*.test.cjs"),
                "tests/helpers": ("*.py",)}
EXCLUDED_DIRS = {"__pycache__", "data", "downloads", "dist", "node_modules"}
PRIVATE_CONTENT = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("personal Windows path", re.compile(r"(?i)[a-z]:[\\/](?:Users|Documents and Settings)[\\/](?!Public[\\/])[^\s\"'<>]+")),
    ("Netscape cookie export", re.compile(r"(?m)^# Netscape HTTP Cookie File")),
)


def _safe_path(path: Path, root: Path) -> None:
    for component in (path, *path.parents):
        if component == root:
            break
        metadata = component.lstat()
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError(f"Linked source path is not allowed: {component.relative_to(root)}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Unsafe source path: {path.relative_to(root)}")


def source_files(root: Path) -> list[Path]:
    root = root.resolve()
    files = [root / name for name in ROOT_FILES]
    for folder, patterns in SOURCE_GLOBS.items():
        directory = root / folder
        if not directory.exists():
            continue
        _safe_path(directory, root)
        for pattern in patterns:
            files.extend(directory.glob(pattern))
    for folder, patterns in SOURCE_TREES.items():
        directory = root / folder
        if not directory.exists():
            continue
        _safe_path(directory, root)
        def walk_error(error):
            raise error
        for current, directories, names in os.walk(directory, followlinks=False, onerror=walk_error):
            directories[:] = sorted(name for name in directories
                                    if not name.startswith(".") and name not in EXCLUDED_DIRS)
            for name in directories:
                _safe_path(Path(current) / name, root)
            files.extend(Path(current) / name for name in names
                         if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns))
    selected = []
    for path in sorted(set(files)):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Missing or unsafe source file: {path.relative_to(root)}")
        _safe_path(path, root)
        if path.stat().st_size > 2_000_000:
            raise ValueError(f"Unexpected source file size: {path.relative_to(root)}")
        contents = path.read_text(encoding="utf-8")
        for description, pattern in PRIVATE_CONTENT:
            if pattern.search(contents):
                # Never include the matched value in diagnostics.
                raise ValueError(f"Review {description} in {path.relative_to(root)} before publishing")
        selected.append(path)
    return selected


def create_archive(root: Path, output: Path) -> list[Path]:
    root = root.resolve()
    files = source_files(root)
    output = output.resolve()
    if output in files:
        raise ValueError("Archive cannot replace a source file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, "smart-social-downloader/" + path.relative_to(root).as_posix())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate and list selected files without creating a ZIP")
    parser.add_argument("--output", type=Path, default=ROOT / f"dist/smart-social-downloader-{__version__}-source.zip")
    args = parser.parse_args(argv)
    try:
        files = source_files(ROOT) if args.check else create_archive(ROOT, args.output)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, str(exc) + "\n")
    for path in files:
        print(path.relative_to(ROOT).as_posix())
    print(f"Validated {len(files)} source files." if args.check else f"Created {args.output} ({len(files)} source files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
