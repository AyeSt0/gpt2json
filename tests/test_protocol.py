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


def test_protocol_repairs_password_verify_state_once(monkeypatch):
    client = ProtocolLoginClient()
    flows = []
    password_posts = []

    def fake_request(session, method, url, **kwargs):
        del method, kwargs
        session.cookies.set("oai-did", "did-repair", domain="auth.openai.com")
        return FakeResponse(status_code=200, url=url)

    def fake_sentinel(did, *, proxies=None, flow="authorize_continue"):
        del proxies
        flows.append((did, flow))
        return f"sentinel-{flow}-{len(flows)}"

    def fake_post(session, url, *, headers, proxies=None, json_body=None, data=None, timeout=None, retries=2):
        del session, headers, proxies, data, timeout, retries
        if url.endswith("/authorize/continue"):
            return FakeResponse(
                payload={"page": {"type": "login_password"}, "continue_url": "https://auth.openai.com/log-in/password"}
            )
        if url.endswith("/password/verify"):
            password_posts.append(json_body)
            if len(password_posts) == 1:
                return FakeResponse(status_code=401, payload={"error": {"code": "invalid_username_or_password"}})
            return FakeResponse(payload={"page": {"type": "consent"}, "continue_url": "https://auth.openai.com/consent"})
        raise AssertionError(f"unexpected post {url}")

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "request_authorize_continue_sentinel", fake_sentinel)
    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    monkeypatch.setattr(client, "_finalize_transition", lambda *args, **kwargs: ('{"access_token":"a.b.c","refresh_token":"r"}', "", kwargs["transition"]))

    result = client.login_and_exchange(account_row(), otp_fetcher=FakeOtpFetcher())

    assert result.ok
    assert result.meta["password_repair_attempted"] is True
    assert len(password_posts) == 2
    assert flows == [
        ("did-repair", "authorize_continue"),
        ("did-repair", "password_verify"),
        ("did-repair", "password_verify"),
    ]
    assert any(event["stage"] == "password_verify_repair_result" and event["status_code"] == 200 for event in result.events)


def test_protocol_repairs_email_otp_validate_state_once(monkeypatch):
    client = ProtocolLoginClient()
    flows = []
    otp_posts = []

    def fake_request(session, method, url, **kwargs):
        del method, kwargs
        session.cookies.set("oai-did", "did-otp-repair", domain="auth.openai.com")
        return FakeResponse(status_code=200, url=url)

    def fake_sentinel(did, *, proxies=None, flow="authorize_continue"):
        del proxies
        flows.append((did, flow))
        return f"sentinel-{flow}-{len(flows)}"

    def fake_post(session, url, *, headers, proxies=None, json_body=None, data=None, timeout=None, retries=2):
        del session, headers, proxies, data, timeout, retries
        if url.endswith("/authorize/continue"):
            return FakeResponse(
                payload={"page": {"type": "login_password"}, "continue_url": "https://auth.openai.com/log-in/password"}
            )
        if url.endswith("/password/verify"):
            return FakeResponse(
                payload={"page": {"type": "email_otp_verification"}, "continue_url": "https://auth.openai.com/email-verification"}
            )
        if url.endswith("/email-otp/validate"):
            otp_posts.append(json_body)
            if len(otp_posts) == 1:
                return FakeResponse(status_code=400, payload={"error": {"code": "invalid_auth_step"}})
            return FakeResponse(payload={"page": {"type": "consent"}, "continue_url": "https://auth.openai.com/consent"})
        raise AssertionError(f"unexpected post {url}")

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "request_authorize_continue_sentinel", fake_sentinel)
    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    monkeypatch.setattr(client, "_finalize_transition", lambda *args, **kwargs: ('{"access_token":"a.b.c","refresh_token":"r"}', "", kwargs["transition"]))

    result = client.login_and_exchange(account_row(), otp_fetcher=FakeOtpFetcher())

    assert result.ok
    assert result.meta["otp_validate_repair_attempted"] is True
    assert len(otp_posts) == 2
    assert flows == [
        ("did-otp-repair", "authorize_continue"),
        ("did-otp-repair", "password_verify"),
        ("did-otp-repair", "email_otp_validate"),
        ("did-otp-repair", "email_otp_validate"),
    ]
    assert any(event["stage"] == "email_otp_validate_repair_result" and event["status_code"] == 200 for event in result.events)


