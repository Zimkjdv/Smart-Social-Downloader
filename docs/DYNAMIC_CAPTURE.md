# Optional JavaScript media capture

Implemented in **0.1.0-preview.2**. This is an optional fallback for video/audio sources created by page scripts. Normal platform extraction and static discovery remain the first steps.

## Enable it

1. Install the base project with `setup.bat` and install ordinary Google Chrome.
2. From the project directory, run:

   ```powershell
   python tools/manage.py browser-setup
   ```

3. Restart the backend using `start.bat`.
4. Open **Settings → General → Enable JavaScript media capture**, check the option and save.

The option defaults to **off**. Settings and diagnostics report whether the optional package and Chrome are present; presence does not guarantee Chrome can launch on every machine. Setup installs the pinned packages from `requirements-browser.txt` into the project `.venv`. It uses installed Chrome and does not download another browser. Ordinary setup/start do not install this optional component. Existing jobs use the setting captured when they start; later jobs use the saved setting.

繁中操作：在專案目錄執行上述指令，重新啟動 `start.bat`，於「設定 → 一般設定」勾選「啟用 JavaScript 媒體捕捉」後儲存。預設關閉；這台電腦已安裝選配套件，使用者仍可自行選擇是否啟用。

## How it works

- If the engine does not support a page, normal generic discovery scans it first. Browser discovery runs when no usable source is found or static alternatives fail without saved partial files. A narrowly recognised empty-media extractor error can also use this fallback; login, rate-limit, network, quality-cap and DRM failures are not blanket retries.
- A fresh, headless Chrome context executes page scripts and observes GET/HEAD media requests and the runtime HTML5 DOM. It briefly attempts muted playback on video/audio elements. It never clicks login, consent, CAPTCHA or arbitrary page buttons.
- Explicit MP4/WebM and other supported video/audio URLs, HLS `.m3u8`, DASH `.mpd`, and extensionless resources with a recognised media Content-Type become candidates. Video bytes and fragments are not transferred during discovery; candidates go to the existing yt-dlp download path.
- Reported DOM source heights and player grouping feed the existing Best/height-limit policy. Multiple independent or ambiguous network sources use the **To choose** workflow. Choices expose only opaque IDs, titles, hosts and counts; signed candidate URLs and headers are not saved in history.
- Selection runs discovery again, so expired URLs are not reused from the earlier scan. The selected player and quality preference keep their existing manifest/folder scopes. No transcoding is added.

This captures supported video/audio transports. It does not turn all page images/assets into downloads. A `blob:` URL is not a downloadable remote file: the underlying HTTP stream must be discovered. WebRTC, WebSocket media, POST-only APIs, bearer-header-only media, interactions, inaccessible content and DRM can remain unsupported. The tool cannot guarantee discovery of every rendition or distinguish every advertisement.

## Network and lifecycle bounds

| Boundary | Limit / behavior |
| --- | --- |
| Capture lifetime | 45 seconds, including browser startup and cleanup; the parent worker stops the owned child/browser tree if scripts or driver calls hang |
| Browser resource requests | 40 observed requests; further requests are aborted |
| Documents / frame depth | 6 documents / at most 2 nested levels |
| Resource body | 2 MiB per accepted resource; 16 MiB total; rejected oversized reads also count |
| Candidates / media attempts | 12 candidates; at most 6 download attempts shared with static fallback |
| Request pacing / 429 | Existing one-second interval, job platform scope, Retry-After, cooldown and global Rate rules |

All page HTTP resources are intercepted and fulfilled through the Python public-address transport. Redirects are checked again; DNS and the actual numeric connection follow the same policy. The browser uses a dead-end proxy and disabled direct hostname resolution; service workers are blocked and WebSockets are never connected to their remote server. Discovery rejects non-public/literal local targets, non-HTTP schemes and methods other than GET/HEAD. Images/fonts, stream fragments and keys are not fetched during discovery. Native downloads are cancelled and popups closed. This is application-level containment, **not an OS sandbox**.

The ordinary Chrome profile, extension session and saved X Cookie are not reused. A temporary anonymous context can receive cookies from this scan and JavaScript; only its domain-scoped anonymous jar is handed to the download engine in memory. Candidate headers retain only User-Agent, Referer and Origin. Passwords, normal Chrome cookies, HAR recordings and traces are not collected.

Playwright creates a temporary browser profile. Normal shutdown cleans it up; forced process termination or an OS crash can leave temporary files in the OS temporary directory. The project never reuses that profile or includes it in source archives. Stop/timeout terminates only the owned download process tree. Browser failure fails the current job and leaves other queued jobs eligible.

## Verification and maintenance

See [TESTING.md](TESTING.md) for reproducible synthetic tests, failure simulations and remaining environment acceptance. Real platform logins and restricted content are not used in these tests.

Keep `requirements-browser.txt` pinned and rerun browser capture/UI tests when upgrading Chrome or Playwright. Parent deadline supervision is deliberate: Playwright's synchronous evaluate/close calls can outlive a page timeout. The Windows WebSocket handler intentionally does not call synchronous `close()` inside the route callback, which hung in local testing; it never calls `connect_to_server()`.

Primary API references: [Playwright network interception](https://playwright.dev/python/docs/network), [Route fulfillment](https://playwright.dev/python/docs/api/class-route), [service workers](https://playwright.dev/python/docs/service-workers), and [WebSocketRoute](https://playwright.dev/python/docs/api/class-websocketroute).
