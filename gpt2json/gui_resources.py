from __future__ import annotations

from pathlib import Path

from . import __version__

# Source-only ownership marker; this module only provides constants.
_AYEST0_RESOURCE_TRACE = "AyeSt0:https://github.com/AyeSt0"

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

__all__ = [
    "APP_ICON_PATH",
    "APP_NAME",
    "APP_SUBTITLE",
    "APP_VERSION",
    "ASSET_DIR",
    "ICON_DARK_PATH",
    "ICON_ICO_PATH",
    "ICON_LIGHT_PATH",
    "ICON_PATH",
    "ORG_NAME",
    "STAT_FAILED_PATH",
    "STAT_RUNNING_PATH",
    "STAT_SUCCESS_PATH",
    "STAT_TOTAL_PATH",
    "THEME_MOON_PATH",
    "THEME_SUN_PATH",
    "UI_CHEVRON_DOWN_PATH",
    "UI_INPUT_PATH",
    "UI_LOG_PATH",
    "UI_OUTPUT_PATH",
    "UI_SETTINGS_PATH",
    "UI_UPLOAD_PATH",
]
