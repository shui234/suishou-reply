import json
import pytest

from suishou.history import HistoryStore, MemoryHistoryStore


BODY = '给代码助手开更多权限之前，先想清楚它出错时谁来收拾。能自动执行只是起点，能看懂改动、及时停下和撤回，才决定你敢不敢把下一步交给它。'
SEED = {'id': 'agent-permissions', 'angle': '可撤回的权限', 'style': '犀利', 'topic': 'AI Agent'}


def post(body=BODY):
    return {'body': body, 'topic': 'AI Agent', 'style': '犀利', 'source': None,
            'copied_tweet': 'PRIVATE ORIGINAL TWEET', 'api_key': 'PRIVATE KEY'}


def test_records_roundtrip_newest_first_with_flags_and_no_unrelated_source_data(tmp_path):
    path = tmp_path / 'nested' / 'history.json'
    store = HistoryStore(path)
    first = store.add(post(), SEED)
    second = store.add(post('第二条原创内容'), SEED)
    store.update(first['id'], favorite=True, published=True)
    loaded = HistoryStore(path)
    assert [item['id'] for item in loaded.records] == [second['id'], first['id']]
    assert loaded.records[1]['favorite'] is True
    assert loaded.records[1]['published'] is True
    assert first['created_at']
    assert first['angle'] == '可撤回的权限'
    assert 'PRIVATE' not in path.read_text(encoding='utf-8')
    assert loaded.recent(1)[0]['id'] == second['id']


def test_default_path_uses_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    store = HistoryStore()
    store.add(post(), SEED)
    assert (tmp_path / 'SuishouReply' / 'original-history.json').exists()


def test_mutating_return_values_cannot_silently_change_saved_history(tmp_path):
    store = HistoryStore(tmp_path / 'history.json')
    result = store.add(post(), SEED)
    result['body'] = 'tampered'
    store.records[0]['favorite'] = True
    store.recent()[0]['body'] = 'tampered'
    assert store.records[0]['body'] == BODY
    assert store.records[0]['favorite'] is False


def test_near_duplicates_ignore_punctuation_and_small_word_changes(tmp_path):
    store = HistoryStore(tmp_path / 'history.json')
    store.add(post(), SEED)
    assert store.is_duplicate(BODY.replace('，', ' ').replace('。', '！'))
    assert store.is_duplicate(BODY.replace('更多权限', '所有权限'))
    assert not store.is_duplicate('开源模型下载成功只是开始，真正麻烦的是部署、内存和后续升级。README写得再漂亮，也代替不了环境配置和故障排查。')
    assert not store.is_duplicate('')


def test_retention_keeps_recent_100_and_old_favorite_with_bounded_file(tmp_path):
    path = tmp_path / 'history.json'
    store = HistoryStore(path)
    first = store.add(post('需要长期保留的收藏'), SEED)
    store.update(first['id'], favorite=True)
    ids = []
    for index in range(510):
        ids.append(store.add(post(f'原创记录{index}'), SEED)['id'])
    loaded = HistoryStore(path)
    assert len(loaded.records) <= 500
    assert len(loaded.recent()) >= 50
    assert [item['id'] for item in loaded.recent(100)] == list(reversed(ids[-100:]))
    assert any(item['id'] == first['id'] and item['favorite'] for item in loaded.records)


def test_clear_removes_all_records_persistently(tmp_path):
    path = tmp_path / 'history.json'
    store = HistoryStore(path)
    record = store.add(post(), SEED)
    store.update(record['id'], favorite=True)
    store.clear()
    assert store.records == []
    assert HistoryStore(path).records == []


@pytest.mark.parametrize('operation', ['add', 'update', 'clear'])
def test_failed_atomic_write_preserves_disk_and_memory(tmp_path, monkeypatch, operation):
    path = tmp_path / 'history.json'
    store = HistoryStore(path)
    record = store.add(post(), SEED)
    before = path.read_bytes()

    def fail_replace(*args):
        raise PermissionError('locked')

    monkeypatch.setattr('suishou.history.os.replace', fail_replace)
    with pytest.raises(OSError, match='历史'):
        if operation == 'add':
            store.add(post('新的原创内容'), SEED)
        elif operation == 'update':
            store.update(record['id'], published=True)
        else:
            store.clear()
    assert path.read_bytes() == before
    assert store.records == [record]
    assert list(tmp_path.iterdir()) == [path]


def test_transient_windows_file_lock_can_finish_atomic_save(tmp_path, monkeypatch):
    import os
    path = tmp_path / 'history.json'
    store = HistoryStore(path)
    store.add(post(), SEED)
    replace = os.replace
    pending_failure = [True]

    def temporarily_locked(source, destination):
        if pending_failure:
            pending_failure.pop()
            error = PermissionError('temporary lock')
            error.winerror = 32
            raise error
        replace(source, destination)

    monkeypatch.setattr('suishou.history.os.replace', temporarily_locked)
    saved = store.add(post('文件锁释放后保存的原创内容'), SEED)
    assert HistoryStore(path).records[0] == saved
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('document', ['{broken', 'null', '[]',
                                   '{"version":1,"records":[{"body":"invalid"}]}'])
def test_corrupt_history_is_explicit_and_never_overwritten(tmp_path, document):
    path = tmp_path / 'history.json'
    path.write_text(document, encoding='utf-8')
    store = HistoryStore(path)
    assert '历史' in store.load_error
    with pytest.raises(ValueError, match='历史'):
        store.add(post(), SEED)
    assert path.read_text(encoding='utf-8') == document
    store.clear()
    assert store.load_error == ''
    assert HistoryStore(path).records == []


def test_existing_directory_is_not_treated_as_empty_history(tmp_path):
    store = HistoryStore(tmp_path)
    assert '历史' in store.load_error
    with pytest.raises(ValueError, match='历史'):
        store.add(post(), SEED)


def test_updates_only_accept_boolean_publication_and_favorite_flags(tmp_path):
    store = HistoryStore(tmp_path / 'history.json')
    record = store.add(post(), SEED)
    for flags in ({'favorite': 'yes'}, {'body': 'changed'}, {'copied_tweet': 'secret'}):
        with pytest.raises(ValueError):
            store.update(record['id'], **flags)
    with pytest.raises(ValueError, match='历史|记录'):
        store.update('missing-id', favorite=True)
    assert store.records == [record]


def test_memory_store_behaves_like_history_without_touching_disk(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    store = MemoryHistoryStore()
    record = store.add(post(), SEED)
    store.update(record['id'], favorite=True)
    assert store.records[0]['favorite'] is True
    assert store.is_duplicate(BODY)
    assert list(tmp_path.iterdir()) == []
    store.clear()
    assert store.records == []
