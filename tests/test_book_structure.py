"""书籍结构校验脚本测试。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.check_book_structure import (
    check_book_structure,
    _check_chapter_sorts,
    _check_file,
    _parse_frontmatter,
    _parse_note_path,
    _to_int,
)


def test_parse_frontmatter_with_yaml():
    content = "---\ntitle: 测试\nsort: 1\n---\n正文"
    meta, body = _parse_frontmatter(content)
    assert meta["title"] == "测试"
    assert meta["sort"] == 1
    assert body == "正文"


def test_parse_frontmatter_without_yaml():
    content = '---\ntitle: "测试"\nsort: "2"\n---\n正文'
    meta, body = _parse_frontmatter(content)
    assert meta["title"] == "测试"
    assert meta["sort"] == "2"


def test_to_int():
    assert _to_int(1) == 1
    assert _to_int("3") == 3
    assert _to_int("abc") is None
    assert _to_int(None) is None


def test_parse_note_path():
    assert _parse_note_path("史记/秦纪一_三家分晋.md") == ("史记", "秦纪一", "三家分晋")
    assert _parse_note_path("史记/秦纪.md") is None
    assert _parse_note_path("a/b/c.md") is None


def test_check_file_missing_required_fields(tmp_path: Path):
    output = tmp_path / "output"
    book_dir = output / "测试书"
    book_dir.mkdir(parents=True)
    f = book_dir / "第一章_事件.md"
    f.write_text("---\n---\n正文", encoding="utf-8")

    issues, meta = _check_file(f, output)
    assert any(i.message.startswith("frontmatter 缺少必填字段") for i in issues)


def test_check_file_consistent_frontmatter(tmp_path: Path):
    output = tmp_path / "output"
    book_dir = output / "测试书"
    book_dir.mkdir(parents=True)
    f = book_dir / "第一章_事件.md"
    f.write_text(
        "---\ntitle: 标题\nbook: 测试书\nchapter: 第一章\nevent: 事件\nsort: 1\nchapter_sort: 1\n---\n正文",
        encoding="utf-8",
    )

    issues, meta = _check_file(f, output)
    assert not issues


def test_check_chapter_sorts_duplicate_and_non_continuous():
    chapters = {
        ("书", "第一章"): [
            {"rel": "书/第一章_a.md", "sort": 1, "chapter_sort": 1},
            {"rel": "书/第一章_b.md", "sort": 1, "chapter_sort": 1},
            {"rel": "书/第一章_c.md", "sort": 3, "chapter_sort": 1},
        ]
    }
    issues = _check_chapter_sorts(chapters)
    messages = [i.message for i in issues]
    assert any("sort 值重复" in m for m in messages)
    assert any("sort 非递增" in m for m in messages)
    assert any("sort 值不连续" in m for m in messages)


def test_check_chapter_sorts_flexible_module():
    """细粒度单元模式：同一 chapter_sort 下多个单事件 chapter，sort 可不为 1。"""
    chapters = {
        ("易经课", "乾卦"): [
            {"rel": "易经课/乾卦_健行不息.md", "sort": 1, "chapter_sort": 3},
        ],
        ("易经课", "坤卦"): [
            {"rel": "易经课/坤卦_厚德载物.md", "sort": 2, "chapter_sort": 3},
        ],
    }
    issues = _check_chapter_sorts(chapters)
    assert not issues


def test_check_book_structure_end_to_end(tmp_path: Path):
    output = tmp_path / "output"
    book_dir = output / "测试书"
    book_dir.mkdir(parents=True)

    (book_dir / "第一章_事件一.md").write_text(
        "---\ntitle: 事件一\nbook: 测试书\nchapter: 第一章\nevent: 事件一\nsort: 1\nchapter_sort: 1\n---\n正文",
        encoding="utf-8",
    )
    (book_dir / "第一章_事件二.md").write_text(
        "---\ntitle: 事件二\nbook: 测试书\nchapter: 第一章\nevent: 事件二\nsort: 2\nchapter_sort: 1\n---\n正文",
        encoding="utf-8",
    )
    (book_dir / "第二章_事件一.md").write_text(
        "---\ntitle: 事件一\nbook: 测试书\nchapter: 第二章\nevent: 事件一\nsort: 1\nchapter_sort: 2\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = check_book_structure(str(output))
    assert not issues


def test_check_book_structure_missing_sort(tmp_path: Path):
    output = tmp_path / "output"
    book_dir = output / "测试书"
    book_dir.mkdir(parents=True)
    (book_dir / "第一章_事件.md").write_text(
        "---\ntitle: 事件\nbook: 测试书\nchapter: 第一章\nevent: 事件\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = check_book_structure(str(output))
    assert any("缺少必填字段: sort" in i.message for i in issues)
    assert any("缺少必填字段: chapter_sort" in i.message for i in issues)


def test_check_book_structure_accepts_zizhi_consistent_stage_sort(tmp_path: Path):
    """阶段模式：同一朝代/纪的 chapter_sort 一致，校验通过。"""
    output = tmp_path / "output"
    book_dir = output / "资治通鉴"
    book_dir.mkdir(parents=True)
    (book_dir / "汉纪一_鸿门宴.md").write_text(
        "---\ntitle: 鸿门宴\nbook: 资治通鉴\nchapter: 汉纪一\nevent: 鸿门宴\nsort: 1\nchapter_sort: 3\n---\n正文",
        encoding="utf-8",
    )
    (book_dir / "汉纪二_垓下之围.md").write_text(
        "---\ntitle: 垓下之围\nbook: 资治通鉴\nchapter: 汉纪二\nevent: 垓下之围\nsort: 1\nchapter_sort: 3\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = check_book_structure(str(output))
    assert not issues


def test_check_book_structure_detects_zizhi_inconsistent_chapter_sort(tmp_path: Path):
    """阶段模式：同一朝代/纪的 chapter_sort 不一致，报 P1。"""
    output = tmp_path / "output"
    book_dir = output / "资治通鉴"
    book_dir.mkdir(parents=True)
    (book_dir / "汉纪一_鸿门宴.md").write_text(
        "---\ntitle: 鸿门宴\nbook: 资治通鉴\nchapter: 汉纪一\nevent: 鸿门宴\nsort: 1\nchapter_sort: 3\n---\n正文",
        encoding="utf-8",
    )
    (book_dir / "汉纪二_垓下之围.md").write_text(
        "---\ntitle: 垓下之围\nbook: 资治通鉴\nchapter: 汉纪二\nevent: 垓下之围\nsort: 1\nchapter_sort: 4\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = check_book_structure(str(output))
    assert any("汉纪 的 chapter_sort 与阶段序号 3 不符" in i.message for i in issues)
    assert any(i.severity == "P1" for i in issues)


def test_check_book_structure_accepts_mingji_module_name_stage_sort(tmp_path: Path):
    """明纪阶段模式：模块名作为 chapter，chapter_sort 等于 BOOK_CATEGORY_ORDER 阶段序号，校验通过。"""
    output = tmp_path / "output"
    book_dir = output / "明纪"
    book_dir.mkdir(parents=True)
    (book_dir / "洪武之治与集权_废相集权.md").write_text(
        "---\ntitle: 废相集权\nbook: 明纪\nchapter: 洪武之治与集权\nevent: 废相集权\nsort: 2\nchapter_sort: 2\n---\n正文",
        encoding="utf-8",
    )
    (book_dir / "洪武之治与集权_胡蓝之狱.md").write_text(
        "---\ntitle: 胡蓝之狱\nbook: 明纪\nchapter: 洪武之治与集权\nevent: 胡蓝之狱\nsort: 1\nchapter_sort: 2\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = check_book_structure(str(output))
    assert not issues


def test_check_book_structure_detects_mingji_inconsistent_chapter_sort(tmp_path: Path):
    """明纪阶段模式：chapter_sort 与 BOOK_CATEGORY_ORDER 阶段序号不符，报 P1。"""
    output = tmp_path / "output"
    book_dir = output / "明纪"
    book_dir.mkdir(parents=True)
    # 洪武之治与集权 应为 chapter_sort=2，故意写成 5 触发告警
    (book_dir / "洪武之治与集权_废相集权.md").write_text(
        "---\ntitle: 废相集权\nbook: 明纪\nchapter: 洪武之治与集权\nevent: 废相集权\nsort: 2\nchapter_sort: 5\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = check_book_structure(str(output))
    assert any("洪武之治与集权 的 chapter_sort 与阶段序号 2 不符" in i.message for i in issues)
    assert any(i.severity == "P1" for i in issues)


def test_output_has_no_structure_issues():
    """回归测试：真实 output/ 目录必须零问题（BUG-017 等历史问题不复发）。"""
    issues, _ = check_book_structure("output")
    assert not issues, "\n".join(
        f"{issue.book}/{issue.file}: [{issue.severity}] {issue.message}"
        for issue in issues
    )


def test_check_file_rejects_module_prefix_in_chapter(tmp_path: Path):
    """回归测试：frontmatter.chapter 和文件名章节部分禁止「模块N」前缀（BUG-019）。"""
    output = tmp_path / "output"
    book_dir = output / "测试书"
    book_dir.mkdir(parents=True)
    f = book_dir / "模块0第一章_事件.md"
    f.write_text(
        "---\ntitle: 标题\nbook: 测试书\nchapter: 模块0第一章\nevent: 事件\nsort: 1\nchapter_sort: 1\n---\n正文",
        encoding="utf-8",
    )

    issues, _ = _check_file(f, output)
    messages = [i.message for i in issues]
    assert any("frontmatter.chapter 含「模块N」前缀" in m for m in messages)
    assert any("文件名章节部分含「模块N」前缀" in m for m in messages)
