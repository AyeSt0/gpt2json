from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"


def project_version() -> str:
    namespace: dict[str, str] = {}
    exec((ROOT / "gpt2json" / "__init__.py").read_text(encoding="utf-8"), namespace)
    return str(namespace.get("__version__", "0.0.0"))


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\seguisb.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return img


def rounded_rect_layer(size: tuple[int, int], box: tuple[int, int, int, int], radius: int, fill, shadow=None) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if shadow:
        sx, sy, blur, color = shadow
        shadow_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow_layer).rounded_rectangle((box[0] + sx, box[1] + sy, box[2] + sx, box[3] + sy), radius, fill=color)
        layer.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(blur)))
    draw.rounded_rectangle(box, radius, fill=fill)
    return layer


def draw_pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, outline: str = "#FFFFFF22") -> None:
    x, y = xy
    f = font(25, bold=True)
    bbox = draw.textbbox((0, 0), text, font=f)
    width = bbox[2] - bbox[0] + 42
    draw.rounded_rectangle((x, y, x + width, y + 42), 21, fill=fill, outline=outline, width=1)
    draw.text((x + 21, y + 7), text, font=f, fill="#FFFFFF")


def create_hero() -> None:
    """Generate the README hero as a premium product banner.

    Keep this deterministic and code-native so the project front page can be
    refreshed without relying on a stale AI mockup.
    """

    version = project_version()
    width, height = 1983, 793

    img = Image.new("RGB", (width, height), "#050816")
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            nx = x / width
            ny = y / height
            c1 = (5, 8, 22)
            c2 = (21, 28, 68)
            c3 = (41, 23, 92)
            t = min(1, max(0, nx * 0.58 + ny * 0.42))
            mid = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
            glow = max(0, 1 - ((nx - 0.78) ** 2 / 0.16 + (ny - 0.55) ** 2 / 0.38))
            pixels[x, y] = tuple(min(255, int(mid[i] * (1 - glow * 0.55) + c3[i] * glow * 0.55)) for i in range(3))
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)

    def add_blur_ellipse(box: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int) -> None:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse(box, fill=color)
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))

    add_blur_ellipse((1040, -250, 2100, 760), (37, 99, 235, 72), 90)
    add_blur_ellipse((780, 290, 1900, 1050), (124, 58, 237, 86), 115)
    add_blur_ellipse((-220, 510, 780, 1120), (6, 182, 212, 48), 120)
    add_blur_ellipse((210, -170, 970, 520), (30, 64, 175, 50), 95)

    mesh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    mesh_draw = ImageDraw.Draw(mesh)
    for i in range(-12, 42):
        points = []
        for x in range(0, width + 1, 18):
            y = 470 + math.sin(x / 130 + i * 0.52) * 24 + i * 22 - x * 0.05
            points.append((x, y))
        mesh_draw.line(points, fill=(148, 163, 255, 13), width=1)
    for i in range(9):
        x0 = 1120 + i * 82
        mesh_draw.line((x0, 120, x0 + 260, 705), fill=(255, 255, 255, 10), width=1)
    img.alpha_composite(mesh)

    frame = Image.new("RGBA", img.size, (0, 0, 0, 0))
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle((76, 72, width - 76, height - 72), 56, fill=(255, 255, 255, 14), outline=(255, 255, 255, 34), width=1)
    frame_draw.rounded_rectangle((96, 92, width - 96, height - 92), 44, outline=(255, 255, 255, 12), width=1)
    img.alpha_composite(frame)

    icon_path = ROOT / "gpt2json" / "assets" / "gpt2json_icon_light.png"
    if icon_path.exists():
        icon = Image.open(icon_path).convert("RGBA").resize((112, 112), Image.Resampling.LANCZOS)
        mask = Image.new("L", (112, 112), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 111, 111), 28, fill=255)
        icon.putalpha(mask)
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow.alpha_composite(icon, (144, 132))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
        img.alpha_composite(icon, (144, 132))

    draw.rounded_rectangle((286, 150, 424, 194), 22, fill=(96, 165, 250, 30), outline=(147, 197, 253, 82), width=1)
    draw.text((316, 157), f"v{version}", font=font(24, bold=True), fill="#DCEBFF")
    draw.text((144, 280), "GPT2JSON", font=font(112, bold=True), fill="#FFFFFF")
    draw.text((149, 405), "Sub2API / CPA JSON 导出工具", font=font(43, bold=True), fill="#DBEAFE")
    draw.text((151, 468), "本地生成 · 按号商格式适配 · 中文桌面体验 · 批次隔离", font=font(30), fill="#AFC4EA")

    # Minimal capability row: fine separators instead of heavy badges.
    cap_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cap_draw = ImageDraw.Draw(cap_layer)
    cap_specs = [(151, "Plus7", "#60A5FA"), (286, "本地导出", "#22D3EE"), (452, "Sub2API", "#A78BFA"), (628, "CPA", "#34D399"), (738, "批次隔离", "#93C5FD")]
    for index, (x, label, color) in enumerate(cap_specs):
        cap_draw.ellipse((x, 584, x + 10, 594), fill=color)
        cap_draw.text((x + 19, 574), label, font=font(22, bold=True), fill=(226, 239, 255, 218))
        if index < len(cap_specs) - 1:
            next_x = cap_specs[index + 1][0]
            cap_draw.line((next_x - 24, 578, next_x - 24, 602), fill=(255, 255, 255, 42), width=1)
    img.alpha_composite(cap_layer)

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((1010, 124, 1818, 658), 42, fill=(0, 0, 0, 86))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel)
    panel_draw.rounded_rectangle((990, 104, 1798, 638), 42, fill=(9, 16, 37, 185), outline=(186, 210, 255, 44), width=1)
    panel_draw.rounded_rectangle((1018, 132, 1770, 610), 28, fill=(255, 255, 255, 9), outline=(255, 255, 255, 18), width=1)

    for i, (label, color) in enumerate([("INPUT", "#60A5FA"), ("LOGIN", "#A78BFA"), ("CODE", "#22D3EE"), ("JSON", "#34D399")]):
        y = 170 + i * 88
        panel_draw.rounded_rectangle((1056, y, 1185, y + 42), 20, fill=(255, 255, 255, 13), outline=(255, 255, 255, 20))
        panel_draw.ellipse((1074, y + 13, 1090, y + 29), fill=color)
        panel_draw.text((1102, y + 9), label, font=font(18, bold=True), fill="#DDEAFF")

    for i in range(11):
        y = 170 + i * 31
        x = 1235 + (i % 3) * 12
        line_width = [400, 455, 335, 480, 392][i % 5]
        fill = [(96, 165, 250, 95), (167, 139, 250, 92), (45, 212, 191, 84), (255, 255, 255, 58)][i % 4]
        panel_draw.rounded_rectangle((x, y, x + line_width, y + 9), 5, fill=fill)

    panel_draw.rounded_rectangle((1056, 515, 1728, 574), 22, fill=(37, 99, 235, 44), outline=(96, 165, 250, 90), width=1)
    panel_draw.text((1084, 532), "output/GPT2JSON_20260429_043512_a1b2c3/", font=font(21, bold=True), fill="#EAF2FF")
    panel_draw.rounded_rectangle((1556, 526, 1700, 563), 18, fill=(16, 185, 129, 180))
    panel_draw.text((1584, 533), "READY", font=font(18, bold=True), fill="#FFFFFF")

    reflection = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(reflection).polygon([(1190, 104), (1350, 104), (1110, 638), (950, 638)], fill=(255, 255, 255, 14))
    panel.alpha_composite(reflection)
    img.alpha_composite(panel)

    arcs = Image.new("RGBA", img.size, (0, 0, 0, 0))
    arc_draw = ImageDraw.Draw(arcs)
    for radius, opacity in [(440, 28), (520, 18), (610, 12)]:
        arc_draw.arc((1430 - radius, 374 - radius, 1430 + radius, 374 + radius), 200, 330, fill=(191, 219, 254, opacity), width=2)
    img.alpha_composite(arcs)

    draw.text((146, 681), "Local-first exporter  /  Supplier format adapter  /  Safe masked logs", font=font(21), fill="#7890BA")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(ASSET_DIR / "hero.png", quality=96)

