# SQLite diagnostics, backups and compaction

Updated **2026-10-15**. The N07 SQLite maintenance milestone adds explicit controls in **Settings → Diagnostics → Download history databases**. No database inspection, backup or compaction starts merely by importing or constructing the application.

## What is managed

| File under `data/` | Purpose | Count shown |
| --- | --- | --- |
| `image-history.sqlite3` | Complete direct images at their exact original paths | `images` rows |
| `media-manifest.sqlite3` | Complete media sources, quality and file metadata | `media` rows |
| `x-profiles.sqlite3` | Complete X account posts, scoped to account/output root | `posts` rows |

Only these fixed filenames and their SQLite sidecars are inspected. The controls accept no arbitrary path or SQL. They do not touch original downloads, Cookie storage, `state.json`, thumbnails or other databases. Missing databases stay missing; the relevant downloader creates them when needed. Symlinks, Windows reparse points, nonregular files, hard-linked database/sidecar files and orphan journals are rejected rather than followed, replaced or silently discarded.

**Check databases** uses read-only SQLite connections and `quick_check(1)`, then reports main/WAL/SHM/journal bytes, page size/count, unused freelist pages and known-table record counts. It does not read row contents into diagnostic exports or verify every media file. Unknown tables/columns and media integrity are outside this basic SQLite check. Counts/sizes are observations, not one atomic multi-database snapshot; downloads or other processes can change them. Errors may leave some sizes/counts unavailable.

Freelist bytes estimate pages SQLite can reuse automatically. They do not measure all internal fragmentation or guarantee that VACUUM will free that many disk bytes. Keeping backups also consumes disk space.

## Create a backup

1. Pause the queue and wait for the active download to finish. Pausing alone does not stop an active account sync: stop it explicitly if you want maintenance now.
2. Select **Create backup**. The operation runs in the background; status reads remain responsive.
3. Wait for completion and the relative backup location. Copy important backups to separate storage if needed.

Backups are created under `data/database-backups/backup-<UTC timestamp>-<random id>/`. The timestamp is UTC. The UI reports the most recent backup from this service session; earlier backup folders remain on disk and are not automatically expired or deleted. Opening the UI or restarting does not scan all retained backup folders to calculate their total disk use.

The SQLite backup API includes committed WAL contents and makes each copied database consistent. It is not a raw copy of a live `.sqlite3` file. Each destination passes a quick check, closes, and is flushed before the entire staging directory is published. A failed set is not published as a successful backup; owned staging files are cleaned up where possible. Disk/permission problems can leave a `.pending-*` directory for manual review. A published set is not a cross-database transaction: another tool instance or external writer can change one database between snapshots. Stop other instances before maintenance.

Backups contain private source identifiers, account names, output paths and file metadata. They are local runtime data, excluded by the existing `data/` Git/source-package policy. Diagnostic export includes only filenames, capacity/counts, status codes and the generated backup name; it does not embed database contents. Do not attach the databases or backups to a public issue.

## Compact unused space

1. Pause the queue and wait until no download is active.
2. Select **Compact databases** and confirm **Back up and compact**.
3. A complete, checked backup of every present database must succeed before any VACUUM starts. Unknown database layouts, corrupt input or failed backup prevent compaction.
4. Each known database runs SQLite `VACUUM`. All records, schema objects and originals are retained. No age-based deletion, missing-file pruning or dedup reset is performed.
5. A WAL checkpoint/truncate is attempted. If another reader still needs the WAL, it remains and the UI explains that truncation was deferred.

SQLite provides transactional protection for each VACUUM; the set of three operations is not a single transaction. If a later database fails, earlier successful compactions and the complete pre-operation backup remain. The UI shows partial completion/error rather than claiming the entire operation succeeded. A retry creates a fresh backup set. There is no automatic backup deletion, automatic VACUUM schedule, repair/rebuild or restore operation.

Existing dedup behavior is preserved: if a file was moved, renamed, removed or changed at its original path, the downloader fetches it again. Maintenance does not search for moved copies or clear valid records. VACUUM may reorganize SQLite's internal page/row storage; the downloaders use their explicit source/account/path keys.

