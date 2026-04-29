from gpt2json.formats import (
    build_cpa_token_json,
    build_export,
    convert_current_token_to_sub,
    validate_cpa_token_json,
    validate_sub2api_export,
)


def test_convert_current_token_to_sub_maps_email_and_ids():
    token = {
        "access_token": "header.payload.sig",
        "refresh_token": "refresh",
        "account_id": "acc-1",
        "email": "demo@example.com",
        "type": "plus",
        "expired": "2026-04-27T00:00:00Z",
    }
    account = convert_current_token_to_sub(token, index=1)
    assert account["name"] == "demo@example.com"
    assert account["extra"] == {}
    assert account["credentials"]["chatgpt_account_id"] == "acc-1"
    assert account["credentials"]["client_id"]
    assert account["credentials"]["expires_in"] == 863999
    assert "gpt-5.4" in account["credentials"]["model_mapping"]
    export = build_export([account])
    assert set(export) == {"proxies", "accounts"}
    assert len(export["accounts"]) == 1


def test_build_cpa_token_json_matches_codex_console_shape():
    token = {
        "access_token": "access",
        "refresh_token": "refresh",
        "id_token": "id",
        "account_id": "acc-1",
        "email": "demo@example.com",
        "type": "plus",
        "last_refresh": "2026-04-27T00:00:00Z",
        "expired": "2026-04-27T01:00:00Z",
    }
    payload = build_cpa_token_json(token)
    assert list(payload) == ["type", "email", "expired", "id_token", "account_id", "access_token", "last_refresh", "refresh_token"]
    assert payload["type"] == "codex"
    assert payload["email"] == "demo@example.com"
    assert payload["expired"] == "2026-04-27T09:00:00+08:00"
    assert payload["last_refresh"] == "2026-04-27T08:00:00+08:00"


def test_validate_sub2api_export_marks_importable():
    token = {
        "access_token": "access",
        "refresh_token": "refresh",
        "account_id": "acc-1",
        "email": "demo@example.com",
        "expired": "2026-04-27T01:00:00Z",
    }
    payload = build_export([convert_current_token_to_sub(token, index=1)])

    result = validate_sub2api_export(payload)

    assert result["ok"] is True
    assert result["status"] == "可导入"
    assert result["count"] == 1
    assert result["issue_count"] == 0


def test_validate_sub2api_export_marks_missing_credentials_not_recommended():
    payload = build_export([convert_current_token_to_sub({"email": "demo@example.com"}, index=1)])

    result = validate_sub2api_export(payload)

    assert result["ok"] is False
    assert result["status"] == "不建议导入"
    assert result["issue_count"] >= 1
    assert any("credentials.access_token" in item for item in result["errors"])


def test_validate_cpa_token_json_marks_importable():
    payload = build_cpa_token_json(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "email": "demo@example.com",
            "expired": "2026-04-27T01:00:00Z",
        }
    )

    result = validate_cpa_token_json(payload)

    assert result["ok"] is True
    assert result["status"] == "可导入"
    assert result["issue_count"] == 0


def test_validate_cpa_token_json_marks_missing_refresh_token_not_recommended():
    payload = build_cpa_token_json(
        {
            "access_token": "access",
            "email": "demo@example.com",
            "expired": "2026-04-27T01:00:00Z",
        }
    )

    result = validate_cpa_token_json(payload)

    assert result["ok"] is False
    assert result["status"] == "不建议导入"
    assert any("refresh_token" in item for item in result["errors"])

