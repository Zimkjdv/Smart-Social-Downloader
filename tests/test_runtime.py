import ctypes
import io
import json
from ctypes import wintypes
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from ssdl.job_runtime import run_job
from ssdl.media import DownloadError
from ssdl.request_policy import RequestPolicy
from ssdl import ipc


class RuntimeTests(unittest.TestCase):
    command = [sys.executable, "-u", str(Path(__file__).with_name("test_fixture_runner.py"))]

    def run_fixture(self, mode="success", **kwargs):
        return run_job({"mode": mode}, kwargs.pop("emit", lambda event: None),
            kwargs.pop("gate", lambda **values: None), kwargs.pop("cancelled", lambda: False), RequestPolicy(),
            command=self.command, no_progress_timeout=kwargs.pop("timeout", 2), **kwargs)

    def test_success_error_exit_and_no_progress_have_distinct_results(self):
        self.assertEqual(self.run_fixture()["title"], "fixture")
        for mode, code in (("error", "fixture_failure"), ("exit", "worker_exited"), ("hang", "download_stalled")):
            with self.subTest(mode=mode), self.assertRaises(DownloadError) as failure:
                self.run_fixture(mode)
            self.assertEqual(failure.exception.code, code)

    def test_stop_does_not_wait_for_stall_deadline(self):
        began = time.monotonic()
        with self.assertRaises(DownloadError) as failure:
            self.run_fixture("hang", timeout=20, cancelled=lambda: time.monotonic() - began > .4)
        self.assertEqual(failure.exception.code, "download_cancelled")
        self.assertLess(time.monotonic() - began, 5)

    def test_large_unicode_input_progress_and_result_survive_chunking(self):
        files = ['folder/' + '\u5716' * 80 + str(index) + '.jpg' for index in range(70000)]
        data = {"mode": "large_files", "files": files}
        self.assertGreater(len(json.dumps(data, ensure_ascii=False).encode('utf-8')), ipc.MAX_FRAME_BYTES)
        progress = []
        result = run_job(data, lambda event: progress.append(event['files']), lambda **values: None,
                         lambda: False, RequestPolicy(), command=self.command, no_progress_timeout=20)
        self.assertEqual(progress, [files])
        self.assertEqual(result['files'], files)
        self.assertEqual(self.run_fixture()['title'], 'fixture')

    def test_invalid_truncated_and_oversized_chunks_have_explicit_errors(self):
        for mode, code in (('bad_chunk', 'worker_protocol'), ('truncated_chunk', 'worker_protocol'),
                           ('oversize_chunk', 'worker_message_too_large')):
            with self.subTest(mode=mode), self.assertRaises(DownloadError) as failure:
                self.run_fixture(mode)
            self.assertEqual(failure.exception.code, code)
        self.assertEqual(self.run_fixture()['title'], 'fixture')

    def test_cancel_during_partial_chunk_does_not_wait_for_completion(self):
        start = time.monotonic()
        with self.assertRaises(DownloadError) as failure:
            self.run_fixture('chunk_hang', timeout=20, cancelled=lambda: time.monotonic() - start > .4)
        self.assertEqual(failure.exception.code, 'download_cancelled')
        self.assertLess(time.monotonic() - start, 5)

    def test_oversize_input_reports_capacity_before_worker_exit(self):
        with patch.object(ipc, 'MAX_MESSAGE_BYTES', 1024), self.assertRaises(DownloadError) as failure:
            run_job({'mode': 'success', 'padding': 'x' * 1024}, lambda event: None,
                    lambda **values: None, lambda: False, RequestPolicy(), command=self.command)
        self.assertEqual(failure.exception.code, 'worker_message_too_large')

    def test_chunk_codec_limits_each_frame_and_rejects_corruption(self):
        value = {'files': ['\u5716\u7247.jpg'] * 20}
        with patch.object(ipc, 'MAX_FRAME_BYTES', 256), patch.object(ipc, 'CHUNK_BYTES', 64):
            stream = io.BytesIO(); ipc.write_message(stream, value)
            wire = stream.getvalue()
            self.assertTrue(all(len(line) <= 256 for line in wire.splitlines(keepends=True)))
            self.assertEqual(ipc.read_message(io.BytesIO(wire)), value)
            frames = wire.splitlines(keepends=True)
            self.assertGreater(len(frames), 1)
            for bad in (b'{bad}\n', wire[:-1], b'[]\n', b'x' * 257,
                        frames[0] + frames[0], frames[0] + frames[-1]):
                with self.subTest(size=len(bad)), self.assertRaises(ipc.ProtocolError):
                    ipc.read_message(io.BytesIO(bad))

    def test_production_child_capacity_errors_remain_compact_and_allow_next_job(self):
        for mode in ("capacity_result", "capacity_progress", "capacity_error", "capacity_selection"):
            with self.subTest(mode=mode), self.assertRaises(DownloadError) as failure:
                self.run_fixture(mode, timeout=15)
            self.assertEqual(failure.exception.code, "worker_message_too_large")
            self.assertEqual(str(failure.exception), ipc.CAPACITY_ERROR)
            self.assertEqual(failure.exception.files, [])
        self.assertEqual(self.run_fixture()["title"], "fixture")

    def test_intentional_queue_wait_is_not_stall(self):
        phases = []
        self.assertEqual(self.run_fixture("wait", timeout=.6,
            gate=lambda **values: time.sleep(1), health=lambda value: phases.append(value["phase"]))["title"], "fixture")
        self.assertIn("waiting", phases)

    @unittest.skipUnless(os.name == "nt", "Windows process-tree ownership")
    def test_active_merge_cpu_is_progress_not_total_duration_timeout(self):
        self.assertEqual(self.run_fixture("merge", timeout=.7)["title"], "fixture")

    @unittest.skipUnless(os.name == "nt", "Windows process-tree ownership")
    def test_stop_terminates_only_the_owned_helper_tree(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handles = []
        def emit(event):
            if event.get("child_pid"):
                handles.append(kernel.OpenProcess(0x100000, False, event["child_pid"]))
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            with self.assertRaises(DownloadError):
                self.run_fixture("tree", emit=emit, cancelled=lambda: bool(handles))
            self.assertTrue(handles[0])
            self.assertEqual(kernel.WaitForSingleObject(handles[0], 3000), 0)
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.kill()
            unrelated.wait(timeout=5)
            for handle in handles:
                if handle:
                    kernel.CloseHandle(handle)

    def test_production_child_blocks_loopback_before_any_transfer(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-runner-") as directory:
            root = Path(directory)
            with self.assertRaises(DownloadError) as failure:
                run_job({"url": "http://127.0.0.1:1/one.png", "output_dir": str(root / "downloads"),
                    "manifest_file": str(root / "manifest.sqlite3"), "image_history_file": str(root / "images.sqlite3")},
                    lambda event: None, lambda **values: None, lambda: False, RequestPolicy(), no_progress_timeout=15)
            self.assertEqual(failure.exception.code, "unsafe_target")
            self.assertFalse(list(root.rglob("*.png")))
