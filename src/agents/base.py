from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from src.utils.llm import LLMClient


@dataclass
class AgentOutput:
    section: str
    content: str
    sources: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "content": self.content,
            "sources": self.sources,
        }


class SpecialistAgent:
    prompt_name: ClassVar[str] = ""
    section_name: ClassVar[str] = ""

    def __init__(
        self,
        llm: LLMClient,
        logger: logging.Logger,
        prompts_dir: Path,
    ) -> None:
        if not self.prompt_name:
            raise ValueError(f"{self.__class__.__name__}.prompt_name must be set")
        if not self.section_name:
            raise ValueError(f"{self.__class__.__name__}.section_name must be set")
        self.llm = llm
        self.logger = logger
        self.prompts_dir = prompts_dir

    def _prompt_path(self) -> Path:
        return self.prompts_dir / f"{self.prompt_name}.md"

    def _load_prompt(self) -> str:
        path = self._prompt_path()
        self.logger.debug("Loading prompt: %s", path)
        return path.read_text(encoding="utf-8")

    def _format_prompt(self, prompt: str, book: str, chapter: str, event: str) -> str:
        # Only replace the three known placeholders so JSON examples in prompts
        # are not misinterpreted as format fields.
        return prompt.replace("{book}", book).replace("{chapter}", chapter).replace("{event}", event)

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        cleaned = self._strip_markdown_fences(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            self.logger.warning("Failed to parse JSON response: %s", exc)
            return {"content": cleaned, "sources": []}

    def _build_output(self, parsed: dict[str, Any]) -> dict[str, Any]:
        content = parsed.get("content") or parsed.get("text") or ""
        sources = parsed.get("sources") or parsed.get("references") or []
        if not isinstance(sources, list):
            sources = [str(sources)]
        sources = [str(s) for s in sources]
        return {
            "section": self.section_name,
            "content": str(content),
            "sources": sources,
        }

    def run(self, book: str, chapter: str, event: str) -> dict[str, Any]:
        self.logger.info(
            "[%s] generating section '%s' for %s/%s/%s",
            self.__class__.__name__,
            self.section_name,
            book,
            chapter,
            event,
        )
        raw_prompt = self._load_prompt()
        system = self._format_prompt(raw_prompt, book, chapter, event)
        user = (
            f"请为《{book}》的「{chapter}」章节中「{event}」这一事件生成内容。\n"
            "请严格按照 prompt 要求的 JSON 格式返回，包含 content 和 sources 字段。"
        )
        response = self.llm.system_user(system, user)
        parsed = self._parse_json_response(response)
        output = self._build_output(parsed)
        self.logger.info(
            "[%s] completed section '%s' (content length=%d, sources=%d)",
            self.__class__.__name__,
            output["section"],
            len(output["content"]),
            len(output["sources"]),
        )
        return output
