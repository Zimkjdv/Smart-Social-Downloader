# Status pages, rendering, and local caches

Implemented on 2026-10-10 for the first three P2 items. The 200-job history limit and complete saved file lists are unchanged.

The N07 [persistence and queue-lock measurements/writer](PERSISTENCE_PERFORMANCE.md) were completed on 2026-10-14. They measure immutable capture, real durable saves and loopback API contention separately from the JSON-only comparison below. Current regression evidence is in [TESTING](../history/TEST_RESULTS.md), while the verification notes here describe the original P2 milestone.

## API views

All new read routes retain the local-origin check.

| Route | Behavior |
| --- | --- |
| `GET /api/summary` | Global counts, active-job summary, settings, login/queue/environment/worker health, and storage/cache totals; no history page. |
| `GET /api/jobs` | Job page with global summary. |
| `GET /api/state` | Same combined snapshot, used by the interface to avoid a second request per poll. |
| `GET /api/jobs/{id}/files?offset=0&limit=100` | Up to 100 indexed filenames, total, and next offset; loaded on demand. |
| `GET /api/jobs/{id}/details` | Job diagnostics and warnings, loaded on demand. |
| `POST /api/storage/rescan` | Request a background full scan; return current state. |
| `POST /api/thumbnails/clear` | Queue preview cleanup; return current state. |

Job/state views accept `page` (default 1), `page_size` (10/20/50; default 20), `status`, `platform`, and `search` (at most 300 characters). Filtering precedes pagination; out-of-range pages are clamped. Global counters and the active monitor include jobs outside the current page.

Each job summary includes its full file count and at most **20 path previews**, omitting full warning/diagnostic text and previous-success payloads. Complete lists remain in saved state and download history. File actions validate the current index and filename; a changed selection returns a conflict.

Mutations return the requested page using the same query parameters. Late responses for older views are discarded and the current view is refreshed. Search is debounced by 250 ms. Request deadlines and uncertain-write handling remain unchanged.

### Synthetic payload measurement

```powershell
.\.venv\Scripts\python.exe tools/measure_state.py
```

The script builds **200 synthetic jobs / 100,180 files**, with 20 accounts containing 5,000 files each. Five iterations measure view construction and JSON encoding. It does not import the app, load real history/cookies, access media, or use the network.

Windows / Python 3.12.10 results:

| View | Bytes | Median construction + encoding |
| --- | ---: | ---: |
| Legacy full list | 4,563,700 | 23.23 ms |
| First page, 20 jobs + previews | 23,350 | 0.18 ms |
| Minimal count-only comparison | 49 | <0.01 ms |

The paged job portion is about **99.5% smaller** for this workload. The 49-byte comparison is not the actual `/api/summary` response, which also includes health/settings metadata. HTTP, queue-lock contention, thumbnail generation, and disk I/O are excluded; this is not an end-to-end latency guarantee.

## Rendering

`static/job_rows.js` reconciles by job ID. Unchanged rows/cells retain their nodes; only changed cells are replaced, and rows move only when order changes. Thumbnail listeners bind once per image, and one delegated table listener handles actions.

Existing scroll/focus restoration remains. Pending actions stay disabled during polling. Pagination and platform controls retain their nodes when their markup is unchanged. A loading fallback supports pages that have not loaded the new renderer helper.

## Storage

- A background full scan builds a path/size index at startup and after download-folder changes.
- Completed downloads update their saved paths. X sync also updates new files at post boundaries. Replacing a path updates its size without double counting.
- Status reads reuse totals. A read more than **10 minutes** after a full scan starts reconciliation for external moves, removals, or additions. Settings → Diagnostics → **Rescan storage** requests it immediately.
- Scan results receive concurrent download updates; stale scans are discarded. Full scans skip symlinks/reparse points and report unreadable entries as partial.

The index uses memory proportional to media-path count. This is not an OS filesystem watcher; external changes can remain in totals until a rescan. Download duplicate checks remain independent.

## Thumbnail cache

- Only requested page previews are inspected; unchanged source metadata is reused for up to **30 seconds**.
- Cache budget: **128 MiB / 1,000 generated JPEGs**; expire previews unused for **30 days**, then evict older accesses first.
- Maintenance runs in the preview worker at startup, after generation when over budget, and at most five minutes between inspections. In-flight generation is protected and may temporarily exceed the budget.
- Settings → Diagnostics → **Clear thumbnail cache** queues cleanup. Visible previews regenerate when needed; original images/videos remain intact.
- Cleanup only removes generated hash-named JPEGs directly in `data/thumbnails/`. It does not recursively delete directories, follow cache symlinks/junctions, or clear downloads, login data, saved state, or duplicate history. Unknown filenames remain untouched.
- Undeletable entries produce a partial-cleanup indicator. Preview errors do not change download results.

## Verification scope

The original Windows restart check loaded all 22 completed records, retained the X session and reported healthy worker, storage and cache status. Status reads returned 20 rows on page 1 (30,410 bytes), two rows on page 2 (5,885 bytes), and a 3,786-byte summary. The payload sizes describe that one history.

The 2026-10-11 follow-up passed **104 Python and 10 Node tests**, including real headless Chrome against synthetic pages and APIs. Coverage includes pagination, keyboard focus, lazy file detail, bounded API responses, storage scans with concurrent updates, and thumbnail cache cleanup and failure handling. The same follow-up covers the component split, stable message keys, multi-player selection and platform cooldown grouping. [P2 verification](../history/P2_COMPLETION.md#verification-status) · [Test results](../history/TEST_RESULTS.md)

## Large histories

The browser fetches file details on demand. The worker and state writer still process full file lists, so IPC and saved history have separate capacity limits. [Capacity measurements](CAPACITY.md) · [Indexed file-detail assessment](DATABASE_MAINTENANCE.md#indexed-file-detail-assessment)
