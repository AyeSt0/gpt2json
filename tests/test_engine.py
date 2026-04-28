import json
import threading
import zipfile
from pathlib import Path

import pytest

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


class RaisingClient(ProtocolLoginClient):
    def login_and_exchange(self, row, *, otp_fetcher, proxies=None):
        del otp_fetcher, proxies
        if "raise" in row.login_email:
            raise RuntimeError("boom")
        token_json = json.dumps(
            {
                "access_token": "a.b.c",
                "refresh_token": "refresh",
                "account_id": f"acc-{row.line_no}",
                "email": row.login_email,
                "expired": "2026-04-27T00:00:00Z",
            },
            ensure_ascii=False,
        )
        return AttemptResult(row=row, status="success", stage="callback", token_json=token_json)


class MalformedTokenClient(ProtocolLoginClient):
    def login_and_exchange(self, row, *, otp_fetcher, proxies=None):
        del otp_fetcher, proxies
        if "badjson" in row.login_email:
            return AttemptResult(row=row, status="success", stage="callback", token_json="{not-json")
        return AttemptResult(
            row=row,
            status="success",
            stage="callback",
            token_json=json.dumps({"access_token": "a.b.c", "refresh_token": "refresh", "expired": "2026-04-27T00:00:00Z"}),
        )


class FlakyFinalizeClient(ProtocolLoginClient):
    attempts_by_email: dict[str, int] = {}

    def login_and_exchange(self, row, *, otp_fetcher, proxies=None):
        del otp_fetcher, proxies
        attempt = self.attempts_by_email.get(row.login_email, 0) + 1
        self.attempts_by_email[row.login_email] = attempt
        if attempt == 1:
            return AttemptResult(
                row=row,
                status="runtime_error",
                stage="finalize",
                reason="TimeoutError: The read operation timed out",
            )
        token_json = json.dumps(
            {
                "access_token": "a.b.c",
                "refresh_token": "refresh",
                "account_id": f"acc-{row.line_no}",
                "email": row.login_email,
                "expired": "2026-04-27T00:00:00Z",
            },
            ensure_ascii=False,
        )
        return AttemptResult(row=row, status="success", stage="callback", token_json=token_json)


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
    assert summary["cpa_zip"]
    cpa_zip = Path(summary["cpa_zip"])
    assert cpa_zip.exists()
    with zipfile.ZipFile(cpa_zip) as archive:
        assert sorted(archive.namelist()) == ["ok1@example.com.json", "ok2@example.com.json"]
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
    assert summary["cpa_zip"]
    assert len(list((out_dir / "CPA").glob("*.json"))) == 2
    assert (out_dir / "cpa_manifest.json").exists()
    assert Path(summary["cpa_zip"]).exists()
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
    assert summary["cpa_zip"] == ""
    assert summary["sub2api_export"]
    assert not (out_dir / "CPA").exists()
    assert (out_dir / "sub2api_accounts.secret.json").exists()
    assert not (out_dir / "cpa_manifest.json").exists()


