"""Original drafting UI contracts: explicit actions, safe text, and retained state."""

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QMessageBox

from suishou.ui import ReplyWindow


@pytest.fixture
def page(qapp):
    window = ReplyWindow()
    window.set_mode("original")
    window.present()
    yield window.original_page
    for dialog in window.findChildren(QMessageBox):
        dialog.reject()
    window.hide()
    window.deleteLater()


def post(**changes):
    record = {"id": "post-1", "body": "AI 工具越多，越要想清楚问题。", "style": "犀利",
              "topic": "AI工具", "source": None, "favorite": False, "published": False}
    record.update(changes)
    return record


def reference(**changes):
    source = {"title": "GitHub Copilot 文档", "summary": "官方使用说明，供进一步阅读。",
              "url": "https://docs.github.com/en/copilot", "provider": "GitHub Docs",
              "kind": "reference", "published_at": "参考文档 · 未标注发布日期", "verified_at": "2026-11-09"}
    source.update(changes)
    return source


def test_generate_defaults_and_selected_values_do_not_need_clipboard(page):
    generated = QSignalSpy(page.generate_requested)
    page.generate_button.click()
    assert generated.at(0) == ["随机", "随机"]
    page.style_combo.setCurrentIndex(page.style_combo.findData("幽默"))
    page.topic_combo.setCurrentIndex(page.topic_combo.findData("AI编程"))
    page.generate_button.click()
    assert generated.at(1) == ["幽默", "AI编程"]
    assert not page.copy_button.isEnabled()


def test_loading_clears_old_content_and_blocks_duplicate_actions(page):
    page.show_post(post(), {"total_tokens": 43})
    page.show_loading("正在查找来源…")
    assert "AI 工具越多" not in page.post_label.text()
    for button in (page.generate_button, page.copy_button, page.favorite_button,
                   page.published_button, page.copy_source_button, page.history_button):
        assert not button.isEnabled()
    assert not page.style_combo.isEnabled()
    cancelled = QSignalSpy(page.cancel_requested)
    page.cancel_button.click()
    assert cancelled.count() == 1
    page.show_error("暂时无法连接")
    assert page.generate_button.isEnabled()
    assert not page.copy_button.isEnabled()
    assert page.status_label.property("state") == "error"


def test_post_actions_and_usage_change_with_record_state(page):
    copied = QSignalSpy(page.copy_requested)
    favorite = QSignalSpy(page.favorite_requested)
    published = QSignalSpy(page.published_requested)
    page.show_post(post(body="AI你好", source=reference()), {"prompt_tokens": 34, "completion_tokens": 9})
    assert "43 tokens" in page.usage_label.text()
    assert "30 / 280" in page.length_label.text()
    assert "含链接" in page.length_label.text()
    assert page.generate_button.text() == "换一条"
    assert page.copy_button.text() == "复制全文"
    assert "正文" in page.copy_button.toolTip() and "链接" in page.copy_button.toolTip()
    assert not page.copy_source_button.isVisible()
    page.copy_button.click()
    page.favorite_button.click()
    page.published_button.click()
    assert copied.at(0) == [True]
    assert favorite.count() == published.count() == 1
    page.show_post(post(favorite=True, published=True), {})
    assert page.favorite_button.isChecked()
    assert page.published_button.isChecked()
    page.show_copied()
    assert "已复制" in page.copy_button.text()
    page.show_idle()
    assert not page.copy_button.isEnabled()


