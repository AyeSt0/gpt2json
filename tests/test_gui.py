import json
import os
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GPT2JSON_SETTINGS_PATH", str(Path(tempfile.gettempdir()) / "gpt2json-test-settings.ini"))

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtTest = pytest.importorskip("PySide6.QtTest")
QtCore = pytest.importorskip("PySide6.QtCore")
QtGui = pytest.importorskip("PySide6.QtGui")

from gpt2json import gui as gui_module  # noqa: E402
from gpt2json.gui import (  # noqa: E402
    APP_NAME,
    APP_VERSION,
    MainWindow,
    build_chinese_text_context_menu,
    build_unified_file_dialog_stylesheet,
    classify_log_line,
    create_app_settings,
    default_output_dir,
    rounded_pixmap,
)


def _app():
    app = QtWidgets.QApplication.instance()
    return app or QtWidgets.QApplication([])


def _clear_settings():
    settings = create_app_settings()
    settings.clear()
    settings.sync()


def _wait_until(app, predicate, *, timeout_ms: int = 2500, interval_ms: int = 50) -> bool:
    deadline = QtCore.QDeadlineTimer(timeout_ms)
    while not deadline.hasExpired():
        app.processEvents()
        if predicate():
            return True
        QtTest.QTest.qWait(interval_ms)
    app.processEvents()
    return bool(predicate())


def _icon_average_brightness(icon) -> float:
    image = icon.pixmap(18, 18).toImage()
    total = 0.0
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() <= 0:
                continue
            total += (color.red() + color.green() + color.blue()) / 3
            count += 1
    return total / max(1, count)


