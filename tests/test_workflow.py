import os
import tempfile
from pathlib import Path

import pytest

# 依赖 langgraph；无 langgraph 时优雅 skip，避免收集期 ImportError 中断 pytest（BUG-031 同源修复）。
pytest.importorskip("langgraph")

import src.core.workflow as workflow_module  # noqa: E402
from src.core.workflow import build_workflow  # noqa: E402


def test_workflow_compiles():
    app = build_workflow()
    assert app is not None


def test_workflow_quality_gate_blocks_save(monkeypatch):
    """质量检查不通过时，不应保存文件。"""

    class FailingReport:
        passed = False
        issues = ["强制失败：结构不完整"]

    def fake_quality_checks(*args, **kwargs):
        return FailingReport()

    monkeypatch.setattr(workflow_module, "run_quality_checks", fake_quality_checks)

    with tempfile.TemporaryDirectory() as tmpdir:
        app = build_workflow(output_base=tmpdir)
        initial_state = {
            "book": "资治通鉴",
            "chapter": "周纪二",
            "event": "商鞅变法",
            "user_input": "",
            "output_path": "",
            "sections": {},
            "sources": {},
            "final_markdown": "占位内容，不应被保存。",
            "errors": [],
        }

        final_state = app.invoke(initial_state)

        # 质量检查应发现问题
        assert final_state["errors"], "预期质量检查应报告问题"
        # save 节点未执行，tmpdir 下不应出现生成的笔记文件
        generated_files = list(Path(tmpdir).rglob("*.md"))
        assert not generated_files, (
            f"质量检查未通过不应保存文件，但生成: {generated_files}"
        )
