"""Strict, bounded Native Messaging frames; no secrets or webpage APIs."""
from __future__ import annotations

import json
import re
import struct
import unicodedata

VERSION = '1.2.1'
HOST_NAME = 'com.suishou.reply'
EXTENSION_ID = 'pibjjmjbipbifeddoahjagcinihkcgnf'
TRUSTED_ORIGIN = f'chrome-extension://{EXTENSION_ID}/'
MAX_INPUT_BYTES = 32768
MAX_OUTPUT_BYTES = 65536
_REQUEST_ID = re.compile(r'[A-Za-z0-9_-]{1,80}\Z')
_POST_URL = re.compile(r'https://x\.com/([A-Za-z0-9_]{1,15})/status/([0-9]{1,25})\Z')
_STYLES = ('自然', '犀利', '幽默')


class ProtocolError(ValueError):
    """Only a fixed safe error, never the input text or decoded JSON."""

    def __init__(self):
        super().__init__('本地通信消息无效，请刷新扩展后重试。')


def valid_request_id(value) -> bool:
    return isinstance(value, str) and _REQUEST_ID.fullmatch(value) is not None


def safe_text(value, maximum: int, *, nonempty: bool = False) -> bool:
    if not isinstance(value, str) or len(value) > maximum:
        return False
    if nonempty and not value.strip():
        return False
    return not any(unicodedata.category(char).startswith('C') and char not in '\r\n\t'
                   for char in value)


def valid_caller(arguments: list[str]) -> bool:
    if len(arguments) not in (1, 2) or arguments[0] != TRUSTED_ORIGIN:
        return False
    if len(arguments) == 1:
        return True
    match = re.fullmatch(r'--parent-window=([0-9]{1,20})', arguments[1])
    return match is not None and int(match[1]) <= 2 ** 64 - 1


def validate_message(value: object) -> dict:
    if not isinstance(value, dict) or type(value.get('v')) is not int or value['v'] != 1:
        raise ProtocolError()
    if not valid_request_id(value.get('id')):
        raise ProtocolError()
    kind = value.get('type')
    if kind in ('cancel', 'ping'):
        if set(value) != {'v', 'type', 'id'}:
            raise ProtocolError()
        return dict(value)
    if (kind != 'generate' or set(value) != {'v', 'type', 'id', 'post', 'style', 'previous'}
            or value['style'] not in _STYLES or not safe_text(value['previous'], 500)):
        raise ProtocolError()
    post = value['post']
    if not isinstance(post, dict) or set(post) != {'id', 'url', 'author', 'text'}:
        raise ProtocolError()
    if not isinstance(post['url'], str):
        raise ProtocolError()
    match = _POST_URL.fullmatch(post['url'])
    if (match is None or post['id'] != match[2] or not isinstance(post['author'], str)
            or post['author'].lower() != '@' + match[1].lower()
            or not safe_text(post['text'], 3000, nonempty=True)):
        raise ProtocolError()
    return dict(value, post=dict(post))


def _read_exact(stream, count: int, *, initial: bool = False) -> bytes | None:
    parts = bytearray()
    while len(parts) < count:
        chunk = stream.read(count - len(parts))
        if not chunk:
            if initial and not parts:
                return None
            raise ProtocolError()
        parts.extend(chunk)
    return bytes(parts)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ProtocolError()
        value[key] = item
    return value


def _invalid_constant(_value):
    raise ProtocolError()


def read_frame(stream) -> dict | None:
    header = _read_exact(stream, 4, initial=True)
    if header is None:
        return None
    length = struct.unpack('<I', header)[0]
    if not 0 < length <= MAX_INPUT_BYTES:
        raise ProtocolError()
    try:
        result = json.loads(_read_exact(stream, length).decode('utf-8'),
                            object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise ProtocolError() from None
    if not isinstance(result, dict):
        raise ProtocolError()
    return result


def encode_frame(message: dict) -> bytes:
    try:
        payload = json.dumps(message, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ProtocolError() from None
    if not 0 < len(payload) <= MAX_OUTPUT_BYTES:
        raise ProtocolError()
    return struct.pack('<I', len(payload)) + payload
