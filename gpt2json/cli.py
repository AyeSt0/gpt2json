from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import ExportConfig, run_export
from .parsing import list_input_formats
from .protocol import DEFAULT_IMPERSONATE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GPT2JSON：Sub2API / CPA JSON 导出工具。")
    supported_formats = ", ".join(["auto", *(fmt.id for fmt in list_input_formats())])
    parser.add_argument("--version", action="version", version=f"GPT2JSON {__version__}")
    parser.add_argument("--input", help="账号文本文件：GPT邮箱----GPT登录密码----免登录接码源")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取账号文本；优先级高于 --input")
    parser.add_argument("--out-dir", required=True, help="输出目录")
    parser.add_argument("--concurrency", type=int, default=0, help="并发数；0 表示自动")
    parser.add_argument("--name-prefix", dest="pool", default="", help="可选：给 Sub2API 账号 name 增加前缀（默认不写）")
    parser.add_argument("--token-type", default="plus", help="高级：写入 token type 字段")
    parser.add_argument("--sub2api", action=argparse.BooleanOptionalAction, default=True, help="是否导出 Sub2API JSON")
    parser.add_argument("--cpa", action=argparse.BooleanOptionalAction, default=True, help="是否导出 CPA JSON")
    parser.add_argument("--input-format", default="auto", help=f"输入格式：{supported_formats}")
    parser.add_argument("--otp-mode", default="auto", choices=["auto", "command", "none"], help="OTP 模式")
    parser.add_argument("--otp-command", default="", help="外部取码命令模板")
    parser.add_argument("--otp-timeout", type=int, default=180, help="OTP 等待超时秒数")
    parser.add_argument("--otp-interval", type=int, default=3, help="OTP 轮询间隔秒数")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP 超时秒数")
    parser.add_argument("--max-attempts", type=int, default=3, help="单账号可恢复失败自动重试次数，1 表示不重试")
    parser.add_argument("--auto-rerun-attempts", type=int, default=2, help="自动重试仍未成功时，对可恢复失败追加单账号自动重跑补救次数")
    parser.add_argument("--impersonate", default=DEFAULT_IMPERSONATE, help="curl-cffi impersonate 指纹")
    parser.add_argument("--insecure", action="store_true", help="关闭 TLS 证书校验")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.stdin and not args.input:
        parser.error("请提供 --input 账号文件，或使用 --stdin 从标准输入读取。")
    if not (args.sub2api or args.cpa):
        parser.error("请至少保留一种导出格式：--sub2api 或 --cpa。")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    input_text = sys.stdin.read() if args.stdin else ""

    def logger(text: str) -> None:
        print(text, flush=True)

    summary = run_export(
        ExportConfig(
            input_path=args.input or "<stdin>",
            out_dir=str(out_dir),
            input_text=input_text,
            concurrency=int(args.concurrency or 0),
            pool=args.pool,
            token_type=args.token_type,
            export_sub2api=bool(args.sub2api),
            export_cpa=bool(args.cpa),
            input_format=args.input_format,
            otp_mode=args.otp_mode,
            otp_command=args.otp_command,
            otp_timeout=args.otp_timeout,
            otp_interval=args.otp_interval,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
            auto_rerun_attempts=args.auto_rerun_attempts,
            verify_ssl=not bool(args.insecure),
            impersonate=args.impersonate,
        ),
        logger=logger,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if int(summary.get("success_count") or 0) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
