"""Native original-post cards. No clipboard, networking, or storage side effects."""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QUrl, Signal, QSignalBlocker
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .ui import _button, _ComboBox, _label


ORIGINAL_STYLES = ("犀利", "幽默", "反常识", "热点")
ORIGINAL_TOPICS = ("AI工具", "GitHub开源", "模型更新", "AI编程", "AI Agent", "行业观察")


def _source_url(value: object) -> str:
    """Only offer public web links supplied as a source, never links from body text."""
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return ""
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in ("https", "http") or not hostname or parsed.username or parsed.password:
            return ""
        if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
            return ""
        try:
            if not ip_address(hostname).is_global:
                return ""
        except ValueError:
            if "." not in hostname:
                return ""
        if parsed.port not in (None, 80, 443):
            return ""
        return value
    except ValueError:
        return ""


def _weighted_length(text: str) -> int:
    # The domain function is loaded lazily so this view also works in previews.
    try:
        from .original import weighted_length
        return weighted_length(text)
    except ImportError:
        return sum(1 if ord(char) <= 0x10FF or 0x2000 <= ord(char) <= 0x200D
                   or 0x2010 <= ord(char) <= 0x201F or 0x2032 <= ord(char) <= 0x2037 else 2
                   for char in text)


class _HistoryDialog(QDialog):
    record_requested = Signal(str)
    clear_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("随手回 · 原创历史")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(460, 480)
        self._records: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(_label("原创历史", "dialogTitle"))
        top.addStretch()
        self.filter_combo = _ComboBox()
        for title, value in (("全部", "all"), ("收藏", "favorite"), ("已发布", "published")):
            self.filter_combo.addItem(title, value)
        self.filter_combo.setAccessibleName("筛选原创历史")
        top.addWidget(self.filter_combo)
        layout.addLayout(top)
        self.records_list = QListWidget()
        self.records_list.setWordWrap(True)
        self.records_list.setAccessibleName("选择历史原创内容")
        layout.addWidget(self.records_list, 1)
        self.empty_label = _label("还没有记录，先去来一条。", "muted", wrap=True)
        layout.addWidget(self.empty_label)
        row = QHBoxLayout()
        self.clear_button = _button("清空／重置历史", "quiet", focus=True)
        self.open_button = _button("查看内容", "primary", focus=True)
        self.close_button = _button("关闭", focus=True)
        for button in (self.clear_button, self.open_button, self.close_button):
            button.setAutoDefault(False)
        row.addWidget(self.clear_button)
        row.addStretch()
        row.addWidget(self.close_button)
        row.addWidget(self.open_button)
        layout.addLayout(row)
        self.filter_combo.currentIndexChanged.connect(self._render)
        self.records_list.currentRowChanged.connect(lambda row: self.open_button.setEnabled(row >= 0))
        self.records_list.itemDoubleClicked.connect(lambda item: self._open_selected())
        self.open_button.clicked.connect(self._open_selected)
        self.close_button.clicked.connect(self.close)
        self.clear_button.clicked.connect(self._confirm_clear)

    def populate(self, records: list[dict]) -> None:
        self._records = [dict(record) for record in records if isinstance(record, dict)]
        self._render()

    def _render(self) -> None:
        self.records_list.clear()
        selected = self.filter_combo.currentData()
        records = [record for record in self._records if selected == "all" or record.get(selected)]
        for record in records:
            state = " · ".join(label for key, label in (("favorite", "已收藏"), ("published", "已发布"))
                               if record.get(key))
            metadata = " · ".join(str(record[key]) for key in ("style", "topic") if record.get(key))
            heading = " · ".join(part for part in (metadata, state) if part)
            body = " ".join(str(record.get("body", "")).split())
            item = QListWidgetItem(f"{heading}\n{body[:100]}{'…' if len(body) > 100 else ''}")
            item.setData(Qt.ItemDataRole.UserRole, str(record.get("id", "")))
            self.records_list.addItem(item)
        self.empty_label.setVisible(not records)
        # Reset stays available when a damaged store could not load any records.
        self.clear_button.setEnabled(True)
        self.open_button.setEnabled(False)

    def _open_selected(self) -> None:
        item = self.records_list.currentItem()
        if item is not None and item.data(Qt.ItemDataRole.UserRole):
            self.record_requested.emit(item.data(Qt.ItemDataRole.UserRole))
            self.close()

    def _confirm_clear(self) -> None:
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle("清空原创历史")
        confirmation.setTextFormat(Qt.TextFormat.PlainText)
        confirmation.setText(f"删除全部 {len(self._records)} 条原创记录？" if self._records
                             else "清空并重置本地原创历史文件？")
        confirmation.setInformativeText("这会重置本地历史文件；收藏和已发布标记也会删除，无法恢复。")
        confirmation.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirmation.button(QMessageBox.StandardButton.Yes).setText("删除全部记录")
        confirmation.button(QMessageBox.StandardButton.Cancel).setText("取消")
        confirmation.finished.connect(lambda result: self.clear_requested.emit()
                                      if result == QMessageBox.StandardButton.Yes else None)
        confirmation.open()


