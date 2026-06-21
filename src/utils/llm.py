from typing import Any, Dict

from langchain_openai import ChatOpenAI

from src.utils.config import get_llm_config


def create_llm(temperature: float = 0.7, **kwargs: Any) -> ChatOpenAI:
    cfg = get_llm_config()
    if not cfg.get("api_key"):
        raise RuntimeError(
            "LLM_API_KEY 未配置。请复制 .env.example 为 .env 并填写 API Key。"
        )
    return ChatOpenAI(
        model=cfg.get("model", "qwen-max-latest"),
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url") or None,
        temperature=temperature,
        **kwargs,
    )
