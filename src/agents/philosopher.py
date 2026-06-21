"""问道悟道 Specialist：从具体事件提炼本质规律。"""

from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt
from src.utils.sources import extract_sources


def run(state: AgentState) -> dict:
    """生成「问道悟道」段落。"""
    llm = create_llm(temperature=0.7)
    prompt = load_prompt(
        "philosopher",
        {
            "book": state["book"],
            "chapter": state["chapter"],
            "event": state["event"],
            "user_input": state["user_input"],
        },
    )
    content = llm.invoke(prompt).content
    title = "问道悟道"
    return {
        "sections": {title: content},
        "sources": {title: extract_sources(content)},
    }
