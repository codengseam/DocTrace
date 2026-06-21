from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.cli.core.workflow import DeepReadingWorkflow
from src.cli.utils.config import Config
from src.cli.utils.llm import MockLLMClient

SECTIONS = ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道"]
REQUIRED_FRONTMATTER = ["title", "book", "chapter", "event", "created_at", "source_agents"]


@pytest.fixture
def workflow(tmp_path):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"

    config_path = tmp_path / "test_config.yaml"
    config_data = {
        "llm": {"mock": True, "temperature": 0.7},
        "paths": {
            "output": str(output_dir),
            "logs": str(logs_dir),
            "prompts": "src/cli/prompts",
            "templates": "templates",
        },
        "rules": {
            "sections": SECTIONS,
            "required_frontmatter": REQUIRED_FRONTMATTER,
        },
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    cfg = Config(config_path)
    return DeepReadingWorkflow(config=cfg, llm=MockLLMClient())


def test_deep_reading_workflow_end_to_end(workflow):
    final_state = workflow.run("资治通鉴 周纪二 商鞅变法")

    required_keys = ["book", "chapter", "event", "output_path", "final_markdown", "quality_report"]
    for key in required_keys:
        assert key in final_state

    assert final_state["book"] == "资治通鉴"
    assert final_state["chapter"] == "周纪二"
    assert final_state["event"] == "商鞅变法"

    output_path = Path(final_state["output_path"])
    assert output_path.exists()

    content = output_path.read_text(encoding="utf-8")
    assert content.startswith("---")

    for key in REQUIRED_FRONTMATTER:
        assert f"{key}:" in content

    for section in SECTIONS:
        assert section in content

    assert "结语" in content

    report = final_state["quality_report"]
    assert isinstance(report, dict)
    assert "passed" in report
    assert "issues" in report
