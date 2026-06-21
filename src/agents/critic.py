"""讲道理 Specialist：只引用明确点评该事件的名家之言。"""

from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt
from src.utils.sources import extract_sources


def run(state: AgentState) -> dict:
    """生成「讲道理」段落。"""
    llm = create_llm(temperature=0.7)
    prompt = load_prompt(
        "critic",
        {
            "book": state["book"],
            "chapter": state["chapter"],
            "event": state["event"],
            "user_input": state["user_input"],
        },
    )
    content = llm.invoke(prompt).content
    title = "讲道理"
    return {
        "sections": {title: content},
        "sources": {title: extract_sources(content)},
    }
