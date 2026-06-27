"""plan-review skill 文档契约测试。

验证 .trae/skills/plan-review/SKILL.md 与 dispatching-parallel-agents/SKILL.md
满足 BUG-031 修复后的路径定义：主路径（会话内 Task 工具并行）+ 路径 B（langgraph 可选增强），
环境缺失时不硬阻塞，错误处理章节不再含误导性条目。
"""

from pathlib import Path
import os

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / ".trae" / "skills"
PLAN_REVIEW_MD = SKILL_DIR / "plan-review" / "SKILL.md"
DISPATCH_MD = SKILL_DIR / "dispatching-parallel-agents" / "SKILL.md"


@pytest.fixture(scope="module")
def plan_review_text() -> str:
    """读取 plan-review SKILL.md 全文。"""
    assert PLAN_REVIEW_MD.exists(), f"缺失 skill 文件: {PLAN_REVIEW_MD}"
    return PLAN_REVIEW_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dispatch_text() -> str:
    """读取 dispatching-parallel-agents SKILL.md 全文。"""
    assert DISPATCH_MD.exists(), f"缺失 skill 文件: {DISPATCH_MD}"
    return DISPATCH_MD.read_text(encoding="utf-8")


class TestPlanReviewSkillContract:
    """plan-review skill 文档契约。"""

    def test_version_bumped_to_v2(self, plan_review_text: str):
        """版本升至 2.0.0，标识主路径重构。"""
        assert "version: 2.0.0" in plan_review_text

    def test_main_path_uses_task_tool(self, plan_review_text: str):
        """主路径明确使用 Trae Task 工具启动 subagent，而非 langgraph。"""
        assert "Task" in plan_review_text
        assert "subagent_type" in plan_review_text
        assert "general_purpose_task" in plan_review_text

    def test_main_path_emphasizes_parallel_in_one_response(self, plan_review_text: str):
        """主路径强调同一响应内发出多个 Task 调用实现并行。"""
        assert "同一响应" in plan_review_text or "同一条响应" in plan_review_text
        assert "并行" in plan_review_text

    def test_path_b_is_optional_enhancement(self, plan_review_text: str):
        """路径 B（langgraph）降级为可选增强，而非唯一路径。"""
        assert "可选增强" in plan_review_text
        assert "路径 B" in plan_review_text

    def test_no_hard_block_on_missing_env(self, plan_review_text: str):
        """环境缺失时不硬阻塞——文档必须明确写出降级策略。"""
        assert "不硬阻塞" in plan_review_text
        assert "主路径" in plan_review_text

    def test_error_table_no_misleading_script_missing_entry(self, plan_review_text: str):
        """错误处理章节不再含 scripts/review_plan.py 不存在 的误导条目。

        文件实际存在（git 历史 commit bfd342c 添加，从未删除），
        旧版 SKILL.md 把它当作不存在分支处理是误导。
        """
        # 不应出现 "scripts/review_plan.py 不存在" 这样的整句误导条目
        assert "scripts/review_plan.py 不存在" not in plan_review_text

    def test_references_dispatching_parallel_agents_skill(self, plan_review_text: str):
        """plan-review 引用 dispatching-parallel-agents skill 作为并行调度底座。"""
        assert "dispatching-parallel-agents" in plan_review_text

    def test_three_roles_defined(self, plan_review_text: str):
        """三角色（架构师/测试/规则）及其维度齐备。"""
        for role in ("架构师", "测试", "规则"):
            assert role in plan_review_text
        # 关键维度词
        assert "可行性" in plan_review_text
        assert "回归风险" in plan_review_text
        assert "过度工程化" in plan_review_text

    def test_report_structure_defined(self, plan_review_text: str):
        """报告结构含三视角 + 汇总结论。"""
        assert "汇总结论" in plan_review_text
        assert "架构师评审" in plan_review_text
        assert "测试评审" in plan_review_text
        assert "规则评审" in plan_review_text

    def test_bug030_referenced_in_version_history(self, plan_review_text: str):
        """版本历史引用 BUG-031。"""
        assert "BUG-031" in plan_review_text


