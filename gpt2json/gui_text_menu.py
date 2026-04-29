from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QMenu, QPlainTextEdit

from .gui_theme import DARK_THEME, LIGHT_THEME

# Source-only ownership marker; context menus never render this value.
_AYEST0_MENU_TRACE = "AyeSt0:https://github.com/AyeSt0"


def _text_widget_has_selection(widget: Any) -> bool:
    if isinstance(widget, QLineEdit):
        return bool(widget.hasSelectedText())
    if isinstance(widget, QPlainTextEdit):
        return bool(widget.textCursor().hasSelection())
    return False


def _text_widget_delete_selection(widget: Any) -> None:
    if isinstance(widget, QLineEdit):
        if not widget.hasSelectedText():
            return
        text = widget.text()
        start = max(0, int(widget.selectionStart()))
        selected = widget.selectedText()
        widget.setText(text[:start] + text[start + len(selected) :])
        widget.setCursorPosition(start)
        return
    if isinstance(widget, QPlainTextEdit):
        cursor = widget.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
            widget.setTextCursor(cursor)


def _context_menu_palette(widget: Any) -> dict[str, str]:
    window = widget.window() if hasattr(widget, "window") else None
    if window is not None and hasattr(window, "_theme") and callable(getattr(window, "palette", None)):
        palette = window.palette()
        if isinstance(palette, dict):
            return palette
    return DARK_THEME if bool(getattr(window, "_theme", "") == "dark") else LIGHT_THEME


def _style_text_context_menu(menu: QMenu, widget: Any) -> None:
    p = _context_menu_palette(widget)
    menu.setObjectName("TextContextMenu")
    menu.setStyleSheet(
        f"""
        QMenu#TextContextMenu {{
            background:{p['card']};
            color:{p['text']};
            border:1px solid {p['border']};
            border-radius:10px;
            padding:6px;
            font-size:13px;
            font-weight:700;
        }}
        QMenu#TextContextMenu::item {{
            min-width:118px;
            min-height:28px;
            padding:5px 24px 5px 14px;
            border-radius:7px;
            background:transparent;
        }}
        QMenu#TextContextMenu::item:selected {{
            color:white;
            background:#2563EB;
        }}
        QMenu#TextContextMenu::item:disabled {{
            color:{p['muted2']};
            background:transparent;
        }}
        QMenu#TextContextMenu::separator {{
            height:1px;
            margin:6px 8px;
            background:{p['border']};
        }}
        """
    )


def build_chinese_text_context_menu(widget: Any) -> QMenu:
    menu = QMenu(widget)
    _style_text_context_menu(menu, widget)
    read_only = bool(getattr(widget, "isReadOnly", lambda: False)())
    has_selection = _text_widget_has_selection(widget)
    clipboard_data = QApplication.clipboard().mimeData()
    clipboard_has_text = bool(clipboard_data is not None and clipboard_data.hasText())

    undo_available = bool(getattr(widget, "isUndoAvailable", lambda: False)())
    redo_available = bool(getattr(widget, "isRedoAvailable", lambda: False)())
    if isinstance(widget, QPlainTextEdit):
        undo_available = bool(widget.document().isUndoAvailable())
        redo_available = bool(widget.document().isRedoAvailable())

    undo_action = menu.addAction("撤销")
    undo_action.setEnabled(not read_only and undo_available)
    undo_action.triggered.connect(widget.undo)
    redo_action = menu.addAction("重做")
    redo_action.setEnabled(not read_only and redo_available)
    redo_action.triggered.connect(widget.redo)
    menu.addSeparator()

    cut_action = menu.addAction("剪切")
    cut_action.setEnabled(not read_only and has_selection)
    cut_action.triggered.connect(widget.cut)
    copy_action = menu.addAction("复制")
    copy_action.setEnabled(has_selection)
    copy_action.triggered.connect(widget.copy)
    paste_action = menu.addAction("粘贴")
    paste_action.setEnabled(not read_only and clipboard_has_text)
    paste_action.triggered.connect(widget.paste)
    delete_action = menu.addAction("删除")
    delete_action.setEnabled(not read_only and has_selection)
    delete_action.triggered.connect(lambda _checked=False, w=widget: _text_widget_delete_selection(w))
    menu.addSeparator()

    select_all_action = menu.addAction("全选")
    if isinstance(widget, QLineEdit):
        has_text = bool(widget.text())
    elif isinstance(widget, QPlainTextEdit):
        has_text = bool(widget.toPlainText())
    else:
        has_text = True
    select_all_action.setEnabled(has_text)
    select_all_action.triggered.connect(widget.selectAll)
    return menu


def install_chinese_text_context_menu(widget: Any) -> None:
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def show_menu(pos: Any, target: Any = widget) -> None:
        menu = build_chinese_text_context_menu(target)
        menu.exec(target.mapToGlobal(pos))

    widget.customContextMenuRequested.connect(show_menu)


__all__ = ["build_chinese_text_context_menu", "install_chinese_text_context_menu"]
