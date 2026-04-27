from gpt2json.formats import build_cpa_token_json, build_export, convert_current_token_to_sub


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


