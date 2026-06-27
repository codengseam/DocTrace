from typing import Any, Dict, List

from src.core.state import AgentState
from src.utils.llm import create_llm
from src.utils.markdown import build_frontmatter
from src.utils.prompts import load_prompt, load_rules


def _sections_to_markdown(sections: Dict[str, str]) -> str:
    """将 sections 字典序列化为 Markdown 文本，便于嵌入 prompt。"""
    parts: List[str] = []
    for title, content in sections.items():
        parts.append(f"### {title}\n\n{content}")
    return "\n\n".join(parts)


def _sources_to_markdown(sources: Dict[str, List[str]]) -> str:
    """将 sources 字典序列化为 Markdown 文本，便于嵌入 prompt。"""
    parts: List[str] = []
    for title, items in sources.items():
        parts.append(f"### {title}")
        for item in items:
            parts.append(f"- {item}")
        parts.append("")
    return "\n".join(parts).strip()


def _has_frontmatter(text: str) -> bool:
    """检查 Markdown 是否已经包含 frontmatter。"""
    return text.strip().startswith("---")


SECTION_TEMPLATES: Dict[str, Dict[str, str]] = {
    # narrative 桶：原 SECTION_TO_AGENT 映射，古籍零回归（design.md §10.5）
    "narrative": {
        "讲事情": "historian",
        "讲人物": "biographer",
        "讲背景": "context_analyst",
        "讲道理": "critic",
        "问道悟道": "philosopher",
        "结语": "editor",
    },
    # modern 桶：5 段，复用现有 specialist 能力定位（design.md §10.5）
    "modern": {
        "入戏": "historian",
        "破题": "critic",
        "方法论": "context_analyst",
        "避坑": "critic",
        "践行": "editor",
    },
    # knowledge 桶：4 段（design.md §10.5）
    "knowledge": {
        "概念": "context_analyst",
        "原理": "historian",
        "实践": "biographer",
        "速查/自测": "editor",
    },
}


def _section_to_agent_map(archetype: str) -> Dict[str, str]:
    """按 archetype 选段落→agent 映射，非法值兜底 narrative。"""
    return SECTION_TEMPLATES.get(archetype, SECTION_TEMPLATES["narrative"])


def run(state: AgentState) -> Dict[str, Any]:
    """汇总 Specialist Agent 输出，生成完整 Markdown 讲书笔记。"""
    book = state["book"]
    chapter = state["chapter"]
    event = state["event"]
    archetype = state.get("archetype", "narrative")
    sections = state.get("sections", {})
    sources = state.get("sources", {})

    section_to_agent = _section_to_agent_map(archetype)

    # 序列化输入，避免 .format() 对字典直接插值
    sections_md = _sections_to_markdown(sections)
    sources_md = _sources_to_markdown(sources)

    prompt = load_prompt(
        "editor",
        {
            "book": book,
            "chapter": chapter,
            "event": event,
            "sections": sections_md,
            "sources": sources_md,
            "rules": load_rules(),
        },
        archetype=archetype,
    )

    llm = create_llm(temperature=0.5)
    response = llm.invoke(prompt)
    content = response.content.strip()

    # 若 LLM 未生成 frontmatter，则自行补齐
    if not _has_frontmatter(content):
        title = f"{book}·{chapter}·{event}"
        # 将段落标题映射为 Specialist Agent 名称（按 archetype 选模板）
        agent_names = [
            section_to_agent.get(section, section)
            for section in sections.keys()
        ] if sections else ["editor"]
        frontmatter = build_frontmatter(
            title=title,
            book=book,
            chapter=chapter,
            event=event,
            source_agents=agent_names,
        )
        body_title = f"# {title}\n\n"
        content = frontmatter + body_title + content

    return {"final_markdown": content}
