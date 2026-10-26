# Desktop GUI acceptance (D04)

D04 adds repeatable acceptance gates for the shared DesktopInterface and the
source-version Windows shell. It does not add packaging or an Electron host.
The automated gate and human observations are separate: **an automation pass
does not complete the manual matrix below**. D05 should wait for that matrix.

## Reproduce

Install the normal locked requirements, optional browser requirements and
requirements-desktop.txt using Python 3.12, then run:

```powershell
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_desktop_isolation tests.test_desktop_gui tests.test_desktop_control tests.test_desktop_service -v
.\.venv\Scripts\python.exe -X utf8 tools/check_desktop_gui.py --matrix
```

The GUI gate opens real WebView2 windows. It uses a reviewed source archive,
receipt-owned temporary root, Chinese/spaced media directory, separate profile
and free loopback port. The existing checkout's service, credentials, jobs and
downloads are not used. Children receive admission only after their owner has
attached a Windows Job Object. Normal shutdown must pass before Job Object
cleanup can be treated as teardown; forced cleanup is never successful evidence.

Use `--startup-only conflict` or `--startup-only concurrent` to reproduce one
native startup case. Default invocation without these switches retains the
shorter two-session D03 smoke. `--keep-workspace` retains a diagnostic source
copy; it is not automatically resumed. Artifacts default to a new directory in
ignored data; `--artifacts-dir` must name a new directory. JSON/PNG evidence is
synthetic and is excluded from source archives. Review retained logs before
sharing logs or screenshots because temporary paths can identify a Windows user.
`workspace_cleanup` reports `removed` or `retained`; WebView2 profile locks may
leave an owned temporary remainder. This is independent of backend shutdown and
does not turn failed acceptance into success.

The report stays failed until all requested phases finish. Missing optional
imports and an undetected WebView2/.NET runtime have distinct error codes:
`desktop_dependencies_missing` and `webview2_runtime_missing`. A detected runtime
must still pass actual initialization. Other failed checks use
`gui_acceptance_failed`; they are not skipped or recorded as passes. The runtime
failure notification test injects an unavailable runtime; this is not a test on
a physically runtime-free Windows installation.

## Automated evidence

| Boundary | Evidence |
| --- | --- |
| Shared DesktopInterface | One parameterized suite runs the same version/capability, successful action, reservation, pre-abort, disposal, unavailable capability and permission refusal checks against both adapters. Host-specific bridge readiness, rejection, timeout and late results remain additional cases. |
| Core independence | A fresh interpreter forbids all pywebview/.NET imports while importing the shell/control modules and serving a real HTTP state request with temporary application data. Normal CI/Docker requirements have no GUI dependency. |
| Actual native lifecycle | Two GUI sessions test started/attached ownership, repeat launch focus, preferences, active synthetic worker continuing after window close, graceful owned stop, partial preservation, backend-exit offline UI and history recovery. Two gated cold processes must produce one primary window and one verified backend. A foreign port listener must survive a visibly failed GUI startup. |
| Shared business UI | The same flow runs in real WebView2 and a fresh automated Chrome context: 32 synthetic jobs, settings, error details, Chinese/English copy, scripted focus trap/return and scrolling. Business requests continue over the shipped HTTP API. |
| Native actions | Actual JS bridge calls exercise injected folder cancel/selection and atomic UTF-8 export. Clipboard writes/readback use the actual STA clipboard and restore its previous data object. File/folder routes retain actual path validation/filesystem IO while OS dispatch is intercepted. External dispatch is intercepted; unsafe schemes are rejected. |
| Media / browser export | WebView2 decodes a PNG and H.264 video, advances decoded frames, seeks and reads HTTP 206 bytes. Chrome plays the native media document without desktop powers and verifies a Blob export's suggested name and JSON bytes. |
| Rendering | Matching 1280×800 CSS viewports produce Chinese/English settings/error PNGs. WebView2 additionally captures renderer scale factors 1, 1.25, 1.5 and 2. This is CDP emulation; actual system devicePixelRatio is recorded separately. |

The boundary mocks replace OS permission/dialog responses and media transport,
not the backend scheduler, state writer, HTTP handler, UI controllers or native
WebView2 renderer. The synthetic worker cannot represent platform rate limits,
real authentication, network downloads or OS file associations. Existing shared
HTTP/download suites remain the authority for business behavior; no second
desktop download engine or queue suite is maintained.

For visual review, compare paired `chrome-settings-*`/`webview-settings-*` and
`chrome-error-*`/`webview-error-*` PNGs at the same language/viewport. Text, focus,
controls and content must remain usable. Native window decorations, font
antialiasing, scrollbar rasterization and the explicit desktop banner/picker are
expected differences. Pixel identity is not an acceptance criterion. CDP
viewport captures omit the native window frame; the separate smoke PNG captures
the real WebView control at its current system scale.

## Manual release gate (pending)

Record Windows version, WebView2/Chrome versions, monitor scaling, language,
test date and operator. Each row needs an observation; absence means pending.
Use disposable source/data and synthetic files. Keep real credentials out of
screenshots and restore the Chrome connector's production port after testing.

| Case | Required observation | Status |
| --- | --- | --- |
| Actual Windows scaling: 100%, 125%, 150%, 200% | Open/reopen/resize at each OS setting, move between mixed-DPI monitors if available; no clipped controls or unusable text | Pending; renderer emulation does not close this row |
| Physical keyboard/focus | Tab/Shift+Tab, Escape, modal focus return, keyboard scrolling and repeat-launch activation | Pending; DOM events are separate evidence |
| Native folder dialog | Choose a Chinese/spaced directory, cancel, verify draft-only change and explicit Save through HTTP | Pending; injected responses do not close this row |
| Native Save As | Save diagnostics, cancel, overwrite confirmation and denied-location error; preserve previous target on failure | Pending |
| Native window close/stop confirmation | Cancel then accept each actual prompt; closing keeps work alive, explicit owned stop preserves the queue | Pending; programmatic close is separate evidence |
| OS applications / permissions | Real image/video association, folder reveal, clipboard refusal/recovery if available, actual external browser activation | Pending; dispatch interception does not close this row |
| Ordinary Chrome authorization callback | Start X and Pixiv from the desktop, complete/cancel in ordinary Chrome with the connector on the isolated port, observe the desktop HTTP state update and no duplicate auth tab | Pending; earlier browser pairing acceptance is not a desktop observation |

These rows are intentionally not converted into completed checkboxes by a JSON
report or by pressing Enter in a script. A missing environment is reported as
unavailable/pending, not passed. Real-account/monitor observations can be added
later without rewriting the automated fixture.

Protocol references: [WebView2 CDP API](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.calldevtoolsprotocolmethodasync),
[device metrics emulation](https://chromedevtools.github.io/devtools-protocol/tot/Emulation/#method-setDeviceMetricsOverride),
[viewport capture](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-captureScreenshot).
