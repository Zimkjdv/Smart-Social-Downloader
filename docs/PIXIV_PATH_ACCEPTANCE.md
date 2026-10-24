# Pixiv author directory compatibility — 2026-10-25

## Scope and reproduction

This is automated synthetic acceptance using native files and real scoped SQLite
archives. Only the remote listing and original-byte transport are replaced;
the production Pixiv scan, directory formatter, original-path checks, per-author
archive and progress/result construction execute normally. No real login,
author profile, production database or downloaded original is read or changed.

```powershell
python -m unittest tests.test_pixiv_paths tests.test_pixiv_profiles tests.test_pixiv_container -v
python tools/check_docker.py --pixiv --report data/pixiv-paths-docker.json
```

Normal Python discovery includes the tests. `--pixiv` builds the reviewed runtime
with the existing Docker acceptance tool, then streams only the fixed test/helper
allowlist into a temporary container directory. The image supplies the actual
`ssdl` runtime and pinned gallery-dl dependency. The process runs as UID/GID
10001, with networking disabled, a read-only root, dropped capabilities, resource
limits and an owned tmpfs. No checkout, browser profile, key, media or state bind
is mounted. Random labelled container/image ownership scopes cleanup; no global
prune is used. The test files are not added to production images.

The probe requires a matching receipt, integer counters, zero failures/errors/skips
and a successful process exit. The first path-only run required nine tests;
[recovery acceptance](PIXIV_RECOVERY_ACCEPTANCE.md) now extends it to exactly
25 tests (nine paths plus 16 recovery cases); [authorization acceptance](PIXIV_AUTH_ACCEPTANCE.md) extends the current gate to 41 with 16 manager/API cases. Unexpected report fields
are rejected. This same gate is enabled alongside existing Docker CI acceptance.

## Verified cases

| Scenario | Observed requirement |
| --- | --- |
| Chinese, invalid characters, controls/bidi, empty names, decomposed Unicode | Portable directory names retain the author ID and support a real write/resync. |
| Long ASCII and multibyte names | UTF-8 length is bounded without truncating the ID; original paths remain usable. |
| Invalid author IDs | Reject zero, leading-zero, missing, boolean, traversal and overlong IDs. |
| Same display name, different IDs | Distinct folders and archive scopes; earlier author's file hashes/mtimes remain unchanged. |
| Complete numeric-ID / old display-name folder | Reuse trusted original files after a simulated name change, with zero transfer/quota calls. |
| Partial numeric-ID / old display-name folder | Keep the verified page and fetch only the missing page into the current author folder. Another simulated rename reuses both locations. |
| Unrecorded files / another author's folder | They do not prove source completion, even when basenames match. |
| New download root | Refetch both files; preserve all media under the old root. |
| Whole author folder moved within the root | Refetch at the recorded/current location; retain the moved copies without searching for or deleting them. |
| File removed during a quota/pause wait | Recheck the original path after waiting and fetch the newly missing page too. |

The nine test methods contain multiple naming/legacy subcases. Two existing
presentation tests separately verify early/final named titles and queue identity.
The real gallery-dl session initialization hook is exercised, but network pacing
and transport are substituted. This is not a live Pixiv extraction test.

## Recorded result

- Native Windows / Python 3.12.10: nine path cases, two presentation cases and
  one strict receipt case passed; no errors or skipped cases.
- Linux Docker / Python 3.12.15 / gallery-dl 1.32.16: nine path cases passed with
  no errors/failures/skips, plus the existing nine runtime/context checks.
- Local path-free Docker receipt: ignored `data/pixiv-paths-docker.json`.

No production directory-rule change was necessary for these scenarios.
Existing original-location refetch semantics remain intact. This does not cover
a live author's actual rename, unknown legacy database layouts, transferring
Windows path strings/absolute archive scopes to Linux, or real Linux/Docker
authorization and downloaded-media recovery. Those remain in [ROADMAP](../ROADMAP.md).

See [real-author acceptance](PIXIV_ACCEPTANCE.md) for the separate 22-work /
24-original Windows run, and [dedup rules](DOWNLOAD_DEDUP.md) for missing-file policy.
