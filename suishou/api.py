"""Asynchronous, single-flight DeepSeek client. No content or key logging."""

import json

from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .config import valid_model
from .prompts import build_messages


ENDPOINT = 'https://api.deepseek.com/chat/completions'
_USAGE_FIELDS = ('prompt_tokens', 'completion_tokens', 'total_tokens',
                 'prompt_cache_hit_tokens', 'prompt_cache_miss_tokens')


def _http_message(status: int) -> str:
    if status == 401:
        return 'API 密钥无效或已失效，请在设置中更新。'
    if status == 402:
        return 'DeepSeek 账户余额不足，请充值后重试。'
    if status == 429:
        return '请求过于频繁，请稍等片刻再试。'
    if status in (400, 404, 422):
        return '请求参数或模型不可用，请检查设置中的模型名称。'
    if 300 <= status < 400:
        return '服务返回了重定向，已停止请求，请稍后重试。'
    if status >= 500:
        return 'DeepSeek 服务暂时不可用，请稍后重试。'
    return '请求未能完成，请检查账户权限后重试。'


class DeepSeekClient(QObject):
    succeeded = Signal(int, str, dict)
    failed = Signal(int, str)

    def __init__(self, parent: QObject | None = None, *, manager=None, timeout_ms: int = 30000):
        super().__init__(parent)
        self._manager = manager if manager is not None else QNetworkAccessManager(self)
        self._timeout_ms = max(1, int(timeout_ms))
        self._active = None

    def generate(self, request_id: int, text: str, key: str, model: str,
                 style: str, previous: str = '') -> None:
        if not text.strip():
            self.cancel()
            self.failed.emit(request_id, '请先粘贴一条推文。')
            return
        self._send(request_id, key, model, build_messages(text, style, previous), 256)

    def generate_original(self, request_id: int, messages: list, key: str, model: str) -> None:
        """Use the same authenticated, cancelable transport for structured posts."""
        if not messages or not isinstance(messages, list):
            self.cancel()
            self.failed.emit(request_id, '缺少原创内容素材，请重新选择话题。')
            return
        self._send(request_id, key, model, messages, 512, json_output=True)

    def _send(self, request_id, key, model, messages, max_tokens, *, json_output=False):
        self.cancel()
        if not key.strip() or any(c in key for c in '\r\n\x00') or not key.isascii():
            self.failed.emit(request_id, '请先在设置中填写有效的 API 密钥。')
            return
        if not valid_model(model):
            self.failed.emit(request_id, '模型名称格式无效，请在设置中检查。')
            return
        payload = {'model': model, 'messages': messages,
                   'thinking': {'type': 'disabled'}, 'stream': False, 'max_tokens': max_tokens}
        if json_output:
            payload['response_format'] = {'type': 'json_object'}
        request = QNetworkRequest(QUrl(ENDPOINT))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json')
        request.setRawHeader(QByteArray(b'Authorization'), QByteArray(b'Bearer ' + key.strip().encode('ascii')))
        request.setRawHeader(QByteArray(b'Accept'), QByteArray(b'application/json'))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        try:
            reply = self._manager.post(request, QByteArray(json.dumps(payload, ensure_ascii=False).encode('utf-8')))
        except (RuntimeError, OSError):
            self.failed.emit(request_id, '网络请求未能启动，请检查网络连接后重试。')
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        token = object()
        self._active = (token, request_id, reply, timer)
        reply.finished.connect(lambda: self._finished(token))
        timer.timeout.connect(lambda: self._timed_out(token))
        timer.start(self._timeout_ms)

    def _take(self, token=None):
        active = self._active
        if active is None or (token is not None and active[0] is not token):
            return None
        self._active = None
        active[3].stop()
        active[3].deleteLater()
        return active

    def cancel(self) -> None:
        active = self._take()
        if active is not None:
            active[2].abort()
            active[2].deleteLater()

    def _timed_out(self, token) -> None:
        active = self._take(token)
        if active is None:
            return
        active[2].abort()
        active[2].deleteLater()
        self.failed.emit(active[1], '请求超时，请检查网络后重试。')

    def _finished(self, token) -> None:
        active = self._take(token)
        if active is None:
            return
        _, request_id, reply, _ = active
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if isinstance(status, int) and not 200 <= status < 300:
                self.failed.emit(request_id, _http_message(status))
                return
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.failed.emit(request_id, '网络连接失败，请检查网络或代理设置后重试。')
                return
            try:
                data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                choice = data['choices'][0]
                if choice.get('finish_reason') == 'length':
                    self.failed.emit(request_id, '回复未生成完整，请重新生成。')
                    return
                if choice.get('finish_reason') != 'stop':
                    self.failed.emit(request_id, '服务未能生成可用回复，请重新生成。')
                    return
                content = choice['message']['content']
                if not isinstance(content, str) or not content.strip():
                    raise ValueError('Empty content')
                raw_usage = data.get('usage', {})
                usage = {}
                if isinstance(raw_usage, dict):
                    usage = {field: raw_usage[field] for field in _USAGE_FIELDS
                             if type(raw_usage.get(field)) in (int, float)
                             and 0 <= raw_usage[field] <= 2 ** 53}
            except (ValueError, TypeError, KeyError, IndexError, AttributeError, UnicodeError):
                self.failed.emit(request_id, '服务返回的回复为空或格式异常，请重新生成。')
                return
            self.succeeded.emit(request_id, content.strip(), usage)
        finally:
            reply.deleteLater()
