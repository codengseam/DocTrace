"""archetype 分桶阶段1测试：打通数据流。

测试契约（来自 docs/archetype-design/design.md §5.4、§5.6、附录A）：
- resolve_archetype(category, explicit) 优先返回 explicit（若合法）
- 其次查 config.yaml 的 archetype_defaults 映射（值需合法）
- 兜底返回 narrative
- AgentState 含 archetype 字段
- main.py 真正调用 resolve_archetype，archetype 透传到 initial_state
- 16 个现有专栏的 archetype 归类正确（通过 resolve_archetype 验证，非复制副本）
"""
import subprocess
import sys
from pathlib import Path

import pytest

from src.utils.prompts import resolve_archetype, _VALID_ARCHETYPES

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# resolve_archetype 契约测试
# ---------------------------------------------------------------------------

class TestResolveArchetypeExplicit:
    """explicit 参数优先，且必须是合法 archetype。"""

    @pytest.mark.parametrize("arch", sorted(_VALID_ARCHETYPES))
    def test_explicit_valid_wins_over_category(self, monkeypatch, arch):
        """显式传入合法 archetype 时，无视 category 直接返回。"""
        monkeypatch.setattr(
            "src.utils.prompts.load_config",
            lambda: {"archetype_defaults": {"史": "narrative"}},
        )
        assert resolve_archetype("史", explicit=arch) == arch

    def test_explicit_invalid_falls_back_to_mapping(self, monkeypatch):
        """显式传入非法值时，回落到 category 映射。"""
        monkeypatch.setattr(
            "src.utils.prompts.load_config",
            lambda: {"archetype_defaults": {"史": "narrative"}},
        )
        assert resolve_archetype("史", explicit="不存在的桶") == "narrative"

    def test_explicit_none_falls_back_to_mapping(self, monkeypatch):
        """explicit=None 时走 category 映射。"""
        monkeypatch.setattr(
            "src.utils.prompts.load_config",
            lambda: {"archetype_defaults": {"财": "modern"}},
        )
        assert resolve_archetype("财", explicit=None) == "modern"

    def test_explicit_empty_string_falls_back_to_mapping(self, monkeypatch):
        """explicit='' 视为未提供，走 category 映射。"""
        monkeypatch.setattr(
            "src.utils.prompts.load_config",
            lambda: {"archetype_defaults": {"技": "knowledge"}},
        )
        assert resolve_archetype("技", explicit="") == "knowledge"


class TestResolveArchetypeMapping:
    """category → archetype 默认映射（design.md §5.4 的 6 条规则）。

    直接读真实 config.yaml 的 archetype_defaults 做参数化，
    避免与配置文件漂移（修复专家意见：原 monkeypatch 重建映射是冗余真相源）。
    """

    @pytest.fixture(autouse=True)
    def _real_config(self, monkeypatch):
        """用真实 config.yaml，不 mock。"""
        from src.utils.config import load_config
        real = load_config(PROJECT_ROOT / "config.yaml")
        monkeypatch.setattr("src.utils.prompts.load_config", lambda: real)

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("史", "narrative"),
            ("经", "narrative"),
            ("养生", "modern"),
            ("财", "modern"),
            ("职场", "modern"),
            ("技", "knowledge"),
        ],
    )
    def test_default_mapping(self, category, expected):
        """6 个 category 的默认 archetype 映射正确。"""
        assert resolve_archetype(category) == expected, (
            f"category={category!r} 默认映射应为 {expected!r}"
        )


