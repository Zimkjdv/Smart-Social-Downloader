# Pixiv artwork identity and legacy completion records

Implemented: 2026-10-25. This extends single-artwork queue/manifest identity;
Pixiv author synchronization continues to scan each time and uses its own
per-author archive. No database schema, login protocol or download-root rule changes.

## Recognized whole-work links

The following examples use the same `pixiv-artwork:100` source identity:

| Form | Example |
| --- | --- |
| Standard | `https://www.pixiv.net/artworks/100` |
| English locale | `https://www.pixiv.net/en/artworks/100` |
| Short | `https://pixiv.net/i/100` |
| Legacy | `https://www.pixiv.net/member_illust.php?illust_id=100&mode=medium` |

Accept HTTP/HTTPS, bare/www Pixiv hosts, an optional final slash on artwork/short
paths, fragments and only the reviewed `utm_source`, `utm_medium`, `utm_campaign`,
`utm_term`, `utm_content`, `utm_id` tracking parameters (case-insensitive names).
Legacy `mode` must be absent or `medium`; a valid unique numeric `illust_id` is
required. Recognized forms are sent to gallery-dl using the standard HTTPS URL,
including percent-encoded legacy ID digits. The submitted job URL stays visible.

Unknown query parameters, page/selection/signed parameters, other locale paths,
unlisted links, author URLs, explicit ports, credentials, duplicate semantic
query keys and invalid IDs retain the complete URL identity (excluding fragment).
Parsing is bounded at 64 query fields. This avoids guessing whether another
parameter changes media, access or resolution. It is not general URL equivalence.

The queue uses this identity to avoid a second pending row. Video-quality and
selected-media preferences remain part of the job and completion key; different
preferences do not share a completed result. The default remains highest quality.

## Existing completion records

The general manifest hashes its source key, so an arbitrary old hash cannot be
reversed to discover its artwork ID. Compatibility uses only:

1. The exact submitted URL's former key, with the same quality/selection suffixes.
2. An existing trusted successful history row whose recognized source and original
   download root match, using the established history-import checks.

A matching old manifest must pass complete-record, relative-path, original-file,
nonempty-size and saved-modification-time checks. Promotion copies its old
verification evidence unchanged, keeps the old row and uses `INSERT OR IGNORE`
for the new key, then verifies again. It does not replace a canonical row another
writer published. Restatting changed files into new completion evidence would
incorrectly bless them; a deterministic mutation regression covers that race.

A remembered canonical record takes precedence even if its original file is now
missing. Another old copy is not used to avoid restoring that original location.
Missing, moved, renamed or changed originals trigger a fresh transfer; moving to
a different download root also refetches. Moved copies remain untouched. Explicit
**Redownload** still forces a transfer, and compatible single-file results can
restore the previous recorded name under the existing engine/ID/extension rules.

If only an unknown old hash remains, a different URL spelling may transfer again.
We do not infer completeness from matching names, scan arbitrary media folders,
merge signatures or delete legacy copies. See [deduplication](DOWNLOAD_DEDUP.md).

## Reproduction and scope

```powershell
python -m unittest tests.test_source_identity tests.test_manifest tests.test_p2 -v
python tools/check_docker.py --pixiv --report data/pixiv-identity.json
```

Fourteen identity cases use temporary originals and real SQLite while replacing
remote transport. They cover recognized/unreviewed forms, canonical routing,
preferences, exact-key/history compatibility, missing/changed/moved/root cases,
explicit force, unknown old hashes, a promotion-time mutation and a competing
canonical publisher. One HTTP API regression covers pending-row reuse and quality
separation. The Linux non-root/network-disabled probe requires **55 Pixiv cases**:
nine paths, 16 recovery, 16 auth and 14 identity, with no failures/errors/skips.

These are synthetic contract checks, not a live Pixiv platform acceptance or
content-hash comparison. Other platforms and signed-URL equivalence remain in
[ROADMAP](../ROADMAP.md); real author checks are recorded [separately](PIXIV_ACCEPTANCE.md).
