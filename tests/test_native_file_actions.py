"""Native action dispatch regression; desktop applications are never launched."""
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.helpers.app import IsolatedApp


class NativeFileActionTests(unittest.TestCase):
    def setUp(self):
        fixture = self.enterContext(IsolatedApp())
        self.app, self.root = fixture.app, fixture.root
        self.file = self.root / "original.mp4"
        self.file.write_bytes(b"invented original")
        self.app.state.jobs["fixture"] = {"id": "fixture", "status": "completed", "files": [self.file.name],
                                          "output_dir": str(self.root)}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.Handler)
        self.enterContext(patch.object(self.app, "PORT", self.server.server_port))
        self.enterContext(patch.object(self.app.Handler, "log_message"))
        self.enterContext(patch("ssdl.http_api.host_browser_required", return_value=False))
        self.launch = Mock()
        self.enterContext(patch("ssdl.http_api.os", SimpleNamespace(name="nt", startfile=self.launch)))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        def close_server():
            self.server.shutdown()
            thread.join(timeout=3)
            self.server.server_close()
        self.addCleanup(close_server)

    def request(self, action, filename="original.mp4"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("POST", "/api/jobs/fixture/" + action,
                               body=json.dumps({"file_index": 0, "filename": filename}),
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_native_file_and_folder_keep_desktop_dispatch(self):
        for action, destination in (("open-file", self.file), ("open-folder", self.root)):
            with self.subTest(action=action):
                code, result = self.request(action)
                self.assertEqual((code, result), (200, {"opened": True}))
                self.launch.assert_called_with(str(destination))

    def test_stale_or_deleted_file_never_launches_desktop(self):
        self.assertEqual(self.request("open-file", "stale.mp4")[0], 409)
        self.file.unlink()
        self.assertEqual(self.request("open-file")[0], 404)
        self.launch.assert_not_called()
        self.assertEqual(self.app.state.jobs["fixture"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
