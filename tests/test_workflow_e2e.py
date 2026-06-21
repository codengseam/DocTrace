"""端到端工作流测试：使用 MockLLMClient 验证完整流程。"""

import os
import tempfile
from pathlib import Path

import pytest

from src.core.workflow import build_workflow


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """启用 Mock 模式，无需 API Key。"""
    monkeypatch.setenv("DEEP_READING_MOCK", "1")
    yield


def test_workflow_end_to_end_with_mock():
    """测试完整工作流：Orchestrator → Specialists → Editor → Quality → Save。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_base = str(Path(tmpdir) / "output")
        app = build_workflow(output_base=output_base)

        initial_state = {
            "book": "资治通鉴",
            "chapter": "周纪二",
            "event": "商鞅变法",
            "user_input": "资治通鉴 周纪二 商鞅变法",
            "output_path": "",
            "sections": {},
            "sources": {},
            "final_markdown": "",
            "errors": [],
        }

        final_state = app.invoke(initial_state)

        # 验证关键字段
        assert final_state["book"] == "资治通鉴"
        assert final_state["chapter"] == "周纪二"
        assert final_state["event"] == "商鞅变法"

        # 验证输出文件已创建
        output_path = Path(final_state["output_path"])
        assert output_path.exists(), f"输出文件不存在: {output_path}"

        # 验证文件内容
        content = output_path.read_text(encoding="utf-8")
        assert len(content) > 0

        # 验证 frontmatter 字段
        for key in ["title", "book", "chapter", "event", "created_at", "source_agents"]:
            assert f"{key}:" in content, f"frontmatter 缺少 {key}"

        # 验证正文结构（5 段 + 结语）
        for section in ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道"]:
            assert section in content, f"缺少章节: {section}"


def test_workflow_natural_language_input():
    """测试自然语言输入解析。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_base = str(Path(tmpdir) / "output")
        app = build_workflow(output_base=output_base)

        initial_state = {
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

        final_state = app.invoke(initial_state)

        # MockLLMClient 会返回固定的解析结果
        assert final_state["book"] == "资治通鉴"
        assert final_state["chapter"] == "周纪二"
        assert final_state["event"] == "商鞅变法"
        assert Path(final_state["output_path"]).exists()
