import json
import pytest

from PySide6.QtCore import QObject, Signal
from suishou.config import Settings
from suishou.original_controller import OriginalController
from suishou.history import HistoryStore


BODY = '让 AI 写代码最省心的时刻，不是它一口气生成了多少行，而是你能看懂它为什么这么写。省下敲键盘的时间，可以留一点给检查边界。'


class Client(QObject):
    succeeded = Signal(int, str, dict)
    failed = Signal(int, str)
    def __init__(self):
        super().__init__()
        self.calls = []
        self.cancels = 0
    def generate_original(self, *args):
        self.calls.append(args)
    def cancel(self):
        self.cancels += 1


class News(QObject):
    succeeded = Signal(int, list)
    failed = Signal(int, str)
    def __init__(self):
        super().__init__()
        self.calls = []
    def fetch(self, *args):
        self.calls.append(args)
    def cancel(self):
        pass


class Page(QObject):
    generate_requested = Signal(str, str)
    cancel_requested = Signal()
    copy_requested = Signal(bool)
    favorite_requested = Signal()
    published_requested = Signal()
    history_requested = Signal()
    clear_history_requested = Signal()
    record_requested = Signal(str)
    def __init__(self):
        super().__init__()
        self.post = None
        self.error = ''
    def set_busy(self, busy):
        self.busy = busy
    def show_loading(self, message=''):
        self.busy = True
    def show_post(self, post, usage):
        self.post, self.usage, self.busy = post, usage, False
    def show_error(self, message):
        self.error, self.busy = message, False
    def show_idle(self, message=''):
        self.post, self.busy = None, False
    def show_copied(self):
        self.copied = True
    def show_history(self, records):
        self.history = records


class Credentials:
    def get(self):
        return 'synthetic-key'


def make(qapp, tmp_path):
    client, news, page = Client(), News(), Page()
    copied = []
    controller = OriginalController(client=client, news=news, page=page,
        history=HistoryStore(tmp_path / 'original.json'), credentials=Credentials(),
        settings=Settings(), copy_text=copied.append)
    return controller, client, news, page, copied


def success(controller, client, body=BODY):
    seed = controller.seed
    client.succeeded.emit(controller.request_id, json.dumps({
        'body': body, 'topic': seed['topic'], 'style': seed['style'], 'source': None}, ensure_ascii=False),
        {'total_tokens': 160})


def test_generate_single_flight_persist_flags_and_copy(qapp, tmp_path):
    ctl, client, news, page, copied = make(qapp, tmp_path)
    for _ in range(20):
        ctl.generate('犀利', 'AI编程')
    assert len(client.calls) == 1 and not news.calls
    success(ctl, client)
    assert page.post['body'] == BODY and len(ctl.history.records) == 1
    ctl.copy(False)
    assert copied == [BODY]
    ctl.toggle_favorite()
    ctl.toggle_published()
    saved = HistoryStore(tmp_path / 'original.json').records[0]
    assert saved['favorite'] and saved['published']
    assert page.post['id'] == saved['id']


def test_cancel_stale_error_duplicate_and_no_auto_retry(qapp, tmp_path):
    ctl, client, news, page, _ = make(qapp, tmp_path)
    ctl.generate('幽默', 'AI工具')
    old = ctl.request_id
    ctl.cancel()
    client.failed.emit(old, '旧错误')
    assert not page.error and not ctl.busy
    ctl.generate('反常识', '行业观察')
    success(ctl, client)
    ctl.generate('犀利', 'AI编程')
    success(ctl, client)
    assert '相似' in page.error or '重复' in page.error
    assert len(client.calls) == 3 and len(ctl.history.records) == 1


def test_news_failure_never_invokes_model(qapp, tmp_path):
    ctl, client, news, page, _ = make(qapp, tmp_path)
    ctl.generate('热点', '随机')
    assert news.calls and not client.calls
    news.failed.emit(ctl.request_id, '暂无可靠新素材')
    assert '可靠' in page.error and not ctl.busy and not client.calls


def test_news_source_is_retained_and_copy_has_real_link(qapp, tmp_path):
    ctl, client, news, page, copied = make(qapp, tmp_path)
    ctl.generate('热点', 'AI Agent')
    source = {'title': 'Agent SDK release', 'published_at': '2026-11-09T01:00:00+00:00',
              'url': 'https://github.com/openai/openai-agents-python/releases/tag/v1',
              'provider': 'OpenAI GitHub', 'summary': 'The SDK adds permission controls.'}
    news.succeeded.emit(ctl.request_id, [source])
    assert len(client.calls) == 1
    success(ctl, client)
    assert page.post['source']['url'] == source['url']
    ctl.copy(True)
    assert copied == [BODY + '\n' + source['url']]
    ctl.clear_history()
    assert ctl.history.records == [] and ctl.current is None


def test_missing_key_invalid_output_and_disk_failure_are_friendly(qapp, tmp_path, monkeypatch):
    ctl, client, _, page, _ = make(qapp, tmp_path)
    monkeypatch.setattr(ctl.credentials, 'get', lambda: None)
    ctl.generate('随机', '随机')
    assert not client.calls and 'Key' in page.error
    monkeypatch.setattr(ctl.credentials, 'get', lambda: 'synthetic-key')
    ctl.generate('随机', '随机')
    client.succeeded.emit(ctl.request_id, '{broken', {})
    assert not ctl.busy and not ctl.history.records
    ctl.generate('随机', '随机')
    def fail(*args):
        raise OSError('private path must not leak')
    monkeypatch.setattr(ctl.history, 'add', fail)
    success(ctl, client)
    assert '保存' in page.error and 'private' not in page.error


@pytest.mark.parametrize('style', ['随机', '犀利', '幽默', '反常识', '热点'])
@pytest.mark.parametrize('topic', ['随机', 'AI工具', 'GitHub开源', '模型更新', 'AI编程', 'AI Agent', '行业观察'])
def test_all_style_topic_selections_dispatch_one_valid_post(qapp, tmp_path, style, topic):
    ctl, client, news, page, _ = make(qapp, tmp_path)
    ctl.generate(style, topic)
    if style == '热点':
        news.succeeded.emit(ctl.request_id, [{'title': 'Verified release fixture',
            'published_at': '2026-11-09T01:00:00Z', 'provider': 'Official fixture',
            'url': 'https://github.com/openai/openai-agents-python/releases',
            'summary': 'Official release fixture used by offline tests.'}])
    assert len(client.calls) == 1
    success(ctl, client)
    assert page.post['body'] == BODY
    assert page.post['style'] == (ctl.seed['style'] if style == '随机' else style)
    if topic != '随机':
        assert page.post['topic'] == topic
