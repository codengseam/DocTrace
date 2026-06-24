#!/usr/bin/env python3
"""书籍结构校验脚本。

扫描 output/ 目录下的 Markdown 笔记，校验 frontmatter 字段、文件路径格式、
章内事件排序等规则，输出控制台摘要与可选的 Markdown 报告。

用法：
    python scripts/check_book_structure.py [--output output] [--report report.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# 把项目根加入 sys.path，使 scripts/ 独立运行时也能 import src
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

FRONTMATTER_PATTERN = r"^---\s*\n(.*?)\n---\s*\n?"
REQUIRED_FIELDS = ["title", "book", "chapter", "event", "sort", "chapter_sort"]
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


@dataclass
class Issue:
    """单个校验问题。"""

    severity: str
    book: str
    chapter: str
    file: str
    message: str
    fix_suggestion: str


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """解析 Markdown frontmatter，返回 (metadata, body)。

    优先使用 PyYAML；不可用时 fallback 到简单 key:value 解析。
    """
    match = re.match(FRONTMATTER_PATTERN, content, re.DOTALL)
    if not match:
        return {}, content

    raw = match.group(1)
    body = content[match.end() :]

    if yaml is not None:
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                return data, body
        except Exception:
            pass

    return _parse_simple_frontmatter(raw), body


def _parse_simple_frontmatter(raw: str) -> dict[str, Any]:
    """无 PyYAML 时解析简单 frontmatter（顶层标量/列表）。"""
    result: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_key is not None:
                item = stripped[2:].strip().strip('"').strip("'")
                if not isinstance(result.get(current_key), list):
                    result[current_key] = []
                result[current_key].append(item)
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            result[current_key] = value.strip().strip('"').strip("'")
    return result


def _to_int(value: Any) -> int | None:
    """将 frontmatter 中的排序值转为整数；失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_note_path(rel_path: str) -> tuple[str, str, str] | None:
    """解析相对路径为 (book, chapter, event)。

    仅接受严格的 ``book/chapter_event.md`` 格式（恰好两级路径，且文件名含 _）。
    """
    parts = rel_path.split("/")
    if len(parts) != 2:
        return None
    book = parts[0]
    stem = parts[1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    if "_" not in stem:
        return None
    chapter, event = stem.split("_", 1)
    if not chapter or not event:
        return None
    return book, chapter, event


def _collect_files(output_path: Path) -> list[Path]:
    """收集 output/ 下所有待校验的 Markdown 文件。"""
    if not output_path.exists():
        return []
    files: list[Path] = []
    for md_path in sorted(output_path.rglob("*.md")):
        if md_path.name.startswith("_"):
            continue
        files.append(md_path)
    return files


def _check_file(md_path: Path, output_path: Path) -> tuple[list[Issue], dict[str, Any]]:
    """校验单个文件，返回 (问题列表, 用于后续聚合的元数据)。"""
    rel = md_path.relative_to(output_path)
    rel_str = str(rel).replace("\\", "/")
    parts = rel_str.split("/")
    dir_book = parts[0] if parts else ""
    issues: list[Issue] = []

    parsed = _parse_note_path(rel_str)
    path_book, path_chapter, path_event = parsed if parsed else ("", "", "")

    # P0: 路径格式
    if parsed is None:
        issues.append(
            Issue(
                severity="P0",
                book=dir_book,
                chapter="",
                file=rel_str,
                message="文件路径不符合 book/chapter_event.md 格式",
                fix_suggestion="将文件路径调整为 `<book>/<chapter>_<event>.md` 格式（仅允许一级子目录）",
            )
        )

    content = md_path.read_text(encoding="utf-8")
    frontmatter, _ = _parse_frontmatter(content)

    # P0: 必填字段缺失
    for field in REQUIRED_FIELDS:
        if field not in frontmatter or frontmatter[field] is None or frontmatter[field] == "":
            issues.append(
                Issue(
                    severity="P0",
                    book=path_book or dir_book,
                    chapter=path_chapter,
                    file=rel_str,
                    message=f"frontmatter 缺少必填字段: {field}",
                    fix_suggestion=f"在文件头部 frontmatter 中添加 `{field}: <值>`",
                )
            )

    # P0: 排序字段必须是整数
    sort_raw = frontmatter.get("sort")
    if sort_raw is not None and sort_raw != "" and _to_int(sort_raw) is None:
        issues.append(
            Issue(
                severity="P0",
                book=path_book or dir_book,
                chapter=path_chapter,
                file=rel_str,
                message=f"sort 不是整数: {sort_raw!r}",
                fix_suggestion="将 `sort` 改为整数（如 `sort: 1`）",
            )
        )

    chapter_sort_raw = frontmatter.get("chapter_sort")
    if (
        chapter_sort_raw is not None
        and chapter_sort_raw != ""
        and _to_int(chapter_sort_raw) is None
    ):
        issues.append(
            Issue(
                severity="P0",
                book=path_book or dir_book,
                chapter=path_chapter,
                file=rel_str,
                message=f"chapter_sort 不是整数: {chapter_sort_raw!r}",
                fix_suggestion="将 `chapter_sort` 改为整数（如 `chapter_sort: 2`）",
            )
        )

    # P1: frontmatter 与路径/目录一致性
    fm_book = frontmatter.get("book")
    if fm_book is not None and fm_book != dir_book:
        issues.append(
            Issue(
                severity="P1",
                book=path_book or dir_book,
                chapter=path_chapter,
                file=rel_str,
                message=f"frontmatter.book ({fm_book!r}) 与目录名 ({dir_book!r}) 不一致",
                fix_suggestion=f"将 `book` 改为 `{dir_book}`，或将文件移动到 `{fm_book}/` 目录下",
            )
        )

    if parsed is not None:
        fm_chapter = frontmatter.get("chapter")
        if fm_chapter is not None and fm_chapter != path_chapter:
            issues.append(
                Issue(
                    severity="P1",
                    book=path_book,
                    chapter=path_chapter,
                    file=rel_str,
                    message=f"frontmatter.chapter ({fm_chapter!r}) 与文件名章节 ({path_chapter!r}) 不一致",
                    fix_suggestion=f"将 `chapter` 改为 `{path_chapter}`，或将文件名章节部分改为 `{fm_chapter}`",
                )
            )

        fm_event = frontmatter.get("event")
        if fm_event is not None and fm_event != path_event:
            issues.append(
                Issue(
                    severity="P1",
                    book=path_book,
                    chapter=path_chapter,
                    file=rel_str,
                    message=f"frontmatter.event ({fm_event!r}) 与文件名事件 ({path_event!r}) 不一致",
                    fix_suggestion=f"将 `event` 改为 `{path_event}`，或将文件名事件部分改为 `{fm_event}`",
                )
            )

    metadata = {
        "rel": rel_str,
        "parsed": parsed,
        "dir_book": dir_book,
        "frontmatter": frontmatter,
        "sort": _to_int(sort_raw),
        "chapter_sort": _to_int(chapter_sort_raw),
    }
    return issues, metadata


def _check_chapter_sorts(
    chapters: dict[tuple[str, str], list[dict[str, Any]]]
) -> list[Issue]:
    """校验章内事件排序相关的 P1/P2 规则。"""
    issues: list[Issue] = []

    # 预计算：哪些 (book, chapter_sort) 是"细粒度单元"模式
    # 即同一 chapter_sort 下存在多个 chapter，且这些 chapter 大多为单事件
    module_groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    chapter_event_counts: dict[tuple[str, str], int] = {}
    for (book, chapter), events in chapters.items():
        cs = next((e["chapter_sort"] for e in events if e["chapter_sort"] is not None), None)
        chapter_event_counts[(book, chapter)] = len(events)
        if cs is not None:
            module_groups[(book, cs)].append(chapter)

    flexible_modules = {
        key for key, chs in module_groups.items()
        if len(chs) > 1 and all(chapter_event_counts[(key[0], ch)] == 1 for ch in chs)
    }

    for (book, chapter), events in sorted(chapters.items()):
        # 只保留有整数 sort 的事件做顺序校验
        sorted_events = [e for e in events if e["sort"] is not None]
        sort_values = [e["sort"] for e in sorted_events]

        cs = next((e["chapter_sort"] for e in events if e["chapter_sort"] is not None), None)
        is_flexible = cs is not None and (book, cs) in flexible_modules

        # P1: 重复 sort
        seen: dict[int, list[str]] = defaultdict(list)
        for event in sorted_events:
            seen[event["sort"]].append(event["rel"])
        for sort_val, files in seen.items():
            if len(files) > 1:
                issues.append(
                    Issue(
                        severity="P1",
                        book=book,
                        chapter=chapter,
                        file=", ".join(files),
                        message=f"sort 值重复: {sort_val}",
                        fix_suggestion=f"重新分配 sort，确保本章内唯一（当前重复值: {sort_val}）",
                    )
                )

        # P1: 非递增 sort
        if len(sort_values) >= 2:
            sorted_by_sort = sorted(sorted_events, key=lambda e: (e["sort"], e["rel"]))
            for i in range(1, len(sorted_by_sort)):
                prev = sorted_by_sort[i - 1]
                curr = sorted_by_sort[i]
                if curr["sort"] <= prev["sort"]:
                    issues.append(
                        Issue(
                            severity="P1",
                            book=book,
                            chapter=chapter,
                            file=curr["rel"],
                            message=(
                                f"sort 非递增: {prev['rel']}(sort={prev['sort']}) "
                                f"-> {curr['rel']}(sort={curr['sort']})"
                            ),
                            fix_suggestion=f"调整 sort，使事件按时间顺序严格递增（当前序列: {sort_values}）",
                        )
                    )

        # P1: 同一章的 chapter_sort 不一致
        chapter_sorts = [e["chapter_sort"] for e in events if e["chapter_sort"] is not None]
        if len(set(chapter_sorts)) > 1:
            files = [e["rel"] for e in events if e["chapter_sort"] is not None]
            issues.append(
                Issue(
                    severity="P1",
                    book=book,
                    chapter=chapter,
                    file=", ".join(files),
                    message=f"同一章的 chapter_sort 不一致: {sorted(set(chapter_sorts))}",
                    fix_suggestion=f"统一本章所有事件的 chapter_sort（当前值: {chapter_sorts}）",
                )
            )

        # P2: sort 未从 1 开始（细粒度单元模式放宽）
        if sort_values and min(sort_values) != 1 and not is_flexible:
            files = [e["rel"] for e in sorted_events]
            issues.append(
                Issue(
                    severity="P2",
                    book=book,
                    chapter=chapter,
                    file=", ".join(files),
                    message=f"sort 未从 1 开始（最小值: {min(sort_values)}）",
                    fix_suggestion="将本章最小 sort 值改为 1",
                )
            )

        # P2: sort 不连续（细粒度单元模式放宽）
        if sort_values and not is_flexible:
            expected = set(range(1, max(sort_values) + 1))
            missing = sorted(expected - set(sort_values))
            if missing:
                files = [e["rel"] for e in sorted_events]
                issues.append(
                    Issue(
                        severity="P2",
                        book=book,
                        chapter=chapter,
                        file=", ".join(files),
                        message=f"sort 值不连续，缺少: {missing}",
                        fix_suggestion=f"补全 sort 序列，使其连续无间断（当前: {sorted(sort_values)}）",
                    )
                )

        # P2: 单事件章节 sort != 1（细粒度单元模式放宽）
        if (
            len(events) == 1
            and events[0]["sort"] is not None
            and events[0]["sort"] != 1
            and not is_flexible
        ):
            issues.append(
                Issue(
                    severity="P2",
                    book=book,
                    chapter=chapter,
                    file=events[0]["rel"],
                    message=f"单事件章节的 sort 不为 1（当前: {events[0]['sort']}）",
                    fix_suggestion="将单事件章节的 sort 改为 1",
                )
            )

    return issues


def _group_by_chapter(file_metadata: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """按（书，章）对文件元数据分组，用于章内排序校验。"""
    chapters: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for meta in file_metadata:
        parsed = meta["parsed"]
        fm = meta["frontmatter"]
        if parsed is not None:
            book, chapter, _ = parsed
        elif fm.get("book") and fm.get("chapter"):
            book = fm["book"]
            chapter = fm["chapter"]
        else:
            continue
        chapters[(book, chapter)].append(meta)
    return chapters


def _format_summary(issues: list[Issue]) -> str:
    """生成按严重级别的汇总。"""
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    lines = [f"共发现 {len(issues)} 个问题："]
    for sev in SEVERITY_ORDER:
        lines.append(f"  {sev}: {counts[sev]}")
    return "\n".join(lines)


def _format_per_book_counts(issues: list[Issue]) -> str:
    """生成每本书的问题计数。"""
    if not issues:
        return "按书籍统计：无问题"
    books: dict[str, dict[str, int]] = defaultdict(lambda: {"P0": 0, "P1": 0, "P2": 0})
    for issue in issues:
        books[issue.book][issue.severity] += 1
    lines = ["按书籍统计："]
    for book in sorted(books.keys()):
        counts = books[book]
        lines.append(f"  {book}: P0={counts['P0']} P1={counts['P1']} P2={counts['P2']}")
    return "\n".join(lines)


def _format_detailed_issues(issues: list[Issue], include_fix: bool = False) -> str:
    """按书籍/章节分组输出问题详情。"""
    if not issues:
        return "未发现问题。"

    # 按 (book, chapter) 分组
    groups: dict[tuple[str, str], list[Issue]] = defaultdict(list)
    for issue in issues:
        groups[(issue.book, issue.chapter)].append(issue)

    lines: list[str] = []
    for (book, chapter) in sorted(groups.keys()):
        chapter_label = chapter if chapter else "（无章节）"
        lines.append(f"\n## {book} / {chapter_label}")
        group_issues = sorted(groups[(book, chapter)], key=lambda i: (SEVERITY_ORDER[i.severity], i.file, i.message))
        for issue in group_issues:
            lines.append(f"- [{issue.severity}] {issue.file}: {issue.message}")
            if include_fix:
                lines.append(f"  - 修复建议：{issue.fix_suggestion}")
    return "\n".join(lines)


def _format_fix_suggestions(issues: list[Issue]) -> str:
    """生成独立的修复建议列表。"""
    if not issues:
        return "无需修复。"
    lines = ["## Fix Suggestions", ""]
    for issue in sorted(
        issues,
        key=lambda i: (
            SEVERITY_ORDER[i.severity],
            i.book,
            i.chapter,
            i.file,
            i.message,
        ),
    ):
        chapter_label = issue.chapter if issue.chapter else "（无章节）"
        lines.append(
            f"- **[{issue.severity}] {issue.book} / {chapter_label} / {issue.file}**\n"
            f"  - 问题：{issue.message}\n"
            f"  - 建议：{issue.fix_suggestion}"
        )
    return "\n".join(lines)


def check_book_structure(output_dir: str) -> tuple[list[Issue], list[dict[str, Any]]]:
    """校验 output/ 下所有笔记的书籍结构。

    返回 (问题列表, 文件元数据列表)。
    """
    output_path = Path(output_dir)
    files = _collect_files(output_path)
    if not output_path.exists():
        return (
            [
                Issue(
                    severity="P0",
                    book="",
                    chapter="",
                    file="",
                    message=f"输出目录不存在: {output_dir}",
                    fix_suggestion=f"创建目录 {output_dir} 或指定正确的 --output 路径",
                )
            ],
            [],
        )

    all_issues: list[Issue] = []
    file_metadata: list[dict[str, Any]] = []

    for md_path in files:
        issues, meta = _check_file(md_path, output_path)
        all_issues.extend(issues)
        file_metadata.append(meta)

    chapters = _group_by_chapter(file_metadata)
    all_issues.extend(_check_chapter_sorts(chapters))

    return all_issues, file_metadata


def write_report(report_path: str, issues: list[Issue]) -> None:
    """将校验结果写入 Markdown 报告。"""
    lines = [
        "# 书籍结构校验报告",
        "",
        f"生成时间：{datetime.now().astimezone().replace(microsecond=0).isoformat()}",
        "",
        "## 汇总",
        "",
        _format_summary(issues),
        "",
        "## 按书籍统计",
        "",
        _format_per_book_counts(issues),
        "",
        "## 问题详情",
        "",
        _format_detailed_issues(issues, include_fix=True),
        "",
        _format_fix_suggestions(issues),
    ]
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="校验 output/ 下 Markdown 笔记的书籍结构与 frontmatter。"
    )
    parser.add_argument(
        "--output", default="output", help="笔记源目录（默认 output）"
    )
    parser.add_argument(
        "--report", default=None, help="输出 Markdown 报告的路径"
    )
    args = parser.parse_args(argv)

    issues, _ = check_book_structure(args.output)

    print(_format_summary(issues))
    print()
    print(_format_per_book_counts(issues))
    print()
    print(_format_detailed_issues(issues, include_fix=False))

    if args.report:
        write_report(args.report, issues)
        print(f"\n报告已写入: {args.report}")

    # 存在 P0/P1 问题时返回 1，P2 不阻断
    for issue in issues:
        if issue.severity in ("P0", "P1"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
