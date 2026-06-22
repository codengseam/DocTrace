"""计划评审工作流：用 LangGraph 并行跑 3 个评审 Agent，汇总为评审报告。

与 src/core/workflow.py（讲书笔记生成工作流）独立，不共享状态。
"""

from typing import Annotated, Dict

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from src.agents import plan_reviewer
from src.utils.logger import get_logger


logger = get_logger("plan_review.workflow")


def _merge_dict(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
    """合并两个字典，新值覆盖旧值。"""
    return {**old, **new}


class PlanReviewState(TypedDict):
    """计划评审工作流状态。"""
    plan_text: str
    project_context: str
    reviews: Annotated[Dict[str, str], _merge_dict]
    final_report: str


def build_review_workflow() -> StateGraph:
    """构建计划评审工作流：3 个评审 Agent 并行 → 汇总。"""
    graph = StateGraph(PlanReviewState)

    def architect_node(state: PlanReviewState) -> dict:
        logger.info("架构师评审中...")
        return plan_reviewer.review_architect(state)

    def test_node(state: PlanReviewState) -> dict:
        logger.info("测试视角评审中...")
        return plan_reviewer.review_test(state)

    def rules_node(state: PlanReviewState) -> dict:
        logger.info("规则视角评审中...")
        return plan_reviewer.review_rules(state)

    def summarize_node(state: PlanReviewState) -> dict:
        """汇总三个评审角色的意见，生成最终报告。"""
        logger.info("汇总评审意见...")
        reviews = state.get("reviews", {})

        # 按固定顺序输出，保证报告可读性
        role_order = ["架构师", "测试", "规则"]
        sections = []
        for role in role_order:
            content = reviews.get(role)
            if content:
                sections.append(content.strip())

        if not sections:
            return {"final_report": "# 计划评审报告\n\n（无评审意见产出，请检查 LLM 配置或 DEEP_READING_MOCK 设置）"}

        report = "# 计划评审报告\n\n"
        report += "\n\n---\n\n".join(sections)
        report += "\n\n---\n\n## 汇总结论\n\n"
        report += "三位评审专家已并行完成评审，请综合上述意见决定是否通过计划或如何修改。"
        return {"final_report": report}

    graph.add_node("architect", architect_node)
    graph.add_node("test", test_node)
    graph.add_node("rules", rules_node)
    graph.add_node("summarize", summarize_node)

    # 三个评审节点并行启动
    graph.add_edge(START, "architect")
    graph.add_edge(START, "test")
    graph.add_edge(START, "rules")

    # 三个评审节点完成后汇入 summarize
    graph.add_edge("architect", "summarize")
    graph.add_edge("test", "summarize")
    graph.add_edge("rules", "summarize")

    graph.add_edge("summarize", END)

    return graph.compile()