Backups require additional disk space, and VACUUM needs working space. Total disk use may increase while the original backup is retained even when the compacted database becomes smaller. Once an independently retained backup is verified, users can choose which old backup folders to remove manually; the tool does not make that choice.

## Scheduling, limits and failures

Only one maintenance operation runs per AppContext. Backup/compaction admission and scheduler selection share the queue condition: the request marks maintenance busy before releasing that condition, and the scheduler will not start another download while a write operation is running, even if the user resumes the queue meanwhile. After maintenance finishes, the queue follows its current pause setting. Read-only checks can run alongside downloads. Different AppContexts have independent service state; SQLite's own locks arbitrate external instances.

SQLite lock waits are limited to **1 second** per connection operation. There is one **120-second cooperative deadline** for the whole task, including inspection/backup/compaction. SQLite VM progress handlers and backup page callbacks check cancellation/timeouts. Native filesystem I/O and rollback may take longer; this is not an OS process deadline. Shutdown cancels and joins the owned maintenance thread before releasing the application's other helpers; it can wait for native I/O. API GET/state/summary return cached small reports instead of doing SQLite work under the queue lock.

`POST /api/databases` accepts only `action: refresh | backup | compact`; compact also requires the exact JSON boolean `confirmed: true`. Backup/compact return 409 if the queue is not paused or any active job remains. Busy/closed services reject new requests. The usual Host/Origin policy applies to both GET and POST. Long tasks return 202 and the UI polls the cached report; uncertain requests are reconciled by reads, never by repeating a mutation. Service instance/revision fields prevent an older poll from replacing a newer result.

On a locked database, wait for other writers and retry. On I/O failure, check permissions/free disk space. On corruption or unfamiliar schema, preserve all original files and backups before seeking repair help; do not delete dedup tables as a workaround. Reports omit underlying exception text so it cannot leak paths or row values.

## Restore a known good backup manually

Stop this tool and every other process using these databases first. Preserve a separate copy of the current database and its `-wal`, `-shm` and `-journal` sidecars before replacing anything. Select a complete backup from a compatible application version and verify it on a copy. Restore only the intended fixed `.sqlite3` files into `data/`; move the corresponding old sidecars into the separate preservation folder so they are not replayed against the restored database. Do not mix live journals with an older backup. Leave media, Cookie files and unrelated runtime data alone. Restart and run **Check databases**, then check a representative already-downloaded item and a missing-file retry. Restoring an older backup can lose newer dedup entries and cause refetches; it does not restore missing media. The app currently offers no automatic restore UI.

## Indexed file-detail assessment

The three databases store completion/dedup evidence; they are not yet the authoritative source for all job file lists. Reusing them as a live paginated job index would mix two lifecycles: users can clear job history while retaining dedup, and a failed/retried job can retain an earlier success. Deleting those rows to implement list cleanup would violate existing rules.

A separate index keyed by job ID, snapshot generation and file ordinal is the preferred future direction. It needs transactional generation publication with state snapshots, restart/backup/rollback migration, concurrent readers, exact file actions and incremental child-to-parent transfer. Merely changing HTTP pagination leaves whole-list IPC/state costs intact; simply lifting the 64 MiB limit does not solve them. Keep schema 2 and current limits for this milestone; indexed storage/cursor delivery is an explicit **future feature** in [ROADMAP](../ROADMAP.md), not claimed as implemented by SQLite maintenance.

## Verification

Disposable real SQLite tests verify size/freelist diagnostics, full row/schema preservation, committed WAL backups, backup failure before VACUUM, corrupt/locked/unknown inputs, reparse paths and orphan sidecars, partial compaction, deadline/shutdown, source/API confirmation guards and the scheduler fence. Real dedup stores still reject moved files after compaction. Node tests cover confirmation, concurrent requests, localization, stale revisions and disposal. A real headless Chrome case checks the nested settings confirmation, Escape/focus return and exact submitted request. Final results are in [TESTING](TESTING.md). No production database, Cookie, media download or running service was used for these tests.
