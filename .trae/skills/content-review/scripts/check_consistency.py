#!/usr/bin/env python3
"""一致性检测命令行入口。

检测 AI 生成内容的前后矛盾、数据交叉矛盾、实体不一致。
纯规则实现，无需 LLM，结果可复现。

四类检测（详见 .trae/skills/content-review/rules/consistency-rules.md）：
1. 数值交叉矛盾：年龄-年份/在位时长/损失-剩余的数学矛盾
2. 同事件异值：同引文异字数/同战役异兵力/同典故异出处
3. 实体别名冲突：字号/谥号/籍贯冲突
4. 时间线倒置：讲事情段落年份逆序且无倒叙标注

用法：
    python .trae/skills/content-review/scripts/check_consistency.py --file output/史记/汉纪/07_鸿门宴.md
    python .trae/skills/content-review/scripts/check_consistency.py --dir output/ --strict
    python .trae/skills/content-review/scripts/check_consistency.py --file - < content.md

退出码：
    0  无问题，或未用 --strict
    1  发现 P0/P1 问题且使用了 --strict
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 把项目根加入 sys.path，使脚本可独立运行
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.consistency import check_consistency, format_consistency_report, ConsistencyIssue, ConsistencyReport

# 复用项目级 archetype 路由（config.yaml + 显式声明）
try:
    from src.utils.prompts import resolve_archetype
except ImportError:  # 兜底：prompts 模块不可用时使用路径启发式
    def resolve_archetype(category: str, explicit=None) -> str:
        return "narrative"


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _detect_archetype(path: Path, fallback: str = "narrative") -> str:
    """从 frontmatter category 字段解析 archetype，路径启发式兜底。"""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return fallback
    # 读 frontmatter category
    if _FRONTMATTER_RE:
        m = _FRONTMATTER_RE.match(content)
        if m:
            raw = m.group(1)
            # 找 category: X 行
            cat_match = re.search(r"^category:\s*[\"']?([^\"'\n]+)[\"']?\s*$", raw, re.MULTILINE)
            if cat_match:
                category = cat_match.group(1).strip()
                archetype = resolve_archetype(category)
                if archetype:
                    return archetype
            # 找 archetype: X 显式声明
            arch_match = re.search(r"^archetype:\s*[\"']?([^\"'\n]+)[\"']?\s*$", raw, re.MULTILINE)
            if arch_match:
                return arch_match.group(1).strip()
    # 兜底：路径启发式
    path_str = str(path)
    if any(k in path_str for k in ["职场", "理财", "养生", "晋升", "面试", "开车", "志愿", "高考", "新媒体"]):
        return "modern"
    if any(k in path_str for k in ["MySQL", "算法", "AI", "Python", "Java", "编程"]):
        return "knowledge"
    return fallback


def check_file(path: Path, archetype: str = "narrative") -> tuple[ConsistencyReport, str]:
    """检测单个文件，返回 (报告, 文件相对路径)。"""
    content = path.read_text(encoding="utf-8")
    report = check_consistency(content, archetype=archetype)
    try:
        rel = str(path.resolve().relative_to(_ROOT))
    except ValueError:
        rel = str(path)
    return report, rel


def check_dir(
    directory: Path,
    glob: str = "**/*.md",
    archetype_override: str | None = None,
) -> list[tuple[str, list[ConsistencyIssue]]]:
    """递归检测目录下所有 Markdown 文件。

    archetype_override 非 None 时，对所有文件使用同一 archetype（覆盖自动检测）。
    """
    results = []
    for md_path in sorted(directory.glob(glob)):
        if md_path.name.startswith("_"):
            continue
        if not md_path.is_file():
            continue
        try:
            archetype = archetype_override if archetype_override else _detect_archetype(md_path)
            report, rel = check_file(md_path, archetype)
            results.append((rel, report.issues))
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: 读取 {md_path} 失败：{exc}", file=sys.stderr)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="一致性检测：检测 AI 生成内容的前后矛盾、数据交叉矛盾、实体不一致"
    )
    parser.add_argument("--file", help="单文件路径，- 表示从 stdin 读取")
    parser.add_argument("--dir", default="", help="目录路径（默认 output/）")
    parser.add_argument("--glob", default="**/*.md", help="文件 glob 模式")
    parser.add_argument("--archetype", default=None, help="形态范式桶（narrative/modern/knowledge），未指定时自动检测；--dir 模式下作 override")
    parser.add_argument("--strict", action="store_true", help="发现 P0/P1 问题时退出码 1")
    parser.add_argument("--output", default="", help="报告输出文件路径（可选）")
    args = parser.parse_args(argv)

    if not args.file and not args.dir:
        args.dir = str(_ROOT / "output")

    all_results: list[tuple[str, list[ConsistencyIssue]]] = []

    if args.file:
        if args.file == "-":
            archetype = args.archetype or "narrative"
            content = sys.stdin.read()
            report = check_consistency(content, archetype=archetype)
            all_results.append(("<stdin>", report.issues))
            report_text = format_consistency_report(report)
        else:
            path = Path(args.file)
            if not path.exists():
                print(f"Error: 文件不存在：{path}", file=sys.stderr)
                return 1
            archetype = args.archetype or _detect_archetype(path)
            report, rel = check_file(path, archetype)
            all_results.append((rel, report.issues))
            report_text = format_consistency_report(report)
    else:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"Error: 目录不存在：{dir_path}", file=sys.stderr)
            return 1
        all_results = check_dir(dir_path, args.glob, archetype_override=args.archetype)
        # 汇总
        total_issues = sum(len(issues) for _, issues in all_results)
        lines = [
            "# 一致性检测汇总报告",
            "",
            f"扫描 {len(all_results)} 个文件，发现 {total_issues} 个一致性问题。",
            "",
        ]
        for rel, issues in all_results:
            if not issues:
                continue
            lines.append(f"## {rel}")
            lines.append("")
            for issue in issues:
                lines.append(f"- [{issue.severity}] {issue.message}")
                if issue.locations:
                    lines.append(f"  - 位置：行 {issue.locations}")
            lines.append("")
        report_text = "\n".join(lines) if total_issues else "✅ 无一致性问题。"

    # 输出
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_text, encoding="utf-8")
        print(f"一致性检测报告已保存至: {output_path}")
    else:
        print(report_text)

    # 退出码
    has_blocking = any(
        issue.severity in ("P0", "P1")
        for _, issues in all_results
        for issue in issues
    )
    if has_blocking and args.strict:
        print("\n[ERROR] --strict 模式：存在 P0/P1 一致性问题，请在合并/推送前修复。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
