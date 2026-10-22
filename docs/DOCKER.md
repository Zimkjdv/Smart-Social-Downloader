# Docker deployment

## Status and scope

The first four Docker roadmap items provide source configuration for an **experimental Linux amd64 deployment** (2026-10-21): a Python 3.12 Dockerfile, Compose file, separate data/cache/media storage, offline backup/restore, local readiness, host-Chrome pairing and browser file actions. Milestone 5's actual isolated image/FFmpeg/Node/context acceptance passes locally. There is no published prebuilt application image. See [runtime acceptance](DOCKER_ACCEPTANCE.md), [storage and recovery](DOCKER_STORAGE.md) and [X login/browser actions](DOCKER_LOGIN.md).

Docker Desktop was found off PATH; its initial WSL query timeout cleared after startup. **A real Linux amd64 build, all nine runtime/context checks and all 14 local Compose storage/network stages pass on 2026-10-21.** The service gate starts the actual entry, checks restart retention, backup/restore, failure recovery, local ports and origin policy. Component versions and fingerprints are in [TESTING](TESTING.md); fixture changes are in [service acceptance](DOCKER_SERVICE_ACCEPTANCE.md). Real downloads, Chrome login, another physical host and actual version migrations remain unaccepted. The commands below remain experimental operator procedures; see [ROADMAP](../ROADMAP.md#docker-化部署) for remaining release acceptance.

On 2026-10-22 the combined gate also passes **15 login/media stages** with invented
sessions, encrypted restart/key recovery and original-byte HTTP media reads. See
[interaction acceptance](DOCKER_INTERACTION_ACCEPTANCE.md) for the private key-volume
substitution and the remaining real host-secret/Chrome/browser checks.

The later [host-storage gate](DOCKER_HOST_ACCEPTANCE.md) adds eight actual host
bind/file-secret stages, including private Windows ACLs and restored encrypted
login, and passes locally on 2026-10-22. It records Docker Desktop's automatic
creation of missing source directories and validates rejection of invalid
directory keys. The optional [host Chrome gate](DOCKER_BROWSER_ACCEPTANCE.md) adds
seven stages for the shipped UI, keyboard selection, actual PNG/H.264 decoding,
playback/seek, refresh and missing-file recovery. Run `--browser` with host-only
Playwright and existing Chrome. Physical-host migration is currently deferred;
human connector/login, other codecs and actual version migration remain pending.

## Build inputs

| File | Responsibility |
| --- | --- |
| [`Dockerfile`](../Dockerfile) | Python 3.12 venv, Node 22, FFmpeg and non-root UID/GID 10001; application source stays root-owned |
| [`compose.yaml`](../compose.yaml) | Local build, loopback publication, init process, read-only root and three persistent volumes; offline maintenance profile |
| [`.dockerignore`](../.dockerignore) | Deny the build context by default; allow only named runtime source inputs |
| [`docker/entrypoint.py`](../docker/entrypoint.py) | Container listener and SIGTERM routing through existing application cleanup |
| [`docker/runtime.py`](../docker/runtime.py) | Required mounts, write-access preflight and exclusive data/media locks |
| [`docker/storage.py`](../docker/storage.py) | Stopped-service full backup and staged restore into empty volumes |
| [`docker/healthcheck.py`](../docker/healthcheck.py) | Bounded loopback readiness probe using the configured port |
| [`compose.login.yaml`](../compose.login.yaml) · [`docker/session_key.py`](../docker/session_key.py) | Optional external-key session persistence and one-time key creation |
| [`docker/debian.sources`](../docker/debian.sources) | Fixed Debian package snapshots with signature checking |
| [`requirements.lock.txt`](../requirements.lock.txt) | Shared exact Python package versions; Windows baseline plus accepted Linux amd64 install/compatibility check |
| [`tools/check_docker.py`](../tools/check_docker.py) · [`tools/docker_runtime_probe.py`](../tools/docker_runtime_probe.py) | Disposable source/context build and network-disabled synthetic runtime acceptance; never copied into the runtime image |

The official image identities were read from Docker Hub on 2026-10-21. Each returned index digest was compared with the downloaded manifest bytes, and a Linux amd64 descriptor was present. This verifies input identity, not image execution.

| Component | Official tag | Pinned image index digest |
| --- | --- | --- |
| Python | `3.12.15-slim-bookworm` | `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258` |
| Node | `22.23.3-bookworm-slim` | `sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392` |

### Why Debian rather than Ubuntu?

The [official Python slim image](https://github.com/docker-library/python/blob/master/3.12/slim-bookworm/Dockerfile) already provides Python 3.12 on Debian Bookworm. The [official Node image](https://github.com/nodejs/docker-node/blob/main/22/bookworm-slim/Dockerfile) provides a matching Bookworm build, from which the Dockerfile copies the Node executable and its license. This keeps the two runtimes on a common OS family and avoids adding a separate Python installation procedure. Ubuntu is also viable; it is not required for the application's current dependencies.

### Repeatability and updates

- Both base images use version tags **and digests**. The initial target is `linux/amd64` only.
- OS packages come from the Debian and Debian Security snapshots at `20261020T000000Z`. Snapshot metadata was reachable when the source configuration was written. Historical metadata expiry is disabled with `Check-Valid-Until: no`; archive signatures remain required. This does not disable TLS or package signature verification.
- Python installs the shared exact pins using binary wheels, then checks package compatibility. It does not update dependencies on application startup. Linux amd64 wheel installation and `pip check` passed the isolated runtime gate; actual platform downloads and optional browser dependencies have separate acceptance requirements.
- A build records installed Debian packages, Python packages and the Node version under `/usr/local/share/ssdl/`.

This fixes component inputs and documents the procedure. It is **not an offline/hermetic build or a promise of byte-identical image output**: wheel hashes are not locked, upstream downloads must remain available, and builder metadata can differ. Record the source revision, any local modifications and the resulting image ID when accepting a build.

Pinned inputs need deliberate maintenance. Review new Python/Node digests, the Debian snapshot and Python pins together, then repeat container acceptance. `--pull` alone does not move a digest-pinned base to a newer release. See [maintenance](MAINTENANCE.md).

## Prerequisites

- Docker Engine with Compose V2, or Docker Desktop in Linux-container mode.
- A Linux amd64 target. Other architectures are not included in this first phase.
- Network access to Docker Hub, PyPI and Debian Snapshot while building.
- A free host port, initially 8765. Stop the native service or select another port if it is already running.

Host Python, Node and FFmpeg installations are not used by the image. Installation of Docker itself is outside this source change.

## Operator procedure — acceptance pending

From the extracted project root:

```powershell
docker version
docker compose version
docker compose config
docker compose build --pull
docker compose up -d
docker compose logs --tail=100 downloader
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Compose builds the local `smart-social-downloader:docker-preview` image; this name does not identify a published Docker Hub image. Its build policy prevents treating that application name as a remote image to pull.

To use a different port in PowerShell:

```powershell
$env:SSDL_PORT = "8876"
docker compose up --build -d
```

For a POSIX shell:

```sh
SSDL_PORT=8876 docker compose up --build -d
```

Use the same environment value for subsequent Compose commands. Open [http://127.0.0.1:8876](http://127.0.0.1:8876) in that example. Choose an unprivileged port such as 8765 or 8876. The same port is used inside and outside the container so existing Host/Origin checks still match the browser address.

The dedicated container entry binds to `0.0.0.0` **inside the container**; Compose publishes to host `127.0.0.1` only. Native `app.py` still defaults to loopback. The download source's public-address policy is unchanged. Host/Origin validation is not broadened: loopback hostnames with the configured port are allowed; an untrusted Host/Origin or cross-site browser request is rejected. Do not add wildcard hosts, host networking or proxy headers to work around a port mismatch.

This is a local service without remote authentication. Docker/network administrators and other containers granted network access are part of the host trust boundary; Host/Origin checks do not authenticate arbitrary network clients. LAN/public access and reverse proxies remain outside the supported configuration. Use a current Docker engine; loopback publication's isolation also depends on the host's Docker/network configuration.

## Health and readiness

`GET /api/health` uses the same local Host/Origin checks as other read APIs. Its response contains only a service marker, health status and four booleans: application lifecycle, queue-worker thread, persistence status and cached required-dependency diagnostics. It returns HTTP 200 when all are ready, otherwise 503. It does not enumerate downloads, disclose paths/session state, start environment commands, access a platform or count against Rate.

The Dockerfile configures a **30-second** interval, 3-second socket probe timeout, **5-second** Docker timeout, **60-second** start period and three failed probes before unhealthy. The Python probe connects directly to `127.0.0.1:$SSDL_PORT`, bypassing proxy environment variables and refusing oversized/unexpected responses or redirects. Use `docker compose ps` to see the result.

An idle or paused queue can be healthy. A failed individual download or a platform cooldown does not make the whole service unhealthy. Required dependency failures, a dead queue worker, shutdown or a recorded persistence failure do. This is a cached readiness signal; it does not continuously recheck free disk space/permissions or guarantee the success of a future platform download. Docker's restart policy handles process exits; it does **not** automatically restart a running process merely because it becomes unhealthy. Inspect logs and diagnose the cause first.

## Paths and stopping

| Compose volume | Container path | Initial contents |
| --- | --- | --- |
| `app-data` | `/app/data` | Settings, history, databases and state backups |
| `cache` | `/app/cache` | Disposable thumbnails and XDG engine caches |
| `media` | `/downloads` | Downloaded media |

Mounts must be present and writable as UID/GID 10001. The root filesystem is read-only; `/tmp` is private temporary storage. Startup checks access and holds exclusive data/media locks until application cleanup finishes. It refuses interrupted restoration or concurrent ownership. Backup/restore, existing-volume permissions, upgrades and recovery procedures are in the [storage guide](DOCKER_STORAGE.md); physical-host and actual-version migration acceptance remains pending.

Native Windows history, Cookie storage and downloads are not imported automatically. Settings paths refer to the **container filesystem**, not Windows drive letters. Docker confines download destinations to `/downloads` and its subdirectories, including paths read from saved history; moving existing native settings into the data volume is unsupported.

```powershell
docker compose down
```

This stops the service and retains named volumes. Starting with the same Compose project name attaches them again. Removing volumes deletes their stored data; it is not part of the ordinary stop procedure.

Compose uses an init process, forwards termination and allows 120 seconds before forced stop. The entry maps SIGTERM to the existing application cleanup path. A paused synthetic queue, settings/history, original bytes and partial media survive real graceful stop/restart in the local service gate. Active platform-download shutdown and its child-process cleanup still require separate acceptance.

## Feature boundaries

The recipe installs the ordinary backend/UI, download engines, FFmpeg and Node. Public URL compatibility still depends on the platform and extractor.

- Chrome, Playwright and desktop media viewers are not installed. Dynamic JavaScript capture remains optional future container work.
- Linux uses memory-only X login by default, with optional external-key AES-GCM persistence through a Compose secret. Pairing uses the existing connector in host Chrome; see [setup and recovery](DOCKER_LOGIN.md). Invented session/restart and media HTTP acceptance pass the [interaction gate](DOCKER_INTERACTION_ACCEPTANCE.md), with actual host file secrets/backup recovery covered by the [host gate](DOCKER_HOST_ACCEPTANCE.md). Real Chrome pairing and browser playback remain pending.
- File actions use browser playback/viewing and a paged job file list. A container does not launch the host's player or file manager. Native Windows keeps its desktop actions; browser codec support can differ.

To inspect a build's recorded versions:

```powershell
docker compose exec downloader cat /usr/local/share/ssdl/os-packages.txt
docker compose exec downloader cat /usr/local/share/ssdl/python-packages.txt
docker compose exec downloader cat /usr/local/share/ssdl/node-version.txt
docker compose images
```

## Source and distribution boundaries

The context allowlist excludes local history, downloads, `.git`, `.venv`, environment files and common credential file formats. Dockerfile copies explicit runtime sources rather than the whole workspace. Keep private files outside allowed source paths; a filename allowlist cannot detect secrets pasted into ordinary source code. Compose does not mount the Docker socket, browser profile, home directory or Cookie exports.

The source ZIP includes these recipes and this guide, not an image or installed runtimes. A locally built image contains third-party binaries, including Python, Node and FFmpeg. Their licenses remain applicable: retain installed Python/package licenses, Debian copyright files and the copied Node license. Before publishing an image, review the actual included versions, notices and applicable source/redistribution obligations; see [third-party notices](../THIRD_PARTY_NOTICES.md). This source milestone does not claim that image distribution review is complete.

## References

- [Docker build practices and image pinning](https://docs.docker.com/build/building/best-practices/)
- [Compose service configuration](https://docs.docker.com/reference/compose-file/services/)
- [Build context and ignore rules](https://docs.docker.com/build/concepts/context/)
- [Debian Snapshot](https://snapshot.debian.org/)
