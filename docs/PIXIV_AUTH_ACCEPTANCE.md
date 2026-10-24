# Pixiv authorization lifecycle — 2026-10-25

## Scope and commands

This is automated acceptance with invented OAuth responses, temporary random
32-byte keys, real AES-GCM storage and an isolated local HTTP server. It never
opens Pixiv/Chrome, reads a real browser profile, exchanges a real code or loads
production credentials. The exchange subprocess is replaced at its stdin/stdout
boundary; API guards, PKCE construction, manager state and storage run normally.

```powershell
python -m unittest tests.test_pixiv_auth -v
node --test tests/frontend.test.cjs
python tools/check_docker.py --pixiv --report data/pixiv-auth-docker.json
```

The Python module has **16 cases**: 13 manager/parser/storage cases and three
real-loopback HTTP API cases. Four additional Node cases run the shipped
connector background script against mocked Chrome APIs; all 28 Node cases pass.
The Docker probe now requires **41 cases** (nine paths, 16 recovery, 16 auth),
zero failures/errors/skips and the matching ownership receipt.

## Coverage

| Boundary | Verified behavior |
| --- | --- |
| Pairing and PKCE | Custom-port pairing URL, SHA-256 challenge, one claim, wrong/unclaimed/obsolete tickets rejected before exchange. |
| Expiry/cancellation | Ten-minute ticket expiry, explicit cancellation and late exchange result cannot reconnect; busy state is released. |
| Successful exchange | Code/verifier are sent through stdin, absent from process arguments; only encrypted refresh-token state is saved. |
| Failed exchange/save | Keep the previous usable session and encrypted file, consume the failed attempt and allow a fresh attempt. |
| Persistence | A fresh manager restores the actual AES-GCM blob with its original test key; wrong key/corrupt payload stays disconnected and preserves the original blob. |
| Memory mode | No session file is created or restored. |
| Invalidated credentials | Store an encrypted expired marker without the rejected token; restart stays expired and reauthorization replaces it. An older download failure cannot invalidate a newer token. |
| Invalidation IO failures | Try to remove an unusable record if writing the expired marker fails; if removal also fails, retain current-process expiry and emit a fixed warning rather than terminate the queue. |
| HTTP source guards | Extension identity/origin, exact Host/port, callback field shape and local-only begin/connect/disconnect are enforced before manager mutation. |
| Connector boundaries | Wrong extension identity, foreign page, subframe, wrong configured port and unpaired callback tab make no authorization request or Cookie read. |
| Connector continuation | Mocked worker reload retains session-scoped pairing; callback is submitted once and sensitive callback addresses are replaced with local result pages. |
| Callback recovery | Reject expired, duplicate-code and changed-port callbacks; tab close clears pairing; a failed callback is consumed and a newly paired attempt can succeed. |

## Reproduced defects

1. `invalidate()` previously cleared only the in-memory token. Restart decrypted
   the old blob and displayed connected again. Save a service-scoped encrypted
   `{expired: true}` marker with no token; restore recognizes it before reading
   a refresh token. Keep token-identity checking under the manager lock, so a
   stale failure cannot overwrite a newly connected session.
2. Callback parsing treated port zero as false/absent. Explicitly require
   `parsed.port is None`; an HTTPS callback with `:0` is now rejected.

Both focused regressions failed before their fixes and pass afterwards. No
existing assertion or source guard was removed.

## Isolation and limits

The Linux probe runs non-root with a read-only image, network disabled and only
owned tmpfs. Tests choose memory/AES-GCM host mode explicitly; AES uses a private
temporary key rather than the real Docker secret path. Existing separate Docker
host/secret acceptance covers the fixed secret mount. These tests therefore do
not establish actual Pixiv login or a real Chrome extension installation.

Mocked Chrome worker reload is not proof of Chrome suspension/browser restart
behavior. Native Windows DPAPI with a real account, fresh Chrome permission
prompts, external OAuth expiration and real Docker callback/login remain manual
work in [ROADMAP](../ROADMAP.md).

If both expired-marker writing and file removal are denied, no process can
guarantee durable invalidation without writable storage. The current process
stays expired and logs the fixed warning; the old encrypted record may remain
restorable after restart. Repair permissions and reconnect/clear the session
before restarting. Wrong-key/unreadable originals are preserved, never rewritten
as plaintext or treated as a successful connection.

Results, versions and source-package coverage are recorded in [TESTING](TESTING.md).
Local path-free evidence remains ignored `data/pixiv-auth-docker.json`.
