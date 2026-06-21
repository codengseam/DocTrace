from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.utils.llm import LLMClient
from src.utils.markdown import build_output_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"

_READING_PREFIXES = [
    "我刚读完",
    "我刚看完",
    "我刚读到",
    "我读了",
    "我读了",
    "我看完",
    "我读完",
    "读了",
    "看了",
    "关于",
    "讲讲",
    "说一下",
]


class OrchestratorAgent:
    def __init__(self, llm: LLMClient, logger: logging.Logger) -> None:
        self.llm = llm
        self.logger = logger

    @staticmethod
    def confirm_missing(book: str | None, chapter: str | None, event: str | None) -> list[str]:
        missing: list[str] = []
        if not book or not book.strip():
            missing.append("book")
        if not chapter or not chapter.strip():
            missing.append("chapter")
        if not event or not event.strip():
            missing.append("event")
        return missing

    def parse_input(self, user_input: str) -> dict[str, Any]:
        self.logger.info("[OrchestratorAgent] parsing input: %s", user_input)
        book, chapter, event = self._extract_with_heuristics(user_input)

        if not book or not chapter or not event:
            book, chapter, event = self._extract_with_llm(user_input, book, chapter, event)

        book = (book or "").strip()
        chapter = (chapter or "").strip()
        event = (event or "").strip()

        output_path = build_output_path(
            _DEFAULT_OUTPUT_DIR,
            book,
            chapter,
            event,
        )
        self.logger.info(
            "[OrchestratorAgent] parsed: book=%s chapter=%s event=%s output=%s",
            book,
            chapter,
            event,
            output_path,
        )
        return {
            "book": book,
            "chapter": chapter,
            "event": event,
            "output_path": str(output_path),
        }

    def _extract_with_heuristics(
        self,
        user_input: str,
    ) -> tuple[str | None, str | None, str | None]:
        text = user_input.strip()
        book: str | None = None
        chapter: str | None = None
        event: str | None = None

        # 1. 显式标签：书名/章节/事件
        label_match = re.search(
            r"(?:书名|书)[：:\s]*([^\n，。,;]+?)(?:[，。,;]|\s+)(?:章节|章)[：:\s]*([^\n，。,;]+?)(?:[，。,;]|\s+)(?:事件|事)[：:\s]*([^\n，。,;]+)",
            text,
        )
        if label_match:
            book, chapter, event = label_match.group(1), label_match.group(2), label_match.group(3)
            return book.strip(), chapter.strip(), event.strip()

        # 2. 去掉常见前缀
        for prefix in _READING_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        # 3. 按空格切分
        parts = text.split()
        if len(parts) >= 3:
            book, chapter, event = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            book, chapter = parts[0], parts[1]
        elif len(parts) == 1 and text:
            # 单段无空格，尝试简单切出最后的动词/事件词
            # 例如 "资治通鉴周纪二商鞅变法" -> 难以准确切分，留给 LLM 处理
            book = text

        return (
            book.strip() if book else None,
            chapter.strip() if chapter else None,
            event.strip() if event else None,
        )

    def _extract_with_llm(
        self,
        user_input: str,
        book: str | None,
        chapter: str | None,
        event: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        system = (
            "你是阅读助手的输入解析器。请从用户输入中提取书名、章节、事件。\n"
            "如果某项缺失，请返回空字符串。\n"
            "只返回 JSON，格式：{\"book\": \"...\", \"chapter\": \"...\", \"event\": \"...\"}"
        )
        hints = []
        if book:
            hints.append(f"已识别书名可能是：{book}")
        if chapter:
            hints.append(f"已识别章节可能是：{chapter}")
        if event:
            hints.append(f"已识别事件可能是：{event}")
        hint_text = "\n".join(hints) if hints else "无先验信息。"
        user = f"用户输入：{user_input}\n\n{hint_text}\n\n请提取并返回 JSON。"

        self.logger.debug("[OrchestratorAgent] falling back to LLM extraction")
        try:
            response = self.llm.system_user(system, user)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            parsed = json.loads(cleaned.strip())
            return (
                parsed.get("book") or book,
                parsed.get("chapter") or chapter,
                parsed.get("event") or event,
            )
        except Exception as exc:
            self.logger.warning("LLM extraction failed: %s", exc)
            return book, chapter, event
