# Windows background lifecycle acceptance

`tools/check_desktop.py` runs the shipped `setup.bat`, `start.bat` and `stop.bat`
in a newly extracted, receipt-owned Windows/Python 3.12 installation. It never
stops the ordinary project or uses its saved sessions, history or media.

```powershell
python tools/check_desktop.py --report desktop-result.json
python tools/check_desktop.py --work-dir D:\Temp --keep-workspace
```

The parent directory must exist. Dependencies are installed from public PyPI
into a new venv. The optional retained workspace contains synthetic diagnostics;
without `--keep-workspace`, only that tool-owned directory is removed. A success
report contains phase names and scope, without paths, tokens or process IDs.
The same acceptance also runs at the end of `check_installation.py`, reusing
its installed disposable venv, including in the `install-windows` CI job.

## Assertions before fallback cleanup

1. Start at a fresh custom port; require real HTTP/environment readiness, a
   successful batch exit and dispatch of the correct browser URL. The background
   process must have no console window according to `GetConsoleWindow`.
2. Start again with an invalid new port and a different output environment.
   Require the original PID/port and another dispatch to the original URL.
3. Start/stop a second source root at a different port; its controls must not
   stop the first root, including when it has no running background instance.
4. Admit two synthetic download jobs through the real API. While one real
   pipe-speaking worker/helper tree is active and another job is queued, pause
   and run real `stop.bat`. Require joined threads, a closed/durable state writer,
   exited worker/helper handles, removal of the service record and an exclusive
   rebind of the released port. Preserve the synthetic partial bytes.
5. Stop again; require success and unchanged saved-state bytes.
6. Run two simultaneous cold `start.bat` calls. Both must exit successfully,
   preserve the recovered job IDs/attempts/quota/paused queue and partial bytes,
   and rotate a log exceeding 2 MiB exactly once. Stop normally again.
7. Hold the same port with an owned foreground entry. Background startup must
   fail nonzero and log the bind error. `stop.bat` must leave that foreground
   entry serving HTTP. Failed background startup must not change saved state.

Each launcher is admitted only after attachment to an owned Windows Job Object.
That object remains open until graceful assertions pass. If an assertion fails,
fallback cleanup affects only its admitted descendants. The foreground conflict
fixture is deliberately closed through its own Job Object, not counted as a
graceful foreground acceptance. No process is selected for termination by name,
port or an arbitrary recorded PID. Worker liveness uses held process handles.

## Fixture boundary and remaining manual scope

A temporary `.pth` hook is installed **only in the disposable venv**, with a
matching root receipt and explicit random admission. It replaces media transport
with the existing synthetic worker, observes application closure, and records
`webbrowser.open` calls. Real batch entry points, Windows events/mutexes, HTTP,
scheduler, worker supervisor, persistence and application shutdown remain active.
The second root has its own venv/state/controls and imports the same read-only
dependency directory; this isolation check is not a second package installation.

Recording `webbrowser.open` proves the requested URL and automatic dispatch path;
it does **not** prove the Windows default-browser association or visible page.
Human double-click/keyboard/prompt behavior, the actual default-browser window,
factory Windows installation and real login/media remain explicit manual work
in [ROADMAP](../ROADMAP.md). Synthetic worker cancellation does not establish
every upstream downloader's shutdown behavior.

This acceptance exposed a launcher concurrency risk during source inspection:
service ownership alone let a losing child exit before its peer became ready.
The launch phase now has its own bounded, project-scoped mutex. An abandoned
mutex can be acquired; timeout does not release an unowned mutex or start a child.

## Recorded result

See [testing results](TESTING.md#windows-background-lifecycle--2026-10-24) for the
native Windows run, regression counts and remaining scope.
