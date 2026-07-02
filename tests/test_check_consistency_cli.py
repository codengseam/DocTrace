"""一致性检测 CLI 脚本回归测试。

被测脚本：.trae/skills/content-review/scripts/check_consistency.py
覆盖四个公共入口：
1. _detect_archetype(path, fallback) —— frontmatter category/archetype 解析 + 路径启发式兜底
2. check_file(path, archetype) —— 单文件检测，返回 (ConsistencyReport, rel_path)
3. check_dir(directory, glob, archetype_override) —— 目录递归检测
4. main(argv) —— CLI 入口，退出码语义

脚本路径含连字符（content-review），无法用普通 import 加载，
这里用 importlib.util 按文件位置加载为模块。
"""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# 确保 src 包可导入（脚本自身也会把 _ROOT 插入 sys.path，这里冗余兜底）
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.consistency import ConsistencyReport

# --- 通过 importlib 加载含连字符路径的 CLI 脚本 ------------------------------
_SCRIPT_PATH = ROOT / ".trae" / "skills" / "content-review" / "scripts" / "check_consistency.py"
_spec = importlib.util.spec_from_file_location("check_consistency_cli", _SCRIPT_PATH)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


# 干净内容（无任何矛盾），多组测试复用
_CLEAN_CONTENT = "# 测试\n\n这是一段没有矛盾的简短文本。\n"
# 含 P0 数值交叉矛盾（前155年生，前140年继位时25岁，实际应 15 岁）
_P0_CONTENT = "# 测试\n\n曹操生于前155年，前140年继位时25岁。\n"
# 含时间线倒置（年份逆序、无倒叙标注）；仅在 narrative 桶会被检测
_TIMELINE_CONTENT = (
    "# 测试\n\n## 讲事情\n\n建安十三年，赤壁之战爆发。\n建安十二年，隆中对提出。\n"
)


# ---------------------------------------------------------------------------
# 1. _detect_archetype
# ---------------------------------------------------------------------------

class TestDetectArchetype:
    """_detect_archetype：从 frontmatter 解析 archetype，路径启发式兜底。"""

    def test_archetype_modern_from_frontmatter(self, tmp_path):
        """frontmatter 显式 archetype: modern（无 category）应返回 modern。"""
        md = tmp_path / "test.md"
        md.write_text("---\ntitle: 测试\narchetype: modern\n---\n\n正文。\n", encoding="utf-8")
        assert cli._detect_archetype(md) == "modern"

    def test_archetype_knowledge_from_frontmatter(self, tmp_path):
        """frontmatter 显式 archetype: knowledge（无 category）应返回 knowledge。"""
        md = tmp_path / "test.md"
        md.write_text("---\narchetype: knowledge\n---\n\n正文。\n", encoding="utf-8")
        assert cli._detect_archetype(md) == "knowledge"

    def test_no_archetype_field_returns_fallback(self, tmp_path):
        """frontmatter 无 category/archetype 字段、路径无关键词，应返回默认 fallback。"""
        md = tmp_path / "test.md"
        md.write_text("---\ntitle: 测试\n---\n\n正文。\n", encoding="utf-8")
        # tmp_path 不含 modern/knowledge 关键词，命中兜底
        assert cli._detect_archetype(md) == "narrative"

    def test_path_heuristic_modern_keywords(self, tmp_path):
        """路径含「职场/理财/面试」等关键词、frontmatter 无声明，应返回 modern。"""
        # 用「理财」关键词（不在 config archetype_defaults 里，纯路径启发式）
        modern_dir = tmp_path / "理财"
        modern_dir.mkdir()
        md = modern_dir / "note.md"
        md.write_text("# 理财笔记\n", encoding="utf-8")  # 无 frontmatter
        assert cli._detect_archetype(md) == "modern"

    def test_path_heuristic_knowledge_keywords(self, tmp_path):
        """路径含「MySQL/算法/Python」等关键词、frontmatter 无声明，应返回 knowledge。"""
        knowledge_dir = tmp_path / "MySQL"
        knowledge_dir.mkdir()
        md = knowledge_dir / "note.md"
        md.write_text("# MySQL 索引\n", encoding="utf-8")
        assert cli._detect_archetype(md) == "knowledge"

    def test_file_not_exist_returns_fallback(self, tmp_path):
        """文件不存在时应返回 fallback，不抛异常。"""
        missing = tmp_path / "nonexistent.md"
        assert cli._detect_archetype(missing) == "narrative"

    def test_custom_fallback_param(self, tmp_path):
        """fallback 参数应可自定义，文件不存在时返回该值。"""
        missing = tmp_path / "nonexistent.md"
        assert cli._detect_archetype(missing, fallback="knowledge") == "knowledge"


