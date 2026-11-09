"""Tray application wiring. Offline demo uses only synthetic local responses."""
from dataclasses import replace
import json
import re
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox
from .api import DeepSeekClient
from .config import Settings, SettingsStore
from .credentials import CredentialStore
from .controller import ReplyController
from .ui import ReplyWindow, SettingsDialog, create_icon
from .history import HistoryStore, MemoryHistoryStore
from .original_controller import OriginalController
from .news import NewsClient


class MemorySettingsStore:
    def __init__(self):
        self.settings = Settings()
    def load(self):
        return replace(self.settings)
    def save(self, settings):
        self.settings = replace(settings)


class DemoCredentials:
    def get(self):
        return 'offline-demo-placeholder'
    def set(self, key):
        pass
    def delete(self):
        pass


class DemoClient(QObject):
    succeeded = Signal(int, str, dict)
    failed = Signal(int, str)
    REPLIES = (
        '工具再多也得先想清楚要做什么，不然只是把拖延换成了研究工具。',
        '选择多了未必省事，能让人少纠结几次的工具，才比较值得留下。',
        '工具栏越来越热闹，待办清单倒是纹丝不动。看来还缺一个替我关掉工具的工具。',
    )
    def __init__(self, parent=None):
        super().__init__(parent)
        self._revision = 0
        self._count = 0
    def generate(self, request_id, text, key, model, style, previous=''):
        self.cancel()
        revision = self._revision
        reply = self.REPLIES[self._count % len(self.REPLIES)]
        self._count += 1
        def complete():
            if self._revision == revision:
                self.succeeded.emit(request_id, reply, {'prompt_tokens': 128, 'completion_tokens': 37, 'total_tokens': 165})
        QTimer.singleShot(420, self, complete)
    def cancel(self):
        self._revision += 1

    def generate_original(self, request_id, messages, key, model):
        self.cancel()
        revision = self._revision
        # Synthetic text is visibly marked as demo by the window; never a live API claim.
        samples = (
            '让 AI 写代码最省心的时刻，不是它一口气生成了多少行，而是你能看懂它为什么这么写。省下敲键盘的时间，可以留一点给检查边界。',
            '工具订阅越多，取消订阅的判断就越重要。把省下的时间花在真正需要完成的事情上，比收集一排用不到的新功能更划算。',
            '给 Agent 开权限像给新同事发钥匙：能进门就够了，没必要顺手把保险柜密码也交出去。自动化最该省的，可能是出事后解释谁批准的时间。',
        )
        body = samples[self._count % len(samples)]
        self._count += 1
        def complete():
            if self._revision == revision:
                self.succeeded.emit(request_id, json.dumps({'body': body, 'topic': 'AI编程',
                    'style': '犀利', 'source': None}, ensure_ascii=False), {'total_tokens': 240})
        QTimer.singleShot(420, self, complete)


class DemoNews(QObject):
    succeeded = Signal(int, list)
    failed = Signal(int, str)
    def fetch(self, request_id, topic='随机'):
        self.failed.emit(request_id, '离线演示不获取新闻。正式模式将查找有日期与摘要的官方来源。')
    def cancel(self):
        pass


