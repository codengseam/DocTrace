#!/usr/bin/env python3
"""内容质检命令行入口。

读取 Markdown 文件或从 stdin 读取内容，调用 LangGraph 并行质检工作流
（史实核验 / 可读性 / 引用克制三视角），输出质检报告到 stdout 或指定文件。

用法：
    python scripts/review_content.py --file path/to/chapter.md
    python scripts/review_content.py --file -              # 从 stdin 读取
    echo "内容" | python scripts/review_content.py --file -
    python scripts/review_content.py --file chapter.md --output report.md
    python scripts/review_content.py --file chapter.md --book 史记 --chapter 汉纪 --event 鸿门宴

环境变量：
    DEEP_READING_MOCK=1  使用 Mock LLM，无需 API Key（用于测试）
    LLM_API_KEY          真实质检需要配置
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def extract_event_from_path(file_path: Path) -> tuple[str, str, str]:
    """从文件路径尝试提取 book/chapter/event。"""
    parts = file_path.parts
    # output/史记/汉纪/07_鸿门宴.md -> book=史记, chapter=汉纪, event=鸿门宴
    if len(parts) >= 3 and parts[-3] == "output":
        book = parts[-2]
    elif len(parts) >= 4 and parts[-4] == "output":
        book = parts[-3]
    else:
        book = ""

    stem = file_path.stem
    if "_" in stem:
        chapter, event = stem.split("_", 1)
    else:
        chapter, event = "", stem
    return book, chapter, event


def main() -> int:
    parser = argparse.ArgumentParser(description="多 Agent 并行内容质检（史实核验/可读性/引用克制）")
    parser.add_argument(
        "--file",
        required=True,
        help="Markdown 文件路径，- 表示从 stdin 读取",
    )
    parser.add_argument(
        "--book",
        default="",
        help="书籍名（可选，默认从路径推断）",
    )
    parser.add_argument(
        "--chapter",
        default="",
        help="章节名（可选，默认从路径推断）",
    )
    parser.add_argument(
        "--event",
        default="",
        help="事件名（可选，默认从路径推断）",
    )
    parser.add_argument(
        "--output",
        default="",
        help="质检报告输出文件路径（可选，默认输出到 stdout）",
    )
    args = parser.parse_args()

    # 读取内容
    if args.file == "-":
        content = sys.stdin.read()
        book = args.book
        chapter = args.chapter
        event = args.event
    else:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: 文件不存在: {file_path}", file=sys.stderr)
            return 1
        content = file_path.read_text(encoding="utf-8")
        inferred_book, inferred_chapter, inferred_event = extract_event_from_path(file_path)
        book = args.book or inferred_book
        chapter = args.chapter or inferred_chapter
        event = args.event or inferred_event

    if not content.strip():
        print("Error: 内容为空", file=sys.stderr)
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
    from src.core.content_review_workflow import build_content_review_workflow

    initial_state = {
        "content": content,
        "book": book,
        "chapter": chapter,
        "event": event,
        "reviews": {},
        "final_report": "",
    }

    app = build_content_review_workflow()
    final_state = app.invoke(initial_state)

    report = final_state.get("final_report", "")
    if not report:
        print("Error: 质检未产出报告", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"质检报告已保存至: {output_path}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
