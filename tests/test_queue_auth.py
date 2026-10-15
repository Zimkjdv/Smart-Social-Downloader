import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from ssdl import media, x_auth
from ssdl.request_policy import RequestPolicy
from ssdl.job_runtime import run_job
from tests.helpers.app import IsolatedApp, seed_jobs


class QueueAndAuthTests(unittest.TestCase):
    def setUp(self):
        fixture = self.enterContext(IsolatedApp())
        self.app, self.root, self.stack = fixture.app, fixture.root, fixture.stack

    def jobs(self):
        return seed_jobs(self.app)

    def test_failed_job_does_not_block_next_job(self):
        self.jobs()
        calls = []
        def run(payload, *args, **kwargs):
            calls.append(payload["url"])
            if len(calls) == 1:
                raise media.DownloadError("fixture failure")
            self.app.state.shutdown.set()
            return {"files": [], "quality": "fixture", "title": "done"}
        with patch.object(self.app, "run_job", run):
            self.app._worker_loop()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.app.state.jobs["0"]["status"], "failed")
        self.assertEqual(self.app.state.jobs["1"]["status"], "completed")
        self.assertIsNone(self.app.state.active_id)

    def test_shutdown_requeues_interrupted_job(self):
        self.jobs()
        def run(*args, **kwargs):
            self.app.state.shutdown.set()
            raise media.DownloadError("cancelled", code="download_cancelled")
        with patch.object(self.app, "run_job", run):
            self.app._worker_loop()
        self.assertEqual(self.app.state.jobs["0"]["status"], "queued")
        self.assertEqual(list(self.app.state.queue), ["0", "1"])

    def test_rate_window_and_cooldown_survive_restore(self):
        self.app.state.job_starts.extend([time.time() - 4000, time.time() - 2, time.time() - 1])
        self.app.state.hourly_job_limit = 2
        self.assertTrue(self.app._quota_locked()["limited"])
        self.assertEqual(self.app._quota_locked()["used"], 2)
        policy = RequestPolicy()
        policy.limit(123)
        restored = RequestPolicy()
        restored.restore(policy.snapshot())
        self.assertGreaterEqual(restored.snapshot()["cooldown_seconds"], 122)
        self.app._save_locked()
        self.app.state.job_starts.clear()
        self.app.state.hourly_job_limit = 40
        self.app._load_saved_state()
        self.assertEqual(self.app._quota_locked()["used"], 2)
        self.assertEqual(self.app._quota_locked()["limit"], 2)

    def test_restart_preserves_stop_and_requeues_only_interrupted_work(self):
        self.jobs()
        self.app.state.jobs["0"].update(status="active", stop_requested=True)
        self.app.state.jobs["1"].update(status="active")
        self.app._save_locked()
        self.app.state.jobs.clear()
        self.app.state.queue.clear()
        self.app._load_saved_state()
        self.assertEqual(self.app.state.jobs["0"]["status"], "failed")
        self.assertEqual(self.app.state.jobs["1"]["status"], "queued")
        self.assertEqual(list(self.app.state.queue), ["1"])
        self.app.state.jobs["0"]["platform"] = "X"
        self.app._retry_failed_x()
        self.assertEqual(self.app.state.jobs["0"]["status"], "failed")
        self.assertEqual(list(self.app.state.queue), ["1"])

    def test_malformed_history_does_not_partially_restore_or_allow_overwrite(self):
        self.jobs()
        original_jobs, original_queue = dict(self.app.state.jobs), list(self.app.state.queue)
        for changes in ({"url": "https://[", "platform": "Web"},
                        {"output_dir": "bad\x00path"}, {"files": ["bad\x00file"]}):
            with self.subTest(changes=changes):
                saved = {"jobs": [dict(original_jobs["0"]), {**original_jobs["1"], **changes}],
                         "queue": ["0", "1"], "download_dir": str(self.root)}
                self.app.STATE_FILE.write_text(json.dumps(saved), encoding="utf-8")
                original = self.app.STATE_FILE.read_bytes()
                self.app._load_saved_state()
                self.assertEqual(self.app.state.jobs, original_jobs)
                self.assertEqual(list(self.app.state.queue), original_queue)
                self.assertFalse(self.app.STATE_STORE.status()["healthy"])
                self.app._save_locked()
                self.assertEqual(self.app.STATE_FILE.read_bytes(), original)
                self.assertFalse(self.app.STATE_STORE.backup.exists())

    def test_restore_normalization_failure_uses_backup_before_applying(self):
        self.jobs()
        self.app._save_locked()
        backup = self.app.STATE_FILE.read_bytes()
        self.app.STATE_STORE.backup.write_bytes(backup)
        bad = json.loads(backup)
        bad["jobs"].append({"id": "late", "url": "https://example.org/late", "status": "queued", "created_at": 300})
        self.app.STATE_FILE.write_text(json.dumps(bad), encoding="utf-8")
        corrupted = self.app.STATE_FILE.read_bytes()
        platform = self.app._platform
        self.app.state.jobs.clear(); self.app.state.queue.clear()
        def normalize(url):
            if url.endswith('/late'): raise ValueError("synthetic normalization failure")
            return platform(url)
        with patch.object(self.app, "_platform", normalize):
            self.app._load_saved_state()
        self.assertEqual(list(self.app.state.jobs), ["0", "1"])
        self.assertEqual(list(self.app.state.queue), ["0", "1"])
        self.assertTrue(self.app.STATE_STORE.status()["recovered"])
        self.assertEqual(self.app.STATE_STORE.backup.read_bytes(), backup)
        preserved = list(self.root.glob('state.corrupt-*.json'))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_bytes(), corrupted)

    def test_late_normalization_failure_without_backup_preserves_all_live_fields(self):
        self.jobs()
        old_jobs, old_queue = self.app.state.jobs, self.app.state.queue
        payload = {'jobs': [dict(old_jobs['0']), {'id': 'late', 'url': 'https://example.org/late',
                    'status': 'queued', 'created_at': 300}], 'queue': ['0', 'late'],
                   'download_dir': str(self.root / 'changed'), 'paused': True, 'hourly_job_limit': 99}
        self.app.STATE_FILE.write_text(json.dumps(payload), encoding='utf-8')
        original = self.app.STATE_FILE.read_bytes()
        with patch.object(self.app, '_platform', side_effect=ValueError('fixture normalization failure')):
            self.app._load_saved_state()
        self.assertIs(self.app.state.jobs, old_jobs)
        self.assertIs(self.app.state.queue, old_queue)
        self.assertEqual(self.app.state.download_dir, self.root)
        self.assertFalse(self.app.state.paused)
        self.assertEqual(self.app.state.hourly_job_limit, 40)
        self.assertTrue(self.app.STATE_STORE.status()['blocked'])
        self.app._save_locked()
        self.assertEqual(self.app.STATE_FILE.read_bytes(), original)

    def test_capacity_failure_releases_worker_for_next_download(self):
        from ssdl import ipc
        self.jobs()
        calls = []
        def execute(payload, *args, **kwargs):
            calls.append(payload['url'])
            if len(calls) == 1:
                payload['padding'] = 'x' * 4096
            try:
                return run_job(payload, *args, **kwargs, command=[sys.executable, '-u',
                    str(Path(__file__).with_name('test_fixture_runner.py'))])
            finally:
                if len(calls) == 2: self.app.state.shutdown.set()
        with patch.object(ipc, 'MAX_MESSAGE_BYTES', 4096), patch.object(self.app, 'run_job', execute):
            self.app._worker_loop()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.app.state.jobs['0']['error_code'], 'worker_message_too_large')
        self.assertEqual(self.app.state.jobs['1']['status'], 'completed')
        self.assertIsNone(self.app.state.active_id)

    def test_malformed_nested_history_uses_valid_backup(self):
        self.jobs(); self.app._save_locked()
        backup = self.app.STATE_FILE.read_bytes()
        self.app.STATE_STORE.backup.write_bytes(backup)
        for field, value in (("download_dir", "bad\x00path"),
                             ("safe_queue", {"platform_cooldowns": {"X": {"cooldown_until": []}}})):
            with self.subTest(field=field):
                saved = {**json.loads(backup), field: value}
                self.app.STATE_FILE.write_text(json.dumps(saved), encoding="utf-8")
                self.app.state.jobs.clear(); self.app.state.queue.clear()
                self.app._load_saved_state()
                self.assertEqual(list(self.app.state.jobs), ["0", "1"])
                self.assertEqual(list(self.app.state.queue), ["0", "1"])
                self.assertEqual(self.app.state.download_dir, self.root)
                self.assertTrue(self.app.STATE_STORE.status()["recovered"])
                self.assertEqual(self.app.STATE_STORE.backup.read_bytes(), backup)

    def test_restore_valid_offline_url_requires_no_network_and_keeps_order(self):
        self.jobs()
        self.app.state.jobs['0']['url'] = 'https://offline.invalid/post'
        self.app.state.queue.clear(); self.app.state.queue.extend(['1', '0'])
        self.app._save_locked()
        self.app.state.jobs.clear(); self.app.state.queue.clear()
        with patch('socket.getaddrinfo', side_effect=AssertionError('history must not use DNS')):
            self.app._load_saved_state()
        self.assertEqual(list(self.app.state.queue), ['1', '0'])
        self.assertTrue(self.app.STATE_STORE.status()['healthy'])

    def test_unrelated_large_history_does_not_block_new_download(self):
        files = ['folder/' + 'a' * 200 + str(index) + '.jpg' for index in range(1000)]
        for index in range(80):
            self.app.state.jobs[str(index)] = {'id': str(index), 'url': f'https://example.org/old/{index}',
                'status': 'completed', 'created_at': index, 'output_dir': str(self.root), 'files': files}
        self.app.state.jobs['new'] = {'id': 'new', 'url': 'https://example.org/new', 'status': 'queued',
                                'platform': 'Web', 'created_at': 100, 'files': []}
        self.app.state.queue.append('new')
        calls = []
        def execute(payload, *args, **kwargs):
            calls.append(payload)
            try:
                self.assertEqual(payload['known_jobs'], [])
                self.assertLess(len(json.dumps(payload).encode()), 4096)
                return run_job(payload, *args, **kwargs, command=[sys.executable, '-u',
                    str(Path(__file__).with_name('test_fixture_runner.py'))])
            finally:
                self.app.state.shutdown.set()
        with patch.object(self.app, 'run_job', execute), patch.object(self.app, '_save_locked', return_value=0):
            self.app._worker_loop()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.app.state.jobs['new']['status'], 'completed')

    def test_relevant_history_keeps_identity_quality_selection_and_root(self):
        from ssdl.scheduler import QueueScheduler
        url = 'https://youtu.be/AbcD1234_-x'
        old = {'url': url, 'status': 'completed', 'output_dir': str(self.root), 'files': ['one.mp4'],
               'video_quality': '720', 'selected_media': 'a' * 24, 'size_bytes': 1}
        self.app.state.jobs['match'] = {**old, 'url': 'https://www.youtube.com/watch?v=AbcD1234_-x&t=20'}
        self.app.state.jobs['quality'] = {**old, 'video_quality': 'best'}
        self.app.state.jobs['selection'] = {**old, 'selected_media': 'b' * 24}
        self.app.state.jobs['directory'] = {**old, 'output_dir': str(self.root / 'other')}
        job = {'url': url, 'video_quality': '720', 'selected_media': 'a' * 24, 'last_success': old}
        known = QueueScheduler(self.app).known_jobs(job, self.root, None)
        self.assertEqual(len(known), 2)
        self.assertEqual([entry['files'] for entry in known], [['one.mp4'], ['one.mp4']])
        job['force_download'] = True
        self.assertEqual(QueueScheduler(self.app).known_jobs(job, self.root, None), [])

    def test_profile_history_is_scoped_to_author_and_keeps_legacy_posts(self):
        from ssdl.scheduler import QueueScheduler
        for author in ('fixture', 'other', 'i'):
            self.app.state.jobs[author] = {'url': f'https://x.com/{author}/status/1234567890',
                'status': 'completed', 'output_dir': str(self.root), 'files': [author + '.jpg']}
        known = QueueScheduler(self.app).known_jobs({'url': 'https://x.com/fixture'}, self.root,
                                                  ('https://x.com/fixture', 'fixture'))
        self.assertEqual([entry['files'][0] for entry in known], ['fixture.jpg', 'i.jpg'])

    def test_cookie_selector_handles_invalid_fields_without_type_errors(self):
        valid = {"domain": "x.com", "name": "auth_token", "value": "synthetic", "expires": 0}
        malformed = [None, {**valid, "name": []}, {**valid, "name": {}}, {**valid, "value": None},
                     {**valid, "expires": float("nan")}, {**valid, "expires": float("inf")},
                     {**valid, "expires": 10 ** 400}, {**valid, "expires": False},
                     {**valid, "domain": "google.com"}, {**valid, "expires": time.time() - 1}]
        self.assertEqual(x_auth._select_x_session(malformed), ({}, 0))
        values, expiry = x_auth._select_x_session([*malformed, valid])
        self.assertEqual(values, {"auth_token": "synthetic"})
        self.assertEqual(expiry, 0)

    def test_pairing_challenge_expires_and_cannot_be_reused(self):
        auth = x_auth.XAuthManager(self.root / "auth")
        synthetic = [{"domain": ".x.com", "name": "auth_token", "value": "synthetic-session-value"}]
        with patch.object(x_auth, "_dpapi", side_effect=lambda value, **kwargs: b"fixture-encrypted"):
            token = auth.prepare_extension()
            for malformed_token in (None, [], {}, "é" * 43, "t" * 44):
                with self.subTest(token_type=type(malformed_token).__name__):
                    with self.assertRaises(x_auth.AuthError):
                        auth.accept_extension(malformed_token, synthetic)
                    self.assertEqual(auth._challenge, token)
            auth._challenge_expires = time.time() - 1
            with self.assertRaises(x_auth.AuthError):
                auth.accept_extension(token, synthetic)
            token = auth.prepare_extension()
            auth.accept_extension(token, synthetic)
            self.assertTrue(auth.status()["connected"])
            with self.assertRaises(x_auth.AuthError):
                auth.accept_extension(token, synthetic)
        self.assertNotIn(b"synthetic-session-value", auth.secret_file.read_bytes())

    def test_storage_failure_clears_ticket_and_reports_failed(self):
        auth = x_auth.XAuthManager(self.root / "auth")
        with patch.object(x_auth, "_dpapi", return_value=b"preflight"):
            token = auth.prepare_extension()
        with patch.object(x_auth, "_dpapi", side_effect=x_auth.AuthError("fixture encryption failure")):
            with self.assertRaises(x_auth.AuthError):
                auth.accept_extension(token, [{"domain": "x.com", "name": "auth_token", "value": "synthetic"}])
        self.assertEqual(auth.status()["phase"], "failed")
        self.assertFalse(auth.status()["busy"])
        self.assertFalse(auth._challenge)

    def test_failed_disconnect_keeps_status_consistent_and_allows_retry(self):
        auth = x_auth.XAuthManager(self.root / "auth")
        with patch.object(x_auth, "_dpapi", return_value=b"fixture-encrypted"):
            auth._remember({"auth_token": "synthetic"}, time.time() + 600, "fixture", auth._stop)
        with patch.object(Path, "unlink", side_effect=PermissionError("synthetic locked file")):
            with self.assertRaises(x_auth.AuthError):
                auth.disconnect()
        self.assertTrue(auth.status()["connected"])
        self.assertTrue(auth.cookies().get("auth_token"))
        self.assertFalse(auth.status()["busy"])
        auth.disconnect()
        self.assertFalse(auth.status()["connected"])
        self.assertEqual(auth.cookies(), {})
        self.assertFalse(auth.secret_file.exists())
