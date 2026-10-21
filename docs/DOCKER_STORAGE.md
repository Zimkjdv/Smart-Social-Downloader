# Docker storage, backup and recovery

This guide accompanies the [Docker deployment configuration](DOCKER.md). **Real local Compose storage/network acceptance passes on 2026-10-21:** new/existing named volumes, permission failures, restart retention, offline backup, corrupted/nonempty restore rejection, interrupted promotion refusal, transported-backup recovery and retained-image selection. See the [14-stage service gate](DOCKER_SERVICE_ACCEPTANCE.md) and [evidence](TESTING.md). The fixture uses independent projects on one engine and a named backup volume; the newer [host gate](DOCKER_HOST_ACCEPTANCE.md) covers actual private host binds and restored encrypted login. A second physical host and actual cross-version migrations remain unaccepted. Keep the source revision, local modifications and image ID with each installation's records. For host-Chrome pairing, memory-only login and a separately backed-up optional encryption key, see [Docker login](DOCKER_LOGIN.md).

## Storage contract

| Volume | Mount | Lifetime and contents |
| --- | --- | --- |
| `app-data` | `/app/data` | Durable settings/history, SQLite dedup records, state backups and optional encrypted session bytes; no encryption key |
| `cache` | `/app/cache` | Persistent but disposable thumbnails and XDG engine caches |
| `media` | `/downloads` | Durable platform/account folders, completed media and partial downloads |

The three named volumes are scoped by the Compose project name. Keep using the same project name for normal restarts/upgrades. `docker compose down` retains volumes; deleting volumes is not a stop or upgrade procedure. The backup includes **both data and media**, so a restoration does not pair older history with unrelated media. Cache is excluded and regenerated.

Native mode keeps its existing `data/thumbnails` path. Docker sets `SSDL_CACHE_DIR=/app/cache` and `XDG_CACHE_HOME=/app/cache`; old caches under a phase-1 data volume are left untouched and become unused. Those legacy directories remain part of a data-volume backup until explicitly retired; only the separate new cache volume is excluded. Neither a Windows history import nor automatic path conversion is implemented.

Docker sets `SSDL_MEDIA_ROOT=/downloads`. Settings may select `/downloads` or a subdirectory. Startup rejects saved download/output paths outside that boundary, and settings reject such changes before creating a directory. The root filesystem is read-only, with a private 512 MiB temporary filesystem at `/tmp`. Temporary data is not backed up. Large engine operations that need more temporary space require separate capacity acceptance before adjusting this limit.

### Ownership and permissions

- The image and maintenance tool run as **UID/GID 10001**, without extra Linux capabilities. New data/cache directories have mode 0700; the initial media directory has mode 0750. The container entry uses umask 0077 for new files and directories.
- Docker's empty named volumes inherit the image's directory content/ownership. Existing volumes keep their ownership; startup does not silently recurse through media to change owners.
- Startup requires all three mount points and checks effective write access. A bad mount/permission fails startup with an explanation, rather than silently storing data in the container layer.
- Downloader and maintenance processes acquire exclusive locks on data and media. A second writer or backup/restore while this edition of the service holds the volumes is rejected. This is a cooperative process lock, not protection against a host administrator or another program that ignores locks. Do not share writable volumes across installations.
- Linux bind-mount operators must pre-create only the intended directories with owner 10001 and restrictive permissions. Do not make them world-writable. Default named volumes avoid host directory ownership setup for runtime data.

## Prepare a backup destination

Backups contain private history and media. Use a private local directory with sufficient space for **all data plus media**, and keep complete backups separately from the Docker volumes. The checksum detects accidental corruption; it does not authenticate who created a backup.

The uncompressed tar format supports large media without a fixed per-file size cap; each backup is limited to 200,000 directory/file entries. Creation and restoration read the archive for checksum verification, so budget additional disk I/O and destination capacity. A failure does not automatically delete old snapshots to free space.

The maintenance profile bind-mounts `${SSDL_BACKUP_DIR:-./backups}` at `/backups` with `create_host_path: false`. Pre-create and verify the intended private directory: Docker Desktop can still create a missing source directory, as recorded by the [host gate](DOCKER_HOST_ACCEPTANCE.md). `backups/` is excluded from Git and from the Docker/source context allowlists.

On Windows, create the default directory from the project root (Docker Desktop needs access to it):

```powershell
New-Item -ItemType Directory -Force .\backups
$backupDirectory = if ($env:SSDL_BACKUP_DIR) { $env:SSDL_BACKUP_DIR } else { '.\backups' }
if (-not (Test-Path -LiteralPath $backupDirectory -PathType Container)) { throw 'Backup directory is missing.' }
```

On Linux, create that specific directory for the container user:

```sh
sudo install -d -m 0700 -o 10001 -g 10001 ./backups
```

For another location, set `SSDL_BACKUP_DIR` to its absolute path in the shell used for Compose commands. Keep the same `SSDL_PORT`, `SSDL_IMAGE` and Compose project selection throughout an operation. The maintenance profile uses the already built application image, no network and no Docker socket.

The examples below use the base Compose file. If encrypted X persistence is
enabled, keep **both** `-f compose.yaml -f compose.login.yaml` on downloader
stop/start/build commands, especially when resuming after backup or restore.
Storage maintenance itself needs no key and can use the base file alone.

The [eight-stage host gate](DOCKER_HOST_ACCEPTANCE.md) verifies real host backups,
file-secret permissions and restored encrypted login locally. The earlier
service gate's named-backup-volume substitution does not limit this newer gate.

