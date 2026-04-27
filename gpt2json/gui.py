from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .engine import ExportConfig, run_export
from .parsing import read_account_file

APP_NAME = "GPT2JSON"
APP_SUBTITLE = "Protocol-first Sub2API / CPA exporter"
ICON_PATH = Path(__file__).resolve().parent / "assets" / "gpt2json_icon.png"


def load_ui_font() -> str:
    for font_path in (Path(r"C:\Windows\Fonts\segoeui.ttf"), Path(r"C:\Windows\Fonts\msyh.ttc")):
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    families = QFontDatabase.families()
    return families[0] if families else "Sans Serif"


class WorkerBridge(QObject):
    log = Signal(str)
    event = Signal(dict)
    done = Signal(dict)
    failed = Signal(str)


class DropLineEdit(QLineEdit):
    dropped = Signal(str)

    def __init__(self, *, directory: bool = False) -> None:
        super().__init__()
        self.directory = directory
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        mime = event.mimeData()
        value = ""
        if mime.hasUrls():
            value = mime.urls()[0].toLocalFile()
        elif mime.hasText():
            value = mime.text().strip()
        if not value:
            event.ignore()
            return
        path = Path(value)
        if self.directory and path.is_file():
            value = str(path.parent)
        self.setText(value)
        self.dropped.emit(value)
        event.acceptProposedAction()


