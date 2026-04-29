"""Capture docs/assets/installer-preview.png from the real installer window.

This script avoids patching labels onto an old screenshot.  It launches the
current Windows installer in a hidden preview mode, places it over a neutral
dark backdrop, captures the actual WPF shell, and closes the installer.
"""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"
WM_CLOSE = 0x0010
SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
PW_RENDERFULLCONTENT = 0x00000002
BI_RGB = 0
DIB_RGB_COLORS = 0
BACKDROP_RGB = (7, 11, 27)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def project_version() -> str:
    namespace: dict[str, str] = {}
    exec((ROOT / "gpt2json" / "__init__.py").read_text(encoding="utf-8"), namespace)
    return str(namespace.get("__version__", "0.0.0"))


def set_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def create_backdrop() -> tk.Tk:
    root = tk.Tk()
    root.configure(bg="#070B1B")
    # Do not combine override-redirect with fullscreen: Tk rejects that on
    # some Windows builds.  A normal fullscreen backdrop is enough for the
    # README screenshot and keeps the capture based on the real installer UI.
    root.attributes("-fullscreen", True)
    root.update()
    return root


def window_text(hwnd: int) -> str:
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def process_id_for_window(hwnd: int) -> int:
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def visible_windows_for_pid(pid: int) -> list[int]:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if ctypes.windll.user32.IsWindowVisible(hwnd) and process_id_for_window(hwnd) == pid and window_text(hwnd):
            found.append(hwnd)
        return True

    ctypes.windll.user32.EnumWindows(enum_proc, 0)
    return found


def wait_for_installer_window(pid: int, timeout: float) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        windows = visible_windows_for_pid(pid)
        preferred = [hwnd for hwnd in windows if "GPT2JSON" in window_text(hwnd)]
        if preferred:
            return preferred[0]
        if windows:
            return windows[0]
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for installer window.")


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("GetWindowRect failed.")
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def _replace_printwindow_transparency(image: Image.Image) -> Image.Image:
    """Turn PrintWindow's exact black transparent pixels into alpha.

    The installer shell is a shaped WPF window.  PrintWindow gives us the real
    rendered controls without accidentally capturing unrelated floating desktop
    windows, but DWM-transparent pixels arrive as pure black.  Only exact black
    pixels are keyed out and composited onto the neutral README backdrop.
    """

    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a and r == 0 and g == 0 and b == 0:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def capture_window_direct(hwnd: int, output: Path, margin: int) -> bool:
    left, top, right, bottom = window_rect(hwnd)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return False

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old_bitmap = gdi32.SelectObject(mem_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT):
            return False

        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = BI_RGB
        buffer = ctypes.create_string_buffer(width * height * 4)
        rows = gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bitmap_info), DIB_RGB_COLORS)
        if rows != height:
            return False

        rendered = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
        rendered = _replace_printwindow_transparency(rendered)
        canvas = Image.new("RGBA", (width + margin * 2, height + margin * 2), (*BACKDROP_RGB, 255))
        canvas.alpha_composite(rendered, (margin, margin))
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(output, quality=96)
        return True
    finally:
        gdi32.SelectObject(mem_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)


def capture_window_screen(hwnd: int, output: Path, margin: int) -> None:
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    # Some desktops have floating media / chat windows marked as always-on-top.
    # Put the installer above them before screen capture so README assets are
    # clean real screenshots, not old screenshots with manual text overlays.
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)
    left, top, right, bottom = window_rect(hwnd)
    bbox = (left - margin, top - margin, right + margin, bottom + margin)
    image = ImageGrab.grab(bbox=bbox, include_layered_windows=True, all_screens=True)
    ctypes.windll.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, quality=96)


def capture_window(hwnd: int, output: Path, margin: int) -> None:
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)
    if capture_window_direct(hwnd, output, margin):
        return
    capture_window_screen(hwnd, output, margin)


def close_window(hwnd: int, process: subprocess.Popen[bytes]) -> None:
    try:
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        process.wait(timeout=3)
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=3)
        except Exception:
            process.kill()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    version = project_version()
    parser = argparse.ArgumentParser(description="Capture the README installer screenshot from the real installer.")
    parser.add_argument(
        "--installer",
        default=str(ROOT / "release" / f"GPT2JSON-Setup-v{version}.exe"),
        help="Path to GPT2JSON-Setup executable.",
    )
    parser.add_argument(
        "--output",
        default=str(ASSET_DIR / "installer-preview.png"),
        help="Output PNG path.",
    )
    parser.add_argument("--wait", type=float, default=2.4, help="Seconds to wait after the installer window appears.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Seconds to wait for the installer window.")
    parser.add_argument("--margin", type=int, default=40, help="Pixels of backdrop to include around the installer.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "win32":
        raise SystemExit("capture_installer_preview.py only supports Windows.")
    args = parse_args(argv)
    installer = Path(args.installer).resolve()
    output = Path(args.output).resolve()
    if not installer.exists():
        raise FileNotFoundError(f"Installer not found: {installer}")

    set_dpi_awareness()
    backdrop = create_backdrop()
    process = subprocess.Popen([str(installer), "--preview-install"], cwd=str(ROOT))
    hwnd = 0
    try:
        hwnd = wait_for_installer_window(process.pid, args.timeout)
        time.sleep(args.wait)
        capture_window(hwnd, output, args.margin)
        print(f"Captured real installer preview: {output}")
    finally:
        if hwnd:
            close_window(hwnd, process)
        else:
            process.terminate()
        backdrop.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
