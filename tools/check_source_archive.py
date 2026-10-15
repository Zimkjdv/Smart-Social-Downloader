"""Build an allowlisted source ZIP and run its tests from an isolated extraction.

Uses the current interpreter's installed dependencies and ordinary Chrome. This
does not install packages, access production data or simulate a fresh OS.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.package_source import create_archive


def extract_verified(archive: Path, destination: Path, root: Path, files: list[Path]) -> Path:
    """Extract only the exact members selected by our source packager."""
    # source_files returns canonical paths. Windows TEMP may use an 8.3 alias
    # (RUNNER~1); normalize the caller's root before lexical relative_to checks.
    root = root.resolve()
    prefix = "smart-social-downloader/"
    expected = {prefix + path.relative_to(root).as_posix(): path for path in files}
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError("Source ZIP members differ from the allowlist")
        if zipped.testzip() is not None:
            raise ValueError("Source ZIP CRC failed")
        for name, source in expected.items():
            target = destination / name
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe source ZIP member")
            contents = zipped.read(name)
            if hashlib.sha256(contents).digest() != hashlib.sha256(source.read_bytes()).digest():
                raise ValueError("Source ZIP bytes differ from the reviewed source")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
    return destination / prefix.rstrip("/")


def run_checks(root: Path) -> None:
    # -E ignores inherited PYTHONPATH/PYTHONHOME; -s excludes user site packages.
    # The venv's installed dependencies remain available, as in normal CI.
    smoke = ("from pathlib import Path; import ssdl.app, tests.helpers.app, tools.package_source; "
             "root=Path.cwd().resolve(); "
             "assert all(Path(m.__file__).resolve().is_relative_to(root) "
             "for m in (ssdl.app, tests.helpers.app, tools.package_source))")
    commands = ([sys.executable, "-E", "-s", "-c", smoke],
                [sys.executable, "-E", "-s", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
                ["node", "--test", "tests/frontend.test.cjs"])
    for command in commands:
        subprocess.run(command, cwd=root, check=True)


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="ssdl-source-acceptance-") as temporary:
            workspace = Path(temporary)
            archive = workspace / "source.zip"
            files = create_archive(ROOT, archive)
            extracted = extract_verified(archive, workspace / "extracted", ROOT, files)
            print(f"Verified {len(files)} source files; testing extracted source.", flush=True)
            run_checks(extracted)
    except subprocess.CalledProcessError as error:
        return error.returncode or 1
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Source acceptance failed: {error}", file=sys.stderr)
        return 1
    print("Extracted source acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
