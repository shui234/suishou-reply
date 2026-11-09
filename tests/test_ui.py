"""Exercise user-visible state transitions and non-activation/privacy contracts."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from suishou.ui import ReplyWindow, SettingsDialog, create_icon


@pytest.fixture(scope="module")
def ui_app():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def window(ui_app):
    widget = ReplyWindow()
    yield widget
    widget.hide()
    widget.deleteLater()


def test_floating_window_is_nonactivating_and_close_hides(window):
    flags = window.windowFlags()
    for flag in (Qt.WindowType.Tool, Qt.WindowType.FramelessWindowHint,
                 Qt.WindowType.WindowStaysOnTopHint, Qt.WindowType.WindowDoesNotAcceptFocus):
        assert flags & flag
    assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.present()
    assert window.isVisible()
    assert window.width() == 440
    pos = window.pos()
    window.close()
    assert not window.isVisible()
    window.present()
    assert window.pos() == pos


def test_state_transitions_clear_stale_reply_and_allow_explicit_retry(window):
    assert not window.copy_button.isEnabled()
    assert not window.regenerate_button.isEnabled()
    window.show_source("一条等待回复的推文")
    window.show_loading()
    assert not window.copy_button.isEnabled()
    assert not window.regenerate_button.isEnabled()
    window.show_reply("一句回复", {"prompt_tokens": 30, "completion_tokens": 8})
    assert window.copy_button.isEnabled()
    assert window.regenerate_button.isEnabled()
    assert window.usage_label.text() == "38 tokens"
    window.show_copied()
    assert "已复制" in window.copy_button.text()
    window.show_loading()
    assert "一句回复" not in window.reply_label.text()
    window.show_error("连接失败")
    assert not window.copy_button.isEnabled()
    assert window.regenerate_button.isEnabled()
    assert window.reply_label.text() == "连接失败"
    window.show_idle()
    assert not window.regenerate_button.isEnabled()


def test_external_text_is_never_interpreted_as_html(window, ui_app):
    hostile = '<img src="https://example.com/track"><b>私密文本</b>'
    window.show_source(hostile)
    window.show_reply(hostile, {})
    assert window.reply_label.text() == hostile
    assert window.source_label.text() == hostile
    for label in (window.reply_label, window.source_label, window.status_label):
        assert label.textFormat() == Qt.TextFormat.PlainText
    window.show_error(hostile)
    assert window.reply_label.text() == hostile
    dialog = SettingsDialog()
    dialog.set_status(hostile, error=True)
    assert dialog.status_label.text() == hostile
    assert dialog.status_label.textFormat() == Qt.TextFormat.PlainText
    dialog.deleteLater()


def test_programmatic_updates_do_not_issue_user_commands(window):
    listening = QSignalSpy(window.listening_requested)
    styles = QSignalSpy(window.style_changed)
    window.set_listening(True)
    window.set_style("幽默")
    assert listening.count() == 0
    assert styles.count() == 0
    assert window.listen_button.isChecked()
    assert window.style_buttons["幽默"].isChecked()
    window.listen_button.click()
    window.style_buttons["犀利"].click()
    assert listening.count() == 1 and listening.at(0) == [False]
    assert styles.count() == 1 and styles.at(0) == ["犀利"]


def test_reply_action_signals_and_light_theme(window):
    copy = QSignalSpy(window.copy_requested)
    regenerate = QSignalSpy(window.regenerate_requested)
    settings = QSignalSpy(window.settings_requested)
    window.show_source("原文")
    window.show_reply("回复", {"total_tokens": 1234})
    window.set_theme("light")
    window.copy_button.click()
    window.regenerate_button.click()
    window.settings_button.click()
    assert copy.count() == regenerate.count() == settings.count() == 1
    assert window.usage_label.text() == "1,234 tokens"
    assert "#F7FAF6" in window.styleSheet()
    assert not create_icon().isNull()


def test_demo_notice_survives_all_generation_states(window):
    window.set_demo_mode(True)
    for update in (window.show_loading, lambda: window.show_reply("回复", {}),
                   lambda: window.show_error("错误"), window.show_idle):
        update()
        assert window.subtitle_label.text() == "离线演示 · 不调用 API"


def test_modes_keep_global_listening_visible_and_present_does_not_switch(window, ui_app):
    changed = QSignalSpy(window.mode_changed)
    window.mode_buttons["original"].click()
    window.present()
    ui_app.processEvents()
    assert window.mode == "original"
    assert window.original_page.isVisible()
    assert window.listen_button.isVisible()
    assert changed.at(0) == ["original"]
    window.show_source("新复制的文本")
    window.show_reply("回复", {})
    window.present()
    assert window.mode == "original"
    window.set_mode("reply")
    assert window.reply_label.text() == "回复"
    assert window.reply_label.isVisible()
    assert window.listen_button.isVisible()
    assert window.width() <= 520
    assert window.height() <= window.screen().availableGeometry().height()


def test_small_logical_work_area_keeps_global_controls_and_scrolls_to_actions(window, ui_app, monkeypatch):
    class SmallScreen:
        def availableGeometry(self):
            return QRect(0, 0, 1093, 600)

    monkeypatch.setattr(window, "screen", lambda: SmallScreen())
    window.set_mode("original")
    window.original_page.show_post({"id": "small-screen", "body": "可复制的原创内容。",
                                    "style": "犀利", "topic": "AI工具"}, {})
    window.present()
    ui_app.processEvents()
    assert window.height() <= 576
    assert window.width() == 440
    for button in (window.listen_button, *window.mode_buttons.values()):
        assert window.rect().contains(button.mapTo(window, QPoint(0, 0)))
        assert window.rect().contains(button.mapTo(window, button.rect().bottomRight()))
    copied = QSignalSpy(window.original_page.copy_requested)
    actions = (window.original_page.generate_button, window.original_page.copy_button,
               window.original_page.favorite_button, window.original_page.published_button)
    for button in actions:
        window.page_scroll.ensureWidgetVisible(button, 0, 0)
        ui_app.processEvents()
        viewport = window.page_scroll.viewport()
        assert viewport.rect().contains(button.mapTo(viewport, QPoint(0, 0)))
        assert viewport.rect().contains(button.mapTo(viewport, button.rect().bottomRight()))
    window.original_page.copy_button.click()
    assert copied.count() == 1
    window.set_mode("reply")
    window.present()
    ui_app.processEvents()
    assert window.height() <= 576
    window.page_scroll.ensureWidgetVisible(window.copy_button, 0, 0)
    ui_app.processEvents()
    viewport = window.page_scroll.viewport()
    assert viewport.rect().contains(window.copy_button.mapTo(viewport, window.copy_button.rect().bottomRight()))


def test_settings_preserve_existing_secret_and_save_waits_for_controller(ui_app):
    dialog = SettingsDialog()
    dialog.populate("deepseek-flash", "犀利", "light", True)
    dialog.show()
    saves = QSignalSpy(dialog.save_requested)
    tests = QSignalSpy(dialog.test_requested)
    deletes = QSignalSpy(dialog.delete_key_requested)
    assert dialog.key_input.text() == ""
    assert dialog.key_input.echoMode() == QLineEdit.EchoMode.Password
    dialog.test_button.click()
    assert tests.at(0) == ["", "deepseek-flash"]
    dialog.save_button.click()
    assert saves.at(0) == ["", "deepseek-flash", "犀利", "light"]
    assert dialog.isVisible()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.delete_key_button.click()
    assert deletes.count() == 1
    dialog.key_input.setText("  synthetic-key  ")
    dialog.model_input.setText("  model-name  ")
    dialog.save_button.click()
    assert saves.at(1)[:2] == ["synthetic-key", "model-name"]
    dialog.reject()
    dialog.deleteLater()


def test_testing_disables_duplicate_commands_and_escape_closes(ui_app):
    dialog = SettingsDialog()
    dialog.populate("deepseek-flash", "自然", "dark", True)
    dialog.show()
    dialog.set_testing(True)
    dialog.set_testing(True)
    assert not dialog.test_button.isEnabled()
    assert not dialog.save_button.isEnabled()
    assert not dialog.delete_key_button.isEnabled()
    dialog.set_testing(False)
    assert dialog.test_button.isEnabled()
    assert dialog.save_button.isEnabled()
    assert dialog.delete_key_button.isEnabled()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    dialog.populate("deepseek-flash", "自然", "dark", False)
    assert not dialog.delete_key_button.isEnabled()
    dialog.deleteLater()
