# Pixiv author works

Source implementation added on 2026-10-23. The UI and worker integration are
implemented; real Pixiv authorization/download acceptance is still pending.
No real Pixiv credential or author collection was accessed during implementation.

## Sign in

1. Open **Settings → Pixiv sign-in**.
2. Click **Open Pixiv authorization**. Native Windows opens ordinary installed
   Chrome when available. Docker/Linux returns a link for the host browser;
   open the downloader itself in ordinary host Chrome for this workflow.
3. In the authorization tab, open **F12 → Network** before completing sign-in.
4. After signing in, locate the `callback` request and copy its URL or `code`.
   Paste it into **Authorization callback URL or code**, then click
   **Complete connection**. The Pixiv code typically expires in about 30 seconds;
   reopen authorization if needed. The local PKCE attempt expires after ten minutes.
5. Existing Refresh Tokens can be entered under **Advanced**. They are validated
   with Pixiv before replacing the connected session.

The user completes sign-in in the browser. The tool does not collect a password
or automate Google/Apple sign-in. A new attempt, cancellation or shutdown
invalidates the old PKCE verifier; a consumed code cannot be submitted again.
Successful connection retries failed Pixiv jobs, excluding stopped/cancelled jobs.

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
    └── 35692440/
        ├── <artwork-id>_p0.jpg
        ├── <artwork-id>_p1.png
        └── ...
```

Stable author ID / artwork ID / page number naming keeps unrelated authors and
pages separate. The existing profiles SQLite database uses an independent
`pixiv:<author-id>` namespace scoped to the exact output directory. No second
Pixiv database, standalone downloader or additional Python package is introduced.

Every author sync scans again. A completed author URL is never used as a permanent
whole-account skip. Existing records must match the newly scanned names/counts,
and each page must still have the recorded path, nonzero size and modification
time. Missing, moved, renamed or changed pages are fetched again. Same-name files
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
- API source checks apply to sign-in/cancel operations. The X Chrome connector
  retains its existing permissions and behavior.

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

## Validation remaining

No tests were added or run for this change. Python/JavaScript syntax and source
consistency checks are separate from functional acceptance. Still required:
real ordinary-Chrome authorization, expired/revoked credentials, an authorized
author's original multi-page/animation frames, re-sync after additions, page
removal/rename, interruption/restart, rate limits and Windows/Docker credential
restoration. Keep these limitations visible in [ROADMAP](../ROADMAP.md).
