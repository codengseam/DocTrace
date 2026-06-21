from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.cli.agents.biographer import BiographerAgent
from src.cli.agents.context_analyst import ContextAnalystAgent
from src.cli.agents.critic import CriticAgent
from src.cli.agents.editor import EditorAgent
from src.cli.agents.historian import HistorianAgent
from src.cli.agents.orchestrator import OrchestratorAgent
from src.cli.agents.philosopher import PhilosopherAgent
from src.cli.utils.llm import MockLLMClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "src/cli/prompts"

SECTIONS = ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道"]


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def logger():
    return logging.getLogger("test.agents")


SPECIALIST_CASES = [
    (HistorianAgent, "讲事情"),
    (BiographerAgent, "讲人物"),
    (ContextAnalystAgent, "讲背景"),
    (CriticAgent, "讲道理"),
    (PhilosopherAgent, "问道悟道"),
]


@pytest.mark.parametrize("agent_cls,section", SPECIALIST_CASES)
def test_specialist_agent_returns_expected_shape(agent_cls, section, mock_llm, logger):
    agent = agent_cls(mock_llm, logger, PROMPTS_DIR)
    result = agent.run("资治通鉴", "周纪二", "商鞅变法")

    assert isinstance(result, dict)
    assert result["section"] == section
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0
    assert isinstance(result["sources"], list)


def test_editor_agent_returns_markdown_with_all_sections(mock_llm, logger):
    sections = [
        {"section": name, "content": f"{name} 的测试内容。", "sources": ["《资治通鉴》"]}
        for name in SECTIONS
    ]
    editor = EditorAgent(mock_llm, logger, PROMPTS_DIR)
    markdown = editor.run("资治通鉴", "周纪二", "商鞅变法", sections)

    assert isinstance(markdown, str)
    assert markdown.startswith("---")
    for name in SECTIONS:
        assert name in markdown
    assert "结语" in markdown


def test_orchestrator_parses_natural_language(mock_llm, logger):
    orchestrator = OrchestratorAgent(mock_llm, logger)
    result = orchestrator.parse_input("我刚读完资治通鉴周纪二商鞅变法")

    assert result["book"] == "资治通鉴"
    assert result["chapter"] == "周纪二"
    assert result["event"] == "商鞅变法"
    assert result["output_path"].endswith("output/资治通鉴/周纪二_商鞅变法.md")


def test_orchestrator_parses_explicit_parameters(mock_llm, logger):
    orchestrator = OrchestratorAgent(mock_llm, logger)
    result = orchestrator.parse_input("资治通鉴 周纪二 商鞅变法")

    assert result["book"] == "资治通鉴"
    assert result["chapter"] == "周纪二"
    assert result["event"] == "商鞅变法"
    assert result["output_path"].endswith("output/资治通鉴/周纪二_商鞅变法.md")
