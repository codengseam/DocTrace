"""archetype 分桶阶段4 基础设施测试：load_prompt 按 archetype 路由。

测试契约（来自 docs/archetype-design/design.md §11.4、§九阶段4）：
- load_prompt(name, variables, archetype="narrative") 按 archetype 选子目录
- narrative 桶维持原 prompts/{name}.md 路径兼容（禁区：narrative prompt 原封不动）
- modern/knowledge 命中 prompts/{archetype}/{name}.md
- modern/knowledge 文件不存在时 fallback 到 narrative 原路径 + 警告（不静默，渐进迁移友好）
- 非法 archetype 兜底 narrative
- variables 替换仍工作（不破坏现有功能）

范围：只测 load_prompt 能力，不碰 specialist/workflow/prompts 文件内容。
"""
import warnings

import pytest

from src.utils.prompts import load_prompt


# ---------------------------------------------------------------------------
# 测试辅助：在 tmp_path 下建隔离的 prompts/ 结构
# ---------------------------------------------------------------------------

def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_full(tmp_path):
    """建完整结构：narrative 原路径 + modern/knowledge 子目录。"""
    prompts = tmp_path / "prompts"
    _write(prompts / "historian.md", "narrative historian")
    _write(prompts / "modern" / "historian.md", "modern historian")
    _write(prompts / "knowledge" / "historian.md", "knowledge historian")
    return prompts


# ---------------------------------------------------------------------------
# 契约1：archetype 路由到对应子目录
# ---------------------------------------------------------------------------