## Make a complete offline backup

1. Pause the queue in the UI. Wait for active work to finish if possible. Stop the service gracefully, keeping the volumes:

   ```powershell
   docker compose stop downloader
   docker compose ps -a
   ```

2. Confirm the downloader is stopped, and stop any other program that writes these volumes. Run the offline tool:

   ```powershell
   docker compose --profile maintenance run --rm --no-deps storage backup
   ```

   It writes `ssdl-<UTC timestamp>-<random id>.tar` and a matching `.tar.sha256`. Both files are required. A `.partial` file or an archive without a complete sidecar is not a finished backup. The tar contains a small format/application-version manifest and ordinary directories/files from both volumes; the separate cache volume and process lock files are excluded. Symbolic/hard links and special files are rejected. The helper does not print archived names or Cookie values.

3. Check that the command succeeded and both files exist. Record the source revision/local changes, application version and image ID outside the volumes. Preserve the matching local image before an upgrade. After a successful backup, resume the same installed image:

   ```powershell
   docker compose up -d --no-build --pull never downloader
   docker compose ps
   ```

A graceful stop cancels active work through the ordinary cleanup path. A restored pending queue can resume when the service starts; a backup does not mark partial downloads complete. An abrupt kill is not a substitute for a consistent offline backup. Lock checks cannot coordinate old/custom services without the shared lock protocol.

## Upgrade

1. Make the complete offline backup above **before changing source or image tags**. Retain the old source and image. For example, choose a unique local rollback tag:

   ```powershell
   docker image tag smart-social-downloader:docker-preview smart-social-downloader:before-upgrade-20261021
   docker image inspect smart-social-downloader:before-upgrade-20261021 --format '{{.Id}}'
   ```

2. Review the new source's state/backup compatibility and pinned dependencies, then build it with the downloader stopped:

   ```powershell
   docker compose build --pull downloader
   docker compose up -d --no-build --pull never downloader
   docker compose ps
   docker compose logs --tail=100 downloader
   ```

3. Inspect Docker health, settings, job history, an existing media file and the selected download location. Resume the paused queue only after these checks. A container's `healthy` state is a bounded readiness signal, not acceptance of a platform download or an upgrade.

Named volumes remain attached at the same container paths. Do not delete them or copy new empty defaults over their contents. Do not start an older application directly on state already changed by a newer version; use the pre-upgrade backup and matching old image instead.

## Restore or move to another Docker host

Restore only a backup you trust. Copy the **archive and sidecar together**, plus the matching source/image identity, to the private backup directory on the target host. Build/load the original matching application image first. The helper checks its backup schema and application version; a future incompatible format/version is rejected. Never restore Windows desktop paths as a Docker backup.

Restore to a **new Compose project**, so the existing installation's volumes remain available. Stop the old downloader before sharing a host port or moving the installation. In the following example, replace the fictional archive filename with the actual generated filename:

```powershell
docker compose -p ssdl-recovery --profile maintenance run --rm --no-deps storage restore ssdl-20261021T120000Z-012345abcdef.tar
```

Both new data/media volumes must be empty apart from their process lock. The helper verifies SHA-256, stages all files inside the destination volumes, rejects traversal/links/devices/duplicates, ignores archived ownership/modes and creates files privately as UID 10001. It then promotes validated content. Existing installations are never overwritten or automatically erased to make room.

**A failed restore is not a successful recovery.** Before promotion, original destinations stay empty; staged files are normally cleaned up. A crash during multi-volume promotion leaves a marker or staging directories that prevent service startup. Keep the backup and failed volumes for inspection, then restore again into another fresh project. Do not remove the marker and start with partial data. Promotion is not an atomic transaction across two volumes.

To restore the pre-upgrade image on the same host, select the retained tag before running the helper and starting the recovery project:

```powershell
$env:SSDL_IMAGE = "smart-social-downloader:before-upgrade-20261021"
```

After a successful restore, start that same project/image without rebuilding:

```powershell
docker compose -p ssdl-recovery up -d --no-build --pull never downloader
docker compose -p ssdl-recovery ps
docker compose -p ssdl-recovery logs --tail=100 downloader
```

On POSIX shells, use `export SSDL_IMAGE=smart-social-downloader:before-upgrade-20261021` for the corresponding selection. Use the same backup-era application image/source first, check history and media, then perform any later upgrade separately. Cache rebuilds on demand. Container paths remain `/app/data`, `/app/cache` and `/downloads` on the new host, so a normal Docker-to-Docker move needs no history path rewrite.

Keep the old volumes until the restored installation has been accepted. The procedure never runs volume deletion, automatic ownership repair or in-place rollback.

## Acceptance evidence and remaining work

Run `python tools/check_docker.py --service --report data/docker-service.json` to repeat the actual local matrix. It uses invented paused history/media and cleans only its receipt-owned resources. Runtime and all 14 service stages pass locally, including default/custom port, Host/Origin and real failed-save health transitions. Fixture substitutions, the same-engine transport limit and synthetic-upgrade scope are explicit in [service acceptance](DOCKER_SERVICE_ACCEPTANCE.md). Host-Chrome login, real platform-download shutdown, another physical host, bind-mount setup and actual version migrations remain on [ROADMAP](../ROADMAP.md#docker-化部署).

References: [Docker volume lifecycle/backup](https://docs.docker.com/engine/storage/volumes/), [Compose service configuration](https://docs.docker.com/reference/compose-file/services/).
