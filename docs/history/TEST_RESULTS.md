# Historical test and acceptance results

These records describe their stated dates, commits, dependencies and environments. Earlier pending items and baseline versions are historical observations, not the current release status. Use [the testing guide](../development/TESTING.md) for commands, [acceptance procedures](../testing/README.md) for reproducible gates and [Roadmap](../development/ROADMAP.md) for remaining work.

## Docker source upgrade and timestamp recovery — 2026-10-29

Added the opt-in [two-source upgrade gate](../testing/DOCKER_UPGRADE_ACCEPTANCE.md) and
strengthened the existing service fixture with real ImageHistory, MediaManifest
and X profile SQLite records. All three must pass integrity and file verification
after restart and full backup recovery.

The new native real-tar/media/SQLite regression first failed with restored
`st_mtime_ns = 1793279730454941000` instead of `1700000000123456700`, despite
identical media bytes. The storage helper had saved only integer seconds and
never applied the archived time during restoration. The fix writes an exact
`SSDL.mtime_ns` PAX field, validates it, applies it before fsync/promotion and
refuses a destination that cannot retain it. The regression now passes; malformed,
out-of-range and legacy timestamp handling, and refusal before promotion on
precision loss, are covered too. Legacy archives cannot reconstruct missing
nanoseconds and may invalidate completion reuse under the existing rules.

Focused native verification passes **88 tests in 7.093 seconds**, zero failures
or skips. A separately generated, byte-verified **288-file source ZIP** passed
the same **88 tests in 7.162 seconds** from its isolated extraction with `-E -s`.
This includes Docker contracts, real local tar/SQLite recovery, packaging and
database maintenance; it is not a full project/GUI regression. The pre-existing
untracked research document remains unchanged. Python compilation and the diff
whitespace check with CRLF allowed also pass.

The historical baseline is commit `d22c9a8fbca149527a6624fdfa1c86d905400aec`.
It passes both runtime probes and six upgrade stages but correctly fails
`matching_image_restore`: its original restore helper loses the file times and
the three SQLite lookups fail. The incomplete receipt is retained as
`data/docker-upgrade-original-baseline.json`; this is a recorded incompatibility,
not successful old-version rollback.

A maintained baseline is the same historical source with **only
`docker/storage.py` replaced by this timestamp correction**. Comparing the
allowlisted inputs confirms that is its only changed file. No application
version was changed: both snapshots identify as `0.1.0-preview.2`, and the
receipt records `version_changed: false`.

| Input | SHA-256 |
| --- | --- |
| Unmodified baseline source | `c07d7158eeff95634be48304508e4b42acbdb79487fd87ce210f049049a8340f` |
| Maintained baseline source | `cff71d6d0f0e07bf501244c0ff68fedbb5bdc16729a6b25dbb843c62e6a4e3bd` |
| Current runtime source | `6a1c821904d718bfaf2879de7d18b2cd315877f7960f79073654f39a436b9254` |
| Maintained baseline image | `sha256:e1b45ddd4ca37852de9df3643aa0e9789d80e2dc55b4a05647f580ed5cd6d569` |
| Current image | `sha256:845bdbb2049236a25e3a6c883fe5b31ce4ec92b9d96d4ecbe7d741eb6676088c` |

The `--pixiv --upgrade-from data/docker-upgrade-maintained-d22c9a8` run completed
successfully: nine candidate runtime/context checks, nine baseline runtime/context
checks, all eight source-upgrade/rollback stages and **55 Linux Pixiv cases** with
zero failures/errors/skips. Receipt: `data/docker-upgrade-maintained.json`.
The test changes a setting through the new HTTP server, restarts it to verify
durability, restores the original backup with the maintained old image into fresh
volumes, then verifies the old setting/login/records while the upgraded volumes
and backup remain unchanged.

The final combined command also completed successfully:

```powershell
.\.venv\Scripts\python.exe tools/check_docker.py --host npipe:////./pipe/dockerDesktopLinuxEngine --interaction --pixiv --upgrade-from data/docker-upgrade-maintained-d22c9a8 --report data/docker-upgrade-final.json
```

That receipt records `passed: true` / `complete: true`, all nine candidate runtime
checks, 14 service/storage stages, 15 login/media stages, eight source-upgrade
stages, nine baseline runtime checks and the 55 Linux Pixiv cases. The run took
133 seconds. Host-file-secret/Chrome acceptance is excluded from this successful
command and retains the separate failure below.

An attempted combined `--browser --pixiv --upgrade-from ...` run completed all
14 service/storage stages and all 15 login/media HTTP stages, then failed at
`host_bind_contract` before the Chrome and upgrade stages. The Docker daemon
returned `invalid mount config for type "bind"` / `stat ...: input/output error`
for the newly created private Windows key directory. Independent reproduction
confirmed Compose path validation passes, but the real mount fails in both
system TEMP and an isolated project-data scratch directory. The underlying host
sharing/identity cause is not established; ACL checks were not relaxed and no
Docker/Windows settings were changed. The incomplete attempt is retained in
`data/docker-upgrade-host-attempt.json`. The earlier 2026-10-22 host/browser
results remain historical evidence, not a successful current rerun.

Components in these real Linux runs: Docker Engine **29.8.2**, Compose **5.6.0**,
Python **3.12.15**, Node **22.23.3**, FFmpeg **5.1.9-0+deb12u1**, yt-dlp
**2026.8.19**, gallery-dl **1.32.16**, EJS **0.8.0**, imageio-ffmpeg **0.6.0**,
pycryptodomex **3.24.1**. The native contract runner uses Python **3.12.10**.

Human Chrome/OAuth/login expiry, current host file-secret/browser rerun, distinct
released application versions and another physical host remain unaccepted.
The deployment guide stays experimental. No published image or release is created.

## Pixiv native Windows author checks — 2026-10-24

[Real author acceptance](../testing/PIXIV_ACCEPTANCE.md) covers Hoshirapu (82728784):
22 works / 24 files, original-image decoding, scan-first totals, pause/stop
recovery, verified repeat sync, single missing/mtime-changed page recovery,
normal-user DPAPI/history restart and bilingual named author titles in Chrome.
The private evidence remains outside the source tree. Other authorization,
legacy-folder, Ugoira and Linux/Docker cases remain explicitly pending.

The focused Python command in that report passes **40 tests in 13.729 seconds**;
frontend Node checks pass **24 cases**, zero skips/failures. This is not a claim
that the complete project suite was rerun locally for this change.

## Settings UI CI contract repair — 2026-10-24

The five pushes from `8c84267` through `5c16a46` failed the Windows Python
regression step. Their Docker and fresh Windows installation jobs passed.
The [reported failing run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40017372470)
executed **344 Python tests in 107.026 seconds**, with **one failure and one
error** in `tests/test_browser_ui.py`:

- `test_settings_draft_language_tabs_keyboard_and_focus_return` expected the
  X tab after one ArrowRight from General. The current visible order is
  General → Pixiv → X → Diagnostics; the controller follows that DOM order.
- `test_advanced_cookie_field_is_reachable_from_summary_with_keyboard` used
  `#settings-panel-x summary`, which now matches both login help and advanced
  Cookies. Playwright rejected the ambiguous focus operation in strict mode.

The existing cases now assert the four-tab sequence and target
`#settings-panel-x .advanced-cookies > summary`. Enter/Tab must still reach the
Cookie field and Shift+Tab must return to its summary. Tests remain enabled,
strict mode remains active, and the suite size and production UI are unchanged.
This is a stale test-contract repair, not evidence of a failed download engine.

The [first repair run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40019763517)
for `c23f745` passed all **344 Python tests in 124.166 seconds**, plus Docker and
fresh Windows installation. It then reached the previously skipped Node step:
**7/23 passed, 16 failed**, with two shared fixture startup errors:

- The synthetic dashboard loaded `app.js` without `pixiv_login.js`, causing
  `SSDLPixivLogin is not defined` across 14 existing DOM cases. Load the real
  Pixiv controller before application composition, as the shipped HTML does.
- The Chrome mock lacked `webRequest.onBeforeRequest` and tab/session APIs used
  by connector 1.2.0. Its single message-listener slot also discarded the X
  handler when the Pixiv handler registered. Model the required API surface and
  dispatch messages to all registered listeners, retaining the first response.

These fixture repairs preserve the existing 23 Node cases and X preflight /
source-rejection assertions. They do not weaken the production connector or
constitute new Pixiv OAuth/callback acceptance.

Local checks cover Python/JavaScript syntax and diff whitespace only; no local test suite
or real platform download was run for this repair. Full execution is performed
by the existing push-triggered workflow. Results must be associated with that
exact commit/run; a completed older run does not verify these changes.

## Host Chrome UI and actual playback — 2026-10-22

Local `--browser` acceptance passes **9 + 14 + 15 + 8 + 7 = 53** stages,
`passed: true`, `complete: true`, exit code 0 with owned-resource cleanup.
Run: **21:59:17–22:01:24 Asia/Taipei**. Docker **29.8.2**, Compose **5.6.0**,
installed host Google Chrome **155.0.8059.86**, Windows ACL host mode.
Runtime source SHA-256: `51bb9a8c7201fd5f0a4786351bbeaffcad3d9eb6c4d1ab51c44ce201a6cfcc6a`.
Image: `sha256:4f4bc4d46afec9348e0d8d345991750f7f28e8df687ed7c483d596e344962faa`.
Browser-tool/probe SHA-256: `7b5d2daa889a7c990b101e59c32ff788215b5f364d780c78ad9748f78c869bea`.

