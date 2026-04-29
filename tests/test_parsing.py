import pytest

from gpt2json.parsing import list_future_input_format_presets, list_input_formats, parse_account_lines, parse_by_format


def test_parse_account_lines_dedupes_and_normalizes():
    rows = parse_account_lines(
        [
            "User@Example.com----pass123----https://otp.local/a",
            "user@example.com----pass456----https://otp.local/b",
            "bad line",
        ]
    )
    assert len(rows) == 1
    assert rows[0].login_email == "user@example.com"
    assert rows[0].password == "pass123"
    assert rows[0].gpt_password == "pass123"
    assert rows[0].password_kind == "gpt"
    assert rows[0].email_credential_kind == ""
    assert rows[0].email_password == ""
    assert rows[0].email_token == ""
    assert rows[0].email_refresh_token == ""
    assert not rows[0].has_email_credential
    assert rows[0].source_format == "dash_otp"


def test_input_format_registry_supports_auto_and_errors():
    dash_format = next(fmt for fmt in list_input_formats() if fmt.id == "dash_otp")
    assert "号商格式 A" in dash_format.label
    assert "免登录接码" in dash_format.label
    assert "pay.ldxp.cn/shop/plus7" in dash_format.description
    assert dash_format.placeholder
    future_presets = list_future_input_format_presets()
    assert future_presets
    assert all(not preset.enabled for preset in future_presets)
    rows = parse_by_format(["user@example.com----pass----https://mail.local/code"], format_id="auto")
    assert len(rows) == 1
    with pytest.raises(ValueError):
        parse_by_format([], format_id="missing")

