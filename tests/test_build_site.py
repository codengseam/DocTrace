"""构建脚本 build_site.py 的单元测试。

使用 pytest 函数式风格，借助 tempfile 隔离每个用例的文件系统。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.build_site import build_site


SAMPLE_FRONTMATTER = """---
title: "商鞅变法"
book: "资治通鉴"
chapter: "周纪二"
event: "商鞅变法"
created_at: "2026-06-21T23:00:00+08:00"
source_agents:
  - historian
  - biographer
---

## 讲事情

商鞅入秦，徙木立信。
"""

SAMPLE_META_YAML = """title: 资治通鉴
category: 史
author: 司马光
description: 司马光主编的编年体通史
cover: 📜
sort: 1
"""


def _create_sample_output(output_dir: Path) -> None:
    """在 output_dir 下创建样例笔记及元数据。"""
    note_path = output_dir / "资治通鉴" / "周纪二_商鞅变法.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(SAMPLE_FRONTMATTER, encoding="utf-8")

    meta_path = output_dir / "资治通鉴" / "_meta.yaml"
    meta_path.write_text(SAMPLE_META_YAML, encoding="utf-8")


def test_build_site_creates_site_directory():
    """构建后 site/ 目录存在。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        result = build_site(str(output_dir), str(site_dir))
        assert result.exists()
        assert result.is_dir()


def test_build_site_creates_nojekyll():
    """site/ 根目录生成 .nojekyll，使 GitHub Pages 跳过 Jekyll 构建。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        nojekyll_path = site_dir / ".nojekyll"
        assert nojekyll_path.exists()
        assert nojekyll_path.is_file()
        assert nojekyll_path.read_text(encoding="utf-8") == ""


def test_build_site_generates_index_json():
    """site/data/index.json 存在且可解析。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        index_path = site_dir / "data" / "index.json"
        assert index_path.exists()
        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "version" in data
        assert "generated_at" in data
        assert "stats" in data
        assert "tree" in data
        assert "notes" in data


def test_index_json_tree_structure():
    """tree 结构正确（book→chapter→event）。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        tree = data["tree"]
        assert len(tree) == 1

        book_node = tree[0]
        assert book_node["title"] == "资治通鉴"
        assert book_node["type"] == "book"
        assert len(book_node["children"]) == 1

        chapter_node = book_node["children"][0]
        assert chapter_node["title"] == "周纪二"
        assert chapter_node["type"] == "chapter"
        assert len(chapter_node["children"]) == 1

        event_node = chapter_node["children"][0]
        assert event_node["title"] == "商鞅变法"
        assert event_node["type"] == "event"
        assert event_node["path"] == "资治通鉴/周纪二_商鞅变法.md"


def test_index_json_notes_content():
    """notes 字典含正确字段。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        notes = data["notes"]
        assert "资治通鉴/周纪二_商鞅变法.md" in notes

        note = notes["资治通鉴/周纪二_商鞅变法.md"]
        assert note["path"] == "资治通鉴/周纪二_商鞅变法.md"
        assert note["book"] == "资治通鉴"
        assert note["chapter"] == "周纪二"
        assert note["event"] == "商鞅变法"
        assert note["title"] == "商鞅变法"
        assert note["created_at"] == "2026-06-21T23:00:00+08:00"
        assert note["source_agents"] == ["historian", "biographer"]
        assert "## 讲事情" in note["content"]
        assert "商鞅入秦" in note["content"]


def test_build_site_copies_notes():
    """site/notes/ 下有 Markdown 文件副本。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        note_copy = site_dir / "notes" / "资治通鉴" / "周纪二_商鞅变法.md"
        assert note_copy.exists()
        text = note_copy.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert "## 讲事情" in text
        assert "商鞅入秦" in text


def test_build_site_empty_output():
    """output/ 为空时不报错，tree 为空列表。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        # output 目录不存在
        build_site(str(output_dir), str(site_dir))
        index_path = site_dir / "data" / "index.json"
        assert index_path.exists()
        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert data["tree"] == []
        assert data["notes"] == {}
        assert data["stats"]["books"] == 0
        assert data["stats"]["notes"] == 0


