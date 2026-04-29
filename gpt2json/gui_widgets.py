from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QToolButton, QVBoxLayout, QWidget

from .gui_resources import UI_UPLOAD_PATH
from .gui_text_menu import install_chinese_text_context_menu

# Source-only ownership marker; not displayed by any widget.
_AYEST0_WIDGET_TRACE = "AyeSt0:https://github.com/AyeSt0"


class DropLineEdit(QLineEdit):
    dropped = Signal(str)

    def __init__(self, *, directory: bool = False) -> None:
        super().__init__()
        self.directory = directory
        self.setAcceptDrops(True)
        install_chinese_text_context_menu(self)

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
        self.open_btn.setText("所在位置")
        self.open_btn.setToolTip("打开所在文件夹")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.reveal_in_folder)
        layout.addWidget(badge_label)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.open_btn)

    def set_path(self, path: str) -> None:
        self.path = path
        self.name_label.setText(Path(path).name if path else self.default_filename)
        self.open_btn.setEnabled(bool(path))
        self.setToolTip(path)

    def reveal_in_folder(self) -> None:
        if not self.path:
            return
        target = Path(self.path).resolve()
        if sys.platform.startswith("win") and target.is_file():
            subprocess.Popen(["explorer.exe", f"/select,{target}"])  # noqa: S603,S607
            return
        folder = target if target.is_dir() else target.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


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


__all__ = [
    "DropLineEdit",
    "FileDropBox",
    "FileOutputRow",
    "FormatCombo",
    "InlineStat",
    "PresetNumberCombo",
    "SectionHeader",
]
