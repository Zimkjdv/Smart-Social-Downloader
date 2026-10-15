# Account scans and metadata capacity

Updated **2026-10-15**, Windows / Python **3.12.10**; measurements were collected during the October 14–15 implementation. This completes the N07 account-scan/IPC/state-boundary milestone. The following milestone adds [SQLite maintenance and index assessment](DATABASE_MAINTENANCE.md); actual indexed file storage remains a future feature in [ROADMAP](../ROADMAP.md#大型媒體清單索引選配). Earlier writer measurements are in [PERSISTENCE_PERFORMANCE](PERSISTENCE_PERFORMANCE.md).

## What the limits mean

| Boundary | Limit | Behavior |
| --- | --- | --- |
| Worker pipe frame, including newline | 16 MiB | Larger JSON travels in ordered 256 KiB payload chunks |
| One reassembled worker message | 64 MiB, UTF-8 JSON | Reject before sending any bytes for that message; use a compact capacity error |
| Saved history JSON | 64 MiB, including schema/indentation | Reject before modifying the primary or its backup; changes stay dirty in memory |
| History read | 64 MiB per candidate | Stat and bounded read both enforce the limit; oversized primary/backup candidates block overwrites |
| Diagnostics early warning | 80% of the state budget | Show the last successfully saved size and a reminder to back up/clear unneeded jobs |

**These are metadata limits, not video/image file-size limits.** There is no fixed supported media count: path length, Unicode, titles, warnings, retained `last_success` and other jobs affect encoded size. Compact IPC and indented whole-history JSON have separate budgets; history may reach its limit before an individual worker message does. Base64 framing adds wire bytes without increasing the logical-message budget.

`json_budget.py` incrementally builds UTF-8 output and stops when the budget is exceeded. A rejected state attempt reports a lower bound (`attempted_bytes_exact: false`), not a fabricated full size. Input objects, immutable snapshots, escaped string fragments, parsed results and libraries still allocate memory; this is not an OS memory limit. HTTP file-detail pagination still uses the in-memory list; it does not remove the IPC or saved-history limit.

Cached account posts now share the 0.5-second progress throttle with scanning. Initial scan, scan-ready, final completion/error and newly downloaded post checkpoints still report immediately. Every post still checks cancellation and re-verifies its exact original files, including after quota waits. No media/dedup records are deleted by this optimization.

## If a capacity message appears

### Saved history is too large (`state_too_large`)

The prior primary and backup are retained. Keep the service running while resolving this: unsaved changes can be lost on shutdown. Pause the queue, copy `data/state.json` and `data/state.json.bak` to a separate backup location, clear unneeded completed jobs through the UI, then use **Settings → Diagnostics → Save local records**. Clearing jobs removes list history, not original media; it does not delete SQLite dedup records. Confirm health returns to normal. A smaller retry clears the capacity failure and warning when below the threshold.

### An existing record is too large (`state_read_too_large`)

The original candidates are preserved and automatic/manual saves are blocked. The tool does not silently start overwriting an empty replacement history, copy an oversized candidate as ordinary corrupt input, or truncate file lists. Stop the service, back up both candidates, then seek help repairing the history or restore a known compatible valid backup before restarting. Do not edit/delete SQLite dedup data as a workaround. Automatic repair or splitting of oversized history is not implemented.

### A worker message is too large (`worker_message_too_large`)

That job stops with a specific error and the next queued job can continue. Original downloaded media and archive entries remain. The compact error intentionally omits its oversized file list; the parent keeps the last successfully received progress, so the UI may not list every original saved immediately before failure. An account retry re-verifies its archive; it may hit the same limit again. Current account sync has no date-range/batch selector, so repeated retry is not a guaranteed remedy. Download individual post URLs as needed, or wait for indexed file storage. Resetting Rate, reconnecting X or changing video quality does not enlarge this metadata budget.

## Reproduce the measurements

From the project virtual environment:

```powershell
python tools/measure_capacity.py
python tools/measure_capacity.py --full-limits
python tools/measure_capacity.py --posts 50000 --files 90000
```

Default boundary probes use **1 MiB**; `--full-limits` explicitly probes the real **67,108,864-byte** boundary. `--posts` accepts 1–100,000 cached synthetic posts and `--files` accepts 1–200,000 synthetic IPC filenames. Output is JSON containing counts, sizes, timings and verified conditions, without login data or local paths. Temporary plans, wire data, primary/backup and media roots are owned and cleaned up. No production history/session is loaded and no platform URL is fetched.

The scan calls the real account planner with a generated gallery timeline, real temporary JSONL and **simulated archive hits**. It excludes real SQLite/media stat/network/Rate costs. Progress counts file references without serializing every event. IPC runs the production chunk codec through a temporary binary file, including write/flush/read/parse, rather than claiming pipe scheduling timings. Separate regression tests run real child pipes. Boundary probes use a synthetic padding field to reach an exact byte size; they are not realistic account histories.

## Results and limits

Single unprofiled samples, run separately from regression tests; these are observations, not CI speed thresholds or stable percentile estimates.

| Cached scan | 5,000 posts / 10,000 files | 50,000 posts / 100,000 files |
| --- | ---: | ---: |
| Scan and JSONL plan | 249.01 ms | 2,450.93 ms |
| Cached re-verification/planned iteration | 334.29 ms | 3,287.45 ms |
| Plan bytes | 3,055,000 | 30,550,000 |
| Progress events | 3 | 13 |
| File references included in progress | 20,000 | 1,002,494 |

An isolated paired 5,000-post comparison before/after throttling emitted **5,004 / 3** events and **50,020,002 / 20,000** file references; cached iteration took **671.99 / 333.55 ms**. Neither run serialized those progress lists, so the reference reduction is not a measured pipe bandwidth or platform speedup. Event counts depend on runtime and the 0.5-second throttle; large/slow scans still emit intermediate lists and retain O(N) in-memory metadata. The deterministic test fixes the clock and checks three boundary reports for an all-cached account.

90,000 Unicode filenames produced **20,520,011 logical bytes** (19.57 MiB), above the single-frame limit, and **27,364,995 wire bytes**. Encode/write took **309.18 ms**, read/decode **177.18 ms**; decoded lists matched exactly. This validates that chunking exceeds one frame, not unlimited account capacity.

At the actual 64 MiB boundary, IPC encoding/writing took **914.87 ms** and the first durable state save **722.03 ms**. Rejecting the state at **limit + 1 byte** took **353.01 ms**. Exact-limit IPC/state were accepted; over-limit IPC wrote no partial message; primary/backup content fingerprints were unchanged after rejection, both validated on read, and a smaller state retry succeeded. No owned temporary files remained. Padding workload and filesystem/cache effects mean these timings cannot be compared directly with full-history writer samples.

Regression coverage and final results are recorded in [TESTING](TESTING.md). No real X login, live platform account, antivirus contention, all platform limits or memory exhaustion acceptance is claimed.

### Full-history serialization follow-up

Run separately with `python tools/measure_persistence.py --workload large --repeats 3`: the same **400,180-path / 21,271,977-byte** history had durable save samples **942.12 / 1,191.54 / 1,581.27 ms**, median **1,191.54 ms**; capture median **27.59 ms**. Contended summary/pause/stop acknowledgement medians were **75.90 / 2,774.78 / 2,531.14 ms**. Primary/backup and acknowledged intents validated; the separate cProfile run took **5,789.24 ms** and is not an unprofiled latency sample.

The earlier writer's five-sample save median was **862.53 ms**. This three-sample run is slower; bounded Python JSON encoding can add CPU cost, and filesystem/scheduling variation remains. It is not a write-speed improvement or a paired causal benchmark. The queue lock still excludes durable I/O, while critical replies still wait for saved generations. The harness now reports format version 3 with bounded-JSON and bounded-read profile rows. These measurements support retaining indexed metadata as a future improvement rather than declaring large history inexpensive.
