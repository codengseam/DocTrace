from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union


def build_frontmatter(
    title: str,
    book: str,
    chapter: str,
    event: str,
    source_agents: List[str],
) -> str:
    created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    agents_yaml = "\n".join(f"  - {agent}" for agent in source_agents)
    return f"""---
title: "{title}"
book: "{book}"
chapter: "{chapter}"
event: "{event}"
created_at: "{created_at}"
source_agents:
{agents_yaml}
---

"""


def save_markdown(
    book: str,
    chapter: str,
    event: str,
    content: str,
    base_dir: Union[Path, str] = "output",
) -> Path:
    base = Path(base_dir)
    book_dir = base / book
    book_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{chapter}_{event}.md"
    path = book_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def split_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    current = []
    current_title = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_title is not None:
                sections[current_title] = "\n".join(current).strip()
            current_title = stripped[3:].strip()
            current = []
        elif current_title is not None:
            current.append(line)
    if current_title is not None:
        sections[current_title] = "\n".join(current).strip()
    return sections
