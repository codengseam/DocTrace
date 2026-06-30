#!/usr/bin/env python3
"""专栏级评分聚合脚本（反馈循环第一档收尾）。

批量遍历 output/ 下所有 *.md，跑 run_content_quality_checks 评分引擎，
输出专栏级聚合报告：avg/min/max/各维度问题分布/按 archetype 切分。

替代 docs/loop_log.md L264 人工手写的"全 67 章最低 97 最高 100 平均 99.4"，
让专栏级聚合能力可追溯、可复跑。

用法：
    python scripts/score_aggregate.py                      # 跑全部
    python scripts/score_aggregate.py --book 史记           # 跑单本
    python scripts/score_aggregate.py --output output      # 指定 output 目录
    python scripts/score_aggregate.py --save               # 结果写回 _meta.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 把 workspace root 加入 sys.path，使 from src.utils... 可导入
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_ARCHETYPE_DEFAULTS = {
    "史": "narrative", "经": "narrative",
    "技": "knowledge", "职场": "modern",
    "养生": "modern", "财": "modern", "心": "modern",
}


def _load_meta(book_dir: Path) -> Dict:
    """读 book_dir/_meta.yaml，无 PyYAML 时返回空 dict。"""
    meta_path = book_dir / "_meta.yaml"
    if not meta_path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except (ImportError, Exception):
        return {}


def _resolve_archetype(book: str, meta: Dict) -> str:
    """按 _meta.yaml.archetype → _meta.yaml.category → 默认表 解析 archetype。"""
    arch = meta.get("archetype")
    if arch in ("narrative", "modern", "knowledge"):
        return arch
    category = meta.get("category", "")
    return _ARCHETYPE_DEFAULTS.get(category, "narrative")


def _collect_md_files(output_dir: Path, book_filter: Optional[str]) -> List[Path]:
    """收集 output_dir 下所有 *.md（不含 _meta.yaml）。"""
    if book_filter:
        book_dir = output_dir / book_filter
        if not book_dir.exists():
            return []
        return sorted(book_dir.glob("*.md"))
    files = []
    for book_dir in sorted(output_dir.iterdir()):
        if book_dir.is_dir():
            files.extend(sorted(book_dir.glob("*.md")))
    return files


def _read_frontmatter_score(text: str) -> Optional[int]:
    """从已有 frontmatter 读 quality_score（不重新跑评分）。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        import yaml
        fm = yaml.safe_load(m.group(1)) or {}
    except (ImportError, Exception):
        # 无 PyYAML 时用正则兜底
        score_match = re.search(r"^quality_score:\s*(\d+)", m.group(1), re.MULTILINE)
        return int(score_match.group(1)) if score_match else None
    s = fm.get("quality_score")
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return int(s)
    return None


def aggregate_scores(
    output_dir: Path,
    book_filter: Optional[str] = None,
    rerun: bool = False,
) -> Dict:
    """聚合专栏级评分。

    Args:
        output_dir: output 目录路径
        book_filter: 仅跑指定书（None=全部）
        rerun: True=重新跑评分引擎；False=读已有 frontmatter 的 quality_score
    """
    from src.utils.content_quality import run_content_quality_checks

    md_files = _collect_md_files(output_dir, book_filter)
    if not md_files:
        return {"error": f"未在 {output_dir} 下找到 .md 文件", "books": {}}

    per_book: Dict[str, List[Dict]] = {}
    total_runs = 0
    total_errors = 0

    for md_path in md_files:
        book = md_path.parent.name
        per_book.setdefault(book, [])
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue

        if rerun:
            meta = _load_meta(md_path.parent)
            archetype = _resolve_archetype(book, meta)
            try:
                report = run_content_quality_checks(text, archetype=archetype)
                score = report.score
                dims = {k: len(v) for k, v in report.details.items()}
            except Exception as exc:
                total_errors += 1
                per_book[book].append({
                    "file": md_path.name,
                    "error": str(exc),
                })
                continue
        else:
            score = _read_frontmatter_score(text)
            if score is None:
                continue
            dims = {}

        per_book[book].append({
            "file": md_path.name,
            "score": score,
            **({"dimensions": dims} if dims else {}),
        })
        total_runs += 1

    # 按书聚合
    books_summary = {}
    all_scores: List[int] = []
    for book, items in per_book.items():
        scores = [it["score"] for it in items if "score" in it]
        if not scores:
            books_summary[book] = {"count": 0, "note": "无评分数据"}
            continue
        all_scores.extend(scores)
        books_summary[book] = {
            "count": len(scores),
            "avg": round(sum(scores) / len(scores), 1),
            "min": min(scores),
            "max": max(scores),
        }

    overall = None
    if all_scores:
        overall = {
            "total": len(all_scores),
            "avg": round(sum(all_scores) / len(all_scores), 1),
            "min": min(all_scores),
            "max": max(all_scores),
        }

    return {
        "overall": overall,
        "books": books_summary,
        "rerun_count": total_runs,
        "errors": total_errors,
    }


