# Pixiv author works

Source implementation added on 2026-10-23. A native Windows / ordinary Chrome
authorization completed on 2026-10-24. The same day, real author acceptance for
Hoshirapu (82728784) passed 22 works / 24 files, pause/stop recovery, repeat sync,
missing/changed-page recovery and normal-user Windows restart/session restore.
See the [measured results and remaining limits](PIXIV_ACCEPTANCE.md). Other
authorization, content and Docker/Linux paths remain pending.

## Sign in with Chrome (default)

1. Restart the downloader after updating its source.
2. Install the Chrome connector once, or update its files and reload it at
   `chrome://extensions`. Version **1.2.0** keeps the same extension ID; Chrome
   may ask you to approve the added Pixiv site and `webRequest` permissions.
   The pairing page provides a connector ZIP and setup instructions.
3. Open **Settings → Pixiv sign-in → Connect Pixiv**. Ordinary Windows opens
   Chrome; Docker/Linux provides a loopback pairing link for host Chrome.
4. Complete Pixiv sign-in or verification in that browser tab if prompted.
   The connector captures the callback, the tool exchanges it and saves the
   session, and the browser returns to the connection status page automatically.
   No F12, code copying, or cookie export is required in this default flow.

If Pixiv is already signed in, it may finish without credentials being entered
again. This does not bypass Pixiv's consent, CAPTCHA or other account checks.
The connector's popup must use the same local port as the downloader. Existing
X connection behavior remains available; Pixiv does not use its cookie reader.

The connector observes only the fixed HTTPS Pixiv callback request, only in the
main frame of the tab paired for this attempt. Host access covers `app-api`,
`accounts` and `www.pixiv.net` so Chrome exposes both callback and initiator.
It does not read Pixiv cookies, passwords or Google/Apple sign-in data. A short-
lived pairing ticket is kept in extension **session** storage, bound to the tab
and local origin, and removed on callback/tab close. It is not a refresh token.
The backend alone owns the verifier and refresh token. Claiming and submitting
require the known extension identity and an unexpired ticket; another attempt,
cancellation or service shutdown invalidates the old attempt. An unpaired tab,
subframe or other local port cannot submit it. Codes are never put in local URLs.

The default continues using gallery-dl's PKCE/token protocol; the connector
simplifies the browser handoff. PixivUtil2's documented Cookie configuration also
needs initial setup, so changing the download engine would not remove that step.

### Advanced fallback

Under **Advanced: manual authorization / refresh token**, the previous manual
flow is still available: open authorization, use F12 → Network to copy the
callback URL/code, and complete the connection. Codes typically expire in about
30 seconds; the local attempt expires after ten minutes. Existing refresh tokens
can be validated here too. Manual fallback does not require the connector.

Successful connection retries failed Pixiv jobs, excluding stopped/cancelled
jobs. A failed replacement preserves any previously connected/saved session.
The dashboard polls every two seconds while authorization is pending. The status
page exposes no code, ticket, verifier or refresh token. A browser/connector update
can require reloading the extension and starting a fresh connection.

## Download an author

Select **Pixiv author works** and enter one author per line, for example:

```text
https://www.pixiv.net/users/35692440
35692440
```

Author URLs pasted into **Media URLs** are also recognized automatically.
The author homepage and `/artworks`, `/illustrations`, `/manga` variants are
normalized to the same author identity. The author mode scans all accessible
image works, rather than interpreting a pasted tab URL as a content-type filter.
Single artwork URLs continue through the ordinary media path with the Pixiv session.

The history and active monitor show `Pixiv author · Author name(ID)` after the
scan identifies the author. Traditional Chinese uses `Pixiv 作者 · 作者名(ID)`.
Names persist in job history; older rows with a matching named author folder
can display that name immediately. Before a name is known, the numeric ID is
shown. This presentation does not change the author's URL, archive identity or
downloaded files.

The workflow scans the full visible list before downloading. The monitor shows
works/files discovered, the final total, verified existing pages and pages to
download. Each work needing a transfer passes the existing delay, hourly quota,
platform cooldown, pause/stop and cancellation gates. Scanning itself uses shared
request pacing; there is no fixed author-post limit.

Illustrations and every available manga page are saved from original-image URLs.
Ugoira is saved as individual original frames, preserving their image encoding;
this mode does not produce a playable animation or preserve playback timing as a
separate file. Unavailable originals are not replaced with thumbnails. Deleted,
private, restricted or API-unlisted content may not be available to the session.

## Files and incremental synchronization

```text
downloads/
└── pixiv/
    └── Author name(35692440)/
        ├── <artwork-id>_p0.jpg
        ├── <artwork-id>_p1.png
        └── ...
```

Both single artwork downloads and author synchronization save new files under
`pixiv/Author name(author-id)/`, using the author display name from Pixiv and the
numeric author ID, with no space before the opening parenthesis. Artwork IDs /
page numbers keep filenames stable. Invalid Windows path characters and control
characters become underscores; long display names are shortened without removing
the ID. An unavailable or empty display name uses `Pixiv(author-id)`. The same
portable naming rules apply on Windows and Linux.

Existing verified pages stay at their recorded paths, including older ID-only
folders and folders using an earlier author display name. A naming update or a
Pixiv display-name change does not re-download those pages. No existing directory
is automatically renamed or moved. A partially downloaded work can therefore
reference both old and new folders; missing pages use the current display name.
Manually moving/renaming a file or folder invalidates its original recorded path
and causes a fresh download, as before.

