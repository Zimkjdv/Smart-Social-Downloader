"""Browser gate contracts; mocks never establish actual playback acceptance."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import check_docker as gate
from tools import docker_browser_acceptance as browser


class DockerBrowserTests(unittest.TestCase):
    def test_browser_flag_includes_all_existing_gates_in_order(self):
        from tools import docker_host_acceptance, docker_interaction_acceptance, docker_service_acceptance
        calls = Mock()
        def run(docker, root, report, *, service_gate):
            service_gate(docker, "fixture", "a" * 32, root, report)
            return dict(report, passed=True, complete=True)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(docker_service_acceptance, "run_checks", calls.service), \
             patch.object(docker_interaction_acceptance, "run_checks", calls.interaction), \
             patch.object(docker_host_acceptance, "run_checks", calls.host), \
             patch.object(browser, "run_checks", calls.browser), \
             patch.object(gate, "run_gate", side_effect=run), patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(gate.main(["--browser", "--browser-headed", "--docker", "fixture-docker",
                "--report", str(Path(directory) / "receipt.json")]), 0)
        self.assertEqual([item[0] for item in calls.mock_calls], ["service", "interaction", "host", "browser"])
        self.assertEqual(calls.browser.call_args.kwargs, {"headed": True})

    def test_headed_requires_browser_and_never_starts_docker(self):
        with patch.object(gate, "run_gate") as run, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as failure:
                gate.main(["--browser-headed"])
        self.assertEqual(failure.exception.code, 2)
        run.assert_not_called()

    def test_exact_origin_and_read_only_requests(self):
        origin = "http://127.0.0.1:19876"
        for method in ("GET", "HEAD"):
            self.assertTrue(browser.local_request(origin + "/static/app.js", origin, method))
        for url, method in (("http://127.0.0.1:8765/", "GET"), ("https://127.0.0.1:19876/", "GET"),
                            ("http://localhost:19876/", "GET"), ("https://external.invalid/", "GET"),
                            ("http://name@127.0.0.1:19876/", "GET"), ("file:///app/private", "GET"),
                            (origin + "/api/auth/x/extension", "POST"), (origin, "DELETE")):
            with self.subTest(url=url, method=method):
                self.assertFalse(browser.local_request(url, origin, method))

    def test_port_mapping_must_match_before_browser_context_creation(self):
        driver = Mock(version="100.1.2.3")
        with self.assertRaisesRegex(gate.GateError, "browser_port_mismatch"):
            browser.exercise_browser(driver, {"port": 12345, "host_port": 12346}, Mock(), {})
        driver.new_context.assert_not_called()

    def test_version_is_categorical_and_never_accepts_path_or_error(self):
        driver = Mock(version="private error value")
        with self.assertRaisesRegex(gate.GateError, "invalid_chrome_version"):
            browser.exercise_browser(driver, {"port": 12345, "host_port": 12345}, Mock(), {})
        driver.new_context.assert_not_called()

    def test_ui_failure_retains_stage_and_closes_context_without_raw_error(self):
        driver = Mock(version="100.1.2.3")
        context = driver.new_context.return_value
        context.new_page.return_value.goto.side_effect = RuntimeError("synthetic-private-value")
        report = {"browser_checks": []}
        with self.assertRaises(RuntimeError):
            browser.exercise_browser(driver, {"port": 12345, "host_port": 12345}, Mock(), report)
        context.close.assert_called_once()
        self.assertEqual(report["browser_checks"], [])
        self.assertEqual(report["browser_error"], "chrome_runtime_failed")
        self.assertNotIn("synthetic-private-value", str(report))
        self.assertEqual(driver.new_context.call_args.kwargs["service_workers"], "block")
        self.assertIs(driver.new_context.call_args.kwargs["accept_downloads"], False)

    def test_image_wait_requires_real_decoded_dimensions(self):
        page = Mock()
        with patch.object(browser, "wait_element") as wait:
            browser.image_decoded(page)
        self.assertEqual(wait.call_args.args[:2], (page, "img"))
        script = wait.call_args.args[2]
        self.assertIn("naturalWidth === 1", script)
        self.assertIn("naturalHeight === 1", script)
        self.assertIn("image.complete", script)

    def test_video_wait_requires_decoded_frames_seek_and_end(self):
        page = Mock()
        with patch.object(browser, "wait_element") as wait:
            browser.play_video(page)
        scripts = "\n".join(call.args[2] for call in wait.call_args_list)
        self.assertIn("getVideoPlaybackQuality().totalVideoFrames > 0", scripts)
        self.assertIn("!v.seeking", scripts)
        self.assertIn("v.ended === true", scripts)
        self.assertEqual(page.locator.return_value.evaluate.call_count, 4)
        for call in page.locator.return_value.evaluate.call_args_list:
            self.assertNotIn("await v.play()", call.args[0])

    def test_metadata_failure_never_starts_playback(self):
        page = Mock()
        page.locator.return_value.evaluate.return_value = False
        with patch.object(browser, "wait_element"), self.assertRaisesRegex(gate.GateError, "browser_video_metadata_failed"):
            browser.play_video(page)
        self.assertEqual(page.locator.return_value.evaluate.call_count, 1)

    def test_sandboxed_native_document_is_polled_from_driver(self):
        page = Mock()
        page.locator.return_value.evaluate.side_effect = [False, True]
        browser.wait_element(page, "video", "v => v.readyState >= 2")
        page.wait_for_function.assert_not_called()
        page.wait_for_timeout.assert_called_once_with(50)
        self.assertEqual(page.locator.return_value.evaluate.call_count, 2)

    def test_stuck_native_document_fails_with_bounded_categorical_error(self):
        page = Mock()
        page.locator.return_value.evaluate.return_value = False
        with patch.object(browser.time, "monotonic", side_effect=[0, 0, 16]), \
             self.assertRaisesRegex(gate.GateError, "^browser_media_condition_timeout$"):
            browser.wait_element(page, "video", "v => v.readyState >= 2")
        page.wait_for_timeout.assert_called_once_with(50)

    def test_source_distribution_includes_browser_gate_but_image_does_not(self):
        from tools.package_source import source_files
        names = {path.relative_to(gate.ROOT).as_posix() for path in source_files(gate.ROOT)}
        self.assertTrue({"tools/docker_browser_acceptance.py", "tests/test_docker_browser.py"} <= names)
        self.assertNotIn("tools/docker_browser_acceptance.py", gate.runtime_sources(gate.ROOT))


if __name__ == "__main__":
    unittest.main()