def test_all_remote_strings_are_plain_text_and_source_is_separate(page, monkeypatch):
    hostile = '<b>AI</b><img src="https://example.com/track">'
    source = {"title": hostile, "summary": hostile, "url": "https://github.com/openai/codex",
              "published_at": "2026-11-09", "provider": "GitHub"}
    page.show_post(post(body=hostile, source=source), {})
    assert page.post_label.text() == hostile
    assert page.source_title_label.text() == hostile
    assert page.source_summary_label.text() == hostile
    assert page.source_url_label.text() == source["url"]
    assert page.source_url_label.wordWrap()
    assert page.source_url_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    assert page.source_card.isVisible()
    for label in page.findChildren(QLabel):
        assert label.textFormat() == Qt.TextFormat.PlainText
    opened = []
    monkeypatch.setattr("suishou.original_ui.QDesktopServices.openUrl", lambda url: opened.append(url.toString()))
    page.source_link_button.click()
    assert opened == [source["url"]]
    copied = QSignalSpy(page.copy_requested)
    page.copy_source_button.click()
    assert copied.at(0) == [True]


@pytest.mark.parametrize("url", ["file:///C:/secret", "javascript:alert(1)", "http://localhost/a",
                                  "https://127.0.0.1/a", "https://user:password@example.com/a"])
def test_unsafe_source_urls_cannot_open(page, url):
    page.show_post(post(source={"title": "来源", "url": url}), {})
    assert not page.source_link_button.isEnabled()
    assert not page.copy_button.isEnabled()
    assert not page.copy_source_button.isEnabled()


@pytest.mark.parametrize("published_at, caption", [
    ("", "参考文档 · 未标注发布日期"),
    ("参考文档 · 未标注发布日期", "参考文档 · 未标注发布日期"),
    ("参考文章 · 2024-12-19", "参考文章 · 2024-12-19"),
])
def test_reference_dates_are_distinct_from_news_and_actual_verification_is_shown(page, published_at, caption):
    page.show_post(post(source=reference(published_at=published_at)), {})
    assert page.source_caption.text() == "延伸阅读 · 官方参考"
    assert page.source_date_label.text() == f"GitHub Docs · {caption} · 核验于 2026-11-09"
    page.show_post(post(source=reference(kind="news", published_at="2026-11-08", verified_at="")), {})
    assert page.source_caption.text() == "事实来源 · 与上方评论分开"
    assert "2026-11-08" in page.source_date_label.text()
    assert "参考文档" not in page.source_date_label.text()


def test_legacy_post_without_link_stays_readable_but_cannot_copy(page):
    copied = QSignalSpy(page.copy_requested)
    favorite = QSignalSpy(page.favorite_requested)
    published = QSignalSpy(page.published_requested)
    record = post()
    page.show_post(record, {})
    assert page.post_label.text() == record["body"]
    assert page.status_label.text() == "旧版内容未附链接，请重新生成"
    assert not page.copy_button.isEnabled()
    assert not page.copy_source_button.isEnabled()
    page.copy_button.click()
    page.copy_source_button.click()
    page.favorite_button.click()
    page.published_button.click()
    assert copied.count() == 0
    assert favorite.count() == published.count() == 1


@pytest.mark.parametrize("body, total, can_copy", [("中" * 128, 280, True), ("中" * 129, 282, False)])
def test_full_copy_limit_includes_the_newline_and_link(page, body, total, can_copy):
    copied = QSignalSpy(page.copy_requested)
    page.show_post(post(body=body, source=reference()), {})
    assert f"{total} / 280" in page.length_label.text()
    assert page.copy_button.isEnabled() == can_copy
    assert page.copy_source_button.isEnabled() == can_copy
    page.copy_button.click()
    assert copied.count() == int(can_copy)
    if not can_copy:
        assert page.status_label.property("state") == "error"
        assert "超过" in page.status_label.text()
        assert page.favorite_button.isEnabled() and page.published_button.isEnabled()


