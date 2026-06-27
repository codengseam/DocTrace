"""archetype 分桶阶段4 内容工作测试：specialist 按 archetype 路由 prompt + 段名。

测试契约（来自 docs/archetype-design/design.md §九阶段4、§10.5）：
- specialist.run 读取 state["archetype"]，传给 load_prompt
- specialist 段名从 SECTION_TEMPLATES 反查（非硬编码）
- narrative 零回归：不传 archetype 默认 narrative，段名/prompt 与改造前一致
- modern/knowledge 桶加载对应子目录 prompt，不 fallback（无 UserWarning）
- tone_setter/chief_editor 内联 PROMPT 已迁文件，按 archetype 加载
- main.py 真实模式不再回落 exec_archetype

禁区：narrative 桶 prompt 内容不动、quality.py 零改动。
"""
import warnings

import pytest

from src.agents import (
    biographer,
    context_analyst,
    critic,
    editor,
    historian,
    philosopher,
)


# ---------------------------------------------------------------------------
# 测试辅助：拦截 load_prompt 和 create_llm
# ---------------------------------------------------------------------------

class FakeLLM:
    """假 LLM，返回固定内容。"""

    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, prompt):
        class Resp:
            content = "fake content"
        return Resp()


class FakeState(dict):
    """可属性访问的 state dict。"""


def _make_state(book="书", chapter="章", event="事件", archetype="narrative", user_input="史料"):
    return FakeState(
        book=book, chapter=chapter, event=event,
        archetype=archetype, user_input=user_input,
    )


def _capture_load_prompt(monkeypatch, captured):
    """拦截 load_prompt，记录 (name, archetype) 到 captured。"""

    def fake_load_prompt(name, variables=None, archetype="narrative"):
        captured.append((name, archetype))
        return "fake prompt"
    # 拦截每个 specialist 模块里的 load_prompt 引用
    for mod in (historian, biographer, context_analyst, critic, philosopher, editor):
        monkeypatch.setattr(mod, "load_prompt", fake_load_prompt)
    monkeypatch.setattr("src.agents.tone_setter.load_prompt", fake_load_prompt)
    monkeypatch.setattr("src.agents.chief_editor.load_prompt", fake_load_prompt)


def _patch_llms(monkeypatch):
    """拦截所有 agent 的 create_llm。"""
    fake_llm = FakeLLM()
    for mod_name in (
        "src.agents.historian", "src.agents.biographer",
        "src.agents.context_analyst", "src.agents.critic",
        "src.agents.philosopher", "src.agents.editor",
        "src.agents.tone_setter", "src.agents.chief_editor",
    ):
        monkeypatch.setattr(f"{mod_name}.create_llm", lambda *a, **kw: fake_llm)


# ---------------------------------------------------------------------------
# 契约1：specialist 传 archetype 给 load_prompt
# ---------------------------------------------------------------------------

class TestSpecialistPassesArchetype:
    """specialist.run 读取 state['archetype'] 并传给 load_prompt。"""

    @pytest.mark.parametrize("arch", ["narrative", "modern", "knowledge"])
    def test_historian_passes_archetype(self, monkeypatch, arch):
        captured = []
        _capture_load_prompt(monkeypatch, captured)
        _patch_llms(monkeypatch)
        historian.run(_make_state(archetype=arch))
        assert captured[-1] == ("historian", arch), (
            f"historian 应传 archetype={arch}，实际：{captured[-1]}"
        )

    @pytest.mark.parametrize("arch", ["narrative", "modern", "knowledge"])
    def test_critic_passes_archetype(self, monkeypatch, arch):
        captured = []
        _capture_load_prompt(monkeypatch, captured)
        _patch_llms(monkeypatch)
        critic.run(_make_state(archetype=arch))
        assert captured[-1] == ("critic", arch)

    @pytest.mark.parametrize("arch", ["narrative", "modern", "knowledge"])
    def test_context_analyst_passes_archetype(self, monkeypatch, arch):
        captured = []
        _capture_load_prompt(monkeypatch, captured)
        _patch_llms(monkeypatch)
        context_analyst.run(_make_state(archetype=arch))
        assert captured[-1] == ("context_analyst", arch)


# ---------------------------------------------------------------------------
# 契约2：specialist 段名从 SECTION_TEMPLATES 反查
# ---------------------------------------------------------------------------

