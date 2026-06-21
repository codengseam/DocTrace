from pathlib import Path
from typing import Any, Dict, Optional


def load_rules() -> str:
    path = Path("RULES.md")
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    path = Path("prompts") / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    content = path.read_text(encoding="utf-8")
    if variables:
        for key, value in variables.items():
            content = content.replace(f"{{{key}}}", str(value))
    return content
