"""Native Messaging companion, reusing the desktop reply transport and vault.

The browser allowlist plus exact caller origin restrict extension access. They
are not authentication against a malicious process running as the same user.
"""
from __future__ import annotations

import math
import os
import queue
import sys
import threading

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal, qInstallMessageHandler
from PySide6.QtNetwork import QNetworkProxyFactory

from .api import DeepSeekClient, _http_message, _USAGE_FIELDS
from .config import Settings, SettingsStore
from .credentials import CredentialStore
from .edge_protocol import (VERSION, ProtocolError, encode_frame, read_frame,
                            safe_text, valid_caller, valid_request_id, validate_message)


_SAFE_ERRORS = {_http_message(code) for code in (0, 300, 400, 401, 402, 404, 422, 429, 500)}
_SAFE_ERRORS.update({
    '请先在设置中填写有效的 API 密钥。',
    '模型名称格式无效，请在设置中检查。',
    '网络请求未能启动，请检查网络连接后重试。',
    '请求超时，请检查网络后重试。',
    '网络连接失败，请检查网络或代理设置后重试。',
    '回复未生成完整，请重新生成。',
    '服务未能生成可用回复，请重新生成。',
    '服务返回的回复为空或格式异常，请重新生成。',
})


class EdgeBridge(QObject):
    """One owned request, injected dependencies, safe responses only."""

    def __init__(self, client, credentials, load_settings, send, stop, parent=None):
        super().__init__(parent)
        self.client = client
        self.credentials = credentials
        self.load_settings = load_settings
        self.send = send
        self.stop = stop
        self._active = None
        self._sequence = 0
        self._closed = False
        self._used_ids = set()
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self.shutdown)
        client.succeeded.connect(self._succeeded)
        client.failed.connect(self._failed)

    def start_idle_timer(self, milliseconds=60000):
        self._idle.start(max(1, int(milliseconds)))

    def _touch(self):
        if self._idle.isActive():
            self._idle.start()

    def _emit(self, kind, identifier, **fields):
        if not self._closed:
            try:
                self.send(dict(v=1, type=kind, id=identifier, **fields))
            except (OSError, ValueError, RuntimeError):
                self.shutdown()

    def _error(self, identifier, code, message):
        self._emit('error', identifier, code=code, message=message)

    def dispatch(self, message):
        if self._closed:
            return
        try:
            message = validate_message(message)
        except (ProtocolError, TypeError, ValueError):
            identifier = message.get('id') if isinstance(message, dict) else None
            self._error(identifier if valid_request_id(identifier) else '',
                        'invalid_request', str(ProtocolError()))
            return
        self._touch()
        identifier = message['id']
        if message['type'] == 'ping':
            self._emit('ready', identifier, version=VERSION)
            return
        if message['type'] == 'cancel':
            if self._active and self._active[1] == identifier:
                self._active = None
                self.client.cancel()
                self._emit('cancelled', identifier)
            return
        if self._active and self._active[1] == identifier:
            return
        if identifier in self._used_ids:
            self._error(identifier, 'duplicate_request', '该请求已经处理，请使用重新生成按钮。')
            return
        if len(self._used_ids) >= 256:
            self._error(identifier, 'session_limit', '本地会话已达到上限，请重新打开扩展面板。')
            return
        self._used_ids.add(identifier)
        if self._active:
            previous_id = self._active[1]
            self._active = None
            self.client.cancel()
            self._emit('cancelled', previous_id)
        try:
            key = self.credentials.get()
            settings = self.load_settings()
        except Exception:
            self._error(identifier, 'credentials', '无法读取本地配置或密钥，请在随手回桌面版设置中重新保存。')
            return
        if not key:
            self._error(identifier, 'credentials', '请先在随手回桌面版设置中保存 DeepSeek API Key。')
            return
        self._sequence += 1
        self._active = (self._sequence, identifier)
        try:
            self.client.generate(self._sequence, message['post']['text'], key,
                                 settings.model, message['style'], message['previous'])
        except Exception:
            self._failed(self._sequence, '无法启动生成，请稍后重试。')
        finally:
            key = None

    def _take(self, sequence):
        if self._closed or self._active is None or self._active[0] != sequence:
            return None
        identifier = self._active[1]
        self._active = None
        self._touch()
        return identifier

    def _succeeded(self, sequence, text, usage):
        identifier = self._take(sequence)
        if identifier is None:
            return
        if not safe_text(text, 500, nonempty=True):
            self._error(identifier, 'invalid_response', '生成结果为空、过长或含无效字符，请重新生成。')
            return
        clean_usage = {}
        if isinstance(usage, dict):
            clean_usage = {name: value for name in _USAGE_FIELDS
                           if type(value := usage.get(name)) in (int, float)
                           and math.isfinite(value) and 0 <= value <= 2 ** 53}
        self._emit('result', identifier, text=text.strip(), usage=clean_usage)

    def _failed(self, sequence, message):
        identifier = self._take(sequence)
        if identifier is None:
            return
        safe = message if message in _SAFE_ERRORS else '生成失败，请检查本地设置或稍后重试。'
        code = ('balance' if '余额' in safe else 'timeout' if '超时' in safe
                else 'credentials' if '密钥' in safe else 'rate_limit' if '频繁' in safe
                else 'network' if '网络' in safe else 'service')
        self._error(identifier, code, safe)

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self._idle.stop()
        if self._active:
            self._active = None
            self.client.cancel()
        self.stop()


