"""计划评审 Specialist：从架构师/测试/规则三个视角并行评审开发计划。

每个评审角色独立调用 LLM，输出带角色标记的评审意见。
由 src/core/plan_review_workflow.py 编排并行执行。
"""

from typing import Any, Dict

from src.utils.llm import create_llm
from src.utils.prompts import load_prompt


# 三个评审角色及其评审维度
ROLE_DIMENSIONS: Dict[str, str] = {
    "架构师": """1. 可行性：计划是否技术上可行？是否有不可逾越的障碍？
2. 依赖：是否依赖未声明的组件/服务/库？依赖是否合理？
3. 与现有架构一致性：是否符合项目现有架构（LangGraph + Agent 专家团 + Skill 入口 + Python 引擎）？
4. 模块化：改动是否破坏现有模块边界？是否引入循环依赖？
5. 扩展性：方案是否为未来扩展留有余地？还是过度设计？""",
    "测试": """1. 可验证性：计划的每一步是否可被测试验证？哪些步骤无法验证？
2. 测试覆盖：是否需要新增单元测试？现有测试是否需要更新？
3. 边界场景：是否考虑了空输入、超长输入、非法路径、并发等边界？
4. Mock 模式：是否能在 DEEP_READING_MOCK=1 下端到端跑通？
5. 回归风险：改动是否可能破坏现有 20 章讲书笔记的生成流程？""",
    "规则": """1. 是否符合 .trae/rules/dev-workflow.md 的开发协作流程规范？
2. 是否符合 .trae/rules/rules.md 的讲书笔记写作规则（若涉及）？
3. 是否破坏现有体系：deep-reading Skill、rules.md、prompts/、quality.py？
4. Trae Skill 边界：若涉及 Skill，是否声称能调度 sub-agents 或直接调用 MCP tools（这两项 Skill 做不到）？
5. 是否遵循项目目录结构与命名规范（见 README §七、§八）？
6. 是否过度工程化：能用规则文件解决的不写 Skill；能用 Skill 引导的不写 Python。""",
}


def review(state: Dict[str, Any], role: str) -> Dict[str, Any]:
    """通用评审函数，根据角色名调用 LLM 评审计划。

    Args:
        state: 工作流状态，需包含 plan_text 和可选的 project_context。
        role: 评审角色名，必须是 ROLE_DIMENSIONS 中的键。

    Returns:
        {"reviews": {role: 评审意见文本}}
    """
    if role not in ROLE_DIMENSIONS:
        raise ValueError(f"未知评审角色: {role}，可选: {list(ROLE_DIMENSIONS.keys())}")

    plan_text = state.get("plan_text", "")
    project_context = state.get("project_context", "") or _default_project_context()

    prompt = load_prompt(
        "plan_reviewer",
        {
            "role": role,
            "dimensions": ROLE_DIMENSIONS[role],
            "plan_text": plan_text,
            "project_context": project_context,
        },
    )

    llm = create_llm(temperature=0.3)
    content = llm.invoke(prompt).content
    return {"reviews": {role: content}}


def review_architect(state: Dict[str, Any]) -> Dict[str, Any]:
    """架构师视角评审。"""
    return review(state, "架构师")


def review_test(state: Dict[str, Any]) -> Dict[str, Any]:
    """测试视角评审。"""
    return review(state, "测试")


def review_rules(state: Dict[str, Any]) -> Dict[str, Any]:
    """规则视角评审。"""
    return review(state, "规则")


def _default_project_context() -> str:
    """默认项目背景，供评审 Agent 理解项目现状。"""
    return (
        "项目：个人 AI 深度阅读助手（/workspace）。\n"
        "架构：LangGraph 编排 + 7 个 Agent（Orchestrator + 5 Specialist + Editor）+ Quality Check。\n"
        "入口：Trae Skill（.trae/skills/deep-reading/）触发 Python 引擎（src/main.py）。\n"
        "规则：.trae/rules/rules.md（讲书笔记写作规则）、.trae/rules/dev-workflow.md（开发协作流程）。\n"
        "提示词：prompts/ 下 7 份讲书 Agent 提示词 + plan_reviewer.md（计划评审）。\n"
        "质量检查：src/utils/quality.py（AI 套路句/现代术语/升华配额等）。\n"
        "已有产出：20 章资治通鉴讲书笔记，平均分 94.3。\n"
        "Skill 边界：不能调度 sub-agents，不能直接调用 MCP tools；真并行需触发 Python 脚本。"
    )
