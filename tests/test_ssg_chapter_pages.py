"""BUG-035 SSG 章节静态页测试。

夸克浏览器阅读模式不执行 JS，必须由原始 HTML 直接含正文。
本测试集验证 SSG 静态生成满足夸克阅读模式触发条件：

1. 每篇笔记都生成对应 SSG HTML
2. HTML 结构符合夸克语义识别标准：<article> + <main> + <h1> + <p>
3. SSG 模板不引用 app.js（避免 SPA 双渲染路径分叉）
4. 正文静态内联（不依赖 fetch / marked.parse）
5. SSG Markdown 渲染（Python markdown + bleach）与 SPA marked.js 渲染语义一致
6. bleach 净化生效（XSS 防护）
7. 书索引页 / 全局索引页生成
8. 幂等性
9. prev/next 导航正确
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from scripts.build_site import (
    _render_markdown_safe,
    _ssg_html_filename,
    build_site,
)

# markdown / bleach 缺失时 SSG 退化为 html.escape，相关断言会失败。
# 通过 requirements.txt 强制依赖，测试环境应已安装；缺失则跳过一致性测试。
md_lib = pytest.importorskip("markdown", reason="markdown 未安装，跳过 SSG 一致性测试")
bleach_lib = pytest.importorskip("bleach", reason="bleach 未安装，跳过 SSG 一致性测试")


SAMPLE_FRONTMATTER = """---
title: "商鞅变法"
book: "资治通鉴"
chapter: "周纪二"
event: "商鞅变法"
created_at: "2026-06-21T23:00:00+08:00"
---

# 商鞅变法

## 讲事情

商鞅入秦，徙木立信。

> 国之所以治者三：一曰法，二曰信，三曰权。

- 项一
- 项二

**强调**和*斜体*。
"""

SAMPLE_META_YAML = """title: 资治通鉴
category: 史
author: 司马光
description: 司马光主编的编年体通史
cover: 📜
sort: 1
"""


def _create_sample_output(output_dir: Path) -> None:
    note_path = output_dir / "资治通鉴" / "周纪二_商鞅变法.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(SAMPLE_FRONTMATTER, encoding="utf-8")

    meta_path = output_dir / "资治通鉴" / "_meta.yaml"
    meta_path.write_text(SAMPLE_META_YAML, encoding="utf-8")


def _build(tmp: str) -> Path:
    output_dir = Path(tmp) / "output"
    site_dir = Path(tmp) / "site"
    _create_sample_output(output_dir)
    build_site(str(output_dir), str(site_dir))
    return site_dir


# ============ 1. 生成性 ============


def test_ssg_reader_dir_created():
    """site/reader/ 目录被创建。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        assert (site_dir / "reader").is_dir()


def test_ssg_html_file_generated_for_each_note():
    """每篇笔记都有对应的 SSG HTML 文件。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        ssg_html = site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        assert ssg_html.exists(), f"SSG HTML 未生成: {ssg_html}"
        assert ssg_html.is_file()


# ============ 2. 语义结构（夸克阅读模式触发条件） ============


def test_ssg_html_has_lang_attribute():
    """<html lang="zh-CN">。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert '<html lang="zh-CN">' in html


def test_ssg_html_has_article_tag():
    """HTML 含 <article> 包裹正文（夸克硬性条件）。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert "<article" in html
        assert "</article>" in html


def test_ssg_html_has_main_tag():
    """HTML 含 <main> 包裹。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert "<main" in html
        assert "</main>" in html


def test_ssg_html_has_h1_tag():
    """HTML 含 <h1> 主标题（夸克硬性条件）。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert re.search(r"<h1[ >]", html)


def test_ssg_html_has_p_tags():
    """HTML 含 <p> 段落（夸克硬性条件）。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert "<p>" in html


# ============ 3. 不引用 app.js（避免双渲染路径分叉） ============


def test_ssg_html_does_not_reference_app_js():
    """SSG 模板不引 app.js，避免 SPA 双渲染路径分叉。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert "app.js" not in html
        assert "<script" not in html


# ============ 4. 正文静态内联 ============


def test_ssg_html_static_content_inlined():
    """正文静态内联，不依赖 fetch / marked.parse。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert "fetch(" not in html
        assert "marked.parse" not in html
        # 正文片段直接在 HTML 中（不在 <script> 里）
        assert "商鞅入秦" in html
        assert "徙木立信" in html


def test_ssg_html_has_meta_description():
    """<meta name="description"> 给搜索引擎与夸克预览。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert '<meta name="description"' in html


# ============ 5. SSG vs SPA 渲染一致性（核心） ============


def test_render_markdown_safe_matches_marked_semantics():
    """SSG 渲染（Python markdown + bleach）与 SPA 渲染（marked.js）语义一致。

    marked.js 默认 GFM，支持标题/段落/引用/列表/强调/链接。
    Python markdown 'extra' extension 等价支持这些核心语法。
    两者输出的 HTML 结构相同：标题→<h*>、段落→<p>、引用→<blockquote>、
    列表→<ul><li>、强调→<strong>/<em>。

    若该测试失败，说明 SSG 与 SPA 渲染分叉，需统一扩展配置。
    """
    md_text = """# 标题

