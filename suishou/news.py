"""Bounded, anonymous official-source news. No model, secrets, or user content."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 6 * 1024 * 1024
TOPICS = ('随机', 'AI工具', 'GitHub开源', '模型更新', 'AI编程', 'AI Agent', '行业观察')


@dataclass(frozen=True)
class Source:
    url: str
    provider: str
    kind: str
    article_host: str
    article_prefix: str = '/'
    topics: tuple[str, ...] = ()


# These are the complete request allowlist, not URLs obtained from feed content.
SOURCES = (
    Source('https://openai.com/news/rss.xml', 'OpenAI', 'rss', 'openai.com'),
    Source('https://deepmind.google/blog/rss.xml', 'Google DeepMind', 'rss', 'deepmind.google', '/blog/'),
    Source('https://api.github.com/repos/openai/openai-agents-python/releases?per_page=20',
           'OpenAI Agents SDK', 'releases', 'github.com', '/openai/openai-agents-python/releases/tag/',
           ('AI Agent', 'GitHub开源', 'AI工具')),
    Source('https://api.github.com/repos/anthropics/claude-code/releases?per_page=20',
           'Anthropic Claude Code', 'releases', 'github.com', '/anthropics/claude-code/releases/tag/',
           ('AI编程', 'AI工具')),
)

_INSTRUCTIONS = re.compile(
    r'ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|'
    r'(?:reveal|print|send)\s+(?:your\s+|the\s+)?(?:api[ -]?key|system\s+prompt)|'
    r'忽略(?:所有|之前|以上|先前|全部)*.{0,8}(?:指令|规则)|'
    r'<\s*/?\s*(?:system|assistant|developer)\b', re.I)


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object', 'svg', 'template'):
            self.hidden.append(tag)
        elif tag in ('p', 'br', 'li', 'div', 'h1', 'h2', 'h3', 'pre') and not self.hidden:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
        elif tag in ('p', 'li', 'div', 'h1', 'h2', 'h3', 'pre'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _clean(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > 200000:
        return ''
    if _INSTRUCTIONS.search(unescape(value)):
        return ''
    parser = _PlainText()
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, RecursionError):
        return ''
    value = ''.join(parser.parts)
    value = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', value)
    value = re.sub(r'(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|>\s*)', '', value)
    # Remove paired Markdown decoration, preserving underscores/operators in code.
    value = re.sub(r'(?<!\w)(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1(?!\w)', r'\2', value)
    value = value.replace('`', '')
    value = ''.join(c for c in value if c in '\n\t' or (ord(c) >= 32 and c not in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069'))
    value = ' '.join(value.split())
    return value if len(value) <= limit else value[:limit - 1].rstrip() + '…'


def _date(value):
    if not isinstance(value, str) or len(value) > 100:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return None
    try:
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _trusted_url(source, value):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and url.hostname == source.article_host
                and url.port in (None, 443) and not url.username and not url.password
                and url.path.startswith(source.article_prefix)
                and '..' not in unquote(url.path).split('/') and '\\' not in unquote(value))
    except ValueError:
        return False


def _topics(source, title, summary, categories):
    if source.topics:
        return source.topics
    text = ' '.join((title, summary, categories)).lower()
    matches = []
    if re.search(r'\bcodex\b|\bcoding\b|\bcode\b|\bdeveloper\w*\b|\bsoftware\b|编程|代码', text):
        matches.append('AI编程')
    if re.search(r'\bagent\w*\b|智能体', text):
        matches.append('AI Agent')
    if re.search(r'\b(?:model|gemini|gpt[- ]?\d|claude|llama|deepseek)\b|模型', text) and re.search(
            r'\b(?:introducing|introduces|new|launch\w*|release\w*|update\w*|preview|available|flash|pro)\b|发布|更新', text):
        matches.append('模型更新')
    if re.search(r'\b(?:tool\w*|app\w*|chatgpt|api|workspace|assistant\w*)\b|工具|助手|应用', text):
        matches.append('AI工具')
    # An official news item without a product/developer signal is industry context.
    if not matches or re.search(r'\b(?:policy|economic\w*|govern\w*|education|universit\w*|partnership|safety)\b', text):
        matches.append('行业观察')
    return tuple(matches)


def parse_source(source: Source, payload: bytes, *, now=None, topic='随机', include_prereleases=False) -> list[dict]:
    """Keep dated source excerpts only. `updated` is never a publication date."""
    if source not in SOURCES or topic not in TOPICS or not payload or len(payload) > MAX_PAYLOAD_BYTES:
        return []
    now = now if now is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        return []
    records = []
    try:
        if source.kind == 'releases':
            values = json.loads(payload.decode('utf-8'))
            if not isinstance(values, list):
                return []
            for item in values[:100]:
                if (not isinstance(item, dict) or item.get('draft') is not False
                        or type(item.get('prerelease')) is not bool
                        or (item['prerelease'] and not include_prereleases)):
                    continue
                records.append((item.get('name') or item.get('tag_name'), item.get('published_at'),
                                item.get('html_url'), item.get('body'), ''))
        else:
            # Entity expansion and external declarations are never needed for RSS.
            if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
                return []
            root = ET.fromstring(payload)
            for item in root.findall('./channel/item')[:2000]:
                records.append((item.findtext('title'), item.findtext('pubDate'), item.findtext('link'),
                                item.findtext('description'), ' '.join(x.text or '' for x in item.findall('category'))))
    except (ValueError, TypeError, UnicodeError, ET.ParseError, RecursionError):
        return []
    items, seen = [], set()
    for raw_title, raw_date, url, raw_summary, categories in records:
        title, summary, published = _clean(raw_title, 220), _clean(raw_summary, 1200), _date(raw_date)
        if (not title or not summary or published is None or not _trusted_url(source, url)
                or not now - timedelta(days=14) <= published <= now or url in seen):
            continue
        topics = _topics(source, title, summary, categories)
        if topic != '随机' and topic not in topics:
            continue
        seen.add(url)
        items.append({'title': title, 'published_at': published.isoformat(), 'url': url,
                      'summary': summary, 'provider': source.provider,
                      'topic': topics[0] if topic == '随机' else topic})
    return sorted(items, key=lambda item: item['published_at'], reverse=True)[:30]


class NewsClient(QObject):
    succeeded = Signal(int, list)
    failed = Signal(int, str)

    def __init__(self, parent: QObject | None = None, *, manager=None, timeout_ms=10000,
                 total_timeout_ms=18000, max_bytes=MAX_PAYLOAD_BYTES, total_bytes=MAX_TOTAL_BYTES,
                 include_prereleases=False, now=None):
        super().__init__(parent)
        self._manager = manager if manager is not None else QNetworkAccessManager(self)
        self._timeout_ms = min(15000, max(1, int(timeout_ms)))
        self._total_timeout_ms = min(25000, max(1, int(total_timeout_ms)))
        self._max_bytes = min(MAX_PAYLOAD_BYTES, max(1, int(max_bytes)))
        self._total_bytes = min(MAX_TOTAL_BYTES, max(1, int(total_bytes)))
        self._include_prereleases = bool(include_prereleases)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._active = None

    def fetch(self, request_id: int, topic: str = '随机') -> None:
        self.cancel()
        if topic not in TOPICS:
            self.failed.emit(request_id, '请选择支持的热点主题，或改选“随机”。')
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        active = {'id': request_id, 'topic': topic, 'queue': list(SOURCES), 'pending': {},
                  'items': [], 'received': 0, 'timer': timer}
        self._active = active
        timer.timeout.connect(lambda: self._complete(active))
        timer.start(self._total_timeout_ms)
        self._pump(active)

    def _pump(self, active):
        if self._active is not active:
            return
        while active['queue'] and len(active['pending']) < 3:
            source = active['queue'].pop(0)
            request = QNetworkRequest(QUrl(source.url))
            request.setRawHeader(QByteArray(b'User-Agent'), QByteArray(b'SuishouReply/1.1 (official-public-news)'))
            request.setRawHeader(QByteArray(b'Accept'), QByteArray(b'application/rss+xml, application/json, application/xml'))
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                                 QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            for attribute in (QNetworkRequest.Attribute.CookieLoadControlAttribute,
                              QNetworkRequest.Attribute.CookieSaveControlAttribute,
                              QNetworkRequest.Attribute.AuthenticationReuseAttribute):
                request.setAttribute(attribute, QNetworkRequest.LoadControl.Manual)
            request.setTransferTimeout(self._timeout_ms)
            try:
                reply = self._manager.get(request)
            except (RuntimeError, OSError):
                continue
            reply.setReadBufferSize(self._max_bytes + 1)
            timer = QTimer(self)
            timer.setSingleShot(True)
            token = object()
            active['pending'][token] = {'reply': reply, 'timer': timer, 'source': source, 'data': bytearray()}
            reply.readyRead.connect(lambda t=token: self._read(active, t))
            reply.metaDataChanged.connect(lambda t=token: self._metadata(active, t))
            reply.finished.connect(lambda t=token: self._finished(active, t))
            timer.timeout.connect(lambda t=token: self._discard(active, t))
            timer.start(self._timeout_ms)
        if not active['pending']:
            self._complete(active)

    def _metadata(self, active, token):
        if self._active is not active or token not in active['pending']:
            return
        length = active['pending'][token]['reply'].header(QNetworkRequest.KnownHeaders.ContentLengthHeader)
        try:
            if length is not None and int(length) > self._max_bytes:
                self._discard(active, token)
        except (ValueError, TypeError, OverflowError):
            self._discard(active, token)

    def _read(self, active, token):
        if self._active is not active or token not in active['pending']:
            return
        record = active['pending'][token]
        limit = min(self._max_bytes - len(record['data']), self._total_bytes - active['received']) + 1
        chunk = bytes(record['reply'].read(limit))
        active['received'] += len(chunk)
        record['data'].extend(chunk)
        if active['received'] > self._total_bytes:
            self._complete(active)
        elif len(record['data']) > self._max_bytes:
            self._discard(active, token)

    @staticmethod
    def _stop_record(record, *, abort=False):
        record['timer'].stop()
        record['timer'].deleteLater()
        if abort:
            record['reply'].abort()
        record['reply'].deleteLater()

    def _discard(self, active, token):
        if self._active is not active:
            return
        record = active['pending'].pop(token, None)
        if record is not None:
            self._stop_record(record, abort=True)
            self._pump(active)

    def _finished(self, active, token):
        if self._active is not active or token not in active['pending']:
            return
        self._metadata(active, token)
        self._read(active, token)
        if self._active is not active:
            return
        record = active['pending'].pop(token, None)
        if record is None:
            return
        reply = record['reply']
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status == 200 and reply.error() == QNetworkReply.NetworkError.NoError:
                active['items'].extend(parse_source(record['source'], bytes(record['data']), now=self._now(),
                                                    topic=active['topic'], include_prereleases=self._include_prereleases))
        finally:
            self._stop_record(record)
        self._pump(active)

    def cancel(self) -> None:
        active, self._active = self._active, None
        if active is None:
            return
        # Break timer -> callback -> active -> timer before deferred deletion.
        # Keeping this cycle can destroy the Python wrapper inside Qt's delete.
        timer = active.pop('timer')
        timer.stop()
        timer.timeout.disconnect()
        timer.deleteLater()
        for record in active['pending'].values():
            self._stop_record(record, abort=True)
        active['pending'].clear()

    def _complete(self, active):
        if self._active is not active:
            return
        items = {item['url']: item for item in active['items']}
        result = sorted(items.values(), key=lambda item: item['published_at'], reverse=True)[:30]
        self.cancel()
        if result:
            self.succeeded.emit(active['id'], result)
        else:
            self.failed.emit(active['id'],
                             '暂未找到近 14 天内有完整来源和摘要的官方动态，来源可能暂时不可用。请稍后重试或改选“随机”。')
