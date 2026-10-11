# Security policy

## Supported versions

This is a preview project. Security fixes target the latest preview/source revision; older revisions do not have a promised backport schedule. The application version is shown in the header and **Settings → Diagnostics**, and included in exported diagnostics. It is separate from yt-dlp, gallery-dl and connector versions.

## Report a vulnerability privately

On the published GitHub repository, use **Security → Advisories → Report a vulnerability** when private vulnerability reporting is enabled. Send a minimal reproduction using synthetic data, the application version, affected component and expected impact. Avoid disclosing exploit details in ordinary public Issues or pull requests.

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

## Maintainer setup before publishing

Enable GitHub private vulnerability reporting for the actual repository, confirm the private report button is available, and nominate a maintainer to receive it. Do not advertise the channel as active before enabling it. Publication and this repository setting have not been performed by adding this file. The release checklist is in [docs/MAINTENANCE.md](docs/MAINTENANCE.md).
