import io
import os
from pathlib import Path
import subprocess
import sys
import time

from PySide6.QtCore import QObject, Signal

from suishou import edge_protocol as protocol
from suishou.edge_bridge import EdgeBridge
from suishou.config import Settings
from suishou.credentials import CredentialError


def request(identifier='one', **changes):
    value = {'v': 1, 'type': 'generate', 'id': identifier,
             'post': {'id': '123', 'url': 'https://x.com/test_user/status/123',
                      'author': '@test_user', 'text': '工具好不好用，还是得看它解决了什么问题。'},
             'style': '自然', 'previous': ''}
    value.update(changes)
    return value


class Client(QObject):
    succeeded = Signal(int, str, dict)
    failed = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.calls = []
        self.cancels = 0

    def generate(self, *args):
        self.calls.append(args)

    def cancel(self):
        self.cancels += 1


class Credentials:
    def __init__(self):
        self.reads = 0
        self.value = 'synthetic-test-key'

    def get(self):
        self.reads += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def setup_bridge(qapp):
    client, credentials, messages, stopped = Client(), Credentials(), [], []
    bridge = EdgeBridge(client, credentials, lambda: Settings(model='test-model'),
                        messages.append, lambda: stopped.append(True))
    return bridge, client, credentials, messages, stopped


def test_ping_no_credentials_and_generate_reuses_original_client(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.dispatch({'v': 1, 'type': 'ping', 'id': 'ping'})
    assert messages == [{'v': 1, 'type': 'ready', 'id': 'ping', 'version': '1.2.0'}]
    assert credentials.reads == 0
    bridge.dispatch(request())
    assert credentials.reads == 1
    assert client.calls[0][1:] == (request()['post']['text'], 'synthetic-test-key',
                                  'test-model', '自然', '')
    client.succeeded.emit(client.calls[0][0], '多一个工具未必少一道工序，能省下重复劳动才算有用。',
                          {'total_tokens': 22, 'arbitrary': 'secret'})
    assert messages[-1]['type'] == 'result'
    assert messages[-1]['usage'] == {'total_tokens': 22}
    assert 'synthetic-test-key' not in str(messages)


def test_new_request_cancels_old_and_stale_signals_are_ignored(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.dispatch(request('one'))
    first = client.calls[-1][0]
    bridge.dispatch(request('two'))
    second = client.calls[-1][0]
    assert first != second and client.cancels == 1
    count = len(messages)
    client.succeeded.emit(first, '旧结果', {})
    client.failed.emit(first, '旧错误')
    assert len(messages) == count
    client.succeeded.emit(second, '当前正确结果', {})
    assert messages[-1]['id'] == 'two'


def test_duplicate_active_id_does_not_restart_paid_request(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.dispatch(request())
    bridge.dispatch(request())
    assert len(client.calls) == 1 and credentials.reads == 1


def test_cancel_only_matching_owner_and_shutdown_stops_work(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.dispatch(request())
    active = client.calls[-1][0]
    bridge.dispatch({'v': 1, 'type': 'cancel', 'id': 'wrong'})
    assert client.cancels == 0
    bridge.dispatch({'v': 1, 'type': 'cancel', 'id': 'one'})
    assert client.cancels == 1 and messages[-1]['type'] == 'cancelled'
    client.succeeded.emit(active, '不得显示', {})
    assert messages[-1]['type'] == 'cancelled'
    bridge.dispatch(request('two'))
    bridge.shutdown()
    bridge.shutdown()
    assert client.cancels == 2 and stopped == [True]
    bridge.dispatch(request('three'))
    assert len(client.calls) == 2


def test_invalid_requests_and_credentials_fail_before_paid_call(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.dispatch(request(key='forbidden'))
    assert not client.calls and credentials.reads == 0
    assert messages[-1]['code'] == 'invalid_request'
    credentials.value = None
    bridge.dispatch(request('missing'))
    assert not client.calls and messages[-1]['code'] == 'credentials'
    credentials.value = CredentialError('should-not-be-returned')
    bridge.dispatch(request('failed'))
    assert not client.calls and 'should-not-be-returned' not in str(messages)


def test_failures_and_invalid_success_never_leak_raw_data_or_retry(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    for index, reason, code in [(1, 'DeepSeek 账户余额不足，请充值后重试。', 'balance'),
                                 (2, '请求超时，请检查网络后重试。', 'timeout'),
                                 (3, 'raw secret response', 'service')]:
        bridge.dispatch(request(f'item{index}'))
        client.failed.emit(client.calls[-1][0], reason)
        assert messages[-1]['code'] == code
    assert len(client.calls) == 3 and 'raw secret' not in str(messages)
    for index, text in enumerate(('', '\ud800', 'x' * 501, 'wrong\u202evalue')):
        bridge.dispatch(request(f'invalid-{index}'))
        client.succeeded.emit(client.calls[-1][0], text, {})
        assert messages[-1]['code'] == 'invalid_response'


def test_replayed_completed_request_never_reads_key_or_generates_again(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.dispatch(request())
    client.succeeded.emit(client.calls[-1][0], '合成回复内容', {})
    bridge.dispatch(request())
    assert len(client.calls) == 1 and credentials.reads == 1
    assert messages[-1]['code'] == 'duplicate_request'


def test_idle_shutdown_is_bounded(qapp):
    bridge, client, credentials, messages, stopped = setup_bridge(qapp)
    bridge.start_idle_timer(15)
    deadline = time.monotonic() + 1
    while not stopped and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(.005)
    assert stopped == [True]


def test_native_cli_refuses_bad_caller_and_synthetic_ping_roundtrips(tmp_path):
    root = Path(__file__).resolve().parents[1]
    executable = [sys.executable, str(root / 'edge_host.py')]
    bad = subprocess.run(executable + ['https://x.com/'], input=b'', capture_output=True, timeout=10)
    assert bad.returncode != 0 and bad.stdout == b'' and bad.stderr == b''
    ping = {'v': 1, 'type': 'ping', 'id': 'subprocess'}
    good = subprocess.run(executable + ['--synthetic', protocol.TRUSTED_ORIGIN],
                          input=protocol.encode_frame(ping), capture_output=True, timeout=10)
    assert good.returncode == 0, good.stderr.decode(errors='replace')
    assert good.stderr == b''
    assert protocol.read_frame(io.BytesIO(good.stdout))['type'] == 'ready'


def test_synthetic_subprocess_generate_and_eof_exit_without_network():
    root = Path(__file__).resolve().parents[1]
    child = subprocess.Popen([sys.executable, str(root / 'edge_host.py'), '--synthetic',
                              protocol.TRUSTED_ORIGIN], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        child.stdin.write(protocol.encode_frame(request()))
        child.stdin.flush()
        reply = protocol.read_frame(child.stdout)
        assert reply['type'] == 'result' and reply['id'] == 'one'
        assert reply['usage'] == {'total_tokens': 0}
        child.stdin.close()
        assert child.wait(timeout=10) == 0
        assert child.stderr.read() == b''
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
