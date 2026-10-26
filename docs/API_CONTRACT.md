# Shared HTTP and desktop contracts (D01)

Browser and future desktop shells share `static/api.js`, controllers, HTTP
routes and AppContext. References: `ssdl/http_api.py`, `ssdl/job_views.py`,
`ssdl/local_media.py`, `static/api.js` and `static/desktop.js`. No API framework,
second queue or authentication store is added.

## Transport, errors and compatibility

Use relative `/api/...` URLs at the actual server origin, normally
`http://127.0.0.1:8765` on Windows (`SSDL_PORT` can select another port). API reads
and writes require one loopback Host at that port, reject cross-site fetches and
validate Origin when supplied. `Origin: null` is rejected. Missing Origin is
accepted for local non-browser clients; loopback does not authenticate other
local processes. A shell must preserve these checks.

POST takes one UTF-8 JSON object, including `{}` for parameterless actions, and
one Content-Length between 1 and 100,000 bytes. Transfer-Encoding is rejected.
JSON failures contain `{error: string}`; database failures additionally expose
`error_code`. Messages are display text, not programmatic discriminators. Usual
statuses: 400 invalid/unsupported operation, 403 source/path refusal, 404 missing
resource, 408 body deadline, 409 stale/conflicting operation, 429 queue capacity
and 503 shutdown/unhealthy service. A 202 starts background work; poll its status.

`SSDLApi.request(path, {method,body,timeoutMs,signal,validate})` validates content
type, JSON and route-specific schema. Its default 15-second deadline covers
headers **and** body; Pixiv actions use 35 seconds. The server has a 10-second
absolute input deadline and 5-second socket write bound, not a guarantee that a
background task completes in that time. Media bypasses the JSON client.

Client codes: http_error, invalid_response, invalid_json, invalid_schema,
timeout, cancelled and network. Cancellation stops waiting, not an accepted
write. `error.uncertain` marks a mutation that may have committed (lost/invalid
response, timeout/cancellation or server failure). Reconcile through a read;
**never automatically repeat the mutation**. Retain the last good snapshot and
user drafts. Existing tests cover header/body timeouts and single-send behavior.

Preserve existing fields, routes and statuses. Add optional fields with schema
validation before using them; breaking changes require an explicit compatibility
decision and regression tests. No versioned URL prefix is introduced.
`app_version` is the application version; legacy `version` is yt-dlp's version.
Neither is a protocol version. Current health also measures dependencies and is
not an identity/attach protocol (D02).

## Shared representations

`State` includes jobs, counts, paused/ready, download_dir, x_cookie_file,
x_auth/pixiv_auth, safe_queue, rate_limit, storage, and optional environment,
persistence, worker, databases and thumbnail_cache. Auth status contains no
cookies, access/refresh tokens or PKCE verifier. Keep one-use pairing URLs out
of general snapshots, browser storage and logs.

Ordering uses `state_instance` (32 hex) paired with `state_sequence` (nonnegative
integer). Ignore older sequences and retired instances. Jobs are summaries:
at most 20 preview filenames, plus file_count/files_complete/warning_count.
Retrieve complete files/details separately. Statuses: queued, active, completed,
failed, selecting. `file_actions` describes the **backend** (`desktop` native host
or `browser` container preview), never the UI shell.

State-producing requests accept view query page (default 1), page_size
(10/20/50, default 20), status/platform (default all), search (300 characters).
The server normalizes/clamps pages and unsupported values; `jobs_page` describes
the actual result. Counts and active_job stay global.

## Route inventory

`{id}` means a server-issued job ID. `State` means the snapshot above. Optional
inputs retain existing defaults. All these operations stay on HTTP, never a
desktop bridge.

