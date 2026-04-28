from __future__ import annotations

import json
import secrets
import threading
import time
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
    max_attempts: int = 3
    auto_rerun_attempts: int = 2


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


def _exception_result(row: Any, *, status: str, stage: str, exc: BaseException) -> AttemptResult:
    reason = f"{type(exc).__name__}: {str(exc)[:240]}"
    return AttemptResult(
        row=row,
        status=status,
        stage=stage,
        reason=reason,
        events=[{"stage": stage, "reason": reason}],
    )


def _is_cancelled(cancel_event: threading.Event | None) -> bool:
    return bool(cancel_event is not None and cancel_event.is_set())


def _cancelled_result(row: Any, *, row_index: int = 0, max_attempts: int = 1) -> AttemptResult:
    result = AttemptResult(
        row=row,
        status="cancelled",
        stage="cancelled",
        reason="user_cancelled",
        events=[{"stage": "cancelled", "reason": "user_cancelled"}],
    )
    result.meta["row_index"] = int(row_index or 0)
    result.meta["attempt"] = 1
    result.meta["max_attempts"] = int(max_attempts or 1)
    return result


def _is_recoverable_retryable(result: AttemptResult) -> bool:
    if result.ok or result.status == "cancelled":
        return False
    status = str(result.status or "").strip()
    stage = str(result.stage or "").strip()
    reason = str(result.reason or "").strip().lower()
    terminal_reasons = {
        "account_deactivated",
        "account_disabled",
        "account_suspended",
        "account_deleted",
        "account_locked",
        "account_not_found",
        "user_not_found",
        "invalid_credentials",
    }
    # The server has already made a deterministic account-state decision.
    # Retrying these rows only burns time and may make the GUI look unstable.
    if reason in terminal_reasons:
        return False
    # These failures are often recoverable by re-running the whole account flow:
    # a new login attempt sends a fresh email OTP and rebuilds the OAuth session.
    if status == "otp_timeout":
        return True
    if reason in {"otp_timeout", "wrong_email_otp_code", "email_otp_expired"}:
        return True
    if status == "email_otp_validate_error":
        return not reason or reason.startswith("http_5") or reason in {"bad_request", "invalid_auth_step"}
    if status in {"auth_entry_error", "authorize_continue_error"} and reason in {"http_403", "http_408", "http_409", "http_425", "http_429"}:
        return True
    if stage == "email_verification" and ("otp" in reason or "code" in reason or "验证码" in reason):
        return True
    transient_markers = (
        "timeout",
        "timed out",
        "read operation timed out",
        "curl: (28)",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "remote disconnected",
        "http_429",
        "http_502",
        "http_503",
        "http_504",
    )
    if status == "runtime_error" and any(marker in reason for marker in transient_markers):
        return True
    if stage == "finalize" and any(marker in reason for marker in transient_markers):
        return True
    if status == "finalize_error" and (reason in {"callback_error", "finalize_unresolved"} or any(marker in reason for marker in transient_markers)):
        return True
    return False


def _diagnose_failure(result: AttemptResult) -> tuple[str, str]:
    status = str(result.status or "").strip()
    stage = str(result.stage or "").strip()
    reason = str(result.reason or "").strip()
    lowered = reason.lower()
    if status == "cancelled":
        return "用户取消", "任务已取消；如需继续，重新开始导出即可。"
    if status == "bad_password":
        return "密码验证失败", "请检查这条账号的 GPT/OpenAI 登录密码是否正确。"
    if lowered in {"account_deactivated", "account_disabled", "account_suspended", "account_deleted"}:
        return "账号状态不可用", "服务端明确返回账号已停用/禁用/注销；自动重试无法修复，建议更换账号或联系上游处理。"
    if lowered in {"account_locked"}:
        return "账号被锁定", "服务端明确返回账号锁定；建议暂停重试，等待解锁或联系上游处理。"
    if lowered in {"account_not_found", "user_not_found"}:
        return "账号不存在", "服务端未识别该 GPT/OpenAI 登录邮箱；请检查账号文本或更换账号。"
    if lowered in {"invalid_credentials"}:
        return "凭据无效", "服务端明确返回凭据无效；请检查 GPT/OpenAI 登录邮箱和登录密码。"
    if reason == "wrong_email_otp_code":
        return "验证码错误或过期", "取码源可能返回了旧验证码。客户端会自动重试并追加自动重跑；如果仍失败，通常需要稍后等待新验证码。"
    if status == "otp_timeout" or reason == "otp_timeout":
        return "未获取到验证码", "请确认取码源可访问，或在高级选项中适当增加验证码等待超时。"
    if status == "email_otp_validate_error":
        return "验证码提交失败", "验证码接口拒绝了当前验证码；通常是旧码、过期码或取码源延迟。"
    if stage == "finalize" or status == "finalize_error":
        if "timeout" in lowered or "timed out" in lowered or "curl: (28)" in lowered:
            return "Callback 换 JSON 超时", "客户端已自动重试并追加自动重跑；如果仍失败，建议调高 HTTP 请求超时或稍后再让客户端自动处理。"
        return "Callback 换 JSON 未完成", "登录和验证码已通过，但最后换取 JSON 未完成；客户端会优先自动重跑可恢复失败。"
    if "timeout" in lowered or "timed out" in lowered or "curl: (28)" in lowered:
        return "网络请求超时", "客户端已自动重试并追加自动重跑；如果仍失败，请调高 HTTP 请求超时或稍后再运行。"
    if reason.startswith("http_"):
        return "接口返回异常", f"服务端返回 {reason.replace('http_', 'HTTP ')}；建议稍后重试。"
    if status == "export_prepare_error":
        return "JSON 整理失败", "登录返回的数据格式不符合预期，当前账号已跳过。"
    if status == "runtime_error":
        return "运行异常", "当前账号发生非预期异常，已隔离；可重跑失败账号或查看安全日志。"
    return "未分类失败", "请复制安全日志或失败报告用于排查。"


