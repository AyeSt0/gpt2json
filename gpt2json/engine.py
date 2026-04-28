from __future__ import annotations

import json
import shutil
import threading
import time
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .formats import build_cpa_token_json, build_export, convert_current_token_to_sub, write_json
from .models import AttemptResult, utc_now_iso
from .otp import OtpFetcher
from .parsing import mask_email, mask_source, parse_by_format, read_account_file, secret_hash
from .protocol import DEFAULT_IMPERSONATE, ProtocolLoginClient

Logger = Callable[[str], None]
EventCallback = Callable[[dict[str, Any]], None]


@dataclass
class ExportConfig:
    input_path: str
    out_dir: str
    input_text: str = ""
    concurrency: int = 0
    pool: str = ""
    token_type: str = "plus"
    export_sub2api: bool = True
    export_cpa: bool = True
    otp_mode: str = "auto"
    otp_command: str = ""
    otp_timeout: int = 180
    otp_interval: int = 3
    timeout: int = 30
    verify_ssl: bool = True
    impersonate: str = DEFAULT_IMPERSONATE
    input_format: str = "auto"


def resolve_concurrency(requested: int, row_count: int) -> int:
    requested_int = int(requested or 0)
    if requested_int <= 0:
        return min(8, max(1, int(row_count or 1)))
    return max(1, requested_int)


def _load_rows(config: ExportConfig) -> tuple[list[Any], str]:
    inline_text = str(config.input_text or "")
    if str(config.input_path or "") == "<stdin>":
        return parse_by_format(inline_text.splitlines(), format_id=config.input_format), "stdin"
    if inline_text.strip():
        return parse_by_format(inline_text.splitlines(), format_id=config.input_format), "paste"
    return read_account_file(config.input_path, format_id=config.input_format), str(config.input_path)


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_compact_json(payload) + "\n")


def _reset_generated_artifacts(out_dir: Path) -> None:
    """Make each export run produce a clean, self-consistent result set.

    The GUI exposes the selected output directory as "the current export".
    Without cleanup, re-running into the same directory can leave stale CPA
    files or stale JSONL rows next to the new summary, which is easy to import
    by mistake.  Only known GPT2JSON-generated children are removed.
    """

    resolved_out = out_dir.resolve()
    generated_files = (
        "sub2api_accounts.secret.json",
        "cpa_manifest.json",
        "summary.json",
        "progress.json",
        "results.safe.jsonl",
    )
    generated_globs = ("cpa_tokens_*.zip",)
    generated_dirs = ("CPA", "sub_accounts")
    for name in generated_files:
        target = (out_dir / name).resolve()
        if target.parent == resolved_out and target.exists() and target.is_file():
            target.unlink()
    for pattern in generated_globs:
        for child in out_dir.glob(pattern):
            target = child.resolve()
            if target.parent == resolved_out and target.exists() and target.is_file():
                target.unlink()
    for name in generated_dirs:
        target = (out_dir / name).resolve()
        if target.parent == resolved_out and target.exists() and target.is_dir():
            shutil.rmtree(target)


def _exception_result(row: Any, *, status: str, stage: str, exc: BaseException) -> AttemptResult:
    reason = f"{type(exc).__name__}: {str(exc)[:240]}"
    return AttemptResult(
        row=row,
        status=status,
        stage=stage,
        reason=reason,
        events=[{"stage": stage, "reason": reason}],
    )


def _prepare_token_data(token_json: str, *, pool: str, token_type: str, fallback_email: str = "") -> dict[str, Any]:
    data = json.loads(token_json)
    if not isinstance(data, dict):
        raise ValueError("token_json top-level is not an object")
    data.setdefault("source", "gpt2json")
    if fallback_email and not str(data.get("email") or "").strip():
        data["email"] = fallback_email
    if pool:
        data.setdefault("pool", pool)
    if token_type:
        data.setdefault("type", token_type)
    return data


