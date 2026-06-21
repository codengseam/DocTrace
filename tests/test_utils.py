from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.config import Config
from src.utils.markdown import build_frontmatter, build_output_path, save_markdown
from src.utils.quality import (
    check_ai_flavor,
    check_chinese_english_mix,
    check_citations,
    check_frontmatter,
    check_structure,
    run_quality_checks,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SECTIONS = ["讲事情", "讲人物", "讲背景", "讲道理", "问道悟道"]
REQUIRED_FRONTMATTER = ["title", "book", "chapter", "event", "created_at", "source_agents"]


def test_config_loads_default_config_yaml():
    cfg = Config(PROJECT_ROOT / "config.yaml")
    assert isinstance(cfg.llm, dict)
    assert isinstance(cfg.paths, dict)
    assert isinstance(cfg.rules, dict)
    assert cfg.path("output").name == "output"
    assert "sections" in cfg.rules


def test_config_resolves_environment_variables(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LLM_BASE_URL", "https://test.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    cfg = Config(PROJECT_ROOT / "config.yaml")
    assert cfg.llm["model"] == "gpt-test"
    assert cfg.llm["base_url"] == "https://test.example.com/v1"
    assert cfg.llm["api_key"] == "test-key"


def test_build_output_path(tmp_path):
    path = build_output_path(tmp_path, "资治通鉴", "周纪二", "商鞅变法")
    assert path == tmp_path / "资治通鉴" / "周纪二_商鞅变法.md"
    assert path.parent.exists()


def test_build_frontmatter():
    fm = build_frontmatter(
        title="《资治通鉴·周纪二》商鞅变法",
        book="资治通鉴",
        chapter="周纪二",
        event="商鞅变法",
        source_agents=["historian", "biographer"],
        created_at="2024-01-01T00:00:00",
    )
    assert fm.startswith("---")
    assert "title: 《资治通鉴·周纪二》商鞅变法" in fm
    assert "book: 资治通鉴" in fm
    assert "chapter: 周纪二" in fm
    assert "event: 商鞅变法" in fm
    assert "created_at: 2024-01-01T00:00:00" in fm
    assert "source_agents:" in fm


def test_save_markdown(tmp_path):
    path = tmp_path / "nested" / "note.md"
    returned = save_markdown(path, "# hello")
    assert returned == path
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "# hello"


def test_check_structure_passes_and_fails():
    content = "\n".join(f"# {s}" for s in SECTIONS) + "\n# 结语\n"
    assert check_structure(content, SECTIONS) == []

    bad = content.replace("讲人物", "")
    issues = check_structure(bad, SECTIONS)
    assert any("讲人物" in issue for issue in issues)

    no_conclusion = "\n".join(f"# {s}" for s in SECTIONS)
    issues = check_structure(no_conclusion, SECTIONS)
    assert any("结语" in issue or "总结" in issue for issue in issues)


def test_check_frontmatter_passes_and_fails():
    content = build_frontmatter(
        "t", "b", "c", "e", ["a"], created_at="2024-01-01T00:00:00"
    ) + "\n# body\n"
    assert check_frontmatter(content, REQUIRED_FRONTMATTER) == []

    issues = check_frontmatter("# no frontmatter", ["title"])
    assert any("frontmatter" in issue for issue in issues)

    missing_title = "---\nbook: b\nchapter: c\nevent: e\ncreated_at: 2024-01-01T00:00:00\n---\n# body\n"
    issues = check_frontmatter(missing_title, ["title"])
    assert any("title" in issue for issue in issues)


def test_check_ai_flavor():
    assert check_ai_flavor("我们可以看到结果") != []
    assert check_ai_flavor("这告诉我们一个道理") != []
    assert check_ai_flavor("综上所述，可以总结") != []
    assert check_ai_flavor("商鞅徙木立信，建立权威") == []


def test_check_chinese_english_mix():
    assert check_chinese_english_mix("这是hello世界") != []
    assert check_chinese_english_mix("这是 hello 世界") == []
    assert check_chinese_english_mix("商鞅变法") == []


def test_check_citations():
    assert check_citations("据《史记·商君列传》记载") == []
    assert check_citations("原文这样写道") == []
    assert check_citations("没有任何引用") != []


def test_run_quality_checks():
    good = (
        build_frontmatter("t", "b", "c", "e", ["a"], created_at="2024-01-01T00:00:00")
        + "\n"
        + "\n".join(f"# {s}\n内容。" for s in SECTIONS)
        + "\n# 结语\n一句话总结。\n"
        + "## 参考来源\n- 《史记》\n"
    )
    report = run_quality_checks(good, SECTIONS, REQUIRED_FRONTMATTER)
    assert report.passed
    assert report.issues == []

    bad = "plain text without sections"
    report = run_quality_checks(bad, SECTIONS, ["title"])
    assert not report.passed
    assert report.issues
