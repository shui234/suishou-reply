import json

import pytest

from suishou.config import Settings, SettingsStore


def test_missing_or_broken_config_uses_defaults(tmp_path):
    path = tmp_path / 'settings.json'
    assert SettingsStore(path).load() == Settings()
    path.write_text('{broken', encoding='utf-8')
    assert SettingsStore(path).load() == Settings()


def test_loading_config_rejects_invalid_values_and_ignores_secrets(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'model': '../bad model', 'style': [], 'theme': 4,
                               'api_key': 'must-not-load'}), encoding='utf-8')
    assert SettingsStore(path).load() == Settings()


def test_saving_roundtrips_custom_model_with_only_allowed_fields(tmp_path):
    path = tmp_path / 'nested' / 'settings.json'
    store = SettingsStore(path)
    settings = Settings(model='vendor/new-model:v2', style='犀利', theme='light')
    store.save(settings)
    assert store.load() == settings
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'model': 'vendor/new-model:v2', 'style': '犀利', 'theme': 'light'}
    assert list(path.parent.iterdir()) == [path]


def test_failed_atomic_replace_keeps_previous_config(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    store = SettingsStore(path)
    store.save(Settings())
    def fail_replace(*args):
        raise PermissionError('locked')
    monkeypatch.setattr('suishou.config.os.replace', fail_replace)
    with pytest.raises(OSError):
        store.save(Settings(style='幽默'))
    assert store.load() == Settings()
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('document', ['null', '[]', '"hello"'])
def test_non_object_config_is_ignored(tmp_path, document):
    path = tmp_path / 'settings.json'
    path.write_text(document, encoding='utf-8')
    assert SettingsStore(path).load() == Settings()
