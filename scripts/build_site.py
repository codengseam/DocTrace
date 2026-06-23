#!/usr/bin/env python3
"""静态站点构建脚本。

扫描 output/ 目录下的 Markdown 笔记，生成静态站点到 site/ 目录，
用于部署到 GitHub Pages。

用法：
    python scripts/build_site.py [--output output] [--site site]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 把项目根加入 sys.path，使 scripts/ 独立运行时也能 import src.utils.sorting
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.sorting import is_flat_book, sort_notes_tree  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

VERSION = "1.1.0"
FRONTMATTER_PATTERN = r"^---\s*\n(.*?)\n---\s*\n?"


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """解析 Markdown frontmatter，返回 (metadata, body)。

    优先使用 PyYAML；不可用时 fallback 到简单 key:value 解析。
    """
    match = re.match(FRONTMATTER_PATTERN, content, re.DOTALL)
    if not match:
        return {}, content

    raw = match.group(1)
    body = content[match.end():]

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


def _parse_note_path(rel_path: str) -> tuple[str, str, str] | None:
    """解析相对路径为 (book, chapter, event)。

    路径格式：book/chapter_event.md
    """
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


def _normalize_source_agents(value: Any) -> list[str]:
    """将 source_agents 规范化为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_created_at(value: Any) -> str:
    """将 created_at 规范化为字符串。"""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _load_book_meta(book_dir: Path, book_name: str) -> dict[str, Any]:
    """读取 book_dir/_meta.yaml，返回规范化后的元数据字典。

    无文件或解析失败时返回默认值：
    title=book_name, category="未分类", description="", author="",
    cover="📖", sort=99。
    """
    defaults: dict[str, Any] = {
        "title": book_name,
        "category": "未分类",
        "description": "",
        "author": "",
        "cover": "📖",
        "sort": 99,
    }
    meta_path = book_dir / "_meta.yaml"
    if not meta_path.exists() or yaml is None:
        return defaults
    try:
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if not isinstance(data, dict):
        return defaults

    result = dict(defaults)
    for key in ("title", "category", "description", "author", "cover"):
        value = data.get(key)
        if value is not None:
            result[key] = str(value)
    sort_value = data.get("sort")
    if sort_value is not None:
        try:
            result["sort"] = int(sort_value)
        except (TypeError, ValueError):
            pass
    return result


def _category_sort_key(category: str) -> tuple[int, str]:
    """返回 (priority, category) 用于排序。

    优先级：经(1) < 史(2) < 子(3) < 集(4) < 其他(50) < 未分类(99)。
    其他分类按字符串序（近似拼音序）排列。
    """
    priority_map = {
        "经": 1,
        "史": 2,
        "子": 3,
        "集": 4,
        "未分类": 99,
    }
    if category in priority_map:
        return (priority_map[category], category)
    return (50, category)


