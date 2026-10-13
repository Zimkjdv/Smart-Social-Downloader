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

The homepage and usage guides are bilingual. Several technical guides are currently in Traditional Chinese.

## Project structure

```text
smart-social-downloader/
├── app.py                         Service entry point
├── setup.bat / start.bat           Install and launch
├── update.bat                     Explicit engine updates
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
│   ├── jobs_controller.js         List actions, filters, pages and file picker
│   └── controller_lifecycle.js    Owned listeners, timers and cleanup
├── chrome-extension/              Chrome X session connector
├── tools/                         Setup, diagnostics and source packaging
├── docs/                          Usage, architecture and maintenance guides
│   └── images/dashboard-preview.svg  Fictional public illustration
├── tests/                         Local fixtures and regression suites
├── .github/
│   ├── ISSUE_TEMPLATE/            Bug, installation, feature and contact forms
│   ├── pull_request_template.md   Change and validation summary
│   └── workflows/                 Windows CI configuration
└── data/ downloads/ .venv/ dist/   Local/generated; excluded from source packages
```

`ssdl` abbreviates **Smart Social Downloader** and names the Python package. Runtime data stays relative to the project root; the media destination can be changed in settings. Importing the entry module does not restore login/history or start workers. Each explicit AppContext owns its queue and services. Full module responsibilities and lifecycle are in [Architecture](docs/ARCHITECTURE.md).

## Updates, reporting and releases

The **application version** appears beneath the app name and in Settings → Diagnostics. Engine versions appear separately in environment diagnostics. `update.bat` updates engines; it does not update application source. See [Maintenance](docs/MAINTENANCE.md) and [CHANGELOG](CHANGELOG.md).

After the GitHub repository is published, use the Issue forms for bugs, installation or feature requests. Read [CONTRIBUTING](CONTRIBUTING.md) first and review diagnostics/screenshots before sharing them. Vulnerabilities use the private process in [SECURITY](SECURITY.md).

Source archives include code, docs, public artwork and licenses. They exclude downloaded media, history, cookies and your Python environment. The versioned archive is source code, not an executable installer. The source repository is [Zimkjdv/Smart-Social-Downloader](https://github.com/Zimkjdv/Smart-Social-Downloader). GitHub private reporting activation and a tagged preview Release are still pending.

## Planned work

Pending reliability fixes, architecture improvements and release acceptance are tracked in [Roadmap](ROADMAP.md). Completed implementation milestones are in [CHANGELOG](CHANGELOG.md).

Docker deployment is on the [roadmap](ROADMAP.md#docker-化部署): a Python 3.12 image, Compose configuration, persistent data/media, health checks and container-compatible login storage. It is not implemented yet.

## License

This project's own code and documentation use [MIT](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
