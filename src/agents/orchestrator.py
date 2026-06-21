import json
import re
from typing import Any, Dict

from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.prompts import load_prompt


def _parse_json_response(response: str) -> Dict[str, Any]:
    """从 LLM 响应中解析 JSON，支持裸 JSON 和 Markdown 代码块。"""
    response = response.strip()
    if response.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            response = match.group(1).strip()
    return json.loads(response)


def run(state: AgentState, interactive: bool = False) -> Dict[str, Any]:
    """解析用户输入，确定书名、章节、事件和输出路径。

    如果 state 中已有 book/chapter/event，则直接使用；否则调用 LLM 解析。
    非交互模式下，缺失字段会被填充默认值。
    """
    book = state.get("book", "")
    chapter = state.get("chapter", "")
    event = state.get("event", "")
    user_input = state.get("user_input", "")

    # 如果已有完整信息，直接计算输出路径
    if book and chapter and event:
        return {
            "book": book,
            "chapter": chapter,
            "event": event,
            "output_path": f"output/{book}/{chapter}_{event}.md",
        }

    # 调用 LLM 解析用户输入
    prompt = load_prompt(
        "orchestrator",
        {
            "user_input": user_input,
            "book": book,
            "chapter": chapter,
            "event": event,
        },
    )
    llm = create_llm(temperature=0.2)
    response = llm.invoke(prompt).content
    parsed = _parse_json_response(response)

    book = parsed.get("book", book) or book
    chapter = parsed.get("chapter", chapter) or chapter
    event = parsed.get("event", event) or event
    missing = parsed.get("missing", [])

    # 非交互模式下，为缺失字段填充默认值
    if not interactive:
        if "book" in missing or not book:
            book = book or user_input or "未知书籍"
        if "chapter" in missing or not chapter:
            chapter = chapter or "未知章节"
        if "event" in missing or not event:
            event = event or user_input or book or "未知事件"

    output_path = f"output/{book}/{chapter}_{event}.md"

    return {
        "book": book,
        "chapter": chapter,
        "event": event,
        "output_path": output_path,
    }