The existing profiles SQLite database uses an independent
`pixiv:<author-id>` namespace scoped to the exact output directory. No second
Pixiv database, standalone downloader or additional Python package is introduced.

Every author sync scans again. A completed author URL is never used as a permanent
whole-account skip. Existing records must match the newly scanned artwork/page
filenames and counts within the same author ID and download root. Each page must
still have its original recorded path, nonzero size and modification time.
Missing, moved, renamed or changed pages are fetched again. Same-name files
without a trusted record are downloaded again.

Successful pages are recorded independently while a work is downloading. A partial
row can supply verified pages after interruption; it is not a completed work
unless it matches the fresh full page list. Stopping or failing retains files and
verified records. A new download directory gets its own verification scope.
Files that are no longer listed by Pixiv are not automatically deleted.

## Credential storage and isolation

- Windows uses the existing DPAPI storage service. The refresh token is in
  `data/pixiv-session.bin`, separate from queue/settings JSON.
- Docker/Linux uses memory by default. The existing optional external key in
  [compose.login.yaml](../compose.login.yaml) also encrypts the Pixiv session.
  Retain that same key for restart/recovery; it is not part of the data backup.
- Saved JSON inside the encrypted envelope identifies the `pixiv` service.
  Unreadable ciphertext remains in place and is not treated as plaintext.
- Tokens/code/verifiers are not returned in public state, diagnostics or argv;
  the parent sends credentials through anonymous stdin to isolated workers.
  Inputs are cleared after submission, settings close or page disposal.
- Token exchange uses a fixed HTTPS Pixiv endpoint, bounded response/time limits,
  disabled proxy use/redirects and the existing public-network policy in a separate
  process. It does not install that process-wide policy in the HTTP server.
- gallery-dl's token cache is in memory for Pixiv. The download adapter removes
  Authorization headers from requests outside Pixiv's API/authentication hosts;
  original-image snapshots use a fresh session and a Pixiv Referer.
- API source checks apply to sign-in/cancel operations. Only the known Chrome
  extension can claim/submit the Pixiv ticket. Its X behavior and identity are
  retained; version 1.2.0 adds explicit Pixiv host / `webRequest` permissions.

## Design references

The implementation uses the already installed [gallery-dl Pixiv extractor](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/pixiv.py)
and its [documented authentication/configuration](https://gdl-org.github.io/docs/configuration.html#extractor.pixiv.refresh-token).
The PKCE handoff follows the protocol used by its
[Pixiv OAuth helper](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/oauth.py).
Dependency licensing remains as described in [third-party notices](../THIRD_PARTY_NOTICES.md).

[PixivUtil2](https://github.com/Nandaka/PixivUtil2) remains a useful design reference:
its [database manager](https://github.com/Nandaka/PixivUtil2/blob/master/PixivDBManager.py)
separates authors, works and manga pages, and its documented missing-file cleanup
reinforces checking disk state. This implementation applies those design ideas
through this project's existing `ProfileArchive` and scheduler. PixivUtil2 is
[BSD-2-Clause](https://github.com/Nandaka/PixivUtil2/blob/master/LICENSE); no package
dependency was added for it.

## Connected status UI

The automatic return page presents a success card and a primary **Back to
downloader** action. The completed sign-in button is hidden. Settings uses the
same compact session-card style as X, with **Reconnect** / **Clear session**
actions, a storage note and an advanced manual fallback. Duplicate success text
and consumed pairing links are removed. Pending/expired states retain their
messages; X errors and cookie-file sign-in remain visible in the shared layout.

## First-transfer initialization repair (2026-10-24)

A reported author sync scanned 45 works / 68 files, then failed with
`'NoneType' object has no attribute 'headers'` before processing the first work.
The local snapshot extractor assigned its Pixiv Referer in the constructor, before
gallery-dl had created its HTTP session. The assignment now runs in `_init`, after
session creation and the existing pacing/Authorization-scope wrappers.

The same failed job was retried through the normal queue. At the recorded
observation it had saved 16 originals across five works, with no error, and was
continuing in the background. This confirms passage through the original failure
boundary; remaining transfers and recovery paths still require their own results.
New job workers load this source change; retry the failed author item to use it.

## Validation remaining

On 2026-10-24, a live dashboard reproduction found that the Pixiv controller's
lifecycle had not been initialized: status text stayed empty and clicking Connect
sent no request. Dashboard composition now initializes it explicitly. Repeating
the same UI action after reloading displayed pending authorization/a pairing link
and the local service returned HTTP 200 for `/api/auth/pixiv/begin`, `/claim` and
`/callback`. The dashboard then showed the Pixiv session connected. This confirms
one native Windows / ordinary Chrome happy path, including automatic return and
session save. It does not confirm other login/restore paths or media downloads.

If an already open page still has an unresponsive button after updating, refresh
that page to load the corrected dashboard scripts, then start the connection again.

No automated tests were added or run for this change. Python/JavaScript syntax and source
consistency checks are separate from functional acceptance. Still required:
other Chrome/Docker authorization paths, expired/revoked credentials, an authorized
author's original multi-page/animation frames, re-sync after additions, page
removal/rename, interruption/restart, rate limits and Windows/Docker credential
restoration. Keep these limitations visible in [ROADMAP](../ROADMAP.md).
