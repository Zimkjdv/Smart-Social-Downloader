# Changelog

Application changes are recorded here. Download engine and Chrome connector versions are tracked separately. The application version lives in [`ssdl/version.py`](ssdl/version.py).

## Unreleased

No GitHub release or tag has been created.

### Fixed

- Fix the first Windows GitHub Actions failure: explicitly read UTF-8 state in the selection regression, resolve temporary paths before comparing restored history, and allow Chrome fixtures a 30-second capture budget. Chrome launch now uses up to 30 seconds within the existing overall capture deadline, and navigation uses only the remaining budget. Preserve late HTTP 429 callbacks and report exhausted capture budgets as timeouts. Add two deterministic regressions; local verification passed 134 Python and 10 Node tests without skips.
- N03: validate connector Cookie record types, field lengths, control characters and finite expiration values before session selection. Malformed input returns a generic 400 without replacing the existing session, touching encrypted storage or consuming a valid pairing ticket; correct retry and fresh pairing remain available.
- N04: `/api/pause` requires an explicit JSON boolean. Missing values, strings, numbers, null and containers return 400 without changing or saving queue state.
- N05: bound the local HTTP server to 32 active connections, with a shared absolute 10-second header/body input deadline and a 5-second socket-write timeout. Reject excess connections with 503 / Retry-After; return 408 for incomplete body reads and close incomplete headers. Enforce unambiguous Content-Length, reject unsupported Transfer-Encoding and malformed/nonfinite JSON without echoing payloads, and release sockets/slots on disconnect or shutdown.
- Add 14 regression cases for Cookie selection/pairing preservation, strict pause input, slow/incomplete HTTP requests, request framing, disconnects, overload recovery, shutdown and injected write timeouts. See [testing details](docs/TESTING.md) for final results and limits.
- N03–N05 verification: 132 Python tests / 10 Node tests passed with zero skips; the final auth/queue follow-up passed all 17 cases. The service was restarted after confirming idle download/login activity; 25 completed jobs, hourly limit 80 and the connected X session were retained. Persistence, worker and environment health are ready. No external platform media was downloaded for this check.
- N01: validate saved URL/path/pacing syntax without network access, reconstruct jobs, queue, settings and cooldowns before committing any live state, and attempt a valid backup when application normalization fails. Preserve damaged primary bytes, keep the good backup and block automatic overwrites when no candidate can be fully restored.
- N02: filter migration history by source, quality, selected player and output root; account sync keeps only relevant highest-quality post history. Add shared UTF-8 chunked IPC for job input, RPC, progress, results and errors, retaining a 16 MiB frame limit and a 64 MiB logical-message limit. Oversize and malformed/truncated transfers report distinct errors; cancellation and subsequent jobs continue.
- Add regressions for malformed/late restore failures, backup preservation, offline URL recovery, unrelated large history, legacy source matching, large Unicode file lists, chunk corruption/limits and cancellation.
- Verification: 118 Python tests / 10 Node tests passed with zero skips; the final runtime follow-up also passed all 11 cases. See [testing details](docs/TESTING.md). The local service was restarted only after confirming idle download/login activity, retaining 25 completed jobs, hourly limit 80 and the connected X session; production history restored healthy. This deployment check did not download external media or inspect Cookie values.

### Changed

