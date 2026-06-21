from unittest.mock import MagicMock, patch

from src.agents.orchestrator import run
from src.core.state import AgentState


def test_orchestrator_uses_existing_fields():
    state: AgentState = {
        "book": "资治通鉴",
        "chapter": "周纪二",
        "event": "商鞅变法",
        "user_input": "",
        "output_path": "",
        "sections": {},
        "sources": {},
        "final_markdown": "",
        "errors": [],
    }
    result = run(state)
    assert result["book"] == "资治通鉴"
    assert result["chapter"] == "周纪二"
    assert result["event"] == "商鞅变法"
    assert "资治通鉴/周纪二_商鞅变法.md" in result["output_path"]


def test_orchestrator_parses_natural_language():
    state: AgentState = {
        "book": "",
        "chapter": "",
        "event": "",
        "user_input": "我刚读完资治通鉴周纪二商鞅变法",
        "output_path": "",
        "sections": {},
        "sources": {},
        "final_markdown": "",
        "errors": [],
    }
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = MagicMock(
        content='{"book": "资治通鉴", "chapter": "周纪二", "event": "商鞅变法", "missing": []}'
    )
    with patch("src.agents.orchestrator.create_llm", return_value=fake_llm):
        result = run(state)
    assert result["book"] == "资治通鉴"
    assert result["chapter"] == "周纪二"
    assert result["event"] == "商鞅变法"


def test_orchestrator_fills_defaults_when_missing():
    state: AgentState = {
        "book": "",
        "chapter": "",
        "event": "",
        "user_input": "商鞅变法",
        "output_path": "",
        "sections": {},
        "sources": {},
        "final_markdown": "",
        "errors": [],
    }
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = MagicMock(
        content='{"book": "", "chapter": "", "event": "商鞅变法", "missing": ["book", "chapter"]}'
    )
    with patch("src.agents.orchestrator.create_llm", return_value=fake_llm):
        result = run(state)
    assert result["event"] == "商鞅变法"
    assert result["chapter"] == "未知章节"
    assert result["book"] == "未知书籍"
