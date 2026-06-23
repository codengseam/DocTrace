"""笔记排序工具模块。

按「朝代/纪 + 序号」对笔记树进行排序，支持可配置的分类顺序。
"""

from __future__ import annotations

from typing import Any

# 中文数字字符映射（一至九）
_DIGIT_MAP: dict[str, int] = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

# 书名 -> {分类名: 序号} 配置
BOOK_CATEGORY_ORDER: dict[str, dict[str, int]] = {
    "资治通鉴": {
        "周纪": 1,
        "秦纪": 2,
        "汉纪": 3,
        "魏纪": 4,
        "晋纪": 5,
        "宋纪": 6,
        "齐纪": 7,
        "梁纪": 8,
        "陈纪": 9,
        "隋纪": 10,
        "唐纪": 11,
        "后梁纪": 12,
        "后唐纪": 13,
        "后晋纪": 14,
        "后汉纪": 15,
        "后周纪": 16,
    },
    "史记": {
        "本纪": 1,
        "表": 2,
        "书": 3,
        "世家": 4,
        "列传": 5,
    },
}

# 未配置/无法匹配时的回退大数，保证排在已配置章节之后
_FALLBACK_ORDER = 9999


def parse_chinese_number(text: str) -> int:
    """解析中文数字（一至九十九）或纯阿拉伯数字。

    - 纯阿拉伯数字：直接 int()
    - 中文数字（含"十"）：解析为整数，如 "二十三" → 23
    - 单字中文数字：如 "五" → 5
    - 无法解析：返回 0
    """
    if not text:
        return 0
    text = text.strip()
    # 纯阿拉伯数字
    if text.isdigit():
        try:
            return int(text)
        except ValueError:
            return 0
    # 含"十"的中文数字
    if "十" in text:
        left, _, right = text.partition("十")
        tens = _DIGIT_MAP.get(left, 1) if left else 1
        ones = _DIGIT_MAP.get(right, 0) if right else 0
        return tens * 10 + ones
    # 单字中文数字
    return _DIGIT_MAP.get(text, 0)


def chapter_sort_key(book: str, chapter: str) -> tuple[int, int, str]:
    """返回章节排序键 (category_order, ordinal, chapter_str)。

    - 查书的分类配置；匹配章节名前缀（长前缀优先，如"后周纪"优先于"周纪"）
    - 剩余部分解析为序号
    - 未配置的书或无法匹配的章节：回退为 (大数, 0, chapter_str)
    """
    categories = BOOK_CATEGORY_ORDER.get(book)
    if not categories:
        return (_FALLBACK_ORDER, 0, chapter)
    # 长前缀优先匹配，避免 "周纪" 误匹配 "后周纪"
    for prefix in sorted(categories.keys(), key=len, reverse=True):
        if chapter.startswith(prefix):
            ordinal = parse_chinese_number(chapter[len(prefix):])
            return (categories[prefix], ordinal, chapter)
    return (_FALLBACK_ORDER, 0, chapter)


def is_flat_book(chapters: list[dict[str, Any]]) -> bool:
    """判断一本书是否所有 chapter 标题都是纯数字（用于前端折叠数字层级）。

    纯数字 chapter 通常来自 `序号_主题.md` 命名（如论语 01_孔子的一生），
    数字本身无展示意义，前端应折叠该层直接显示事件标题。
    混合 chapter（如史记既有"秦纪一"又有"01"）不折叠，避免结构不一致。
    """
    if not chapters:
        return False
    return all(
        isinstance(ch.get("title", ""), str)
        and ch.get("title", "").strip().isdigit()
        for ch in chapters
    )


def sort_notes_tree(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对 tree 结构就地按规则排序并返回。

    - book 节点按书名排序
    - 每个 book 的 children（chapter）按 chapter_sort_key 排序
    - 每个 chapter 的 children（event）按 path 排序（保持稳定）
    """
    tree.sort(key=lambda node: node.get("title", ""))
    for book_node in tree:
        book_name = book_node.get("title", "")
        children = book_node.get("children") or []
        children.sort(
            key=lambda ch: chapter_sort_key(book_name, ch.get("title", ""))
        )
        for chapter_node in children:
            events = chapter_node.get("children") or []
            # 优先按 frontmatter 的 sort 字段排序（章内事件历史时间顺序）；
            # 无 sort 字段时回退到 path 排序，保证向后兼容。
            # sort key 用 (is_none, sort_value, path) 三元组，确保 None 不与 int
            # 直接比较而抛 TypeError：is_none=True 的节点统一排到有 sort 值的节点之后。
            events.sort(
                key=lambda e: (
                    e.get("sort") is None,
                    e.get("sort") if e.get("sort") is not None else 0,
                    e.get("path", ""),
                )
            )
    return tree
