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

`update.bat` updates engine dependencies, not application source or the extension. To update application source, stop the service and update the files in the same project folder while retaining your local runtime data. If dependency pins changed, run `setup.bat` to apply the reviewed baseline before restarting; copying source or a normal check-only restart does not install new pins. Use `update.bat` for an explicit update within the compatibility ranges instead. After an extension update, reload it at `chrome://extensions`. After source updates, restart the backend and refresh the interface so its reported version matches the running code.

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
- [ ] Require the fresh source/venv installation job, including real isolated-console Ctrl+C shutdown/recovery, as well as regression checks; record remaining desktop/account acceptance from [Installation acceptance](INSTALLATION_ACCEPTANCE.md) and [Console acceptance](CONSOLE_ACCEPTANCE.md).
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

## Dependency updates and Action pins

CI's three direct Action identities use full commit SHAs with release comments.
These official repository tags/commits were verified on **2026-10-17**:

| Action | Release | Fixed commit |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | [3d3c42e5aac5ba805825da76410c181273ba90b1](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1) |
| `actions/setup-python` | v7.0.0 | [5fda3b95a4ea91299a34e894583c3862153e4b97](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97) |
| `actions/setup-node` | v7.1.0 | [949feb2413d6458794dcd2491c4babbbce0c15c1](https://github.com/actions/setup-node/commit/949feb2413d6458794dcd2491c4babbbce0c15c1) |

Keep the `# vX.Y.Z` comments when updating SHAs. A tag/branch can move; a full SHA
selects the reviewed revision. See GitHub's [secure use reference](https://docs.github.com/en/actions/reference/security/secure-use).

`.github/dependabot.yml` schedules weekly update proposals: Actions on Monday,
Python requirements on Wednesday, both at 06:00 Asia/Taipei. GitHub may start the
checks later. Each ecosystem allows three open version-update PRs; minor/patch
updates are grouped and major changes remain separate. Calendar versions such as
yt-dlp may be classified as major changes. Python proposals cover the requirements
files Dependabot discovers, including the core baseline and optional browser pins.
The configuration adds no automatic approval, merge or deployment. Scheduling
and groups follow the [Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).

### Review, regression and recovery

1. Read upstream release notes/diffs. Verify each Action SHA against its official
   repository/release, check runner/Node requirements and retain the version
   comment. New Action identities require explicit `REVIEWED_ACTIONS` review.
   CI uses `contents: read`, checkout without persisted credentials and ordinary
   `pull_request` checks.
2. Test Python changes in a disposable source copy with a fresh Python 3.12 venv.
   Run `setup.bat` with the proposed lock, verify compatibility with
   `requirements.txt`, and inspect direct/transitive versions and licenses.
   Change compatibility ranges deliberately. Avoid copying a development venv's
   entire freeze into the core baseline. Install the matching optional browser
   requirements with `python tools/manage.py browser-setup`; `update.bat` updates
   core engines only.
3. Require environment/dependency checks, full Python/Node regression and source
   ZIP acceptance. Engine changes need quality, original bytes, HLS/DASH integrity,
   manifest/dedup and cancellation coverage. Chrome/Playwright changes additionally
   need capture deadlines, rejected private targets, header stripping and UI/focus
   coverage. Record actual versions/results and pending account/platform checks.
4. Review and merge manually after all required checks pass. For rollback, stop
   the service, restore previous source/requirements, run `setup.bat` and restore
   matching browser requirements if installed. Setup reinstalls pinned core
   packages but does not remove all extras; use a new venv for a fresh comparison.

```powershell
.\.venv\Scripts\python.exe tools/check_workflows.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe tools/manage.py check
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/check_source_archive.py
```

The offline pin check accepts reviewed `owner/repo@<40 lowercase hex>` references
in literal block-style `uses:` lines, including quoted scalars. Flow, alias,
multiline, dynamic and new Action references fail for review. This conservative
source policy is not a general YAML parser: even a shell string containing
`uses:` needs review. It checks direct reference syntax, not commit provenance,
nested Action dependencies, runner images or known vulnerabilities. Its tool,
regressions and Dependabot configuration ship in the source ZIP.

The [first Python proposal review](DEPENDENCY_ACCEPTANCE.md) accepts pycryptodomex
3.24.1 and adds its minimum to the explicit-update ranges. It defers pyee 14 because
Playwright 1.63.0 requires pyee below 14; that major needs a compatible browser
upgrade. Actions proposal acceptance, repository security settings, SSL deprecations,
closed-socket ResourceWarnings and intermittent Windows 10053 remain in
[ROADMAP](../ROADMAP.md). Update proposals/pinning do not constitute a CVE audit
or establish that these observations are fixed.

## Triage and security

SQLite capacity checks, consistent backups, manual compaction and offline restore steps are documented in [Database maintenance](DATABASE_MAINTENANCE.md). Use Settings → Diagnostics; pause the queue and wait for active downloads before backup/compaction. Backups contain private runtime metadata and are excluded from source archives. No automatic pruning of dedup records or media is performed.

Issue forms ask separately for application, engine and connector versions. Reproduce ordinary reports with synthetic/local data first. When an upstream extractor is responsible, document the relevant engine version and update path. Do not ask users to post cookies or unredacted diagnostic data.

Follow [SECURITY.md](../SECURITY.md) for vulnerabilities. When private reporting is unavailable, the public contact-request form only asks for a private channel; it must not contain reproduction details or secrets. Provide a private channel before asking for those details.

Installation, API protection and publishing privacy are explained further in [RELEASE.md](RELEASE.md).
