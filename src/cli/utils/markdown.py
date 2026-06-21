from __future__ import annotations

from datetime import datetime
from pathlib import Path


def slugify(text: str) -> str:
    return text.strip().replace(" ", "_").replace("/", "_")


def build_output_path(output_dir: Path, book: str, chapter: str, event: str) -> Path:
    folder = output_dir / slugify(book)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(chapter)}_{slugify(event)}.md"
    return folder / filename


def build_frontmatter(
    title: str,
    book: str,
    chapter: str,
    event: str,
    source_agents: list[str],
    created_at: str | None = None,
) -> str:
    if created_at is None:
        created_at = datetime.now().isoformat()
    lines = [
        "---",
        f"title: {title}",
        f"book: {book}",
        f"chapter: {chapter}",
        f"event: {event}",
        f"created_at: {created_at}",
        f"source_agents: {source_agents}",
        "---",
        "",
    ]
    return "\n".join(lines)


def save_markdown(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
