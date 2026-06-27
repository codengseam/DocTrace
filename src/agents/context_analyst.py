"""讲背景 Specialist：补齐前因后果与制度环境。

阶段4：按 archetype 加载对应桶 prompt，段名从 SECTION_TEMPLATES 反查。
- narrative：讲背景
- modern：方法论（context_analyst 负责）
- knowledge：概念（context_analyst 负责）
"""

from src.agents.editor import SECTION_TEMPLATES
from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt
from src.utils.sources import extract_sources

_AGENT_NAME = "context_analyst"
_DEFAULT_TITLE = "讲背景"


def _section_title(archetype: str) -> str:
    """按 archetype 反查本 specialist 负责的段名。"""
    mapping = SECTION_TEMPLATES.get(archetype, SECTION_TEMPLATES["narrative"])
    for section, agent in mapping.items():
        if agent == _AGENT_NAME:
            return section
    return _DEFAULT_TITLE


def run(state: AgentState) -> dict:
    """生成段落（段名按 archetype 路由）。"""
    archetype = state.get("archetype", "narrative")
    llm = create_llm(temperature=0.7)
    prompt = load_prompt(
        "context_analyst",
        {
            "book": state["book"],
            "chapter": state["chapter"],
            "event": state["event"],
            "user_input": state["user_input"],
        },
        archetype=archetype,
    )
    content = llm.invoke(prompt).content
    title = _section_title(archetype)
    return {
        "sections": {title: content},
        "sources": {title: extract_sources(content)},
    }