def _failure_report_row(result: AttemptResult) -> dict[str, Any]:
    category, suggestion = _diagnose_failure(result)
    return {
        "row_index": int((result.meta or {}).get("row_index") or 0),
        "line_no": result.row.line_no,
        "email_hash": secret_hash(result.row.login_email),
        "login_masked": mask_email(result.row.login_email),
        "otp_source_masked": mask_source(result.row.otp_source),
        "status": result.status,
        "stage": result.stage,
        "reason": result.reason,
        "category": category,
        "suggestion": suggestion,
        "attempt": int((result.meta or {}).get("attempt") or 1),
        "max_attempts": int((result.meta or {}).get("max_attempts") or 1),
        "normal_attempts": int((result.meta or {}).get("normal_attempts") or (result.meta or {}).get("max_attempts") or 1),
        "auto_rerun_attempts": int((result.meta or {}).get("auto_rerun_attempts") or 0),
        "otp_required": bool(result.otp_required),
    }


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


def _create_batch_output_dir(output_root: Path) -> tuple[str, Path]:
    """Create a unique per-run result directory under the selected output root."""

    output_root.mkdir(parents=True, exist_ok=True)
    for _attempt in range(100):
        batch_id = f"{_run_timestamp()}_{secrets.token_hex(3)}"
        out_dir = output_root / f"GPT2JSON_{batch_id}"
        try:
            out_dir.mkdir()
        except FileExistsError:
            continue
        return batch_id, out_dir
    raise FileExistsError(f"failed to create a unique GPT2JSON export directory under {output_root}")


def _unique_child_file_path(directory: Path, filename: str) -> Path:
    """Return a non-existing child path, preserving the original name when possible."""

    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10000):
        candidate = directory / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"failed to create a unique filename for {filename}")


