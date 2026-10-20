# Docker X login and browser file actions

Docker milestone 4 is implemented in source. **The isolated FFmpeg/Node/context container gate passes, but real Chrome pairing, encrypted restart and browser playback acceptance remain pending.** The runtime gate loads no saved login or application service. Follow [deployment](DOCKER.md) and [storage/recovery](DOCKER_STORAGE.md) first. Native Windows remains the primary accepted environment.

## Choose session storage

| Environment/configuration | Stored session | Restart behavior |
| --- | --- | --- |
| Native Windows default | Existing Windows DPAPI format in `data/x-auth.bin` | Restores for the same Windows user when DPAPI is available |
| Default Linux/container | Memory only | Connect again after the service restarts |
| Optional Docker login override | AES-256-GCM encrypted `data/x-auth.bin`, separate 32-byte key | Restores with the same external key and data volume |

The default container never writes a plaintext session file or creates a key beside the encrypted session. It can still use the Chrome connector and download accessible X media. UI settings and the pairing page show the actual storage mode. Other website sessions, Google/Apple passwords and unrelated Chrome cookies are not read.

Changing to memory mode does not delete an existing encrypted session from an earlier configuration; it is not loaded or overwritten by new in-memory connections. **Disconnect** removes both the active in-memory session and the saved encrypted session. Restoring a data backup can restore its saved session, so protect backups and disconnect/reconnect when intentionally revoking local saved access. Disconnecting the tool does not revoke X's own browser session.

## Pair host Chrome

