"""Create a reviewed source-only ZIP; runtime folders are never traversed."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssdl.version import __version__

ROOT_FILES = (".gitignore", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "README_CN.md",
              "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md", "ROADMAP.md", "requirements.txt",
              "requirements.lock.txt", "requirements-browser.txt", "start.bat", "setup.bat", "update.bat",
              "app.py")
SOURCE_GLOBS = {"ssdl": ("*.py",), "static": ("*.js", "*.css", "*.html"),
                "chrome-extension": ("*.js", "*.html", "manifest.json", "README.md"),
                "tests": ("test_*.py", "*.test.cjs"), "tools": ("manage.py", "package_source.py", "measure_state.py", "measure_persistence.py", "measure_capacity.py"),
                "docs": ("*.md",), "docs/images": ("dashboard-preview.svg",),
                ".github/ISSUE_TEMPLATE": ("*.yml", "*.yaml"),
                ".github": ("pull_request_template.md",),
                ".github/workflows": ("*.yml", "*.yaml")}
PRIVATE_CONTENT = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("personal Windows path", re.compile(r"(?i)[a-z]:[\\/](?:Users|Documents and Settings)[\\/](?!Public[\\/])[^\s\"'<>]+")),
    ("Netscape cookie export", re.compile(r"(?m)^# Netscape HTTP Cookie File")),
)


def source_files(root: Path) -> list[Path]:
    root = root.resolve()
    files = [root / name for name in ROOT_FILES]
    for folder, patterns in SOURCE_GLOBS.items():
        for pattern in patterns:
            files.extend((root / folder).glob(pattern))
    selected = []
    for path in sorted(set(files)):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Missing or unsafe source file: {path.relative_to(root)}")
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
