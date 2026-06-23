"""内容质检 Specialist：史实核验 / 可读性 / 引用克制 三个并行视角。"""

from typing import Any, Dict

from src.utils.llm import create_llm
from src.utils.prompts import load_prompt


ROLE_DIMENSIONS: Dict[str, str] = {
    "史实核验": """你负责内容真实性质检（满分 40）。检查：
1. 人名、时间、地点、因果是否与正史一致。
2. 关键年份是否给出（改革/为相/死亡/战役年份等）。
3. 典故出处是否准确，不无据张冠李戴。
4. 名家点评是否真实有出处，是否伪造或把论整体的话套在具体事件上。
5. 跨文化映照是否用了演义虚构、张冠李戴、因果错置。
6. 史料层累、存疑说法是否已说明。
输出分数（0-40）、问题清单、修复建议。""",
    "可读性": """你负责可读性质检（满分 30）。检查：
1. 是否有场景、对话、戏剧性转折，还是流水账。
2. 单章内是否有重复的古文、金句、事实。
3. 章节间是否重复讲述同一事件。
4. 是否有 AI 套路句式（我们可以看到/这告诉我们/综上所述/不是 X 而是 Y 滥用等）。
5. 是否有现代学科术语硬套历史（博弈论/底层逻辑/坐标系等）。
6. 段尾升华是否过多（应 ≤2 处，只在问道悟道/结语）。
输出分数（0-30）、问题清单、修复建议。""",
    "引用克制": """你负责引用克制质检（满分 15）。检查：
1. 是否有「（见讲故事）」「（详见下章）」「（见上文）」等内联跳转。
2. 行内「——《XX·XX》」引用是否过多（建议每千字 ≤3 处）。
3. 是否几乎每段都挂同一出处。
4. 文末是否有「参考来源」，且来源完整。
5. 删除行内引用后是否丢失来源。
输出分数（0-15）、问题清单、修复建议。""",
}


def review(state: Dict[str, Any], role: str) -> Dict[str, Any]:
    """通用质检函数，根据角色调用 LLM 评审内容。"""
    if role not in ROLE_DIMENSIONS:
        raise ValueError(f"未知质检角色: {role}，可选: {list(ROLE_DIMENSIONS.keys())}")

    content = state.get("content", "")
    book = state.get("book", "")
    chapter = state.get("chapter", "")
    event = state.get("event", "")

    prompt = load_prompt(
        "content_reviewer_sub",
        {
            "role": role,
            "dimensions": ROLE_DIMENSIONS[role],
            "content": content,
            "book": book,
            "chapter": chapter,
            "event": event,
        },
    )

    llm = create_llm(temperature=0.3)
    content_text = llm.invoke(prompt).content
    return {"reviews": {role: content_text}}


def review_truth(state: Dict[str, Any]) -> Dict[str, Any]:
    """史实核验视角。"""
    return review(state, "史实核验")


def review_readability(state: Dict[str, Any]) -> Dict[str, Any]:
    """可读性视角。"""
    return review(state, "可读性")


def review_citation(state: Dict[str, Any]) -> Dict[str, Any]:
    """引用克制视角。"""
    return review(state, "引用克制")
