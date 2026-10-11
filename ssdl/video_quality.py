"""Read declared rendition dimensions before yt-dlp selects a video format."""
from __future__ import annotations

from functools import lru_cache
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urljoin, urlparse
from .media_selection import SelectionRequired, selection_id, choice, MAX_CHOICES

VIDEO_QUALITIES = ("best", "2160", "1440", "1080", "720", "480", "360", "240", "144")


def validate_video_quality(value):
    if not isinstance(value, str) or value not in VIDEO_QUALITIES:
        raise ValueError("影片畫質設定不正確")
    return value


def video_format(value="best"):
    value = validate_video_quality(value)
    return "bv*+ba/b" if value == "best" else f"bv*[height>0][height<={value}]+ba/b[height>0][height<={value}]"


def rendition_dimensions(url):
    """CDNs may declare rendition dimensions in a path segment, not the name."""
    return resolution_hint(unquote(urlparse(url).path)) if isinstance(url, str) else {}


def select_video_variant(variants, value="best"):
    value = validate_video_quality(value)
    if value == "best":
        return max(variants, key=lambda item: item.get("bitrate") or 0)
    eligible = [(rendition_dimensions(item.get("url", "")).get("height") or _dimension(item.get("height")) or 0, item)
                for item in variants]
    eligible = [(height, item) for height, item in eligible if 0 < height <= int(value)]
    if not eligible:
        raise ValueError("平台未提供符合畫質上限的影片，或沒有回報解析度；請改選最高畫質。")
    return max(eligible, key=lambda pair: (pair[0], pair[1].get("bitrate") or 0))[1]


def _dimension(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if 72 <= number <= 16384 else None


def resolution_hint(value):
    """Require a resolution marker; arbitrary IDs and URL queries are not quality."""
    if not isinstance(value, str):
        return {}
    dimensions = re.search(r"(?<!\d)(\d{2,5})\s*[x×]\s*(\d{2,5})(?!\d)", value, re.I)
    if dimensions:
        width, height = map(_dimension, dimensions.groups())
        if width and height:
            return {"width": width, "height": height}
    height = re.search(r"(?<![a-z0-9])(\d{2,5})p(?![a-z0-9])", value, re.I)
    height = _dimension(height[1]) if height else None
    return {"height": height} if height else {}


def source_dimensions(url, attributes=None):
    """Prefer source labels, then explicit 1080p / 1920x1080 filename markers."""
    attributes = attributes or {}
    result = {}
    for key in ("data-height", "height", "res", "data-res", "size"):
        height = _dimension(attributes.get(key))
        if height:
            result["height"] = height
            break
    width = _dimension(attributes.get("width"))
    if width:
        result["width"] = width
    for key in ("label", "title", "data-quality", "data-res"):
        for field, number in resolution_hint(attributes.get(key)).items():
            result.setdefault(field, number)
    filename = unquote(urlparse(url).path.rsplit("/", 1)[-1]) if isinstance(url, str) else ""
    for field, number in resolution_hint(filename).items():
        result.setdefault(field, number)
    return result


def fill_dimensions(format_info, dimensions):
    if format_info.get("vcodec") == "none":
        return
    for key, value in dimensions.items():
        if not format_info.get(key):
            format_info[key] = value


class _SourceDimensions(HTMLParser):
    """Read HTML source attributes without executing scripts or fetching URLs."""
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.sources = {}
        self.video_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"video", "amp-video", "dl8-video", "dl8-live-video"}:
            self.video_depth += 1
            is_video = True
        else:
            is_video = tag == "source" and self.video_depth > 0
        if not is_video:
            return
        raw = next((attrs.get(key) for key in ("src", "data-video-src", "data-src", "data-source") if attrs.get(key)), None)
        if raw and len(self.sources) < 512:
            url = urljoin(self.base_url, raw)
            # A video's width/height can describe the player box, not the file.
            dimensions = source_dimensions(url, attrs if tag == "source" else {})
            if dimensions:
                self.sources.setdefault(url, dimensions)

    def handle_endtag(self, tag):
        if tag in {"video", "amp-video", "dl8-video", "dl8-live-video"}:
            self.video_depth = max(0, self.video_depth - 1)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


