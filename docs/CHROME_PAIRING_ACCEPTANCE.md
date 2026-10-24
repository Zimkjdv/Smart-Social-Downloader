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

## Current evidence

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

Pixiv received two actual UI begin requests, but no connector claim/callback;
therefore Pixiv auto-return/permission effectiveness is not accepted. Cancel,
post-expiry re-pair, offline/retry, browser/worker restart and Pixiv restore remain
pending in [ROADMAP](../ROADMAP.md). The actual browser steps were manual because
Codex's origin gate denied 8877. Screenshots show both its Browser and Chrome
management rules set Browse to Always allow, but the tool still reports a saved
permission/managed-policy denial. This is an unresolved host permission mismatch,
not evidence of a downloader login or DPAPI defect. A resumed direct Chrome
request after restarting Codex was also denied before loading the page; that
tool access discrepancy remains unresolved; its cause is unconfirmed. The
operator requested deferring the remaining live pairing cases while CI is fixed.
No alternate browser surface,
direct debugging connection or permission bypass was used.

Private metadata-only receipts: ignored `data/chrome-pairing.json` and
`data/chrome-pairing-tool-smoke.json`. Regression/source results and remaining
scope are in [TESTING](TESTING.md). No complete-acceptance claim is made for this
roadmap item.
