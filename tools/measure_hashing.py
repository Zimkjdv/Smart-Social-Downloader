"""Measure SHA-256 on synthetic owned files; never inspect application data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

BLOCK = 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(BLOCK):
            value.update(block)
    return value.digest()


def measure(paths, rounds):
    sizes = [path.stat().st_size for path in paths]
    timings = {}
    for name, operation in (("metadata", lambda path: path.stat()), ("sha256", digest)):
        samples = []
        for _ in range(rounds):
            started = time.perf_counter()
            for path in paths:
                operation(path)
            samples.append(time.perf_counter() - started)
        timings[name] = {"median_ms": round(statistics.median(samples) * 1000, 3),
                         "min_ms": round(min(samples) * 1000, 3),
                         "max_ms": round(max(samples) * 1000, 3)}
    return {"files": len(paths), "bytes": sum(sizes), "rounds": rounds, "timings": timings}


def accept(root, *, large_mib=32, small_files=512, rounds=3):
    if (type(large_mib) is not int or not 1 <= large_mib <= 512
            or type(small_files) is not int or not 1 <= small_files <= 4096
            or type(rounds) is not int or not 1 <= rounds <= 9):
        raise ValueError("Synthetic benchmark sizes/rounds are out of range")
    # Exclusively create our dataset, never reuse a caller's media directory.
    root.mkdir(exist_ok=False)
    block = bytes(range(256)) * 4096
    large = root / "large.bin"
    with large.open("xb") as output:
        for _ in range(large_mib):
            output.write(block)
    small = []
    for index in range(small_files):
        path = root / f"small-{index:04d}.bin"
        path.write_bytes(index.to_bytes(4, "big") + block[:4092])
        small.append(path)
    a, b = root / "source-a.bin", root / "source-b.bin"
    a.write_bytes(b"synthetic original A")
    b.write_bytes(a.read_bytes())
    original, before = digest(a), a.stat()
    same = original == digest(b)
    a.write_bytes(b"synthetic original B")
    os.utime(a, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = a.stat()
    checks = {"same_bytes_different_paths_match": same,
              "same_size_different_bytes_differ": original != digest(a),
              "same_size_and_mtime_can_hide_byte_change":
                  before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns and original != digest(a)}
    if not all(checks.values()):
        raise ValueError("Synthetic content identity checks failed")
    return {"schema": 1, "passed": True, "python": sys.version.split()[0], "platform": sys.platform,
            "algorithm": "sha256", "read_block_bytes": BLOCK,
            "scope": "synthetic-repeat-reads-with-os-cache-not-cold-disk",
            "checks": checks, "large": measure([large], rounds), "small": measure(small, rounds)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--large-mib", type=int, default=32)
    parser.add_argument("--small-files", type=int, default=512)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="ssdl-hash-assessment-") as name:
        report = accept(Path(name) / "synthetic", large_mib=args.large_mib,
                        small_files=args.small_files, rounds=args.rounds)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
