"""Native bridge boundaries; only synthetic data is used."""
import io
import json
import struct

import pytest

from suishou import edge_protocol as protocol


def request(**changes):
    value = {'v': 1, 'type': 'generate', 'id': 'request-1',
             'post': {'id': '123456', 'url': 'https://x.com/test_user/status/123456',
                      'author': '@test_user', 'text': 'AI工具应该先解决实际问题，再讨论参数。'},
             'style': '自然', 'previous': ''}
    value.update(changes)
    return value


def test_frame_roundtrip_and_clean_eof():
    value = request()
    encoded = protocol.encode_frame(value)
    assert struct.unpack('<I', encoded[:4])[0] == len(encoded) - 4
    assert protocol.read_frame(io.BytesIO(encoded)) == value
    assert protocol.read_frame(io.BytesIO()) is None


@pytest.mark.parametrize('raw', [b'\x01', struct.pack('<I', 0),
    struct.pack('<I', 32769), struct.pack('<I', 5) + b'{}',
    struct.pack('<I', 1) + b'\xff', struct.pack('<I', 4) + b'null',
    struct.pack('<I', 13) + b'{"v":1,"v":2}',
    struct.pack('<I', 9) + b'{"n":NaN}'])
def test_rejects_malformed_frames_without_exposing_data(raw):
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.read_frame(io.BytesIO(raw))
    assert 'NaN' not in str(exc.value)


def test_rejects_large_outgoing_frame():
    with pytest.raises(protocol.ProtocolError):
        protocol.encode_frame({'text': 'x' * 65536})


@pytest.mark.parametrize('change', [
    {'v': True}, {'v': 2}, {'type': 'fetch'}, {'id': '../a'}, {'id': 'x' * 81},
    {'key': 'synthetic-secret'}, {'model': 'custom'}, {'style': '热点'},
    {'previous': 'x' * 501}, {'previous': '\ud800'}, {'previous': '\u202eabc'},
])
def test_schema_rejects_untrusted_fields_and_types(change):
    with pytest.raises(protocol.ProtocolError):
        protocol.validate_message(request(**change))


@pytest.mark.parametrize('change', [
    {'id': '999'}, {'url': 'https://x.com/test_user/status/123456?x=1'},
    {'url': 'https://twitter.com/test_user/status/123456'},
    {'url': 'https://x.com.evil/test_user/status/123456'},
    {'author': '@someone_else'}, {'author': 'test_user'}, {'text': ''},
    {'text': ' '}, {'text': 'x' * 3001}, {'text': '\x00secret'},
    {'cookie': 'never accepted'}, {'text': '\udfff'},
])
def test_post_identity_and_minimal_fields_are_required(change):
    value = request()
    value['post'].update(change)
    with pytest.raises(protocol.ProtocolError):
        protocol.validate_message(value)


def test_valid_request_controls_and_case_insensitive_author():
    value = request()
    value['post']['author'] = '@TEST_user'
    value['post']['text'] += '\n可以再补充一点。'
    assert protocol.validate_message(value) == value
    for kind in ('ping', 'cancel'):
        value = {'v': 1, 'type': kind, 'id': 'control'}
        assert protocol.validate_message(value) == value
        with pytest.raises(protocol.ProtocolError):
            protocol.validate_message(dict(value, text='extra'))


def test_trusted_origin_and_parent_window_are_exact():
    origin = protocol.TRUSTED_ORIGIN
    assert protocol.valid_caller([origin])
    assert protocol.valid_caller([origin, '--parent-window=0'])
    assert protocol.valid_caller([origin, '--parent-window=123456'])
    for args in ([], [origin.rstrip('/')], [origin + 'evil'],
                 ['https://x.com/'], [origin, '--parent-window=-1'],
                 [origin, '--parent-window=1', '--parent-window=2'],
                 [origin, '--demo'], [origin, '--parent-window=1;cmd']):
        assert not protocol.valid_caller(args)
