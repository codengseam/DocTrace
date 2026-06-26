"""src/utils/sorting.py 的单元测试。

覆盖：
- parse_chinese_number：阿拉伯数字、中文数字（含"十"）、单字、空串、无法解析
- chapter_sort_key：朝代序号、长前缀优先匹配、未配置书回退
- is_flat_book：空列表、全纯数字、混合、非数字
- sort_notes_tree：book/chapter/event 三级排序、sort 字段优先、None 回退、稳定排序
- wellness books 章内 sort 连续性（BUG-017）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.utils.sorting import (
    chapter_sort_key,
    is_flat_book,
    parse_chinese_number,
    sort_notes_tree,
)


# ---------- parse_chinese_number ----------


def test_parse_chinese_number_arabic():
    """纯阿拉伯数字直接 int。"""
    assert parse_chinese_number("1") == 1
    assert parse_chinese_number("23") == 23
    assert parse_chinese_number("99") == 99


def test_parse_chinese_number_single():
    """单字中文数字。"""
    assert parse_chinese_number("一") == 1
    assert parse_chinese_number("五") == 5
    assert parse_chinese_number("九") == 9


def test_parse_chinese_number_ten():
    """含"十"的中文数字。"""
    assert parse_chinese_number("十") == 10
    assert parse_chinese_number("十一") == 11
    assert parse_chinese_number("二十") == 20
    assert parse_chinese_number("二十三") == 23
    assert parse_chinese_number("九十九") == 99


def test_parse_chinese_number_empty_and_invalid():
    """空串与无法解析返回 0。"""
    assert parse_chinese_number("") == 0
    assert parse_chinese_number("   ") == 0
    assert parse_chinese_number("abc") == 0
    assert parse_chinese_number("周纪") == 0


def test_parse_chinese_number_strips_whitespace():
    """前后空白被剥离。"""
    assert parse_chinese_number("  5  ") == 5
    assert parse_chinese_number("  二十  ") == 20


# ---------- chapter_sort_key ----------


def test_chapter_sort_key_zizhi():
    """资治通鉴周纪按序号排序。"""
    assert chapter_sort_key("资治通鉴", "周纪一") == (1, 1, "周纪一")
    assert chapter_sort_key("资治通鉴", "周纪四") == (1, 4, "周纪四")
    assert chapter_sort_key("资治通鉴", "周纪十") == (1, 10, "周纪十")


def test_chapter_sort_key_category_order():
    """资治通鉴各朝代按配置顺序：周纪<秦纪<汉纪。"""
    zhou = chapter_sort_key("资治通鉴", "周纪一")
    qin = chapter_sort_key("资治通鉴", "秦纪一")
    han = chapter_sort_key("资治通鉴", "汉纪一")
    assert zhou < qin < han


def test_chapter_sort_key_long_prefix_priority():
    """长前缀优先匹配：后周纪不应被周纪误匹配。"""
    # 后周纪序号 16，周纪序号 1
    hou_zhou = chapter_sort_key("资治通鉴", "后周纪一")
    zhou = chapter_sort_key("资治通鉴", "周纪一")
    # 后周纪的 category_order (16) > 周纪 (1)
    assert hou_zhou[0] == 16
    assert zhou[0] == 1
    assert hou_zhou > zhou


def test_chapter_sort_key_shiji():
    """史记按秦纪/汉纪/本纪/表/书/世家/列传顺序。"""
    assert chapter_sort_key("史记", "秦纪一") == (1, 1, "秦纪一")
    assert chapter_sort_key("史记", "汉纪一") == (2, 1, "汉纪一")
    assert chapter_sort_key("史记", "列传七") == (7, 7, "列传七")


def test_chapter_sort_key_tang_song_ming():
    """唐纪/宋纪 按中文数字序号排序；明纪按模块名完全匹配阶段序号。"""
    assert chapter_sort_key("唐纪", "唐纪一") == (1, 1, "唐纪一")
    assert chapter_sort_key("唐纪", "唐纪三十三") == (1, 33, "唐纪三十三")
    assert chapter_sort_key("宋纪", "宋纪三十三") == (1, 33, "宋纪三十三")
    # 明纪改为模块名模式：chapter 是完整模块名，startswith 完全匹配，
    # 无数字后缀故 ordinal=0
    assert chapter_sort_key("明纪", "元末群雄与明朝建立") == (1, 0, "元末群雄与明朝建立")
    assert chapter_sort_key("明纪", "洪武之治与集权") == (2, 0, "洪武之治与集权")
    assert chapter_sort_key("明纪", "明亡与清军入关") == (8, 0, "明亡与清军入关")
    # 阶段序号正确：元末(1) < 洪武(2) < ... < 明亡(8)
    assert chapter_sort_key("明纪", "元末群雄与明朝建立") < chapter_sort_key("明纪", "明亡与清军入关")
    # 未配置的模块名回退为大数
    assert chapter_sort_key("明纪", "不存在的模块")[0] == 9999


def test_chapter_sort_key_unconfigured_book():
    """未配置的书回退为大数。"""
    key = chapter_sort_key("论语", "学而")
    assert key == (9999, 0, "学而")


def test_chapter_sort_key_unmatched_chapter():
    """配置书但章节名不匹配任何前缀，回退大数。"""
    key = chapter_sort_key("资治通鉴", "杂事")
    assert key == (9999, 0, "杂事")


# ---------- is_flat_book ----------


def test_is_flat_book_empty():
    """空列表返回 False。"""
    assert is_flat_book([]) is False


def test_is_flat_book_all_numeric():
    """所有 chapter 标题都是纯数字 → True。"""
    chapters = [
        {"title": "01", "children": []},
        {"title": "02", "children": []},
        {"title": "03", "children": []},
    ]
    assert is_flat_book(chapters) is True


def test_is_flat_book_mixed():
    """混合（数字 + 非数字）→ False。"""
    chapters = [
        {"title": "01", "children": []},
        {"title": "秦纪一", "children": []},
    ]
    assert is_flat_book(chapters) is False


def test_is_flat_book_non_numeric():
    """全非数字 → False。"""
    chapters = [
        {"title": "周纪一", "children": []},
        {"title": "周纪二", "children": []},
    ]
    assert is_flat_book(chapters) is False


def test_is_flat_book_missing_title():
    """缺 title 字段视为非数字 → False。"""
    chapters = [
        {"title": "01", "children": []},
        {"children": []},
    ]
    assert is_flat_book(chapters) is False


def test_is_flat_book_whitespace_digits():
    """带空白的纯数字仍算数字。"""
    chapters = [{"title": "  01  ", "children": []}]
    assert is_flat_book(chapters) is True


# ---------- sort_notes_tree ----------


def _make_event(title: str, path: str, sort: int | None = None) -> dict:
    """构造 event 节点。"""
    node = {"title": title, "type": "event", "path": path}
    if sort is not None:
        node["sort"] = sort
    return node


def _make_chapter(
    title: str, events: list[dict], chapter_sort: int | None = None
) -> dict:
    node = {"title": title, "type": "chapter", "children": events}
    if chapter_sort is not None:
        node["chapter_sort"] = chapter_sort
    return node


def _make_book(title: str, chapters: list[dict]) -> dict:
    return {"title": title, "type": "book", "children": chapters}


def test_sort_notes_tree_book_order():
    """book 节点按 title 排序。"""
    tree = [
        _make_book("资治通鉴", []),
        _make_book("论语", []),
        _make_book("史记", []),
    ]
    sort_notes_tree(tree)
    assert [b["title"] for b in tree] == ["史记", "论语", "资治通鉴"]


def test_sort_notes_tree_chapter_order_zizhi():
    """资治通鉴 chapter 按朝代+序号排序。"""
    tree = [
        _make_book(
            "资治通鉴",
            [
                _make_chapter("周纪四", []),
                _make_chapter("周纪一", []),
                _make_chapter("秦纪一", []),
                _make_chapter("汉纪二", []),
            ],
        )
    ]
    sort_notes_tree(tree)
    chapters = tree[0]["children"]
    assert [c["title"] for c in chapters] == [
        "周纪一",
        "周纪四",
        "秦纪一",
        "汉纪二",
    ]


def test_sort_notes_tree_zizhi_stage_mode_orders_by_ordinal():
    """阶段模式：同一 chapter_sort 下按章节名中文序号排序，避免字符串序。"""
    tree = [
        _make_book(
            "资治通鉴",
            [
                _make_chapter("汉纪十五", [], chapter_sort=3),
                _make_chapter("汉纪三", [], chapter_sort=3),
                _make_chapter("汉纪十七", [], chapter_sort=3),
                _make_chapter("汉纪二", [], chapter_sort=3),
                _make_chapter("周纪四", [], chapter_sort=1),
            ],
        )
    ]
    sort_notes_tree(tree)
    chapters = tree[0]["children"]
    assert [c["title"] for c in chapters] == [
        "周纪四",
        "汉纪二",
        "汉纪三",
        "汉纪十五",
        "汉纪十七",
    ]


def test_sort_notes_tree_event_sort_field_priority():
    """event 优先按 sort 字段排序（章内事件历史时间顺序）。"""
    # 故意把 path 顺序打乱，验证 sort 字段优先
    tree = [
        _make_book(
            "资治通鉴",
            [
                _make_chapter(
                    "周纪四",
                    [
                        _make_event("完璧归赵", "a.md", sort=2),
                        _make_event("胡服骑射", "b.md", sort=1),
                        _make_event("负荆请罪", "c.md", sort=4),
                        _make_event("渑池之会", "d.md", sort=3),
                    ],
                )
            ],
        )
    ]
    sort_notes_tree(tree)
    events = tree[0]["children"][0]["children"]
    assert [e["title"] for e in events] == [
        "胡服骑射",
        "完璧归赵",
        "渑池之会",
        "负荆请罪",
    ]


def test_sort_notes_tree_event_none_sort_fallback_to_path():
    """无 sort 字段时回退到 path 排序，且排在有 sort 值的节点之后。"""
    tree = [
        _make_book(
            "资治通鉴",
            [
                _make_chapter(
                    "周纪一",
                    [
                        _make_event("无排序B", "b.md"),
                        _make_event("有排序2", "z.md", sort=2),
                        _make_event("无排序A", "a.md"),
                        _make_event("有排序1", "y.md", sort=1),
                    ],
                )
            ],
        )
    ]
    sort_notes_tree(tree)
    events = tree[0]["children"][0]["children"]
    # 有 sort 的先排：sort=1 → sort=2
    # 无 sort 的后排：按 path → a.md → b.md
    assert [e["title"] for e in events] == [
        "有排序1",
        "有排序2",
        "无排序A",
        "无排序B",
    ]


def test_sort_notes_tree_event_all_none_uses_path():
    """全部 event 无 sort 字段时，纯按 path 排序（向后兼容）。"""
    tree = [
        _make_book(
            "论语",
            [
                _make_chapter(
                    "学而",
                    [
                        _make_event("事件C", "c.md"),
                        _make_event("事件A", "a.md"),
                        _make_event("事件B", "b.md"),
                    ],
                )
            ],
        )
    ]
    sort_notes_tree(tree)
    events = tree[0]["children"][0]["children"]
    assert [e["title"] for e in events] == ["事件A", "事件B", "事件C"]


def test_sort_notes_tree_event_sort_does_not_crash_on_none():
    """sort 字段混合 None 与 int 不抛 TypeError（回归测试）。"""
    tree = [
        _make_book(
            "资治通鉴",
            [
                _make_chapter(
                    "周纪四",
                    [
                        _make_event("无排序", "x.md"),
                        _make_event("有排序", "y.md", sort=1),
                    ],
                )
            ],
        )
    ]
    # 不应抛 TypeError
    sort_notes_tree(tree)
    events = tree[0]["children"][0]["children"]
    assert len(events) == 2


def test_sort_notes_tree_in_place_return():
    """sort_notes_tree 就地排序并返回同一对象。"""
    tree = [_make_book("论语", [])]
    result = sort_notes_tree(tree)
    assert result is tree


def test_sort_notes_tree_empty():
    """空树不报错。"""
    assert sort_notes_tree([]) == []


def test_sort_notes_tree_preserves_flat_flag():
    """排序不破坏 book 节点上的 flat 标记。"""
    tree = [
        {
            "title": "论语",
            "type": "book",
            "flat": True,
            "children": [
                _make_chapter("01", [_make_event("孔子", "a.md")]),
                _make_chapter("02", [_make_event("性格", "b.md")]),
            ],
        }
    ]
    sort_notes_tree(tree)
    assert tree[0]["flat"] is True


def test_sort_notes_tree_unconfigured_book_chapter_kept():
    """未配置书的 chapter 仍保留（回退大数），按字符串序稳定。"""
    tree = [
        _make_book(
            "无名书",
            [
                _make_chapter("第二章", []),
                _make_chapter("第一章", []),
            ],
        )
    ]
    sort_notes_tree(tree)
    chapters = tree[0]["children"]
    # 两者都回退到 (9999, 0, chapter)，按 chapter 字符串序
    assert [c["title"] for c in chapters] == ["第一章", "第二章"]


def test_sort_notes_tree_yijing_chapter_and_event_order():
    """易经课按大模块与卦序排序：chapter_sort 定模块，event sort 定卦序。"""
    tree = [
        _make_book(
            "易经课",
            [
                _make_chapter("中孚卦", [_make_event("诚信感物", "z.md", sort=31)], chapter_sort=4),
                _make_chapter("乾卦", [_make_event("健行不息", "a.md", sort=1)], chapter_sort=3),
                _make_chapter("基础", [_make_event("四象与八卦", "b.md", sort=2)], chapter_sort=2),
                _make_chapter("开篇", [_make_event("为什么要学易经", "c.md", sort=2)], chapter_sort=1),
                _make_chapter("坤卦", [_make_event("厚德载物", "d.md", sort=2)], chapter_sort=3),
                _make_chapter("咸卦", [_make_event("感应之道", "e.md", sort=1)], chapter_sort=4),
            ],
        )
    ]
    sort_notes_tree(tree)
    chapters = tree[0]["children"]
    assert [c["title"] for c in chapters] == [
        "开篇",
        "基础",
        "乾卦",
        "坤卦",
        "咸卦",
        "中孚卦",
    ]


# ---------- BUG-017：养生类书籍章内 sort 连续性 ----------


WELLNESS_BOOKS = ["睡眠与精力修复课", "饮食养生课", "饮食养生课第二版"]
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SORT_RE = re.compile(r"^sort:\s*(\d+)\s*$", re.MULTILINE)
CHAPTER_RE = re.compile(r"^chapter:\s*(.+?)\s*$", re.MULTILINE)


def _parse_simple_frontmatter(content: str) -> dict[str, str | int]:
    data: dict[str, str | int] = {}
    match = FRONTMATTER_RE.match(content)
    if not match:
        return data
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.isdigit():
            value = int(value)
        data[key] = value
    return data


@pytest.mark.parametrize("book_name", WELLNESS_BOOKS)
def test_wellness_book_sort_values_are_continuous_per_chapter(book_name: str):
    """回归测试：养生类书籍每章内 sort 值为 1-based 连续序列（BUG-017）。"""
    book_dir = Path("output") / book_name
    if not book_dir.exists():
        pytest.skip(f"{book_name} 不存在")

    chapter_sorts: dict[str, list[int]] = {}
    for md_path in sorted(book_dir.rglob("*.md")):
        if md_path.name.startswith("_"):
            continue
        content = md_path.read_text(encoding="utf-8")
        fm = _parse_simple_frontmatter(content)
        chapter = fm.get("chapter")
        sort = fm.get("sort")
        if not chapter or not isinstance(sort, int):
            continue
        chapter_sorts.setdefault(str(chapter), []).append(sort)

    errors = []
    for chapter, sorts in sorted(chapter_sorts.items()):
        expected = list(range(1, len(sorts) + 1))
        if sorted(sorts) != expected:
            errors.append(
                f"{book_name}/{chapter}: sort 值 {sorted(sorts)} 期望 {expected}"
            )

    assert not errors, "\n".join(errors)
