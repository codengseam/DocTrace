from typing import Optional

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
from src.core.state import AgentState
from src.utils.config import load_config
from src.utils.logger import get_logger, make_log_path
from src.utils.markdown import save_markdown
from src.utils.quality import run_quality_checks


def build_workflow(output_base: Optional[str] = None) -> StateGraph:
    if output_base is None:
        cfg = load_config()
        output_base = cfg.get("output_dir") or cfg.get("output", {}).get("base_dir", "output")

    logger = get_logger("deep_reading.workflow")

    graph = StateGraph(AgentState)

    def orchestrator_node(state: AgentState) -> dict:
        logger.info("Orchestrator 解析输入...")
        return orchestrator.run(state)

    def historian_node(state: AgentState) -> dict:
        logger.info("史料专家生成中...")
        return historian.run(state)

    def biographer_node(state: AgentState) -> dict:
        logger.info("人物专家生成中...")
        return biographer.run(state)

    def context_analyst_node(state: AgentState) -> dict:
        logger.info("背景专家生成中...")
        return context_analyst.run(state)

    def critic_node(state: AgentState) -> dict:
        logger.info("名家专家生成中...")
        return critic.run(state)

    def philosopher_node(state: AgentState) -> dict:
        logger.info("悟道专家生成中...")
        return philosopher.run(state)

    def editor_node(state: AgentState) -> dict:
        logger.info("编辑专家汇总润色中...")
        return editor.run(state)

    def quality_node(state: AgentState) -> dict:
        """质量检查节点：检查结构完整性、AI 味、引用等。"""
        content = state.get("final_markdown", "")
        cfg = load_config()
        required_sections = cfg.get("quality_check", {}).get(
            "required_sections",
            ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"],
        )
        required_frontmatter = [
            "title", "book", "chapter", "event", "created_at", "source_agents"
        ]
        report = run_quality_checks(
            content,
            expected_sections=required_sections,
            required_frontmatter=required_frontmatter,
        )
        if report.passed:
            logger.info("质量检查通过")
        else:
            logger.warning("质量检查发现问题：%s", "; ".join(report.issues))
        return {"errors": report.issues}

    def quality_router(state: AgentState) -> str:
        """根据质量检查结果决定下一步：通过则保存，失败则结束。"""
        if state.get("errors"):
            logger.warning("质量检查未通过，跳过保存")
            return END
        return "save"

    def save_node(state: AgentState) -> dict:
        # 记录日志
        event = state.get("event", "unknown")
        cfg = load_config()
        logs_dir = cfg.get("logs", {}).get("base_dir", "logs")
        log_path = make_log_path(logs_dir, event)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"书名: {state.get('book', '')}\n"
                f"章节: {state.get('chapter', '')}\n"
                f"事件: {state.get('event', '')}\n"
                f"输出: {state.get('output_path', '')}\n"
                f"质量问题: {state.get('errors', [])}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("无法写入日志文件 %s: %s", log_path, exc)

        path = save_markdown(
            book=state["book"],
            chapter=state["chapter"],
            event=state["event"],
            content=state["final_markdown"],
            base_dir=output_base,
        )
        logger.info("笔记已保存至 %s", path)
        return {"output_path": str(path)}

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("historian", historian_node)
    graph.add_node("biographer", biographer_node)
    graph.add_node("context_analyst", context_analyst_node)
    graph.add_node("critic", critic_node)
    graph.add_node("philosopher", philosopher_node)
    graph.add_node("editor", editor_node)
    graph.add_node("quality", quality_node)
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
    graph.add_edge("editor", "quality")
    graph.add_conditional_edges("quality", quality_router)
    graph.add_edge("save", END)

    return graph.compile()
