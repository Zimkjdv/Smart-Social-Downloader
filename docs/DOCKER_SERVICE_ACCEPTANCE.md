# Docker service, storage and recovery acceptance

This extends [runtime acceptance](DOCKER_ACCEPTANCE.md) with real disposable
Compose services, named volumes and offline backup/restore. It uses the accepted
runtime image rather than host Python packages or an existing installation.

```sh
python tools/check_docker.py --service --report data/docker-service.json
```

For Docker Desktop's Linux engine on Windows:

```powershell
.\.venv\Scripts\python.exe tools/check_docker.py --service --host npipe:////./pipe/dockerDesktopLinuxEngine --report data/docker-service.json
```

Use a local Docker engine and Compose V2. The service gate rejects remote TCP
engines because its HTTP checks connect directly to host loopback. The runtime
gate alone does not have this host-network requirement. The service gate creates
and deletes only uniquely named, receipt-owned fixture resources. No existing
Compose project, application volume, browser profile, Cookie or encryption key is
mounted. Do not reuse the report path for concurrent checks.

## Real acceptance matrix

Each successful run must contain the original **nine runtime/context checks** and
all **14 service stages** below. Fake CLI unit tests do not satisfy this matrix.

| Stage | Required result |
| --- | --- |
| `compose_contract` | Resolve the actual Compose file for default/custom ports; assert loopback publication, matching ports, three named storage mounts, read-only/init settings and network-disabled maintenance with a non-creating backup bind; inspect the built image's 30s/5s/60s/three-retry health configuration |
| `empty_volume_permissions` | New Docker volumes inherit UID/GID 10001 and data/cache 0700, media 0750; real mount/write preflight passes; the actual readiness probe fails before a service is listening |
| `default_port_readiness` | Start the actual container entry on port 8765, reach HTTP readiness and execute the actual readiness script successfully; stop gracefully before seeding invented history |
| `existing_volume_restart` | Start/recreate/restart with a matching custom port; a paused queued job, completed job, Rate setting, original bytes and partial media survive |
| `origin_policy` | Accept the configured local origin; reject foreign Host/Origin, cross-site requests and wrong-port origins; reject a download directory outside `/downloads` |
| `health_failure_recovery` | Revoke fixture data-directory write access, trigger a real failed save, observe HTTP 503 and Docker `unhealthy` while the process remains running without a restart; restore access and save successfully |
| `writer_exclusion` | Offline backup fails while the downloader owns the data/media locks |
| `permission_rejection` | Service startup fails with unwritable existing data storage; restoring permissions permits healthy startup |
| `offline_backup` | After a clean stop, the real maintenance command backs up complete data/media without modifying originals; inspect the SHA-256 sidecar and archive contents, excluding cache and process locks |
| `checksum_rejection` | A deliberately corrupted archive fails restore into fresh volumes and leaves both targets empty apart from locks |
| `interrupted_restore` | Terminate a real restore after the first volume is promoted; retain its marker/staging state and verify that normal application startup refuses it |
| `archive_transport` | Copy the good archive and sidecar out through the host and into a separate backup volume; the transported archive hash remains identical |
| `fresh_volume_restore` | Restore the transported backup into fresh data/media volumes; compare every fixture file's bytes and relative path with the offline source inventory; omit cache, reject a second restore over nonempty targets and start the recovered service |
| `retained_image_rollback` | Start a distinct synthetic upgrade image on the original volumes, stop it, then start the recovery project using the retained backup-era image; verify the exact image identity and restored history/media |

## Fixture changes and limits

The operator recipe is in [storage/recovery](DOCKER_STORAGE.md). For automated
acceptance, the gate resolves that exact Compose source into a disposable JSON
model, then changes only fixture deployment settings:

- Use the image just accepted by the runtime gate; remove its build setting and
  select `pull_policy: never`.
- Attach newly created external fixture volumes, a separate project network and
  receipt labels. Helpers have no network; the service uses a dedicated ordinary
  bridge so published-port behavior matches the operator recipe. Its synthetic
  queue stays paused, and no platform download is attempted.
- Use a fixture-owned named backup volume at `/backups` in place of the operator's
  private host bind. Root helpers initialize/import only this invented backup
  volume as UID/GID 10001. Runtime data/media and maintenance operate as UID 10001.
  Actual host bind permissions/sharing still depend on the deployment host.
- Set the fixture restart policy to `no` and shorten health intervals to one
  second/two retries. The original image's health defaults are checked separately.
  Shutdown uses a bounded 30-second graceful stop; exit code 0 is required.
- Prefer publishing default port 8765. If another service owns it, publish a free
  loopback port to the container's 8765 and send the canonical 8765 Host header.
  The receipt distinguishes this fallback as `isolated_ephemeral`; the gate never
  stops the existing listener. Custom-port acceptance uses matching host/container
  ports without that fallback. Free-port selection can race another process; a
  collision fails acceptance rather than replacing that process.

The upgrade fixture adds only a label to produce a distinct image identity. It
tests selection of the retained image and full-backup recovery, **not a migration
between two actual application versions**. Archive transport and recovery use
independent volumes/projects on the **same engine**. A second physical host,
different filesystem/architecture, bind-mount sharing or an incompatible future
application/database migration requires separate acceptance.

The interruption injection streams a probe into a fixture helper, intercepts the
real restore's directory sync and exits the child process abruptly after data
promotion. It changes no runtime source or production entry point. The interrupted
volumes remain blocked until fixture cleanup; recovery always uses fresh volumes.

## Results, ownership and cleanup

The ignored JSON receipt retains fixed stage names and errors, component/Compose versions,
the runtime image ID, runtime-source/gate/probe hashes and the service-source
fingerprint. It excludes archive names/content, fixture resource names, absolute
paths, raw builder/HTTP output and exception messages. New attempts replace old
successful reports before execution. All stages plus resource cleanup must pass
for exit code 0. `service_error` identifies the fixed last stage on failure;
`complete: false` is never success evidence.

Volumes are checked for the matching receipt label before use. Helpers reject
mounts outside the gate's created resource list. Cleanup verifies receipt labels
before removing containers, networks or volumes and refuses foreign resources.
There is no prune operation. Temporary image tags/build caches follow the runtime
gate's cleanup rules. An interruption of the host Python process may leave owned
fixtures for inspection; never use a broad prune to recover them.

The existing Linux CI job runs `--service` and includes its safe receipt in the job
summary. Current local evidence and scope are in [TESTING](TESTING.md). Storage and
network acceptance does not prove host-Chrome pairing, real X login, active
platform-download shutdown, browser playback or a complete deployment release.
Remaining work is listed in [ROADMAP](../ROADMAP.md#docker-化部署).

References: [Compose resolved configuration](https://docs.docker.com/reference/cli/docker/compose/config/),
[Docker volumes and backup](https://docs.docker.com/engine/storage/volumes/),
[Compose health checks](https://docs.docker.com/reference/compose-file/services/#healthcheck).
