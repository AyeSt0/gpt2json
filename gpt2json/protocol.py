from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
from collections.abc import Callable
from typing import Any

from curl_cffi import requests

from .models import AccountRow, AttemptResult, utc_now_iso
from .oauth import OAuthStart, decode_jwt_segment, generate_oauth_url, submit_callback_url
from .otp import OtpFetcher
from .parsing import mask_email, mask_source

PAGE_TYPE_HINTS = (
    ("/sign-in-with-chatgpt/codex/consent", "sign_in_with_chatgpt_codex_consent"),
    ("/email-verification", "email_otp_verification"),
    ("/api/accounts/email-otp/send", "email_otp_send"),
    ("/api/accounts/email-otp/validate", "email_otp_validate"),
    ("/add-phone", "add_phone"),
    ("/about-you", "about_you"),
    ("/log-in/password", "login_password"),
    ("/log-in", "login"),
)

DEFAULT_IMPERSONATE = "chrome136"

AUTH_NAV_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-site",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

AUTH_JSON_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "content-type": "application/json",
    "origin": "https://auth.openai.com",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


def _headers(base: dict[str, str], **overrides: Any) -> dict[str, str]:
    merged = dict(base)
    for key, value in overrides.items():
        text = str(value or "").strip()
        if text:
            merged[key.replace("_", "-")] = text
    return merged


