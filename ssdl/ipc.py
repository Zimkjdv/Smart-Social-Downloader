"""Bounded binary JSON frames; larger job messages travel in ordered chunks."""
from __future__ import annotations

import base64
import binascii
import json
from .json_budget import encode_json, JSONBudgetError

MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 256 * 1024


class ProtocolError(ValueError):
    pass


class MessageTooLarge(ProtocolError):
    pass


CAPACITY_ERROR = "下載工作資料超過 64 MiB 通訊容量；此工作已停止，已下載原檔保留，後續佇列會繼續。"


def _encode(value):
    try:
        return encode_json(value, MAX_MESSAGE_BYTES)
    except JSONBudgetError as exc:
        raise MessageTooLarge("Message exceeds total byte budget") from exc
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("Invalid message") from exc


def write_message(stream, value):
    raw = _encode(value)
    if len(raw) > MAX_MESSAGE_BYTES:
        raise MessageTooLarge("Message exceeds total byte budget")
    if len(raw) + 1 <= MAX_FRAME_BYTES:
        stream.write(raw + b"\n")
        stream.flush()
        return
    for offset in range(0, len(raw), CHUNK_BYTES):
        frame = _encode({"_ipc": "chunk", "size": len(raw), "offset": offset,
                         "data": base64.b64encode(raw[offset:offset + CHUNK_BYTES]).decode("ascii")})
        if len(frame) + 1 > MAX_FRAME_BYTES:
            raise ProtocolError("Chunk exceeds frame byte budget")
        stream.write(frame + b"\n")
        stream.flush()


def _read_frame(stream):
    line = stream.readline(MAX_FRAME_BYTES + 1)
    if not line:
        return None
    if len(line) > MAX_FRAME_BYTES:
        raise ProtocolError("Frame exceeds byte budget")
    if not line.endswith(b"\n"):
        raise ProtocolError("Truncated frame")
    try:
        value = json.loads(line)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("Invalid frame") from exc
    if not isinstance(value, dict):
        raise ProtocolError("Invalid frame object")
    return value


def read_message(stream):
    frame = _read_frame(stream)
    if frame is None or "_ipc" not in frame:
        return frame
    size = frame.get("size")
    if type(size) is not int or size <= 0:
        raise ProtocolError("Invalid chunk size")
    if size > MAX_MESSAGE_BYTES:
        raise MessageTooLarge("Message exceeds total byte budget")
    raw = bytearray()
    while True:
        if (frame.get("_ipc") != "chunk" or type(frame.get("size")) is not int or frame["size"] != size
                or type(frame.get("offset")) is not int or frame["offset"] != len(raw)
                or not isinstance(frame.get("data"), str) or len(frame["data"]) > ((CHUNK_BYTES + 2) // 3) * 4):
            raise ProtocolError("Invalid chunk sequence")
        try:
            chunk = base64.b64decode(frame["data"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ProtocolError("Invalid chunk encoding") from exc
        if not chunk or len(chunk) > CHUNK_BYTES or len(raw) + len(chunk) > size:
            raise ProtocolError("Invalid chunk bytes")
        raw.extend(chunk)
        if len(raw) == size:
            break
        frame = _read_frame(stream)
        if frame is None:
            raise ProtocolError("Truncated message")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("Invalid message JSON") from exc
    if not isinstance(value, dict) or "_ipc" in value:
        raise ProtocolError("Invalid message object")
    return value
