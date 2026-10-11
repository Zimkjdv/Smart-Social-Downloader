"""Measure synthetic API payloads without loading state, cookies, or media."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ssdl.job_views import job_page, job_summary


def main():
    jobs = [{"id": f"{index:032x}", "url": f"https://example.org/post/{index}",
             "platform": "X", "status": "completed", "title": "Synthetic media",
             "created_at": index, "mode": "x_profile" if index >= 180 else "url",
             "files": [f"twitter/example{index}/media-{number:012d}.jpg" for number in
                       range(5000 if index >= 180 else 1)],
             "last_success": {"files": ["old-result.jpg"]}, "warnings": [], "error_detail": ""}
            for index in range(200)]
    for name, build in (
        ("Legacy full list", lambda: {"jobs": [dict(job) for job in jobs]}),
        ("Page 20 + previews", lambda: {"jobs": [job_summary(job) for job in job_page(jobs)[0]]}),
        ("Summary only", lambda: {"counts": {"completed": len(jobs)}, "total_jobs": len(jobs)}),
    ):
        timings = []
        for _ in range(5):
            started = time.perf_counter()
            encoded = json.dumps(build(), ensure_ascii=False).encode("utf-8")
            timings.append((time.perf_counter() - started) * 1000)
        print(f"{name}: {len(encoded):,} bytes; median {sorted(timings)[2]:.2f} ms")
    print("Synthetic 200 jobs / 100,180 files; view construction + JSON only. No filesystem or network I/O.")


if __name__ == "__main__":
    main()