段落一。

> 引用

- 列表项一
- 列表项二

**强调**和*斜体*。
"""
    html = _render_markdown_safe(md_text)
    # 标题
    assert re.search(r"<h1[^>]*>标题</h1>", html), html
    # 段落
    assert "<p>段落一。</p>" in html
    # 引用
    assert "<blockquote>" in html
    assert "<p>引用</p>" in html
    # 列表
    assert "<ul>" in html
    assert "<li>列表项一</li>" in html
    assert "<li>列表项二</li>" in html
    # 强调
    assert "<strong>强调</strong>" in html
    assert "<em>斜体</em>" in html


# ============ 6. bleach 净化（XSS 防护） ============


def test_bleach_strips_script_tags():
    """bleach 净化剥离 <script> 与 javascript: 协议。"""
    malicious_md = """正常段落。

<script>alert('xss')</script>

<a href="javascript:alert(1)">恶意链接</a>
"""
    html = _render_markdown_safe(malicious_md)
    assert "<script" not in html
    assert "</script>" not in html
    assert "javascript:" not in html


def test_bleach_preserves_safe_links():
    """bleach 保留安全的 https 链接。"""
    md = "[官网](https://example.com)"
    html = _render_markdown_safe(md)
    assert 'href="https://example.com"' in html


# ============ 7. 索引页 ============


def test_book_index_html_generated():
    """每本书目录索引页 site/reader/{book}/index.html 生成。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        book_index = site_dir / "reader" / "资治通鉴" / "index.html"
        assert book_index.exists()
        html = book_index.read_text(encoding="utf-8")
        assert "<article" in html
        assert "资治通鉴" in html
        # 索引页应包含章节链接
        assert "周纪二_商鞅变法.html" in html


def test_global_index_html_generated():
    """全章节总索引页 site/reader/index.html 生成。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        global_index = site_dir / "reader" / "index.html"
        assert global_index.exists()
        html = global_index.read_text(encoding="utf-8")
        assert "<article" in html
        assert "资治通鉴" in html
        assert "全章节索引" in html


# ============ 8. 幂等性 ============


def test_build_ssg_idempotent():
    """连续构建两次，SSG HTML 内容一致。"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        build_site(str(output_dir), str(site_dir))
        html1 = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")

        build_site(str(output_dir), str(site_dir))
        html2 = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")

        assert html1 == html2


# ============ 9. 辅助函数 ============


def test_ssg_html_filename():
    """_ssg_html_filename 生成 {chapter}_{event}.html。"""
    note = {"chapter": "周纪二", "event": "商鞅变法"}
    assert _ssg_html_filename(note) == "周纪二_商鞅变法.html"


def test_ssg_html_filename_no_event():
    """event 为空时退化为 {chapter}.html。"""
    note = {"chapter": "学而", "event": ""}
    assert _ssg_html_filename(note) == "学而.html"


# ============ 10. prev/next 导航 ============


def test_ssg_html_prev_next_navigation():
    """多章节时 SSG HTML 含 prev/next 导航。"""
    extra_md = """---
title: "纸上谈兵"
book: "资治通鉴"
chapter: "周纪二"
event: "纸上谈兵"
created_at: "2026-06-22T00:00:00+08:00"
---

# 纸上谈兵

赵括纸上谈兵，长平败北。
"""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "output"
        site_dir = Path(tmp) / "site"
        _create_sample_output(output_dir)
        # 同章节下新增第二篇事件
        (output_dir / "资治通鉴" / "周纪二_纸上谈兵.md").write_text(
            extra_md, encoding="utf-8"
        )
        build_site(str(output_dir), str(site_dir))

        # 第二篇应有 prev 链接回第一篇
        html2 = (
            site_dir / "reader" / "资治通鉴" / "周纪二_纸上谈兵.html"
        ).read_text(encoding="utf-8")
        assert 'rel="prev"' in html2
        assert "周纪二_商鞅变法.html" in html2

        # 第一篇应有 next 链接到第二篇
        html1 = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert 'rel="next"' in html1
        assert "周纪二_纸上谈兵.html" in html1


def test_ssg_html_first_chapter_no_prev():
    """首篇笔记的 prev 显示「已是第一章」且无 href。"""
    with tempfile.TemporaryDirectory() as tmp:
        site_dir = _build(tmp)
        html = (
            site_dir / "reader" / "资治通鉴" / "周纪二_商鞅变法.html"
        ).read_text(encoding="utf-8")
        assert "已是第一章" in html
