#!/usr/bin/env python3
"""静态站点构建脚本。

扫描 output/ 目录下的 Markdown 笔记，生成静态站点到 site/ 目录，
用于部署到 GitHub Pages。

用法：
    python scripts/build_site.py [--output output] [--site site]
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

# 把项目根加入 sys.path，使 scripts/ 独立运行时也能 import src.utils.sorting
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.sorting import sort_notes_tree  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

# BUG-035：SSG 章节静态页依赖（构建期把 Markdown 渲染为 HTML 并净化）
# 与 yaml 同样的 try-except 容错，缺失时打印告警并跳过 SSG 步骤
try:
    import markdown as md_lib  # type: ignore
except ImportError:
    md_lib = None  # type: ignore

try:
    import bleach  # type: ignore
except ImportError:
    bleach = None  # type: ignore

VERSION = "1.1.0"
FRONTMATTER_PATTERN = r"^---\s*\n(.*?)\n---\s*\n?"


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """解析 Markdown frontmatter，返回 (metadata, body)。

    优先使用 PyYAML；不可用时 fallback 到简单 key:value 解析。
    """
    match = re.match(FRONTMATTER_PATTERN, content, re.DOTALL)
    if not match:
        return {}, content

    raw = match.group(1)
    body = content[match.end():]

    if yaml is not None:
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                return data, body
        except Exception:
            pass

    return _parse_simple_frontmatter(raw), body


def _parse_simple_frontmatter(raw: str) -> dict[str, Any]:
    """无 PyYAML 时解析简单 frontmatter（顶层标量/列表）。"""
    result: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_key is not None:
                item = stripped[2:].strip().strip('"').strip("'")
                if not isinstance(result.get(current_key), list):
                    result[current_key] = []
                result[current_key].append(item)
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            result[current_key] = value.strip().strip('"').strip("'")
    return result


def _parse_note_path(rel_path: str) -> tuple[str, str, str] | None:
    """解析相对路径为 (book, chapter, event)。

    路径格式：book/chapter_event.md
    """
    parts = rel_path.split("/")
    if len(parts) < 2:
        return None
    book = parts[0]
    stem = parts[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    if "_" in stem:
        chapter, event = stem.split("_", 1)
    else:
        chapter = stem
        event = ""
    return book, chapter, event


def _normalize_source_agents(value: Any) -> list[str]:
    """将 source_agents 规范化为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_created_at(value: Any) -> str:
    """将 created_at 规范化为字符串。"""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _to_int(value: Any) -> int | None:
    """将 frontmatter 中的排序值转为整数；失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_book_meta(book_dir: Path, book_name: str) -> dict[str, Any]:
    """读取 book_dir/_meta.yaml，返回规范化后的元数据字典。

    无文件或解析失败时返回默认值：
    title=book_name, category="未分类", description="", author="",
    cover="📖", sort=99。
    """
    defaults: dict[str, Any] = {
        "title": book_name,
        "category": "未分类",
        "description": "",
        "author": "",
        "cover": "📖",
        "sort": 99,
    }
    meta_path = book_dir / "_meta.yaml"
    if not meta_path.exists():
        return defaults
    try:
        raw = meta_path.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(raw)
        else:
            data = _parse_simple_frontmatter(raw)
    except Exception:
        return defaults
    if not isinstance(data, dict):
        return defaults

    result = dict(defaults)
    for key in ("title", "category", "description", "author", "cover"):
        value = data.get(key)
        if value is not None:
            result[key] = str(value)
    sort_value = data.get("sort")
    if sort_value is not None:
        try:
            result["sort"] = int(sort_value)
        except (TypeError, ValueError):
            pass
    return result


def _category_sort_key(category: str) -> tuple[int, str]:
    """返回 (priority, category) 用于排序。

    优先级：经(1) < 史(2) < 子(3) < 集(4) < 其他(50) < 未分类(99)。
    其他分类按字符串序（近似拼音序）排列。
    """
    priority_map = {
        "经": 1,
        "史": 2,
        "子": 3,
        "集": 4,
        "未分类": 99,
    }
    if category in priority_map:
        return (priority_map[category], category)
    return (50, category)


def _ensure_sage_portrait_thumbnails(images_dir: Path, max_width: int = 400) -> None:
    """为圣贤堂头像生成缩略图，减少首屏图片体积。

    卡片最大显示宽度约 360px，缩略图取 400px 可覆盖 1x/2x 屏；
    原图保留在 images/，缩略图写入 images/thumbs/。
    """
    try:
        from PIL import Image
    except ImportError:
        print("[build_site] Pillow 未安装，跳过头像缩略图生成", file=sys.stderr)
        return

    thumbs_dir = images_dir / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    for img_path in sorted(images_dir.glob("*.jpg")):
        thumb_path = thumbs_dir / img_path.name
        if thumb_path.exists() and thumb_path.stat().st_mtime >= img_path.stat().st_mtime:
            continue
        try:
            with Image.open(img_path) as im:
                if im.width > max_width:
                    ratio = max_width / im.width
                    im = im.resize((max_width, int(im.height * ratio)), Image.LANCZOS)
                im.save(thumb_path, "JPEG", quality=85, optimize=True)
        except Exception as exc:
            print(f"[build_site] 生成缩略图失败 {img_path.name}: {exc}", file=sys.stderr)


def _copy_static_assets(site_path: Path) -> None:
    """将 src/web/static-site/ 下的前端产物复制到 site/。

    避免 site/ 下的 html/css/js 靠手动维护而与源文件不同步，
    导致 GitHub Pages 部署后出现功能缺失。
    """
    root = Path(__file__).resolve().parent.parent
    source_dir = root / "src" / "web" / "static-site"
    if not source_dir.exists():
        return

    assets = [
        ("index.html", site_path / "index.html"),
        ("gaokao.html", site_path / "gaokao.html"),
        ("css/style.css", site_path / "css" / "style.css"),
        ("js/app.js", site_path / "js" / "app.js"),
        ("sw.js", site_path / "sw.js"),
    ]

    # 复制圣贤堂展厅页到 site/demos/（独立演示页，不依赖主站 SPA）
    demos_dir = root / "demos"
    if demos_dir.exists():
        saints_src = demos_dir / "saints_hall.html"
        if saints_src.exists():
            saints_dest = site_path / "demos" / "saints_hall.html"
            saints_dest.parent.mkdir(parents=True, exist_ok=True)
            # 源文件在 demos/，使用 ../site/index.html 可在本地直接打开；
            # 复制到 site/demos/ 后需回退到 site 根目录，故重写为 ../index.html。
            html = saints_src.read_text(encoding="utf-8")
            html = html.replace("../site/index.html?", "../index.html?")
            saints_dest.write_text(html, encoding="utf-8")
        # 复制本地缓存的头像图片到 site/demos/images/
        images_src = demos_dir / "images"
        if images_src.exists():
            images_dest = site_path / "demos" / "images"
            images_dest.mkdir(parents=True, exist_ok=True)
            _ensure_sage_portrait_thumbnails(images_src)
            for img in images_src.glob("*.jpg"):
                shutil.copy2(img, images_dest / img.name)
            thumbs_src = images_src / "thumbs"
            if thumbs_src.exists():
                thumbs_dest = images_dest / "thumbs"
                thumbs_dest.mkdir(parents=True, exist_ok=True)
                for thumb in thumbs_src.glob("*.jpg"):
                    shutil.copy2(thumb, thumbs_dest / thumb.name)
    for src_rel, dest in assets:
        src = source_dir / Path(src_rel)
        if not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


# ============ BUG-035: SSG 章节静态页 ============
# 夸克浏览器阅读模式不执行 JS，无法看到 SPA 通过 fetch + marked.parse 动态渲染的正文。
# 必须在构建期把每篇笔记渲染为独立静态 HTML，原始 HTML 直接含 <article> + 正文。
# SSG 模板不引 app.js，避免双渲染路径分叉；bleach 净化避免 XSS。

_SSG_ALLOWED_TAGS = [
    "article", "section", "header", "nav", "main", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "em", "strong", "del", "sup", "sub",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
]

_SSG_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "pre": ["class"],
    "div": ["class"],
    "span": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}

_SSG_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_SSG_CHAPTER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}} - {{BOOK_TITLE}} | 豪书斋</title>
    <meta name="description" content="{{DESCRIPTION}}">
    <link rel="stylesheet" href="{{CSS_PATH}}">
</head>
<body class="ssg-reader" data-theme="day" data-font="serif">
    <header class="ssg-topbar">
        <a class="ssg-back" href="{{HOME_PATH}}">← 返回书架</a>
        <a class="ssg-toc" href="{{BOOK_INDEX_PATH}}">{{BOOK_TITLE}} · 目录</a>
    </header>
    <main class="page-main">
        <article class="markdown-body reader-content">
            <h1 class="ssg-chapter-title">{{TITLE}}</h1>
            <p class="ssg-meta">出处：{{BOOK_TITLE}} / {{CHAPTER}}{{EVENT_SEP}}{{EVENT}}</p>
            {{CONTENT_HTML}}
        </article>
    </main>
    <nav class="chapter-nav">
        <a class="chapter-btn prev" href="{{PREV_HREF}}" rel="prev">{{PREV_LABEL}}</a>
        <a class="chapter-btn next" href="{{NEXT_HREF}}" rel="next">{{NEXT_LABEL}}</a>
    </nav>
</body>
</html>"""

