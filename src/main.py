import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保从项目根目录导入 src 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _sanitize_filename(name: str) -> str:
    """简单的文件名安全化，防止路径穿越。

    替换路径分隔符与 ``..``，剥离首尾空白与下划线。
    """
    if not name:
        return "untitled"
    safe = name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    safe = safe.strip("_")
    return safe or "untitled"


def _parse_slots_from_input(user_input: str) -> tuple[str, str, str]:
    """从自然语言输入中按空白符切分，尝试提取书名/章节/事件。

    仅用于 stub 模式下的简单解析；真实生成仍由 Orchestrator 调用 LLM 处理。
    """
    parts = [p for p in user_input.split() if p]
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], ""
    if len(parts) == 1:
        return parts[0], "", ""
    return "", "", ""


def _generate_stub(
    book: str, chapter: str, event: str, user_input: str, output_dir: str,
    dry_run: bool = False, archetype: str = "narrative",
) -> Path:
    """Generate a placeholder note for testing the web interface without API keys."""
    # stub 模式支持从 --input 简单解析三个槽位
    if not (book and chapter and event) and user_input:
        parsed_book, parsed_chapter, parsed_event = _parse_slots_from_input(user_input)
        book = book or parsed_book
        chapter = chapter or parsed_chapter
        event = event or parsed_event

    if not (book and chapter and event):
        print(
            "Error: --stub 模式需要明确指定 --book、--chapter、--event，"
            "或提供包含这三项的 --input。",
            file=sys.stderr,
        )
        sys.exit(1)

    book = _sanitize_filename(book)
    chapter = _sanitize_filename(chapter)
    event = _sanitize_filename(event)

    target_dir = Path(output_dir) / book
    output_path = target_dir / f"{chapter}_{event}.md"

    if dry_run:
        print(f"[STUB DRY RUN] 预期保存路径：{output_path}")
        return output_path

    target_dir.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"File already exists: {output_path}")
        return output_path

    # 阶段3：按 archetype 取段落模板（narrative 6 / modern 5 / knowledge 4）
    # stub 路径直接读 config，不 import workflow（避免 langgraph 依赖）
    sections = _get_stub_sections(archetype)

    created_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
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


def _get_stub_sections(archetype: str) -> list:
    """stub 模式按 archetype 取段落名，直接读 config 不依赖 workflow。

    与 workflow.get_required_sections 行为一致（同源 config.section_templates），
    但避免 import src.core.workflow 触发 langgraph 依赖（stub 用于无 API 环境）。
    """
    valid = {"narrative", "modern", "knowledge"}
    if archetype not in valid:
        archetype = "narrative"
    from src.utils.config import load_config
    cfg = load_config()
    templates = cfg.get("section_templates", {}) if isinstance(cfg, dict) else {}
    if isinstance(templates, dict) and archetype in templates:
        return list(templates[archetype])
    qc = cfg.get("quality_check", {}) if isinstance(cfg, dict) else {}
    return list(qc.get(
        "required_sections",
        ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"],
    ))


def _load_book_meta(book: str, output_dir: str) -> dict:
    """读取 output/{book}/_meta.yaml，返回解析后的 dict。

    用内置简易解析器（避免依赖 PyYAML），只支持单层 key:value。
    文件不存在或解析失败时返回空 dict。
    """
    if not book:
        return {}
    safe_book = _sanitize_filename(book)
    meta_path = Path(output_dir) / safe_book / "_meta.yaml"
    if not meta_path.exists():
        return {}
    result: dict = {}
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="个人 AI 深度阅读助手")
    parser.add_argument("--book", help="书名，例如：资治通鉴")
    parser.add_argument("--chapter", help="章节，例如：周纪二")
    parser.add_argument("--event", help="事件，例如：商鞅变法")
    parser.add_argument(
        "--archetype",
        help="形态范式桶（narrative/modern/knowledge），"
        "未传则按 category 默认映射（fiction 待实现）",
    )
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

    # 解析 archetype（design.md §5.6 信源优先级）：
    #   CLI --archetype > _meta.yaml.archetype > category 默认映射 > narrative
    # 阶段1 打通数据流：读 _meta.yaml 的 category 与 archetype，调 resolve_archetype 兜底。
    # CLI 传非法值时视为未提供，回落到 _meta.yaml.archetype。
    from src.utils.prompts import resolve_archetype, _VALID_ARCHETYPES

    meta = _load_book_meta(book, args.output_dir)
    cli_archetype = args.archetype or ""
    meta_archetype = meta.get("archetype", "")
    category = meta.get("category", "")
    # CLI 合法时优先；CLI 非法或未传时用 _meta.yaml 的显式 archetype；都未传时走 category 默认映射
    explicit = cli_archetype if cli_archetype in _VALID_ARCHETYPES else (meta_archetype or None)
    archetype = resolve_archetype(category, explicit=explicit)

    # fiction 桶待实现（design.md §5.2），未落地前回落 narrative 避免 build_workflow 崩溃。
    # 放在 resolve_archetype 之后、stub/真实分支之前，统一拦截（单一信源）。
    if archetype not in ("narrative", "modern", "knowledge"):
        print(f"警告：archetype {archetype!r} 未落地，回落 narrative", file=sys.stderr)
        archetype = "narrative"

    if args.stub:
        output_path = _generate_stub(
            book, chapter, event, user_input, args.output_dir,
            dry_run=args.dry_run, archetype=archetype,
        )
        return 0

    if args.dry_run:
        print("[DRY RUN] 跳过工作流调用，不生成笔记。")
        return 0

    # 阶段3：执行层（specialist/editor prompt）尚未按 archetype 分桶（阶段4 落地）。
    # 真实模式下 modern/knowledge 会因 specialist 硬编码 narrative 段名导致 quality 失败（P0-1）。
    # 阶段4 specialist 改造前，真实模式统一回落 narrative 执行；stub 模式已 return，保留分桶展示。
    # 注意：initial_state['archetype'] 保留用户意图（modern/knowledge），供阶段4 specialist 读取；
    # 仅 build_workflow 用回落的 exec_archetype，保证 quality 检查与 specialist 生成段名匹配。
    exec_archetype = archetype
    if archetype != "narrative":
        print(
            f"警告：archetype {archetype!r} 真实生成尚未落地（阶段4），"
            f"回落 narrative 执行",
            file=sys.stderr,
        )
        exec_archetype = "narrative"

    from src.core.workflow import build_workflow

    initial_state = {
        "book": book,
        "chapter": chapter,
        "event": event,
        "archetype": archetype,
        "user_input": user_input,
        "output_path": "",
        "sections": {},
        "sources": {},
        "final_markdown": "",
        "errors": [],
    }

    app = build_workflow(output_base=args.output_dir, archetype=exec_archetype)
    final_state = app.invoke(initial_state)

    if final_state.get("errors"):
        print("质量检查未通过：")
        for issue in final_state["errors"]:
            print(f"  - {issue}")
        return 1

    output_path = Path(final_state["output_path"])
    print(f"已生成笔记：{output_path}")
    print("\n--- 内容预览 ---\n")
    print(final_state["final_markdown"][:1500])

    return 0


if __name__ == "__main__":
    sys.exit(main())
