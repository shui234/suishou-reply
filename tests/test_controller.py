from types import SimpleNamespace
import pytest
from PySide6.QtCore import QObject, Signal, QMimeData
from PySide6.QtTest import QTest
from suishou.controller import ReplyController

TWEET_A = 'AI工具越来越多，真正省下时间的反而是少用几个。'
TWEET_B = '很多产品都想替用户做决定，但我更希望它先把选择讲清楚。'
REPLY = '工具再多也得先想清楚要做什么，不然只是把拖延换成了研究工具。'


class FakeClient(QObject):
    succeeded = Signal(int, str, dict)
    failed = Signal(int, str)
    def __init__(self):
        super().__init__()
        self.calls = []
        self.cancellations = 0
    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
    def cancel(self):
        self.cancellations += 1


class FakeWindow(QObject):
    copy_requested = Signal()
    regenerate_requested = Signal()
    listening_requested = Signal(bool)
    style_changed = Signal(str)
    def __init__(self):
        super().__init__()
        self.reply = ''
        self.error = ''
        self.source = ''
        self.copied = False
    def set_listening(self, value): self.listening = value
    def set_style(self, value): pass
    def set_theme(self, value): pass
    def show_source(self, text): self.source = text
    def show_loading(self): self.reply = ''
    def show_reply(self, text, usage): self.reply = text
    def show_error(self, message): self.error = message
    def show_idle(self, message=''): self.reply = ''
    def show_copied(self): self.copied = True
    def present(self): pass


def make_controller(qapp):
    client, window = FakeClient(), FakeWindow()
    controller = ReplyController(
        clipboard=qapp.clipboard(), client=client, window=window,
        settings=SimpleNamespace(model='deepseek-flash', style='自然', theme='dark'),
        credentials=SimpleNamespace(get=lambda: 'synthetic-test-key'),
        store=SimpleNamespace(save=lambda settings: None), debounce_ms=15,
    )
    return controller, client, window


def test_default_paused_and_enable_does_not_read_existing(qapp):
    ctl, api, win = make_controller(qapp)
    qapp.clipboard().setText(TWEET_A)
    QTest.qWait(30)
    assert not api.calls and not ctl.listening
    ctl.set_listening(True)
    QTest.qWait(30)
    assert not api.calls
    qapp.clipboard().setText(TWEET_B)
    QTest.qWait(40)
    assert len(api.calls) == 1
    ctl.shutdown()


def test_copy_flow_preserves_original_and_prevents_loop(qapp):
    ctl, api, win = make_controller(qapp)
    ctl.set_listening(True)
    qapp.clipboard().setText(TWEET_A)
    QTest.qWait(40)
    request_id = api.calls[-1][0][0]
    api.succeeded.emit(request_id, REPLY, {'total_tokens': 90})
    assert win.reply == REPLY
    assert qapp.clipboard().text() == TWEET_A
    win.copy_requested.emit()
    QTest.qWait(40)
    assert qapp.clipboard().text() == REPLY
    assert win.copied and len(api.calls) == 1
    # Windows clipboard managers can strip custom MIME markers.
    qapp.clipboard().setText(REPLY)
    QTest.qWait(40)
    assert len(api.calls) == 1
    ctl.shutdown()


def test_latest_copy_debounced_and_stale_result_ignored(qapp):
    ctl, api, win = make_controller(qapp)
    ctl.set_listening(True)
    qapp.clipboard().setText(TWEET_A)
    qapp.clipboard().setText(TWEET_B)
    QTest.qWait(40)
    assert len(api.calls) == 1 and api.calls[0][0][1] == TWEET_B
    old_id = api.calls[-1][0][0]
    qapp.clipboard().setText(TWEET_A)
    QTest.qWait(40)
    new_id = api.calls[-1][0][0]
    api.succeeded.emit(new_id, '最新的结果', {})
    api.succeeded.emit(old_id, '过期的结果', {})
    api.failed.emit(old_id, '过期的错误')
    assert win.reply == '最新的结果' and not win.error
    ctl.shutdown()


def test_duplicate_session_text_and_explicit_regenerate(qapp):
    ctl, api, win = make_controller(qapp)
    ctl.set_listening(True)
    for text in (TWEET_A, TWEET_B, TWEET_A):
        qapp.clipboard().setText(text)
        QTest.qWait(40)
    assert len(api.calls) == 2
    win.regenerate_requested.emit()
    QTest.qWait(10)
    assert len(api.calls) == 3
    ctl.shutdown()


def test_pause_and_invalid_copy_cancel_inflight(qapp):
    ctl, api, win = make_controller(qapp)
    ctl.set_listening(True)
    qapp.clipboard().setText(TWEET_A)
    QTest.qWait(40)
    old_id = api.calls[-1][0][0]
    qapp.clipboard().setText('密码：Abcd123456! 请不要向任何人泄露')
    api.succeeded.emit(old_id, REPLY, {})
    QTest.qWait(40)
    assert not win.reply and len(api.calls) == 1
    qapp.clipboard().setText(TWEET_B)
    ctl.set_listening(False)
    QTest.qWait(40)
    assert len(api.calls) == 1
    ctl.shutdown()


def test_api_error_no_retry_and_manual_retry_available(qapp):
    ctl, api, win = make_controller(qapp)
    ctl.set_listening(True)
    qapp.clipboard().setText(TWEET_A)
    QTest.qWait(40)
    api.failed.emit(api.calls[-1][0][0], '余额不足，请前往 DeepSeek 检查余额。')
    QTest.qWait(100)
    assert '余额不足' in win.error and len(api.calls) == 1
    win.regenerate_requested.emit()
    assert len(api.calls) == 2
    ctl.shutdown()


def test_missing_key_reports_paused_to_tray(qapp):
    ctl, api, win = make_controller(qapp)
    states = []
    ctl.listening_changed.connect(states.append)
    ctl.credentials.get = lambda: None
    ctl.set_listening(True)
    assert not ctl.listening and not win.listening
    assert states == [False]
    ctl.shutdown()


def test_dedup_does_not_expire_during_session(qapp):
    ctl, api, win = make_controller(qapp)
    ctl._timer.setInterval(0)
    ctl.set_listening(True)
    for number in range(260):
        qapp.clipboard().setText(f'这是第{number}条模拟推文，同一轮运行不应对重复内容自动收费。')
        qapp.processEvents()
    assert len(api.calls) == 260
    qapp.clipboard().setText('这是第0条模拟推文，同一轮运行不应对重复内容自动收费。')
    qapp.processEvents()
    assert len(api.calls) == 260
    ctl.shutdown()


@pytest.mark.parametrize('keep_marker', [False, True])
def test_restoring_own_reply_cancels_intervening_request(qapp, keep_marker):
    ctl, api, win = make_controller(qapp)
    ctl.set_listening(True)
    qapp.clipboard().setText(TWEET_A)
    QTest.qWait(40)
    api.succeeded.emit(api.calls[-1][0][0], REPLY, {})
    ctl.copy_reply()
    qapp.clipboard().setText(TWEET_B)
    QTest.qWait(40)
    old_id = api.calls[-1][0][0]
    restored = QMimeData()
    restored.setText(REPLY)
    if keep_marker:
        restored.setData('application/x-suishou-reply', b'1')
    qapp.clipboard().setMimeData(restored)
    api.succeeded.emit(old_id, '这是旧任务返回的结果，不该继续显示。', {})
    assert not win.reply
    assert ctl.request_id != old_id
    assert len(api.calls) == 2
    ctl.shutdown()