- N06 (state ownership and lifecycle): add typed AppState/AppContext and an explicit create_app factory; inject an instance into HTTP routes, scheduler and repository instead of the app module. Importing the entry point and constructing a context no longer restore login/history or start workers. After binding the port, start restores state and X login once. Close stops instance-owned helpers, prevents new pairing/scans and persists the stopped queue; separate applications no longer share mutable queue/service state. Runtime paths, public API and connector ID stay compatible. Engine/frontend module splits remain in ROADMAP.
- Document lock ownership and shutdown order, remove stale backend imports, and migrate API/queue fixtures to temporary AppContext instances without mocking import-time auth restore. Add 11 lifecycle acceptance cases for fresh-process imports, binding failure, restart recovery, idempotence, late login callbacks, helper shutdown and two running contexts.
- N06 verification: 145 Python tests / 10 Node tests passed with zero skips; final lifecycle follow-up passed 11 cases. Source allowlist validates 118 files. Tests used temporary data and synthetic sessions; production login/history were not restored by tests. Remaining splits, performance measurements and transport-fixture follow-up stay in ROADMAP.
- Confirm the first hosted Windows/Python 3.12 CI success at commit 2bdb9f7; the repository and recommended GitHub topics are now published. Private reporting, preview tags and Releases remain pending.
- Initialize the main branch for [Zimkjdv/Smart-Social-Downloader](https://github.com/Zimkjdv/Smart-Social-Downloader), with a reviewed source-only initial commit. Downloaded media, local history, Cookie storage, virtual environments, logs and generated archives are excluded. This is source publication, not a tagged preview Release or confirmation of GitHub CI/private reporting.
- Use Python 3.12 as the installation and CI baseline, raise the runtime minimum to 3.12, prefer that interpreter in first-time setup (with PATH fallback if the launcher cannot find it) and remove the older websockets dependency branch.
- Update the roadmap with planned Docker deployment; no container deployment is implemented yet.
- Consolidate completed review milestones here and pending work in [ROADMAP.md](ROADMAP.md); retire the former review checklist and update documentation links, directory trees and the source-package allowlist.
- Rename the planning file to uppercase ROADMAP.md and update all documentation and package references. N01–N05 are completed here; remaining review findings stay in the roadmap.

## 0.1.0-preview.2 — 2026-10-11

**Unpublished preview.**

### Added

- Optional JavaScript video/audio discovery using a fresh Chrome context, checked Python networking, bounded resources and the existing quality/player-selection workflow. Defaults off; `python tools/manage.py browser-setup` installs optional pinned packages.
- Parent-supervised capture deadline for blocked page scripts and browser calls, including owned browser/helper cleanup.
- P2 regression, fault-injection, all quality-cap paths and real headless Chrome UI tests using synthetic data. See [testing records](docs/TESTING.md).
- Python 3.12 CI installs optional capture and requires Chrome so browser acceptance cannot silently skip on that lane. GitHub execution remains pending.

### Fixed

- Avoided a Windows synchronous WebSocket-route close deadlock; remote WebSocket forwarding remains disabled.
- Capture byte budgets count rejected oversized resources and stop on exhausted resource budgets.
- Preserve newer-schema backups, including missing/corrupt primary history and saves without a prior load.
- Keep different query-identified media separate unless a DOM/JSON player explicitly groups their renditions.
- Restrict job removal to its exact API route; preserve consistent X login state when disconnect storage removal fails.
- Restore keyboard navigation from the advanced Cookie summary and prevent delayed older status snapshots from replacing newer UI state.

### Documentation

- Updated bilingual homepages/usage, optional setup, architecture, third-party notices and implementation records.
- Recorded the full-project audit and six reproduced fixes in [PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md).

## 0.1.0-preview.1 — 2026-10-11

**Unpublished preview baseline.** No GitHub release or tag has been created. These entries summarize existing work; they do not mean all features were introduced or tested on this date.

### Included

- Local Windows web interface with English / Traditional Chinese switching.
- Queued video/image downloads through yt-dlp, gallery-dl and FFmpeg, platform folders, HLS/DASH integrity checks and original-size images where available.
- Best video quality by default, optional height limits, and selection between multiple generic players.
- X account media scans, existing-file verification, missing/new media sync and Chrome session connection with Windows encrypted storage.
- Serial worker, 3–8 second job delays, configurable hourly quota and per-platform/shared cooldown modes.
- Cancellation, progress deadlines, versioned state recovery, thumbnails, storage maintenance, paginated status and redacted diagnostic exports.
- Local API source checks and public network target validation.

### Release preparation

- Short English and Traditional Chinese README pages with a fictional-data UI illustration; detailed usage moved into `docs/USAGE*.md`.
- A shared application version in the header, settings, status API, diagnostic export, launcher output, CLI and source archive name.
- Bug, installation, feature and private-security-contact Issue forms; contribution, security and maintenance guides.

### Verification status

At the original preview baseline, the remaining P2 changes and quality dropdown still needed regression and real-browser acceptance. Follow-up results are recorded in [TESTING.md](docs/TESTING.md). GitHub CI and clean-Windows/Chrome pairing checks remain in [ROADMAP.md](ROADMAP.md). Installation and CI now use Python 3.12.

## Completed implementation milestones — 2026-10-10 to 2026-10-11

Consolidated from the former project review. These are historical implementation milestones, not additional releases or claims of universal platform compatibility. Older counts (5, 16, then 59 Python / 8 Node tests) were intermediate results; the later recorded baseline is 104 Python / 10 Node tests, with zero skips. See [testing scope and evidence](docs/TESTING.md). Pending acceptance and newly discovered edge cases are tracked only in [ROADMAP.md](ROADMAP.md).

### P0 and P1

| ID | Completed work |
| --- | --- |
| R01 | Consistent Host/Origin/cross-site checks on sensitive GET and mutation APIs; dedicated Chrome pairing remains available. This controls access to the local service, not the media URLs users can submit. |
| R02 | Generic media identity retains query parameters, separates different media/quality/signatures and avoids implicit overwriting of completed files. Existing legacy files remain; signature changes can produce a new identity. |
| R03 | HLS/DASH fragment retries capped at three; missing fragments fail instead of reporting complete, including gallery-dl delegation. Local missing-video/audio, merge-failure and recovered-source fixtures verify behavior; historical downloads are not automatically revalidated. |
| R04 | MIT project license, third-party notices, privacy exclusions, pinned baseline dependencies, separate setup/start/update flows, source-only archive allowlist and Windows CI configuration. GitHub publication is still pending. |
| R05 | Shared API client with body-inclusive request deadlines, response validation, retained last-good data, restored controls and no automatic resend of uncertain writes. |
| R06 | Isolated download processes, Windows Job Object cleanup, cancellation for normal/account jobs, configurable 30–3600 second progress deadline (default 300), merge CPU activity handling and worker recovery. |
| R07 | Shared setup/start/UI diagnostics, executable and dependency checks, background caching and actionable optional-feature warnings. |
| R08 | Source manifests verify original location, size, modification time and completion; missing/moved/renamed files are fetched again. Stable YouTube IDs, migration and account per-file checks are covered; content-hash deduplication is not implemented. |
| R09 | Versioned state, validated backups, atomic writes, visible save failures and retry, interrupted-job recovery and future-schema protection. Schema 2 later adds validated player-selection metadata. |
| R10 | Validated SSDL_PORT and connector 1.1.0 user-selected destination; origin mismatch rejected before Cookie access, one-time pairing tickets and explicit failure states. |
| R11 | Shared public HTTP/HTTPS target and actual-connection checks, including redirects and HLS/DASH subresources; unsupported external network downloaders/proxies rejected. This is not an OS sandbox. |
| R12 | Shared error/warning redaction and diagnostic exports that omit private source history, titles, file lists, download paths and login data. |
| R13 | Synthetic API/DOM/connector, persistence, queue, network, process and download regression/fault tests; later extended with real headless Chrome on synthetic pages. |

### Login and interface follow-ups

- Check Windows encryption capability before obtaining login Cookies; explain normal desktop startup when DPAPI is unavailable in a restricted process environment. Pairing failures reach the main UI, consumed tickets are cleared, pending status refreshes every two seconds and waiting can be cancelled. Default-port pairing succeeded in the normal Windows user environment; this does not complete new-connector/custom-port acceptance.
- Split settings into General, X Login and Diagnostics tabs, retaining drafts and saving all fields; centered SVG close button, fixed header/footer, scrollable content, responsive diagnostic columns and keyboard/focus behavior.
- English and Traditional Chinese UI, compact icon actions/tooltips, previews and thumbnails, file-location actions, filename-first display with full-path tooltips, timestamps with years and SIZE/TIME download duration.
- Queue pause/resume, retry and clearing controls, configurable hourly quota and confirmed Rate reset. Delay/cooldown protections remain when quota counts reset.
- X account media scanning reports discovered totals and progress, supports incremental missing/new media retrieval and retains completed files when rows are cleared.

### P2 and media workflows

- Summary and paginated job/file APIs; job pages of 10/20/50, previews limited to 20 paths and file-detail pages capped at 100. A synthetic 200-job/100,180-file list shrank from 4,563,700 to 23,350 response bytes; this was serialization size, not full HTTP/disk latency.
- Row/cell reconciliation retains unchanged DOM, image elements, focus, page and scroll state; delegated actions avoid duplicate listeners and stale page/filter responses are ignored.
- Incremental download capacity accounting with ten-minute/manual background correction; generated thumbnail maintenance with 128 MiB/1000-file budget and 30-day unused expiry. Cleanup does not remove source media.
- API, scheduler and repository moved out of the application module; frontend state/presentation/login modules extracted. Existing shared-state coupling remains a roadmap improvement.
- Fixed English/Traditional Chinese locale keys (626 each), modal focus containment/return, Esc, inert backgrounds, narrow-screen and reduced-motion support.
- Multiple independent generic players enter a selection state and release the worker; selected source and quality persist across retries. Explicit player groupings join renditions, while different query-identified media remain distinct. No claim of general-purpose advertisement detection.
- Independent platform cooldowns by default, optional shared mode, persisted deadlines and scheduler bypass for cooling platforms; serial worker, hourly quota, 3–8 second job delay and minimum request spacing remain.
- Corrected HTML5 rendition ranking using resolution metadata and labels. One recorded local replacement was verified as 1592×1080 and 149,520,781 bytes; this single-media check was not acceptance of every quality route.
- Best quality remains default; optional 2160p through 144p height caps choose the highest available rendition within the cap without upscaling. Unknown/no-fitting resolutions report reasons. Images retain original size; account sync keeps highest available quality. Distinct preferences use separate identity/output locations.
- Optional JavaScript capture and subsequent P2/quality/browser regressions are recorded under preview.2 above. The earlier implementation-stage “not yet tested” notes are superseded by those later results, except real-account/live-platform/clean-system acceptance.

### Structure, release preparation and historical validation

- Backend moved to `ssdl/`, documentation to `docs/`, retaining the root launcher, runtime locations and connector location. English README became the default homepage; Traditional Chinese is in README_CN, detailed operations in `docs/USAGE*.md`.
- Added fictional-data SVG homepage artwork, centralized application version, diagnostic version display, issue/PR templates, security policy and contribution/maintenance guidance. Engine, connector and state-schema versions remain separate.
- Verified baseline installation in an independent Windows source copy and fresh Python 3.12 venv; startup still worked with package downloading disabled. This was not a clean Windows OS installation.
- Previous deployment checks performed only when the queue/login operation was idle: latest recorded service state retained 25 completed jobs, hourly limit 80 and connected X state, with 13 healthy environment checks. These historical snapshots do not describe every later runtime state.
- Prior audit reproduced and fixed six defects: future-schema backup overwrite, query-media grouping collisions, unknown POST removal routes, inconsistent disconnect on storage failure, advanced-Cookie keyboard navigation and stale status responses. Details remain in [PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md).
- Historical full regression: 104 Python / 10 Node tests, zero skips; Python duration 52.765 seconds. Additional syntax, dependency, locale, documentation-link and source-archive checks were recorded separately. Archives grew with implementation; the latest pre-migration archive contained 113 allowlisted source files, excluding runtime data.