class _SyntheticClient(QObject):
    """Explicit test mode: this class cannot issue a network request."""
    succeeded = Signal(int, str, dict)
    failed = Signal(int, str)

    def __init__(self):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._complete)
        self._request = None

    def generate(self, request_id, text, key, model, style, previous=''):
        self.cancel()
        self._request = request_id
        self._timer.start(5)

    def _complete(self):
        request_id = self._request
        self._request = None
        if request_id is not None:
            self.succeeded.emit(request_id,
                '工具多不代表效率高，先确认它省掉了哪一步重复劳动，再决定要不要加入工作流。',
                {'total_tokens': 0})

    def cancel(self):
        self._timer.stop()
        self._request = None


class _SyntheticCredentials:
    def get(self):
        return 'synthetic-no-network-no-vault'


def _reader(stream, incoming):
    """At most two bounded messages held; never queue an unbounded Qt signal."""
    try:
        while True:
            message = read_frame(stream)
            if message is None:
                incoming.put(('eof', None))
                return
            incoming.put(('message', message))
    except Exception:
        incoming.put(('invalid', None))


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    synthetic = bool(arguments and arguments[0] == '--synthetic')
    if synthetic:
        arguments.pop(0)
    if not valid_caller(arguments):
        return 2
    try:
        # Edge native pipes require binary mode on Windows. FileIO/os.read avoids
        # a daemon thread retaining a BufferedReader lock at interpreter shutdown.
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        input_stream = os.fdopen(os.dup(sys.stdin.fileno()), 'rb', buffering=0)
        output_stream = os.fdopen(os.dup(sys.stdout.fileno()), 'wb', buffering=0)
        qInstallMessageHandler(lambda *_arguments: None)
        app = QCoreApplication(sys.argv[:1])
        app.setApplicationName('SuishouReplyBridge')
        app.setApplicationVersion(VERSION)
        if synthetic:
            client, credentials, load_settings = _SyntheticClient(), _SyntheticCredentials(), Settings
        else:
            QNetworkProxyFactory.setUseSystemConfiguration(True)
            client, credentials = DeepSeekClient(), CredentialStore()
            load_settings = SettingsStore().load

        def send(message):
            frame = encode_frame(message)
            cursor = 0
            while cursor < len(frame):
                written = output_stream.write(frame[cursor:])
                if not written:
                    raise OSError('closed pipe')
                cursor += written

        bridge = EdgeBridge(client, credentials, load_settings, send, app.quit)
        bridge.start_idle_timer()
        incoming = queue.Queue(maxsize=1)
        reader = threading.Thread(target=_reader, args=(input_stream, incoming),
                                  name='native-input', daemon=True)
        poll = QTimer()

        def receive():
            try:
                kind, message = incoming.get_nowait()
            except queue.Empty:
                return
            if kind == 'message':
                bridge.dispatch(message)
            else:
                if kind == 'invalid':
                    bridge._error('', 'invalid_request', str(ProtocolError()))
                poll.stop()
                bridge.shutdown()

        poll.timeout.connect(receive)
        poll.start(5)
        reader.start()
        result = app.exec()
        poll.stop()
        bridge.shutdown()
        output_stream.close()
        # stdin may still be waiting for a browser frame after idle timeout.
        # Do not join that daemon or close its descriptor from another thread.
        return result
    except Exception:
        # stdout is reserved for frames; exceptions never print credential data.
        return 1
