from __future__ import annotations

import hashlib
import re
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AccountRow

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@dataclass(frozen=True)
class InputFormat:
    """A pluggable account-file parser.

    More formats can be added by registering a parser that converts raw lines
    into the canonical AccountRow model. Canonical semantics:
    - row.password / row.gpt_password: GPT/OpenAI login password.
    - row.email_credential_kind + row.email_password/email_token/...:
      mailbox-side auth material, only for formats that include it.
    - row.otp_source: no-login OTP URL or mailbox address/source.
    """

    id: str
    label: str
    parser: Callable[[Iterable[str]], list[AccountRow]]
    description: str = ""
    placeholder: str = ""


@dataclass(frozen=True)
class InputFormatPreset:
    """A visible but not necessarily implemented input-format preset."""

    id: str
    label: str
    description: str = ""
    placeholder: str = ""
    enabled: bool = False


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def secret_hash(value: Any, length: int = 16) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:length]


def mask_email(email: str) -> str:
    text = normalize_email(email)
    if "@" not in text:
        return ""
    local, domain = text.split("@", 1)
    if len(local) <= 2:
        head = local[:1]
    else:
        head = local[:2]
    return f"{head}***@{domain}"


def is_url_source(value: Any) -> bool:
    return bool(HTTP_URL_RE.match(str(value or "").strip()))


def is_email_source(value: Any) -> bool:
    text = str(value or "").strip()
    return not is_url_source(text) and bool(EMAIL_RE.match(normalize_email(text)))


def normalize_otp_source(value: Any) -> str:
    text = str(value or "").strip()
    return text if is_url_source(text) else normalize_email(text)


def mask_source(source: str) -> str:
    text = str(source or "").strip()
    if not text:
        return ""
    if is_url_source(text):
        parsed = urllib.parse.urlparse(text)
        return f"{parsed.netloc or 'url'}#{secret_hash(text, length=10)}"
    if is_email_source(text):
        return mask_email(text)
    return f"source#{secret_hash(text, length=10)}"


def slug_email(email: str) -> str:
    text = normalize_email(email)
    out: list[str] = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch in {"@", ".", "+", "-", "_"}:
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "account"


def decode_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def parse_dash_otp_lines(lines: Iterable[str]) -> list[AccountRow]:
    """Parse: gpt-email----gpt-password----otp-url-or-otp-mailbox.

    Important: the middle field is GPT/OpenAI password, not mailbox password.
    If a future input format carries mailbox credentials, it must use a
    separate parser and set AccountRow.email_credential_kind plus the matching
    field, e.g. email_password, email_token, or email_refresh_token.
    """

    rows: list[AccountRow] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(lines, 1):
        line = str(raw or "").strip()
        if not line or line.startswith("#"):
            continue
        first = line.find("----")
        last = line.rfind("----")
        if first <= 0 or last <= first:
            continue
        login_email = normalize_email(line[:first])
        gpt_password = line[first + 4 : last].strip()
        otp_source = normalize_otp_source(line[last + 4 :])
        if not EMAIL_RE.match(login_email):
            continue
        if not gpt_password:
            continue
        if not (is_url_source(otp_source) or is_email_source(otp_source)):
            continue
        if login_email in seen:
            continue
        seen.add(login_email)
        rows.append(
            AccountRow(
                line_no=line_no,
                login_email=login_email,
                password=gpt_password,
                otp_source=otp_source,
                password_kind="gpt",
                otp_email=otp_source if is_email_source(otp_source) else "",
                source_format="dash_otp",
                raw_line=line,
            )
        )
    return rows


def parse_account_lines(lines: Iterable[str]) -> list[AccountRow]:
    """Backward-compatible alias for the current default account format."""

    return parse_dash_otp_lines(lines)


INPUT_FORMATS: dict[str, InputFormat] = {
    "dash_otp": InputFormat(
        id="dash_otp",
        label="卡网 Plus7 / 三段式 OTP",
        parser=parse_dash_otp_lines,
        description="目前暂时只支持卡网 https://pay.ldxp.cn/shop/plus7 提供的格式；第二段是 GPT/OpenAI 登录密码，后续格式适配敬请期待。",
        placeholder="GPT邮箱----GPT登录密码----免登录取码源\n每行一个账号，粘贴内容优先于文件。",
    ),
}


FUTURE_INPUT_FORMAT_PRESETS: tuple[InputFormatPreset, ...] = (
    InputFormatPreset(
        id="mail_password",
        label="号商邮箱账密格式（待适配）",
        description="按号商实际交付字段适配；包含邮箱账号密码或应用密码时再开放。",
    ),
    InputFormatPreset(
        id="mail_oauth",
        label="号商邮箱令牌格式（待适配）",
        description="按号商实际交付字段适配；包含邮箱 access/refresh token 等令牌时再开放。",
    ),
    InputFormatPreset(
        id="jmap_api",
        label="号商自定义取码格式（待适配）",
        description="按号商实际交付字段适配；包含自定义取码链接、取码令牌或专用取码入口时再开放。",
    ),
    InputFormatPreset(
        id="csv_table",
        label="CSV / 表格批量（即将支持）",
        description="表格列映射导入，适合多来源混合整理后的批量文件。",
    ),
)


def list_input_formats() -> list[InputFormat]:
    return list(INPUT_FORMATS.values())


def list_future_input_format_presets() -> list[InputFormatPreset]:
    return list(FUTURE_INPUT_FORMAT_PRESETS)


def parse_by_format(lines: Iterable[str], *, format_id: str = "auto") -> list[AccountRow]:
    materialized = list(lines)
    selected = str(format_id or "auto").strip().lower()
    if selected == "auto":
        best_rows: list[AccountRow] = []
        for fmt in INPUT_FORMATS.values():
            rows = fmt.parser(materialized)
            if len(rows) > len(best_rows):
                best_rows = rows
        return best_rows
    if selected not in INPUT_FORMATS:
        supported = ", ".join(["auto", *INPUT_FORMATS.keys()])
        raise ValueError(f"unsupported input format: {format_id!r}; supported: {supported}")
    return INPUT_FORMATS[selected].parser(materialized)


def read_account_file(path: str | Path, *, format_id: str = "auto") -> list[AccountRow]:
    file_path = Path(path)
    return parse_by_format(decode_text_file(file_path).splitlines(), format_id=format_id)
