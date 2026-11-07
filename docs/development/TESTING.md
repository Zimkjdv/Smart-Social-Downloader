# Testing and source distribution

This guide owns test commands, fixture ownership and source-package boundaries.
Read [acceptance procedures](../testing/README.md) for native/container gates and
[historical results](../history/TEST_RESULTS.md) for dated evidence.
Open environment and release work is tracked in [Roadmap](ROADMAP.md).

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

`tests/helpers/docker.py` supplies the fake CLI shared by Docker gate contracts.
Those tests verify source selection, receipts and owned cleanup; only the actual
[Docker runtime/service gates](../testing/DOCKER_SERVICE_ACCEPTANCE.md) establish container
execution evidence. The helper is shipped by the existing code-only fixture policy.

The [interaction gate](../testing/DOCKER_INTERACTION_ACCEPTANCE.md) separately exercises real
container sessions/media. Native action regression mocks desktop launching;
it never opens a user's media viewer or file manager.

The [host-storage gate](../testing/DOCKER_HOST_ACCEPTANCE.md) further checks actual private
host bind directories and file-backed secrets. Its probes stay outside the
runtime image. Shared contracts use the same fake CLI; native ACL regressions
use only empty temporary Windows directories.

## Reviewed packaging boundaries

`tools/package_source.py` combines a fixed root-file list, shallow globs for
assets/tools, explicit documentation categories and recursive **code-only** boundaries:

| Boundary | Allowed files |
| --- | --- |
| `ssdl/` | Python modules, including subpackages |
| `desktop/` | Optional shell Python modules, including subpackages; no binaries/profile data |
| `tests/` | `__init__.py`, `test_*.py`, `*.test.cjs` |
| `tests/helpers/` | Python helper modules, including subpackages |
| `docs/` | Index, guides, deployment, reference, development, testing and history Markdown in explicitly listed folders; two named agent guides |
| `docs/research/` | Only the reviewed content-hash assessment; local research is not automatically shipped |
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
.\.venv\Scripts\python.exe tools/check_docs.py
.\.venv\Scripts\python.exe tools/package_source.py --check
.\.venv\Scripts\python.exe tools/check_source_archive.py
```

`-t .` gives unittest a stable project/package root. Targeted runs work too:
`python -m unittest tests.test_queue_auth tests.test_p2`.

The last command builds a disposable source ZIP, verifies the exact allowlisted
member set, duplicate absence, CRC and source bytes, then extracts into an owned
temporary directory. A child interpreter checks that app/helper/packager imports
come from the extraction, checks shipped documentation links/anchors and runs the **full Python suite**, followed by the
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
remain in [ROADMAP](ROADMAP.md).

## Acceptance lanes

Fresh dependency installation is now checked by a separate Windows job/tool;
the extraction regression above intentionally uses current dependencies. See
[Installation acceptance](../testing/INSTALLATION_ACCEPTANCE.md).

The optional Windows GUI gate is separate from core/source/Docker acceptance:
`python tools/check_desktop_gui.py --matrix` opens actual WebView2 sessions with
isolated sources/data/profile and compares the shared UI with fresh Chrome.
Neither GUI dependencies nor an interactive desktop are required by normal CI.
See [D04 GUI acceptance](../testing/DESKTOP_GUI_ACCEPTANCE.md) for artifacts, startup-only
reproduction, completed manual baseline and remaining environment limits.

D05 release tooling and packaging recipes are included in source allowlists;
compiled executables, vendor downloads, build venvs and acceptance data are not.
Windows executable/installer acceptance is a separate opt-in lane documented in
[Windows distribution](../deployment/WINDOWS_DISTRIBUTION.md); it does not add GUI dependencies
to the core/source or Docker gates.

## Documentation changes

Use [the documentation index](../README.md) to choose the owning guide. Keep current instructions in guides/reference/development and dated observations in history. README files contain a short tree; the complete module tree lives in [Architecture](../reference/ARCHITECTURE.md). When moving or merging a page, update relative links and heading anchors, the documentation index, and the explicit documentation boundaries in `tools/package_source.py`.

`python tools/check_docs.py` checks local Markdown destinations and heading anchors in shipped documents. It does not request remote URLs. Run the release tests and extracted-source acceptance when changing packaging boundaries. Personal research and execution receipts remain outside the reviewed source list.

Browser tests require optional Playwright dependencies and ordinary Chrome; explicit skips are not full browser acceptance. Syntax checks and mocked tests alone do not establish native GUI, clean-Windows or live-account acceptance.