class OriginalPage(QWidget):
    generate_requested = Signal(str, str)
    cancel_requested = Signal()
    copy_requested = Signal(bool)
    favorite_requested = Signal()
    published_requested = Signal()
    history_requested = Signal()
    clear_history_requested = Signal()
    record_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._post: dict | None = None
        self._busy = False
        self._url = ""
        self.history_dialog: _HistoryDialog | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        heading.addWidget(_label("写一条自己的观察", "cardTitle"))
        heading.addStretch()
        self.history_button = _button("历史", "quiet")
        self.history_button.clicked.connect(self.history_requested)
        heading.addWidget(self.history_button)
        layout.addLayout(heading)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.style_combo = _ComboBox()
        self.style_combo.addItem("随机风格", "随机")
        for item in ORIGINAL_STYLES:
            self.style_combo.addItem(item, item)
        self.style_combo.setAccessibleName("原创风格")
        self.topic_combo = _ComboBox()
        self.topic_combo.addItem("随机主题", "随机")
        for item in ORIGINAL_TOPICS:
            self.topic_combo.addItem(item, item)
        self.topic_combo.setAccessibleName("原创主题")
        filters.addWidget(self.style_combo, 1)
        filters.addWidget(self.topic_combo, 1)
        layout.addLayout(filters)

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.content_scroll.setMinimumHeight(210)
        self.content_scroll.setMaximumHeight(240)
        content = QWidget()
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 0, 5, 0)
        cards.setSpacing(10)
        self.post_card = QFrame()
        self.post_card.setObjectName("contentCard")
        post_layout = QVBoxLayout(self.post_card)
        post_layout.setContentsMargins(14, 13, 14, 14)
        post_layout.setSpacing(10)
        self.post_caption = _label("灵感，从这一条开始", "caption")
        self.post_label = _label("", "post", wrap=True)
        self.post_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.post_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.post_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.post_label.setMinimumHeight(90)
        post_layout.addWidget(self.post_caption)
        post_layout.addWidget(self.post_label)
        cards.addWidget(self.post_card)
        self.source_card = QFrame()
        self.source_card.setObjectName("sourceCard")
        source_layout = QVBoxLayout(self.source_card)
        source_layout.setContentsMargins(14, 12, 14, 12)
        source_layout.setSpacing(7)
        self.source_caption = _label("事实来源 · 与上方评论分开", "caption", wrap=True)
        source_layout.addWidget(self.source_caption)
        self.source_title_label = _label("", "cardTitle", wrap=True)
        self.source_date_label = _label("", "caption", wrap=True)
        self.source_summary_label = _label("", "source", wrap=True)
        self.source_url_label = _label("", "source", wrap=True)
        self.source_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_url_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.source_link_button = _button("打开原始来源 ↗", "quiet")
        self.source_link_button.clicked.connect(self._open_source)
        source_layout.addWidget(self.source_title_label)
        source_layout.addWidget(self.source_date_label)
        source_layout.addWidget(self.source_summary_label)
        source_layout.addWidget(self.source_url_label)
        source_layout.addWidget(self.source_link_button, 0, Qt.AlignmentFlag.AlignLeft)
        cards.addWidget(self.source_card)
        cards.addStretch()
        self.content_scroll.setWidget(content)
        layout.addWidget(self.content_scroll, 1)

        metrics = QHBoxLayout()
        self.length_label = _label("", "usage")
        self.usage_label = _label("", "usage")
        metrics.addWidget(self.length_label)
        metrics.addStretch()
        metrics.addWidget(self.usage_label)
        layout.addLayout(metrics)
        self.status_label = _label("", "status", wrap=True)
        layout.addWidget(self.status_label)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.generate_button = _button("来一条", "primary")
        self.copy_button = _button("复制全文")
        self.copy_button.setToolTip("复制正文和链接，粘贴后即可自行发布")
        self.cancel_button = _button("取消", "quiet")
        self.generate_button.clicked.connect(lambda: self.generate_requested.emit(
            str(self.style_combo.currentData()), str(self.topic_combo.currentData())))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(True))
        self.cancel_button.clicked.connect(self.cancel_requested)
        actions.addWidget(self.generate_button, 1)
        actions.addWidget(self.copy_button, 1)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        secondary = QHBoxLayout()
        secondary.setSpacing(6)
        self.favorite_button = _button("收藏", "toggle")
        self.published_button = _button("标记已发布", "toggle")
        self.copy_source_button = _button("复制并附来源", "quiet")
        self.favorite_button.setCheckable(True)
        self.published_button.setCheckable(True)
        self.favorite_button.clicked.connect(self.favorite_requested)
        self.published_button.clicked.connect(self.published_requested)
        self.copy_source_button.clicked.connect(lambda: self.copy_requested.emit(True))
        secondary.addWidget(self.favorite_button)
        secondary.addWidget(self.published_button)
        secondary.addStretch()
        secondary.addWidget(self.copy_source_button)
        # Preserve the existing action for integrations; the main button now
        # copies the complete post, so a second visible copy action is redundant.
        self.copy_source_button.hide()
        layout.addLayout(secondary)
        self.show_idle()

    def _set_status(self, message: str, state: str = "") -> None:
        self.status_label.setText(str(message))
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        has_post = bool(self._post and str(self._post.get("body", "")).strip())
        for widget in (self.style_combo, self.topic_combo, self.generate_button, self.history_button):
            widget.setEnabled(not self._busy)
        for button in (self.favorite_button, self.published_button):
            button.setEnabled(not self._busy and has_post)
        can_copy = bool(has_post and self._url
                        and _weighted_length(str(self._post.get("body", ""))) + 24 <= 280)
        self.copy_button.setEnabled(not self._busy and can_copy)
        self.source_link_button.setEnabled(not self._busy and bool(self._url))
        self.copy_source_button.setEnabled(not self._busy and can_copy)
        self.cancel_button.setVisible(self._busy)
        self.cancel_button.setEnabled(self._busy)
        if self.history_dialog is not None:
            self.history_dialog.setEnabled(not self._busy)

    def show_loading(self, message: str = "正在生成…") -> None:
        self._post = None
        self._url = ""
        self.post_caption.setText("正在准备下一条")
        self.post_label.setText(str(message))
        self.source_card.hide()
        self.length_label.clear()
        self.usage_label.clear()
        self.copy_button.setText("复制全文")
        self._set_status(str(message))
        self.content_scroll.verticalScrollBar().setValue(0)
        self.set_busy(True)

    def show_post(self, post: dict, usage: dict) -> None:
        self._post = dict(post)
        body = str(post.get("body", ""))
        self.post_label.setText(body)
        metadata = " · ".join(str(post[key]) for key in ("style", "topic") if post.get(key))
        self.post_caption.setText(metadata or "你的原创内容")
        self.generate_button.setText("换一条")
        self.copy_button.setText("复制全文")
        for button, key, yes, no in ((self.favorite_button, "favorite", "已收藏", "收藏"),
                                     (self.published_button, "published", "已发布", "标记已发布")):
            with QSignalBlocker(button):
                button.setChecked(bool(post.get(key)))
            button.setText(yes if post.get(key) else no)
        source = post.get("source")
        source = source if isinstance(source, dict) else {}
        self._url = _source_url(source.get("url"))
        is_reference = source.get("kind") == "reference"
        self.source_caption.setText("延伸阅读 · 官方参考" if is_reference else "事实来源 · 与上方评论分开")
        self.source_title_label.setText(str(source.get("title", "")))
        dates = [str(source["provider"])] if source.get("provider") else []
        published_at = str(source.get("published_at") or "")
        if is_reference:
            dates.append(published_at or "参考文档 · 未标注发布日期")
        elif published_at:
            dates.append(published_at)
        if source.get("verified_at"):
            dates.append(f"核验于 {source['verified_at']}")
        self.source_date_label.setText(" · ".join(dates))
        self.source_summary_label.setText(str(source.get("summary", "")))
        self.source_url_label.setText(self._url)
        self.source_link_button.setText("打开参考文档 ↗" if is_reference else "打开原始来源 ↗")
        self.source_link_button.setToolTip(self._url)
        self.source_card.setVisible(bool(source))
        length = _weighted_length(body) + (24 if self._url else 0)
        self.length_label.setText(f"{length} / 280 加权字符" + (" · 含链接" if self._url else ""))
        total = usage.get("total_tokens")
        if total is None and isinstance(usage.get("prompt_tokens"), int) and isinstance(usage.get("completion_tokens"), int):
            total = usage["prompt_tokens"] + usage["completion_tokens"]
        self.usage_label.setText(f"{total:,} tokens" if isinstance(total, int) and total >= 0 else "用量未返回")
        if not source:
            self._set_status("旧版内容未附链接，请重新生成", "error")
        elif not self._url:
            self._set_status("来源链接不可用，请重新生成", "error")
        elif length > 280:
            self._set_status("正文加链接超过 280 加权字符，请重新生成", "error")
        else:
            self._set_status("已生成 · 复制全文后自行发布", "ready")
        self.content_scroll.verticalScrollBar().setValue(0)
        self.set_busy(False)

    def show_error(self, message: str) -> None:
        self.show_idle(str(message))
        self._set_status("生成未完成 · 可以再试一次", "error")

    def show_idle(self, message: str = "") -> None:
        self._post = None
        self._url = ""
        self.post_caption.setText("灵感，从这一条开始")
        self.post_label.setText(str(message) or "选个风格，或把惊喜留给随机。\n点「来一条」，写下你对 AI 的观察。")
        self.source_card.hide()
        self.length_label.clear()
        self.usage_label.clear()
        self.copy_button.setText("复制全文")
        self.favorite_button.setChecked(False)
        self.published_button.setChecked(False)
        self.favorite_button.setText("收藏")
        self.published_button.setText("标记已发布")
        self._set_status("无需复制推文 · 内容生成后由你确认发布")
        self.set_busy(False)

    def show_copied(self) -> None:
        self.copy_button.setText("已复制 ✓")
        self._set_status("已复制 · 回到 X 粘贴即可", "ready")

    def _open_source(self) -> None:
        if self._url and not self._busy:
            QDesktopServices.openUrl(QUrl(self._url))

    def show_history(self, records: list[dict]) -> None:
        if self.history_dialog is None:
            self.history_dialog = _HistoryDialog(self)
            self.history_dialog.record_requested.connect(self.record_requested)
            self.history_dialog.clear_requested.connect(self.clear_history_requested)
        self.history_dialog.populate(records)
        self.history_dialog.show()
        self.history_dialog.raise_()
