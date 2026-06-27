import warnings
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.config import load_config


# 规则文件主从配置：
# - 主库：.trae/skills/deep-reading/rules.md（按需加载，不污染开发对话上下文）
# - 从库：RULES.md（根目录，兼容其他 IDE/工具）
RULES_PRIMARY = Path(".trae/skills/deep-reading/rules.md")
RULES_FALLBACK = Path("RULES.md")


# 阶段4：已落地的 archetype 桶（fiction 预留未落地，不在此列）。
# narrative 读原 prompts/{name}.md；modern/knowledge 读 prompts/{archetype}/{name}.md。
_LANDED_ARCHETYPES = {"narrative", "modern", "knowledge"}


def load_rules() -> str:
    """加载项目写作规则，优先读主库，主库不存在则读从库。"""
    for path in (RULES_PRIMARY, RULES_FALLBACK):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def load_prompt(
    name: str,
    variables: Optional[Dict[str, Any]] = None,
    archetype: str = "narrative",
) -> str:
    """加载 prompt 文件，按 archetype 选子目录（design.md §九阶段4、§11.4）。

    - narrative（默认）：读原 prompts/{name}.md（兼容，禁区不动）
    - modern/knowledge：读 prompts/{archetype}/{name}.md；文件不存在时 fallback
      到 narrative 原路径 + UserWarning（渐进迁移友好，不静默掩盖忘迁）
    - 非法 archetype（含 fiction 未落地）：兜底 narrative
    """
    if archetype not in _LANDED_ARCHETYPES:
        archetype = "narrative"

    original_path = Path("prompts") / f"{name}.md"

    if archetype == "narrative":
        path = original_path
    else:
        bucket_path = Path("prompts") / archetype / f"{name}.md"
        if bucket_path.exists():
            path = bucket_path
        else:
            warnings.warn(
                f"{archetype} 桶 prompt '{name}' 未迁移，fallback 到 narrative 原路径",
                UserWarning,
                stacklevel=2,
            )
            path = original_path

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    content = path.read_text(encoding="utf-8")
    if variables:
        for key, value in variables.items():
            content = content.replace(f"{{{key}}}", str(value))
    return content


_VALID_ARCHETYPES = {"narrative", "modern", "knowledge", "fiction"}
_DEFAULT_ARCHETYPE = "narrative"


def resolve_archetype(category: str, explicit: Optional[str] = None) -> str:
    """根据 category 解析 archetype。

    优先级（见 docs/archetype-design/design.md §5.6）：
    1. explicit 为合法 archetype 时直接返回
    2. 查 config.yaml 的 archetype_defaults 映射
    3. 兜底返回 narrative（古籍基线）

    Args:
        category: 主题类目（史/经/养生/财/技/职场）
        explicit: 显式声明的 archetype，优先级最高；非法值视为未提供

    Returns:
        archetype 字符串（narrative/modern/knowledge/fiction）
    """
    if explicit and explicit in _VALID_ARCHETYPES:
        return explicit
    config = load_config() or {}
    mapping = config.get("archetype_defaults") or {}
    if isinstance(mapping, dict) and category in mapping:
        value = str(mapping[category])
        # config 笔误防护：映射值必须是合法 archetype，否则兜底
        if value in _VALID_ARCHETYPES:
            return value
    return _DEFAULT_ARCHETYPE
