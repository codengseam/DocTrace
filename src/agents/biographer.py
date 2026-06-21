"""讲人物 Specialist：聚焦主角团人性矛盾和复杂面。"""

from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt
from src.utils.sources import extract_sources


def run(state: AgentState) -> dict:
    """生成「讲人物」段落。"""
    llm = create_llm(temperature=0.7)
    prompt = load_prompt(
        "biographer",
        {
            "book": state["book"],
            "chapter": state["chapter"],
            "event": state["event"],
            "user_input": state["user_input"],
        },
    )
    content = llm.invoke(prompt).content
    title = "讲人物"
    return {
        "sections": {title: content},
        "sources": {title: extract_sources(content)},
    }
