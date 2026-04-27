import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtTest = pytest.importorskip("PySide6.QtTest")
QtCore = pytest.importorskip("PySide6.QtCore")

from gpt2json.gui import APP_NAME, ORG_NAME, MainWindow


def _app():
    app = QtWidgets.QApplication.instance()
    return app or QtWidgets.QApplication([])


def _clear_settings():
    settings = QtCore.QSettings(ORG_NAME, APP_NAME)
    settings.clear()
    settings.sync()


def test_gui_enables_run_only_after_valid_preflight(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

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
    window.output_edit.setText("output")
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
    assert not window.paste_edit.isVisible()
    assert window.file_drop.isVisible()
    assert window._last_preflight_count == 1

    window.clear_input()
    app.processEvents()

    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()

    window.output_edit.setText("output")
    window.close()
    _clear_settings()
