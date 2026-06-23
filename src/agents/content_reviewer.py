"""内容质检 Agent：对生成内容做四维度质检并给出评分与修复建议。"""

from src.core.state import AgentState
from src.utils.content_quality import run_content_quality_checks, format_report
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt


def run(state: AgentState) -> dict:
    """运行内容质检。

    输入 state 中需包含：
    - content: 要检查的 Markdown 内容
    - book/chapter/event: 可选，用于定位

    输出：
    - review: 结构化质检报告文本
    - score: 总分
    - passed: 是否合格（>=85）
    - fixes: 修复建议列表
    """
    content = state.get("content", "")
    if not content:
        return {
            "review": "内容为空，无法质检。",
            "score": 0,
            "passed": False,
            "fixes": [],
        }

    # 先跑规则化检测
    report = run_content_quality_checks(content)
    base_report = format_report(report)

    # 再用 LLM 做深度可读性与真实性分析
    llm = create_llm(temperature=0.5)
    prompt = load_prompt(
        "content_reviewer",
        {
            "content": content,
            "base_report": base_report,
            "book": state.get("book", ""),
            "chapter": state.get("chapter", ""),
            "event": state.get("event", ""),
        },
    )
    deep_review = llm.invoke(prompt).content

    return {
        "review": deep_review,
        "score": report.score,
        "passed": report.passed,
        "fixes": report.issues,
        "sections": {"内容质检": deep_review},
    }