def test_run_export_isolates_single_account_runtime_errors(tmp_path: Path):
    out_dir = tmp_path / "out"
    text = "\n".join(
        [
            "ok@example.com----pass----https://otp.local/1",
            "raise@example.com----pass----https://otp.local/2",
            "ok2@example.com----pass----https://otp.local/3",
        ]
    )
    summary = run_export(
        ExportConfig(input_path="missing.txt", out_dir=str(out_dir), input_text=text, concurrency=3),
        client_factory=lambda: RaisingClient(),
    )

    assert summary["success_count"] == 2
    assert summary["failure_count"] == 1
    safe_rows = [json.loads(line) for line in (out_dir / "results.safe.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sorted(row["status"] for row in safe_rows) == ["runtime_error", "success", "success"]
    assert sorted(row["row_index"] for row in safe_rows) == [1, 2, 3]
    assert summary["failure_report"]
    report = json.loads(Path(summary["failure_report"]).read_text(encoding="utf-8"))
    assert report["count"] == 1
    assert report["failures"][0]["login_masked"] == "ra***@example.com"
    assert "suggestion" in report["failures"][0]
    assert (out_dir / "sub2api_accounts.secret.json").exists()


def test_run_export_marks_malformed_success_token_as_failure(tmp_path: Path):
    out_dir = tmp_path / "out"
    text = "\n".join(
        [
            "ok@example.com----pass----https://otp.local/1",
            "badjson@example.com----pass----https://otp.local/2",
        ]
    )
    summary = run_export(
        ExportConfig(input_path="missing.txt", out_dir=str(out_dir), input_text=text, concurrency=2),
        client_factory=lambda: MalformedTokenClient(),
    )

    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    safe_rows = [json.loads(line) for line in (out_dir / "results.safe.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["status"] for row in safe_rows} == {"success", "export_prepare_error"}
    assert len(list((out_dir / "CPA").glob("*.json"))) == 1


def test_run_export_retries_transient_finalize_timeout(tmp_path: Path):
    out_dir = tmp_path / "out"
    FlakyFinalizeClient.attempts_by_email = {}
    events = []
    summary = run_export(
        ExportConfig(
            input_path="missing.txt",
            out_dir=str(out_dir),
            input_text="ok@example.com----pass----https://otp.local/1",
            concurrency=1,
            max_attempts=2,
        ),
        client_factory=lambda: FlakyFinalizeClient(),
        on_event=events.append,
    )

    assert summary["success_count"] == 1
    assert summary["failure_count"] == 0
    assert FlakyFinalizeClient.attempts_by_email["ok@example.com"] == 2
    assert any(event.get("type") == "row_retry" for event in events)
    safe_rows = [json.loads(line) for line in (out_dir / "results.safe.jsonl").read_text(encoding="utf-8").splitlines()]
    assert safe_rows[0]["status"] == "success"
    assert safe_rows[0]["attempt"] == 2
    assert summary["retry_count"] == 1
    assert summary["failure_report"] == ""


def test_run_export_cleans_previous_generated_artifacts(tmp_path: Path):
    out_dir = tmp_path / "out"
    (out_dir / "CPA").mkdir(parents=True)
    (out_dir / "CPA" / "stale@example.com.json").write_text("{}", encoding="utf-8")
    (out_dir / "sub_accounts").mkdir(parents=True)
    (out_dir / "sub_accounts" / "sub_stale.json").write_text("{}", encoding="utf-8")
    (out_dir / "cpa_tokens_stale.zip").write_text("old", encoding="utf-8")
    (out_dir / "results.safe.jsonl").write_text('{"status":"old"}\n', encoding="utf-8")
    (out_dir / "summary.json").write_text("{}", encoding="utf-8")

    summary = run_export(
        ExportConfig(input_path="missing.txt", out_dir=str(out_dir), input_text=account_text(), concurrency=3),
        client_factory=lambda: FakeClient(),
    )

    assert summary["success_count"] == 2
    assert not (out_dir / "CPA" / "stale@example.com.json").exists()
    assert not (out_dir / "sub_accounts").exists()
    assert not (out_dir / "cpa_tokens_stale.zip").exists()
    safe_rows = (out_dir / "results.safe.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(safe_rows) == 3
    assert all("old" not in row for row in safe_rows)


def test_run_export_keeps_previous_artifacts_when_input_load_fails(tmp_path: Path):
    out_dir = tmp_path / "out"
    (out_dir / "CPA").mkdir(parents=True)
    stale = out_dir / "CPA" / "stale@example.com.json"
    stale.write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        run_export(ExportConfig(input_path=str(tmp_path / "missing.txt"), out_dir=str(out_dir)))

    assert stale.exists()


def test_run_export_reports_cancelled_rows_without_outputs(tmp_path: Path):
    out_dir = tmp_path / "out"
    cancel_event = threading.Event()
    cancel_event.set()

    summary = run_export(
        ExportConfig(input_path="missing.txt", out_dir=str(out_dir), input_text=account_text(), concurrency=3),
        client_factory=lambda: FakeClient(),
        cancel_event=cancel_event,
    )

    assert summary["cancelled"] is True
    assert summary["success_count"] == 0
    assert summary["failure_count"] == 3
    assert summary["cancelled_count"] == 3
    safe_rows = [json.loads(line) for line in (out_dir / "results.safe.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["status"] for row in safe_rows} == {"cancelled"}
    assert not (out_dir / "sub2api_accounts.secret.json").exists()
    assert not (out_dir / "CPA").exists()


def test_resolve_concurrency_auto_caps_at_eight():
    assert resolve_concurrency(0, 0) == 1
    assert resolve_concurrency(0, 3) == 3
    assert resolve_concurrency(0, 20) == 8
    assert resolve_concurrency(5, 20) == 5
    assert resolve_concurrency(128, 20) == 128


