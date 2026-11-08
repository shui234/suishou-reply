import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QImage
from suishou.clipboard import inspect_text, read_clipboard_text


@pytest.mark.parametrize('text', [
    '最近的AI工具越来越多，真正省下时间的反而是少用几个。',
    'Building software is easy. Finding a problem worth solving is hard.',
    '我觉得 API 的设计还是应该先考虑使用体验，而不只是参数数量。',
])
def test_accept_tweets(text):
    assert inspect_text(text).allowed


@pytest.mark.parametrize('text', [
    '', '123456', 'https://x.com/someone/status/1234567890',
    'C:\\Users\\alice\\private\\document.txt',
    '密码：Password123! 请勿泄露这个账号的登录信息',
    '验证码 583920，5分钟内有效，请勿向任何人提供',
    'Your login code is 583920. Do not share it with anyone.',
    '我的密码是 Abcd123456! 你可以用它登录这个测试账户。',
    'The password is SyntheticPassword123! Please keep it secret.',
    'Here is my key sk-abcdefghijklmnop1234567890123456',
    'Authorization: Bearer abcdefghijklmnopqrstuvwxyz',
    'token=abcdefghijklmnop1234567890',
    'ghp_abcdefghijklmnopqrstuvwxyz0123456789',
    '-----BEGIN PRIVATE KEY-----\nabcdefghijklmno',
    '{"password":"secret-value-123", "user":"alice"}',
    'def my_function():\n    return some_private_value',
    'A7bK9mX2pQ4rT8vW6zY1aC5dE0fG3hI9',
    '字' * 3001,
])
def test_reject_non_tweets_and_obvious_secrets(text):
    assert not inspect_text(text).allowed


def test_mime_ignores_files_and_images(qapp):
    data = QMimeData()
    data.setText('这是一段足够长的文字，但实际复制的是图片或者文件。')
    data.setUrls([QUrl.fromLocalFile('C:/secret.txt')])
    assert read_clipboard_text(data) is None
    data = QMimeData()
    data.setImageData(QImage(1, 1, QImage.Format.Format_RGB32))
    data.setText('这是一段足够长的文字，但它还含有图片。')
    assert read_clipboard_text(data) is None


def test_browser_html_uses_only_plain_text(qapp):
    data = QMimeData()
    data.setHtml('<b>网页复制带格式</b>')
    data.setText('网页复制通常会附带格式，保留它的纯文本即可正常处理。')
    assert read_clipboard_text(data) == data.text()