def test_protocol_retries_finalize_inside_current_session(monkeypatch):
    client = ProtocolLoginClient(timeout=10)
    events = []
    password_posts = []
    finalize_calls = []

    client.event_callback = lambda event: events.append(event)

    def fake_request(session, method, url, **kwargs):
        del method, kwargs
        session.cookies.set("oai-did", "did-finalize", domain="auth.openai.com")
        return FakeResponse(status_code=200, url=url)

    def fake_sentinel(did, *, proxies=None, flow="authorize_continue"):
        del proxies
        return f"sentinel-{did}-{flow}"

    def fake_post(session, url, *, headers, proxies=None, json_body=None, data=None, timeout=None, retries=2):
        del session, headers, proxies, data, timeout, retries
        if url.endswith("/authorize/continue"):
            return FakeResponse(
                payload={"page": {"type": "login_password"}, "continue_url": "https://auth.openai.com/log-in/password"}
            )
        if url.endswith("/password/verify"):
            password_posts.append(json_body)
            return FakeResponse(payload={"page": {"type": "consent"}, "continue_url": "https://auth.openai.com/consent"})
        raise AssertionError(f"unexpected post {url}")

    def fake_finalize(*args, **kwargs):
        del args, kwargs
        finalize_calls.append(1)
        if len(finalize_calls) == 1:
            raise TimeoutError("The read operation timed out")
        return '{"access_token":"a.b.c","refresh_token":"r"}', "", {"page_type": "consent", "continue_url": ""}

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "request_authorize_continue_sentinel", fake_sentinel)
    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    monkeypatch.setattr(client, "_finalize_transition", fake_finalize)
    monkeypatch.setattr(client, "_local_retry_sleep", lambda _attempt: None)

    result = client.login_and_exchange(account_row(), otp_fetcher=FakeOtpFetcher())

    assert result.ok
    assert len(password_posts) == 1
    assert len(finalize_calls) == 2
    assert result.meta["finalize_local_attempt"] == 2
    assert any(event["stage"] == "finalize_retry" for event in result.events)
    assert any(event["stage"] == "finalize_retry" for event in events)


def test_protocol_refetches_otp_without_restarting_login(monkeypatch):
    client = ProtocolLoginClient(timeout=10)
    password_posts = []
    otp_codes = []
    resend_posts = []

    class RefetchOtpFetcher(FakeOtpFetcher):
        def __init__(self):
            self.codes = ["111111", "222222"]
            self.last_code = ""

        def poll_row(self, row, *, proxies=None):
            del row, proxies
            self.last_code = self.codes.pop(0)
            return self.last_code

        def last_details_for_row(self, row):
            del row
            return SimpleNamespace(backend="json", status_code=200, signature=f"sig-{self.last_code}")

    def fake_request(session, method, url, **kwargs):
        del method, kwargs
        session.cookies.set("oai-did", "did-refetch", domain="auth.openai.com")
        return FakeResponse(status_code=200, url=url)

    def fake_sentinel(did, *, proxies=None, flow="authorize_continue"):
        del proxies
        return f"sentinel-{did}-{flow}"

    def fake_post(session, url, *, headers, proxies=None, json_body=None, data=None, timeout=None, retries=2):
        del session, headers, proxies, data, timeout, retries
        if url.endswith("/authorize/continue"):
            return FakeResponse(
                payload={"page": {"type": "login_password"}, "continue_url": "https://auth.openai.com/log-in/password"}
            )
        if url.endswith("/password/verify"):
            password_posts.append(json_body)
            return FakeResponse(
                payload={"page": {"type": "email_otp_verification"}, "continue_url": "https://auth.openai.com/email-verification"}
            )
        if url.endswith("/email-otp/send"):
            resend_posts.append(json_body)
            return FakeResponse(
                payload={"page": {"type": "email_otp_verification"}, "continue_url": "https://auth.openai.com/email-verification"}
            )
        if url.endswith("/email-otp/validate"):
            otp_codes.append(json_body["code"])
            if len(otp_codes) == 1:
                return FakeResponse(status_code=401, payload={"error": {"code": "wrong_email_otp_code"}})
            return FakeResponse(payload={"page": {"type": "consent"}, "continue_url": "https://auth.openai.com/consent"})
        raise AssertionError(f"unexpected post {url}")

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "request_authorize_continue_sentinel", fake_sentinel)
    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    monkeypatch.setattr(client, "_finalize_transition", lambda *args, **kwargs: ('{"access_token":"a.b.c","refresh_token":"r"}', "", kwargs["transition"]))

    result = client.login_and_exchange(account_row(), otp_fetcher=RefetchOtpFetcher())

    assert result.ok
    assert len(password_posts) == 1
    assert otp_codes == ["111111", "222222"]
    assert resend_posts == [{}]
    assert result.meta["otp_refetch_attempted"] == 1
    assert any(event["stage"] == "otp_refetch" for event in result.events)
    assert any(event["stage"] == "email_otp_resend" and event["status_code"] == 200 for event in result.events)