def test_build_site_idempotent():
    """连续构建两次结果一致。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)

        build_site(str(output_dir), str(site_dir))
        data1 = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )

        build_site(str(output_dir), str(site_dir))
        data2 = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )

        # generated_at 可能因时间不同而变化，但 tree/notes/stats 应一致
        assert data1["tree"] == data2["tree"]
        assert data1["notes"] == data2["notes"]
        assert data1["stats"] == data2["stats"]


def test_index_json_chinese_not_escaped():
    """JSON 文件中中文不被 \\u 转义。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        raw = (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        assert "资治通鉴" in raw
        assert "周纪二" in raw
        assert "商鞅变法" in raw
        assert "\\u" not in raw


def test_build_site_cli():
    """CLI 调用 python scripts/build_site.py --output ... --site ... 返回 0。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/build_site.py",
                "--output",
                str(output_dir),
                "--site",
                str(site_dir),
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert (site_dir / "data" / "index.json").exists()
        assert (
            site_dir / "notes" / "资治通鉴" / "周纪二_商鞅变法.md"
        ).exists()


def test_index_json_books_structure():
    """books 数组存在、长度正确、字段正确。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        books = data["books"]
        assert isinstance(books, list)
        assert len(books) == 1

        book = books[0]
        assert book["id"] == "资治通鉴"
        assert book["title"] == "资治通鉴"
        assert book["category"] == "史"
        assert book["author"] == "司马光"
        assert book["cover"] == "📜"
        assert book["sort"] == 1
        assert book["chapter_count"] == 1
        assert book["note_count"] == 1


def test_index_json_books_tree_per_book():
    """某本书的 tree 只含本书章节，不含其他书。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        # 额外创建第二本书（无 _meta.yaml）
        note2 = output_dir / "论语" / "学而_学而时习之.md"
        note2.parent.mkdir(parents=True, exist_ok=True)
        note2.write_text(
            """---
title: "学而时习之"
book: "论语"
chapter: "学而"
event: "学而时习之"
---

## 讲事情

学而时习之，不亦说乎。
""",
            encoding="utf-8",
        )
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        books = data["books"]
        assert len(books) == 2

        zz_book = next(b for b in books if b["id"] == "资治通鉴")
        assert len(zz_book["tree"]) == 1
        assert zz_book["tree"][0]["title"] == "周纪二"
        # 资治通鉴的 tree 不应包含论语的章节
        for ch in zz_book["tree"]:
            assert ch["title"] != "学而"

        ly_book = next(b for b in books if b["id"] == "论语")
        assert len(ly_book["tree"]) == 1
        assert ly_book["tree"][0]["title"] == "学而"


def test_index_json_categories():
    """categories 列表存在且包含 '史'。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        categories = data["categories"]
        assert isinstance(categories, list)
        assert "史" in categories


def test_index_json_backward_compat():
    """顶层 tree 和 notes 仍存在且结构不变。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        # 顶层 tree 仍存在
        assert "tree" in data
        tree = data["tree"]
        assert len(tree) == 1
        assert tree[0]["title"] == "资治通鉴"
        assert tree[0]["type"] == "book"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["title"] == "周纪二"

        # notes 仍存在
        assert "notes" in data
        notes = data["notes"]
        assert "资治通鉴/周纪二_商鞅变法.md" in notes


def test_book_meta_defaults():
    """无 _meta.yaml 时，category 为 '未分类'、cover 为 '📖'。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        # 创建一本没有 _meta.yaml 的书
        note_path = output_dir / "无名书" / "第一章_某事件.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            """---
title: "某事件"
book: "无名书"
chapter: "第一章"
event: "某事件"
---

## 讲事情

某事件内容。
""",
            encoding="utf-8",
        )
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        books = data["books"]
        assert len(books) == 1
        book = books[0]
        assert book["category"] == "未分类"
        assert book["cover"] == "📖"
        assert book["title"] == "无名书"
        assert book["sort"] == 99
        assert book["author"] == ""
        assert book["description"] == ""


def test_stats_includes_categories():
    """stats.categories 为 int。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        assert "categories" in data["stats"]
        assert isinstance(data["stats"]["categories"], int)
        assert data["stats"]["categories"] == 1


# ---------- sort 字段注入（问题一） ----------


def test_event_node_includes_sort_field():
    """event 节点注入 frontmatter 的 sort 字段。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        note_path = output_dir / "资治通鉴" / "周纪四_胡服骑射.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            """---
title: "胡服骑射"
book: "资治通鉴"
chapter: "周纪四"
event: "胡服骑射"
sort: 1
created_at: "2026-06-21T23:00:00+08:00"
---

## 讲事情

赵武灵王胡服骑射。
""",
            encoding="utf-8",
        )
        meta_path = output_dir / "资治通鉴" / "_meta.yaml"
        meta_path.write_text(SAMPLE_META_YAML, encoding="utf-8")

        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        event_node = data["tree"][0]["children"][0]["children"][0]
        assert event_node["sort"] == 1


def test_event_node_sort_none_when_absent():
    """frontmatter 无 sort 字段时，event 节点 sort 为 None。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        event_node = data["tree"][0]["children"][0]["children"][0]
        assert event_node["sort"] is None


def test_event_sort_orders_by_sort_field():
    """章内多个 event 按 sort 字段排序（而非 path）。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        book_dir = output_dir / "资治通鉴"
        book_dir.mkdir(parents=True, exist_ok=True)
        (book_dir / "_meta.yaml").write_text(SAMPLE_META_YAML, encoding="utf-8")

        # 故意让 path 顺序与 sort 顺序相反
        notes = [
            ("周纪四_完璧归赵.md", "完璧归赵", 2),
            ("周纪四_胡服骑射.md", "胡服骑射", 1),
            ("周纪四_负荆请罪.md", "负荆请罪", 4),
            ("周纪四_渑池之会.md", "渑池之会", 3),
        ]
        for filename, event, sort in notes:
            (book_dir / filename).write_text(
                f"""---
title: "{event}"
book: "资治通鉴"
chapter: "周纪四"
event: "{event}"
sort: {sort}
created_at: "2026-06-21T23:00:00+08:00"
---

## 讲事情

{event}内容。
""",
                encoding="utf-8",
            )

        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        events = data["tree"][0]["children"][0]["children"]
        titles = [e["title"] for e in events]
        assert titles == ["胡服骑射", "完璧归赵", "渑池之会", "负荆请罪"]


# ---------- flat 标记（问题三） ----------


def test_book_node_flat_flag_true_for_all_numeric_chapters():
    """所有 chapter 标题都是纯数字时，book 节点 flat=True。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        book_dir = output_dir / "论语"
        book_dir.mkdir(parents=True, exist_ok=True)
        for idx, name in [(1, "孔子的一生"), (2, "孔子的性格")]:
            (book_dir / f"0{idx}_{name}.md").write_text(
                f"""---
title: "{name}"
book: "论语"
chapter: "0{idx}"
event: "{name}"
---

## 讲事情

内容。
""",
                encoding="utf-8",
            )

        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        book_node = data["tree"][0]
        assert book_node["flat"] is True


def test_book_node_flat_flag_false_for_named_chapters():
    """chapter 标题非纯数字时（如周纪四），book 节点 flat=False。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        book_node = data["tree"][0]
        assert book_node["flat"] is False


def test_book_node_flat_flag_false_for_mixed_chapters():
    """混合 chapter（数字 + 非数字）时 flat=False（如史记既有秦纪又有01）。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        book_dir = output_dir / "史记"
        book_dir.mkdir(parents=True, exist_ok=True)
        (book_dir / "秦纪一_某事.md").write_text(
            """---
title: "某事"
book: "史记"
chapter: "秦纪一"
event: "某事"
---

## 讲事情

内容。
""",
            encoding="utf-8",
        )
        (book_dir / "01_另一事.md").write_text(
            """---
title: "另一事"
book: "史记"
chapter: "01"
event: "另一事"
---

## 讲事情

内容。
""",
            encoding="utf-8",
        )

        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        book_node = data["tree"][0]
        assert book_node["flat"] is False


def test_books_array_includes_flat_flag():
    """books 数组中每个 book 也带 flat 标记。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        data = json.loads(
            (site_dir / "data" / "index.json").read_text(encoding="utf-8")
        )
        book = data["books"][0]
        assert "flat" in book
        assert book["flat"] is False
