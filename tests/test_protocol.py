import json
from types import SimpleNamespace

from gpt2json.models import AccountRow
from gpt2json.protocol import ProtocolLoginClient


class FakeResponse:
    def __init__(self, *, status_code=200, payload=None, text="", headers=None, url="https://auth.openai.com/"):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload, ensure_ascii=False)
        self.headers = headers or {}
        self.url = url

    def json(self):
        return self._payload


class FakeOtpFetcher:
    def prime_row(self, row, *, proxies=None):
        del row, proxies

    def backend_plan_for_row(self, row):
        del row
        return {
            "source_kind": "url",
            "provider": "no_login_url",
            "display_name": "No-login OTP URL",
            "primary_backend": "http_url",
            "planned_backends": ["http_url"],
            "backend_candidates": [],
        }

    def poll_row(self, row, *, proxies=None):
        del row, proxies
        return "123456"

    def last_details_for_row(self, row):
        del row
        return SimpleNamespace(backend="json", status_code=200, signature="sig-new")


def account_row() -> AccountRow:
    return AccountRow(
        line_no=1,
        login_email="user@example.com",
        password="correct-password",
        otp_source="https://otp.local/latest",
        raw_line="user@example.com----correct-password----https://otp.local/latest",
    )


def test_protocol_uses_flow_specific_sentinel_for_password(monkeypatch):
    client = ProtocolLoginClient()
    flows = []
    posts = []

    def fake_request(session, method, url, **kwargs):
        del method, kwargs
        session.cookies.set("oai-did", "did-123", domain="auth.openai.com")
        return FakeResponse(status_code=200, url=url)

    def fake_sentinel(did, *, proxies=None, flow="authorize_continue"):
        del proxies
        flows.append((did, flow))
        return f"sentinel-{flow}"

    def fake_post(session, url, *, headers, proxies=None, json_body=None, data=None, timeout=None, retries=2):
        del session, proxies, data, timeout, retries
        posts.append((url, headers, json_body))
        if url.endswith("/authorize/continue"):
            return FakeResponse(
                payload={"page": {"type": "login_password"}, "continue_url": "https://auth.openai.com/log-in/password"}
            )
        if url.endswith("/password/verify"):
            return FakeResponse(payload={"page": {"type": "consent"}, "continue_url": "https://auth.openai.com/consent"})
        raise AssertionError(f"unexpected post {url}")

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "request_authorize_continue_sentinel", fake_sentinel)
    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    monkeypatch.setattr(client, "_finalize_transition", lambda *args, **kwargs: ('{"access_token":"a.b.c","refresh_token":"r"}', "", kwargs["transition"]))

    result = client.login_and_exchange(account_row(), otp_fetcher=FakeOtpFetcher())

    assert result.ok
    assert flows == [("did-123", "authorize_continue"), ("did-123", "password_verify")]
    password_post = next(item for item in posts if item[0].endswith("/password/verify"))
    assert password_post[1]["openai-sentinel-token"] == "sentinel-password_verify"
    assert password_post[1]["oai-device-id"] == "did-123"
    assert password_post[2] == {"password": "correct-password"}


def test_protocol_uses_flow_specific_sentinel_for_email_otp(monkeypatch):
    client = ProtocolLoginClient()
    flows = []
    posts = []

    def fake_request(session, method, url, **kwargs):
        del method, kwargs
        session.cookies.set("oai-did", "did-otp", domain="auth.openai.com")
        return FakeResponse(status_code=200, url=url)

    def fake_sentinel(did, *, proxies=None, flow="authorize_continue"):
        del proxies
        flows.append((did, flow))
        return f"sentinel-{flow}"

    def fake_post(session, url, *, headers, proxies=None, json_body=None, data=None, timeout=None, retries=2):
        del session, proxies, data, timeout, retries
        posts.append((url, headers, json_body))
        if url.endswith("/authorize/continue"):
            return FakeResponse(
                payload={"page": {"type": "login_password"}, "continue_url": "https://auth.openai.com/log-in/password"}
            )
        if url.endswith("/password/verify"):
            return FakeResponse(
                payload={"page": {"type": "email_otp_verification"}, "continue_url": "https://auth.openai.com/email-verification"}
            )
        if url.endswith("/email-otp/validate"):
            return FakeResponse(payload={"page": {"type": "consent"}, "continue_url": "https://auth.openai.com/consent"})
        raise AssertionError(f"unexpected post {url}")

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "request_authorize_continue_sentinel", fake_sentinel)
    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    monkeypatch.setattr(client, "_finalize_transition", lambda *args, **kwargs: ('{"access_token":"a.b.c","refresh_token":"r"}', "", kwargs["transition"]))

    result = client.login_and_exchange(account_row(), otp_fetcher=FakeOtpFetcher())

    assert result.ok
    assert flows == [
        ("did-otp", "authorize_continue"),
        ("did-otp", "password_verify"),
        ("did-otp", "email_otp_validate"),
    ]
    otp_post = next(item for item in posts if item[0].endswith("/email-otp/validate"))
    assert otp_post[1]["openai-sentinel-token"] == "sentinel-email_otp_validate"
    assert otp_post[1]["oai-device-id"] == "did-otp"
    assert otp_post[2] == {"code": "123456"}
