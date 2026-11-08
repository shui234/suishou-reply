"""Native UI + real Qt HTTP/clipboard integration against a local synthetic server.

Only imported by the explicit --self-test flag. No production URL override exists.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PySide6.QtCore import QEventLoop, QMimeData, QTimer, Qt, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QSslSocket
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtTest import QTest
from .api import DeepSeekClient
from .config import Settings
from .controller import ReplyController
from .runtime import MemorySettingsStore, DemoCredentials
from .ui import ReplyWindow

TWEET = 'AI工具越来越多，真正省下时间的反而是少用几个。'
TWEET_B = '很多产品都想替用户做决定，但我更希望它先把选择讲清楚。'
REPLY = '工具再多也得先想清楚要做什么，不然只是把拖延换成了研究工具。'


def _wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _until(predicate, timeout_ms=2500):
    for _ in range(timeout_ms // 20):
        if predicate():
            return True
        _wait(20)
    return bool(predicate())


def run_self_test(app, screenshot: Path | None = None):
    checks = {}
    clipboard = app.clipboard()
    original = QMimeData()
    existing = clipboard.mimeData()
    if existing:
        for fmt in existing.formats():
            original.setData(fmt, existing.data(fmt))
    calls = []
    status = {'code': 200}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': REPLY}}],
                               'usage': {'prompt_tokens': 128, 'completion_tokens': 37, 'total_tokens': 165}}).encode()
            self.send_response(status['code'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class LocalManager(QNetworkAccessManager):
        def createRequest(self, operation, request, outgoingData=None):
            local = QNetworkRequest(request)
            local.setUrl(QUrl(f'http://127.0.0.1:{server.server_port}/chat/completions'))
            return super().createRequest(operation, local, outgoingData)

    manager = LocalManager()
    api = DeepSeekClient(manager=manager)
    window = ReplyWindow()
    window.set_demo_mode(True)
    source = QPlainTextEdit()
    source.setWindowTitle('随手回 · 模拟推文测试源')
    source.resize(600, 180)
    source.move(60, 80)
    controller = ReplyController(clipboard=clipboard, client=api, window=window,
        settings=Settings(), credentials=DemoCredentials(), store=MemorySettingsStore(), debounce_ms=70)

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)

    try:
        source.setPlainText(TWEET)
        source.show()
        source.activateWindow()
        source.setFocus()
        _wait(120)
        check('default_paused', not controller.listening)
        clipboard.setText(TWEET_B)
        _wait(120)
        check('paused_sends_nothing', not calls)
        controller.set_listening(True)
        _wait(120)
        check('enable_does_not_upload_existing_clipboard', not calls)
        QTest.keyClick(source, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(source, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        focus_before = app.focusWindow()
        check('copy_request_reply', _until(lambda: bool(controller.current_reply)))
        check('native_popup_does_not_steal_focus', app.focusWindow() == focus_before and focus_before is not None)
        check('original_clipboard_preserved', clipboard.text() == TWEET)
        check('real_http_payload', calls[0]['model'] == 'deepseek-flash' and calls[0]['thinking'] == {'type': 'disabled'})
        check('visible_reply', window.reply_label.text() == REPLY and window.isVisible())
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            check('screenshot_saved', window.grab().save(str(screenshot)))
        window.copy_button.click()
        _wait(150)
        check('reply_copy_and_no_loop', clipboard.text() == REPLY and len(calls) == 1)
        window.regenerate_button.click()
        check('manual_regenerate', _until(lambda: len(calls) == 2 and bool(controller.current_reply)))
        clipboard.setText(TWEET_B)
        clipboard.setText('这是最新的一条模拟推文，连续复制时只应该生成这一条的评论。')
        check('latest_copy_only', _until(lambda: len(calls) == 3 and bool(controller.current_reply)))
        check('latest_text_in_request', '最新的一条模拟推文' in calls[-1]['messages'][-1]['content'])
        status['code'] = 402
        clipboard.setText('这是一条模拟余额不足时的推文，用来检查错误提示是否友好。')
        check('api_error_displayed', _until(lambda: '余额不足' in window.status_label.text() or '余额不足' in window.reply_label.text()))
        count = len(calls)
        _wait(200)
        check('no_automatic_retry', len(calls) == count)
        clipboard.setText('密码：SyntheticPassword123! 这是不能发出去的测试凭据。')
        _wait(150)
        check('sensitive_clipboard_not_sent', len(calls) == count)
        controller.set_listening(False)
        clipboard.setText(TWEET)
        _wait(150)
        check('pause_stops_requests', len(calls) == count)
        window.close()
        check('close_only_hides', not window.isVisible())
        check('tls_backend_available', QSslSocket.supportsSsl())
    except Exception as error:
        # Record only predefined check names / exception type; never clipboard or keys.
        checks['failure'] = str(error) if isinstance(error, AssertionError) else type(error).__name__
    finally:
        controller.shutdown()
        window.hide()
        source.close()
        clipboard.setMimeData(original)
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
    return {'passed': all(value is True for value in checks.values()),
            'mode': 'native-qt-local-http-synthetic-data', 'checks': checks,
            'real_deepseek_account_tested': False}
