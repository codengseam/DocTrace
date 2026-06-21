from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


class LLMClient:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
    ) -> None:
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.temperature = temperature
        self._llm: BaseChatModel | None = None

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            if ChatOpenAI is None:
                raise RuntimeError("langchain-openai is required for LLMClient")
            kwargs: dict[str, Any] = {
                "model": self.model,
                "temperature": self.temperature,
                "api_key": self.api_key or None,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._llm = ChatOpenAI(**kwargs)
        return self._llm

    def invoke(self, messages: list[BaseMessage]) -> str:
        response = self.llm.invoke(messages)
        return response.content if isinstance(response, AIMessage) else str(response)

    def system_user(self, system: str, user: str) -> str:
        return self.invoke([SystemMessage(content=system), HumanMessage(content=user)])


class MockLLMClient(LLMClient):
    """Deterministic LLM client for tests and dry-runs without API keys."""

    def __init__(self, temperature: float = 0.7) -> None:
        super().__init__(model="mock", base_url="", api_key="mock", temperature=temperature)

    @property
    def llm(self) -> BaseChatModel:  # type: ignore[override]
        raise RuntimeError("MockLLMClient does not use a real LLM")

    def invoke(self, messages: list[BaseMessage]) -> str:
        user = ""
        system = ""
        for m in messages:
            if isinstance(m, SystemMessage):
                system = str(m.content)
            elif isinstance(m, HumanMessage):
                user = str(m.content)
        return self._mock_response(user, system)

    def _mock_response(self, user: str, system: str = "") -> str:
        combined = user + "\n" + system

        # Editor prompt detection
        if "编辑专家" in system or "frontmatter" in system.lower() or "结语" in system:
            return (
                "# 讲事情\n\n秦孝公求贤，商鞅变法。\n\n"
                "# 讲人物\n\n商鞅坚毅刻薄。\n\n"
                "# 讲背景\n\n战国争霸，秦国求变。\n\n"
                "# 讲道理\n\n司马迁评其天资刻薄。\n\n"
                "# 问道悟道\n\n变革需信任与制度并重。\n\n"
                "# 结语\n\n变法强国，亦需人心。\n\n"
                "## 参考来源\n\n- 《资治通鉴·周纪二》\n- 《史记·商君列传》\n"
            )

        # Orchestrator prompt detection
        if "输入解析器" in system or ("提取" in combined and '"book"' in combined):
            return '{"book": "资治通鉴", "chapter": "周纪二", "event": "商鞅变法"}'

        if "讲事情" in combined or "historian" in combined.lower():
            return json.dumps({
                "section": "讲事情",
                "content": "秦孝公发布求贤令，商鞅入秦，以变法强国之策打动孝公，逐步推行废井田、奖军功、重农桑等措施。",
                "sources": ["《资治通鉴·周纪二》"],
            }, ensure_ascii=False)
        if "讲人物" in combined or "biographer" in combined.lower():
            return json.dumps({
                "section": "讲人物",
                "content": "商鞅性格坚毅而刻薄，以徙木立信建立权威，又以严刑峻法推动改革，最终因树敌过多而身死。",
                "sources": ["《史记·商君列传》"],
            }, ensure_ascii=False)
        if "讲背景" in combined or "context_analyst" in combined.lower():
            return json.dumps({
                "section": "讲背景",
                "content": "战国初期，列国争霸，秦国偏居西陲，贵族势力强大，亟需打破世袭、富国强兵。",
                "sources": ["《战国策》"],
            }, ensure_ascii=False)
        if "讲道理" in combined or "critic" in combined.lower():
            return json.dumps({
                "section": "讲道理",
                "content": "司马迁评商鞅：'商君，其天资刻薄人也。' 指出变法虽强秦，却失人心。",
                "sources": ["《史记·商君列传》"],
            }, ensure_ascii=False)
        if "问道悟道" in combined or "philosopher" in combined.lower():
            return json.dumps({
                "section": "问道悟道",
                "content": "变革需要制度与信任的双重杠杆：徙木立信解决信任，严法解决激励；但过度依赖惩罚会透支合法性。",
                "sources": ["《资治通鉴·周纪二》"],
            }, ensure_ascii=False)

        # Default: editor / generic
        return (
            "# 讲事情\n\n秦孝公求贤，商鞅变法。\n\n"
            "# 讲人物\n\n商鞅坚毅刻薄。\n\n"
            "# 讲背景\n\n战国争霸，秦国求变。\n\n"
            "# 讲道理\n\n司马迁评其天资刻薄。\n\n"
            "# 问道悟道\n\n变革需信任与制度并重。\n\n"
            "# 结语\n\n变法强国，亦需人心。\n\n"
            "## 参考来源\n\n- 《资治通鉴·周纪二》\n- 《史记·商君列传》\n"
        )


def build_llm(config: dict[str, Any] | None = None) -> LLMClient:
    cfg = config or {}
    if os.getenv("DEEP_READING_MOCK") == "1" or cfg.get("mock"):
        return MockLLMClient(temperature=cfg.get("temperature", 0.7))
    return LLMClient(
        model=cfg.get("model"),
        base_url=cfg.get("base_url"),
        api_key=cfg.get("api_key"),
        temperature=cfg.get("temperature", 0.7),
    )
