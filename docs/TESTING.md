# Regression and acceptance tests

## First GitHub Actions repair — 2026-10-11

The [initial Windows run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/38117758688) failed with two errors and two failing subtests: the runner's default cp1252 encoding could not decode UTF-8 history, its short temporary-directory alias differed from the normalized restored path, and a four-second Chrome fixture budget could expire before the synthetic HTTP 429 request.

Use explicit UTF-8 and resolved fixture paths. The first repair's hosted run confirmed those fixes but exposed an additional eight-second Chrome launch timeout and a second fixture still using four seconds. Real Chrome fixtures now use a 30-second budget; launch allows up to 30 seconds within the existing overall capture deadline, and navigation uses only the remaining budget. Capture preserves fatal responses delivered during final browser calls and reports an exhausted budget as `browser_capture_timeout`. Two deterministic regressions cover startup exhaustion and a late HTTP 429 callback.

**134 Python tests passed in 65.378 seconds; 10 Node tests passed; zero skips.** The source-package allowlist check passed for 116 files. These local checks use synthetic fixtures; the repair's hosted CI result must be confirmed separately.

After adjusting the launch and navigation deadlines, the focused browser suite passed all 18 cases in 54.154 seconds with zero skips, including the supervised infinite-script deadline and private-network isolation cases.

## N03–N05 fixes — 2026-10-11

**132 Python tests passed in 57.492 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12.10 / Node 24.19.0, including synthetic-page real headless Chrome tests. Fourteen new regressions extend the N01/N02 baseline. A final focused auth/queue rerun passed all 17 cases in 0.239 seconds, covering the malformed pairing-token guard added after the full run.

- N03: Cookie array/object/null and overlong/control-character fields, boolean/nonfinite/huge expirations, mixed valid/invalid records and record-count limits; selector safety, generic HTTP 400, unchanged encrypted session and usable pairing ticket; successful correction/re-pairing. Malformed/non-ASCII pairing tokens also return AuthError without consuming the ticket.
- N04: missing paused, strings (including `"false"`), numbers, null and containers all return 400 with unchanged paused state and no save call; explicit true/false each save successfully.
- N05: owned partial headers/bodies, trickle input and the shared absolute deadline, early EOF and disconnects, malformed/duplicate/oversize Content-Length and Transfer-Encoding, invalid UTF-8/deep/nonfinite JSON, bounded admission, 503 / Retry-After, recovery after capacity is released, shutdown and injected socket-write timeout cleanup. Normal state/pause requests and extension CORS/prepare/accept routing still work.

The HTTP fixture uses two slots and short deadlines to exercise production admission/read logic without resource-exhaustion stress. A first full run exposed an observer race in a native large-write test: Windows could finish sending before the test saw an active slot. It was replaced with controlled TimeoutError injection and an explicit handler gate; the successful full run uses that deterministic test. This validates configured write timeout and cleanup, not native TCP throughput. Production defaults are 32 active connections, 10 seconds for total header/body input and 5 seconds for socket writes; API disk work is outside those transport deadlines.

Additional checks: 50 Python sources parse, 15 JavaScript/CJS sources pass `node --check`, and both locales contain all 633 keys. Local links resolve in 21 Markdown documents. The allowlisted source archive contains 116 files, including the new HTTP server and regression module; bytes and ZIP CRC are checked, and runtime directories remain excluded.