class SectionTitle(QWidget):
    def __init__(self, number: int, title: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        badge = QLabel(str(number))
        badge.setObjectName("StepBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        layout.addWidget(badge)
        layout.addWidget(label)
        layout.addStretch(1)


class InlineStat(QWidget):
    def __init__(self, title: str, color: str) -> None:
        super().__init__()
        self.value_label = QLabel("0")
        self.value_label.setObjectName("StatValue")
        self.value_label.setStyleSheet(f"color: {color};")
        title_label = QLabel(title)
        title_label.setObjectName("StatTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))


class FileOutputRow(QFrame):
    def __init__(self, filename: str) -> None:
        super().__init__()
        self.setObjectName("OutputRow")
        self.setFixedHeight(52)
        self.path = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)
        icon = QLabel("JSON")
        icon.setObjectName("FileIcon")
        self.name_label = QLabel(filename)
        self.name_label.setObjectName("OutputName")
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy_btn = QToolButton()
        self.copy_btn.setObjectName("CopyButton")
        self.copy_btn.setText("Copy")
        self.copy_btn.setToolTip("Copy path")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_path)
        layout.addWidget(icon)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.copy_btn)

    def set_path(self, path: str) -> None:
        self.path = path
        self.copy_btn.setEnabled(bool(path))
        self.setToolTip(path)

    def copy_path(self) -> None:
        if self.path:
            QApplication.clipboard().setText(self.path)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(980, 680)
        self.resize(1000, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.bridge = WorkerBridge()
        self.bridge.log.connect(self.append_log)
        self.bridge.event.connect(self.on_event)
        self.bridge.done.connect(self.on_done)
        self.bridge.failed.connect(self.on_failed)
        self._worker_thread: threading.Thread | None = None
        self._drag_start: Any = None
        self._total = 0
        self._done = 0
        self._success = 0
        self._failure = 0
        self._running = 0
        self._log_waiting = True
        self._build_ui()
        self.apply_style()

    def _build_ui(self) -> None:
        outer = QWidget(self)
        outer.setObjectName("Outer")
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        self.shell = QFrame()
        self.shell.setObjectName("Shell")
        shadow = QGraphicsDropShadowEffect(self.shell)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.GlobalColor.gray)
        self.shell.setGraphicsEffect(shadow)
        outer_layout.addWidget(self.shell)
        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(24, 22, 24, 22)
        shell_layout.setSpacing(14)
        shell_layout.addLayout(self._build_header())
        shell_layout.addLayout(self._build_content(), 1)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(14)
        self.logo = QLabel()
        self.logo.setObjectName("LogoImage")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if ICON_PATH.exists():
            self.logo.setPixmap(QPixmap(str(ICON_PATH)).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.logo.setText("G")
        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("Subtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        self.status_label = QLabel("●  Ready")
        self.status_label.setObjectName("StatusPill")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.min_btn = self._window_button("−")
        self.max_btn = self._window_button("□")
        self.close_btn = self._window_button("×", close=True)
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self._toggle_max_restore)
        self.close_btn.clicked.connect(self.close)
        header.addWidget(self.logo)
        header.addLayout(title_stack, 1)
        header.addWidget(self.status_label)
        header.addSpacing(70)
        header.addWidget(self.min_btn)
        header.addWidget(self.max_btn)
        header.addWidget(self.close_btn)
        return header

    def _build_content(self) -> QHBoxLayout:
        content = QHBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._build_main_card(), 65)
        content.addWidget(self._build_right_column(), 35)
        return content

    def _build_main_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(SectionTitle(1, "Source"))
        source_grid = QGridLayout()
        source_grid.setContentsMargins(0, 0, 0, 0)
        source_grid.setHorizontalSpacing(12)
        source_grid.setVerticalSpacing(10)
        self.input_edit = DropLineEdit()
        self.input_edit.setObjectName("PathEdit")
        self.input_edit.setFixedHeight(40)
        self.input_edit.setPlaceholderText("GPT email----GPT password----OTP source")
        self.input_edit.setToolTip("Current format: GPT email----GPT password----no-login OTP URL/source. The middle field is not mailbox password.")
        self.input_edit.dropped.connect(lambda _p: self.preflight(silent=True))
        self.output_edit = DropLineEdit(directory=True)
        self.output_edit.setObjectName("PathEdit")
        self.output_edit.setFixedHeight(40)
        self.output_edit.setPlaceholderText("Choose export folder")
        self.output_edit.setText("output")
        input_btn = QPushButton("Browse")
        input_btn.setObjectName("BrowseButton")
        input_btn.setFixedHeight(40)
        input_btn.clicked.connect(self.pick_input)
        output_btn = QPushButton("Browse")
        output_btn.setObjectName("BrowseButton")
        output_btn.setFixedHeight(40)
        output_btn.clicked.connect(self.pick_output)
        source_grid.addWidget(self._field_label("Account file"), 0, 0)
        source_grid.addWidget(self.input_edit, 0, 1)
        source_grid.addWidget(input_btn, 0, 2)
        source_grid.addWidget(self._field_label("Output folder"), 1, 0)
        source_grid.addWidget(self.output_edit, 1, 1)
        source_grid.addWidget(output_btn, 1, 2)
        source_grid.setColumnMinimumWidth(0, 118)
        source_grid.setRowMinimumHeight(0, 42)
        source_grid.setRowMinimumHeight(1, 42)
        source_grid.setColumnStretch(1, 1)
        source_holder = QWidget()
        source_holder.setFixedHeight(90)
        source_holder.setLayout(source_grid)
        layout.addWidget(source_holder)
        layout.addWidget(self._divider())
        layout.addWidget(SectionTitle(2, "Options"))
        options_grid = QGridLayout()
        options_grid.setContentsMargins(0, 0, 0, 0)
        options_grid.setHorizontalSpacing(16)
        options_grid.setVerticalSpacing(8)
        self.pool_combo = self._combo(["plus-20", "plus", "default"])
        self.token_type_combo = self._combo(["plus", "free", "team"])
        self.concurrency_spin = self._spin(1, 64, 5)
        options_grid.addWidget(self._field_label("Pool"), 0, 0)
        options_grid.addWidget(self._field_label("Type"), 0, 1)
        options_grid.addWidget(self._field_label("Concurrency"), 0, 2)
        options_grid.addWidget(self.pool_combo, 1, 0)
        options_grid.addWidget(self.token_type_combo, 1, 1)
        options_grid.addWidget(self.concurrency_spin, 1, 2)
        options_grid.setColumnStretch(0, 2)
        options_grid.setColumnStretch(1, 2)
        options_grid.setColumnStretch(2, 1)
        layout.addLayout(options_grid)
        self.advanced_btn = QToolButton()
        self.advanced_btn.setObjectName("AdvancedBar")
        self.advanced_btn.setText("Advanced OTP  v")
        self.advanced_btn.setFixedHeight(40)
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.clicked.connect(self.toggle_advanced)
        layout.addWidget(self.advanced_btn)
        self.advanced_panel = QWidget()
        advanced_grid = QGridLayout(self.advanced_panel)
        advanced_grid.setContentsMargins(0, 0, 0, 0)
        advanced_grid.setHorizontalSpacing(12)
        advanced_grid.setVerticalSpacing(8)
        self.timeout_spin = self._spin(10, 600, 30)
        self.otp_timeout_spin = self._spin(10, 600, 180)
        self.otp_interval_spin = self._spin(1, 60, 3)
        advanced_grid.addWidget(self._field_label("HTTP timeout"), 0, 0)
        advanced_grid.addWidget(self._field_label("OTP timeout"), 0, 1)
        advanced_grid.addWidget(self._field_label("OTP interval"), 0, 2)
        advanced_grid.addWidget(self.timeout_spin, 1, 0)
        advanced_grid.addWidget(self.otp_timeout_spin, 1, 1)
        advanced_grid.addWidget(self.otp_interval_spin, 1, 2)
        self.advanced_panel.setVisible(False)
        layout.addWidget(self.advanced_panel)
        format_row = QHBoxLayout()
        format_row.setSpacing(14)
        format_row.addWidget(self._field_label("Output format"))
        format_row.addSpacing(18)
        format_row.addWidget(self._selected_chip("Sub2API JSON"))
        format_row.addWidget(self._selected_chip("CPA Manifest"))
        format_row.addStretch(1)
        layout.addLayout(format_row)
        layout.addWidget(self._divider())
        layout.addWidget(SectionTitle(3, "Export"))
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setObjectName("Progress")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("PercentLabel")
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.percent_label)
        layout.addLayout(progress_row)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)
        self.total_stat = InlineStat("Total", "#0F172A")
        self.success_stat = InlineStat("Success", "#16A34A")
        self.failed_stat = InlineStat("Failed", "#DC2626")
        self.running_stat = InlineStat("Running", "#2563EB")
        for idx, stat in enumerate([self.total_stat, self.success_stat, self.failed_stat, self.running_stat]):
            stats_row.addWidget(stat, 1)
            if idx < 3:
                stats_row.addWidget(self._vertical_divider())
        layout.addLayout(stats_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(16)
        self.preflight_btn = QPushButton("Preflight")
        self.preflight_btn.setObjectName("SecondaryButton")
        self.preflight_btn.setFixedHeight(42)
        self.preflight_btn.clicked.connect(self.preflight)
        self.run_btn = QPushButton("Start Export")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setFixedHeight(42)
        self.run_btn.clicked.connect(self.start_run)
        self.open_out_btn = QPushButton("Open Output")
        self.open_out_btn.setObjectName("SecondaryButton")
        self.open_out_btn.setFixedHeight(42)
        self.open_out_btn.clicked.connect(self.open_output_dir)
        buttons.addWidget(self.preflight_btn, 1)
        buttons.addWidget(self.run_btn, 2)
        buttons.addWidget(self.open_out_btn, 1)
        layout.addLayout(buttons)
        return card

    def _build_right_column(self) -> QWidget:
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        output_card = QFrame()
        output_card.setObjectName("Card")
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(16, 16, 16, 16)
        output_layout.setSpacing(14)
        output_layout.addWidget(self._card_title("JSON", "Output files"))
        self.sub2api_row = FileOutputRow("sub2api_plus_accounts.secret.json")
        self.cpa_row = FileOutputRow("cpa_manifest.json")
        output_layout.addWidget(self.sub2api_row)
        output_layout.addWidget(self.cpa_row)
        layout.addWidget(output_card)
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.setSpacing(14)
        log_layout.addWidget(self._card_title(">_", "Live log"))
        self.log_edit = QPlainTextEdit()
        self.log_edit.setObjectName("LogBox")
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlainText("Waiting to start")
        log_layout.addWidget(self.log_edit, 1)
        layout.addWidget(log_card, 1)
        return right

    def _window_button(self, text: str, *, close: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("CloseButton" if close else "WindowButton")
        button.setText(text)
        return button

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _card_title(self, icon: str, text: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        icon_label = QLabel(icon)
        icon_label.setObjectName("TitleIcon")
        label = QLabel(text)
        label.setObjectName("RightTitle")
        layout.addWidget(icon_label)
        layout.addWidget(label)
        layout.addStretch(1)
        return widget

    def _combo(self, values: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(values)
        combo.setCurrentText(values[0])
        combo.setFixedHeight(40)
        return combo

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setFixedHeight(40)
        return spin

    def _selected_chip(self, text: str) -> QLabel:
        chip = QLabel(text)
        chip.setObjectName("SelectedChip")
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setFixedHeight(36)
        return chip

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    def _vertical_divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("VerticalDivider")
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        return line

    def apply_style(self) -> None:
        font = QFont(load_ui_font(), 10)
        QApplication.instance().setFont(font)  # type: ignore[union-attr]
        self.setStyleSheet(
            """
            #Outer { background: transparent; }
            #Shell { background: #F6F8FC; border: 1px solid #D9E2EF; border-radius: 18px; }
            #LogoImage { min-width:48px; max-width:48px; min-height:48px; max-height:48px; border-radius:13px; }
            #Title { color:#0F172A; font-size:26px; font-weight:800; letter-spacing:-0.5px; }
            #Subtitle { color:#64748B; font-size:14px; font-weight:500; }
            #StatusPill { color:#079345; background:#DCFCE7; border:1px solid #B7E4C7; border-radius:18px; padding:7px 18px; min-width:78px; font-size:14px; font-weight:700; }
            #WindowButton, #CloseButton { border:none; background:transparent; color:#0F172A; font-size:20px; min-width:34px; max-width:34px; min-height:30px; max-height:30px; border-radius:8px; }
            #WindowButton:hover { background:#E8EEF8; }
            #CloseButton:hover { background:#FEE2E2; color:#DC2626; }
            #Card { background:rgba(255,255,255,0.92); border:1px solid #D8E1EE; border-radius:14px; }
            #StepBadge { min-width:28px; max-width:28px; min-height:28px; max-height:28px; border-radius:8px; color:white; font-size:16px; font-weight:800; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #22A7FF,stop:1 #6D4DFF); }
            #SectionTitle, #RightTitle { color:#0F172A; font-size:17px; font-weight:800; }
            #TitleIcon { color:#1E40AF; font-weight:900; font-size:12px; min-width:34px; }
            #FieldLabel { color:#283752; font-size:13px; font-weight:500; }
            QLineEdit, QComboBox, QSpinBox { min-height:38px; border-radius:8px; padding-left:12px; padding-right:10px; color:#0F172A; background:#FFFFFF; border:1px solid #D5DFEC; font-size:13px; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border:1px solid #60A5FA; background:#FFFFFF; }
            QLineEdit::placeholder { color:#8A95A8; }
            QComboBox::drop-down { border:none; width:28px; }
            QSpinBox::up-button, QSpinBox::down-button { width:22px; border:none; background:transparent; }
            #BrowseButton { min-height:38px; min-width:78px; border-radius:8px; color:#0F172A; background:#FFFFFF; border:1px solid #D5DFEC; font-weight:600; }
            #BrowseButton:hover, #SecondaryButton:hover, #AdvancedBar:hover { background:#EFF6FF; border-color:#93C5FD; }
            #AdvancedBar { min-height:40px; border-radius:8px; padding:0 12px; text-align:left; color:#0F172A; background:#FBFCFE; border:1px solid #D5DFEC; font-size:13px; font-weight:500; }
            #SelectedChip { min-height:34px; min-width:142px; padding:0 14px; border-radius:8px; color:white; font-weight:800; font-size:13px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #7C3AED); }
            #Divider { background:#E1E7F0; border:none; }
            #VerticalDivider { background:#E4EAF2; border:none; min-height:48px; }
            #Progress { height:9px; border-radius:5px; border:none; background:#E2E8F0; }
            #Progress::chunk { border-radius:5px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #7C3AED); }
            #PercentLabel { color:#2563EB; font-size:14px; font-weight:700; min-width:34px; }
            #StatTitle { color:#475569; font-size:12px; font-weight:500; }
            #StatValue { font-size:24px; font-weight:900; }
            #SecondaryButton { min-height:42px; border-radius:9px; color:#17233C; background:#FFFFFF; border:1px solid #D5DFEC; font-weight:700; font-size:13px; }
            #PrimaryButton { min-height:42px; border:none; border-radius:9px; color:white; font-weight:800; font-size:13px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1677FF,stop:1 #7C3AED); }
            #PrimaryButton:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0F63D6,stop:1 #6D28D9); }
            #PrimaryButton:disabled, #SecondaryButton:disabled { background:#E2E8F0; color:#94A3B8; border:1px solid #CBD5E1; }
            #OutputRow { min-height:50px; background:#FBFCFE; border:1px solid #DCE4EF; border-radius:9px; }
            #OutputName { color:#0F172A; font-size:13px; font-weight:500; }
            #FileIcon { color:#334155; font-size:10px; font-weight:800; min-width:28px; }
            #CopyButton { border:none; background:transparent; color:#1E3A8A; min-width:44px; max-width:44px; min-height:28px; max-height:28px; border-radius:6px; font-size:11px; font-weight:700; }
            #CopyButton:hover { background:#DBEAFE; }
            #CopyButton:disabled { color:#A8B2C2; }
            #LogBox { border-radius:9px; border:1px solid #D8E1EE; background:#FBFCFE; color:#64748B; padding:12px; font-family:Consolas, 'Cascadia Mono', monospace; font-size:12px; }
            """
        )

    def _toggle_max_restore(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 92:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def toggle_advanced(self) -> None:
        visible = self.advanced_btn.isChecked()
        self.advanced_panel.setVisible(visible)
        self.advanced_btn.setText("Advanced OTP  ^" if visible else "Advanced OTP  v")

    def _set_status(self, text: str, mode: str) -> None:
        styles = {
            "ready": "color:#079345;background:#DCFCE7;border:1px solid #B7E4C7;",
            "running": "color:#6D28D9;background:#EDE9FE;border:1px solid #DDD6FE;",
            "done": "color:#15803D;background:#DCFCE7;border:1px solid #BBF7D0;",
            "failed": "color:#DC2626;background:#FEE2E2;border:1px solid #FECACA;",
        }
        self.status_label.setText(text)
        self.status_label.setStyleSheet(styles.get(mode, styles["ready"]) + "border-radius:18px;padding:7px 18px;min-width:78px;font-size:14px;font-weight:700;")

    def append_log(self, text: str) -> None:
        if self._log_waiting:
            self.log_edit.clear()
            self._log_waiting = False
        self.log_edit.appendPlainText(text)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select account file", str(Path.cwd()), "Text Files (*.txt);;All Files (*)")
        if path:
            self.input_edit.setText(path)
            self.preflight(silent=True)

    def pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder", self.output_edit.text() or str(Path.cwd()))
        if path:
            self.output_edit.setText(path)

    def open_output_dir(self) -> None:
        path = Path(self.output_edit.text().strip() or Path.cwd())
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def preflight(self, silent: bool = False) -> bool:
        input_path = Path(self.input_edit.text().strip())
        if not input_path.exists() or not input_path.is_file():
            if not silent:
                QMessageBox.warning(self, "Missing input", "Choose an account .txt file first.")
            return False
        try:
            rows = read_account_file(input_path)
        except Exception as exc:
            if not silent:
                QMessageBox.critical(self, "Preflight failed", f"Read failed: {type(exc).__name__}: {exc}")
            return False
        self._total = len(rows)
        self.total_stat.set_value(self._total)
        self._done = self._success = self._failure = self._running = 0
        self.success_stat.set_value(0)
        self.failed_stat.set_value(0)
        self.running_stat.set_value(0)
        self._update_progress()
        if not silent:
            self.append_log(f"[preflight] valid rows: {self._total} | format=auto | outputs: Sub2API JSON + CPA Manifest")
            QMessageBox.information(self, "Preflight complete", f"Valid rows: {self._total}\nFormat: Auto detect\nOutputs: Sub2API JSON + CPA Manifest")
        return bool(rows)

    def start_run(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            QMessageBox.information(self, "Running", "The current task is still running.")
            return
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, "Missing input", "Choose an account .txt file first.")
            return
        if not output_dir:
            QMessageBox.warning(self, "Missing output", "Choose an output folder first.")
            return
        if not self.preflight(silent=True):
            QMessageBox.warning(self, "No valid rows", "No valid account rows were found.")
            return
        self._done = self._success = self._failure = self._running = 0
        self.success_stat.set_value(0)
        self.failed_stat.set_value(0)
        self.running_stat.set_value(0)
        self._update_progress()
        self.log_edit.clear()
        self._log_waiting = False
        self._set_status("●  Running", "running")
        self.run_btn.setEnabled(False)
        self.preflight_btn.setEnabled(False)
        self.sub2api_row.set_path("")
        self.cpa_row.set_path("")
        config = ExportConfig(
            input_path=input_path,
            out_dir=output_dir,
            concurrency=int(self.concurrency_spin.value()),
            pool=self.pool_combo.currentText().strip() or "plus-20",
            token_type=self.token_type_combo.currentText().strip() or "plus",
            otp_timeout=int(self.otp_timeout_spin.value()),
            otp_interval=int(self.otp_interval_spin.value()),
            timeout=int(self.timeout_spin.value()),
            input_format="auto",
        )

        def worker() -> None:
            try:
                summary = run_export(config, logger=self.bridge.log.emit, on_event=self.bridge.event.emit)
                self.bridge.done.emit(summary)
            except Exception as exc:
                self.bridge.failed.emit(f"{type(exc).__name__}: {exc}")

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _update_progress(self) -> None:
        total = max(1, int(self._total or 1))
        self.progress.setRange(0, total)
        self.progress.setValue(min(self._done, total))
        percent = int((min(self._done, total) / total) * 100) if self._total else 0
        self.percent_label.setText(f"{percent}%")

    def on_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "started":
            self._total = int(event.get("total") or 0)
            self.total_stat.set_value(self._total)
            self._update_progress()
        elif event_type == "row_start":
            self._running += 1
            self.running_stat.set_value(self._running)
        elif event_type == "row_done":
            self._done = int(event.get("done") or self._done + 1)
            self._running = max(0, self._running - 1)
            if event.get("ok"):
                self._success += 1
            else:
                self._failure += 1
            self.success_stat.set_value(self._success)
            self.failed_stat.set_value(self._failure)
            self.running_stat.set_value(self._running)
            self._update_progress()

    def on_done(self, summary: dict) -> None:
        self.run_btn.setEnabled(True)
        self.preflight_btn.setEnabled(True)
        self._set_status("●  Done", "done")
        self._done = int(summary.get("success_count", 0) or 0) + int(summary.get("failure_count", 0) or 0)
        self._running = 0
        self.running_stat.set_value(0)
        self._update_progress()
        sub2api_path = str(summary.get("sub2api_export") or "")
        cpa_path = str(summary.get("cpa_manifest") or "")
        self.sub2api_row.set_path(sub2api_path)
        self.cpa_row.set_path(cpa_path)
        self.append_log("")
        self.append_log(f"[summary] success={summary.get('success_count', 0)} failure={summary.get('failure_count', 0)}")
        if sub2api_path:
            self.append_log(f"[sub2api] {sub2api_path}")
        if cpa_path:
            self.append_log(f"[cpa] {cpa_path}")
        QMessageBox.information(self, "Complete", f"Export complete\nSuccess: {summary.get('success_count', 0)}\nFailed: {summary.get('failure_count', 0)}")

    def on_failed(self, message: str) -> None:
        self.run_btn.setEnabled(True)
        self.preflight_btn.setEnabled(True)
        self._running = 0
        self.running_stat.set_value(0)
        self._set_status("●  Failed", "failed")
        self.append_log(f"[fatal] {message}")
        QMessageBox.critical(self, "Run failed", message)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
