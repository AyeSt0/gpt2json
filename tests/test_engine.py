import json
from pathlib import Path

from gpt2json.engine import ExportConfig, resolve_concurrency, run_export
from gpt2json.models import AttemptResult
from gpt2json.protocol import ProtocolLoginClient


class FakeClient(ProtocolLoginClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def login_and_exchange(self, row, *, otp_fetcher, proxies=None):
        del otp_fetcher, proxies
        if "ok" in row.login_email:
            token_json = json.dumps(
                {
                    "access_token": "a.b.c",
                    "refresh_token": "refresh",
                    "account_id": f"acc-{row.line_no}",
                    "email": row.login_email,
                    "type": "plus",
                    "expired": "2026-04-27T00:00:00Z",
                },
                ensure_ascii=False,
            )
            return AttemptResult(row=row, status="success", stage="callback", token_json=token_json)
        return AttemptResult(row=row, status="bad_password", stage="password_verify", reason="bad_password")


def account_text() -> str:
    return "\n".join(
        [
            "ok1@example.com----pass----https://otp.local/1",
            "bad@example.com----pass----https://otp.local/2",
            "ok2@example.com----pass----https://otp.local/3",
        ]
    )


def test_run_export_writes_cpa_and_sub2api(tmp_path: Path):
    input_path = tmp_path / "accounts.txt"
    input_path.write_text(account_text(), encoding="utf-8")
    out_dir = tmp_path / "out"
    summary = run_export(
        ExportConfig(input_path=str(input_path), out_dir=str(out_dir), concurrency=3),
        client_factory=lambda: FakeClient(),
    )
    assert summary["success_count"] == 2
    assert summary["cpa_dir"]
    assert (out_dir / "cpa_manifest.json").exists()
    assert (out_dir / "sub2api_accounts.secret.json").exists()
    cpa_files = sorted((out_dir / "CPA").glob("*.json"))
    assert len(cpa_files) == 2
    assert {item.name for item in cpa_files} == {"ok1@example.com.json", "ok2@example.com.json"}
    assert json.loads(cpa_files[0].read_text(encoding="utf-8"))["access_token"] == "a.b.c"
    assert json.loads(cpa_files[0].read_text(encoding="utf-8"))["type"] == "codex"
    sub_payload = json.loads((out_dir / "sub2api_accounts.secret.json").read_text(encoding="utf-8"))
    assert set(sub_payload) == {"proxies", "accounts"}
    assert sub_payload["accounts"][0]["credentials"]["client_id"]
    assert sub_payload["accounts"][0]["credentials"]["expires_in"] == 863999
    manifest = json.loads((out_dir / "cpa_manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 2
    assert manifest["format"] == "cpa-per-account-json"
    assert len(manifest["files"]) == 2
    assert "accounts" not in manifest


def test_run_export_accepts_pasted_input_and_auto_concurrency(tmp_path: Path):
    out_dir = tmp_path / "out"
    summary = run_export(
        ExportConfig(input_path="missing.txt", out_dir=str(out_dir), input_text=account_text(), concurrency=0),
        client_factory=lambda: FakeClient(),
    )
    assert summary["input"] == "paste"
    assert summary["concurrency"] == 3
    assert summary["concurrency_mode"] == "auto"
    assert summary["success_count"] == 2


def test_run_export_cpa_only(tmp_path: Path):
    out_dir = tmp_path / "out"
    summary = run_export(
        ExportConfig(
            input_path="missing.txt",
            out_dir=str(out_dir),
            input_text=account_text(),
            export_sub2api=False,
            export_cpa=True,
        ),
        client_factory=lambda: FakeClient(),
    )
    assert summary["sub2api_export"] == ""
    assert summary["cpa_dir"]
    assert summary["cpa_manifest"]
    assert len(list((out_dir / "CPA").glob("*.json"))) == 2
    assert (out_dir / "cpa_manifest.json").exists()
    assert not (out_dir / "sub2api_accounts.secret.json").exists()


def test_run_export_sub2api_only(tmp_path: Path):
    out_dir = tmp_path / "out"
    summary = run_export(
        ExportConfig(
            input_path="missing.txt",
            out_dir=str(out_dir),
            input_text=account_text(),
            export_sub2api=True,
            export_cpa=False,
        ),
        client_factory=lambda: FakeClient(),
    )
    assert summary["cpa_dir"] == ""
    assert summary["cpa_manifest"] == ""
    assert summary["sub2api_export"]
    assert not (out_dir / "CPA").exists()
    assert (out_dir / "sub2api_accounts.secret.json").exists()
    assert not (out_dir / "cpa_manifest.json").exists()


def test_resolve_concurrency_auto_caps_at_eight():
    assert resolve_concurrency(0, 0) == 1
    assert resolve_concurrency(0, 3) == 3
    assert resolve_concurrency(0, 20) == 8
    assert resolve_concurrency(5, 20) == 5


