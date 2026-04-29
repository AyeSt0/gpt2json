from __future__ import annotations

import hashlib
import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QLibraryInfo,
    QLockFile,
    QObject,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    QTranslator,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QHeaderView,
    QLabel,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .engine import ExportConfig, run_export
from .gui_file_dialog import DialogDragFilter, LocalizedFileDialogProxyModel, build_unified_file_dialog_stylesheet
from .gui_log_style import DARK_LOG_COLORS, LIGHT_LOG_COLORS, classify_log_line
from .gui_paths import create_app_settings, default_output_dir, single_instance_lock_path
from .gui_resources import (
    APP_ICON_PATH,
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    ICON_DARK_PATH,
    ICON_LIGHT_PATH,
    ICON_PATH,
    STAT_FAILED_PATH,
    STAT_RUNNING_PATH,
    STAT_SUCCESS_PATH,
    STAT_TOTAL_PATH,
    THEME_MOON_PATH,
    THEME_SUN_PATH,
    UI_CHEVRON_DOWN_PATH,
    UI_INPUT_PATH,
    UI_LOG_PATH,
    UI_OUTPUT_PATH,
    UI_SETTINGS_PATH,
)
from .gui_text_menu import build_chinese_text_context_menu as build_chinese_text_context_menu
from .gui_text_menu import install_chinese_text_context_menu
from .gui_theme import DARK_THEME, LIGHT_THEME
from .gui_widgets import (
    DropLineEdit,
    FileDropBox,
    FileOutputRow,
    FormatCombo,
    InlineStat,
    PresetNumberCombo,
    SectionHeader,
)
from .parsing import decode_text_file, list_future_input_format_presets, list_input_formats, parse_by_format
from .updater import RELEASES_PAGE_URL, check_latest_release


def install_qt_translations(app: QApplication | None) -> None:
    """Load Qt's Simplified Chinese translations for built-in dialogs.

    GPT2JSON's own widgets are handwritten in Chinese, but Qt built-ins such as
    QFileDialog provide tooltips and detail-view headers from qtbase_*.qm.  Keep
    the translator objects alive at module scope; otherwise Qt silently falls
    back to English after garbage collection.
    """

    global _QT_TRANSLATIONS_INSTALLED
    if app is None or _QT_TRANSLATIONS_INSTALLED:
        return

    filenames = ("qtbase_zh_CN.qm", "qt_zh_CN.qm")
    translation_roots = [
        Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)),
        Path(__file__).resolve().parent / "assets" / "translations",
    ]
    if hasattr(sys, "_MEIPASS"):
        bundle_root = Path(sys._MEIPASS)
        translation_roots.extend(
            [
                bundle_root / "PySide6" / "translations",
                bundle_root / "PySide6" / "Qt" / "translations",
            ]
        )

    installed = False
    for filename in filenames:
        for root in translation_roots:
            path = root / filename
            if not path.exists():
                continue
            translator = QTranslator(app)
            if translator.load(str(path)):
                app.installTranslator(translator)
                _QT_TRANSLATORS.append(translator)
                installed = True
                break
    _QT_TRANSLATIONS_INSTALLED = installed


READY_LOG = "🟢 等待开始：请粘贴账号文本，或导入账号文件。\n📄 当前支持：自动识别 / LDXP Plus7 三段式 OTP。\n📮 说明：程序会优先尝试账密登录；只有服务端要求验证码时，才会访问输入里的取码源。"
_UI_FONT_FAMILY = ""
_QT_TRANSLATORS: list[QTranslator] = []
_QT_TRANSLATIONS_INSTALLED = False

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


