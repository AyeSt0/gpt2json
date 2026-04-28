from __future__ import annotations

import hashlib
import os
import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .engine import ExportConfig, run_export
from .parsing import decode_text_file, list_future_input_format_presets, list_input_formats, parse_by_format
from .updater import RELEASES_PAGE_URL, check_latest_release

APP_NAME = "GPT2JSON"
APP_VERSION = f"v{__version__}"
APP_SUBTITLE = "Sub2API / CPA JSON 导出工具"
ORG_NAME = "GPT2JSON"
ASSET_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSET_DIR / "gpt2json_icon.png"
ICON_ICO_PATH = ASSET_DIR / "gpt2json_icon.ico"
ICON_LIGHT_PATH = ASSET_DIR / "gpt2json_icon_light.png"
ICON_DARK_PATH = ASSET_DIR / "gpt2json_icon_dark.png"
APP_ICON_PATH = ICON_ICO_PATH if ICON_ICO_PATH.exists() else ICON_PATH
THEME_SUN_PATH = ASSET_DIR / "theme_sun.png"
THEME_MOON_PATH = ASSET_DIR / "theme_moon.png"
UI_INPUT_PATH = ASSET_DIR / "ui_input.png"
UI_SETTINGS_PATH = ASSET_DIR / "ui_settings.png"
UI_OUTPUT_PATH = ASSET_DIR / "ui_output.png"
UI_LOG_PATH = ASSET_DIR / "ui_log.png"
UI_UPLOAD_PATH = ASSET_DIR / "ui_upload.png"
UI_CHEVRON_DOWN_PATH = ASSET_DIR / "ui_chevron_down.png"
STAT_TOTAL_PATH = ASSET_DIR / "stat_total.png"
STAT_SUCCESS_PATH = ASSET_DIR / "stat_success.png"
STAT_FAILED_PATH = ASSET_DIR / "stat_failed.png"
STAT_RUNNING_PATH = ASSET_DIR / "stat_running.png"


def settings_file_path() -> Path:
    """Return the file-backed settings path.

    Qt's default QSettings backend writes to the Windows registry.  GPT2JSON keeps
    GUI preferences in an ini file instead so the application itself remains
    registry-free; only the optional installer creates the normal Windows
    uninstall entry.
    """

    override = os.environ.get("GPT2JSON_SETTINGS_PATH", "").strip()
    if override:
        return Path(override).expanduser()

    if sys.platform.startswith("win"):
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data) / APP_NAME / "settings.ini"

    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation)
    if base:
        return Path(base) / APP_NAME / "settings.ini"

    return Path.home() / ".gpt2json" / "settings.ini"


def create_app_settings() -> QSettings:
    path = settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return QSettings(str(path), QSettings.Format.IniFormat)

READY_LOG = "🟢 等待开始：请粘贴账号文本，或导入账号文件。\n📄 当前支持：自动识别 / LDXP Plus7 三段式 OTP。\n📮 说明：程序会优先尝试账密登录；只有服务端要求验证码时，才会访问输入里的取码源。"
_UI_FONT_FAMILY = ""

LIGHT_THEME = {
    "shell": "#F6F8FC",
    "card": "#FFFFFF",
    "soft": "#F8FAFD",
    "input": "#FFFFFF",
    "border": "#D9E2EF",
    "border2": "#CBD8EA",
    "text": "#0F172A",
    "muted": "#64748B",
    "muted2": "#94A3B8",
    "progress": "#E2E8F0",
    "log": "#FBFCFE",
    "shadow": "#8FA2BD",
    "status_bg": "#DCFCE7",
    "status_fg": "#15803D",
    "status_bd": "#B7E4C7",
}

DARK_THEME = {
    "shell": "#08111F",
    "card": "#0F1A29",
    "soft": "#142235",
    "input": "#101B2A",
    "border": "#26364A",
    "border2": "#334760",
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    "muted2": "#64748B",
    "progress": "#334155",
    "log": "#0C1624",
    "shadow": "#000000",
    "status_bg": "#123B2A",
    "status_fg": "#86EFAC",
    "status_bd": "#1F6B43",
}

LIGHT_LOG_COLORS = {
    "default": "#475569",
    "info": "#2563EB",
    "start": "#7C3AED",
    "account": "#334155",
    "otp": "#B45309",
    "output": "#0F766E",
    "success": "#15803D",
    "warning": "#B45309",
    "error": "#DC2626",
    "cancel": "#EA580C",
}

DARK_LOG_COLORS = {
    "default": "#CBD5E1",
    "info": "#93C5FD",
    "start": "#C4B5FD",
    "account": "#E2E8F0",
    "otp": "#FCD34D",
    "output": "#5EEAD4",
    "success": "#86EFAC",
    "warning": "#FBBF24",
    "error": "#FCA5A5",
    "cancel": "#FDBA74",
}


def classify_log_line(text: str) -> str:
    line = str(text or "").strip()
    if not line:
        return "default"
    if line.startswith(("✅", "🎉")) or line.startswith("成功：") or "任务完成：" in line:
        return "success"
    if line.startswith(("⚠️", "💥")) or line.startswith(("失败：", "主流程异常：")):
        return "error"
    if line.startswith("🛑") or line.startswith("取消"):
        return "cancel"
    if line.startswith("🔁"):
        return "warning"
    if line.startswith(("🚀", "🧩", "📦 任务")) or line.startswith(("开始导出：", "运行配置：")):
        return "start"
    if line.startswith(("👤", "🚪", "🛡️", "📨", "🔑", "🎫", "📦")):
        return "account"
    if line.startswith(("🧭", "🔎", "🧪", "🔄", "ℹ️", "✨", "👀", "🟢", "📄")):
        return "info"
    if line.startswith("🧾 失败诊断报告"):
        return "output"
    if line.startswith(("📮", "📫", "📬", "🧾", "⌛")) or "验证码" in line:
        return "otp"
    if line.startswith(("📁", "🧰", "📘", "📚")) or "输出：" in line or "输出目录：" in line:
        return "output"
    return "default"


class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, document: Any, *, theme: str = "light") -> None:
        super().__init__(document)
        self.theme = theme

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        colors = DARK_LOG_COLORS if self.theme == "dark" else LIGHT_LOG_COLORS
        kind = classify_log_line(text)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colors.get(kind, colors["default"])))
        if kind in {"success", "error", "cancel", "start"}:
            fmt.setFontWeight(QFont.Weight.DemiBold)
        self.setFormat(0, len(text), fmt)

        account_start = text.find("账号 #")
        if account_start >= 0:
            account_end = text.find("：", account_start)
            if account_end < 0:
                account_end = text.find(":", account_start)
            if account_end < 0:
                account_end = len(text)
            account_fmt = QTextCharFormat(fmt)
            account_fmt.setFontWeight(QFont.Weight.Bold)
            self.setFormat(account_start, max(0, account_end - account_start), account_fmt)


def load_ui_font() -> str:
    global _UI_FONT_FAMILY
    if _UI_FONT_FAMILY:
        return _UI_FONT_FAMILY
    for font_path in (Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\segoeui.ttf")):
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _UI_FONT_FAMILY = families[0]
                return _UI_FONT_FAMILY
    families = QFontDatabase.families()
    _UI_FONT_FAMILY = families[0] if families else "Sans Serif"
    return _UI_FONT_FAMILY


class WorkerBridge(QObject):
    log = Signal(str)
    event = Signal(dict)
    done = Signal(dict)
    failed = Signal(str)
    update_checked = Signal(dict)
    preflight_done = Signal(dict)


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


class FileDropBox(QFrame):
    clicked = Signal()
    path_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.path = ""
        self.setAcceptDrops(True)
        self.setObjectName("FileDropBox")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(8)
        icon = QLabel("TXT")
        icon.setObjectName("DropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if UI_UPLOAD_PATH.exists():
            icon.setPixmap(QPixmap(str(UI_UPLOAD_PATH)).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.icon = icon
        self.label = QLabel("拖入账号文件或点击选择")
        self.label.setObjectName("DropText")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        suffix = QLabel("支持 .txt · 自动识别账号格式")
        suffix.setObjectName("DropSuffix")
        suffix.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label)
        layout.addWidget(suffix)
        layout.addStretch(1)

    def _normalize_drop_value(self, value: str) -> str:
        text = str(value or "").strip().strip('"').strip("'")
        if text.startswith("file:///"):
            return QUrl(text).toLocalFile()
        return text

    def set_path(self, value: str) -> None:
        self.path = str(value or "").strip()
        self.label.setText(Path(self.path).name if self.path else "拖入账号文件或点击选择")
        self.setToolTip(self.path)
        self.path_changed.emit(self.path)

    def clear(self) -> None:
        self.set_path("")

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
            value = self._normalize_drop_value(mime.text())
        if value and Path(value).is_file():
            self.set_path(value)
            event.acceptProposedAction()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class SectionHeader(QWidget):
    def __init__(self, icon: str | Path, title: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        icon_label = QLabel()
        icon_label.setObjectName("SectionIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = Path(icon) if not isinstance(icon, Path) else icon
        if icon_path.exists():
            icon_label.setPixmap(QPixmap(str(icon_path)).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_label.setText(str(icon))
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch(1)


class InlineStat(QFrame):
    def __init__(self, icon: str | Path, title: str, color: str = "") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        icon_label = QLabel()
        icon_label.setObjectName("StatIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = Path(icon) if isinstance(icon, (str, Path)) else Path()
        if icon_path.exists():
            icon_label.setPixmap(QPixmap(str(icon_path)).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_label.setText(str(icon))
            if color:
                icon_label.setStyleSheet(f"background:{color};")
        title_label = QLabel(title)
        title_label.setObjectName("StatTitle")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("StatValue")
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        text.addWidget(title_label)
        text.addWidget(self.value_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)
        layout.addWidget(icon_label)
        layout.addLayout(text, 1)

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))


class FileOutputRow(QFrame):
    def __init__(self, filename: str, badge: str) -> None:
        super().__init__()
        self.setObjectName("OutputRow")
        self.path = ""
        self.default_filename = filename
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(10)
        badge_label = QLabel(badge)
        badge_label.setObjectName("OutputBadge")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label = QLabel(filename)
        self.name_label.setObjectName("OutputName")
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_btn = QToolButton()
        self.open_btn.setObjectName("CopyButton")
        self.open_btn.setText("打开")
        self.open_btn.setToolTip("打开文件")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_path)
        self.copy_btn = QToolButton()
        self.copy_btn.setObjectName("CopyButton")
        self.copy_btn.setText("复制")
        self.copy_btn.setToolTip("复制路径")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_path)
        layout.addWidget(badge_label)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.open_btn)
        layout.addWidget(self.copy_btn)

    def set_path(self, path: str) -> None:
        self.path = path
        self.name_label.setText(Path(path).name if path else self.default_filename)
        self.open_btn.setEnabled(bool(path))
        self.copy_btn.setEnabled(bool(path))
        self.setToolTip(path)

    def open_path(self) -> None:
        if self.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.path).resolve())))

    def copy_path(self) -> None:
        if self.path:
            QApplication.clipboard().setText(self.path)


