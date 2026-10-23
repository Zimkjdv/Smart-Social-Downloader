"""Pixiv author identity across scan progress, transfer and job presentation."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from gallery_dl.extractor.common import Message

from ssdl import gallery_adapter, pixiv_profiles
from ssdl.job_views import job_summary
from tests.helpers.app import IsolatedApp


class PixivAuthorPresentationTests(unittest.TestCase):
    def test_author_title_is_available_before_transfer_and_in_final_result(self):
        self.addCleanup(gallery_adapter.engines.gallery_config.clear)
        events, transferred = [], []
        author = {"id": 82728784, "name": "Hoshirapu"}
        metadata = {"id": 123456, "user": author, "count": 1, "num": 0, "extension": "png"}

        class Source:
            category, subcategory, status = "pixiv", "artworks", 0
            session = SimpleNamespace(send=Mock())

            def initialize(self):
                pass

            def items(self):
                yield Message.Directory, "", dict(metadata)
                yield Message.Url, "https://i.pximg.net/img-original/2026/10/24/00/00/00/123456_p0.png", dict(metadata)

        def transfer(snapshot, root, emit):
            ready = next(event for event in events if event.get("profile_scan_finished"))
            self.assertEqual(ready["title"], "Pixiv · Hoshirapu(82728784)")
            self.assertEqual(ready["files"], [])
            snapshot.initialize()
            try:
                self.assertEqual(snapshot.session.headers["Referer"], "https://www.pixiv.net/")
                for kind, _, data in snapshot.items():
                    if kind != Message.Url:
                        continue
                    name = str(Path("pixiv") / data["author_folder"] / f'{data["id"]}_p{data["num"]}.{data["extension"]}')
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic original image bytes")
                    transferred.append(name)
                    emit({"files": list(transferred)})
            finally:
                snapshot.session.close()
            return {"files": list(transferred), "quality": "original"}

        with tempfile.TemporaryDirectory(prefix="ssdl-pixiv-title-") as temporary:
            root = Path(temporary)
            with patch.object(gallery_adapter, "_pace_gallery"), \
                    patch.object(gallery_adapter, "download_gallery", side_effect=transfer), \
                    patch.object(pixiv_profiles.engines.gallery_extractor, "find", return_value=Source()), \
                    patch.object(pixiv_profiles.request_policy, "POLICY", Mock()):
                result = pixiv_profiles.download_pixiv_account(
                    "https://www.pixiv.net/users/82728784", root, events.append,
                    archive_file=root / "profiles.sqlite3", refresh_token="SYNTHETIC_PIXIV_SESSION",
                    before_post=Mock(), checkpoint=Mock())
        self.assertEqual(result["title"], "Pixiv · Hoshirapu(82728784)")
        self.assertEqual(len(result["files"]), 1)

    def test_progress_publishes_pixiv_name_without_replacing_x_account_identity(self):
        with IsolatedApp() as fixture:
            app = fixture.app
            title = "Pixiv · " + "A" * 160 + "(12345678901234567890)"
            for mode, expected in (("pixiv_profile", title), ("x_profile", "@fixture"), ("urls", title[:180])):
                with self.subTest(mode=mode):
                    app.state.jobs["author"] = {"id": "author", "mode": mode, "title": "@fixture", "files": []}
                    app._progress_hook("author")({"title": title})
                    self.assertEqual(job_summary(app.state.jobs["author"])["title"], expected)
