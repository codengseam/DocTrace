#!/usr/bin/env python3
"""HaloRead loop_log.md 结构校验脚本。

校验项：
- [核心 P1] 1. 日期倒序：所有 "## YYYY-MM-DD ..." 标题按日期倒序排列
- [核心 P1] 2. #lesson slug 合法：每条记录底部 #lesson 标签必须来自受控 slug 表
- [P3 提示] 3. 索引锚点对应：索引区"最近10条"的锚点指向的 H2 必须存在
- [P3 提示] 4. #lesson 计数告警：同一 slug 出现 ≥3 次且未标"已入checklist: yes"时告警
- [P3 提示] 5. 化石区已迁出：loop_log.md 中不应出现"## 一、测评框架"等化石标题

退出码：
- 0：核心校验全部通过（P3 告警不阻断）
- 1：核心校验失败
- --strict 模式下 P3 告警也阻断

用法：
    python scripts/check_loop_log.py
    python scripts/check_loop_log.py --strict
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# 受控 slug 主题表（与 docs/loop_log.md 文件末"slug 主题表"一致）
CONTROLLED_SLUGS = {
    "git_hygiene",
    "reader_interaction",
    "content_quality",
    "book_structure",
    "deployment",
    "soul_injection",
    "ai_course",
}

# 化石标题正则（应已迁出到 docs/archive/loop_log_fossils.md）
FOSSIL_TITLE_PATTERNS = [
    re.compile(r"^## 一、测评框架", re.MULTILINE),
    re.compile(r"^## 二、循环记录", re.MULTILINE),
    re.compile(r"^## 三、开发沉淀记录", re.MULTILINE),
    re.compile(r"^### 第[一二三四五六七八九十百\d]+章", re.MULTILINE),
    re.compile(r"^### 第\d+章", re.MULTILINE),
]

H2_DATE_RE = re.compile(r"^## (\d{4})-(\d{2})-(\d{2})\b", re.MULTILINE)
LESSON_TAG_RE = re.compile(r"#lesson:\s*(\w+)")
INDEX_ANCHOR_RE = re.compile(r"^\- \[(\d{4}-\d{2}-\d{2})[^\]]*\]\(#L(\d+)\)", re.MULTILINE)
# 已入checklist 标记必须独占一行（行首到行尾），避免命中方案 C 手册里的示例文本。
CHECKLIST_MARKER_RE = re.compile(r"^已入checklist:\s*yes\s*$", re.MULTILINE | re.IGNORECASE)

DEFAULT_LOOP_LOG = Path(__file__).resolve().parent.parent / "docs" / "loop_log.md"


def _load(path: Path) -> str:
    if not path.exists():
        print(f"[P1] 文件不存在: {path}", file=sys.stderr)
        return ""
    return path.read_text(encoding="utf-8")


def check_date_descending(content: str) -> list[str]:
    """核心 P1：所有 ## YYYY-MM-DD 标题按日期倒序排列。返回错误列表。"""
    errors: list[str] = []
    matches = list(H2_DATE_RE.finditer(content))
    if not matches:
        errors.append("[P1] 未找到任何 ## YYYY-MM-DD ... 标题，日期倒序校验无法执行")
        return errors

    prev_date = ""
    prev_line = 0
    for m in matches:
        date_str = m.group(1) + "-" + m.group(2) + "-" + m.group(3)
        line_no = content.count("\n", 0, m.start()) + 1
        if prev_date and date_str > prev_date:
            errors.append(
                f"[P1] 日期非倒序：L{line_no} '{date_str}' 晚于上一条 '{prev_date}' (L{prev_line})"
            )
        prev_date = date_str
        prev_line = line_no
    return errors


def check_lesson_slug_legal(content: str) -> list[str]:
    """核心 P1：所有 #lesson slug 必须来自受控表。返回错误列表。"""
    errors: list[str] = []
    for m in LESSON_TAG_RE.finditer(content):
        slug = m.group(1)
        line_no = content.count("\n", 0, m.start()) + 1
        if slug not in CONTROLLED_SLUGS:
            errors.append(
                f"[P1] 非法 #lesson slug '{slug}' (L{line_no})，必须来自受控表："
                + ", ".join(sorted(CONTROLLED_SLUGS))
            )
    return errors