Tests use temporary storage and synthetic sessions, without reading real Cookie values or downloading external platform media. Local deployment checks are recorded separately in [CHANGELOG](../CHANGELOG.md#unreleased): the idle service restarted healthy, retaining 25 completed jobs, hourly limit 80 and the connected X session. Remaining architecture, performance and environment acceptance stay in [ROADMAP](../ROADMAP.md).

## N01/N02 fixes — 2026-10-11

**118 Python tests passed in 54.482 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12.10 / Node 24.19.0, with synthetic-page real headless Chrome coverage. There are 14 new regression tests. A final targeted runtime rerun covers the frame-error classification cleanup after the full run.

- N01: malformed saved URLs/paths/nested pacing, late normalization failure with and without a backup, unchanged live jobs/queue/settings on failure, protected original/backup bytes, and offline URL recovery with no DNS request.
- N02: 80 unrelated completed jobs with 80,000 file paths no longer enter a new download payload; legacy source/quality/player/root matching and X post-author scoping remain.
- A real isolated child round-trips 70,000 long Unicode filenames (more than 16 MiB of UTF-8 JSON) through input, progress and final result, including an RPC checkpoint.
- Corrupt, reordered, truncated and oversize chunks report explicit errors; cancellation during a partial chunk is prompt, and capacity failure does not block the next queued job. Smaller-budget boundary tests exercise bounds without allocating 64 MiB for every failure case.

The logical message budget remains 64 MiB and the wire-frame budget remains 16 MiB. This is bounded chunking, not unlimited account capacity or proof of improved large-history disk latency. Network, login, persistence, browser, media/quality and source-package tests remain green.

## Earlier review and documentation migration — 2026-10-11

Re-ran the existing suite after the Python 3.12 baseline change and documentation migration: **104 Python tests passed in 53.365 seconds; 10 Node tests passed; zero skips**. The run includes synthetic-data headless Chrome tests and source-packaging tests. No live platform download, real Cookie access or production service restart was performed.

Separate temporary-fixture probes identified issues outside the existing regression coverage:

- A valid queued row followed by a malformed saved URL leaves a partial job map, an empty queue and a healthy storage indicator.
- A synthetic history payload of approximately 17.28 MB exceeds the 16 MiB child input limit; the real process supervisor returns `worker_exited` before downloading.
- Array/object Cookie names raise an uncaught TypeError in session selection.
- POSTing a string `"false"` to the isolated pause API returns 200 and enables pause.
- A partial HTTP request reaches body reading with no socket timeout; the probe closes its single owned connection. Resource-exhaustion testing was not performed.

These probes originally exposed missing regression coverage. N01–N05 are now fixed and covered above. Completed fixes are recorded in [CHANGELOG](../CHANGELOG.md#unreleased); architecture suggestions and unmeasured performance risks remain pending in [ROADMAP](../ROADMAP.md#本輪整體審查).

## Earlier audit record — 2026-10-11

**104 Python tests + 10 Node tests passed, with zero skipped tests** on Windows, Python 3.12.10, Node.js 24.19.0, installed Google Chrome and Playwright 1.63.0. Python execution took 52.765 seconds. This reruns the earlier 59 Python/8 Node baseline, adds P2, quality and optional browser coverage, and checks the six reproduced fixes in the [project audit](PROJECT_AUDIT.md); it is not a claim that every live platform works.

Tests use synthetic URLs, data and HTTP/API fixtures, temporary directories and fresh headless Chrome contexts. The public-address network tests route checked synthetic numeric addresses to an owned local fixture. They do not disable the production network policy. No ordinary Chrome profile, real login Cookie, actual user history or platform download is used.

Additional local checks pass: 47 Python files parse, 15 JavaScript/CJS files pass `node --check`, `pip check` reports no broken requirements, and English/Traditional Chinese each have all 626 locale keys. Local documentation links resolve. The allowlisted source archive contains 113 files with matching source bytes and valid ZIP CRC; runtime folders are absent. These checks do not replace staged-file review after Git initialization.

## Reproduce

The latest local run above includes the Python-baseline adjustment and N01–N05 fixes. GitHub CI remains pending until a repository exists; local results are not GitHub CI results.

From the project root after `setup.bat`:

```powershell
python tools/manage.py browser-setup
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/package_source.py --check
```

Install ordinary Chrome for browser coverage. Without Playwright/Chrome, browser tests explicitly skip and the result is **not full browser acceptance**. GitHub CI uses only Python 3.12, installs the optional package and asserts Chrome exists before running the suite. This matches the local project baseline. The current [Windows runner image](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md) lists Chrome, but image updates can affect availability. No GitHub run has occurred yet.

## P2 coverage

| Area | Cases |
| --- | --- |
| Bounded state APIs | 200-job filtering/page boundaries; 20-file previews; summary without job rows; file pages capped at 100; invalid offsets/limits, missing job and untrusted Origin; full history remains intact |
| DOM reconciliation | Unchanged row/cell identity survives refresh; page size survives reload; existing offline/timeout/uncertain-write tests preserve valid state and never repeat a mutation |
| Snapshot ordering | Delayed older polling cannot undo a newer mutation; scoped sequence validation and service-instance changes reject retired responses while allowing restart |
| Capacity/cache | Replacement counted once, background scan overlay, deletion corrected by rescan, cache age/count pruning, delete failure reported, explicit cleanup preserves original/custom files |
| Player choices | Generic/static/dynamic grouping, opaque IDs without signed URLs, invalid/stale/foreign selection rejected, save/reload pending choice, selected quality retained and worker released for the next job |
| Cooldowns | Cooling X skipped while YouTube proceeds; order retained within X; deadlines restored; switching shared/per-platform preserves outstanding global deadlines; 429 captures Retry-After |
| UI and translation | Actual Chrome: fixed locale key parity/HTML keys, English switch, settings arrows/tabs/drafts, Tab/Shift+Tab/Esc/focus return, background inert, selection, 390px viewport and table scrolling |

Audit regressions additionally protect future-schema backups with missing/corrupt/valid older primary files, separate query-identified unlabelled media, reject unknown job-removal routes, preserve consistent authentication after a failed disconnect and make the advanced Cookie summary keyboard reachable. These use synthetic data, including fresh headless Chrome for network grouping and keyboard focus.

## Quality paths

Best and all caps (**2160, 1440, 1080, 720, 480, 360, 240, 144**) are submitted through actual UI controls and validated by the real HTTP API. Actual yt-dlp format selection uses synthetic format metadata; X native variant hooks and gallery-dl's delegated format options apply every cap. Tests cover lower fallback, separate audio/video, unknown dimensions, audio-only or only-too-high formats, source-size/label hints, extractor-dimension precedence, generic player changes, separate quality manifests/folders, retry retention and image normalization. Profile mode submits Best and rejects capped batch API requests.

This tests resolution selection logic, not the visual fidelity of each platform's codec. One synthetic 640×360 MP4 uses dynamic discovery and the existing capped download path; saved bytes equal the source and FFmpeg decodes the complete short fixture. Existing HLS/DASH tests also verify missing fragments, missing audio, merge failure and successful decode after recovery.

## Dynamic capture and faults

- Real Chrome executes an external script/config fetch, creates a player at runtime and reports its source height without downloading media during discovery.
- Extensionless HLS/DASH are recognised by Content-Type, and an anonymous JavaScript cookie remains domain scoped and transient.
- Separate players remain independent; normal/static extraction runs first and partial saved downloads do not start another browser attempt.
- Private redirects, local WebSockets, non-HTTP schemes and POST requests do not reach their private fixture. Cookies/Authorization never appear in candidate headers.
- Request/candidate/body budgets and missing optional dependencies have explicit tests. Rejected oversized resource reads count toward total bytes and end the scan.
- A real infinite JavaScript loop is stopped by parent capture supervision in approximately two seconds in its one-second-limit fixture; the owned child, browser and driver tree are terminated. Production capture limit is 45 seconds. Existing cancellation/tree tests protect unrelated processes.
- Capture 429 propagates to cooldown; other synthetic job failures and pending choices release the worker so subsequent work can start.

An initial Windows WebSocket `close()` route callback hung; the implementation now never connects the remote socket and avoids synchronous close in that callback. The regression now completes. An FFmpeg fixture used an invalid duration spelling during development; the corrected fixture uses `0.4` seconds. Failed/interrupted development runs are not counted as passing results.

## Remaining environment acceptance

- Fresh Windows installation with the Python 3.12 baseline.
- Actual Chrome connector pairing on a custom port and extension reload using an authorised account.
- GitHub CI/repository/tag/Release checks after repository creation.
- Live platform-specific JavaScript players, authenticated/interactive pages and newly changed extractors; support varies and no universal playback capture is claimed.

Existing upstream SSL option deprecation and occasional closed-socket ResourceWarnings remain dependency-maintenance observations; they did not fail the successful suite. Rerun these tests when changing the engine, Playwright or Chrome baseline.
