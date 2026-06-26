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

注意：当前 prompt 内联在代码中作为 PROMPT 常量。
按项目约定（src/utils/prompts.py 的 load_prompt 读取 prompts/ 目录），
应迁移到 prompts/chief_editor.md，并用 load_prompt("chief_editor", {...}) 加载。
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from src.utils.llm import create_llm

logger = logging.getLogger(__name__)


# 总编终审 prompt。
# TODO: 迁移到 prompts/chief_editor.md，通过 load_prompt("chief_editor", {...}) 加载。
PROMPT = """你是 HaloRead 项目的总编（Chief Editor）。合规质检已通过，你只做灵魂终审。

回答三个问题：
1. 活人测试：核心人物读者读完能用一句话说出他的"两难"吗？不能（仍是标签）→ fail
2. 洞察独家性：核心洞察套在同类人物（如刚直悲剧：比干/杨椒山/杨涟）上成不成立？套得上（正确废话）→ fail
3. 底色敬畏感：面对生死悲剧语气是否克制？有戏谑/爽文化 → fail

输出 JSON：
{
  "verdict": "GO" | "REWORK",
  "soul_questions": {
    "live_human_test": {"pass": true/false, "reason": "..."},
    "insight_exclusivity": {"pass": true/false, "reason": "..."},
    "tone_reverence": {"pass": true/false, "reason": "..."}
  },
  "rework_direction": "若 REWORK 给具体方向，GO 则 null"
}

试点期阈值：任一问 fail 即 REWORK。但试点首 5 篇只打标记不强制打回（verdict 仍输出，主流程不据此阻断）。

# 待审成稿

```markdown
{final_markdown}
```
"""


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

    # 用 .replace 而非 .format，避免 prompt 中示例 JSON 的花括号被误当作占位符
    # （与 src/utils/prompts.py 的 load_prompt 实现保持一致）
    prompt = PROMPT.replace("{final_markdown}", final_markdown)

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
