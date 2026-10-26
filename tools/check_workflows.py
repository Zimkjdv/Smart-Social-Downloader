"""Offline check of reviewed, literal Action pins in this repo's block YAML.

This is a conservative source policy, not a general YAML parser, action-origin
verifier or vulnerability scanner. Unsupported uses syntax needs manual review.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_ACTIONS = frozenset({"actions/checkout", "actions/setup-python", "actions/setup-node", "actions/upload-artifact", "actions/download-artifact"})
USES_KEY = re.compile(r"^\s*(?:-\s*)?(?:uses|'uses'|\"uses\")\s*:\s*(.*)$")
USES_TOKEN = re.compile(r"(?<![\w-])(?:uses|'uses'|\"uses\")\s*:")
PIN = re.compile(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})")


def check_text(content: str, name: str) -> int:
    count = 0
    for number, line in enumerate(content.splitlines(), 1):
        # Action refs cannot contain '#'; only this reviewed scalar form is
        # accepted. Do not treat inline/flow/dynamic forms as missing actions.
        code = line.split("#", 1)[0]
        if not USES_TOKEN.search(code):
            continue
        key = USES_KEY.fullmatch(code)
        value = key.group(1).strip() if key else ""
        if value.startswith(("'", '"')) and value.endswith(value[0]):
            value = value[1:-1]
        match = PIN.fullmatch(value)
        if not match or match.group(1) not in REVIEWED_ACTIONS:
            # Never echo potentially sensitive/untrusted scalar values.
            raise ValueError(f"{name}:{number}: require a reviewed Action and literal full commit SHA")
        count += 1
    return count


def check_workflows(root: Path = ROOT) -> tuple[int, int]:
    root = root.resolve()
    directory = root / ".github/workflows"
    paths = sorted(set(directory.glob("*.yml")) | set(directory.glob("*.yaml")))
    if not paths:
        raise ValueError("No workflow files found")
    pins = 0
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Workflow must be an ordinary source file inside the project")
        pins += check_text(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())
    return len(paths), pins


def main() -> int:
    try:
        workflows, pins = check_workflows()
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Workflow pin check failed: {error}", file=sys.stderr)
        return 1
    print(f"Reviewed {pins} pinned Action references in {workflows} workflow files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
