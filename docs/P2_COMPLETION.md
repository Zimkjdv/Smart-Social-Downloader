# P2 architecture and interaction changes

Implemented on 2026-10-11. The earlier performance work remains described in [PERFORMANCE.md](PERFORMANCE.md).

## Components

- N06 follow-up (2026-10-13): `media.py` is a stable facade over shared contracts, engines, adapters, orchestration and X services. Settings, diagnostics and list controllers now complete the frontend split; N06 is complete. Remaining work is N07/N08 in ROADMAP.
- `ssdl/app.py` is the composition root and factory. `ssdl/app_context.py` owns typed AppState, instance-specific services, state views and explicit start/close; importing the entry point does not restore login/history or launch workers.
- `ssdl/http_api.py` owns HTTP routes, origin checks, settings and user actions.
- `ssdl/scheduler.py` owns serial scheduling, quota accounting, progress and job completion.
- `ssdl/state_repository.py` owns history loading, migration, atomic saving and legacy row consolidation.
- Components receive the live app context explicitly and never import `app`. Existing root callbacks remain bound aliases for embedding compatibility. This is an incremental split, not a conversion to a new web framework or a removal of all shared state.
- `static/ui_state.js`, `job_presentation.js`, `x_login.js` and `media_selection.js` retain shared state, keyed rows, login and player selection. Three controller factories receive explicit dependencies and own their private flags/listeners/timers; `app.js` composes them and publishes validated snapshots. Script ordering in HTML is explicit; no bundler or new dependency is required.

## Fixed translation keys and keyboard interaction

`static/locales.js` contains fixed keys with English and Traditional Chinese text. UI translation calls and static HTML attributes use these keys. Change wording in the catalog without renaming its key. `i18n.js` manages language selection, interpolation and a compatibility adapter for legacy backend messages; external titles, filenames and raw engine output are not translated.

`ui_accessibility.js` confines Tab/Shift+Tab to the topmost modal, closes that modal with Escape and restores focus. Background content is inert while a modal is open. Native dialogs and nested custom dialogs share the same boundary. Existing settings tab arrows/Home/End remain available. Focus outlines, horizontal filter scrolling, wrapping controls and compact dialogs support narrow windows; reduced-motion preferences are respected. The download table keeps horizontal scrolling so data and actions remain readable.

## Multiple generic players

1. Platform-specific extractors retain their normal behavior. A generic extractor page with multiple entries pauses before downloading media.
2. The static fallback groups HTML video/audio source variants by player, structured JSON source collections by their object, and embedded player results by their owning iframe. Ambiguous literals are separate choices rather than presumed to be the main content. Known JSON advertising/poster fields remain excluded; this is not a universal ad classifier.
3. A job becomes **To choose** (`selecting`). It releases the worker and does not enter failed-job retry batches. The row's choose icon opens a list of player ordinals, reported titles, source hosts and variant counts. Choosing one enqueues the job. Closing the dialog keeps the choice pending.
4. Only bounded metadata and an opaque player ID reach the UI or history. Signed candidate URLs and discovery cookies remain transient in the child. Selection re-runs extraction under the normal request policy; it does not trust a media URL supplied by the browser.
5. Retry retains the selected player and video-quality preference. A changed or missing player prompts again. The manifest identity and `media-<selection ID>/` subfolder separate chosen media from another choice. Player IDs use the page path and DOM/entry marker; they are not content hashes and page reordering can require re-selection.
6. Generic extractor choices are capped at 12; larger playlists fail with a request to use an individual player URL. Fallback retains its existing 6-page/2-depth/12-candidate/6-download-attempt/time/size limits. Discovery may be incomplete at those limits. Each selection pass is a normal queue attempt and consumes Rate; subsequent requests remain paced.

Single-player pages select the best available rendition at the configured quality ceiling without a confirmation. Choosing a player does not guarantee every source is reachable, correctly labelled, or available at the requested quality. The static workflow does not execute JavaScript; [optional dynamic capture](DYNAMIC_CAPTURE.md) is now available as a bounded fallback. DRM remains unsupported.

## Platform cooldowns

Settings → General offers **Per-platform cooldowns** (default) and **Shared cooldown for all platforms**.

- Cooldown belongs to the submitted job's platform. Its metadata, redirects, CDNs, media fragments and scan requests share that scope through the parent worker RPC. X/Twitter, YouTube URL aliases and other recognised platform domains use a common family; generic sites use the normalised source host.
- A 429 updates that platform's deadline and exponential backoff, honouring Retry-After. The scheduler can take the next eligible platform while preserving order within a platform. An already-running job remains the single active worker and may wait for its own cooldown.
- The global hourly quota, at least one-second request interval, 3–8-second job delay and single worker still apply. Platform grouping does not add concurrent workers or a separate Rate allowance.
- Switching to shared mode preserves the longest outstanding deadline. Switching back preserves any global deadline until it expires. Reset Rate never clears either cooldown type.
- Deadlines, strikes and mode are saved. Old shared cooldowns migrate as a global deadline so an update does not shorten an existing restriction. Settings displays outstanding platform deadlines; the banner reflects the active/eligible queued job instead of another platform's cooldown.

History now uses **schema 2**, accepting schema 0/1 input. It adds the `selecting` status and validated player metadata. An older application must not overwrite schema 2; keep its valid backup when upgrading.

## Verification status

The implementation round originally performed syntax checks only. Follow-up acceptance on 2026-10-11 now passes **104 Python + 10 Node tests**, including real headless Chrome with synthetic pages and APIs. Coverage includes bounded APIs/files, storage overlays and cache cleanup/failure, multi-player selection/persistence, pending-choice worker release, platform cooldown scheduling/restoration, all quality caps, bilingual UI, keyboard focus, drafts, pagination and narrow windows. Capture tests include 429, private redirects/WebSockets, anonymous cookies, byte-identical playable downloads and infinite-script timeout. The subsequent audit also covers newer-schema backups, query identity, route specificity, failed disconnects, advanced Cookie keyboard access and delayed state responses. See [TESTING.md](TESTING.md) for commands and limits. Actual account pairing, clean Windows with Python 3.12 and GitHub CI acceptance remain separate pending work.
