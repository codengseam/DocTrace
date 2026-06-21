import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:*", "http://127.0.0.1:*"]}})

BASE_DIR = Path(__file__).resolve().parent.parent.parent
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
    for book_name in sorted(books.keys()):
        book_node = {"title": book_name, "type": "book", "children": []}
        for chapter_name in sorted(books[book_name].keys()):
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
    return jsonify(tree)


@app.route("/api/notes/<path:filepath>", methods=["GET"])
def get_note(filepath):
    file_path = OUTPUT_DIR / filepath
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Invalid path"}), 400

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": "Not found"}), 404

    return file_path.read_text(encoding="utf-8")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    book = data.get("book")
    chapter = data.get("chapter")
    event = data.get("event")

    missing = [field for field in ("book", "chapter", "event") if not data.get(field)]
    if missing:
        return (
            jsonify({"success": False, "error": f"Missing fields: {', '.join(missing)}"}),
            400,
        )

    use_stub = os.environ.get("DEEP_READING_STUB") in ("1", "true", "yes")

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
        )
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
    app.run(host="127.0.0.1", port=port, debug=True)
