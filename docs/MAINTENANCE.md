# Releases and maintenance

This guide prepares a source release. Creating these files does not create a repository, tag or GitHub release. Current acceptance work remains listed in [ROADMAP.md](../ROADMAP.md).

## Four independent versions

| Version | Source | Meaning |
| --- | --- | --- |
| Application | `ssdl/version.py` → `__version__` | This project's UI, queue, API and integrations. |
| Download engines | Installed packages / environment diagnostics | yt-dlp, gallery-dl and FFmpeg; may change after `update.bat`. |
| Chrome connector | `chrome-extension/manifest.json` | Extension permissions, pairing and browser behavior. |
| Saved-state schema | `ssdl/persistence.py` | History format and migration; currently schema 2. |

The current application is **0.1.0-preview.2**, an unpublished prerelease; the original baseline was `0.1.0-preview.1`. Preview APIs may change; document migrations explicitly. Use the single application constant for runtime identity instead of hardcoding copies in HTML/JavaScript. Git tags use `v` plus the same version (for example `v0.1.0-preview.2`). Markdown and changelog references must be updated during release preparation.

The header and Settings → Diagnostics show the application version. Environment diagnostics lists engine versions separately; exported diagnostics includes `app_version`. Status/summary API responses also include `app_version`; the older `version` field retains its historical yt-dlp meaning for compatibility. Changing application identity does not require a state-schema or connector bump.

Get the installed source version without starting the service:

```powershell
python tools/manage.py --version
```

`update.bat` updates engine dependencies, not application source or the extension. To update application source, stop the service and update the files in the same project folder while retaining your local runtime data. After an extension update, reload it at `chrome://extensions`. After source updates, restart the backend and refresh the interface so its reported version matches the running code.

## Preparing a release

- [ ] Review the pending acceptance checks in Roadmap; execute the applicable regression, clean-install and real-browser checks, and record the actual results.
- [ ] Update `ssdl/version.py` for the new release and move the relevant Unreleased entries into a dated CHANGELOG section.
- [ ] Update English / Traditional Chinese README, usage guides and version examples where needed.
- [ ] Review dependency baseline/ranges and third-party license obligations. Engine updates should not silently modify the application version.
- [ ] If the connector changed, decide whether its independent version needs a bump and document reloading/pairing requirements. Retain its identity unless intentionally migrating.
- [ ] Review migration behavior before changing a state schema; keep newer-schema overwrite protection.
- [ ] Build the source-only archive with `tools/package_source.py`; review the explicit file list and contents. Runtime data must remain excluded.
- [ ] Run `tools/check_source_archive.py` to verify exact source bytes/member set/CRC and run the complete regression from the extracted source with current installed dependencies.
- [ ] Inspect the repository's staged files/diff and confirm no personal data is being submitted.
- [ ] Enable private vulnerability reporting and verify the channel described in SECURITY.md.
- [ ] Confirm GitHub CI results. Do not describe configured CI as passing CI.
- [ ] Create a tag matching the application version and publish a **prerelease** for a preview. Summarize known limitations and pending checks in its notes.

These are maintainer actions, not steps every user must perform. The application works locally before repository publication.

## Source archive

```powershell
.\.venv\Scripts\python.exe tools/package_source.py --check
.\.venv\Scripts\python.exe tools/package_source.py
.\.venv\Scripts\python.exe tools/check_source_archive.py
```

Default output: `dist/smart-social-downloader-<application-version>-source.zip`. The containing source directory remains `smart-social-downloader/` so users can preserve the same project root. Use `--output` to select another archive location. Code, documentation, the public illustration, Issue forms and licenses are allowlisted; packaging does not traverse runtime directories. The archive is source code, not an executable installer, and users still run `setup.bat`.

The acceptance command uses disposable output, not the versioned ZIP in `dist/`. It verifies import origins and runs Python/Node suites inside the extraction; CI runs this after checkout regressions. Shared fixtures, recursive code boundaries and clean-OS limitations are documented in [Source testing](SOURCE_TESTING.md).

The demonstration in `docs/images/dashboard-preview.svg` is a hand-built UI illustration with fictional data. It is safe to publish and is not evidence that real-browser acceptance passed. Future screenshots should replace personal accounts, URLs and paths before committing.

## Triage and security

SQLite capacity checks, consistent backups, manual compaction and offline restore steps are documented in [Database maintenance](DATABASE_MAINTENANCE.md). Use Settings → Diagnostics; pause the queue and wait for active downloads before backup/compaction. Backups contain private runtime metadata and are excluded from source archives. No automatic pruning of dedup records or media is performed.

Issue forms ask separately for application, engine and connector versions. Reproduce ordinary reports with synthetic/local data first. When an upstream extractor is responsible, document the relevant engine version and update path. Do not ask users to post cookies or unredacted diagnostic data.

Follow [SECURITY.md](../SECURITY.md) for vulnerabilities. When private reporting is unavailable, the public contact-request form only asks for a private channel; it must not contain reproduction details or secrets. Provide a private channel before asking for those details.

Installation, API protection and publishing privacy are explained further in [RELEASE.md](RELEASE.md).