def create_installer_preview() -> None:
    """Preserve the real installer screenshot used by README.

    The installer is a transparent WPF shell, so a faithful preview is captured
    from the running installer and then sanitized to remove the local username
    from the install path.  Do not regenerate it as a synthetic mockup here.
    The only deterministic edit this script applies is the version badge, so
    README screenshots never drift behind the package version.
    """

    preview = ASSET_DIR / "installer-preview.png"
    if preview.exists():
        version = project_version()
        img = Image.open(preview).convert("RGBA")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        # The badge is part of the sanitized real screenshot.  Keep the same
        # geometry proportionally so it survives small future screenshot crops.
        x1 = int(width * 0.162)
        y1 = int(height * 0.787)
        x2 = int(width * 0.217)
        y2 = int(height * 0.822)
        draw.rounded_rectangle((x1, y1, x2, y2), radius=max(10, int(height * 0.017)), fill=(124, 147, 190, 245), outline=(205, 222, 255, 110), width=1)
        text = f"v{version}"
        text_font = font(max(15, int(height * 0.020)), bold=True)
        bbox = draw.textbbox((0, 0), text, font=text_font)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y1 + (y2 - y1 - (bbox[3] - bbox[1])) / 2 - 1), text, font=text_font, fill="#FFFFFF")
        img.convert("RGB").save(preview, quality=96)
        print(f"Preserved real installer screenshot and updated version badge: {preview}")
        return
    raise FileNotFoundError(
        "installer-preview.png is intentionally a sanitized real screenshot. "
        "Build the installer, capture it locally, sanitize the install path, "
        "then save it to docs/assets/installer-preview.png."
    )

