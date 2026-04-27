from gpt2json.mail_providers import (
    CRED_REFRESH_TOKEN,
    detect_mail_provider,
    mailbox_context_from_row,
    provider_plan_for_row,
)
from gpt2json.models import AccountRow


def test_detect_common_mail_providers():
    assert detect_mail_provider("demo@outlook.com").id == "microsoft"
    assert detect_mail_provider("demo@hotmail.com").id == "microsoft"
    assert detect_mail_provider("demo@gmail.com").id == "gmail"
    assert detect_mail_provider("demo@fastmail.com").id == "fastmail"
    assert detect_mail_provider("demo@icloud.com").id == "icloud"
    assert detect_mail_provider("demo@qq.com").id == "qq"
    assert detect_mail_provider("demo@163.com").id == "netease"
    assert detect_mail_provider("demo@luckmail.com").id == "luckmail"
    assert detect_mail_provider("demo@custom-luckmail.local").id == "luckmail"
    assert detect_mail_provider("demo@example.invalid").id == "generic_imap"


def test_mailbox_context_keeps_token_separate_from_gpt_password():
    row = AccountRow(
        line_no=1,
        login_email="gpt@example.com",
        password="gpt-password",
        otp_source="mail@hotmail.com",
        otp_email="mail@hotmail.com",
        email_credential_kind="refresh_token",
        email_refresh_token="mail-refresh-token",
    )
    context = mailbox_context_from_row(row)
    assert context is not None
    assert context.provider.id == "microsoft"
    assert context.credential_kind == CRED_REFRESH_TOKEN
    assert context.refresh_token == "mail-refresh-token"
    assert row.gpt_password == "gpt-password"

    plan = provider_plan_for_row(row)
    assert plan["provider"] == "microsoft"
    assert plan["credential_supported"] is True
    assert "graph" in plan["planned_backends"]


def test_provider_plan_keeps_no_login_url_as_http_backend():
    row = AccountRow(
        line_no=1,
        login_email="gpt@example.com",
        password="gpt-password",
        otp_source="https://otp.local/latest",
    )
    plan = provider_plan_for_row(row)
    assert plan["provider"] == "no_login_url"
    assert plan["credential_supported"] is True
    assert plan["planned_backends"] == ["http_url"]