def _build_sub_account(token_payload: dict[str, Any], *, pool: str, index: int) -> dict[str, Any]:
    account = convert_current_token_to_sub(token_payload, index=index)
    email = str((account.get("extra") or {}).get("email") or token_payload.get("email") or "").strip()
    if pool and email:
        account["name"] = f"{pool}-{email}"
    return account


def _run_timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _safe_result_row(result: AttemptResult) -> dict[str, Any]:
    return {
        "line_no": result.row.line_no,
        "email_hash": secret_hash(result.row.login_email),
        "login_masked": mask_email(result.row.login_email),
        "otp_source_masked": mask_source(result.row.otp_source),
        "status": result.status,
        "stage": result.stage,
        "otp_required": bool(result.otp_required),
        "reason": result.reason,
        "events": result.events[-8:],
        "started_at": result.started_at,
        "finished_at": result.finished_at,
    }


def run_export(
    config: ExportConfig,
    *,
    logger: Logger | None = None,
    on_event: EventCallback | None = None,
    client_factory: Callable[[], ProtocolLoginClient] | None = None,
) -> dict[str, Any]:
    log = logger or (lambda _text: None)
    emit = on_event or (lambda _event: None)
    out_dir = Path(config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, input_source = _load_rows(config)
    export_sub2api = bool(config.export_sub2api)
    export_cpa = bool(config.export_cpa)
    if not (export_sub2api or export_cpa):
        raise ValueError("at least one export format must be selected")
    _reset_generated_artifacts(out_dir)
    concurrency = resolve_concurrency(config.concurrency, len(rows))
    summary: dict[str, Any] = {
        "started_at": utc_now_iso(),
        "input": input_source,
        "out_dir": str(out_dir),
        "row_count": len(rows),
        "concurrency": concurrency,
        "concurrency_mode": "auto" if int(config.concurrency or 0) <= 0 else "manual",
        "pool": config.pool,
        "token_type": config.token_type,
        "export_sub2api": export_sub2api,
        "export_cpa": export_cpa,
        "otp_mode": config.otp_mode,
        "input_format": config.input_format,
    }
    write_json(out_dir / "progress.json", summary)
    emit(
        {
            "type": "started",
            "total": len(rows),
            "out_dir": str(out_dir),
            "concurrency": concurrency,
        }
    )
    if not rows:
        summary["finished_at"] = utc_now_iso()
        summary["success_count"] = 0
        summary["error"] = "no_valid_rows"
        write_json(out_dir / "summary.json", summary)
        emit({"type": "finished", "summary": summary})
        return summary

    lock = threading.Lock()
    results: list[AttemptResult] = []
    successes: list[dict[str, Any]] = []
    run_stamp = _run_timestamp()

    def run_one(row: Any) -> AttemptResult:
        emit({"type": "row_start", "line_no": row.line_no, "email_masked": mask_email(row.login_email)})

        def emit_stage(event: dict[str, Any]) -> None:
            payload = {
                "type": "row_stage",
                "line_no": row.line_no,
                "email_masked": mask_email(row.login_email),
            }
            payload.update(event)
            emit(payload)

        try:
            client = (
                client_factory()
                if client_factory is not None
                else ProtocolLoginClient(
                    impersonate=config.impersonate,
                    verify_ssl=config.verify_ssl,
                    timeout=config.timeout,
                    event_callback=emit_stage,
                )
            )
            otp_fetcher = OtpFetcher(
                mode=config.otp_mode,
                command=config.otp_command,
                timeout=config.otp_timeout,
                interval=config.otp_interval,
                impersonate=config.impersonate,
                verify=config.verify_ssl,
            )
            result = client.login_and_exchange(row, otp_fetcher=otp_fetcher)
            if not isinstance(result, AttemptResult):
                raise TypeError(f"client returned {type(result).__name__}, expected AttemptResult")
            return result
        except Exception as exc:
            emit_stage({"stage": "runtime_exception", "reason": f"{type(exc).__name__}: {str(exc)[:180]}"})
            return _exception_result(row, status="runtime_error", stage="runtime_exception", exc=exc)

    log(f"[+] loaded rows: {len(rows)} | concurrency={concurrency} ({summary['concurrency_mode']})")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(run_one, row): row for row in rows}
        for future in as_completed(future_map):
            row = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = _exception_result(row, status="worker_crash", stage="worker_future", exc=exc)
            with lock:
                if result.ok:
                    try:
                        token_payload = _prepare_token_data(
                            result.token_json,
                            pool=config.pool,
                            token_type=config.token_type,
                            fallback_email=result.row.login_email,
                        )
                    except Exception as exc:
                        result.status = "export_prepare_error"
                        result.stage = "export_prepare"
                        result.reason = f"{type(exc).__name__}: {str(exc)[:240]}"
                        result.token_json = ""
                        result.events.append({"stage": "export_prepare", "reason": result.reason})
                    else:
                        successes.append(token_payload)
                results.append(result)
                _append_jsonl(out_dir / "results.safe.jsonl", _safe_result_row(result))
            status_line = f"[{result.status}] {mask_email(result.row.login_email)}"
            if result.reason:
                status_line += f" | {result.reason}"
            log(status_line)
            emit(
                {
                    "type": "row_done",
                    "done": len(results),
                    "total": len(rows),
                    "ok": bool(result.ok),
                    "status": result.status,
                    "stage": result.stage,
                    "reason": result.reason,
                    "line_no": result.row.line_no,
                    "email_masked": mask_email(result.row.login_email),
                    "otp_required": bool(result.otp_required),
                    "events": result.events[-8:],
                }
            )

    successes.sort(key=lambda item: str(item.get("email") or ""))
    sub_accounts: list[dict[str, Any]] = []
    cpa_files: list[dict[str, Any]] = []
    cpa_dir = out_dir / "CPA"
    for index, token_payload in enumerate(successes, 1):
        email = str(token_payload.get("email") or "").strip()
        if export_cpa:
            cpa_payload = build_cpa_token_json(token_payload)
            cpa_filename = f"{email}.json" if email else f"token_{run_stamp}_{index:03d}.json"
            cpa_path = cpa_dir / cpa_filename
            write_json(cpa_path, cpa_payload)
            cpa_files.append(
                {
                    "file": str(cpa_path.relative_to(out_dir)).replace("\\", "/"),
                    "email_hash": secret_hash(email),
                    "email_masked": mask_email(email),
                    "type": str(cpa_payload.get("type") or ""),
                }
            )
        if export_sub2api:
            sub_account = _build_sub_account(token_payload, pool=config.pool, index=index)
            sub_accounts.append(sub_account)

    cpa_zip_path = out_dir / f"cpa_tokens_{run_stamp}.zip"
    if successes and export_cpa:
        with zipfile.ZipFile(cpa_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in cpa_files:
                file_path = out_dir / str(item["file"])
                archive.write(file_path, arcname=file_path.name)
        write_json(
            out_dir / "cpa_manifest.json",
            {
                "exported_at": utc_now_iso(),
                "count": len(successes),
                "format": "cpa-per-account-json",
                "directory": "CPA",
                "zip": cpa_zip_path.name,
                "files": cpa_files,
            },
        )
    if successes and export_sub2api:
        write_json(out_dir / "sub2api_accounts.secret.json", build_export(sub_accounts))

    summary["finished_at"] = utc_now_iso()
    summary["success_count"] = len(successes)
    summary["failure_count"] = len(rows) - len(successes)
    summary["success_emails"] = sorted(str(item.get("email") or "") for item in successes if str(item.get("email") or "").strip())
    summary["sub2api_export"] = str(out_dir / "sub2api_accounts.secret.json") if successes and export_sub2api else ""
    summary["cpa_dir"] = str(cpa_dir) if successes and export_cpa else ""
    summary["cpa_zip"] = str(cpa_zip_path) if successes and export_cpa else ""
    summary["cpa_manifest"] = str(out_dir / "cpa_manifest.json") if successes and export_cpa else ""
    write_json(out_dir / "summary.json", summary)
    write_json(out_dir / "progress.json", summary)
    log(f"[done] success={summary['success_count']} failure={summary['failure_count']}")
    emit({"type": "finished", "summary": summary})
    return summary

