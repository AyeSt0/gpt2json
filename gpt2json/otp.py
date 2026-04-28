from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from curl_cffi import requests

from .mail_providers import backend_plan_for_row
from .models import AccountRow
from .parsing import is_url_source, normalize_email, secret_hash

OTP_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
HTML_RE = re.compile(r"<(?:!doctype|html|head|body|script|style)\b", re.IGNORECASE)
FETCH_URL_RE = re.compile(
    r"(?:fetch|axios\.(?:get|post)|request)\s*\(\s*[`'\"]([^`'\"]{1,300})[`'\"]",
    re.IGNORECASE,
)
STRING_API_URL_RE = re.compile(r"[`'\"]([^`'\"]*(?:otp|code|verify|mail|email)[^`'\"]{0,220})[`'\"]", re.IGNORECASE)
CURRENT_EMAIL_RE = re.compile(r"\bcurrentEmail\b\s*=\s*[`'\"]([^`'\"]+@[^`'\"]+)[`'\"]", re.IGNORECASE)


def extract_otp_from_text(text: Any) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    match = OTP_RE.search(raw)
    return match.group(1) if match else ""


def extract_otp_from_json(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return extract_otp_from_text(payload)
    if isinstance(payload, (int, float)):
        return extract_otp_from_text(str(payload))
    if isinstance(payload, list):
        for item in payload:
            code = extract_otp_from_json(item)
            if code:
                return code
        return ""
    if not isinstance(payload, dict):
        return ""

    # A number of no-login mail pages return structured error payloads with
    # fields like trace_id/status/code.  Do not recursively mine those for any
    # random six digits; only successful payloads or explicit OTP fields should
    # be considered.
    success_value = payload.get("success")
    if success_value is False:
        explicit_error_safe_keys = (
            "latest_code",
            "latestCode",
            "verification_code",
            "verificationCode",
            "otp",
            "oai_code",
            "pin",
        )
        for key in explicit_error_safe_keys:
            if key in payload:
                code = extract_otp_from_json(payload.get(key))
                if code:
                    return code
        return ""

    for key in ("latest_code", "latestCode", "code", "otp", "oai_code", "verification_code", "verificationCode", "pin"):
        if key in payload:
            code = extract_otp_from_json(payload.get(key))
            if code:
                return code
    for key in ("data", "result", "mail", "message", "latest", "item"):
        if key in payload:
            code = extract_otp_from_json(payload.get(key))
            if code:
                return code
    for value in payload.values():
        code = extract_otp_from_json(value)
        if code:
            return code
    return ""


def _json_response(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def _canonical_hash(payload: Any, length: int = 16) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        text = str(payload or "")
    return secret_hash(text, length=length)


@dataclass(frozen=True)
class OtpFetchDetails:
    code: str = ""
    signature: str = ""
    backend: str = ""
    status_code: int = 0


def _looks_like_html(text: str, content_type: str = "") -> bool:
    ctype = str(content_type or "").lower()
    if "text/html" in ctype:
        return True
    return bool(HTML_RE.search(str(text or "")[:2048]))


def _resolve_js_template_url(raw_url: str, *, base_url: str, email: str, html_text: str) -> str:
    candidate = str(raw_url or "").strip()
    if not candidate:
        return ""
    # Support the common front-end shape:
    #   `/api/foo?email=${encodeURIComponent(email)}`
    # without executing arbitrary JavaScript.
    selected_email = str(email or "").strip()
    if not selected_email:
        current_match = CURRENT_EMAIL_RE.search(str(html_text or ""))
        selected_email = str(current_match.group(1) or "").strip() if current_match else ""
    quoted_email = urllib.parse.quote(selected_email, safe="")
    candidate = re.sub(r"\$\{\s*encodeURIComponent\(\s*(?:email|currentEmail)\s*\)\s*\}", quoted_email, candidate)
    candidate = re.sub(r"\$\{\s*(?:email|currentEmail)\s*\}", quoted_email, candidate)
    candidate = candidate.replace("{email}", quoted_email)
    if "email=" not in candidate and selected_email and any(token in candidate.lower() for token in ("code", "otp", "mail", "email")):
        separator = "&" if "?" in candidate else "?"
        candidate = f"{candidate}{separator}email={quoted_email}"
    return urllib.parse.urljoin(base_url, candidate)


def _discover_api_urls_from_html(base_url: str, html_text: str, email: str) -> list[str]:
    text = str(html_text or "")
    urls: list[str] = []
    seen: set[str] = set()

    def push(raw_url: str) -> None:
        raw = str(raw_url or "").strip()
        lowered_raw = raw.lower()
        if not (
            lowered_raw.startswith(("http://", "https://", "/", "./", "../"))
            or "/api/" in lowered_raw
        ):
            return
        url = _resolve_js_template_url(raw_url, base_url=base_url, email=email, html_text=text)
        if not url:
            return
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            return
        lowered = url.lower()
        if not any(token in lowered for token in ("otp", "code", "verify", "mail", "email")):
            return
        if url not in seen:
            seen.add(url)
            urls.append(url)

    for pattern in (FETCH_URL_RE, STRING_API_URL_RE):
        for match in pattern.finditer(text):
            push(match.group(1))
    return urls[:8]


def render_otp_url(email: str, url_source: str) -> str:
    template = str(url_source or "").strip()
    if not template:
        return ""
    if "{email}" in template:
        return template.format(email=urllib.parse.quote(str(email or "").strip(), safe=""))
    return template


def fetch_otp_details_via_url(
    email: str,
    url_template: str,
    *,
    timeout: int = 20,
    impersonate: str = "chrome136",
    verify: bool = True,
    proxies: Any = None,
) -> tuple[str, str]:
    details = fetch_otp_fetch_details_via_url(
        email,
        url_template,
        timeout=timeout,
        impersonate=impersonate,
        verify=verify,
        proxies=proxies,
    )
    return details.code, details.signature


def fetch_otp_fetch_details_via_url(
    email: str,
    url_template: str,
    *,
    timeout: int = 20,
    impersonate: str = "chrome136",
    verify: bool = True,
    proxies: Any = None,
) -> OtpFetchDetails:
    url = render_otp_url(email, url_template)
    if not url:
        return OtpFetchDetails()

    def request_once(target_url: str, *, referer: str = "") -> Any:
        headers = {
            "accept": "application/json,text/plain,text/html,*/*",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "cache-control": "no-cache",
            "pragma": "no-cache",
        }
        if referer:
            headers["referer"] = referer
        return requests.get(
            target_url,
            headers=headers,
            impersonate=impersonate,
            proxies=proxies,
            verify=verify,
            timeout=timeout,
        )

    response = request_once(url)
    status_code = int(getattr(response, "status_code", 0) or 0)
    payload = _json_response(response)
    if payload is not None:
        code = extract_otp_from_json(payload)
        return OtpFetchDetails(code=code, signature=_canonical_hash(payload), backend="json", status_code=status_code)

    text = getattr(response, "text", "") or ""
    content_type = str((getattr(response, "headers", {}) or {}).get("content-type") or "")
    if _looks_like_html(text, content_type):
        for api_url in _discover_api_urls_from_html(str(getattr(response, "url", "") or url), text, email):
            try:
                api_response = request_once(api_url, referer=str(getattr(response, "url", "") or url))
            except Exception:
                continue
            api_status = int(getattr(api_response, "status_code", 0) or 0)
            api_payload = _json_response(api_response)
            if api_payload is not None:
                api_code = extract_otp_from_json(api_payload)
                return OtpFetchDetails(
                    code=api_code,
                    signature=_canonical_hash(api_payload),
                    backend="html_api_json",
                    status_code=api_status,
                )
            api_text = getattr(api_response, "text", "") or ""
            api_code = extract_otp_from_text(api_text)
            if api_code or api_text:
                return OtpFetchDetails(
                    code=api_code,
                    signature=secret_hash(api_text),
                    backend="html_api_text",
                    status_code=api_status,
                )
        # HTML application shells frequently contain unrelated six-digit
        # constants in scripts/styles.  If an API endpoint was not usable, do
        # not guess from the raw page.
        return OtpFetchDetails(code="", signature=secret_hash(text) if text else "", backend="html", status_code=status_code)

    code = extract_otp_from_text(text)
    return OtpFetchDetails(code=code, signature=secret_hash(text) if code or text else "", backend="text", status_code=status_code)


def fetch_otp_via_command(email: str, command_template: str) -> str:
    command = str(command_template or "").strip()
    if not command:
        return ""
    rendered = command.format(email=str(email or "").strip())
    env = dict(os.environ)
    env["OTP_EMAIL"] = str(email or "").strip()
    output = subprocess.check_output(rendered, shell=True, env=env, stderr=subprocess.STDOUT, timeout=60)
    text = output.decode("utf-8", errors="ignore")
    try:
        return extract_otp_from_json(json.loads(text))
    except Exception:
        return extract_otp_from_text(text)


class OtpFetcher:
    def __init__(
        self,
        *,
        mode: str = "auto",
        command: str = "",
        timeout: int = 180,
        interval: int = 3,
        impersonate: str = "chrome136",
        verify: bool = True,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.mode = str(mode or "auto").strip().lower()
        self.command = str(command or "").strip()
        self.timeout = max(5, int(timeout or 180))
        self.interval = max(1, int(interval or 3))
        self.impersonate = str(impersonate or "chrome136").strip() or "chrome136"
        self.verify = bool(verify)
        self.cancel_event = cancel_event
        self._seen_by_source: dict[str, set[str]] = {}
        self._primed_code_by_source: dict[str, tuple[str, str]] = {}
        self._last_details_by_source: dict[str, OtpFetchDetails] = {}

    @staticmethod
    def _code_marker(code: str) -> str:
        return f"code:{str(code or '').strip()}"

    def _remember_seen_code(self, source_key: str, code: str, marker: str = "") -> None:
        seen = self._seen_by_source.setdefault(source_key, set())
        if marker:
            seen.add(marker)
        if code:
            seen.add(self._code_marker(code))

    def is_cancelled(self) -> bool:
        return bool(self.cancel_event is not None and self.cancel_event.is_set())

    def _wait_interval(self) -> bool:
        if self.cancel_event is not None:
            return bool(self.cancel_event.wait(self.interval))
        time.sleep(self.interval)
        return False

    def has_backend_for_source(self, source: str) -> bool:
        text = str(source or "").strip()
        if not text:
            return False
        if is_url_source(text):
            return True
        if self.mode in {"auto", "command"} and self.command:
            return True
        return False

    def backend_plan_for_row(self, row: AccountRow) -> dict[str, object]:
        return backend_plan_for_row(row).to_event()

    def last_details_for_source(self, source: str) -> OtpFetchDetails:
        if not source:
            return OtpFetchDetails()
        return self._last_details_by_source.get(secret_hash(source), OtpFetchDetails())

    def last_details_for_row(self, row: AccountRow) -> OtpFetchDetails:
        return self.last_details_for_source(row.otp_source)

    def has_backend_for_row(self, row: AccountRow) -> bool:
        if self.has_backend_for_source(row.otp_source):
            return True
        # Mailbox backends are intentionally routed through row-level methods
        # so future IMAP/Graph/JMAP/POP3/API implementations do not touch the
        # OAuth login protocol code. Returning False today keeps current
        # behavior unchanged until a concrete adapter is implemented.
        _plan = backend_plan_for_row(row)
        return False

    def prime_row(self, row: AccountRow, proxies: Any = None) -> None:
        self.prime_source(row.otp_source, fallback_email=row.login_email, proxies=proxies)

    def prime_source(self, source: str, fallback_email: str = "", proxies: Any = None) -> None:
        if not is_url_source(source):
            return
        source_key = secret_hash(source)
        seen = self._seen_by_source.setdefault(source_key, set())
        try:
            details = fetch_otp_fetch_details_via_url(
                fallback_email,
                source,
                impersonate=self.impersonate,
                verify=self.verify,
                proxies=proxies,
            )
            code, signature = details.code, details.signature
            self._last_details_by_source[source_key] = details
        except Exception:
            code, signature = "", ""
        marker = signature or code
        if marker:
            seen.add(marker)
        if code:
            # Some no-login OTP pages include timestamps/counters in their JSON.
            # In that case the response signature can change while the visible
            # six-digit code is still the stale pre-login code.  Track the code
            # itself as a separate marker so stale codes are not submitted.
            self._remember_seen_code(source_key, code, marker)
            self._primed_code_by_source[source_key] = (code, marker or code)

    def fetch_source_once(self, source: str, fallback_email: str, proxies: Any = None) -> str:
        source_text = str(source or "").strip()
        if is_url_source(source_text):
            details = fetch_otp_fetch_details_via_url(
                fallback_email,
                source_text,
                impersonate=self.impersonate,
                verify=self.verify,
                proxies=proxies,
            )
            code, signature = details.code, details.signature
            source_key = secret_hash(source_text)
            self._last_details_by_source[source_key] = details
            if not code:
                return ""
            seen = self._seen_by_source.setdefault(source_key, set())
            marker = signature or code
            code_marker = self._code_marker(code)
            if marker in seen or code_marker in seen:
                return ""
            self._remember_seen_code(source_key, code, marker)
            return code
        if self.command and self.mode in {"auto", "command"}:
            return fetch_otp_via_command(normalize_email(fallback_email), self.command)
        return ""

    def fetch_row_once(self, row: AccountRow, proxies: Any = None) -> str:
        code = self.fetch_source_once(row.otp_source, row.login_email, proxies=proxies)
        if code:
            return code
        # Future mailbox backend adapters plug in here based on
        # backend_plan_for_row(row). Current release intentionally only
        # executes URL and command backends.
        return ""

    def poll_source(self, source: str, fallback_email: str, proxies: Any = None) -> str:
        if not self.has_backend_for_source(source):
            return ""
        deadline = time.time() + self.timeout
        source_key = secret_hash(source)
        primed_deadline = time.time() + min(45, max(10, self.timeout // 3))
        while time.time() < deadline:
            if self.is_cancelled():
                return ""
            code = self.fetch_source_once(source, fallback_email, proxies=proxies)
            if code:
                return code
            if is_url_source(source) and time.time() >= primed_deadline:
                # Never submit the code observed during priming.  Priming is
                # only a stale-code baseline taken before OpenAI asks for a new
                # email OTP.  Returning it here turns an expected wait into a
                # hard wrong_email_otp_code failure.
                primed = self._primed_code_by_source.pop(source_key, None)
                if primed and primed[0]:
                    self._remember_seen_code(source_key, primed[0], primed[1] or primed[0])
            if self._wait_interval():
                return ""
        return ""

    def poll_row(self, row: AccountRow, proxies: Any = None) -> str:
        if self.has_backend_for_source(row.otp_source):
            return self.poll_source(row.otp_source, row.login_email, proxies=proxies)
        # Future mailbox backends should share the same timeout/interval loop.
        if not self.has_backend_for_row(row):
            return ""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self.is_cancelled():
                return ""
            code = self.fetch_row_once(row, proxies=proxies)
            if code:
                return code
            if self._wait_interval():
                return ""
        return ""