def _response_json_or_empty(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_absolute_url(base_url: str, candidate_url: Any) -> str:
    text = str(candidate_url or "").strip()
    if not text:
        return ""
    return urllib.parse.urljoin(base_url, text) if text.startswith("/") else text


def _extract_continue_url_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("continue_url", "continueUrl", "next_url", "nextUrl", "redirect_url", "redirectUrl"):
        candidate = str(payload.get(key) or "").strip()
        if candidate:
            return candidate
    return ""


def _extract_page_type_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    page = payload.get("page") or {}
    return str(page.get("type") or "").strip() if isinstance(page, dict) else ""


def _extract_response_error_code(payload: Any, raw_text: str = "") -> str:
    if isinstance(payload, dict):
        error = payload.get("error") or {}
        if isinstance(error, dict):
            code = str(error.get("code") or "").strip()
            if code:
                return code
        code = str(payload.get("code") or payload.get("error_code") or "").strip()
        if code:
            return code
    lowered = str(raw_text or "").lower()
    if "invalid_auth_step" in lowered:
        return "invalid_auth_step"
    if "bad_request" in lowered:
        return "bad_request"
    return ""


def _decode_error_payload_from_location(location_url: Any) -> dict[str, Any]:
    text = str(location_url or "").strip()
    if not text:
        return {}
    try:
        parsed = urllib.parse.urlparse(text)
        params = urllib.parse.parse_qs(parsed.query or "")
        raw_payload = str((params.get("payload") or [""])[0] or "").strip()
        if not raw_payload:
            return {}
        padded = raw_payload + "=" * (-len(raw_payload) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="ignore"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _extract_auth_continue_url_from_text(raw_text: str) -> str:
    text = str(raw_text or "").replace("\\/", "/")
    if not text:
        return ""
    match = re.search(r'"continue_url"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1).replace("\\/", "/")
    match = re.search(r"https://auth\.openai\.com/[^\s\"'<>]+", text, re.IGNORECASE)
    if match:
        return match.group(0)
    path_match = re.search(
        r'/(?:sign-in-with-chatgpt/codex/consent|email-verification|about-you|add-phone|log-in(?:/password)?)',
        text,
        re.IGNORECASE,
    )
    if path_match:
        return urllib.parse.urljoin("https://auth.openai.com", path_match.group(0))
    return ""


def _extract_page_type_from_text(raw_text: str) -> str:
    text = str(raw_text or "").replace("\\/", "/")
    if not text:
        return ""
    for pattern in (
        r'"page"\s*:\s*\{[^{}]*"type"\s*:\s*"([A-Za-z0-9_./:-]+)"',
        r'"page_type"\s*:\s*"([A-Za-z0-9_./:-]+)"',
        r'"pageType"\s*:\s*"([A-Za-z0-9_./:-]+)"',
        r'"type"\s*:\s*"([A-Za-z0-9_./:-]+)"',
    ):
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _infer_page_type_from_url(candidate_url: Any) -> str:
    text = str(candidate_url or "").strip()
    if not text:
        return ""
    try:
        path = urllib.parse.urlsplit(text).path or text
    except Exception:
        path = text
    lowered = str(path or "").strip().lower().rstrip("/")
    for suffix, page_type in PAGE_TYPE_HINTS:
        if lowered.endswith(suffix):
            return page_type
    return ""


def _extract_callback_url_from_payload(payload: Any, raw_text: str = "") -> str:
    candidates: list[str] = []
    if isinstance(payload, dict):
        for key in ("callback_url", "callbackUrl", "redirect_url", "redirectUrl", "continue_url", "continueUrl", "url"):
            candidate = str(payload.get(key) or "").strip()
            if candidate:
                candidates.append(candidate)
    for candidate in candidates:
        lowered = candidate.lower()
        if "code=" in lowered and "state=" in lowered:
            return candidate
    match = re.search(r"https://[^\s\"']+[?&]code=[^&\s\"']+[^\s\"']*state=[^\s\"']+", str(raw_text or ""))
    return str(match.group(0) or "").strip() if match else ""


def _extract_transition_targets(*, payload: Any, raw_text: Any, request_url: str, location_url: Any = "") -> dict[str, Any]:
    payload_dict = payload if isinstance(payload, dict) else {}
    response_text = str(raw_text or "")
    normalized_location_url = _normalize_absolute_url(request_url, location_url)
    location_error = _decode_error_payload_from_location(normalized_location_url)
    error_code = _extract_response_error_code(payload_dict, response_text)
    if not error_code and isinstance(location_error, dict):
        error_code = str(location_error.get("errorCode") or location_error.get("error_code") or "").strip()
    callback_url = _extract_callback_url_from_payload(payload_dict, response_text)
    if not callback_url and normalized_location_url and "code=" in normalized_location_url and "state=" in normalized_location_url:
        callback_url = normalized_location_url
    continue_url = _extract_continue_url_from_payload(payload_dict) or _extract_auth_continue_url_from_text(response_text)
    if not continue_url and normalized_location_url and not error_code:
        lowered = normalized_location_url.lower()
        if any(marker in lowered for marker in ("consent_challenge=", "/api/oauth/oauth2/auth", "/api/accounts/consent", "/sign-in-with-chatgpt/")):
            continue_url = normalized_location_url
    page_type = (
        _extract_page_type_from_payload(payload_dict)
        or _extract_page_type_from_text(response_text)
        or _infer_page_type_from_url(continue_url)
        or _infer_page_type_from_url(normalized_location_url)
        or _infer_page_type_from_url(request_url)
    )
    return {
        "status_code": 0,
        "payload": payload_dict,
        "raw_text": response_text,
        "location_url": normalized_location_url,
        "continue_url": continue_url,
        "page_type": page_type,
        "callback_url": callback_url,
        "error_code": error_code,
    }


def _extract_transition_targets_from_response(response: Any, *, request_url: str) -> dict[str, Any]:
    raw_text = str(getattr(response, "text", "") or "")
    payload = _response_json_or_empty(response)
    headers = getattr(response, "headers", {}) or {}
    transition = _extract_transition_targets(
        payload=payload,
        raw_text=raw_text,
        request_url=request_url,
        location_url=headers.get("Location") or headers.get("location") or "",
    )
    transition["status_code"] = int(getattr(response, "status_code", 0) or 0)
    return transition


def _get_preferred_session_cookie_value(session: requests.Session, cookie_name: str, *, preferred_domains: tuple[str, ...] = ()) -> str:
    cookie_key = str(cookie_name or "").strip()
    if not cookie_key:
        return ""
    seen_values: set[str] = set()

    def _normalize(value: Any) -> str:
        text = str(value or "").strip()
        if not text or text in seen_values:
            return ""
        seen_values.add(text)
        return text

    for domain in preferred_domains:
        try:
            normalized = _normalize(session.cookies.get(cookie_key, domain=domain))
        except Exception:
            normalized = ""
        if normalized:
            return normalized
    try:
        normalized = _normalize(session.cookies.get(cookie_key))
    except Exception:
        normalized = ""
    if normalized:
        return normalized
    try:
        for item in session.cookies:
            if str(getattr(item, "name", "") or "").strip() != cookie_key:
                continue
            normalized = _normalize(getattr(item, "value", ""))
            if normalized:
                return normalized
    except Exception:
        pass
    return ""


def _get_cookie_values(session: requests.Session, cookie_name: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    def push(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)

    for domain in (".auth.openai.com", "auth.openai.com", ".openai.com", "openai.com"):
        try:
            push(session.cookies.get(cookie_name, domain=domain))
        except Exception:
            continue
    try:
        push(session.cookies.get(cookie_name))
    except Exception:
        pass
    try:
        for item in session.cookies:
            if str(getattr(item, "name", "") or "").strip() == cookie_name:
                push(getattr(item, "value", ""))
    except Exception:
        pass
    return values


def _extract_workspace_info_from_auth_cookie(cookie_value: str) -> tuple[str, int]:
    raw = str(cookie_value or "").strip()
    if not raw:
        return "", 0
    try:
        decoded = urllib.parse.unquote(raw)
        if decoded != raw:
            raw = decoded
    except Exception:
        pass
    auth_json: dict[str, Any] = {}
    for part in raw.split("."):
        payload = decode_jwt_segment(part)
        if isinstance(payload, dict) and "workspaces" in payload:
            auth_json = payload
            break
    workspaces = auth_json.get("workspaces") or []
    if not isinstance(workspaces, list):
        return "", 0
    if not workspaces:
        return "", 0
    return str((workspaces[0] or {}).get("id") or "").strip(), len(workspaces)


def _extract_workspace_id_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("client_auth_session", "session", "data", "result", "payload"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            nested_id = _extract_workspace_id_from_payload(nested)
            if nested_id:
                return nested_id
    workspace_id = str(
        payload.get("workspace_id")
        or payload.get("workspaceId")
        or payload.get("default_workspace_id")
        or ((payload.get("workspace") or {}).get("id") if isinstance(payload.get("workspace"), dict) else "")
        or ""
    ).strip()
    if workspace_id:
        return workspace_id
    workspaces = payload.get("workspaces") or []
    if isinstance(workspaces, list) and workspaces:
        return str((workspaces[0] or {}).get("id") or "").strip()
    return ""


def _extract_workspaces_count_from_payload(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    for key in ("client_auth_session", "session", "data", "result", "payload"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            nested_count = _extract_workspaces_count_from_payload(nested)
            if nested_count:
                return nested_count
    workspaces = payload.get("workspaces") or []
    return len(workspaces) if isinstance(workspaces, list) else 0


def _probe_client_auth_session_dump(session: requests.Session, *, client: ProtocolLoginClient, proxies: Any) -> dict[str, Any]:
    auth_session_values = _get_cookie_values(session, "oai-client-auth-session")
    minimized_values = _get_cookie_values(session, "auth-session-minimized")
    checksum_values = _get_cookie_values(session, "auth-session-minimized-client-checksum")
    probe = {
        "attempted": False,
        "ok": False,
        "status_code": 0,
        "workspace_id": "",
        "workspaces_count": 0,
        "session_id": "",
        "checksum_present": bool(checksum_values),
        "auth_session_present": bool(auth_session_values),
        "minimized_session_present": bool(minimized_values),
        "error_code": "",
        "error": "",
        "workspaces_present": False,
        "payload": {},
    }
    if not (probe["auth_session_present"] or probe["minimized_session_present"] or probe["checksum_present"]):
        return probe
    probe["attempted"] = True
    try:
        resp = client._request(
            session,
            "GET",
            "https://auth.openai.com/api/accounts/client_auth_session_dump",
            proxies=proxies,
            headers={
                "accept": "application/json",
                "referer": "https://auth.openai.com/log-in",
                "origin": "https://auth.openai.com",
                "cache-control": "no-cache",
                "pragma": "no-cache",
            },
            allow_redirects=True,
            timeout=20,
        )
        probe["status_code"] = int(getattr(resp, "status_code", 0) or 0)
        payload = _response_json_or_empty(resp)
        probe["payload"] = payload if isinstance(payload, dict) else {}
        error_payload = probe["payload"].get("error") or {}
        if isinstance(error_payload, dict):
            probe["error_code"] = str(error_payload.get("code") or "").strip()
        client_auth_session = probe["payload"].get("client_auth_session") or {}
        if isinstance(client_auth_session, dict):
            probe["session_id"] = str(probe["payload"].get("session_id") or client_auth_session.get("session_id") or "").strip()
            probe["workspace_id"] = _extract_workspace_id_from_payload(client_auth_session)
            probe["workspaces_count"] = _extract_workspaces_count_from_payload(client_auth_session)
        probe["workspaces_present"] = bool(probe["workspaces_count"])
        probe["ok"] = probe["status_code"] == 200 and bool(client_auth_session)
    except Exception as exc:
        probe["error"] = str(exc)[:200]
    return probe


def _org_flag_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _org_text_blob(org: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("id", "name", "display_name", "title", "slug", "type", "kind", "org_type", "organization_type", "workspace_type", "plan_type", "role"):
        value = str(org.get(key) or "").strip()
        if value:
            parts.append(value.lower())
    return " ".join(parts)


def _org_personal_hint(org: dict[str, Any]) -> bool:
    for key in ("is_personal", "personal", "is_personal_workspace", "personal_workspace", "is_user_workspace", "user_workspace"):
        if _org_flag_enabled(org.get(key)):
            return True
    return any(token in _org_text_blob(org) for token in ("personal", "individual", "private"))


def _org_team_hint(org: dict[str, Any]) -> bool:
    return any(token in _org_text_blob(org) for token in ("team", "business", "enterprise", "workspace", "company"))


def _extract_first_project_id(org: dict[str, Any]) -> str:
    projects = org.get("projects") or []
    if not isinstance(projects, list):
        return ""
    for project in projects:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or project.get("project_id") or "").strip()
        if project_id:
            return project_id
    return ""


def _select_preferred_org_candidate(orgs: Any) -> dict[str, Any]:
    if not isinstance(orgs, list):
        return {}
    best: dict[str, Any] = {}
    for index, raw_org in enumerate(orgs):
        if not isinstance(raw_org, dict):
            continue
        org_id = str(raw_org.get("id") or raw_org.get("org_id") or "").strip()
        if not org_id:
            continue
        default_hint = any(_org_flag_enabled(raw_org.get(key)) for key in ("is_default", "default", "selected", "is_selected"))
        personal_hint = _org_personal_hint(raw_org)
        team_hint = _org_team_hint(raw_org)
        score = max(0, 20 - index)
        if personal_hint:
            score += 600
        if default_hint:
            score += 200
        if team_hint and not personal_hint:
            score -= 80
        candidate = {
            "org_id": org_id,
            "project_id": _extract_first_project_id(raw_org),
            "score": score,
            "org": raw_org,
        }
        if not best or candidate["score"] > int(best.get("score") or 0):
            best = candidate
    return best


def _inject_selected_org_context(token_json: str | None, *, organization_id: str = "", project_id: str = "") -> str | None:
    if not token_json:
        return token_json
    updates = {k: v for k, v in {"organization_id": organization_id.strip(), "project_id": project_id.strip()}.items() if v}
    if not updates:
        return token_json
    try:
        payload = json.loads(token_json)
    except Exception:
        return token_json
    if not isinstance(payload, dict):
        return token_json
    payload.update(updates)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _is_consent_branch(*, page_type: str, continue_url: str) -> bool:
    normalized_page_type = str(page_type or "").strip().lower()
    normalized_continue_url = str(continue_url or "").strip().lower()
    return normalized_page_type == "sign_in_with_chatgpt_codex_consent" or "sign-in-with-chatgpt/codex/consent" in normalized_continue_url


def _transition_status_code(transition: dict[str, Any]) -> int:
    try:
        return int(transition.get("status_code") or 0)
    except Exception:
        return 0


def _transition_reason(transition: dict[str, Any]) -> str:
    status_code = _transition_status_code(transition)
    return str(transition.get("error_code") or (f"http_{status_code}" if status_code else "")).strip()


def _compact_transition_event(stage: str, transition: dict[str, Any], **extra: Any) -> dict[str, Any]:
    event = {
        "stage": stage,
        "status_code": _transition_status_code(transition),
        "page_type": str(transition.get("page_type") or "").strip(),
        "continue_url": str(transition.get("continue_url") or "").strip()[:300],
        "callback_url_present": bool(transition.get("callback_url")),
    }
    error_code = str(transition.get("error_code") or "").strip()
    if error_code:
        event["error_code"] = error_code
    if transition.get("error"):
        event["error"] = str(transition.get("error") or "")[:180]
    event.update(extra)
    return event


def _should_repair_password_verify(transition: dict[str, Any]) -> bool:
    status_code = _transition_status_code(transition)
    reason = _transition_reason(transition).lower()
    if status_code in {408, 409, 425, 429} or status_code >= 500:
        return True
    # `invalid_username_or_password` is normally terminal, but it is also the
    # most common disguise when the auth state machine rejects a stale
    # Sentinel/session pairing.  Try one same-session repair before surfacing it
    # as a real bad-password diagnosis.
    return status_code in {400, 401, 403} and reason in {"", "bad_request", "invalid_auth_step", "invalid_username_or_password"}


def _should_repair_email_otp_validate(transition: dict[str, Any]) -> bool:
    status_code = _transition_status_code(transition)
    reason = _transition_reason(transition).lower()
    if status_code in {408, 409, 425, 429} or status_code >= 500:
        return True
    if reason in {"wrong_email_otp_code", "email_otp_expired"}:
        return False
    return status_code in {400, 401, 403} and reason in {"", "bad_request", "invalid_auth_step"}


def _password_failure_status(transition: dict[str, Any]) -> str:
    status_code = _transition_status_code(transition)
    reason = _transition_reason(transition).lower()
    if status_code in {408, 409, 425, 429} or status_code >= 500 or reason in {"bad_request", "invalid_auth_step"}:
        return "password_error"
    return "bad_password" if status_code in {400, 401, 403} else "password_error"


def _short_exception_reason(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:220]}"


def _is_transient_finalize_reason(reason: str) -> bool:
    lowered = str(reason or "").strip().lower()
    if not lowered:
        return False
    transient_markers = (
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "remote disconnected",
        "empty reply",
        "eof",
        "curl: (28)",
    )
    if any(marker in lowered for marker in transient_markers):
        return True
    return lowered in {"callback_error", "finalize_unresolved", "workspace_select_error", "workspace_select_continue_missing"}


def _is_otp_code_stale_reason(reason: str) -> bool:
    return str(reason or "").strip().lower() in {"wrong_email_otp_code", "email_otp_expired"}


ProtocolEventCallback = Callable[[dict[str, Any]], None]


class ProtocolLoginClient:
    def __init__(
        self,
        *,
        impersonate: str = DEFAULT_IMPERSONATE,
        verify_ssl: bool = True,
        timeout: int = 30,
        event_callback: ProtocolEventCallback | None = None,
    ) -> None:
        self.impersonate = str(impersonate or DEFAULT_IMPERSONATE).strip() or DEFAULT_IMPERSONATE
        self.verify_ssl = bool(verify_ssl)
        self.timeout = max(10, int(timeout or 30))
        self.event_callback = event_callback

    def _emit_stage(self, stage: str, **payload: Any) -> None:
        if not self.event_callback:
            return
        event = {"stage": stage}
        event.update(payload)
        try:
            self.event_callback(event)
        except Exception:
            # Runtime telemetry must never break the actual login flow.
            return

    def _finalize_timeout(self) -> int:
        # Keep the final callback/token phase aligned with the user-selected
        # HTTP timeout instead of silently stretching the GUI default 30s to
        # 60s.  Slow callback chains are now handled by session-local retry
        # below, which is much cheaper than re-running password + OTP.
        return max(10, int(self.timeout or 30))

    def _local_finalize_attempts(self) -> int:
        raw = os.getenv("GPT2JSON_FINALIZE_ATTEMPTS", "").strip()
        try:
            value = int(raw) if raw else 2
        except ValueError:
            value = 2
        return max(1, min(4, value))

    def _otp_refetch_attempts(self) -> int:
        raw = os.getenv("GPT2JSON_OTP_REFETCH_ATTEMPTS", "").strip()
        try:
            value = int(raw) if raw else 1
        except ValueError:
            value = 1
        return max(0, min(3, value))

    def _otp_refetch_timeout(self) -> int:
        raw = os.getenv("GPT2JSON_OTP_REFETCH_TIMEOUT", "").strip()
        try:
            value = int(raw) if raw else 20
        except ValueError:
            value = 20
        return max(5, min(60, value))

    def _local_retry_sleep(self, attempt: int) -> None:
        time.sleep(min(2.0, 0.45 + max(0, attempt - 1) * 0.35))

    def _poll_otp_row(self, otp_fetcher: OtpFetcher, row: AccountRow, *, proxies: Any = None, timeout: int | None = None) -> str:
        """Poll OTP, optionally with a temporary shorter timeout.

        The first OTP wait can use the user-configured value.  A same-session
        refetch after a known stale code should be fast: if the no-login source
        still does not expose a new code shortly after `/email-otp/send`, it is
        cheaper to leave the current attempt than to pin a worker for minutes.
        """

        if timeout is None or not hasattr(otp_fetcher, "timeout"):
            return otp_fetcher.poll_row(row, proxies=proxies)
        old_timeout = otp_fetcher.timeout
        try:
            otp_fetcher.timeout = max(5, min(int(old_timeout or timeout), int(timeout)))
            return otp_fetcher.poll_row(row, proxies=proxies)
        finally:
            try:
                otp_fetcher.timeout = old_timeout
            except Exception:
                pass

    def _request(self, session: requests.Session, method: str, url: str, *, proxies: Any = None, headers: dict[str, Any] | None = None, json_body: Any = None, data: Any = None, allow_redirects: bool = False, timeout: int | None = None) -> Any:
        kwargs = {
            "headers": headers or {},
            "proxies": proxies,
            "verify": self.verify_ssl,
            "timeout": timeout or self.timeout,
            "allow_redirects": allow_redirects,
            "impersonate": self.impersonate,
        }
        if json_body is not None:
            kwargs["json"] = json_body
        elif data is not None:
            kwargs["data"] = data
        return session.request(method=method.upper(), url=url, **kwargs)

    def _request_with_retry(
        self,
        session: requests.Session,
        method: str,
        url: str,
        *,
        proxies: Any = None,
        headers: dict[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
        allow_redirects: bool = False,
        timeout: int | None = None,
        retries: int = 2,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return self._request(
                    session,
                    method,
                    url,
                    proxies=proxies,
                    headers=headers,
                    json_body=json_body,
                    data=data,
                    allow_redirects=allow_redirects,
                    timeout=timeout,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(1 + attempt)
        if last_error:
            raise last_error
        raise RuntimeError("request failed without exception")

    def _post_with_retry(self, session: requests.Session, url: str, *, headers: dict[str, Any], proxies: Any = None, json_body: Any = None, data: Any = None, timeout: int | None = None, retries: int = 2) -> Any:
        return self._request_with_retry(
            session,
            "POST",
            url,
            proxies=proxies,
            headers=headers,
            json_body=json_body,
            data=data,
            timeout=timeout,
            retries=retries,
        )

    def _build_sentinel_request_body(self, did: str, *, flow: str = "authorize_continue") -> str:
        return json.dumps({"p": str(os.getenv("OPENAI_SENTINEL_P") or "").strip(), "id": str(did or "").strip(), "flow": str(flow or "authorize_continue").strip()}, ensure_ascii=False)

    def _build_sentinel_header(self, did: str, token: str, *, flow: str = "authorize_continue") -> str:
        return json.dumps(
            {
                "p": str(os.getenv("OPENAI_SENTINEL_P") or "").strip(),
                "t": str(os.getenv("OPENAI_SENTINEL_T") or "").strip(),
                "c": str(token or "").strip(),
                "id": str(did or "").strip(),
                "flow": str(flow or "authorize_continue").strip(),
            },
            ensure_ascii=False,
        )

    def request_authorize_continue_sentinel(self, did: str, *, proxies: Any = None, flow: str = "authorize_continue") -> str:
        body = self._build_sentinel_request_body(did, flow=flow)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    "https://sentinel.openai.com/backend-api/sentinel/req",
                    headers={
                        "origin": "https://sentinel.openai.com",
                        "referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html?sv=20260219f9f6",
                        "content-type": "text/plain;charset=UTF-8",
                    },
                    data=body,
                    proxies=proxies,
                    verify=self.verify_ssl,
                    timeout=self.timeout,
                    impersonate=self.impersonate,
                )
                break
            except Exception as exc:
                last_error = exc
                if attempt >= 2:
                    raise
                time.sleep(1 + attempt)
        else:
            if last_error:
                raise last_error
            raise RuntimeError("sentinel req failed without exception")
        if resp.status_code != 200:
            raise RuntimeError(f"sentinel req returned status {resp.status_code}")
        token = str((resp.json() or {}).get("token") or "").strip()
        if not token:
            raise RuntimeError("sentinel req returned empty token")
        return self._build_sentinel_header(did, token, flow=flow)

    def _sentinel_for_flow(self, did: str, *, flow: str, proxies: Any = None, fallback: str = "") -> str:
        """Mint a Sentinel token for the concrete auth step.

        auth.openai.com treats the login flow as a small state machine.  A
        token minted for `authorize_continue` can be accepted for the email
        step but later make `/password/verify` look like a credential failure
        on some accounts.  Keep the flow-specific request best-effort so older
        sandboxes that only understand one token shape can still fall back.
        """

        try:
            return self.request_authorize_continue_sentinel(did, proxies=proxies, flow=flow)
        except Exception:
            return str(fallback or "").strip()

    def _visit_auth_page(self, session: requests.Session, url: str, *, referer: str, proxies: Any = None, stage: str) -> dict[str, Any]:
        """Best-effort browser-like navigation between auth API steps.

        Real browser login does not jump directly from one JSON API to the
        next: after `/authorize/continue` it loads the password page, and after
        password verification it may load the email verification page.  These
        page visits can refresh cookies/checksums used by the next API call.
        Keep this best-effort so older sandboxes that do not require the page
        hop are not penalized by a transient warm-up failure.
        """

        target_url = str(url or "").strip()
        if not target_url:
            return {}
        parsed = urllib.parse.urlparse(target_url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "auth.openai.com":
            return {}
        try:
            resp = self._request_with_retry(
                session,
                "GET",
                target_url,
                proxies=proxies,
                headers=_headers(AUTH_NAV_HEADERS, referer=referer or "https://auth.openai.com/log-in"),
                allow_redirects=True,
                timeout=self.timeout,
                retries=1,
            )
            transition = _extract_transition_targets_from_response(resp, request_url=target_url)
            self._emit_stage(stage, **{k: v for k, v in _compact_transition_event(stage, transition).items() if k != "stage"})
            return transition
        except Exception as exc:
            transition = {
                "status_code": 0,
                "payload": {},
                "raw_text": "",
                "location_url": "",
                "continue_url": target_url,
                "page_type": _infer_page_type_from_url(target_url),
                "callback_url": "",
                "error_code": "",
                "error": f"{type(exc).__name__}: {str(exc)[:180]}",
            }
            self._emit_stage(stage, error=transition["error"], page_type=transition["page_type"], status_code=0)
            return transition

    def _request_email_otp_resend(
        self,
        session: requests.Session,
        *,
        row: AccountRow,
        referer: str,
        did: str,
        sentinel_token: str,
        proxies: Any = None,
    ) -> dict[str, Any]:
        """Best-effort in-session request for a fresh email OTP.

        Some accounts receive an old code from the no-login source on the first
        poll.  A browser user would stay on the verification page and click
        "send again" instead of restarting the whole OAuth flow; mirror that
        behavior here.  The endpoint shape may differ between auth revisions,
        so this remains non-fatal and falls back to polling the source again.
        """

        headers = _headers(
            AUTH_JSON_HEADERS,
            referer=referer or "https://auth.openai.com/email-verification",
            oai_device_id=did,
            **{"openai-sentinel-token": sentinel_token},
        )
        candidate_bodies: tuple[dict[str, Any], ...] = (
            {},
            {"email": row.login_email},
            {"email": {"value": row.login_email, "kind": "email"}},
        )
        last_transition: dict[str, Any] = {}
        last_error = ""
        for body in candidate_bodies:
            try:
                resp = self._post_with_retry(
                    session,
                    "https://auth.openai.com/api/accounts/email-otp/send",
                    headers=headers,
                    proxies=proxies,
                    json_body=body,
                    timeout=min(self.timeout, 15),
                    retries=0,
                )
                transition = _extract_transition_targets_from_response(resp, request_url="https://auth.openai.com/api/accounts/email-otp/send")
                last_transition = transition
                if transition["status_code"] < 400:
                    event = _compact_transition_event("email_otp_resend", transition, body_shape="empty" if not body else "email")
                    self._emit_stage("email_otp_resend", **{k: v for k, v in event.items() if k != "stage"})
                    return transition
            except Exception as exc:
                last_error = _short_exception_reason(exc)
        if last_error:
            self._emit_stage("email_otp_resend", status_code=0, error=last_error)
        elif last_transition:
            event = _compact_transition_event("email_otp_resend", last_transition)
            self._emit_stage("email_otp_resend", **{k: v for k, v in event.items() if k != "stage"})
        return last_transition

    def _follow_redirect_chain_to_callback(self, session: requests.Session, *, start_url: str, oauth_start: OAuthStart, proxies: Any = None) -> tuple[str | None, str]:
        current_url = str(start_url or "").strip()
        if not current_url:
            return None, "callback_error"
        for _ in range(15):
            if "code=" in current_url and "state=" in current_url:
                token_json = submit_callback_url(
                    callback_url=current_url,
                    expected_state=oauth_start.state,
                    code_verifier=oauth_start.code_verifier,
                    redirect_uri=oauth_start.redirect_uri,
                    verify=self.verify_ssl,
                    timeout=self._finalize_timeout(),
                )
                return token_json, ""
            final_resp = self._request_with_retry(
                session,
                "GET",
                current_url,
                proxies=proxies,
                headers=_headers(AUTH_NAV_HEADERS, referer="https://auth.openai.com/"),
                allow_redirects=False,
                timeout=self._finalize_timeout(),
            )
            next_url = ""
            if final_resp.status_code in {301, 302, 303, 307, 308}:
                next_url = _normalize_absolute_url(current_url, (getattr(final_resp, "headers", {}) or {}).get("Location") or "")
            elif final_resp.status_code == 200:
                transition = _extract_transition_targets_from_response(final_resp, request_url=current_url)
                if transition["callback_url"]:
                    token_json = submit_callback_url(
                        callback_url=transition["callback_url"],
                        expected_state=oauth_start.state,
                        code_verifier=oauth_start.code_verifier,
                        redirect_uri=oauth_start.redirect_uri,
                        verify=self.verify_ssl,
                        timeout=self._finalize_timeout(),
                    )
                    return token_json, ""
                if "consent_challenge=" in current_url:
                    consent_resp = self._post_with_retry(
                        session,
                        current_url,
                        headers={
                            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "content-type": "application/x-www-form-urlencoded",
                            "origin": "https://auth.openai.com",
                            "referer": current_url,
                        },
                        data={"action": "accept"},
                        proxies=proxies,
                        timeout=self._finalize_timeout(),
                    )
                    next_url = _normalize_absolute_url(current_url, (getattr(consent_resp, "headers", {}) or {}).get("Location") or "")
                else:
                    meta_match = re.search(r'content=["\']?\d+;\s*url=([^"\'>\s]+)', str(final_resp.text or ""), re.IGNORECASE)
                    next_url = urllib.parse.urljoin(current_url, meta_match.group(1)) if meta_match else str(transition.get("continue_url") or "").strip()
            else:
                return None, "callback_error"
            if not next_url:
                return None, "callback_error"
            current_url = next_url
        return None, "callback_error"

    def _select_workspace_and_finalize(self, session: requests.Session, *, workspace_id: str, oauth_start: OAuthStart, proxies: Any = None, referer: str, sentinel_token: str = "") -> tuple[str | None, dict[str, Any], str]:
        select_resp = self._post_with_retry(
            session,
            "https://auth.openai.com/api/accounts/workspace/select",
            headers=_headers(
                AUTH_JSON_HEADERS,
                referer=str(referer or "https://auth.openai.com/sign-in-with-chatgpt/codex/consent").strip(),
            ),
            data=json.dumps({"workspace_id": workspace_id}, ensure_ascii=False, separators=(",", ":")),
            proxies=proxies,
            timeout=self._finalize_timeout(),
        )
        transition = _extract_transition_targets_from_response(select_resp, request_url="https://auth.openai.com/api/accounts/workspace/select")
        if transition["callback_url"]:
            token_json = submit_callback_url(
                callback_url=transition["callback_url"],
                expected_state=oauth_start.state,
                code_verifier=oauth_start.code_verifier,
                redirect_uri=oauth_start.redirect_uri,
                verify=self.verify_ssl,
                timeout=self._finalize_timeout(),
            )
            return token_json, transition, ""

        continue_url = str(transition.get("continue_url") or "").strip()
        payload = transition.get("payload") or {}
        selected_org_id = ""
        selected_project_id = ""
        try:
            orgs = (payload.get("data") or {}).get("orgs") or []
            candidate = _select_preferred_org_candidate(orgs)
            org_id = str(candidate.get("org_id") or "").strip()
            if org_id:
                selected_org_id = org_id
                selected_project_id = str(candidate.get("project_id") or "").strip()
                body = {"org_id": org_id}
                if selected_project_id:
                    body["project_id"] = selected_project_id
                headers = _headers(AUTH_JSON_HEADERS, referer="https://auth.openai.com/sign-in-with-chatgpt/codex/consent")
                if sentinel_token:
                    headers["openai-sentinel-token"] = sentinel_token
                org_resp = self._post_with_retry(
                    session,
                    "https://auth.openai.com/api/accounts/organization/select",
                    headers=headers,
                    proxies=proxies,
                    json_body=body,
                )
                org_transition = _extract_transition_targets_from_response(org_resp, request_url="https://auth.openai.com/api/accounts/organization/select")
                if org_transition["callback_url"]:
                    token_json = submit_callback_url(
                        callback_url=org_transition["callback_url"],
                        expected_state=oauth_start.state,
                        code_verifier=oauth_start.code_verifier,
                        redirect_uri=oauth_start.redirect_uri,
                        verify=self.verify_ssl,
                        timeout=self._finalize_timeout(),
                    )
                    token_json = _inject_selected_org_context(token_json, organization_id=selected_org_id, project_id=selected_project_id)
                    return token_json, org_transition, ""
                if org_transition["continue_url"]:
                    continue_url = str(org_transition["continue_url"]).strip()
                    transition = org_transition
        except Exception:
            pass

        if continue_url:
            token_json, follow_reason = self._follow_redirect_chain_to_callback(session, start_url=continue_url, oauth_start=oauth_start, proxies=proxies)
            if token_json:
                token_json = _inject_selected_org_context(token_json, organization_id=selected_org_id, project_id=selected_project_id)
                return token_json, transition, ""
            return None, transition, follow_reason
        if transition["status_code"] not in {200, 301, 302, 303, 307, 308}:
            return None, transition, "workspace_select_error"
        if transition["error_code"]:
            return None, transition, "workspace_select_error"
        return None, transition, "workspace_select_continue_missing"

    def _finalize_transition(self, session: requests.Session, *, transition: dict[str, Any], oauth_start: OAuthStart, proxies: Any = None, sentinel: str = "") -> tuple[str | None, str, dict[str, Any]]:
        callback_url = str(transition.get("callback_url") or "").strip()
        continue_url = str(transition.get("continue_url") or "").strip()
        page_type = str(transition.get("page_type") or "").strip()
        if callback_url:
            token_json = submit_callback_url(
                callback_url=callback_url,
                expected_state=oauth_start.state,
                code_verifier=oauth_start.code_verifier,
                redirect_uri=oauth_start.redirect_uri,
                verify=self.verify_ssl,
                timeout=self._finalize_timeout(),
            )
            return token_json, "", transition

        if continue_url:
            token_json, reason = self._follow_redirect_chain_to_callback(session, start_url=continue_url, oauth_start=oauth_start, proxies=proxies)
            if token_json:
                return token_json, "", transition
            if _is_consent_branch(page_type=page_type, continue_url=continue_url):
                auth_cookie = _get_preferred_session_cookie_value(
                    session,
                    "oai-client-auth-session",
                    preferred_domains=("auth.openai.com", ".auth.openai.com", "openai.com", ".openai.com"),
                )
                workspace_id, _workspace_count = _extract_workspace_info_from_auth_cookie(auth_cookie)
                probe = _probe_client_auth_session_dump(session, client=self, proxies=proxies)
                workspace_id = workspace_id or str(probe.get("workspace_id") or "").strip()
                if workspace_id:
                    token_json, workspace_transition, ws_reason = self._select_workspace_and_finalize(
                        session,
                        workspace_id=workspace_id,
                        oauth_start=oauth_start,
                        proxies=proxies,
                        referer=continue_url,
                        sentinel_token=sentinel,
                    )
                    if token_json:
                        return token_json, "", workspace_transition
                    return None, ws_reason or reason, workspace_transition
            return None, reason, transition

        auth_cookie = _get_preferred_session_cookie_value(
            session,
            "oai-client-auth-session",
            preferred_domains=("auth.openai.com", ".auth.openai.com", "openai.com", ".openai.com"),
        )
        workspace_id, _workspace_count = _extract_workspace_info_from_auth_cookie(auth_cookie)
        if not workspace_id:
            probe = _probe_client_auth_session_dump(session, client=self, proxies=proxies)
            workspace_id = str(probe.get("workspace_id") or "").strip()
        if workspace_id:
            token_json, workspace_transition, ws_reason = self._select_workspace_and_finalize(
                session,
                workspace_id=workspace_id,
                oauth_start=oauth_start,
                proxies=proxies,
                referer="https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
                sentinel_token=sentinel,
            )
            if token_json:
                return token_json, "", workspace_transition
            return None, ws_reason, workspace_transition
        return None, "finalize_unresolved", transition

    def login_and_exchange(self, row: AccountRow, *, otp_fetcher: OtpFetcher, proxies: Any = None) -> AttemptResult:
        result = AttemptResult(
            row=row,
            status="started",
            stage="oauth_start",
            events=[{"stage": "oauth_start", "login_masked": mask_email(row.login_email), "otp_source_masked": mask_source(row.otp_source)}],
        )
        session = requests.Session()
        oauth_start = generate_oauth_url()
        try:
            self._emit_stage("oauth_start")
            otp_fetcher.prime_row(row, proxies=proxies)
            entry = self._request(
                session,
                "GET",
                oauth_start.auth_url,
                proxies=proxies,
                headers=_headers(AUTH_NAV_HEADERS, referer="https://chatgpt.com/"),
                allow_redirects=True,
                timeout=30,
            )
            entry_status = int(getattr(entry, "status_code", 0) or 0)
            result.events.append({"stage": "entry", "status_code": entry_status, "url": str(getattr(entry, "url", "") or "")[:300]})
            self._emit_stage("entry", status_code=entry_status)
            if entry_status >= 400:
                result.status = "auth_entry_error"
                result.stage = "entry"
                result.reason = f"http_{entry_status}"
                return result

            did = _get_preferred_session_cookie_value(
                session,
                "oai-did",
                preferred_domains=("auth.openai.com", ".auth.openai.com", "openai.com", ".openai.com"),
            )
            result.stage = "sentinel"
            result.events.append({"stage": "sentinel", "did_present": bool(did)})
            self._emit_stage("sentinel", did_present=bool(did))
            sentinel = self._sentinel_for_flow(did, flow="authorize_continue", proxies=proxies)
            result.meta["did_present"] = bool(did)

            authorize_resp = self._post_with_retry(
                session,
                "https://auth.openai.com/api/accounts/authorize/continue",
                headers=_headers(
                    AUTH_JSON_HEADERS,
                    referer="https://auth.openai.com/log-in",
                    oai_device_id=did,
                    **{"openai-sentinel-token": sentinel},
                ),
                json_body={"username": {"value": row.login_email, "kind": "email"}, "screen_hint": "login"},
                proxies=proxies,
            )
            authorize_transition = _extract_transition_targets_from_response(authorize_resp, request_url="https://auth.openai.com/api/accounts/authorize/continue")
            result.events.append({"stage": "authorize_continue", "status_code": authorize_transition["status_code"], "page_type": authorize_transition["page_type"], "continue_url": authorize_transition["continue_url"][:300]})
            self._emit_stage(
                "authorize_continue",
                status_code=authorize_transition["status_code"],
                page_type=authorize_transition["page_type"],
            )
            if authorize_transition["status_code"] >= 400:
                result.status = "authorize_continue_error"
                result.stage = "authorize_continue"
                result.reason = authorize_transition["error_code"] or f"http_{authorize_transition['status_code']}"
                return result

            password_referer = authorize_transition["continue_url"] or "https://auth.openai.com/log-in/password"
            password_page = self._visit_auth_page(
                session,
                password_referer,
                referer="https://auth.openai.com/log-in",
                proxies=proxies,
                stage="password_page_warmup",
            )
            if password_page:
                result.events.append(_compact_transition_event("password_page_warmup", password_page))
                password_referer = str(password_page.get("continue_url") or password_referer).strip()

            password_sentinel = self._sentinel_for_flow(did, flow="password_verify", proxies=proxies, fallback=sentinel)
            result.meta["password_sentinel_flow"] = "password_verify" if password_sentinel and password_sentinel != sentinel else "authorize_continue"

            def post_password_verify(sentinel_header: str, referer_url: str) -> Any:
                return self._post_with_retry(
                    session,
                    "https://auth.openai.com/api/accounts/password/verify",
                    headers=_headers(
                        AUTH_JSON_HEADERS,
                        referer=referer_url or "https://auth.openai.com/log-in/password",
                        oai_device_id=did,
                        **{"openai-sentinel-token": sentinel_header},
                    ),
                    json_body={"password": row.gpt_password},
                    proxies=proxies,
                )

            pwd_resp = post_password_verify(password_sentinel, password_referer)
            pwd_transition = _extract_transition_targets_from_response(pwd_resp, request_url="https://auth.openai.com/api/accounts/password/verify")
            result.events.append({"stage": "password_verify", "status_code": pwd_transition["status_code"], "page_type": pwd_transition["page_type"], "continue_url": pwd_transition["continue_url"][:300], "callback_url_present": bool(pwd_transition["callback_url"])})
            self._emit_stage(
                "password_verify",
                status_code=pwd_transition["status_code"],
                page_type=pwd_transition["page_type"],
                callback_url_present=bool(pwd_transition["callback_url"]),
            )

            if _should_repair_password_verify(pwd_transition):
                result.meta["password_repair_attempted"] = True
                result.events.append(_compact_transition_event("password_verify_repair", pwd_transition, action="refresh_page_and_sentinel"))
                self._emit_stage(
                    "password_verify_repair",
                    status_code=pwd_transition["status_code"],
                    page_type=pwd_transition["page_type"],
                    reason=_transition_reason(pwd_transition),
                    action="refresh_page_and_sentinel",
                )
                repair_page = self._visit_auth_page(
                    session,
                    password_referer or "https://auth.openai.com/log-in/password",
                    referer="https://auth.openai.com/log-in",
                    proxies=proxies,
                    stage="password_page_repair",
                )
                if repair_page:
                    result.events.append(_compact_transition_event("password_page_repair", repair_page))
                    password_referer = str(repair_page.get("continue_url") or password_referer).strip()
                repair_sentinel = self._sentinel_for_flow(did, flow="password_verify", proxies=proxies, fallback=password_sentinel or sentinel)
                pwd_resp = post_password_verify(repair_sentinel, password_referer)
                pwd_transition = _extract_transition_targets_from_response(pwd_resp, request_url="https://auth.openai.com/api/accounts/password/verify")
                result.events.append(_compact_transition_event("password_verify_repair_result", pwd_transition))
                self._emit_stage(
                    "password_verify_repair_result",
                    status_code=pwd_transition["status_code"],
                    page_type=pwd_transition["page_type"],
                    callback_url_present=bool(pwd_transition["callback_url"]),
                )

            if pwd_transition["status_code"] >= 400:
                result.status = _password_failure_status(pwd_transition)
                result.stage = "password_verify"
                result.reason = pwd_transition["error_code"] or f"http_{pwd_transition['status_code']}"
                return result

            current_transition = pwd_transition
            needs_otp = "otp" in str(pwd_transition["page_type"]).lower() or "verify" in str(pwd_transition["continue_url"]).lower()
            if needs_otp:
                result.otp_required = True
                result.stage = "email_verification"
                otp_plan = otp_fetcher.backend_plan_for_row(row)
                result.events.append({"stage": "otp_backend_plan", **otp_plan})
                self._emit_stage("otp_backend_plan", **otp_plan)
                code = self._poll_otp_row(otp_fetcher, row, proxies=proxies)
                if not code:
                    otp_details = otp_fetcher.last_details_for_row(row)
                    result.events.append(
                        {
                            "stage": "otp_fetch",
                            "backend": otp_details.backend,
                            "status_code": otp_details.status_code,
                            "code_present": False,
                            "signature": otp_details.signature[:12],
                        }
                    )
                    self._emit_stage(
                        "otp_fetch",
                        backend=otp_details.backend,
                        status_code=otp_details.status_code,
                        code_present=False,
                    )
                    result.status = "otp_timeout"
                    result.reason = "otp_timeout"
                    return result
                otp_details = otp_fetcher.last_details_for_row(row)
                result.events.append(
                    {
                        "stage": "otp_fetch",
                        "backend": otp_details.backend,
                        "status_code": otp_details.status_code,
                        "code_present": True,
                        "signature": otp_details.signature[:12],
                    }
                )
                self._emit_stage(
                    "otp_fetch",
                    backend=otp_details.backend,
                    status_code=otp_details.status_code,
                    code_present=True,
                )
                otp_referer = str(pwd_transition.get("continue_url") or "https://auth.openai.com/email-verification").strip()
                otp_page = self._visit_auth_page(
                    session,
                    otp_referer,
                    referer=password_referer or "https://auth.openai.com/log-in/password",
                    proxies=proxies,
                    stage="email_otp_page_warmup",
                )
                if otp_page:
                    result.events.append(_compact_transition_event("email_otp_page_warmup", otp_page))
                    otp_referer = str(otp_page.get("continue_url") or otp_referer).strip()
                otp_sentinel = self._sentinel_for_flow(did, flow="email_otp_validate", proxies=proxies, fallback=password_sentinel or sentinel)
                result.meta["otp_sentinel_flow"] = "email_otp_validate" if otp_sentinel and otp_sentinel not in {password_sentinel, sentinel} else result.meta.get("password_sentinel_flow", "authorize_continue")

                def post_email_otp_validate(sentinel_header: str, referer_url: str) -> Any:
                    return self._post_with_retry(
                        session,
                        "https://auth.openai.com/api/accounts/email-otp/validate",
                        headers=_headers(
                            AUTH_JSON_HEADERS,
                            referer=referer_url or "https://auth.openai.com/email-verification",
                            oai_device_id=did,
                            **{"openai-sentinel-token": sentinel_header},
                        ),
                        json_body={"code": code},
                        proxies=proxies,
                    )

                otp_resp = post_email_otp_validate(otp_sentinel, otp_referer)
                current_transition = _extract_transition_targets_from_response(otp_resp, request_url="https://auth.openai.com/api/accounts/email-otp/validate")
                result.events.append(_compact_transition_event("email_otp_validate", current_transition))
                self._emit_stage(
                    "email_otp_validate",
                    **{k: v for k, v in _compact_transition_event("email_otp_validate", current_transition).items() if k != "stage"},
                )
                if _should_repair_email_otp_validate(current_transition):
                    result.meta["otp_validate_repair_attempted"] = True
                    result.events.append(_compact_transition_event("email_otp_validate_repair", current_transition, action="refresh_page_and_sentinel"))
                    self._emit_stage(
                        "email_otp_validate_repair",
                        status_code=current_transition["status_code"],
                        page_type=current_transition["page_type"],
                        reason=_transition_reason(current_transition),
                        action="refresh_page_and_sentinel",
                    )
                    repair_otp_page = self._visit_auth_page(
                        session,
                        otp_referer or "https://auth.openai.com/email-verification",
                        referer=password_referer or "https://auth.openai.com/log-in/password",
                        proxies=proxies,
                        stage="email_otp_page_repair",
                    )
                    if repair_otp_page:
                        result.events.append(_compact_transition_event("email_otp_page_repair", repair_otp_page))
                        otp_referer = str(repair_otp_page.get("continue_url") or otp_referer).strip()
                    repair_otp_sentinel = self._sentinel_for_flow(did, flow="email_otp_validate", proxies=proxies, fallback=otp_sentinel or password_sentinel or sentinel)
                    otp_resp = post_email_otp_validate(repair_otp_sentinel, otp_referer)
                    current_transition = _extract_transition_targets_from_response(otp_resp, request_url="https://auth.openai.com/api/accounts/email-otp/validate")
                    result.events.append(_compact_transition_event("email_otp_validate_repair_result", current_transition))
                    self._emit_stage(
                        "email_otp_validate_repair_result",
                        status_code=current_transition["status_code"],
                        page_type=current_transition["page_type"],
                        callback_url_present=bool(current_transition["callback_url"]),
                    )

                otp_refetch_limit = self._otp_refetch_attempts()
                otp_refetch_count = 0
                while current_transition["status_code"] >= 400 and otp_refetch_count < otp_refetch_limit and _is_otp_code_stale_reason(_transition_reason(current_transition)):
                    otp_refetch_count += 1
                    result.meta["otp_refetch_attempted"] = otp_refetch_count
                    reason = _transition_reason(current_transition)
                    result.events.append(
                        {
                            "stage": "otp_refetch",
                            "reason": reason,
                            "otp_refetch_attempt": otp_refetch_count,
                            "max_otp_refetch_attempts": otp_refetch_limit,
                        }
                    )
                    self._emit_stage(
                        "otp_refetch",
                        reason=reason,
                        otp_refetch_attempt=otp_refetch_count,
                        max_otp_refetch_attempts=otp_refetch_limit,
                    )
                    resend_sentinel = self._sentinel_for_flow(did, flow="email_otp_send", proxies=proxies, fallback=otp_sentinel or password_sentinel or sentinel)
                    resend_transition = self._request_email_otp_resend(
                        session,
                        row=row,
                        referer=otp_referer,
                        did=did,
                        sentinel_token=resend_sentinel or otp_sentinel or password_sentinel or sentinel,
                        proxies=proxies,
                    )
                    if resend_transition:
                        result.events.append(_compact_transition_event("email_otp_resend", resend_transition))
                    code = self._poll_otp_row(otp_fetcher, row, proxies=proxies, timeout=self._otp_refetch_timeout())
                    if not code:
                        otp_details = otp_fetcher.last_details_for_row(row)
                        result.events.append(
                            {
                                "stage": "otp_fetch",
                                "backend": otp_details.backend,
                                "status_code": otp_details.status_code,
                                "code_present": False,
                                "signature": otp_details.signature[:12],
                                "otp_refetch_attempt": otp_refetch_count,
                            }
                        )
                        self._emit_stage(
                            "otp_fetch",
                            backend=otp_details.backend,
                            status_code=otp_details.status_code,
                            code_present=False,
                            otp_refetch_attempt=otp_refetch_count,
                        )
                        break
                    otp_details = otp_fetcher.last_details_for_row(row)
                    result.events.append(
                        {
                            "stage": "otp_fetch",
                            "backend": otp_details.backend,
                            "status_code": otp_details.status_code,
                            "code_present": True,
                            "signature": otp_details.signature[:12],
                            "otp_refetch_attempt": otp_refetch_count,
                        }
                    )
                    self._emit_stage(
                        "otp_fetch",
                        backend=otp_details.backend,
                        status_code=otp_details.status_code,
                        code_present=True,
                        otp_refetch_attempt=otp_refetch_count,
                    )
                    retry_otp_sentinel = self._sentinel_for_flow(did, flow="email_otp_validate", proxies=proxies, fallback=resend_sentinel or otp_sentinel or password_sentinel or sentinel)
                    otp_resp = post_email_otp_validate(retry_otp_sentinel, otp_referer)
                    current_transition = _extract_transition_targets_from_response(otp_resp, request_url="https://auth.openai.com/api/accounts/email-otp/validate")
                    result.events.append(_compact_transition_event("email_otp_validate", current_transition, otp_refetch_attempt=otp_refetch_count))
                    self._emit_stage(
                        "email_otp_validate",
                        **{k: v for k, v in _compact_transition_event("email_otp_validate", current_transition, otp_refetch_attempt=otp_refetch_count).items() if k != "stage"},
                    )
                if current_transition["status_code"] >= 400:
                    result.status = "email_otp_validate_error"
                    result.reason = current_transition["error_code"] or f"http_{current_transition['status_code']}"
                    return result

            result.stage = "finalize"
            finalize_attempt_limit = self._local_finalize_attempts()
            self._emit_stage("finalize", local_finalize_attempts=finalize_attempt_limit)
            token_json = None
            finalize_reason = ""
            finalize_transition = current_transition
            for finalize_attempt in range(1, finalize_attempt_limit + 1):
                try:
                    token_json, finalize_reason, finalize_transition = self._finalize_transition(
                        session,
                        transition=current_transition,
                        oauth_start=oauth_start,
                        proxies=proxies,
                        sentinel=sentinel,
                    )
                except Exception as exc:
                    token_json = None
                    finalize_reason = _short_exception_reason(exc)
                    finalize_transition = current_transition
                if token_json:
                    result.meta["finalize_local_attempt"] = finalize_attempt
                    break
                if finalize_attempt >= finalize_attempt_limit or not _is_transient_finalize_reason(finalize_reason):
                    break
                result.meta["finalize_local_retries"] = finalize_attempt
                result.events.append(
                    {
                        "stage": "finalize_retry",
                        "reason": finalize_reason,
                        "next_finalize_attempt": finalize_attempt + 1,
                        "max_finalize_attempts": finalize_attempt_limit,
                    }
                )
                self._emit_stage(
                    "finalize_retry",
                    reason=finalize_reason,
                    next_finalize_attempt=finalize_attempt + 1,
                    max_finalize_attempts=finalize_attempt_limit,
                )
                self._local_retry_sleep(finalize_attempt)
            if token_json:
                result.status = "success"
                result.stage = "callback"
                result.token_json = token_json
                result.meta["final_page_type"] = str(finalize_transition.get("page_type") or "").strip()
                result.meta["final_continue_url"] = str(finalize_transition.get("continue_url") or "").strip()
                self._emit_stage(
                    "callback",
                    page_type=str(finalize_transition.get("page_type") or "").strip(),
                    callback_url_present=bool(finalize_transition.get("callback_url")),
                )
                return result

            result.status = "finalize_error"
            result.stage = str(finalize_transition.get("page_type") or current_transition.get("page_type") or "")
            result.reason = finalize_reason or "finalize_error"
            result.meta["final_transition"] = {
                "page_type": str(finalize_transition.get("page_type") or ""),
                "continue_url": str(finalize_transition.get("continue_url") or ""),
                "callback_url_present": bool(finalize_transition.get("callback_url")),
            }
            return result
        except Exception as exc:
            result.status = "runtime_error"
            result.reason = f"{type(exc).__name__}: {str(exc)[:240]}"
            return result
        finally:
            result.finished_at = utc_now_iso()
