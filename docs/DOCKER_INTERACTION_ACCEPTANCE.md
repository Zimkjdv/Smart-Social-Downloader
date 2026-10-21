# Docker login and media acceptance

This gate extends [runtime acceptance](DOCKER_ACCEPTANCE.md) and
[service/storage acceptance](DOCKER_SERVICE_ACCEPTANCE.md). Run from source with
Python 3.12 and a local Linux amd64 Docker engine with Compose:

```powershell
python tools/check_docker.py --interaction --report data/docker-interaction.json
```

`--interaction` includes the nine runtime and 14 service stages, then the following
15 stages. Linux CI uses the same command. The output is a categorical JSON receipt;
all stages and owned-resource cleanup must pass for exit code 0. On failure,
`interaction_error` identifies the last stage. A previous successful receipt is
replaced before the next attempt.

| Stage | Required evidence |
| --- | --- |
| `login_override_contract` | Resolve actual base/login Compose files; only the downloader receives the external secret at the exact configured path |
| `memory_pairing` | Real service reports memory/host-browser mode; accept an invented X cookie through the connector API; reject wrong/replayed tickets; no session file is written |
| `pairing_cancel_repair` | Disconnect invalidates the old ticket; issuing a replacement invalidates its predecessor; a new ticket connects |
| `memory_restart` | Gracefully stop/restart the actual service; login is disconnected and no session file appears |
| `private_key_generation` | Actual generator creates a 32-byte UID/GID 10001, mode 0600 key; a second call refuses to overwrite it |
| `encrypted_pairing` | Read-only runtime key mount; AES-GCM mode; invented login saves ciphertext with private permissions; fresh nonces and rejected tampered/truncated/invalid envelopes |
| `encrypted_restart` | Same key restores the session after actual process restart without changing ciphertext |
| `wrong_key_preservation` | Restart with another key; session remains disconnected, original ciphertext remains unchanged and public service stays healthy |
| `missing_key_preservation` | Restart without the configured key; saved bytes remain; pairing fails without plaintext fallback |
| `key_recovery_disconnect` | Restore original key, reconnect through saved ciphertext, disconnect, then restart; no saved or active login remains |
| `browser_file_actions` | Paged recorded-file API and browser open-file URL; container refuses native folder launching |
| `original_head_ranges` | Hash-identical PNG and generated MP4 bytes, fixed MIME/no-store/nosniff/sandbox headers, bodyless HEAD, single/suffix/open-ended Range, invalid-range rejection and If-Range fallback |
| `media_path_rejection` | Reject escaping symlink, mismatched index/filename, traversal selection and untrusted Origin |
| `moved_file_retention` | A renamed original returns 404; job stays completed and service remains healthy |
| `concurrent_reader_recovery` | Four held large responses fill reader slots; a fifth is refused, health remains responsive and closing clients releases the slots |

## Isolation and fixture differences

The gate uses the accepted runtime image and the existing receipt-owned Compose
fixture. It creates new data/cache/media/key volumes, a private project network
and free matching loopback host/container port. No production project, history,
download or real cookie is loaded. The invented queue is paused. Synthetic PNG,
FFmpeg-generated MP4 and a bounded 16 MiB slow-reader file have no external source.

Pairing HTTP requests emulate the existing connector protocol using an explicitly
invented cookie. Tickets and session bytes are held in process memory and never
printed or retained in receipts. This does **not** log into X or install/use Chrome.

Key generation runs the shipped helper on a separate owned volume. An initial
root helper only assigns that empty key directory to UID 10001; generation and
session operations use UID 10001. The fixture maps that key volume read-only to
`/run/secrets`, after renaming the generated file to the Compose secret target.
It checks the actual login override model separately. This deliberate substitute
avoids relying on host filesystem permissions: **actual host file-backed Compose
secret mounts, Docker Desktop directory sharing and second-host permissions
still require operator acceptance**. No production key is rotated.

The source probe is streamed into owned helpers and the fixture container; it is
excluded from runtime build inputs. The gate uses the real authentication manager,
encryption library, persistence and HTTP routes. It does not patch runtime code or
add a production test endpoint. Cleanup checks ownership labels and removes only
resources created by this attempt. There is no prune operation.

## Remaining human/environment acceptance

Real host Chrome installation/default and custom-port pairing, ten-minute expiry,
revoked/expired X login, actual browser playback/codec behavior, Windows default
player/Explorer interaction, host secret binds and physical-host/version migration
remain in [ROADMAP](../ROADMAP.md#docker-化部署). Synthetic protocol requests and
original-byte HTTP checks do not prove those interactions. Docker remains
experimental, with no published prebuilt image. See [test evidence](TESTING.md).
