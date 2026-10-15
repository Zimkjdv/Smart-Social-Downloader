# Usage guide

[English homepage](../README.md) | [繁體中文操作指南](USAGE_CN.md)

Detailed installation and interface instructions. Paths in commands are relative to the project root. For application versions and release steps, see [maintenance](MAINTENANCE.md).

## Features

| Feature | Behavior |
| --- | --- |
| Multiple URLs | Paste one URL per line, or separate URLs with spaces or commas. Up to 30 URLs per submission and 200 jobs in the list. |
| Background queue | One worker processes jobs sequentially. Refreshing or closing the browser does not stop the backend. |
| Video quality | Best quality by default, with optional 2160p–144p height limits. Retries retain the job's choice; X account sync continues to use best quality. |
| Queue pacing | Random 3–8 second delay between jobs, shared request pacing, configurable hourly limit, and rate-limit cooldown. |
| X account media | Download an account's images/videos, including replies; exclude reposted and quoted media. Stop/resume sync, verify existing files, and fetch new media. |
| Account scan | Discover accessible media before downloading, then display total, existing, completed, and remaining file counts. |
| Generic web fallback | Discover HTML5 sources, metadata, player JSON, and embedded players when yt-dlp reports an unsupported page. |
| Stream integrity | Fail on unavailable HLS/DASH fragments after retries. Missing audio and merge errors remain failures. |
| Platform folders | Group downloads by platform, preserving account/album subfolders where supplied. |
| Live status | Queued, active, completed, and failed counts, current progress, file size, and elapsed download time. |
| Job management | Pause/resume, retry failed jobs, remove records, and clear completed/all jobs while preserving downloaded files. |
| Filters and pagination | Server-side status/platform/search filters and 10/20/50 jobs per page. File lists and diagnostics load on demand. |
| Local previews | Generate image thumbnails and video frames from saved files without fetching them again. |
| Efficient updates and caches | Preserve unchanged table cells, update storage totals incrementally, and reclaim generated previews within a 128 MiB / 1,000-file budget. |
| File actions | Icon buttons for viewing/playing media, opening its folder, retrying, and removing the record; tooltips describe actions. |
| Download warnings | A compact warning count opens full diagnostic messages. |
| Header controls | Rate counter/reset, actual folder size/file count, status refresh, pause/resume, and settings. |
| Languages | Switch between English and Traditional Chinese; the browser remembers your choice. |
| Settings tabs | General, X sign-in, and Diagnostics sections, with visible header/footer controls and preserved drafts when switching tabs. |
| Persistence | Versioned state, validated backups, corruption recovery, and visible save errors. Interrupted work is queued again. |
| Cancellation and health | Stop any active job; isolate download processes and stop stalled work after a configurable no-progress deadline. |
| Verified file history | General downloads use source manifests with original paths, sizes, and modification times. |
| Diagnostic export | Export a redacted local report without media URLs, file paths, or session cookies. |
| X login connector | Connect an existing X session through ordinary Chrome. Stored session cookies use Windows encryption and stay out of API responses. |
| Environment diagnostics | Settings shows Python, engines, FFmpeg, JavaScript runtime, dependencies, Chrome, session encryption, and the local port, with repair guidance. |
| Resilient status updates | API requests have a deadline and validate responses. Failed updates retain the last valid list and recover the controls. |

