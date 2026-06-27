import tempfile
from pathlib import Path

import pytest

# 依赖 langgraph；无 langgraph 时优雅 skip，避免收集期 ImportError 中断 pytest（BUG-031 同源修复）。
pytest.importorskip("langgraph")

from src.core.workflow import build_workflow  # noqa: E402


def test_workflow_uses_custom_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = build_workflow(output_base=tmpdir)
        assert app is not None