def format_report(result: Dict) -> str:
    """格式化聚合报告为 Markdown。"""
    lines = ["## 专栏级评分聚合报告", ""]
    if result.get("error"):
        lines.append(f"**错误**：{result['error']}")
        return "\n".join(lines)

    overall = result.get("overall")
    if overall:
        lines.extend([
            "### 总览",
            f"- 总篇数：{overall['total']}",
            f"- 平均分：{overall['avg']}",
            f"- 最低分：{overall['min']}",
            f"- 最高分：{overall['max']}",
            "",
        ])
    else:
        lines.extend(["### 总览", "无评分数据", ""])

    lines.append("### 按书统计")
    lines.append("")
    lines.append("| 书名 | 篇数 | 平均分 | 最低分 | 最高分 |")
    lines.append("|---|---|---|---|---|")
    for book, s in sorted(result.get("books", {}).items()):
        if s.get("count", 0) == 0:
            lines.append(f"| {book} | 0 | - | - | - |")
        else:
            lines.append(
                f"| {book} | {s['count']} | {s['avg']} | {s['min']} | {s['max']} |"
            )

    if result.get("rerun_count"):
        lines.append("")
        lines.append(f"（本次重跑评分 {result['rerun_count']} 篇，错误 {result['errors']} 项）")
    return "\n".join(lines)


def save_to_metas(output_dir: Path, result: Dict) -> None:
    """把每本书的 avg/min 写回 _meta.yaml。"""
    import yaml
    for book, s in result.get("books", {}).items():
        if s.get("count", 0) == 0:
            continue
        meta_path = output_dir / book / "_meta.yaml"
        if not meta_path.exists():
            continue
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["avg_score"] = s["avg"]
            meta["min_score"] = s["min"]
            tmp = meta_path.with_suffix(".tmp")
            tmp.write_text(
                yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            tmp.replace(meta_path)
        except Exception as exc:
            print(f"⚠️ 写回 {meta_path} 失败：{exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="专栏级评分聚合")
    parser.add_argument("--output", default="output", help="output 目录路径")
    parser.add_argument("--book", default=None, help="仅聚合指定书")
    parser.add_argument("--rerun", action="store_true", help="重新跑评分引擎（默认读已有 score）")
    parser.add_argument("--save", action="store_true", help="把 avg/min 写回 _meta.yaml")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    args = parser.parse_args()

    output_dir = Path(args.output)
    if not output_dir.exists():
        print(f"错误：{output_dir} 不存在", file=sys.stderr)
        sys.exit(1)

    result = aggregate_scores(output_dir, args.book, args.rerun)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))

    if args.save and not args.json:
        save_to_metas(output_dir, result)
        print("\n已把 avg/min 写回各书 _meta.yaml")


if __name__ == "__main__":
    main()
