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
    version = project_version()
    width, height = 1983, 793
    img = vertical_gradient((width, height), (9, 16, 38), (51, 35, 116)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Soft aurora blobs.
    for cx, cy, r, color in [
        (1740, 130, 390, (59, 130, 246, 90)),
        (1390, 650, 460, (124, 58, 237, 110)),
        (520, 710, 360, (20, 184, 166, 70)),
    ]:
        blob = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(blob).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        img.alpha_composite(blob.filter(ImageFilter.GaussianBlur(80)))

    # Fine grid.
    grid = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    for x in range(0, width, 56):
        g.line((x, 0, x, height), fill=(255, 255, 255, 12), width=1)
    for y in range(0, height, 56):
        g.line((0, y, width, y), fill=(255, 255, 255, 10), width=1)
    img.alpha_composite(grid)

    # Logo chip.
    icon_path = ROOT / "gpt2json" / "assets" / "gpt2json_icon_light.png"
    if icon_path.exists():
        icon = Image.open(icon_path).convert("RGBA").resize((92, 92), Image.Resampling.LANCZOS)
        mask = Image.new("L", (92, 92), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 92, 92), 24, fill=255)
        icon.putalpha(mask)
        img.alpha_composite(icon, (142, 126))
    draw.rounded_rectangle((260, 137, 510, 207), 35, fill=(255, 255, 255, 18), outline=(255, 255, 255, 45), width=1)
    draw.text((290, 151), f"v{version} ready", font=font(30, bold=True), fill="#DDEBFF")

    draw.text((142, 250), "GPT2JSON", font=font(108, bold=True), fill="#FFFFFF")
    draw.text((146, 378), "Sub2API / CPA JSON 导出工具", font=font(46, bold=True), fill="#DBEAFE")
    draw.text((148, 444), "协议优先 · 中文桌面体验 · 每次导出唯一批次目录", font=font(32), fill="#B7C7E8")

    x = 148
    for label, color in [
        ("粘贴 / 文件输入", "#2563EB"),
        ("自动并发", "#7C3AED"),
        ("OTP 免登录取码", "#0891B2"),
        ("Sub2API + CPA", "#059669"),
    ]:
        draw_pill(draw, (x, 548), label, color)
        x += draw.textbbox((0, 0), label, font=font(25, bold=True))[2] + 78

    # Right product cards.
    card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)
    cards = [
        ((1110, 140, 1760, 310), "#FFFFFF", "输入", "GPT邮箱----GPT密码----OTP取码源", "#2563EB"),
        ((1030, 350, 1835, 530), "#F8FAFC", "处理", "OAuth → 按需取码 → Callback 换 JSON", "#7C3AED"),
        ((1160, 570, 1785, 705), "#FFFFFF", "输出", "GPT2JSON_时间戳_编码 / JSON", "#059669"),
    ]
    for box, fill, title, body, accent in cards:
        card_layer.alpha_composite(rounded_rect_layer((width, height), box, 36, fill, shadow=(0, 18, 40, (0, 0, 0, 70))))
        cd.rounded_rectangle((box[0] + 34, box[1] + 34, box[0] + 98, box[1] + 98), 18, fill=accent)
        cd.text((box[0] + 124, box[1] + 34), title, font=font(34, bold=True), fill="#0F172A")
        cd.text((box[0] + 124, box[1] + 84), body, font=font(26), fill="#475569")
        for i in range(3):
            y = box[1] + 120 + i * 18
            cd.rounded_rectangle((box[0] + 124, y, box[2] - 52 - i * 34, y + 8), 4, fill=(148, 163, 184, 95))
    card_layer = card_layer.rotate(-4, resample=Image.Resampling.BICUBIC, center=(1450, 420))
    img.alpha_composite(card_layer)

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(ASSET_DIR / "hero.png", quality=95)


