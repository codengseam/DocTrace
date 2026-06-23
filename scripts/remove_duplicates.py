#!/usr/bin/env python3
"""删除 output/ 目录下内容重复的 Markdown 笔记。

保留优先级更高的文件（主题分组文件），删除其余重复文件。
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
BODY_FM_PATTERN = re.compile(rb"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
KEY_FM_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
ARABIC_DIGITS = re.compile(r"[0-9]")
CHINESE_CHARS = re.compile(r"[\u4e00-\u9fff]")


def _note_body(path: Path) -> bytes:
    content = path.read_bytes()
    return BODY_FM_PATTERN.sub(b"", content, count=1).strip()


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    """简单 frontmatter 解析，不依赖 PyYAML，只取标量 key: value。"""
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not match:
        return {}
    fm: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            # 列表项跳过，不影响本章判断
            continue
        km = KEY_FM_PATTERN.match(stripped)
        if not km:
            continue
        key, value = km.group(1), km.group(2).strip()
        # 去掉引号
        value = value.strip('"').strip("'")
        if key in ("sort", "chapter_sort"):
            try:
                fm[key] = int(value)
            except ValueError:
                fm[key] = value
        else:
            fm[key] = value
    return fm


def _filename_chapter(rel: str) -> str:
    """从相对路径解析出文件名中的 chapter 部分。"""
    stem = Path(rel).stem
    if "_" in stem:
        return stem.split("_", 1)[0]
    return stem


def _file_score(rel: str, fm: dict[str, Any]) -> tuple[int, int, str]:
    """返回文件保留优先级（越大越优先），以及用于并列的 path 键。"""
    score = 0
    fn_chapter = _filename_chapter(rel)
    fm_chapter = str(fm.get("chapter", "")).strip()
    # frontmatter 中的 chapter 与文件名 chapter 一致，说明是主题分组文件
    if fm_chapter and fm_chapter == fn_chapter:
        score += 10000
    # 有显式排序字段，更可能是规范文件
    if fm.get("sort") is not None or fm.get("chapter_sort") is not None:
        score += 1000
    # 主题名越长（中文越多），越倾向于保留
    chapter_cn_len = len(CHINESE_CHARS.findall(fn_chapter))
    score += chapter_cn_len
    # 文件名含阿拉伯数字的扣分
    if ARABIC_DIGITS.search(Path(rel).name):
        score -= 5
    # 路径越短/字典序越小越优先（用于最终 tie-break）
    return (score, -len(rel), rel)


def find_duplicates() -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for md_path in sorted(OUTPUT_DIR.rglob("*.md")):
        body = _note_body(md_path)
        h = hashlib.sha256(body).hexdigest()
        groups.setdefault(h, []).append(md_path)
    return {h: files for h, files in groups.items() if len(files) > 1}


def remove_duplicates() -> list[Path]:
    """删除重复文件，返回被删除的文件路径列表。"""
    removed: list[Path] = []
    dups = find_duplicates()
    if not dups:
        return removed

    for files in dups.values():
        scored = []
        for f in files:
            rel = str(f.relative_to(ROOT)).replace("\\", "/")
            fm = _parse_frontmatter(f)
            scored.append((_file_score(rel, fm), f))
        scored.sort(key=lambda x: x[0], reverse=True)
        for _, f in scored[1:]:
            print(f"删除重复文件: {f.relative_to(ROOT)}")
            f.unlink()
            removed.append(f)

    # 清理空目录
    for book_dir in sorted(OUTPUT_DIR.iterdir()):
        if not book_dir.is_dir():
            continue
        for subdir in list(book_dir.rglob("*")):
            if subdir.is_dir() and not any(subdir.iterdir()):
                print(f"删除空目录: {subdir.relative_to(ROOT)}")
                shutil.rmtree(subdir)

    return removed


def main(argv: list[str] | None = None) -> int:
    removed = remove_duplicates()
    if removed:
        print(f"\n共删除 {len(removed)} 个重复文件。")
    else:
        print("没有需要删除的重复文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