The initial gate passes actual PNG and keyboard selection but fails H.264
playback: a native video document's opaque sandbox creates `Origin: null`,
rejected by the API. A single-header probe restores metadata/Range reads.
The minimized shipped-handler Chrome regression fails with the old policy;
a controlled old-header attempt still fails with the corrected driver polling,
then the fixed handler passes decode, advancing playback, seek and end.
Native sandbox documents also block Playwright's in-page polling task;
the acceptance helper polls through bounded driver-side element evaluation.
No script permission is added. Fixed inert inline MIME types retain origin;
SVG/unknown media remain attachment/octet-stream under the opaque sandbox,
HTML is rejected and null/foreign origins remain rejected. See the
[W3C sandbox directive](https://w3c.github.io/webappsec-csp/#directive-sandbox).

The new seven stages pass against the actual Docker entry/UI and a fresh Chrome
context, including page reload/refresh, missing-file status and subsequent image
recovery. All media and sessions are invented. This does not install the real
connector, log into X, exercise sound/other codecs or launch Explorer/player.
The user has deferred physical-host migration. See [procedure and limits](../testing/DOCKER_BROWSER_ACCEPTANCE.md).

Full local checkout: **344 Python tests in 104.152 seconds / 23 Node**, zero skips.
The 16 new cases cover native Chrome decode/play/seek, media MIME/sandbox/null
origin guards, exact browser request origins, dialog/CLI contracts, categorical
failures and bounded driver polling. The initial 30 focused Docker contracts and
subsequent 19 playback/browser/API-source cases also pass.

A repeated final gate includes a bounded fire-and-observe play trigger, so a
stalled `play()` promise cannot hang acceptance. All 53 stages and cleanup pass.
The final helper also passes 19 focused playback/browser/source-policy cases.
A Git-index export excludes the deferred comparison document, verifies **201**
source ZIP members and passes **344 Python tests in 104.323 seconds / 23 Node**,
then **116** dependency-fault cases in **72.078 seconds** with only the previously
reviewed SSL warning and zero skips/unexpected faults.

## Actual host binds and file secrets — 2026-10-22

Local `--host-storage` acceptance passes **9 + 14 + 15 + 8 = 46** stages,
`passed: true`, `complete: true`, exit code 0 and owned-resource cleanup.
Run: **03:14:04–03:15:58 Asia/Taipei**, Docker **29.8.2**, Compose **5.6.0**,
Linux amd64 image, Windows host permission mode `windows_acl`. Runtime source
and image identities match the preceding accepted interaction run. Host-source
SHA-256: `0f6e378e585f3697eed716cae0d2c34345bfdf94008609df5fb97af91a18eec6`.

The actual Compose maintenance commands generate a host key, reject overwrite,
create an offline host archive/checksum and restore it into fresh application
volumes/project. The downloader receives the real file-backed secret as a
read-only bind, restores invented login after restart and recovers encrypted
login/settings/original/partial media from the backup. Complete source/restored
file inventories match before starting the recovery service; the external key
is excluded from the archive and cache is excluded. No real X cookie, browser
profile, platform media or production installation is used.

The first Windows permission implementation reproduces module-autoload failure
under an inherited PowerShell 7 module path, then `Set-Acl` requesting unavailable
`SeSecurityPrivilege`. Restrict the child Windows PowerShell module path and use
.NET access-rule-only persistence. A later strict ACL comparison rejects the
`OWNER RIGHTS` alias after Docker host access. Anonymous checks confirm the
actual directory owner remains the executor; accept that fixed alias only under
the owner match, and regress rejection of an Everyone rule on an empty fixture.
POSIX ownership/mode changes apply only to Linux binds.

Desktop behavior differs from the original no-create expectation: a missing bind
source becomes a private directory, and a missing file secret can become an
empty directory. Record `host_missing_bind: desktop_created_private_directory`
and `host_missing_secret: desktop_directory_key_rejected`; authentication refuses
the invalid key, the original ciphertext/key/media remain intact, and cleanup
removes the fixture directory. Document explicit operator path checks. Ordinary
Linux acceptance requires native missing-source rejection rather than accepting
this Desktop behavior. This matrix still does not transport a backup between two
physical hosts or verify actual application-version migration/real browser login.

See [host gate procedure and scope](../testing/DOCKER_HOST_ACCEPTANCE.md).

Full local checkout regression passes **328 Python tests in 99.972 seconds**,
zero skips; **55** focused Docker/release/workflow/native-action contracts pass
in **4.324 seconds**, and **23 Node tests** pass. The ten new host cases cover
native private ACLs, owner-alias/Everyone behavior, CLI gate ordering, mount
contracts, foreign resources, path/receipt rejection and source inclusion.

Git-index source export excludes the deferred comparison document and verifies
**197** ZIP members. Extracted-source acceptance passes **328 Python tests in
98.881 seconds / 23 Node tests**, then **116** dependency-fault cases in **71.657
seconds**, with only the existing reviewed SSL observation and zero skips or
unexpected faults. **105** Python syntax checks, **460** local documentation
links and eight pinned Action references pass.

The [first pushed host-gate run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/39661649472)
passes all 46 Docker stages on Linux, including POSIX ownership/private modes,
native missing-bind rejection and missing-secret rejection, plus the fresh
Windows installation job. Windows full regression fails only the new synthetic
owner-alias case: it installs an owner-relative ACL without establishing the
current user as owner, although that is the condition under test. Explicitly set
the temporary fixture's owner before applying the alias, avoiding dependence on
the Windows token's default owner. The production ACL owner check is unchanged.

## Docker login and media HTTP — 2026-10-22

The combined `--interaction` gate passes **9 runtime + 14 service + 15 interaction
stages**, exit code 0, `passed: true`, `complete: true`, including cleanup of all
owned resources. Local run: **01:45:13–01:46:36 Asia/Taipei**, Docker Engine
**29.8.2**, Compose **5.6.0**, Linux amd64, Python **3.12.15**, Node **22.23.3**.
The runtime source fingerprint is
`b427feb5b549e69d3a2d4713830f1c173ac16a51b97f1003885ccf76e41f52d5`;
interaction source fingerprint:
`f8dac53261cb70216954e5c8d43e4866e272c3aeadfa566665d45663fc74943e`.

The real service accepts invented connector sessions, rejects wrong/replayed,
cancelled and replaced tickets, writes no memory-mode login, and loses that login
on restart. The shipped generator creates a private 32-byte UID 10001 key and
refuses overwrite. AES-GCM envelopes use fresh nonces and reject corruption;
actual service restarts restore with the matching key, preserve ciphertext under
wrong/missing keys, recover with the original key and remain disconnected after
Disconnect/restart. No real X session or browser profile is read.

The same container serves paged recorded files and original hash-identical PNG
and generated MP4 bytes with HEAD/Range/If-Range and security headers. It rejects
escaping symlinks, stale/traversal selections and untrusted origins. Renaming a
file leaves the completed job intact. Four unread 16 MiB synthetic responses fill
the reader slots; another read receives 503 while health stays available. Closing
the clients releases the slots and restores reads.

Initial local attempt stops at `engine_failed` while Docker Desktop is starting;
a later full run reaches the new login contract. Actual Compose 5.6.0 resolves
the short secret target to `/run/secrets/x_session_key`, so the first strict
basename assertion fails. Accept only the two equivalent normalized target forms,
add rejection regressions for maintenance-key exposure/other target paths, and
repeat the full gate successfully. **43 focused tool/release/workflow contracts
pass in 2.124 seconds**, plus **two native file-action dispatch tests in 1.036
seconds** using a mocked desktop launcher, including stale/deleted selections.

Full checkout regression before the two native additions: **316 Python tests in
98.505 seconds**, zero skips. A Git-index export excludes the deferred comparison
document and verifies **193** source ZIP members; extracted-source acceptance
passes **318 Python tests in 98.257 seconds / 23 Node tests**, followed by **116**
dependency-fault checks in **74.156 seconds** with only the existing reviewed SSL
observation and no unexpected failures. **102** Python syntax checks, **438** local
documentation links and the eight pinned Action references also pass. The only
remaining untracked file is the deliberately deferred comparison document.

This gate resolves the real login override but substitutes a receipt-owned
read-only key volume for the operator's host file-backed secret. Actual host
secret ownership/sharing, real Chrome installation/default/custom port/ten-minute
expiry, real X login, browser codec playback, Windows player/Explorer interaction,
physical-host transport and actual version migration remain unaccepted. Procedure
and fixture differences: [interaction acceptance](../testing/DOCKER_INTERACTION_ACCEPTANCE.md).


## Compose v2/v5 acceptance compatibility — 2026-10-21

The [first pushed Docker job](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/39509618385)
builds the image and passes all nine runtime checks on Docker **28.0.4**, then
fails `compose_contract` before creating service fixtures. Its
[runner manifest](https://github.com/actions/runner-images/blob/ubuntu24/20261018.339/images/ubuntu/Ubuntu2404-Readme.md)
specifies Compose **2.38.2**; local Docker Desktop uses Compose **5.6.0**.

Download the official Compose 2.38.2 Windows executable for a fast daemon-free
reproduction, verify it against its official SHA-256 sidecar
(`ba8f09d3873f7a9755b863ed2013a1276b96fcbbc074c69ff3d3cfbce3e0186f`),
and run the actual `config --format json` output through the service contract.
It fails in **0.36 seconds** with `KeyError: create_host_path`; a one-field unit
reproduction fails in **0.001 seconds**. Changing only the source boolean shows
that false serializes as `bind: {}`, while true remains
`bind: {create_host_path: true}`. An attempted absent-field variant left an invalid
empty YAML bind node and is discarded as a different failure.

Read an omitted JSON field as false and continue rejecting explicit true or a
non-boolean value. The actual official 2.38.2 configuration loop now passes;
**37 focused tests pass in 1.570 seconds**, including the formerly failing case
and its unsafe-true rejection. A repeated full local Docker gate passes **9 + 14**
stages from **06:45:12–06:46:03 Asia/Taipei**, with Compose **5.6.0** recorded in
the safe receipt. Its service-source SHA-256 is
`cdbb54bcd3041e4372c27c43ec850fdb069e0e6f97acf5ea5eefa615bc4e71f6`;
runtime-source/gate/probe/image identities match the preceding accepted run.
No operator source configuration, application data or bind permission policy is
changed by this compatibility fix. The downloaded diagnostic binary and captured
model remain under ignored local data, outside source packages and commits.

Before this one-case addition, the final Git-index source export verifies **188**
members and passes **309 Python tests in 96.431 seconds / 23 Node tests**, then
**116** dependency-fault checks in **72.969 seconds**, with only the existing
reviewed SSL observation. The common Docker fake is shipped under
`tests/helpers/docker.py`; the deferred comparison document is absent. **98**
Python syntax checks and **418** local documentation links pass. The added
regression raises the full suite to **310** cases; remote rerun results are
verified separately from these local results.

## Docker Compose storage/network and recovery — 2026-10-21

**Real Docker acceptance passes all 9 runtime + 14 service stages**, including a
repeat after the final ownership/startup-probe checks. The final run started at
**06:27:53 Asia/Taipei** and finished at **06:28:43**, exit code 0,
`passed: true`, `complete: true`; default publication used matching host/container
port **8765**, and a matching free custom port also passed. Docker Engine
**29.8.2**, Linux amd64, Python **3.12.15**, Node **22.23.3**, FFmpeg
**5.1.9-0+deb12u1** and the pinned package versions match the runtime record below.

The actual Compose entry starts on fresh volumes, exits cleanly and restarts with
invented paused history/settings, a completed media file and a partial download.
The real health probe fails before startup and passes when ready. Revoking data
write access causes an actual failed save, HTTP 503 and Docker `unhealthy` without
restarting the process; restoring access/save returns readiness. Foreign
Host/Origin, cross-site and wrong-port origins are refused, as is an output path
outside the media root. A running writer excludes maintenance; an unwritable
existing volume refuses startup and works again after permissions are repaired.

The real offline backup preserves all source data/media bytes and excludes cache
and lock files. A corrupted archive leaves fresh restore targets empty. An actual
restore child exits abruptly with code 75 after first-volume promotion; its marker
and staging state remain, and ordinary startup refuses them. The good archive and
sidecar are copied through host temporary storage into another backup volume,
restored into independent fresh volumes and compared with the entire offline file
inventory. A second restore refuses nonempty destinations. A distinct label-only
upgrade image starts on the original volumes, then the recovery project starts
with the exact retained image ID and verified original history/media. All owned
containers, networks and fixture volumes are cleaned.

| Accepted input/output | SHA-256 |
| --- | --- |
| Public runtime source inventory | `b427feb5b549e69d3a2d4713830f1c173ac16a51b97f1003885ccf76e41f52d5` |
| Host acceptance gate | `358a8f65ad5366ecfbb247cd68dc6ed9b257fe6ea2dc89b1c69c4ff54d384345` |
| Storage probe + service gate + Compose source | `435349140db8564aedd119351882e4a8adfd0f8397d4cc568b38af209027bb0d` |
| Resulting test image | `aa9534766ffd28f15e273d4fd5b34a26821b6d1a91b8321e9bd7717749d61466` |

**Complete local regression: 309 Python tests in 97.233 seconds / 23 Node tests,
zero skips.** The focused 36 gate/release/workflow tests pass in 1.579 seconds,
including ten new service contracts. The current checkout allowlist validates
**189 files**, including a deferred untracked comparison document; the Git-index
source export omits that document. The Action policy validates eight reviewed full-SHA references.
No installed package or production history/login/media was used or changed.

The first service attempt found that an internal-only fixture bridge produced no
usable published bindings on this engine, then exposed separate `__main__` and
package exception identities leaking a traceback. Use the operator recipe's
ordinary dedicated bridge and unify gate exception identity; unexpected fixture
errors now retain categorical failed receipts. Helpers/maintenance remain
network-disabled and the invented queue remains paused. A first unit fixture
mocked `Path.stat` globally and failed before reaching its intended callback;
using actual public source with fake Docker responses proves the intended service
failure path without launching a container.

This proves local named-volume operations and same-engine archive transport to
independent projects. It does **not** prove another physical host, actual
cross-version database migration, operator host-bind permissions, real X/Chrome
pairing, browser playback or active external-platform download shutdown. Those
remain in [ROADMAP](../development/ROADMAP.md#docker-化部署). Fixture substitutions and commands
are in [service acceptance](../testing/DOCKER_SERVICE_ACCEPTANCE.md). Remote CI results are
separate from these local results.

## Docker FFmpeg, JavaScript and context acceptance — 2026-10-21

**Actual Docker acceptance passes all nine checks**, twice: an initial real build
and a cached repeat with the final gate. Environment: Docker Desktop Engine
**29.8.2**, Linux amd64; Python **3.12.15**, Node **22.23.3**, FFmpeg
**5.1.9-0+deb12u1**, yt-dlp **2026.8.19**, gallery-dl **1.32.16**, yt-dlp-ejs
**0.8.0**, imageio-ffmpeg **0.6.0**, pycryptodomex **3.24.1**. The final repeat
started at **06:15:09 Asia/Taipei** and finished at **06:15:15**, with exit code 0,
`passed: true`, `complete: true`. Docker Desktop was installed off PATH; its
initial `DockerDesktop/Wsl/CommandTimedOut` cleared after startup without changing
Windows features or restarting WSL/services.

The real build-context audit rejects synthetic private-state inputs; the actual
runtime probe runs without network, application volumes, real media or sessions.
It checks UID/read-only isolation, dependency installation/compatibility, the
yt-dlp Node provider and bundled EJS hashes, stream-copy audio/video packet
integrity, generated JPEG output, application image contents and the absence of
Chrome/Playwright in the default image. All nine categorical stages are present
in the ignored local `data/docker-runtime.json` receipt. Temporary test containers
and image tags are cleaned; build caches may remain.

| Accepted input/output | SHA-256 |
| --- | --- |
| Public runtime source inventory | `b427feb5b549e69d3a2d4713830f1c173ac16a51b97f1003885ccf76e41f52d5` |
| Host acceptance gate | `442e6661f5c4787b7cca3f708d4a7314af53d27d760e7b98ab966824141f16d8` |
| Stdin runtime probe | `1b17657347c720b37df43b6dfc3d55a6dde40d2afa8d29e7e37e6fc18415931c` |
| Resulting test image | `aa9534766ffd28f15e273d4fd5b34a26821b6d1a91b8321e9bd7717749d61466` |

That acceptance ran against uncommitted Docker implementation work; these
fingerprints identify its inputs, rather than claiming a released Git revision.

**26 focused Python tests pass in 1.158 seconds, zero skips:** 10 new Docker-gate
contracts, nine source-release cases and seven workflow-policy cases. They cover
source boundaries/reparse rejection, synthetic context assertions, fixed base
identities, strict ordered receipts and versions, stale-success replacement,
engine/build/runtime failures, timeouts, isolation arguments and owned cleanup.
The earlier focused command had one nonexistent test-module name, then exposed
the workflow test's old six-reference expectation; correcting the module name
and updating that expectation to eight leaves the final run green. Fake Docker
contracts are separate from the actual container evidence above.

The source allowlist validates **184 files**; Python syntax for the new probe and
the eight-reference Action policy pass. No complete Windows/Node regression or
extracted-source suite was rerun for this milestone. The new Linux CI workflow is
prepared locally, **not yet run on GitHub**. No prebuilt image was published.

This is runtime acceptance, **not** a running Compose-service, persistence,
backup/recovery, network/Origin, real-platform, host-Chrome login or browser
playback acceptance. Those remain in [ROADMAP](../development/ROADMAP.md#docker-化部署).
The native service, installed production packages, history and login were not
used or changed. Commands and limits are in [Docker acceptance](../testing/DOCKER_ACCEPTANCE.md).

## Dependency fault tracking and HTTP-error resource cleanup — 2026-10-21

**289 Python tests pass in 94.336 seconds / 23 Node tests pass; zero skips**, from the verified source ZIP. The same extraction then passes the new **116-case** gate in **69.609 seconds**, retaining only the reviewed SSL observation and no resource warnings/unexpected faults. The allowlist contains **164** source members; exact source bytes/CRC, **84** Python syntax checks, **335** local documentation links, `pip check` and the six-reference workflow policy pass. Deferred Downvid research stays outside the source/export/commit. The pushed revision's two Windows CI jobs are verified separately.

The new gate's first complete run executed **116 cases** with no test failures/skips but correctly failed on **two socket ResourceWarnings** during delegated-HLS missing-fragment cleanup. A one-case forced-GC/tracemalloc reproduction attributed allocations to requests/urllib3; closing the delegated engine alone retained both warnings, while closing released HTTP-error responses removed them. The permanent actual-stream regression failed before the fix and passes afterward, preserving missing-fragment failure and request-count assertions.

The fixed gate passes **116 cases in 70.078 seconds**, including 30 repetitions of each foreign-source/CORS and delayed-body 403/recovery acceptance case. It records one precisely reviewed SSL deprecation, with no ResourceWarnings or unexpected faults. Local environment: Python **3.12.10**, OpenSSL **3.0.16**, yt-dlp **2026.8.19**, gallery-dl **1.32.16**, requests **2.34.2**, urllib3 **2.8.0**, Playwright **1.63.0**, pyee **13.0.1**; the existing local pycryptodomex remains **3.24.0**. No production package update was performed; CI installs the reviewed **3.24.1** pin independently.

**27 focused cases pass**, including 13 tracking contracts, five response/engine-ownership contracts and nine source-release contracts. A real owned unclosed socket proves the gate fails; synthetic wrapped 10053, a later success after a failure, subtest failure, skipped coverage, background/unraisable exceptions, import warnings, overflow, stale-report interruption and hook restoration are covered. A final one-case UserWarning injection exposed nested stream warning capture hiding a new observation; forwarding non-resource categories fixes it and the added real-case regression requires the outer gate to fail. Response tests preserve readable bodies and weak error ownership, close each response/engine once, continue other response cleanup after a close failure, retain rate limiting and leave borrowed sessions open.

The SSL observation remains upstream behavior, not a fixed TLS defect. Numeric 10053 injection verifies classification; complete local exchanges protect the earlier refusal cleanup fix, without claiming all native Windows aborts are fixed. Reports exclude raw messages, URLs/headers, absolute paths and subtest/skip text. No production history/Cookie, real X session or external platform media was used. See [Dependency faults](../development/DEPENDENCY_FAULTS.md) for report/exit rules and upgrade procedure.

## First dependency proposal acceptance — 2026-10-21

**271 Python tests passed in 92.336 seconds / 23 Node tests passed; zero skips.** The full suite ran from a verified source ZIP using the interpreter from the newly installed candidate venv, with pycryptodomex **3.24.1**, Playwright **1.63.0** and pyee **13.0.1**. Existing original-byte, quality-selection, HLS/DASH missing-fragment, deduplication, worker, persistence, API and actual Chrome fixture cases remained enabled. The verified source contains **160** allowlisted members; **81** Python syntax checks, local documentation links, `pip check`, environment diagnostics and the six-reference offline Action policy pass.

The real Windows/Python **3.12.10** fresh-source/venv acceptance passes setup, offline batch startup, graceful restart, missing-marker repair, explicit update, exact-baseline restoration, optional browser installation, real isolated-console Ctrl+C with idle/active/restored queues and invalid-port rejection. Update selected gallery-dl **1.32.17**, then setup restored **1.32.16**; the separate IDNA **3.10 → 3.20** restoration probe also passed. This proves current-machine fresh-source/venv behavior, not a factory Windows desktop or real account/platform acceptance.

Additional one-off probes use only that receipt-gated owned fixture: deliberately install pycryptodomex **3.24.0**, confirm its inventory, run the shipped `update.bat` and require **3.24.1**, then run shipped `setup.bat` and verify every core/browser pin. Saved-state, synthetic original and partial-media hashes remain unchanged. Temporary fixture batch substitutions are restored byte-for-byte before source verification; the running production venv is not updated.

Resolve the exact proposed pyee **14.0.0** browser requirements with pip `--dry-run --ignore-installed --only-binary=:all:`. It fails with `ResolutionImpossible`, identifying Playwright's `pyee>=13,<14` constraint; the complete installed distribution inventory is unchanged. This agrees with proposal #2's original failing Windows job. Proposal #1's original green job predates the new installation/console checks, so the integrated revision requires both current Windows CI jobs after push. Review decisions, upstream sources and future Actions/browser gates are in [Dependency acceptance](DEPENDENCY_ACCEPTANCE.md).

Ignored local logs and JSON reports retain actual versions/results. Deferred Downvid research is excluded from the staged export, source ZIP and commit. No production state, Cookie/profile, live platform download, real X pairing or full CVE scan is part of this acceptance; remaining work stays in [ROADMAP](../development/ROADMAP.md).

## Windows console shutdown and recovery — 2026-10-21

**271 Python tests passed in 94.018 seconds / 23 Node tests passed from the extracted staged-source ZIP; zero skips.** Thirteen new offline console cases cover empty/overflow/shared console membership, admission before child creation, non-inheritable SIGINT handling, wrong receipts/unknown members, SYNCHRONIZE handle cleanup and PID reuse protection, refused native events, entry-factory restoration, hidden/new-console flags and explicit HTTP 201 expectations. The final focused installation/console run passed 26 cases. An earlier checkout run passed 270 Python tests in 94.311 seconds / 23 Node tests before the final membership-contract case was added; the full extracted run includes that case.

Real installation acceptance from the clean staged source also passed on Windows / Python 3.12.10, with **159** allowlisted source members and a new venv. It generated real CTRL_C_EVENTs in three owned hidden-console launches: idle, active synthetic worker plus pending job, and restored paused queue. The shipped entry, server, AppContext, scheduler, writer and worker supervision remained real; only platform transfer used a synthetic pipe-speaking worker/helper. Normal exit, closed writer/services, reusable port, terminated worker/helper handles, preserved original/partial bytes and exact restored IDs/attempts/pause/hourly limit/one consumed quota slot were checked before fallback outer Job Object cleanup.

The same run retained setup/offline startup, missing-marker repair, update/baseline restoration, optional browser pins and invalid-port rejection. The isolated update selected gallery-dl **1.32.17**, then setup restored the pinned **1.32.16** baseline; the IDNA **3.10 → 3.20** replacement probe also passed. The first sandboxed setup could not reach public PyPI (Windows 10013); the permitted-network rerun and final clean-source run passed. A blocked download was not classified as a missing package release or a passing test. Production packages/state/Cookies were not changed.

The clean source ZIP's member set/source bytes/CRC, 81 Python syntax checks, local documentation links, `pip check` and the six-reference workflow policy passed. Deferred Downvid research stayed outside the staged source/export and commit. This proves automated console-event handling on the current Windows environment, not factory Windows installation, physical keyboard/batch confirmation prompts, repeated interruption during native disk I/O or real account/media compatibility. See [Console acceptance](../testing/CONSOLE_ACCEPTANCE.md) and [ROADMAP](../development/ROADMAP.md).

## Windows installation acceptance and transport follow-up — 2026-10-17

**258 Python tests passed in 92.167 seconds; 23 Node tests passed; zero skips.** The focused HTTP/source/environment/installation run passed 38 cases. Thirteen new small installation cases cover isolated environment/pin parsing, receipt/admission guards, owned group failure/ordering, bounded command errors, foreign-service rejection, exclusive port reuse, setup/update markers and the check-only start route. One environment case requires DEVNULL stdin. Two new HTTP cases bound rejected-body cleanup and forbid draining oversized/ambiguous input; the existing gated late-body test now asserts exact discarded bytes.

An earlier 256-case run failed on the existing foreign-Origin POST with Windows 10053 before reading 403. Keep that failure as evidence; add strict framed/body-budget cleanup after emitting the response rather than suppressing transport errors. The final full run passes. An installed fixture also reproduced `pip check` hanging on inherited control stdin; tracing identified it and DEVNULL fixes the actual environment probe. Initial closed-port probes timed out in this Windows environment, so acceptance now requires successful exclusive rebind instead. Failed development runs are not counted as passing verification.

The real opt-in installer executes shipped batch files in an extracted source and brand-new venv, with independent graceful lifecycle and package restoration probes. This uses synthetic state/media, public dependency downloads, a custom loopback port and ordinary installed runtimes. Production history/Cookie/profile access, service restart, actual X sign-in and live platform media are outside the run. See [Installation acceptance](../testing/INSTALLATION_ACCEPTANCE.md) for actual phases, ownership and the fresh-source/venv versus bare-desktop boundary.

The actual installation run passed on Windows / Python 3.12.10 with all 156 source members, every core baseline pin, optional browser pins, offline start, missing-marker repair, settings preservation, graceful installed lifecycle and invalid-port rejection. `update.bat` resolved to the same current core versions as the baseline; the separate IDNA 3.10 → 3.20 probe demonstrated a real package replacement during restoration. Final base-interpreter admission with site startup disabled (`-I -S`) also passed a real batch-child/owned-cleanup smoke check.

The extracted-source gate passed **258 Python tests in 92.433 seconds / 23 Node tests**, zero skips. Thirty repetitions each of the complete foreign-Origin/CORS and delayed-body refusal cases passed (60 checks in 2.072 seconds); this is bounded regression evidence, not a guarantee against every Windows 10053. The final focused rerun passed all 38 cases, `pip check` and the six-reference workflow policy passed, and 79 Python syntax checks/local Markdown links validated. Source ZIP members, source bytes and CRC were verified. Successful installation logs/report remain ignored local evidence rather than source-package contents.

## Dependency and CI maintenance — 2026-10-17

**242 Python tests passed in 92.931 seconds; 23 Node tests passed; zero skips.** Windows / Python 3.12.10. The source allowlist validates **152 files**. Seven new cases cover reviewed full SHA/quoted scalars; mutable, abbreviated, dynamic, local, Docker and unknown references; flow/multiline/alias syntax; comment/error handling; both workflow extensions and canonical roots; missing workflows/CLI failure; and shipped policy/configuration. The focused policy/release run passed all 16 cases.

Official release tags and commit identities were checked separately through the GitHub API. The offline gate does not query GitHub, validate general YAML, authenticate a commit's provenance or scan for CVEs. Existing browser/capture, quality/streaming, IPC, persistence and SQLite regressions remain enabled. Update review and recovery are documented in [Maintenance](../development/MAINTENANCE.md#dependency-updates-and-action-pins); Dependabot's first proposals and remaining real Windows/account/platform acceptance stay in [ROADMAP](../development/ROADMAP.md).

The extracted-source gate also passes **242 Python tests in 93.354 seconds / 23 Node tests**, zero skips, with all 152 members/CRC/source bytes verified. Offline policy, `pip check`, 76 Python syntax checks and local documentation links pass. The workflow now runs the offline pin gate before Node setup and retains the existing checkout and extracted-distribution regressions. No production service restart, personal history/Cookie read or live platform download was used.

## N08 shared fixtures and source distribution — 2026-10-16

**234 Python tests passed in 92.591 seconds; 23 Node tests passed; zero skips.** Windows / Python 3.12.10 / Node 24.19.0. The reviewed source allowlist validates **149 files**, including the test package, shared helpers and extracted-source acceptance tool. Eleven new cases cover independent fixture contexts, failure/worker/override cleanup, nested code and helper packaging, reparse parents, isolated nested discovery, unexpected/duplicate/changed archive contents, failed child commands and refused POST body/response/connection behavior. Existing Chrome, capture, HLS/DASH, IPC, quality, writer and SQLite cases remain enabled.

The extracted distribution passed the complete **234 Python tests in 91.829 seconds / 23 Node tests**, with zero skips. The command verified all 149 members, CRC and source bytes, checked import origins and ran both suites from the extraction. The first launch was blocked by a full C drive before execution; the successful run used an owned temporary directory on D. It uses current installed dependencies rather than a fresh OS or venv. CI now runs the same gate after checkout tests. Python syntax (74 source files), local Markdown links and `pip check` also pass. See [Testing guide](../development/TESTING.md) for boundaries, fixture ownership, commands and limitations.

CI follow-up: the first GitHub run on `464cc7e` failed four new release checks because Windows TEMP used the `RUNNER~1` short path while the packager returned canonical paths. Canonicalize both the release fixture root and the root passed to archive verification; add a noncanonical-root regression. The focused nine release checks pass, and the final extracted-source run passes **235 Python tests in 91.070 seconds / 23 Node tests**, zero skips. Source authorization, archive membership and reparse checks remain enforced. A new Windows CI run verifies the follow-up separately.

The gated 64 KB late-body request and full/partial/disconnected unauthorized requests pass without parsing the rejected JSON, mutating state or reading private summaries. Previous Windows 10053 remains unreproduced; no assertion suppresses a failed complete 403 exchange and production HTTP source/body handling is unchanged. No real Cookie/history read, production restart or live platform download was performed. N08 is complete; installation, real-account/platform/release acceptance and optional features remain in [ROADMAP](../development/ROADMAP.md).

## N07 SQLite diagnostics, backup and compaction — 2026-10-15

**223 Python tests passed in 90.368 seconds; 23 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates **143 files**, including the owned database service, UI controller, real SQLite acceptance module and [database maintenance guide](../reference/DATABASE_MAINTENANCE.md). Existing real Chrome/capture, streaming, quality, source policy, writer and capacity cases remain enabled. No production service restart, personal database/Cookie access or live platform media download occurred.

Nineteen new Python cases verify passive/missing-database behavior; physical size/freelist/count diagnostics without row/path leaks; complete pre-compaction backup and exact row/schema/media preservation; moved-file refetch behavior through all three real dedup stores; committed WAL snapshots and retained old backups; failure before VACUUM without partial publication; corrupt/unknown/locked databases; reparse paths and orphan journals; deadline/owned shutdown; partial compaction; WAL reader deferral; Unicode/space/URI characters in roots; Host/Origin and strict confirmation contracts; pause/active/busy/closing responses; and scheduler admission fencing. SQLite tests use real temporary files and native SQLite backup/VACUUM. Fault injection covers fsync, per-database failure and cancellation; no host-specific speed threshold is used.

Three new Node cases cover one confirmed submission, cancellation, concurrent clicks, report contracts, language switching, stale revisions, active-download button guards, health warnings and disposed late responses. A new real headless Chrome case opens the compaction dialog from Settings → Diagnostics, cancels with Escape and returns focus to its trigger, submits exactly one `{action: compact, confirmed: true}` request, and checks the translated backup result. A synthetic screenshot was inspected for the settings layout; it is ignored runtime output, not a public screenshot of a real account.

The source ZIP was built and each allowlisted entry and CRC checked against current sources. The maintenance service never deletes media or prunes dedup rows; backups do not bypass original-path verification. SQLite/index evaluation is complete in [DATABASE_MAINTENANCE](../reference/DATABASE_MAINTENANCE.md); actual indexed storage remains a future feature and N08 is the next P2 item in [ROADMAP](../development/ROADMAP.md).

## N07 account scan, IPC and state capacity — 2026-10-15

**203 Python tests passed in 89.881 seconds; 20 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates **139 files**, including `json_budget.py`, `measure_capacity.py`, the capacity acceptance module and [CAPACITY](../reference/CAPACITY.md). Existing real Chrome UI/capture, stream integrity, worker, source policy, quality, lifecycle and writer suites remain enabled.

Eleven new capacity cases cover byte-exact UTF-8/Unicode/escaping, early budget rejection, invalid JSON producing no IPC bytes, primary/backup preservation and smaller retries, oversized read/write protection, growth after stat, warning after save/restore, writer error preservation and recovery, real temporary account plans with deterministic cached-progress throttling, codec/scaled boundary probes, cleanup and source-package inclusion. A new runtime case exercises all four production child terminal paths (oversized result/progress/error/selection) through real pipes with a scaled budget, then runs another job. Two new Node cases cover capacity contracts, MiB size/warnings, save blocking/recovery and English translation. Existing queue tests also cover a capacity failure followed by another queued item.

The first full run caught an outdated measurement assertion: primary preservation now validates and copies the same bounded bytes, so `_read` is no longer called twice. Update attribution to `_read_contents` (two reads) and `json_encode_bounded`, retaining three schema validations/two atomic writes/two fsyncs. The corrected full run passed. No speed thresholds are asserted in CI.

After regressions finished, actual **64 MiB / limit + 1 byte** probes accepted exact-size state/IPC, rejected over-limit data, checked unchanged primary/backup content fingerprints and validated both reads, verified no partial IPC/temporary residue, and recovered with smaller history. Separate cached synthetic 5,000/50,000-post scans, 90,000 Unicode filename IPC and a three-sample 400,180-path full-history follow-up are documented with workload exclusions and slower bounded-encoding observations in [CAPACITY](../reference/CAPACITY.md). The source archive was built and its allowlisted entries verified.

Tests use temporary synthetic files and isolated helpers; no personal history/Cookie read, production service restart or live platform download occurred. SQLite diagnostics/backup/maintenance is completed by the subsequent milestone above; actual indexed metadata remains a future feature in [ROADMAP](../development/ROADMAP.md).

## N07 owned writer and durable barriers — 2026-10-14

**191 Python tests passed in 86.888 seconds; 18 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates 135 files, including `state_writer.py` and its new acceptance module. Chrome UI/capture, HLS/DASH, IPC, worker, source-policy, recovery and quality regressions remain enabled. Twenty-four new focused cases passed in 0.189 seconds; final writer/harness reruns cover idle snapshot release and recovered retry notices.

Tests cover immutable files/last-success/selection/pacing containers; passive construction/idempotent lifecycle; one in-flight/latest pending snapshot; checkpoint deadline, automatic flush and barriers; failure/dirty retention/manual recovery; invalid capture while an older write succeeds; future-backup and corrupt-primary preservation; independent contexts; closing producer guards/flush/join; all 13 route barrier locations; stop during startup persistence; account pause/stop during quota persistence without another charge. Real loopback requests read summary and cancel intent while native-write substitutes remain gated, and check critical replies do not return before release. No timing threshold is used for CI assertions.

The initial new fault case exposed an older accepted generation being misclassified after a newer capture failed. Waiting now checks whether an in-flight/pending accepted snapshot can still satisfy that barrier; the corrected case and all existing assertions pass. Review also found that a recovered store could retain an obsolete failure notice after a successful retry; it now restores the recovery notice and has a dedicated regression. Route-only no-op save mocks use generation zero or an explicit wait stub; production barriers retain strict generation validation and real save/API tests retain their durability checks. Idle writers release completed snapshots to avoid retaining a large history unnecessarily.

The same three-workload benchmark ran separately after full tests, with five samples per operation. At 400,180 paths / 20.29 MiB, capture median/p95 was 27.50/28.43 ms, snapshot retained/peak allocation 3,286,608/3,448,880 bytes, and durable save median/p95 862.53/868.75 ms. Contended summary median fell from 1,044.32 to 130.56 ms; pause/stop acknowledgement remained 1,856.81/1,901.52 ms because they wait for durable writes. Allocation excludes existing strings, other snapshots and serialization buffers; cProfile runs in the actual writer and is separate from latency timing. Details/limitations are in [PERSISTENCE_PERFORMANCE](../reference/PERSISTENCE_PERFORMANCE.md).

No personal Cookie/history access, production service restart or live platform media download occurred. Writer completion was a scoped N07 milestone; account/IPC/64 MiB capacity and SQLite maintenance are covered by the subsequent sections above. Actual indexed storage remains a future feature in [ROADMAP](../development/ROADMAP.md).

## N07 persistence measurement milestone — 2026-10-14

**167 Python tests passed in 86.091 seconds; 18 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates 133 files, including the new measurement tool, acceptance module and performance report. Existing Chrome UI/capture, HLS/DASH integrity, worker supervision, source policy, lifecycle and quality suites remain enabled.

Eight new cases validate synthetic counts and offline schema, nearest-rank statistics, real temporary primary/backup saves and summary/pause/stop acknowledgements, the gate at actual handler lock acquisition, failed-save rejection, owned writer/HTTP cleanup, RLock condition wait/notify semantics and source-package inclusion. They run the small workload and assert correctness, without machine-specific latency thresholds. The final focused rerun also passed all eight cases.

The full three-workload benchmark was repeated **separately after regression tests finished**, with five samples per operation. The 400,180-path / 20.29 MiB state saved in a median 927.67 ms (nearest-rank p95 1,267.31 ms). Contended summary/pause/stop acknowledgement medians were 1,044.32 / 2,057.78 / 1,930.42 ms. Measurements and cProfile-overhead limits are in [PERSISTENCE_PERFORMANCE](../reference/PERSISTENCE_PERFORMANCE.md).

No production service restart, personal Cookie/history access or external platform download occurred. Stop measures saved intent rather than actual subprocess termination; scan/IPC/64 MiB capacity and SQLite maintenance are outside this milestone. The writer was designed but not implemented at this first measurement; the follow-up above completes it, with remaining work in [ROADMAP](../development/ROADMAP.md).

## N06 frontend controller completion — 2026-10-13

**159 Python tests passed in 85.029 seconds; 18 Node tests passed; zero skips.** The source allowlist validates 130 files, including lifecycle and three new controller scripts. All seven real headless Chrome UI cases remain enabled, alongside synthetic Chrome capture, HLS/DASH, fault and child-process suites.

Eight new Node cases cover module loading without DOM/application globals, idempotent initialization/disposal, listener/timer cleanup, concurrent settings saves, closed settings ignoring late reads, old auto-close versus reopened drafts, disposed diagnostic reads/search debounce, object URL cleanup, and closed job details ignoring late responses. Existing offline recovery, snapshot ordering, uncertain writes, draft/scroll/language and connector tests still pass. Two new real Chrome cases cancel/confirm Rate without duplicate writes and page through 120 filenames before sending the exact selected index/name once.

Preliminary browser fixture runs exposed an ambiguous open-media selector and a keyboard assertion appended to the wrong test while adding coverage; the final run uses the action icon explicitly and retains the keyboard assertion in its original cookie-field case. Production focus and mutation assertions were not disabled. New controller lifecycle guards are covered by the Node cases.

No personal Cookie access, live platform download or backend service restart was performed. The page preserves its UI/API behavior and normal 30-second/active 2-second polling. N06 is complete; remaining work and platform/installation acceptance are in [ROADMAP](../development/ROADMAP.md).

## N06 download adapters and orchestration — 2026-10-13

**157 Python tests passed in 84.218 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12. The source allowlist validates 126 files, including seven new implementation modules and `test_media_architecture.py`. Ten new boundary/account tests passed in 0.190 seconds; focused manifest (7) and all-quality (10) suites also passed.

- Shared source/error/entry-point identity and gallery configuration lock; all implementation modules are included in the source allowlist and do not import the media facade.
- Engine routing and unsupported-video fallback; existing partial files prevent another fallback attempt. Original images bypass gallery/video and retain best/original mode; X credentials are stripped from other platform configuration. Public X posts use the dedicated service, and account links still require login.
- Replacement of the active request-policy object reaches paced HTTP and HTTP 429 backoff. Existing real child-process IPC, cancellation, no-progress/capture supervision, guarded HLS/DASH, missing-fragment failures and decoded stream acceptance remain in the full suite.
- Synthetic X timeline with real temporary ProfileArchive storage: scan total before transfer, completed post reuse without another transfer, moving one file refetches only its missing expected path, incomplete scans start no downloads, partial results retain error/files and do not mark the post complete, and temporary scan handles/shared lock are released.

An AST comparison of 29 moved top-level functions/classes against the previous commit matches after reversing the explicit dependency qualifications. This is an additional check against unintended extraction edits, not proof of all behavior. The first full attempt caught two missing imports in relocated browser test mocks; the passing run includes those corrections. Existing library socket ResourceWarnings remain tracked under dependency maintenance; assertions were not disabled.

No live platform media or personal Cookie values were used. Public entry points, API fields, archive/runtime locations, original-byte behavior and quality selection remain compatible. Frontend splitting was pending at this milestone and is completed in the follow-up above; current pending work remains in [ROADMAP](../development/ROADMAP.md).

## N06 state ownership and lifecycle — 2026-10-11

**145 Python tests passed in 83.787 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12, using temporary storage and synthetic browser pages. The source allowlist now validates 118 files, including `ssdl/app_context.py` and `tests/test_app_context.py`. The final focused lifecycle follow-up passed all 11 cases in 0.403 seconds.

The new acceptance cases verify fresh-process entry imports and context construction without login/history restore or thread startup, independent queue/pacing/services/locks/handlers, idempotent start and close, binding failure without migration, paused queue/settings/quota recovery into a new context, owned helper shutdown, rejection of pairing after auth shutdown, suppression of late login retry callbacks, and closing one running context while another worker continues. Queue/auth (17), P2 (13), HTTP framing/admission (11), environment (5), source policy (3) and diagnostic (3) focused suites also passed. A final startup-failure guard avoids joining unstarted helper threads and clears a worker that could not start; the expanded lifecycle suite passed 13 cases in 0.405 seconds.

One preliminary source-policy fixture call ended with Windows 10053 while a POST was rejected before its body was read; the focused retry and both full runs passed. This intermittent transport behavior is recorded for additional fixture/response coverage in N08; it was not suppressed by changing assertions or source authorization.

The application factory retains the existing production root, API fields and connector ID. Acceptance creates isolated application instances; it does not restore the user's actual X session, download live platform content or claim full Windows installation acceptance. Engine splitting was pending at this milestone and is completed in the 2026-10-13 follow-up above; current remaining work stays in [ROADMAP](../development/ROADMAP.md).

## First GitHub Actions repair — 2026-10-11

The [initial Windows run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/38117758688) failed with two errors and two failing subtests: the runner's default cp1252 encoding could not decode UTF-8 history, its short temporary-directory alias differed from the normalized restored path, and a four-second Chrome fixture budget could expire before the synthetic HTTP 429 request.

Use explicit UTF-8 and resolved fixture paths. The first repair's hosted run confirmed those fixes but exposed an additional eight-second Chrome launch timeout and a second fixture still using four seconds. Real Chrome fixtures now use a 30-second budget; launch allows up to 30 seconds within the existing overall capture deadline, and navigation uses only the remaining budget. Capture preserves fatal responses delivered during final browser calls and reports an exhausted budget as `browser_capture_timeout`. Two deterministic regressions cover startup exhaustion and a late HTTP 429 callback.

**134 Python tests passed in 65.378 seconds; 10 Node tests passed; zero skips.** The source-package allowlist check passed for 116 files. The repair subsequently [passed hosted Windows CI at commit 2bdb9f7](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/38118843888), including Python, Node, environment and packaging steps.

After adjusting the launch and navigation deadlines, the focused browser suite passed all 18 cases in 54.154 seconds with zero skips, including the supervised infinite-script deadline and private-network isolation cases.

## N03–N05 fixes — 2026-10-11

**132 Python tests passed in 57.492 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12.10 / Node 24.19.0, including synthetic-page real headless Chrome tests. Fourteen new regressions extend the N01/N02 baseline. A final focused auth/queue rerun passed all 17 cases in 0.239 seconds, covering the malformed pairing-token guard added after the full run.

- N03: Cookie array/object/null and overlong/control-character fields, boolean/nonfinite/huge expirations, mixed valid/invalid records and record-count limits; selector safety, generic HTTP 400, unchanged encrypted session and usable pairing ticket; successful correction/re-pairing. Malformed/non-ASCII pairing tokens also return AuthError without consuming the ticket.
- N04: missing paused, strings (including `"false"`), numbers, null and containers all return 400 with unchanged paused state and no save call; explicit true/false each save successfully.
- N05: owned partial headers/bodies, trickle input and the shared absolute deadline, early EOF and disconnects, malformed/duplicate/oversize Content-Length and Transfer-Encoding, invalid UTF-8/deep/nonfinite JSON, bounded admission, 503 / Retry-After, recovery after capacity is released, shutdown and injected socket-write timeout cleanup. Normal state/pause requests and extension CORS/prepare/accept routing still work.

The HTTP fixture uses two slots and short deadlines to exercise production admission/read logic without resource-exhaustion stress. A first full run exposed an observer race in a native large-write test: Windows could finish sending before the test saw an active slot. It was replaced with controlled TimeoutError injection and an explicit handler gate; the successful full run uses that deterministic test. This validates configured write timeout and cleanup, not native TCP throughput. Production defaults are 32 active connections, 10 seconds for total header/body input and 5 seconds for socket writes; API disk work is outside those transport deadlines.

Additional checks: 50 Python sources parse, 15 JavaScript/CJS sources pass `node --check`, and both locales contain all 633 keys. Local links resolve in 21 Markdown documents. The allowlisted source archive contains 116 files, including the new HTTP server and regression module; bytes and ZIP CRC are checked, and runtime directories remain excluded.

Tests use temporary storage and synthetic sessions, without reading real Cookie values or downloading external platform media. Local deployment checks are recorded separately in [CHANGELOG](../../CHANGELOG.md#unreleased): the idle service restarted healthy, retaining 25 completed jobs, hourly limit 80 and the connected X session. Remaining architecture, performance and environment acceptance stay in [ROADMAP](../development/ROADMAP.md).

## N01/N02 fixes — 2026-10-11

**118 Python tests passed in 54.482 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12.10 / Node 24.19.0, with synthetic-page real headless Chrome coverage. There are 14 new regression tests. A final targeted runtime rerun covers the frame-error classification cleanup after the full run.

- N01: malformed saved URLs/paths/nested pacing, late normalization failure with and without a backup, unchanged live jobs/queue/settings on failure, protected original/backup bytes, and offline URL recovery with no DNS request.
- N02: 80 unrelated completed jobs with 80,000 file paths no longer enter a new download payload; legacy source/quality/player/root matching and X post-author scoping remain.
- A real isolated child round-trips 70,000 long Unicode filenames (more than 16 MiB of UTF-8 JSON) through input, progress and final result, including an RPC checkpoint.
- Corrupt, reordered, truncated and oversize chunks report explicit errors; cancellation during a partial chunk is prompt, and capacity failure does not block the next queued job. Smaller-budget boundary tests exercise bounds without allocating 64 MiB for every failure case.

The logical message budget remains 64 MiB and the wire-frame budget remains 16 MiB. This is bounded chunking, not unlimited account capacity or proof of improved large-history disk latency. Network, login, persistence, browser, media/quality and source-package tests remain green.

## Earlier review and documentation migration — 2026-10-11

Re-ran the existing suite after the Python 3.12 baseline change and documentation migration: **104 Python tests passed in 53.365 seconds; 10 Node tests passed; zero skips**. The run includes synthetic-data headless Chrome tests and source-packaging tests. No live platform download, real Cookie access or production service restart was performed.

Separate temporary-fixture probes identified issues outside the existing regression coverage:

- A valid queued row followed by a malformed saved URL leaves a partial job map, an empty queue and a healthy storage indicator.
- A synthetic history payload of approximately 17.28 MB exceeds the 16 MiB child input limit; the real process supervisor returns `worker_exited` before downloading.
- Array/object Cookie names raise an uncaught TypeError in session selection.
- POSTing a string `"false"` to the isolated pause API returns 200 and enables pause.
- A partial HTTP request reaches body reading with no socket timeout; the probe closes its single owned connection. Resource-exhaustion testing was not performed.

These probes originally exposed missing regression coverage. N01–N05 are now fixed and covered above. Completed fixes are recorded in [CHANGELOG](../../CHANGELOG.md#unreleased); architecture suggestions and unmeasured performance risks remain pending in [ROADMAP](../development/ROADMAP.md#本輪整體審查).

## Earlier audit record — 2026-10-11

**104 Python tests + 10 Node tests passed, with zero skipped tests** on Windows, Python 3.12.10, Node.js 24.19.0, installed Google Chrome and Playwright 1.63.0. Python execution took 52.765 seconds. This reruns the earlier 59 Python/8 Node baseline, adds P2, quality and optional browser coverage, and checks the six reproduced fixes in the [project audit](PROJECT_AUDIT.md); it is not a claim that every live platform works.

Tests use synthetic URLs, data and HTTP/API fixtures, temporary directories and fresh headless Chrome contexts. The public-address network tests route checked synthetic numeric addresses to an owned local fixture. They do not disable the production network policy. No ordinary Chrome profile, real login Cookie, actual user history or platform download is used.

Additional local checks pass: 47 Python files parse, 15 JavaScript/CJS files pass `node --check`, `pip check` reports no broken requirements, and English/Traditional Chinese each have all 626 locale keys. Local documentation links resolve. The allowlisted source archive contains 113 files with matching source bytes and valid ZIP CRC; runtime folders are absent. These checks do not replace staged-file review after Git initialization.

## P2 coverage

| Area | Cases |
| --- | --- |
| Bounded state APIs | 200-job filtering/page boundaries; 20-file previews; summary without job rows; file pages capped at 100; invalid offsets/limits, missing job and untrusted Origin; full history remains intact |
| DOM reconciliation | Unchanged row/cell identity survives refresh; page size survives reload; existing offline/timeout/uncertain-write tests preserve valid state and never repeat a mutation |
| Snapshot ordering | Delayed older polling cannot undo a newer mutation; scoped sequence validation and service-instance changes reject retired responses while allowing restart |
| Capacity/cache | Replacement counted once, background scan overlay, deletion corrected by rescan, cache age/count pruning, delete failure reported, explicit cleanup preserves original/custom files |
| Player choices | Generic/static/dynamic grouping, opaque IDs without signed URLs, invalid/stale/foreign selection rejected, save/reload pending choice, selected quality retained and worker released for the next job |
| Cooldowns | Cooling X skipped while YouTube proceeds; order retained within X; deadlines restored; switching shared/per-platform preserves outstanding global deadlines; 429 captures Retry-After |
| UI and translation | Actual Chrome: fixed locale key parity/HTML keys, English switch, settings arrows/tabs/drafts, Tab/Shift+Tab/Esc/focus return, background inert, selection, 390px viewport and table scrolling |

Audit regressions additionally protect future-schema backups with missing/corrupt/valid older primary files, separate query-identified unlabelled media, reject unknown job-removal routes, preserve consistent authentication after a failed disconnect and make the advanced Cookie summary keyboard reachable. These use synthetic data, including fresh headless Chrome for network grouping and keyboard focus.

## Quality paths

Best and all caps (**2160, 1440, 1080, 720, 480, 360, 240, 144**) are submitted through actual UI controls and validated by the real HTTP API. Actual yt-dlp format selection uses synthetic format metadata; X native variant hooks and gallery-dl's delegated format options apply every cap. Tests cover lower fallback, separate audio/video, unknown dimensions, audio-only or only-too-high formats, source-size/label hints, extractor-dimension precedence, generic player changes, separate quality manifests/folders, retry retention and image normalization. Profile mode submits Best and rejects capped batch API requests.

This tests resolution selection logic, not the visual fidelity of each platform's codec. One synthetic 640×360 MP4 uses dynamic discovery and the existing capped download path; saved bytes equal the source and FFmpeg decodes the complete short fixture. Existing HLS/DASH tests also verify missing fragments, missing audio, merge failure and successful decode after recovery.

## Dynamic capture and faults

- Real Chrome executes an external script/config fetch, creates a player at runtime and reports its source height without downloading media during discovery.
- Extensionless HLS/DASH are recognised by Content-Type, and an anonymous JavaScript cookie remains domain scoped and transient.
- Separate players remain independent; normal/static extraction runs first and partial saved downloads do not start another browser attempt.
- Private redirects, local WebSockets, non-HTTP schemes and POST requests do not reach their private fixture. Cookies/Authorization never appear in candidate headers.
- Request/candidate/body budgets and missing optional dependencies have explicit tests. Rejected oversized resource reads count toward total bytes and end the scan.
- A real infinite JavaScript loop is stopped by parent capture supervision in approximately two seconds in its one-second-limit fixture; the owned child, browser and driver tree are terminated. Production capture limit is 45 seconds. Existing cancellation/tree tests protect unrelated processes.
- Capture 429 propagates to cooldown; other synthetic job failures and pending choices release the worker so subsequent work can start.

An initial Windows WebSocket `close()` route callback hung; the implementation now never connects the remote socket and avoids synchronous close in that callback. The regression now completes. An FFmpeg fixture used an invalid duration spelling during development; the corrected fixture uses `0.4` seconds. Failed/interrupted development runs are not counted as passing results.

## Remaining environment acceptance

- Fresh Windows installation with the Python 3.12 baseline.
- Actual Chrome connector pairing on a custom port and extension reload using an authorised account.
- Tag/Release and private vulnerability reporting checks; the existing repository has passing Windows CI history.
- Live platform-specific JavaScript players, authenticated/interactive pages and newly changed extractors; support varies and no universal playback capture is claimed.

Existing upstream SSL option deprecation and occasional closed-socket ResourceWarnings remain dependency-maintenance observations; they did not fail the successful suite. Rerun these tests when changing the engine, Playwright or Chrome baseline.


## Windows background lifecycle — 2026-10-24

Native Windows / Python 3.12.10: `tools/check_desktop.py` passed all **7 phases**
using a freshly verified source ZIP and installed venv under spaces/Unicode paths.
The tool used fresh loopback ports and synthetic media; no ordinary session,
history, output file or production service was changed. Success evidence is
stored locally in ignored `data/desktop-acceptance.json` (path-free summary).

- Real background batch launch exited while HTTP remained ready; the service
  had no console window and dispatched the exact custom-port URL.
- Repeated start with a changed/invalid port and output environment reopened the
  original URL/PID. Separate-project stop/start left the first service reachable.
- Active synthetic worker plus helper exited during real `stop.bat`, before
  fallback cleanup. The writer closed durably, owned threads joined, partial
  bytes remained and the service record disappeared; the port could be rebound.
- Repeated stop preserved saved-state bytes. Two concurrent cold launchers both
  succeeded, rotated the oversized log once, and recovered exact job IDs,
  attempts, paused queue, Rate usage and partial bytes before another normal stop.
- A real owned foreground entry retained HTTP service after background bind
  rejection and `stop.bat`; the bind error reached the background log and saved
  state stayed unchanged. Its eventual cleanup used only its admitted Job Object.

The full installation tool also passed all **13 installation/console phases**
plus the nested **7 desktop phases**, including optional browser dependency
installation, an actual package update, locked baseline restoration and real
owned-console Ctrl+C. Its path-free local report is
`data/desktop-installation-acceptance.json`. Production dependencies were unchanged.

Final extracted-source regression: **220 verified source files, 354 Python tests
and 24 Node tests passed**; the extracted dependency fault tracker also passed
116 cases with no errors/failures/skips, and the complete source acceptance exited
successfully. The new desktop/installation unit subset passed
21 tests. The standalone native tool passed again with the final fresh-shutdown
evidence check. The usual upstream SSL-options deprecation remains an observation,
not a failed assertion. The deferred `DOWNVID_COMPARISON.md` was not included in
the reviewed export, source ZIP, staging or commit.

The first development run found the fixture hook could be evaluated twice by
Python's venv site initialization, causing a fixture-only nested factory error.
Make hook installation idempotent and fail closed instead of allowing site.py
exception handling to fall back to ordinary media transport. Retain that regression.
No acceptance assertion was removed to obtain the successful run.

Browser verification records `webbrowser.open` dispatch and does not open a
personal browser. It is not evidence of Windows default-browser association,
visible pages, human double-clicks or every upstream engine's cancellation.
See [complete scope](../testing/DESKTOP_ACCEPTANCE.md); those manual checks remain in ROADMAP.


## Pixiv directory compatibility — 2026-10-25

- Native Windows / Python 3.12.10: `tests.test_pixiv_paths`, presentation,
  container receipt, Docker gate and workflow-policy suites passed **29 cases**.
- Linux Docker / Python 3.12.15 / gallery-dl 1.32.16: `check_docker.py --pixiv`
  passed all nine path cases, with zero errors/failures/skips, alongside the nine
  existing runtime/context checks. The final strict receipt probe was rerun.
- Test real directories and SQLite while replacing remote listings/transport;
  cover portable names, simulated renames, old complete/partial folders, root
  changes, relocation and removal during a wait. Retained originals keep their
  hashes/mtimes; complete reuse makes no quota call.
- No production path change was needed. Docker has no network, runs as a
  non-root user and mounts no host media/state. Full boundaries and remaining
  actual author rename / OS archive migration are in
  [path acceptance](../testing/PIXIV_PATH_ACCEPTANCE.md).


## Pixiv incremental and failure recovery — 2026-10-25

- Native Windows / Python 3.12.10: full regression passed **383 Python cases**;
  Node passed **24 cases**. The focused path/recovery/presentation/receipt suite
  passed **28 cases**.
- Initial fault injection reproduced count-only acceptance of gapped ordinals,
  duplicate ordinals with different extensions, unrelated error-file import,
  `.part` masking cancellation and duplicate retained-page payloads masking it
  again. Tests failed before the corresponding production corrections, then
  passed with assertions retained.
- Linux / Python 3.12.15: the combined `--pixiv` probe passed **25 cases**
  (nine paths and 16 recovery), zero errors/failures/skips; its first standalone
  run also passed the nine existing runtime/context checks.
- Full CI-shaped Docker integration `check_docker.py --browser --pixiv` passed
  on the local Linux engine: runtime/context, 14 service, 15 interaction, eight
  actual host-bind/secret and seven host-Chrome stages, plus both Pixiv groups
  running 25 tests. Existing PNG/H.264 decode/seek and scoped backup/restore
  remained successful; receipt is ignored `data/pixiv-roadmap-docker.json`.
- The reviewed source ZIP (230 files, deferred comparison excluded) passed
  the complete extracted regression: **383 Python + 24 Node cases**, then
  **116 dependency-fault cases** with zero errors/failures/skips. Source acceptance
  exited successfully. The known reviewed urllib3 SSL-options deprecation
  remained an observation. Private log: `data/pixiv-roadmap-source.log`.
- The real isolated RequestPolicy closes a synthetic 429 response, retains
  cooldown and permits a retry after its test clock advances. No real network
  limit, production queue, original download or login state was changed.
- [Recovery acceptance](../testing/PIXIV_RECOVERY_ACCEPTANCE.md) records cases, failure
  causes, corrections and the live/Ugoira coverage that remains pending.


## Pixiv authorization lifecycle — 2026-10-25

- Full native Windows / Python 3.12.10 regression: **399 Python cases passed**.
  Node passed **28 cases**, including four new connector-script boundaries.
- The focused auth module passed **16 cases** (13 manager/parser/storage and
  three real-loopback API cases). Source archive verification covered **233
  files**, then 17 auth/receipt cases and all 28 Node cases passed in extraction.
- Linux Docker / Python 3.12.15 passed **41 Pixiv cases** without failures/errors/
  skips, alongside the nine existing runtime/context checks; no host state or
  browser profile was mounted and networking was disabled.
- Reproduced stale encrypted credentials restoring after invalidation and an
  explicit port-zero callback being accepted. Preserve both failing regressions;
  store a token-free encrypted expired marker and require absent callback ports.
- Private evidence: ignored `data/pixiv-auth-docker.json` and
  `data/pixiv-auth-regression.log`. Known upstream SSL-options deprecation is an
  observation. Storage-denial limits, mocked Chrome scope and remaining real
  login/DPAPI/permission prompts are in [auth acceptance](../testing/PIXIV_AUTH_ACCEPTANCE.md).


## Pixiv artwork identity and legacy compatibility — 2026-10-25

- Native Windows / Python 3.12.10: complete regression passed **414 cases in
  108.227 seconds**, zero failures/errors/skips. The final focused identity,
  manifest, HTTP/P2 and container-receipt command passed **36 cases**. Node passed
  **28 cases**. The earlier auth commit `ccbb14f` also passed all three
  [GitHub CI jobs](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40139113814).
- Fourteen new identity cases use real temporary originals and SQLite with
  synthetic transport; one HTTP case verifies pending-row reuse and quality
  separation. Preserve exact old URL completion evidence and root scope;
  unanchored old hashes and unknown query semantics are not guessed.
- Reproduced promotion accepting a file changed after its old lookup when the
  new record restatted that file. Copy the old size/mtime evidence unchanged,
  insert without replacing another writer, then verify again. Keep the failing
  mutation regression and competing-writer/original-missing cases. Two URL
  boundary subcases also reproduced normalization of an empty port/username;
  require an exact reviewed authority instead.
- Linux / Python 3.12.15: final `check_docker.py --browser --pixiv` passed the
  existing **53 runtime/service/interaction/host/browser stages**, plus **55 Pixiv
  cases**, zero failures/errors/skips, with `passed: true`, `complete: true` and
  owned-resource cleanup. Initial integration reached the Pixiv stage without a
  successful receipt after cases were extended while its image was already
  built; rebuild/rerun using the fixed final test/source versions passed. The
  final image source fingerprint is
  `5d7588331f14340f14ba8a55fb35eb6ddb51801ef332bb67db02f8f08ce2928f`.
- Verified a **235-file** source ZIP from the reviewed Git-file export, excluding
  the deferred comparison document and all runtime data. Full extracted-source
  regression passed **414 Python cases in 107.241 seconds / 28 Node cases**.
- Extracted dependency-fault acceptance passed **116 cases in 71.719 seconds**,
  with only the reviewed urllib3 SSL-options deprecation and zero unexpected
  observations. The current checkout interpreter has pycryptodomex 3.24.0; this
  run did not reinstall its packages. The source lock and successful Docker
  runtime use the reviewed 3.24.1 baseline; fresh Windows CI installs that lock.
- Private logs/receipts are ignored `data/pixiv-identity-regression.log`,
  `data/pixiv-identity-source.log` and `data/pixiv-identity-docker.json`. No
  production service, download, queue or login state was changed. Recognized
  URL forms, legacy limits and remaining live-platform scope are in
  [source identity](../reference/DOWNLOAD_DEDUP.md#pixiv-artwork-identity-and-legacy-completion-records).


## Ordinary Chrome pairing: partial live acceptance — 2026-10-25

- Operator-assisted ordinary Chrome / connector 1.2.0: observed the explicit
  8877/8765 mismatch; actual `/api/auth/x/prepare` and `/api/auth/x/extension`
  both returned 200 with matching extension Origin/ID and reduced Chrome
  User-Agent 155.0.0.0. No Cookie/code/token was printed or included in reports.
- Native Windows user DPAPI round-trip passed. The temporary saved X session
  remained connected after a new backend AppContext restored it. Production
  service port 8765 was not restarted; the runner loads no production history.
- The real X ticket was waiting at 597.6 seconds and failed at 616.6 seconds,
  preserving the existing connected session. No shortened TTL or patched clock.
  Post-expiry re-pairing is still pending.
- Two ordinary-browser Pixiv begin requests succeeded; no connector claim or
  callback reached the service. Pixiv auto-return and restore are not accepted.
  Cancel/re-pair, offline/retry and actual browser/worker restarts also remain.
- Both supplied Codex settings screenshots show Browse allowed for 8877,
  including Chrome management. Nevertheless browser tools still reject that
  origin under saved permissions/managed policy. Stop UI retries after checking
  those settings; do not substitute another browser/CDP/proxy to bypass it.
  This gate failure does not establish a DPAPI or downloader authorization bug.
- The live temporary service exited 0. The final runner's separate native
  random-byte DPAPI/start/restart/cleanup probe also passed, with encrypted test
  scope removal confirmed and no browser connection requested. The operator
  confirmed returning the connector destination to production port 8765.
- Full native regression: **420 Python in 105.083 seconds**. Verified **238 source
  files**, excluding private state and the deferred comparison document; complete
  extraction passed **420 Python in 107.638 seconds / 28 Node cases**, then
  **116 dependency-fault cases in 71.000 seconds**, zero failures/errors/skips.
  Only the previously reviewed urllib3 SSL-options deprecation was observed.
  The current checkout interpreter remains on pycryptodomex 3.24.0; this run did
  not install packages or change the reviewed 3.24.1 source baseline.
- Six new mocked runner contracts cover report/port boundaries, explicit opt-in,
  secret-free snapshots, fixed operator notes, private real-expiry setup and
  orderly forced cleanup. They do not count as real Chrome UI coverage.
- Private ignored evidence: `data/chrome-pairing.json`,
  `data/chrome-pairing-tool-smoke.json`, `data/chrome-pairing-regression.log` and
  `data/chrome-pairing-source.log`. Procedure and all remaining scope are in
  [ordinary Chrome acceptance](../testing/CHROME_PAIRING_ACCEPTANCE.md).


## Chrome pairing CI path-alias repair — 2026-10-25

The [c21b928 run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40141804763)
passed fresh Windows installation and Docker acceptance. Its Windows regression
ran 420 cases in 120.629 seconds with one failure, at the first report-path
assertion in `test_explicit_custom_port_and_report_boundary`. CI supplies TEMP
through the Windows 8.3 spelling `RUNNER~1`; the validator returns the resolved
long path. The fixture compared that canonical result with its unresolved path.
This was a test expectation failure, not a rejected valid report location.

A new deterministic regression invokes the same original boundary case through
a real temporary directory spelled using an existing component followed by
`..`. This reproduces equivalent-but-lexically-different paths without requiring
8.3-name creation. It failed before the fix. Resolve the owned fixture root in
setUp, then compare paths in the same canonical form. The directory-existence
check and zero-error assertion ensure the inner case reaches its path checks.
All original port/path rejection assertions remain active; the production
validator, auth handlers and workflow configuration are unchanged.

Focused pairing/source tests pass **16 cases**. Complete native regression
passes **421 Python cases in 107.080 seconds**, zero failures/errors/skips.
Source verification covers **238 files**, with the deferred comparison document
and all private state excluded. Complete extracted-source acceptance passed
**421 Python cases in 105.857 seconds / 28 Node cases**, followed by **116
dependency-fault cases in 71.672 seconds**, zero failures/errors/skips. Only the
existing reviewed urllib3 SSL-options deprecation was observed. Private logs are
ignored `data/chrome-pairing-ci-repair.log` and `data/chrome-ci-repair-source.log`.

A direct Chrome request on resumption still received the saved-permission/
managed-policy denial, despite the prior Browser/Chrome allow screenshots and
the local origin rule `access = "allow"`. The actual cause remains unconfirmed;
no global settings or browser policy were changed. The operator chose to keep
remaining real pairing work pending while this CI repair completes. This turn
did not start another live-login service or claim additional real-pairing cases.


## Browser UI CI fixture capacity and diagnostics — 2026-10-25

The [e11e4d1 run](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40142930583)
confirms both Chrome report-path tests pass. Fresh Windows installation and
Docker also pass. The Windows regression instead reports one error among 421
cases in 124.733 seconds: the first UI keyboard case reaches its snapshot wait
with `ReferenceError: lastResponse is not defined`, before interacting with the
Cookie field. The old harness did not report failed resource requests, so the
original runner's exact trigger cannot be established from that log.

Thirty successive local page loads pass. Aborting only `ui_state.js` reproduces
the exact ReferenceError. Delaying that deferred script still loads normally,
which does not support an early snapshot wait as the cause. A separate real TCP
probe stops accepting pending connections at the fixture's default backlog of
five. Increase the fixture to 64, matching the application's existing listener;
the production server and frontend behavior are unchanged.

Three regressions fail before this change: eight real pending connections,
an aborted bootstrap asset, and an HTTP-successful script that throws during
initialization. After the change all 11 Chrome UI cases pass. The last two
regressions require an immediate assertion naming the failed resource or script
error, not the secondary global-variable error. Ordinary loads and reloads now
check resource failures/HTTP errors and JavaScript errors before waiting for the
first snapshot. No retries, longer timeouts, disabled tests or swallowed script
errors were introduced. These synthetic isolated tests do not access the denied
live pairing origin, a personal browser profile or production login state.

Complete native regression passes **424 Python cases in 105.309 seconds**, zero
failures/errors/skips. Python syntax checks cover 130 files; the reviewed eight
Action pins and changed-document local links also pass. Private native output
is ignored `data/browser-ui-ci-repair.log`.

The reviewed **238-file** source ZIP excludes the deferred comparison document
and private state. Complete extracted-source acceptance passes **424 Python
cases in 106.536 seconds / 28 Node cases**, followed by **116 dependency-fault
cases in 71.094 seconds**, zero failures/errors/skips. Only the existing reviewed
urllib3 SSL-options deprecation is observed. The checkout interpreter still has
pycryptodomex 3.24.0; no packages were installed or source-lock versions changed.
The acceptance child exited zero and logged completion; the local wrapper then
hit a GBK encoding error while echoing Unicode Node checkmarks. Reading its
UTF-8 log confirms the successful child result, separately from that console
summary failure. Private extracted output is ignored
`data/browser-ui-ci-source.log`.


## Hosted CI confirmation — 2026-10-25

[Run 40143826641](https://github.com/Zimkjdv/Smart-Social-Downloader/actions/runs/40143826641)
for `d22c9a8` completed successfully at 07:50 Taipei time. All three jobs
(`windows`, `install-windows`, `docker-runtime`) and their acceptance steps
passed, including extracted-source tests. The earlier failed runs remain
historical failures; this successful push validates the path normalization and
browser fixture repairs on hosted runners. Real-account Chrome pairing remains
a separate acceptance procedure.


## Default branch protection — 2026-10-25

The repository initially had no branch rules or rulesets. After the owner
completed GitHub account verification, the UI confirmed `Ruleset created` and
`Protect main Active`, applying to `main`. The read-only ruleset API confirms
[rule 25801940](https://github.com/Zimkjdv/Smart-Social-Downloader/rules/25801940)
has active enforcement, deletion/non-fast-forward restrictions, pull requests
with zero required approvals and resolved review threads, and strict required
checks `windows`, `install-windows`, `docker-runtime`, each bound to GitHub
Actions integration 15368. The bypass list is empty. No destructive push or
branch deletion was attempted to verify these settings. These are live GitHub
repository settings, not settings installed by a source checkout.


## Follow-up source verification — 2026-10-25

A tracked-file export excluded the deferred comparison document and all private
runtime data. The 238-file source ZIP passed byte/CRC/allowlist verification,
then the extracted source passed **424 Python tests in 108.471 seconds**, **28
Node tests**, and **116 dependency-fault tests in 71.156 seconds**, with zero
failures/errors/skips. The dependency probe observed only the previously
reviewed urllib3 SSL-options deprecation. Eight reviewed Action pins and the
CRLF-aware whitespace check also pass. No runtime source or dependency versions
changed; the final acceptance documentation is byte-verified in the reviewed
source archive. Private output is ignored `data/main-protection-source.log`.


## Completed native Chrome main flow — 2026-10-25

Follow-up ordinary Chrome 155 / connector 1.2.0 at port 8877 used the real
Windows user, native DPAPI and actual auth handlers. Observed outcomes:

- Cancel returned 200 and phase idle; a fresh real connector exchange connected.
- Offline Connect displayed service-unavailable; online retry connected using
  fresh real prepare/submission requests.
- An unchanged 600-second X ticket was waiting at 544.2 seconds and failed at
  601.5 seconds while the existing login remained connected. Re-pairing after
  the operator's Chrome restart succeeded and status was connected at 625.2
  seconds.
- Pixiv begin/claim/callback all returned 200, with matching extension Origin/ID
  on claim/callback; the browser automatically returned to the local connected
  page. A new backend AppContext restored both DPAPI-encrypted sessions with
  no additional callback or manual token entry.
- After the operator reported `Service Worker (無法使用)`, another real X
  prepare/submission returned 200. The receipt contains four successful X
  pairs in total. This is assisted recovery evidence, not a worker-termination
  trace or an in-flight OAuth suspension test.
- The saved connector destination returned to 8765, observed through the 8877
  mismatch message. The runner exited 0 and removed its temporary scope. The
  normal 8765 background service was started after a connection-refused probe;
  the same HTTP probe then returned 200.

The final report has `closed: true` and `temporary_scope_removed: true`.
Receipts/screenshots stay under ignored `data/`; no Cookie, code, token, browser
profile or login file enters the commit/archive. The full procedure and broader
remaining scope are in [Chrome acceptance](../testing/CHROME_PAIRING_ACCEPTANCE.md).

## D01 shared API and Browser Adapter — 2026-10-26

D01 adds a versioned platform seam without changing business routes or importing
GUI packages. Checkout regression passed 428 Python cases; two additional real
headless Chrome cases then passed for a diagnostics download and detached media
preview. The final reviewed source ZIP contained 241 files and passed all 430
Python cases, 36 Node frontend cases and 116 dependency-fault cases. All eight
pinned Action references passed policy checks. The known urllib3 SSL-options
deprecation remained a reviewed dependency observation.

Fixtures cover popup blocking/closure, unsafe destinations, cancellation and
export cleanup, X disconnect invalidation, Pixiv backend-open ownership and
late disposal. Local HTTP tests preserve native/container dispatch and reject
stale/deleted files, traversal, non-media and foreign origins before OS launch.
The two Chrome tests use a fresh temporary context and synthetic HTTP content;
they do not establish pywebview/WebView2 or real-account login acceptance.
Runtime output stays in ignored data. The unrelated untracked comparison note
was excluded from the tracked-source export. See [contracts](../reference/API_CONTRACT.md).

### D01 hosted Docker gate follow-up

At `6c81b3a`, hosted Windows and installation jobs passed; Docker reached renamed
file rejection after successful image decoding, keyboard selection, H.264
playback/seek and reload checks, then failed. A reserved about:blank tab had
already fired DOMContentLoaded, allowing the gate's URL check to run before the
actual media navigation committed. A real Chrome test with delayed 404 headers
reproduced `browser_error_navigation_escaped` before the fix and passed after it.
The gate now waits for the exact local-origin job/content destination and then
checks 404. Origin restrictions and missing-file validation remain enforced.

## D02 supervisor control — 2026-10-26

The final 245-file reviewed source ZIP passed 442 Python cases, 36 frontend
cases and 116 dependency-fault cases. A new disposable Windows source/venv
passed the full installation gate including optional browser installation,
updates/restored pins, hidden console Ctrl+C, and nine native background phases.
New native cases verify attached identity/stop refusal, a second real process
requesting window focus, closing window controls without stopping work, deliberate
receipt-owned Job Object exit, cold recovery, and refusal to stop a replacement.
No PID-based termination or ordinary project state was used.

D01's hosted follow-up at a437206 passed windows, install-windows and
docker-runtime. Local Docker runtime plus all seven real browser stages and 55
Pixiv cases passed as a focused check. The local full Docker sequence separately
stopped at host_bind_contract_failed under Windows Docker Desktop/Compose; it did
not reach its browser stage. That host-bind result is not reported as a full
local Docker pass. Linux hosted Docker completed the full sequence successfully.
D03 real WebView2 presentation remains separate from these control fixtures.

## D03 native WebView2 source shell — 2026-10-26

The final 255-file reviewed source ZIP passed 450 Python cases, 41 frontend
cases and 116 dependency-fault cases. The complete fresh Windows source/venv
installation with browser dependencies and all nine background-control phases
also passed. The eight pinned Action references passed policy checks; pip check
reported no broken requirements after the optional desktop pins were installed.

An opt-in native WebView2 gate then opened two receipt-owned temporary GUI
sessions with separate application data and a dedicated persistent profile. Both
verified the six-method bridge allowlist, the real dashboard, shared HTTP writes,
repeat launch/focus, refused navigation followed by a successful new bridge call,
closing the window while backend stayed reachable and explicit owned shutdown.
Language/page preferences survived the second session. The observed device pixel
ratio was 2; the synthetic screenshot was visually inspected. No ordinary Chrome
profile, real account, user history or production media was used. Temporary
receipts/PNG remain in ignored data, not the source ZIP.

The first navigation refusal exposed a pywebview WinForms cache detail: cancelling
kept the actual trusted document but cached the attempted URI. The host now
preserves the committed CoreWebView2 Source and existing readiness after that
cancelled navigation. Native regression checks this behavior and bridge reuse.
Portable fixtures additionally test permissions/cancel/timeout, late handshakes,
settings draft epochs, native export/cancel, popup/frame/message origin guards
and ordinary Chrome selection for pairing fallback.

This is current-runtime source-GUI smoke, not a fresh Windows OS, all DPI values,
actual native picker/clipboard permissions or real-account Chrome callbacks.
Those remain D04. No D05 frozen EXE/installer work was performed. Commands and
scope: [desktop guide](../guides/WINDOWS.md).

## D04 shared contracts and native GUI matrix — 2026-10-26

The 260-file reviewed source export passed 455 Python cases, 57 frontend cases
and 116 dependency-fault cases. All eight pinned Action references passed policy
checks. Core HTTP was additionally served in a fresh interpreter that rejects
all pywebview/.NET imports. GUI packages remain optional; core/Docker CI has no
new GUI installation. The reviewed urllib3 SSL-options warning remains the same
dependency observation documented above.

Real receipt-owned WebView2 sessions passed the expanded GUI matrix on this
Windows/Python 3.12.10 host, WebView2 155.0.4283.62 and Chrome 155.0.8059.86.
The renderer's initial devicePixelRatio was 2; this does not measure OS settings.
Matching 1280×800 CSS viewport captures
of settings/errors in Chinese and English were visually inspected. The desktop
picker, banner, font rendering and scrollbar differences are expected; no pixel
identity is asserted. Four CDP scale captures are renderer emulation, not four
actual Windows display settings.

The matrix passed shared HTTP/UI flows, scripted focus/scroll, actual clipboard
write/readback with previous data restored, injected picker cancel/selection and
UTF-8 export, validated/intercepted file/folder/external dispatch, PNG/H.264 decode,
advancing frames, seek, HTTP 206 and Chrome Blob/native-media export/playback.
Two sessions verified profile preferences, attached-stop refusal, backend-exit
offline UI, history/pending-queue/partial recovery, active synthetic work after
programmatic window close and graceful owned shutdown. Concurrent gated GUI
processes produced one primary window and backend. A foreign listener survived
failed startup and its native error message was captured. Final fixture cleanup
was reported separately from acceptance. Reports/PNGs are ignored local data.

Red/green regressions found two bridge-wait cancellation issues (closed host
reported unsupported; abort waited for handshake timeout) and a startup error
rendering failure. Actual WebView2 NavigationStarting represented NavigateToString
as a data URI, which the guard rejected; initialization could also overwrite an
early error load. The host now registers exact generated HTML bytes, grants no
native powers to those documents, keeps arbitrary data navigation blocked and
waits for initialization before showing the error. The native conflict gate
failed before this fix and passed after it. Temporary diagnostic tracing was
removed.

The user-assisted follow-up passed the current Windows host's manual baseline:
actual folder/Save As dialogs, cancel/overwrite/read-only refusal, physical
keyboard/focus/scroll, actual OS scales 100/125/150/200%, PNG/MP4/folder/external
applications, native close/stop prompts and desktop-initiated ordinary Chrome
X/Pixiv callback/clear/reconnect. A genuinely reopened second window restored
both DPAPI sessions; its close left the backend reachable before isolated login
cleanup and owned stop. Connector port 8765 was restored; production stayed
available. A PermissionError in the auxiliary polling loop made some first-round
live samples incomplete, so they are not used to infer DPI transitions or closure.

The follow-up also found an invalid PNG IDAT CRC in the synthetic fixture:
permissive browser decoding had accepted it. A strict chunk-CRC regression failed
before correction and passed after it. The application media path did not change.
The 455-case source run includes this regression. A GUI matrix attempted during
human desktop operations failed with gui_clipboard_write_failed and remains a
failed attempt; its cause is not established. The final matrix, run alone after
the operator finished, passed all six shared/native/media groups, both GUI
sessions, concurrent startup and foreign-port conflict with strict checks
unchanged. Its report states passed=true, 260 source files and normal workspace
removal. This does not prove the earlier clipboard failure cannot recur.

Hosted push and PR workflows at the initial D04 commit 3b8b72c both passed all
three jobs: Windows regression, fresh Windows installation and Docker runtime.
The follow-up commit requires its own hosted checks after pushing.

Fresh-process startup at every scale, mixed-DPI monitors, actual clipboard
permission refusal and physically runtime-free Windows remain untested. The
runtime failure notification is injected. Exact commands, human reports and
evidence boundaries are in [D04 acceptance](../testing/DESKTOP_GUI_ACCEPTANCE.md). D05 was
not started.


## D05 Windows distribution — 2026-10-26

The directory bundle and per-user Inno Setup installer were built on the current
Windows 10 build 19045 host with Python 3.12.10. They include separate windowless
GUI and console/pipe runtime executables, Node 22.23.4 and a separately built
LGPL FFmpeg 8.1.3 with zlib 1.3.2. Download hashes, Microsoft/Inno publisher
signatures, exact dependency versions and pip check passed. Bundled licenses,
corresponding sources, build recipe and source ZIP hash accompany the runtime.
The source wheel's unrelated FFmpeg binary is excluded.

The extracted source suite passed 468 Python, 59 frontend and 116 dependency-fault
cases. Both workflows and all 15 pinned Action references passed policy checks.
The final session-size and external-home corrections passed all 13 distribution cases.

The reviewed 282-file source export passed the real WebView2/Chrome matrix:
both GUI sessions, shared UI/media/clipboard groups and concurrent/conflicting
startup. Profile and HTTP-backed preferences survived restart. The matrix's
physical dialogs/keys, scale changes and external application dispatch remain
injected or emulated as documented in D04; no new human observations are inferred.

Receipt-owned frozen acceptance passed actual WebView2/UI/bridge/preferences,
close with backend alive, framed worker and invalid Pixiv exchange, PNG-to-JPEG
thumbnail decoding, HTTPS protocol discovery, HTTP UI and synthetic DPAPI restore.
External Python/Node were removed from child PATH. Different installation paths
attached to the same data-scope owner; attached-stop was refused. Graceful stop
and restart preserved history, login, preferences and original media. Real silent
installers with a unique test AppId refused an update while the backend ran,
then allowed update and installer rollback after stop. Uninstall removed program
files and retained user data/media. The two installer versions contain the same
current application/data schema, not an arbitrary future downgrade test.

Regressions exposed and corrected Windows SQLite connections left open during
directory swap, legacy cp950 output corrupting JSON pipes, and a migration bound
smaller than the encrypted-session store's canonical limit. The final migration
regression imports actual DPAPI ciphertext larger than 16 KiB and verifies exact
bytes, source/media preservation and rollback. Migration also refuses active
foreground writers, newer state, linked inputs and failed destination replacement;
a prepared backup supports recovery after an interrupted swap. A source child with a separate data home resolves the reviewed code through an explicit
role entry, rather than searching that data directory for Python modules. Native folder
selection runs on an STA thread. No production data was imported.

Clean Windows 10/11 acceptance remains unchecked. The host has no Windows
Sandbox and the user confirmed no other clean machine/VM. PATH isolation and
hosted runners are not substitutes. Actual missing-Runtime bootstrap/repair,
installed shortcuts/native prompts and real-account Chrome callbacks in that
clean environment remain gates in ROADMAP and WINDOWS_DISTRIBUTION. No tag,
public Release, automatic updater, signing, tray or startup registration was added.

The first hosted D05 source runs exposed a stale native acceptance assertion:
the new writer lease refused a same-scope foreground conflict before socket bind,
but the fixture still required an OSError log. It now requires the specific
writer-lease diagnostic and retains its foreground-survival, unchanged-state and
normal-stop checks. No production refusal or shutdown behavior was weakened.
The corrected receipt-owned native source acceptance passed all nine phases locally,
including that conflict and abrupt-exit recovery, before the follow-up push.

## Desktop planning context — 2026-10-26

The following completed plan is preserved for its design decisions and original acceptance boundaries. Current contracts live in reference documents; open work remains in Roadmap.

### Windows 桌面版：先 pywebview，保留 Electron 遷移路線

2026-10-26 規劃，D01～D03 已完成並記錄於 CHANGELOG；D04 自動化與目前 Windows 主機的人工基線驗收已完成，額外環境限制列於驗收指南。D05 的資料夾型發行包、安裝程式與目前主機驗收已實作，乾淨 Windows 驗收仍待環境；D06 保留後續。決策依據為使用者指定的「先做 pywebview，業務功能走標準 API，桌面專屬功能集中封裝」，並參考 [Python WebUI 轉 Windows GUI 對話](chatgpt-conversation://6ade3c59-7034-83e8-843b-79c106709fe9)。目標是瀏覽器版與桌面版共用同一份 Web UI／Python 後端，日後替換外殼時保留業務程式與資料。

#### 現況判斷與必要前置

**現有前後端已具備可沿用的分離，不需要先重寫或拆成兩個 repository。** `static/` 提供 HTML／CSS／JavaScript，`static/api.js` 集中 HTTP／JSON 請求與回應檢查，`ssdl/http_api.py` 提供路由，`AppContext`／scheduler／repository 處理工作與保存。先補齊桌面差異的 Interface 與生命週期，再接 pywebview；不把改用 FastAPI、React、TypeScript、bundler 或 WebSocket 列為前置。

以下盤點以 D01 實作前的結構為基準；各階段完成紀錄見下方與 CHANGELOG。

| 原始位置 | 規劃當時的能力／耦合 | 需要的調整 | 時機 |
| --- | --- | --- | --- |
| `static/api.js`、各 controller | 已透過 HTTP 操作工作、設定、登入及診斷；API client 有期限、取消、schema 與不確定寫入結果處理 | 整理共用業務契約；controller 不直接使用外殼 bridge | D01，GUI 前 |
| `static/jobs_controller.js`、`diagnostics_controller.js`、登入腳本 | 分散使用 `window.open`、Blob 匯出、剪貼簿及 browser／desktop 檔案操作分支 | 以集中式 `DesktopInterface` 與 Browser／Pywebview Adapter 承接實際差異 | D01／D03 |
| `ssdl/http_api.py` | 開資料夾／開檔路由內直接呼叫 `os.startfile` | 路徑與工作檔案驗證留在後端；Windows 分派集中至平台 Module | D01，GUI 前 |
| `ssdl/desktop_service.py`、`tools/manage.py`、`ssdl/app.py` | 已有 Windows 互斥鎖、ready／stop／done、日誌及正常關閉；啟動成功會直接開瀏覽器 | 分離「確保服務可用」與「顯示介面」，形成可供不同外殼使用的控制 Interface | D02，GUI 前 |
| `AppContext.ROOT`、`desktop_service.ROOT`、`job_runtime.py` | 靜態資源、狀態／登入／SQLite、cache 及預設 downloads 依賴專案 root；子程序使用 `sys.executable -m ...` | 開發版保留現有位置；安裝版前分開資源與可寫資料，定義 frozen EXE 的 backend／worker 入口 | D05，安裝版前；不阻塞來源版原型 |

#### 共用架構與責任

```text
共用 static/ Web UI
  ├─ SSDLApi → 同源 HTTP／JSON → Python 工作／設定／登入／媒體／保存
  └─ DesktopInterface → Browser Adapter 或 Pywebview Adapter
                                      └─ 未來 Electron preload／IPC Adapter

桌面外殼 → BackendSupervisor 的控制 Interface → 獨立 Python 後端程序
```

`DesktopInterface` 是放置可替換實作的 Seam；Browser 與 Pywebview 是第一批實際 Adapter，Electron 先記錄對應方式，不建立沒有使用者的空實作。外殼只處理視窗、原生互動與後端程序管理，不能擁有第二份佇列、下載狀態、資料庫、登入憑證或下載引擎。

建議落點為 `static/desktop.js`（Interface／組裝與 Browser Adapter）、`static/desktop_pywebview.js`（唯一直接接觸 pywebview bridge 的前端 Adapter）、`ssdl/platform_actions.py`（後端 OS 分派）、`ssdl/desktop_control.py`（Supervisor／薄控制入口）及 `desktop/pywebview_app.py`（GUI 啟動與視窗）。現有 `desktop_service.py` 的 Windows 控制實作繼續沿用；名稱與檔案數於實作時依責任調整，不先建立空檔案。未來 Electron 的主程序／preload／打包設定再放入獨立外殼目錄。

| Interface | 職責與契約 |
| --- | --- |
| `SSDLApi` | 工作加入／暫停／停止／重試、設定、X／Pixiv 授權狀態、診斷、檔案清單及媒體內容一律使用共用 HTTP API；保留相對 `/api/...`、現有輪詢與錯誤語意。只有實際需求與量測支持時才增加 SSE／WebSocket。 |
| `DesktopInterface` | 由組裝入口注入 controller；集中原生選擇資料夾、開外部連結、診斷匯出及必要的視窗操作。動作方法使用 Promise、可序列化資料及一致的取消／不支援／錯誤結果；保留點擊手勢的分頁預留及 dispose 是同步的本機生命週期操作，不跨 bridge；先訂版本與能力清單，能力缺少時保留瀏覽器替代操作，不依 user-agent 猜測。 |
| 工作檔案與 OS 操作 | 前端以工作 ID、檔案索引與既有檔名核對欄位提出開檔／顯示位置需求。後端保留檔案範圍、存在性、類型及過期選取驗證，再交平台 Module 執行 OS 分派；不讓 renderer 以任意路徑或 shell command 繞過驗證。現有 HTTP 開檔路由維持相容。 |
| `BackendSupervisor` | 集中啟動／附接、就緒、身分與版本核對、服務擁有權、正常停止及錯誤處理。pywebview 呼叫共用 Python 實作；為未來 Electron 保留薄的控制 CLI／私有程序通道與 JSON 結果／退出碼，不在 JavaScript 重寫服務管理。控制協定與業務 HTTP 分開，不新增無保護的 HTTP 關機入口。 |

一般 controller 不直接存取 `window.pywebview.api`、`ipcRenderer`、Node／Python 物件或框架型別；框架偵測、bridge ready 時序及轉換只在 Adapter／組裝入口。bridge 僅暴露必要桌面方法，不能把整個 AppContext 或任意 method／IPC channel dispatcher 交給網頁。若新增本機驗證憑證，使用外殼無關的協定，不能把業務 HTTP 契約綁到 `pywebview.token`。

#### D01：共用契約與平台操作（已完成）

2026-10-26 完成，實作／測試範圍見 [共用契約](../reference/API_CONTRACT.md) 及 [CHANGELOG](../../CHANGELOG.md#unreleased)。業務 API 保留；Browser Adapter 已承接開頁、配對分頁預留、診斷下載、剪貼簿與取消清理，Windows 開檔分派集中於平台 Module。未宣稱 pywebview／WebView2 已驗收。

#### D02：後端與視窗生命週期（已完成）

2026-10-26 完成，見 [Supervisor 契約](../reference/DESKTOP_CONTROL.md) 及 [CHANGELOG](../../CHANGELOG.md#unreleased)。啟動／附接與開頁分離；核對 Windows 控制鎖、HTTP 身分、版本及執行個體，缺引擎仍可取得 UI／API 就緒。外殼停止使用執行個體專屬事件；單視窗與喚回事件已通過原生雙程序驗證，關閉視窗控制不停止後端。真正 GUI 與關窗提示由 D03 接上。

#### D03：pywebview／WebView2 來源版本（已完成）

2026-10-26 完成，使用方式見 [桌面指南](../guides/WINDOWS.md)，實作與證據見 [CHANGELOG](../../CHANGELOG.md#unreleased) 及 [測試紀錄](../history/TEST_RESULTS.md)。`desktop.bat` 使用選配鎖定依賴載入相同 HTTP UI；原生視窗、資料夾選擇、診斷另存、專用 profile、關窗續抓與明確停止均已接上。原生 guard 限制導航／frame／彈窗與 bridge 訊息來源，X／Pixiv 授權沿用一般 Chrome。

兩次真實 WebView2 隔離啟動已驗證 UI／bridge、共用 HTTP 寫入、重複開啟喚回、語言／頁數保存、拒絕導航後 bridge 仍可使用、關窗續留後端與 owned stop；當前實際 devicePixelRatio 為 2。D03 是來源版本與基本 smoke；D04 擴充結果列於下方，也不是 D05 安裝包。

#### D04：共用介面與實際 Windows GUI 驗收（目前主機基線完成）

- [x] 以同一組 Interface 契約驗證 Browser／Pywebview Adapter，包括能力缺少、bridge 尚未就緒、取消、拒絕、逾時及視窗已關閉；業務測試跨 HTTP 執行，不為每個外殼複製下載引擎／佇列測試。核心匯入與實際 HTTP 請求在禁止 GUI 匯入的獨立 interpreter 通過；一般 Web／Docker 與既有 CI 不增加 GUI 套件。
- [x] 在暫存資料與專用 profile 自動化驗收真實 WebView2：啟動、既有／重複／同時啟動、埠衝突、後端退出、關窗續抓、明確停止與重啟恢復；缺少套件／Runtime 有明確失敗碼，不能跳過當作通過。實際未安裝 Runtime 的乾淨機器與人手操作仍屬人工觀察；實機 GUI 與 Chrome fixture 證據分列。
- [x] 對照瀏覽器版與桌面版的工作／設定／錯誤／語系／媒體頁：鍵盤與焦點、捲動、100／125／150／200% DPI、中文及空白路徑、資料夾選擇取消、開檔／顯示位置、圖片及影片 Range／播放、Blob 匯出、剪貼簿、外部頁與一般 Chrome 授權回接。以相同 viewport 截圖比較；訂明可接受的原生視窗／字型差異，不宣稱不同引擎逐像素相同。

2026-10-26 已新增 `tools/check_desktop_gui.py --matrix` 與 [D04 驗收指南](../testing/DESKTOP_GUI_ACCEPTANCE.md)。WebView2／Chrome 共用 UI 流程與 1280×800 CSS viewport 截圖、實際圖片／影片／Range、原生剪貼簿還原及瀏覽器 Blob 已通過；原生對話框回傳與檔案／外部分派明確標示為注入／攔截。四種 renderer scale 是 CDP 模擬，與使用者另外完成的實際 Windows 100／125／150／200% 縮放分列。人工已確認鍵盤／原生對話框與提示、中文空白路徑、開檔／位置／外部頁、覆寫與唯讀拒絕、桌面發起的 X／Pixiv 一般 Chrome 回接及後端重啟登入保留；第 2 輪關窗續留後端後，已清除隔離登入、正常停止 8877 並恢復連接器 8765。每個比例重新啟動、多螢幕 DPI、真實剪貼簿權限拒絕與未安裝 Runtime 的乾淨機器未測，詳見指南；D04 完成範圍如驗收指南。

#### D05：Windows 發行包與安裝版（實作／目前主機通過；乾淨機器待驗收）

- [x] 在打包前區分唯讀程式資源、使用者資料／登入／SQLite、cache／WebView profile 與使用者選擇的媒體目錄。開發版預設保持既有路徑；安裝版使用可寫使用者目錄並提供有備份與回退的明確遷移，不把資料寫進 Program Files 或 onefile 解壓暫存目錄，不因切換外殼就另建一份歷史／登入。服務／視窗互斥與擁有權識別須對齊同一資料 scope，不能因版本安裝位置不同而允許兩個 backend 共寫。需跨外殼保存的語言／清單偏好採有版本的中立資料格式或共用 API，不以複製 WebView2 profile 到 Electron 作為遷移機制。
- [x] 處理 `desktop_service` 與 `job_runtime` 目前依賴 `sys.executable -m ...` 的 frozen 相容性：定義 GUI／backend／下載 worker 的明確程序角色與啟動方式，避免 EXE 子程序遞迴開 GUI；驗證 FFmpeg／Node／下載引擎、靜態資源、Chrome 連接器、DLL 與 WebView2 Runtime 的定位、日誌與正常關閉。先做可檢查的資料夾型發行包，再評估單一 EXE。
- [x] 補上選配依賴與實際元件授權／對應原始碼、來源封裝 allowlist／排除規則、Windows 打包 CI，以及 README／架構／安裝／回復文件。使用 PyInstaller onedir＋每位使用者 Inno Setup；Node／FFmpeg 內附，WebView2 缺少時使用已校驗的 Microsoft bootstrapper。
- [ ] 在沒有預裝 Python／Node 的乾淨 Windows 10／11 驗收安裝、缺少 Runtime 的線上安裝／離線失敗處置、真人雙擊／捷徑／原生提示及安裝版 Chrome 授權，並在該環境核對更新保留資料、回退與解除安裝。目前無 Windows Sandbox，使用者確認沒有其他乾淨測試機；不把 PATH 隔離或目前主機當作乾淨 OS 通過。自動更新、簽章、托盤與開機啟動不在本階段。

2026-10-26 已在 Windows 10 build 19045 產生真正的 GUI／runtime EXE、資料夾 ZIP 與安裝程式；新程序以限定 PATH 驗證內附工具、實際 WebView2／bridge／HTTP 偏好、獨立 worker／Pixiv 管線、跨安裝位置共用資料 scope、DPAPI 合成登入／歷史恢復、正常停止，以及真實安裝／更新／回退／拒絕使用中程式／解除安裝保留資料。匯入先驗證及備份，SQLite 連線正常關閉後原子替換；中斷與明確回復均保留新舊資料。詳細範圍、指令及限制見 [Windows 發行指南](../deployment/WINDOWS_DISTRIBUTION.md)。本輪不實作 D06，也不建立公開 Release。

#### D06：Electron 遷移保留與成本控制

- [ ] 在 Browser／Pywebview 兩個 Adapter 通過後記錄 Electron 對應表：同一份 `static/` 與標準 HTTP API、同一個 Python backend／資料格式／授權流程，替換的部分是主程序、視窗生命週期、桌面 Adapter、後端啟動入口與打包。先保留設計與契約，待使用者決定再實作 Electron。
- [ ] 未來 Electron 以 preload／`contextBridge` 暴露相同 `DesktopInterface`；renderer 不直接拿 Node、檔案系統或任意 IPC。逐方法驗證參數、來源／frame 與能力，維持 `contextIsolation`／sandbox，透過同一個 Supervisor 控制協定管理 Python 子程序。重跑 Adapter 契約及真實外殼驗收；不承諾只改啟動檔即可零成本遷移。

實作順序為 **D01 → D02 → D03 → D04 → D05**；D06 是將來替換外殼的保留規劃。先交付可在現有 Python 環境執行的單視窗版本，再處理免裝 Python 的安裝包。每一步以獨立 diff／明確通過條件收斂，不為桌面化順帶重寫後端、導入前端框架或實作選配索引；所需時間與 token 在第一個 WebView2 原型驗證後再細估，避免把打包／真人授權排錯算成幾行外殼程式的成本。

技術依據：[pywebview 架構](https://pywebview.flowrl.com/guide/architecture)支援直接載入既有 HTTP 服務；[pywebview 官方文件](https://pywebview.flowrl.com/api/)說明 GUI 主執行緒、bridge 與 profile 設定；[Electron context isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation)及[安全建議](https://www.electronjs.org/docs/latest/tutorial/security)作為未來 preload／IPC 設計依據。上述後續階段為依本專案現況提出的工程規劃，官方文件不代表此專案已完成整合驗收。

## Source-package HTTP regressions — 2026-10-17

### Refused POST response coverage

Owned loopback tests verify unauthorized POST bodies receive 403 without JSON
parsing, saving or private-state reads. Cases cover foreign Host/Origin, opaque
Origin, cross-site fetch metadata and the connector attempting an unrelated API.
A gated handler writes 403 before a 64 KB invalid JSON body is delivered, making
the late-body order explicit without sleeps. Partial bodies, disconnected
clients, released slots and subsequent trusted requests are also covered.

The previously observed Windows 10053 has not been reproduced consistently,
including the new late-body fixture. No assertion hides a failed complete 403
exchange, and no production source policy or body-reading behavior was relaxed.
These are additional regression cases, not a claim that an intermittent socket
defect was conclusively fixed. Latest results: [TESTING](../history/TEST_RESULTS.md).

2026-10-17 follow-up: a complete run encountered 10053 again on a foreign-Origin
POST. Response handling now drains only an unread, strictly framed body up to
100,000 bytes, after sending the refusal, within 0.1 seconds and the original
deadline. It does not parse JSON or access application data. Ambiguous/oversized
frames are not read. The late-body test asserts exact bytes; new tests verify
bounded incomplete cleanup and rejected framing. This addresses the unread-body
closure case while keeping other intermittent transport observations pending.
