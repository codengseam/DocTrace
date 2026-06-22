from pathlib import Path
from typing import Any, Dict, Optional


# 规则文件主从配置：
# - 主库：.trae/rules/rules.md（Trae 自动加载）
# - 从库：RULES.md（根目录，兼容其他 IDE/工具）
RULES_PRIMARY = Path(".trae/rules/rules.md")
RULES_FALLBACK = Path("RULES.md")


def load_rules() -> str:
    """加载项目写作规则，优先读主库，主库不存在则读从库。"""
    for path in (RULES_PRIMARY, RULES_FALLBACK):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def load_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    path = Path("prompts") / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    content = path.read_text(encoding="utf-8")
    if variables:
        for key, value in variables.items():
            content = content.replace(f"{{{key}}}", str(value))
    return content
