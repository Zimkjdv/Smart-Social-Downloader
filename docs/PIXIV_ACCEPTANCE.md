# Pixiv author acceptance — 2026-10-24

## Scope and environment

Real native Windows acceptance used the user-selected public author
[Hoshirapu (82728784)](https://www.pixiv.net/users/82728784), the running local
queue and its already connected Pixiv session. This was not a fresh OAuth login.
The existing unrelated download finished normally before this author's work
started. Existing delay, quota and cooldown settings were retained.

Environment: Python 3.12.10, gallery-dl 1.32.16, FFmpeg 7.1, Playwright 1.63.0
and installed Google Chrome. The original-media path used gallery-dl; browser
checks used a fresh temporary Chrome context against the local dashboard.

The accessible list contained **22 works / 24 original files**, including two
works with multiple pages. Final media total: **250,202,814 bytes (238.6 MiB)**.
Every saved page is under `pixiv/Hoshirapu(82728784)/`.

## Observed results

| Scenario | Result |
| --- | --- |
| Scan before transfer | The monitor reported 22 works / 24 files with scan complete and zero files transferred before starting downloads. |
| File identity and decoding | 24 unique, nonempty files; 22 work IDs; contiguous page numbers within each work. FFmpeg decoded the first frame of every file successfully. |
| Pause | At 13 completed files, the job reached paused state and the count stayed unchanged across a two-second observation. Pause was then cleared. |
| Stop and continue | Stop produced `download_cancelled` / stopped state with all 13 files retained. Adding the author again reused the same history row, verified those 13 files and downloaded the remaining 11. The retained files kept their size and modification time. |
| Repeat complete sync | 24 files reused, zero downloaded, 22 works skipped. All SHA-256 hashes and modification times stayed unchanged. Hourly usage stayed 99 → 99; the observed sync took 2.48 seconds. |
| Missing page | Temporarily move one newly downloaded second page into a private backup outside the download root. Sync reused 23 files and downloaded exactly one; all 24 hashes matched the baseline and the other 23 modification times stayed unchanged. The verified temporary backup was removed afterwards. |
| Changed file | Change only one file's modification time by two seconds. Sync reused 23 files and downloaded exactly one, with all baseline hashes preserved and the other 23 modification times unchanged. |
| Archive consistency | Read the scoped archive without writing: 22 work records / 24 page entries; paths, sizes and modification times all verified against the final files. |
| Restart and saved login | Gracefully stop and start the managed service in the normal Windows user context. The encrypted Pixiv session reconnected, completed history and 24 files were preserved, and the queue stayed unpaused. |
| Author name in the dashboard | Actual Chrome rendered `Pixiv 作者 · Hoshirapu(82728784)` and `Pixiv author · Hoshirapu(82728784)`. Reload retained the English name; no page errors were observed. |
| Name before transfer | Both recovery scans exposed `Pixiv · Hoshirapu(82728784)` through the job API before their missing/changed file transfer began. |

The final job is completed with an empty error code. The one existing notice
explains accessible originals / original animation frames; it is not an engine
transfer error. No media was permanently removed by the checks.

A service launched in the restricted tool context could not decrypt Windows
DPAPI data and reported an expired session. Its existing encrypted file remained
intact; relaunching in the normal Windows user context restored the connection.
This verifies that environment distinction, not cross-machine key portability.

## Author title implementation and regression checks

Author scan metadata now supplies the stable `Pixiv · Name(ID)` title during
progress and at completion. The scheduler retains it, including long numeric
IDs. Both dashboard languages format the prefix around the same identity.
Older completed rows can use a matching named author folder immediately; an
ID-only record stays ID-only until an author name becomes available. Rendering
only accepts a named folder for the same numeric author ID. This fallback does
not scan the filesystem, move media or change duplicate-download checks.

The two new Python cases cover scan-time/final author titles, snapshot session
initialization and profile progress behavior. The new Node case covers metadata,
Windows/POSIX historical paths, mismatched IDs, ID-only fallback and English copy.

Local results:

- `python -m unittest tests.test_pixiv_profiles tests.test_p2 tests.test_queue_auth tests.test_browser_ui -v`:
  **40 passed in 13.729 seconds**, including the eight real Chrome UI cases.
- `node --test tests/frontend.test.cjs`: **24 passed**, zero failures/skips.
- Separate live dashboard Chrome observation passed against the actual service.

Private receipts, hashes, temporary files and text-only UI captures stay in
ignored `data/`; cookies, tokens, local absolute paths and media are not copied
into this document or the source package.

## Remaining acceptance

This one author does not establish all of Pixiv's available content or account
permissions. The following remain in [ROADMAP](../ROADMAP.md):

- Fresh authorization on other Chrome installations and Docker; expired,
  cancelled or mismatched callback attempts and extension upgrade permissions.
- Live new works, inaccessible/deleted/private responses, real rate-limit/failure
  recovery and original Ugoira frame coverage. The automated portion now has
  [16 synthetic recovery cases](PIXIV_RECOVERY_ACCEPTANCE.md); it does not replace
  those actual platform observations.
- An actual author rename and archive migration between OS path/scope formats.
  Synthetic Unicode/long-name, same-name/different-ID, legacy-folder reuse, root
  change and whole-folder relocation now pass on Windows and Linux; see
  [2026-10-25 path acceptance](PIXIV_PATH_ACCEPTANCE.md). Production archive records
  were not edited to manufacture those cases.
- Linux/Docker title/media/session persistence and additional browser environments.

The completed Windows checks above are recorded in [CHANGELOG](../CHANGELOG.md).