class AppRuntime(QObject):
    def __init__(self, app, *, demo=False, tray_enabled=True, store=None, credentials=None):
        super().__init__()
        self.app, self.demo = app, demo
        self.store = store if store is not None else (MemorySettingsStore() if demo else SettingsStore())
        self.credentials = credentials if credentials is not None else (DemoCredentials() if demo else CredentialStore())
        self.settings = self.store.load()
        self.window = ReplyWindow()
        self.window.setWindowIcon(create_icon())
        if demo:
            self.window.set_demo_mode(True)
        self.client = DemoClient(self) if demo else DeepSeekClient(self)
        self.test_client = DemoClient(self) if demo else DeepSeekClient(self)
        self.controller = ReplyController(clipboard=app.clipboard(), client=self.client,
            window=self.window, settings=self.settings, credentials=self.credentials, store=self.store, parent=self)
        self.original_client = DemoClient(self) if demo else DeepSeekClient(self)
        self.news = DemoNews(self) if demo else NewsClient(self)
        self.history = MemoryHistoryStore() if demo else HistoryStore()
        self.original_controller = OriginalController(client=self.original_client, news=self.news,
            page=self.window.original_page, history=self.history, credentials=self.credentials,
            settings=self.settings, copy_text=self.controller.copy_generated_text,
            history_error=self.history.load_error, parent=self)
        self.window.mode_changed.connect(self._mode_changed)
        self.controller.listening_changed.connect(self._listening_mode)
        self.settings_dialog = SettingsDialog()
        self.settings_dialog.setWindowIcon(create_icon())
        self.settings_dialog.save_requested.connect(self.save_settings)
        self.settings_dialog.test_requested.connect(self.test_connection)
        self.settings_dialog.delete_key_requested.connect(self.delete_key)
        self.settings_dialog.finished.connect(self._settings_closed)
        self.window.settings_requested.connect(self.open_settings)
        self.test_client.succeeded.connect(self._test_succeeded)
        self.test_client.failed.connect(self._test_failed)
        self._test_id = 0
        self._cleaned = False
        self.tray = None
        if tray_enabled:
            self._create_tray()
        app.aboutToQuit.connect(self.cleanup)

    def _create_tray(self):
        self.tray = QSystemTrayIcon(create_icon(), self)
        self.tray.setToolTip('随手回 · 监听已暂停' + (' · 离线演示' if self.demo else ''))
        self.menu = QMenu()
        title = self.menu.addAction('随手回 · X 互动与原创' + (' · 离线演示' if self.demo else ''))
        title.setEnabled(False)
        self.menu.addSeparator()
        self.toggle_action = self.menu.addAction('开启监听')
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.controller.set_listening)
        self.controller.listening_changed.connect(self._update_tray)
        self.menu.addAction('推文回复', lambda: self.show_mode('reply'))
        self.menu.addAction('来一条 · 原创短帖', lambda: self.show_mode('original'))
        style_menu = self.menu.addMenu('回复风格')
        group = QActionGroup(self)
        self.style_actions = {}
        for style in ('自然', '犀利', '幽默'):
            action = QAction(style, group)
            action.setCheckable(True)
            action.setChecked(style == self.settings.style)
            action.triggered.connect(lambda checked, s=style: self._tray_style(s))
            style_menu.addAction(action)
            self.style_actions[style] = action
        self.window.style_changed.connect(self._sync_style_actions)
        self.menu.addAction('设置…', self.open_settings)
        self.menu.addSeparator()
        self.menu.addAction('退出随手回', self.app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.window.present()

    def show_mode(self, mode):
        self.window.set_mode(mode)
        self.window.present()

    def _mode_changed(self, mode):
        if mode == 'original':
            self.controller.set_listening(False)
        else:
            self.original_controller.cancel()

    def _listening_mode(self, enabled):
        if enabled:
            self.original_controller.cancel()
            self.window.set_mode('reply')

    def _update_tray(self, enabled):
        if not self.tray:
            return
        self.toggle_action.blockSignals(True)
        self.toggle_action.setChecked(enabled)
        self.toggle_action.setText('暂停监听' if enabled else '开启监听')
        self.toggle_action.blockSignals(False)
        self.tray.setToolTip('随手回 · ' + ('正在监听' if enabled else '监听已暂停') + (' · 离线演示' if self.demo else ''))

    def _tray_style(self, style):
        self.controller.set_style(style)
        self.window.set_style(self.settings.style)
        self._sync_style_actions(self.settings.style)

    def _sync_style_actions(self, style):
        if self.tray:
            self.style_actions[self.settings.style].setChecked(True)

    def start(self):
        self.window.present()
        if self.demo:
            self.window.show_idle('离线演示：开启监听后，复制一段模拟推文。')
            return
        try:
            has_key = bool(self.credentials.get())
        except Exception:
            has_key = False
        if not has_key:
            self.open_settings()

    def open_settings(self):
        self.original_controller.cancel()
        if self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        # Deliberately remain paused after the dialog closes: keys can be on the clipboard.
        self.controller.set_listening(False)
        self._update_tray(False)
        try:
            has_key = bool(self.credentials.get())
        except Exception:
            has_key = False
        self.settings_dialog.populate(self.settings.model, self.settings.style, self.settings.theme, has_key)
        self.settings_dialog.set_status('离线演示模式：不保存密钥，不访问网络。' if self.demo else '设置期间监听已暂停；关闭后可手动重新开启。')
        self.settings_dialog.setModal(True)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _settings_closed(self, result):
        self._test_id += 1
        self.test_client.cancel()
        self.settings_dialog.key_input.clear()
        self.settings_dialog.set_testing(False)

    def save_settings(self, key, model, style, theme):
        model = model.strip()
        key = key.strip()
        if not re.fullmatch(r'[A-Za-z0-9._:/-]{1,100}', model):
            self.settings_dialog.set_status('请输入有效的模型名称，例如 deepseek-flash。', True)
            return
        if style not in ('自然', '犀利', '幽默') or theme not in ('dark', 'light'):
            self.settings_dialog.set_status('请选择有效的风格和主题。', True)
            return
        if key and (len(key) > 4096 or not key.isascii() or any(ch.isspace() or ord(ch) < 33 for ch in key)):
            self.settings_dialog.set_status('API Key 格式不正确，请检查是否复制了额外文字。', True)
            return
        try:
            if key:
                self.credentials.set(key)
            updated = Settings(model=model, style=style, theme=theme)
            self.store.save(updated)
        except Exception:
            self.settings_dialog.set_status('保存失败，请检查 Windows 凭据管理器及本地配置目录是否可用。', True)
            return
        self.settings = updated
        self.controller.settings = updated
        self.original_controller.settings = updated
        self.window.set_theme(theme)
        self.window.set_style(style)
        self._sync_style_actions(style)
        self.settings_dialog.accept()
        self.window.show_idle('设置已保存。开启监听后，下一次复制推文时生成回复。')

    def delete_key(self):
        self._test_id += 1
        self.test_client.cancel()
        self.settings_dialog.set_testing(False)
        try:
            self.credentials.delete()
        except Exception:
            self.settings_dialog.set_status('无法删除密钥，请检查 Windows 凭据管理器。', True)
            return
        self.settings_dialog.populate(self.settings.model, self.settings.style, self.settings.theme, False)
        self.settings_dialog.set_status('已从 Windows 凭据管理器删除密钥，监听保持暂停。')

    def test_connection(self, key, model):
        try:
            key = key.strip() or self.credentials.get()
        except Exception:
            key = None
        if not key:
            self.settings_dialog.set_status('请先输入 API Key。', True)
            return
        if not re.fullmatch(r'[A-Za-z0-9._:/-]{1,100}', model.strip()):
            self.settings_dialog.set_status('请输入有效的模型名称。', True)
            return
        if not key.isascii() or any(ch.isspace() or ord(ch) < 33 for ch in key):
            self.settings_dialog.set_status('API Key 格式不正确。', True)
            return
        self._test_id += 1
        self.settings_dialog.set_testing(True)
        self.settings_dialog.set_status('正在连接 DeepSeek…' if not self.demo else '正在模拟连接…')
        self.test_client.generate(self._test_id, '做工具时少一个不必要的步骤，往往比多一个功能更让人舒服。', key, model.strip(), '自然')

    def _test_succeeded(self, request_id, text, usage):
        if request_id != self._test_id:
            return
        self.settings_dialog.set_testing(False)
        token_note = f' · {usage["total_tokens"]} tokens' if 'total_tokens' in usage else ''
        self.settings_dialog.set_status(('模拟连接成功' if self.demo else '连接成功，模型可正常生成回复') + token_note + '。')

    def _test_failed(self, request_id, message):
        if request_id == self._test_id:
            self.settings_dialog.set_testing(False)
            self.settings_dialog.set_status(message, True)

    def cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        self.controller.shutdown()
        self.original_controller.shutdown()
        self.test_client.cancel()
        self.settings_dialog.key_input.clear()
        self.settings_dialog.hide()
        self.window.hide()
        if self.tray:
            self.tray.hide()
