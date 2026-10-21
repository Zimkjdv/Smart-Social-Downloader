# Smart Social Downloader

English | [繁體中文](README_CN.md)

A local video and image download manager with a browser interface. Paste URLs, queue downloads, and organize media into platform folders. Powered by **yt-dlp**, **gallery-dl** and **FFmpeg**.

**Windows · Python 3.12 · MIT · Preview 0.1.0-preview.2 (not yet published)**

![Smart Social Downloader dashboard illustration](docs/images/dashboard-preview.svg)

*Interface illustration with fictional accounts, URLs and artwork; no personal download history.*

## Features

- **Videos and images:** multi-platform URL downloads, native HLS/DASH, original-size images where available, and platform/account folders.
- **Quality control:** highest available video quality by default; optional 2160p–144p height limits. Merge streams without re-encoding.
- **Optional JavaScript capture:** a temporary Chrome context can discover dynamic video/audio sources and hand them to the normal download queue. [Enable it](docs/DYNAMIC_CAPTURE.md).
- **X account media:** scan accessible images/videos first, show file totals, verify existing files, and sync missing/new media using your connected X session.
- **Queue control:** background serial downloads, 3–8 second delays, configurable hourly quota, per-platform/shared cooldowns, pause, stop and retry.
- **A manageable library:** local thumbnails, file size/time, view/play/open-folder actions, filters, pagination and preserved history.
- **Local operation:** English / Traditional Chinese UI, Windows-encrypted X session storage, environment checks and redacted diagnostic export.

## Quick start

1. Install **Python 3.12** on Windows, then download and extract the project source.
2. Run **`setup.bat`** to create `.venv` and install the pinned dependency baseline.
3. Run **`start.bat`**.
4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765), paste media URLs and click **Add to Download Queue**.

`start.bat` also sets up an unfinished installation. Later starts check the local environment without installing or updating packages. Keep the backend running; refreshing or closing the browser does not stop downloads.

Some sites, including YouTube, need **Node.js 22+ or Deno 2.3+**. Install a runtime if diagnostics requests it, then restart the service. See [installation and troubleshooting](docs/TROUBLESHOOTING.md).

For X login, sign into X in ordinary Chrome, then use **Settings → X sign-in**. If the connector is needed, follow its [one-time installation guide](chrome-extension/README.md). The tool connects an existing session; it does not perform Google/Apple sign-in.

## Limits and support

- Platform/extractor support and account access determine what is available. Not every URL can be downloaded; deleted, inaccessible or DRM content may be unavailable.
- “Original-size / best quality” means the files a platform exposes. The uploader's pre-compression original cannot be reconstructed.
- Generic discovery handles static HTML/player data and embedded players; multiple players can require a choice. Optional JavaScript capture needs Playwright and ordinary Chrome; interactive/login-only/DRM transports can remain unsupported.
- Pacing cannot guarantee avoidance of account restrictions. Default quota is 40 started jobs per rolling hour; failures and retries count. Submissions allow up to 30 URLs, with up to 200 job records.
- Windows is the primary supported environment. macOS/Linux, clean-Windows/Chrome pairing and all preview workflows are not fully verified. See [review progress](ROADMAP.md).

## Documentation

| Guide | Contents |
| --- | --- |
| [Usage](docs/USAGE.md) / [繁體中文操作指南](docs/USAGE_CN.md) | Settings, quality, file actions, X sync, queue limits and CLI commands |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Installation, diagnostics, local API and login repair |
| [Chrome connector](chrome-extension/README.md) | Installation, pairing, custom port and reloading |
| [Video quality](docs/VIDEO_QUALITY.md) · [Existing-file checks](docs/DOWNLOAD_DEDUP.md) | Selection, storage and duplicate-download rules |
| [JavaScript capture](docs/DYNAMIC_CAPTURE.md) · [Testing](docs/TESTING.md) | Optional setup, capture bounds, regression and browser acceptance |
| [Project audit](docs/PROJECT_AUDIT.md) | Reproduced bugs, fixes and remaining acceptance (Chinese) |
| [Reliability](docs/RELIABILITY.md) · [Performance](docs/PERFORMANCE.md) | Recovery, cancellation, integrity, pagination and cache behavior |
| [Architecture](docs/ARCHITECTURE.md) · [P2 details](docs/P2_COMPLETION.md) | Module boundaries, UI keys, player choice and cooldown scope |
| [Release privacy](docs/RELEASE.md) · [Maintenance](docs/MAINTENANCE.md) | Source packages, application/engine versions and release checklist |
| [Installation](docs/INSTALLATION_ACCEPTANCE.md) · [Console acceptance](docs/CONSOLE_ACCEPTANCE.md) | Fresh source/venv, update/restore, real Ctrl+C and Windows CI |
| [Docker deployment](docs/DOCKER.md) · [Storage and recovery](docs/DOCKER_STORAGE.md) | Experimental Linux amd64 recipes, health checks, volumes, backup and rollback; host/browser acceptance remains |
| [Docker X login and files](docs/DOCKER_LOGIN.md) | Host Chrome pairing, memory/external-key sessions and browser media/file actions |
| [Docker runtime acceptance](docs/DOCKER_ACCEPTANCE.md) | Isolated image/context checks, synthetic FFmpeg/Node verification and Linux CI |
| [Docker service acceptance](docs/DOCKER_SERVICE_ACCEPTANCE.md) | Disposable Compose startup, storage, backup/restore, failure recovery and local network checks |
| [Docker login/media acceptance](docs/DOCKER_INTERACTION_ACCEPTANCE.md) | Invented sessions, encrypted restart/key recovery and original-byte HTTP file access |

