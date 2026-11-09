from PySide6.QtTest import QTest
from suishou.runtime import AppRuntime, MemorySettingsStore, DemoCredentials
from suishou.config import Settings


def test_runtime_demo_complete_flow_and_settings_pause(qapp):
    runtime = AppRuntime(qapp, demo=True, tray_enabled=False,
                         store=MemorySettingsStore(), credentials=DemoCredentials())
    assert not runtime.controller.listening
    runtime.controller.set_listening(True)
    text = 'AI工具越来越多，真正省下时间的反而是少用几个。'
    qapp.clipboard().setText(text)
    QTest.qWait(1200)
    assert runtime.controller.current_reply
    assert runtime.window.reply_label.text() == runtime.controller.current_reply
    assert qapp.clipboard().text() == text
    runtime.window.copy_button.click()
    QTest.qWait(30)
    assert qapp.clipboard().text() == runtime.controller.current_reply
    runtime.open_settings()
    assert not runtime.controller.listening
    runtime.settings_dialog.reject()
    assert not runtime.controller.listening
    runtime.cleanup()


def test_setting_model_key_and_theme(qapp):
    store = MemorySettingsStore()
    credentials = DemoCredentials()
    runtime = AppRuntime(qapp, demo=True, tray_enabled=False,
                         store=store, credentials=credentials)
    runtime.open_settings()
    runtime.save_settings('', 'deepseek-flash', '幽默', 'light')
    assert store.load().style == '幽默'
    assert runtime.controller.settings.theme == 'light'
    assert not runtime.controller.listening
    runtime.cleanup()


def test_reopening_settings_does_not_reset_unsaved_fields(qapp):
    runtime = AppRuntime(qapp, demo=True, tray_enabled=False)
    runtime.open_settings()
    runtime.settings_dialog.model_input.setText('another-model')
    runtime.open_settings()
    assert runtime.settings_dialog.model_input.text() == 'another-model'
    runtime.cleanup()
def test_original_mode_pauses_clipboard_and_mode_switch_cancels(qapp):
    runtime = AppRuntime(qapp, demo=True, tray_enabled=False)
    runtime.controller.set_listening(True)
    runtime.window.set_mode('original')
    assert not runtime.controller.listening
    ctl = runtime.original_controller
    ctl.generate('犀利', 'AI编程')
    assert ctl.busy
    runtime.window.set_mode('reply')
    QTest.qWait(500)
    assert not ctl.busy and ctl.current is None
    runtime.window.set_mode('original')
    ctl.generate('幽默', 'AI工具')
    QTest.qWait(500)
    assert ctl.current and runtime.window.original_page.isVisible() is False
    before = ctl.current['body'] + '\n' + ctl.current['source']['url']
    ctl.copy()
    assert qapp.clipboard().text() == before
    runtime.open_settings()
    assert not ctl.busy
    runtime.settings_dialog.reject()
    runtime.cleanup()
