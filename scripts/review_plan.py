#!/usr/bin/env python3
"""计划评审命令行入口。

读取计划文本文件，调用 LangGraph 并行评审工作流（架构师/测试/规则三视角），
输出评审报告到 stdout 或指定文件。

用法：
    python scripts/review_plan.py --plan path/to/plan.md
    python scripts/review_plan.py --plan -              # 从 stdin 读取
    echo "计划内容" | python scripts/review_plan.py --plan -
    python scripts/review_plan.py --plan plan.md --output report.md

环境变量：
    DEEP_READING_MOCK=1  使用 Mock LLM，无需 API Key（用于测试）
    LLM_API_KEY          真实评审需要配置
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 确保从项目根目录导入 src 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="多 Agent 评审开发计划（架构师/测试/规则三视角并行）")
    parser.add_argument(
        "--plan",
        required=True,
        help="计划文本文件路径，- 表示从 stdin 读取",
    )
    parser.add_argument(
        "--context",
        default="",
        help="项目背景上下文（可选，默认使用内置项目背景）",
    )
    parser.add_argument(
        "--output",
        default="",
        help="评审报告输出文件路径（可选，默认输出到 stdout）",
    )
    args = parser.parse_args()

    # 读取计划文本
    if args.plan == "-":
        plan_text = sys.stdin.read()
    else:
        plan_path = Path(args.plan)
        if not plan_path.exists():
            print(f"Error: 计划文件不存在: {plan_path}", file=sys.stderr)
            return 1
        plan_text = plan_path.read_text(encoding="utf-8")

    if not plan_text.strip():
        print("Error: 计划文本为空", file=sys.stderr)
        return 1

    # 检查 API Key（Mock 模式除外）
    is_mock = os.getenv("DEEP_READING_MOCK") in ("1", "true", "yes")
    if not is_mock and not os.getenv("LLM_API_KEY"):
        print(
            "Error: LLM_API_KEY 未配置。请复制 .env.example 为 .env 并填写 API Key，"
            "或设置 DEEP_READING_MOCK=1 使用 Mock 模式测试。",
            file=sys.stderr,
        )
        return 1

    # 延迟导入，避免在参数解析阶段就加载 LangGraph
    try:
        from src.core.plan_review_workflow import build_review_workflow
    except ImportError as e:
        print(
            "Error: 路径 B（LangGraph 真并行）依赖未就绪。\n"
            f"  导入失败：{e}\n"
            "  请运行 `pip install langgraph` 安装依赖，或改走主路径：\n"
            "  在 Trae 会话内调用 plan-review skill，由 Task 工具启动多个 subagent 并行评审（无需 .env、无需 langgraph）。\n"
            "  详见 .trae/skills/plan-review/SKILL.md。",
            file=sys.stderr,
        )
        return 1

    initial_state = {
        "plan_text": plan_text,
        "project_context": args.context,
        "reviews": {},
        "final_report": "",
    }

    app = build_review_workflow()
    final_state = app.invoke(initial_state)

    report = final_state.get("final_report", "")
    if not report:
        print("Error: 评审未产出报告", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"评审报告已保存至: {output_path}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
