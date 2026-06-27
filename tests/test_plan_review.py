"""计划评审工作流测试：验证多 Agent 并行评审流程。

路径 B（langgraph）的单元测试。无 langgraph 环境下整体 skip，
避免收集期 ImportError 中断 pytest（BUG-031 回归保护）。
主路径（会话内 Task 工具并行）的文档契约测试见 tests/test_plan_review_skill.py。
"""

import os
import tempfile
from pathlib import Path

import pytest

# 路径 B 依赖 langgraph；无 langgraph 时优雅 skip，而非收集期 ImportError 中断。
pytest.importorskip("langgraph")

from src.core.plan_review_workflow import build_review_workflow  # noqa: E402


def test_review_workflow_compiles():
    """工作流能成功构建。"""
    app = build_review_workflow()
    assert app is not None


def test_review_workflow_runs_with_mock():
    """Mock 模式下完整评审流程能跑通，三角色并行产出意见。"""
    os.environ["DEEP_READING_MOCK"] = "1"
    try:
        app = build_review_workflow()
        initial_state = {
            "plan_text": "## 计划：测试计划\n- 步骤1: 做A\n- 步骤2: 做B",
            "project_context": "",
            "reviews": {},
            "final_report": "",
        }
        final_state = app.invoke(initial_state)

        # 三个角色都应产出意见
        reviews = final_state["reviews"]
        assert "架构师" in reviews
        assert "测试" in reviews
        assert "规则" in reviews

        # 每个角色的意见应非空
        for role, content in reviews.items():
            assert content.strip(), f"{role}评审意见为空"

        # 最终报告应包含三个角色和汇总结论
        report = final_state["final_report"]
        assert "架构师评审" in report
        assert "测试评审" in report
        assert "规则评审" in report
        assert "汇总结论" in report
    finally:
        os.environ.pop("DEEP_READING_MOCK", None)


def test_review_workflow_report_order():
    """报告按固定顺序输出：架构师 → 测试 → 规则。"""
    os.environ["DEEP_READING_MOCK"] = "1"
    try:
        app = build_review_workflow()
        initial_state = {
            "plan_text": "测试计划",
            "project_context": "",
            "reviews": {},
            "final_report": "",
        }
        final_state = app.invoke(initial_state)
        report = final_state["final_report"]

        # 架构师应在测试之前，测试应在规则之前
        assert report.index("架构师评审") < report.index("测试评审")
        assert report.index("测试评审") < report.index("规则评审")
    finally:
        os.environ.pop("DEEP_READING_MOCK", None)


def test_review_plan_script_cli():
    """CLI 调用 scripts/review_plan.py 在 Mock 模式下返回 0。"""
    import subprocess
    import sys

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write("## 计划：CLI 测试\n- 步骤1: 做A")
        plan_path = f.name

    try:
        env = os.environ.copy()
        env["DEEP_READING_MOCK"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/review_plan.py",
                "--plan",
                plan_path,
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "计划评审报告" in result.stdout
        assert "架构师评审" in result.stdout
    finally:
        Path(plan_path).unlink(missing_ok=True)


def test_review_plan_script_missing_file():
    """计划文件不存在时返回非零。"""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "scripts/review_plan.py",
            "--plan",
            "/nonexistent/plan.md",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "不存在" in result.stderr or "Error" in result.stderr
