# Windows console shutdown acceptance

The Windows installation acceptance tool now exercises the shipped
`ssdl.app.main()` entry point with a real **CTRL_C_EVENT**. Run it with:

```powershell
python tools/check_installation.py --browser
```

This is an automated console-event check on Windows / Python 3.12. It is separate
from manually pressing keys in Windows Terminal, PowerShell or cmd, and from a
factory Windows installation or real X sign-in. Those remain in
[ROADMAP](../ROADMAP.md).

## Scope and ownership

- The real base Python interpreter starts with `-I -S` in a **new hidden console**.
  It waits for receipt/admission before creating any venv or application child.
  The owner attaches its kill-on-close Job Object before admission.
- The gate must be the only console client before child creation. The application
  checks the receipt and console membership again before generating the event:
  only its gate, itself and its immediate venv redirector can be attached; the
  controlling caller must not be present. Missing, shared or unknown membership
  fails closed. No process is attached to another terminal.
- The gate uses a no-op SIGINT handler rather than inheritable SIG_IGN. The
  application's default KeyboardInterrupt handler receives the real event.
  `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)` targets that isolated console;
  CTRL_BREAK, an input character or an injected Python exception is not used.
- The real entry, HTTP server, AppContext, scheduler, writer, services and worker
  supervisor execute. Only media transfer is substituted with a synthetic
  pipe-speaking worker, which starts a sleeping helper after supervisor admission.
  It creates synthetic partial bytes; it never invokes a platform extractor.
- Roots, state, media, receipts and ports belong to the disposable installation.
  No production service, normal browser profile or personal login is used.

Native behavior is documented by Microsoft:
[console events](https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent),
[console membership](https://learn.microsoft.com/en-us/windows/console/getconsoleprocesslist),
[creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags).

## Required acceptance results

1. **Idle:** after normal environment readiness, send Ctrl+C and require exit 0,
   closed AppContext, stopped owned service threads, a closed durable writer and
   a stopped control thread. Exclusive port rebind must succeed.
2. **Active plus pending:** add two synthetic URLs through the normal API, resume
   until the first worker and its helper are running, then pause further admission.
   Hold SYNCHRONIZE-only handles to both worker processes, send Ctrl+C and require
   normal entry shutdown and both processes to exit. Checks run **before** closing
   the outer cleanup Job Object; fallback termination cannot make acceptance pass.
   Each held handle has a bounded five-second wait and cannot be confused by PID
   reuse. Partial bytes must be unchanged.
3. **Restart:** start the real entry again and require the exact two job IDs,
   queued statuses, no active job, one started attempt and one unstarted attempt,
   saved pause/hourly limit and exactly one consumed quota slot. Interrupt this
   entry normally too. Existing original-media sentinel bytes must survive.

Each console phase removes only its previous fixture closure report before
launch. A nonzero exit, failed event, stale/missing report, surviving process or
incorrect restored state fails the run. Deadlines and the outer owned Job Object
remain fallback cleanup for a failing fixture, not evidence of graceful shutdown.

## Reports, CI and limitations

The installation JSON report adds `idle-console-ctrl-c`,
`active-console-ctrl-c-owned-tree`, `console-restart-durable-queue`, and
`console_close: real-ctrl-c-in-owned-hidden-console`. Local diagnostic receipts
and PID records stay in the owned temporary copy; source ZIPs contain no receipts.
The existing `install-windows` CI job runs these phases in a fresh source/venv.

Offline contracts cover refusal before spawning/signalling, explicit admission,
hidden-console flags, native signal failure, handle ownership/cleanup and strict
HTTP status expectations. They do not substitute for the real console run.

This check does not exercise a batch shell's interactive `Terminate batch job?`
prompt, physical keyboard dispatch, repeated Ctrl+C during native I/O, closing a
terminal window, forced OS termination, or real FFmpeg/platform cancellation.
Native disk I/O can still delay graceful shutdown. See
[installation acceptance](INSTALLATION_ACCEPTANCE.md), [reliability](RELIABILITY.md)
and [actual verification records](TESTING.md).
