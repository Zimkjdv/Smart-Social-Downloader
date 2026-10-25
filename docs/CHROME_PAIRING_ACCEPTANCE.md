# Ordinary Chrome pairing acceptance

Date: 2026-10-25. Native Windows / Python 3.12 is required. The installed
connector, ordinary browser profile, authorization endpoints, storage and clock
are real. This opt-in procedure is separate from the synthetic
[Pixiv lifecycle suite](PIXIV_AUTH_ACCEPTANCE.md).

## Start an isolated service

```powershell
python tools/check_chrome_pairing.py --port 8877 --allow-real-login --report data/chrome-pairing.json
```

Run from the ordinary Windows user, not a restricted automation account. The
runner first checks native DPAPI with random bytes, copies only allowlisted
public interface/connector files to a temporary application root, binds only
`127.0.0.1` and refuses the default port 8765. Existing production history,
media and saved login are not loaded. Download submission is disabled in this
pairing scope. Cookie values, codes, tickets and refresh tokens are never
included in stdout or the report.

A real connection can save a temporary DPAPI-encrypted session. Keep the runner
open for the entire procedure. Its report records only phase/connected flags,
encrypted-file presence, fixed auth route/status, Chrome version and whether
extension Origin/ID match. Operator notes are distinct from observed HTTP events.
No browser/credential transport is mocked and no additional test HTTP endpoint
is added. `closed` is a lifecycle flag, not a claim that every acceptance case
passed.

## Operator and service steps

| Case | Operator action | Required observation |
| --- | --- | --- |
| Reload/permissions | In ordinary Chrome, reload connector 1.2.0 and approve the requested Pixiv/webRequest permissions if prompted. | Record the version and actual prompt outcome; retain the same public extension ID. |
| Wrong port | Visit `http://127.0.0.1:8877/chrome-connect` with connector still at 8765, then press Connect. | Visible mismatch; the test service receives no extension Cookie submission. |
| Custom port | In the actual extension popup, select 8877 and connect X. | Real prepare and extension POSTs return 200 with matching extension Origin/ID; `status` reports connected/DPAPI/encrypted file. |
| Backend restart | Type `restart`, then `status` in the runner. | A new AppContext restores the temporary saved session without reconnecting. |
| Real ticket expiry | Type `prepare-x`, then leave X pairing alone for at least 600 actual seconds and type `status`. | The waiting ticket expires with failed phase; existing saved login may remain connected. No clock patch or shortened TTL. |
| Cancel/re-pair | Cancel the waiting connection in the isolated dashboard, then use the connector to connect again. | Disconnect succeeds, the pending attempt is gone, and a fresh real extension submission connects. |
| Offline/retry | Type `offline`, try connecting on the existing page, then type `online` and retry. | Browser reports failure while offline; a fresh real prepare/submission succeeds after recovery. |
| Pixiv callback | In the isolated dashboard choose Settings → Pixiv → Connect, finish ordinary-browser login and return. | Real begin/claim/callback succeed, the callback comes from the connector and status becomes connected; verify again after `restart`. |
| Browser lifecycle | Close the paired tab/reload worker or restart Chrome when safe, then start a new attempt. | Record separately which real browser lifecycle was exercised; backend restart is not browser restart. |
| Restore/cleanup | Set the extension back to its original production port, then type `stop`. | Production destination restored; runner exits, temporary encrypted sessions are removed. |

The popup port changes only the connector destination, not the service port.
The web page cannot silently change it. Browser security/website permission
denials must be resolved by the operator; the runner does not install/reload an
extension, alter browser settings or bypass a denied origin. When UI automation
is unavailable, operator actions plus actual server events are recorded as
assisted manual acceptance, not automated UI coverage.

Commands: `status`, `prepare-x`, `offline`, `online`, `restart`, `stop`.
Optional attestations: `note connector-reloaded-1.2.0`, `note permissions-reviewed`,
`note port-configured`, `note chrome-restarted`, `note port-restored`. Only enter
an attestation after the operator actually completes that step. The seven unit
contracts in `tests.test_chrome_pairing` check runner boundaries; they do not
prove real Chrome login.

The runner's final cleanup cancels late saves, shuts its server/application,
removes its own temporary scope and then marks cleanup in the report. It never
logs session contents. Session removal is local; it does not sign out the
operator's Chrome account. After an interrupted process, verify scope cleanup
before treating its lifecycle report as complete.

## Initial partial evidence

Completed assisted-manual observations:

- The operator confirmed reloading 1.2.0 and reported the actual 8877/8765
  mismatch message. Reload/permission UI was operator-driven, not automated.
- Actual ordinary Chrome X prepare and submission returned 200 with matching
  extension Origin/ID. Its reduced User-Agent reports Chrome 155.0.0.0.
- Native DPAPI saved the temporary session; a new backend AppContext restored
  it as connected without another submission.
