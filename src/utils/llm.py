"""LLM 客户端工厂与 Mock 实现。

提供与 ChatOpenAI 相同接口的 MockLLMClient，用于无 API Key 时的测试与占位生成。
"""

import json
import os
from typing import Any, Optional

from src.utils.config import get_llm_config

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


class _MockResponse:
    """模拟 LLM 响应，提供 .content 属性以兼容 ChatOpenAI 接口。"""

    def __init__(self, content: str) -> None:
        self.content = content


class MockLLMClient:
    """确定性 LLM 客户端，用于测试和占位生成，无需 API Key。

    与 ChatOpenAI 接口兼容：invoke(prompt) 返回带 .content 属性的对象。
    """

    def __init__(self, temperature: float = 0.7) -> None:
        self.temperature = temperature

    def invoke(self, prompt: str, **kwargs: Any) -> _MockResponse:
        return _MockResponse(self._mock_response(prompt))

    def _mock_response(self, prompt: str) -> str:
        combined = prompt

        # Orchestrator: 返回 JSON 解析结果
        if "输入解析器" in combined or ('"book"' in combined and "提取" in combined):
            return '{"book": "资治通鉴", "chapter": "周纪二", "event": "商鞅变法", "missing": []}'

        # Editor: 返回完整 Markdown
        if "编辑专家" in combined or "frontmatter" in combined.lower() or "结语" in combined:
            return (
                "---\n"
                f'title: "资治通鉴·周纪二：商鞅变法"\n'
                f'book: "资治通鉴"\n'
                f'chapter: "周纪二"\n'
                f'event: "商鞅变法"\n'
                f'created_at: "2026-06-21T00:00:00"\n'
                f'source_agents: ["historian", "biographer", "context_analyst", "critic", "philosopher"]\n'
                "---\n\n"
                "# 资治通鉴·周纪二：商鞅变法\n\n"
                "## 讲事情\n\n秦孝公发布求贤令，商鞅入秦，以变法强国之策打动孝公，逐步推行废井田、奖军功、重农桑等措施。事见《资治通鉴·周纪二》。\n\n"
                "## 讲人物\n\n商鞅性格坚毅而刻薄，以徙木立信建立权威，又以严刑峻法推动改革。《史记·商君列传》载其事迹。\n\n"
                "## 讲背景\n\n战国初期，列国争霸，秦国偏居西陲，贵族势力强大，亟需打破世袭、富国强兵。\n\n"
                "## 讲道理\n\n司马迁评商鞅：'商君，其天资刻薄人也。' 指出变法虽强秦，却失人心。见《史记·商君列传》。\n\n"
                "## 问道悟道\n\n变革需要制度与信任的双重杠杆：徙木立信解决信任，严法解决激励；但过度依赖惩罚会透支合法性。\n\n"
                "## 结语\n\n变法强国，亦需人心。\n"
            )

        # Specialist agents: 返回带 section 标记的内容
        if "讲事情" in combined or "historian" in combined.lower():
            return "秦孝公发布求贤令，商鞅入秦，以变法强国之策打动孝公，逐步推行废井田、奖军功、重农桑等措施。\n\n来源：\n- 《资治通鉴·周纪二》"
        if "讲人物" in combined or "biographer" in combined.lower():
            return "商鞅性格坚毅而刻薄，以徙木立信建立权威，又以严刑峻法推动改革。\n\n来源：\n- 《史记·商君列传》"
        if "讲背景" in combined or "context_analyst" in combined.lower():
            return "战国初期，列国争霸，秦国偏居西陲，贵族势力强大，亟需打破世袭、富国强兵。\n\n来源：\n- 《战国策》"
        if "讲道理" in combined or "critic" in combined.lower():
            return "司马迁评商鞅：'商君，其天资刻薄人也。' 指出变法虽强秦，却失人心。\n\n来源：\n- 《史记·商君列传》"
        if "问道悟道" in combined or "philosopher" in combined.lower():
            return "变革需要制度与信任的双重杠杆：徙木立信解决信任，严法解决激励。\n\n来源：\n- 《资治通鉴·周纪二》"

        # 默认
        return "占位内容。"


def _is_mock_mode() -> bool:
    """检查是否启用 Mock 模式。"""
    return os.getenv("DEEP_READING_MOCK") in ("1", "true", "yes")


def create_llm(temperature: float = 0.7, **kwargs: Any):
    """创建 LLM 客户端。

    当 DEEP_READING_MOCK=1 时返回 MockLLMClient，无需 API Key。
    否则返回 ChatOpenAI，需要配置 LLM_API_KEY。
    """
    if _is_mock_mode():
        return MockLLMClient(temperature=temperature)

    if ChatOpenAI is None:
        raise RuntimeError(
            "langchain-openai 未安装。请运行 pip install langchain-openai，"
            "或设置 DEEP_READING_MOCK=1 使用占位模式。"
        )

    cfg = get_llm_config()
    if not cfg.get("api_key"):
        raise RuntimeError(
            "LLM_API_KEY 未配置。请复制 .env.example 为 .env 并填写 API Key，"
            "或设置 DEEP_READING_MOCK=1 使用占位模式。"
        )
    return ChatOpenAI(
        model=cfg.get("model", "qwen-max-latest"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url") or None,
        temperature=temperature,
        **kwargs,
    )