def check_index_anchors(content: str) -> list[str]:
    """P3：索引区"最近10条"的锚点指向的 H2 必须存在。返回告警列表。"""
    warnings: list[str] = []
    lines = content.split("\n")
    for m in INDEX_ANCHOR_RE.finditer(content):
        date_str = m.group(1)
        anchor_line = int(m.group(2))
        if anchor_line < 1 or anchor_line > len(lines):
            warnings.append(
                f"[P3] 索引锚点指向越界行号 L{anchor_line} (date={date_str})"
            )
            continue
        target = lines[anchor_line - 1]
        if not target.startswith("## "):
            warnings.append(
                f"[P3] 索引锚点 #L{anchor_line} 指向的不是 H2 标题（实际：'{target[:40]}'）"
            )
            continue
        if date_str not in target:
            warnings.append(
                f"[P3] 索引锚点 #L{anchor_line} 日期 {date_str} 与目标 H2 不匹配（'{target[:40]}'）"
            )
    return warnings


def check_lesson_count_warning(content: str) -> list[str]:
    """P3：同一 slug 出现 ≥3 次且未标"已入checklist: yes"时告警。返回告警列表。"""
    warnings: list[str] = []
    slug_counter: Counter[str] = Counter(LESSON_TAG_RE.findall(content))

    # 把每条记录（按 H2 切分）的"已入checklist: yes"标记收集起来
    # 简化策略：全文只要存在任一"已入checklist: yes"标记，则该 slug 视为已入
    has_checklist_marker = bool(CHECKLIST_MARKER_RE.search(content))

    for slug, count in slug_counter.items():
        if count >= 3 and not has_checklist_marker:
            warnings.append(
                f"[P3] #lesson slug '{slug}' 出现 {count} 次（≥3），但全文未发现"
                f"'已入checklist: yes' 标记，建议触发方案 C（见 docs/loop_log.md 文件末）"
            )
    return warnings


def check_fossil_migrated(content: str) -> list[str]:
    """P3：loop_log.md 中不应出现化石标题。返回告警列表。"""
    warnings: list[str] = []
    for pattern in FOSSIL_TITLE_PATTERNS:
        for m in pattern.finditer(content):
            line_no = content.count("\n", 0, m.start()) + 1
            warnings.append(
                f"[P3] 发现化石标题未迁出：L{line_no} '{m.group(0)}'，"
                f"应移到 docs/archive/loop_log_fossils.md"
            )
    return warnings


def run(path: Path, strict: bool = False) -> int:
    content = _load(path)
    if not content:
        return 1

    core_errors: list[str] = []
    p3_warnings: list[str] = []

    core_errors.extend(check_date_descending(content))
    core_errors.extend(check_lesson_slug_legal(content))
    p3_warnings.extend(check_index_anchors(content))
    p3_warnings.extend(check_lesson_count_warning(content))
    p3_warnings.extend(check_fossil_migrated(content))

    print(f"=== loop_log 结构校验 ({path}) ===")
    print(f"核心校验（P1）：{len(core_errors)} 项失败")
    for e in core_errors:
        print(f"  ❌ {e}")
    print(f"P3 提示：{len(p3_warnings)} 项")
    for w in p3_warnings:
        print(f"  ⚠️  {w}")

    if core_errors:
        print("\n结果：❌ 核心校验失败")
        return 1
    if strict and p3_warnings:
        print("\n结果：❌ --strict 模式下 P3 告警也阻断")
        return 1
    print("\n结果：✅ 核心校验通过" + ("（P3 告警不阻断）" if p3_warnings else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="HaloRead loop_log.md 结构校验")
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_LOOP_LOG,
        help=f"loop_log.md 路径（默认：{DEFAULT_LOOP_LOG}）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="P3 告警也阻断退出码",
    )
    args = parser.parse_args()
    return run(args.path, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
