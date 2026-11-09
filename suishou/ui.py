"""Native, non-activating presentation for 随手回.

This module deliberately knows nothing about the clipboard, credentials, or HTTP.
All text received from outside the UI is rendered as plain text.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, Signal, QSignalBlocker
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


STYLES = ("自然", "犀利", "幽默")
PRIVACY_NOTICE = (
    "开启监听后，符合条件的剪贴板文本将发送给 DeepSeek。"
    "敏感文本过滤无法保证识别所有秘密，请复制私密内容前暂停。"
)

_PALETTES = {
    "dark": {
        "background": "#151C19", "field": "#1D2722", "line": "#334139",
        "text": "#EEF5EF", "muted": "#A8BAAF", "dim": "#8DA398",
        "accent": "#AFEBC7", "accent_hover": "#C3F4D5", "accent_text": "#173325",
        "hover": "#2B3931", "disabled": "#66786D", "error": "#FFBCB1",
    },
    "light": {
        "background": "#F7FAF6", "field": "#EDF2EC", "line": "#D6E0D4",
        "text": "#203729", "muted": "#566B5E", "dim": "#63786A",
        "accent": "#215C3C", "accent_hover": "#2D714C", "accent_text": "#F5FFF7",
        "hover": "#E1EADF", "disabled": "#839388", "error": "#B33C2A",
    },
}


def create_icon(size: int = 64) -> QIcon:
    """Return the app's mint speech bubble / return-arrow icon, without assets."""
    size = max(16, int(size))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 64, size / 64)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#AFEBC7"))
    painter.drawRoundedRect(3, 3, 58, 58, 17, 17)
    bubble = QPainterPath()
    bubble.moveTo(17, 19)
    bubble.lineTo(47, 19)
    bubble.quadTo(50, 19, 50, 23)
    bubble.lineTo(50, 39)
    bubble.quadTo(50, 43, 46, 43)
    bubble.lineTo(29, 43)
    bubble.lineTo(20, 49)
    bubble.lineTo(20, 43)
    bubble.lineTo(17, 43)
    bubble.quadTo(14, 43, 14, 39)
    bubble.lineTo(14, 23)
    bubble.quadTo(14, 19, 17, 19)
    painter.setBrush(QColor("#193C2A"))
    painter.drawPath(bubble)
    painter.setPen(QPen(QColor("#AFEBC7"), 3.2, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    arrow = QPainterPath()
    arrow.moveTo(41, 26)
    arrow.lineTo(41, 31)
    arrow.quadTo(41, 35, 37, 35)
    arrow.lineTo(25, 35)
    arrow.moveTo(29, 30)
    arrow.lineTo(24, 35)
    arrow.lineTo(29, 39)
    painter.drawPath(arrow)
    painter.end()
    return QIcon(pixmap)


def _label(text: str = "", name: str = "", *, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    if name:
        label.setObjectName(name)
    return label


def _button(text: str, name: str = "", *, focus: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(34)
    if name:
        button.setObjectName(name)
    if not focus:
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button


class _ComboBox(QComboBox):
    """Keep a visible native dropdown affordance under either stylesheet."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#7C9487"), 1.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = self.width() - 18, self.height() // 2
        painter.drawLine(x - 4, y - 2, x, y + 2)
        painter.drawLine(x, y + 2, x + 4, y - 2)
        painter.end()


def _stylesheet(theme: str) -> str:
    p = _PALETTES.get(theme, _PALETTES["dark"])
    return f"""
        QWidget {{ font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
                   font-size: 12px; color: {p['text']}; }}
        QWidget#surface, QDialog {{ background: {p['background']}; }}
        QWidget#surface {{ border: 1px solid {p['line']}; border-radius: 17px; }}
        QLabel {{ background: transparent; border: none; }}
        QLabel#wordmark {{ font-size: 18px; font-weight: 600; }}
        QLabel#subtitle, QLabel#muted, QLabel#source {{ color: {p['muted']}; }}
        QLabel#subtitle {{ font-size: 10px; }}
        QLabel#caption {{ font-size: 11px; color: {p['dim']}; }}
        QLabel#reply {{ font-size: 16px; }}
        QLabel#post {{ font-size: 16px; line-height: 1.6; }}
        QLabel#cardTitle {{ font-size: 13px; font-weight: 600; }}
        QFrame#contentCard, QFrame#sourceCard {{ background: {p['field']};
                                              border: 1px solid {p['line']}; border-radius: 10px; }}
        QLabel#privacy {{ font-size: 10px; color: {p['muted']}; }}
        QLabel#status {{ color: {p['muted']}; font-size: 11px; }}
        QLabel#status[state='error'] {{ color: {p['error']}; }}
        QLabel#status[state='ready'] {{ color: {p['accent']}; }}
        QLabel#usage {{ font-size: 10px; color: {p['dim']}; }}
        QLabel#dialogTitle {{ font-size: 21px; font-weight: 600; }}
        QLabel#keyHint {{ color: {p['muted']}; font-size: 11px; }}
        QFrame#divider {{ background: {p['line']}; border: 0; max-height: 1px; }}
        QPushButton {{ border: 1px solid {p['line']}; border-radius: 8px;
                      background: transparent; padding: 0 12px; }}
        QPushButton:hover {{ background: {p['hover']}; }}
        QPushButton:pressed {{ background: {p['field']}; }}
        QPushButton:focus {{ border: 1px solid {p['accent']}; }}
        QPushButton:disabled {{ color: {p['disabled']}; border-color: {p['line']}; }}
        QPushButton#primary {{ background: {p['accent']}; color: {p['accent_text']};
                              border-color: {p['accent']}; font-weight: 600; }}
        QPushButton#primary:hover {{ background: {p['accent_hover']}; }}
        QPushButton#primary:disabled {{ background: {p['field']};
                                       color: {p['disabled']}; border-color: {p['line']}; }}
        QPushButton#quiet {{ border: 0; color: {p['muted']}; padding: 0 8px; }}
        QPushButton#deleteKey {{ border: 0; color: {p['muted']}; text-align: left;
                                padding: 0; font-size: 11px; }}
        QPushButton#deleteKey:hover {{ color: {p['error']}; background: transparent; }}
        QPushButton#listen {{ border-radius: 14px; min-height: 28px; padding: 0 13px;
                             color: {p['muted']}; background: {p['field']}; }}
        QPushButton#listen:checked {{ background: {p['accent']};
                                     color: {p['accent_text']}; border-color: {p['accent']}; }}
        QPushButton#style {{ min-height: 30px; border: 0; border-radius: 7px;
                            color: {p['muted']}; padding: 0 20px; }}
        QPushButton#style:checked {{ background: {p['field']}; color: {p['text']};
                                    font-weight: 600; }}
        QPushButton#mode {{ min-height: 36px; color: {p['muted']}; }}
        QPushButton#mode:checked {{ background: {p['field']}; color: {p['accent']};
                                   border-color: {p['accent']}; font-weight: 600; }}
        QPushButton#toggle:checked {{ color: {p['accent']}; border-color: {p['accent']}; }}
        QListWidget {{ background: {p['field']}; border: 1px solid {p['line']};
                       border-radius: 8px; padding: 5px; }}
        QListWidget::item {{ padding: 10px 6px; border-bottom: 1px solid {p['line']}; }}
        QListWidget::item:selected {{ background: {p['hover']}; color: {p['accent']}; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: 0; }}
        QScrollBar:vertical {{ width: 5px; background: transparent; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {p['line']}; border-radius: 2px;
                                      min-height: 20px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QLineEdit, QComboBox {{ background: {p['field']}; border: 1px solid {p['line']};
                              border-radius: 7px; padding: 8px 10px; min-height: 20px; }}
        QLineEdit:focus, QComboBox:focus {{ border-color: {p['accent']}; }}
        QComboBox QAbstractItemView {{ background: {p['background']}; color: {p['text']};
                                      selection-background-color: {p['hover']}; }}
        QComboBox::drop-down {{ border: 0; width: 25px; }}
        QComboBox::down-arrow {{ image: none; }}
        QToolTip {{ background: {p['field']}; color: {p['text']}; border: 1px solid {p['line']}; }}
    """


class ReplyWindow(QWidget):
    copy_requested = Signal()
    regenerate_requested = Signal()
    settings_requested = Signal()
    listening_requested = Signal(bool)
    style_changed = Signal(str)
    mode_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowTitle("随手回")
        self.setWindowIcon(create_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedWidth(440)
        self._theme = "dark"
        self._has_source = False
        self._placed = False
        self._drag_offset: QPoint | None = None
        self.mode = "reply"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        self._surface = surface
        surface.setObjectName("surface")
        outer.addWidget(surface)
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(22, 21, 22, 18)
        layout.setSpacing(0)

        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        icon = _label()
        icon.setPixmap(create_icon(64).pixmap(34, 34))
        icon.setFixedSize(34, 34)
        header.addWidget(icon)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        title = _label("随手回", "wordmark")
        subtitle = _label("一句好回复，刚刚好。", "subtitle")
        self.subtitle_label = subtitle
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.settings_button = _button("设置", "quiet")
        self.settings_button.setAccessibleName("打开设置")
        self.settings_button.clicked.connect(self.settings_requested)
        header.addWidget(self.settings_button)
        self.hide_button = _button("×", "quiet")
        self.hide_button.setFixedWidth(26)
        self.hide_button.setAccessibleName("隐藏窗口")
        self.hide_button.clicked.connect(self.close)
        header.addWidget(self.hide_button)
        for widget in (self.header, icon, title, subtitle):
            widget.installEventFilter(self)
        layout.addWidget(self.header)
        layout.addSpacing(18)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode, text in (("reply", "推文回复"), ("original", "来一条")):
            button = _button(text, "mode")
            button.setCheckable(True)
            button.setAccessibleName(f"切换到{text}")
            self._mode_group.addButton(button)
            self.mode_buttons[mode] = button
            button.clicked.connect(lambda checked=False, selected=mode: self.set_mode(selected))
            mode_row.addWidget(button, 1)
        self.mode_buttons["reply"].setChecked(True)
        layout.addLayout(mode_row)
        layout.addSpacing(14)

        listen_row = QHBoxLayout()
        listen_row.addWidget(_label("剪贴板监听", "muted"))
        listen_row.addStretch()
        self.listen_button = _button("○  已暂停", "listen")
        self.listen_button.setCheckable(True)
        self.listen_button.setMinimumHeight(28)
        self.listen_button.setAccessibleName("开启或暂停剪贴板监听")
        self.listen_button.toggled.connect(self.listening_requested)
        listen_row.addWidget(self.listen_button)
        layout.addLayout(listen_row)
        layout.addSpacing(16)

        shell_layout = layout
        self.pages = QStackedWidget()
        self.reply_page = QWidget()
        layout = QVBoxLayout(self.reply_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        styles = QHBoxLayout()
        styles.setSpacing(3)
        self._style_group = QButtonGroup(self)
        self._style_group.setExclusive(True)
        self.style_buttons: dict[str, QPushButton] = {}
        for name in STYLES:
            button = _button(name, "style")
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.setAccessibleName(f"{name}回复风格")
            self._style_group.addButton(button)
            self.style_buttons[name] = button
            styles.addWidget(button, 1)
        self._style_group.buttonClicked.connect(lambda button: self.style_changed.emit(button.text()))
        layout.addLayout(styles)
        layout.addSpacing(16)

        source_row = QHBoxLayout()
        source_row.setAlignment(Qt.AlignmentFlag.AlignTop)
        source_row.setSpacing(9)
        source_row.addWidget(_label("原文", "caption"))
        self.source_label = _label("等待你复制一条推文", "source", wrap=True)
        self.source_label.setMinimumHeight(34)
        self.source_label.setMaximumHeight(40)
        source_row.addWidget(self.source_label, 1)
        layout.addLayout(source_row)
        layout.addSpacing(12)
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(15)
        layout.addWidget(_label("你的回复", "caption"))
        layout.addSpacing(8)

        self.reply_label = _label("", "reply", wrap=True)
        self.reply_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.reply_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.reply_scroll = QScrollArea()
        self.reply_scroll.setWidgetResizable(True)
        self.reply_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.reply_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reply_scroll.setWidget(self.reply_label)
        self.reply_scroll.setFixedHeight(116)
        layout.addWidget(self.reply_scroll)
        layout.addSpacing(12)

        status_row = QHBoxLayout()
        status_row.setSpacing(5)
        self.status_label = _label("", "status", wrap=True)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.usage_label = _label("", "usage")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.usage_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(status_row)
        layout.addSpacing(14)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_button = _button("复制回复", "primary")
        self.regenerate_button = _button("换一条")
        self.close_button = _button("关闭", "quiet")
        self.copy_button.clicked.connect(self.copy_requested)
        self.regenerate_button.clicked.connect(self.regenerate_requested)
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.copy_button, 1)
        actions.addWidget(self.regenerate_button)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        self.pages.addWidget(self.reply_page)
        from .original_ui import OriginalPage
        self.original_page = OriginalPage()
        self.pages.addWidget(self.original_page)
        layout = shell_layout
        # Keep global controls in view while the full page (including its actions)
        # can scroll on high-DPI screens with a short logical work area.
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.page_scroll.setMinimumHeight(120)
        self.page_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.page_scroll.setWidget(self.pages)
        layout.addWidget(self.page_scroll)
        layout.addSpacing(15)
        privacy = _label(PRIVACY_NOTICE, "privacy", wrap=True)
        self.privacy_label = privacy
        layout.addWidget(privacy)
        self.set_style("自然")
        self.set_theme("dark")
        self.show_idle()

    def set_mode(self, mode: str) -> None:
        selected = mode if mode in self.mode_buttons else "reply"
        changed = selected != self.mode
        self.mode = selected
        self.mode_buttons[selected].setChecked(True)
        self.pages.setCurrentWidget(self.original_page if selected == "original" else self.reply_page)
        self.page_scroll.verticalScrollBar().setValue(0)
        self.privacy_label.setText(
            '原创内容与收藏保存在本机，可在历史中清理。生成时将灵感和近期原创发送给 DeepSeek；仅热点模式获取官方公开来源。'
            if selected == 'original' else PRIVACY_NOTICE)
        if changed:
            self.mode_changed.emit(selected)

    def _set_status(self, text: str, state: str = "") -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_listening(self, enabled: bool) -> None:
        with QSignalBlocker(self.listen_button):
            self.listen_button.setChecked(bool(enabled))
        self.listen_button.setText("●  监听中" if enabled else "○  已暂停")
        self.listen_button.setToolTip("点击暂停监听" if enabled else "点击开始监听新的复制内容")

    def set_style(self, style: str) -> None:
        self.style_buttons.get(style, self.style_buttons["自然"]).setChecked(True)

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in _PALETTES else "dark"
        self.setStyleSheet(_stylesheet(self._theme))

    def set_demo_mode(self, enabled: bool) -> None:
        self.subtitle_label.setText("离线演示 · 不调用 API" if enabled else "在 AI 的噪声里，找有用的信号。")

    def show_source(self, text: str) -> None:
        self._has_source = bool(text.strip())
        summary = " ".join(text.split())
        self.source_label.setText(summary[:91] + "…" if len(summary) > 92 else summary)

    def show_loading(self) -> None:
        self.reply_label.setText("正在想一句合适的回复…")
        self.reply_scroll.verticalScrollBar().setValue(0)
        self._set_status("DeepSeek 正在生成")
        self.usage_label.clear()
        self.copy_button.setText("复制回复")
        self.copy_button.setEnabled(False)
        self.regenerate_button.setEnabled(False)

    def show_reply(self, text: str, usage: dict) -> None:
        self.reply_label.setText(text)
        self.reply_scroll.verticalScrollBar().setValue(0)
        self.copy_button.setText("复制回复")
        self.copy_button.setEnabled(bool(text.strip()))
        self.regenerate_button.setEnabled(self._has_source)
        self._set_status("已生成 · 复制后自行粘贴", "ready")
        total = usage.get("total_tokens")
        if total is None:
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            if isinstance(prompt, int) and isinstance(completion, int):
                total = prompt + completion
        self.usage_label.setText(f"{total:,} tokens" if isinstance(total, int) and total >= 0 else "用量未返回")

    def show_error(self, message: str) -> None:
        self.reply_label.setText(message)
        self.reply_scroll.verticalScrollBar().setValue(0)
        self._set_status("生成未完成", "error")
        self.usage_label.clear()
        self.copy_button.setText("复制回复")
        self.copy_button.setEnabled(False)
        self.regenerate_button.setEnabled(self._has_source)

    def show_idle(self, message: str = "开启监听后，复制一条推文即可。") -> None:
        self.reply_label.setText(message)
        self.reply_scroll.verticalScrollBar().setValue(0)
        self._has_source = False
        self.source_label.setText("等待你复制一条推文")
        self._set_status("等待新的复制内容" if self.listen_button.isChecked() else "监听已暂停")
        self.usage_label.clear()
        self.copy_button.setText("复制回复")
        self.copy_button.setEnabled(False)
        self.regenerate_button.setEnabled(False)

    def show_copied(self) -> None:
        self.copy_button.setText("已复制 ✓")
        self._set_status("已复制 · 回到 X 粘贴即可", "ready")

    def present(self) -> None:
        """Show in the work-area corner once, keeping the user's active app active."""
        screen = self.screen() or QApplication.primaryScreen()
        self._surface.layout().activate()
        preferred_height = (self._surface.sizeHint().height()
                            - self.page_scroll.sizeHint().height() + self.pages.sizeHint().height())
        if screen:
            limit = max(1, screen.availableGeometry().height() - 24)
            self.setMaximumHeight(limit)
            preferred_height = min(preferred_height, limit)
        self.resize(self.width(), preferred_height)
        if not self._placed:
            screen = self.screen() or QApplication.primaryScreen()
            if screen:
                area = screen.availableGeometry()
                self.move(max(area.left(), area.right() - self.width() - 23),
                          max(area.top(), area.bottom() - self.height() - 23))
            self._placed = True
        self.show()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return True
        if event.type() == QEvent.Type.MouseMove and self._drag_offset is not None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._drag_offset = None
        return super().eventFilter(watched, event)


class SettingsDialog(QDialog):
    save_requested = Signal(str, str, str, str)
    test_requested = Signal(str, str)
    delete_key_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("随手回 · 设置")
        self.setWindowIcon(create_icon())
        self.setModal(True)
        self.setMinimumWidth(480)
        self.resize(480, 610)
        self.setStyleSheet(_stylesheet("dark"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 24, 25, 22)
        layout.setSpacing(14)
        layout.addWidget(_label("连接 DeepSeek", "dialogTitle"))
        layout.addWidget(_label("设置期间已暂停监听，保存后仍由你决定何时开启。", "muted", wrap=True))

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("输入 DeepSeek API Key")
        self.key_input.setAccessibleName("DeepSeek API Key")
        form.addRow("API Key", self.key_input)
        self.key_hint = _label("尚未保存 API Key。", "keyHint", wrap=True)
        form.addRow("", self.key_hint)
        endpoint = _label("https://api.deepseek.com", "muted")
        endpoint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("服务地址", endpoint)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("输入 DeepSeek 模型名称")
        self.model_input.setAccessibleName("DeepSeek 模型")
        form.addRow("模型", self.model_input)
        form.addRow("", _label("默认关闭思考模式，让回复更快、更省。", "keyHint", wrap=True))
        self.style_combo = _ComboBox()
        self.style_combo.addItems(STYLES)
        self.style_combo.setAccessibleName("默认回复风格")
        form.addRow("回复风格", self.style_combo)
        self.theme_combo = _ComboBox()
        self.theme_combo.addItem("深色 · 松墨", "dark")
        self.theme_combo.addItem("浅色 · 薄荷", "light")
        self.theme_combo.setAccessibleName("界面主题")
        form.addRow("界面主题", self.theme_combo)
        layout.addLayout(form)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addWidget(_label(PRIVACY_NOTICE, "muted", wrap=True))
        layout.addWidget(_label("测试连接会发送一条简短请求，可能消耗少量 tokens。", "keyHint", wrap=True))
        self.status_label = _label("", "status", wrap=True)
        self.status_label.setMinimumHeight(32)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.delete_key_button = _button("删除已保存的 API Key", "deleteKey", focus=True)
        self.delete_key_button.setAutoDefault(False)
        self.delete_key_button.clicked.connect(self.delete_key_requested)
        layout.addWidget(self.delete_key_button, 0, Qt.AlignmentFlag.AlignLeft)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.test_button = _button("测试连接", focus=True)
        self.test_button.setAutoDefault(False)
        self.test_button.clicked.connect(self._request_test)
        self.cancel_button = _button("取消", focus=True)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = _button("保存设置", "primary", focus=True)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._request_save)
        buttons.addWidget(self.test_button)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.populate("", "自然", "dark", False)

    def populate(self, model: str, style: str, theme: str, has_key: bool) -> None:
        # Never rehydrate a stored secret into a widget or expose a masked prefix.
        self.key_input.clear()
        self.key_input.setPlaceholderText("已保存；留空保留，输入新 Key 替换" if has_key else "输入 DeepSeek API Key")
        self.key_hint.setText("已保存 API Key；不会在此显示。" if has_key else "尚未保存 API Key。")
        self.model_input.setText(model)
        self.style_combo.setCurrentText(style if style in STYLES else "自然")
        index = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(max(0, index))
        self.delete_key_button.setEnabled(has_key)
        self.setStyleSheet(_stylesheet(theme))
        self.set_status("")
        self.set_testing(False)

    def _request_save(self) -> None:
        self.save_requested.emit(self.key_input.text().strip(), self.model_input.text().strip(),
                                 self.style_combo.currentText(), self.theme_combo.currentData())

    def _request_test(self) -> None:
        self.test_requested.emit(self.key_input.text().strip(), self.model_input.text().strip())

    def set_status(self, message: str, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("state", "error" if error else "ready")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_testing(self, busy: bool) -> None:
        self.test_button.setText("正在测试…" if busy else "测试连接")
        self.test_button.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.key_input.setEnabled(not busy)
        self.model_input.setEnabled(not busy)
        if busy:
            if not hasattr(self, "_delete_was_enabled"):
                self._delete_was_enabled = self.delete_key_button.isEnabled()
            self.delete_key_button.setEnabled(False)
        elif hasattr(self, "_delete_was_enabled"):
            self.delete_key_button.setEnabled(self._delete_was_enabled)
            del self._delete_was_enabled
