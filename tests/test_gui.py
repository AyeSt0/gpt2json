import os
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GPT2JSON_SETTINGS_PATH", str(Path(tempfile.gettempdir()) / "gpt2json-test-settings.ini"))

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtTest = pytest.importorskip("PySide6.QtTest")

from gpt2json import gui as gui_module  # noqa: E402
from gpt2json.gui import APP_NAME, APP_VERSION, MainWindow, create_app_settings  # noqa: E402


def _app():
    app = QtWidgets.QApplication.instance()
    return app or QtWidgets.QApplication([])


def _clear_settings():
    settings = create_app_settings()
    settings.clear()
    settings.sync()


def test_gui_enables_run_only_after_valid_preflight(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    assert window.windowTitle() == f"{APP_NAME} {APP_VERSION}"
    assert window.version_badge.text() == APP_VERSION
    assert not window.run_btn.isEnabled()

    window.paste_edit.setPlainText("ok@example.com----pass----https://otp.test/{email}")
    QtTest.QTest.qWait(350)
    app.processEvents()

    assert window._input_mode == "paste"
    assert window._last_preflight_count == 1
    assert window.run_btn.isEnabled()

    window.sub2api_check.setChecked(False)
    window.cpa_check.setChecked(False)
    window._refresh_output_format_state()
    assert not window.run_btn.isEnabled()

    window.sub2api_check.setChecked(True)
    window.cpa_check.setChecked(True)
    window.concurrency_spin.setEditText("128")
    assert window.concurrency_spin.value() == 128
    window.output_edit.setText("output")
    initial_stack_height = window.input_stack.height()
    window.resize(1400, 900)
    app.processEvents()
    assert window.width() == 1400
    assert window.height() == 900
    assert window.input_stack.height() > initial_stack_height
    window.close()
    _clear_settings()


def test_gui_input_mode_switch_and_clear(tmp_path):
    _clear_settings()
    app = _app()
    input_file = tmp_path / "accounts.txt"
    input_file.write_text("ok@example.com----pass----https://otp.test/{email}\n", encoding="utf-8")
    window = MainWindow()
    window.show()
    app.processEvents()

    window.file_drop.set_path(str(input_file))
    QtTest.QTest.qWait(350)
    app.processEvents()

    assert window._input_mode == "file"
    assert window.input_stack.currentIndex() == 1
    assert window._last_preflight_count == 1
    assert not window.sub2api_row.isVisible()
    assert not window.cpa_row.isVisible()

    window.sub2api_row.set_path(str(tmp_path / "out" / "sub2api_accounts.secret.json"))
    window.cpa_row.set_path(str(tmp_path / "out" / "CPA"))
    window._refresh_output_format_state()
    app.processEvents()
    assert window.sub2api_row.isVisible()
    assert window.cpa_row.isVisible()

    window.clear_input()
    app.processEvents()

    assert window._input_mode == "file"
    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()

    window.output_edit.setText("output")
    window.close()
    _clear_settings()


def test_gui_switching_input_mode_does_not_reuse_stale_preflight(tmp_path):
    _clear_settings()
    app = _app()
    input_file = tmp_path / "accounts.txt"
    input_file.write_text("ok@example.com----pass----https://otp.test/{email}\n", encoding="utf-8")
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    window.paste_edit.setPlainText("这不是有效账号")
    QtTest.QTest.qWait(350)
    app.processEvents()
    assert window._input_mode == "paste"
    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()

    window.file_drop.set_path(str(input_file))
    QtTest.QTest.qWait(350)
    app.processEvents()
    assert window._input_mode == "file"
    assert window._last_preflight_count == 1
    assert window.run_btn.isEnabled()

    window.paste_tab.click()
    QtTest.QTest.qWait(350)
    app.processEvents()
    assert window._input_mode == "paste"
    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()
    assert "粘贴文本" in window.input_source_label.text()

    window.close()
    _clear_settings()


def test_gui_clear_input_preserves_current_tab_and_theme_toggle(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    assert window._theme == "light"
    assert "深色" in window.theme_btn.toolTip()
    light_stylesheet = window.styleSheet()
    window.toggle_theme()
    app.processEvents()
    assert window._theme == "dark"
    assert "浅色" in window.theme_btn.toolTip()
    assert window.styleSheet() != light_stylesheet

    window.paste_edit.setPlainText("ok@example.com----pass----https://otp.test/{email}")
    QtTest.QTest.qWait(350)
    app.processEvents()
    assert window._input_mode == "paste"
    assert window.run_btn.isEnabled()

    window.clear_input()
    app.processEvents()
    assert window._input_mode == "paste"
    assert window.input_stack.currentIndex() == 0
    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()

    window.close()
    _clear_settings()


def test_gui_async_preflight_discards_stale_file_result(tmp_path, monkeypatch):
    _clear_settings()
    app = _app()
    slow_file = tmp_path / "slow.txt"
    fast_file = tmp_path / "fast.txt"
    slow_file.write_text("placeholder", encoding="utf-8")
    fast_file.write_text("placeholder", encoding="utf-8")
    release_slow = threading.Event()

    def fake_decode_text_file(path):
        file_path = Path(path)
        if file_path == slow_file:
            release_slow.wait(1)
            return "\n".join(
                [
                    "slow1@example.com----pass----https://otp.test/{email}",
                    "slow2@example.com----pass----https://otp.test/{email}",
                ]
            )
        return "fast@example.com----pass----https://otp.test/{email}"

    monkeypatch.setattr(gui_module, "decode_text_file", fake_decode_text_file)

    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    window.file_drop.set_path(str(slow_file))
    QtTest.QTest.qWait(330)
    app.processEvents()
    assert window._input_mode == "file"

    window.file_drop.set_path(str(fast_file))
    QtTest.QTest.qWait(420)
    app.processEvents()
    assert window._last_preflight_count == 1
    assert window.run_btn.isEnabled()

    release_slow.set()
    QtTest.QTest.qWait(200)
    app.processEvents()
    assert window._last_preflight_count == 1

    window.close()
    _clear_settings()


def test_gui_cancel_button_sets_cancel_event(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    window._cancel_event = threading.Event()
    window._set_running(True)
    app.processEvents()
    assert window.cancel_btn.isVisible()
    assert window.cancel_btn.isEnabled()

    window.cancel_run()
    app.processEvents()
    assert window._is_cancelling
    assert window._cancel_event.is_set()
    assert not window.cancel_btn.isEnabled()

    window._set_running(False)
    window.close()
    _clear_settings()