def test_source_url_and_actions_fit_small_logical_screen(page, qapp, monkeypatch):
    class SmallScreen:
        def availableGeometry(self):
            return QRect(0, 0, 1093, 600)

    window = page.window()
    monkeypatch.setattr(window, "screen", lambda: SmallScreen())
    url = "https://docs.example.com/" + "a" * 150 + "/" + "b" * 150
    page.show_post(post(body="中" * 120 + "🧩", source=reference(url=url)), {})
    window.present()
    qapp.processEvents()
    assert window.width() == 440 and window.height() <= 576
    assert page.source_url_label.text() == url
    assert page.content_scroll.horizontalScrollBar().maximum() == 0
    page.content_scroll.ensureWidgetVisible(page.source_url_label, 0, 0)
    qapp.processEvents()
    source_viewport = page.content_scroll.viewport()
    assert 0 <= page.source_url_label.mapTo(source_viewport, QPoint()).x()
    assert page.source_url_label.mapTo(source_viewport, page.source_url_label.rect().topRight()).x() < source_viewport.width()
    for button in (page.generate_button, page.copy_button, page.favorite_button, page.published_button):
        window.page_scroll.ensureWidgetVisible(button, 0, 0)
        qapp.processEvents()
        viewport = window.page_scroll.viewport()
        assert viewport.rect().contains(button.mapTo(viewport, QPoint()))
        assert viewport.rect().contains(button.mapTo(viewport, button.rect().bottomRight()))


def test_history_filters_and_opens_selected_record(page):
    records = [post(), post(id="post-2", body="收藏的内容", favorite=True),
               post(id="post-3", body="已发布的内容", published=True)]
    selected = QSignalSpy(page.record_requested)
    page.show_history(records)
    dialog = page.history_dialog
    assert dialog.isVisible()
    assert dialog.records_list.count() == 3
    dialog.filter_combo.setCurrentIndex(dialog.filter_combo.findData("favorite"))
    assert dialog.records_list.count() == 1
    dialog.records_list.setCurrentRow(0)
    dialog.open_button.click()
    assert selected.at(0) == ["post-2"]
    page.show_history(records)
    dialog = page.history_dialog
    dialog.filter_combo.setCurrentIndex(dialog.filter_combo.findData("published"))
    assert dialog.records_list.count() == 1
    dialog.records_list.setCurrentRow(0)
    dialog.open_button.click()
    assert selected.at(1) == ["post-3"]


def test_clear_history_requires_explicit_in_app_confirmation(page, qapp):
    cleared = QSignalSpy(page.clear_history_requested)
    page.show_history([post()])
    page.history_dialog.clear_button.click()
    qapp.processEvents()
    confirmation = page.history_dialog.findChild(QMessageBox)
    assert confirmation is not None and confirmation.isVisible()
    assert cleared.count() == 0
    confirmation.button(QMessageBox.StandardButton.Cancel).click()
    assert cleared.count() == 0
    page.history_dialog.clear_button.click()
    qapp.processEvents()
    confirmation = next(dialog for dialog in page.history_dialog.findChildren(QMessageBox) if dialog.isVisible())
    confirmation.button(QMessageBox.StandardButton.Yes).click()
    assert cleared.count() == 1


def test_busy_page_blocks_already_open_history_actions(page):
    page.show_history([post()])
    page.show_loading()
    assert not page.history_dialog.isEnabled()
    page.show_error("连接失败")
    assert page.history_dialog.isEnabled()


def test_empty_history_can_still_reset_a_corrupt_store(page, qapp):
    page.show_history([])
    assert page.history_dialog.clear_button.isEnabled()
    page.history_dialog.clear_button.click()
    qapp.processEvents()
    confirmation = page.history_dialog.findChild(QMessageBox)
    assert confirmation is not None and confirmation.isVisible()
    confirmation.reject()


def test_idle_clears_previous_record_marks_and_long_content_remains_scrollable(page, qapp):
    page.show_post(post(body="内容" * 280, favorite=True, published=True,
                        source={"title": "事实来源", "summary": "摘要" * 200,
                                "url": "https://github.com/openai/codex"}), {})
    qapp.processEvents()
    assert page.content_scroll.verticalScrollBar().maximum() > 0
    assert page.copy_button.isVisible()
    assert page.favorite_button.isChecked()
    page.show_idle()
    assert not page.favorite_button.isChecked()
    assert page.favorite_button.text() == "收藏"
    assert page.published_button.text() == "标记已发布"