def create_installer_preview() -> None:
    version = project_version()
    width, height = 1400, 840
    img = vertical_gradient((width, height), (239, 246, 255), (245, 243, 255)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Floating organic shell.
    shell = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shell)
    sd.rounded_rectangle((108, 92, 1292, 748), 58, fill="#FFFFFF")
    sd.ellipse((34, 190, 290, 550), fill="#FFFFFF")
    sd.ellipse((1120, 122, 1350, 410), fill="#FFFFFF")
    shell = shell.filter(ImageFilter.GaussianBlur(0.2))
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((128, 118, 1282, 768), 58, fill=(30, 41, 59, 55))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(34)))
    img.alpha_composite(shell)

    # Left curved visual panel.
    left = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ld = ImageDraw.Draw(left)
    ld.rounded_rectangle((100, 92, 602, 748), 58, fill="#0B1026")
    ld.ellipse((430, 230, 790, 610), fill=(255, 255, 255, 0))
    for i in range(5):
        pts = []
        for t in range(0, 220):
            y = 690 - t * 2.6
            x = 190 + i * 54 + math.sin(t / 24 + i) * 44 + t * 1.1
            pts.append((x, y))
        ld.line(pts, fill=(96, 165, 250, 70 + i * 18), width=6)
    ld.ellipse((268, 250, 458, 440), outline=(255, 255, 255, 70), width=2)
    ld.rounded_rectangle((258, 280, 468, 470), 42, fill=(37, 99, 235, 210))
    ld.text((318, 318), "GJ", font=font(62, bold=True), fill="#FFFFFF")
    ld.text((174, 560), "GPT2JSON", font=font(48, bold=True), fill="#FFFFFF")
    ld.text((176, 620), "协议优先 · 本地导出 · 中文体验", font=font(24), fill="#CBD5E1")
    img.alpha_composite(left)

    # Elliptic cut-out visual cue.
    cut = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(cut).ellipse((500, 330, 700, 520), fill=(239, 246, 255, 255))
    img.alpha_composite(cut.filter(ImageFilter.GaussianBlur(0.3)))
    draw.ellipse((514, 344, 686, 506), outline="#D8B4FE", width=3)

    # Right install content.
    draw.text((730, 150), "安装", font=font(64, bold=True), fill="#111827")
    draw.rounded_rectangle((844, 164, 964, 204), 20, fill="#EEF2FF")
    draw.text((872, 170), f"v{version}", font=font(22, bold=True), fill="#4F46E5")
    draw.text((732, 232), "选择安装位置后会自动创建 GPT2JSON 文件夹。", font=font(28), fill="#64748B")

    draw.text((732, 310), "安装位置", font=font(24, bold=True), fill="#334155")
    draw.rounded_rectangle((732, 348, 1168, 410), 18, fill="#F8FAFC", outline="#E2E8F0", width=2)
    draw.text((758, 365), r"C:\Users\...\Programs\GPT2JSON", font=font(23), fill="#475569")
    draw.rounded_rectangle((1186, 348, 1260, 410), 18, fill="#EEF2FF")
    draw.text((1208, 365), "浏览", font=font(22, bold=True), fill="#4F46E5")

    draw.text((732, 470), "安装进度", font=font(24, bold=True), fill="#334155")
    draw.rounded_rectangle((732, 510, 1260, 528), 9, fill="#E2E8F0")
    draw.rounded_rectangle((732, 510, 1118, 528), 9, fill="#2563EB")
    draw.ellipse((1108, 501, 1138, 537), fill="#60A5FA")

    for x, text, fill, fg in [
        (732, "开始", "#2563EB", "#FFFFFF"),
        (900, "取消", "#F1F5F9", "#334155"),
    ]:
        draw.rounded_rectangle((x, 610, x + 132, 666), 20, fill=fill, outline="#E2E8F0")
        draw.text((x + 42, 624), text, font=font(24, bold=True), fill=fg)
    draw.text((732, 700), "不会写入 GUI 偏好到注册表；卸载入口使用同风格外壳。", font=font(23), fill="#64748B")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(ASSET_DIR / "installer-preview.png", quality=95)


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
        window.cpa_row.set_path(r"output\GPT2JSON_20260429_043512_a1b2c3\cpa_tokens_20260429_043512_a1b2c3.zip")
        window._refresh_output_format_state()
        window.log_edit.setPlainText(
            "🚀 开始导出：配置已确认，正在按协议获取 JSON。\n"
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
