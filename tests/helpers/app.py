"""Own an isolated AppContext, its service overrides and temporary files."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

from ssdl.app import create_app
from ssdl.persistence import StateStore


class IsolatedApp:
    def __enter__(self):
        self.resources = ExitStack()
        try:
            temporary = self.resources.enter_context(tempfile.TemporaryDirectory(prefix="ssdl-app-fixture-"))
            root = Path(temporary).resolve()
            app = create_app(root, download_dir=root, storage=Mock(), state_store=StateStore(root / "state.json"))
            # Stop both currently installed overrides and the original owned
            # services. Restore patches only after app workers/writer stop.
            for service in (app.X_AUTH, app.THUMBNAILS, app.STORAGE, app.ENVIRONMENT, app.DATABASES):
                self.resources.callback(service.shutdown)
            patches = ExitStack()
            self.resources.callback(patches.close)
            self.resources.callback(app.close)
            app.JOB_DELAY_MIN = app.JOB_DELAY_MAX = 0
            self.fixture = SimpleNamespace(app=app, root=root, stack=patches)
            return self.fixture
        except BaseException:
            self.resources.close()
            raise

    def __exit__(self, *exception):
        return self.resources.__exit__(*exception)


def seed_jobs(app, count=2):
    keys = []
    for index in range(count):
        key = str(index)
        app.state.jobs[key] = {"id": key, "url": f"https://example.org/{key}", "status": "queued",
                               "platform": "Web", "created_at": 100 + index, "files": []}
        app.state.queue.append(key)
        keys.append(key)
    return keys