class TestDispatchingParallelAgentsSkillContract:
    """dispatching-parallel-agents skill 文档契约。"""

    def test_skill_file_exists(self, dispatch_text: str):
        """技能文件存在。"""
        assert dispatch_text

    def test_provenance_from_superpowers(self, dispatch_text: str):
        """标注原生自 obra/superpowers（MIT）。"""
        assert "obra/superpowers" in dispatch_text
        assert "MIT" in dispatch_text

    def test_trae_task_tool_adapted(self, dispatch_text: str):
        """适配 Trae Task 工具（subagent_type 参数）。"""
        assert "Task" in dispatch_text
        assert "subagent_type" in dispatch_text
        assert "search" in dispatch_text
        assert "general_purpose_task" in dispatch_text

    def test_parallel_rule_clear(self, dispatch_text: str):
        """并行规则清晰：同一响应多 Task = 并行。"""
        assert "同一个响应" in dispatch_text or "同一条消息" in dispatch_text
        assert "并行" in dispatch_text
        assert "串行" in dispatch_text

    def test_self_contained_query_rule(self, dispatch_text: str):
        """强调 subagent 指令必须自包含（subagent 看不到主会话历史）。"""
        assert "自包含" in dispatch_text
        assert "看不到主会话" in dispatch_text or "看不到" in dispatch_text

    def test_conflict_check_after_return(self, dispatch_text: str):
        """返回后必须检查冲突 + 跑全测。"""
        assert "冲突" in dispatch_text
        assert "全量测试" in dispatch_text or "全测" in dispatch_text

    def test_when_not_to_use_section(self, dispatch_text: str):
        """含「何时不该用」章节，防止滥用。"""
        assert "不该用" in dispatch_text or "何时不" in dispatch_text

    def test_relation_to_plan_review(self, dispatch_text: str):
        """声明与 plan-review skill 的关系。"""
        assert "plan-review" in dispatch_text


class TestReviewPlanScriptBehavior:
    """review_plan.py 路径 B 降级行为测试（BUG-031 R4）。

    验证 langgraph 缺失时：退出码 1 + stderr 含友好主路径提示 + 不含裸 traceback。
    用 subprocess 真跑，非源码 grep。
    """

    def test_langgraph_missing_returns_1_with_friendly_hint(self, tmp_path: Path):
        """langgraph 未安装时 review_plan.py 退出码 1，stderr 含主路径提示，无裸 traceback。

        用 DEEP_READING_MOCK=1 绕过 LLM_API_KEY 检查，让脚本走到 langgraph 延迟导入分支。
        无 langgraph 时触发 ImportError → 友好提示（而非裸 traceback）。
        """
        import subprocess
        import sys

        # 探测当前环境是否有 langgraph；有则该测试无法触发 ImportError 分支，skip
        try:
            import langgraph  # noqa: F401
            pytest.skip("当前环境已安装 langgraph，无法触发 ImportError 降级分支")
        except ImportError:
            pass  # 期望状态：无 langgraph

        plan_file = tmp_path / "plan.md"
        plan_file.write_text("## 测试计划\n- 步骤1", encoding="utf-8")

        env = os.environ.copy()
        # Mock 模式绕过 LLM_API_KEY 检查，让脚本走到 langgraph 延迟导入
        env["DEEP_READING_MOCK"] = "1"
        env.pop("LLM_API_KEY", None)

        result = subprocess.run(
            [sys.executable, "scripts/review_plan.py", "--plan", str(plan_file)],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            env=env,
        )

        # langgraph 缺失应退出 1
        assert result.returncode != 0, "langgraph 缺失时应非零退出"

        # stderr 必须含友好主路径提示
        assert "路径 B" in result.stderr, f"stderr 应含路径 B 提示，实际: {result.stderr}"
        assert "Task 工具" in result.stderr or "主路径" in result.stderr, (
            f"stderr 应含主路径/Task 工具提示，实际: {result.stderr}"
        )
        # 不应含裸 traceback（友好提示替代了 traceback）
        assert "Traceback (most recent call last)" not in result.stderr, (
            f"stderr 不应含裸 traceback，实际: {result.stderr}"
        )
