#!/usr/bin/env python3
"""整理养生类课程：统一模块+章节结构、归入养生分类。

处理范围：
- 《饮食养生课》：按 _目录.md 的 10 模块 42 章整理。
- 《饮食养生课第二版》：把另一套模块文件（厨房之道/食养根本/食材列传/饮之有道/吃法决定命运/吃出一辈子）拆成独立书。
- 《睡眠与精力修复课》：按 _写作指南.md 的 7 模块 40 章整理。

效果：
- 文件命名：模块名_章节名.md
- frontmatter：book / chapter / event / title / sort / chapter_sort 一致
- _meta.yaml 统一 category: 养生
- 旧编号前缀从正文 H1 中移除，改为“模块名｜章节名”
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"

DIET_BOOK = "饮食养生课"
DIET_V2_BOOK = "饮食养生课第二版"
SLEEP_BOOK = "睡眠与精力修复课"

# 饮食养生课 canonical 结构：模块顺序 + 每模块下的章节顺序
DIET_MODULES: list[tuple[str, list[str]]] = [
    ("开篇", ["你为什么不会吃", "吃错一口身体记账", "你的饮食健康自测"]),
    (
        "饮食的底层逻辑",
        [
            "食物如何变成能量",
            "血糖过山车与胰岛素",
            "炎症从餐桌上开始",
            "肠道菌群第二基因组",
            "脾胃与昼夜节律",
        ],
    ),
    (
        "喝水",
        [
            "每天到底喝多少水",
            "喝水的时间与姿势",
            "白开水茶咖啡怎么选",
            "酒精的真相与误区",
        ],
    ),
    (
        "吃饭",
        [
            "三餐黄金比例",
            "主食的翻身仗",
            "蛋白质怎么挑",
            "脂肪的好坏之分",
            "彩虹饮食法",
            "进食顺序与七分饱",
            "手掌法则与五味调和",
        ],
    ),
    ("水果", ["水果的甜蜜陷阱", "果糖与代谢负担", "应季水果与寒热体质"]),
    (
        "菜谱与烹饪",
        [
            "健康家常菜原则",
            "快手早餐五分钟",
            "自带便当的学问",
            "一锅出的晚餐",
            "低油低盐与节气食方",
        ],
    ),
    (
        "饮食习惯",
        [
            "细嚼慢咽的力量",
            "规律进食与情绪性进食",
            "外卖与聚餐生存指南",
            "轻断食与间歇性禁食",
            "夜宵与家庭饮食环境",
        ],
    ),
    (
        "场景化解决方案",
        [
            "减脂期饮食",
            "增肌期饮食",
            "加班族与学生党",
            "熬夜后修复",
            "老年人饮食",
        ],
    ),
    (
        "误区与避坑",
        ["常见饮食误区", "网红减肥法与伪排毒", "保健品与代餐陷阱"],
    ),
    (
        "长期饮食体系",
        ["搭建个人饮食管理系统", "饮食与运动睡眠配合"],
    ),
]

# 饮食养生课第二版结构：从现有命名模块文件拆出
DIET_V2_MODULES: list[tuple[str, list[str]]] = [
    (
        "食养根本",
        [
            "一口饭的体内旅程",
            "人为什么会吃错",
            "你被这些常识骗了多少",
            "养生变瘦长寿的饮食公约数",
        ],
    ),
    (
        "食材列传",
        [
            "五谷为养",
            "五果为助",
            "五畜为益",
            "五菜为充",
            "奶与豆之辩",
            "蛋与鱼之优",
        ],
    ),
    (
        "饮之有道",
        [
            "每天该喝多少水",
            "汤粥的真相",
            "茶酒咖啡怎么选",
            "隐形糖与含糖饮料",
        ],
    ),
    (
        "吃法决定命运",
        [
            "三餐的黄金顺序",
            "七分饱与饱腹感",
            "细嚼慢咽的力量",
            "进食时间与昼夜节律",
            "外卖聚餐与情绪性进食",
        ],
    ),
    (
        "厨房之道",
        [
            "食材搭配的真科学",
            "油盐酱醋糖",
            "料酒味精醋",
            "火候之妙",
            "一荤一素一汤一菇",
            "一锅出与便当",
        ],
    ),
    (
        "吃出一辈子",
        [
            "你的饮食决策地图",
            "吃出不病抗炎饮食",
            "吃出轻盈减重不减肌",
            "吃出长寿蓝区与地中海",
            "不同年纪不同吃法",
        ],
    ),
]

# 睡眠与精力修复课结构
SLEEP_MODULES: list[tuple[str, list[str]]] = [
    (
        "开篇",
        [
            "你不是缺觉是不会休息",
            "为什么精力总不够用",
            "怎么用好这份修复指南",
        ],
    ),
    (
        "修复的底层逻辑",
        [
            "睡眠周期与九十分钟",
            "深睡修复身体",
            "快速眼动整理记忆",
            "精力耗散的本质",
            "古人怎么看待睡眠",
        ],
    ),
    (
        "夜间睡眠优化",
        [
            "打造深睡环境",
            "睡前仪式",
            "快速入睡法",
            "黄金九十分钟",
            "R90周期法",
            "固定作息的逻辑",
            "半夜醒来怎么办",
            "梦与睡眠质量",
            "正确补觉",
            "四季作息调整",
        ],
    ),
    (
        "日间快速修复",
        [
            "正确午睡",
            "子午觉的智慧",
            "十分钟工位回血",
            "主动走神",
            "散步恢复法",
            "闭目养神姿势",
            "咖啡因时机",
        ],
    ),
    (
        "冥想与呼吸修复",
        [
            "正念冥想入门",
            "走神冥想",
            "三分钟呼吸放松",
            "身体扫描",
            "4-7-8入睡呼吸法",
            "传统吐纳静坐",
            "焦虑急救呼吸",
        ],
    ),
    (
        "场景化解决方案",
        [
            "熬夜后修复",
            "高压加班回血",
            "考前睡眠保障",
            "焦虑失眠应对",
            "倒时差调作息",
        ],
    ),
    (
        "误区避坑与长期体系",
        [
            "常见睡眠误区",
            "越睡越累的真相",
            "长期精力管理体系",
        ],
    ),
]


def _build_lookup(modules: list[tuple[str, list[str]]]) -> dict[str, tuple[str, int, int]]:
    """返回 章节名 -> (模块名, 全局sort, 模块内chapter_sort) 的映射。"""
    lookup: dict[str, tuple[str, int, int]] = {}
    global_sort = 1
    for chapter_sort, (module, events) in enumerate(modules):
        for event in events:
            lookup[event] = (module, global_sort, chapter_sort)
            global_sort += 1
    return lookup


DIET_LOOKUP = _build_lookup(DIET_MODULES)
DIET_V2_LOOKUP = _build_lookup(DIET_V2_MODULES)
SLEEP_LOOKUP = _build_lookup(SLEEP_MODULES)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
# 匹配 # 饮食课·01｜标题... 或 # 睡眠课·01｜标题...
OLD_HEADING_RE = re.compile(r"^(# )(?:饮食课|睡眠课)・?\d+\s*[｜|]\s*(.+)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end():]
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_key is not None:
                item = stripped[2:].strip().strip('"').strip("'")
                if not isinstance(data.get(current_key), list):
                    data[current_key] = []
                data[current_key].append(item)
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            data[current_key] = value.strip().strip('"').strip("'")
    return data, body


def _dump_frontmatter(data: dict[str, Any]) -> str:
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, str):
            if any(c in v for c in [":", "#", "'", '"', "\n"]):
                v = v.replace('"', '\\"')
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af._-]", "_", name)
    safe = safe.replace("..", "_")
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("_-")
    return safe or "untitled"


def _migrate_book(
    book_dir: Path,
    new_book_name: str,
    lookup: dict[str, tuple[str, int, int]],
    title_prefix: str,
    dest_dir: Path | None = None,
    dry_run: bool = False,
) -> tuple[list[str], list[Path]]:
    """迁移一本书的所有文件，返回 (日志列表, 未匹配文件列表)。"""
    logs: list[str] = []
    skipped: list[Path] = []
    target_dir = dest_dir or book_dir
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    # 收集当前目录下所有 .md 笔记（非下划线开头）
    old_files = [p for p in book_dir.glob("*.md") if not p.name.startswith("_")]

    # 按 lookup 映射迁移
    for old_path in old_files:
        stem = old_path.stem
        # 从旧文件名提取章节名：旧格式为 饮食课XX_标题 / 睡眠课XX_标题 / 模块名_标题
        if "_" in stem:
            _, event = stem.split("_", 1)
        else:
            event = stem

        mapping = lookup.get(event)
        if not mapping:
            skipped.append(old_path)
            continue

        module, sort, chapter_sort = mapping
        new_stem = f"{_sanitize_filename(module)}_{_sanitize_filename(event)}"
        new_path = target_dir / f"{new_stem}.md"

        if dry_run:
            logs.append(f"[dry-run] 将迁移: {old_path.relative_to(OUTPUT)} -> {new_path.relative_to(OUTPUT)}")
            continue

        text = old_path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)

        fm["title"] = f"{title_prefix}·{event}"
        fm["book"] = new_book_name
        fm["chapter"] = module
        fm["event"] = event
        fm["sort"] = sort
        fm["chapter_sort"] = chapter_sort
        fm.setdefault("created_at", "2026-06-23")
        fm.setdefault("source_agents", ["diet-expert"])

        # 清理旧 H1 编号前缀：# 饮食课·01｜标题... -> # 模块名｜标题...
        def _replace_heading(m: re.Match[str]) -> str:
            rest = m.group(2)
            # rest 可能带副标题，保留
            return f"{m.group(1)}{module}｜{rest}"

        body = OLD_HEADING_RE.sub(_replace_heading, body)

        new_text = _dump_frontmatter(fm) + body.lstrip()
        new_path.write_text(new_text, encoding="utf-8")
        if old_path != new_path:
            old_path.unlink()
        logs.append(f"迁移: {old_path.relative_to(OUTPUT)} -> {new_path.relative_to(OUTPUT)}")

    return logs, skipped


def _update_meta(book_dir: Path, category: str) -> None:
    meta_path = book_dir / "_meta.yaml"
    text = meta_path.read_text(encoding="utf-8") if meta_path.exists() else ""
    lines = text.splitlines()
    new_lines = []
    replaced = False
    for line in lines:
        if line.strip().startswith("category:"):
            new_lines.append(f"category: {category}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"category: {category}")
    meta_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> int:
    diet_dir = OUTPUT / DIET_BOOK
    diet_v2_dir = OUTPUT / DIET_V2_BOOK
    sleep_dir = OUTPUT / SLEEP_BOOK

    logs: list[str] = []

    # 注意执行顺序：
    # 1. 先把《饮食养生课》目录里的“第二版”模块文件移走，避免与 canonical 章节同名冲突。
    # 2. 再处理 canonical 编号文件。
    # 3. 最后处理睡眠课。

    v2_logs, _ = _migrate_book(
        diet_dir,
        DIET_V2_BOOK,
        DIET_V2_LOOKUP,
        "饮食养生课第二版",
        dest_dir=diet_v2_dir,
    )
    logs += v2_logs

    primary_logs, _ = _migrate_book(
        diet_dir,
        DIET_BOOK,
        DIET_LOOKUP,
        "饮食养生课",
    )
    logs += primary_logs

    sleep_logs, _ = _migrate_book(
        sleep_dir,
        SLEEP_BOOK,
        SLEEP_LOOKUP,
        "睡眠课",
    )
    logs += sleep_logs

    # 更新 _meta.yaml
    _update_meta(diet_dir, "养生")
    _update_meta(diet_v2_dir, "养生")
    _update_meta(sleep_dir, "养生")
    logs.append("更新 _meta.yaml: category -> 养生")

    # 最终未匹配文件检查：扫描三本书目录，看是否还有未迁移的笔记
    all_book_dirs = [diet_dir, diet_v2_dir, sleep_dir]
    remaining: list[str] = []
    for book_dir in all_book_dirs:
        for p in sorted(book_dir.glob("*.md")):
            if p.name.startswith("_"):
                continue
            # 若文件名是旧编号格式，说明未迁移
            if re.match(r"^(?:饮食课|睡眠课)\d+_", p.name):
                remaining.append(str(p.relative_to(OUTPUT)))

    if remaining:
        logs.append("警告：以下旧文件未迁移：")
        for name in remaining:
            logs.append(f"  - {name}")

    print("\n".join(logs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