def _safe_result_row(result: AttemptResult, *, row_index: int = 0) -> dict[str, Any]:
    return {
        "row_index": int(row_index or 0),
        "line_no": result.row.line_no,
        "email_hash": secret_hash(result.row.login_email),
        "login_masked": mask_email(result.row.login_email),
        "otp_source_masked": mask_source(result.row.otp_source),
        "status": result.status,
        "stage": result.stage,
        "otp_required": bool(result.otp_required),
        "reason": result.reason,
        "attempt": int((result.meta or {}).get("attempt") or 1),
        "max_attempts": int((result.meta or {}).get("max_attempts") or 1),
        "normal_attempts": int((result.meta or {}).get("normal_attempts") or (result.meta or {}).get("max_attempts") or 1),
        "auto_rerun_attempts": int((result.meta or {}).get("auto_rerun_attempts") or 0),
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
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    log = logger or (lambda _text: None)
    emit = on_event or (lambda _event: None)
    export_sub2api = bool(config.export_sub2api)
    export_cpa = bool(config.export_cpa)
    if not (export_sub2api or export_cpa):
        raise ValueError("at least one export format must be selected")
    rows, input_source = _load_rows(config)
    output_root = Path(config.out_dir)
    batch_id, out_dir = _create_batch_output_dir(output_root)
    concurrency = resolve_concurrency(config.concurrency, len(rows))
    max_attempts = max(1, min(5, int(config.max_attempts or 1)))
    auto_rerun_attempts = max(0, min(5, int(config.auto_rerun_attempts or 0)))
    total_attempt_limit = max_attempts + auto_rerun_attempts
    summary: dict[str, Any] = {
        "started_at": utc_now_iso(),
        "input": input_source,
        "output_root": str(output_root),
        "out_dir": str(out_dir),
        "batch_id": batch_id,
        "row_count": len(rows),
        "concurrency": concurrency,
        "concurrency_mode": "auto" if int(config.concurrency or 0) <= 0 else "manual",
        "pool": config.pool,
        "token_type": config.token_type,
        "export_sub2api": export_sub2api,
        "export_cpa": export_cpa,
        "otp_mode": config.otp_mode,
        "input_format": config.input_format,
        "max_attempts": max_attempts,
        "auto_rerun_attempts": auto_rerun_attempts,
        "total_attempt_limit": total_attempt_limit,
    }
    write_json(out_dir / "progress.json", summary)
    emit(
        {
            "type": "started",
            "total": len(rows),
            "output_root": str(output_root),
            "out_dir": str(out_dir),
            "batch_id": batch_id,
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
    run_stamp = batch_id

    def run_one(row: Any, row_index: int) -> AttemptResult:
        emit({"type": "row_start", "row_index": row_index, "line_no": row.line_no, "email_masked": mask_email(row.login_email)})
        if _is_cancelled(cancel_event):
            return _cancelled_result(row, row_index=row_index, max_attempts=total_attempt_limit)

        current_attempt = 1

        def emit_stage(event: dict[str, Any]) -> None:
            payload = {
                "type": "row_stage",
                "row_index": row_index,
                "line_no": row.line_no,
                "email_masked": mask_email(row.login_email),
                "attempt": current_attempt,
                "max_attempts": total_attempt_limit,
                "normal_attempts": max_attempts,
                "auto_rerun_attempts": auto_rerun_attempts,
                "auto_rerun": current_attempt > max_attempts,
            }
            payload.update(event)
            emit(payload)

        result: AttemptResult | None = None
        for attempt in range(1, total_attempt_limit + 1):
            current_attempt = attempt
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
                    cancel_event=cancel_event,
                )
                if _is_cancelled(cancel_event):
                    return _cancelled_result(row, row_index=row_index, max_attempts=total_attempt_limit)
                result = client.login_and_exchange(row, otp_fetcher=otp_fetcher)
                if not isinstance(result, AttemptResult):
                    raise TypeError(f"client returned {type(result).__name__}, expected AttemptResult")
            except Exception as exc:
                emit_stage({"stage": "runtime_exception", "reason": f"{type(exc).__name__}: {str(exc)[:180]}"})
                result = _exception_result(row, status="runtime_error", stage="runtime_exception", exc=exc)

            result.meta["attempt"] = attempt
            result.meta["max_attempts"] = total_attempt_limit
            result.meta["normal_attempts"] = max_attempts
            result.meta["auto_rerun_attempts"] = auto_rerun_attempts
            result.meta["row_index"] = row_index
            if _is_cancelled(cancel_event) and not result.ok:
                result.status = "cancelled"
                result.stage = "cancelled"
                result.reason = "user_cancelled"
                result.events.append({"stage": "cancelled", "reason": "user_cancelled"})
                return result
            if result.ok or attempt >= total_attempt_limit or not _is_recoverable_retryable(result):
                return result
            is_auto_rerun = attempt >= max_attempts
            emit(
                {
                    "type": "row_retry",
                    "row_index": row_index,
                    "line_no": row.line_no,
                    "email_masked": mask_email(row.login_email),
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "max_attempts": total_attempt_limit,
                    "normal_attempts": max_attempts,
                    "auto_rerun_attempts": auto_rerun_attempts,
                    "auto_rerun": is_auto_rerun,
                    "status": result.status,
                    "stage": result.stage,
                    "reason": result.reason,
                }
            )
            wait_seconds = min(18, 8 + (attempt - max_attempts + 1) * 5) if is_auto_rerun else min(6, 1 + attempt * 2)
            if cancel_event is not None:
                if cancel_event.wait(wait_seconds):
                    return _cancelled_result(row, row_index=row_index, max_attempts=total_attempt_limit)
            else:
                time.sleep(wait_seconds)

        return result or _cancelled_result(row, row_index=row_index, max_attempts=total_attempt_limit)

    log(f"[+] loaded rows: {len(rows)} | concurrency={concurrency} ({summary['concurrency_mode']})")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(run_one, row, row_index): (row, row_index) for row_index, row in enumerate(rows, 1)}
        for future in as_completed(future_map):
            row, row_index = future_map[future]
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
                _append_jsonl(out_dir / "results.safe.jsonl", _safe_result_row(result, row_index=row_index))
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
                    "row_index": row_index,
                    "line_no": result.row.line_no,
                    "email_masked": mask_email(result.row.login_email),
                    "otp_required": bool(result.otp_required),
                    "attempt": int((result.meta or {}).get("attempt") or 1),
                    "max_attempts": int((result.meta or {}).get("max_attempts") or 1),
                    "normal_attempts": int((result.meta or {}).get("normal_attempts") or (result.meta or {}).get("max_attempts") or 1),
                    "auto_rerun_attempts": int((result.meta or {}).get("auto_rerun_attempts") or 0),
                    "events": result.events[-8:],
                }
            )
            if _is_cancelled(cancel_event):
                emit({"type": "cancelling", "done": len(results), "total": len(rows)})

    successes.sort(key=lambda item: str(item.get("email") or ""))
    sub_accounts: list[dict[str, Any]] = []
    cpa_files: list[dict[str, Any]] = []
    cpa_dir = out_dir / "CPA"
    for index, token_payload in enumerate(successes, 1):
        email = str(token_payload.get("email") or "").strip()
        if export_cpa:
            cpa_payload = build_cpa_token_json(token_payload)
            cpa_filename = f"{email}.json" if email else f"token_{run_stamp}_{index:03d}.json"
            cpa_path = _unique_child_file_path(cpa_dir, cpa_filename)
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

    if successes and export_cpa:
        write_json(
            out_dir / "cpa_manifest.json",
            {
                "exported_at": utc_now_iso(),
                "count": len(successes),
                "format": "cpa-per-account-json",
                "directory": "CPA",
                "files": cpa_files,
            },
        )
    if successes and export_sub2api:
        write_json(out_dir / "sub2api_accounts.secret.json", build_export(sub_accounts))

    summary["finished_at"] = utc_now_iso()
    summary["success_count"] = len(successes)
    summary["failure_count"] = len(rows) - len(successes)
    summary["cancelled"] = _is_cancelled(cancel_event)
    summary["cancelled_count"] = len([result for result in results if result.status == "cancelled"])
    retry_count = len([result for result in results if int((result.meta or {}).get("attempt") or 1) > 1])
    auto_rerun_count = len([result for result in results if int((result.meta or {}).get("attempt") or 1) > max_attempts])
    failed_results = [result for result in results if not result.ok]
    failure_rows = [_failure_report_row(result) for result in failed_results]
    failure_categories: dict[str, int] = {}
    for item in failure_rows:
        category = str(item.get("category") or "未分类失败")
        failure_categories[category] = failure_categories.get(category, 0) + 1
    summary["success_emails"] = sorted(str(item.get("email") or "") for item in successes if str(item.get("email") or "").strip())
    summary["sub2api_export"] = str(out_dir / "sub2api_accounts.secret.json") if successes and export_sub2api else ""
    summary["cpa_dir"] = str(cpa_dir) if successes and export_cpa else ""
    summary["cpa_zip"] = ""
    summary["cpa_manifest"] = str(out_dir / "cpa_manifest.json") if successes and export_cpa else ""
    summary["retry_count"] = retry_count
    summary["auto_rerun_count"] = auto_rerun_count
    summary["failure_categories"] = failure_categories
    if failure_rows:
        failure_report_path = out_dir / "failure_report.safe.json"
        write_json(
            failure_report_path,
            {
                "exported_at": utc_now_iso(),
                "count": len(failure_rows),
                "note": "Safe report only: credentials and raw OTP sources are not included.",
                "categories": failure_categories,
                "failures": failure_rows,
            },
        )
        summary["failure_report"] = str(failure_report_path)
    else:
        summary["failure_report"] = ""
    write_json(out_dir / "summary.json", summary)
    write_json(out_dir / "progress.json", summary)
    if summary["cancelled"]:
        log(f"[cancelled] success={summary['success_count']} failure={summary['failure_count']}")
    else:
        log(f"[done] success={summary['success_count']} failure={summary['failure_count']}")
    emit({"type": "finished", "summary": summary})
    return summary
