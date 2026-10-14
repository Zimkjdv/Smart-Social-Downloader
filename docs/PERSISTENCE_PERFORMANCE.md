# Persistence and queue-lock measurements

Measured on **2026-10-14**, Windows / Python **3.12.10**. The original baseline below uses `432a575` plus the measurement tool. The follow-up implements the N07 writer and repeats the same workloads with durable barriers, snapshot capture and allocation measurements. Later account/IPC/capacity acceptance is recorded separately in [CAPACITY](CAPACITY.md); SQLite maintenance remains in [ROADMAP](../ROADMAP.md#n07保存成本與長期資料維護).

## Reproduce

From an installed source checkout:

```powershell
.\.venv\Scripts\python.exe tools/measure_persistence.py
# Quick smoke measurement, not a representative performance run:
.\.venv\Scripts\python.exe tools/measure_persistence.py --workload small --repeats 1
# Save the path-free numeric report in the ignored runtime folder if desired:
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe tools/measure_persistence.py > data/persistence-benchmark.json
```

The default runs all three workloads with five samples per save/operation. `--workload` can be repeated; `--repeats` accepts 1–20. Use the project's Python 3.12 environment and avoid running regression suites or other heavy work at the same time. Both documented runs were made separately after regression tests finished. The updated numeric output has format version 2 and measures writer completion, not just snapshot submission.

The tool creates a temporary AppContext and an HTTP server on an ephemeral **loopback** port. It never calls `start()`, restores history/login, starts a download worker or fetches the synthetic `example.org` URLs. Injected metadata services avoid filesystem scans, preview generation and engine/browser discovery. Media files are not created. Primary/backup writes, schema validation, `fsync`, the queue condition and API handlers are real. Owned writers and HTTP handlers are joined before temporary state is removed.

The output contains environment versions, counts, bytes and timings; it omits temporary paths, saved job content, cookies and the server port. Failed saves/API acknowledgements fail the command rather than yield valid measurements. Run errors are for local troubleshooting and should be reviewed before sharing.

## Baseline workloads and steady saves

Each history contains one synthetic active job for the stop API; other jobs are completed. The last 20 jobs in the account workloads contain large file lists. Paths are ASCII; production metadata, longer/Unicode paths, retries retaining `last_success`, disk contention and antivirus scanning can change the cost. The large case is **below the 64 MiB state limit** and does not test that boundary.

| Workload | Jobs | File paths | Final state bytes | Cold save (ms) | Steady median (ms) | Steady p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small | 20 | 20 | 7,817 | 3.34 | 3.47 | 4.19 |
| account | 200 | 100,180 | 5,371,976 (5.12 MiB) | 110.91 | 226.09 | 238.88 |
| large | 200 | 400,180 | 21,271,976 (20.29 MiB) | 502.61 | 927.67 | 1,267.31 |

Cold save starts without either history file. One warm-up then establishes both primary and backup before steady measurements. Timing covers `StateRepository.save_locked` under the application's condition, including diagnostic redaction, validation/deep-copy, UTF-8 JSON construction, validating existing history files and atomic durable writes. Cold versus steady values are distinct workloads; they are not a controlled subtraction of individual backup costs. The byte count is taken after pause/stop acknowledgement and can vary slightly with temporary-root length and timestamps.

**p95 uses nearest rank. With five samples, it is the maximum, not a stable tail-latency estimate.** These are local observations, not a CI speed requirement or a guarantee on other disks/CPUs.

## Baseline API latency under contention

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

## Baseline phase attribution

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

## Writer implementation (2026-10-14)

`state_writer.py` now moves whole-history serialization/validation/I/O out of the queue condition. The implementation retains the baseline format, files and API response contracts:

1. **Immutable capture.** The repository captures jobs, queue, settings, pacing and Rate in one generation. Nested mappings/lists, `last_success` and selection structures are frozen; immutable path strings are shared. Mutable list containers and live job dictionaries are not shared with the writer. Capturing invalid JSON objects/keys leaves a failed generation visible even if an older write subsequently succeeds.
2. **One owned writer.** Each AppContext owns at most one in-flight snapshot and one replaceable pending snapshot. Completed snapshots are released while idle. Coalescing keeps the latest complete state, while StateStore retains schema validation, valid-backup rotation, corrupt-input preservation and future-version protection. Construction starts no threads; explicit start/save does. Restore precedes normal download startup.
3. **Durable barriers.** All 13 API mutation routes, login retry, job starts/results/recovery and account quota charges wait outside the queue lock. A successfully written newer complete snapshot can satisfy an older accepted generation. Failed writes remain dirty without a busy retry loop; a new submission/manual save or closing flush can try again. Existing HTTP status/health-warning behavior is retained; an unhealthy response is not a durable acknowledgement. The API adds numeric writer generations/counters and pending/running/closed flags for diagnostics without changing saved schema 2.
4. **Bounded checkpoints.** Account post/scan checkpoints and initial scheduling delay may coalesce. The first pending checkpoint sets a **0.5-second** scheduling deadline; later checkpoints do not move it. Critical submissions/barriers and close make it immediately eligible. Time behind an in-flight write, disk work and scheduling are additional; this is not a 0.5-second durability guarantee. Final results and charges remain critical. Sudden termination can lose unfinished checkpoints.
5. **Responsive health and shutdown.** StateStore health has a separate short lock; summary never takes the long write lock. New/admitted API mutations are rejected once close begins. Shutdown stops producers, joins the download worker, captures the final queue state, flushes and joins the writer. It waits for owned persistence rather than abandoning it at the former worker join timeout; blocked native filesystem I/O can extend shutdown. Separate processes writing the same root are still unsupported.
6. **Concurrent cancellation.** Stop checks remain available while saving. A stop received during the job-start barrier prevents launching its download. Account pause/stop is checked after a quota barrier, so a charged post does not charge again or wait on its own hourly quota when resumed.

### Follow-up capture, memory and durable saves

The updated harness captures under the real condition, releases it and waits for the writer generation. The contended gate is unchanged in purpose: the handler arrives as another save begins, but only immutable capture now holds the queue lock. Phase profiling runs **in the actual writer thread**; profiling only the waiting caller would omit its work. Allocation is a separate tracemalloc capture with no concurrent writer I/O and is not used for timing.

| Workload | Capture median / p95 (ms) | Snapshot retained / peak bytes | Durable save median / p95 (ms) |
| --- | ---: | ---: | ---: |
| small | 0.108 / 0.111 | 9,456 / 10,504 | 3.46 / 3.66 |
| account | 7.01 / 17.23 | 887,440 / 929,576 | 223.94 / 232.40 |
| large | 27.50 / 28.43 | 3,286,608 / 3,448,880 | 862.53 / 868.75 |

Large snapshot allocation is approximately **3.13 MiB retained / 3.29 MiB peak**. This excludes pre-existing path strings/history, in-flight/pending snapshots and JSON/deep-copy/I/O buffers. It is not process RSS or whole-save peak memory. Transient capture can coexist with the two owned writer snapshots. Exact final JSON bytes differ by one byte from the baseline due to timestamps; file-path counts and workload shapes are unchanged.

| Workload | Operation | Baseline contended median (ms) | Writer uncontended median (ms) | Writer contended median (ms) |
| --- | --- | ---: | ---: | ---: |
| small | summary | 5.24 | 0.84 | 1.77 |
| small | pause | 9.74 | 4.65 | 8.19 |
| small | stop acknowledgement | 11.38 | 4.74 | 8.17 |
| account | summary | 214.54 | 0.82 | 102.58 |
| account | pause | 430.96 | 228.46 | 440.10 |
| account | stop acknowledgement | 483.11 | 242.94 | 489.74 |
| large | summary | 1,044.32 | 0.82 | 130.56 |
| large | pause | 2,057.78 | 868.83 | 1,856.81 |
| large | stop acknowledgement | 1,930.42 | 952.22 | 1,901.52 |

Contended summary queue-lock wait medians were **0.83 / 32.34 / 51.62 ms**. The large summary response improved by about **87.5%** in this five-sample local comparison. Snapshot capture still holds the queue lock, and CPU/GIL scheduling, JSON parse/encode and response construction remain. The unchanged validation and full-history serialization cost means critical pause/stop acknowledgements still wait roughly one or two full saves; this change does not establish a general write-speed improvement. Coalescing can reduce redundant writes, but is not guaranteed for two closely timed critical calls.

The same five-sample/p95 and hardware/workload limits apply. cProfile writer totals were 9.80 / 1,238.91 / 5,112.14 ms; instrumented costs remain much higher than unprofiled ones. No production history, platform download, account scan, IPC or 64 MiB boundary is covered by this comparison.

## Verification

The eight harness cases now check capture/allocation and profile the real writer, retaining real primary/backup and API checks. Twenty-four additional writer cases cover immutable nested structures, coalescing/deadlines, barriers, failures/retry, newer failed captures versus older accepted writes, lifecycle/thread cleanup, valid/future/corrupt backups, recovered retry notices, independent contexts, all route barrier locations, stop-before-launch and account pause/stop without double charging. Real loopback requests prove summary/cancel checks complete while a controlled disk write is still blocked; critical responses complete after release. These deterministic cases enforce correctness, without CI speed thresholds. Full results are in [TESTING](TESTING.md); completed work is in [CHANGELOG](../CHANGELOG.md#unreleased).
