"""内容质检工作流：用 LangGraph 并行跑 3 个质检 Agent，汇总为质检报告。

与 src/core/workflow.py（讲书笔记生成工作流）独立，不共享状态。
"""

from typing import Annotated, Dict

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from src.agents import content_reviewer_sub
from src.utils.logger import get_logger


logger = get_logger("content_review.workflow")


def _merge_dict(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
    """合并两个字典，新值覆盖旧值。"""
    return {**old, **new}


class ContentReviewState(TypedDict):
    """内容质检工作流状态。"""

    content: str
    book: str
    chapter: str
    event: str
    reviews: Annotated[Dict[str, str], _merge_dict]
    final_report: str


def build_content_review_workflow() -> StateGraph:
    """构建内容质检工作流：3 个质检 Agent 并行 → 汇总。"""
    graph = StateGraph(ContentReviewState)

    def truth_node(state: ContentReviewState) -> dict:
        logger.info("史实核验视角质检中...")
        return content_reviewer_sub.review_truth(state)

    def readability_node(state: ContentReviewState) -> dict:
        logger.info("可读性视角质检中...")
        return content_reviewer_sub.review_readability(state)

    def citation_node(state: ContentReviewState) -> dict:
        logger.info("引用克制视角质检中...")
        return content_reviewer_sub.review_citation(state)

    def summarize_node(state: ContentReviewState) -> dict:
        """汇总三个视角的意见，生成最终报告。"""
        logger.info("汇总质检意见...")
        reviews = state.get("reviews", {})

        role_order = ["史实核验", "可读性", "引用克制"]
        sections = []
        for role in role_order:
            content = reviews.get(role)
            if content:
                sections.append(content.strip())

        if not sections:
            return {
                "final_report": "# 内容质检报告\n\n（无质检意见产出，请检查 LLM 配置或 DEEP_READING_MOCK 设置）"
            }

        book = state.get("book", "")
        chapter = state.get("chapter", "")
        event = state.get("event", "")
        header = f"# 内容质检报告：{book}·{chapter}·{event}" if book else "# 内容质检报告"

        report = f"{header}\n\n"
        report += "\n\n---\n\n".join(sections)
        report += "\n\n---\n\n## 汇总结论\n\n"
        report += "三位质检专家已并行完成质检，请按优先级修复问题后重新评分。"
        return {"final_report": report}

    graph.add_node("truth", truth_node)
    graph.add_node("readability", readability_node)
    graph.add_node("citation", citation_node)
    graph.add_node("summarize", summarize_node)

    graph.add_edge(START, "truth")
    graph.add_edge(START, "readability")
    graph.add_edge(START, "citation")

    graph.add_edge("truth", "summarize")
    graph.add_edge("readability", "summarize")
    graph.add_edge("citation", "summarize")

    graph.add_edge("summarize", END)

    return graph.compile()
