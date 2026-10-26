# Desktop GUI acceptance (D04)

D04 adds repeatable acceptance gates for the shared DesktopInterface and the
source-version Windows shell. It does not add packaging or an Electron host.
The automated gate and human observations are recorded separately. The current
Windows host passed the baseline manual matrix on 2026-10-26; the additional
environments listed below remain untested. D05 packaging has not started.

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
| Rendering | Matching 1280×800 CSS viewports produce Chinese/English settings/error PNGs. WebView2 additionally captures renderer scale factors 1, 1.25, 1.5 and 2. This is CDP emulation; the renderer's unmodified initial devicePixelRatio is recorded separately and does not measure OS settings. |

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

## Manual baseline — completed on this host

Operator: the project owner, assisted in this chat on 2026-10-26. Environment:
Windows 10 build 19045, Python 3.12.10, WebView2 155.0.4283.62, ordinary Chrome
155.0.8059.86, Traditional Chinese, restored to 200% scaling.
Disposable sources/data and synthetic files were used; real login material was
kept out of reports. The connector was restored from isolated port 8877 to 8765.

| Case | Observation | Status |
| --- | --- | --- |
| Actual Windows scaling: 100%, 125%, 150%, 200% | Operator changed OS settings, resized the running window and checked jobs/settings: readable text, unclipped controls and usable scroll at all four; restored 200% | Passed by operator; renderer captures are separate |
| Physical keyboard/focus | Operator confirmed Tab/Shift+Tab, Escape, modal focus return and scrolling; observer recorded trusted Tab/Escape events | Passed; repeat-launch activation is automated evidence |
| Native folder dialog | Cancel/select a Chinese/spaced directory, draft-only update, explicit Save through HTTP | Passed by operator; real selection and saved settings observed |
| Native Save As | Cancel/save diagnostics, overwrite confirmation, read-only refusal; readable UTF-8 JSON and unchanged read-only original hash | Passed by operator and file checks |
| Native close/stop confirmation | Cancel then accept actual prompts; first-round stop recorded cancelled/completed, second-round close left backend alive before owned cleanup | Passed by operator and lifecycle receipts |
| OS applications | Actual PNG/MP4 association, folder reveal and external Node.js download page | Passed by operator; permission-refusal mocks remain separate |
| Ordinary Chrome callback/restart | Desktop initiated X/Pixiv; clear/cancel then reconnect; automatic desktop return, no duplicate tabs; both DPAPI sessions restored in the genuinely reopened second round | Passed by operator and HTTP state |

Additional environments remain **untested**, not passed: fresh-process startup at
each OS scale, mixed-DPI monitor movement, actual clipboard permission refusal
and a physically runtime-free Windows installation. The injected runtime failure
and permission cases are automated evidence only. These limits do not establish
Windows 11 or clean-machine installer acceptance; those belong to later release
work. OAuth-in-progress browser restart/worker-sleep combinations remain in the
separate authorization roadmap.

## User-assisted follow-up — 2026-10-26

The user requested continuing the manual gate after the automated implementation
was pushed. A separate receipt-owned copy of the reviewed D04 sources was opened
as a clearly labelled native GUI on isolated port 8877. Its stock backend,
dialogs, file associations and ordinary Chrome launch paths were used without
the automated transport/dialog/dispatch replacements. Production port 8765
remained available with its 39 completed records.

The operator confirmed folder selection/cancel and draft/save behavior, native
Save As/cancel, physical Tab/Shift+Tab/Escape, focus return, scrolling and
cancelling the actual window-close prompt. Native dialog observations separately
recorded a successful folder selection, Save As cancellation and a completed
export whose UTF-8 JSON was readable.

After saving connector port 8877, the popup-created X session was explicitly
cleared in the isolated backend. The desktop then initiated X/Pixiv connection;
the operator confirmed ordinary Chrome, automatic desktop return, clear/cancel
followed by reconnect and no duplicate authorization tabs per operation. Actual
HTTP state reported both connected with persistent DPAPI storage. Pixiv recorded
two begin/claim/callback sequences and one local disconnect. This does not claim
OAuth-in-progress worker sleep/restart or expired-code behavior.

The operator also confirmed actual PNG/MP4 applications, folder reveal, the
external official Node.js page, overwrite confirmation and read-only target
refusal. The synthetic read-only original's hash was unchanged. The initial PNG
fixture had an invalid IDAT CRC which permissive browser decoders accepted; it
was corrected before retrying the Windows viewer, with a red/green format
regression added. This was a fixture correction, not an application media change.

On Windows 10 build 19045, the operator changed OS scaling through 100%, 125%,
150% and 200%, resized and inspected settings/jobs, reported readable text,
unclipped controls and working scroll at all four, and restored 200%. The
auxiliary observer only captured devicePixelRatio 2; it did not measure OS
settings and stopped updating after its polling loop recorded a PermissionError. These human OS observations do not assert that the renderer
rasterization factor changed.
Fresh-process startup at every scale and mixed-DPI monitor movement were not
exercised. Scripted CDP captures remain separate evidence.

The first round recorded stop cancellation followed by successful explicit
stop. Its backend was therefore already stopped before the actual close; that
close is not evidence of background continuation. After the first window really
closed, the second native window started the backend and both DPAPI logins were
independently confirmed connected over HTTP. Closing the second window returned
code 0 and left its backend reachable. The driver then cleared both isolated
sessions through the standard APIs, verified owned shutdown, and port 8877 stopped
accepting connections. No isolated auth files remained. The ordinary connector
was restored to 8765, whose production service stayed available.

The first auxiliary observation loop's PermissionError is retained in its local
receipt; it is not treated as product success or failure. Its live samples are
incomplete. Independent window-exit receipts, native action responses, HTTP/file
checks and explicit operator reports support the observations above.

Protocol references: [WebView2 CDP API](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.calldevtoolsprotocolmethodasync),
[device metrics emulation](https://chromedevtools.github.io/devtools-protocol/tot/Emulation/#method-setDeviceMetricsOverride),
[viewport capture](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-captureScreenshot).
