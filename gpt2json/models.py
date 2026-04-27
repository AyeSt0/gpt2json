from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class AccountRow:
    line_no: int
    login_email: str
    # Compatibility name kept as `password`; semantically this is always the
    # GPT/OpenAI account password used for auth.openai.com password verification.
    password: str
    otp_source: str
    password_kind: str = "gpt"
    # Mailbox-side credentials are optional and deliberately separate from the
    # GPT/OpenAI password. Future input adapters can set one of these depending
    # on source format: password/app-password/token/refresh-token/cookie/etc.
    email_credential_kind: str = ""
    email_password: str = ""
    email_token: str = ""
    email_refresh_token: str = ""
    email_client_id: str = ""
    email_extra: dict[str, str] = field(default_factory=dict, compare=False)
    otp_email: str = ""
    source_format: str = ""

    @property
    def gpt_password(self) -> str:
        return self.password

    @property
    def has_email_password(self) -> bool:
        return bool(self.email_password)

    @property
    def has_email_token(self) -> bool:
        return bool(self.email_token or self.email_refresh_token)

    @property
    def has_email_credential(self) -> bool:
        return bool(self.email_password or self.email_token or self.email_refresh_token or self.email_extra)


@dataclass
class AttemptResult:
    row: AccountRow
    status: str
    stage: str = ""
    token_json: str = ""
    reason: str = ""
    otp_required: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str = field(default_factory=utc_now_iso)

    @property
    def ok(self) -> bool:
        return self.status == "success" and bool(self.token_json)
