# Regression and acceptance tests

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

See [host gate procedure and scope](DOCKER_HOST_ACCEPTANCE.md).

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
and fixture differences: [interaction acceptance](DOCKER_INTERACTION_ACCEPTANCE.md).


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
remain in [ROADMAP](../ROADMAP.md#docker-化部署). Fixture substitutions and commands
are in [service acceptance](DOCKER_SERVICE_ACCEPTANCE.md). Remote CI results are
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
playback acceptance. Those remain in [ROADMAP](../ROADMAP.md#docker-化部署).
The native service, installed production packages, history and login were not
used or changed. Commands and limits are in [Docker acceptance](DOCKER_ACCEPTANCE.md).

## Dependency fault tracking and HTTP-error resource cleanup — 2026-10-21

**289 Python tests pass in 94.336 seconds / 23 Node tests pass; zero skips**, from the verified source ZIP. The same extraction then passes the new **116-case** gate in **69.609 seconds**, retaining only the reviewed SSL observation and no resource warnings/unexpected faults. The allowlist contains **164** source members; exact source bytes/CRC, **84** Python syntax checks, **335** local documentation links, `pip check` and the six-reference workflow policy pass. Deferred Downvid research stays outside the source/export/commit. The pushed revision's two Windows CI jobs are verified separately.

The new gate's first complete run executed **116 cases** with no test failures/skips but correctly failed on **two socket ResourceWarnings** during delegated-HLS missing-fragment cleanup. A one-case forced-GC/tracemalloc reproduction attributed allocations to requests/urllib3; closing the delegated engine alone retained both warnings, while closing released HTTP-error responses removed them. The permanent actual-stream regression failed before the fix and passes afterward, preserving missing-fragment failure and request-count assertions.

The fixed gate passes **116 cases in 70.078 seconds**, including 30 repetitions of each foreign-source/CORS and delayed-body 403/recovery acceptance case. It records one precisely reviewed SSL deprecation, with no ResourceWarnings or unexpected faults. Local environment: Python **3.12.10**, OpenSSL **3.0.16**, yt-dlp **2026.8.19**, gallery-dl **1.32.16**, requests **2.34.2**, urllib3 **2.8.0**, Playwright **1.63.0**, pyee **13.0.1**; the existing local pycryptodomex remains **3.24.0**. No production package update was performed; CI installs the reviewed **3.24.1** pin independently.

**27 focused cases pass**, including 13 tracking contracts, five response/engine-ownership contracts and nine source-release contracts. A real owned unclosed socket proves the gate fails; synthetic wrapped 10053, a later success after a failure, subtest failure, skipped coverage, background/unraisable exceptions, import warnings, overflow, stale-report interruption and hook restoration are covered. A final one-case UserWarning injection exposed nested stream warning capture hiding a new observation; forwarding non-resource categories fixes it and the added real-case regression requires the outer gate to fail. Response tests preserve readable bodies and weak error ownership, close each response/engine once, continue other response cleanup after a close failure, retain rate limiting and leave borrowed sessions open.

The SSL observation remains upstream behavior, not a fixed TLS defect. Numeric 10053 injection verifies classification; complete local exchanges protect the earlier refusal cleanup fix, without claiming all native Windows aborts are fixed. Reports exclude raw messages, URLs/headers, absolute paths and subtest/skip text. No production history/Cookie, real X session or external platform media was used. See [Dependency faults](DEPENDENCY_FAULTS.md) for report/exit rules and upgrade procedure.

## First dependency proposal acceptance — 2026-10-21

**271 Python tests passed in 92.336 seconds / 23 Node tests passed; zero skips.** The full suite ran from a verified source ZIP using the interpreter from the newly installed candidate venv, with pycryptodomex **3.24.1**, Playwright **1.63.0** and pyee **13.0.1**. Existing original-byte, quality-selection, HLS/DASH missing-fragment, deduplication, worker, persistence, API and actual Chrome fixture cases remained enabled. The verified source contains **160** allowlisted members; **81** Python syntax checks, local documentation links, `pip check`, environment diagnostics and the six-reference offline Action policy pass.

The real Windows/Python **3.12.10** fresh-source/venv acceptance passes setup, offline batch startup, graceful restart, missing-marker repair, explicit update, exact-baseline restoration, optional browser installation, real isolated-console Ctrl+C with idle/active/restored queues and invalid-port rejection. Update selected gallery-dl **1.32.17**, then setup restored **1.32.16**; the separate IDNA **3.10 → 3.20** restoration probe also passed. This proves current-machine fresh-source/venv behavior, not a factory Windows desktop or real account/platform acceptance.

Additional one-off probes use only that receipt-gated owned fixture: deliberately install pycryptodomex **3.24.0**, confirm its inventory, run the shipped `update.bat` and require **3.24.1**, then run shipped `setup.bat` and verify every core/browser pin. Saved-state, synthetic original and partial-media hashes remain unchanged. Temporary fixture batch substitutions are restored byte-for-byte before source verification; the running production venv is not updated.

Resolve the exact proposed pyee **14.0.0** browser requirements with pip `--dry-run --ignore-installed --only-binary=:all:`. It fails with `ResolutionImpossible`, identifying Playwright's `pyee>=13,<14` constraint; the complete installed distribution inventory is unchanged. This agrees with proposal #2's original failing Windows job. Proposal #1's original green job predates the new installation/console checks, so the integrated revision requires both current Windows CI jobs after push. Review decisions, upstream sources and future Actions/browser gates are in [Dependency acceptance](DEPENDENCY_ACCEPTANCE.md).

Ignored local logs and JSON reports retain actual versions/results. Deferred Downvid research is excluded from the staged export, source ZIP and commit. No production state, Cookie/profile, live platform download, real X pairing or full CVE scan is part of this acceptance; remaining work stays in [ROADMAP](../ROADMAP.md).

## Windows console shutdown and recovery — 2026-10-21

**271 Python tests passed in 94.018 seconds / 23 Node tests passed from the extracted staged-source ZIP; zero skips.** Thirteen new offline console cases cover empty/overflow/shared console membership, admission before child creation, non-inheritable SIGINT handling, wrong receipts/unknown members, SYNCHRONIZE handle cleanup and PID reuse protection, refused native events, entry-factory restoration, hidden/new-console flags and explicit HTTP 201 expectations. The final focused installation/console run passed 26 cases. An earlier checkout run passed 270 Python tests in 94.311 seconds / 23 Node tests before the final membership-contract case was added; the full extracted run includes that case.

Real installation acceptance from the clean staged source also passed on Windows / Python 3.12.10, with **159** allowlisted source members and a new venv. It generated real CTRL_C_EVENTs in three owned hidden-console launches: idle, active synthetic worker plus pending job, and restored paused queue. The shipped entry, server, AppContext, scheduler, writer and worker supervision remained real; only platform transfer used a synthetic pipe-speaking worker/helper. Normal exit, closed writer/services, reusable port, terminated worker/helper handles, preserved original/partial bytes and exact restored IDs/attempts/pause/hourly limit/one consumed quota slot were checked before fallback outer Job Object cleanup.

The same run retained setup/offline startup, missing-marker repair, update/baseline restoration, optional browser pins and invalid-port rejection. The isolated update selected gallery-dl **1.32.17**, then setup restored the pinned **1.32.16** baseline; the IDNA **3.10 → 3.20** replacement probe also passed. The first sandboxed setup could not reach public PyPI (Windows 10013); the permitted-network rerun and final clean-source run passed. A blocked download was not classified as a missing package release or a passing test. Production packages/state/Cookies were not changed.

The clean source ZIP's member set/source bytes/CRC, 81 Python syntax checks, local documentation links, `pip check` and the six-reference workflow policy passed. Deferred Downvid research stayed outside the staged source/export and commit. This proves automated console-event handling on the current Windows environment, not factory Windows installation, physical keyboard/batch confirmation prompts, repeated interruption during native disk I/O or real account/media compatibility. See [Console acceptance](CONSOLE_ACCEPTANCE.md) and [ROADMAP](../ROADMAP.md).

## Windows installation acceptance and transport follow-up — 2026-10-17

**258 Python tests passed in 92.167 seconds; 23 Node tests passed; zero skips.** The focused HTTP/source/environment/installation run passed 38 cases. Thirteen new small installation cases cover isolated environment/pin parsing, receipt/admission guards, owned group failure/ordering, bounded command errors, foreign-service rejection, exclusive port reuse, setup/update markers and the check-only start route. One environment case requires DEVNULL stdin. Two new HTTP cases bound rejected-body cleanup and forbid draining oversized/ambiguous input; the existing gated late-body test now asserts exact discarded bytes.

An earlier 256-case run failed on the existing foreign-Origin POST with Windows 10053 before reading 403. Keep that failure as evidence; add strict framed/body-budget cleanup after emitting the response rather than suppressing transport errors. The final full run passes. An installed fixture also reproduced `pip check` hanging on inherited control stdin; tracing identified it and DEVNULL fixes the actual environment probe. Initial closed-port probes timed out in this Windows environment, so acceptance now requires successful exclusive rebind instead. Failed development runs are not counted as passing verification.

The real opt-in installer executes shipped batch files in an extracted source and brand-new venv, with independent graceful lifecycle and package restoration probes. This uses synthetic state/media, public dependency downloads, a custom loopback port and ordinary installed runtimes. Production history/Cookie/profile access, service restart, actual X sign-in and live platform media are outside the run. See [Installation acceptance](INSTALLATION_ACCEPTANCE.md) for actual phases, ownership and the fresh-source/venv versus bare-desktop boundary.

The actual installation run passed on Windows / Python 3.12.10 with all 156 source members, every core baseline pin, optional browser pins, offline start, missing-marker repair, settings preservation, graceful installed lifecycle and invalid-port rejection. `update.bat` resolved to the same current core versions as the baseline; the separate IDNA 3.10 → 3.20 probe demonstrated a real package replacement during restoration. Final base-interpreter admission with site startup disabled (`-I -S`) also passed a real batch-child/owned-cleanup smoke check.

The extracted-source gate passed **258 Python tests in 92.433 seconds / 23 Node tests**, zero skips. Thirty repetitions each of the complete foreign-Origin/CORS and delayed-body refusal cases passed (60 checks in 2.072 seconds); this is bounded regression evidence, not a guarantee against every Windows 10053. The final focused rerun passed all 38 cases, `pip check` and the six-reference workflow policy passed, and 79 Python syntax checks/local Markdown links validated. Source ZIP members, source bytes and CRC were verified. Successful installation logs/report remain ignored local evidence rather than source-package contents.

## Dependency and CI maintenance — 2026-10-17

**242 Python tests passed in 92.931 seconds; 23 Node tests passed; zero skips.** Windows / Python 3.12.10. The source allowlist validates **152 files**. Seven new cases cover reviewed full SHA/quoted scalars; mutable, abbreviated, dynamic, local, Docker and unknown references; flow/multiline/alias syntax; comment/error handling; both workflow extensions and canonical roots; missing workflows/CLI failure; and shipped policy/configuration. The focused policy/release run passed all 16 cases.

Official release tags and commit identities were checked separately through the GitHub API. The offline gate does not query GitHub, validate general YAML, authenticate a commit's provenance or scan for CVEs. Existing browser/capture, quality/streaming, IPC, persistence and SQLite regressions remain enabled. Update review and recovery are documented in [Maintenance](MAINTENANCE.md#dependency-updates-and-action-pins); Dependabot's first proposals and remaining real Windows/account/platform acceptance stay in [ROADMAP](../ROADMAP.md).

The extracted-source gate also passes **242 Python tests in 93.354 seconds / 23 Node tests**, zero skips, with all 152 members/CRC/source bytes verified. Offline policy, `pip check`, 76 Python syntax checks and local documentation links pass. The workflow now runs the offline pin gate before Node setup and retains the existing checkout and extracted-distribution regressions. No production service restart, personal history/Cookie read or live platform download was used.

## N08 shared fixtures and source distribution — 2026-10-16

**234 Python tests passed in 92.591 seconds; 23 Node tests passed; zero skips.** Windows / Python 3.12.10 / Node 24.19.0. The reviewed source allowlist validates **149 files**, including the test package, shared helpers and extracted-source acceptance tool. Eleven new cases cover independent fixture contexts, failure/worker/override cleanup, nested code and helper packaging, reparse parents, isolated nested discovery, unexpected/duplicate/changed archive contents, failed child commands and refused POST body/response/connection behavior. Existing Chrome, capture, HLS/DASH, IPC, quality, writer and SQLite cases remain enabled.

The extracted distribution passed the complete **234 Python tests in 91.829 seconds / 23 Node tests**, with zero skips. The command verified all 149 members, CRC and source bytes, checked import origins and ran both suites from the extraction. The first launch was blocked by a full C drive before execution; the successful run used an owned temporary directory on D. It uses current installed dependencies rather than a fresh OS or venv. CI now runs the same gate after checkout tests. Python syntax (74 source files), local Markdown links and `pip check` also pass. See [SOURCE_TESTING](SOURCE_TESTING.md) for boundaries, fixture ownership, commands and limitations.

CI follow-up: the first GitHub run on `464cc7e` failed four new release checks because Windows TEMP used the `RUNNER~1` short path while the packager returned canonical paths. Canonicalize both the release fixture root and the root passed to archive verification; add a noncanonical-root regression. The focused nine release checks pass, and the final extracted-source run passes **235 Python tests in 91.070 seconds / 23 Node tests**, zero skips. Source authorization, archive membership and reparse checks remain enforced. A new Windows CI run verifies the follow-up separately.

The gated 64 KB late-body request and full/partial/disconnected unauthorized requests pass without parsing the rejected JSON, mutating state or reading private summaries. Previous Windows 10053 remains unreproduced; no assertion suppresses a failed complete 403 exchange and production HTTP source/body handling is unchanged. No real Cookie/history read, production restart or live platform download was performed. N08 is complete; installation, real-account/platform/release acceptance and optional features remain in [ROADMAP](../ROADMAP.md).

## N07 SQLite diagnostics, backup and compaction — 2026-10-15

**223 Python tests passed in 90.368 seconds; 23 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates **143 files**, including the owned database service, UI controller, real SQLite acceptance module and [database maintenance guide](DATABASE_MAINTENANCE.md). Existing real Chrome/capture, streaming, quality, source policy, writer and capacity cases remain enabled. No production service restart, personal database/Cookie access or live platform media download occurred.

Nineteen new Python cases verify passive/missing-database behavior; physical size/freelist/count diagnostics without row/path leaks; complete pre-compaction backup and exact row/schema/media preservation; moved-file refetch behavior through all three real dedup stores; committed WAL snapshots and retained old backups; failure before VACUUM without partial publication; corrupt/unknown/locked databases; reparse paths and orphan journals; deadline/owned shutdown; partial compaction; WAL reader deferral; Unicode/space/URI characters in roots; Host/Origin and strict confirmation contracts; pause/active/busy/closing responses; and scheduler admission fencing. SQLite tests use real temporary files and native SQLite backup/VACUUM. Fault injection covers fsync, per-database failure and cancellation; no host-specific speed threshold is used.

Three new Node cases cover one confirmed submission, cancellation, concurrent clicks, report contracts, language switching, stale revisions, active-download button guards, health warnings and disposed late responses. A new real headless Chrome case opens the compaction dialog from Settings → Diagnostics, cancels with Escape and returns focus to its trigger, submits exactly one `{action: compact, confirmed: true}` request, and checks the translated backup result. A synthetic screenshot was inspected for the settings layout; it is ignored runtime output, not a public screenshot of a real account.

The source ZIP was built and each allowlisted entry and CRC checked against current sources. The maintenance service never deletes media or prunes dedup rows; backups do not bypass original-path verification. SQLite/index evaluation is complete in [DATABASE_MAINTENANCE](DATABASE_MAINTENANCE.md); actual indexed storage remains a future feature and N08 is the next P2 item in [ROADMAP](../ROADMAP.md).

## N07 account scan, IPC and state capacity — 2026-10-15

**203 Python tests passed in 89.881 seconds; 20 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates **139 files**, including `json_budget.py`, `measure_capacity.py`, the capacity acceptance module and [CAPACITY](CAPACITY.md). Existing real Chrome UI/capture, stream integrity, worker, source policy, quality, lifecycle and writer suites remain enabled.

Eleven new capacity cases cover byte-exact UTF-8/Unicode/escaping, early budget rejection, invalid JSON producing no IPC bytes, primary/backup preservation and smaller retries, oversized read/write protection, growth after stat, warning after save/restore, writer error preservation and recovery, real temporary account plans with deterministic cached-progress throttling, codec/scaled boundary probes, cleanup and source-package inclusion. A new runtime case exercises all four production child terminal paths (oversized result/progress/error/selection) through real pipes with a scaled budget, then runs another job. Two new Node cases cover capacity contracts, MiB size/warnings, save blocking/recovery and English translation. Existing queue tests also cover a capacity failure followed by another queued item.

The first full run caught an outdated measurement assertion: primary preservation now validates and copies the same bounded bytes, so `_read` is no longer called twice. Update attribution to `_read_contents` (two reads) and `json_encode_bounded`, retaining three schema validations/two atomic writes/two fsyncs. The corrected full run passed. No speed thresholds are asserted in CI.

After regressions finished, actual **64 MiB / limit + 1 byte** probes accepted exact-size state/IPC, rejected over-limit data, checked unchanged primary/backup content fingerprints and validated both reads, verified no partial IPC/temporary residue, and recovered with smaller history. Separate cached synthetic 5,000/50,000-post scans, 90,000 Unicode filename IPC and a three-sample 400,180-path full-history follow-up are documented with workload exclusions and slower bounded-encoding observations in [CAPACITY](CAPACITY.md). The source archive was built and its allowlisted entries verified.

Tests use temporary synthetic files and isolated helpers; no personal history/Cookie read, production service restart or live platform download occurred. SQLite diagnostics/backup/maintenance is completed by the subsequent milestone above; actual indexed metadata remains a future feature in [ROADMAP](../ROADMAP.md).

## N07 owned writer and durable barriers — 2026-10-14

**191 Python tests passed in 86.888 seconds; 18 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates 135 files, including `state_writer.py` and its new acceptance module. Chrome UI/capture, HLS/DASH, IPC, worker, source-policy, recovery and quality regressions remain enabled. Twenty-four new focused cases passed in 0.189 seconds; final writer/harness reruns cover idle snapshot release and recovered retry notices.

Tests cover immutable files/last-success/selection/pacing containers; passive construction/idempotent lifecycle; one in-flight/latest pending snapshot; checkpoint deadline, automatic flush and barriers; failure/dirty retention/manual recovery; invalid capture while an older write succeeds; future-backup and corrupt-primary preservation; independent contexts; closing producer guards/flush/join; all 13 route barrier locations; stop during startup persistence; account pause/stop during quota persistence without another charge. Real loopback requests read summary and cancel intent while native-write substitutes remain gated, and check critical replies do not return before release. No timing threshold is used for CI assertions.

The initial new fault case exposed an older accepted generation being misclassified after a newer capture failed. Waiting now checks whether an in-flight/pending accepted snapshot can still satisfy that barrier; the corrected case and all existing assertions pass. Review also found that a recovered store could retain an obsolete failure notice after a successful retry; it now restores the recovery notice and has a dedicated regression. Route-only no-op save mocks use generation zero or an explicit wait stub; production barriers retain strict generation validation and real save/API tests retain their durability checks. Idle writers release completed snapshots to avoid retaining a large history unnecessarily.

The same three-workload benchmark ran separately after full tests, with five samples per operation. At 400,180 paths / 20.29 MiB, capture median/p95 was 27.50/28.43 ms, snapshot retained/peak allocation 3,286,608/3,448,880 bytes, and durable save median/p95 862.53/868.75 ms. Contended summary median fell from 1,044.32 to 130.56 ms; pause/stop acknowledgement remained 1,856.81/1,901.52 ms because they wait for durable writes. Allocation excludes existing strings, other snapshots and serialization buffers; cProfile runs in the actual writer and is separate from latency timing. Details/limitations are in [PERSISTENCE_PERFORMANCE](PERSISTENCE_PERFORMANCE.md).

No personal Cookie/history access, production service restart or live platform media download occurred. Writer completion was a scoped N07 milestone; account/IPC/64 MiB capacity and SQLite maintenance are covered by the subsequent sections above. Actual indexed storage remains a future feature in [ROADMAP](../ROADMAP.md).

## N07 persistence measurement milestone — 2026-10-14

**167 Python tests passed in 86.091 seconds; 18 Node tests passed; zero skips.** Windows / Python 3.12.10. The reviewed source allowlist validates 133 files, including the new measurement tool, acceptance module and performance report. Existing Chrome UI/capture, HLS/DASH integrity, worker supervision, source policy, lifecycle and quality suites remain enabled.

Eight new cases validate synthetic counts and offline schema, nearest-rank statistics, real temporary primary/backup saves and summary/pause/stop acknowledgements, the gate at actual handler lock acquisition, failed-save rejection, owned writer/HTTP cleanup, RLock condition wait/notify semantics and source-package inclusion. They run the small workload and assert correctness, without machine-specific latency thresholds. The final focused rerun also passed all eight cases.

The full three-workload benchmark was repeated **separately after regression tests finished**, with five samples per operation. The 400,180-path / 20.29 MiB state saved in a median 927.67 ms (nearest-rank p95 1,267.31 ms). Contended summary/pause/stop acknowledgement medians were 1,044.32 / 2,057.78 / 1,930.42 ms. Measurements and cProfile-overhead limits are in [PERSISTENCE_PERFORMANCE](PERSISTENCE_PERFORMANCE.md).

No production service restart, personal Cookie/history access or external platform download occurred. Stop measures saved intent rather than actual subprocess termination; scan/IPC/64 MiB capacity and SQLite maintenance are outside this milestone. The writer was designed but not implemented at this first measurement; the follow-up above completes it, with remaining work in [ROADMAP](../ROADMAP.md).

## N06 frontend controller completion — 2026-10-13

**159 Python tests passed in 85.029 seconds; 18 Node tests passed; zero skips.** The source allowlist validates 130 files, including lifecycle and three new controller scripts. All seven real headless Chrome UI cases remain enabled, alongside synthetic Chrome capture, HLS/DASH, fault and child-process suites.

Eight new Node cases cover module loading without DOM/application globals, idempotent initialization/disposal, listener/timer cleanup, concurrent settings saves, closed settings ignoring late reads, old auto-close versus reopened drafts, disposed diagnostic reads/search debounce, object URL cleanup, and closed job details ignoring late responses. Existing offline recovery, snapshot ordering, uncertain writes, draft/scroll/language and connector tests still pass. Two new real Chrome cases cancel/confirm Rate without duplicate writes and page through 120 filenames before sending the exact selected index/name once.

Preliminary browser fixture runs exposed an ambiguous open-media selector and a keyboard assertion appended to the wrong test while adding coverage; the final run uses the action icon explicitly and retains the keyboard assertion in its original cookie-field case. Production focus and mutation assertions were not disabled. New controller lifecycle guards are covered by the Node cases.

No personal Cookie access, live platform download or backend service restart was performed. The page preserves its UI/API behavior and normal 30-second/active 2-second polling. N06 is complete; remaining work and platform/installation acceptance are in [ROADMAP](../ROADMAP.md).

## N06 download adapters and orchestration — 2026-10-13

**157 Python tests passed in 84.218 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12. The source allowlist validates 126 files, including seven new implementation modules and `test_media_architecture.py`. Ten new boundary/account tests passed in 0.190 seconds; focused manifest (7) and all-quality (10) suites also passed.

- Shared source/error/entry-point identity and gallery configuration lock; all implementation modules are included in the source allowlist and do not import the media facade.
- Engine routing and unsupported-video fallback; existing partial files prevent another fallback attempt. Original images bypass gallery/video and retain best/original mode; X credentials are stripped from other platform configuration. Public X posts use the dedicated service, and account links still require login.
- Replacement of the active request-policy object reaches paced HTTP and HTTP 429 backoff. Existing real child-process IPC, cancellation, no-progress/capture supervision, guarded HLS/DASH, missing-fragment failures and decoded stream acceptance remain in the full suite.
- Synthetic X timeline with real temporary ProfileArchive storage: scan total before transfer, completed post reuse without another transfer, moving one file refetches only its missing expected path, incomplete scans start no downloads, partial results retain error/files and do not mark the post complete, and temporary scan handles/shared lock are released.

An AST comparison of 29 moved top-level functions/classes against the previous commit matches after reversing the explicit dependency qualifications. This is an additional check against unintended extraction edits, not proof of all behavior. The first full attempt caught two missing imports in relocated browser test mocks; the passing run includes those corrections. Existing library socket ResourceWarnings remain tracked under dependency maintenance; assertions were not disabled.

No live platform media or personal Cookie values were used. Public entry points, API fields, archive/runtime locations, original-byte behavior and quality selection remain compatible. Frontend splitting was pending at this milestone and is completed in the follow-up above; current pending work remains in [ROADMAP](../ROADMAP.md).

## N06 state ownership and lifecycle — 2026-10-11

**145 Python tests passed in 83.787 seconds; 10 Node tests passed; zero skips.** Windows / Python 3.12, using temporary storage and synthetic browser pages. The source allowlist now validates 118 files, including `ssdl/app_context.py` and `tests/test_app_context.py`. The final focused lifecycle follow-up passed all 11 cases in 0.403 seconds.

The new acceptance cases verify fresh-process entry imports and context construction without login/history restore or thread startup, independent queue/pacing/services/locks/handlers, idempotent start and close, binding failure without migration, paused queue/settings/quota recovery into a new context, owned helper shutdown, rejection of pairing after auth shutdown, suppression of late login retry callbacks, and closing one running context while another worker continues. Queue/auth (17), P2 (13), HTTP framing/admission (11), environment (5), source policy (3) and diagnostic (3) focused suites also passed. A final startup-failure guard avoids joining unstarted helper threads and clears a worker that could not start; the expanded lifecycle suite passed 13 cases in 0.405 seconds.

One preliminary source-policy fixture call ended with Windows 10053 while a POST was rejected before its body was read; the focused retry and both full runs passed. This intermittent transport behavior is recorded for additional fixture/response coverage in N08; it was not suppressed by changing assertions or source authorization.

The application factory retains the existing production root, API fields and connector ID. Acceptance creates isolated application instances; it does not restore the user's actual X session, download live platform content or claim full Windows installation acceptance. Engine splitting was pending at this milestone and is completed in the 2026-10-13 follow-up above; current remaining work stays in [ROADMAP](../ROADMAP.md).

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

Tests use temporary storage and synthetic sessions, without reading real Cookie values or downloading external platform media. Local deployment checks are recorded separately in [CHANGELOG](../CHANGELOG.md#unreleased): the idle service restarted healthy, retaining 25 completed jobs, hourly limit 80 and the connected X session. Remaining architecture, performance and environment acceptance stay in [ROADMAP](../ROADMAP.md).

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

These probes originally exposed missing regression coverage. N01–N05 are now fixed and covered above. Completed fixes are recorded in [CHANGELOG](../CHANGELOG.md#unreleased); architecture suggestions and unmeasured performance risks remain pending in [ROADMAP](../ROADMAP.md#本輪整體審查).

## Earlier audit record — 2026-10-11

**104 Python tests + 10 Node tests passed, with zero skipped tests** on Windows, Python 3.12.10, Node.js 24.19.0, installed Google Chrome and Playwright 1.63.0. Python execution took 52.765 seconds. This reruns the earlier 59 Python/8 Node baseline, adds P2, quality and optional browser coverage, and checks the six reproduced fixes in the [project audit](PROJECT_AUDIT.md); it is not a claim that every live platform works.

Tests use synthetic URLs, data and HTTP/API fixtures, temporary directories and fresh headless Chrome contexts. The public-address network tests route checked synthetic numeric addresses to an owned local fixture. They do not disable the production network policy. No ordinary Chrome profile, real login Cookie, actual user history or platform download is used.

Additional local checks pass: 47 Python files parse, 15 JavaScript/CJS files pass `node --check`, `pip check` reports no broken requirements, and English/Traditional Chinese each have all 626 locale keys. Local documentation links resolve. The allowlisted source archive contains 113 files with matching source bytes and valid ZIP CRC; runtime folders are absent. These checks do not replace staged-file review after Git initialization.

## Reproduce

The latest local run is listed at the top. The repository has passing Windows CI history; verify each new commit separately. Local results are not GitHub CI results.

From the project root after `setup.bat`:

```powershell
python tools/manage.py browser-setup
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/package_source.py --check
.\.venv\Scripts\python.exe tools/check_source_archive.py
```

Install ordinary Chrome for browser coverage. Without Playwright/Chrome, browser tests explicitly skip and the result is **not full browser acceptance**. GitHub CI uses only Python 3.12, installs the optional package and asserts Chrome exists before running the suite. This matches the local project baseline. Runner image updates can affect Chrome availability; the workflow requires it explicitly.

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
