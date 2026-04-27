from __future__ import annotations

import base64
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUTH_CLAIM = "https://api.openai.com/auth"
PROFILE_CLAIM = "https://api.openai.com/profile"
DEFAULT_EXPIRES_IN = 864000


def decode_jwt_payload(token: str) -> dict[str, Any]:
    if not token or token.count(".") < 2:
        return {}
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_expired_time(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return int(datetime.fromisoformat(text).timestamp())
    except Exception:
        return 0


def _auth_claims(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get(AUTH_CLAIM, {})
    return data if isinstance(data, dict) else {}


def _profile_claims(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get(PROFILE_CLAIM, {})
    return data if isinstance(data, dict) else {}


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}, ()):
            return value
    return ""


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _organization_text_blob(org: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("id", "name", "display_name", "title", "slug", "type", "kind", "organization_type", "org_type"):
        value = str(org.get(key) or "").strip()
        if value:
            parts.append(value.lower())
    return " ".join(parts)


def _choose_organization_id(organizations: Any) -> str:
    if not isinstance(organizations, list):
        return ""
    best_id = ""
    best_score = -1
    for index, raw_org in enumerate(organizations):
        if not isinstance(raw_org, dict):
            continue
        org_id = str(raw_org.get("id") or raw_org.get("org_id") or "").strip()
        if not org_id:
            continue
        text_blob = _organization_text_blob(raw_org)
        personal_hint = any(
            _truthy_flag(raw_org.get(key))
            for key in ("is_personal", "personal", "is_personal_workspace", "personal_workspace")
        ) or any(token in text_blob for token in ("personal", "individual", "private"))
        default_hint = any(_truthy_flag(raw_org.get(key)) for key in ("is_default", "default", "selected", "is_selected"))
        score = max(0, 10 - index)
        if personal_hint:
            score += 300
        if default_hint:
            score += 100
        if score > best_score:
            best_score = score
            best_id = org_id
    return best_id


def _default_name(index: int, token_type: str) -> str:
    return f"{token_type or 'unknown'}-普号-{index:04d}"


def convert_current_token_to_sub(source_data: dict[str, Any], index: int = 1) -> dict[str, Any]:
    access_payload = decode_jwt_payload(str(source_data.get("access_token") or ""))
    access_auth = _auth_claims(access_payload)
    access_profile = _profile_claims(access_payload)
    id_payload = decode_jwt_payload(str(source_data.get("id_token") or ""))
    id_auth = _auth_claims(id_payload)

    organizations = _first_non_empty(id_auth.get("organizations"), access_auth.get("organizations"), [])
    organization_id = str(_first_non_empty(source_data.get("organization_id"), _choose_organization_id(organizations)) or "")
    expires_at = parse_expired_time(source_data.get("expired")) or int(access_payload.get("exp") or 0)
    issued_at = int(access_payload.get("iat") or 0)
    expires_in = max(expires_at - issued_at, 0) if expires_at and issued_at else DEFAULT_EXPIRES_IN
    token_type = str(_first_non_empty(source_data.get("type"), access_auth.get("chatgpt_plan_type"), "unknown"))
    account_email = str(_first_non_empty(source_data.get("email"), access_profile.get("email"), id_payload.get("email")))

    return {
        "name": account_email or _default_name(index, token_type),
        "platform": "openai",
        "type": "oauth",
        "credentials": {
            "access_token": str(source_data.get("access_token") or ""),
            "chatgpt_account_id": str(_first_non_empty(source_data.get("account_id"), access_auth.get("chatgpt_account_id"))),
            "chatgpt_user_id": str(
                _first_non_empty(
                    access_auth.get("chatgpt_user_id"),
                    access_auth.get("user_id"),
                    access_payload.get("sub"),
                    id_payload.get("sub"),
                )
            ),
            "expires_at": expires_at,
            "expires_in": expires_in,
            "organization_id": organization_id,
            "refresh_token": str(source_data.get("refresh_token") or ""),
        },
        "extra": {
            "email": account_email,
            "sub": str(_first_non_empty(access_payload.get("sub"), id_payload.get("sub"))),
        },
        "concurrency": 10,
        "priority": 1,
        "rate_multiplier": 1,
        "auto_pause_on_expired": True,
    }


def normalize_sub_account(account: dict[str, Any], index: int | None = None) -> dict[str, Any]:
    normalized = copy.deepcopy(account)
    normalized.setdefault("platform", "openai")
    normalized.setdefault("type", "oauth")
    normalized.setdefault("concurrency", 10)
    normalized.setdefault("priority", 1)
    normalized.setdefault("rate_multiplier", 1)
    normalized.setdefault("auto_pause_on_expired", True)
    credentials = normalized.setdefault("credentials", {})
    extra = normalized.setdefault("extra", {})
    access_payload = decode_jwt_payload(str(credentials.get("access_token") or ""))
    auth_info = _auth_claims(access_payload)
    profile_info = _profile_claims(access_payload)
    expires_at = parse_expired_time(credentials.get("expires_at")) or int(access_payload.get("exp") or 0)
    credentials.setdefault("access_token", "")
    credentials.setdefault("refresh_token", "")
    credentials.setdefault("chatgpt_account_id", _first_non_empty(auth_info.get("chatgpt_account_id")))
    credentials.setdefault("chatgpt_user_id", _first_non_empty(auth_info.get("chatgpt_user_id"), auth_info.get("user_id"), access_payload.get("sub")))
    credentials.setdefault("organization_id", "")
    credentials.setdefault("expires_at", expires_at)
    credentials.setdefault("expires_in", DEFAULT_EXPIRES_IN if expires_at else 0)
    extra.setdefault("email", _first_non_empty(profile_info.get("email"), access_payload.get("email")))
    extra.setdefault("sub", _first_non_empty(access_payload.get("sub")))
    normalized.setdefault("name", str(extra.get("email") or _default_name(index or 1, "openai")))
    return normalized


def build_export(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "sub2api-data",
        "version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "proxies": [],
        "accounts": accounts,
    }


def write_json(path: str | Path, payload: Any, *, indent: int = 2) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")

