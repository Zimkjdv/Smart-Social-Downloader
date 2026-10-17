# Contributing

Thanks for helping maintain Smart Social Downloader. Read the [README](README.md), [architecture](docs/ARCHITECTURE.md) and [maintenance guide](docs/MAINTENANCE.md) before changing behavior. English and Traditional Chinese reports are welcome.

## Questions, bugs and requests

Use the repository Issue forms for bugs, installation/login problems and feature requests. Copy the **application version** from Settings → Diagnostics, and engine versions from the environment checks. These versions have different meanings. State the job mode and quality preference when reporting downloads, and use a public, non-sensitive example only when needed.

Review diagnostics and screenshots before sharing. Do not attach cookies, private URLs, local databases, browser profiles or your runtime directories. Use [SECURITY.md](SECURITY.md) to report vulnerabilities privately.

## Local work

1. Install Python 3.12 on Windows and run `setup.bat` in your checkout. Installation and CI use this baseline.
2. Run `start.bat`, or use `tools/manage.py` as described in the README.
3. Keep changes focused and describe the behavior, documentation changes and validation performed in the pull request.

Backend code is in `ssdl/`; browser code is in `static/`. Use the existing component boundaries and fixed locale keys. Update both README languages or both usage guides when a user-facing workflow changes. Do not change the Chrome manifest key casually: it determines the extension identity.

When validating a change, prefer existing temporary-file/local-HTTP fixtures and mocked browser APIs. Do not use another person's account, private cookies or real-platform downloads as an unattended test fixture. Validation commands and their limitations are listed in [the usage guide](docs/USAGE.md#tests-and-source-packages). Report checks you did not perform as pending.

Use `tests/helpers/` for shared synthetic fixtures and run Python discovery with `-s tests -t .`. Follow the [fixture and source-distribution guide](docs/SOURCE_TESTING.md) when adding subpackages, support modules or tools. Run `python tools/check_source_archive.py` before publishing source changes; it tests the extracted ZIP with the current installed dependencies.

Installer/launcher changes also require [fresh Windows installation acceptance](docs/INSTALLATION_ACCEPTANCE.md): `python tools/check_installation.py --browser`. This explicit command downloads packages into an owned new venv; small offline harness tests remain in ordinary discovery. Keep actual desktop/login acceptance separate from fixture evidence.

## Pull requests

Dependency updates follow the [maintenance review gate](docs/MAINTENANCE.md#dependency-updates-and-action-pins). Retain complete Action SHAs and release comments; run `python tools/check_workflows.py` before proposing a CI change. New Action identities require review of the explicit allowlist. Dependabot PRs need the same regression/source-distribution checks as other changes.

Include the problem, relevant Issue, change summary, validation results or pending checks, and any compatibility impact on API/state/connector behavior. A successful syntax check is not a passing regression suite. Add a concise entry under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) for notable changes; the maintainer assigns release versions.

Before committing, inspect your staged files and diff. `.gitignore` does not remove already tracked private data. See [release privacy guidance](docs/RELEASE.md).

Contributions to this project's code and documentation are made under its [MIT license](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
