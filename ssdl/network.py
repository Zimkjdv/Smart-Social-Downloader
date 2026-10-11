"""Public HTTP(S) transport policy installed only in an isolated download process.

DNS results are checked at resolution and sockets connect to the checked numeric
address. Redirects, manifests, keys, fragments, and extractor requests inherit it.
This is an application transport boundary, not an operating-system sandbox.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit
import urllib.request
from unittest.mock import patch


class NetworkBlocked(OSError):
    code = "unsafe_target"


def public_address(value):
    try:
        address = ipaddress.ip_address(value)
        embedded = getattr(address, "ipv4_mapped", None) or getattr(address, "sixtofour", None)
        teredo = getattr(address, "teredo", None)
        return (address.is_global and not address.is_multicast and
                (embedded is None or embedded.is_global) and
                (teredo is None or all(item.is_global for item in teredo)))
    except ValueError:
        return False


def validate_url(value):
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None:
            raise ValueError
        if any(ord(char) <= 32 or ord(char) == 127 for char in value):
            raise ValueError
        parsed.port
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or "%" in host:
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise ValueError
        else:
            if not public_address(host):
                raise ValueError
        return host
    except (ValueError, TypeError, UnicodeError):
        raise NetworkBlocked("媒體來源必須是公開 HTTP／HTTPS 網址；已拒絕非公開目標。") from None


def checked_addresses(resolver, host, port, family=0, type=0, proto=0, flags=0):
    if not host:
        raise NetworkBlocked("已拒絕非公開網路目標。")
    values = resolver(host, port, family, type, proto, flags)
    if not values or any(not public_address(value[4][0]) for value in values):
        raise NetworkBlocked("來源 DNS 包含非公開位址；已拒絕連線。")
    return values


@contextmanager
def public_network(activity=lambda: None):
    """Must never wrap the web server: it needs its own loopback sockets."""
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_open = urllib.request.OpenerDirector.open
    original_recv = socket.socket.recv
    original_recv_into = socket.socket.recv_into
    original_ssl_read = ssl.SSLSocket.read

    def resolve(host, port, family=0, type=0, proto=0, flags=0):
        return checked_addresses(original_resolve, host, port, family, type, proto, flags)

    def numeric(sock, address):
        if sock.family not in {socket.AF_INET, socket.AF_INET6}:
            raise NetworkBlocked("只允許公開 IPv4／IPv6 媒體連線。")
        values = checked_addresses(original_resolve, address[0], address[1], sock.family, sock.type, sock.proto)
        # A second DNS lookup cannot silently switch this socket to an unchecked
        # address: the original connect receives a numeric address, not a host.
        return values[0][4]

    def connect(sock, address):
        result = original_connect(sock, numeric(sock, address))
        activity()
        return result

    def connect_ex(sock, address):
        result = original_connect_ex(sock, numeric(sock, address))
        if result == 0:
            activity()
        return result

    def opened(opener, request, *args, **kwargs):
        validate_url(request.full_url if hasattr(request, "full_url") else request)
        return original_open(opener, request, *args, **kwargs)

    def received(sock, *args, **kwargs):
        value = original_recv(sock, *args, **kwargs)
        if value:
            activity()
        return value

    def received_into(sock, *args, **kwargs):
        value = original_recv_into(sock, *args, **kwargs)
        if value:
            activity()
        return value

    def ssl_read(sock, *args, **kwargs):
        value = original_ssl_read(sock, *args, **kwargs)
        if value:
            activity()
        return value

    with ExitStack() as stack:
        for owner, name, value in ((socket, "getaddrinfo", resolve),
                (socket.socket, "connect", connect), (socket.socket, "connect_ex", connect_ex),
                (socket.socket, "recv", received), (socket.socket, "recv_into", received_into),
                (ssl.SSLSocket, "read", ssl_read), (urllib.request.OpenerDirector, "open", opened),
                (urllib.request, "getproxies", lambda: {})):
            stack.enter_context(patch.object(owner, name, value))
        import requests
        original_send = requests.Session.send

        def send(session, request, **kwargs):
            validate_url(request.url)
            kwargs["proxies"] = {}
            return original_send(session, request, **kwargs)

        stack.enter_context(patch.object(requests.Session, "send", send))
        import yt_dlp
        from yt_dlp.downloader.external import ExternalFD
        from yt_dlp.downloader.fragment import FragmentFD
        original_director = yt_dlp.YoutubeDL.build_request_director
        original_urlopen = yt_dlp.YoutubeDL.urlopen

        def director(downloader, handlers, preferences=None):
            # curl_cffi uses its own resolver and would bypass Python sockets.
            downloader.params["proxy"] = ""
            downloader.__dict__.pop("proxies", None)
            return original_director(downloader, [handler for handler in handlers if handler.RH_KEY == "Urllib"], preferences)

        def yt_open(downloader, request):
            validate_url(request if isinstance(request, str) else getattr(request, "url", getattr(request, "full_url", "")))
            return original_urlopen(downloader, request)

        def forbidden_external(*args, **kwargs):
            raise NetworkBlocked("此來源需要外部網路下載器；目前僅允許受檢查的 HTTP／HLS／DASH 傳輸。")

        original_fragments = FragmentFD.download_and_append_fragments
        def fragments(downloader, context, *args, **kwargs):
            try:
                return original_fragments(downloader, context, *args, **kwargs)
            except BaseException:
                # Upstream closes the destination for expected fragment errors,
                # but a policy exception must also release the .part handle.
                stream = context.get("dest_stream")
                if stream is not None and context.get("filename") != "-":
                    stream.close()
                raise

        stack.enter_context(patch.object(yt_dlp.YoutubeDL, "build_request_director", director))
        stack.enter_context(patch.object(yt_dlp.YoutubeDL, "urlopen", yt_open))
        # FFmpeg remains available for merging local files; network downloads
        # via external programs have no socket policy and are rejected.
        stack.enter_context(patch.object(ExternalFD, "real_download", forbidden_external))
        stack.enter_context(patch.object(FragmentFD, "download_and_append_fragments", fragments))
        from yt_dlp.downloader.rtmp import RtmpFD
        stack.enter_context(patch.object(RtmpFD, "real_download", forbidden_external))
        yield
