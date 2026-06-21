from langgraph.graph import END, START, StateGraph

from src.agents import (
    biographer,
    context_analyst,
    critic,
    editor,
    historian,
    orchestrator,
    philosopher,
)
from typing import Optional

from src.core.state import AgentState
from src.utils.config import load_config
from src.utils.markdown import save_markdown


def build_workflow(output_base: Optional[str] = None) -> StateGraph:
    if output_base is None:
        cfg = load_config()
        output_base = cfg.get("output", {}).get("base_dir", "output")

    graph = StateGraph(AgentState)

    def orchestrator_node(state: AgentState) -> dict:
        return orchestrator.run(state)

    def historian_node(state: AgentState) -> dict:
        return historian.run(state)

    def biographer_node(state: AgentState) -> dict:
        return biographer.run(state)

    def context_analyst_node(state: AgentState) -> dict:
        return context_analyst.run(state)

    def critic_node(state: AgentState) -> dict:
        return critic.run(state)

    def philosopher_node(state: AgentState) -> dict:
        return philosopher.run(state)

    def editor_node(state: AgentState) -> dict:
        return editor.run(state)

    def save_node(state: AgentState) -> dict:
        path = save_markdown(
            book=state["book"],
            chapter=state["chapter"],
            event=state["event"],
            content=state["final_markdown"],
            base_dir=output_base,
        )
        return {"output_path": str(path)}

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("historian", historian_node)
    graph.add_node("biographer", biographer_node)
    graph.add_node("context_analyst", context_analyst_node)
    graph.add_node("critic", critic_node)
    graph.add_node("philosopher", philosopher_node)
    graph.add_node("editor", editor_node)
    graph.add_node("save", save_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "historian")
    graph.add_edge("orchestrator", "biographer")
    graph.add_edge("orchestrator", "context_analyst")
    graph.add_edge("orchestrator", "critic")
    graph.add_edge("orchestrator", "philosopher")
    graph.add_edge("historian", "editor")
    graph.add_edge("biographer", "editor")
    graph.add_edge("context_analyst", "editor")
    graph.add_edge("critic", "editor")
    graph.add_edge("philosopher", "editor")
    graph.add_edge("editor", "save")
    graph.add_edge("save", END)

    return graph.compile()
