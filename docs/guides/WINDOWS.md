# Windows source launches

Use these commands from the extracted source folder after installing Python 3.12. Both entries use the same backend, queue, media and local HTTP interface. For the packaged EXE/installer and data migration, see [Windows distribution](../deployment/WINDOWS_DISTRIBUTION.md).

| Entry | Interface | Closing its UI |
| --- | --- | --- |
| `start.bat` | Default browser | Downloads continue; use `stop.bat` to stop the service. |
| `desktop.bat` | Optional WebView2 window | Downloads continue; use its owned Stop action or `stop.bat`. |

## Browser background service

### Browser background start and stop

Run `start.bat` from the extracted project folder. First-time installation still
uses `setup.bat`; subsequent starts check the environment without updating packages.
Once ready, the hidden background process opens the web interface in your default
browser. The launch window closes after success. Closing the browser leaves the
service running. This is a desktop process, not a Windows service or login startup task.

Run `stop.bat` from the **same project folder** to stop it. It requests normal
shutdown, lets AppContext stop workers and save the queue, then waits for completion.
Previously active work can remain queued for restart; already saved media is retained.
Stop can take time while downloads, HTTP requests or state writes finish. After
45 seconds the command reports a timeout without forcibly terminating processes;
inspect the log and run stop again if needed. Startup waits up to 60 seconds; a
startup timeout does not prove the background process has exited.

Repeated `start.bat` calls open the existing background service rather than starting
another copy. `SSDL_PORT` selects a new instance's port; an existing background
instance keeps its original port, recorded in `data/background-service.json`.
Stop it before changing ports. `SSDL_NONINTERACTIVE=1` suppresses browser launch
and batch pauses, for callers that manage their own UI.

### Logs and foreground mode

- Output and startup errors: `data/background.log`. On a new startup, a log over
  2 MiB is moved to `data/background.previous.log`; output during a long-running
  instance is not continuously rotated. Logs can contain local paths; review them
  before sharing. Runtime records/logs remain excluded from Git/source packages.
- If another program or a foreground downloader owns the port, startup fails
  and leaves that program alone. Stop an old foreground downloader with Ctrl+C
  before switching to background mode.
- For a visible foreground console:
  `.venv\Scripts\python.exe -X utf8 tools\manage.py start`.
  `python app.py` is also unchanged. Use Ctrl+C to stop these foreground entries;
  `stop.bat` targets only this project's managed background entry.
- Docker/Linux startup is unchanged. The desktop background commands require
  Windows and the current user's Windows desktop session.

### Ownership and lifecycle

`ssdl/desktop_service.py` owns a Windows named mutex and ready/stop/done events,
scoped by the resolved writable data home in the current Windows session. Source
launches default to the project path; D05 installations default to
`%LOCALAPPDATA%\Smart Social Downloader`. An absolute `SSDL_HOME` overrides either.
See [Windows distribution](../deployment/WINDOWS_DISTRIBUTION.md). It does not
kill processes by PID, executable name or listening port. The PID in the local
record is informative, not a termination target. Separate project copies have
separate controls, although they still need different HTTP ports.

The background child has no console window. It uses the same application factory
and cleanup context as the foreground app. Readiness is published only after port
binding and application startup. Stop removes readiness, exits HTTP admission and
calls the existing application shutdown path. The done event is published after
cleanup. No new HTTP shutdown endpoint or browser-facing stop token is introduced.

Simultaneous launchers serialize their startup phase through a second, bounded
project mutex, so both can reopen the same ready service without treating a losing
child's exit as startup failure. A waiting launcher times out after 60 seconds;
it does not release an unowned mutex or kill another process.

`stop.bat` and the opt-in native Windows [background acceptance tool](../testing/DESKTOP_ACCEPTANCE.md)
are included in source packages. The installation CI also exercises background
start/stop, concurrent starts, occupied ports, project isolation and active worker
recovery. The test records browser URL dispatch; default-browser windows and
human double-click behavior remain in [ROADMAP](../development/ROADMAP.md).

## Optional desktop window

The optional pywebview shell displays the **same** HTML/CSS/JavaScript and local
HTTP API as the browser version. It adds a native window frame, folder chooser,
diagnostics Save As and explicit background-service controls. Browser and Docker
usage remain available. This is a source version requiring Python, not a packaged
installer/EXE. D04 automated acceptance and the current Windows host's manual
baseline are complete. D05 directory/installer builds and current-host executable checks are implemented;
clean Windows acceptance remains pending. See [distribution/migration](../deployment/WINDOWS_DISTRIBUTION.md). See [D04 acceptance](../testing/DESKTOP_GUI_ACCEPTANCE.md).

### Desktop window start and stop

1. Use the normal Windows/Python 3.12 setup. Double-click **desktop.bat**; first
   use installs the exact optional versions in requirements-desktop.txt.
2. Microsoft Edge WebView2 Runtime is required. Install/repair it from
   [Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/) if the
   window cannot initialize. The shell explicitly selects EdgeChromium and
   refuses an IE fallback.
3. If an older background service is already running with a port/PID-only
   record, run **stop.bat** then desktop.bat. The supervisor refuses to guess
   identity or silently terminate it.
4. Closing the window leaves background work running. The window banner and
   close confirmation say so. **Stop background service** asks for confirmation
   and preserves the queue; it is available when this window started the backend.
   An attached window shows the explicit **stop.bat** alternative.
5. Opening desktop.bat again requests focus for the existing project window.
   Browser **start.bat**, **stop.bat** and foreground Ctrl+C remain supported.

