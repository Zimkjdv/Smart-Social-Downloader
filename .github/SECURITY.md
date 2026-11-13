# Security policy

## Supported versions

This is a preview project. Security fixes target the latest preview/source revision; older revisions do not have a promised backport schedule. The application version is shown in the header and **Settings → Diagnostics**, and included in exported diagnostics. It is separate from yt-dlp, gallery-dl and connector versions.

## Report a vulnerability privately

Use **Security → Advisories → Report a vulnerability** to send the maintainer a private report. Include a minimal reproduction using synthetic data, the application version, affected component and expected impact. Keep exploit details in the private report. [GitHub Security Advisories](https://github.com/Zimkjdv/Smart-Social-Downloader/security/advisories)

If the private-report button is unavailable, use the **Request a private security contact** Issue form. Include only a request for a private channel. Wait for the maintainer to provide that channel before sharing any technical details. Do not post credentials or the vulnerability itself. There is no dedicated security email address configured in this source tree.

For ordinary installation, login or download failures without a vulnerability, use the corresponding Issue form instead.

## What to share

- Application, engine and connector versions, OS/Python version and affected API or component.
- Steps that reproduce the issue with a local fixture or synthetic, non-sensitive input.
- A short description of impact and any available mitigation.
- An optional report from **Settings → Diagnostics → Export diagnostics**, reviewed by you before sending.

Never attach `data/`, `downloads/`, `.venv/`, browser profiles, cookie exports, `x-auth.bin`, state backups, database files or unredacted logs. Screenshots can expose source URLs, account names and filesystem paths even when a diagnostic report is redacted.

## Scope and boundaries

Relevant issues include unintended local API access, credential disclosure, unsafe network target access, unsafe file operations and source-package privacy leaks. The service binds to loopback; source checks do not isolate it from other programs running as the same local user. Windows encryption protects stored X cookies in that user's context, not from programs already able to act as that user.

Platform account restrictions, deleted media and unsupported websites are not by themselves security vulnerabilities. The project cannot promise response times or continuous security monitoring.

## Maintainer release check

Before publishing, confirm that GitHub private vulnerability reporting is enabled, the report button is available and the repository maintainer can receive reports. [Release checklist](../docs/development/MAINTENANCE.md#preparing-a-release)
