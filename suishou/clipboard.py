"""Conservative clipboard eligibility checks. Never persist inspected text."""
from dataclasses import dataclass
import hashlib
import re
import unicodedata

OWN_MIME = 'application/x-suishou-reply'
MIN_LENGTH = 12
MAX_LENGTH = 3000


@dataclass(frozen=True)
class Inspection:
    allowed: bool
    text: str = ''
    reason: str = ''


def normalize(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode('utf-8')).hexdigest()


_SECRET = re.compile(
    r'(?i)(?:\b(?:sk-[\w-]{12,}|gh[pousr]_[\w]{16,}|github_pat_[\w]{16,}'
    r'|AKIA[A-Z0-9]{16}|AIza[\w-]{20,}|xox[baprs]-[\w-]{12,})'
    r'|-----BEGIN[ A-Z]*PRIVATE KEY-----'
    r'|\bBearer\s+\S{8,}'
    r'|\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}'
    r'|(?:password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|token|密码|密钥|口令)'
    r'[\s\"\x27]*(?:[:=：]|是|为|\bis\b)[\s\"\x27]*\S{3,}'
    r'|(?:验证码|校验码|动态码|动态口令|一次性密码|(?:verification|login|security|authentication|one.time)\s*code|OTP)[\s\S]{0,24}\d{4,8}'
    r'|\d{4,8}[\s\S]{0,12}(?:验证码|校验码|动态码|verification\s*code))'
)
_CODE = re.compile(
    r'(?im)(?:^\s*(?:def |class |import |from \w+ import |function |const |let |SELECT .+ FROM |'
    r'curl |powershell |pip install |npm install |<html|<!doctype|```)|^\s*[\[{][\s\S]*[\]}]\s*$)'
)


def inspect_text(text: str) -> Inspection:
    text = normalize(text)
    if not MIN_LENGTH <= len(text) <= MAX_LENGTH:
        return Inspection(False, reason='长度不在 12～3000 字范围内')
    if any(unicodedata.category(ch) == 'Cc' and ch not in '\n\t' for ch in text):
        return Inspection(False, reason='含有非文本控制字符')
    if _SECRET.search(text):
        return Inspection(False, reason='可能含有密钥、密码或验证码')
    if re.fullmatch(r'(?:https?://\S+\s*)+', text, re.I):
        return Inspection(False, reason='仅包含链接')
    if re.match(r'^(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:Users|home|tmp)/)', text):
        return Inspection(False, reason='文件路径')
    if re.fullmatch(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text):
        return Inspection(False, reason='邮箱地址')
    if re.fullmatch(r'[\d\s+().-]+', text):
        return Inspection(False, reason='数字或号码')
    if re.fullmatch(r'[A-Za-z0-9_+/=-]{16,}', text):
        return Inspection(False, reason='疑似令牌')
    if _CODE.search(text):
        return Inspection(False, reason='代码或结构化数据')
    if not any(ch.isalpha() for ch in text):
        return Inspection(False, reason='没有可评论的正文')
    return Inspection(True, text)


def read_clipboard_text(mime) -> str | None:
    if mime is None or mime.hasUrls() or mime.hasImage() or not mime.hasText():
        return None
    return normalize(mime.text())
