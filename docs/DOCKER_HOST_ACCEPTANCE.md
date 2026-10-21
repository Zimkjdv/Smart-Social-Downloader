# Docker host bind and file-secret acceptance

This completes the local host-filesystem portion of Docker storage/login
acceptance. It uses actual host backup/key directories and the file-backed
Compose secret from the operator configuration. It does not substitute a named
key/backup volume. Physical-host transport, actual version migrations and real
Chrome/browser interactions remain separate work.

```powershell
python tools/check_docker.py --host-storage --report data/docker-host.json
```

Use Python 3.12, Compose and a local Linux amd64 Docker engine. On Windows the
gate discovers Docker Desktop's CLI; an explicit engine can be selected with
`--host npipe:////./pipe/dockerDesktopLinuxEngine`. Linux CI uses the same
`--host-storage` command. It includes the **9 runtime + 14 service + 15 interaction
checks**, then these eight stages:

| Stage | Actual evidence required |
| --- | --- |
| `private_host_directories` | Create a new private host directory, then separate key/backup directories; use protected Windows ACLs or the POSIX private parent |
| `host_bind_contract` | Resolve base/login Compose, retain actual host paths, network-disabled maintenance and `create_host_path: false`; map only new owned application volumes |
| `missing_bind_behavior` | Record native Linux rejection or Docker Desktop's actual automatic directory creation; any Desktop-created directory/file must inherit the private host ACL |
| `host_key_generation` | Actual maintenance command creates a 32-byte host key, refuses overwrite and keeps its hash unchanged; verify host privacy |
| `file_secret_restart` | Actual Compose file secret is a read-only bind at the configured target; UID 10001 cannot open it for writing; invented login restores after service restart |
| `host_backup_integrity` | Actual maintenance backup writes archive/sidecar to the host; checksum matches, ciphertext is included, external key bytes are excluded and original data/media/key hashes stay unchanged |
| `host_restore_login` | Restore that host backup into fresh owned volumes/project, compare complete inventories/settings/media, exclude cache and recover encrypted login using the same host file secret |
| `missing_secret_rejection` | Recreate with a nonexistent secret source; require Compose rejection, or on Desktop reject the invalid directory key through authentication; preserve original key/session/media |

## Host permissions

The gate creates only a random, empty temporary directory. It never accepts an
existing user backup/key directory. The fixture path includes a space to exercise
native CLI/Compose argument handling. Host paths stay in process-local fixture
configuration and are excluded from the receipt.

On **Windows**, the root DACL permits only the current Windows user, SYSTEM and
the local Administrators group, with child inheritance. Verify the root,
directories and generated files against those same identities. The helper uses
Windows PowerShell's .NET filesystem ACL methods, writing only access rules;
it does not request audit-policy privileges or change the machine's execution
policy. Its native module search path is isolated from a parent PowerShell 7.
Only permission errors, not raw command output or account SIDs, reach the receipt.
Docker Desktop may express the current owner's access using the Windows
`OWNER RIGHTS` alias (`S-1-3-4`). Accept that alias only when the file/directory's
actual owner is the current user. The regression also adds an Everyone rule to
an empty temporary directory and requires rejection; unknown accounts remain
outside the accepted identities.
See Microsoft's [Owner Rights definition](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-identifiers).

Docker Desktop's Linux view of an NTFS bind does not establish Windows privacy.
The gate checks the real Windows ACLs; it does not require synthetic Linux mode
bits/ownership on that bind to stand in for those ACLs.

On **Linux**, the temporary parent stays mode 0700 under the invoking host user.
A receipt-guarded root helper initializes only the two new empty bind directories
as UID/GID 10001, mode 0700. The generator, storage maintenance and application
run as UID 10001; verify keys, archives and sidecars are mode 0600 under that UID.
Before removing fixtures, the helper returns those files/directories to the
invoking host UID/GID. Rootless engines and user-namespace remapping are outside
this acceptance target; use a normal local engine with matching host UIDs.

Root helpers have no network and only the ownership/access capabilities needed
for the invented directories. Receipt markers, ordinary-file/name/count checks
and mount checks guard initialization/ownership return. Application data/media
remain fresh receipt-owned named volumes. No production installation or login
is mounted; the X cookie is explicitly invented and no X request is made.

## Missing paths on Docker Desktop

The Windows gate observes Docker Desktop automatically creating a missing bind
source directory even with `create_host_path: false`. That behavior is recorded
as `host_missing_bind: desktop_created_private_directory`; ordinary Linux must
reject the missing source. The test-created directory remains inside the private
fixture root. This is an observed engine difference, not evidence that Compose
enforces the host-directory precondition on Desktop.

Before any operator maintenance command, explicitly confirm the intended backup
or key directory exists and has private host permissions. Before enabling the
login override, confirm `x-session.key` is an ordinary 32-byte file. A missing
secret that becomes a directory must never yield a connected login or overwrite
existing ciphertext. The gate accepts only explicit rejection of that key,
records the outcome and removes the fixture's empty directory during cleanup.

## Results and cleanup

The JSON receipt contains fixed `host_checks`, `host_permissions`, a source
fingerprint and categorical `host_error` on failure. It excludes paths, account
SIDs, key/ciphertext hashes or bytes, backup names and raw command output.
All prior/new stages and cleanup must pass for `passed: true`, `complete: true`
and exit code 0. A new attempt replaces an older successful receipt first.
The fixed `host_missing_bind` and `host_missing_secret` fields distinguish native
Compose rejection from the validated Desktop behaviors above.

Cleanup stops/removes only receipt-owned containers/networks/volumes, returns
ownership of the new bind contents, then removes the temporary directory. There
is no prune. A host-process interruption can leave private fixtures; diagnose the
fixed error and inspect the owned attempt before cleanup rather than targeting a
production directory. A failed attempt is not acceptance evidence.

Results are recorded in [TESTING](TESTING.md). Linux CI covers ordinary POSIX bind
permissions; local Docker Desktop acceptance covers this Windows host's sharing
and ACL behavior. These runs do not prove another machine's sharing/security
configuration, real account login, browser decoding or a future database migration.
The deployment remains experimental; see [ROADMAP](../ROADMAP.md#docker-化部署).

References: [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/),
[Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/),
[Directory.SetAccessControl](https://learn.microsoft.com/en-us/dotnet/api/system.io.directory.setaccesscontrol?view=netframework-4.8.1).
