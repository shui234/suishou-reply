"""Native UI + real Qt HTTP/clipboard integration against a local synthetic server.

Only imported by the explicit --self-test flag. No production URL override exists.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PySide6.QtCore import QEventLoop, QMimeData, QTimer, Qt, QUrl, QObject, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QSslSocket
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtTest import QTest
from .api import DeepSeekClient
from .config import Settings
from .controller import ReplyController
from .runtime import MemorySettingsStore, DemoCredentials
from .ui import ReplyWindow
from .original_controller import OriginalController
from .history import MemoryHistoryStore
from .original import STYLES, TOPICS, weighted_length

TWEET = 'AI工具越来越多，真正省下时间的反而是少用几个。'
TWEET_B = '很多产品都想替用户做决定，但我更希望它先把选择讲清楚。'
REPLY = '工具再多也得先想清楚要做什么，不然只是把拖延换成了研究工具。'
POST = '让 AI 写代码最省心的时刻，不是它一口气生成了多少行，而是你能看懂它为什么这么写。省下敲键盘的时间，可以留一点给检查边界。'


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
    status = {'code': 200, 'malformed': False, 'post': POST}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            content = REPLY
            if payload.get('response_format'):
                content = '{broken' if status['malformed'] else json.dumps({
                    'body': status['post'], 'topic': 'AI编程', 'style': '犀利', 'source': None}, ensure_ascii=False)
            body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': content}}],
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
    original_api = DeepSeekClient(manager=LocalManager())
    class FixtureNews(QObject):
        succeeded = Signal(int, list)
        failed = Signal(int, str)
        source = None
        def fetch(self, request_id, topic='随机'):
            if self.source:
                self.succeeded.emit(request_id, [self.source])
            else:
                self.failed.emit(request_id, '离线演示：暂无可核实的新素材。')
        def cancel(self):
            pass
    original_news = FixtureNews()
    post_controller = OriginalController(client=original_api, news=original_news,
        page=window.original_page, history=MemoryHistoryStore(), settings=Settings(),
        credentials=DemoCredentials(), copy_text=controller.copy_generated_text)

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
        status['code'] = 200
        window.set_mode('original')
        window.present()
        page = window.original_page
        check('original_random_defaults', page.style_combo.currentData() == '随机' and page.topic_combo.currentData() == '随机')
        page.generate_button.click()
        for _ in range(15):
            post_controller.generate()
        check('original_complete_http_flow', _until(lambda: post_controller.current is not None))
        check('original_single_request', len(calls) == count + 1)
        check('original_json_mode', calls[-1]['response_format'] == {'type': 'json_object'} and calls[-1]['max_tokens'] == 512)
        check('original_visible_and_length', page.post_label.text() == POST and weighted_length(POST) <= 280)
        check('original_clipboard_unchanged', clipboard.text() == TWEET)
        if screenshot:
            check('original_screenshot_saved', window.grab().save(str(screenshot.with_name('preview-original.png'))))
        controller.set_listening(True)
        before = len(calls)
        page.copy_button.click()
        _wait(150)
        check('original_copy_no_reply_loop', clipboard.text() == POST and len(calls) == before)
        clipboard.setText(POST)
        _wait(150)
        check('original_history_restore_no_loop', len(calls) == before)
        controller.set_listening(False)
        page.favorite_button.click()
        page.published_button.click()
        check('original_local_flags', post_controller.current['favorite'] and post_controller.current['published'])
        page.history_button.click()
        check('original_history_visible', page.history_dialog.isVisible() and page.history_dialog.records_list.count() == 1)
        page.history_dialog.close()
        page.generate_button.click()
        check('original_duplicate_rejected', _until(lambda: not post_controller.busy) and '相似' in page.post_label.text())
        check('original_no_duplicate_saved', len(post_controller.history.records) == 1)
        # Verify every combination traverses the real JSON HTTP path; history is
        # explicitly isolated/cleared so a fixed synthetic body is appropriate.
        combinations = True
        for style in STYLES[:-1]:
            for topic in TOPICS:
                post_controller.clear_history()
                post_controller.generate(style, topic)
                combinations = combinations and _until(lambda: post_controller.current is not None)
        check('original_all_nonnews_filter_combinations', combinations)
        post_controller.clear_history()
        post_controller.generate('热点', '随机')
        check('original_unavailable_news_stops_model', not post_controller.busy and post_controller.current is None
              and '离线演示' in page.post_label.text())
        # Actual official RSS metadata captured 2026-11-09; the comment is a
        # synthetic fixture, not live DeepSeek output. No network in this test.
        original_news.source = {
            'title': 'Speeding up planning decisions with AI',
            'published_at': '2026-10-30T14:18:30+00:00',
            'url': 'https://deepmind.google/blog/speeding-up-planning-decisions-with-ai/',
            'summary': 'Google DeepMind and UK government work together to reduce planning assessment times',
            'provider': 'Google DeepMind', 'topic': '行业观察'}
        status['post'] = 'DeepMind 与英国政府合作，用 AI 辅助规划评估。审批流程里，提速值得关注，但更该看依据是否可追溯、责任是否清楚；效率的好处，不能靠让错误更难被发现来换。'
        page.style_combo.setCurrentIndex(page.style_combo.findData('热点'))
        page.topic_combo.setCurrentIndex(page.topic_combo.findData('行业观察'))
        page.generate_button.click()
        check('original_hot_source_visible', _until(lambda: post_controller.current is not None)
              and page.source_title_label.text() == original_news.source['title'])
        page.copy_source_button.click()
        check('original_copy_with_source', clipboard.text().endswith(original_news.source['url'])
              and weighted_length(clipboard.text()) <= 280)
        if screenshot:
            check('hot_screenshot_saved', window.grab().save(str(screenshot.with_name('preview-hot.png'))))
        post_controller.clear_history()
        status['malformed'] = True
        post_controller.generate('犀利', 'AI编程')
        check('original_malformed_json_feedback', _until(lambda: not post_controller.busy) and '格式异常' in page.post_label.text())
        status['malformed'] = False
        post_controller.generate('犀利', 'AI编程')
        post_controller.cancel()
        _wait(100)
        check('original_cancel_ignores_late_result', not post_controller.busy and post_controller.current is None)
        post_controller.clear_history()
        check('original_history_cleared', not post_controller.history.records)
        window.close()
        check('close_only_hides', not window.isVisible())
        check('tls_backend_available', QSslSocket.supportsSsl())
    except Exception as error:
        # Record only predefined check names / exception type; never clipboard or keys.
        checks['failure'] = str(error) if isinstance(error, AssertionError) else type(error).__name__
    finally:
        post_controller.shutdown()
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
