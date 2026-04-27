from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.parse
from typing import Any

from curl_cffi import requests

from .mail_providers import mailbox_context_from_row, provider_plan_for_row
from .models import AccountRow
from .parsing import is_url_source, normalize_email, secret_hash


OTP_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


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

    for key in ("code", "otp", "oai_code", "verification_code", "verificationCode", "pin"):
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
    impersonate: str = "chrome124",
    verify: bool = True,
    proxies: Any = None,
) -> tuple[str, str]:
    url = render_otp_url(email, url_template)
    if not url:
        return "", ""
    response = requests.get(
        url,
        headers={"accept": "application/json,text/plain,*/*"},
        impersonate=impersonate,
        proxies=proxies,
        verify=verify,
        timeout=timeout,
    )
    payload = _json_response(response)
    if payload is not None:
        code = extract_otp_from_json(payload)
        if code:
            return code, _canonical_hash(payload)
    text = getattr(response, "text", "") or ""
    code = extract_otp_from_text(text)
    return code, secret_hash(text) if code or text else ""


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
        impersonate: str = "chrome124",
        verify: bool = True,
    ) -> None:
        self.mode = str(mode or "auto").strip().lower()
        self.command = str(command or "").strip()
        self.timeout = max(5, int(timeout or 180))
        self.interval = max(1, int(interval or 3))
        self.impersonate = str(impersonate or "chrome124").strip() or "chrome124"
        self.verify = bool(verify)
        self._seen_by_source: dict[str, set[str]] = {}
        self._primed_code_by_source: dict[str, tuple[str, str]] = {}

    def has_backend_for_source(self, source: str) -> bool:
        text = str(source or "").strip()
        if not text:
            return False
        if is_url_source(text):
            return True
        if self.mode in {"auto", "command"} and self.command:
            return True
        return False

    def provider_plan_for_row(self, row: AccountRow) -> dict[str, object]:
        return provider_plan_for_row(row)

    def has_backend_for_row(self, row: AccountRow) -> bool:
        if self.has_backend_for_source(row.otp_source):
            return True
        # Mailbox provider adapters are intentionally routed through row-level
        # methods so future IMAP/Graph/JMAP/provider-API backends do not touch the
        # OAuth login protocol code. Returning False today keeps current
        # behavior unchanged until a concrete adapter is implemented.
        _context = mailbox_context_from_row(row)
        return False

    def prime_row(self, row: AccountRow, proxies: Any = None) -> None:
        self.prime_source(row.otp_source, proxies=proxies)

    def prime_source(self, source: str, proxies: Any = None) -> None:
        if not is_url_source(source):
            return
        source_key = secret_hash(source)
        seen = self._seen_by_source.setdefault(source_key, set())
        try:
            code, signature = fetch_otp_details_via_url(
                "",
                source,
                impersonate=self.impersonate,
                verify=self.verify,
                proxies=proxies,
            )
        except Exception:
            code, signature = "", ""
        marker = signature or code
        if marker:
            seen.add(marker)
        if code:
            self._primed_code_by_source[source_key] = (code, marker or code)

    def fetch_source_once(self, source: str, fallback_email: str, proxies: Any = None) -> str:
        source_text = str(source or "").strip()
        if is_url_source(source_text):
            code, signature = fetch_otp_details_via_url(
                fallback_email,
                source_text,
                impersonate=self.impersonate,
                verify=self.verify,
                proxies=proxies,
            )
            if not code:
                return ""
            source_key = secret_hash(source_text)
            seen = self._seen_by_source.setdefault(source_key, set())
            marker = signature or code
            if marker in seen:
                return ""
            seen.add(marker)
            return code
        if self.command and self.mode in {"auto", "command"}:
            return fetch_otp_via_command(normalize_email(fallback_email), self.command)
        return ""

    def fetch_row_once(self, row: AccountRow, proxies: Any = None) -> str:
        code = self.fetch_source_once(row.otp_source, row.login_email, proxies=proxies)
        if code:
            return code
        # Future mailbox provider adapters plug in here based on
        # mailbox_context_from_row(row). Current release intentionally only
        # executes URL and command backends.
        return ""

    def poll_source(self, source: str, fallback_email: str, proxies: Any = None) -> str:
        if not self.has_backend_for_source(source):
            return ""
        deadline = time.time() + self.timeout
        source_key = secret_hash(source)
        primed_deadline = time.time() + min(45, max(10, self.timeout // 3))
        while time.time() < deadline:
            code = self.fetch_source_once(source, fallback_email, proxies=proxies)
            if code:
                return code
            if is_url_source(source) and time.time() >= primed_deadline:
                primed = self._primed_code_by_source.pop(source_key, None)
                if primed and primed[0]:
                    seen = self._seen_by_source.setdefault(source_key, set())
                    seen.add(primed[1] or primed[0])
                    return primed[0]
            time.sleep(self.interval)
        return ""

    def poll_row(self, row: AccountRow, proxies: Any = None) -> str:
        if self.has_backend_for_source(row.otp_source):
            return self.poll_source(row.otp_source, row.login_email, proxies=proxies)
        # Future provider backends should share the same timeout/interval loop.
        if not self.has_backend_for_row(row):
            return ""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            code = self.fetch_row_once(row, proxies=proxies)
            if code:
                return code
            time.sleep(self.interval)
        return ""
