import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ssdl import media_coordinator
from ssdl import media, video_quality as quality
from ssdl.media_selection import SelectionRequired
from ssdl.web_media import PlayerHTML, MediaCandidate


class QualityTests(unittest.TestCase):
    def test_all_quality_values_and_invalid_types(self):
        for value in quality.VIDEO_QUALITIES:
            self.assertEqual(quality.validate_video_quality(value), value)
            selector = quality.video_format(value)
            self.assertIn("ba", selector)
            if value != "best":
                self.assertIn(f"height<={value}", selector)
                self.assertIn("height>0", selector)
        for value in (None, True, 720, {}, "auto", "0", "1080p"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                quality.validate_video_quality(value)

    def formats(self):
        return [{"format_id": str(height), "url": f"https://cdn.example/{height}.mp4", "ext": "mp4",
                 "height": height, "width": height * 2, "vcodec": "avc1", "acodec": "aac"}
                for height in (144, 240, 360, 480, 720, 1080, 1440, 2160)]

    def select(self, value, formats):
        options = media.video_options(Path("unused"), lambda event: None, [], video_quality=value)
        options.update(quiet=True, no_warnings=True)
        with media.yt_dlp.YoutubeDL(options) as downloader:
            return downloader.process_ie_result({"id": "fixture", "title": "fixture", "extractor": "fixture",
                "webpage_url": "https://example.org/page", "formats": copy.deepcopy(formats)}, download=False)

    def test_engine_selects_all_eight_caps_best_and_lower_fallback(self):
        for value in quality.VIDEO_QUALITIES:
            with self.subTest(value=value):
                selected = self.select(value, self.formats())
                self.assertEqual(selected["height"], 2160 if value == "best" else int(value))
        selected = self.select("720", [item for item in self.formats() if item["height"] in {480, 1080}])
        self.assertEqual(selected["height"], 480)

    def test_unknown_too_high_audio_only_and_split_audio(self):
        variants = self.formats()
        unknown = {**variants[0], "height": None, "width": None}
        for formats in ([unknown], [variants[-1]], [{**unknown, "vcodec": "none"}]):
            with self.subTest(formats=formats), self.assertRaises(media.yt_dlp.utils.ExtractorError):
                self.select("720", formats)
        video = {**variants[4], "acodec": "none"}
        audio = {"format_id": "audio", "url": "https://cdn.example/audio.m4a", "ext": "m4a",
                 "vcodec": "none", "acodec": "aac", "abr": 128}
        self.assertEqual([item["format_id"] for item in self.select("720", [video, audio])["requested_formats"]], ["720", "audio"])

    def test_source_hints_preserve_extractor_dimensions_and_ignore_ids_player_box(self):
        self.assertEqual(quality.source_dimensions("https://cdn.example/123456.mp4?height=2160"), {})
        self.assertEqual(quality.source_dimensions("https://cdn.example/movie_1080p.mp4?token=a"), {"height": 1080})
        self.assertEqual(quality.source_dimensions("", {"size": "720", "label": "1920x1080"}), {"height": 720, "width": 1920})
        info = {"formats": [{"url": "https://cdn.example/1080p.mp4", "height": 480, "width": 854}]}
        quality.enrich_video_formats(info, MediaCandidate("", "", height=720))
        self.assertEqual(info["formats"][0]["height"], 480)
        parser = quality._SourceDimensions("https://example.org/page")
        parser.feed('<video width="1920" height="1080" src="/opaque.mp4"></video>')
        self.assertEqual(parser.sources, {})
        self.assertIn("720p", quality.video_quality_text({"entries": [{"height": 720}]}))

    def test_static_renditions_group_and_multiple_players_remain_distinct(self):
        parser = PlayerHTML("https://example.org/page")
        parser.feed('<video id="main"><source src="/1080p.mp4" size="1080"><source src="/720p.mp4" size="720"></video><video id="other" src="/other.mp4"></video>')
        items = parser.finish()
        self.assertEqual(len({item.group for item in items}), 2)
        self.assertEqual(items[0].height, 1080)
        self.assertEqual(items[0].group, items[1].group)

    def test_x_variants_at_all_caps_and_missing_metadata(self):
        variants = [{"url": f"https://video.twimg.com/{height*2}x{height}/movie.mp4", "bitrate": height}
                    for height in (144, 240, 360, 480, 720, 1080, 1440, 2160)]
        for value in quality.VIDEO_QUALITIES:
            chosen = quality.select_video_variant(variants, value)
            self.assertEqual(chosen["bitrate"], 2160 if value == "best" else int(value))
        with self.assertRaises(ValueError):
            quality.select_video_variant([{"url": "https://video.twimg.com/opaque.mp4", "bitrate": 100}], "720")

    def test_generic_choices_select_only_chosen_player_and_prompt_on_change(self):
        from yt_dlp.extractor.generic import GenericIE
        entries = [{"id": "a", "url": "https://cdn.example/a.mp4", "title": "A"},
                   {"id": "b", "url": "https://cdn.example/b.mp4", "title": "B"}]
        with media.yt_dlp.YoutubeDL({"quiet": True}) as downloader:
            quality.install_video_quality(downloader, allow_selection=True)
            extractor = downloader.get_info_extractor("Generic")
            with patch.object(GenericIE, "_real_extract", return_value={"_type": "playlist", "entries": entries}):
                with self.assertRaises(SelectionRequired) as failure:
                    extractor._real_extract("https://example.org/page")
                self.assertNotIn("url", failure.exception.options[0])
                downloader.params["ssdl_selected_media"] = failure.exception.options[1]["id"]
                self.assertEqual(extractor._real_extract("https://example.org/page")["id"], "b")
                downloader.params["ssdl_selected_media"] = "f" * 24
                with self.assertRaises(SelectionRequired):
                    extractor._real_extract("https://example.org/page")

    def test_gallery_generic_hook_remains_installed_without_interactive_selection(self):
        with media.yt_dlp.YoutubeDL({"quiet": True}) as downloader:
            quality.install_video_quality(downloader)
            self.assertFalse(downloader.params["ssdl_selection_enabled"])
            self.assertIsInstance(downloader.get_info_extractor("Generic"), quality._generic_extractor())

    def test_gallery_delegation_and_native_x_hook_apply_every_cap(self):
        for value in quality.VIDEO_QUALITIES:
            with self.subTest(value=value):
                media.configure_gallery(Path("unused"), video_quality=value)
                self.assertEqual(media.gallery_config.get(("downloader", "ytdl"), "format"), quality.video_format(value))
                raw = media.gallery_config.get(("downloader", "ytdl"), "raw-options")
                self.assertEqual(raw["format"], quality.video_format(value))
                self.assertFalse(raw["skip_unavailable_fragments"])
                if value == "best": continue
                extractor = Mock(category="twitter")
                extractor._extract_media.return_value = "fixture"
                original = extractor._extract_media
                media._pace_gallery(extractor, lambda event: None, value)
                variants = [{"url": f"https://video.twimg.com/{height*2}x{height}/video.mp4", "bitrate": height,
                             "content_type": "video/mp4"} for height in (144, 240, 360, 480, 720, 1080, 1440, 2160)]
                extractor._extract_media({}, [{"video_info": {"variants": variants}}], [])
                self.assertEqual(original.call_args.args[1][0]["video_info"]["variants"][0]["bitrate"], int(value))

    def test_quality_preferences_have_separate_manifests_and_images_stay_best(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def saved(url, output, emit, **options):
                path = output / (options["video_quality"] + ".mp4")
                path.write_bytes(b"fixture-media")
                return {"files": [path.name], "title": "fixture", "quality": options["video_quality"], "media_id": "fixture"}
            with patch.object(media_coordinator, "_download_source", side_effect=saved) as engine:
                for preference in ("720", "1080", "720"):
                    media.download("https://example.org/page", root, lambda event: None,
                                   video_quality=preference, manifest_file=root / "manifest.sqlite3")
                self.assertEqual(engine.call_count, 2)
                media.download("https://example.org/image.png", root, lambda event: None, video_quality="720")
                self.assertEqual(engine.call_args.kwargs["video_quality"], "best")


if __name__ == "__main__":
    unittest.main()