1. Start the container, then open the tool in **ordinary Chrome on the Docker host**, using [http://127.0.0.1:8765](http://127.0.0.1:8765) or the configured port. Sign into X in that same Chrome profile.
2. In Settings → X sign-in, press **Connect Chrome**. The web UI opens a host-browser pairing tab; the container does not launch or inspect a host Chrome process/profile. If the popup is blocked, use the explicit pairing link shown in settings. If using another browser, open the tool/pairing page in ordinary Chrome.
3. On first use, select **Download Chrome connector**, extract the ZIP, open `chrome://extensions` in Chrome's address bar, enable Developer mode and load the extracted `chrome-extension` folder. This manual Chrome permission step is still required. The container's `/app/chrome-extension` path is not a host path.
4. Refresh the pairing page, then connect the signed-in X session. The connector's existing extension ID and permissions remain unchanged. It sends only the allowed X cookies directly to the selected loopback service; the web page never receives cookie values.
5. For a custom port, explicitly set that same number in the extension popup's local connection settings before connecting. Browser pages cannot silently select another cookie destination. Host and container ports still match.

The ticket is single-use, expires after ten minutes and is returned only by the explicit connect action, not normal status/history. The pairing page uses a URL fragment, so the ticket is not part of an HTTP request URL, and clears it after an attempt. The fallback link is removed when connection leaves the waiting phase. Cancel/disconnect and shutdown invalidate pending pairing. Existing callbacks retry failed X jobs after a successful connection; public downloads remain independent of login availability.

This works with the existing connector protocol. No Chrome/Playwright installation, browser profile mount, remote debugging port, Docker socket or host command bridge is required. Remote Docker hosts, public/LAN access and third-party OAuth application registration are not included.

## Optional encrypted persistence

The optional [`compose.login.yaml`](../compose.login.yaml) grants **only the downloader** a file-backed Compose secret at `/run/secrets/x_session_key`. The maintenance backup container receives no key. The key is not an environment-variable value or an image layer. Local Compose secrets are file mounts, not a managed encrypted key vault; protect the original host file with host permissions.

First build the current image using the base Compose file. Create the private key directory on the host:

```powershell
# Windows / Docker Desktop, from the project root
New-Item -ItemType Directory -Force .\.secrets
```

```sh
# Linux: the application/key generator uses UID/GID 10001
sudo install -d -m 0700 -o 10001 -g 10001 ./.secrets
```

Create a random key using the already built image and the base configuration (before enabling the override):

```powershell
docker compose --profile maintenance run --rm --no-deps session-key
```

The helper creates exactly 32 random bytes at `.secrets/x-session.key`, with private permissions, and never prints or overwrites key material. If a key already exists, it fails instead of rotating it. Linux Compose file-backed secrets retain host file ownership; the key must remain readable by UID 10001. Do not rely on `uid`/`mode` declarations to repair a file-backed secret. On Windows, keep the host directory accessible only to the intended user and Docker Desktop.

Stop the current downloader, then recreate it with the override:

```powershell
docker compose stop downloader
docker compose -f compose.yaml -f compose.login.yaml up -d --no-build --pull never downloader
```

Keep using **both Compose files** for later downloader creation/upgrades; omitting the override selects memory mode. For a different key directory, set `SSDL_X_KEY_DIR` to its absolute path for both generation and override commands. `SSDL_X_KEY_FILE` contains only the container mount path; do not supply raw key bytes through environment variables, settings, logs or Git.

Connect X again after enabling encrypted storage; an earlier memory-only connection was not saved. Diagnostics checks key access/encryption without reading actual cookies. A missing, unreadable or malformed configured key stops the pairing attempt with an explanation; it does not fall back to plaintext or silently claim persistence. Public media downloading remains available.

### Recovery and rotation

- Data/media backups contain the encrypted session but **not the key**. Keep a separate, private, offline backup of the key. Neither `.secrets/` nor generated backups are included in Git, source ZIPs or build inputs.
- To restore saved login on another Docker host, restore the matching data/media backup, supply the same key through the login override, then start the matching image. Restoring storage itself needs no key. Expired or revoked X sessions still require reconnecting.
- If the key is lost or different, existing ciphertext is not decrypted. Use the original key or reconnect under a new key. No automatic key rotation/migration is performed. The original encrypted file remains until explicitly replaced by a successful connection or removed by Disconnect.
- Stop the downloader before changing the mounted key. The process keeps one key in memory for its lifetime; restart to use a replacement. Preserve the old data/key backup if rollback is needed.

AES-GCM uses a fresh 96-bit nonce, a 128-bit authentication tag and a versioned authenticated envelope. The existing pinned `pycryptodomex` supplies the cipher. Windows DPAPI remains the native default, with its existing saved format. This protects saved session bytes at rest; a host administrator or a process with both the key and data can access them. This source milestone is not a cryptographic audit.

## Browser media and folder behavior

Container UI actions adapt to browser mode:

- **Play/view:** opens the selected recorded media file in a browser tab, sending the original file bytes. Playback depends on the browser's container/codec support; there is no conversion. Types without an inline MIME mapping are offered as downloads. A browser's save/download controls can retain the original file when playback is unsupported.
- **Folder:** opens that job's paged file list, even for a single file. Selecting a file opens it in the browser. This is a job file browser, not arbitrary host/container filesystem access.
- **Top storage button:** explains how to browse files from the job list. It does not claim to launch host Explorer/Finder.

Native Windows keeps the default-app and Explorer actions. A container cannot launch the host file manager without additional host software; no such command execution bridge is added here. Named Docker volumes are managed by Docker. If a host-folder workflow is needed later, review explicit bind mounts and host permissions separately rather than treating `/downloads` as a Windows path.

`GET`/`HEAD /api/jobs/<id>/content` requires the current file index **and exact recorded filename**. It checks the same Host/Origin policy as other read APIs, confines paths to the job/media root, opens regular files, rejects escaping paths and uses no-follow directory/file opens on Linux. At most four streams run concurrently; data is copied in 64 KiB chunks outside the queue lock. Single byte ranges and suffix/open-ended ranges return 206, invalid/multiple ranges return 416, and full reads return 200. Unknown `If-Range` conditions yield a full response.

Raw media uses fixed MIME mappings, no-store/nosniff headers and a sandbox policy; HTML/SVG/script content is not served as active application content. Request logging omits content-query filenames. A moved/deleted file, stale selection or read failure does not change job completion or block the download queue. File URLs are local access paths, not public sharing links.

## Pending acceptance

No new tests were added or run for this implementation. Real Windows regression, Docker secret ownership/default memory behavior, encrypted reconnect/restart, original/wrong/lost key handling, Chrome pairing/cancel/custom port, original-byte/Range playback and browser/native action behavior still require acceptance. They remain explicit in [ROADMAP](../ROADMAP.md#docker-化部署).

References: [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/), [PyCryptodome AES-GCM](https://www.pycryptodome.org/), [HTTP Range](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Range), [Chrome cookies API](https://developer.chrome.com/docs/extensions/reference/api/cookies).