def build_site(output_dir: str = "output", site_dir: str = "site") -> Path:
    """扫描 output/ 下的 Markdown 笔记，生成静态站点到 site/。

    Args:
        output_dir: 笔记源目录，默认 "output"。
        site_dir: 静态站点输出目录，默认 "site"。

    Returns:
        站点输出目录的 Path。
    """
    output_path = Path(output_dir)
    site_path = Path(site_dir)

    data_dir = site_path / "data"
    notes_dir = site_path / "notes"
    data_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)

    # 清空 notes 目录，保证幂等（处理笔记删除场景）
    for child in notes_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    notes: dict[str, dict[str, Any]] = {}
    books: dict[str, dict[str, list[dict[str, Any]]]] = {}

    if output_path.exists():
        for md_path in sorted(output_path.rglob("*.md")):
            rel = md_path.relative_to(output_path)
            rel_str = str(rel).replace("\\", "/")
            parsed = _parse_note_path(rel_str)
            if parsed is None:
                continue
            book, chapter, event = parsed

            text = md_path.read_text(encoding="utf-8")
            frontmatter, content = _parse_frontmatter(text)

            title = frontmatter.get("title") or event or chapter
            if not isinstance(title, str):
                title = str(title)
            created_at = _normalize_created_at(frontmatter.get("created_at"))
            source_agents = _normalize_source_agents(frontmatter.get("source_agents"))

            note_entry = {
                "path": rel_str,
                "book": book,
                "chapter": chapter,
                "event": event,
                "title": title,
                "created_at": created_at,
                "source_agents": source_agents,
                "content": content,
            }
            notes[rel_str] = note_entry

            books.setdefault(book, {}).setdefault(chapter, []).append(
                {
                    "title": event or chapter,
                    "type": "event",
                    "path": rel_str,
                    "sort": frontmatter.get("sort"),
                    "chapter_sort": frontmatter.get("chapter_sort"),
                }
            )

            # 复制 Markdown 文件到 site/notes/（保持相对路径结构）
            dest = notes_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_path, dest)

    # 构建每本书的 tree（book -> chapter -> event）
    book_trees: dict[str, list[dict[str, Any]]] = {}
    for book_name in sorted(books.keys()):
        chapters: list[dict[str, Any]] = []
        for chapter_name in sorted(books[book_name].keys()):
            events = sorted(
                books[book_name][chapter_name], key=lambda e: e["path"]
            )
            # chapter_sort 取第一个有值的事件（同章所有事件应相同）
            chapter_sort = None
            for ev in events:
                if ev.get("chapter_sort") is not None:
                    chapter_sort = ev["chapter_sort"]
                    break
            chapters.append(
                {
                    "title": chapter_name,
                    "type": "chapter",
                    "children": events,
                    "chapter_sort": chapter_sort,
                }
            )
        book_trees[book_name] = chapters

    # 顶层 tree（向后兼容），并按朝代/序号规则排序
    tree: list[dict[str, Any]] = []
    for book_name in sorted(books.keys()):
        tree.append(
            {
                "title": book_name,
                "type": "book",
                "children": book_trees[book_name],
                "flat": is_flat_book(book_trees[book_name]),
            }
        )
    sort_notes_tree(tree)

    # 构建 books 数组（含元数据 + 本书 tree + 计数）
    books_array: list[dict[str, Any]] = []
    for book_name in books.keys():
        book_dir = output_path / book_name
        meta = _load_book_meta(book_dir, book_name)
        chapter_count = len(book_trees[book_name])
        note_count = sum(len(ch["children"]) for ch in book_trees[book_name])
        books_array.append(
            {
                "id": book_name,
                "title": meta["title"],
                "category": meta["category"],
                "description": meta["description"],
                "author": meta["author"],
                "cover": meta["cover"],
                "sort": meta["sort"],
                "chapter_count": chapter_count,
                "note_count": note_count,
                "tree": book_trees[book_name],
                "flat": is_flat_book(book_trees[book_name]),
            }
        )

    # 排序：category 优先级 → book sort → title
    books_array.sort(
        key=lambda b: (
            _category_sort_key(b["category"])[0],
            b["sort"],
            b["title"],
        )
    )

    # categories 列表（按优先级排序，只含实际出现的分类）
    categories = sorted(
        {b["category"] for b in books_array},
        key=_category_sort_key,
    )

    index = {
        "version": VERSION,
        "generated_at": datetime.now()
        .astimezone()
        .replace(microsecond=0)
        .isoformat(),
        "stats": {
            "books": len(books),
            "notes": len(notes),
            "categories": len(categories),
        },
        "books": books_array,
        "categories": categories,
        "tree": tree,
        "notes": notes,
    }

    index_path = data_dir / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 .nojekyll 标记，让 GitHub Pages 跳过 Jekyll 构建，直接部署静态文件
    (site_path / ".nojekyll").write_text("", encoding="utf-8")

    return site_path


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="扫描 output/ 下的 Markdown 笔记，生成静态站点到 site/。"
    )
    parser.add_argument(
        "--output", default="output", help="笔记源目录（默认 output）"
    )
    parser.add_argument(
        "--site", default="site", help="站点输出目录（默认 site）"
    )
    args = parser.parse_args(argv)

    site_path = build_site(output_dir=args.output, site_dir=args.site)
    print(f"静态站点已生成: {site_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
