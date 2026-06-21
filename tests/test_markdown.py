import tempfile
from pathlib import Path

from src.utils.markdown import build_frontmatter, save_markdown, split_sections


def test_build_frontmatter_contains_required_fields():
    fm = build_frontmatter(
        title="测试标题",
        book="资治通鉴",
        chapter="周纪二",
        event="商鞅变法",
        source_agents=["Editor Agent"],
    )
    assert "title: 测试标题" in fm
    assert "book: 资治通鉴" in fm
    assert "chapter: 周纪二" in fm
    assert "event: 商鞅变法" in fm
    assert "source_agents: Editor Agent" in fm
    assert "created_at:" in fm


def test_save_markdown_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_markdown(
            book="资治通鉴",
            chapter="周纪二",
            event="商鞅变法",
            content="# 测试",
            base_dir=tmpdir,
        )
        assert path.exists()
        assert path.parent.name == "资治通鉴"
        assert path.name == "周纪二_商鞅变法.md"
        assert path.read_text(encoding="utf-8") == "# 测试"


def test_split_sections_parses_headings():
    text = "## 讲事情\n\n内容一\n\n## 讲人物\n\n内容二"
    sections = split_sections(text)
    assert sections["讲事情"] == "内容一"
    assert sections["讲人物"] == "内容二"
