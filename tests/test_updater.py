from __future__ import annotations

import json
import urllib.error

from gpt2json import updater


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_version_compare() -> None:
    assert updater.is_newer_version("v0.2.0", "0.1.9")
    assert updater.is_newer_version("1.0.0", "1.0.0-rc.1")
    assert not updater.is_newer_version("v0.1.0", "0.1.0")
    assert not updater.is_newer_version("0.9.9", "1.0.0")


def test_check_latest_release_available(monkeypatch) -> None:
    def fake_urlopen(req, timeout=0):  # noqa: ANN001
        assert "api.github.com" in req.full_url
        assert timeout == 6
        return FakeResponse(
            {
                "tag_name": "v0.2.0",
                "name": "GPT2JSON v0.2.0",
                "html_url": "https://github.com/AyeSt0/gpt2json/releases/tag/v0.2.0",
                "published_at": "2026-04-28T00:00:00Z",
                "assets": [{"name": "GPT2JSON-windows-x64.zip"}],
            }
        )

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)

    info = updater.check_latest_release("0.1.0")

    assert info.has_release
    assert info.update_available
    assert info.latest_version == "0.2.0"
    assert info.assets == ("GPT2JSON-windows-x64.zip",)


def test_check_latest_release_not_found(monkeypatch) -> None:
    def fake_urlopen(req, timeout=0):  # noqa: ANN001, ARG001
        raise urllib.error.HTTPError(updater.RELEASES_API_URL, 404, "Not Found", None, None)

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)

    info = updater.check_latest_release("0.1.0")

    assert not info.has_release
    assert not info.update_available
    assert "Release" in info.error
