# Docker runtime acceptance

This is Docker roadmap milestone 5: build the reviewed image and check its FFmpeg,
JavaScript runtime and source boundaries. It does not replace the pending storage,
recovery, network, host-Chrome pairing or real-platform acceptance in
[ROADMAP](../ROADMAP.md#docker-化部署).

## Run the gate

Use host Python 3.12 and a working Linux Docker engine. No host Python packages,
FFmpeg, Node, application state or media are needed by this gate:

```sh
python tools/check_docker.py --report data/docker-runtime.json
```

Add `--service` to also run the [Compose storage/network/recovery matrix](DOCKER_SERVICE_ACCEPTANCE.md).
Add `--interaction` to include both that matrix and [login/media HTTP acceptance](DOCKER_INTERACTION_ACCEPTANCE.md).
Add `--host-storage` to include all of those plus [actual host binds/file secrets](DOCKER_HOST_ACCEPTANCE.md).
Add `--upgrade-from ../ssdl-before-upgrade` to independently build an older trusted
source directory and run [upgrade/backup rollback acceptance](DOCKER_UPGRADE_ACCEPTANCE.md).
That mode uses a local engine, disposable application volumes and invented history
after these runtime checks pass. The default runtime-only mode still mounts no
application volumes and starts no application service.

On Windows, the tool discovers Docker Desktop's installed CLI even when it is not
on PATH. If the engine endpoint is not selected by the environment:

```powershell
.\.venv\Scripts\python.exe tools/check_docker.py --host npipe:////./pipe/dockerDesktopLinuxEngine --report data/docker-runtime.json
```

`--docker` can select a different CLI executable. The tool uses an empty temporary
CLI configuration, preserving only the installed CLI plugin directory when
needed. It does not read personal registry credentials, change a saved context,
start Docker, configure WSL, log into a registry, push an image or publish ports.
Builds need public access to Docker Hub, PyPI and Debian Snapshot. An unhealthy or
unavailable engine fails the gate; it is never treated as a skipped success.

## What runs

| Check | Required evidence |
| --- | --- |
| Source selection | Shallow public runtime inputs only; reject linked/reparse paths, excessive source sizes and known private-key/Cookie-export/personal-path patterns |
| Build-context allowlist | Copy reviewed source into disposable staging; add invented state/media/.git/.venv/.env/Cookie/key canaries; build an independent audit stage whose copied files must exactly match the public allowlist (transport control files may be absent) |
| Runtime image | Build the unchanged staged Dockerfile's named `runtime` target for Linux amd64 and record its image ID |
| Isolation | Fresh UID/GID 10001 container; read-only root, no network, no application volumes, bounded memory/processes/CPU and one private 256 MiB scratch tmpfs |
| Dependencies | Python 3.12 base version, `pip check`, yt-dlp/gallery-dl availability and system `/usr/bin/ffmpeg`/`ffprobe` selection |
| JavaScript | Exact pinned Node version; yt-dlp's actual Node provider executes arithmetic/BigInt with its permission flags; installed EJS core/lib hashes match yt-dlp's reviewed hashes |
| FFmpeg | Generate one-second synthetic video/audio, merge with stream copy, inspect codecs/dimensions/duration, compare video and audio packet hashes before/after |
| Thumbnail | Generate a small JPEG from the merged synthetic video and check its format/size |
| Image contents | Expected `/app` roots, empty state/cache/media directories, no synthetic canary in application files; only venv's expected interpreter/lib links are allowed |
| Optional browser | Default image contains neither Playwright nor Chrome/Chromium; dynamic capture remains optional |

The context audit is appended only to the temporary Dockerfile and is removed
before building the runtime target. Its image and the runtime test image have
unique temporary tags. Cleanup removes only those tags and a container with the
matching receipt label. It never prunes caches, images or volumes or removes an
unrelated container. Failed image-tag removal may leave a temporary image for
manual inspection; it is not a deployment image. Cached build layers can remain.

The probe is streamed on standard input; it is not installed in the runtime
image. It creates no AppContext, restores no login and reads no Chrome profile or
production history. The JavaScript check uses internal interfaces from the
**pinned** yt-dlp release; review the probe when updating yt-dlp/EJS. It checks the
runtime bridge and installed scripts, without claiming that a live YouTube
challenge or any external platform currently works. The privacy checks cover the
reviewed source/context and expected image paths; they are not a general secret
scanner or vulnerability audit of downloaded packages/base images.

## Receipts and failures

`data/docker-runtime.json` is ignored by Git. It contains categorical check names,
component versions, the source/gate/probe SHA-256 and resulting image ID. It excludes
raw command output, exception messages, absolute paths, URLs, Cookie/key values
and synthetic canary values. A new incomplete receipt replaces an old success
**before** checking the engine. Only all checks plus owned-container cleanup can
set `passed: true` / `complete: true` and return exit code 0.

Exit code 1 means a check/build/engine/cleanup failed; 2 means the tool/report
could not run; 130 means interruption. `checks` lists successful stages before a
failure. `probe_error`, when present, is a fixed runtime-stage category. A
missing receipt or `complete: false` is never acceptance evidence. Report file
names must end in `.json`; within the project they must stay under `data/` to
avoid replacing shipped source. Do not run two checks into the same report path.

Each Docker command has a deadline (engine 30 seconds, each build 15 minutes,
runtime probe 4 minutes). The probe also bounds its media commands. A missing
daemon, registry/network failure, changed package API, failed synthesis or bad
receipt fails closed. Inspect Docker Desktop/engine status first; reproduce a
build failure with the documented [build procedure](DOCKER.md) when detailed
builder output is needed. On Windows, `DockerDesktop/Wsl/CommandTimedOut` means
Docker could not finish querying WSL distributions; the acceptance tool does not
restart WSL/services or change Windows features to work around it.

## CI and evidence boundary

The `docker-runtime` job in [checks.yml](../.github/workflows/checks.yml) runs this
gate with `--host-storage` on an Ubuntu 24.04 hosted runner with Python 3.12. Ubuntu is the **CI host**;
the image still uses the pinned Debian Bookworm bases. The job reuses reviewed
full-SHA checkout/setup-python actions, requires no registry credentials and
writes the categorical receipt to the job summary even on failure. It builds and
checks locally on that runner; it does not publish an image or deploy the app.

`tests/test_docker_gate.py` verifies source selection, synthetic audit assertions,
receipt rejection, failure/stale-result handling, isolation command arguments and
owned cleanup using fake CLI responses. These contract tests **cannot** prove
that Docker built an image, that `.dockerignore` actually filtered a context or
that Node/FFmpeg ran. Record those only from a real successful gate receipt.

Current local results and remaining limits are recorded in [TESTING](TESTING.md).
The workflow file being present does not mean GitHub has run it successfully.

### Primary references

- [Docker named stages and targets](https://docs.docker.com/build/building/multi-stage/)
- [Docker build and GitHub Actions](https://docs.docker.com/build/ci/github-actions/)
- [yt-dlp external JavaScript runtime setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [FFmpeg command reference](https://ffmpeg.org/ffmpeg.html)
