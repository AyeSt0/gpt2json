from gpt2json.formats import build_export, convert_current_token_to_sub


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
    assert account["extra"]["email"] == "demo@example.com"
    assert account["credentials"]["chatgpt_account_id"] == "acc-1"
    export = build_export([account])
    assert export["type"] == "sub2api-data"
    assert len(export["accounts"]) == 1