| Method / path | Input | Success / behavior |
| --- | --- | --- |
| GET `/api/state`, `/api/jobs` | View query | 200 State |
| GET `/api/summary` | None | 200 summary State, empty jobs and no jobs_page |
| GET `/api/ui-preferences` | None | 200 `{preferences:null}` before first save, otherwise `{preferences:{schema:1,language,page_size}}`; shared by browser and desktop shells. |
| POST `/api/ui-preferences` | Exact object: schema:1, language:en/zh-Hant, page_size:10/20/50 | 200 `{preferences:...}` after atomic save; rejects extra fields, future schemas and invalid values with 400. Uses the same origin guard and mutation uncertainty rules. |
| POST `/api/jobs` | urls: 1–30 strings; mode urls/x_profile/pixiv_profile; video_quality best/2160/1440/1080/720/480/360/240/144 | 201 `{added,reused,already_pending,rejected,state}`; ID arrays, per-URL rejections. Profiles require best quality; max 200 retained jobs. |
| POST `/api/pause` | paused: boolean | 200 State; pause scheduling |
| POST `/api/jobs/{id}/stop` | `{}` | 200 State; request active worker stop, retain files; 409 unless active |
| POST `/api/jobs/{id}/retry` | `{}` | 200 State; 409 for pending work or profile conflict |
| POST `/api/jobs/{id}/select-media` | selection_id from current options | 200 State; 409 unless selecting, 400 for invalid selection |
| POST `/api/jobs/{id}` | `{}` | 200 State; remove queue/history, retain files; 409 if active |
| POST `/api/jobs/clear-done`, `/api/jobs/clear-all` | `{}` | 200 `{removed,state}`; clear-all adds pending_active and defers removing active work |
| POST `/api/jobs/retry-failed` | `{}` | 200 `{retried,state}` |
| POST `/api/rate/reset` | `{}` | 200 `{reset:true,previous_used,state}` |
| POST `/api/settings` | Required download_dir (nonblank string ≤2000); optional x_cookie_file (≤2000), hourly_job_limit (integer 1–1000), no_progress_timeout (integer 30–3600), dynamic_capture (boolean), cooldown_mode (global/platform) | 200 persisted State; omitted settings retained. Backend validates/resolves paths; optional capture runtime required for dynamic_capture. |
| GET `/api/jobs/{id}/files` | offset ≥0 (default 0), limit 1–100 (default 100) | 200 `{job_id,total,offset,limit,next_offset,files:[{index,filename}]}`; next_offset null at end |
| GET `/api/jobs/{id}/details` | None | 200 job summary plus full warnings/error_detail |
| POST `/api/downloads/open` | `{}` | 200 `{opened:true}`; create/open configured Windows directory; unsupported/OS failure 400 |
| POST `/api/jobs/{id}/open-file`, `/open-folder` | file_index (integer, default 0), exact current filename | 200 `{opened:true}` after validation; stale 409, escape 403, missing 404, unsupported media 400. Container open-file adds browser:true/url; open-folder 400, use UI file list. |
| GET/HEAD `/api/jobs/{id}/content` | Exactly file_index/filename, optional Range header | 200 full / 206 single byte range / 416 invalid range. Exact current file, root containment and supported media required. Sandbox/CSP, inline content; no arbitrary filesystem browsing. |
| GET `/api/jobs/{id}/thumbnail` | key from thumbnail_url, optional If-None-Match | 200 JPEG, 304 unchanged or 404 unavailable/stale |

| Method / path | Input | Success / behavior |
| --- | --- | --- |
| GET `/api/health` | None | 200 healthy / 503 unhealthy `{service:"ssdl",status,checks}`; application/worker/persistence/dependencies. Probe directly, not through State validator. |
| GET `/api/identity` | None | D02: 200 UI/API ready / 503 unavailable; versioned service/instance/scope/app/API/origin/port metadata. Same origin guard; see [supervisor contract](DESKTOP_CONTROL.md). Not a shutdown capability. |
| GET `/api/environment` | None | 200 phase/busy/ready, checked_at, status/errors/warnings, port, checks |
| POST `/api/environment/refresh` | `{}` | 202 environment report; poll |
| GET `/api/diagnostics` | None | 200 redacted `{format_version:1,created_at,counts,jobs,environment,...}` |
| POST `/api/state/save` | `{}` | 200 State after save generation acknowledgement |
| POST `/api/storage/rescan`, `/api/thumbnails/clear` | `{}` | 202 State; background maintenance |
| GET `/api/databases` | None | 200 maintenance status |
| POST `/api/databases` | action refresh/backup/compact; compact also confirmed:true | 202 maintenance status. Backup/compact need paused queue, no active job; 409 with error_code otherwise. Poll instance/revision, phase, entries/totals. |
| GET `/api/auth/x/setup` | None | 200 extension_dir/id, port/origin, host_browser, storage_mode/persistent |
| GET `/api/auth/x/connector` | None | 200 allowlisted connector ZIP, not JSON |
| POST `/api/auth/x/connect` | `{}` | 202 State, optional pairing_url for host browser; normal Chrome sign-in |
| POST `/api/auth/x/login`, `/open-extensions` | `{}` | 200 State after native Chrome dispatch; 400 on container (UI instructions) |
| POST `/api/auth/x/disconnect` | `{}` | 200 State; invalidate attempt, clear session/legacy cookie-file setting |
| GET `/api/auth/pixiv/status` | None | 200 `{pixiv_auth}` |
| POST `/api/auth/pixiv/begin` | `{}` automatic or `{manual:true}` | 200 `{pairing_url or authorization_url,opened,expires_in}`. If opened:true do not open again. |
| POST `/api/auth/pixiv/connect` | Exactly code or refresh_token | 200 `{pixiv_auth}`; input transient, never front-end storage |
| POST `/api/auth/pixiv/disconnect` | `{}` | 200 `{pixiv_auth}`; cancel pairing/clear session |

