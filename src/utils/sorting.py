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
        "秦纪": 1,
        "汉纪": 2,
        "本纪": 3,
        "表": 4,
        "书": 5,
        "世家": 6,
        "列传": 7,
    },
    "唐纪": {"唐纪": 1},
    "宋纪": {"宋纪": 1},
    "明纪": {
        "元末群雄与明朝建立": 1,
        "洪武之治与集权": 2,
        "永乐盛世与仁宣之治": 3,
        "土木之变与夺门之变": 4,
        "成弘正之治与社会转型": 5,
        "嘉靖隆庆与张居正改革": 6,
        "万历怠政与晚明危机": 7,
        "明亡与清军入关": 8,
    },
}

# 未配置/无法匹配时的回退大数，保证排在已配置章节之后
_FALLBACK_ORDER = 9999

# 「阶段模式」书籍：chapter_sort 表示大阶段顺序（如朝代/纪），
# 同一阶段下的章节再按章节名中的序号排序。
STAGE_MODE_BOOKS: set[str] = {"资治通鉴", "明纪"}


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
    """判断章节列表是否为"扁平"结构（所有章节标题都是纯数字）。

    空列表返回 False；任一章节标题不是纯数字也返回 False。
    """
    if not chapters:
        return False
    for ch in chapters:
        title = str(ch.get("title", "")).strip()
        if not title.isdigit():
            return False
    return True


def _to_int(value: Any) -> int | None:
    """将节点上的排序值安全转为整数；失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sort_notes_tree(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对 tree 结构就地按规则排序并返回。

    - book 节点按书名排序
    - chapter 节点：
      - 「阶段模式」书籍（如资治通鉴）：chapter_sort 表示朝代/纪阶段顺序，
        同一阶段内按章节名序号排序；无 chapter_sort 时回退到 chapter_sort_key。
      - 其他书籍：优先按 frontmatter 中的 chapter_sort 排序；
        无 chapter_sort 时回退到 chapter_sort_key（朝代/纪序号等）。
    - event 节点优先按 frontmatter 中的 sort 排序；
      无 sort 时回退到 path 排序（保持稳定）
    """
    tree.sort(key=lambda node: node.get("title", ""))
    for book_node in tree:
        book_name = book_node.get("title", "")
        children = book_node.get("children") or []
        stage_mode = book_name in STAGE_MODE_BOOKS

        def chapter_key(ch: dict[str, Any]) -> tuple[int, int, str]:
            title = str(ch.get("title", ""))
            explicit = _to_int(ch.get("chapter_sort"))
            canonical = chapter_sort_key(book_name, title)

            if stage_mode:
                # chapter_sort 是阶段顺序；章节名序号作为阶段内二次排序
                primary = explicit if explicit is not None else canonical[0]
                return (primary, canonical[1], title)

            # 非阶段模式：chapter_sort 是绝对顺序，内部按 event sort 稳定
            events = ch.get("children") or []
            event_sorts = [_to_int(e.get("sort")) for e in events]
            min_event_sort = min(
                [s for s in event_sorts if s is not None], default=0
            )
            if explicit is not None:
                return (explicit, min_event_sort, title)
            return (canonical[0], canonical[1], title)

        children.sort(key=chapter_key)

        for chapter_node in children:
            events = chapter_node.get("children") or []

            def event_key(e: dict[str, Any]) -> tuple[int, int, str]:
                explicit = _to_int(e.get("sort"))
                if explicit is not None:
                    return (0, explicit, "")
                return (1, 0, str(e.get("path", "")))

            events.sort(key=event_key)
    return tree
