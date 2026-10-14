# Persistence and queue-lock measurements

Measured on **2026-10-14**, Windows / Python **3.12.10**, against the implementation at `432a575` plus the measurement tool. This completes the first N07 milestone. The proposed writer below is **not implemented**; pending work remains in [ROADMAP](../ROADMAP.md#n07保存成本與長期資料維護).

## Reproduce

From an installed source checkout:

```powershell
.\.venv\Scripts\python.exe tools/measure_persistence.py
# Quick smoke measurement, not a representative performance run:
.\.venv\Scripts\python.exe tools/measure_persistence.py --workload small --repeats 1
# Save the path-free numeric report in the ignored runtime folder if desired:
.\.venv\Scripts\python.exe tools/measure_persistence.py > data/persistence-benchmark.json
```

The default runs all three workloads with five samples per save/operation. `--workload` can be repeated; `--repeats` accepts 1–20. Use the project's Python 3.12 environment and avoid running regression suites or other heavy work at the same time. The documented run was repeated separately after regression tests finished.

The tool creates a temporary AppContext and an HTTP server on an ephemeral **loopback** port. It never calls `start()`, restores history/login, starts a download worker or fetches the synthetic `example.org` URLs. Injected metadata services avoid filesystem scans, preview generation and engine/browser discovery. Media files are not created. Primary/backup writes, schema validation, `fsync`, the queue condition and API handlers are real. Owned writers and HTTP handlers are joined before temporary state is removed.

The output contains environment versions, counts, bytes and timings; it omits temporary paths, saved job content, cookies and the server port. Failed saves/API acknowledgements fail the command rather than yield valid measurements. Run errors are for local troubleshooting and should be reviewed before sharing.

## Workloads and steady saves

Each history contains one synthetic active job for the stop API; other jobs are completed. The last 20 jobs in the account workloads contain large file lists. Paths are ASCII; production metadata, longer/Unicode paths, retries retaining `last_success`, disk contention and antivirus scanning can change the cost. The large case is **below the 64 MiB state limit** and does not test that boundary.

| Workload | Jobs | File paths | Final state bytes | Cold save (ms) | Steady median (ms) | Steady p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small | 20 | 20 | 7,817 | 3.34 | 3.47 | 4.19 |
| account | 200 | 100,180 | 5,371,976 (5.12 MiB) | 110.91 | 226.09 | 238.88 |
| large | 200 | 400,180 | 21,271,976 (20.29 MiB) | 502.61 | 927.67 | 1,267.31 |

Cold save starts without either history file. One warm-up then establishes both primary and backup before steady measurements. Timing covers `StateRepository.save_locked` under the application's condition, including diagnostic redaction, validation/deep-copy, UTF-8 JSON construction, validating existing history files and atomic durable writes. Cold versus steady values are distinct workloads; they are not a controlled subtraction of individual backup costs. The byte count is taken after pause/stop acknowledgement and can vary slightly with temporary-root length and timestamps.

**p95 uses nearest rank. With five samples, it is the maximum, not a stable tail-latency estimate.** These are local observations, not a CI speed requirement or a guarantee on other disks/CPUs.

## API latency under contention

Uncontended requests have no concurrent saver. For the contended case, a synthetic writer acquires the real queue lock, then begins saving when the real handler attempts to acquire that lock. This intentionally measures waiting behind a **whole save**, rather than a randomly timed request. No artificial sleep is included in the timed save. Each request uses a fresh local connection, reads/decodes the response and checks HTTP 200 plus persistence health. Pause and stop each perform another real save before returning.

| Workload | Operation | Uncontended HTTP median (ms) | Contended HTTP median (ms) |
| --- | --- | ---: | ---: |
| small | summary | 1.11 | 5.24 |
| small | pause | 5.02 | 9.74 |
| small | stop/cancel acknowledgement | 7.08 | 11.38 |
| account | summary | 1.08 | 214.54 |
| account | pause | 213.53 | 430.96 |
| account | stop/cancel acknowledgement | 237.50 | 483.11 |
| large | summary | 0.79 | 1,044.32 |
| large | pause | 1,070.03 | 2,057.78 |
| large | stop/cancel acknowledgement | 1,043.59 | 1,930.42 |

Measured queue-lock waiting inside contended summary handlers was **3.94 / 213.25 / 1,043.00 ms**, respectively. The full JSON report also includes samples, p95, lock waits and concurrent-writer durations for each operation. Independent medians need not add up exactly.

The tool validates primary and backup afterwards and verifies the acknowledged pause flag and stop intent were persisted. **Stop acknowledgement does not measure termination of a real download subprocess.** There is no rendering, platform traffic, account scan or IPC transfer in this benchmark. These results reproduce delayed API access under synthetic load; they do not establish that the user's current history has a visible UI stall.

## Phase attribution

A separate **cProfile-instrumented save** records the existing functions without changing production persistence. Its total was 9.60 / 1,242.43 / 4,931.05 ms, much slower than the unprofiled saves above. Use this section to locate work; do not treat its absolute costs as uninstrumented latency.

| Cumulative phase (ms) | small | account | large | Calls per save |
| --- | ---: | ---: | ---: | --- |
| Diagnostic field traversal | 0.44 | 83.29 | 333.81 | Recursive traversal |
| `validate_state`, including deep-copy | 4.84 | 648.07 | 2,406.23 | 3: new payload, backup, primary |
| JSON serialization | 1.52 | 209.98 | 852.37 | 1 |
| UTF-8 encoding | 0.004 | 0.94 | 3.72 | 1 |
| `_read`, including JSON parse and validation | 3.68 | 419.74 | 1,660.56 | 2: backup and primary |
| `_atomic`, including write/flush/fsync/replace | 1.76 | 7.87 | 23.97 | 2: backup and primary |
| `fsync` | 0.78 | 4.75 | 16.15 | 2 |

**Cumulative rows overlap and must not be summed**: `_read` contains validation; `_atomic` contains fsync. Profiling overhead is also substantial for recursive/list-heavy work. In this run, traversal/validation/JSON construction consumed much more time than durable writes. Increasing API transfer timeouts or removing fsync would not address the lock ownership and repeated full-history work shown here.

## Writer design for the next milestone

The measured baseline supports moving whole-history serialization/validation/I/O out of the queue condition. The next implementation should satisfy these requirements:

1. **Capture an immutable snapshot under the condition.** Include jobs, queue, settings, pacing and Rate in one generation. Copy/freeze nested file lists and `last_success`/selection structures before releasing the lock; shallow copies of mutable jobs are insufficient. Measure capture time and memory at the same sizes. Sharing immutable path strings may help, but keeping a reference to a mutable list is unsafe.
2. **Own one writer per AppContext.** Preserve StateStore's schema checks, validated backup rotation, damaged-input preservation and newer-version protection. Bound the queue to an in-flight snapshot and a replaceable latest pending snapshot; avoid retaining one large snapshot for every progress event. Coalesce superseded progress generations, while preserving the current queue/settings/history represented by the newest snapshot.
3. **Wait for durable generations outside the queue lock.** Critical settings/pause/stop/enqueue/result transitions request a generation barrier; a successfully written newer snapshot can satisfy an older barrier only if it contains the resulting current state. Preserve existing response fields and persistence-failure warnings. A failed/blocked save must not be acknowledged as durable. Progress checkpoints can be coalesced with an explicit bounded flush policy; final results still require a barrier.
4. **Keep health reads responsive.** `_state` calls `StateStore.status()` while holding the queue lock. That method currently shares the store's write lock. Moving only `save()` to a thread would move the wait to this health call. Publish a small immutable health snapshot under a separate short lock, so summary never waits for disk work or creates a queue/store lock-order deadlock. Publish consistent last-success/error information and retain the existing health API shape.
5. **Define failure and shutdown ordering.** Restore fully before starting the writer/download worker. On close, stop producers and the owned worker, capture/flush the final snapshot and join the writer. Reject new submissions after close. Preserve pending dirty state and diagnostic errors for an explicit retry after I/O failure; protect a future-version history from retries as today. Audit every save caller rather than changing `save_locked()` to fire-and-forget.
6. **Compare before and after with the same tool.** Update the harness to observe snapshot capture, writer completion and durable barriers, not just enqueue time. Add deterministic tests for coalescing, mutation after capture, critical barriers, failed saves/retry, future/corrupt backup protection, two independent contexts and shutdown. Verify summary no longer queues behind a whole disk save; also report remaining CPU/GIL contention and critical-operation latency. Avoid brittle CI millisecond thresholds.

This is a design recommendation based on measurements, not an implemented writer or a promise that threading alone eliminates all delays. Large account scan/IPC/capacity diagnostics and user-controlled SQLite backup/maintenance remain separate N07 milestones.

## Verification

Eight harness acceptance cases cover synthetic counts/offline schema validation, statistics, real saves and all APIs, the contention gate, failed saves, writer cleanup, condition wait/notify semantics and inclusion in the reviewed source package. Tests use the small workload and enforce correctness without performance thresholds. Full results are recorded in [TESTING](TESTING.md); completed work is in [CHANGELOG](../CHANGELOG.md#unreleased).
