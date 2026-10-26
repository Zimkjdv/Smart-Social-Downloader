# Windows distribution (D05)

D05 builds a Windows x64 directory bundle and a per-user Inno Setup installer.
Python, Node, FFmpeg, the download engines, optional capture dependencies and
desktop DLLs are included. No Python/Node installation is required to run it.
Google Chrome remains an external application. There is no onefile extraction,
automatic application update, signing, tray or startup registration.

Implementation and current-host executable/installer acceptance are complete.
**Clean Windows 10/11 acceptance remains pending:** this host has no Windows
Sandbox and the owner confirmed no other clean test environment was available.
Removing external Python/Node from PATH is separate evidence, not a fresh OS.
No GitHub Release/tag or signed public release has been created.

## Install and use

Run `SmartSocialDownloader-<version>-windows-x64-setup.exe`. The default program
directory is `%LOCALAPPDATA%\Programs\Smart Social Downloader`; no administrator
permission is requested. The source version's setup/start/update batch files are
not used by the installed application. Open the Start menu shortcut or
`SmartSocialDownloader.exe`. Close keeps background work running. Use the GUI's
confirmed Stop action or the Start menu **停止背景服務** shortcut before updating
or uninstalling; the installer refuses active installed processes and never
forces them closed.

Setup checks Microsoft's documented WebView2 registry keys. If Evergreen Runtime
is missing, it runs the bundled Microsoft bootstrapper and requires a successful
install before continuing. This first Runtime installation needs Internet;
repair/install it separately for an offline machine. The bootstrapper's fixed
download/hash and Microsoft publisher signature are checked at build time.
Windows 10 build 19041+ or Windows 11 x64 is the target; other architectures and
clean OS versions have not been accepted.

Stop an older source service with its `stop.bat` before using the installed
application on port 8765. This also avoids confusing the Chrome connector with
two different data scopes. Ordinary Chrome authorization and the connector ID
are unchanged. Extract the connector ZIP supplied by the connection page when
installing it; that endpoint reads bundled resources, not the writable data root.

## Data locations and switching hosts

| Content | Source default | Installed default |
| --- | --- | --- |
| HTML/CSS/JS, connector, native DLLs | Project directory | Application `_internal`, treated as resources |
| History, SQLite, encrypted X/Pixiv sessions | Project `data` | `%LOCALAPPDATA%\Smart Social Downloader\data` |
| Preview cache / WebView profile | Project `data` / `data\webview2` | User root `cache` / `cache\webview2` |
| Default media | Project `downloads` | User root `downloads`; choose a folder in Settings |
| Import backups | User root `data-backups` | User root `data-backups` |

`SSDL_HOME` can explicitly select an absolute writable data scope for either
source or installed code. Installed data cannot be under the application
directory or Program Files. A different executable/install location does not
change the default user scope. Foreground and background entry points share a
writer lease; window/owner/identity locks are keyed by the resolved data scope.
An incompatible running version must be stopped explicitly, never replaced by
guessing a PID or taking over its files.

Language and page size use versioned `data/ui-preferences.json` through
`GET/POST /api/ui-preferences`. The first successful read with no saved file seeds
it from legacy localStorage. Later hosts restore the HTTP value; late hydration
cannot overwrite a user's fresh selection, writes keep order, and failed writes
are not automatically retried. A future Electron host uses this file/API and the
same runtime supervisor; copying WebView profile folders is not the migration.

## Import and recover existing source data

1. If legacy language/page size matters, first open the D05 source GUI once so
   its existing profile seeds the neutral HTTP preference file.
2. Close the source and installed windows, and stop both background services.
3. Use the Start menu **匯入舊版資料**, select the old project directory containing
   `data`, and confirm the source/destination shown. The console alternative is:

   ```powershell
   & "$installDir\ssdl-runtime.exe" --role migrate "$oldProject"
   ```

4. Import validates state/version, takes SQLite backup snapshots, verifies their
   integrity and checks encrypted sessions can be read by this Windows user.
   Original media paths remain in history; media and source data are not moved.
   Source mutation, newer state, links, active writers, full disk or invalid
   input refuse the import before replacing the destination.
5. The existing destination `data` directory is retained under
   `data-backups\<backup-id>\data`; the validated import replaces it by directory
   rename. Start the installed application and continue from that data scope.
   This is a one-time cutover, not synchronization with older source versions.
6. To undo, stop/close again, choose **回復匯入前資料** and select that backup,
   or run `ssdl-runtime.exe --role rollback <backup-id>`. Newer destination data
   is retained as `after-data`. A prepared backup left by an interrupted
   directory swap can also restore the prior data. Neither command deletes
   media. Keep backups private; they contain history and encrypted sessions.

DPAPI imports require the same Windows user/machine. An unreadable encrypted
session refuses import instead of silently dropping it or saving plaintext.
Do not run an older source copy against its old data in parallel after cutover;
to intentionally share the new scope, use D05 code with the same `SSDL_HOME`.
Stop *all* older foreground instances, including custom-port instances, first.
Old binaries do not implement the new writer lease.

