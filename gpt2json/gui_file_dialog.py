from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QIdentityProxyModel, QObject, Qt
from PySide6.QtWidgets import QDialog

# Source-only ownership marker; file dialogs never display this value.
_AYEST0_DIALOG_TRACE = "AyeSt0:https://github.com/AyeSt0"


class LocalizedFileDialogProxyModel(QIdentityProxyModel):
    HEADER_LABELS = ("名称", "大小", "类型", "修改时间")

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal and section < len(self.HEADER_LABELS):
            return self.HEADER_LABELS[section]
        return super().headerData(section, orientation, role)


class DialogDragFilter(QObject):
    def __init__(self, dialog: QDialog) -> None:
        super().__init__(dialog)
        self.dialog = dialog
        self._drag_offset: Any = None

    def eventFilter(self, obj: QObject, event: Any) -> bool:  # noqa: N802
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = self._global_point(event) - self.dialog.frameGeometry().topLeft()
            event.accept()
            return True
        if event_type == QEvent.Type.MouseMove and self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.dialog.move(self._global_point(event) - self._drag_offset)
            event.accept()
            return True
        if event_type == QEvent.Type.MouseButtonRelease:
            self._drag_offset = None
        return super().eventFilter(obj, event)

    @staticmethod
    def _global_point(event: Any) -> Any:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()


