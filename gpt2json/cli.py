from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import ExportConfig, run_export


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GPT2JSON：协议优先的 Sub2API / CPA JSON 导出工具。")
    parser.add_argument("--version", action="version", version=f"GPT2JSON {__version__}")
    parser.add_argument("--input", required=True, help="账号文本文件：GPT邮箱----GPT密码----OTP取码源")
    parser.add_argument("--out-dir", required=True, help="输出目录")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数")
    parser.add_argument("--pool", default="plus", help="Sub2API 池名称")
    parser.add_argument("--token-type", default="plus", help="令牌类型")
    parser.add_argument("--input-format", default="auto", help="输入格式：auto 或 dash_otp")
    parser.add_argument("--otp-mode", default="auto", choices=["auto", "command", "none"], help="OTP 模式")
    parser.add_argument("--otp-command", default="", help="外部取码命令模板")
    parser.add_argument("--otp-timeout", type=int, default=180, help="OTP 等待超时秒数")
    parser.add_argument("--otp-interval", type=int, default=3, help="OTP 轮询间隔秒数")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP 超时秒数")
    parser.add_argument("--impersonate", default="chrome124", help="curl-cffi impersonate 指纹")
    parser.add_argument("--insecure", action="store_true", help="关闭 TLS 证书校验")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def logger(text: str) -> None:
        print(text, flush=True)

    summary = run_export(
        ExportConfig(
            input_path=args.input,
            out_dir=str(out_dir),
            concurrency=max(1, int(args.concurrency or 1)),
            pool=args.pool,
            token_type=args.token_type,
            input_format=args.input_format,
            otp_mode=args.otp_mode,
            otp_command=args.otp_command,
            otp_timeout=args.otp_timeout,
            otp_interval=args.otp_interval,
            timeout=args.timeout,
            verify_ssl=not bool(args.insecure),
            impersonate=args.impersonate,
        ),
        logger=logger,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if int(summary.get("success_count") or 0) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