The homepage and usage guides are bilingual. Several technical guides are currently in Traditional Chinese.

## Project structure

```text
smart-social-downloader/
├── app.py                         Service entry point
├── setup.bat / start.bat           Install and launch
├── update.bat                     Explicit engine updates
├── Dockerfile / compose.yaml      Experimental Linux amd64 deployment
├── compose.login.yaml             Optional external-key encrypted X sessions
├── .dockerignore / docker/        Build context, snapshot, entry, health and storage tools
├── requirements*.txt              Update ranges / pinned baseline / optional capture
├── README.md / README_CN.md        English / Traditional Chinese homepages
├── CHANGELOG.md                   Application changes
├── SECURITY.md / CONTRIBUTING.md   Private reporting / contribution guide
├── LICENSE / THIRD_PARTY_NOTICES.md
├── ROADMAP.md               Pending work, review findings and acceptance
├── ssdl/                          Python backend
│   ├── version.py                 Single application version
│   ├── app.py                     Composition root
│   ├── app_context.py             Typed state, owned services and lifecycle
│   ├── session_storage.py         DPAPI / external-key / memory session storage
│   ├── local_media.py             Job-scoped, bounded browser media streaming
│   ├── state_writer.py            Immutable snapshots, coalescing and durability
│   ├── database_maintenance.py    SQLite diagnostics, checked backups and VACUUM
│   ├── json_budget.py             Bounded UTF-8 JSON for persistence and IPC
│   ├── media.py                   Stable download entry points
│   ├── media_contracts.py         Shared source identity, paths and errors
│   ├── media_coordinator.py       Routing, generic discovery and manifest reuse
│   ├── media_engines.py           Optional engines and shared defaults
│   ├── video_adapter.py          yt-dlp quality and original stream transfers
│   ├── gallery_adapter.py        gallery-dl configuration and transfers
│   ├── image_adapter.py          Original image bytes and verified history
│   ├── x_account_media.py        X account scan/sync and public-post media
│   ├── browser_media.py           Optional temporary Chrome discovery
│   └── *.py                       API, scheduling, persistence and downloads
├── static/                        Browser UI, styles and locale keys
│   ├── app.js                     Composition, state publishing and refresh
│   ├── settings_controller.js     Settings, drafts, tabs and Rate confirmation
│   ├── diagnostics_controller.js  Environment, health and cache maintenance
│   ├── database_controller.js     SQLite status, confirmation and owned polling
│   ├── jobs_controller.js         List actions, filters, pages and file picker
│   └── controller_lifecycle.js    Owned listeners, timers and cleanup
├── chrome-extension/              Chrome X session connector
├── tools/                         Setup, diagnostics, measurement and packaging
│   ├── package_source.py           Reviewed source-only ZIP
│   ├── check_source_archive.py     Full regression from the extracted ZIP
│   ├── check_workflows.py          Reviewed Action identity / full SHA check
│   ├── check_installation.py       Fresh Windows source/venv acceptance
│   ├── check_dependency_faults.py  Versioned warning / transport regression gate
│   ├── check_docker.py             Isolated Docker image/context acceptance
│   ├── docker_runtime_probe.py     Synthetic FFmpeg/Node probe streamed into the image
│   ├── docker_service_acceptance.py  Disposable Compose storage/network/recovery checks
│   ├── docker_storage_probe.py     Receipt-gated invented history/media and fault injection
│   ├── docker_interaction_acceptance.py  Container login and media HTTP acceptance
│   ├── docker_interaction_probe.py  Invented session/key/media fixture actions
│   ├── measure_persistence.py      Isolated synthetic saves and API latency
│   └── measure_capacity.py         Account scan, IPC and 64 MiB boundary probes
├── docs/                          Usage, architecture and maintenance guides
│   └── images/dashboard-preview.svg  Fictional public illustration
├── tests/                         Importable local regression package
│   ├── helpers/app.py             Shared isolated AppContext fixture
│   ├── helpers/install_runner.py  Receipt-gated installation child
│   ├── helpers/console_runner.py  Isolated Windows Ctrl+C / worker fixture
│   └── test_*.py / frontend.test.cjs  Python / Node suites
├── .github/
│   ├── dependabot.yml             Dependency update proposals
│   ├── ISSUE_TEMPLATE/            Bug, installation, feature and contact forms
│   ├── pull_request_template.md   Change and validation summary
│   └── workflows/                 Windows CI configuration
└── data/ downloads/ .venv/ dist/   Local/generated; excluded from source packages
```

