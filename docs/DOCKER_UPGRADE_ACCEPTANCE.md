# Docker source upgrade and backup rollback acceptance

`--upgrade-from` builds a trusted older source directory and the current source
as separate images. It upgrades invented paused history, media, three SQLite
archives and an invented encrypted X session, then restores the original backup
into fresh volumes with the original image. It never mounts an existing
installation. See [deployment](DOCKER.md) and [storage recovery](DOCKER_STORAGE.md).

## Run

Extract the older trusted source distribution to a separate directory. Keep its
source revision and any local changes in your operator records. From the current
source directory, with host Python 3.12 and a local Linux amd64 Docker engine:

```powershell
python tools/check_docker.py --upgrade-from ../ssdl-before-upgrade --report data/docker-upgrade.json
```

On Windows, add `--host npipe:////./pipe/dockerDesktopLinuxEngine` if needed.
Combine with `--browser --pixiv` for the existing service, host-storage, Chrome
playback and synthetic Linux Pixiv matrices. Upgrade acceptance is opt-in; a
source ZIP needs no Git installation or historical checkout to run it.

Only explicitly allowlisted runtime source is read from the older directory.
The gate snapshots those bytes before building, uses an independent context
audit, and runs the current reviewed runtime probe against both images. Old
host-side tools are not executed. Build-time code in a Dockerfile or dependency
still runs, so use a source distribution you trust. Building needs the public
registries/package sources documented in the deployment guide.

## Checks

| Stage | Evidence |
| --- | --- |
| `distinct_source_images` | Different application-source fingerprints and image IDs; changing only a tag, Dockerfile label or license is rejected |
| `baseline_state_login` | Original image creates volume ownership, paused queue/history/media, three file-verified SQLite records and an AES-GCM session; generated key is separate and mounted read-only |
| `pre_upgrade_backup` | Original image's stopped-service backup includes data/media without changing originals; checksum and archive contents verified |
| `candidate_upgrade` | Current image opens those same volumes, preserves settings/history/queue/original bytes and encrypted session, and looks up the old SQLite records using current application modules |
| `candidate_restart` | Graceful stop/restart preserves the upgraded installation, readiness and verified records |
| `candidate_writes` | A settings change made through current HTTP survives another restart; upgraded volumes differ from the pre-upgrade snapshot |
| `matching_image_restore` | Original image restores its backup into independent empty volumes; complete byte inventory matches and all three SQLite records remain reusable |
| `rollback_restart_retention` | Restored old installation restarts with settings/login/records intact; upgraded volumes and original backup remain unchanged |

Receipt-owned resources are cleaned even on failure. The ordinary runtime gate
keeps the candidate image alive while a nested baseline runtime gate keeps the
old image alive. Each gate removes its own temporary tags/containers; Compose
fixtures require matching receipt labels before resource removal. No pruning or
in-place rollback is performed.

## Receipts and limits

`upgrade_checks` must contain all eight stages, `upgrade_baseline` must contain a
complete successful nine-check runtime receipt, and the outer receipt must have
`passed: true` and `complete: true`. Any source/build/runtime/cleanup failure
fails the combined gate. `upgrade_error` is categorical; raw commands, paths,
platform URLs, cookies and keys are excluded. The main gate replaces stale
success before starting, as described in [runtime acceptance](DOCKER_ACCEPTANCE.md).

`upgrade_versions` records the literal application versions and `version_changed`.
Different source revisions sharing a preview version remain **source revision
acceptance**. They cannot establish migration between released application
versions. Invented data and file-secret volume substitution do not establish
real OAuth, expired platform sessions, active platform downloads, or migration
to another physical host. Actual host-file secrets are exercised by the
[host-storage gate](DOCKER_HOST_ACCEPTANCE.md).

The original storage helper discarded file modification times. An old helper
restoring its own archive therefore fails the stronger SQLite reuse assertion.
Use a baseline with the timestamp fix backported when accepting a maintained
older source against current source, and record that local change explicitly.
Do not silently substitute the current restore helper or weaken the record
checks to make an unmodified older image pass. Old archives without nanosecond
metadata cannot reconstruct their original precision; restored media may need
to be fetched again under the existing verification rules.

Local evidence, including failed unmodified-baseline acceptance, is recorded in
[TESTING](TESTING.md). Human Chrome/OAuth, different application release versions
and another physical host remain in [ROADMAP](../ROADMAP.md#docker-化部署).
