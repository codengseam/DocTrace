from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.utils.llm import LLMClient
from src.utils.markdown import build_frontmatter


class EditorAgent:
    def __init__(
        self,
        llm: LLMClient,
        logger: logging.Logger,
        prompts_dir: Path,
    ) -> None:
        self.llm = llm
        self.logger = logger
        self.prompts_dir = prompts_dir

    def _load_prompt(self) -> str:
        path = self.prompts_dir / "editor.md"
        self.logger.debug("Loading editor prompt: %s", path)
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _format_sections(sections: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for section in sections:
            name = section.get("section", "")
            content = section.get("content", "")
            sources = section.get("sources", [])
            sources_text = "\n".join(f"- {s}" for s in sources) or "- （无）"
            parts.append(
                f"## {name}\n\n{content}\n\n### 引用\n{sources_text}\n"
            )
        return "\n---\n".join(parts)

    def run(self, book: str, chapter: str, event: str, sections: list[dict[str, Any]]) -> str:
        self.logger.info(
            "[EditorAgent] assembling final markdown for %s/%s/%s",
            book,
            chapter,
            event,
        )
        raw_prompt = self._load_prompt()
        sections_text = self._format_sections(sections)
        system = raw_prompt.format(
            book=book,
            chapter=chapter,
            event=event,
            sections=sections_text,
        )
        user = (
            f"请将以下关于《{book}》「{chapter}」中「{event}」的五段 Specialist 输出，"
            "润色、拼接成一篇完整的 Markdown 讲书笔记。\n\n"
            f"{sections_text}\n\n"
            "要求：\n"
            "1. 以 YAML frontmatter 开头，包含 title、book、chapter、event、created_at、source_agents。\n"
            "2. 正文严格按顺序包含：讲事情、讲人物、讲背景、讲道理、问道悟道。\n"
            "3. 文末加一段结语，用一句话总结全文最核心的本质。\n"
            "4. 统一语气、补齐引用、去除 AI 味，直接输出 Markdown 全文。"
        )
        response = self.llm.system_user(system, user)
        markdown = self._ensure_frontmatter(response, book, chapter, event, sections)
        self.logger.info(
            "[EditorAgent] final markdown generated (length=%d)",
            len(markdown),
        )
        return markdown

    def _ensure_frontmatter(
        self,
        content: str,
        book: str,
        chapter: str,
        event: str,
        sections: list[dict[str, Any]],
    ) -> str:
        content = content.strip()
        if content.startswith("---"):
            return content
        source_agents = [s.get("section", "") for s in sections]
        title = f"《{book}·{chapter}》{event}"
        frontmatter = build_frontmatter(
            title=title,
            book=book,
            chapter=chapter,
            event=event,
            source_agents=source_agents,
        )
        return frontmatter + "\n" + content
