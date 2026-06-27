"""archetype 分桶阶段3测试：结构模板分桶 + soul injection 按桶路由。

测试契约（来自 docs/archetype-design/design.md §10、§10.6、阶段3 计划）：
- build_workflow(output_base, archetype="narrative") 接受 archetype 参数
- get_required_sections(archetype) 纯函数：narrative 6 段 / modern 5 段 / knowledge 4 段
- config.yaml 新增 section_templates，narrative 与 legacy quality_check.required_sections 一致
- editor.SECTION_TEMPLATES 三桶映射，SECTION_TO_AGENT 删除
- main._generate_stub(archetype) 按桶生成对应段数
- workflow.quality_node 按 archetype 取 required_sections
- soul injection 按桶路由：narrative 启用 / modern·knowledge 跳过走原 else 分支

禁区：src/utils/quality.py 内部零改动。
langgraph 未安装时，模块顶部注入最小 mock 让真实 workflow.py 可被导入测试。
"""
import subprocess
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 避开 langgraph：模块顶部注入最小 mock，让真实 src.core.workflow 可导入
# ---------------------------------------------------------------------------

def _ensure_langgraph_available():
    """langgraph 未安装时注入最小 mock，让真实 workflow.py 能被 import。

    Green 阶段写真实的 workflow.py 后，测试直接测真实实现（mock 只补 langgraph 缺失）。
    """
    if "langgraph" in sys.modules:
        return  # 真实 langgraph 已装，无需 mock

    class _FakeStateGraph:
        """最小 StateGraph mock，记录节点/边注册，支持 compile 返回可调用对象。"""
        def __init__(self, state_type):
            self._nodes = {}
            self._edges = []
            self._conditional = {}

        def add_node(self, name, fn):
            self._nodes[name] = fn

        def add_edge(self, src, dst):
            self._edges.append((src, dst))

        def add_conditional_edges(self, name, router_fn, path_map=None):
            self._conditional[name] = router_fn

        def compile(self):
            return self  # 返回 self 充当编译后的图

    langgraph_mod = types.ModuleType("langgraph")
    graph_mod = types.ModuleType("langgraph.graph")
    graph_mod.StateGraph = _FakeStateGraph
    graph_mod.START = "__start__"
    graph_mod.END = "__end__"
    langgraph_mod.graph = graph_mod
    # 自标识为 fake，供其他测试（如 test_workflow_e2e）检测并 skip，
    # 避免本模块的全局 mock 污染让 importorskip 失效后用 fake 跑真实编排测试。
    langgraph_mod._FAKE = True
    sys.modules["langgraph"] = langgraph_mod
    sys.modules["langgraph.graph"] = graph_mod


_ensure_langgraph_available()

from src.core.workflow import build_workflow, get_required_sections  # noqa: E402
from src.utils.config import load_config  # noqa: E402


# ---------------------------------------------------------------------------
# 契约1：build_workflow 的 archetype 参数
# ---------------------------------------------------------------------------

class TestBuildWorkflowArchetypeParam:
    """build_workflow(output_base, archetype) 接受 archetype 参数。"""

    def test_default_archetype_is_narrative(self):
        """默认 archetype='narrative' 编译不报错。"""
        graph = build_workflow()
        assert graph is not None

    def test_modern_compiles(self):
        """archetype='modern' 编译不报错。"""
        graph = build_workflow(archetype="modern")
        assert graph is not None

    def test_knowledge_compiles(self):
        """archetype='knowledge' 编译不报错。"""
        graph = build_workflow(archetype="knowledge")
        assert graph is not None

    @pytest.mark.parametrize("bad", ["", "fiction", "narrative-modern", "不存在的桶", None])
    def test_invalid_archetype_raises(self, bad):
        """非法 archetype（含 fiction 未落地、空串、None）抛 ValueError。"""
        with pytest.raises(ValueError):
            build_workflow(archetype=bad)


# ---------------------------------------------------------------------------
# 契约2：get_required_sections 纯函数
# ---------------------------------------------------------------------------

class TestGetRequiredSections:
    """get_required_sections(archetype) 返回对应桶的段名列表。"""

    def test_function_exists(self):
        """函数存在且可调用。"""
        assert callable(get_required_sections)

    def test_narrative_six_sections(self):
        """narrative 桶 6 段（design.md §10.1）。"""
        sections = get_required_sections("narrative")
        assert sections == ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]

    def test_modern_five_sections(self):
        """modern 桶 5 段（design.md §10.2）。"""
        sections = get_required_sections("modern")
        assert sections == ["入戏", "破题", "方法论", "避坑", "践行"]

    def test_knowledge_four_sections(self):
        """knowledge 桶 4 段（design.md §10.3）。"""
        sections = get_required_sections("knowledge")
        assert sections == ["概念", "原理", "实践", "速查/自测"]

    def test_invalid_archetype_falls_back_to_narrative(self):
        """非法 archetype 兜底返回 narrative 6 段（不抛异常，健壮性）。"""
        sections = get_required_sections("不存在")
        assert sections == ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]