def rounded_pixmap(source: QPixmap, size: int, radius: float) -> QPixmap:
    scaled = source.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    if scaled.width() != size or scaled.height() != size:
        x = max(0, (scaled.width() - size) // 2)
        y = max(0, (scaled.height() - size) // 2)
        scaled = scaled.copy(x, y, size, size)

    output = QPixmap(size, size)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return output


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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        install_qt_translations(QApplication.instance())
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
        self._last_result_dir = ""
        self._last_failed_rerun_file = ""
        self._pending_failed_rerun_autostart = False
        self._failed_rerun_autostart_silent = False
        self._starting_failed_rerun_batch = False
        self._failed_rerun_start_retries = 0
        self._batch_auto_rerun_count = 0
        self._batch_auto_rerun_accumulated_success = 0
        self._output_dir_custom = False
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
        # No fake outer gutter: the frameless window itself is transparent and
        # the shell paints the only visible surface.  Keeping an inset here
        # makes the app look like it has a second rounded-rectangle frame.
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.shell = QFrame()
        self.shell.setObjectName("Shell")
        self.shadow = QGraphicsDropShadowEffect(self.shell)
        # Disable the drop-shadow effect: on some Windows scaling / GPU
        # combinations QGraphicsDropShadowEffect shows a sharp rectangular
        # halo around the rounded frameless window.  The shell itself remains
        # borderless so the top-level app does not show a stray outer frame.
        self.shadow.setEnabled(False)
        self.shadow.setBlurRadius(0)
        self.shadow.setOffset(0, 0)
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
        install_chinese_text_context_menu(self.paste_edit)
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
        self.output_edit.setText(str(default_output_dir()))
        self.output_edit.setPlaceholderText("选择输出目录")
        self.output_edit.textChanged.connect(self._refresh_controls_state)
        self.output_edit.textEdited.connect(self._mark_output_dir_custom)
        self.output_edit.dropped.connect(lambda _path: self._mark_output_dir_custom())
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
        self.max_attempts_spin = self._spin(1, 5, 3)
        self.auto_rerun_spin = self._spin(0, 5, 2)
        self.batch_auto_rerun_spin = self._spin(0, 3, 1)
        for spin in (
            self.timeout_spin,
            self.otp_timeout_spin,
            self.otp_interval_spin,
            self.max_attempts_spin,
            self.auto_rerun_spin,
            self.batch_auto_rerun_spin,
        ):
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
        self.rerun_failed_btn = QPushButton("重跑失败账号")
        self.rerun_failed_btn.setObjectName("SecondaryButton")
        self.rerun_failed_btn.setToolTip("只读取上次生成的 failed_rerun.secret.txt，作为新批次手动补跑可恢复失败账号。")
        self.rerun_failed_btn.setVisible(False)
        self.rerun_failed_btn.clicked.connect(lambda: self.rerun_failed_accounts())
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setToolTip("请求取消当前导出；已在执行的账号会在安全点收尾。")
        self.cancel_btn.clicked.connect(self.cancel_run)
        self.open_out_btn = QPushButton("打开输出目录")
        self.open_out_btn.setObjectName("SecondaryButton")
        self.open_out_btn.clicked.connect(self.open_output_dir)
        buttons.addWidget(self.preflight_btn, 1)
        buttons.addWidget(self.run_btn, 2)
        buttons.addWidget(self.rerun_failed_btn, 2)
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
        self.output_hint_label = QLabel("任务完成后显示结果所在位置；未运行时这里保持精简。")
        self.output_hint_label.setObjectName("HintText")
        self.output_hint_label.setWordWrap(True)
        output_layout.addWidget(self.output_hint_label)
        self.sub2api_row = FileOutputRow("sub2api_accounts.secret.json", "Sub2API")
        self.cpa_row = FileOutputRow("CPA_<批次>/", "CPA")
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
        install_chinese_text_context_menu(self.log_edit)
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

    def _dialog_start_directory(self, path_text: str = "") -> Path:
        raw = (path_text or "").strip()
        path = Path(raw).expanduser() if raw else Path.cwd()
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.is_file():
            path = path.parent
        while not path.exists() and path.parent != path:
            path = path.parent
        return path if path.exists() else Path.cwd()

    def _file_dialog_sidebar_places(self) -> list[tuple[str, QUrl, str]]:
        places: list[tuple[str, QUrl, str]] = []
        seen: set[str] = set()

        def add_url(label: str, url: QUrl, tooltip: str = "") -> None:
            if not label:
                return
            key = url.toString().casefold()
            if key in seen:
                return
            seen.add(key)
            places.append((label, url, tooltip or url.toLocalFile() or label))

        def add(label: str, value: str | Path, tooltip: str = "") -> None:
            if not label:
                return
            path = Path(value).expanduser()
            if not path.exists():
                return
            try:
                key = str(path.resolve()).casefold()
            except Exception:
                key = str(path).casefold()
            if key in seen:
                return
            seen.add(key)
            places.append((label, QUrl.fromLocalFile(str(path)), tooltip or str(path)))

        standard_locations: tuple[tuple[str, QStandardPaths.StandardLocation], ...] = (
            ("桌面", QStandardPaths.StandardLocation.DesktopLocation),
            ("文档", QStandardPaths.StandardLocation.DocumentsLocation),
            ("下载", QStandardPaths.StandardLocation.DownloadLocation),
            ("图片", QStandardPaths.StandardLocation.PicturesLocation),
            ("音乐", QStandardPaths.StandardLocation.MusicLocation),
            ("视频", QStandardPaths.StandardLocation.MoviesLocation),
        )
        for label, location in standard_locations:
            value = QStandardPaths.writableLocation(location)
            if value:
                add(label, value)

        # Qt's non-native QFileDialog can show a Windows-style drive overview
        # when navigated to the empty file URL.  Put it after the high-frequency
        # user folders so the sidebar stays short and task-oriented.
        add_url("此电脑", QUrl("file:"), "查看所有磁盘和驱动器")

        return places

    def _apply_unified_file_dialog_style(self, dialog: QFileDialog, *, accept_text: str) -> None:
        dialog.setObjectName("UnifiedFileDialog")
        dialog.setWindowIcon(QIcon(str(APP_ICON_PATH)) if APP_ICON_PATH.exists() else self.windowIcon())
        dialog.setWindowFlags((dialog.windowFlags() | Qt.WindowType.FramelessWindowHint) & ~Qt.WindowType.WindowContextHelpButtonHint)
        # QFileDialog is a complex top-level widget.  Enabling translucent
        # background here can make the native child viewport show through as a
        # fully transparent window on Windows, especially with Direct2D / DPI
        # scaling.  Keep it opaque; the unified title bar still provides the
        # visual integration without turning the dialog into a see-through pane.
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setViewMode(QFileDialog.ViewMode.Detail)
        dialog.setLabelText(QFileDialog.DialogLabel.Accept, accept_text)
        dialog.setLabelText(QFileDialog.DialogLabel.Reject, "取消")
        dialog.setLabelText(QFileDialog.DialogLabel.LookIn, "位置")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "名称")
        dialog.setLabelText(QFileDialog.DialogLabel.FileType, "类型")
        proxy = LocalizedFileDialogProxyModel(dialog)
        dialog.setProxyModel(proxy)
        dialog._localized_proxy = proxy  # type: ignore[attr-defined]
        dialog.setStyleSheet(build_unified_file_dialog_stylesheet(self.palette()))
        dialog.resize(760, 520)

        sidebar_places = self._file_dialog_sidebar_places()
        if sidebar_places:
            dialog.setSidebarUrls([url for _label, url, _tooltip in sidebar_places])

        self._install_file_dialog_chrome(dialog)
        self._arrange_file_dialog_toolbar(dialog)
        self._localize_file_dialog_widgets(dialog)
        self._localize_file_dialog_sidebar(dialog, sidebar_places)
        self._tune_file_dialog_views(dialog)
        for delay_ms in (0, 50, 200):
            QTimer.singleShot(
                delay_ms,
                lambda d=dialog, places=sidebar_places: (
                    self._install_file_dialog_chrome(d),
                    self._arrange_file_dialog_toolbar(d),
                    self._localize_file_dialog_widgets(d),
                    self._localize_file_dialog_sidebar(d, places),
                    self._tune_file_dialog_views(d),
                ),
            )
        normalized_accept = accept_text.replace("&", "")
        for button in dialog.findChildren(QPushButton):
            if button.text().replace("&", "") == normalized_accept:
                button.setObjectName("DialogPrimaryButton")
                button.setDefault(True)
                break

    def _install_file_dialog_chrome(self, dialog: QFileDialog) -> None:
        if dialog.findChild(QWidget, "FileDialogTitleBar") is not None:
            return
        grid = dialog.layout()
        if not isinstance(grid, QGridLayout):
            return

        existing: list[tuple[Any, tuple[int, int, int, int]]] = []
        for index in reversed(range(grid.count())):
            position = grid.getItemPosition(index)
            item = grid.takeAt(index)
            if item is not None:
                existing.append((item, position))
        for item, (row, column, row_span, column_span) in reversed(existing):
            grid.addItem(item, row + 1, column, row_span, column_span)

        grid.setContentsMargins(10, 8, 10, 10)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        title_bar = QFrame(dialog)
        title_bar.setObjectName("FileDialogTitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 0, 4, 0)
        title_layout.setSpacing(8)

        icon = QLabel()
        icon.setObjectName("FileDialogTitleIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = ICON_DARK_PATH if self._theme == "dark" else ICON_LIGHT_PATH
        if not icon_path.exists():
            icon_path = ICON_PATH
        if icon_path.exists():
            icon.setPixmap(QPixmap(str(icon_path)).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        title = QLabel(dialog.windowTitle() or APP_NAME)
        title.setObjectName("FileDialogTitle")

        close_button = QToolButton()
        close_button.setObjectName("FileDialogCloseButton")
        close_button.setText("×")
        close_button.setToolTip("关闭")
        close_button.clicked.connect(dialog.reject)

        title_layout.addWidget(icon)
        title_layout.addWidget(title, 1)
        title_layout.addWidget(close_button)
        grid.addWidget(title_bar, 0, 0, 1, max(1, grid.columnCount()))

        drag_filter = DialogDragFilter(dialog)
        dialog._drag_filter = drag_filter  # type: ignore[attr-defined]
        for widget in (title_bar, icon, title):
            widget.installEventFilter(drag_filter)

    def _find_layout_containing_widget(self, layout: Any, widget: QWidget) -> Any:
        if layout is None:
            return None
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            if item.widget() is widget:
                return layout
            child_layout = item.layout()
            found = self._find_layout_containing_widget(child_layout, widget) if child_layout is not None else None
            if found is not None:
                return found
        return None

    def _file_dialog_toolbar_layout(self, dialog: QFileDialog) -> Any:
        combo = dialog.findChild(QComboBox, "lookInCombo")
        if combo is None:
            return None
        return self._find_layout_containing_widget(dialog.layout(), combo)

    def _refresh_file_dialog_current_dir(self, dialog: QFileDialog) -> None:
        current_url = dialog.directoryUrl()
        for tree in dialog.findChildren(QTreeView):
            model = tree.model()
            source_model = model.sourceModel() if hasattr(model, "sourceModel") else model
            if source_model is not None and hasattr(source_model, "setRootPath") and hasattr(source_model, "rootPath"):
                source_model.setRootPath(source_model.rootPath())
        if current_url.isValid():
            dialog.setDirectoryUrl(current_url)
        self._tune_file_dialog_views(dialog)

    def _file_dialog_toolbar_icon(self, name: str, fallback: QStyle.StandardPixmap) -> tuple[QIcon, str]:
        # Do not tint the platform icons into a single silhouette: in dark mode
        # that made every toolbar action look like the same white blob.  These
        # lightweight vector glyphs keep the familiar Windows/Fluent outline
        # language while using small semantic accents for easy scanning.
        dark = self._theme == "dark"
        base = QColor("#E2E8F0" if dark else "#475569")
        muted = QColor("#94A3B8" if dark else "#64748B")
        blue = QColor("#60A5FA" if dark else "#2563EB")
        purple = QColor("#C4B5FD" if dark else "#7C3AED")
        green = QColor("#86EFAC" if dark else "#16A34A")
        amber = QColor("#FCD34D" if dark else "#F59E0B")
        amber_fill = QColor("#78350F" if dark else "#FEF3C7")
        surface = QColor("#1E293B" if dark else "#EFF6FF")

        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(base, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        def line(x1: float, y1: float, x2: float, y2: float, color: QColor | None = None, width: float = 2.0) -> None:
            painter.setPen(QPen(color or base, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        def rounded_rect(x: float, y: float, w: float, h: float, radius: float, stroke: QColor, fill: QColor | None = None, width: float = 1.6) -> None:
            painter.setPen(QPen(stroke, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(fill if fill is not None else Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(int(x), int(y), int(w), int(h), radius, radius)

        if name == "backButton":
            line(14, 5, 8, 11, blue)
            line(8, 11, 14, 17, blue)
            line(9, 11, 18, 11, base)
        elif name == "forwardButton":
            line(8, 5, 14, 11, blue)
            line(14, 11, 8, 17, blue)
            line(4, 11, 13, 11, base)
        elif name == "toParentButton":
            line(11, 5, 5, 11, purple)
            line(11, 5, 17, 11, purple)
            line(11, 6, 11, 18, base)
            line(7, 18, 15, 18, muted, 1.8)
        elif name == "refreshButton":
            painter.setPen(QPen(green, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawArc(5, 5, 12, 12, 35 * 16, 285 * 16)
            line(16, 4, 17, 9, green)
            line(16, 4, 12, 5, green)
        elif name == "newFolderButton":
            folder = QPainterPath()
            folder.moveTo(3, 8)
            folder.lineTo(8, 8)
            folder.lineTo(10, 6)
            folder.lineTo(14, 6)
            folder.lineTo(16, 8)
            folder.lineTo(19, 8)
            folder.lineTo(19, 17)
            folder.lineTo(3, 17)
            folder.closeSubpath()
            painter.setPen(QPen(amber, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(amber_fill)
            painter.drawPath(folder)
            line(15, 11, 15, 15, blue, 1.8)
            line(13, 13, 17, 13, blue, 1.8)
        elif name == "listModeButton":
            for y, color in ((7, blue), (11, purple), (15, green)):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(4, y - 1, 2, 2)
                line(8, y, 18, y, base, 1.7)
        elif name == "detailModeButton":
            colors = (blue, purple, green, muted)
            positions = ((4, 5), (12, 5), (4, 13), (12, 13))
            for (x, y), color in zip(positions, colors, strict=True):
                rounded_rect(x, y, 6, 6, 1.5, color, surface, 1.4)
        else:
            fallback_icon = QApplication.style().standardIcon(fallback)
            painter.end()
            return fallback_icon, "platform"

        painter.end()
        return QIcon(pixmap), "accent"

    def _arrange_file_dialog_toolbar(self, dialog: QFileDialog) -> None:
        layout = self._file_dialog_toolbar_layout(dialog)
        if layout is None:
            return
        root_layout = dialog.layout()
        if isinstance(root_layout, QGridLayout):
            # QFileDialog's default grid reserves column 0 for the "Look in"
            # label and places the toolbar/address row at column 1.  Once the
            # label is folded into our toolbar, re-span the row from column 0
            # so navigation buttons start flush with the content margin.
            position = None
            for index in range(root_layout.count()):
                item = root_layout.itemAt(index)
                if item is not None and item.layout() is layout:
                    position = root_layout.getItemPosition(index)
                    break
            if position is not None and position[1] != 0:
                root_layout.removeItem(layout)
                root_layout.addLayout(layout, position[0], 0, position[2], root_layout.columnCount())
        location_label = dialog.findChild(QLabel, "lookInLabel")
        if location_label is not None:
            if root_layout is not None:
                root_layout.removeWidget(location_label)
            location_label.setText("")
            location_label.setFixedSize(0, 0)
            location_label.setVisible(False)
        combo = dialog.findChild(QComboBox, "lookInCombo")
        if combo is None:
            return

        inline_label = dialog.findChild(QLabel, "ToolbarLocationLabel")
        if inline_label is None:
            inline_label = QLabel("位置", dialog)
            inline_label.setObjectName("ToolbarLocationLabel")
            inline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inline_label.setMinimumWidth(28)

        refresh_button = dialog.findChild(QToolButton, "refreshButton")
        if refresh_button is None:
            refresh_button = QToolButton(dialog)
            refresh_button.setObjectName("refreshButton")
            refresh_button.clicked.connect(lambda _checked=False, d=dialog: self._refresh_file_dialog_current_dir(d))

        widgets: list[QWidget] = []
        for name in ("backButton", "forwardButton", "toParentButton"):
            button = dialog.findChild(QToolButton, name)
            if button is not None:
                widgets.append(button)
        widgets.extend([refresh_button, inline_label, combo])
        for name in ("newFolderButton", "listModeButton", "detailModeButton"):
            button = dialog.findChild(QToolButton, name)
            if button is not None:
                widgets.append(button)

        # QFileDialog builds this row as: address bar, then buttons.  Reorder it
        # to the Windows-native mental model: navigation buttons first, then the
        # location/address bar, with folder/view tools at the right.
        for widget in widgets:
            index = layout.indexOf(widget)
            if index >= 0:
                layout.takeAt(index)
        if isinstance(layout, QHBoxLayout):
            layout.setSpacing(4)
        for index, widget in enumerate(widgets):
            stretch = 1 if widget is combo else 0
            layout.insertWidget(index, widget, stretch)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _localize_file_dialog_widgets(self, dialog: QFileDialog) -> None:
        # Qt translations cover these once qtbase_zh_CN.qm is loaded.  These
        # explicit fallbacks keep packaged builds Chinese even if a translation
        # file is missing from the runtime bundle.
        toolbar_buttons: dict[str, tuple[str, QStyle.StandardPixmap]] = {
            "backButton": ("后退", QStyle.StandardPixmap.SP_FileDialogBack),
            "forwardButton": ("前进", QStyle.StandardPixmap.SP_ArrowForward),
            "toParentButton": ("向上一级", QStyle.StandardPixmap.SP_FileDialogToParent),
            "refreshButton": ("刷新", QStyle.StandardPixmap.SP_BrowserReload),
            "newFolderButton": ("新建文件夹", QStyle.StandardPixmap.SP_FileDialogNewFolder),
            "listModeButton": ("列表", QStyle.StandardPixmap.SP_FileDialogListView),
            "detailModeButton": ("详细信息", QStyle.StandardPixmap.SP_FileDialogDetailedView),
        }
        for button in dialog.findChildren(QToolButton):
            config = toolbar_buttons.get(button.objectName())
            if not config:
                continue
            tooltip, pixmap = config
            button.setText("")
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setAutoRaise(True)
            button.setFixedSize(30, 30)
            button.setIconSize(QSize(18, 18))
            icon, icon_color = self._file_dialog_toolbar_icon(button.objectName(), pixmap)
            button.setIcon(icon)
            button.setProperty("themeIconColor", icon_color)
            button.setProperty("themeIconMode", self._theme)

    def _localize_file_dialog_sidebar(self, dialog: QFileDialog, places: list[tuple[str, QUrl, str]]) -> None:
        sidebar = dialog.findChild(QListView, "sidebar")
        if sidebar is None:
            return
        sidebar.setMinimumWidth(96)
        sidebar.setMaximumWidth(112)
        sidebar.setIconSize(QSize(14, 14))
        sidebar.setSpacing(1)
        model = sidebar.model()
        if model is None:
            return
        if not bool(getattr(model, "_gpt2json_sidebar_connected", False)):
            model._gpt2json_sidebar_connected = True

            def relabel_later(*_args: Any, d: QFileDialog = dialog, p: list[tuple[str, QUrl, str]] = places, m: Any = model) -> None:
                if bool(getattr(m, "_gpt2json_sidebar_relabeling", False)):
                    return
                QTimer.singleShot(0, lambda: self._localize_file_dialog_sidebar(d, p))

            model.modelReset.connect(relabel_later)
            model.rowsInserted.connect(relabel_later)
            model.layoutChanged.connect(relabel_later)
            model.dataChanged.connect(relabel_later)
        model._gpt2json_sidebar_relabeling = True
        try:
            for row, (label, url, tooltip) in enumerate(places):
                if row >= model.rowCount():
                    break
                index = model.index(row, 0)
                model.setData(index, label, Qt.ItemDataRole.DisplayRole)
                model.setData(index, tooltip or url.toLocalFile(), Qt.ItemDataRole.ToolTipRole)
        finally:
            model._gpt2json_sidebar_relabeling = False

    def _tune_file_dialog_views(self, dialog: QFileDialog) -> None:
        # Keep QFileDialog's familiar information layout, but make the detail
        # table denser and closer to the main UI instead of turning it into a
        # sparse custom picker.
        for tree in dialog.findChildren(QTreeView):
            tree.setAlternatingRowColors(True)
            tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            tree.setUniformRowHeights(True)
            tree.setSortingEnabled(True)
            header = tree.header()
            header.setHighlightSections(False)
            header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            header.setMinimumSectionSize(72)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            if tree.model() is not None and tree.model().columnCount() >= 4:
                header.resizeSection(0, 280)
                header.resizeSection(1, 86)
                header.resizeSection(2, 116)
                header.resizeSection(3, 150)
        splitter = dialog.findChild(QSplitter, "splitter")
        if splitter is not None:
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(8)
            splitter.setSizes([104, 640])

    def _create_input_file_dialog(self, start_path: str = "") -> QFileDialog:
        dialog = QFileDialog(self, "选择账号文件", str(self._dialog_start_directory(start_path)))
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilters(["文本文件 (*.txt)", "所有文件 (*)"])
        self._apply_unified_file_dialog_style(dialog, accept_text="选择文件")
        return dialog

    def _create_output_directory_dialog(self, start_path: str = "") -> QFileDialog:
        start_dir = self._dialog_start_directory(start_path)
        dialog = QFileDialog(self, "选择输出目录", str(start_dir))
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        # 不启用 ShowDirsOnly：用户选输出目录时也能看到目录内文件，
        # 信息量更接近系统默认浏览窗口；若误选文件，pick_output 会回退到父目录。
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, False)
        self._apply_unified_file_dialog_style(dialog, accept_text="选择此目录")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "文件夹")
        return dialog

    def _refresh_logo(self) -> None:
        icon_path = ICON_DARK_PATH if self._theme == "dark" else ICON_LIGHT_PATH
        if not icon_path.exists():
            icon_path = ICON_PATH
        if icon_path.exists():
            self.logo.setText("")
            self.logo.setPixmap(rounded_pixmap(QPixmap(str(icon_path)), 50, 14))
        else:
            self.logo.setPixmap(QPixmap())
            self.logo.setText("GJ")

    def apply_style(self) -> None:
        p = self.palette()
        chevron_url = UI_CHEVRON_DOWN_PATH.as_posix()
        QApplication.instance().setFont(QFont(load_ui_font(), 10))  # type: ignore[union-attr]
        self.shadow.setEnabled(False)
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
            #Shell {{ background:{p['shell']}; border:none; border-radius:18px; }}
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
            #CopyButton {{ border:none; background:transparent; color:{p['muted2']}; min-width:64px; max-width:64px; min-height:28px; max-height:28px; border-radius:6px; font-size:11px; font-weight:800; }}
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

    def _setting_bool(self, key: str, default: bool = False) -> bool:
        value = self.settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _default_output_dir_text(self) -> str:
        return str(default_output_dir())

    def _mark_output_dir_custom(self, *_args: Any) -> None:
        self._output_dir_custom = True

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
        saved_output_dir = str(self.settings.value("output_dir", "") or "").strip()
        has_saved_output_dir = bool(self.settings.contains("output_dir") and saved_output_dir)
        explicit_custom = self._setting_bool("output_dir_custom", False)
        legacy_custom = has_saved_output_dir and saved_output_dir != "output"
        self._output_dir_custom = bool(explicit_custom or legacy_custom)
        output_dir = saved_output_dir if self._output_dir_custom else self._default_output_dir_text()
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
        self.max_attempts_spin.setValue(int_setting("max_attempts", 3, 1, 5))
        self.auto_rerun_spin.setValue(int_setting("auto_rerun_attempts", 2, 0, 5))
        self.batch_auto_rerun_spin.setValue(int_setting("batch_auto_rerun_attempts", 1, 0, 3))
        self.advanced_btn.setText("高级选项（弹窗配置）  ›")

    def _save_settings(self) -> None:
        self.settings.setValue("theme", self._theme)
        self.settings.setValue("output_dir_custom", self._output_dir_custom)
        if self._output_dir_custom:
            self.settings.setValue("output_dir", self.output_edit.text().strip() or self._default_output_dir_text())
        else:
            self.settings.remove("output_dir")
        self.settings.setValue("input_format", self._input_format())
        self.settings.setValue("export_sub2api", self.sub2api_check.isChecked())
        self.settings.setValue("export_cpa", self.cpa_check.isChecked())
        self.settings.setValue("concurrency", int(self.concurrency_spin.value()))
        self.settings.setValue("timeout", int(self.timeout_spin.value()))
        self.settings.setValue("otp_timeout", int(self.otp_timeout_spin.value()))
        self.settings.setValue("otp_interval", int(self.otp_interval_spin.value()))
        self.settings.setValue("max_attempts", int(self.max_attempts_spin.value()))
        self.settings.setValue("auto_rerun_attempts", int(self.auto_rerun_spin.value()))
        self.settings.setValue("batch_auto_rerun_attempts", int(self.batch_auto_rerun_spin.value()))
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
                self.output_hint_label.setText("正在导出，完成后这里会自动出现结果所在位置入口。")
            elif has_result:
                self.output_hint_label.setText("已生成结果，可直接打开所在位置。")
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

    def _read_failed_rerun_text(self) -> str:
        path_text = str(self._last_failed_rerun_file or "").strip()
        if not path_text:
            return ""
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def _reset_failed_rerun_autostart_state(self) -> None:
        self._pending_failed_rerun_autostart = False
        self._failed_rerun_autostart_silent = False
        self._starting_failed_rerun_batch = False
        self._failed_rerun_start_retries = 0

    def _batch_auto_rerun_limit(self) -> int:
        if hasattr(self, "batch_auto_rerun_spin"):
            return max(0, min(3, int(self.batch_auto_rerun_spin.value())))
        return 1

    def rerun_failed_accounts(self, *, automatic: bool = False) -> None:
        if self._is_running:
            if automatic:
                self.append_log("🟡 批次级自动补跑：当前仍有任务在运行，已跳过本次自动触发。")
            return
        label = "批次级自动补跑" if automatic else "重跑失败账号"
        try:
            text = self._read_failed_rerun_text()
        except Exception as exc:
            self._last_failed_rerun_file = ""
            self._reset_failed_rerun_autostart_state()
            self._refresh_controls_state()
            message = f"{label}：失败清单读取失败：{type(exc).__name__}: {exc}"
            self.append_log(f"⚠️ {message}")
            if not automatic:
                QMessageBox.warning(self, "无法读取失败清单", message)
            return
        if not text:
            self._last_failed_rerun_file = ""
            self._reset_failed_rerun_autostart_state()
            self._refresh_controls_state()
            message = "没有找到可恢复失败账号清单，或清单已经不存在。"
            self.append_log(f"🟡 {label}：{message}")
            if not automatic:
                QMessageBox.information(self, "没有可重跑账号", message)
            return
        count = len([line for line in text.splitlines() if line.strip()])
        self._pending_failed_rerun_autostart = True
        self._failed_rerun_autostart_silent = bool(automatic)
        self._starting_failed_rerun_batch = True
        self._input_mode = "paste"
        previous_blocked = self.paste_edit.blockSignals(True)
        try:
            self.paste_edit.setPlainText(text)
        finally:
            self.paste_edit.blockSignals(previous_blocked)
        self._preflight_timer.stop()
        self._refresh_input_mode()
        self._set_status("准备补跑", "warning")
        self.append_log(f"🔄 {label}：已载入 {count} 个可恢复失败账号，预检查通过后作为新批次执行。")
        self.preflight(silent=True)

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
        has_failed_rerun = bool(str(getattr(self, "_last_failed_rerun_file", "") or "").strip())
        pending_failed_rerun = bool(self._pending_failed_rerun_autostart or self._starting_failed_rerun_batch)
        interaction_locked = bool(self._is_running or pending_failed_rerun)
        can_start = (
            (not self._is_running)
            and (not self._preflight_running)
            and (not pending_failed_rerun)
            and output_selected
            and has_output
            and has_input
            and has_valid_rows
        )
        self.run_btn.setEnabled(can_start)
        self.run_btn.setText("取消中..." if self._is_cancelling else "开始导出")
        if hasattr(self, "rerun_failed_btn"):
            self.rerun_failed_btn.setVisible(has_failed_rerun)
            self.rerun_failed_btn.setEnabled(
                has_failed_rerun and not self._is_running and not self._preflight_running and not pending_failed_rerun and output_selected and has_output
            )
        self.cancel_btn.setVisible(self._is_running)
        self.cancel_btn.setEnabled(self._is_running and not self._is_cancelling)
        self.cancel_btn.setText("取消中..." if self._is_cancelling else "取消")
        self.preflight_btn.setText("预检查中..." if self._preflight_running else "预检查")
        self.preflight_btn.setEnabled((not self._is_running) and (not self._preflight_running) and (not pending_failed_rerun) and has_input)
        self.clear_input_btn.setEnabled(not interaction_locked and (bool(self._paste_text()) or bool(self._input_path())))
        if hasattr(self, "clear_log_btn"):
            self.clear_log_btn.setEnabled(not interaction_locked)
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
            self.auto_rerun_spin,
            self.batch_auto_rerun_spin,
        ):
            widget.setEnabled(not interaction_locked)
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
        raw = self.output_edit.text().strip() or self._default_output_dir_text()
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
        dialog.setFixedSize(540, 392)
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
        auto_rerun_spin = self._spin(0, 5, int(self.auto_rerun_spin.value()))
        batch_auto_spin = self._spin(0, 3, int(self.batch_auto_rerun_spin.value()))
        for spin in (http_spin, otp_spin, interval_spin, attempts_spin, auto_rerun_spin, batch_auto_spin):
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
        add_row(3, "自动重试次数", "单账号遇到可恢复失败时最多尝试几次，默认 3。", attempts_spin)
        add_row(4, "单账号自动重跑补救次数", "自动重试仍未成功时，进入单账号自动重跑补救；账号停用等终态失败不会重跑。", auto_rerun_spin)
        add_row(5, "批次级自动补跑次数", "批次结束后读取失败清单重新开批；0 表示关闭，默认 1。", batch_auto_spin)
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
            self.auto_rerun_spin.setValue(auto_rerun_spin.value())
            self.batch_auto_rerun_spin.setValue(batch_auto_spin.value())
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
        dialog = self._create_input_file_dialog(self.file_drop.path)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selectedFiles():
            self.file_drop.set_path(dialog.selectedFiles()[0])
            self._input_mode = "file"
            self._refresh_input_mode()
            self._schedule_preflight()

    def pick_output(self) -> None:
        dialog = self._create_output_directory_dialog(self.output_edit.text())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selectedFiles():
            selected = Path(dialog.selectedFiles()[0])
            if selected.is_file():
                selected = selected.parent
            self._output_dir_custom = True
            self.output_edit.setText(str(selected))
            self._save_settings()

    def open_output_dir(self) -> None:
        path = Path(self._last_result_dir or self.output_edit.text().strip() or self._default_output_dir_text())
        ok, message = self._validate_output_dir(create=True)
        if not ok:
            QMessageBox.warning(self, "输出目录不可用", message)
            return
        if not path.exists():
            path = Path(self.output_edit.text().strip() or self._default_output_dir_text())
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
            was_rerun_autostart = bool(self._pending_failed_rerun_autostart)
            label = "批次级自动补跑" if self._failed_rerun_autostart_silent else "重跑失败账号"
            self._reset_failed_rerun_autostart_state()
            self._set_status("等待修正" if silent else "预检查失败", "warning" if silent else "failed")
            self._refresh_controls_state()
            if was_rerun_autostart:
                self.append_log(f"⚠️ {label}预检查失败：{error}")
            if not silent:
                QMessageBox.critical(self, "预检查失败", f"读取失败：{error}")
            return
        if not has_input:
            self._last_preflight_count = 0
            self._last_preflight_raw_count = 0
            self._last_preflight_error = ""
            self._reset_counts(0)
            was_rerun_autostart = bool(self._pending_failed_rerun_autostart)
            label = "批次级自动补跑" if self._failed_rerun_autostart_silent else "重跑失败账号"
            self._reset_failed_rerun_autostart_state()
            self._set_status("就绪", "ready")
            self._refresh_controls_state()
            if was_rerun_autostart:
                self.append_log(f"⚠️ {label}预检查失败：失败清单没有可识别的账号行。")
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
        if self._pending_failed_rerun_autostart:
            if row_count > 0:
                label = "批次级自动补跑" if self._failed_rerun_autostart_silent else "重跑失败账号"
                self._pending_failed_rerun_autostart = False
                self.append_log(f"✅ {label}预检查通过：识别到 {row_count} 个账号，开始新批次。")
                QTimer.singleShot(0, self.start_run)
            else:
                label = "批次级自动补跑" if self._failed_rerun_autostart_silent else "重跑失败账号"
                self._reset_failed_rerun_autostart_state()
                self.append_log(f"⚠️ {label}预检查失败：失败清单没有识别到有效行。")
            return
        if not silent:
            outputs = self._selected_output_labels() or "未选择"
            input_format_label = self._input_format_label()
            skipped = max(0, raw_count - row_count)
            self.append_log(f"🧪 预检查完成：识别到 {self._total} 个有效账号，跳过 {skipped} 行；输入格式：{input_format_label}；导出：{outputs}。")
            QMessageBox.information(self, "预检查完成", f"有效行数：{self._total}\n跳过行数：{skipped}\n输入格式：{input_format_label}\n输出：{outputs}")

    def start_run(self) -> None:
        silent_autostart = bool(self._failed_rerun_autostart_silent)
        from_failed_rerun = bool(self._starting_failed_rerun_batch)

        def stop_silent_autostart(message: str) -> None:
            self.append_log(f"⚠️ 批次级自动补跑：{message}")
            self._reset_failed_rerun_autostart_state()
            self._refresh_controls_state()

        if self._worker_thread and self._worker_thread.is_alive():
            if silent_autostart:
                if self._failed_rerun_start_retries < 20:
                    self._failed_rerun_start_retries += 1
                    if self._failed_rerun_start_retries == 1:
                        self.append_log("🔄 批次级自动补跑：上一批任务正在收尾，稍等片刻后自动继续。")
                    QTimer.singleShot(80, self.start_run)
                    return
                stop_silent_autostart("上一批任务长时间未完成收尾，已停止本次自动触发；可稍后点击“重跑失败账号”。")
                return
            QMessageBox.information(self, "正在运行", "当前任务还没有结束。")
            return
        input_path = self._input_path() if self._input_mode == "file" else ""
        paste_text = self._paste_text() if self._input_mode == "paste" else ""
        output_dir = self.output_edit.text().strip() or self._default_output_dir_text()
        if not paste_text and not input_path:
            if silent_autostart:
                stop_silent_autostart("没有可用输入，已停止本次自动触发。")
                return
            QMessageBox.warning(self, "缺少输入", "请粘贴账号文本，或导入账号文件。")
            return
        if not output_dir:
            if silent_autostart:
                stop_silent_autostart("缺少输出目录，已停止本次自动触发。")
                return
            QMessageBox.warning(self, "缺少输出", "请先选择输出目录。")
            return
        output_ok, output_message = self._validate_output_dir(create=True)
        if not output_ok:
            if silent_autostart:
                stop_silent_autostart(f"输出目录不可用：{output_message}")
                return
            QMessageBox.warning(self, "输出目录不可用", output_message)
            return
        if not (self.sub2api_check.isChecked() or self.cpa_check.isChecked()):
            if silent_autostart:
                stop_silent_autostart("没有选择导出格式，已停止本次自动触发。")
                return
            QMessageBox.warning(self, "缺少导出格式", "请至少选择 Sub2API JSON 或 CPA JSON。")
            return
        if not self._current_preflight_cache_valid():
            self.preflight(silent=True)
            if silent_autostart:
                stop_silent_autostart("预检查状态已变化，已重新预检查；需要时请点击“重跑失败账号”。")
                return
            QMessageBox.information(self, "预检查中", "输入内容需要先完成预检查。请稍等识别完成后再开始导出。")
            return
        if not from_failed_rerun:
            self._batch_auto_rerun_count = 0
            self._batch_auto_rerun_accumulated_success = 0
        self._reset_counts(self._total)
        if from_failed_rerun and not self._log_waiting and self.log_edit.toPlainText().strip():
            label = "批次级自动补跑" if silent_autostart else "重跑失败账号"
            self.append_log("")
            self.append_log(f"━━ {label}：新批次开始，只处理失败清单中的账号。")
        else:
            self.log_edit.clear()
            self._log_waiting = False
        self._set_status("运行中", "running")
        self.append_log("🚀 开始导出：配置已确认，正在按协议获取 JSON。")
        self.append_log(f"🧩 运行配置：输入格式={self._input_format_label()}；导出={self._selected_output_labels()}；并发={'自动' if int(self.concurrency_spin.value()) == 0 else self.concurrency_spin.value()}。")
        total_attempts = int(self.max_attempts_spin.value()) + int(self.auto_rerun_spin.value())
        self.append_log(f"🔁 稳定性策略：可恢复失败先自动重试 {int(self.max_attempts_spin.value())} 次；仍未成功时进入单账号自动重跑补救 {int(self.auto_rerun_spin.value())} 次，最多 {total_attempts} 次。")
        batch_auto_limit = self._batch_auto_rerun_limit()
        if batch_auto_limit:
            self.append_log(f"🔄 批次级自动补跑：批次结束后最多自动补跑 {batch_auto_limit} 次，只处理 failed_rerun.secret.txt 中的可恢复失败账号。")
        else:
            self.append_log("🔄 批次级自动补跑：当前已关闭；仍会生成失败清单并保留“重跑失败账号”手动入口。")
        self.append_log("🧭 执行流程：OAuth 初始化 → 账号密码验证 → 按需获取邮箱验证码 → Callback 换取 JSON。")
        self.append_log("🔎 登录策略：优先账密登录；只有出现验证码页面时才启用取码源；全程不拉起浏览器。")
        self.append_log(f"📁 输出根目录：{Path(output_dir).resolve()}（本次会自动新建唯一批次目录，不覆盖旧文件）")
        self._cancel_event = threading.Event()
        self._is_cancelling = False
        self._last_result_dir = ""
        self._last_failed_rerun_file = ""
        if from_failed_rerun and silent_autostart:
            self._batch_auto_rerun_count += 1
        self._reset_failed_rerun_autostart_state()
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
            auto_rerun_attempts=int(self.auto_rerun_spin.value()),
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
            "password_page_warmup": "密码页预热",
            "password_verify": "密码验证",
            "password_verify_repair": "密码链路修复",
            "password_page_repair": "密码页修复",
            "password_verify_repair_result": "密码修复结果",
            "email_verification": "邮箱验证码",
            "email_otp_page_warmup": "验证码页预热",
            "otp_backend_plan": "验证码获取",
            "otp_fetch": "验证码获取",
            "email_otp_validate": "验证码提交",
            "email_otp_validate_repair": "验证码链路修复",
            "email_otp_page_repair": "验证码页修复",
            "email_otp_validate_repair_result": "验证码修复结果",
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
            "account_deactivated": "服务端返回账号已停用；自动重试无法修复，请更换账号或联系上游处理。",
            "account_disabled": "服务端返回账号已禁用；自动重试无法修复，请更换账号或联系上游处理。",
            "account_suspended": "服务端返回账号已暂停；自动重试无法修复，请更换账号或联系上游处理。",
            "account_deleted": "服务端返回账号已注销；自动重试无法修复，请更换账号或联系上游处理。",
            "account_locked": "服务端返回账号锁定；建议暂停重试，等待解锁或联系上游处理。",
            "account_not_found": "服务端未识别该登录邮箱，请检查账号文本或更换账号。",
            "user_not_found": "服务端未识别该登录邮箱，请检查账号文本或更换账号。",
            "invalid_credentials": "服务端返回凭据无效，请检查 GPT/OpenAI 邮箱和登录密码。",
            "invalid_username_or_password": "服务端返回账号或密码不匹配，请检查第二段是否为 GPT/OpenAI 登录密码。",
            "invalid_auth_step": "认证步骤状态不同步，客户端会自动刷新会话状态后重试。",
            "bad_request": "认证接口认为当前请求状态不完整，客户端会自动刷新页面状态后重试。",
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

    def _is_terminal_reason(self, value: Any) -> bool:
        return str(value or "").strip().lower() in {
            "account_deactivated",
            "account_disabled",
            "account_suspended",
            "account_deleted",
            "account_locked",
            "account_not_found",
            "user_not_found",
            "invalid_credentials",
            "invalid_username_or_password",
        }

    def _attempt_suffix(self, event: dict[str, Any]) -> str:
        try:
            attempt = int(event.get("attempt") or 1)
            max_attempts = int(event.get("max_attempts") or 0)
            normal_attempts = int(event.get("normal_attempts") or max_attempts or 0)
            auto_rerun_attempts = int(event.get("auto_rerun_attempts") or max(0, max_attempts - normal_attempts))
        except Exception:
            return ""
        if attempt <= 1:
            return ""
        if normal_attempts and attempt > normal_attempts:
            extra_index = max(1, attempt - normal_attempts)
            extra_total = max(1, auto_rerun_attempts)
            return f"（补救 {extra_index}/{extra_total}，总 {attempt}/{max_attempts or attempt}）"
        if normal_attempts:
            return f"（重试 {attempt}/{normal_attempts}）"
        return f"（第 {attempt} 次）"

    def _retry_attempt_text(self, event: dict[str, Any]) -> str:
        try:
            next_attempt = int(event.get("next_attempt") or 0)
            max_attempts = int(event.get("max_attempts") or 0)
            normal_attempts = int(event.get("normal_attempts") or max_attempts or 0)
            auto_rerun_attempts = int(event.get("auto_rerun_attempts") or max(0, max_attempts - normal_attempts))
        except Exception:
            return "下一次尝试"
        if not next_attempt:
            return "下一次尝试"
        if bool(event.get("auto_rerun")):
            extra_index = max(1, next_attempt - normal_attempts)
            extra_total = max(1, auto_rerun_attempts)
            return f"补救第 {extra_index}/{extra_total} 次（总第 {next_attempt}/{max_attempts or next_attempt} 次）"
        if normal_attempts and max_attempts and max_attempts > normal_attempts:
            return f"常规第 {next_attempt}/{normal_attempts} 次（总上限 {max_attempts} 次）"
        return f"第 {next_attempt}/{max_attempts} 次尝试" if max_attempts else "下一次尝试"

    def _friendly_stage_message(self, event: dict[str, Any]) -> str:
        account = f"{self._account_label(event)}{self._attempt_suffix(event)}"
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
        if stage == "password_page_warmup":
            if event.get("error"):
                return f"🧩 {account}：密码页预热暂未完成，继续使用当前会话尝试验证。"
            return f"🧩 {account}：已按浏览器流程预热密码页（{status}），同步认证会话状态。"
        if stage == "password_verify":
            try:
                code = int(event.get("status_code") or 0)
            except Exception:
                code = 0
            if code >= 400:
                return f"🚫 {account}：密码验证被服务端拒绝（{status}），不会进入验证码阶段。"
            if bool(event.get("callback_url_present")):
                return f"✅ {account}：密码验证通过，已直接获得 Callback。"
            if "otp" in page_type.lower() or "verify" in page_type.lower():
                return f"📮 {account}：密码验证通过，服务端要求邮箱验证码，准备访问取码源。"
            return f"🔑 {account}：密码验证完成（{status}），继续推进授权流程。"
        if stage == "password_verify_repair":
            reason = self._reason_display(event.get("reason"))
            suffix = f"；原因：{reason}" if reason else ""
            return f"🧰 {account}：密码验证链路触发一次自动修复，正在刷新页面状态和风控票据{suffix}。"
        if stage == "password_page_repair":
            if event.get("error"):
                return f"🧩 {account}：密码页状态重新同步失败，仍会用刷新后的风控票据再试一次。"
            return f"🧩 {account}：密码页状态已重新同步（{status}），准备再次验证密码。"
        if stage == "password_verify_repair_result":
            try:
                code = int(event.get("status_code") or 0)
            except Exception:
                code = 0
            if code >= 400:
                return f"🚫 {account}：密码链路自动修复后仍被拒绝（{status}），将按失败诊断处理。"
            return f"✅ {account}：密码链路自动修复成功（{status}），继续推进后续流程。"
        if stage == "email_otp_page_warmup":
            if event.get("error"):
                return f"🧩 {account}：验证码页预热暂未完成，继续使用当前会话提交验证码。"
            return f"🧩 {account}：已预热验证码页（{status}），同步取码提交前的会话状态。"
        if stage == "otp_backend_plan":
            primary = self._backend_display(event.get("primary_backend"))
            display_name = str(event.get("display_name") or "").strip()
            suffix = f" · {display_name}" if display_name and display_name != primary else ""
            return f"📫 {account}：取码方式已确定为 {primary}{suffix}，正在等待新的邮箱验证码。"
        if stage == "otp_fetch":
            backend = self._backend_display(event.get("backend"))
            if bool(event.get("code_present")):
                return f"📬 {account}：已获取验证码（来源：{backend}，{status}），准备提交验证。"
            return f"⌛ {account}：本轮未拿到新验证码（来源：{backend}，{status}），将先自动重试；仍未成功时进入自动重跑补救。"
        if stage == "email_otp_validate":
            try:
                code = int(event.get("status_code") or 0)
            except Exception:
                code = 0
            final_attempt = int(event.get("attempt") or 1) >= int(event.get("max_attempts") or 1)
            tail = "已到自动重试与自动重跑补救上限，将写入失败诊断" if final_attempt else "稍后会按自动重试 / 自动重跑补救策略处理"
            if code == 401:
                return f"🧾 {account}：验证码提交后被拒绝（{status}），可能是旧码/过期码，{tail}。"
            if code == 403:
                return f"🚫 {account}：验证码提交后被服务端拒绝（{status}），优先按账号状态问题诊断。"
            if code >= 400:
                return f"🧾 {account}：验证码提交接口返回异常（{status}），等待失败诊断。"
            if bool(event.get("callback_url_present")):
                return f"🧾 {account}：验证码提交成功（{status}），已获得 Callback。"
            return f"🧾 {account}：验证码已提交（{status}），正在进入收尾流程。"
        if stage == "email_otp_validate_repair":
            reason = self._reason_display(event.get("reason"))
            suffix = f"；原因：{reason}" if reason else ""
            return f"🧰 {account}：验证码提交链路触发一次自动修复，正在刷新页面状态和风控票据{suffix}。"
        if stage == "email_otp_page_repair":
            if event.get("error"):
                return f"🧩 {account}：验证码页状态重新同步失败，仍会用刷新后的风控票据再试一次。"
            return f"🧩 {account}：验证码页状态已重新同步（{status}），准备再次提交验证码。"
        if stage == "email_otp_validate_repair_result":
            try:
                code = int(event.get("status_code") or 0)
            except Exception:
                code = 0
            if code >= 400:
                return f"🧾 {account}：验证码链路自动修复后仍返回异常（{status}），稍后会按自动重试策略处理。"
            return f"✅ {account}：验证码链路自动修复成功（{status}），继续进入收尾流程。"
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
            out_dir = str(event.get("out_dir") or "").strip()
            if out_dir:
                self._last_result_dir = out_dir
            self.append_log(f"📦 任务已启动：共 {self._total} 个账号，并发={concurrency}。")
            if out_dir:
                self.append_log(f"🗂️ 本次结果目录：{out_dir}")
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
            auto_rerun = bool(event.get("auto_rerun"))
            attempt_text = self._retry_attempt_text(event)
            detail = f"；原因：{reason}" if reason else ""
            if auto_rerun:
                self.append_log(f"🔄 自动重跑补救：{account} 上次停在「{self._stage_display(stage)}」{detail}，正在进行{attempt_text}。")
            else:
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
                attempt = int(event.get("attempt") or 1)
                max_attempts = int(event.get("max_attempts") or 1)
                if status == "cancelled":
                    self.append_log(f"🛑 取消：{account} 已停止，等待其它运行中的账号收尾。")
                elif self._is_terminal_reason(reason):
                    detail = self._reason_display(reason)
                    self.append_log(f"🚫 终态失败：{account} {detail} 客户端不会继续消耗重跑次数。")
                else:
                    detail = f"；原因：{self._reason_display(reason)}" if reason else ""
                    if attempt >= max_attempts and max_attempts > 1:
                        self.append_log(
                            f"⚠️ 可恢复失败：{account} 已自动重试 / 自动重跑补救 {attempt}/{max_attempts} 次，"
                            f"仍停在「{self._stage_display(stage or status)}」{detail}。"
                        )
                    else:
                        self.append_log(f"⚠️ 失败：{account} 停在「{self._stage_display(stage or status)}」{detail}。")
            self.success_stat.set_value(self._success)
            self.failed_stat.set_value(self._failure)
            self.running_stat.set_value(self._running)
            self._update_progress()

    def _append_export_validation_logs(self, validation: Any, *, summary_file: str = "") -> None:
        if not isinstance(validation, dict) or not validation.get("checked"):
            return
        status = str(validation.get("status") or ("可导入" if validation.get("ok", True) else "不建议导入"))
        self.append_log(f"🔍 导出校验：已检查导出的 JSON 是否可导入，整体状态：{status}。")
        detail = f"详情见 {summary_file}。" if summary_file else "详情见 _diagnostics/summary.json。"
        sub = validation.get("sub2api") if isinstance(validation.get("sub2api"), dict) else {}
        if sub.get("selected"):
            count = int(sub.get("count") or 0)
            if bool(sub.get("ok")):
                self.append_log(f"✅ 导出校验：Sub2API JSON 可导入（{count} 个账号）。")
            else:
                issue_count = int(sub.get("issue_count") or len(sub.get("errors") or []))
                self.append_log(f"⚠️ 导出校验：Sub2API JSON 不建议导入（{issue_count} 个问题）；{detail}")
        cpa = validation.get("cpa") if isinstance(validation.get("cpa"), dict) else {}
        if cpa.get("selected"):
            count = int(cpa.get("count") or 0)
            issue_count = int(cpa.get("issue_count") or len(cpa.get("errors") or []))
            if bool(cpa.get("ok")):
                self.append_log(f"✅ 导出校验：CPA 单账号 JSON 可导入 {count}/{count} 个。")
            else:
                not_recommended = min(count, issue_count) if count else issue_count
                self.append_log(f"⚠️ 导出校验：CPA 单账号 JSON 不建议导入 {not_recommended}/{count} 个；{detail}")

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
        cpa_dir = str(summary.get("cpa_dir") or "")
        result_dir = str(summary.get("out_dir") or "")
        diagnostics_dir = str(summary.get("diagnostics_dir") or "")
        summary_file = str(summary.get("summary_file") or "")
        failure_report = str(summary.get("failure_report") or "")
        failed_rerun_file = str(summary.get("failed_rerun_file") or "")
        rerunnable_failure_count = int(summary.get("rerunnable_failure_count") or 0)
        non_rerunnable_failure_count = int(summary.get("non_rerunnable_failure_count") or 0)
        failure_categories = summary.get("failure_categories") if isinstance(summary.get("failure_categories"), dict) else {}
        retry_count = int(summary.get("retry_count") or 0)
        auto_rerun_count = int(summary.get("auto_rerun_count") or 0)
        cpa_path = cpa_dir or str(summary.get("cpa_manifest") or "")
        self.sub2api_row.set_path(sub2api_path)
        self.cpa_row.set_path(cpa_path)
        if result_dir:
            self._last_result_dir = result_dir
        if failed_rerun_file and rerunnable_failure_count > 0 and Path(failed_rerun_file).exists() and not cancelled:
            self._last_failed_rerun_file = failed_rerun_file
        else:
            self._last_failed_rerun_file = ""
        self._refresh_output_format_state()
        self.append_log("")
        if cancelled:
            self.append_log(f"🛑 任务已取消：成功 {success_count} 个，未完成/失败 {failure_count} 个，其中取消 {cancelled_count} 个。")
        else:
            self.append_log(f"🎉 任务完成：成功 {success_count} 个，失败 {failure_count} 个。")
        if retry_count or auto_rerun_count:
            self.append_log(f"🧮 自动重试 / 自动重跑补救统计：{retry_count} 个账号触发自动重试，其中 {auto_rerun_count} 个进入自动重跑补救。")
        self._append_export_validation_logs(summary.get("export_validation"), summary_file=summary_file)
        if failure_categories:
            parts = [f"{name} {count} 个" for name, count in failure_categories.items()]
            self.append_log(f"⚠️ 失败诊断：{'；'.join(parts)}。")
            terminal_count = sum(int(failure_categories.get(name, 0) or 0) for name in ("账号状态不可用", "账号被锁定", "账号不存在", "凭据无效", "密码验证失败"))
            unretryable_count = max(0, non_rerunnable_failure_count - terminal_count - cancelled_count)
            if terminal_count:
                self.append_log(f"🚫 终态账号：{terminal_count} 个账号已被服务端明确拒绝，客户端不会继续消耗重跑次数。")
            if rerunnable_failure_count and not cancelled and not self._last_failed_rerun_file:
                self.append_log(f"🟡 可恢复失败：{rerunnable_failure_count} 个账号已达到当前自动重试与自动重跑补救上限；可增加自动重跑补救次数或降低并发后再次开始。")
            if unretryable_count and not cancelled:
                self.append_log(f"🧯 未自动补跑：{unretryable_count} 个失败暂未归类为可恢复，请查看失败诊断报告后处理。")
        if sub2api_path:
            self.append_log(f"🧰 Sub2API 输出：{sub2api_path}")
        if result_dir:
            self.append_log(f"🗂️ 本次结果目录：{result_dir}")
        if diagnostics_dir:
            self.append_log(f"🧾 诊断目录：{diagnostics_dir}（普通导入只需要根目录 JSON 和 CPA 文件夹）")
        if cpa_path:
            if cpa_dir:
                self.append_log(f"📚 CPA 单账号 JSON 目录：{cpa_dir}")
        if failure_report:
            self.append_log(f"🧾 失败诊断报告：{failure_report}")
        if self._last_failed_rerun_file:
            self.append_log(f"🔁 可恢复失败清单：{rerunnable_failure_count} 个账号已写入 {self._last_failed_rerun_file}")
            self.append_log("🛠️ 这份清单可用于批次级自动补跑，也可点击“重跑失败账号”手动补跑。")
        batch_auto_limit = self._batch_auto_rerun_limit()
        should_batch_auto_rerun = (
            bool(self._last_failed_rerun_file)
            and rerunnable_failure_count > 0
            and not cancelled
            and self._batch_auto_rerun_count < batch_auto_limit
        )
        if should_batch_auto_rerun:
            next_batch_auto_rerun = self._batch_auto_rerun_count + 1
            self._batch_auto_rerun_accumulated_success += success_count
            self._failed_rerun_autostart_silent = True
            self._starting_failed_rerun_batch = True
            self.append_log(
                f"🔄 批次级自动补跑：检测到 {rerunnable_failure_count} 个可恢复失败账号，"
                f"将执行第 {next_batch_auto_rerun}/{batch_auto_limit} 次批次级自动补跑；"
                "达到上限后若仍失败，将保留“重跑失败账号”入口，不再自动循环。"
            )
            self._refresh_controls_state()
            QTimer.singleShot(0, lambda: self.rerun_failed_accounts(automatic=True))
            return
        if self._last_failed_rerun_file and not cancelled:
            if batch_auto_limit <= 0:
                self.append_log("🟡 批次级自动补跑：当前已关闭；仍有可恢复失败账号时，请点击“重跑失败账号”手动补跑。")
            elif self._batch_auto_rerun_count >= batch_auto_limit:
                self.append_log(
                    f"🟡 批次级自动补跑：已达到当前 {batch_auto_limit} 次上限；"
                    "仍有可恢复失败账号时，请点击“重跑失败账号”手动补跑。"
                )
        self.append_log("👀 提示：导出校验为“可导入”后再导入目标系统；标记为“不建议导入”的文件请先修正或重新导出。")
        self._refresh_controls_state()
        if cancelled:
            QMessageBox.information(self, "已取消", f"导出已取消\n成功：{success_count}\n失败/未完成：{failure_count}\n取消：{cancelled_count}")
        else:
            extra = f"\n可重跑：{rerunnable_failure_count}" if self._last_failed_rerun_file else ""
            if self._batch_auto_rerun_accumulated_success:
                total_success = self._batch_auto_rerun_accumulated_success + success_count
                QMessageBox.information(
                    self,
                    "自动补跑批次完成",
                    f"自动补跑批次完成\n本次补跑成功：{success_count}\n本次补跑失败：{failure_count}{extra}\n累计成功：{total_success}\n当前仍失败：{failure_count}",
                )
                self._batch_auto_rerun_accumulated_success = 0
            else:
                QMessageBox.information(self, "完成", f"导出完成\n成功：{success_count}\n失败：{failure_count}{extra}")

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
    install_qt_translations(app)
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    lock_path = single_instance_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(lock_path))
    if not instance_lock.tryLock(100):
        instance_lock.removeStaleLockFile()
        if not instance_lock.tryLock(100):
            QMessageBox.information(None, "GPT2JSON 已在运行", "GPT2JSON 已经打开。\n\n为避免新旧版本或多个任务同时写入，请先关闭现有窗口后再启动。")
            return 0
    app._gpt2json_instance_lock = instance_lock  # type: ignore[attr-defined]
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
