from __future__ import annotations

# Source-only ownership marker.  It is intentionally not rendered in the GUI or
# exported JSON; it simply keeps the project signature close to the UI log rules.
_AYEST0_MARK = "AyeSt0"
_AYEST0_HOME = "https://github.com/AyeSt0"

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
    if line.startswith(("⚠️", "💥", "🚫")) or line.startswith(("失败：", "主流程异常：")):
        return "error"
    if line.startswith("🛑") or line.startswith("取消"):
        return "cancel"
    if line.startswith(("🔁", "⚡", "🔄 自动重跑补救", "🔄 批次级自动补跑", "🔄 重跑失败账号", "🟡")):
        return "warning"
    if line.startswith(("🚀", "🧩", "📦 任务")) or line.startswith(("开始导出：", "运行配置：")):
        return "start"
    if line.startswith(("👤", "🚪", "🛡️", "📨", "🔑", "🎫", "📦")):
        return "account"
    if line.startswith(("🧭", "🔎", "🔍", "🧪", "🔄", "ℹ️", "✨", "👀", "🟢", "📄", "🧮", "⏱️")):
        return "info"
    if line.startswith(("🧾 失败诊断报告", "🧾 诊断目录")):
        return "output"
    if line.startswith(("📮", "📫", "📬", "🧾", "⌛")) or "验证码" in line:
        return "otp"
    if line.startswith(("📁", "🗂️", "🧰", "📘", "📚")) or "输出：" in line or "输出目录：" in line or "输出根目录：" in line:
        return "output"
    return "default"


__all__ = ["DARK_LOG_COLORS", "LIGHT_LOG_COLORS", "classify_log_line"]
