# Backend supervisor contract (D02)

The Windows launcher and future GUI share `ssdl/desktop_service.py`.
`ensure_backend()` starts/attaches **without opening a page**; `start(check)` is
the compatible browser launcher combining ensure and `open_page(result)`.
Console and Docker entry points remain independent. No GUI package is imported.

## Identity and readiness

`/api/identity` uses the ordinary Host/Origin/cross-site guard. It returns 200
when application API and shipped index are ready, otherwise 503. It reports
format_version:1, service:ssdl, instance (random AppContext state-instance ID),
scope (normalized writable-data-home hash), app_version, api_contract:1, actual origin
and port, and api_ready/ui_ready. No local path, cookie or stop credential is
included. `/api/health` retains its stricter worker/persistence/dependency health;
missing engines must not prevent opening diagnostics.

The private local record adds an informational PID. Attachment requires the
project's Windows owner mutex, ready event and non-stopping state **plus** a
bounded, direct loopback identity response matching the record. Arbitrary HTTP
200, a PID or the existence of a stale file is insufficient. No proxy or redirect
is used; connect has a two-second bound and response header/body processing has
an absolute two-second shutdown deadline, including trickle traffic. Metadata is
bounded to 4096 bytes. This initial protocol accepts the exact application
version, control version and API contract; future version-range compatibility
must be explicitly designed. Additive metadata fields may be ignored.

`ensure_backend(check_environment=None)` returns the identity plus ownership
`started` or `attached`. Repeated launches retain the actual running port even
if a new environment value differs. Cold startup honors configured/default port;
it never silently chooses another one. An occupied foreground/foreign port
fails without restoring or overwriting its data. Startup waits at most 60 seconds
after the existing launch-lock wait, observes child exit, and leaves timeout
cleanup to explicit operator stop. It does not kill a PID.

The browser launcher retains its existing environment preflight. A GUI may omit
the preflight so installed core code can display missing-engine diagnostics.
If an older running backend has the old port/PID-only record, explicitly run
`stop.bat` and restart before using the new control protocol; it is not silently
adopted or terminated. Data/history/login formats are unchanged.

## Ownership and shutdown

Launch/attach/stop serialize through the existing project launch mutex. Only a
descriptor marked started and matching the current instance can use
`stop_owned(result)`. It signals **instance-specific Windows stop/done events**,
so even a replacement outside the launch protocol cannot receive a stale stop.
An attached shell cannot implicitly stop another session's service.

`stop.bat` / `stop()` remains the explicit operator stop for this project's
current or pending service, including an older version. Foreground services
remain under Ctrl+C. No HTTP shutdown endpoint is added. All stops retain the
AppContext worker/auth/helper/writer shutdown and durability order; stop timeout
does not force-kill anything.

`WindowSession` is a separate data-home-scoped mutex and focus event, acquired and
released on the GUI main thread. A repeated process requests focus and exits;
the primary can consume the focus event. Closing these window controls does not
stop the backend. Actual GUI focus, close messaging and explicit stop controls
are implemented in D03, not inferred from this kernel-control fixture.

## Shell-neutral control CLI

Use the project environment, with the repository as working directory:

```powershell
.\.venv\Scripts\python.exe -m ssdl.desktop_control ensure
.\.venv\Scripts\python.exe -m ssdl.desktop_control status
.\.venv\Scripts\python.exe -m ssdl.desktop_control stop
```

`ensure` never opens a browser. stdout is one JSON object
`{format_version:1,ok:true,result:...}` and exit 0; diagnostic launcher output
goes to stderr. Failure is exit 1 with ok:false and
error_code:backend_control_failed, without echoing private exception details.
`stop-owned` reads a bounded descriptor JSON from stdin terminated by EOF. It
checks ownership and instance before signaling. This CLI is the future Electron
control boundary; business operations still use HTTP.

## Evidence boundaries

Portable fixtures cover incompatible/foreign metadata, arbitrary HTTP 200,
replacement identity, trickle deadline, API readiness under unhealthy engines,
origin rejection, startup exit/timeout, ownership and window-control cleanup.
`tools/check_desktop.py` additionally exercises real Windows start/attach,
secondary-process focus delivery, closing window controls while backend stays
available, attached/stale stop refusal, owned stop and restart after deliberate
receipt-owned process-tree exit. Existing batch/concurrent/port/durability cases
remain. These controls do not constitute WebView2 acceptance or a fresh OS test.