# ---------------------------------------------------------------------------
# 2. check_file
# ---------------------------------------------------------------------------

class TestCheckFile:
    """check_file：单文件检测，返回 (ConsistencyReport, rel_path)。"""

    def test_clean_file_no_issues(self, tmp_path):
        """干净文件应返回空 issues 列表。"""
        md = tmp_path / "clean.md"
        md.write_text(_CLEAN_CONTENT, encoding="utf-8")
        report, _ = cli.check_file(md, archetype="narrative")
        assert isinstance(report, ConsistencyReport)
        assert report.issues == []

    def test_p0_contradiction_detected(self, tmp_path):
        """含 P0 数值交叉矛盾的文件，issues 非空且包含 P0。"""
        md = tmp_path / "dirty.md"
        md.write_text(_P0_CONTENT, encoding="utf-8")
        report, _ = cli.check_file(md, archetype="narrative")
        assert len(report.issues) >= 1
        p0 = [i for i in report.issues if i.severity == "P0"]
        assert len(p0) >= 1, f"应检测到 P0 矛盾，实际: {report.issues}"

    def test_rel_path_is_relative(self, tmp_path, monkeypatch):
        """文件在 _ROOT 下时，rel_path 应为相对路径（不含绝对前缀）。

        通过 monkeypatch 把 cli._ROOT 指向 tmp_path，使文件落在「项目根」下，
        触发 path.resolve().relative_to(_ROOT) 分支，得到相对路径。
        """
        monkeypatch.setattr(cli, "_ROOT", tmp_path)
        md = tmp_path / "clean.md"
        md.write_text(_CLEAN_CONTENT, encoding="utf-8")
        _, rel = cli.check_file(md, archetype="narrative")
        assert rel == "clean.md"
        assert not rel.startswith("/"), f"rel 应为相对路径，实际: {rel}"


# ---------------------------------------------------------------------------
# 3. check_dir
# ---------------------------------------------------------------------------

