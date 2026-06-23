from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.utils.sorting import sort_notes_tree  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

app = Flask(__name__, static_folder="static", template_folder="templates")

OUTPUT_DIR = BASE_DIR / "output"
MAIN_SCRIPT = BASE_DIR / "src" / "main.py"

load_dotenv(BASE_DIR / ".env")


def _has_api_key() -> bool:
    return bool(os.environ.get("LLM_API_KEY"))


def _iter_notes():
    """Yield (relative_path, book, chapter, event) for each Markdown note."""
    if not OUTPUT_DIR.exists():
        return
    for md_path in sorted(OUTPUT_DIR.rglob("*.md")):
        rel = md_path.relative_to(OUTPUT_DIR)
        parts = rel.parts
        if len(parts) < 2:
            continue
        book = parts[0]
        stem = parts[-1]
        if stem.endswith(".md"):
            stem = stem[:-3]
        if "_" in stem:
            chapter, event = stem.split("_", 1)
        else:
            chapter = stem
            event = ""
        yield str(rel).replace(os.sep, "/"), book, chapter, event


def _extract_path_from_output(stdout):
    """Extract the generated note's relative path from main.py stdout."""
    if not stdout:
        return None
    prefixes = ("Saved: ", "File already exists: ", "已生成笔记：")
    for line in stdout.splitlines():
        for prefix in prefixes:
            if line.startswith(prefix):
                abs_path = line[len(prefix):].strip()
                try:
                    rel = Path(abs_path).resolve().relative_to(OUTPUT_DIR.resolve())
                    return str(rel).replace(os.sep, "/")
                except (ValueError, OSError):
                    return abs_path
    return None


def _parse_note_path(rel_path: str) -> tuple[str, str, str] | None:
    """解析相对路径为 (book, chapter, event)。"""
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


def _load_book_meta(book_dir: Path, book_name: str) -> dict[str, Any]:
    """读取 book_dir/_meta.yaml 元数据，失败时返回默认值。"""
    defaults: dict[str, Any] = {
        "title": book_name,
        "category": "未分类",
        "description": "",
        "author": "",
        "cover": "📖",
        "sort": 99,
    }
    meta_path = book_dir / "_meta.yaml"
    if not meta_path.exists() or yaml is None:
        return defaults
    try:
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
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
    """分类排序键：经 < 史 < 子 < 集 < 其他 < 未分类。"""
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