`ssdl` abbreviates **Smart Social Downloader** and names the Python package. Runtime data stays relative to the project root; the media destination can be changed in settings. Importing the entry module does not restore login/history or start workers. Each explicit AppContext owns its queue and services. Full module responsibilities and lifecycle are in [Architecture](docs/ARCHITECTURE.md).

## Updates, reporting and releases

The **application version** appears beneath the app name and in Settings → Diagnostics. Engine versions appear separately in environment diagnostics. `update.bat` updates engines; it does not update application source. See [Maintenance](docs/MAINTENANCE.md) and [CHANGELOG](CHANGELOG.md).

CI Actions use reviewed commit SHAs. Dependabot proposes weekly Actions/Python dependency updates for maintainer review and regression/source-distribution checks. See [dependency maintenance](docs/MAINTENANCE.md#dependency-updates-and-action-pins).

The [first dependency review](docs/DEPENDENCY_ACCEPTANCE.md) adopts pycryptodomex 3.24.1 and retains the compatible browser pins. After updating source with changed dependency pins, stop the service and run `setup.bat` to apply the reviewed baseline, then restart. Updating source or restarting alone does not install changed packages; `update.bat` explicitly updates within the compatibility ranges.

Maintainers can run `python tools/check_dependency_faults.py --report data/dependency-faults.json` after engine/browser updates. CI and extracted-source acceptance also run this [fault-tracking gate](docs/DEPENDENCY_FAULTS.md), recording versions and safe fault categories; new warnings, socket resource leaks or failed transport checks fail acceptance.

Windows CI also checks installation, offline startup/restart and package update/restore in a fresh extracted source and venv. Maintainers can run `python tools/check_installation.py --browser`; it downloads dependencies into disposable storage. See [acceptance scope](docs/INSTALLATION_ACCEPTANCE.md) for the distinction between batch cleanup, graceful app close and remaining real desktop/X checks.

State saves use an owned background writer with immutable snapshots. Critical changes wait for durable writes without holding the queue lock; failed saves remain visible and can be retried in Diagnostics. Maintainers can reproduce synthetic capture/save/API latency measurements with `python tools/measure_persistence.py`. See [persistence performance](docs/PERSISTENCE_PERFORMANCE.md) for results and limits; the command uses disposable history and does not download media or restore login.

Settings → Diagnostics shows saved history size and warns at 80% of its **64 MiB** limit. Capacity failures preserve the last good records and original media; oversized child messages report a specific error and allow subsequent jobs to continue. These limits apply to JSON metadata, not video/image file sizes. For recovery steps, synthetic account/IPC measurements and `python tools/measure_capacity.py --full-limits`, see [capacity and limits](docs/CAPACITY.md).

The same tab offers SQLite capacity checks, consistent local backups and manual compaction. Pause the queue and wait for active downloads to finish before backup/compaction; compaction first creates a checked backup and retains dedup records and original media. Backups stay under `data/database-backups/` and need additional space. See [database maintenance and recovery](docs/DATABASE_MAINTENANCE.md); indexed file storage remains a future feature in [ROADMAP](ROADMAP.md).

After the GitHub repository is published, use the Issue forms for bugs, installation or feature requests. Read [CONTRIBUTING](CONTRIBUTING.md) first and review diagnostics/screenshots before sharing them. Vulnerabilities use the private process in [SECURITY](SECURITY.md).

Source archives include code, docs, public artwork and licenses. They exclude downloaded media, history, cookies and your Python environment. The versioned archive is source code, not an executable installer. The source repository is [Zimkjdv/Smart-Social-Downloader](https://github.com/Zimkjdv/Smart-Social-Downloader). GitHub private reporting activation and a tagged preview Release are still pending.

Maintainers can run `python tools/check_source_archive.py` to build, verify and test the extracted source ZIP using the current installed dependencies. See [test fixtures and source acceptance](docs/SOURCE_TESTING.md) for package boundaries and commands.

## Planned work

Pending reliability fixes, architecture improvements and release acceptance are tracked in [Roadmap](ROADMAP.md). Completed implementation milestones are in [CHANGELOG](CHANGELOG.md).

The experimental [Docker deployment](docs/DOCKER.md) includes Python 3.12/Compose, three persistent volumes, local networking/health checks, [backup/recovery](docs/DOCKER_STORAGE.md) and [host Chrome login/browser file actions](docs/DOCKER_LOGIN.md). Linux sessions use memory by default, with optional external-key encrypted persistence. Actual Linux amd64 builds, the [nine-check runtime gate](docs/DOCKER_ACCEPTANCE.md), [14-stage service/storage gate](docs/DOCKER_SERVICE_ACCEPTANCE.md) and [15-stage invented-login/media HTTP gate](docs/DOCKER_INTERACTION_ACCEPTANCE.md) pass; Linux CI runs the combined gate. Host secret-file permissions, another physical host, actual version migrations and real Chrome/browser interaction remain on the [roadmap](ROADMAP.md#docker-化部署); no prebuilt image is published.

## License

This project's own code and documentation use [MIT](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
