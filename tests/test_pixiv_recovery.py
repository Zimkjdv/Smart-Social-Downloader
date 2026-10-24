"""Fault injection for scan-first completeness and verified-page continuation."""
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gallery_dl.extractor.common import Message
from ssdl.media_contracts import DownloadError
from ssdl.request_policy import RequestPolicy
from ssdl.x_profiles import ProfileArchive
from tests.helpers.pixiv import PixivFixture, Source


def source_messages(messages):
    source = Source({"id": 123, "name": "作者"}, ())
    source.items = lambda: iter(messages)
    return source


def valid_messages(count=2):
    return list(Source({"id": 123, "name": "作者"}, (("100", count),)).items())


class PixivRecoveryTests(unittest.TestCase):
    def test_incremental_sync_downloads_only_new_works(self):
        with PixivFixture() as fixture:
            first = fixture.sync()
            before = fixture.signature(first["files"])
            quota = Mock()
            result = fixture.sync(works=(("100", 2), ("200", 3)), before_post=quota)
            self.assertEqual(result["downloaded_file_count"], 3)
            self.assertEqual(result["skipped_file_count"], 2)
            self.assertEqual(fixture.signature(first["files"]), before)
            self.assertEqual(quota.call_count, 1)
            self.assertEqual(fixture.events[-1]["profile_total_files"], 5)
            self.assertEqual(fixture.sync(works=(("100", 2), ("200", 3)))["downloaded_file_count"], 0)

    def test_inaccessible_deleted_or_private_works_warn_and_keep_old_originals(self):
        with PixivFixture() as fixture:
            first = fixture.sync()
            before = fixture.signature(first["files"])
            result = fixture.sync(works=(("100", 0), ("200", 1)), previous_files=first["files"])
            self.assertEqual(result["downloaded_file_count"], 1)
            self.assertEqual(fixture.events[-1]["profile_total_files"], 1)
            self.assertTrue(any("1 個作品未提供" in text for text in result["warnings"]))
            self.assertEqual(fixture.signature(first["files"]), before)

    def test_all_unavailable_has_zero_totals_and_no_transfer(self):
        with PixivFixture() as fixture:
            quota = Mock()
            result = fixture.sync(works=(("100", 0), ("200", 0)), before_post=quota)
            self.assertEqual(result["files"], [])
            self.assertEqual(fixture.events[-1]["profile_total_files"], 0)
            self.assertTrue(any("2 個作品未提供" in text for text in result["warnings"]))
            quota.assert_not_called()

    def test_scan_transport_failure_never_publishes_total_or_starts_transfer(self):
        source = Source({"id": 123, "name": "作者"}, (("100", 1),))
        def incomplete():
            yield from valid_messages(1)
            raise ConnectionError("synthetic listing interrupted")
        source.items = incomplete
        with PixivFixture() as fixture:
            quota = Mock()
            with self.assertRaises(DownloadError):
                fixture.sync(source=source, before_post=quota)
            self.assertEqual(fixture.transferred, [])
            self.assertFalse(any(event.get("profile_scan_complete") for event in fixture.events))
            quota.assert_not_called()

    def test_short_listing_and_nonzero_engine_status_fail_before_transfer(self):
        for short in (True, False):
            with self.subTest(short=short), PixivFixture() as fixture:
                source = source_messages(valid_messages()[:-1] if short else valid_messages())
                source.status = 0 if short else 1
                with self.assertRaises(DownloadError) as caught:
                    fixture.sync(source=source)
                self.assertEqual(caught.exception.code, "pixiv_scan_incomplete")
                self.assertEqual(fixture.transferred, [])

    def test_duplicate_or_gapped_page_numbers_are_not_complete_works(self):
        for number, extension in ((0, "png"), (2, "png"), (0, "jpg")):
            with self.subTest(number=number, extension=extension), PixivFixture() as fixture:
                messages = valid_messages()
                kind, url, data = messages[-1]
                messages[-1] = kind, url, dict(data, num=number, extension=extension)
                with self.assertRaises(DownloadError) as caught:
                    fixture.sync(source=source_messages(messages))
                self.assertEqual(caught.exception.code, "pixiv_invalid_media")
                self.assertEqual(fixture.transferred, [])

    def test_partial_transfer_failure_or_cancel_preserves_only_completed_pages(self):
        for code in ("download_failed", "download_cancelled", "rate_limited"):
            with self.subTest(code=code), PixivFixture() as fixture:
                def interrupted(snapshot, root, emit):
                    def stop_after_first(data):
                        emit(data)
                        raise DownloadError("synthetic transfer interrupted", data["files"], code=code)
                    return fixture.transfer(snapshot, root, stop_after_first)
                with self.assertRaises(DownloadError) as caught:
                    fixture.sync(transfer=interrupted)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(len(caught.exception.files), 1)
                retained = caught.exception.files
                before = fixture.signature(retained)
                archive = ProfileArchive(fixture.archive, fixture.root, "pixiv:123")
                try:
                    self.assertIsNone(archive.lookup("100", 2))
                    self.assertEqual(len(archive.verified_files(post_id="100")), 1)
                finally:
                    archive.close()
                fixture.policy.job_completed.assert_not_called()
                result = fixture.sync()
                self.assertEqual(result["downloaded_file_count"], 1)
                self.assertEqual(fixture.signature(retained), before)
                self.assertEqual(fixture.events[-1]["profile_completed_files"], 2)

    def test_error_paths_do_not_import_unrelated_files_or_parts(self):
        with PixivFixture() as fixture:
            unrelated = fixture.root / "unrelated.png"
            unrelated.write_bytes(b"synthetic unrelated original")
            part = fixture.root / "unfinished.png.part"
            part.write_bytes(b"synthetic incomplete bytes")
            def interrupted(snapshot, root, emit):
                def stop(data):
                    emit(data)
                    raise DownloadError("synthetic cancelled", [*data["files"], unrelated.name, part.name], code="download_cancelled")
                return fixture.transfer(snapshot, root, stop)
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(transfer=interrupted)
            self.assertEqual(caught.exception.code, "download_cancelled")
            self.assertEqual(len(caught.exception.files), 1)
            self.assertNotIn(unrelated.name, caught.exception.files)
            self.assertEqual(fixture.sync()["downloaded_file_count"], 1)
            self.assertEqual(unrelated.read_bytes(), b"synthetic unrelated original")
            self.assertTrue(part.exists())

    def test_incomplete_transfer_result_is_not_accepted_as_success(self):
        with PixivFixture() as fixture:
            def short(snapshot, root, emit):
                snapshot.assets = snapshot.assets[:1]
                return fixture.transfer(snapshot, root, emit)
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(transfer=short)
            self.assertEqual(caught.exception.code, "pixiv_incomplete_media")
            self.assertEqual(len(caught.exception.files), 1)
            self.assertFalse(any(event.get("profile_stage") == "done" for event in fixture.events))
            self.assertEqual(fixture.sync()["downloaded_file_count"], 1)

    def test_actual_429_wrapper_closes_response_and_preserves_scan_error_code(self):
        policy = RequestPolicy()
        response = SimpleNamespace(status_code=429, headers={"Retry-After": "1"}, close=Mock())
        source = Source({"id": 123, "name": "作者"}, ())
        source.session.send = Mock(return_value=response)
        policy.wrap_session(source.session)
        def limited():
            source.session.send(Mock())
            yield from ()
        source.items = limited
        with PixivFixture() as fixture:
            with patch("ssdl.request_policy.time.monotonic", return_value=1000):
                with self.assertRaises(DownloadError) as caught:
                    fixture.sync(source=source, policy=policy)
                self.assertGreater(policy.snapshot()["cooldown_seconds"], 0)
            self.assertEqual(caught.exception.code, "rate_limited")
            response.close.assert_called_once()
            self.assertEqual(fixture.transferred, [])
            self.assertFalse(any(event.get("profile_scan_complete") for event in fixture.events))
            resumed = Source({"id": 123, "name": "作者"}, ())
            resumed.session.send = Mock(return_value=SimpleNamespace(status_code=200))
            policy.wrap_session(resumed.session)
            def successful():
                resumed.session.send(Mock())
                yield from valid_messages()
            resumed.items = successful
            # Advance only the isolated policy clock, retaining the same cooldown
            # state; never wait a real minute or remove production safeguards.
            with patch("ssdl.request_policy.time.monotonic", return_value=1061):
                self.assertEqual(policy.snapshot()["cooldown_seconds"], 0)
                self.assertEqual(fixture.sync(source=resumed, policy=policy)["downloaded_file_count"], 2)

    def test_expired_login_and_warnings_redact_session_values(self):
        class AuthenticationError(RuntimeError):
            pass
        source = Source({"id": 123, "name": "作者"}, ())
        def denied():
            raise AuthenticationError("refresh token SYNTHETIC_PIXIV_SESSION rejected")
            yield from ()
        source.items = denied
        with PixivFixture() as fixture:
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(source=source)
            self.assertEqual(caught.exception.code, "pixiv_login_required")
            self.assertNotIn("SYNTHETIC_PIXIV_SESSION", str(caught.exception))
            def warning(snapshot, root, emit):
                logging.warning("synthetic session SYNTHETIC_PIXIV_SESSION https://example.org/a?token=PRIVATE_FIXTURE")
                return fixture.transfer(snapshot, root, emit)
            result = fixture.sync(transfer=warning)
            self.assertNotIn("SYNTHETIC_PIXIV_SESSION", str(result["warnings"]))
            self.assertNotIn("PRIVATE_FIXTURE", str(result["warnings"]))

    def test_completed_work_survives_later_work_failure(self):
        with PixivFixture() as fixture:
            def fail_second(snapshot, root, emit):
                if str(snapshot.assets[0][1]["id"]) == "200":
                    raise DownloadError("synthetic later failure")
                return fixture.transfer(snapshot, root, emit)
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(works=(("100", 2), ("200", 1)), transfer=fail_second)
            retained = caught.exception.files
            self.assertEqual(len(retained), 2)
            before = fixture.signature(retained)
            result = fixture.sync(works=(("100", 2), ("200", 1)))
            self.assertEqual(result["downloaded_file_count"], 1)
            self.assertEqual(result["skipped_file_count"], 2)
            self.assertEqual(fixture.signature(retained), before)

    def test_retained_page_repeated_in_payload_is_not_counted_or_recorded_twice(self):
        with PixivFixture() as fixture:
            retained = fixture.seed("123", pages=(0,))
            def interrupted(snapshot, root, emit):
                def stop(data):
                    names = retained + data["files"]
                    emit(dict(data, files=names))
                    raise DownloadError("synthetic cancellation", names, code="download_cancelled")
                return fixture.transfer(snapshot, root, stop)
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(transfer=interrupted)
            self.assertEqual(caught.exception.code, "download_cancelled")
            self.assertEqual(len(set(caught.exception.files)), 2)
            self.assertTrue(all(event.get("profile_completed_files", 0) <= 2 for event in fixture.events))
            self.assertEqual(fixture.sync()["downloaded_file_count"], 0)

    def test_cancellation_before_scan_does_not_start_transfer_or_claim_totals(self):
        with PixivFixture() as fixture:
            def cancelled():
                raise DownloadError("synthetic stop", code="download_cancelled")
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(checkpoint=cancelled)
            self.assertEqual(caught.exception.code, "download_cancelled")
            self.assertEqual(fixture.transferred, [])
            self.assertFalse(any(event.get("profile_scan_complete") for event in fixture.events))

    def test_unrelated_progress_files_and_empty_finals_are_not_partial_success(self):
        with PixivFixture() as fixture:
            unrelated = fixture.root / "unrelated.png"
            unrelated.write_bytes(b"synthetic unrelated")
            def false_progress(snapshot, root, emit):
                name = "pixiv/作者(123)/100_p0.png"
                empty = root / name
                empty.parent.mkdir(parents=True, exist_ok=True)
                empty.write_bytes(b"")
                emit({"files": [unrelated.name, name]})
                raise DownloadError("synthetic failure", [name])
            with self.assertRaises(DownloadError) as caught:
                fixture.sync(transfer=false_progress)
            self.assertEqual(caught.exception.files, [])
            self.assertEqual(fixture.sync()["downloaded_file_count"], 2)
            self.assertEqual(unrelated.read_bytes(), b"synthetic unrelated")

    def test_contiguous_original_animation_frames_still_use_the_original_path(self):
        messages = valid_messages(3)
        for index in range(1, len(messages)):
            kind, _, data = messages[index]
            messages[index] = (kind,
                f'https://i.pximg.net/img-original/2026/10/25/00/00/00/100_ugoira{data["num"]}.jpg',
                dict(data, extension="jpg"))
        with PixivFixture() as fixture:
            result = fixture.sync(source=source_messages(messages))
            self.assertEqual(result["downloaded_file_count"], 3)
            self.assertTrue(all(name.endswith(".jpg") for name in result["files"]))
