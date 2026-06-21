#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

# Allow running `python src/main.py` directly without PYTHONPATH setup.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.cli.core.workflow import DeepReadingWorkflow
from src.cli.utils.config import get_config
from src.cli.utils.llm import build_llm


def setup_logging() -> None:
    root = logging.getLogger("deep_reading")
    root.setLevel(logging.DEBUG)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        root.addHandler(handler)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="个人 AI 深度阅读助手")
    parser.add_argument("--book", help="书名")
    parser.add_argument("--chapter", help="章节")
    parser.add_argument("--event", help="事件")
    parser.add_argument("--input", dest="user_input", help="自然语言输入")
    parser.add_argument("--mock", action="store_true", help="使用 Mock LLM（无需 API Key）")
    return parser.parse_args(argv)


def build_user_input(args: argparse.Namespace) -> str:
    if args.user_input:
        return args.user_input
    parts = [p for p in [args.book, args.chapter, args.event] if p]
    if not parts:
        raise SystemExit("请提供 --input 自然语言输入，或 --book/--chapter/--event 参数组合。")
    return " ".join(parts)


def _has_api_key(llm_config: dict[str, Any]) -> bool:
    return bool(llm_config.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging()

    config = get_config()
    llm_config = dict(config.llm)
    if args.mock:
        llm_config["mock"] = True

    if not args.mock and not _has_api_key(llm_config):
        print(
            "错误：未检测到 LLM API Key。请执行以下任一操作：\n"
            "  1. 复制 .env.example 为 .env 并填写 LLM_API_KEY\n"
            "  2. 设置环境变量 LLM_API_KEY 或 OPENAI_API_KEY\n"
            "  3. 使用 --mock 参数进行离线演示"
        )
        return 1

    workflow = DeepReadingWorkflow(config=config, llm=build_llm(llm_config))
    user_input = build_user_input(args)

    final_state = workflow.run(user_input)

    print("\n===== 生成结果 =====")
    print(f"书名：{final_state['book']}")
    print(f"章节：{final_state['chapter']}")
    print(f"事件：{final_state['event']}")
    print(f"输出文件：{final_state['output_path']}")
    print(f"日志文件：{final_state['log_path']}")

    report = final_state.get("quality_report", {})
    if report.get("passed"):
        print("质量检查：通过")
    else:
        print("质量检查：未通过")
        for issue in report.get("issues", []):
            print(f"  - {issue}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