Connector-only POST routes retain extension-ID/header, exact-origin and ticket
checks: `/api/auth/x/prepare` (`{}` → `{token}`), `/api/auth/x/extension`
(`{cookies}` plus Bearer token → `{connected,message}`), `/api/auth/pixiv/claim`
(`{ticket}` → `{authorization_url}`), `/api/auth/pixiv/callback` (`{ticket,code}` →
`{pixiv_auth}`). OPTIONS/CORS applies only to this allowlist. A shell must not
impersonate the extension or read Chrome cookies. Pairing links require matching
loopback port, exact path and ticket fragment; controllers validate before open.

## DesktopInterface version 1

D03 adds [the actual Pywebview Adapter](DESKTOP_GUI.md). The explicit shell
composition maps the same methods to six native calls and negotiates immutable
version/capabilities. `ready` is a local Promise; owned native shells additionally
support confirmed stopBackend. Folder results affect only a live settings draft,
and Save still crosses HTTP. Native dialogs use serializable inputs/results,
not Window/.NET objects. Browser fallback and file_actions meanings are unchanged.

The composition root creates `SSDLDesktop.createBrowser({browser,document})`
and injects `desktop` into controllers. The standalone Chrome pairing page owns
its browser instance. Controllers have no framework detection or bridge imports.
`version:1`, `kind:"browser"` and immutable `capabilities` describe supported
actions, not whether a permission will be granted.

Action methods return a Promise of serializable `{status}`: completed,
cancelled, unsupported, blocked or error. Expected failures do not throw framework
objects or echo URL/ticket/clipboard content. Reservation and disposal are local
lifecycle methods; their objects/signals never cross a future native bridge.

| Method | Contract / fallback |
| --- | --- |
| openExternal(url) | HTTP(S) or relative URL, no credentials/other schemes; detached tab. Keep manual link/instructions when blocked. |
| reserveExternal() | **Synchronous reservation before HTTP await**, preserving click gesture. Returns `{open(url):Promise<Result>,cancel():void}`, never a Window. Navigate once; cancellation/disposal closes only unused tabs. Successful pages belong to user. |
| saveText({filename,text,mimeType}, {signal}?) | Filename without path; text ≤16 Mi characters; MIME application/json or text/plain. Blob download; release URL after short delay, abort, failure or disposal. Completed means download requested, not proof file retained. Signal is local cleanup only. |
| copyText(text) | Text ≤16 Mi characters; Clipboard API if present/permitted. Otherwise select input and keep Ctrl+C fallback. |
| pickDirectory() | Browser: unsupported; retain editable path. Future native adapter: completed plus path or cancelled; settings still validated over HTTP. |
| dispose() | Idempotent synchronous cleanup. New actions cancelled. No business/backend shutdown. |

`ssdl/platform_actions.py` owns Windows file-association dispatch and unsupported
host detection. HTTP retains source, job, path, existence and media checks, and
translates OS errors to existing messages. No shell or arbitrary-path bridge.

## Evidence and next step

`node --test tests/frontend.test.cjs` covers version/capabilities, synchronous
reservation, unsafe schemes, blocked/closed/cancelled operations, successful tab
ownership, clipboard fallback and export cleanup. Controller fixtures retain X
disconnect invalidation, Pixiv opened ownership and late-response/disposal tests.
`tests/test_native_file_actions.py` crosses real local HTTP with a synthetic OS
dispatcher: native/container behavior, unsupported hosts, association failure,
stale/deleted files, non-media, traversal and foreign origin. This is fixture
evidence, not real pywebview acceptance. D02 separates service control from page
presentation; D03 adds the actual second adapter behind this seam.