_SSG_BOOK_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{BOOK_TITLE}} · 目录 | 豪书斋</title>
    <link rel="stylesheet" href="{{CSS_PATH}}">
</head>
<body class="ssg-index">
    <header class="ssg-topbar">
        <a class="ssg-back" href="{{HOME_PATH}}">← 返回书架</a>
        <a class="ssg-toc" href="{{GLOBAL_INDEX_PATH}}">全部书目</a>
    </header>
    <main class="page-main">
        <article class="ssg-book-index">
            <h1>{{BOOK_TITLE}}</h1>
            {{DESCRIPTION_HTML}}
            <ul class="ssg-chapter-list">
                {{CHAPTER_LIST_HTML}}
            </ul>
        </article>
    </main>
</body>
</html>"""

_SSG_GLOBAL_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>豪书斋 · 全章节索引</title>
    <link rel="stylesheet" href="{{CSS_PATH}}">
</head>
<body class="ssg-index">
    <header class="ssg-topbar">
        <a class="ssg-back" href="{{HOME_PATH}}">← 返回书架</a>
    </header>
    <main class="page-main">
        <article class="ssg-global-index">
            <h1>豪书斋 · 全章节索引</h1>
            <p class="ssg-intro">本页为静态生成，供搜索引擎与无 JS 浏览器（如夸克阅读模式）使用。</p>
            <ul class="ssg-book-list">
                {{BOOKS_LIST_HTML}}
            </ul>
        </article>
    </main>
</body>
</html>"""


