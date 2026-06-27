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
    python scripts/review_content.py --file output/理财课/xxx.md --archetype modern  # 强制指定桶

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


def _derive_output_dir(file_path: Path) -> str:
    """从文件路径推导 output 目录（路径含 'output' 时取到该段，否则取父目录）。"""
    parts = file_path.resolve().parts
    for i, part in enumerate(parts):
        if part == "output" and i > 0:
            return str(Path(*parts[: i + 1]))
    return str(file_path.parent)


def resolve_archetype_for_file(file_path: Path, cli_archetype: str, book: str) -> str:
    """解析 archetype（design.md §5.6 信源优先级）：

    CLI --archetype > _meta.yaml.archetype > category 默认映射 > narrative。
    stdin 模式（无 file_path）时仅用 CLI 或兜底 narrative。
    """
    from src.main import _load_book_meta
    from src.utils.prompts import _VALID_ARCHETYPES, resolve_archetype

    cli = cli_archetype or ""
    if file_path is None:
        return cli if cli in _VALID_ARCHETYPES else "narrative"

    output_dir = _derive_output_dir(file_path)
    meta = _load_book_meta(book, output_dir)
    meta_archetype = meta.get("archetype", "")
    category = meta.get("category", "")
    explicit = cli if cli in _VALID_ARCHETYPES else (meta_archetype or None)
    return resolve_archetype(category, explicit=explicit)


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
    parser.add_argument(
        "--archetype",
        default="",
        help="形态范式桶（narrative/modern/knowledge），未传则按 _meta.yaml 或 category 默认映射",
    )
    args = parser.parse_args()

    # 读取内容
    file_path_for_resolve: Path | None = None
    if args.file == "-":
        content = sys.stdin.read()
        book = args.book
        chapter = args.chapter
        event = args.event
    else:
        file_path_for_resolve = Path(args.file)
        if not file_path_for_resolve.exists():
            print(f"Error: 文件不存在: {file_path_for_resolve}", file=sys.stderr)
            return 1
        content = file_path_for_resolve.read_text(encoding="utf-8")
        inferred_book, inferred_chapter, inferred_event = extract_event_from_path(file_path_for_resolve)
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

    # 阶段2 质检分桶：解析 archetype 并跑规则化质检（纯规则，无需 LLM）
    archetype = resolve_archetype_for_file(file_path_for_resolve, args.archetype, book)
    from src.utils.content_quality import run_content_quality_checks
    rule_report = run_content_quality_checks(content, archetype=archetype)
    rule_section = (
        f"## 规则化质检（archetype={archetype}）\n\n"
        f"- 评分：{rule_report.score}/100（{'通过' if rule_report.passed else '未通过'}）\n"
        f"- 问题数：{len(rule_report.issues)}\n"
    )
    if rule_report.issues:
        rule_section += "\n问题清单：\n"
        for i, issue in enumerate(rule_report.issues, 1):
            rule_section += f"{i}. {issue}\n"

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

    llm_report = final_state.get("final_report", "")
    report = rule_section + ("\n---\n\n" + llm_report if llm_report else "")
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
