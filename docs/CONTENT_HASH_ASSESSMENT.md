# Content hash comparison assessment — 2026-10-25

## Decision

Keep content hashing **optional and separate from source identity**. A future
first increment should report exact-byte duplicate candidates after a verified
download; it should not automatically skip new URLs, remove files, rename files,
create hard links or search for moved media. This assessment does not enable a
runtime hash index or change the existing download/manifest schema.

The required rule remains: if the recorded original path is missing, renamed,
moved, or under another download root, fetch the source again. A matching hash
at some other location cannot satisfy that original-path requirement.

## Current code and boundaries

`ssdl/media_contracts.py:source_key` recognizes supported source identities and
hashes normalized direct-image URLs. `MediaManifest.key` hashes a source key for
storage. Neither digest describes file contents. `file_entries` / `verify_entries`
check original paths, size and modification time. `ImageHistory`, `MediaManifest`
and the per-account `ProfileArchive` provide completion evidence with independent
root/source/account scopes. These records must continue to work without a content
index, including when it is disabled, unavailable or corrupt.

A new URL's digest is unknown until its complete bytes have been obtained unless
the source provides separately trusted content evidence. Therefore a local hash
index alone cannot guarantee a zero-transfer download across arbitrary URLs.
Resized images, recompressed videos, different containers or changed metadata
can have different bytes despite similar visible content. Perceptual similarity
is outside this exact-byte comparison proposal.

## Proposed future contract

Use streamed **SHA-256**, reading 1 MiB blocks rather than loading whole videos
into memory. Candidate identity would be `(algorithm, digest, byte_size)`, with
an explicit schema/algorithm version. Prefer a new private SQLite database rather
than mixing job cleanup with the current source-completion databases.

| Proposed record | Purpose |
| --- | --- |
| Algorithm, digest and byte size | Identify exact-byte candidate groups. |
| Resolved download root and relative original path | Keep every original file and its scope distinct. |
| Observed size, nanosecond mtime and available file identity | Invalidate stale observations and detect replacement during hashing. |
| Completion generation / source reference | Link only to independently verified complete output. |
| Hash state/version and observation time | Distinguish pending, valid, changed and failed observations. |

One digest may reference several original files. Clear-history operations must not
remove originals or treat one URL/account's success as another's authorization.
Do not persist raw authenticated URLs, cookies or tokens in this index; references
and digest metadata are still private runtime data and stay excluded from source
archives, Git, public diagnostics and release artifacts.

1. Admit only verified complete files after source completion; exclude `.part`,
   `.tmp`, `.ytdl`, failed/unfinished streams and untrusted imported files.
2. Use the established path restrictions. Do not follow links/reparse escapes or
   use an index hit to import an unknown old file as complete.
3. Hash outside queue/state locks with one bounded, cancellable background task.
   Compare the opened file's identity/size/mtime before and after reading; discard
   changed/deleted observations, and revalidate the path before publishing.
   Size/mtime checks are observations, not protection against arbitrary concurrent
   writers that deliberately restore metadata. A later destructive action would
   need independent confirmation and fresh verification of both complete files.
4. Publish a successful hash only after the full read and final checks. IO failure,
   cancellation or shutdown leaves a retryable observation, never a valid digest.
5. Show duplicate candidates only when both original paths remain valid. A stale
   record falls back to ordinary source download; it cannot block queue progress.
6. Keep existing SQLite schemas unchanged. A missing/new/unsupported hash database
   disables this optional comparison and leaves normal downloads usable. Initial
   backfill would be explicit, bounded and limited to trusted completion records.

Automatic reuse, hard-link storage and destructive duplicate cleanup require a
separate product decision. Hash equality alone is not source provenance, access
authorization or an existing record's integrity proof.

## Reproducible cost probe

```powershell
python tools/measure_hashing.py --report hash-assessment.json
```

The tool exclusively creates a fresh synthetic dataset in an owned temporary
directory. It accepts sizes/round counts, not media paths, and deletes only its
temporary directory. It never loads application state or reads original downloads.
Reports omit paths and raw hashes. Its streaming helper is for this probe only.

Native Windows / Python 3.12.10, 3 rounds, median elapsed times:

| Dataset | Metadata only | Streamed SHA-256 |
| --- | ---: | ---: |
| 1 × 32 MiB file | 0.031 ms | 81.145 ms |
| 512 × 4 KiB files (2 MiB total) | 17.361 ms | 234.361 ms |

These are repeated reads with the operating-system cache and this machine's
filesystem overhead. They are not cold-disk measurements, peak-memory profiling,
network-drive results, or a performance promise for other machines. The probe
does not flush caches or elevate privileges. Small-file opens have material cost,
so neither every status poll nor every unchanged-source re-add should hash all
stored files. A future index needs explicit scheduling and cached observations.

All three synthetic identity checks passed: identical bytes at different paths;
same-size different bytes; and different bytes with the original mtime restored.
Three unit cases passed for the report contract, owned-directory refusal and
argument bounds. Local evidence is ignored `data/hash-assessment.json`.

The assessment is complete. Runtime indexing, its migration/backfill, UI and
additional disk/concurrency/shutdown acceptance remain a separately approved
future feature in [ROADMAP](../ROADMAP.md).
