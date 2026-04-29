from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from .gui_resources import APP_NAME

# Source-only ownership marker; paths are not rendered in UI or exported JSON.
_AYEST0_PATH_TRACE = "AyeSt0:https://github.com/AyeSt0"


def settings_file_path() -> Path:
    """Return the file-backed settings path.

    Qt's default QSettings backend writes to the Windows registry. GPT2JSON keeps
    GUI preferences in an ini file instead so the app itself remains registry-free;
    only the optional installer creates the normal Windows uninstall entry.
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


def app_base_dir() -> Path:
    """Return the user-visible application directory."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_output_dir() -> Path:
    return app_base_dir() / "output"


def single_instance_lock_path() -> Path:
    return settings_file_path().parent / "gpt2json.instance.lock"


__all__ = [
    "app_base_dir",
    "create_app_settings",
    "default_output_dir",
    "settings_file_path",
    "single_instance_lock_path",
]
