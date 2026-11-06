"""Synthetic Pixiv listings/transport with real paths and scoped SQLite archives."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gallery_dl.extractor.common import Message
from ssdl import gallery_adapter, pixiv_profiles
from ssdl.x_profiles import ProfileArchive


class Source:
    category, subcategory, status = "pixiv", "artworks", 0

    def __init__(self, author, works):
        self.author, self.works = author, works
        self.session = SimpleNamespace(send=Mock(), close=Mock())

    def initialize(self):
        pass

    def items(self):
        for artwork, count in self.works:
            data = {"id": int(artwork), "user": dict(self.author), "count": count, "extension": "png"}
            yield Message.Directory, "", dict(data)
            for page in range(count):
                yield Message.Url, f"https://i.pximg.net/img-original/2026/10/25/00/00/00/{artwork}_p{page}.png", dict(data, num=page)


class PixivFixture:
    def __enter__(self):
        self.stack = ExitStack()
        self.workspace = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="ssdl-pixiv-")))
        self.root = self.workspace / "media"
        self.root.mkdir()
        self.archive = self.workspace / "data/profiles.sqlite3"
        self.events, self.transferred = [], []
        return self

    def __exit__(self, *args):
        gallery_adapter.engines.gallery_config.clear()
        return self.stack.__exit__(*args)

    def seed(self, folder, artwork="100", pages=(0, 1), *, account="123", record=True):
        names = []
        for page in pages:
            name = str(Path("pixiv") / folder / f"{artwork}_p{page}.png")
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f"synthetic original {artwork}/{page}".encode())
            names.append(name)
        if record:
            archive = ProfileArchive(self.archive, self.root, "pixiv:" + account)
            try:
                archive.record(artwork, names, len(names))
            finally:
                archive.close()
        return names

    def signature(self, names, root=None):
        root = root or self.root
        return {name: ((root / name).stat().st_mtime_ns, hashlib.sha256((root / name).read_bytes()).hexdigest()) for name in names}

    def transfer(self, snapshot, root, emit):
        names = []
        snapshot.initialize()
        try:
            for kind, _, data in snapshot.items():
                if kind != Message.Url:
                    continue
                relative = Path(*(segment.format_map(data) for segment in snapshot.directory_fmt)) / snapshot.filename_fmt.format_map(data)
                target = root / relative
                if not target.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Synthetic transport escaped its fixture")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(f'synthetic original {data["id"]}/{data["num"]}'.encode())
                names.append(str(relative))
                self.transferred.append(str(relative))
                emit({"files": list(names)})
        finally:
            snapshot.session.close()
        return {"files": names, "quality": "original"}

    def sync(self, *, name="作者", account="123", works=(("100", 2),), root=None,
             source=None, before_post=None, checkpoint=None, transfer=None, previous_files=(), policy=None):
        self.events.clear()
        self.transferred.clear()
        source = source or Source({"id": int(account), "name": name}, works)
        self.policy = policy or Mock()
        with patch.object(gallery_adapter, "_pace_gallery"), \
             patch.object(gallery_adapter, "download_gallery", side_effect=transfer or self.transfer), \
             patch.object(pixiv_profiles.engines.gallery_extractor, "find", return_value=source), \
             patch.object(pixiv_profiles.request_policy, "POLICY", self.policy):
            return pixiv_profiles.download_pixiv_account(
                f"https://www.pixiv.net/users/{account}", root or self.root, self.events.append,
                archive_file=self.archive, refresh_token="SYNTHETIC_PIXIV_SESSION",
                before_post=before_post or Mock(), checkpoint=checkpoint or Mock(), previous_files=previous_files)
