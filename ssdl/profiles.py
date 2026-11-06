"""Account URLs and provider identity shared by queue admission and workers."""
import re
from urllib.parse import urlparse

from .x_profiles import normalize_account, account_from_url as x_account_from_url

PROFILE_MODES = frozenset({"x_profile", "pixiv_profile"})


def normalize_pixiv_account(raw):
    if not isinstance(raw, str):
        raise ValueError("請輸入 Pixiv 作者網址或作者 ID。")
    value = raw.strip()
    if re.fullmatch(r"[1-9][0-9]{0,19}", value):
        account = value
    else:
        try:
            parsed = urlparse(value)
            match = re.fullmatch(r"/(?:[a-z]{2}/)?users/([1-9][0-9]{0,19})(?:/(?:artworks|illustrations|manga))?/?", parsed.path)
            if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"pixiv.net", "www.pixiv.net"}
                    or parsed.username or parsed.password or parsed.port is not None or not match):
                raise ValueError
            account = match[1]
        except (ValueError, UnicodeError):
            raise ValueError("請輸入 Pixiv 作者首頁、作品頁網址或數字作者 ID。") from None
    return f"https://www.pixiv.net/users/{account}", account


def account_from_url(url):
    profile = x_account_from_url(url)
    if profile:
        return profile
    if not isinstance(url, str) or "://" not in url:
        return None
    try:
        return normalize_pixiv_account(url)
    except ValueError:
        return None


def profile_mode(url):
    return "pixiv_profile" if (urlparse(url).hostname or "").lower() in {"pixiv.net", "www.pixiv.net"} else "x_profile"
