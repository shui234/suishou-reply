import uuid

import pytest

from suishou.credentials import CredentialError, CredentialStore


def test_windows_vault_roundtrip_update_and_delete():
    store = CredentialStore('SuishouReply/Test/' + str(uuid.uuid4()))
    try:
        assert store.get() is None
        store.set('synthetic-test-key-first')
        assert store.get() == 'synthetic-test-key-first'
        store.set('synthetic-test-key-second')
        assert store.get() == 'synthetic-test-key-second'
        store.delete()
        assert store.get() is None
        store.delete()
    finally:
        store.delete()


@pytest.mark.parametrize('key', ['', '   ', 'bad\nkey', 'a' * 3000, '\ud800'])
def test_reject_invalid_key_without_persisting(key):
    store = CredentialStore('SuishouReply/Test/' + str(uuid.uuid4()))
    with pytest.raises(CredentialError):
        store.set(key)
    assert store.get() is None


def test_unavailable_vault_fails_closed(monkeypatch):
    def unavailable():
        raise OSError('unavailable SECRET')
    monkeypatch.setattr('suishou.credentials._load_api', unavailable)
    store = CredentialStore('SuishouReply/Test/' + str(uuid.uuid4()))
    for operation in (store.get, lambda: store.set('secret-test'), store.delete):
        with pytest.raises(CredentialError) as caught:
            operation()
        assert 'SECRET' not in str(caught.value)
        assert 'secret-test' not in str(caught.value)