class FormatCombo(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("FormatCombo")
        self.setFixedHeight(38)


class PresetNumberCombo(QComboBox):
    def __init__(self, *, minimum: int, presets: list[int], auto_text: str = "自动", maximum: int | None = None) -> None:
        super().__init__()
        self.minimum = int(minimum)
        self.maximum = int(maximum) if maximum is not None else None
        self.auto_text = auto_text
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setObjectName("PresetNumberCombo")
        self.setFixedHeight(38)
        self.addItem(auto_text, 0)
        for value in presets:
            if self.minimum <= int(value) and (self.maximum is None or int(value) <= self.maximum):
                self.addItem(str(int(value)), int(value))
        self.setCurrentIndex(0)

    def value(self) -> int:
        text = self.currentText().strip()
        if not text or text.lower() == "auto" or text == self.auto_text:
            return 0
        try:
            value = int(text)
        except Exception:
            return 0
        value = max(self.minimum, value)
        return min(self.maximum, value) if self.maximum is not None else value

    def setValue(self, value: int) -> None:
        value = max(self.minimum, int(value or 0))
        if self.maximum is not None:
            value = min(self.maximum, value)
        if value == 0:
            self.setCurrentIndex(0)
            self.setEditText(self.auto_text)
            return
        for index in range(self.count()):
            if int(self.itemData(index) or 0) == value:
                self.setCurrentIndex(index)
                return
        self.setEditText(str(value))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(980, 640)
        self.resize(1180, 740)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.settings = create_app_settings()
        self.bridge = WorkerBridge()
        self.bridge.log.connect(self.append_log)
        self.bridge.event.connect(self.on_event)
        self.bridge.done.connect(self.on_done)
        self.bridge.failed.connect(self.on_failed)
        self.bridge.update_checked.connect(self.on_update_checked)
        self.bridge.preflight_done.connect(self.on_preflight_done)
        self._worker_thread: threading.Thread | None = None
        self._preflight_thread: threading.Thread | None = None
        self._drag_start: Any = None
        self._theme = "light"
        self._update_check_running = False
        self._input_mode = "paste"
        self._clearing_input = False
        self._is_running = False
        self._is_cancelling = False
        self._cancel_event: threading.Event | None = None
        self._status_text = "就绪"
        self._status_mode = "ready"
        self._total = 0
        self._done = 0
        self._success = 0
        self._failure = 0
        self._running = 0
        self._last_preflight_count = 0
        self._last_preflight_raw_count = 0
        self._last_preflight_error = ""
        self._last_preflight_source = ""
        self._last_preflight_snapshot_key = ""
        self._preflight_seq = 0
        self._preflight_running = False
        self._log_waiting = True
        self._preflight_timer = QTimer(self)
        self._preflight_timer.setSingleShot(True)
        self._preflight_timer.setInterval(260)
        self._preflight_timer.timeout.connect(lambda: self.preflight(silent=True))
        self._build_ui()
        self._restore_settings()
        self.apply_style()
        self._refresh_input_mode()
        self._refresh_output_format_state()
        self._refresh_controls_state()

    def _build_ui(self) -> None:
        outer = QWidget(self)
        outer.setObjectName("Outer")
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        self.shell = QFrame()
        self.shell.setObjectName("Shell")
        self.shadow = QGraphicsDropShadowEffect(self.shell)
        self.shadow.setBlurRadius(28)
        self.shadow.setOffset(0, 10)
        self.shell.setGraphicsEffect(self.shadow)
        outer_layout.addWidget(self.shell)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(22, 18, 22, 18)
        shell_layout.setSpacing(14)
        shell_layout.addLayout(self._build_header())
        shell_layout.addLayout(self._build_content(), 1)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setObjectName("SizeGrip")
        self.size_grip.raise_()

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(14)
        self.logo = QLabel()
        self.logo.setObjectName("LogoImage")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._refresh_logo()

        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        self.version_badge = QToolButton()
        self.version_badge.setText(APP_VERSION)
        self.version_badge.setObjectName("VersionBadge")
        self.version_badge.setToolTip("检查 GitHub Release 更新")
        self.version_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_badge.clicked.connect(self.check_updates)
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("Subtitle")
        title_row.addWidget(title)
        title_row.addWidget(self.version_badge, 0, Qt.AlignmentFlag.AlignBottom)
        title_row.addStretch(1)
        title_stack.addLayout(title_row)
        title_stack.addWidget(subtitle)

        self.status_label = QLabel(self._status_text)
        self.status_label.setObjectName("StatusPill")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedWidth(94)
        # 状态变更现在只进入日志和进度区；顶部不再保留“就绪/运行中”胶囊，避免标题栏出现无意义占位。
        self.status_label.setVisible(False)
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("ThemeButton")
        self.theme_btn.setToolTip("切换深色 / 浅色")
        self.theme_btn.setIconSize(QSize(22, 22))
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.min_btn = self._window_button("−")
        self.max_btn = self._window_button("□")
        self.close_btn = self._window_button("×", close=True)
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self._toggle_max_restore)
        self.close_btn.clicked.connect(self.close)

        window_controls = QFrame()
        window_controls.setObjectName("WindowControls")
        controls_layout = QHBoxLayout(window_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addWidget(self.theme_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addSpacing(10)
        controls_layout.addWidget(self.min_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addWidget(self.max_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_layout.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addWidget(self.logo)
        header.addLayout(title_stack, 1)
        header.addWidget(window_controls, 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    def _build_content(self) -> QHBoxLayout:
        content = QHBoxLayout()
        content.setSpacing(14)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(self._build_input_card(), 62)
        top_row.addWidget(self._build_settings_card(), 38)
        left_layout.addLayout(top_row, 1)
        left_layout.addWidget(self._build_run_card(), 0)

        content.addWidget(left, 70)
        content.addWidget(self._build_right_column(), 30)
        return content

    def _build_input_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(SectionHeader(UI_INPUT_PATH, "账号输入"))

        tabs_frame = QFrame()
        tabs_frame.setObjectName("SegmentGroup")
        tabs = QHBoxLayout(tabs_frame)
        tabs.setContentsMargins(2, 2, 2, 2)
        tabs.setSpacing(0)
        self.paste_tab = QPushButton("粘贴文本")
        self.paste_tab.setObjectName("SegmentButton")
        self.paste_tab.setCheckable(True)
        self.paste_tab.setChecked(True)
        self.file_tab = QPushButton("导入文件")
        self.file_tab.setObjectName("SegmentButton")
        self.file_tab.setCheckable(True)
        self.input_mode_group = QButtonGroup(self)
        self.input_mode_group.setExclusive(True)
        self.input_mode_group.addButton(self.paste_tab)
        self.input_mode_group.addButton(self.file_tab)
        self.paste_tab.clicked.connect(lambda: self._select_input_mode("paste"))
        self.file_tab.clicked.connect(lambda: self._select_input_mode("file"))
        tabs.addWidget(self.paste_tab)
        tabs.addWidget(self.file_tab)
        layout.addWidget(tabs_frame)

        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        self.input_source_label = QLabel("当前来源：粘贴文本")
        self.input_source_label.setObjectName("SourcePill")
        self.clear_input_btn = QPushButton("全部清空")
        self.clear_input_btn.setObjectName("MiniButton")
        self.clear_input_btn.clicked.connect(self.clear_input)
        source_row.addWidget(self.input_source_label, 1)
        source_row.addWidget(self.clear_input_btn)
        layout.addLayout(source_row)

        self.input_stack = QStackedWidget()
        self.input_stack.setObjectName("InputStack")
        self.input_stack.setMinimumHeight(210)
        self.input_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.paste_edit = QPlainTextEdit()
        self.paste_edit.setObjectName("PasteBox")
        self.paste_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.paste_edit.setPlaceholderText("自动识别账号格式\n当前支持：GPT邮箱----GPT密码----OTP取码源\n每行一个账号，以当前选中的输入来源为准。")
        self.paste_edit.textChanged.connect(self._on_paste_changed)
        self.input_stack.addWidget(self.paste_edit)

        file_page = QWidget()
        file_page_layout = QVBoxLayout(file_page)
        file_page_layout.setContentsMargins(0, 0, 0, 0)
        file_page_layout.setSpacing(10)
        self.file_drop = FileDropBox()
        self.file_drop.clicked.connect(self.pick_input)
        self.file_drop.path_changed.connect(self._on_file_changed)
        file_page_layout.addWidget(self.file_drop, 1)
        self.input_stack.addWidget(file_page)
        layout.addWidget(self.input_stack, 1)

        self.input_hint_label = QLabel()
        self.input_hint_label.setObjectName("HintText")
        self.input_hint_label.setWordWrap(True)
        self.input_hint_label.setMinimumHeight(34)
        layout.addWidget(self.input_hint_label)
        return card

    def _build_settings_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        layout.addWidget(SectionHeader(UI_SETTINGS_PATH, "导出设置"))

        layout.addWidget(self._field_label("账号格式"))
        self.input_format_combo = FormatCombo()
        self.input_format_combo.addItem("自动识别（推荐）", "auto")
        for fmt in list_input_formats():
            self.input_format_combo.addItem(fmt.label, fmt.id)
            self.input_format_combo.setItemData(self.input_format_combo.count() - 1, fmt.description, Qt.ItemDataRole.ToolTipRole)
        for preset in list_future_input_format_presets():
            label = f"{preset.label}"
            self.input_format_combo.addItem(label, f"disabled:{preset.id}")
            index = self.input_format_combo.count() - 1
            self.input_format_combo.setItemData(index, preset.description or "预制格式，后续版本开放。", Qt.ItemDataRole.ToolTipRole)
            item = self.input_format_combo.model().item(index)
            if item is not None:
                item.setEnabled(False)
        self.input_format_combo.currentIndexChanged.connect(self._on_input_format_changed)
        layout.addWidget(self.input_format_combo)
        self._on_input_format_changed()

        layout.addWidget(self._field_label("导出格式"))
        format_row = QHBoxLayout()
        format_row.setSpacing(8)
        self.sub2api_check = self._chip_button("Sub2API JSON", checked=True)
        self.cpa_check = self._chip_button("CPA JSON", checked=True)
        self.sub2api_check.clicked.connect(self._refresh_output_format_state)
        self.cpa_check.clicked.connect(self._refresh_output_format_state)
        format_row.addWidget(self.sub2api_check)
        format_row.addWidget(self.cpa_check)
        format_row.addStretch(1)
        layout.addLayout(format_row)

        compact = QGridLayout()
        compact.setHorizontalSpacing(10)
        compact.setVerticalSpacing(6)
        compact.addWidget(self._field_label("并发数量"), 0, 0)
        compact.addWidget(self._field_label("验证码获取"), 0, 1)
        self.concurrency_spin = PresetNumberCombo(minimum=0, presets=[1, 2, 4, 8, 12, 16, 24, 32, 64])
        self.concurrency_spin.setToolTip("可下拉选择常用并发，也可以直接输入任意正整数；自动会按账号数上限 8。")
        self.backend_label = QLabel("按输入自动")
        self.backend_label.setObjectName("BackendPill")
        self.backend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        compact.addWidget(self.concurrency_spin, 1, 0)
        compact.addWidget(self.backend_label, 1, 1)
        compact.setColumnStretch(0, 1)
        compact.setColumnStretch(1, 2)
        layout.addLayout(compact)

        output_grid = QGridLayout()
        output_grid.setHorizontalSpacing(8)
        output_grid.addWidget(self._field_label("输出目录"), 0, 0, 1, 2)
        self.output_edit = DropLineEdit(directory=True)
        self.output_edit.setObjectName("PathEdit")
        self.output_edit.setText("output")
        self.output_edit.setPlaceholderText("选择输出目录")
        self.output_edit.textChanged.connect(self._refresh_controls_state)
        self.output_btn = QPushButton("浏览")
        self.output_btn.setObjectName("BrowseButton")
        self.output_btn.clicked.connect(self.pick_output)
        output_grid.addWidget(self.output_edit, 1, 0)
        output_grid.addWidget(self.output_btn, 1, 1)
        output_grid.setColumnStretch(0, 1)
        layout.addLayout(output_grid)

        self.advanced_btn = QToolButton()
        self.advanced_btn.setObjectName("AdvancedBar")
        self.advanced_btn.setText("高级选项（弹窗配置）  ›")
        self.advanced_btn.setCheckable(False)
        self.advanced_btn.clicked.connect(self.open_advanced_dialog)
        layout.addWidget(self.advanced_btn)

        self.timeout_spin = self._spin(10, 600, 30)
        self.otp_timeout_spin = self._spin(10, 600, 180)
        self.otp_interval_spin = self._spin(1, 60, 3)
        self.max_attempts_spin = self._spin(1, 5, 2)
        for spin in (self.timeout_spin, self.otp_timeout_spin, self.otp_interval_spin, self.max_attempts_spin):
            spin.setVisible(False)
        layout.addStretch(1)
        return card

    def _build_run_card(self) -> QFrame:
        card = self._card()
        card.setMinimumHeight(164)
        card.setMaximumHeight(176)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
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

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.total_stat = InlineStat(STAT_TOTAL_PATH, "总数")
        self.success_stat = InlineStat(STAT_SUCCESS_PATH, "成功")
        self.failed_stat = InlineStat(STAT_FAILED_PATH, "失败")
        self.running_stat = InlineStat(STAT_RUNNING_PATH, "运行中")
        for stat in (self.total_stat, self.success_stat, self.failed_stat, self.running_stat):
            stats.addWidget(stat, 1)
        layout.addLayout(stats)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.preflight_btn = QPushButton("预检查")
        self.preflight_btn.setObjectName("SecondaryButton")
        self.preflight_btn.clicked.connect(lambda: self.preflight(silent=False))
        self.run_btn = QPushButton("开始导出")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.clicked.connect(self.start_run)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setToolTip("请求取消当前导出；已在执行的账号会在安全点收尾。")
        self.cancel_btn.clicked.connect(self.cancel_run)
        self.open_out_btn = QPushButton("打开输出目录")
        self.open_out_btn.setObjectName("SecondaryButton")
        self.open_out_btn.clicked.connect(self.open_output_dir)
        buttons.addWidget(self.preflight_btn, 1)
        buttons.addWidget(self.run_btn, 2)
        buttons.addWidget(self.cancel_btn, 1)
        buttons.addWidget(self.open_out_btn, 1)
        layout.addLayout(buttons)
        return card

    def _build_right_column(self) -> QWidget:
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        output_card = self._card()
        output_card.setMaximumHeight(218)
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(16, 14, 16, 14)
        output_layout.setSpacing(12)
        output_layout.addWidget(SectionHeader(UI_OUTPUT_PATH, "导出结果"))
        self.output_hint_label = QLabel("任务完成后显示可打开的结果；未运行时这里保持精简。")
        self.output_hint_label.setObjectName("HintText")
        self.output_hint_label.setWordWrap(True)
        output_layout.addWidget(self.output_hint_label)
        self.sub2api_row = FileOutputRow("sub2api_accounts.secret.json", "Sub2API")
        self.cpa_row = FileOutputRow("cpa_tokens_*.zip + CPA/", "CPA")
        self.sub2api_row.setVisible(False)
        self.cpa_row.setVisible(False)
        output_layout.addWidget(self.sub2api_row)
        output_layout.addWidget(self.cpa_row)
        layout.addWidget(output_card, 0)

        log_card = self._card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 14, 16, 14)
        log_layout.setSpacing(12)
        log_layout.addWidget(SectionHeader(UI_LOG_PATH, "运行日志"))
        log_actions = QHBoxLayout()
        log_actions.setSpacing(8)
        self.copy_log_btn = QPushButton("复制日志")
        self.copy_log_btn.setObjectName("MiniButton")
        self.copy_log_btn.clicked.connect(self.copy_log)
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.setObjectName("MiniButton")
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_actions.addWidget(self.copy_log_btn)
        log_actions.addWidget(self.clear_log_btn)
        log_actions.addStretch(1)
        log_layout.addLayout(log_actions)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setObjectName("LogBox")
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlainText(READY_LOG)
        self.log_highlighter = LogHighlighter(self.log_edit.document(), theme=self._theme)
        log_layout.addWidget(self.log_edit, 1)
        layout.addWidget(log_card, 1)
        return right

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        return card

    def _window_button(self, text: str, *, close: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("CloseButton" if close else "WindowButton")
        button.setText(text)
        return button

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _chip_button(self, text: str, *, checked: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("ChipButton")
        button.setCheckable(True)
        button.setChecked(checked)
        return button

    def _small_badge(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SmallBadge")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setFixedHeight(38)
        return spin

    def palette(self) -> dict[str, str]:
        return DARK_THEME if self._theme == "dark" else LIGHT_THEME

    def _refresh_logo(self) -> None:
        icon_path = ICON_DARK_PATH if self._theme == "dark" else ICON_LIGHT_PATH
        if not icon_path.exists():
            icon_path = ICON_PATH
        if icon_path.exists():
            self.logo.setText("")
            self.logo.setPixmap(
                QPixmap(str(icon_path)).scaled(
                    50,
                    50,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.logo.setPixmap(QPixmap())
            self.logo.setText("GJ")

    def apply_style(self) -> None:
        p = self.palette()
        chevron_url = UI_CHEVRON_DOWN_PATH.as_posix()
        QApplication.instance().setFont(QFont(load_ui_font(), 10))  # type: ignore[union-attr]
        self.shadow.setColor(Qt.GlobalColor.black if self._theme == "dark" else Qt.GlobalColor.gray)
        self._refresh_logo()
        self.theme_btn.setText("")
        icon_path = THEME_SUN_PATH if self._theme == "dark" else THEME_MOON_PATH
        self.theme_btn.setToolTip("切换到浅色模式" if self._theme == "dark" else "切换到深色模式")
        if icon_path.exists():
            self.theme_btn.setIcon(QIcon(str(icon_path)))
        else:
            self.theme_btn.setText("☀" if self._theme == "dark" else "☾")
        self.setStyleSheet(
            f"""
            #Outer {{ background: transparent; }}
            #Shell {{ background:{p['shell']}; border:1px solid {p['border']}; border-radius:18px; }}
            #SizeGrip {{ width:18px; height:18px; }}
            #LogoImage {{ min-width:50px; max-width:50px; min-height:50px; max-height:50px; border-radius:14px; }}
            #Title {{ color:{p['text']}; font-size:26px; font-weight:900; letter-spacing:-0.6px; }}
            #VersionBadge {{ color:#2563EB; background:{p['soft']}; border:1px solid {p['border']}; border-radius:8px; padding:2px 7px; font-size:11px; font-weight:900; margin-bottom:4px; }}
            #Subtitle {{ color:{p['muted']}; font-size:14px; font-weight:500; }}
            #StatusPill {{ border-radius:14px; padding:6px 15px; min-width:50px; font-size:13px; font-weight:800; }}
            #WindowControls {{ min-height:40px; max-height:40px; }}
            #ThemeButton {{ border:1px solid {p['border']}; background:{p['card']}; color:{p['text']}; min-width:36px; max-width:36px; min-height:36px; max-height:36px; border-radius:18px; font-family:'Segoe UI Symbol','Microsoft YaHei UI'; font-size:16px; }}
            #ThemeButton:hover {{ border-color:#60A5FA; color:#2563EB; }}
            #WindowButton, #CloseButton {{ border:none; background:transparent; color:{p['text']}; font-size:18px; min-width:36px; max-width:36px; min-height:36px; max-height:36px; border-radius:10px; padding:0; }}
            #WindowButton:hover {{ background:{p['soft']}; }}
            #CloseButton:hover {{ background:#EF4444; color:white; }}
            #Card {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:13px; }}
            #SectionIcon {{ color:#2563EB; min-width:22px; max-width:22px; font-size:18px; }}
            #SectionTitle {{ color:{p['text']}; font-size:17px; font-weight:900; }}
            #FieldLabel {{ color:{p['text']}; font-size:12px; font-weight:800; }}
            #HintText {{ color:{p['muted']}; font-size:12px; }}
            #SourcePill {{ min-height:30px; border-radius:8px; padding:0 10px; color:{p['muted']}; background:{p['soft']}; border:1px solid {p['border']}; font-size:12px; font-weight:800; }}
            #SegmentGroup {{ min-height:38px; border:1px solid {p['border']}; border-radius:9px; background:{p['soft']}; }}
            #SegmentButton {{ min-height:34px; border:none; border-radius:7px; color:{p['muted']}; background:transparent; font-size:13px; font-weight:800; }}
            #SegmentButton:hover {{ color:#2563EB; background:{p['input']}; }}
            #SegmentButton:checked {{ color:#2563EB; background:{p['input']}; }}
            #PasteBox {{ border-radius:9px; padding:10px; color:{p['text']}; background:{p['input']}; border:1px solid #3B82F6; font-family:Consolas, 'Microsoft YaHei UI', monospace; font-size:12px; }}
            #PasteBox:focus {{ border:1px solid #60A5FA; }}
            #FileDropBox {{ min-height:44px; border-radius:9px; background:{p['soft']}; border:1px dashed {p['border2']}; }}
            #FileDropBox:hover {{ border-color:#3B82F6; }}
            #DropIcon {{ color:{p['muted']}; font-size:12px; font-weight:800; }}
            #DropText {{ color:{p['text']}; font-size:14px; font-weight:900; }}
            #DropSuffix {{ color:{p['muted']}; font-size:12px; font-weight:800; }}
            QLineEdit, QSpinBox, QComboBox {{ min-height:36px; border-radius:8px; padding-left:10px; padding-right:8px; color:{p['text']}; background:{p['input']}; border:1px solid {p['border']}; font-size:12px; font-weight:700; }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border:1px solid #60A5FA; }}
            QComboBox::drop-down {{ width:24px; border:none; background:transparent; }}
            QComboBox::down-arrow {{ image:url("{chevron_url}"); width:10px; height:10px; margin-right:7px; }}
            QComboBox QAbstractItemView {{ color:{p['text']}; background:{p['card']}; border:1px solid {p['border']}; selection-background-color:#2563EB; selection-color:white; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width:20px; border:none; background:transparent; }}
            #BrowseButton {{ min-height:36px; min-width:62px; border-radius:8px; color:{p['text']}; background:{p['soft']}; border:1px solid {p['border']}; font-weight:800; }}
            #MiniButton {{ min-height:30px; padding:0 10px; border-radius:8px; color:{p['muted']}; background:{p['soft']}; border:1px solid {p['border']}; font-size:12px; font-weight:800; }}
            #BrowseButton:hover, #AdvancedBar:hover, #SecondaryButton:hover, #MiniButton:hover {{ border-color:#3B82F6; color:#2563EB; }}
            #ChipButton {{ min-height:38px; padding:0 12px; border-radius:8px; color:{p['muted']}; background:{p['soft']}; border:1px solid {p['border']}; font-size:12px; font-weight:900; }}
            #ChipButton:checked {{ color:white; border:1px solid #2563EB; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #7C3AED); }}
            #ChipButton:disabled {{ color:{p['muted2']}; background:{p['progress']}; border:1px solid {p['border']}; }}
            #BackendPill, #SmallBadge {{ min-height:36px; border-radius:8px; padding:0 9px; color:{p['muted']}; background:{p['soft']}; border:1px solid {p['border']}; font-size:12px; font-weight:800; }}
            #SmallBadge {{ min-width:52px; max-height:26px; min-height:26px; color:{p['muted2']}; }}
            #AdvancedBar {{ min-height:38px; border-radius:8px; padding:0 12px; text-align:left; color:{p['muted']}; background:{p['soft']}; border:1px solid {p['border']}; font-size:12px; font-weight:800; }}
            #Progress {{ height:9px; border-radius:5px; border:none; background:{p['progress']}; }}
            #Progress::chunk {{ border-radius:5px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #7C3AED); }}
            #PercentLabel {{ color:#2563EB; font-size:13px; font-weight:900; min-width:32px; }}
            #StatCard {{ background:{p['soft']}; border:1px solid {p['border']}; border-radius:9px; }}
            #StatIcon {{ color:white; min-width:38px; max-width:38px; min-height:38px; max-height:38px; border-radius:12px; font-size:11px; font-weight:900; }}
            #StatTitle {{ color:{p['muted']}; font-size:11px; font-weight:700; }}
            #StatValue {{ color:{p['text']}; font-size:21px; font-weight:900; }}
            #PrimaryButton {{ min-height:44px; border:none; border-radius:9px; color:white; font-weight:900; font-size:14px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1677FF,stop:1 #7C3AED); }}
            #PrimaryButton:hover {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0F63D6,stop:1 #6D28D9); }}
            #PrimaryButton:disabled, #SecondaryButton:disabled {{ background:{p['progress']}; color:{p['muted2']}; border:1px solid {p['border']}; }}
            #SecondaryButton {{ min-height:42px; border-radius:9px; color:{p['text']}; background:{p['soft']}; border:1px solid {p['border']}; font-weight:900; font-size:13px; }}
            #OutputRow {{ min-height:54px; background:{p['soft']}; border:1px solid {p['border']}; border-radius:9px; }}
            #OutputBadge {{ color:white; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #2563EB,stop:1 #7C3AED); min-width:54px; max-width:54px; min-height:26px; max-height:26px; border-radius:7px; font-size:10px; font-weight:900; }}
            #OutputName {{ color:{p['text']}; font-size:12px; font-weight:700; }}
            #CopyButton {{ border:none; background:transparent; color:{p['muted2']}; min-width:42px; max-width:42px; min-height:28px; max-height:28px; border-radius:6px; font-size:11px; font-weight:800; }}
            #CopyButton:hover {{ color:#2563EB; background:{p['card']}; }}
            #LogBox {{ border-radius:9px; border:1px solid {p['border']}; background:{p['log']}; color:{p['muted']}; padding:11px; font-family:Consolas, 'Cascadia Mono', monospace; font-size:12px; }}
            """
        )
        if hasattr(self, "log_highlighter"):
            self.log_highlighter.set_theme(self._theme)
        self._apply_status_style()

    def _apply_status_style(self) -> None:
        dark = self._theme == "dark"
        if self._status_mode == "ready":
            style = "color:transparent;background:transparent;border:1px solid transparent;"
            self.status_label.setText("")
        elif self._status_mode == "running":
            style = (
                "color:#C4B5FD;background:#24154B;border:1px solid #5B21B6;"
                if dark
                else "color:#6D28D9;background:#EDE9FE;border:1px solid #DDD6FE;"
            )
        elif self._status_mode == "warning":
            style = (
                "color:#FDE68A;background:#3A2607;border:1px solid #92400E;"
                if dark
                else "color:#B45309;background:#FEF3C7;border:1px solid #FDE68A;"
            )
        elif self._status_mode == "failed":
            style = (
                "color:#FCA5A5;background:#3F1212;border:1px solid #7F1D1D;"
                if dark
                else "color:#DC2626;background:#FEE2E2;border:1px solid #FECACA;"
            )
        else:
            p = self.palette()
            style = f"color:{p['status_fg']};background:{p['status_bg']};border:1px solid {p['status_bd']};"
            self.status_label.setText(self._status_text)
        if self._status_mode != "ready":
            self.status_label.setText(self._status_text)
        self.status_label.setStyleSheet(style + "border-radius:14px;padding:6px 8px;min-width:94px;max-width:94px;font-size:13px;font-weight:800;")

    def toggle_theme(self) -> None:
        self._theme = "dark" if self._theme == "light" else "light"
        self.apply_style()
        self._save_settings()

    def check_updates(self) -> None:
        if self._update_check_running:
            return
        self._update_check_running = True
        self.version_badge.setEnabled(False)
        self.version_badge.setText("检查中")
        self.append_log("🔄 更新检查：正在查询 GitHub Release；只检查版本，不会自动替换本地程序。")

        def worker() -> None:
            info = check_latest_release(__version__)
            self.bridge.update_checked.emit(info.as_dict())

        threading.Thread(target=worker, name="gpt2json-update-check", daemon=True).start()

    def on_update_checked(self, info: dict[str, Any]) -> None:
        self._update_check_running = False
        self.version_badge.setEnabled(True)
        self.version_badge.setText(APP_VERSION)

        error = str(info.get("error") or "").strip()
        html_url = str(info.get("html_url") or RELEASES_PAGE_URL)
        if error:
            self.append_log(f"ℹ️ 更新检查：{error}")
            QMessageBox.information(self, "检查更新", f"{error}\n\n如果还没发布正式版，可以继续使用当前构建。")
            return

        latest = str(info.get("tag_name") or info.get("latest_version") or "").strip()
        if bool(info.get("update_available")):
            self.append_log(f"✨ 更新检查：发现新版本 {latest}，可前往 GitHub Release 下载。")
            answer = QMessageBox.question(
                self,
                "发现新版本",
                f"当前版本：{APP_VERSION}\n最新版本：{latest}\n\n是否打开 GitHub Release 下载页？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(html_url))
            return

        self.append_log(f"✅ 更新检查：当前已经是最新发布版 {latest or APP_VERSION}。")
        QMessageBox.information(self, "检查更新", f"当前已经是最新发布版：{latest or APP_VERSION}")

    def _restore_settings(self) -> None:
        def int_setting(key: str, default: int, minimum: int, maximum: int | None = None) -> int:
            try:
                value = int(self.settings.value(key, default) or default)
            except Exception:
                value = default
            value = max(minimum, value)
            return min(maximum, value) if maximum is not None else value

        theme = str(self.settings.value("theme", "light") or "light")
        self._theme = "dark" if theme == "dark" else "light"
        output_dir = str(self.settings.value("output_dir", "output") or "output")
        self.output_edit.setText(output_dir)
        input_format = str(self.settings.value("input_format", "auto") or "auto")
        for index in range(self.input_format_combo.count()):
            item = self.input_format_combo.model().item(index)
            if str(self.input_format_combo.itemData(index) or "") == input_format and item is not None and item.isEnabled():
                self.input_format_combo.setCurrentIndex(index)
                break
        self.sub2api_check.setChecked(str(self.settings.value("export_sub2api", "true")).lower() != "false")
        self.cpa_check.setChecked(str(self.settings.value("export_cpa", "true")).lower() != "false")
        self.concurrency_spin.setValue(int_setting("concurrency", 0, 0))
        self.timeout_spin.setValue(int_setting("timeout", 30, 10, 600))
        self.otp_timeout_spin.setValue(int_setting("otp_timeout", 180, 10, 600))
        self.otp_interval_spin.setValue(int_setting("otp_interval", 3, 1, 60))
        self.max_attempts_spin.setValue(int_setting("max_attempts", 2, 1, 5))
        self.advanced_btn.setText("高级选项（弹窗配置）  ›")

    def _save_settings(self) -> None:
        self.settings.setValue("theme", self._theme)
        self.settings.setValue("output_dir", self.output_edit.text().strip() or "output")
        self.settings.setValue("input_format", self._input_format())
        self.settings.setValue("export_sub2api", self.sub2api_check.isChecked())
        self.settings.setValue("export_cpa", self.cpa_check.isChecked())
        self.settings.setValue("concurrency", int(self.concurrency_spin.value()))
        self.settings.setValue("timeout", int(self.timeout_spin.value()))
        self.settings.setValue("otp_timeout", int(self.otp_timeout_spin.value()))
        self.settings.setValue("otp_interval", int(self.otp_interval_spin.value()))
        self.settings.setValue("max_attempts", int(self.max_attempts_spin.value()))
        self.settings.sync()

    def _schedule_preflight(self) -> None:
        if self._is_running:
            return
        self._last_preflight_count = 0
        self._last_preflight_raw_count = 0
        self._last_preflight_error = ""
        self._last_preflight_snapshot_key = ""
        self._preflight_seq += 1
        self._preflight_running = False
        if self._has_active_input():
            self._set_status("预检查中", "running")
        self._preflight_timer.start()
        self._refresh_controls_state()

    def _reset_counts(self, total: int = 0) -> None:
        if not hasattr(self, "total_stat"):
            return
        self._total = int(total or 0)
        self._done = self._success = self._failure = self._running = 0
        self.total_stat.set_value(self._total)
        self.success_stat.set_value(0)
        self.failed_stat.set_value(0)
        self.running_stat.set_value(0)
        self._update_progress()

    def _active_input_label(self) -> str:
        if self._input_mode == "file":
            path = self._input_path()
            return f"当前来源：文件 · {Path(path).name}" if path else "当前来源：文件 · 等待选择"
        count = len([line for line in self._paste_text().splitlines() if line.strip()])
        return f"当前来源：粘贴文本 · {count} 行原始文本" if count else "当前来源：粘贴文本"

    def _refresh_input_mode(self) -> None:
        is_paste = self._input_mode == "paste"
        self.paste_tab.setChecked(is_paste)
        self.file_tab.setChecked(not is_paste)
        self.input_stack.setCurrentIndex(0 if is_paste else 1)
        self.input_source_label.setText(self._active_input_label())
        self._refresh_controls_state()

    def _select_input_mode(self, mode: str) -> None:
        self._input_mode = "file" if mode == "file" else "paste"
        self._refresh_input_mode()
        if self._input_mode == "paste":
            self.paste_edit.setFocus()
        if self._has_active_input():
            self._schedule_preflight()
        else:
            self._last_preflight_count = 0
            self._last_preflight_raw_count = 0
            self._last_preflight_error = ""
            self._last_preflight_snapshot_key = ""
            self._reset_counts(0)
            self._set_status("就绪", "ready")
            self._refresh_controls_state()

    def _on_file_changed(self, _path: str = "") -> None:
        if self._clearing_input:
            return
        self._input_mode = "file"
        self._refresh_input_mode()
        self._schedule_preflight()

    def _refresh_output_format_state(self, *_args: Any) -> None:
        if hasattr(self, "sub2api_row"):
            any_selected = self.sub2api_check.isChecked() or self.cpa_check.isChecked()
            has_sub2api = bool(self.sub2api_row.path)
            has_cpa = bool(self.cpa_row.path)
            has_result = has_sub2api or has_cpa
            self.sub2api_row.setVisible(has_sub2api)
            self.cpa_row.setVisible(has_cpa)
            self.sub2api_row.setEnabled(has_sub2api)
            self.cpa_row.setEnabled(has_cpa)
            if self._is_running:
                self.output_hint_label.setText("正在导出，完成后这里会自动出现文件 / 文件夹入口。")
            elif has_result:
                self.output_hint_label.setText("已生成结果，可直接打开或复制路径。")
            elif any_selected:
                self.output_hint_label.setText("结果区会在导出完成后显示；平时不用在这里操作。")
            else:
                self.output_hint_label.setText("请至少勾选一种导出格式。")
        self._refresh_controls_state()

    def clear_input(self) -> None:
        if self._is_running:
            return
        current_mode = self._input_mode
        self._clearing_input = True
        try:
            self.paste_edit.clear()
            self.file_drop.clear()
        finally:
            self._clearing_input = False
        self._input_mode = current_mode
        self._last_preflight_count = 0
        self._last_preflight_raw_count = 0
        self._last_preflight_error = ""
        self._last_preflight_snapshot_key = ""
        self._refresh_input_mode()
        self._reset_counts(0)
        self._set_status("就绪", "ready")

    def copy_log(self) -> None:
        QApplication.clipboard().setText(self.log_edit.toPlainText())
        self._set_status("日志已复制", "done")

    def clear_log(self) -> None:
        self.log_edit.setPlainText(READY_LOG)
        self._log_waiting = True

    def _has_active_input(self) -> bool:
        if self._input_mode == "paste":
            return bool(self._paste_text())
        path = Path(self._input_path())
        return bool(str(path)) and path.exists() and path.is_file()

    def _refresh_controls_state(self, *_args: Any) -> None:
        if not hasattr(self, "run_btn"):
            return
        output_selected = self.sub2api_check.isChecked() or self.cpa_check.isChecked()
        has_output = bool(self.output_edit.text().strip())
        has_input = self._has_active_input()
        has_valid_rows = self._last_preflight_count > 0 and not self._last_preflight_error
        can_start = (not self._is_running) and (not self._preflight_running) and output_selected and has_output and has_input and has_valid_rows
        self.run_btn.setEnabled(can_start)
        self.run_btn.setText("取消中..." if self._is_cancelling else "开始导出")
        self.cancel_btn.setVisible(self._is_running)
        self.cancel_btn.setEnabled(self._is_running and not self._is_cancelling)
        self.cancel_btn.setText("取消中..." if self._is_cancelling else "取消")
        self.preflight_btn.setText("预检查中..." if self._preflight_running else "预检查")
        self.preflight_btn.setEnabled((not self._is_running) and (not self._preflight_running) and has_input)
        self.clear_input_btn.setEnabled(not self._is_running and (bool(self._paste_text()) or bool(self._input_path())))
        if hasattr(self, "clear_log_btn"):
            self.clear_log_btn.setEnabled(not self._is_running)
        if hasattr(self, "copy_log_btn"):
            self.copy_log_btn.setEnabled(True)
        for widget in (
            self.paste_tab,
            self.file_tab,
            self.paste_edit,
            self.file_drop,
            self.input_format_combo,
            self.sub2api_check,
            self.cpa_check,
            self.concurrency_spin,
            self.output_edit,
            self.output_btn,
            self.advanced_btn,
            self.timeout_spin,
            self.otp_timeout_spin,
            self.otp_interval_spin,
            self.max_attempts_spin,
        ):
            widget.setEnabled(not self._is_running)
        self.open_out_btn.setEnabled(bool(has_output))

    def _set_running(self, running: bool) -> None:
        self._is_running = bool(running)
        if not running:
            self._is_cancelling = False
            self._cancel_event = None
        self._refresh_controls_state()

    def cancel_run(self) -> None:
        if not self._is_running:
            return
        if self._cancel_event is not None:
            self._cancel_event.set()
        if not self._is_cancelling:
            self._is_cancelling = True
            self._set_status("取消中", "warning")
            self.append_log("🛑 取消请求：已发送。不会再推进新账号，正在等待运行中的账号到安全点收尾。")
        self._refresh_controls_state()

    def _validate_output_dir(self, *, create: bool = False) -> tuple[bool, str]:
        raw = self.output_edit.text().strip() or "output"
        path = Path(raw)
        if path.exists() and path.is_file():
            return False, "输出目录不能是已有文件。"
        try:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            parent = path if path.exists() else path.parent
            if parent and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
            probe_dir = path if path.exists() else parent
            if probe_dir and probe_dir.exists():
                probe = probe_dir / ".gpt2json_write_test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
        except Exception as exc:
            return False, f"输出目录不可写：{type(exc).__name__}: {exc}"
        return True, ""

    def _on_paste_changed(self) -> None:
        if self._clearing_input:
            return
        if self._paste_text():
            self._input_mode = "paste"
        self._refresh_input_mode()
        self._schedule_preflight()

    def _on_input_format_changed(self) -> None:
        format_id = self._input_format()
        if format_id == "auto":
            self.paste_edit.setPlaceholderText("粘贴账号文本，或导入账号文件。\n每行一个账号；字段含义以识别到的账号格式为准。\n当前默认自动识别。")
            self.input_hint_label.setText("自动识别：字段语义以识别到的账号格式为准。")
        else:
            for fmt in list_input_formats():
                if fmt.id == format_id:
                    self.paste_edit.setPlaceholderText(fmt.placeholder or fmt.description or fmt.label)
                    self.input_hint_label.setText(fmt.description or "字段语义以当前账号格式为准。")
                    break
        self._schedule_preflight()

    def _toggle_max_restore(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()
        self.max_btn.setText("❐" if self.isMaximized() else "□")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 88:
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

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if hasattr(self, "size_grip"):
            grip_size = self.size_grip.sizeHint()
            margin = 8
            self.size_grip.move(
                self.width() - grip_size.width() - margin,
                self.height() - grip_size.height() - margin,
            )
            self.size_grip.raise_()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 88:
            self._toggle_max_restore()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._is_running:
            answer = QMessageBox.question(
                self,
                "任务仍在运行",
                "当前导出任务还在运行。建议先取消并等待收尾，避免留下半成品。\n\n是否现在请求取消？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.cancel_run()
            event.ignore()
            return
        self._save_settings()
        super().closeEvent(event)

    def open_advanced_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("高级选项")
        dialog.setModal(True)
        dialog.setObjectName("AdvancedDialog")
        dialog.setFixedSize(500, 336)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        title = QLabel("高级选项")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("这些参数只影响下一次导出；普通情况下保持默认即可。")
        subtitle.setObjectName("DialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        http_spin = self._spin(10, 600, int(self.timeout_spin.value()))
        otp_spin = self._spin(10, 600, int(self.otp_timeout_spin.value()))
        interval_spin = self._spin(1, 60, int(self.otp_interval_spin.value()))
        attempts_spin = self._spin(1, 5, int(self.max_attempts_spin.value()))
        for spin in (http_spin, otp_spin, interval_spin, attempts_spin):
            spin.setFixedWidth(110)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        def add_row(row: int, label: str, help_text: str, spin: QSpinBox) -> None:
            label_box = QVBoxLayout()
            label_box.setContentsMargins(0, 0, 0, 0)
            label_box.setSpacing(2)
            name = QLabel(label)
            name.setObjectName("DialogField")
            desc = QLabel(help_text)
            desc.setObjectName("DialogHelp")
            label_box.addWidget(name)
            label_box.addWidget(desc)
            grid.addLayout(label_box, row, 0)
            grid.addWidget(spin, row, 1)

        add_row(0, "HTTP 请求超时（秒）", "登录、OAuth、接口请求的单次等待时间。", http_spin)
        add_row(1, "验证码等待超时（秒）", "触发邮箱验证码后，最多轮询取码源多久。", otp_spin)
        add_row(2, "验证码轮询间隔（秒）", "两次取码请求之间的间隔，过低可能触发限流。", interval_spin)
        add_row(3, "自动重试次数", "单账号遇到瞬时超时/网络抖动时最多尝试几次，默认 2。", attempts_spin)
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        p = self.palette()
        dialog.setStyleSheet(
            f"""
            #AdvancedDialog {{ background:{p['card']}; }}
            #DialogTitle {{ color:{p['text']}; font-size:18px; font-weight:900; }}
            #DialogSubtitle, #DialogHelp {{ color:{p['muted']}; font-size:12px; }}
            #DialogField {{ color:{p['text']}; font-size:13px; font-weight:800; }}
            QSpinBox {{ min-height:36px; border-radius:8px; padding-left:10px; padding-right:8px; color:{p['text']}; background:{p['input']}; border:1px solid {p['border']}; font-size:12px; font-weight:800; }}
            QSpinBox:focus {{ border:1px solid #60A5FA; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width:20px; border:none; background:transparent; }}
            QPushButton {{ min-height:32px; min-width:72px; border-radius:8px; color:{p['text']}; background:{p['soft']}; border:1px solid {p['border']}; font-weight:800; }}
            QPushButton:hover {{ border-color:#3B82F6; color:#2563EB; }}
            """
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.timeout_spin.setValue(http_spin.value())
            self.otp_timeout_spin.setValue(otp_spin.value())
            self.otp_interval_spin.setValue(interval_spin.value())
            self.max_attempts_spin.setValue(attempts_spin.value())
            self._save_settings()

    def _set_status(self, text: str, mode: str) -> None:
        self._status_text = text.replace("●", "").strip()
        self._status_mode = mode
        self._apply_status_style()

    def append_log(self, text: str) -> None:
        if self._log_waiting:
            self.log_edit.clear()
            self._log_waiting = False
        scroll_bar = self.log_edit.verticalScrollBar()
        should_follow = scroll_bar.value() >= scroll_bar.maximum() - 24
        self.log_edit.appendPlainText(text)
        if should_follow:
            scroll_bar.setValue(scroll_bar.maximum())

    def pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择账号文件", str(Path.cwd()), "文本文件 (*.txt);;所有文件 (*)")
        if path:
            self.file_drop.set_path(path)
            self._input_mode = "file"
            self._refresh_input_mode()
            self._schedule_preflight()

    def pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_edit.text() or str(Path.cwd()))
        if path:
            self.output_edit.setText(path)
            self._save_settings()

    def open_output_dir(self) -> None:
        path = Path(self.output_edit.text().strip() or "output")
        ok, message = self._validate_output_dir(create=True)
        if not ok:
            QMessageBox.warning(self, "输出目录不可用", message)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _paste_text(self) -> str:
        return self.paste_edit.toPlainText().strip()

    def _input_path(self) -> str:
        return self.file_drop.path.strip()

    def _input_format(self) -> str:
        if not hasattr(self, "input_format_combo"):
            return "auto"
        value = self.input_format_combo.currentData()
        return str(value or "auto")

    def _input_format_label(self) -> str:
        if not hasattr(self, "input_format_combo"):
            return "自动识别"
        return str(self.input_format_combo.currentText() or "自动识别")

    def _selected_output_labels(self) -> str:
        labels: list[str] = []
        if self.sub2api_check.isChecked():
            labels.append("Sub2API JSON")
        if self.cpa_check.isChecked():
            labels.append("CPA JSON")
        return " + ".join(labels)

    def _make_preflight_snapshot(self, *, silent: bool) -> dict[str, Any]:
        input_format = self._input_format()
        mode = self._input_mode
        if mode == "paste":
            paste_text = self._paste_text()
            digest = hashlib.sha256(paste_text.encode("utf-8")).hexdigest()
            return {
                "mode": "paste",
                "source": paste_text,
                "source_label": "paste",
                "format_id": input_format,
                "key": f"paste:{input_format}:{digest}",
                "has_input": bool(paste_text),
                "silent": bool(silent),
            }

        raw_path = self._input_path()
        path = Path(raw_path)
        key = f"file:{input_format}:{raw_path}:missing"
        source_label = "file"
        has_input = False
        try:
            if raw_path and path.exists() and path.is_file():
                stat = path.stat()
                resolved = str(path.resolve())
                key = f"file:{input_format}:{resolved}:{stat.st_size}:{stat.st_mtime_ns}"
                source_label = resolved
                has_input = True
        except Exception:
            pass
        return {
            "mode": "file",
            "source": raw_path,
            "source_label": source_label,
            "format_id": input_format,
            "key": key,
            "has_input": has_input,
            "silent": bool(silent),
        }

    @staticmethod
    def _evaluate_preflight_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        mode = str(snapshot.get("mode") or "paste")
        source = str(snapshot.get("source") or "")
        format_id = str(snapshot.get("format_id") or "auto")
        if mode == "paste":
            if not source.strip():
                return {"has_input": False, "row_count": 0, "raw_count": 0, "source": "paste"}
            lines = source.splitlines()
            rows = parse_by_format(lines, format_id=format_id)
            return {"has_input": True, "row_count": len(rows), "raw_count": len([line for line in lines if str(line).strip()]), "source": "paste"}

        input_path = Path(source)
        if not input_path.exists() or not input_path.is_file():
            return {"has_input": False, "row_count": 0, "raw_count": 0, "source": "file"}
        lines = decode_text_file(input_path).splitlines()
        rows = parse_by_format(lines, format_id=format_id)
        return {"has_input": True, "row_count": len(rows), "raw_count": len([line for line in lines if str(line).strip()]), "source": str(input_path)}

    def _current_preflight_cache_valid(self) -> bool:
        snapshot = self._make_preflight_snapshot(silent=True)
        return (
            bool(snapshot.get("has_input"))
            and bool(self._last_preflight_snapshot_key)
            and self._last_preflight_snapshot_key == snapshot.get("key")
            and self._last_preflight_count > 0
            and not self._last_preflight_error
        )

    def preflight(self, silent: bool = False) -> bool:
        if self._is_running:
            return True
        snapshot = self._make_preflight_snapshot(silent=silent)
        if not snapshot.get("has_input"):
            result = {
                "seq": self._preflight_seq + 1,
                "key": snapshot.get("key", ""),
                "silent": bool(silent),
                "has_input": False,
                "row_count": 0,
                "raw_count": 0,
                "source": snapshot.get("source_label", ""),
                "error": "",
            }
            self._preflight_seq = int(result["seq"])
            self.on_preflight_done(result)
            return False

        self._preflight_seq += 1
        seq = self._preflight_seq
        snapshot["seq"] = seq
        self._preflight_running = True
        self._set_status("预检查中", "running")
        self._refresh_controls_state()

        def worker() -> None:
            try:
                result = self._evaluate_preflight_snapshot(snapshot)
                result["error"] = ""
            except Exception as exc:
                result = {
                    "has_input": False,
                    "row_count": 0,
                    "raw_count": 0,
                    "source": snapshot.get("source_label", ""),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            result.update({"seq": seq, "key": snapshot.get("key", ""), "silent": bool(silent)})
            self.bridge.preflight_done.emit(result)

        self._preflight_thread = threading.Thread(target=worker, name="gpt2json-preflight", daemon=True)
        self._preflight_thread.start()
        return self._current_preflight_cache_valid()

    def on_preflight_done(self, result: dict[str, Any]) -> None:
        if int(result.get("seq") or 0) != self._preflight_seq:
            return
        self._preflight_running = False
        if self._is_running:
            self._refresh_controls_state()
            return
        silent = bool(result.get("silent"))
        error = str(result.get("error") or "")
        has_input = bool(result.get("has_input"))
        row_count = int(result.get("row_count") or 0)
        raw_count = int(result.get("raw_count") or 0)
        self._last_preflight_source = str(result.get("source") or "")
        self._last_preflight_snapshot_key = str(result.get("key") or "") if not error and has_input else ""
        if error:
            self._last_preflight_count = 0
            self._last_preflight_raw_count = 0
            self._last_preflight_error = error
            self._set_status("等待修正" if silent else "预检查失败", "warning" if silent else "failed")
            self._refresh_controls_state()
            if not silent:
                QMessageBox.critical(self, "预检查失败", f"读取失败：{error}")
            return
        if not has_input:
            self._last_preflight_count = 0
            self._last_preflight_raw_count = 0
            self._last_preflight_error = ""
            self._reset_counts(0)
            self._set_status("就绪", "ready")
            self._refresh_controls_state()
            if not silent:
                QMessageBox.warning(self, "缺少输入", "请粘贴账号文本，或导入账号文件。")
            return
        self._reset_counts(row_count)
        self._last_preflight_count = row_count
        self._last_preflight_raw_count = raw_count
        self._last_preflight_error = ""
        if row_count:
            self._set_status(f"已识别 {row_count}", "done")
        else:
            self._set_status("等待有效行" if silent else "无有效行", "warning")
        self._refresh_controls_state()
        if not silent:
            outputs = self._selected_output_labels() or "未选择"
            input_format_label = self._input_format_label()
            skipped = max(0, raw_count - row_count)
            self.append_log(f"🧪 预检查完成：识别到 {self._total} 个有效账号，跳过 {skipped} 行；输入格式：{input_format_label}；导出：{outputs}。")
            QMessageBox.information(self, "预检查完成", f"有效行数：{self._total}\n跳过行数：{skipped}\n输入格式：{input_format_label}\n输出：{outputs}")

    def start_run(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            QMessageBox.information(self, "正在运行", "当前任务还没有结束。")
            return
        input_path = self._input_path() if self._input_mode == "file" else ""
        paste_text = self._paste_text() if self._input_mode == "paste" else ""
        output_dir = self.output_edit.text().strip()
        if not paste_text and not input_path:
            QMessageBox.warning(self, "缺少输入", "请粘贴账号文本，或导入账号文件。")
            return
        if not output_dir:
            QMessageBox.warning(self, "缺少输出", "请先选择输出目录。")
            return
        output_ok, output_message = self._validate_output_dir(create=True)
        if not output_ok:
            QMessageBox.warning(self, "输出目录不可用", output_message)
            return
        if not (self.sub2api_check.isChecked() or self.cpa_check.isChecked()):
            QMessageBox.warning(self, "缺少导出格式", "请至少选择 Sub2API JSON 或 CPA JSON。")
            return
        if not self._current_preflight_cache_valid():
            self.preflight(silent=True)
            QMessageBox.information(self, "预检查中", "输入内容需要先完成预检查。请稍等识别完成后再开始导出。")
            return
        self._reset_counts(self._total)
        self.log_edit.clear()
        self._log_waiting = False
        self._set_status("运行中", "running")
        self.append_log("🚀 开始导出：配置已确认，正在按协议获取 JSON。")
        self.append_log(f"🧩 运行配置：输入格式={self._input_format_label()}；导出={self._selected_output_labels()}；并发={'自动' if int(self.concurrency_spin.value()) == 0 else self.concurrency_spin.value()}。")
        self.append_log(f"🔁 稳定性策略：瞬时网络/Callback 超时自动重试，最多 {int(self.max_attempts_spin.value())} 次。")
        self.append_log("🧭 执行流程：OAuth 初始化 → 账号密码验证 → 按需获取邮箱验证码 → Callback 换取 JSON。")
        self.append_log("🔎 登录策略：优先账密登录；只有出现验证码页面时才启用取码源；全程不拉起浏览器。")
        self.append_log(f"📁 输出目录：{Path(output_dir).resolve()}")
        self._cancel_event = threading.Event()
        self._is_cancelling = False
        self._set_running(True)
        self.sub2api_row.set_path("")
        self.cpa_row.set_path("")
        self._refresh_output_format_state()
        config = ExportConfig(
            input_path=input_path or "<paste>",
            out_dir=output_dir,
            input_text=paste_text,
            concurrency=int(self.concurrency_spin.value()),
            export_sub2api=self.sub2api_check.isChecked(),
            export_cpa=self.cpa_check.isChecked(),
            otp_timeout=int(self.otp_timeout_spin.value()),
            otp_interval=int(self.otp_interval_spin.value()),
            timeout=int(self.timeout_spin.value()),
            max_attempts=int(self.max_attempts_spin.value()),
            input_format=self._input_format(),
        )

        def worker() -> None:
            try:
                summary = run_export(config, logger=lambda _text: None, on_event=self.bridge.event.emit, cancel_event=self._cancel_event)
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

    def _status_code_label(self, value: Any) -> str:
        try:
            code = int(value or 0)
        except Exception:
            code = 0
        return f"HTTP {code}" if code else "已响应"

    def _backend_display(self, value: Any) -> str:
        mapping = {
            "http_url": "免登录 HTTP URL",
            "command": "本地命令",
            "imap": "IMAP",
            "imap_xoauth2": "IMAP XOAUTH2",
            "graph": "Graph",
            "jmap": "JMAP",
            "pop3": "POP3",
            "api": "Provider API",
            "json": "JSON 接口",
            "html_api_json": "HTML 自动发现 API(JSON)",
            "html_api_text": "HTML 自动发现 API(Text)",
            "html": "HTML 页面",
            "text": "文本页面",
        }
        key = str(value or "").strip()
        return mapping.get(key, key or "自动")

    def _stage_display(self, value: Any) -> str:
        mapping = {
            "oauth_start": "OAuth 初始化",
            "entry": "授权入口",
            "sentinel": "风控票据",
            "authorize_continue": "账号识别",
            "password_verify": "密码验证",
            "email_verification": "邮箱验证码",
            "otp_backend_plan": "验证码获取",
            "otp_fetch": "验证码获取",
            "email_otp_validate": "验证码提交",
            "finalize": "Callback 换票",
            "callback": "JSON 回调",
            "runtime_exception": "单账号异常",
            "worker_future": "任务线程",
            "export_prepare": "JSON 整理",
            "cancelled": "用户取消",
            "password_error": "密码验证",
            "bad_password": "密码验证",
        }
        key = str(value or "").strip()
        return mapping.get(key, key or "未知阶段")

    def _account_label(self, event: dict[str, Any]) -> str:
        email = str(event.get("email_masked") or "").strip()
        try:
            row_index = int(event.get("row_index") or event.get("account_index") or 0)
        except (TypeError, ValueError):
            row_index = 0
        try:
            line_no = int(event.get("line_no") or 0)
        except (TypeError, ValueError):
            line_no = 0
        sequence = row_index or line_no
        if sequence > 0:
            width = max(3, len(str(max(int(self._total or 0), sequence))))
            suffix = f" {email}" if email else ""
            line_suffix = f"（行 {line_no}）" if row_index and line_no and line_no != row_index else ""
            return f"账号 #{sequence:0{width}d}{suffix}{line_suffix}"
        if email:
            return f"账号 {email}"
        return "账号"

    def _reason_display(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        lowered = raw.lower()
        mapping = {
            "wrong_email_otp_code": "验证码不正确或已过期，通常是取码源返回了旧码。",
            "otp_timeout": "在等待时间内没有获取到新的验证码。",
            "callback_error": "没有拿到 OAuth Callback，可能是跳转链路未完成。",
            "finalize_unresolved": "登录已推进到收尾阶段，但最终 Callback 没有解析成功。",
            "workspace_select_error": "工作区选择接口返回异常。",
            "workspace_select_continue_missing": "工作区选择完成后没有返回下一步地址。",
            "user_cancelled": "用户取消了本次任务。",
            "no_valid_rows": "没有识别到有效账号行。",
        }
        if raw in mapping:
            return mapping[raw]
        if lowered.startswith("timeout:"):
            return "请求超时：目标服务响应较慢或网络不稳定，可稍后重试，或在高级选项里调高 HTTP 请求超时。"
        if lowered.startswith("runtimeerror: token exchange failed"):
            return "Token 交换失败：Callback 已拿到，但换取 JSON token 时服务端返回异常。"
        if lowered.startswith("valueerror: token_json"):
            return "返回的 token JSON 格式不符合预期。"
        if raw.startswith("http_"):
            return f"接口返回 {raw.replace('http_', 'HTTP ')}。"
        if len(raw) > 180:
            return raw[:180] + "…"
        return raw

    def _friendly_stage_message(self, event: dict[str, Any]) -> str:
        account = self._account_label(event)
        stage = str(event.get("stage") or "").strip()
        status = self._status_code_label(event.get("status_code"))
        page_type = str(event.get("page_type") or "").strip()
        if stage == "oauth_start":
            return f"🧭 {account}：开始 OAuth 初始化，创建授权会话。"
        if stage == "entry":
            return f"🚪 {account}：授权入口已响应（{status}），正在保存会话状态。"
        if stage == "sentinel":
            return f"🛡️ {account}：会话已建立，正在获取风控校验票据。"
        if stage == "authorize_continue":
            return f"📨 {account}：邮箱已提交到认证接口（{status}），正在确认下一步登录方式。"
        if stage == "password_verify":
            if bool(event.get("callback_url_present")):
                return f"✅ {account}：密码验证通过，已直接获得 Callback。"
            if "otp" in page_type.lower() or "verify" in page_type.lower():
                return f"📮 {account}：密码验证通过，服务端要求邮箱验证码，准备访问取码源。"
            return f"🔑 {account}：密码验证完成（{status}），继续推进授权流程。"
        if stage == "otp_backend_plan":
            primary = self._backend_display(event.get("primary_backend"))
            display_name = str(event.get("display_name") or "").strip()
            suffix = f" · {display_name}" if display_name and display_name != primary else ""
            return f"📫 {account}：取码方式已确定为 {primary}{suffix}，正在等待新的邮箱验证码。"
        if stage == "otp_fetch":
            backend = self._backend_display(event.get("backend"))
            if bool(event.get("code_present")):
                return f"📬 {account}：已获取验证码（来源：{backend}，{status}），准备提交验证。"
            return f"⌛ {account}：暂未获取到新验证码（来源：{backend}，{status}），将继续等待或按超时处理。"
        if stage == "email_otp_validate":
            if bool(event.get("callback_url_present")):
                return f"🧾 {account}：验证码提交成功（{status}），已获得 Callback。"
            return f"🧾 {account}：验证码已提交（{status}），正在进入收尾流程。"
        if stage == "finalize":
            return f"🎫 {account}：正在完成 Callback 跳转并换取最终 JSON。"
        if stage == "callback":
            return f"📦 {account}：Callback 完成，JSON 已获取。"
        if stage == "runtime_exception":
            return f"🧯 {account}：当前账号发生异常，已隔离处理，不影响其它账号继续运行。"
        if stage == "export_prepare":
            return f"🧹 {account}：JSON 整理时发现格式异常，已跳过当前账号。"
        if stage == "cancelled":
            return f"🛑 {account}：收到取消信号，当前账号不再继续推进。"
        return ""

    def on_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "started":
            self._total = int(event.get("total") or 0)
            self.total_stat.set_value(self._total)
            self._update_progress()
            concurrency = event.get("concurrency") or "自动"
            self.append_log(f"📦 任务已启动：共 {self._total} 个账号，并发={concurrency}。")
        elif event_type == "row_start":
            self._running += 1
            self.running_stat.set_value(self._running)
            self.append_log(f"👤 {self._account_label(event)}：进入执行队列，准备开始登录流程。")
        elif event_type == "row_stage":
            message = self._friendly_stage_message(event)
            if message:
                self.append_log(message)
        elif event_type == "row_retry":
            account = self._account_label(event)
            stage = str(event.get("stage") or event.get("status") or "").strip()
            reason = self._reason_display(event.get("reason"))
            next_attempt = int(event.get("next_attempt") or 0)
            max_attempts = int(event.get("max_attempts") or 0)
            attempt_text = f"第 {next_attempt}/{max_attempts} 次尝试" if next_attempt and max_attempts else "下一次尝试"
            detail = f"；原因：{reason}" if reason else ""
            self.append_log(f"🔁 自动重试：{account} 上次停在「{self._stage_display(stage)}」{detail}，正在进行{attempt_text}。")
        elif event_type == "cancelling":
            self._is_cancelling = True
            self._set_status("取消中", "warning")
            self._refresh_controls_state()
        elif event_type == "row_done":
            self._done = int(event.get("done") or self._done + 1)
            self._running = max(0, self._running - 1)
            account = self._account_label(event)
            if event.get("ok"):
                self._success += 1
                suffix = "；本次经过邮箱验证码验证" if event.get("otp_required") else ""
                self.append_log(f"✅ 成功：{account} 已获取 JSON{suffix}，稍后统一写入导出文件。")
            else:
                self._failure += 1
                status = str(event.get("status") or "failed")
                reason = str(event.get("reason") or "").strip()
                stage = str(event.get("stage") or "").strip()
                if status == "cancelled":
                    self.append_log(f"🛑 取消：{account} 已停止，等待其它运行中的账号收尾。")
                else:
                    detail = f"；原因：{self._reason_display(reason)}" if reason else ""
                    self.append_log(f"⚠️ 失败：{account} 停在「{self._stage_display(stage or status)}」{detail}。")
            self.success_stat.set_value(self._success)
            self.failed_stat.set_value(self._failure)
            self.running_stat.set_value(self._running)
            self._update_progress()

    def on_done(self, summary: dict) -> None:
        self._set_running(False)
        success_count = int(summary.get("success_count", 0) or 0)
        failure_count = int(summary.get("failure_count", 0) or 0)
        cancelled = bool(summary.get("cancelled"))
        cancelled_count = int(summary.get("cancelled_count", 0) or 0)
        if cancelled:
            self._set_status("已取消", "warning")
        elif success_count and failure_count:
            self._set_status("部分完成", "warning")
        elif success_count:
            self._set_status("完成", "done")
        else:
            self._set_status("无成功", "failed")
        self._done = success_count + failure_count
        self._running = 0
        self.running_stat.set_value(0)
        self._update_progress()
        sub2api_path = str(summary.get("sub2api_export") or "")
        cpa_zip = str(summary.get("cpa_zip") or "")
        cpa_dir = str(summary.get("cpa_dir") or "")
        failure_report = str(summary.get("failure_report") or "")
        failure_categories = summary.get("failure_categories") if isinstance(summary.get("failure_categories"), dict) else {}
        retry_count = int(summary.get("retry_count") or 0)
        cpa_path = cpa_zip or cpa_dir or str(summary.get("cpa_manifest") or "")
        self.sub2api_row.set_path(sub2api_path)
        self.cpa_row.set_path(cpa_path)
        self._refresh_output_format_state()
        self.append_log("")
        if cancelled:
            self.append_log(f"🛑 任务已取消：成功 {success_count} 个，未完成/失败 {failure_count} 个，其中取消 {cancelled_count} 个。")
        else:
            self.append_log(f"🎉 任务完成：成功 {success_count} 个，失败 {failure_count} 个。")
        if retry_count:
            self.append_log(f"🔁 自动恢复：本次有 {retry_count} 个账号通过自动重试完成或收敛。")
        if failure_categories:
            parts = [f"{name} {count} 个" for name, count in failure_categories.items()]
            self.append_log(f"⚠️ 失败诊断：{'；'.join(parts)}。")
        if sub2api_path:
            self.append_log(f"🧰 Sub2API 输出：{sub2api_path}")
        if cpa_path:
            if cpa_zip:
                self.append_log(f"📘 CPA ZIP 输出：{cpa_zip}")
            if cpa_dir:
                self.append_log(f"📚 CPA 单账号 JSON 目录：{cpa_dir}")
        if failure_report:
            self.append_log(f"🧾 失败诊断报告：{failure_report}")
        self.append_log("👀 提示：可以打开输出目录检查文件，确认后再导入目标系统。")
        if cancelled:
            QMessageBox.information(self, "已取消", f"导出已取消\n成功：{success_count}\n失败/未完成：{failure_count}\n取消：{cancelled_count}")
        else:
            QMessageBox.information(self, "完成", f"导出完成\n成功：{success_count}\n失败：{failure_count}")

    def on_failed(self, message: str) -> None:
        self._set_running(False)
        self._running = 0
        self.running_stat.set_value(0)
        self._refresh_output_format_state()
        self._set_status("失败", "failed")
        self.append_log(f"💥 主流程异常：{message}")
        QMessageBox.critical(self, "运行失败", message)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
