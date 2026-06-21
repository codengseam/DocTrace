"""讲背景 Specialist：补齐前因后果与制度环境。"""

from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt


def _extract_sources(content: str) -> list[str]:
    """从 LLM 输出中提取文末来源列表。"""
    markers = ["来源：", "参考资料：", "引用：", "出处：", "参考："]
    for marker in markers:
        idx = content.rfind(marker)
        if idx != -1:
            tail = content[idx + len(marker):]
            lines = [line.strip().lstrip("-0123456789. ").strip() for line in tail.splitlines() if line.strip()]
            return [line for line in lines if line]
    return []


def run(state: AgentState) -> dict:
    """生成「讲背景」段落。"""
    llm = create_llm(temperature=0.7)
    prompt = load_prompt(
        "context_analyst",
        {
            "book": state["book"],
            "chapter": state["chapter"],
            "event": state["event"],
            "user_input": state["user_input"],
        },
    )
    content = llm.invoke(prompt).content
    title = "讲背景"
    return {
        "sections": {title: content},
        "sources": {title: _extract_sources(content)},
    }