def _render_markdown_safe(md_text: str) -> str:
    """把 Markdown 渲染为 HTML 并用 bleach 净化，避免 XSS。

    依赖缺失时退化为 HTML escape，保证不抛错（与 yaml 同样的容错策略）。
    """
    if md_lib is None or bleach is None:
        return html_module.escape(md_text)
    raw_html = md_lib.markdown(
        md_text,
        extensions=["extra", "toc"],
        output_format="html5",
    )
    return bleach.clean(
        raw_html,
        tags=_SSG_ALLOWED_TAGS,
        attributes=_SSG_ALLOWED_ATTRS,
        protocols=_SSG_ALLOWED_PROTOCOLS,
        strip=True,
    )


def _ssg_html_filename(note_entry: dict[str, Any]) -> str:
    """根据 note 生成 SSG HTML 文件名（不含路径，含 .html 后缀）。

    与 site/notes/*.md 镜像：{chapter}_{event}.html。
    """
    chapter = str(note_entry.get("chapter") or "")
    event = str(note_entry.get("event") or "")
    stem = f"{chapter}_{event}" if event else chapter
    return stem + ".html"


def _flatten_book_tree(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 book 的 tree (chapter -> event) 扁平化为 event 线性列表（已排序）。"""
    flat: list[dict[str, Any]] = []
    for chapter_node in tree:
        for event_node in (chapter_node.get("children") or []):
            flat.append(event_node)
    return flat


def _render_chapter_html(
    note_entry: dict[str, Any],
    book_meta: dict[str, Any],
    prev_entry: dict[str, Any] | None,
    next_entry: dict[str, Any] | None,
) -> str:
    """渲染单篇笔记的 SSG HTML。"""
    title = str(note_entry.get("title") or "")
    book_title = str(book_meta.get("title") or "")
    chapter = str(note_entry.get("chapter") or "")
    event = str(note_entry.get("event") or "")

    content_html = _render_markdown_safe(note_entry.get("content") or "")

    # 路径相对 site/reader/{book}/{chapter}_{event}.html
    css_path = "../../css/style.css"
    home_path = "../../index.html"
    book_index_path = "index.html"

    prev_href = ""
    prev_label = "已是第一章"
    if prev_entry:
        prev_href = _ssg_html_filename(prev_entry)
        prev_label = f"上一章 · {prev_entry.get('title') or ''}"
    next_href = ""
    next_label = "已是最后一章"
    if next_entry:
        next_href = _ssg_html_filename(next_entry)
        next_label = f"下一章 · {next_entry.get('title') or ''}"

    event_sep = " · " if event else ""
    raw_content = note_entry.get("content") or ""
    description = raw_content[:160].replace("\n", " ").strip()
    if len(raw_content) > 160:
        description += "…"

    html = _SSG_CHAPTER_TEMPLATE
    html = html.replace("{{TITLE}}", html_module.escape(title))
    html = html.replace("{{BOOK_TITLE}}", html_module.escape(book_title))
    html = html.replace("{{CHAPTER}}", html_module.escape(chapter))
    html = html.replace("{{EVENT}}", html_module.escape(event))
    html = html.replace("{{EVENT_SEP}}", event_sep)
    html = html.replace("{{DESCRIPTION}}", html_module.escape(description))
    html = html.replace("{{CSS_PATH}}", css_path)
    html = html.replace("{{HOME_PATH}}", home_path)
    html = html.replace("{{BOOK_INDEX_PATH}}", book_index_path)
    html = html.replace("{{CONTENT_HTML}}", content_html)
    html = html.replace("{{PREV_HREF}}", html_module.escape(prev_href))
    html = html.replace("{{PREV_LABEL}}", html_module.escape(prev_label))
    html = html.replace("{{NEXT_HREF}}", html_module.escape(next_href))
    html = html.replace("{{NEXT_LABEL}}", html_module.escape(next_label))
    return html


def _render_book_index_html(
    book_meta: dict[str, Any],
    book_notes: list[dict[str, Any]],
) -> str:
    """渲染某本书的目录索引页 site/reader/{book}/index.html。"""
    book_title = str(book_meta.get("title") or "")
    description = str(book_meta.get("description") or "")

    # 按 chapter 分组，保留首次出现顺序（book_notes 已排序）
    chapters: dict[str, list[dict[str, Any]]] = {}
    chapter_order: list[str] = []
    for note in book_notes:
        ch = str(note.get("chapter") or "")
        if ch not in chapters:
            chapters[ch] = []
            chapter_order.append(ch)
        chapters[ch].append(note)

    parts: list[str] = []
    for ch_name in chapter_order:
        events = chapters[ch_name]
        parts.append(
            f'<li class="ssg-chapter-group"><h2>{html_module.escape(ch_name)}</h2><ul>'
        )
        for ev in events:
            ev_title = str(ev.get("title") or "")
            ev_href = _ssg_html_filename(ev)
            parts.append(
                f'<li><a href="{html_module.escape(ev_href)}">{html_module.escape(ev_title)}</a></li>'
            )
        parts.append("</ul></li>")
    chapter_list_html = "\n".join(parts)

    description_html = (
        f"<p>{html_module.escape(description)}</p>" if description else ""
    )

    html = _SSG_BOOK_INDEX_TEMPLATE
    html = html.replace("{{BOOK_TITLE}}", html_module.escape(book_title))
    html = html.replace("{{DESCRIPTION_HTML}}", description_html)
    html = html.replace("{{CHAPTER_LIST_HTML}}", chapter_list_html)
    html = html.replace("{{CSS_PATH}}", "../css/style.css")
    html = html.replace("{{HOME_PATH}}", "../../index.html")
    html = html.replace("{{GLOBAL_INDEX_PATH}}", "../index.html")
    return html


def _render_global_index_html(books_array: list[dict[str, Any]]) -> str:
    """渲染全章节总索引页 site/reader/index.html。"""
    parts: list[str] = []
    for book in books_array:
        book_id = str(book.get("id") or "")
        book_title = str(book.get("title") or "")
        book_desc = str(book.get("description") or "")
        # URL 中文路径需 quote；文件系统层不 quote（mkdir 直接支持中文）
        book_href = f"{quote(book_id)}/index.html"
        chapter_count = book.get("chapter_count", 0)
        note_count = book.get("note_count", 0)
        parts.append(
            f'<li class="ssg-book-card">'
            f'<h2><a href="{html_module.escape(book_href)}">{html_module.escape(book_title)}</a></h2>'
            f'<p class="ssg-book-meta">章节 {chapter_count} · 笔记 {note_count}</p>'
            f'<p>{html_module.escape(book_desc)}</p>'
            f'</li>'
        )
    books_list_html = "\n".join(parts)

    html = _SSG_GLOBAL_INDEX_TEMPLATE
    html = html.replace("{{BOOKS_LIST_HTML}}", books_list_html)
    html = html.replace("{{CSS_PATH}}", "../css/style.css")
    html = html.replace("{{HOME_PATH}}", "../index.html")
    return html


def _build_ssg_pages(
    site_path: Path,
    books_array: list[dict[str, Any]],
    notes: dict[str, dict[str, Any]],
) -> None:
    """为每篇笔记生成 SSG 静态 HTML，并生成书索引页与全章节索引页。

    产物路径：site/reader/{书}/{章节}_{事件}.html
    夸克浏览器阅读模式不执行 JS，必须由原始 HTML 直接含正文。
    """
    if md_lib is None or bleach is None:
        print(
            "[build_site] markdown/bleach 未安装，跳过 SSG 章节页生成。"
            "请运行 pip install markdown bleach 启用夸克阅读模式兼容。",
            file=sys.stderr,
        )
        return

    reader_dir = site_path / "reader"
    # 幂等：清空旧 SSG 产物（处理笔记删除场景）
    if reader_dir.exists():
        for child in reader_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        reader_dir.mkdir(parents=True, exist_ok=True)

    total_html = 0
    for book in books_array:
        book_id = str(book.get("id") or "")
        book_title = str(book.get("title") or "")
        book_meta = {
            "title": book_title,
            "description": book.get("description") or "",
        }
        book_dir = reader_dir / book_id
        book_dir.mkdir(parents=True, exist_ok=True)

        # book["tree"] 已经过 sort_notes_tree 排序，扁平化得到 event 线性列表
        flat_notes = _flatten_book_tree(book.get("tree") or [])

        # 取每篇 note_entry（含 content），并保留 ev_node 用于 prev/next
        ev_entries: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for ev_node in flat_notes:
            ev_path = str(ev_node.get("path") or "")
            note_entry = notes.get(ev_path)
            if not note_entry:
                continue
            ev_entries.append((ev_node, note_entry))

        # 生成每篇笔记的 HTML
        for idx, (_ev_node, note_entry) in enumerate(ev_entries):
            prev_entry = ev_entries[idx - 1][1] if idx > 0 else None
            next_entry = ev_entries[idx + 1][1] if idx < len(ev_entries) - 1 else None

            chapter_html = _render_chapter_html(
                note_entry, book_meta, prev_entry, next_entry
            )

            html_filename = _ssg_html_filename(note_entry)
            html_path = book_dir / html_filename
            html_path.write_text(chapter_html, encoding="utf-8")
            total_html += 1

        # 生成书索引页 site/reader/{书}/index.html
        book_notes_list = [entry for _, entry in ev_entries]
        book_index_html = _render_book_index_html(book_meta, book_notes_list)
        (book_dir / "index.html").write_text(book_index_html, encoding="utf-8")
        total_html += 1

    # 生成全章节总索引页 site/reader/index.html
    global_index_html = _render_global_index_html(books_array)
    (reader_dir / "index.html").write_text(global_index_html, encoding="utf-8")
    total_html += 1

    print(
        f"[build_site] SSG 章节页已生成：{total_html} 个 HTML 文件 -> {reader_dir}"
    )


def build_site(output_dir: str = "output", site_dir: str = "site") -> Path:
    """扫描 output/ 下的 Markdown 笔记，生成静态站点到 site/。

    Args:
        output_dir: 笔记源目录，默认 "output"。
        site_dir: 静态站点输出目录，默认 "site"。

    Returns:
        站点输出目录的 Path。
    """
    output_path = Path(output_dir)
    site_path = Path(site_dir)

    data_dir = site_path / "data"
    notes_dir = site_path / "notes"
    data_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)

    # 同步前端静态资源（html/css/js/sw），避免手动维护导致 GitHub Pages 版本滞后
    _copy_static_assets(site_path)

    # 清空 notes 目录，保证幂等（处理笔记删除场景）
    for child in notes_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    notes: dict[str, dict[str, Any]] = {}
    books: dict[str, dict[str, list[dict[str, Any]]]] = {}

    if output_path.exists():
        for md_path in sorted(output_path.rglob("*.md")):
            # 跳过下划线开头的辅助文件（如 _目录.md、_meta.yaml 等），
            # 与 check_book_structure.py 保持一致，避免目录中出现空章节。
            if md_path.name.startswith("_"):
                continue
            rel = md_path.relative_to(output_path)
            rel_str = str(rel).replace("\\", "/")
            parsed = _parse_note_path(rel_str)
            if parsed is None:
                continue
            book, chapter, event = parsed

            text = md_path.read_text(encoding="utf-8")
            frontmatter, content = _parse_frontmatter(text)

            title = frontmatter.get("title") or event or chapter
            if not isinstance(title, str):
                title = str(title)
            created_at = _normalize_created_at(frontmatter.get("created_at"))
            source_agents = _normalize_source_agents(frontmatter.get("source_agents"))
            note_sort = _to_int(frontmatter.get("sort"))
            note_chapter_sort = _to_int(frontmatter.get("chapter_sort"))

            note_entry = {
                "path": rel_str,
                "book": book,
                "chapter": chapter,
                "event": event,
                "title": title,
                "created_at": created_at,
                "source_agents": source_agents,
                "sort": note_sort,
                "chapter_sort": note_chapter_sort,
                "content": content,
            }
            notes[rel_str] = note_entry

            books.setdefault(book, {}).setdefault(chapter, []).append(
                {
                    "title": event or chapter,
                    "type": "event",
                    "path": rel_str,
                    "sort": note_sort,
                    "chapter_sort": note_chapter_sort,
                }
            )

            # 复制 Markdown 文件到 site/notes/（保持相对路径结构）
            dest = notes_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_path, dest)

    # 构建每本书的 tree（book -> chapter -> event）
    book_trees: dict[str, list[dict[str, Any]]] = {}
    for book_name in sorted(books.keys()):
        chapters: list[dict[str, Any]] = []
        for chapter_name in sorted(books[book_name].keys()):
            events = books[book_name][chapter_name]
            chapter_sort = next(
                (e.get("chapter_sort") for e in events if e.get("chapter_sort") is not None),
                None,
            )
            chapters.append(
                {
                    "title": chapter_name,
                    "type": "chapter",
                    "chapter_sort": chapter_sort,
                    "children": events,
                }
            )
        book_trees[book_name] = chapters

    # 顶层 tree（向后兼容），并按朝代/序号规则排序
    tree: list[dict[str, Any]] = []
    for book_name in sorted(books.keys()):
        tree.append(
            {
                "title": book_name,
                "type": "book",
                "children": book_trees[book_name],
            }
        )
    sort_notes_tree(tree)

    # 构建 books 数组（含元数据 + 本书 tree + 计数）
    books_array: list[dict[str, Any]] = []
    for book_name in books.keys():
        book_dir = output_path / book_name
        meta = _load_book_meta(book_dir, book_name)
        chapter_count = len(book_trees[book_name])
        note_count = sum(len(ch["children"]) for ch in book_trees[book_name])
        books_array.append(
            {
                "id": book_name,
                "title": meta["title"],
                "category": meta["category"],
                "description": meta["description"],
                "author": meta["author"],
                "cover": meta["cover"],
                "sort": meta["sort"],
                "chapter_count": chapter_count,
                "note_count": note_count,
                "tree": book_trees[book_name],
            }
        )

    # 排序：category 优先级 → book sort → title
    books_array.sort(
        key=lambda b: (
            _category_sort_key(b["category"])[0],
            b["sort"],
            b["title"],
        )
    )

    # categories 列表（按优先级排序，只含实际出现的分类）
    categories = sorted(
        {b["category"] for b in books_array},
        key=_category_sort_key,
    )

    generated_at = (
        datetime.now()
        .astimezone()
        .replace(microsecond=0)
        .isoformat()
    )
    stats = {
        "books": len(books),
        "notes": len(notes),
        "categories": len(categories),
    }

    # 首页索引：仅含元数据与目录树，不含笔记正文，保证首屏极速加载
    index = {
        "version": VERSION,
        "generated_at": generated_at,
        "stats": stats,
        "books": books_array,
        "categories": categories,
        "tree": tree,
    }

    index_path = data_dir / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 搜索索引：仅含标题、路径、出处和摘要，按需加载
    search_notes = []
    for rel_str, note in notes.items():
        content = note.get("content", "")
        snippet = content[:300].replace("\n", " ")
        if len(content) > 300:
            snippet = snippet.rstrip() + "…"
        search_notes.append(
            {
                "path": rel_str,
                "book": note.get("book", ""),
                "chapter": note.get("chapter", ""),
                "event": note.get("event", ""),
                "title": note.get("title", ""),
                "snippet": snippet,
            }
        )
    search_index = {
        "version": VERSION,
        "generated_at": generated_at,
        "stats": stats,
        "notes": search_notes,
    }
    search_index_path = data_dir / "search-index.json"
    search_index_path.write_text(
        json.dumps(search_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 .nojekyll 标记，让 GitHub Pages 跳过 Jekyll 构建，直接部署静态文件
    (site_path / ".nojekyll").write_text("", encoding="utf-8")

    # BUG-035：为每篇笔记生成 SSG 静态 HTML，让夸克阅读模式能识别章节正文
    _build_ssg_pages(site_path, books_array, notes)

    return site_path


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="扫描 output/ 下的 Markdown 笔记，生成静态站点到 site/。"
    )
    parser.add_argument(
        "--output", default="output", help="笔记源目录（默认 output）"
    )
    parser.add_argument(
        "--site", default="site", help="站点输出目录（默认 site）"
    )
    args = parser.parse_args(argv)

    site_path = build_site(output_dir=args.output, site_dir=args.site)
    print(f"静态站点已生成: {site_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