def _read_note_content(rel_path: str) -> str:
    """读取笔记正文，失败时返回空字符串。"""
    try:
        return (OUTPUT_DIR / rel_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _build_index() -> dict[str, Any]:
    """扫描 output/ 目录，构建与静态站点 index.json 兼容的数据。"""
    notes: dict[str, dict[str, Any]] = {}
    books: dict[str, dict[str, list[dict[str, Any]]]] = {}

    if OUTPUT_DIR.exists():
        for md_path in sorted(OUTPUT_DIR.rglob("*.md")):
            rel = md_path.relative_to(OUTPUT_DIR)
            rel_str = str(rel).replace(os.sep, "/")
            parsed = _parse_note_path(rel_str)
            if parsed is None:
                continue
            book, chapter, event = parsed
            content = _read_note_content(rel_str)
            title = event or chapter

            notes[rel_str] = {
                "path": rel_str,
                "book": book,
                "chapter": chapter,
                "event": event,
                "title": title,
                "content": content,
            }
            books.setdefault(book, {}).setdefault(chapter, []).append(
                {
                    "title": event or chapter,
                    "type": "event",
                    "path": rel_str,
                }
            )

    # 每本书的目录树
    book_trees: dict[str, list[dict[str, Any]]] = {}
    for book_name in sorted(books.keys()):
        chapters: list[dict[str, Any]] = []
        for chapter_name in sorted(books[book_name].keys()):
            events = sorted(
                books[book_name][chapter_name], key=lambda e: e["path"]
            )
            chapters.append(
                {
                    "title": chapter_name,
                    "type": "chapter",
                    "children": events,
                }
            )
        book_trees[book_name] = chapters

    # 顶层合并树
    tree: list[dict[str, Any]] = []
    for book_name in sorted(books.keys()):
        tree.append(
            {
                "title": book_name,
                "type": "book",
                "children": book_trees[book_name],
            }
        )

    # 书籍数组（含元数据）
    books_array: list[dict[str, Any]] = []
    for book_name in books.keys():
        book_dir = OUTPUT_DIR / book_name
        meta = _load_book_meta(book_dir, book_name)
        chapters = book_trees[book_name]
        note_count = sum(len(ch["children"]) for ch in chapters)
        books_array.append(
            {
                "id": book_name,
                "title": meta["title"],
                "category": meta["category"],
                "description": meta["description"],
                "author": meta["author"],
                "cover": meta["cover"],
                "sort": meta["sort"],
                "chapter_count": len(chapters),
                "note_count": note_count,
                "tree": chapters,
            }
        )

    books_array.sort(
        key=lambda b: (
            _category_sort_key(b["category"])[0],
            b["sort"],
            b["title"],
        )
    )

    categories = sorted(
        {b["category"] for b in books_array},
        key=_category_sort_key,
    )

    return {
        "version": "1.1.0",
        "generated_at": datetime.now()
        .astimezone()
        .replace(microsecond=0)
        .isoformat(),
        "stats": {
            "books": len(books_array),
            "notes": len(notes),
            "categories": len(categories),
        },
        "books": books_array,
        "categories": categories,
        "tree": tree,
        "notes": notes,
    }


@app.route("/api/notes", methods=["GET"])
def list_notes():
    """Return a tree of notes: book -> chapter -> event."""
    books = {}
    for rel_path, book, chapter, event in _iter_notes():
        books.setdefault(book, {}).setdefault(chapter, []).append(
            {
                "title": event or chapter,
                "type": "event",
                "path": rel_path,
            }
        )

    tree = []
    for book_name in books.keys():
        book_node = {"title": book_name, "type": "book", "children": []}
        for chapter_name in books[book_name].keys():
            events = sorted(
                books[book_name][chapter_name], key=lambda e: e["path"]
            )
            book_node["children"].append(
                {
                    "title": chapter_name,
                    "type": "chapter",
                    "children": events,
                }
            )
        tree.append(book_node)
    sort_notes_tree(tree)
    return jsonify(tree)


@app.route("/api/index", methods=["GET"])
def index_data():
    """Return the full bookshelf index (books, categories, notes, tree)."""
    return jsonify(_build_index())


@app.route("/api/notes/<path:filepath>", methods=["GET"])
def get_note(filepath):
    file_path = OUTPUT_DIR / filepath
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Invalid path"}), 400

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": "Not found"}), 404

    content = file_path.read_text(encoding="utf-8")
    return Response(content, mimetype="text/plain; charset=utf-8")


@app.route("/api/search", methods=["GET"])
def search_notes():
    """Search notes by keyword in filename and content."""
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"query": "", "results": []})

    query_lower = query.lower()
    results = []
    for rel_path, book, chapter, event in _iter_notes():
        title = event or chapter
        matched_in_name = (
            query_lower in rel_path.lower() or query_lower in title.lower()
        )

        file_path = OUTPUT_DIR / rel_path
        content = ""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass

        matched_in_content = query_lower in content.lower()
        if not (matched_in_name or matched_in_content):
            continue

        snippet = ""
        if matched_in_content:
            idx = content.lower().find(query_lower)
            if idx >= 0:
                start = max(0, idx - 30)
                end = min(len(content), idx + len(query) + 60)
                snippet = content[start:end].replace("\n", " ")
                if start > 0:
                    snippet = "…" + snippet
                if end < len(content):
                    snippet = snippet + "…"

        results.append(
            {
                "path": rel_path,
                "book": book,
                "chapter": chapter,
                "event": event,
                "title": title,
                "snippet": snippet,
            }
        )

    return jsonify({"query": query, "results": results})


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    book = data.get("book")
    chapter = data.get("chapter")
    event = data.get("event")
    user_input = data.get("input")

    use_stub = os.environ.get("DEEP_READING_STUB") in ("1", "true", "yes")

    if user_input:
        if not use_stub and not _has_api_key():
            return jsonify({
                "success": False,
                "error": "未配置 LLM_API_KEY。请复制 .env.example 为 .env 并填写 API Key，或设置 DEEP_READING_STUB=1 使用占位模式。"
            }), 400

        cmd = [sys.executable, str(MAIN_SCRIPT), "--input", user_input]
        if use_stub:
            cmd.append("--stub")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "error": "生成超时（300 秒），请稍后重试或简化输入。"}), 504
        except Exception as exc:  # pragma: no cover - unexpected execution error
            return jsonify({"success": False, "error": str(exc)}), 500

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Generation failed").strip()
            return jsonify({"success": False, "error": message}), 500

        generated_path = _extract_path_from_output(result.stdout)
        return jsonify({
            "success": True,
            "path": generated_path,
            "stub": use_stub,
            "message": "占位生成完成" if use_stub else "笔记生成完成",
        })

    missing = [field for field in ("book", "chapter", "event") if not data.get(field)]
    if missing:
        return (
            jsonify({"success": False, "error": f"Missing fields: {', '.join(missing)}"}),
            400,
        )

    if not use_stub and not _has_api_key():
        return jsonify({
            "success": False,
            "error": "未配置 LLM_API_KEY。请复制 .env.example 为 .env 并填写 API Key，或设置 DEEP_READING_STUB=1 使用占位模式。"
        }), 400

    cmd = [
        sys.executable,
        str(MAIN_SCRIPT),
        "--book",
        book,
        "--chapter",
        chapter,
        "--event",
        event,
    ]
    if use_stub:
        cmd.append("--stub")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "生成超时（300 秒），请稍后重试或简化输入。"}), 504
    except Exception as exc:  # pragma: no cover - unexpected execution error
        return jsonify({"success": False, "error": str(exc)}), 500

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Generation failed").strip()
        return jsonify({"success": False, "error": message}), 500

    generated_path = Path(book) / f"{chapter}_{event}.md"
    return jsonify({
        "success": True,
        "path": str(generated_path).replace(os.sep, "/"),
        "stub": use_stub,
        "message": "占位生成完成" if use_stub else "笔记生成完成",
    })


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("DEEP_READING_WEB_PORT", "8080"))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
