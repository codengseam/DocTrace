"""讲道理 Specialist：只引用明确点评该事件的名家之言。

阶段4：按 archetype 加载对应桶 prompt，段名从 SECTION_TEMPLATES 反查。
- narrative：讲道理
- modern：破题 + 避坑（critic 负责，但一个 agent 一个段名，取首个匹配）
- knowledge：critic 不参与
"""

from src.agents.editor import SECTION_TEMPLATES
from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt
from src.utils.sources import extract_sources

_AGENT_NAME = "critic"
_DEFAULT_TITLE = "讲道理"


def _section_title(archetype: str) -> str:
    """按 archetype 反查本 specialist 负责的段名。

    注意：modern 桶 critic 负责两个段（破题+避坑），但一个 agent 节点一次只产
    一段。workflow 的 modern 边链是 orchestrator→critic（单次），取首个匹配
    「破题」。避坑段由 editor 汇总时从 prompt 上下文补，或后续拆分 critic 为
    两节点。当前阶段4 最小实现：critic 产「破题」。
    """
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
        "critic",
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