class TestResolveArchetypeFallback:
    """兜底逻辑。"""

    def test_unknown_category_falls_back_to_narrative(self, monkeypatch):
        """未知 category 兜底走 narrative（古籍基线）。"""
        monkeypatch.setattr(
            "src.utils.prompts.load_config",
            lambda: {"archetype_defaults": {"史": "narrative"}},
        )
        assert resolve_archetype("完全不存在的类目") == "narrative"

    def test_empty_config_falls_back_to_narrative(self, monkeypatch):
        """config 无 archetype_defaults 时兜底 narrative。"""
        monkeypatch.setattr("src.utils.prompts.load_config", lambda: {})
        assert resolve_archetype("史") == "narrative"

    def test_none_config_falls_back_to_narrative(self, monkeypatch):
        """load_config 返回 None 时兜底 narrative。"""
        monkeypatch.setattr("src.utils.prompts.load_config", lambda: None)
        assert resolve_archetype("史") == "narrative"

    def test_config_value_invalid_falls_back_to_narrative(self, monkeypatch):
        """config 映射值非法（笔误）时兜底 narrative，防脏值污染下游。"""
        monkeypatch.setattr(
            "src.utils.prompts.load_config",
            lambda: {"archetype_defaults": {"史": "narative"}},  # 拼错
        )
        assert resolve_archetype("史") == "narrative"


# ---------------------------------------------------------------------------
# AgentState 字段测试
# ---------------------------------------------------------------------------

class TestAgentStateArchetypeField:
    """AgentState 必须含 archetype 字段。"""

    def test_state_has_archetype_field(self):
        """AgentState 类型定义含 archetype 键（静态契约）。"""
        from src.core.state import AgentState

        # TypedDict 在运行时是 dict，用 __annotations__ 验证字段声明存在
        assert "archetype" in AgentState.__annotations__, (
            "AgentState 缺少 archetype 字段声明"
        )


# ---------------------------------------------------------------------------
# main.py 集成测试：resolve_archetype 真正被调用且 archetype 透传到 initial_state
# ---------------------------------------------------------------------------

