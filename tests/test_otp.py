import json

from gpt2json import otp


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