def build_unified_file_dialog_stylesheet(p: dict[str, str]) -> str:
    """Return the GPT2JSON themed stylesheet for non-native file dialogs."""

    return f"""
        QFileDialog#UnifiedFileDialog {{
            background:{p['card']};
            color:{p['text']};
            border:1px solid {p['border']};
            border-radius:14px;
        }}
        #FileDialogTitleBar {{
            min-height:42px;
            max-height:42px;
            border:none;
            border-bottom:1px solid {p['border']};
            background:transparent;
        }}
        #FileDialogTitleIcon {{
            min-width:22px;
            max-width:22px;
            min-height:22px;
            max-height:22px;
        }}
        #FileDialogTitle {{
            color:{p['text']};
            font-size:14px;
            font-weight:900;
        }}
        #FileDialogCloseButton {{
            min-width:32px;
            max-width:32px;
            min-height:32px;
            max-height:32px;
            border:none;
            border-radius:8px;
            color:{p['text']};
            background:transparent;
            font-size:18px;
            padding:0;
        }}
        #FileDialogCloseButton:hover {{
            color:white;
            background:#EF4444;
        }}
        #ToolbarLocationLabel {{
            color:{p['muted']};
            font-size:12px;
            font-weight:800;
        }}
        QFileDialog#UnifiedFileDialog QLabel {{
            color:{p['muted']};
            font-size:12px;
            font-weight:700;
        }}
        QFileDialog#UnifiedFileDialog QLineEdit,
        QFileDialog#UnifiedFileDialog QComboBox {{
            min-height:34px;
            border-radius:9px;
            padding-left:10px;
            padding-right:8px;
            color:{p['text']};
            background:{p['input']};
            border:1px solid {p['border']};
            font-size:12px;
            font-weight:600;
        }}
        QFileDialog#UnifiedFileDialog QLineEdit:focus,
        QFileDialog#UnifiedFileDialog QComboBox:focus {{
            border:1px solid #60A5FA;
        }}
        QFileDialog#UnifiedFileDialog QComboBox::drop-down {{
            width:24px;
            border:none;
            background:transparent;
        }}
        QFileDialog#UnifiedFileDialog QListView,
        QFileDialog#UnifiedFileDialog QTreeView {{
            outline:0;
            color:{p['text']};
            background:{p['input']};
            border:1px solid {p['border']};
            border-radius:9px;
            padding:4px;
            alternate-background-color:{p['soft']};
            selection-background-color:#2563EB;
            selection-color:white;
        }}
        QFileDialog#UnifiedFileDialog QListView#sidebar {{
            min-width:96px;
            max-width:112px;
            color:{p['text']};
            background:{p['soft']};
            border:1px solid {p['border']};
            border-radius:9px;
            padding:4px;
            font-size:11px;
            font-weight:700;
        }}
        QFileDialog#UnifiedFileDialog QListView::item,
        QFileDialog#UnifiedFileDialog QTreeView::item {{
            min-height:22px;
            padding:2px 6px;
            border-radius:6px;
        }}
        QFileDialog#UnifiedFileDialog QListView#sidebar::item {{
            min-height:23px;
            padding:2px 5px;
            border-radius:7px;
        }}
        QFileDialog#UnifiedFileDialog QListView::item:hover,
        QFileDialog#UnifiedFileDialog QTreeView::item:hover {{
            color:#2563EB;
            background:{p['soft']};
        }}
        QFileDialog#UnifiedFileDialog QListView#sidebar::item:hover {{
            color:#2563EB;
            background:{p['input']};
        }}
        QFileDialog#UnifiedFileDialog QListView::item:selected,
        QFileDialog#UnifiedFileDialog QTreeView::item:selected {{
            color:white;
            background:#2563EB;
        }}
        QFileDialog#UnifiedFileDialog QListView#sidebar::item:selected {{
            color:white;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1677FF,stop:1 #7C3AED);
        }}
        QFileDialog#UnifiedFileDialog QHeaderView::section {{
            min-height:26px;
            color:{p['muted']};
            background:{p['soft']};
            border:none;
            border-bottom:1px solid {p['border']};
            padding:5px 8px;
            font-size:12px;
            font-weight:800;
        }}
        QFileDialog#UnifiedFileDialog QToolButton {{
            min-width:28px;
            max-width:30px;
            min-height:28px;
            max-height:30px;
            border-radius:5px;
            color:{p['text']};
            background:transparent;
            border:1px solid transparent;
            padding:3px;
        }}
        QFileDialog#UnifiedFileDialog QToolButton:hover {{
            border-color:{p['border']};
            color:#2563EB;
            background:{p['soft']};
        }}
        QFileDialog#UnifiedFileDialog QToolButton:pressed,
        QFileDialog#UnifiedFileDialog QToolButton:checked {{
            border-color:#93C5FD;
            color:#2563EB;
            background:{p['input']};
        }}
        QFileDialog#UnifiedFileDialog QPushButton {{
            min-height:34px;
            min-width:82px;
            border-radius:9px;
            color:{p['text']};
            background:{p['soft']};
            border:1px solid {p['border']};
            font-size:12px;
            font-weight:800;
            padding:0 13px;
        }}
        QFileDialog#UnifiedFileDialog QPushButton:hover {{
            border-color:#3B82F6;
            color:#2563EB;
            background:{p['input']};
        }}
        QFileDialog#UnifiedFileDialog QPushButton#DialogPrimaryButton {{
            color:white;
            border:1px solid #2563EB;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1677FF,stop:1 #7C3AED);
        }}
        QFileDialog#UnifiedFileDialog QPushButton#DialogPrimaryButton:hover {{
            color:white;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0F63D6,stop:1 #6D28D9);
        }}
        QFileDialog#UnifiedFileDialog QSplitter::handle {{
            background:transparent;
        }}
        QFileDialog#UnifiedFileDialog QSplitter::handle:horizontal {{
            width:8px;
            margin:0 2px;
        }}
        QFileDialog#UnifiedFileDialog QSplitter::handle:horizontal:hover {{
            background:{p['border']};
            border-radius:4px;
        }}
        QFileDialog#UnifiedFileDialog QScrollBar:vertical {{
            width:10px;
            background:transparent;
            margin:2px;
        }}
        QFileDialog#UnifiedFileDialog QScrollBar::handle:vertical {{
            min-height:28px;
            border-radius:5px;
            background:{p['border2']};
        }}
        QFileDialog#UnifiedFileDialog QScrollBar::add-page:vertical,
        QFileDialog#UnifiedFileDialog QScrollBar::sub-page:vertical {{
            background:transparent;
        }}
        QFileDialog#UnifiedFileDialog QScrollBar::add-line:vertical,
        QFileDialog#UnifiedFileDialog QScrollBar::sub-line:vertical {{
            height:0;
            background:transparent;
        }}
        QFileDialog#UnifiedFileDialog QScrollBar:horizontal {{
            height:10px;
            background:transparent;
            margin:2px;
        }}
        QFileDialog#UnifiedFileDialog QScrollBar::handle:horizontal {{
            min-width:28px;
            border-radius:5px;
            background:{p['border2']};
        }}
        QFileDialog#UnifiedFileDialog QScrollBar::add-page:horizontal,
        QFileDialog#UnifiedFileDialog QScrollBar::sub-page:horizontal {{
            background:transparent;
        }}
        QFileDialog#UnifiedFileDialog QScrollBar::add-line:horizontal,
        QFileDialog#UnifiedFileDialog QScrollBar::sub-line:horizontal {{
            width:0;
            background:transparent;
        }}
        QFileDialog#UnifiedFileDialog QAbstractScrollArea::corner {{
            background:transparent;
            border:none;
        }}
    """


__all__ = ["DialogDragFilter", "LocalizedFileDialogProxyModel", "build_unified_file_dialog_stylesheet"]