def _icon_color_signature(icon) -> tuple[int, int, int]:
    image = icon.pixmap(18, 18).toImage()
    red = green = blue = count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() <= 0:
                continue
            red += color.red()
            green += color.green()
            blue += color.blue()
            count += 1
    count = max(1, count)
    return (red // count, green // count, blue // count)


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
    assert _wait_until(app, lambda: window._last_preflight_count == 1 and window.run_btn.isEnabled())

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
    assert window.max_attempts_spin.value() == 3
    assert window.auto_rerun_spin.value() == 2
    window.max_attempts_spin.setValue(3)
    assert window.max_attempts_spin.value() == 3
    window.output_edit.setText("output")
    initial_stack_height = window.input_stack.height()
    window.resize(1400, 900)
    app.processEvents()
    assert window.width() == 1400
    assert window.height() == 900
    assert window.input_stack.height() > initial_stack_height
    window.close()
    _clear_settings()


def test_gui_default_output_dir_uses_app_output_until_user_changes(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.output_edit.text() == str(default_output_dir())
    assert not window._output_dir_custom

    window.close()
    _clear_settings()


def test_gui_output_dir_manual_choice_is_remembered(tmp_path):
    _clear_settings()
    app = _app()
    custom_out = tmp_path / "custom-out"

    window = MainWindow()
    window.output_edit.setText(str(custom_out))
    window._mark_output_dir_custom()
    window._save_settings()
    window.close()

    restored = MainWindow()
    restored.show()
    app.processEvents()

    assert restored.output_edit.text() == str(custom_out)
    assert restored._output_dir_custom

    restored.close()
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
    assert _wait_until(app, lambda: window._last_preflight_count == 1)

    assert window._input_mode == "file"
    assert window.input_stack.currentIndex() == 1
    assert window._last_preflight_count == 1
    assert not window.sub2api_row.isVisible()
    assert not window.cpa_row.isVisible()

    window.sub2api_row.set_path(str(tmp_path / "out" / "sub2api_accounts.secret.json"))
    window.cpa_row.set_path(str(tmp_path / "out" / "CPA_20260429_043512_a1b2c3"))
    window._refresh_output_format_state()
    app.processEvents()
    assert window.sub2api_row.isVisible()
    assert window.cpa_row.isVisible()
    assert window.sub2api_row.open_btn.text() == "所在位置"
    assert not hasattr(window.sub2api_row, "copy_btn")
    assert "所在位置" in window.output_hint_label.text()

    window.clear_input()
    app.processEvents()

    assert window._input_mode == "file"
    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()

    window.output_edit.setText("output")
    window.close()
    _clear_settings()


def test_gui_shows_failed_rerun_entry_from_summary(tmp_path, monkeypatch):
    _clear_settings()
    app = _app()
    monkeypatch.setattr(gui_module.QMessageBox, "information", lambda *args, **kwargs: gui_module.QMessageBox.StandardButton.Ok)
    rerun_file = tmp_path / "failed_rerun.secret.txt"
    rerun_file.write_text("retry@example.com----pass----https://otp.test/{email}\n", encoding="utf-8")
    failure_report = tmp_path / "failure_report.safe.json"
    failure_report.write_text(json.dumps({"failures": []}, ensure_ascii=False), encoding="utf-8")

    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    window.on_done(
        {
            "success_count": 1,
            "failure_count": 1,
            "cancelled": False,
            "cancelled_count": 0,
            "sub2api_export": "",
            "cpa_dir": "",
            "cpa_manifest": "",
            "out_dir": str(tmp_path / "out" / "GPT2JSON_batch"),
            "failure_report": str(failure_report),
            "failed_rerun_file": str(rerun_file),
            "rerunnable_failure_count": 1,
            "failure_categories": {"验证码错误或过期": 1},
        }
    )

    assert window._last_failed_rerun_file == str(rerun_file)
    assert window.rerun_failed_btn.isVisible()
    assert window.rerun_failed_btn.isEnabled()
    log_text = window.log_edit.toPlainText()
    assert "可恢复失败清单" in log_text
    assert "重跑失败账号" in log_text

    window.close()
    _clear_settings()


def test_gui_rerun_failed_accounts_loads_secret_text_and_autostarts(tmp_path, monkeypatch):
    _clear_settings()
    app = _app()
    rerun_file = tmp_path / "failed_rerun.secret.txt"
    raw_line = "retry@example.com----pass----https://otp.test/{email}"
    rerun_file.write_text(raw_line + "\n", encoding="utf-8")

    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window._last_failed_rerun_file = str(rerun_file)
    window.show()
    app.processEvents()

    called = {"start": 0}

    def fake_start_run():
        called["start"] += 1

    monkeypatch.setattr(window, "start_run", fake_start_run)
    window.rerun_failed_accounts()

    assert window._input_mode == "paste"
    assert window.paste_edit.toPlainText().strip() == raw_line
    assert _wait_until(app, lambda: called["start"] == 1 and not window._pending_failed_rerun_autostart)
    assert window._last_preflight_count == 1

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
    assert _wait_until(app, lambda: not window._preflight_running)
    assert window._input_mode == "paste"
    assert window._last_preflight_count == 0
    assert not window.run_btn.isEnabled()

    window.file_drop.set_path(str(input_file))
    assert _wait_until(app, lambda: window._last_preflight_count == 1 and window.run_btn.isEnabled())
    assert window._input_mode == "file"
    assert window._last_preflight_count == 1
    assert window.run_btn.isEnabled()

    window.paste_tab.click()
    assert _wait_until(app, lambda: not window._preflight_running)
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
    assert not window.shadow.isEnabled()
    light_stylesheet = window.styleSheet()
    window.toggle_theme()
    app.processEvents()
    assert window._theme == "dark"
    assert "浅色" in window.theme_btn.toolTip()
    assert window.styleSheet() != light_stylesheet

    window.paste_edit.setPlainText("ok@example.com----pass----https://otp.test/{email}")
    assert _wait_until(app, lambda: window._input_mode == "paste" and window.run_btn.isEnabled())
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


def test_rounded_pixmap_masks_logo_corners():
    _app()
    source = QtGui.QPixmap(50, 50)
    source.fill(QtGui.QColor("#2563EB"))
    rounded = rounded_pixmap(source, 50, 14)
    image = rounded.toImage()

    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(49, 0).alpha() == 0
    assert image.pixelColor(25, 25).alpha() == 255


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
    assert _wait_until(app, lambda: window._input_mode == "file", timeout_ms=1200)
    assert window._input_mode == "file"

    window.file_drop.set_path(str(fast_file))
    assert _wait_until(app, lambda: window._last_preflight_count == 1 and window.run_btn.isEnabled())
    assert window._last_preflight_count == 1
    assert window.run_btn.isEnabled()

    release_slow.set()
    assert _wait_until(app, lambda: not window._preflight_running, timeout_ms=1200)
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


def test_gui_runtime_logs_include_account_sequence(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    app.processEvents()

    window.log_edit.clear()
    window.on_event({"type": "started", "total": 12, "concurrency": 3})
    window.on_event({"type": "row_start", "row_index": 3, "line_no": 9, "email_masked": "te***@example.com"})
    window.on_event(
        {
            "type": "row_stage",
            "row_index": 3,
            "line_no": 9,
            "email_masked": "te***@example.com",
            "stage": "password_verify",
            "status_code": 200,
            "page_type": "email_otp_verification",
        }
    )
    window.on_event(
        {
            "type": "row_done",
            "done": 1,
            "total": 12,
            "ok": True,
            "row_index": 3,
            "line_no": 9,
            "email_masked": "te***@example.com",
            "otp_required": True,
        }
    )

    text = window.log_edit.toPlainText()
    assert "账号 #003 te***@example.com" in text
    assert "行 9" in text
    assert "密码验证通过" in text
    assert "成功：账号 #003" in text

    window.log_edit.clear()
    window.on_event(
        {
            "type": "row_retry",
            "row_index": 3,
            "line_no": 9,
            "email_masked": "te***@example.com",
            "stage": "finalize",
            "reason": "TimeoutError: The read operation timed out",
            "next_attempt": 2,
            "max_attempts": 2,
        }
    )
    retry_text = window.log_edit.toPlainText()
    assert "自动重试" in retry_text
    assert "账号 #003 te***@example.com" in retry_text
    assert "第 2/2 次尝试" in retry_text

    window.log_edit.clear()
    window.on_event(
        {
            "type": "row_retry",
            "row_index": 3,
            "line_no": 9,
            "email_masked": "te***@example.com",
            "stage": "email_verification",
            "reason": "wrong_email_otp_code",
            "next_attempt": 4,
            "max_attempts": 5,
            "normal_attempts": 3,
            "auto_rerun_attempts": 2,
            "auto_rerun": True,
        }
    )
    rerun_text = window.log_edit.toPlainText()
    assert "自动重跑补救" in rerun_text
    assert "补救第 1/2 次" in rerun_text
    assert "总第 4/5 次" in rerun_text

    window.close()
    _clear_settings()


def test_log_line_classification_for_semantic_colors():
    assert classify_log_line("✅ 成功：账号 #001 已获取 JSON") == "success"
    assert classify_log_line("⚠️ 失败：账号 #002 停在「验证码提交」") == "error"
    assert classify_log_line("🚫 账号 #002：验证码提交后被服务端拒绝（HTTP 403）") == "error"
    assert classify_log_line("🛑 取消请求：已发送") == "cancel"
    assert classify_log_line("📮 账号 #003：服务端要求邮箱验证码") == "otp"
    assert classify_log_line("🧰 Sub2API 输出：out.json") == "output"
    assert classify_log_line("🗂️ 本次结果目录：output/GPT2JSON_20260429_043512_a1b2c3") == "output"
    assert classify_log_line("🚀 开始导出：配置已确认") == "start"
    assert classify_log_line("🔁 自动重试：账号 #001 正在进行第 2/2 次尝试。") == "warning"
    assert classify_log_line("🔄 自动重跑补救：账号 #001 正在进行第 4/5 次尝试。") == "warning"
    assert classify_log_line("🧮 自动处理统计：2 个账号触发恢复策略") == "info"
    assert classify_log_line("🔍 导出校验：已检查导出的 JSON 是否可导入。") == "info"
    assert classify_log_line("✅ 导出校验：Sub2API JSON 可导入（2 个账号）。") == "success"
    assert classify_log_line("⚠️ 导出校验：Sub2API JSON 不建议导入（1 个问题）。") == "error"
    assert classify_log_line("🟡 可恢复失败：1 个账号已达到当前自动处理上限") == "warning"
    assert classify_log_line("🚫 终态失败：账号 #001 服务端返回账号已停用") == "error"
    assert classify_log_line("🧾 失败诊断报告：failure_report.safe.json") == "output"
    assert classify_log_line("📦 任务已启动：共 3 个账号，并发=3。") == "start"
    assert classify_log_line("🧭 执行流程：OAuth 初始化 → 账号密码验证 → 按需获取邮箱验证码 → Callback 换取 JSON。") == "info"
    assert classify_log_line("🔎 登录策略：遇到验证码才启用取码源。") == "info"


def test_text_context_menu_is_chinese():
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    window.paste_edit.setPlainText("hello")
    cursor = window.paste_edit.textCursor()
    cursor.select(cursor.SelectionType.Document)
    window.paste_edit.setTextCursor(cursor)
    menu = build_chinese_text_context_menu(window.paste_edit)
    action_texts = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert action_texts == ["撤销", "重做", "剪切", "复制", "粘贴", "删除", "全选"]
    assert menu.objectName() == "TextContextMenu"
    assert "border-radius:10px" in menu.styleSheet()
    assert "#2563EB" in menu.styleSheet()

    log_menu = build_chinese_text_context_menu(window.log_edit)
    log_actions = {action.text(): action for action in log_menu.actions() if not action.isSeparator()}
    assert "复制" in log_actions
    assert "粘贴" in log_actions
    assert not log_actions["粘贴"].isEnabled()

    window.close()
    _clear_settings()


def test_output_directory_dialog_uses_unified_theme(tmp_path):
    _clear_settings()
    app = _app()
    window = MainWindow()
    window.toggle_theme()
    missing_child = tmp_path / "missing" / "output"
    dialog = window._create_output_directory_dialog(str(missing_child))
    QtTest.QTest.qWait(80)
    app.processEvents()

    assert dialog.objectName() == "UnifiedFileDialog"
    assert dialog.windowFlags() & QtCore.Qt.WindowType.FramelessWindowHint
    assert not dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
    assert dialog.testAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
    title_bar = dialog.findChild(QtWidgets.QFrame, "FileDialogTitleBar")
    assert title_bar is not None
    close_button = dialog.findChild(QtWidgets.QToolButton, "FileDialogCloseButton")
    assert close_button is not None
    assert close_button.text() == "×"
    grid = dialog.layout()
    assert isinstance(grid, QtWidgets.QGridLayout)
    title_bar_row = next(grid.getItemPosition(index)[0] for index in range(grid.count()) if grid.itemAt(index).widget() is title_bar)
    assert title_bar_row == 0
    assert dialog.testOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog)
    assert not dialog.testOption(QtWidgets.QFileDialog.Option.ShowDirsOnly)
    assert dialog.fileMode() == QtWidgets.QFileDialog.FileMode.Directory
    assert dialog.labelText(QtWidgets.QFileDialog.DialogLabel.Accept) == "选择此目录"
    assert dialog.labelText(QtWidgets.QFileDialog.DialogLabel.Reject) == "取消"
    assert dialog.labelText(QtWidgets.QFileDialog.DialogLabel.FileName) == "文件夹"
    assert Path(dialog.directory().absolutePath()) == tmp_path
    tooltips = {button.objectName(): button.toolTip() for button in dialog.findChildren(QtWidgets.QToolButton)}
    assert tooltips["backButton"] == "后退"
    assert tooltips["forwardButton"] == "前进"
    assert tooltips["toParentButton"] == "向上一级"
    assert tooltips["refreshButton"] == "刷新"
    assert tooltips["newFolderButton"] == "新建文件夹"
    assert tooltips["listModeButton"] == "列表"
    assert tooltips["detailModeButton"] == "详细信息"
    toolbar_buttons = {
        button.objectName(): button
        for button in dialog.findChildren(QtWidgets.QToolButton)
        if button.objectName()
        in {"backButton", "forwardButton", "toParentButton", "refreshButton", "newFolderButton", "listModeButton", "detailModeButton"}
    }
    assert list(toolbar_buttons) == ["backButton", "forwardButton", "toParentButton", "newFolderButton", "listModeButton", "detailModeButton", "refreshButton"]
    for button in toolbar_buttons.values():
        assert button.text() == ""
        assert not button.icon().isNull()
        assert button.toolButtonStyle() == QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.iconSize().width() == 18
        assert button.width() == 30
        assert button.property("themeIconColor") == "accent"
        assert button.property("themeIconMode") == "dark"
    assert len({_icon_color_signature(button.icon()) for button in toolbar_buttons.values()}) >= 4
    toolbar_layout = window._file_dialog_toolbar_layout(dialog)
    toolbar_order = [
        toolbar_layout.itemAt(index).widget().objectName()
        for index in range(toolbar_layout.count())
        if toolbar_layout.itemAt(index).widget() is not None
    ]
    assert toolbar_order[:6] == ["backButton", "forwardButton", "toParentButton", "refreshButton", "ToolbarLocationLabel", "lookInCombo"]
    assert toolbar_order[-3:] == ["newFolderButton", "listModeButton", "detailModeButton"]
    original_location_label = dialog.findChild(QtWidgets.QLabel, "lookInLabel")
    assert original_location_label is not None
    assert not original_location_label.isVisible()
    assert original_location_label.width() == 0
    sidebar = dialog.findChild(QtWidgets.QListView, "sidebar")
    assert sidebar is not None
    assert 92 <= sidebar.minimumWidth() <= 100
    assert sidebar.iconSize().width() <= 16
    sidebar_labels = [sidebar.model().index(row, 0).data(QtCore.Qt.ItemDataRole.DisplayRole) for row in range(sidebar.model().rowCount())]
    assert sidebar_labels[:6] == ["桌面", "文档", "下载", "图片", "音乐", "视频"]
    assert sidebar_labels[-1] == "此电脑"
    assert not any(str(label).startswith("本地磁盘") for label in sidebar_labels)
    assert dialog.sidebarUrls()[sidebar_labels.index("此电脑")].toString() == "file:"
    computer_index = sidebar.model().index(sidebar_labels.index("此电脑"), 0)
    assert computer_index.data(QtCore.Qt.ItemDataRole.ToolTipRole) == "查看所有磁盘和驱动器"
    splitter = dialog.findChild(QtWidgets.QSplitter, "splitter")
    assert splitter is not None
    assert splitter.handleWidth() == 8
    tree = dialog.findChild(QtWidgets.QTreeView, "treeView")
    assert tree is not None
    assert tree.selectionBehavior() == QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
    assert tree.model().headerData(0, QtCore.Qt.Orientation.Horizontal) == "名称"
    assert tree.model().headerData(1, QtCore.Qt.Orientation.Horizontal) == "大小"
    stylesheet = dialog.styleSheet()
    assert "QFileDialog#UnifiedFileDialog" in stylesheet
    assert "QPushButton#DialogPrimaryButton" in stylesheet
    assert gui_module.DARK_THEME["card"] in stylesheet

    dialog.close()
    window.close()
    _clear_settings()


def test_account_file_dialog_uses_unified_theme(tmp_path):
    _clear_settings()
    app = _app()
    input_file = tmp_path / "accounts.txt"
    input_file.write_text("ok@example.com----pass----https://otp.test/{email}\n", encoding="utf-8")
    window = MainWindow()
    dialog = window._create_input_file_dialog(str(input_file))
    app.processEvents()

    assert dialog.objectName() == "UnifiedFileDialog"
    assert dialog.testOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog)
    assert dialog.fileMode() == QtWidgets.QFileDialog.FileMode.ExistingFile
    assert dialog.nameFilters() == ["文本文件 (*.txt)", "所有文件 (*)"]
    assert dialog.labelText(QtWidgets.QFileDialog.DialogLabel.Accept) == "选择文件"
    assert Path(dialog.directory().absolutePath()) == tmp_path
    back_button = dialog.findChild(QtWidgets.QToolButton, "backButton")
    assert back_button.property("themeIconColor") == "accent"
    assert back_button.property("themeIconMode") == "light"
    assert _icon_average_brightness(back_button.icon()) < 130

    style = build_unified_file_dialog_stylesheet(gui_module.LIGHT_THEME)
    assert "QTreeView" in style
    assert "border-radius:9px" in style

    dialog.close()
    window.close()
    _clear_settings()
