"""总编终审节点（Chief Editor）：合规质检通过后，做"灵魂三问"终审。

不查错别字/引用密度（那是 content_reviewer 的活），只做灵魂终审：
1. 活人测试：核心人物读者读完能用一句话说出他的"两难"吗？不能（仍是标签）→ fail
2. 洞察独家性：核心洞察套在同类人物上是否成立？套得上（正确废话）→ fail
3. 底色敬畏感：面对生死悲剧语气是否克制？有戏谑/爽文化 → fail

输出 JSON：
{
  "verdict": "GO" | "REWORK",
  "soul_questions": {
    "live_human_test": {"pass": bool, "reason": "..."},
    "insight_exclusivity": {"pass": bool, "reason": "..."},
    "tone_reverence": {"pass": bool, "reason": "..."}
  },
  "rework_direction": "..." | null
}

试点期阈值：任一问 fail 即 REWORK。
试点首 5 篇只打标记不强制打回（verdict 仍输出，主流程不据此阻断）。

阶段4：prompt 已迁文件，按 archetype 路由（design.md §9.2/§9.3）。
- narrative：prompts/chief_editor.md（活人测试/洞察独家性/底色敬畏感）
- modern：prompts/modern/chief_editor.md（实用价值测试/方法独家性/落地可行性）
- knowledge：prompts/knowledge/chief_editor.md（准确性测试/深度独家性/可操作性）
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from src.utils.llm import create_llm
from src.utils.prompts import load_prompt

logger = logging.getLogger(__name__)


# 阶段4：prompt 已迁移到 prompts/chief_editor.md（narrative）/
# prompts/modern/chief_editor.md / prompts/knowledge/chief_editor.md。
# load_prompt 按 archetype 路由，未迁移的桶 fallback 到 narrative + 警告。


def _parse_json_response(response: str) -> Dict[str, Any]:
    """从 LLM 响应中解析 JSON，支持裸 JSON 和 Markdown 代码块。"""
    response = response.strip()
    if response.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            response = match.group(1).strip()
    return json.loads(response)


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """对合规质检通过的成稿做灵魂三问终审。

    Args:
        state: 工作流状态，需包含 final_markdown（合规质检通过的成稿）。

    Returns:
        {
            "verdict": "GO" | "REWORK",
            "soul_questions": {
                "live_human_test": {"pass": bool, "reason": str},
                "insight_exclusivity": {"pass": bool, "reason": str},
                "tone_reverence": {"pass": bool, "reason": str},
            },
            "rework_direction": str | None,
        }
    """
    final_markdown = state.get("final_markdown", "")
    archetype = state.get("archetype", "narrative")

    # 阶段4：按 archetype 加载 prompt（load_prompt 内部做 variables 替换）
    prompt = load_prompt(
        "chief_editor",
        {"final_markdown": final_markdown},
        archetype=archetype,
    )

    llm = create_llm(temperature=0.3)

    try:
        response = llm.invoke(prompt).content
        parsed = _parse_json_response(response)
        verdict = parsed.get("verdict", "GO")
        soul_questions = parsed.get("soul_questions", {})
        rework_direction: Optional[str] = parsed.get("rework_direction")
    except Exception as exc:
        logger.warning("ChiefEditor LLM 调用或 JSON 解析失败: %s", exc)
        # 兜底：不阻断主流程，默认放行
        verdict = "GO"
        soul_questions = {}
        rework_direction = None

    # 规范化 verdict，防止 LLM 输出非法值
    if verdict not in ("GO", "REWORK"):
        verdict = "GO"

    return {
        "verdict": verdict,
        "soul_questions": soul_questions,
        "rework_direction": rework_direction,
    }