Platform support depends on upstream extractors, content availability, and access permissions. See [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [gallery-dl configuration](https://gdl-org.github.io/docs/configuration.html).

## Quick start

The main supported environment is **Windows with Python 3.12**. Installation and CI use Python 3.12, matching the local environment. Chrome session storage and opening files/folders use Windows features.

1. Download or clone the source and extract it into your own folder.
2. Run **`setup.bat`** to create `.venv`, install the baseline from `requirements.lock.txt`, and check the engines and FFmpeg.
3. Run **`start.bat`**.
4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) in your browser.

`start.bat` also runs setup if installation has not completed. Subsequent starts check the local environment, including `pip check`, without installing or updating packages. Close the service terminal to stop the backend.

```powershell
python tools/manage.py setup
.\.venv\Scripts\python.exe tools/manage.py start
```

Some sites, including YouTube, require a supported JavaScript runtime. Diagnostics checks for **Node.js 22+ or Deno 2.3+**, including whether the executable runs and its version is supported; it does not install a global runtime automatically. See the [yt-dlp JavaScript runtime requirements](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

```powershell
.\.venv\Scripts\python.exe tools/manage.py check
```

### Environment diagnostics

Open **Settings → Diagnostics → Environment diagnostics** for individual results and repair instructions. Setup, startup, and the interface share the same checks. Required engine, FFmpeg, or dependency failures stop the launcher; optional JavaScript runtime, Chrome, or session-encryption warnings describe which features need attention.

The server checks once in the background at startup. Status polling reads the cached report; **Recheck** starts another local inspection. External diagnostic commands have time limits and run outside the download worker. Checks do not access your saved cookies or download history, request platform content, or install packages. After installing a runtime or changing PATH, restart the service so it sees the new environment.

### Settings

- **General:** download folder, hourly job limit, Rate reset, and no-progress timeout.
- **X sign-in:** Chrome session connection, disconnect, and the advanced cookie-file option. The header's X sign-in control opens this tab directly.
- **Diagnostics:** environment checks, local state/worker health, save retry, and diagnostic export.

The header, tabs, and footer stay visible while the content scrolls. Switching tabs or languages preserves unsaved settings; **Save settings** saves fields across all tabs. Cancel or close discards unsaved edits. Use Left/Right arrow keys or Home/End on a tab to navigate; Escape closes the settings window.

### Custom local port

The default is `8765`. To use another port, stop the service and start it from PowerShell:

```powershell
$env:SSDL_PORT = "8877"
.\start.bat
```

Open `http://127.0.0.1:8877`. For X login, open the Chrome connector popup, expand **本機連接設定 (Local connection settings)**, enter **8877**, and click its connection button. This changes the connector's destination, not the server port. The connector remembers the selected port and only sends to `127.0.0.1`; a connection page cannot silently select a different destination. `SSDL_PORT` accepts whole numbers from 1 to 65535. Unavailable ports still require choosing a free port.

## Download media

Select **Media URLs**, paste links, and click **Add to Download Queue**. Jobs run in the backend; the browser shows their status.

The refresh button reads local status without submitting downloads or requesting platform content. Status updates every **30 seconds while idle** and **2 seconds while queued or active**. Refreshing the whole page leaves backend work running, but may discard unsent form input.

Interface API requests have a **15-second deadline**, including reading the response body. Invalid JSON or unexpected response fields leave the last valid data visible and show an error; controls become usable again, and polling continues. When a write request times out, the backend may already have performed it: the interface reads status again instead of automatically resubmitting that action. Check the updated status before retrying.

Completed rows show size, elapsed time, thumbnails, and file actions. Single-file rows abbreviate the directory and show the filename; hovering reveals the full path. Multi-file rows let you choose a file to open. Full dates include the year.

The list defaults to 20 jobs per page. Filters, search, pagination, scrolling, and language changes do not cancel downloads. Pause prevents new work from starting; an active single-post download finishes. X account sync pauses between posts.

**Stop** ends the active job and its owned helper processes while preserving saved files and partial files. The next queued job can continue. Settings provides a **no-progress timeout**, default **300 seconds**, configurable from **30 to 3600 seconds** for subsequent jobs. Network data, changing progress, and CPU activity while merging reset that timer; deliberate queue waits are exempt. It is not a total download-duration limit.

### Status and cache performance

Polling retrieves the current job page with global counters and the active monitor. Each row carries at most 20 path previews plus the full file count; opening a multi-file selection fetches up to 100 filenames per request. Unchanged rows/cells keep their DOM nodes and thumbnails.

Storage updates after downloads and X post boundaries. External filesystem changes are reconciled by a background scan after 10 minutes on a status read, or through **Settings → Diagnostics → Rescan storage**. **Clear thumbnail cache** removes generated previews; the cache budget is 128 MiB / 1,000 previews, with 30-day expiry. Original media remains intact.

See [performance details and synthetic measurements](PERFORMANCE.md) for API contracts, limits, and verification scope.

## X account media and login

1. Sign into X in your normal Chrome browser.
2. Open **Settings → X sign-in** and connect Chrome login. If direct cookie access is unavailable, load `chrome-extension/` as an unpacked extension at `chrome://extensions`, then use its connection button.
3. Select **X Account Media** and enter `https://x.com/username`, `https://x.com/username/media`, or `@username`. Multiple accounts use the same separators.
4. Add the account to the queue. The tool scans accessible media first, downloads missing files, and displays file-count progress.

Account sync includes media published in replies and excludes reposts and quoted-post media. Counts describe media accessible during that scan, rather than every item ever posted. Deleted posts, login requirements, and platform limits can affect discovery.

Subsequent syncs verify recorded files and fetch new or missing media. Stop terminates the current sync; retry uses saved history to recover incomplete work. Verified existing posts do not consume another hourly download slot.

The connector reads selected X cookies and sends them to the local service. It does not sign into Google or Apple. Sessions use Windows DPAPI encryption. Disconnect in settings to remove the saved session; removing the extension revokes its browser permissions. Advanced users can supply a Netscape-format X cookie file. Do not commit or upload cookies.

If Windows reports that session encryption is unavailable, close the service and run `start.bat` from your normal Windows desktop. A service launched under a restricted automation or sandbox account may not be able to use your Windows encryption keys. Reload the connection page and reconnect; signing into X repeatedly does not fix a local encryption error. Failed pairing attempts discard their one-time ticket so the next click can request a fresh one. Login status refreshes every two seconds while connecting or waiting for the connector.

The unpacked connector may need manual maintenance when Chrome, X cookie behavior, or the pairing protocol changes. After updating its files, reload it in Chrome and reconnect if needed. Changing the public manifest key changes the extension ID and can break pairing. Extractor updates normally belong to yt-dlp/gallery-dl.

**Updating an existing connector to 1.1.0:** reload it at `chrome://extensions` once, then refresh the local connection page. This version adds storage permission for the selected local port; the extension stores the port, not a copy of your X cookies. New installations use the same unpacked-extension steps above.

See the [connector instructions](../chrome-extension/README.md) and [Chinese usage guide](USAGE_CN.md).

## Queue limits and cooldown

Settings → General offers per-platform cooldowns (default) or a shared cooldown. A cooled platform can wait while another eligible platform proceeds; all jobs still share the hourly Rate limit, request interval and single worker. Changing mode and Reset Rate preserve existing cooldowns. See [P2 interaction and architecture](P2_COMPLETION.md).

- **Delay:** 3–8 seconds between jobs, including the initial scheduled start.
- **Requests:** managed Python HTTP calls share a one-second minimum start interval. No separate transfer bandwidth cap is applied. Internal redirects may not trigger a separate pacing interval; network target checks still apply.
- **Hourly Rate:** default 40 started jobs in a rolling 60-minute window, configurable from 1 to 1000. Failures and retries count. A multi-image post counts as one job; account downloads count posts that need media downloads.
- **Reset Rate:** click the header counter or settings reset button and confirm. Reset clears local usage while preserving the limit, pacing, and platform cooldown.
- **Cooldown:** HTTP 429 or recognized throttling triggers backoff of 60, 120, 240, 480, then 900 seconds. A longer `Retry-After` takes precedence, capped at one day. By default only that platform waits; shared mode applies the wait to all platforms.
- **Resume:** queued work continues when limits permit. Cooldown expiry alone does not resubmit failed jobs.

Rate usage and cooldown are persisted. Pacing lowers request frequency but cannot guarantee avoidance of platform restrictions or remove account restrictions.

## Files, quality, and duplicate checks

```text
downloads/
├── youtube/
├── twitter/account/
├── instagram/account/
└── example.org/
```

Unknown sources use a sanitized host-based folder. CDN media discovered from a page uses the original page's platform folder. Custom download locations use the same grouping.

X images request `orig`; videos select the highest available video/audio combination and use FFmpeg to merge without re-encoding. General downloads use `data/media-manifest.sqlite3` to verify original paths, sizes, modification times, and successful completion. YouTube link variants use the stable video ID; X posts use the post ID. Existing direct-image and X-account histories use the same file-verification rules.

Video selection prioritizes reported resolution. Generic HTML5 pages also read source quality attributes such as `size`, `data-height`, and labels, plus explicit filename markers such as `1080p` or `1920x1080`. Existing extractor dimensions take precedence. This prevents a descending source list from selecting its last, lowest-resolution entry. The list shows the selected dimensions or height; unavailable dimensions display **Resolution not reported**. These are source declarations, not a guarantee of visual quality or the uploader's original file. Previously completed files are not automatically upgraded: use the row's **Retry** icon to fetch the current best version and replace the same-name file. See [video quality details](VIDEO_QUALITY.md).

**Moved, renamed, removed, or relocated files are downloaded again.** The tool checks recorded locations and does not search your disks for moved copies. A single stable media ID can retain its recorded filename when the title changes; changed albums or formats may use new paths. Verified legacy successful rows can seed the manifest. A same-name file with no trusted completion record is insufficient. This is not global content-hash deduplication.

Generic direct-media IDs combine the page and full media URL, preserving query parameters and ignoring fragments. Different media IDs and renditions remain distinct. Unknown signature parameters are retained, so a changed signature can produce a new filename. Updated IDs may also differ from older path-only IDs; old files are preserved. Candidates do not append to another candidate's partial file.

HLS/DASH fragments retry up to three times. Missing required fragments, missing audio, and merge failures produce failed jobs. Previously completed files are not automatically revalidated. See [duplicate-check details](DOWNLOAD_DEDUP.md) (Chinese).

## Choosing video quality

In **Add download → Media URLs**, choose **Best quality (default)** or a height limit: **2160p, 1440p, 1080p, 720p, 480p, 360p, 240p, or 144p**. These are preferences, not a list fetched from each video's player. No confirmation popup is added.

The tool chooses the best available version **at or below the selected height**. A 720p limit can select 480p when 720p is unavailable. If no reported version meets the limit, the job fails with an explanation; it does not silently exceed the limit or upscale. Images keep their source dimensions and bytes. X posts can select exposed MP4 renditions; X account batch sync currently stays on Best quality.

Each job saves its choice, which retries reuse even after changing the input dropdown. The dropdown starts on Best quality when the page is opened and keeps the current choice during status refreshes. Different choices create separate jobs and completion records; capped downloads go to `<platform>/quality-720p/...` (for a 720p limit), preserving existing Best files. For a mixed-media gallery, its source images are also saved in that choice's folder. Direct image links use their existing shared image history. Changing the limit requires submitting the URL again. See [selection and storage details](VIDEO_QUALITY.md).

## UI maintenance and keyboard use

UI copy uses fixed keys in `static/locales.js`. Tab/Shift+Tab stays inside the topmost dialog, Escape closes it, and focus returns to its trigger. Narrow windows retain scrollable filters and tables; controls wrap. See [P2 details and verification status](P2_COMPLETION.md).

## Generic web fallback

For unsupported pages, discovery checks HTML5 video/audio/source elements, Open Graph/Twitter player metadata, JSON-LD, player JSON, literal media URLs, and embedded frames. Relative URLs and common encodings are supported, with bounded page size, depth, candidates, and scan time.

MP4/WebM/HLS/DASH candidates return to yt-dlp for selection and downloading. The source Referer and temporary cookies received during public-page discovery are passed along without saving those cookies to disk. Candidates are grouped by player. Multiple generic players pause as **To choose**; use the row’s choose icon to select one before downloading. Quality variants within that player follow the quality dropdown. The worker continues other jobs while a choice is pending. This is not a whole-page gallery crawler.

The static scanner does not execute scripts. Optional JavaScript video/audio capture is now available: run `python tools/manage.py browser-setup`, restart, then enable it in Settings → General. A temporary Chrome context observes supported MP4/HLS/DASH requests and runtime HTML5 sources, preserving quality and player selection. It does not use normal Chrome/X login cookies or click page controls. Underlying HTTP streams must be found for `blob:` players; DRM, WebSockets, POST-only or interactive/login-only flows remain unsupported. See [setup and bounds](DYNAMIC_CAPTURE.md) and [acceptance tests](TESTING.md).

## Updates

Stop the service, run **`update.bat`**, then restart. Updates use compatible ranges in `requirements.txt`; `requirements.lock.txt` remains the recovery baseline.

```powershell
.\.venv\Scripts\python.exe tools/manage.py update
```

Run `setup.bat` to reinstall the baseline after a problematic engine update. Source updates do not trigger dependency updates on every launch.

## Local API and privacy

The service binds to loopback. Sensitive APIs validate Host/Origin and browser cross-site metadata. Other websites attempting to read job history or operate the tool are rejected without private state. The connector has a narrowly scoped pairing endpoint.

This protects access to the **local API**; it does not restrict platforms you paste. It is not an account-permission system against other programs on the same computer.

The HTTP service admits up to 32 active connections. Headers and request bodies share a 10-second absolute input deadline; socket writes have a 5-second timeout. Excess connections receive 503 / Retry-After; incomplete body reads time out with 408. POST bodies need a single Content-Length of 1–100,000 bytes; chunked request bodies are unsupported. These transport limits do not stop background downloads or bound disk operations inside an API route. `/api/pause` requires an explicit JSON boolean. Invalid connector Cookie data returns 400 while retaining the saved session and valid pairing ticket. See [reliability details](RELIABILITY.md).

Separately, download processes only connect to public HTTP/HTTPS media targets. DNS answers, numeric socket targets, redirects, HLS keys/fragments, and DASH resources are checked. Loopback and private media targets are rejected. Native HLS/DASH and local FFmpeg merging are supported; system proxies, curl impersonation, RTMP, and external FFmpeg network downloading are unavailable under this policy. This is an application transport check, not an OS sandbox.

Settings shows state-saving and worker health. `data/state.json` uses schema version 2 (with migration from versions 0/1) and keeps a validated `state.json.bak` before replacement. A damaged primary can recover from the backup; newer schemas remain untouched. On a save error, changes remain in memory: fix disk permissions/space and use **Retry saving history** before closing the service.

**Export diagnostics** downloads a local JSON report with redacted errors and environment/worker/state information. It omits source URLs, media titles, file lists, download paths, and actual login cookies. Nothing is sent automatically. See [reliability and recovery details](RELIABILITY.md) (Chinese).

Runtime data, cookies, downloaded media, `.venv`, logs, and generated packages are excluded from normal Git tracking. Inspect staged files before publishing: `.gitignore` cannot erase committed secrets or recognize every arbitrarily named export.

## Project structure

```text
smart-social-downloader/
├── app.py                      Launch entry point
├── setup.bat                   First install / restore baseline dependencies
├── start.bat                   Check environment and start the service
├── update.bat                  Update download engines explicitly
├── requirements.txt            Compatible dependency ranges for updates
├── requirements.lock.txt       Pinned installation baseline
├── requirements-browser.txt    Optional pinned Playwright dependencies
├── README.md                   English documentation
├── README_CN.md                Traditional Chinese documentation
├── CHANGELOG.md                Application changes
├── SECURITY.md                 Private vulnerability reporting
├── CONTRIBUTING.md             Contribution and Issue guidance
├── ROADMAP.md           Pending findings and acceptance work
├── LICENSE                     MIT license for this project's code
├── THIRD_PARTY_NOTICES.md       Dependency licenses and distribution notes
├── .gitignore                  Exclusions for local data and generated files
├── ssdl/                       Python backend package
│   ├── __init__.py             Package marker and version export
│   ├── version.py              Single application version
│   ├── app.py                  Composition root, state views and startup
│   ├── http_api.py             HTTP routes, origin checks and actions
│   ├── http_server.py          Connection limits, input deadlines and socket cleanup
│   ├── scheduler.py            Serial scheduling and download lifecycle
│   ├── state_repository.py     History migration and saving
│   ├── media_selection.py      Validated generic player choices
│   ├── job_views.py            Bounded job summaries, pagination and file pages
│   ├── config.py               Shared local port configuration
│   ├── environment.py          Shared startup and interface diagnostics
│   ├── diagnostics.py          Common redaction and shareable diagnostic text
│   ├── persistence.py          State schema, atomic writes, backup and recovery
│   ├── media_manifest.py       Verified source-to-file completion records
│   ├── job_runtime.py          Download supervision, cancellation and deadlines
│   ├── job_runner.py           Isolated download process and private pipe protocol
│   ├── ipc.py                  Bounded UTF-8 frames and chunked job messages
│   ├── process_group.py        Ownership and cleanup of child/helper processes
│   ├── network.py              Public HTTP transport and actual address checks
│   ├── media.py                Compatible download entry points
│   ├── media_contracts.py      Shared source identity, paths and errors
│   ├── media_engines.py        Optional engines and shared settings
│   ├── media_coordinator.py    Routing, discovery and verified source reuse
│   ├── video_adapter.py        yt-dlp video/stream transfers
│   ├── gallery_adapter.py      gallery-dl configuration and transfers
│   ├── image_adapter.py        Original image bytes and history
│   ├── x_account_media.py      X account scan/sync and public-post media
│   ├── video_quality.py        Source resolution hints and video selection labels
│   ├── web_media.py            Generic page and player discovery
│   ├── browser_media.py        Optional temporary Chrome media discovery
│   ├── x_auth.py               X session connection and encrypted storage
│   ├── x_profiles.py           X account URLs and download history
│   ├── image_history.py        Direct-image history
│   ├── request_policy.py       Request pacing and cooldown
│   ├── download_stats.py       Download folder statistics
│   └── thumbnails.py           Local thumbnail generation
├── static/                     Browser interface
│   ├── index.html              Main page and settings
│   ├── locales.js              Fixed English / Traditional Chinese message keys
│   ├── ui_state.js             Shared in-page state
│   ├── job_presentation.js     Job formatting and keyed row rendering
│   ├── x_login.js              X login actions
│   ├── media_selection.js      Player selection dialog
│   ├── ui_accessibility.js     Modal focus and keyboard boundaries
│   ├── ui_accessibility.css    Focus, responsive and reduced-motion styles
│   ├── api.js                  API deadlines and response validation
│   ├── app.js                  Composition, state publishing and refresh
│   ├── settings_controller.js  Settings, drafts, tabs and Rate confirmation
│   ├── diagnostics_controller.js Environment, health and maintenance
│   ├── jobs_controller.js      List actions, filters, pages and file picker
│   ├── controller_lifecycle.js Owned listeners, timers and cleanup
│   ├── job_rows.js             Preserve rows and patch changed cells
│   ├── i18n.js                 English / Traditional Chinese translations
│   ├── settings.css            Tabbed settings window and scrolling content
│   ├── chrome-connect.*        Local connection page
│   └── *.css                   Layout and component styles
├── chrome-extension/           Chrome X session connector
│   ├── manifest.json           Identity, permissions, and content-script rules
│   ├── background.js           Pairing and cookie transfer to loopback
│   ├── connect.js              Bridge for the local connection page
│   ├── popup.html / popup.js   Connection controls and local port selection
│   └── README.md               Installation and maintenance
├── tools/                      Installation and release tools
│   ├── manage.py               Setup, start, update, and diagnostics
│   ├── package_source.py       Source-only ZIP packaging
│   ├── check_source_archive.py  Full regression in the extracted source ZIP
│   └── measure_state.py        Synthetic API payload measurement
├── docs/                       Detailed guides
│   ├── ARCHITECTURE.md         Module responsibilities and path rules
│   ├── TROUBLESHOOTING.md      Installation, API, and login troubleshooting
│   ├── RELEASE.md              Installation, API protection, and publishing
│   ├── RELIABILITY.md          Cancellation, manifests, recovery and diagnostics
│   └── DOWNLOAD_DEDUP.md       Existing-file and duplicate-check policy
├── tests/                      Local fixtures and regression tests
│   └── helpers/app.py           Shared isolated AppContext fixture
├── .github/workflows/          Windows CI configuration
├── data/                       Local state, session storage, and caches *
├── downloads/                  Default downloaded media *
├── .venv/                      Local Python environment *
└── dist/                       Generated source ZIP *
```

`ssdl` abbreviates **Smart Social Downloader**. It is the Python package name used in imports such as `from ssdl import media`; it does not name a platform download folder.

Folders marked `*` are created locally and excluded from Git and source packages. The backend keeps existing state and downloads relative to the project root. A custom download location replaces `downloads/` for media storage. See [architecture details](ARCHITECTURE.md).

## Tests and source packages

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/package_source.py --check
.\.venv\Scripts\python.exe tools/package_source.py
.\.venv\Scripts\python.exe tools/check_source_archive.py
```

Tests use temporary files, local HTTP fixtures, a synthetic DOM, mocked extension APIs and fresh headless Chrome, without private cookies or real-platform downloads. They cover byte preservation, format selection, dynamic discovery, API failures, cancellation, queue recovery, persistence, manifests, network targets, redaction, login challenges, keyboard access and release exclusions. The frontend suite uses Node's built-in test runner (Node.js 22+) with no npm installation. Install optional dependencies with `python tools/manage.py browser-setup` and ordinary Chrome for browser coverage; otherwise those tests explicitly skip. See [TESTING.md](TESTING.md) for results and remaining clean-Windows/real-account acceptance.

The ZIP at `dist/smart-social-downloader-<application-version>-source.zip` uses an explicit source list. It includes code, docs, licenses, and setup scripts, excluding your environment, history, cookies, and media. The acceptance command builds a disposable ZIP and runs the full suites from its extraction using installed dependencies. See [fixture and source boundaries](SOURCE_TESTING.md). GitHub also provides built-in source downloads.

## License and documentation

The project's own code and docs use [MIT](../LICENSE). Dependencies retain their licenses; gallery-dl is GPL-2.0-only. Combined distribution must respect third-party conditions. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md), including future executable/portable packaging requirements.

- [Traditional Chinese README](../README_CN.md)
- [Review and improvement progress](../ROADMAP.md) (Chinese)
- [Installation, API protection, privacy, and release guide](RELEASE.md) (Chinese)
- [Environment, API, and login troubleshooting](TROUBLESHOOTING.md) (Chinese)
- [Architecture](ARCHITECTURE.md) (Chinese)
- [Duplicate-check policy](DOWNLOAD_DEDUP.md) (Chinese)
- [Reliability, recovery, and diagnostic export](RELIABILITY.md) (Chinese)

## Application versions and reports

The application version in the header and Settings → Diagnostics comes from the running backend. Engine versions are listed separately. See [Maintenance](MAINTENANCE.md), [CHANGELOG](../CHANGELOG.md), [CONTRIBUTING](../CONTRIBUTING.md) and [SECURITY](../SECURITY.md). After replacing source files, restart the service and refresh the page to use the new version.
