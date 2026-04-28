import json
import threading
import time

from gpt2json import otp
from gpt2json.models import AccountRow


class FakeResponse:
    def __init__(self, *, url: str, text: str = "", payload=None, status_code: int = 200, content_type: str = "application/json"):
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise json.JSONDecodeError("no json", "", 0)
        return self._payload


def test_extract_otp_ignores_error_trace_digits():
    assert (
        otp.extract_otp_from_json(
            {
                "success": False,
                "details": {"code": "EMAIL_FETCH_FAILED", "trace_id": "trace 123456"},
                "error": "temporary failure",
            }
        )
        == ""
    )


def test_fetch_otp_discovers_no_login_html_api(monkeypatch):
    html = """
    <html><script>
      const currentEmail = "probe@example.com";
      fetch(`/api/public/chatgpt-codes?email=${encodeURIComponent(email)}`, {});
    </script></html>
    """
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/otp-page"):
            return FakeResponse(url=url, text=html, content_type="text/html; charset=utf-8")
        assert url == "https://otp.local/api/public/chatgpt-codes?email=probe%40example.com"
        return FakeResponse(
            url=url,
            payload={"success": True, "latest_code": "123456", "emails": []},
            content_type="application/json",
        )

    monkeypatch.setattr(otp.requests, "get", fake_get)

    details = otp.fetch_otp_fetch_details_via_url("probe@example.com", "https://otp.local/otp-page")

    assert details.code == "123456"
    assert details.backend == "html_api_json"
    assert len(calls) == 2


def test_otp_prime_row_renders_email_placeholder(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(url=url, payload={"success": True, "latest_code": "654321"})

    monkeypatch.setattr(otp.requests, "get", fake_get)

    row = AccountRow(
        line_no=1,
        login_email="probe@example.com",
        password="pass",
        otp_source="https://otp.local/latest?email={email}",
    )
    fetcher = otp.OtpFetcher(timeout=5, interval=1)
    fetcher.prime_row(row)

    assert calls[0][0] == "https://otp.local/latest?email=probe%40example.com"


def test_otp_poll_ignores_primed_code_when_payload_signature_changes(monkeypatch):
    calls = []
    responses = iter(
        [
            otp.OtpFetchDetails(code="111111", signature="old-envelope", backend="json", status_code=200),
            otp.OtpFetchDetails(code="111111", signature="new-envelope-same-code", backend="json", status_code=200),
        ]
    )

    def fake_fetch(email, source, **kwargs):  # noqa: ANN001, ARG001
        calls.append((email, source))
        return next(responses)

    row = AccountRow(
        line_no=1,
        login_email="probe@example.com",
        password="pass",
        otp_source="https://otp.local/latest?email={email}",
    )
    fetcher = otp.OtpFetcher(timeout=30, interval=30)
    monkeypatch.setattr(otp, "fetch_otp_fetch_details_via_url", fake_fetch)
    monkeypatch.setattr(fetcher, "_wait_interval", lambda: True)

    fetcher.prime_row(row)
    assert fetcher.poll_row(row) == ""
    assert len(calls) == 2


def test_otp_poll_accepts_new_code_after_prime(monkeypatch):
    responses = iter(
        [
            otp.OtpFetchDetails(code="111111", signature="old-envelope", backend="json", status_code=200),
            otp.OtpFetchDetails(code="222222", signature="new-envelope-new-code", backend="json", status_code=200),
        ]
    )

    def fake_fetch(email, source, **kwargs):  # noqa: ANN001, ARG001
        return next(responses)

    row = AccountRow(
        line_no=1,
        login_email="probe@example.com",
        password="pass",
        otp_source="https://otp.local/latest?email={email}",
    )
    fetcher = otp.OtpFetcher(timeout=30, interval=30)
    monkeypatch.setattr(otp, "fetch_otp_fetch_details_via_url", fake_fetch)

    fetcher.prime_row(row)
    assert fetcher.poll_row(row) == "222222"


def test_otp_poll_source_cancel_wakes_interval(monkeypatch):
    cancel_event = threading.Event()
    fetcher = otp.OtpFetcher(timeout=30, interval=30, cancel_event=cancel_event)
    monkeypatch.setattr(fetcher, "fetch_source_once", lambda *args, **kwargs: "")

    started = time.monotonic()
    cancel_event.set()
    code = fetcher.poll_source("https://otp.local/latest", "probe@example.com")

    assert code == ""
    assert time.monotonic() - started < 1
