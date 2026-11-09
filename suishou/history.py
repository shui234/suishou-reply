"""Atomic local history for generated originals only; copied tweets never enter it."""

from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import tempfile
import time
import unicodedata
from uuid import UUID, uuid4

from .original import _source_data


_MAX_RECORDS = 500
_RECENT_GUARANTEE = 200
_MAX_FILE_BYTES = 8 * 1024 * 1024
_TEXT_FIELDS = ('id', 'created_at', 'seed_id', 'angle', 'body', 'topic', 'style')


def _plain_text(value, maximum=4000) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(unicodedata.category(char).startswith('C') and char not in '\n\r\t'
                   for char in value)):
        raise ValueError('原创历史记录格式异常，请重新生成。')
    return value


def _clean_record(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError('原创历史记录格式异常。')
    record = {field: _plain_text(value.get(field)) for field in _TEXT_FIELDS}
    try:
        UUID(record['id'])
        created = datetime.fromisoformat(record['created_at'])
        if created.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError('原创历史记录的编号或时间格式异常。') from exc
    for flag in ('favorite', 'published'):
        if type(value.get(flag)) is not bool:
            raise ValueError('原创历史记录状态格式异常。')
        record[flag] = value[flag]
    record['source'] = _source_data(value.get('source'))
    return record


def _normalized(text: str) -> str:
    return ''.join(char for char in unicodedata.normalize('NFKC', text).casefold()
                   if unicodedata.category(char)[0] in 'LN')


class HistoryStore:
    """Retain the latest 200 entries and older favorites, bounded at 500.

    A damaged/unreadable file sets ``load_error`` and blocks mutations except
    explicit ``clear``. This lets the app explain recovery without replacing
    unreadable user data during startup or silently pretending it is empty.
    """

    def __init__(self, path: Path | None = None):
        local = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local'))
        self.path = Path(path) if path is not None else local / 'SuishouReply' / 'original-history.json'
        self._records: list[dict] = []
        self.load_error = ''
        self._load()

    def _load(self) -> None:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return
        except OSError:
            self.load_error = '原创历史无法读取，文件可能被占用。请检查文件权限或明确清空历史后重试。'
            return
        try:
            if size > _MAX_FILE_BYTES:
                raise ValueError
            data = json.loads(self.path.read_text(encoding='utf-8-sig'))
            if (not isinstance(data, dict) or type(data.get('version')) is not int
                    or data['version'] != 1 or not isinstance(data.get('records'), list)
                    or len(data['records']) > _MAX_RECORDS):
                raise ValueError
            records = [_clean_record(item) for item in data['records']]
            if len({item['id'] for item in records}) != len(records):
                raise ValueError
            self._records = records
        except OSError:
            self.load_error = '原创历史无法读取，文件可能被占用。请检查文件权限或明确清空历史后重试。'
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self.load_error = '原创历史文件已损坏或格式不支持，原文件已保留。请先备份，或明确清空历史后重试。'

    @property
    def records(self) -> list[dict]:
        return deepcopy(self._records)

    def recent(self, limit: int = 50) -> list[dict]:
        if type(limit) is not int or limit < 0:
            raise ValueError('历史记录数量必须为非负整数。')
        return deepcopy(self._records[:limit])

    def is_duplicate(self, body: str) -> bool:
        if not isinstance(body, str):
            return False
        candidate = _normalized(body)
        if not candidate:
            return False
        candidate_grams = {candidate[index:index + 3] for index in range(len(candidate) - 2)}
        for record in self._records[:100]:
            previous = _normalized(record['body'])
            if candidate == previous:
                return True
            if min(len(candidate), len(previous)) < 12:
                continue
            if SequenceMatcher(None, candidate, previous, autojunk=False).ratio() >= 0.86:
                return True
            previous_grams = {previous[index:index + 3] for index in range(len(previous) - 2)}
            union = candidate_grams | previous_grams
            if union and len(candidate_grams & previous_grams) / len(union) >= 0.7:
                return True
        return False

    def _ensure_writable(self) -> None:
        if self.load_error:
            raise ValueError(self.load_error)

    def _bounded(self, records: list[dict]) -> list[dict]:
        protected = {item['id'] for item in records[:_RECENT_GUARANTEE]}
        protected.update(item['id'] for item in records if item['favorite'])
        if len(protected) > _MAX_RECORDS:
            raise ValueError('原创历史中的收藏过多，请先取消部分旧收藏，再生成新内容。')
        remaining = _MAX_RECORDS - len(protected)
        selected = set(protected)
        for record in records:
            if record['id'] not in selected and remaining:
                selected.add(record['id'])
                remaining -= 1
        return [record for record in records if record['id'] in selected]

    def _persist(self, records: list[dict]) -> None:
        temporary = None
        try:
            serialized = json.dumps({'version': 1, 'records': records}, ensure_ascii=False, indent=2)
            if len(serialized.encode('utf-8')) > _MAX_FILE_BYTES:
                raise OSError('history size limit')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.original-history-', suffix='.tmp', delete=False) as handle:
                temporary = handle.name
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            # Windows indexers/antivirus may briefly hold an existing file.
            # Retry only known Windows sharing/access errors; never delete the
            # destination or relax the all-or-nothing replacement guarantee.
            for attempt in range(3):
                try:
                    os.replace(temporary, self.path)
                    break
                except PermissionError as exc:
                    if attempt == 2 or getattr(exc, 'winerror', None) not in (5, 32, 33):
                        raise
                    time.sleep(0.03 * (attempt + 1))
        except (OSError, UnicodeError) as exc:
            raise OSError('原创历史保存失败，原有记录已保留。请检查文件权限或磁盘空间后重试。') from exc
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass

    def add(self, post: dict, seed: dict) -> dict:
        self._ensure_writable()
        if not isinstance(post, dict) or not isinstance(seed, dict):
            raise ValueError('原创历史记录格式异常，请重新生成。')
        record = _clean_record({
            'id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
            'seed_id': seed.get('id'), 'angle': seed.get('angle'),
            'body': post.get('body'), 'topic': post.get('topic'), 'style': post.get('style'),
            'source': post.get('source'), 'favorite': False, 'published': False,
        })
        records = self._bounded([record] + self._records)
        self._persist(records)
        self._records = records
        return deepcopy(record)

    def update(self, record_id: str, **flags) -> dict:
        self._ensure_writable()
        if any(key not in ('favorite', 'published') or type(value) is not bool
               for key, value in flags.items()):
            raise ValueError('历史记录只能修改收藏和已发布状态。')
        records = deepcopy(self._records)
        record = next((item for item in records if item['id'] == record_id), None)
        if record is None:
            raise ValueError('这条原创历史记录已不存在，请刷新后重试。')
        record.update(flags)
        records = self._bounded(records)
        self._persist(records)
        self._records = records
        return deepcopy(record)

    def clear(self) -> None:
        self._persist([])
        self._records = []
        self.load_error = ''


class MemoryHistoryStore(HistoryStore):
    """The same history behavior for demos/tests, without reading or writing disk."""

    def __init__(self):
        self.path = None
        self._records = []
        self.load_error = ''

    def _persist(self, records: list[dict]) -> None:
        pass
