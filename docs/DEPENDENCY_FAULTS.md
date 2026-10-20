# Dependency and transport fault tracking

Implemented **2026-10-21**, for Windows / Python 3.12. This opt-in maintainer gate
also runs in CI and from the extracted source ZIP. It never loads production
history, login data or real browser profiles.

## Run after engine, Python, Playwright or Chrome updates

Install the reviewed core/browser dependencies, Chrome and Node first:

```powershell
.\.venv\Scripts\python.exe tools/check_dependency_faults.py --report data/dependency-faults.json
```

The fixed synthetic suites cover original media, gallery-dl, public-network
policy, HLS/DASH failure/recovery, actual temporary Chrome capture, API source
authorization and bounded local HTTP handling. Two complete HTTP acceptance cases
are repeated **30 times each**: foreign-source/CORS routing and the gated
delayed-body 403 exchange, including subsequent normal operation.
`--http-repeats 1..100` changes the count; failures remain recorded even if a later
attempt succeeds. Missing browser coverage/skips fail the gate.

Garbage collection runs after each case and at suite cleanup. Warning filters,
warning output, unraisable-exception and thread-exception hooks are scoped to this
test process and restored on exit. Production warning filters and APIs stay the
same. This command neither changes packages nor downloads live platform media.

## Results and failure rules

| Result | Exit | Meaning |
| --- | --- | --- |
| `complete: true`, `passed: true` | 0 | All cases passed without skips or unexpected faults; reviewed observations may remain. |
| `complete: true`, `passed: false` | 1 | Test/subtest failure, resource warning, unraisable/thread exception, new warning, skip or overflow needs review. |
| `complete: false` | 2, or 130 on interruption | Infrastructure/report failure or interrupted acceptance; never a successful receipt. |

The optional JSON report is atomically replaced. An incomplete receipt is written
first so interruption cannot leave an old passing result. Output failure returns
nonzero. Reports contain application/Python/OpenSSL/platform identity, seven
package versions, test totals, categorical observations, source-relative locations,
counts and numeric `winerror`/`errno`. They export no raw messages, URLs, bodies,
headers, cookies, absolute paths, subtest parameters or skip reasons.

At most **256 distinct observations** are kept; duplicates are counted. Overflow
fails rather than discarding evidence and passing. `observed_during` identifies
when a warning surfaced, including cleanup; it does **not** identify its allocation
site or prove that test/library caused the leak. Test loading is inside the
observation scope, covering dependency-import warnings too.

## Observation register

| ID | Evidence and disposition | Gate policy |
| --- | --- | --- |
| `ssl_options_deprecated` | Reproduced through gallery-dl X initialization: its browser TLS adapter passes deprecated `OP_NO_TLS*` flags through urllib3. Upstream behavior remains unresolved; TLS verification/protocol settings are unchanged. | Reviewed only for the exact warning text, `urllib3/util/ssl_.py` origin, Python **3.12**, gallery-dl **1.32.16** and urllib3 **2.8.0**. Other text/origin/versions fail for review. |
| `socket_resource_warning` / `resource_warning` | Reproduced **two** unclosed sockets during delegated-HLS missing-fragment cleanup. Allocation traces pointed into requests/urllib3. Closing the engine alone did not remove them; releasing HTTP-error responses did. The fix below removes this reproduction. | No blanket allowlist, including sockets whose representation says `[closed]`. Any occurrence fails. |
| `windows_connection_aborted` | Records **10053** through exception chains. Earlier rejected-body handling is protected by complete 403/recovery repetitions. Synthetic injection verifies classification and retention of failures. | Unexpected occurrences fail; a later success never erases them. Injection does not prove that every native Windows abort has been reproduced or fixed. |
| `python_warning`, other exceptions / unraisables / thread failures | New observations keep safe categories and source locations for a focused rerun. | Fail for diagnosis; do not widen the SSL rule just to obtain green CI. |

See Python's [warning handling](https://docs.python.org/3.12/library/warnings.html)
and [SSL option deprecation](https://docs.python.org/3.12/library/ssl.html#ssl.OP_NO_TLSv1).
Review upstream release/source again after version changes. A reviewed observation
is not a fixed defect or CVE scan. Actual Chrome capture is tested; the report's
Playwright version does not identify the independently installed Chrome build.

## HTTP-error resource ownership fix

`RequestPolicy.wrap_yt_dlp` arranges cleanup for yt-dlp HTTP-error responses.
Extractors can still inspect/read a caught error body. Weak-key registration does
not retain the exception/traceback; a finalizer closes its response when the
exception is released. An engine close hook drains remaining live error responses
at the job boundary. Reusing an exception does not duplicate registration. HTTP
429 keeps immediate close and cooldown behavior.

The gallery adapter explicitly closes every delegated engine it prepared, once,
on success, transfer failure or preparation failure. Borrowed extractor sessions
remain owned by their caller. Cleanup failures emit generic ResourceWarnings
without replacing the transfer error or exposing response data. No third-party
source is patched in place or library-global close hook installed by the app.

Regressions cover readable bodies, release/close paths, weak ownership, multiple
response cleanup, rate-limit errors, borrowed-session ownership and the real
delegated missing-fragment case with forced GC. That case failed with two
ResourceWarnings before the fix and passes without them afterward.

That resource assertion forwards other warning categories to the active warning
handler. An injected UserWarning in the actual stream case must fail the outer
gate, preventing a local warning-capture assertion from hiding new observations.

For a focused developer allocation trace:

```powershell
.\.venv\Scripts\python.exe -X tracemalloc=10 -W always::ResourceWarning -m unittest tests.test_streams.StreamTests.test_gallery_delegated_hls_cannot_complete_with_a_missing_fragment -v
```

Direct unittest output may contain local paths; review/redact it before sharing.
Prefer categorical JSON for public reports. Emission can occur in GC/cookie
handling; inspect allocation evidence before deciding who owns the defect.

## Maintenance integration and limits

Windows CI runs the gate before ordinary regression. Source acceptance runs it
after Python/Node checks in the verified extraction, with the current interpreter's
packages. CI prints bounded JSON into its log. Local `data/` reports are ignored
and excluded from source releases. No package update, rollback, automatic retry
or allowlist edit is performed by the checker.

Keep the [dependency review/recovery process](MAINTENANCE.md#review-regression-and-recovery),
both Windows CI jobs, [third-party notices](../THIRD_PARTY_NOTICES.md) and
release-specific license review. Source packages exclude installed dependencies;
future binary distributions need separate license review. Actual verification is
in [TESTING](TESTING.md); desktop/account/platform/release work stays in
[ROADMAP](../ROADMAP.md).