class TestMainArchetypeIntegration:
    """验证 main.py 真正调用 resolve_archetype 并把结果注入 initial_state。

    修复专家意见：原 test_cli_archetype_passed_to_state 用 --stub 模式，
    但 stub 分支不走 initial_state 构造，测试名实不符。
    改用 sys.modules 注入假的 src.core.workflow 模块（langgraph 未安装时也能跑），
    拦截 build_workflow 捕获传入的 initial_state 断言。
    """

    @pytest.fixture
    def fake_workflow(self, monkeypatch):
        """注入假的 src.core.workflow 模块，捕获 initial_state。

        build_workflow 返回带 .invoke 方法的假 app（模拟 LangGraph 接口）。
        """
        import types
        captured = {}

        class FakeApp:
            def invoke(self, initial_state):
                captured.update(initial_state)
                return initial_state

        def fake_build_workflow(output_base="output", archetype="narrative"):
            return FakeApp()

        fake_mod = types.ModuleType("src.core.workflow")
        fake_mod.build_workflow = fake_build_workflow
        monkeypatch.setitem(sys.modules, "src.core.workflow", fake_mod)
        return captured

    def test_archetype_passed_to_initial_state_via_cli(self, monkeypatch, fake_workflow, tmp_path):
        """CLI --archetype modern 时，initial_state['archetype'] == 'modern'。"""
        import src.main as main_mod
        monkeypatch.setattr(
            sys, "argv",
            [
                "src.main",
                "--book", "测试书",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--archetype", "modern",
                "--output-dir", str(tmp_path),
            ],
        )
        rc = main_mod.main()
        assert rc == 0
        assert fake_workflow.get("archetype") == "modern", (
            f"initial_state['archetype'] 应为 'modern'，实际 {fake_workflow.get('archetype')!r}"
        )

    def test_archetype_resolved_from_meta_yaml(self, monkeypatch, fake_workflow):
        """不传 --archetype 时，从 _meta.yaml 的 archetype 字段解析。

        用真实 output/易经课/_meta.yaml（archetype: knowledge）验证。
        """
        import src.main as main_mod
        monkeypatch.setattr(
            sys, "argv",
            [
                "src.main",
                "--book", "易经课",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--output-dir", str(PROJECT_ROOT / "output"),
            ],
        )
        rc = main_mod.main()
        assert rc == 0
        assert fake_workflow.get("archetype") == "knowledge", (
            f"易经课 _meta.yaml 声明 archetype: knowledge，"
            f"initial_state 应为 'knowledge'，实际 {fake_workflow.get('archetype')!r}"
        )

    def test_archetype_falls_back_to_category_default(self, monkeypatch, fake_workflow):
        """_meta.yaml 无 archetype 字段、不传 CLI 时，按 category 默认映射。

        用真实 output/理财课/_meta.yaml（category: 财，无 archetype）验证。
        """
        import src.main as main_mod
        monkeypatch.setattr(
            sys, "argv",
            [
                "src.main",
                "--book", "理财课",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--output-dir", str(PROJECT_ROOT / "output"),
            ],
        )
        rc = main_mod.main()
        assert rc == 0
        assert fake_workflow.get("archetype") == "modern", (
            f"理财课 category=财 默认映射 modern，"
            f"initial_state 应为 'modern'，实际 {fake_workflow.get('archetype')!r}"
        )

    def test_archetype_falls_back_to_narrative_for_history(self, monkeypatch, fake_workflow):
        """古籍专栏（资治通鉴，category=史，无 archetype）兜底 narrative。"""
        import src.main as main_mod
        monkeypatch.setattr(
            sys, "argv",
            [
                "src.main",
                "--book", "资治通鉴",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--output-dir", str(PROJECT_ROOT / "output"),
            ],
        )
        rc = main_mod.main()
        assert rc == 0
        assert fake_workflow.get("archetype") == "narrative", (
            f"资治通鉴 category=史 默认映射 narrative，"
            f"initial_state 应为 'narrative'，实际 {fake_workflow.get('archetype')!r}"
        )

    def test_cli_archetype_overrides_meta_yaml(self, monkeypatch, fake_workflow):
        """CLI --archetype 优先级高于 _meta.yaml.archetype。"""
        import src.main as main_mod
        # 易经课 _meta.yaml 声明 knowledge，CLI 强制 modern 应胜出
        monkeypatch.setattr(
            sys, "argv",
            [
                "src.main",
                "--book", "易经课",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--archetype", "modern",
                "--output-dir", str(PROJECT_ROOT / "output"),
            ],
        )
        rc = main_mod.main()
        assert rc == 0
        assert fake_workflow.get("archetype") == "modern", (
            f"CLI --archetype modern 应覆盖 _meta.yaml 的 knowledge，"
            f"实际 {fake_workflow.get('archetype')!r}"
        )

    def test_cli_invalid_archetype_falls_back_to_meta(self, monkeypatch, fake_workflow):
        """CLI 传非法 archetype 时，回落到 _meta.yaml 的 archetype 字段。

        行为锁定（design.md §5.6）：CLI 非法值不影响 _meta.yaml 信源，
        explicit = cli or meta or None，非法 cli 被 resolve_archetype 视为未提供，
        回落到 meta_archetype（易经课 knowledge）。
        """
        import src.main as main_mod
        monkeypatch.setattr(
            sys, "argv",
            [
                "src.main",
                "--book", "易经课",
                "--chapter", "测试章",
                "--event", "测试事件",
                "--archetype", "不存在的桶",
                "--output-dir", str(PROJECT_ROOT / "output"),
            ],
        )
        rc = main_mod.main()
        assert rc == 0
        assert fake_workflow.get("archetype") == "knowledge", (
            f"CLI 非法值应回落到 _meta.yaml 的 knowledge，"
            f"实际 {fake_workflow.get('archetype')!r}"
        )

    def test_cli_help_lists_archetype(self):
        """--help 输出含 --archetype。"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert "--archetype" in result.stdout


# ---------------------------------------------------------------------------
# 16 专栏 _meta.yaml 归类测试（通过 resolve_archetype 验证，非复制副本）
# ---------------------------------------------------------------------------

# design.md §5.4 的 16 专栏归类（目录名 → 期望 archetype）
# 注：大厂晋升指南（技→modern）和面试现场（职场→modern）目录尚未建立，
#     待建时大厂晋升指南必须显式 archetype: modern（否则技类默认 knowledge 误判）。
EXPECTED_ARCHETYPES = {
    "资治通鉴": "narrative",
    "史记": "narrative",
    "三国": "narrative",
    "唐纪": "narrative",
    "宋纪": "narrative",
    "明纪": "narrative",
    "孔子传": "narrative",
    "论语": "narrative",
    "易经课": "knowledge",  # 覆盖默认（经→narrative）
    "理财课": "modern",
    "AI大模型学习": "knowledge",
    "职场沟通课": "modern",
    "饮食养生课": "modern",
    "饮食养生课第二版": "modern",
    "锻炼养生课": "modern",
    "睡眠与精力修复课": "modern",
}


def _load_meta(book_dir: str) -> dict:
    """读取真实 _meta.yaml（复用生产 _load_book_meta，避免测试自造解析器漂移）。"""
    from src.main import _load_book_meta
    return _load_book_meta(book_dir, str(PROJECT_ROOT / "output"))


class TestMetaYamlArchetype:
    """16 个专栏 _meta.yaml 的 archetype 归类正确。

    修复专家意见：原测试复制一份 defaults 副本自证，与 resolve_archetype 脱钩。
    现改为调用 resolve_archetype(category, explicit=meta_archetype) 验证，
    让测试真正锁住 resolve_archetype 的行为。
    解析器复用生产 _load_book_meta，避免两套解析逻辑漂移。
    """

    @pytest.fixture(autouse=True)
    def _real_config(self, monkeypatch):
        """用真实 config.yaml，确保 resolve_archetype 走真映射。"""
        from src.utils.config import load_config
        real = load_config(PROJECT_ROOT / "config.yaml")
        monkeypatch.setattr("src.utils.prompts.load_config", lambda: real)

    @pytest.mark.parametrize("book_dir,expected", sorted(EXPECTED_ARCHETYPES.items()))
    def test_book_archetype_via_resolve(self, book_dir, expected):
        meta_path = PROJECT_ROOT / "output" / book_dir / "_meta.yaml"
        assert meta_path.exists(), f"{book_dir} 的 _meta.yaml 应存在但缺失: {meta_path}"
        meta = _load_meta(book_dir)
        category = meta.get("category", "")
        meta_archetype = meta.get("archetype", "") or None
        actual = resolve_archetype(category, explicit=meta_archetype)
        assert actual == expected, (
            f"{book_dir}: category={category!r} meta_archetype={meta_archetype!r} "
            f"resolve_archetype 返回 {actual!r}, 期望 {expected!r}"
        )


# ---------------------------------------------------------------------------
# config.yaml 端到端测试
# ---------------------------------------------------------------------------

class TestConfigArchetypeDefaults:
    """config.yaml 的 archetype_defaults 能被 load_config 读到。"""

    def test_config_has_archetype_defaults(self):
        from src.utils.config import load_config

        cfg = load_config(PROJECT_ROOT / "config.yaml")
        assert "archetype_defaults" in cfg, "config.yaml 缺少 archetype_defaults 顶层映射表"
        mapping = cfg["archetype_defaults"]
        assert isinstance(mapping, dict), f"archetype_defaults 应为 dict, 实际 {type(mapping)}"
        for cat in ("史", "经", "养生", "财", "职场", "技"):
            assert cat in mapping, f"archetype_defaults 缺少 category: {cat}"
        assert mapping["史"] == "narrative"
        assert mapping["经"] == "narrative"
        assert mapping["养生"] == "modern"
        assert mapping["财"] == "modern"
        assert mapping["职场"] == "modern"
        assert mapping["技"] == "knowledge"
