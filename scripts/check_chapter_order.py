#!/usr/bin/env python3
"""章内事件时间排序校验脚本。

扫描 output/ 目录，对每个含多个事件的章节，校验 frontmatter 的 sort 字段：
1. 多事件章节：每个 event 必须有 sort 字段
2. sort 必须是整数
3. 同章内 sort 必须单调递增（无重复、无倒序）

用途：开发自检（dev-selfcheck Skill 触发）、CI 校验。与 build_site.py 分离，
校验失败不阻断站点构建。

用法：
    python scripts/check_chapter_order.py [--output output]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

FRONTMATTER_PATTERN = r"^---\s*\n(.*?)\n---\s*\n?"


def _parse_sort_from_frontmatter(content: str) -> tuple[int | None, str | None]:
    """从 Markdown frontmatter 提取 sort 字段。

    返回 (sort_value, error_msg)。sort_value 为 None 表示无 sort 字段
    或解析失败（error_msg 说明原因）。
    """
    match = re.match(FRONTMATTER_PATTERN, content, re.DOTALL)
    if not match:
        return None, None  # 无 frontmatter，不算错（单文件可能无）
    raw = match.group(1)
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("sort:"):
            value = stripped.split(":", 1)[1].strip()
            try:
                return int(value), None
            except ValueError:
                return None, f"sort 字段不是整数: {value!r}"
            return None, None
    return None, None  # 无 sort 字段


def _parse_note_path(rel_path: str) -> tuple[str, str, str] | None:
    """解析相对路径为 (book, chapter, event)。"""
    parts = rel_path.split("/")
    if len(parts) < 2:
        return None
    book = parts[0]
    stem = parts[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    if "_" in stem:
        chapter, event = stem.split("_", 1)
    else:
        chapter = stem
        event = ""
    return book, chapter, event


def check_chapter_order(output_dir: str = "output") -> list[str]:
    """校验 output/ 下所有章节内事件的时间排序。

    返回问题列表（空列表表示通过）。每个问题为一行描述。
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return [f"输出目录不存在: {output_dir}"]

    # book -> chapter -> [(event, sort_value, rel_path)]
    chapters: dict[str, dict[str, list[tuple[str, int | None, str]]]] = {}

    for md_path in sorted(output_path.rglob("*.md")):
        if md_path.name.startswith("_"):
            continue
        rel = md_path.relative_to(output_path)
        rel_str = str(rel).replace("\\", "/")
        parsed = _parse_note_path(rel_str)
        if parsed is None:
            continue
        book, chapter, event = parsed
        content = md_path.read_text(encoding="utf-8")
        sort_val, _ = _parse_sort_from_frontmatter(content)
        chapters.setdefault(book, {}).setdefault(chapter, []).append(
            (event, sort_val, rel_str)
        )

    issues: list[str] = []

    for book_name in sorted(chapters.keys()):
        for chapter_name in sorted(chapters[book_name].keys()):
            events = chapters[book_name][chapter_name]
            # 单事件章节无需排序校验
            if len(events) < 2:
                continue

            # 检查 1：多事件章节每个 event 必须有 sort 字段
            missing = [(ev, path) for ev, sv, path in events if sv is None]
            if missing:
                for ev, path in missing:
                    issues.append(
                        f"[{book_name}/{chapter_name}] {ev} 缺少 sort 字段（{path}）"
                    )
                continue  # 缺 sort 无法继续校验顺序

            # 检查 2：sort 必须无重复
            sort_values = [sv for _, sv, _ in events]
            seen: dict[int, str] = {}
            for ev, sv, path in events:
                if sv in seen:
                    issues.append(
                        f"[{book_name}/{chapter_name}] sort 重复: {ev} 与 "
                        f"{seen[sv]} 都用 sort={sv}（{path}）"
                    )
                else:
                    seen[sv] = ev

            # 检查 3：sort 必须单调递增（按 sort 排序后应与原顺序一致，
            # 且相邻 sort 递增）
            sorted_events = sorted(events, key=lambda e: (e[1], e[2]))
            for i in range(1, len(sorted_events)):
                prev_ev, prev_sv, _ = sorted_events[i - 1]
                curr_ev, curr_sv, _ = sorted_events[i]
                if curr_sv <= prev_sv:
                    issues.append(
                        f"[{book_name}/{chapter_name}] sort 非递增: "
                        f"{prev_ev}(sort={prev_sv}) → {curr_ev}(sort={curr_sv})"
                    )

    return issues


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。返回 0 表示通过，1 表示有问题。"""
    parser = argparse.ArgumentParser(
        description="校验 output/ 下章节内事件的时间排序（sort 字段）。"
    )
    parser.add_argument(
        "--output", default="output", help="笔记源目录（默认 output）"
    )
    args = parser.parse_args(argv)

    issues = check_chapter_order(args.output)

    if not issues:
        print("✅ 章内事件时间排序校验通过")
        return 0

    print(f"❌ 章内事件时间排序校验失败（{len(issues)} 个问题）:")
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
