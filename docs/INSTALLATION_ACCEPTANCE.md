# Windows installation acceptance

`tools/check_installation.py` exercises the shipped scripts in a disposable
source extraction and a newly created Python 3.12 venv. It downloads dependencies
from public PyPI into that copy and its owned cache. Run it explicitly; ordinary
unittest discovery does not create this venv or install packages.

## Run

Prerequisites: Windows, Python 3.12 and an internet connection. Node.js 22+ and
ordinary Chrome enable their optional checks. The application and actual X login
use the project's normal support boundaries.

```powershell
python tools/check_installation.py --browser
python tools/check_installation.py --browser --work-dir D:\Temp --report installation-result.json
```

The parent passed to `--work-dir` must already exist. The tool creates a unique
temporary directory beneath it and deletes only its own directory on success or
failure. Allow space for a new venv, wheels and optional Playwright driver.
`--report` writes a path-free JSON success summary with versions and passed
phases. `--keep-workspace` retains the synthetic copy/cache/logs for local
diagnosis and prints its location; remove that owned copy after inspection.

## Actual acceptance phases

1. Build and verify the allowlisted source ZIP; extract it under a path containing
   spaces and Unicode. Assert that `.venv` and `data` are absent. Clear inherited
   Python/pip/application overrides, disable personal pip configuration, use public
   PyPI and an owned pip cache/temp location. PATH still supplies system runtimes.
2. Execute the real `setup.bat`. Verify the locked setup marker, Python 3.12,
   `.venv` interpreter prefix, disabled system site packages and every exact core
   baseline pin. All application state and the media target belong to the fixture.
3. Run real `start.bat` with a fresh custom loopback port and an offline empty
   package index. Require engine and environment readiness. Verify unique output
   scope and application version before mutations. Save pause and hourly limit 73
   through the normal local APIs. Check unchanged marker/installed versions.
4. Clean up the batch process through its own Windows Job Object. This is **forced
   batch cleanup**, not evidence of interactive Ctrl+C handling. Separately start
   the installed AppContext/HTTP server through a receipt-gated fixture, restore
   settings and stop normally: require joined owned threads, a closed writer and
   no pending generation. Exclusive rebind confirms the port can be reused.
5. Remove only the fixture's setup marker and run `start.bat` again. Require its
   automatic setup repair, baseline pins and retained settings, then close the
   application normally through the separate fixture.
6. Execute real `update.bat` against the current compatibility ranges and record
   resolved core versions. It may select the same versions as the baseline.
   Install **IDNA 3.10 without dependencies in this isolated venv only**, confirm
   the version changed, then run `setup.bat` and verify every original baseline
   pin. This provides a real restoration probe even when no newer engine exists.
   Review the fixed probe if a future baseline itself uses IDNA 3.10.
7. Compare saved-state and synthetic original-media hashes across package
   maintenance. With `--browser`, install and verify all optional browser pins
   through the normal CLI and recheck core pins. Restart/close the installed app
   normally again. An invalid-port launch must exit nonzero without pausing or
   altering saved state.

Baseline restoration reinstalls exact required versions; it does not remove every
extra package left by an update. That distinction is also in [Maintenance](MAINTENANCE.md#dependency-updates-and-action-pins).

## Ownership and noninteractive scripts

The gate uses the real base Python interpreter, attaches its Windows Job Object
and only then admits child creation. Venv redirectors, batch scripts, pip and the
application inherit that group. Cleanup targets this admitted group, never a
process name or the service on port 8765. A fresh kernel-selected port plus output
scope/version checks prevent mutations against an unrelated local service.

The admitted children use ordinary inherited Job Object membership, with no
breakaway flags; the existing ProcessGroup uses kill-on-close. See Microsoft's
[Job Objects reference](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

`tests/helpers/install_runner.py` requires a matching random receipt in its own
source root. Imports or an invalid receipt cannot construct an AppContext. No
receipt ships in source packages. The graceful fixture uses installed dependencies
and the real services/server without replacing their persistence or shutdown.

Setting `SSDL_NONINTERACTIVE` suppresses `pause` in setup/start/update scripts;
exit codes and console errors remain. Without it, the normal interactive script
behavior is retained. Environment probes use DEVNULL stdin: the real pip check
otherwise stalled when it inherited the fixture's live control pipe. HTTP waits
are bounded, and closed-port detection uses exclusive binding rather than treating
a Windows loopback connection timeout as proof of shutdown.

## CI and remaining acceptance

The `install-windows` job in the existing workflow uses Python 3.12/Node 22 on a
fresh hosted Windows runner and calls this tool with `--browser`. It installs into
the extracted `.venv`; the job does not install application packages globally.
The separate `windows` job retains all Python/Node/Chrome and extracted-source
regressions. Both jobs use reviewed full Action SHAs and read-only permissions.

This verifies fresh source/venv behavior on an existing Windows image, including
the hosted runner image. It does not establish factory Windows installation,
general desktop Ctrl+C behavior, real X pairing/login, live media compatibility
or correctness of every future engine release. No ordinary Chrome profile,
production Cookie/history, service restart or live media download is used.
Those environment/account checks remain in [ROADMAP](../ROADMAP.md); actual
results and development-failure observations are in [TESTING](TESTING.md).