# ---------------------------------------------------------------------------
# 契约3：config.yaml 的 section_templates
# ---------------------------------------------------------------------------

class TestConfigSectionTemplates:
    """config.yaml 新增 section_templates 字段，三桶段名齐全。"""

    @pytest.fixture
    def cfg(self):
        return load_config(PROJECT_ROOT / "config.yaml")

    def test_has_section_templates(self, cfg):
        """config 含 section_templates 顶层字段。"""
        assert "section_templates" in cfg, "config.yaml 缺少 section_templates"

    def test_three_archetypes_present(self, cfg):
        """section_templates 含 narrative/modern/knowledge 三桶。"""
        templates = cfg["section_templates"]
        for arch in ("narrative", "modern", "knowledge"):
            assert arch in templates, f"section_templates 缺少 {arch}"

    def test_narrative_matches_legacy(self, cfg):
        """narrative 桶段名与 legacy quality_check.required_sections 完全一致。

        护栏：保证古籍专栏零回归。
        """
        legacy = cfg["quality_check"]["required_sections"]
        narrative = cfg["section_templates"]["narrative"]
        assert narrative == legacy, (
            f"narrative 段名与 legacy 不一致，会破坏古籍专栏\n"
            f"  legacy:    {legacy}\n  narrative: {narrative}"
        )

    def test_modern_five(self, cfg):
        assert cfg["section_templates"]["modern"] == [
            "入戏", "破题", "方法论", "避坑", "践行"
        ]

    def test_knowledge_four(self, cfg):
        assert cfg["section_templates"]["knowledge"] == [
            "概念", "原理", "实践", "速查/自测"
        ]


# ---------------------------------------------------------------------------
# 契约4：editor.SECTION_TEMPLATES
# ---------------------------------------------------------------------------

class TestEditorSectionTemplates:
    """editor.py 用 SECTION_TEMPLATES 替代 SECTION_TO_AGENT。"""

    def test_section_templates_exists(self):
        """SECTION_TEMPLATES 字典存在。"""
        from src.agents import editor
        assert hasattr(editor, "SECTION_TEMPLATES"), "editor 缺少 SECTION_TEMPLATES"

    def test_section_to_agent_removed(self):
        """旧的 SECTION_TO_AGENT 已删除（避免双真相源漂移）。"""
        from src.agents import editor
        assert not hasattr(editor, "SECTION_TO_AGENT"), (
            "SECTION_TO_AGENT 仍存在，应迁移为 SECTION_TEMPLATES"
        )

    def test_three_archetypes_mapped(self):
        """SECTION_TEMPLATES 含三桶映射。"""
        from src.agents import editor
        for arch in ("narrative", "modern", "knowledge"):
            assert arch in editor.SECTION_TEMPLATES, (
                f"SECTION_TEMPLATES 缺少 {arch} 桶"
            )

    def test_narrative_mapping_preserved(self):
        """narrative 桶映射与原 SECTION_TO_AGENT 完全一致（古籍零回归）。"""
        from src.agents import editor
        expected = {
            "讲事情": "historian",
            "讲人物": "biographer",
            "讲背景": "context_analyst",
            "讲道理": "critic",
            "问道悟道": "philosopher",
            "结语": "editor",
        }
        assert editor.SECTION_TEMPLATES["narrative"] == expected

    def test_all_agents_in_valid_set(self):
        """所有映射的 agent 名都在现有 5 个 specialist + editor 集合内（不新增 agent）。"""
        from src.agents import editor
        valid_agents = {
            "historian", "biographer", "context_analyst",
            "critic", "philosopher", "editor",
        }
        for arch, mapping in editor.SECTION_TEMPLATES.items():
            for section, agent_name in mapping.items():
                assert agent_name in valid_agents, (
                    f"{arch}/{section} 映射到未知 agent: {agent_name}"
                )

    @pytest.mark.parametrize("bad", ["", "fiction", "不存在", None])
    def test_section_to_agent_map_invalid_falls_back_to_narrative(self, bad):
        """P1-3：_section_to_agent_map 对非法 archetype 兜底返回 narrative 映射。"""
        from src.agents import editor
        result = editor._section_to_agent_map(bad)
        assert result == editor.SECTION_TEMPLATES["narrative"], (
            f"非法 archetype {bad!r} 应兜底 narrative 映射"
        )

    def test_section_templates_keys_match_config(self):
        """P2-3：editor.SECTION_TEMPLATES 每桶 key 集合 == config.section_templates 对应桶列表。

        防止 config 加了段但 editor 映射没同步（双真相源漂移）。
        """
        from src.agents import editor
        cfg = load_config(PROJECT_ROOT / "config.yaml")
        templates = cfg["section_templates"]
        for arch in ("narrative", "modern", "knowledge"):
            editor_keys = set(editor.SECTION_TEMPLATES[arch].keys())
            config_keys = set(templates[arch])
            assert editor_keys == config_keys, (
                f"{arch} 桶 editor 与 config 段名不一致："
                f"editor={editor_keys} config={config_keys}"
            )