Program rollback means stopping the application and reinstalling a retained
previous installer. Data rollback is the explicit operation above. The tested
installer upgrade/downgrade uses two installer versions with the same current
application/data schema; it does not promise arbitrary future schema downgrades.
Uninstall removes program files and shortcuts, preserving user data, backups,
selected media and shared WebView2 Runtime. It does not uninstall Chrome.

## Build from reviewed source

Use Windows x64 / Python 3.12 and a disposable build venv. Core/source/Docker
setup does not install release tooling. On a Linux Docker engine (local Docker
Desktop or the Linux CI job), build the fixed Windows media tool first:

```powershell
python tools/prepare_windows_ffmpeg.py --output dist/windows-media
python -m pip install -r requirements.lock.txt -r requirements-browser.txt -r requirements-desktop.txt -r requirements-build.txt
python tools/build_windows.py --ffmpeg-dir dist/windows-media --output dist/windows-build
```

Output paths must be new. The build verifies exact runtime versions, pip check,
download hashes and Inno/Microsoft signatures. A compiler can be supplied with
`--iscc`; otherwise verified Inno Setup 6.7.3 is installed per-user into the
ignored vendor cache. Git builds copy indexed file names with current reviewed
bytes, excluding unrelated untracked files. Source-archive builds use the source
allowlist. Outputs include an inspectable directory, ZIP, installer and hashes.

`SmartSocialDownloader.exe` is windowless. `ssdl-runtime.exe --role` explicitly
selects backend, control, worker, Pixiv exchange, diagnose, migrate or rollback;
no Python `-m` switches are passed to a frozen bootloader. UTF-8 JSON and existing
binary worker pipes remain the transport. Installed diagnostics checks bundled
metadata rather than launching an external pip interpreter. Bundled tools are
added to the process PATH, not the user's global PATH.

The FFmpeg build enables native codecs, zlib, Windows TLS and PNG/JPEG preview
support, with external GPL codecs/nonfree options disabled. It supports stream
copy/merge and the tested thumbnail inputs; it is not identical to the source
wheel's broader external-codec build. Additional codec/platform sampling remains
release work. No media is re-encoded by the download queue.

The package includes component licenses, Node/CPython/WebView2 notices, the exact
FFmpeg/zlib source archives/build recipe, application source ZIP and gallery-dl /
mutagen source archives. The wheel's unrelated FFmpeg binary is excluded.
Application MIT licensing does not relicense bundled third-party code; see
[third-party notices](../THIRD_PARTY_NOTICES.md). Keep these directories with the
program when redistributing a folder bundle.

## Acceptance and CI

```powershell
python tools/check_windows_distribution.py --bundle dist/windows-build/dist/SmartSocialDownloader --report data/frozen.json --gui --iscc .release-check/windows-vendor/inno-6.7.3/ISCC.exe
```

The helper requires a fresh receipt and stdin admission after Windows Job Object
attachment. It starts only owned disposable processes. A strict pass precedes
fallback cleanup. Synthetic sessions are actual DPAPI ciphertext; no account
credentials or live platform media are used. Local GUI probing requires an
explicit matching disposable receipt and runs fixed compiled checks, exposing no
HTTP/bridge eval channel. Ordinary launches do not import the probe.

Current-host acceptance passed bundled tool/metadata discovery with external
Python/Node removed from PATH, PNG thumbnail decoding and HTTPS protocol,
framed worker and invalid Pixiv exchange, actual frozen WebView2/UI/bridge and
neutral preferences, close with backend alive, attach from another installation,
attached-stop refusal, graceful stop, restarted history/login/preferences/media,
and real silent install/update/installer rollback/active refusal/uninstall.
Installer tests use a unique AppId and disposable location, preserving any real
installation. Busy-profile cleanup is reported separately from acceptance.

`windows-package.yml` cross-builds the media tool, builds the Windows bundle,
executes frozen/installer acceptance and uploads preview artifacts/checksums only
after success. Hosted GUI interaction is not claimed; local `--gui` is separate.
The existing core/source/Docker lanes retain no GUI dependency.

Remaining clean-machine gate: test Windows 10 and 11 without Python/Node,
missing Runtime online bootstrap/failure/offline repair, real double-click and
shortcuts/native prompts, installed Chrome real-account callbacks, and restore /
uninstall in that environment. No clean-machine or installer-driven Runtime
installation result is inferred from the current host's installed Runtime.

References: [PyInstaller runtime](https://pyinstaller.org/en/v6.22.3/runtime-information.html),
[PyInstaller subprocess caveats](https://pyinstaller.org/en/v6.22.3/common-issues-and-pitfalls.html),
[Inno application mutex](https://jrsoftware.org/ishelp/topic_setup_appmutex.htm),
[Microsoft Runtime distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution),
[zlib 1.3.2 source/hash](https://zlib.net/).
