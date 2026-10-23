# Windows desktop background service

## Start and stop

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

## Logs and foreground mode

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

## Ownership and lifecycle

`ssdl/desktop_service.py` owns a Windows named mutex and ready/stop/done events,
scoped by the resolved project path in the current Windows session. It does not
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

`stop.bat` and the opt-in native Windows [background acceptance tool](DESKTOP_ACCEPTANCE.md)
are included in source packages. The installation CI also exercises background
start/stop, concurrent starts, occupied ports, project isolation and active worker
recovery. The test records browser URL dispatch; default-browser windows and
human double-click behavior remain in [ROADMAP](../ROADMAP.md).