# ---------------------------------------------------------------------------
# 契约5：main._generate_stub 按 archetype 生成对应段数
# ---------------------------------------------------------------------------

class TestStubModeArchetype:
    """stub 模式按 archetype 生成对应段数的占位内容。"""

    def _run_stub(self, tmp_path, archetype):
        """跑 stub 生成并返回文件内容。"""
        result = subprocess.run(
            [
                sys.executable, "-m", "src.main",
                "--book", "测试书",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--archetype", archetype,
                "--stub",
                "--output-dir", str(tmp_path),
            ],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"stub 失败: {result.stderr}"
        md_files = list(tmp_path.rglob("*.md"))
        assert md_files, f"未生成 md 文件: {result.stdout}"
        return md_files[0].read_text(encoding="utf-8")

    def test_modern_has_five_sections(self, tmp_path):
        """modern 桶 stub 含 5 段标题。"""
        content = self._run_stub(tmp_path, "modern")
        for section in ["入戏", "破题", "方法论", "避坑", "践行"]:
            assert f"## {section}" in content, f"modern stub 缺少段: {section}"

    def test_knowledge_has_four_sections(self, tmp_path):
        """knowledge 桶 stub 含 4 段标题。"""
        content = self._run_stub(tmp_path, "knowledge")
        for section in ["概念", "原理", "实践", "速查/自测"]:
            assert f"## {section}" in content, f"knowledge stub 缺少段: {section}"

    def test_narrative_has_six_sections(self, tmp_path):
        """narrative 桶 stub 仍含原 6 段（零回归）。"""
        content = self._run_stub(tmp_path, "narrative")
        for section in ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]:
            assert f"## {section}" in content, f"narrative stub 缺少段: {section}"

    def test_fiction_falls_back_to_narrative(self, tmp_path):
        """BUG-029 回归：--archetype fiction 未落地，CLI 层回落 narrative 不崩溃。

        prompts._VALID_ARCHETYPES 含 fiction（预留），workflow._VALID_ARCHETYPES
        不含（未落地），跨层不一致。main.py 在 build_workflow 前拦截 fiction→narrative。
        """
        result = subprocess.run(
            [
                sys.executable, "-m", "src.main",
                "--book", "测试书",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--archetype", "fiction",
                "--stub",
                "--output-dir", str(tmp_path),
            ],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, (
            f"--archetype fiction 应回落 narrative 不崩溃，但退出码非 0: {result.stderr}"
        )
        md_files = list(tmp_path.rglob("*.md"))
        assert md_files, f"未生成 md 文件: {result.stdout}"
        content = md_files[0].read_text(encoding="utf-8")
        # 回落 narrative 应含 6 段
        for section in ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]:
            assert f"## {section}" in content, (
                f"fiction 回落 narrative 后应含 6 段，缺: {section}"
            )
        # 应有 stderr 警告
        assert "回落" in result.stderr or "narrative" in result.stderr, (
            f"fiction 回落应有 stderr 警告，实际: {result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# 契约6：quality_node 按 archetype 路由 required_sections
# ---------------------------------------------------------------------------

class TestQualityNodeArchetypeRouting:
    """quality_node 闭包按 archetype 取对应 required_sections 传给 run_quality_checks。

    用 FakeStateGraph 捕获 quality 节点函数，直接调用验证（不真跑图）。
    """

    def _capture_and_call_quality_node(self, archetype, monkeypatch):
        """build_workflow 时捕获 quality 节点函数，mock run_quality_checks 后直接调用。"""
        captured = {"quality_fn": None, "expected_sections": None}

        def fake_run_quality_checks(content, expected_sections=None, required_frontmatter=None):
            captured["expected_sections"] = expected_sections

            class FakeReport:
                passed = True
                issues = []
            return FakeReport()

        # mock 真实模块的 run_quality_checks（已被 workflow 顶部 import）
        monkeypatch.setattr(
            "src.core.workflow.run_quality_checks", fake_run_quality_checks
        )

        # patch workflow 模块已绑定的 StateGraph（顶部 from langgraph.graph import）
        class CapturingGraph:
            def __init__(self, state_type):
                pass

            def add_node(self, name, fn):
                if name == "quality":
                    captured["quality_fn"] = fn

            def add_edge(self, src, dst):
                pass

            def add_conditional_edges(self, name, fn, path_map=None):
                pass

            def compile(self):
                return None

        monkeypatch.setattr("src.core.workflow.StateGraph", CapturingGraph)

        build_workflow(archetype=archetype)
        assert captured["quality_fn"] is not None, "未捕获到 quality 节点函数"

        # 直接调用 quality_node 闭包。
        # 注意：quality_node 通过闭包捕获 required_sections，不读 state["archetype"]，
        # 因此 state 里不放 archetype（避免给人"state 驱动路由"的错觉）。
        state = {"final_markdown": "---\ntitle: x\n---\n# x\n"}
        captured["quality_fn"](state)
        return captured

    def test_modern_routes_five_sections(self, monkeypatch):
        captured = self._capture_and_call_quality_node("modern", monkeypatch)
        assert captured["expected_sections"] == [
            "入戏", "破题", "方法论", "避坑", "践行"
        ]

    def test_knowledge_routes_four_sections(self, monkeypatch):
        captured = self._capture_and_call_quality_node("knowledge", monkeypatch)
        assert captured["expected_sections"] == [
            "概念", "原理", "实践", "速查/自测"
        ]

    def test_narrative_routes_six_sections(self, monkeypatch):
        captured = self._capture_and_call_quality_node("narrative", monkeypatch)
        assert captured["expected_sections"] == [
            "讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"
        ]


# ---------------------------------------------------------------------------
# 契约7：soul injection 按桶路由（design.md §10.6）
# ---------------------------------------------------------------------------

class TestSoulInjectionArchetypeRouting:
    """三桶均启用 tone_setter/chief_editor（阶段4 边链裁剪后 modern/knowledge 也启用）。

    用 CapturingGraph 验证节点注册与边，不真跑图。
    """

    def _capture_graph_topology(self, archetype, monkeypatch):
        """build_workflow 时捕获所有 add_node/add_edge 调用。"""
        calls = {"nodes": [], "edges": []}

        # 隔离环境差异：强制 soul injection 三个开关为 True，
        # 让路由逻辑只由 archetype 决定（三桶均启用，区别在 specialist 节点裁剪）。
        # 生产环境 agent 可用性是独立问题，不在此契约测试范围。
        monkeypatch.setattr("src.core.workflow.SOUL_INJECTION_ENABLED", True)
        monkeypatch.setattr("src.core.workflow._TONE_SETTER_AVAILABLE", True)
        monkeypatch.setattr("src.core.workflow._CHIEF_EDITOR_AVAILABLE", True)

        class TopologyGraph:
            def __init__(self, state_type):
                pass

            def add_node(self, name, fn):
                calls["nodes"].append(name)

            def add_edge(self, src, dst):
                calls["edges"].append((src, dst))

            def add_conditional_edges(self, name, fn, path_map=None):
                pass

            def compile(self):
                return None

        # patch workflow 模块已绑定的 StateGraph
        monkeypatch.setattr("src.core.workflow.StateGraph", TopologyGraph)
        build_workflow(archetype=archetype)
        return calls

    def test_narrative_registers_soul_nodes(self, monkeypatch):
        """narrative 桶注册 tone_setter 和 chief_editor 节点。"""
        calls = self._capture_graph_topology("narrative", monkeypatch)
        assert "tone_setter" in calls["nodes"], "narrative 应注册 tone_setter"
        assert "chief_editor" in calls["nodes"], "narrative 应注册 chief_editor"

    def test_modern_registers_soul_nodes(self, monkeypatch):
        """阶段4 边链裁剪：modern 桶也注册 tone_setter/chief_editor（prompt 已建）。"""
        calls = self._capture_graph_topology("modern", monkeypatch)
        assert "tone_setter" in calls["nodes"], "modern 应注册 tone_setter（阶段4 已开启）"
        assert "chief_editor" in calls["nodes"], "modern 应注册 chief_editor（阶段4 已开启）"

    def test_knowledge_registers_soul_nodes(self, monkeypatch):
        """阶段4 边链裁剪：knowledge 桶也注册 tone_setter/chief_editor。"""
        calls = self._capture_graph_topology("knowledge", monkeypatch)
        assert "tone_setter" in calls["nodes"], "knowledge 应注册 tone_setter"
        assert "chief_editor" in calls["nodes"], "knowledge 应注册 chief_editor"

    def test_modern_specialists_trimmed(self, monkeypatch):
        """modern 桶只注册需要的 4 specialist（historian/critic/context_analyst），
        不注册 biographer/philosopher（design.md §10.5 modern 映射无此二 agent）。
        """
        calls = self._capture_graph_topology("modern", monkeypatch)
        nodes = calls["nodes"]
        # modern 桶需要的 specialist（editor 是汇总节点不算 specialist）
        for spec in ("historian", "critic", "context_analyst"):
            assert spec in nodes, f"modern 应注册 {spec}"
        # modern 桶不需要的 specialist
        assert "biographer" not in nodes, "modern 不应注册 biographer（无对应段）"
        assert "philosopher" not in nodes, "modern 不应注册 philosopher（无对应段）"

    def test_knowledge_specialists_trimmed(self, monkeypatch):
        """knowledge 桶只注册需要的 4 specialist（context_analyst/historian/biographer），
        不注册 critic/philosopher。
        """
        calls = self._capture_graph_topology("knowledge", monkeypatch)
        nodes = calls["nodes"]
        for spec in ("context_analyst", "historian", "biographer"):
            assert spec in nodes, f"knowledge 应注册 {spec}"
        assert "critic" not in nodes, "knowledge 不应注册 critic（无对应段）"
        assert "philosopher" not in nodes, "knowledge 不应注册 philosopher（无对应段）"

    def test_narrative_keeps_all_5_specialists(self, monkeypatch):
        """narrative 桶保留全部 5 specialist（零回归）。"""
        calls = self._capture_graph_topology("narrative", monkeypatch)
        nodes = calls["nodes"]
        for spec in ("historian", "biographer", "context_analyst", "critic", "philosopher"):
            assert spec in nodes, f"narrative 应注册 {spec}（零回归）"

    def test_modern_edge_chain_complete(self, monkeypatch):
        """modern 桶完整边链：orchestrator→tone_setter→3 Specialist→editor→quality
        →chief_editor→save→END（阶段4 边链裁剪 + soul injection 开启）。

        modern specialist：historian(入戏)/critic(破题)/context_analyst(方法论)。
        避坑/践行由 editor 补写（prompts/modern/editor.md §避坑段补写指令）。
        """
        calls = self._capture_graph_topology("modern", monkeypatch)
        edges = calls["edges"]
        modern_specialists = ("historian", "critic", "context_analyst")
        # orchestrator → tone_setter（soul injection 开启）
        assert ("orchestrator", "tone_setter") in edges, (
            "modern 应有 orchestrator→tone_setter 边（soul injection 已开启）"
        )
        # tone_setter → 3 Specialist 并行扇出
        for spec in modern_specialists:
            assert ("tone_setter", spec) in edges, (
                f"modern 应有 tone_setter→{spec} 边"
            )
        # 3 Specialist → editor 扇入
        for spec in modern_specialists:
            assert (spec, "editor") in edges, (
                f"modern 应有 {spec}→editor 扇入边"
            )
        # editor → quality → chief_editor → save → END
        assert ("editor", "quality") in edges, "modern 应有 editor→quality 边"
        assert ("chief_editor", "save") in edges, "modern 应有 chief_editor→save 边"
        assert ("save", "__end__") in edges, "modern 应有 save→END 边"
        # 反断言：modern 不应有裁剪掉的 specialist 边
        assert ("tone_setter", "biographer") not in edges, "modern 不应有 tone_setter→biographer 边"
        assert ("tone_setter", "philosopher") not in edges, "modern 不应有 tone_setter→philosopher 边"
        assert ("biographer", "editor") not in edges, "modern 不应有 biographer→editor 边"
        # 反断言：modern 不应有 orchestrator→Specialist 直连（应经 tone_setter）
        for spec in modern_specialists:
            assert ("orchestrator", spec) not in edges, (
                f"modern 不应有 orchestrator→{spec} 直连（应经 tone_setter）"
            )

    def test_knowledge_edge_chain_complete(self, monkeypatch):
        """knowledge 桶完整边链：orchestrator→tone_setter→3 Specialist→editor→quality
        →chief_editor→save→END。

        knowledge specialist：context_analyst(概念)/historian(原理)/biographer(实践)。
        速查/自测由 editor 补写。
        """
        calls = self._capture_graph_topology("knowledge", monkeypatch)
        edges = calls["edges"]
        knowledge_specialists = ("context_analyst", "historian", "biographer")
        assert ("orchestrator", "tone_setter") in edges, "knowledge 应有 orchestrator→tone_setter 边"
        for spec in knowledge_specialists:
            assert ("tone_setter", spec) in edges, f"knowledge 应有 tone_setter→{spec} 边"
            assert (spec, "editor") in edges, f"knowledge 应有 {spec}→editor 边"
        assert ("editor", "quality") in edges
        assert ("chief_editor", "save") in edges
        assert ("save", "__end__") in edges
        # 反断言：裁剪掉的 specialist
        assert ("tone_setter", "critic") not in edges, "knowledge 不应有 tone_setter→critic 边"
        assert ("tone_setter", "philosopher") not in edges, "knowledge 不应有 tone_setter→philosopher 边"

    def test_narrative_edge_chain_complete(self, monkeypatch):
        """narrative 桶完整边链：orchestrator→tone_setter→5 Specialist→editor→quality
        →chief_editor→save→END（design.md §10.6，零回归）。

        不只查节点存在，逐条断言关键边，防止"注册了节点却忘了连边"。
        """
        calls = self._capture_graph_topology("narrative", monkeypatch)
        edges = calls["edges"]
        # START → orchestrator（图入口，P2-6 补）
        assert ("__start__", "orchestrator") in edges, "应有 START→orchestrator 入口边"
        # orchestrator → tone_setter（串行注入，非直连 Specialist）
        assert ("orchestrator", "tone_setter") in edges, (
            "narrative 应有 orchestrator→tone_setter 边"
        )
        # tone_setter → 5 Specialist 并行扇出
        for spec in ("historian", "biographer", "context_analyst", "critic", "philosopher"):
            assert ("tone_setter", spec) in edges, (
                f"narrative 应有 tone_setter→{spec} 边"
            )
        # 5 Specialist → editor 扇入
        for spec in ("historian", "biographer", "context_analyst", "critic", "philosopher"):
            assert (spec, "editor") in edges, (
                f"narrative 应有 {spec}→editor 边"
            )
        # editor → quality → chief_editor → save → END
        assert ("editor", "quality") in edges, "narrative 应有 editor→quality 边"
        assert ("chief_editor", "save") in edges, (
            "narrative 应有 chief_editor→save 边（终审后保存）"
        )
        assert ("save", "__end__") in edges, "narrative 应有 save→END 边"
        # 关键反断言：narrative 不应有 orchestrator→Specialist 直连（那是 else 分支）
        for spec in ("historian", "biographer", "context_analyst", "critic", "philosopher"):
            assert ("orchestrator", spec) not in edges, (
                f"narrative 不应有 orchestrator→{spec} 直连（应经 tone_setter）"
            )


# ---------------------------------------------------------------------------
# 契约8：quality_router 条件边路由（P1-2：原 add_conditional_edges 未验证是假象）
# ---------------------------------------------------------------------------

class TestQualityRouterConditionalEdge:
    """quality_router 的 router_fn 真正决定 quality 通过后去哪。

    原测试 TopologyGraph.add_conditional_edges 是 pass，"不断链"是假象。
    现捕获 router_fn 直接调用：errors 空 → save/chief_editor；errors 非空 → END。
    """

    def _capture_router_fn(self, archetype, monkeypatch):
        """build_workflow 时捕获 quality 节点注册的 router_fn。"""
        # 强制 soul injection 三开关为 True，让路由只由 archetype 决定
        monkeypatch.setattr("src.core.workflow.SOUL_INJECTION_ENABLED", True)
        monkeypatch.setattr("src.core.workflow._TONE_SETTER_AVAILABLE", True)
        monkeypatch.setattr("src.core.workflow._CHIEF_EDITOR_AVAILABLE", True)

        captured = {"router_fn": None}

        class RouterGraph:
            def __init__(self, state_type):
                pass

            def add_node(self, name, fn):
                pass

            def add_edge(self, src, dst):
                pass

            def add_conditional_edges(self, name, fn, path_map=None):
                # quality 节点的条件边路由函数
                if name == "quality":
                    captured["router_fn"] = fn

            def compile(self):
                return None

        monkeypatch.setattr("src.core.workflow.StateGraph", RouterGraph)
        build_workflow(archetype=archetype)
        assert captured["router_fn"] is not None, "未捕获到 quality 的 router_fn"
        return captured["router_fn"]

    def test_modern_pass_goes_to_chief_editor(self, monkeypatch):
        """modern 桶 quality 通过（errors 空）→ router_fn 返回 'chief_editor'。

        阶段4 边链裁剪后 modern 启用 soul injection，quality 通过走终审再 save
        （design.md §10.6，与 narrative 一致）。
        """
        router_fn = self._capture_router_fn("modern", monkeypatch)
        result = router_fn({"errors": []})
        assert result == "chief_editor", "modern 启用 soul injection 后应走终审"

    def test_modern_fail_goes_to_end(self, monkeypatch):
        """modern 桶 quality 失败（errors 非空）→ router_fn 返回 END。"""
        router_fn = self._capture_router_fn("modern", monkeypatch)
        assert router_fn({"errors": ["缺讲人物"]}) == "__end__"

    def test_knowledge_pass_goes_to_chief_editor(self, monkeypatch):
        """knowledge 桶 quality 通过 → 'chief_editor'（阶段4 三桶均走终审）。"""
        router_fn = self._capture_router_fn("knowledge", monkeypatch)
        result = router_fn({"errors": []})
        assert result == "chief_editor", "knowledge 启用 soul injection 后应走终审"

    def test_knowledge_fail_goes_to_end(self, monkeypatch):
        """knowledge 桶 quality 失败 → END。"""
        router_fn = self._capture_router_fn("knowledge", monkeypatch)
        assert router_fn({"errors": ["x"]}) == "__end__"

    def test_narrative_pass_goes_to_chief_editor(self, monkeypatch):
        """narrative 桶 quality 通过 → 'chief_editor'（终审后再 save）。"""
        router_fn = self._capture_router_fn("narrative", monkeypatch)
        assert router_fn({"errors": []}) == "chief_editor"

    def test_narrative_fail_goes_to_end(self, monkeypatch):
        """narrative 桶 quality 失败 → END（跳过终审和保存）。"""
        router_fn = self._capture_router_fn("narrative", monkeypatch)
        assert router_fn({"errors": ["x"]}) == "__end__"


# ---------------------------------------------------------------------------
# 契约9：_soul_injection_for_archetype 纯函数直接单测（P1-3）
# ---------------------------------------------------------------------------

class TestSoulInjectionForArchetypePureFunction:
    """_soul_injection_for_archetype 的开关组合逻辑直接单测。

    原测试只通过拓扑间接验证，soul injection 开关一旦为 False 就全桶跳过，
    无法区分"archetype 选对了"还是"开关恰好为 False"。现直接测纯函数。
    """

    def test_narrative_all_flags_on_returns_true(self, monkeypatch):
        """narrative + 三开关全 True → 启用 soul injection。"""
        monkeypatch.setattr("src.core.workflow.SOUL_INJECTION_ENABLED", True)
        monkeypatch.setattr("src.core.workflow._TONE_SETTER_AVAILABLE", True)
        monkeypatch.setattr("src.core.workflow._CHIEF_EDITOR_AVAILABLE", True)
        from src.core.workflow import _soul_injection_for_archetype
        assert _soul_injection_for_archetype("narrative") is True

    @pytest.mark.parametrize("flag", [
        "SOUL_INJECTION_ENABLED", "_TONE_SETTER_AVAILABLE", "_CHIEF_EDITOR_AVAILABLE",
    ])
    def test_narrative_any_flag_off_returns_false(self, monkeypatch, flag):
        """narrative + 任一开关 False → 不启用（缺一不可）。"""
        monkeypatch.setattr("src.core.workflow.SOUL_INJECTION_ENABLED", True)
        monkeypatch.setattr("src.core.workflow._TONE_SETTER_AVAILABLE", True)
        monkeypatch.setattr("src.core.workflow._CHIEF_EDITOR_AVAILABLE", True)
        monkeypatch.setattr(f"src.core.workflow.{flag}", False)
        from src.core.workflow import _soul_injection_for_archetype
        assert _soul_injection_for_archetype("narrative") is False

    @pytest.mark.parametrize("arch", ["modern", "knowledge"])
    def test_non_narrative_all_flags_on_returns_true(self, monkeypatch, arch):
        """阶段4 边链裁剪后：modern/knowledge 三开关全 True 也启用 soul injection。

        原 design.md §10.6 modern/knowledge 跳过，因 prompt 未建 + 边链未裁剪。
        阶段4 内容工作落地后 prompt 已建 + 边链按桶裁剪，三桶均启用。
        """
        monkeypatch.setattr("src.core.workflow.SOUL_INJECTION_ENABLED", True)
        monkeypatch.setattr("src.core.workflow._TONE_SETTER_AVAILABLE", True)
        monkeypatch.setattr("src.core.workflow._CHIEF_EDITOR_AVAILABLE", True)
        from src.core.workflow import _soul_injection_for_archetype
        assert _soul_injection_for_archetype(arch) is True

    def test_invalid_archetype_returns_false(self, monkeypatch):
        """非法 archetype 兜底 False（不启用 soul injection）。"""
        monkeypatch.setattr("src.core.workflow.SOUL_INJECTION_ENABLED", True)
        monkeypatch.setattr("src.core.workflow._TONE_SETTER_AVAILABLE", True)
        monkeypatch.setattr("src.core.workflow._CHIEF_EDITOR_AVAILABLE", True)
        from src.core.workflow import _soul_injection_for_archetype
        assert _soul_injection_for_archetype("fiction") is False
        assert _soul_injection_for_archetype("") is False


# ---------------------------------------------------------------------------
# 契约10：get_required_sections fallback 路径（P1-2）
# ---------------------------------------------------------------------------

class TestGetRequiredSectionsFallback:
    """config.section_templates 缺失时 fallback 到 quality_check.required_sections。

    P1-2：原 fake_load_config 永远返回完整 section_templates，fallback 路径零覆盖。
    """

    def test_no_section_templates_falls_back_to_quality_check(self, monkeypatch):
        """config 无 section_templates 时，narrative 回落到 quality_check.required_sections。"""
        legacy = ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]
        monkeypatch.setattr(
            "src.core.workflow.load_config",
            lambda: {"quality_check": {"required_sections": legacy}},
        )
        assert get_required_sections("narrative") == legacy

    def test_no_section_templates_modern_also_falls_back(self, monkeypatch):
        """config 无 section_templates 时，modern 也回落到 quality_check（因 modern 不在 templates）。"""
        legacy = ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]
        monkeypatch.setattr(
            "src.core.workflow.load_config",
            lambda: {"quality_check": {"required_sections": legacy}},
        )
        # modern 不在 templates（因 templates 缺失），fallback 到 quality_check 列表
        assert get_required_sections("modern") == legacy

    def test_empty_config_falls_back_to_legacy_hardcoded(self, monkeypatch):
        """config 完全空时，fallback 到 _LEGACY_REQUIRED_SECTIONS 硬编码。"""
        monkeypatch.setattr("src.core.workflow.load_config", lambda: {})
        result = get_required_sections("narrative")
        assert result == ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"]

    def test_non_dict_config_falls_back_to_legacy(self, monkeypatch):
        """config 返回非 dict 时，兜底 legacy。"""
        monkeypatch.setattr("src.core.workflow.load_config", lambda: None)
        assert get_required_sections("narrative") == [
            "讲事情", "讲人物", "讲背景", "讲道理", "问道悟道", "结语"
        ]


