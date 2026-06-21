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


def run(state: AgentState) -> Dict[str, Any]:
    """汇总 Specialist Agent 输出，生成完整 Markdown 讲书笔记。"""
    book = state["book"]
    chapter = state["chapter"]
    event = state["event"]
    sections = state.get("sections", {})
    sources = state.get("sources", {})

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
    )

    llm = create_llm(temperature=0.5)
    response = llm.invoke(prompt)
    content = response.content.strip()

    # 若 LLM 未生成 frontmatter，则自行补齐
    if not _has_frontmatter(content):
        title = f"{book}·{chapter}·{event}"
        # 列出所有贡献内容的 Specialist Agent 名称
        agent_names = list(sections.keys()) if sections else ["Editor Agent"]
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