class TestCheckDir:
    """check_dir：目录递归检测。"""

    def test_empty_dir_returns_empty(self, tmp_path):
        """空目录应返回空列表。"""
        assert cli.check_dir(tmp_path) == []

    def test_two_md_files_returns_two(self, tmp_path):
        """含 2 个 md 文件的目录应返回 2 个元素。"""
        (tmp_path / "a.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        (tmp_path / "b.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        results = cli.check_dir(tmp_path)
        assert len(results) == 2

    def test_archetype_override_modern_skips_timeline(self, tmp_path):
        """archetype_override='modern' 时，所有文件用 modern 桶，时间线 issue 为 0。

        对照：override='narrative' 时同一文件应检出时间线倒置。
        """
        (tmp_path / "timeline.md").write_text(_TIMELINE_CONTENT, encoding="utf-8")

        modern_results = cli.check_dir(tmp_path, archetype_override="modern")
        assert len(modern_results) == 1
        _, modern_issues = modern_results[0]
        timeline_modern = [i for i in modern_issues if i.type == "timeline_inversion"]
        assert timeline_modern == [], f"modern 桶应跳过时间线，实际: {timeline_modern}"

        # 对照组：narrative 桶应检出时间线倒置
        narrative_results = cli.check_dir(tmp_path, archetype_override="narrative")
        _, narrative_issues = narrative_results[0]
        timeline_narrative = [i for i in narrative_issues if i.type == "timeline_inversion"]
        assert len(timeline_narrative) >= 1, "narrative 桶应检出时间线倒置"

    def test_underscore_prefixed_files_skipped(self, tmp_path):
        """以 _ 开头的文件应被跳过。"""
        (tmp_path / "_skip.md").write_text(_P0_CONTENT, encoding="utf-8")
        (tmp_path / "keep.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        results = cli.check_dir(tmp_path)
        assert len(results) == 1
        rel, _ = results[0]
        assert "_skip" not in rel, f"应跳过 _ 开头文件，实际: {rel}"

    def test_subdirectory_recursion(self, tmp_path):
        """子目录中的 md 文件应被递归发现（**/*.md glob）。"""
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (tmp_path / "top.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        (sub / "nested.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        results = cli.check_dir(tmp_path)
        assert len(results) == 2, f"应递归发现 2 个文件（含子目录），实际: {len(results)}"
        rels = [r[0] for r in results]
        assert any("nested" in r for r in rels), f"应包含子目录文件，实际: {rels}"

    def test_mixed_archetype_auto_detection(self, tmp_path):
        """同一目录混合原型文件应各自自动路由（modern 跳过 timeline，narrative 检出）。"""
        # modern 文件：路径含"职场"启发式 → modern → 跳过 timeline
        modern_dir = tmp_path / "职场课"
        modern_dir.mkdir()
        (modern_dir / "m.md").write_text(_TIMELINE_CONTENT, encoding="utf-8")
        # narrative 文件：无路径启发式 → narrative → 检出 timeline
        (tmp_path / "n.md").write_text(_TIMELINE_CONTENT, encoding="utf-8")
        results = cli.check_dir(tmp_path)
        assert len(results) == 2
        by_name = {}
        for rel, issues in results:
            by_name[Path(rel).name] = issues
        # modern 文件无 timeline issue
        m_timeline = [i for i in by_name["m.md"] if i.type == "timeline_inversion"]
        assert m_timeline == [], f"职场路径应路由为 modern 跳过 timeline，实际: {m_timeline}"
        # narrative 文件有 timeline issue
        n_timeline = [i for i in by_name["n.md"] if i.type == "timeline_inversion"]
        assert len(n_timeline) >= 1, f"应路由为 narrative 检出 timeline，实际: {n_timeline}"

    def test_detect_archetype_category_field(self, tmp_path):
        """frontmatter category 字段应经 resolve_archetype 解析 archetype。"""
        # category: 职场 → config.yaml archetype_defaults → modern
        md = tmp_path / "cat.md"
        md.write_text(
            "---\ntitle: 测试\ncategory: 职场\n---\n\n正文。\n", encoding="utf-8"
        )
        assert cli._detect_archetype(md) == "modern", (
            "category: 职场 应解析为 modern"
        )
        # category: 技 → knowledge
        md2 = tmp_path / "tech.md"
        md2.write_text(
            "---\ntitle: 测试\ncategory: 技\n---\n\n正文。\n", encoding="utf-8"
        )
        assert cli._detect_archetype(md2) == "knowledge", (
            "category: 技 应解析为 knowledge"
        )


# ---------------------------------------------------------------------------
# 4. main —— CLI 入口
# ---------------------------------------------------------------------------

class TestMainCli:
    """main：CLI 入口，验证退出码与输出。"""

    def test_file_mode_clean_returns_zero(self, tmp_path, capsys):
        """--file 模式干净文件应返回 0。"""
        md = tmp_path / "clean.md"
        md.write_text(_CLEAN_CONTENT, encoding="utf-8")
        rc = cli.main(["--file", str(md)])
        assert rc == 0

    def test_file_mode_p0_strict_returns_one(self, tmp_path, capsys):
        """--file 含 P0 + --strict 应返回 1。"""
        md = tmp_path / "dirty.md"
        md.write_text(_P0_CONTENT, encoding="utf-8")
        rc = cli.main(["--file", str(md), "--strict"])
        assert rc == 1

    def test_file_mode_p0_no_strict_returns_zero(self, tmp_path, capsys):
        """--file 含 P0 但无 --strict 应返回 0。"""
        md = tmp_path / "dirty.md"
        md.write_text(_P0_CONTENT, encoding="utf-8")
        rc = cli.main(["--file", str(md)])
        assert rc == 0

    def test_file_not_exist_returns_one(self, tmp_path, capsys):
        """--file 不存在应返回 1。"""
        rc = cli.main(["--file", str(tmp_path / "nonexistent.md")])
        assert rc == 1

    def test_stdin_mode_returns_zero(self, tmp_path, capsys, monkeypatch):
        """--file - stdin 模式应返回 0（干净内容）。"""
        monkeypatch.setattr(sys, "stdin", io.StringIO(_CLEAN_CONTENT))
        rc = cli.main(["--file", "-"])
        assert rc == 0

    def test_dir_mode_returns_zero(self, tmp_path, capsys):
        """--dir 模式（无 --strict）应返回 0。"""
        (tmp_path / "a.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        rc = cli.main(["--dir", str(tmp_path)])
        assert rc == 0

    def test_dir_not_exist_returns_one(self, tmp_path, capsys):
        """--dir 不存在应返回 1。"""
        rc = cli.main(["--dir", str(tmp_path / "nonexistent")])
        assert rc == 1

    def test_archetype_modern_override_skips_timeline(self, tmp_path, capsys):
        """--archetype modern override：modern 桶跳过时间线倒置检测。

        对照：--archetype narrative 应检出时间线倒置（P2）。
        """
        md = tmp_path / "timeline.md"
        md.write_text(_TIMELINE_CONTENT, encoding="utf-8")

        # modern：时间线检测被跳过，报告应显示 0 项
        rc_modern = cli.main(["--file", str(md), "--archetype", "modern"])
        out_modern = capsys.readouterr().out
        assert rc_modern == 0
        assert "时间线倒置（0 项）" in out_modern, f"modern 应跳过时间线，输出: {out_modern}"

        # 对照：narrative 应检出时间线倒置
        rc_narrative = cli.main(["--file", str(md), "--archetype", "narrative"])
        out_narrative = capsys.readouterr().out
        assert rc_narrative == 0  # P2 不触发 --strict 退出码
        assert "时间线倒置（1 项）" in out_narrative, f"narrative 应检出时间线，输出: {out_narrative}"

    def test_output_writes_file(self, tmp_path, capsys):
        """--output 应把报告写入文件，文件存在且非空。"""
        md = tmp_path / "clean.md"
        md.write_text(_CLEAN_CONTENT, encoding="utf-8")
        out_file = tmp_path / "reports" / "result.md"
        rc = cli.main(["--file", str(md), "--output", str(out_file)])
        assert rc == 0
        assert out_file.exists(), "输出文件应存在"
        assert out_file.stat().st_size > 0, "输出文件应非空"

    def test_no_args_default_scans_output(self, tmp_path, capsys, monkeypatch):
        """无参数时默认扫描 _ROOT/output/，应返回 0（无 --strict）。

        通过 monkeypatch 把 cli._ROOT 指向 tmp_path，并在其下建 output/clean.md，
        确定性地验证「无 --file/--dir 时回退到 _ROOT/output」的代码路径。
        """
        monkeypatch.setattr(cli, "_ROOT", tmp_path)
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        (out_dir / "clean.md").write_text(_CLEAN_CONTENT, encoding="utf-8")
        rc = cli.main([])
        assert rc == 0