# ---------------------------------------------------------------------------
# 契约11：_get_stub_sections 与 get_required_sections 双真相源一致性（P1-4）
# ---------------------------------------------------------------------------

class TestStubWorkflowConsistency:
    """main._get_stub_sections 与 workflow.get_required_sections 行为一致。

    P1-4：两套代码分别手写（main 直读 config / workflow 经 load_config），
    存在漂移风险。锁住三桶输出完全一致。
    """

    @pytest.mark.parametrize("arch", ["narrative", "modern", "knowledge"])
    def test_stub_matches_workflow(self, arch):
        """_get_stub_sections(arch) == get_required_sections(arch) 三桶一致。"""
        from src.main import _get_stub_sections
        stub_result = _get_stub_sections(arch)
        workflow_result = get_required_sections(arch)
        assert stub_result == workflow_result, (
            f"{arch} 桶 stub 与 workflow 输出不一致："
            f"stub={stub_result} workflow={workflow_result}"
        )


# ---------------------------------------------------------------------------
# 契约12：阶段4 真实模式 modern/knowledge 直接用 archetype 执行（P0-1 回落已解除）
# ---------------------------------------------------------------------------

class TestRealModeArchetypeExecution:
    """阶段4：真实模式（非 stub）下 modern/knowledge 直接用 archetype 执行。

    原阶段3 P0-1 修复：specialist 硬编码 narrative 段名，quality 用 modern 段名
    检查会全缺导致不 save，故 build_workflow 用回落的 exec_archetype=narrative。
    阶段4 specialist 已按 archetype 路由 prompt+段名，回落已解除，
    build_workflow 直接收到 archetype，initial_state.archetype 也是 archetype。
    """

    def _run_real_mode_capturing_workflow(self, monkeypatch, archetype):
        """真实模式跑 main，mock build_workflow 捕获传入的 archetype 参数和 initial_state。"""
        import sys as _sys
        captured = {"bw_archetype": None, "state_archetype": None}

        class FakeApp:
            def invoke(self, initial_state):
                captured["state_archetype"] = initial_state.get("archetype")
                return {"errors": [], "output_path": "/tmp/x.md", "final_markdown": ""}

        def fake_build_workflow(output_base=None, archetype="narrative"):
            captured["bw_archetype"] = archetype
            return FakeApp()

        import types
        fake_mod = types.ModuleType("src.core.workflow")
        fake_mod.build_workflow = fake_build_workflow
        monkeypatch.setitem(_sys.modules, "src.core.workflow", fake_mod)

        import src.main as main_mod
        monkeypatch.setattr(_sys, "argv", [
            "src.main", "--book", "测试书", "--chapter", "测试章",
            "--event", "测试事件", "--archetype", archetype,
            "--output-dir", "/tmp/test_p0_1",
        ])
        rc = main_mod.main()
        assert rc == 0, f"main 返回非 0"
        return captured

    def test_modern_real_mode_uses_modern_archetype(self, monkeypatch):
        """阶段4：modern 真实模式直接用 modern 执行，无回落。"""
        captured = self._run_real_mode_capturing_workflow(monkeypatch, "modern")
        assert captured["bw_archetype"] == "modern", (
            f"build_workflow 应收到 modern（阶段4 已解除回落），实际 {captured['bw_archetype']!r}"
        )
        assert captured["state_archetype"] == "modern", (
            f"initial_state 应为 modern，实际 {captured['state_archetype']!r}"
        )

    def test_knowledge_real_mode_uses_knowledge_archetype(self, monkeypatch):
        """阶段4：knowledge 真实模式直接用 knowledge 执行，无回落。"""
        captured = self._run_real_mode_capturing_workflow(monkeypatch, "knowledge")
        assert captured["bw_archetype"] == "knowledge"
        assert captured["state_archetype"] == "knowledge"

    def test_narrative_real_mode_uses_narrative(self, monkeypatch):
        """narrative 真实模式：build_workflow 和 initial_state 都是 narrative。"""
        captured = self._run_real_mode_capturing_workflow(monkeypatch, "narrative")
        assert captured["bw_archetype"] == "narrative"
        assert captured["state_archetype"] == "narrative"