class TestLoadPromptArchetypeRouting:
    """load_prompt 按 archetype 选子目录（§11.4）。"""

    def test_modern_hits_subdirectory(self, tmp_path, monkeypatch):
        """modern 桶命中 prompts/modern/{name}.md。"""
        _setup_full(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert load_prompt("historian", archetype="modern") == "modern historian"

    def test_knowledge_hits_subdirectory(self, tmp_path, monkeypatch):
        """knowledge 桶命中 prompts/knowledge/{name}.md。"""
        _setup_full(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert load_prompt("historian", archetype="knowledge") == "knowledge historian"

    def test_narrative_hits_original_path(self, tmp_path, monkeypatch):
        """narrative 桶命中原 prompts/{name}.md（兼容，不建 narrative/ 子目录）。"""
        _setup_full(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert load_prompt("historian", archetype="narrative") == "narrative historian"


# ---------------------------------------------------------------------------
# 契约2：默认 archetype 是 narrative（向后兼容）
# ---------------------------------------------------------------------------

class TestLoadPromptDefaultArchetype:
    """不传 archetype 时默认 narrative，行为与显式 narrative 一致（零回归）。"""

    def test_default_archetype_is_narrative(self, tmp_path, monkeypatch):
        """load_prompt(name) 等价于 load_prompt(name, archetype='narrative')。"""
        _setup_full(tmp_path)
        monkeypatch.chdir(tmp_path)
        default_result = load_prompt("historian")
        narrative_result = load_prompt("historian", archetype="narrative")
        assert default_result == narrative_result == "narrative historian"

    def test_existing_callers_unaffected(self, tmp_path, monkeypatch):
        """现有 load_prompt(name, variables) 调用不传 archetype 仍工作。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "editor.md", "Hello {book}")
        monkeypatch.chdir(tmp_path)
        # 现有调用方式：name + variables，不传 archetype
        assert load_prompt("editor", {"book": "史记"}) == "Hello 史记"


# ---------------------------------------------------------------------------
# 契约3：modern/knowledge 文件不存在时 fallback 到 narrative 原路径 + 警告
# ---------------------------------------------------------------------------

class TestLoadPromptFallback:
    """modern/knowledge prompt 未迁移时 fallback 到 narrative 原路径。

    阶段4 是增量迁移：未迁的 agent 在 modern/knowledge 桶下应用 narrative 版
    prompt（而非崩溃）。警告防掩盖"忘迁了"。
    """

    def test_modern_fallback_to_narrative_when_missing(self, tmp_path, monkeypatch):
        """modern 子目录无 historian.md 时，fallback 读原 prompts/historian.md。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "historian.md", "narrative historian")
        # 不建 modern/ 子目录
        monkeypatch.chdir(tmp_path)
        with pytest.warns(UserWarning, match="modern"):
            result = load_prompt("historian", archetype="modern")
        assert result == "narrative historian"

    def test_knowledge_fallback_to_narrative_when_missing(self, tmp_path, monkeypatch):
        """knowledge 子目录无文件时 fallback。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "historian.md", "narrative historian")
        monkeypatch.chdir(tmp_path)
        with pytest.warns(UserWarning, match="knowledge"):
            result = load_prompt("historian", archetype="knowledge")
        assert result == "narrative historian"

    def test_modern_subdir_exists_but_file_missing_falls_back(self, tmp_path, monkeypatch):
        """modern/ 子目录存在但缺 historian.md 时也 fallback。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "historian.md", "narrative historian")
        _write(prompts / "modern" / "critic.md", "modern critic")  # 子目录存在但无 historian
        monkeypatch.chdir(tmp_path)
        with pytest.warns(UserWarning):
            result = load_prompt("historian", archetype="modern")
        assert result == "narrative historian"

    def test_fallback_warning_mentions_archetype_and_name(self, tmp_path, monkeypatch):
        """警告文案含 archetype 和 prompt name，便于定位忘迁的 agent。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "historian.md", "narrative historian")
        monkeypatch.chdir(tmp_path)
        with pytest.warns(UserWarning) as record:
            load_prompt("historian", archetype="modern")
        msg = str(record[0].message)
        assert "modern" in msg, f"警告应含 archetype 'modern'：{msg}"
        assert "historian" in msg, f"警告应含 prompt name 'historian'：{msg}"


# ---------------------------------------------------------------------------
# 契约4：非法 archetype 兜底 narrative
# ---------------------------------------------------------------------------

class TestLoadPromptInvalidArchetype:
    """非法 archetype（fiction/空串/拼写错误）兜底 narrative，不崩溃。"""

    @pytest.mark.parametrize("bad", ["", "fiction", "narrativ", "不存在"])
    def test_invalid_archetype_falls_back_to_narrative(self, tmp_path, monkeypatch, bad):
        """非法 archetype 读 narrative 原路径（fiction 桶未落地，不建子目录）。"""
        _setup_full(tmp_path)
        monkeypatch.chdir(tmp_path)
        # 非法 archetype 不应崩溃，兜底 narrative
        result = load_prompt("historian", archetype=bad)
        assert result == "narrative historian"


# ---------------------------------------------------------------------------
# 契约5：variables 替换在 archetype 路由下仍工作
# ---------------------------------------------------------------------------

class TestLoadPromptVariablesReplacement:
    """archetype 路由 + variables 替换同时工作（不破坏现有功能）。"""

    def test_variables_replaced_in_modern_prompt(self, tmp_path, monkeypatch):
        """modern 桶 prompt 的 {var} 占位符被替换。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "historian.md", "narrative {book}")
        _write(prompts / "modern" / "historian.md", "modern {book}")
        monkeypatch.chdir(tmp_path)
        assert load_prompt("historian", {"book": "理财课"}, archetype="modern") == "modern 理财课"

    def test_variables_replaced_in_fallback(self, tmp_path, monkeypatch):
        """fallback 到 narrative 时 variables 仍替换。"""
        prompts = tmp_path / "prompts"
        _write(prompts / "historian.md", "narrative {book}")
        monkeypatch.chdir(tmp_path)
        with pytest.warns(UserWarning):
            result = load_prompt("historian", {"book": "理财课"}, archetype="modern")
        assert result == "narrative 理财课"


# ---------------------------------------------------------------------------
# 契约6：prompt 文件完全不存在时仍 raise FileNotFoundError（不静默）
# ---------------------------------------------------------------------------

class TestLoadPromptFileNotFound:
    """prompt 文件（含 narrative 原路径）完全不存在时 raise，不静默返回空。"""

    def test_missing_narrative_raises(self, tmp_path, monkeypatch):
        """narrative 原路径也无该文件时 raise FileNotFoundError。"""
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_prompt("not_exist")

    def test_missing_in_modern_falls_back_then_raises_if_narrative_also_missing(
        self, tmp_path, monkeypatch
    ):
        """modern 无文件 → fallback → narrative 也无文件 → raise。"""
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        monkeypatch.chdir(tmp_path)
        # 无 modern/ 也无原文件，应先警告 fallback 再 raise
        with pytest.raises(FileNotFoundError):
            load_prompt("not_exist", archetype="modern")
