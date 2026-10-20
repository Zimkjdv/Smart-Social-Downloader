# Test fixtures and source distribution acceptance

N08 (2026-10-16) keeps tests importable independently of test-class ordering and
checks the distributable source in addition to the working checkout.

## Shared fixture

`tests` is an explicit Python package. `tests/helpers/app.py` provides
`IsolatedApp` and `seed_jobs`; helpers never import a test case. Queue/auth and P2
API tests enter the fixture with `self.enterContext(IsolatedApp())`.

Each fixture creates a separate temporary root, AppContext, StateStore, services
and patch stack. It does not restore production history or login. Its own delay
bounds are zero; the process-wide random generator and application globals stay
unchanged. Cleanup closes the app while overrides are installed, restores
patches, stops the original services and then removes temporary files. Cleanup
also runs on test/setup failure. Tests cover independent instances, owned worker
shutdown, override restoration and directory removal.

Current suites stay at the top level: an additional unit/integration/browser
split has no current need. Future nested Python suites need `__init__.py` in each
package directory and must follow the `test_*.py` naming convention. New shared
support belongs under `tests/helpers/`, not another test class.

## Reviewed packaging boundaries

`tools/package_source.py` combines a fixed root-file list, shallow globs for
assets/docs/tools and recursive **code-only** boundaries:

| Boundary | Allowed files |
| --- | --- |
| `ssdl/` | Python modules, including subpackages |
| `tests/` | `__init__.py`, `test_*.py`, `*.test.cjs` |
| `tests/helpers/` | Python helper modules, including subpackages |
| Other source folders | Only the explicit `SOURCE_GLOBS` entries |

Hidden directories, `__pycache__`, `data`, `downloads`, `dist` and `node_modules`
are excluded from these walks. Selected files and traversed directories may not
be symlinks or Windows reparse paths, even when their targets remain inside the
source root. Sources must be UTF-8 and at most 2 MB per file. Existing content
checks reject recognizable private keys, personal Windows paths and Netscape
Cookie exports without echoing the value.

No workspace-wide recursive search is used. Review the selected list and the
contents before publishing: these checks are not a universal secret scanner.
An arbitrarily named support module outside `tests/helpers/`, non-code test
fixture or new tool must be explicitly added to the policy. New Node suites
also need registration in the regression commands; the current Node suite is
`tests/frontend.test.cjs`.

## Run checkout and extracted-source checks

After installing the pinned baseline, optional browser dependencies, ordinary
Chrome and Node:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/package_source.py --check
.\.venv\Scripts\python.exe tools/check_source_archive.py
```

`-t .` gives unittest a stable project/package root. Targeted runs work too:
`python -m unittest tests.test_queue_auth tests.test_p2`.

The last command builds a disposable source ZIP, verifies the exact allowlisted
member set, duplicate absence, CRC and source bytes, then extracts into an owned
temporary directory. A child interpreter checks that app/helper/packager imports
come from the extraction and runs the **full Python suite**, followed by the
Node suite and the [dependency fault gate](DEPENDENCY_FAULTS.md), with the extracted directory as cwd. Python ignores inherited
PYTHONPATH/PYTHONHOME and user site packages; the current venv's installed
dependencies and system Chrome/Node are intentionally available. Failures stop
acceptance with a nonzero exit code; temporary outputs are cleaned on success
and failure. The command does not install dependencies or restart the service.

Roots are canonicalized before relative-path comparisons, including Windows
TEMP short-name aliases. The release fixture uses the same normalization; a
noncanonical-root regression protects this contract without relaxing link checks.

Windows CI runs both checkout and extracted-source checks on Python 3.12 / Node
22 and requires real Chrome availability. This verifies source completeness and
test imports; it does **not** verify a fresh operating system, a new dependency
installation, real Chrome account pairing or live platform compatibility. Those
remain in [ROADMAP](../ROADMAP.md).

## Refused POST response coverage

Owned loopback tests verify unauthorized POST bodies receive 403 without JSON
parsing, saving or private-state reads. Cases cover foreign Host/Origin, opaque
Origin, cross-site fetch metadata and the connector attempting an unrelated API.
A gated handler writes 403 before a 64 KB invalid JSON body is delivered, making
the late-body order explicit without sleeps. Partial bodies, disconnected
clients, released slots and subsequent trusted requests are also covered.

The previously observed Windows 10053 has not been reproduced consistently,
including the new late-body fixture. No assertion hides a failed complete 403
exchange, and no production source policy or body-reading behavior was relaxed.
These are additional regression cases, not a claim that an intermittent socket
defect was conclusively fixed. Latest results: [TESTING](TESTING.md).

2026-10-17 follow-up: a complete run encountered 10053 again on a foreign-Origin
POST. Response handling now drains only an unread, strictly framed body up to
100,000 bytes, after sending the refusal, within 0.1 seconds and the original
deadline. It does not parse JSON or access application data. Ambiguous/oversized
frames are not read. The late-body test asserts exact bytes; new tests verify
bounded incomplete cleanup and rejected framing. This addresses the unread-body
closure case while keeping other intermittent transport observations pending.

Fresh dependency installation is now checked by a separate Windows job/tool;
the extraction regression above intentionally uses current dependencies. See
[Installation acceptance](INSTALLATION_ACCEPTANCE.md).
