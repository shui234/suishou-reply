"""Single-flight original-post workflow; never consumes clipboard input."""
import random

from PySide6.QtCore import QObject

from .original import choose_seed, build_original_messages, parse_post, weighted_length, TOPICS


class OriginalController(QObject):
    def __init__(self, *, client, news, page, history, credentials, settings,
                 copy_text, history_error='', parent=None):
        super().__init__(parent)
        self.client, self.news, self.page = client, news, page
        self.history, self.credentials, self.settings = history, credentials, settings
        self.copy_text = copy_text
        self.history_error = history_error
        self.current = None
        self.usage = {}
        self.seed = None
        self.source = None
        self.request_id = 0
        self.busy = False
        self._closed = False
        client.succeeded.connect(self._succeeded)
        client.failed.connect(self._failed)
        news.succeeded.connect(self._news_ready)
        news.failed.connect(self._failed)
        page.generate_requested.connect(self.generate)
        page.cancel_requested.connect(self.cancel)
        page.copy_requested.connect(self.copy)
        page.favorite_requested.connect(self.toggle_favorite)
        page.published_requested.connect(self.toggle_published)
        page.history_requested.connect(self.show_history)
        page.clear_history_requested.connect(self.clear_history)
        page.record_requested.connect(self.select_record)
        if history_error:
            page.show_error(history_error)

    def generate(self, style='随机', topic='随机'):
        if self._closed or self.busy:
            return
        if self.history_error:
            self.page.show_error(self.history_error)
            return
        try:
            key = self.credentials.get()
        except Exception:
            key = None
        if not key:
            self.page.show_error('请先在设置中安全保存 DeepSeek API Key。')
            return
        try:
            self.seed = choose_seed(style, topic, self.history.recent())
        except (ValueError, OSError):
            self.page.show_error('无法读取话题灵感，请检查程序文件是否完整。')
            return
        self.request_id += 1
        self.busy = True
        self.current, self.source, self.usage = None, None, {}
        self.page.show_loading('正在查找近 14 天的官方来源…' if style == '热点' else '正在酝酿一条新观点…')
        if style == '热点':
            self.news.fetch(self.request_id, topic)
        else:
            self._request_model(key)

    def _request_model(self, key=None):
        if not self.busy or self._closed:
            return
        try:
            key = key or self.credentials.get()
            if not key:
                self._failed(self.request_id, '无法读取 API Key，请在设置中重新保存。')
                return
            messages = build_original_messages(self.seed, self.history.recent(), self.source)
        except Exception:
            self._failed(self.request_id, '生成素材不可用，请重新选择话题后重试。')
            return
        self.page.show_loading('DeepSeek 正在写作…')
        self.client.generate_original(self.request_id, messages, key, self.settings.model)

    def _news_ready(self, request_id, sources):
        if not self.busy or self._closed or request_id != self.request_id:
            return
        if not sources:
            self._failed(request_id, '暂无可靠的新素材，请换个话题或稍后再试。')
            return
        used = {(record.get('source') or {}).get('url') for record in self.history.recent()}
        fresh = [source for source in sources if source.get('url') not in used]
        if not fresh:
            self._failed(request_id, '近期可用来源已在原创历史中使用，请换个话题或稍后再试。')
            return
        self.source = random.choice(fresh)
        self.seed['theme'] = self.source['title']
        if self.source.get('topic') in TOPICS[1:]:
            self.seed['topic'] = self.source['topic']
        self.seed['instructions'] = '以 source 为唯一事实依据；不使用本地灵感推断新闻事实。'
        self._request_model()

    def _succeeded(self, request_id, raw, usage):
        if not self.busy or self._closed or request_id != self.request_id:
            return
        self.busy = False
        try:
            post = parse_post(raw, self.seed, self.source)
            if self.history.is_duplicate(post['body']):
                self.page.show_error('这条内容与近期记录相似，已拦截；点击「换一条」再试，不会自动重试扣费。')
                return
            self.current = self.history.add(post, self.seed)
        except ValueError as exc:
            # Validator errors are fixed public messages, never raw server data.
            self.page.show_error(str(exc))
            return
        except OSError:
            self.page.show_error('原创记录保存失败，请检查本地数据目录权限后重试。')
            return
        self.usage = usage
        self.page.show_post(self.current, usage)

    def _failed(self, request_id, message):
        if not self.busy or self._closed or request_id != self.request_id:
            return
        self.busy = False
        self.current = None
        self.page.show_error(message)

    def cancel(self):
        was_busy = self.busy
        self.request_id += 1
        self.busy = False
        self.client.cancel()
        self.news.cancel()
        self.page.set_busy(False)
        if was_busy:
            self.current = None
            self.page.show_idle('已取消生成。调整风格或话题后，再来一条。')

    def copy(self, with_source=False):
        if self._closed or self.busy or not self.current:
            return
        text = self.current['body']
        if with_source and self.current.get('source'):
            text += '\n' + self.current['source']['url']
        if weighted_length(text) > 280:
            self.page.show_error('内容超过普通 X 帖子的长度限制，请换一条。')
            return
        self.copy_text(text)
        self.page.show_copied()

    def _toggle(self, flag):
        if self._closed or self.busy or not self.current:
            return
        try:
            self.current = self.history.update(self.current['id'], **{flag: not self.current[flag]})
        except (OSError, ValueError, KeyError):
            self.page.show_error('本地标记保存失败，请检查数据目录权限。')
            return
        self.page.show_post(self.current, self.usage)

    def toggle_favorite(self):
        self._toggle('favorite')

    def toggle_published(self):
        self._toggle('published')

    def show_history(self):
        self.page.show_history(self.history.records)

    def select_record(self, record_id):
        self.cancel()
        record = next((r for r in self.history.records if r['id'] == record_id), None)
        if record:
            self.current, self.usage = record, {}
            self.page.show_post(record, {})

    def clear_history(self):
        self.cancel()
        try:
            self.history.clear()
        except (OSError, ValueError):
            self.page.show_error('无法清理原创历史，请检查本地数据目录权限。')
            return
        self.history_error = ''
        self.current = None
        self.page.show_idle('原创历史、收藏与已发布标记已清理。')
        dialog = getattr(self.page, 'history_dialog', None)
        if dialog is not None:
            dialog.populate([])

    def shutdown(self):
        self._closed = True
        self.cancel()