For console diagnostics or dependency repair:

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/manage.py desktop-setup
.\.venv\Scripts\python.exe -X utf8 tools/manage.py desktop
```

Startup logs are in data/background.log and data/desktop.log when an exception
occurs. A missing required component should be repaired, not worked around by
disabling browser security. The default port stays 8765; SSDL_PORT retains the
existing explicit custom-port behavior and connector must use that same port.

### Behavior and storage

The window is a resizable native frame, initially 1360×900 logical pixels with
a 1080×720 minimum. It uses the existing responsive UI. The native frame, font
rasterization and OS scaling may differ from Chrome; no pixel-identical claim
or full DPI matrix is made.

Profile storage is dedicated to this checkout at **data/webview2**, with explicit
private_mode=False. Language and page-size preferences persist across launches.
No personal Chrome profile or cookies are imported. Histories, downloaded files,
SQLite and X/Pixiv DPAPI sessions stay in the existing backend locations. The [Windows distribution](../deployment/WINDOWS_DISTRIBUTION.md) defines writable installed-app data locations and shell-neutral preference
migration; copying this profile into Electron is not the migration mechanism.

X/Pixiv sign-in still runs in **ordinary Chrome** using the same connector and
backend pairing routes. The backend's opened flag owns normal authorization
launching; the adapter does not open a duplicate. Pairing/setup/manual Pixiv
fallback links specifically choose ordinary Chrome, even if another browser is
the Windows default. Other links use the default external browser. Auth results
reach the desktop through the same HTTP polling/status rendering. Desktop-initiated
X/Pixiv callbacks, clear/reconnect and backend restart with
DPAPI login retention passed on the current host. OAuth-in-progress browser
restart/worker suspension combinations remain in the authorization roadmap.

Choose folder changes only the current settings draft; Save still sends it
through the standard HTTP settings validation. Cancel leaves the draft intact.
Diagnostics uses native Save As and UTF-8/atomic replacement; the Browser Adapter
continues using a downloaded Blob. Browser file preview, Range and Docker file
list behavior are unchanged. A native dialog can outlive a renderer cancellation
or timeout; close the pending dialog before retrying. No mutation is auto-retried.

### Boundaries and future Electron

The composition root selects the Pywebview Adapter only for explicit
`?shell=pywebview`. A regular browser with that marker has no native bridge;
desktop actions become unavailable while business HTTP remains usable. No
user-agent detection is used. `static/desktop_pywebview.js` alone handles bridge
readiness, result validation, cancellation/deadlines and method mapping.

Only describe, open_external, pick_directory, save_text, copy_text and
stop_backend are exposed. There is no AppContext, arbitrary method/channel,
filesystem-read or business-download bridge. Core imports/ordinary tests do not
require pywebview or .NET. A future Electron shell replaces this adapter and
native host while retaining standard HTTP, state and supervisor contracts.

The pinned Windows host guards top-level navigation, frames, popup requests and
bridge message Source using WebView2 native events before dispatch. Only the
exact local UI document receives native powers. External pages open outside the
privileged window; invalid schemes/credentials are rejected. File URL access,
debug tools, permissive SSL and implicit WebView downloads are disabled. Main UI
Host/Origin checks and media sandbox/CSP remain intact; no extra CORS/null-origin
exception or second Bottle business server is started.

The WebView2 integration centrally replaces pywebview's default popup/message
handlers. It also preserves the committed document URL and readiness after a
cancelled navigation: WinForms control.Source otherwise caches the attempted
URI. These are **version-pinned** hooks and must be revalidated when updating
pywebview; the real smoke exercises refusal followed by a fresh bridge call.

The host registers exact loading/error HTML bytes because NavigateToString can
emit an internal data URI. Only registered documents before a service identity
exists may navigate; they never receive native powers. Arbitrary data URLs stay
blocked. Startup errors wait for renderer initialization so its first load cannot
overwrite the error document. Real port-conflict acceptance verifies the message.

### Reproduce the native smoke

After desktop dependencies are installed:

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/check_desktop_gui.py
```

This opt-in command opens two short real WebView2 sessions in receipt-owned
temporary source/profile/data, using the current interpreter's packages. It
exercises UI/bridge readiness and allowlist, a shared HTTP write, language/page
preference persistence, blocked navigation with continued bridge access, closing
the window while backend stays reachable and explicit owned shutdown. It saves
a path-free JSON report and synthetic UI PNG in ignored data. It records the
actual device pixel ratio; it is not a clean Windows OS or complete D04 matrix.

Portable Python/Node fixtures additionally cover missing/incompatible/late
bridge, action timeout/cancellation, folder draft epochs, native export/cancel,
origin/frame/message refusal and Chrome fallback selection. The current host's
actual dialogs, OS scaling, physical keyboard/focus and real-account callbacks
were separately confirmed by the operator. Clipboard permission refusal is
covered only by injected cases.

For the expanded real GUI/Chrome/media/lifecycle matrix, run the same tool with
`--matrix`. Native clipboard, codecs, seek, Range and scripted focus are now
covered. [D04 acceptance](../testing/DESKTOP_GUI_ACCEPTANCE.md) records the separate human
keyboard/OS scaling/dialog/account observations, artifacts and untested
environments.

Technical references: [pywebview API](https://pywebview.flowrl.com/api/),
[Windows engine selection](https://pywebview.flowrl.com/guide/web_engine),
[pinned pywebview source](https://github.com/r0x0r/pywebview/tree/6.2.1).
