# Docker host Chrome playback acceptance

This optional gate extends the [46-stage Docker matrix](DOCKER_HOST_ACCEPTANCE.md)
with seven stages in **installed host Google Chrome**. It drives the shipped web
interface and native image/video documents, rather than substituting HTTP byte
checks for decoding. Run from source with Python 3.12, a local Linux amd64 Docker
engine, Compose, ordinary Google Chrome and the pinned host-only dependency:

```powershell
python -m pip install -r requirements-browser.txt
python tools/check_docker.py --browser --report data/docker-browser.json
```

`--browser` includes runtime, service, interaction and host-storage acceptance:
**9 + 14 + 15 + 8 + 7 = 53 stages**. To observe the temporary browser window,
add `--browser-headed`. This option requires `--browser`. Docker Desktop users
whose CLI does not select the Linux engine can also pass
`--host npipe:////./pipe/dockerDesktopLinuxEngine` on Windows.

| Stage | Required evidence |
| --- | --- |
| `chrome_runtime` | Fresh host Chrome context loads the real Docker UI and completed synthetic job on a matching loopback port |
| `file_picker_image` | Folder icon opens the real file list; selecting the original PNG opens a new tab that decodes to its expected dimensions |
| `keyboard_file_picker` | Enter opens the dialog, focus starts at Close, Tab selects the first file and Enter opens the decoded image |
| `h264_playback_seek` | The play/view action opens the generated H.264 MP4; Chrome decodes frames, advances time, seeks and reaches the end |
| `reload_retains_state` | Browser reload and the UI refresh action preserve the backend job's completed status and recorded file count |
| `renamed_file_rejection` | Renaming an invented original makes the UI selection return 404 instead of serving a different file |
| `browser_reader_recovery` | The job remains completed, health responds, a subsequent original opens/decodes and no application JavaScript exception was raised |

## Isolation, failures and receipts

Chrome uses Playwright's `channel="chrome"`, an ephemeral context and no personal
profile, X session, extension or saved browser data. Google Chrome is already
installed; the gate does not install or alter it. Playwright's documented
[branded browser channel](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge)
is used. The application image still contains neither Chrome nor Playwright.

Only GET/HEAD requests to this fixture's exact `127.0.0.1` origin are allowed in
the browser context. Service workers and accepted downloads are disabled. No
HAR, trace, video recording, screenshot, ticket, cookie or raw error is retained.
The queue is paused and media comes only from the existing synthetic probe.
Muted playback uses normal autoplay policy; there are no codec/policy bypasses.
The generated video exercises H.264/yuv420p; audio and other codecs remain outside
this result. Non-default free ports avoid touching the user's running service.

The categorical JSON report records Chrome version, source fingerprints, passed
stages and `browser_mode: isolated_chrome_automated`. Any missing Chrome/Playwright,
decode, UI, timeout or cleanup failure fails the gate; there is no success-by-skip.
`browser_error` identifies the last browser stage when available. An incomplete
receipt replaces previous success before execution. Only receipt-owned Docker
resources and the temporary browser context are cleaned up.

## Remaining human checks

This is automated **real browser decoding and UI** acceptance. It is not a human
X login or an all-codec certification. The following remain in
[ROADMAP](../ROADMAP.md#docker-化部署):

- Host Chrome connector first installation/reload and pairing on default/custom
  ports using the user's authorised X account.
- Actual ten-minute ticket expiry, cancel/re-pair and platform-revoked login.
- Human assessment of playback controls, sound and other downloaded codecs.
- Windows default-player and Explorer interaction; a Docker container cannot
  launch the host's desktop applications.
- Another physical host and an actual application-version migration. Cross-host
  acceptance is currently deferred by the user.

For each manual attempt record the source revision, host OS, Chrome/connector
versions, port, steps, expected/observed result and pass/fail in a private local
record. Never include tickets, Cookie values or personal media in public evidence.
Keep Docker marked experimental until the remaining acceptance is completed.
