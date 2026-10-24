# Pixiv incremental sync and failure recovery — 2026-10-25

## Scope

Sixteen automated fault cases use invented remote metadata/bytes, native files
and the real profile archive. They exercise production scan-first orchestration,
progress, error classification and verified-page continuation. An isolated real
`RequestPolicy` wraps a synthetic HTTP 429 response; no real HTTP request is sent.
The pacing clock advances only inside that test to model an expired cooldown.

```powershell
python -m unittest tests.test_pixiv_recovery tests.test_pixiv_paths tests.test_pixiv_profiles tests.test_pixiv_container -v
python tools/check_docker.py --pixiv --report data/pixiv-recovery-docker.json
```

The second command now runs **9 path + 16 recovery cases** inside the reviewed
Linux runtime, with no network or host data mounts. The strict receipt requires
exactly 25 tests, zero errors/failures/skips and a successful process exit.
It uses the same non-root/read-only/tmpfs ownership boundary documented in
[directory acceptance](PIXIV_PATH_ACCEPTANCE.md), and runs in existing Docker CI.

## Cases

| Scenario | Required outcome |
| --- | --- |
| A later listing adds a new work | Transfer only the new pages, retain prior hashes/mtimes, charge the work callback once, then reuse everything on another sync. |
| Deleted/private/inaccessible work represented by zero available originals | Warn, process the other accessible work, preserve old originals and report totals only for current accessible originals. |
| Every work unavailable | Zero current totals and no transfer/quota call; retain explicit warnings. |
| Listing transport failure, short page list or nonzero extractor status | No transfer and no claim that scan totals are complete. |
| Duplicate, out-of-range or gapped ordinals | Reject before transfer, including a duplicate ordinal with another extension. |
| Failure, cancellation or limit after one successful page | Preserve that page, retain the error code and resume with only the missing page. A partial row does not satisfy the fresh full-work lookup. |
| Error payload includes unrelated files / `.part` | Ignore those candidates, retain only valid planned originals and preserve cancellation classification. |
| Transfer returns too few final files | Reject completion, preserve the successful page and fill only the missing page next time. |
| Real policy wrapper receives HTTP 429 | Close the synthetic response, retain `rate_limited` and cooldown, and allow a new attempt using the same policy after the controlled clock expires. |
| Expired session / warning text | Retain login-required classification and redact synthetic session/query values. |
| A later work fails | Earlier complete work remains reusable and byte/mtime-identical. |
| Cancellation before scanning | No transfer and no complete totals. |
| Unrelated progress path or empty planned final | Neither is partial-success evidence. |
| Contiguous synthetic Ugoira frame metadata | Keep accepting original-frame paths; this is not live frame-count or animation decoding acceptance. |
| Retained page repeated in progress/error files | Do not count/archive it twice or overwrite cancellation classification. |

Several methods contain multiple failure/metadata subcases, rather than counting
each input as another test method.

## Bugs reproduced and fixed

The initial 12-case run failed two focused cases. Additional inputs reproduced
the same failure patterns before their fixes; no assertion was weakened.

1. **Page completeness used only file count and filename uniqueness.** Two
   returned pages numbered `0,2` could pass a two-page count; `0.png,0.jpg` could
   also evade the filename-only duplicate check. Track each work's integer
   ordinals independently of extensions, reject numbers outside `0..count-1`,
   and retain the existing expected-count barrier. Unique in-range ordinals plus
   the full count establish coverage without assuming arrival order.
2. **Progress/error file lists were too broadly trusted.** A synthetic error
   referencing an unrelated image imported it into the work's archive. Adding
   an unfinished `.part` caused archive validation to raise and replaced the
   original `download_cancelled` with `download_failed`, reporting no retained
   originals. Admit only the work's currently planned missing paths, verify
   nonempty safe original files through the shared `file_entries` rules, and
   exclude already retained pages. This also prevents duplicate retained-page
   payloads from raising an archive error or double-counting progress.

The protocol still relies on the downloader's successful-final-file contract;
size/mtime/nonempty checks do not decode all originals or prove the integrity of
arbitrary unknown imported bytes. Trusted completion records and fresh listing
identity remain necessary. Failed/unknown files do not become completion evidence.

## Results and remaining live checks

Targeted native Windows / Python 3.12.10: **28 cases passed** (16 recovery, nine
paths, two presentation and one receipt contract). Linux/Python 3.12.15 results,
full regression and package checks are recorded in [TESTING](TESTING.md).
Local categorical evidence stays in ignored `data/pixiv-recovery-docker.json`.

These cases do not establish Pixiv's actual permission responses, real remote
additions/deletions, real platform cooldown durations or every network failure.
Real Ugoira frame completeness/decoding, fresh authentication and live Linux
media recovery remain in [ROADMAP](../ROADMAP.md). The separate real-author
22-work/24-original run is documented in [Pixiv acceptance](PIXIV_ACCEPTANCE.md).
