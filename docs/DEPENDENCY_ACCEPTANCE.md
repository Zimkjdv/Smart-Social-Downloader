# First dependency proposal acceptance

Review date: **2026-10-21**. Application baseline: `88e2852`; Windows / Python 3.12.
Dependency updates are independent of the application and connector versions.

## Proposals actually received

| Proposal | Reviewed head | Scope | Decision |
| --- | --- | --- | --- |
| [Dependabot #1](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/1) | `638f84097ae383e1048d3d3996a851d730f2c7ba` | `requirements.lock.txt`: pycryptodomex 3.24.0 → 3.24.1, one patch in the Python maintenance group | Accept: fresh-environment, regression and recovery verification passed |
| [Dependabot #2](https://github.com/Zimkjdv/Smart-Social-Downloader/pull/2) | `7d1c727e1a8083a494a2dfe12ffa9bbcdfb5ca59` | `requirements-browser.txt`: pyee 13.0.1 → 14.0.0, separate major proposal | Defer: incompatible with the pinned Playwright dependency range |

Both proposals were authored by `dependabot[bot]` in this repository. They confirm
discovery of the core lock and optional browser requirements. Their base preceded
the newer installation/console CI, so old green checks are insufficient for the
current main branch. The reviewed patch is merged onto the current main history;
later changes are retained rather than replacing main with the old proposal tree.

At review, #1's original Windows checks had passed:
[run 38959531157](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/38959531157).
#2 failed during optional-browser installation:
[run 38959546139](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/38959546139).
No Actions update proposal had arrived; the existing six full-SHA references and
offline policy remain unchanged. Future Actions proposals still require review.

## Why the choices differ

Upstream's [3.24.1 release](https://github.com/Legrandin/pycryptodome/releases/tag/v3.24.1)
fixes nonce-dependent timing in ECDSA, EdDSA and DSA signing. This is a dependency
maintenance reason to adopt the patch, not evidence that this downloader's own
paths expose those signing operations. This review is not a full CVE or affected-
usage audit. Upstream [license](https://github.com/Legrandin/pycryptodome/blob/v3.24.1/LICENSE.rst)
and [package metadata](https://pypi.org/pypi/pycryptodomex/3.24.1/json) were reviewed;
the source ZIP still excludes installed third-party packages.

The lock now selects **pycryptodomex 3.24.1**. The explicit update range also adds
`pycryptodomex>=3.24.1,<4`: yt-dlp's default extra merely requests pycryptodomex,
so an existing older satisfying dependency need not be upgraded by pip's ordinary
dependency strategy. Running `setup.bat` restores the reviewed pin; explicit
`update.bat` must also replace an old version. The running production environment
is not modified by this acceptance.

[Playwright 1.63.0 metadata](https://pypi.org/pypi/playwright/1.63.0/json) requires
`pyee>=13,<14`; [pyee 14 metadata](https://pypi.org/pypi/pyee/14.0.0/json) requires
Python >=3.12, which our target already satisfies. The rejection is the Playwright
constraint, not the Python version. Keep **pyee 13.0.1**; do not loosen Playwright's
declared requirements, install pyee 14 with `--no-deps`, or mark its failing CI as
passing. Reconsider with a compatible Playwright/browser-driver update and rerun
capture/UI acceptance together.

## Verification procedure

1. Export the staged current source, excluding untracked deferred research and
   all runtime data; build and verify the allowlisted ZIP.
2. Run the existing [installation acceptance](INSTALLATION_ACCEPTANCE.md) with
   `--browser` in a new source extraction and venv. This includes actual batch
   scripts, exact core/browser pins, offline starts, repair, update/restore,
   graceful lifecycle, real isolated-console Ctrl+C and queue recovery.
3. In that owned fixture only, deliberately install pycryptodomex 3.24.0, confirm
   the version, execute the shipped update script and require 3.24.1 or newer.
   Then run shipped setup and require every baseline pin again, retaining browser
   pins, saved-state bytes and synthetic original/partial media.
4. Resolve #2's exact browser requirements with pip `--dry-run --ignore-installed
   --only-binary=:all:`. Require a dependency conflict identifying Playwright/pyee,
   not a network or missing-release error. Verify the installed distribution
   inventory is unchanged; the incompatible proposal is never installed.
5. Run environment/`pip check`, original-byte/quality/stream/worker/persistence
   and real Chrome regressions from the source ZIP using the **fresh candidate
   interpreter**, not the pre-existing developer venv. Check syntax, local links
   and workflow pins; inspect the actual pushed commit's two Windows CI jobs.

Probe commands use the existing receipt-gated process owner. Any temporary batch
substitution for the deliberate downgrade/dry-run is confined to the fixture and
restored byte-for-byte before source verification. No production history, browser
profile, Cookie or live platform media is used. Actual results are recorded in
[TESTING](TESTING.md) and [CHANGELOG](../CHANGELOG.md).

The completed local run passes **271 Python / 23 Node**, zero skips, using the
fresh interpreter. It verifies **160** source members, the actual
**3.24.0 → update → 3.24.1 → setup** recovery, unchanged state/media and unchanged
package inventory after the rejected pyee resolution. Fresh installation, browser
pins, console recovery, dependency/environment checks and workflow policy also
pass. Local success does not substitute for the integrated commit's Windows CI.

## Maintenance after this review

Keep the documented [review and recovery gate](MAINTENANCE.md#review-regression-and-recovery).
First proposal acceptance does not authorize automatic approval/merge, establish
ongoing platform compatibility, or replace future release-note/license/security
review. New source revisions still need their own CI confirmation.


## Actions proposal #5 and deferred Python candidates — 2026-10-27

The official setup-python v7.1.0 tag resolves to
`6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`, matching #5. Its manifest still uses
Node 24; the current hosted runner supports that runtime. The mirror and
mirror-token options are not configured, permissions remain contents:read and
checkout still disables persisted credentials. This is an Action source/input
review, not a full vulnerability audit of its bundled dependencies.

The original proposal changes three calls in checks.yml. D05 adds two calls in
windows-package.yml; update all five to the same reviewed SHA/version comment.
The two workflows retain 15 full-SHA references, and all seven policy tests pass.
Before merging, require the refreshed head's source/installation/Docker checks
and Windows media/build/frozen/installer acceptance. Actual merge SHA and hosted
CI evidence are recorded in [PR integration](PR_INTEGRATION.md).

Python proposals #3 and #2 stay Draft. An isolated gallery-dl 1.32.17 / Playwright
1.64.0 candidate passes source/frozen checks but has unresolved native GUI matrix
failures; the old dependency baseline also fails a different native startup
case. Do not claim an upgrade cause, fix or stable native acceptance. Their full
observations and resume conditions are in the integration record. Main retains
gallery-dl 1.32.16, Playwright 1.63.0 and pyee 13.0.1. The 1.64.0 candidate permits
pyee 14, but that candidate is not integrated; resolver success is not acceptance.
No production packages, login state or TLS behavior are changed by this review.

Sources: [official release](https://github.com/actions/setup-python/releases/tag/v7.1.0),
[exact manifest](https://github.com/actions/setup-python/blob/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0/action.yml),
[Playwright metadata](https://pypi.org/pypi/playwright/1.64.0/json).
