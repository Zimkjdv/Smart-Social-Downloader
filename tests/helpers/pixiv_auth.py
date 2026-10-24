"""Invented OAuth exchange with real private AES-GCM or memory-only storage."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from ssdl import pixiv_auth
from ssdl.session_storage import SessionStorage

TOKEN = "SYNTHETIC_PIXIV_REFRESH_TOKEN_FIRST"
NEXT_TOKEN = "SYNTHETIC_PIXIV_REFRESH_TOKEN_NEXT"
CODE = "SYNTHETIC_PIXIV_AUTHORIZATION_CODE"


class AuthFixture:
    def __init__(self, *, memory=False):
        self.memory = memory

    def __enter__(self):
        self.stack = ExitStack()
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="ssdl-pixiv-auth-")))
        self.key = self.root / "private-key.bin"
        self.key.write_bytes(secrets.token_bytes(32))
        values = dict(os.environ)
        values.pop("SSDL_X_KEY_FILE", None)
        values["SSDL_CONTAINER"] = "1" if self.memory else "0"
        if not self.memory:
            values["SSDL_X_KEY_FILE"] = str(self.key)
        self.stack.enter_context(patch.dict(os.environ, values, clear=True))
        self.stack.enter_context(patch.object(pixiv_auth, "host_browser_required", return_value=True))
        self.exchange = Mock(return_value=self.response(TOKEN))
        self.stack.enter_context(patch.object(pixiv_auth.subprocess, "run", self.exchange))
        self.managers = []
        self.auth = self.manager()
        return self

    def __exit__(self, *args):
        for manager in self.managers:
            manager.shutdown()
        return self.stack.__exit__(*args)

    def manager(self, *, port=18991):
        storage = SessionStorage(windows_protect=Mock(side_effect=AssertionError("Unexpected native login access")))
        auth = pixiv_auth.PixivAuthManager(self.root / "data", storage=storage, port=port)
        self.managers.append(auth)
        return auth

    @staticmethod
    def response(token):
        return SimpleNamespace(returncode=0, stdout=json.dumps({"refresh_token": token}).encode())

    def begin(self):
        result = self.auth.begin()
        ticket = parse_qs(urlsplit(result["pairing_url"]).fragment)["ticket"][0]
        return result, ticket

    def connect(self):
        _, ticket = self.begin()
        self.auth.claim(ticket)
        return self.auth.connect(ticket=ticket, code=CODE)
