import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保从项目根目录导入 src 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _generate_stub(book: str, chapter: str, event: str, output_dir: str) -> Path:
    """Generate a placeholder note for testing the web interface without API keys."""
    target_dir = Path(output_dir) / book
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{chapter}_{event}.md"

    if output_path.exists():
        print(f"File already exists: {output_path}")
        return output_path

    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sections = ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]
    lines = [
        f'---',
        f'title: "{book}·{chapter}：{event}"',
        f'book: "{book}"',
        f'chapter: "{chapter}"',
        f'event: "{event}"',
        f'created_at: "{created_at}"',
        f'source_agents: ["stub_engine"]',
        f'---',
        "",
        f"# {book}·{chapter}：{event}",
        "",
    ]
    for section in sections:
        lines.extend([f"## {section}", "", f"这里是「{section}」的占位内容，围绕《{book}》{chapter}中的「{event}」展开。", ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_path}")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="个人 AI 深度阅读助手")
    parser.add_argument("--book", help="书名，例如：资治通鉴")
    parser.add_argument("--chapter", help="章节，例如：周纪二")
    parser.add_argument("--event", help="事件，例如：商鞅变法")
    parser.add_argument("--input", dest="user_input", help="自然语言输入")
    parser.add_argument("--dry-run", action="store_true", help="只生成不保存")
    parser.add_argument("--stub", action="store_true", help="使用占位生成器（无需 API Key，用于测试 Web 界面）")
    parser.add_argument(
        "--output-dir", default="output", help="输出目录根路径"
    )
    args = parser.parse_args()

    user_input = args.user_input or ""
    book = args.book or ""
    chapter = args.chapter or ""
    event = args.event or ""

    if not user_input and not book and not chapter and not event:
        parser.print_help()
        return 1

    if not user_input:
        parts = [p for p in [book, chapter, event] if p]
        user_input = " ".join(parts)

    if args.stub:
        output_path = _generate_stub(book, chapter, event, args.output_dir)
        if args.dry_run:
            print(f"[STUB DRY RUN] 预期保存路径：{output_path}")
        return 0

    from src.core.workflow import build_workflow

    initial_state = {
        "book": book,
        "chapter": chapter,
        "event": event,
        "user_input": user_input,
        "output_path": "",
        "sections": {},
        "sources": {},
        "final_markdown": "",
        "errors": [],
    }

    app = build_workflow(output_base=args.output_dir)
    final_state = app.invoke(initial_state)

    output_path = Path(final_state["output_path"])
    if args.dry_run:
        print("[DRY RUN] 生成结果：")
        print(final_state["final_markdown"][:2000])
        print(f"\n...（省略）\n")
        print(f"预期保存路径：{output_path}")
    else:
        print(f"已生成笔记：{output_path}")
        print("\n--- 内容预览 ---\n")
        print(final_state["final_markdown"][:1500])

    return 0


if __name__ == "__main__":
    sys.exit(main())