def capture_gui_previews() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("GPT2JSON_SETTINGS_PATH", str(Path(tempfile.gettempdir()) / "gpt2json-docs-preview.ini"))

    from PySide6.QtWidgets import QApplication

    from gpt2json.gui import MainWindow, create_app_settings

    app = QApplication.instance() or QApplication([])
    settings = create_app_settings()
    settings.clear()
    settings.sync()

    def render(path: Path, *, dark: bool) -> None:
        window = MainWindow()
        window.resize(1180, 740)
        if dark and window._theme != "dark":
            window.toggle_theme()
        window.output_edit.setText(r"output")
        window.paste_edit.setPlainText(
            "user01@example.test----gpt-password----https://otp.example/latest?mail={email}\n"
            "user02@example.test----gpt-password----https://otp.example/latest?mail={email}\n"
            "user03@example.test----gpt-password----https://otp.example/latest?mail={email}"
        )
        window._reset_counts(20)
        window._done = 13
        window._success = 11
        window._failure = 2
        window._running = 4
        window.total_stat.set_value(20)
        window.success_stat.set_value(11)
        window.failed_stat.set_value(2)
        window.running_stat.set_value(4)
        window._update_progress()
        window.sub2api_row.set_path(r"output\GPT2JSON_20260429_043512_a1b2c3\sub2api_accounts.secret.json")
        window.cpa_row.set_path(r"output\GPT2JSON_20260429_043512_a1b2c3\CPA_20260429_043512_a1b2c3")
        window._refresh_output_format_state()
        window.log_edit.setPlainText(
            "🚀 开始导出：配置已确认，正在生成导入 JSON。\n"
            "📁 输出根目录：output（本次会自动新建唯一批次目录，不覆盖旧文件）\n"
            "🗂️ 本次结果目录：output\\GPT2JSON_20260429_043512_a1b2c3\n"
            "📮 账号 #003 user03@example.test：密码验证通过，服务端要求邮箱验证码，准备访问取码源。\n"
            "✅ 成功：账号 #011 user11@example.test 已获取 JSON，稍后统一写入导出文件。\n"
            "🔁 自动重试：账号 #012 上次停在「Callback 换 JSON」；原因：请求超时，正在进行第 2/3 次尝试。"
        )
        window.run_btn.setEnabled(True)
        window.show()
        app.processEvents()
        pixmap = window.grab()
        image = pixmap.toImage()
        # QImage save preserves alpha more reliably than manual conversion on Windows.
        tmp = path.with_suffix(".tmp.png")
        image.save(str(tmp))
        rgba = Image.open(tmp).convert("RGBA")
        tmp.unlink(missing_ok=True)
        background = Image.new("RGBA", rgba.size, (15, 23, 42, 255) if dark else (241, 245, 249, 255))
        background.alpha_composite(rgba)
        background.save(path)
        window.close()

    render(ASSET_DIR / "gui-zh-preview.png", dark=False)
    render(ASSET_DIR / "gui-zh-preview-dark.png", dark=True)
    settings.clear()
    settings.sync()


def main() -> None:
    create_hero()
    create_installer_preview()
    capture_gui_previews()
    print(f"Generated docs assets in {ASSET_DIR}")


if __name__ == "__main__":
    main()