class TestSpecialistSectionTitle:
    """specialist 返回的段名按 archetype 从 SECTION_TEMPLATES 反查。"""

    def test_historian_narrative_title_is_讲事情(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = historian.run(_make_state(archetype="narrative"))
        assert "讲事情" in result["sections"]

    def test_historian_modern_title_is_入戏(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = historian.run(_make_state(archetype="modern"))
        assert "入戏" in result["sections"]

    def test_historian_knowledge_title_is_原理(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = historian.run(_make_state(archetype="knowledge"))
        assert "原理" in result["sections"]

    def test_context_analyst_modern_title_is_方法论(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = context_analyst.run(_make_state(archetype="modern"))
        assert "方法论" in result["sections"]

    def test_context_analyst_knowledge_title_is_概念(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = context_analyst.run(_make_state(archetype="knowledge"))
        assert "概念" in result["sections"]

    def test_biographer_narrative_title_is_讲人物(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = biographer.run(_make_state(archetype="narrative"))
        assert "讲人物" in result["sections"]

    def test_biographer_knowledge_title_is_实践(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = biographer.run(_make_state(archetype="knowledge"))
        assert "实践" in result["sections"]

    def test_critic_narrative_title_is_讲道理(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = critic.run(_make_state(archetype="narrative"))
        assert "讲道理" in result["sections"]

    def test_critic_modern_title_is_破题(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = critic.run(_make_state(archetype="modern"))
        assert "破题" in result["sections"]

    def test_philosopher_narrative_title_is_问道悟道(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        result = philosopher.run(_make_state(archetype="narrative"))
        assert "问道悟道" in result["sections"]


# ---------------------------------------------------------------------------
# 契约3：narrative 零回归（不传 archetype 默认 narrative）
# ---------------------------------------------------------------------------

class TestSpecialistDefaultArchetype:
    """state 不含 archetype 时默认 narrative，行为与显式 narrative 一致。"""

    def test_historian_default_archetype_is_narrative(self, monkeypatch):
        captured = []
        _capture_load_prompt(monkeypatch, captured)
        _patch_llms(monkeypatch)
        state = FakeState(book="书", chapter="章", event="事件", user_input="史料")
        historian.run(state)
        assert captured[-1] == ("historian", "narrative")

    def test_historian_default_title_is_讲事情(self, monkeypatch):
        _capture_load_prompt(monkeypatch, [])
        _patch_llms(monkeypatch)
        state = FakeState(book="书", chapter="章", event="事件", user_input="史料")
        result = historian.run(state)
        assert "讲事情" in result["sections"]


# ---------------------------------------------------------------------------
# 契约4：modern/knowledge 桶加载对应子目录 prompt（无 fallback 警告）
# ---------------------------------------------------------------------------

class TestSpecialistLoadsBucketPrompt:
    """modern/knowledge specialist 加载 prompts/{archetype}/{name}.md，无 UserWarning。

    用真实 load_prompt（不 mock），但拦截 create_llm 避免真实 API 调用。
    若 fallback 会触发 UserWarning，用 -W error 升级为异常来捕获。
    """

    def test_historian_modern_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            historian.run(_make_state(archetype="modern"))

    def test_historian_knowledge_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            historian.run(_make_state(archetype="knowledge"))

    def test_critic_modern_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            critic.run(_make_state(archetype="modern"))

    def test_context_analyst_knowledge_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            context_analyst.run(_make_state(archetype="knowledge"))

    def test_editor_modern_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        state = _make_state(archetype="modern")
        state["sections"] = {"入戏": "内容"}
        state["sources"] = {"入戏": []}
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            editor.run(state)

    def test_editor_knowledge_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        state = _make_state(archetype="knowledge")
        state["sections"] = {"概念": "内容"}
        state["sources"] = {"概念": []}
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            editor.run(state)


# ---------------------------------------------------------------------------
# 契约5：tone_setter/chief_editor 内联 PROMPT 已迁文件
# ---------------------------------------------------------------------------

class TestToneSetterChiefEditorPromptMoved:
    """tone_setter/chief_editor 不再有内联 PROMPT 常量，改用 load_prompt。"""

    def test_tone_setter_no_inline_prompt_constant(self):
        """tone_setter 模块不再有 PROMPT 常量。"""
        import src.agents.tone_setter as mod
        assert not hasattr(mod, "PROMPT"), (
            "tone_setter 应删除内联 PROMPT 常量，改用 load_prompt 加载"
        )

    def test_chief_editor_no_inline_prompt_constant(self):
        """chief_editor 模块不再有 PROMPT 常量。"""
        import src.agents.chief_editor as mod
        assert not hasattr(mod, "PROMPT"), (
            "chief_editor 应删除内联 PROMPT 常量，改用 load_prompt 加载"
        )

    def test_tone_setter_passes_archetype(self, monkeypatch):
        captured = []
        _capture_load_prompt(monkeypatch, captured)
        _patch_llms(monkeypatch)
        from src.agents import tone_setter
        state = _make_state(archetype="modern")
        state["source_material"] = "史料"
        tone_setter.run(state)
        assert captured[-1] == ("tone_setter", "modern")

    def test_chief_editor_passes_archetype(self, monkeypatch):
        captured = []
        _capture_load_prompt(monkeypatch, captured)
        _patch_llms(monkeypatch)
        from src.agents import chief_editor
        state = _make_state(archetype="knowledge")
        state["final_markdown"] = "成稿"
        chief_editor.run(state)
        assert captured[-1] == ("chief_editor", "knowledge")

    def test_tone_setter_modern_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        from src.agents import tone_setter
        state = _make_state(archetype="modern")
        state["source_material"] = "史料"
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            tone_setter.run(state)

    def test_chief_editor_knowledge_no_fallback_warning(self, monkeypatch):
        _patch_llms(monkeypatch)
        from src.agents import chief_editor
        state = _make_state(archetype="knowledge")
        state["final_markdown"] = "成稿"
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            chief_editor.run(state)


# ---------------------------------------------------------------------------
# 契约6：main.py 真实模式不再回落 exec_archetype
# ---------------------------------------------------------------------------

class TestMainNoExecArchetypeFallback:
    """main.py 真实模式直接用 archetype 调 build_workflow，无 exec_archetype 回落。"""

    def test_main_no_exec_archetype_variable(self):
        """main.py 不再有 exec_archetype 赋值/传参（注释提及可保留作历史说明）。"""
        import re
        import src.main as mod
        import inspect
        source = inspect.getsource(mod)
        # 移除注释和字符串，只检查代码逻辑
        code_only = re.sub(r'#.*$', '', source, flags=re.MULTILINE)
        code_only = re.sub(r'"""[\s\S]*?"""', '', code_only)
        assert "exec_archetype =" not in code_only, (
            "main.py 不应有 exec_archetype 赋值（specialist 已按 archetype 路由）"
        )
        assert "exec_archetype)" not in code_only, (
            "main.py 不应向 build_workflow 传 exec_archetype"
        )