@lru_cache(maxsize=1)
def _generic_extractor():
    from yt_dlp.extractor.generic import GenericIE

    class QualityGenericIE(GenericIE):
        @classmethod
        def ie_key(cls):
            return "Generic"

        def _real_extract(self, url):
            result = super()._real_extract(url)
            enabled = self._downloader.params.get("ssdl_selection_enabled", False)
            selected = self._downloader.params.get("ssdl_selected_media", "")
            if result.get("_type", "video") == "video":
                enrich_video_formats(result)
                if enabled and selected and self._downloader.params.get("ssdl_selection_single", False):
                    item = choice(selection_id(url, f"generic:{result.get('id') or 0}:0"),
                        result.get("title") or "", url, variants=len(result.get("formats") or [1]))
                    if item["id"] != selected:
                        raise SelectionRequired([item])
            elif enabled and result.get("_type") in {"playlist", "multi_video"}:
                from itertools import islice
                entries = list(islice(result.get("entries") or (), MAX_CHOICES + 1))
                if len(entries) > MAX_CHOICES:
                    # Refuse silent truncation when a page exposes more players than the UI limit.
                    from .media import DownloadError
                    raise DownloadError("網頁媒體數量超過解析上限，請改貼單一播放器網址。", code="media_selection_limit")
                if len(entries) > 1 or selected and entries:
                    options = [choice(selection_id(url, f"generic:{entry.get('id') or index}:{index}"),
                        entry.get("title") or "", entry.get("webpage_url") or entry.get("url") or url,
                        variants=len(entry.get("formats") or [1]), kind="video") for index, entry in enumerate(entries)]
                    index = next((index for index, item in enumerate(options) if item["id"] == selected), None)
                    if index is None:
                        raise SelectionRequired(options)
                    return entries[index]
                result["entries"] = entries
            return result

        @staticmethod
        def _source_quality(base_url, webpage, entries):
            parser = _SourceDimensions(base_url)
            parser.feed(webpage)
            parser.close()
            for entry in entries:
                for rendition in entry.get("formats") or []:
                    url = rendition.get("url", "")
                    fill_dimensions(rendition, parser.sources.get(url) or source_dimensions(url))
                yield entry

        def _extract_embeds(self, url, webpage, **kwargs):
            entries = super()._extract_embeds(url, webpage, **kwargs)
            response = kwargs.get("urlh")
            base_url = response.url if response else url
            return self._source_quality(base_url, webpage, entries)

        def _parse_html5_media_entries(self, base_url, webpage, video_id, *args, **kwargs):
            entries = super()._parse_html5_media_entries(base_url, webpage, video_id, *args, **kwargs)
            return list(self._source_quality(base_url, webpage, entries))

    return QualityGenericIE


def install_video_quality(downloader, selected_media="", *, allow_selection=False, select_single=False):
    """Replace only Generic; keep all platform extractors and network policy."""
    downloader.params["ssdl_selected_media"] = selected_media
    downloader.params["ssdl_selection_enabled"] = allow_selection
    downloader.params["ssdl_selection_single"] = select_single
    downloader.add_info_extractor(_generic_extractor()())


def enrich_video_formats(info, candidate=None):
    formats = info.get("formats") or []
    if not formats and info.get("url"):
        dimensions = source_dimensions(info["url"]) or rendition_dimensions(info["url"])
        if candidate and candidate.height:
            dimensions.setdefault("height", candidate.height)
        fill_dimensions(info, dimensions)
    for rendition in formats:
        dimensions = source_dimensions(rendition.get("url", "")) or rendition_dimensions(rendition.get("url", ""))
        if candidate and candidate.height and len(formats) == 1:
            dimensions.setdefault("height", candidate.height)
        fill_dimensions(rendition, dimensions)


def video_quality_text(info):
    """Playlist wrappers must not hide the selected HTML5 entry's resolution."""
    resolutions = set()

    def collect(item):
        if not isinstance(item, dict):
            return
        if item.get("entries") is not None:
            for entry in item["entries"]:
                collect(entry)
            return
        width, height = item.get("width"), item.get("height")
        resolutions.add(f"{width}×{height}" if width and height else f"{height}p" if height else "解析度未回報")

    collect(info or {})
    label = next(iter(resolutions)) if len(resolutions) == 1 else "多個解析度" if resolutions else "解析度未回報"
    return f"{label} · 保留影音編碼"
