"""scripts/migrate_wellness_books.py 的单元测试。

覆盖纯函数：
- _build_lookup：模块/章节顺序映射正确
- _sanitize_filename：特殊字符与空白处理
"""

from __future__ import annotations

from scripts.migrate_wellness_books import (
    DIET_MODULES,
    DIET_V2_MODULES,
    SLEEP_MODULES,
    _build_lookup,
    _sanitize_filename,
)


def test_build_lookup_diet_modules():
    """饮食养生课 lookup 包含所有章节，sort 从 1 开始递增。"""
    lookup = _build_lookup(DIET_MODULES)
    total_events = sum(len(events) for _, events in DIET_MODULES)
    assert len(lookup) == total_events
    assert lookup["你为什么不会吃"] == ("开篇", 1, 0)
    assert lookup["饮食与运动睡眠配合"] == (
        "长期饮食体系",
        total_events,
        len(DIET_MODULES) - 1,
    )


def test_build_lookup_v2_modules():
    """第二版 lookup 覆盖新增模块。"""
    lookup = _build_lookup(DIET_V2_MODULES)
    assert "食养根本" in {module for module, _ in DIET_V2_MODULES}
    assert lookup["一口饭的体内旅程"] == ("食养根本", 1, 0)
    assert lookup["细嚼慢咽的力量"] == ("吃法决定命运", 17, 3)


def test_build_lookup_sleep_modules():
    """睡眠课 lookup 覆盖开篇到长期体系。"""
    lookup = _build_lookup(SLEEP_MODULES)
    assert lookup["你不是缺觉是不会休息"] == ("开篇", 1, 0)
    assert lookup["长期精力管理体系"] == (
        "误区避坑与长期体系",
        sum(len(events) for _, events in SLEEP_MODULES),
        len(SLEEP_MODULES) - 1,
    )


def test_sanitize_filename_basic():
    """普通中文章节名保持不变。"""
    assert _sanitize_filename("细嚼慢咽的力量") == "细嚼慢咽的力量"


def test_sanitize_filename_special_chars():
    """特殊字符替换为下划线并去重。"""
    assert _sanitize_filename("4-7-8 入睡呼吸法") == "4-7-8_入睡呼吸法"
