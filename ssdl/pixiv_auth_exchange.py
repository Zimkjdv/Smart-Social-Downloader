"""Isolated, fixed-endpoint Pixiv token exchange; credentials travel only over stdin."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


def exchange(values):
    from gallery_dl.extractor.pixiv import PixivAppAPI
    from .network import public_network
    grant = values["grant"]
    if grant not in {"authorization_code", "refresh_token"}:
        raise ValueError("grant")
    data = {"client_id": PixivAppAPI.CLIENT_ID, "client_secret": PixivAppAPI.CLIENT_SECRET, "grant_type": grant}
    if grant == "authorization_code":
        data.update(code=values["code"], code_verifier=values["verifier"], include_policy="true",
                    redirect_uri="https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback")
    else:
        data["refresh_token"] = values["refresh_token"]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    headers = {"User-Agent": "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)",
               "Content-Type": "application/x-www-form-urlencoded", "X-Client-Time": stamp,
               "X-Client-Hash": hashlib.md5((stamp + PixivAppAPI.HASH_SECRET).encode()).hexdigest()}
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = Request("https://oauth.secure.pixiv.net/auth/token", data=urlencode(data).encode(), headers=headers)
    with public_network(), build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(32 * 1024 + 1)
    if len(raw) > 32 * 1024:
        raise ValueError("response limit")
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get("error") or result.get("has_error"):
        raise ValueError("rejected")
    nested = result.get("response")
    token = result.get("refresh_token") or (nested.get("refresh_token") if isinstance(nested, dict) else None)
    if not isinstance(token, str) or not 20 <= len(token) <= 4096:
        raise ValueError("token")
    return {"refresh_token": token}


def main():
    try:
        raw = sys.stdin.buffer.read(16 * 1024 + 1)
        if len(raw) > 16 * 1024:
            raise ValueError("input limit")
        result = exchange(json.loads(raw))
        sys.stdout.write(json.dumps(result))
        return 0
    except Exception:
        sys.stdout.write('{"error":"pixiv_auth_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
