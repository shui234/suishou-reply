"""Clipboard orchestration: latest revision wins, zero automatic retries."""
from PySide6.QtCore import QObject, Signal, QTimer, QMimeData
from .clipboard import OWN_MIME, fingerprint, inspect_text, read_clipboard_text


class ReplyController(QObject):
    listening_changed = Signal(bool)

    def __init__(self, *, clipboard, client, window, settings, credentials,
                 store, debounce_ms=350, parent=None):
        super().__init__(parent)
        self.clipboard, self.client, self.window = clipboard, client, window
        self.settings, self.credentials, self.store = settings, credentials, store
        self.listening = False
        self.current_text = ''
        self.current_reply = ''
        self.request_id = 0
        self.busy = False
        self._last_observed = None
        self._seen = set()
        self._own = set()
        self._closed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._dispatch)
        clipboard.dataChanged.connect(self._clipboard_changed)
        client.succeeded.connect(self._succeeded)
        client.failed.connect(self._failed)
        window.copy_requested.connect(self.copy_reply)
        window.regenerate_requested.connect(self.regenerate)
        window.listening_requested.connect(self.set_listening)
        window.style_changed.connect(self.set_style)
        window.set_listening(False)
        window.set_style(settings.style)
        window.set_theme(settings.theme)

    def _invalidate(self):
        self.request_id += 1  # Before abort: abort can emit finished synchronously.
        self._timer.stop()
        self.busy = False
        self.client.cancel()

    def set_listening(self, enabled):
        if self._closed:
            return
        enabled = bool(enabled)
        if enabled:
            try:
                key = self.credentials.get()
            except Exception:
                key = None
            if not key:
                self.set_listening(False)
                self.window.show_error('请先在设置中安全保存 DeepSeek API Key，再开启监听。')
                self.window.set_listening(False)
                self.window.present()
                return
        self._invalidate()
        self.listening = enabled
        self._last_observed = None
        self.current_text = self.current_reply = ''
        self.window.show_source('')
        self.window.set_listening(enabled)
        self.window.show_idle('监听已开启，下一次复制推文时生成回复。' if enabled else '监听已暂停，剪贴板内容不会发送。')
        self.listening_changed.emit(enabled)

    def _clipboard_changed(self):
        if self._closed or not self.listening:
            return
        mime = self.clipboard.mimeData()
        text = read_clipboard_text(mime)
        digest = fingerprint(text) if text is not None else None
        owned = (mime is not None and mime.hasFormat(OWN_MIME)) or (digest is not None and digest in self._own)
        if owned:
            # Immediate copy of the finished reply keeps it visible. Restoring an
            # older own reply via clipboard history must still cancel newer work.
            if self.busy or self._timer.isActive() or digest != fingerprint(self.current_reply):
                self._last_observed = digest
                self._invalidate()
                self.current_text = self.current_reply = ''
                self.window.show_source('')
                self.window.show_idle('已忽略复制的回复，继续等待新的推文。')
            return
        if digest is not None and digest == self._last_observed:
            return
        self._last_observed = digest
        self._invalidate()
        self.current_text = self.current_reply = ''
        if text is None:
            self.window.show_source('')
            self.window.show_idle('已忽略图片或文件，继续等待推文。')
            return
        inspected = inspect_text(text)
        if not inspected.allowed:
            self.window.show_source('')
            self.window.show_idle('已跳过：' + inspected.reason + '。')
            return
        self.current_text = inspected.text
        self.window.show_source(self.current_text)
        if digest in self._seen:
            self.window.show_error('这段内容本次运行已处理。需要再次生成时，请点击「换一条」。')
            self.window.present()
            return
        self.window.show_loading()
        self.window.present()
        self._timer.start()

    def _dispatch(self):
        if self._closed or not self.listening or not self.current_text:
            return
        try:
            key = self.credentials.get()
        except Exception:
            key = None
        if not key:
            self.window.show_error('无法读取 API Key，请打开设置重新保存。')
            return
        self.busy = True
        self._seen.add(fingerprint(self.current_text))
        previous = self.current_reply
        self.current_reply = ''
        self.window.show_loading()
        self.client.generate(self.request_id, self.current_text, key,
                             self.settings.model, self.settings.style, previous=previous)

    def _succeeded(self, request_id, reply, usage):
        if self._closed or not self.listening or request_id != self.request_id:
            return
        self.busy = False
        self.current_reply = reply
        self.window.show_reply(reply, usage)

    def _failed(self, request_id, message):
        if self._closed or not self.listening or request_id != self.request_id:
            return
        self.busy = False
        self.current_reply = ''
        self.window.show_error(message)

    def regenerate(self):
        if not self.listening or not self.current_text or self.busy:
            return
        self._invalidate()
        self._dispatch()

    def copy_reply(self):
        if not self.current_reply or self.busy:
            return
        self._own.add(fingerprint(self.current_reply))
        mime = QMimeData()
        mime.setText(self.current_reply)
        mime.setData(OWN_MIME, b'1')
        self.clipboard.setMimeData(mime)
        self.window.show_copied()

    def set_style(self, style):
        if style not in ('自然', '犀利', '幽默'):
            return
        old_style = self.settings.style
        self.settings.style = style
        try:
            self.store.save(self.settings)
        except Exception:
            self.settings.style = old_style
            self.window.set_style(old_style)
            self.window.show_error('风格设置保存失败，请检查本地配置目录权限。')

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.listening = False
        self._invalidate()
        self.clipboard.dataChanged.disconnect(self._clipboard_changed)
        self.current_text = self.current_reply = ''
        self._seen.clear()
        self._own.clear()
