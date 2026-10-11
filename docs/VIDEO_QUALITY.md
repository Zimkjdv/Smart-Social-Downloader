# Video resolution selection

[English README](../README.md) · [繁體中文 README](../README_CN.md)

## Selection and display

- Best quality uses `bv*+ba/b`. A selected height limit uses `bv*[height>0][height<=N]+ba/b[height>0][height<=N]`. Resolution is the first requested sort field; yt-dlp retains its usability and extractor preference checks. Available video and audio streams are merged without re-encoding.
- Existing width and height from platform extractors or HLS/DASH manifests are preserved.
- Generic HTML5 sources supplement missing dimensions from source attributes (`size`, `height`, `data-height`, `res`, labels), then explicit filename markers such as `1080p` or `1920x1080`. The player element's display width and height are not treated as media dimensions.
- Numeric IDs and URL query parameters are not guessed as resolutions. This does not modify signed URLs, cookies, source identities, or request policy, and introduces no new dependency or additional network request.
- The same Generic extension and resolution preference apply when gallery-dl delegates a video to yt-dlp. The app's generic fallback also recognizes these source markers.
- Selected quality displays dimensions when both are known, or a height such as `1080p`. HTML5 playlist wrappers retain the selected entry's quality. Missing information displays **Resolution not reported**; mixed entries display **Multiple resolutions**.

Reported dimensions describe source metadata. They do not prove visual quality, that every accessible rendition has been discovered, or that a platform retains the uploader's original bytes. This change does not add dynamic browser playback capture, DRM support, or dynamic selection from browser traffic. Independent static players now use the bounded workflow described in [P2_COMPLETION.md](P2_COMPLETION.md).

## Quality dropdown — 2026-10-11

The Media URLs input offers Best quality by default and the fixed height limits 2160, 1440, 1080, 720, 480, 360, 240, and 144. This is a preference selector, not a preview API that enumerates formats for each URL. It does not add a download confirmation dialog. Opening/reloading the page starts at Best quality; status polling and language/mode changes retain the in-page URL-mode selection.

The best available reported version at or below the limit is selected. For example, 720p falls back to 480p if only 1080p and 480p are available. Missing matching or reported dimensions cause an actionable `quality_unavailable` failure, without exceeding the cap or transcoding. Direct images keep their original behavior. Authenticated/public X posts filter exposed MP4 variants by declared height and bitrate; single renditions can also use their reported source height. Other gallery videos must expose a matching version/height or report an unavailable quality. X account batch sync currently uses Best quality; its mode hides the dropdown and the API rejects non-Best account requests.

### Persistence and deduplication

- `POST /api/jobs` accepts a validated `video_quality` string; omitted values mean `best`. The optional job field is stored in the existing schema and added to API summaries. Older jobs load as Best quality.
- A submission applies the same choice to its media URLs. Direct image links normalize to Best because a video cap does not apply to them.
- Same-source jobs reuse/pending checks are scoped to the selected preference. Different preferences remain separate, even when the provider resolves them to the same rendition. Retry retains the job preference; change it by submitting the URL with a different choice.
- Best quality retains existing filenames, directories, and manifest keys. Capped videos/galleries add a platform subfolder such as `youtube/quality-720p/` or `twitter/quality-720p/<account>/` and a preference suffix to the manifest source identity. This avoids overwriting or incorrectly skipping a different requested version.
- A mixed-media gallery's original images also live in its choice's folder and can therefore exist in multiple quality folders. Direct image links continue to use shared verified image history. The tool does not perform cross-version content-hash deduplication.
- The `quality-720p` folder describes the request's ceiling, not a guarantee that every saved video is exactly 720p. Actual quality remains visible in the job where reported.
- Profile archive behavior, stream integrity, network policy, pacing, and rate counting remain unchanged. Changing a quality does not silently modify or redownload existing jobs.

Follow-up regression acceptance on 2026-10-11 covers Best and every fixed cap through the UI/API, actual yt-dlp synthetic format selection, native X variant filtering, gallery-dl delegation, unknown/missing/too-high formats, split audio/video, images, profile-mode restrictions, retry and manifest scopes. A captured synthetic 360p MP4 downloads byte-for-byte through the normal capped engine and passes FFmpeg decoding. All **104 Python + 10 Node tests** pass locally, including real headless Chrome against a synthetic backend and the subsequent audit fixes. See [TESTING.md](TESTING.md). No additional real-platform capped downloads were run; the historical 1080p recovery remains a separate record.

## Existing downloads

Completed files and verified history are retained. The tool does not silently upgrade older files. To replace an earlier lower-quality download, use its row's **Retry** icon. Retry bypasses the verified-existing-file shortcut, runs the current format selection, and replaces the same-name final file on successful completion. It uses the ordinary queue, hourly limit, pacing, and cooldown.

## Investigation record — 2026-10-11

A reported HTML5 page exposed six MP4 sources, ordered 1080p, 720p, 480p, 360p, 240p, and 144p. Its `<source>` elements declared their heights using `size`, and their filenames included `1080p`-style markers. The installed upstream Generic/HTML5 extraction returned all six without dimensions; the default tie-break selected the last source. FFmpeg inspection of the saved file confirmed **212×144**.

After supplementing the declared dimensions, metadata extraction sorted the six versions by resolution and selected **1080p**. The affected item completed through the existing retry API, replacing the original same-name file. FFmpeg inspection confirmed **1592×1080**, H.264 video and AAC audio, a duration of **19:32.54**, and a file size of **149,520,781 bytes** (142.6 MiB). The queue reports completion and the selected `1080p` quality. This was metadata inspection, not a complete decode of every frame.

No regression tests were added or run for this change. Python/JavaScript syntax checks and the source-specific extraction diagnosis were performed; the existing P1 test results predate this change.

## Maintenance

`ssdl/video_quality.py` registers a Generic extractor subclass through yt-dlp's `add_info_extractor`, retaining its extractor key. It supplements generic embedded results before format selection and retains an HTML5 parser extension for compatible versions. This uses upstream internal extraction hooks; after changing the yt-dlp baseline, check these hooks and selection behavior. Platform extractors remain registered normally.

Primary implementation references: [yt-dlp Generic extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/generic.py), [HTML5 embed extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/genericembeds.py), [format sorting](https://github.com/yt-dlp/yt-dlp#sorting-formats).
