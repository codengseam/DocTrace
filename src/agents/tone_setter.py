"""定调节点（ToneSetter）：在 5 个 Specialist 写作之前，为本篇定下灵魂基调。

输出《本篇核心史观与情感基调大纲》，包含五要素：
1. 核心史观（1 句话）：只能从本事件得出的独家洞察
2. 情感基调（1 句话）：冰冷/悲悯/激昂/讽刺（允许逐篇换调）
3. 核心冲突（1-2 句）：人物两难
4. 灵魂锚点（2-3 个）：必须写到位的具体场景/细节
5. 风格锚点：对标当年明月《明朝那些事儿》哪一篇的笔法

输出 JSON：{"tone_outline": "..."}，300-500 字。

注意：当前 prompt 内联在代码中作为 PROMPT 常量。
按项目约定（src/utils/prompts.py 的 load_prompt 读取 prompts/ 目录），
应迁移到 prompts/tone_setter.md，并用 load_prompt("tone_setter", {...}) 加载。
"""

import json
import logging
import re
from typing import Any, Dict

from src.utils.llm import create_llm

logger = logging.getLogger(__name__)


# 定调节点 prompt。
# TODO: 迁移到 prompts/tone_setter.md，通过 load_prompt("tone_setter", {...}) 加载。
PROMPT = """你是 HaloRead 项目的定调节点（ToneSetter）。你的职责是在 5 个 Specialist 写作之前，为本篇定下灵魂基调。

阅读以下史料，输出《本篇核心史观与情感基调大纲》，必须包含五要素：
1. 核心史观：只能从本事件得出的独家洞察（禁止"以史为鉴"等正确废话）
2. 情感基调：冰冷/悲悯/激昂/讽刺（逐篇换调，不强制统一）
3. 核心冲突：本篇人物两难是什么
4. 灵魂锚点：2-3 个必须写到位的具体场景/细节
5. 风格锚点：对标当年明月《明朝那些事儿》哪一篇的笔法

约束：
- 禁止脸谱化标签（奸臣/忠臣/伟人）
- 洞察必须独家，套在同类人物上不成立才算合格
- 输出 JSON：{"tone_outline": "..."}，300-500 字

# 输入

书名：{book}
章节：{chapter}
事件：{event}

原始史料：
{source_material}
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
    """生成本篇核心史观与情感基调大纲。

    Args:
        state: 工作流状态，需包含 book/chapter/event，
            可选 source_material（原始史料）或 user_input（回退为史料）。

    Returns:
        {"tone_outline": "..."}，tone_outline 为含五要素的大纲文本（300-500 字）。
    """
    book = state.get("book", "")
    chapter = state.get("chapter", "")
    event = state.get("event", "")
    # 原始史料：优先用 source_material，回退到 user_input
    source_material = state.get("source_material", "") or state.get("user_input", "")

    # 用 .replace 而非 .format，避免 prompt 中示例 JSON 的花括号被误当作占位符
    # （与 src/utils/prompts.py 的 load_prompt 实现保持一致）
    prompt = PROMPT
    for key, value in {
        "book": book,
        "chapter": chapter,
        "event": event,
        "source_material": source_material,
    }.items():
        prompt = prompt.replace(f"{{{key}}}", str(value))

    llm = create_llm(temperature=0.7)

    try:
        response = llm.invoke(prompt).content
        parsed = _parse_json_response(response)
        tone_outline = parsed.get("tone_outline", "")
    except Exception as exc:
        logger.warning("ToneSetter LLM 调用或 JSON 解析失败: %s", exc)
        tone_outline = ""

    if not tone_outline:
        # 兜底：构造最小大纲，避免下游 Specialist 无基调可依
        tone_outline = (
            f"【核心史观】{event or '本篇'}揭示了非常规的因果与代价。\n"
            "【情感基调】悲悯。\n"
            f"【核心冲突】{event or '本篇'}中人物在理想与现实之间的两难抉择。\n"
            "【灵魂锚点】关键决策时刻、命运转折细节、人物独白或对话。\n"
            "【风格锚点】对标《明朝那些事儿》白描叙事、克制冷峻的笔法。"
        )

    return {"tone_outline": tone_outline}