- The real 600-second X ticket remained waiting at 597.6 seconds, then reported
  failed at 616.6 seconds. The prior valid session stayed connected. No clock or
  TTL was modified. This verifies expiry, not post-expiry re-pairing.
- The service closed normally (exit 0) and its TemporaryDirectory cleanup ran.
  The final runner revision separately passed native startup/restart/cleanup
  with random DPAPI bytes and `temporary_scope_removed: true`, without a browser
  connection. Production service port 8765 was not restarted; the operator
  confirmed restoring the connector destination to 8765 after cleanup.

At the initial checkpoint, Pixiv had received begin requests without claim or
callback. Cancel/re-pair, post-expiry retry, offline recovery and browser
lifecycle cases were still pending. The browser tool then denied port 8877
despite visible allow rules, so the operator deferred these cases while CI was
repaired. This was an external tool-access discrepancy, not a DPAPI diagnosis.
The later follow-up below supersedes that partial native acceptance result.
Initial metadata-only receipts remain ignored `data/chrome-pairing.json` and
`data/chrome-pairing-tool-smoke.json`.

## Follow-up evidence — 2026-10-25

The HTTP browser surface now reaches the isolated service on port 8877. A fresh
native-DPAPI session (`data/chrome-pairing-followup.json`, ignored) observed the
actual dashboard start an X connection, return HTTP 200 from disconnect on
Cancel, then report phase `idle` with no pending session file. The installed
1.2.0 connector was detected on `/chrome-connect`; clicking Connect while it
still targeted 8765 displayed the explicit 8877/8765 mismatch. No extension
Cookie submission reached this isolated session at that point.

The operator selected 8877 and pressed Connect in the installed popup. Real
X prepare/submission returned 200 with matching extension Origin/ID; status
reported connected, native DPAPI and an encrypted session file. This completes
the cancel/re-pair sequence above. With the same pairing page already loaded,
`offline` produced the visible service-unavailable message. After `online`,
the same button obtained a fresh ticket and connected again. No response was
fabricated and no request was retried silently.

Pixiv begin/claim/callback also returned 200. The claim and callback matched
the extension Origin/ID, status became connected/not pending/not busy with a
DPAPI-encrypted file, and the browser automatically returned to the local
`/pixiv-connect#result=connected` success page. The operator completed Pixiv's
external login page because the browser tool's site-safety policy denied that
page. No code, Cookie or refresh token was copied into the receipt. The X
ticket-expiry clock remains unmodified at 600 seconds.


The operator then restarted ordinary Chrome using its normal restart command.
Browser inventory changed from connection 3 to connection 4, with new restored
tab IDs. The real connector was still detected on the restored pairing page;
Pixiv's local success page and server-connected state remained available. This
is assisted observation of an actual browser restart. It does not separately
establish an in-flight OAuth callback across worker suspension. The runner's
`chrome-restarted` note records the operator action, while new browser/tab IDs
and later extension POSTs provide separate observed evidence.


The fresh X ticket was still waiting at 544.2 actual seconds and failed at
601.5 seconds. The saved X session remained connected. After the ordinary
Chrome restart, clicking Connect on a fresh page produced another successful
real prepare/submission and returned phase `connected` at the 625.2-second
status observation. The runner then restarted its backend AppContext without
another browser submission: both X and Pixiv restored as connected with their
DPAPI-encrypted files present; Pixiv had no pending/busy attempt. The real
receipt contains four successful X prepare/submission pairs, one successful
Pixiv begin/claim/callback sequence and the separate cancellation event.


For the worker-idle check, the operator reported the exact Chrome label
`Service Worker (無法使用)` without opening DevTools. A further real Connect
action then returned 200 from both prepare/submission with matching extension
Origin/ID, and X remained connected. This is operator-assisted recovery from
the reported idle/unavailable display, not an instrumented worker-termination
trace. Chrome's [lifecycle documentation](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
explains ordinary idle termination and event-driven revival. In-flight Pixiv
OAuth across worker suspension is still a separate acceptance case.


Finally, the operator restored the connector to 8765. The 8877 page then
reported the explicit mismatch against connector port 8765, confirming the
saved destination. The runner exited 0 with `closed: true` and
`temporary_scope_removed: true`; its temporary encrypted X/Pixiv sessions were
removed. The normal 8765 service was initially not listening; the standard
`tools/manage.py start-background` launcher passed its environment checks and
restored HTTP 200 at the production URL. No acceptance downloads were submitted.

This completes the listed native main-flow cases on this one Windows user /
Chrome 155 / connector 1.2.0 environment with operator assistance. The four real
X exchanges and Pixiv callback are server observations, whereas extension popup,
external login, Chrome restart and worker-display checks include operator
observations. It does not establish clean-install permission prompts, real
Docker login, external OAuth expiration or in-flight OAuth continuity across
worker/browser termination. Those broader cases remain in ROADMAP.
