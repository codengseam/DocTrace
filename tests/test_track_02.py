"""Track 2 工具与存储层单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.storage.file_manager import FileManager
from src.storage.metadata_store import MetadataStore
from src.tools.obsidian_writer import ObsidianWriter
from src.tools.source_cache import SourceCache
from src.tools.web_search import WebSearch
from src.utils.config import load_config, load_env


class TestConfigUtils(unittest.TestCase):
    """验证配置加载工具可导入并正确处理文件。"""

    def test_load_config_parses_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                'output_dir: "output"\n'
                'trusted_domains:\n'
                '  - "zh.wikipedia.org"\n',
                encoding="utf-8",
            )
            config = load_config(config_path)
            self.assertEqual(config.get("output_dir"), "output")
            self.assertIn("zh.wikipedia.org", config.get("trusted_domains", []))

    def test_load_env_parses_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "DASHSCOPE_API_KEY=sk-test\n"
                "# 这是注释\n"
                "OBSIDIAN_VAULT_PATH=/tmp/vault\n",
                encoding="utf-8",
            )
            env = load_env(env_path)
            self.assertEqual(env["DASHSCOPE_API_KEY"], "sk-test")
            self.assertEqual(env["OBSIDIAN_VAULT_PATH"], "/tmp/vault")
            self.assertNotIn("# 这是注释", env)


class TestFileManager(unittest.TestCase):
    """验证文件路径生成与文件名规范化。"""

    def test_get_output_path_returns_correct_path(self) -> None:
        fm = FileManager(output_dir="output")
        path = fm.get_output_path("资治通鉴", "周纪二", "商鞅变法")
        self.assertEqual(
            path,
            Path("output") / "资治通鉴" / "周纪二_商鞅变法.md",
        )

    def test_sanitize_filename_handles_chinese_and_illegal_chars(self) -> None:
        fm = FileManager()
        self.assertEqual(fm.sanitize_filename("周纪二_商鞅变法.md"), "周纪二_商鞅变法.md")
        self.assertEqual(fm.sanitize_filename("a/b\\c?d.txt"), "a_b_c_d.txt")
        self.assertEqual(fm.sanitize_filename("  hello   world  "), "hello_world")


class TestMetadataStore(unittest.TestCase):
    """验证元数据增删改查。"""

    def test_add_or_update_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataStore(Path(tmp) / "metadata.json")
            store.add_or_update("周纪二_商鞅变法", {"book": "资治通鉴", "event": "商鞅变法"})
            result = store.get("周纪二_商鞅变法")
            self.assertEqual(result, {"book": "资治通鉴", "event": "商鞅变法"})

            store.add_or_update("周纪二_商鞅变法", {"event": "卫鞅变法", "chapter": "周纪二"})
            result = store.get("周纪二_商鞅变法")
            self.assertEqual(result, {"event": "卫鞅变法", "chapter": "周纪二"})

    def test_get_missing_key_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataStore(Path(tmp) / "metadata.json")
            self.assertIsNone(store.get("不存在的键"))


class TestSourceCache(unittest.TestCase):
    """验证资料来源缓存读写。"""

    def test_record_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(Path(tmp) / "cache.json")
            cache.record("商鞅变法", ["https://zh.wikipedia.org/wiki/商鞅变法"])
            sources = cache.get("商鞅变法")
            self.assertEqual(sources, ["https://zh.wikipedia.org/wiki/商鞅变法"])

    def test_get_missing_query_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(Path(tmp) / "cache.json")
            self.assertIsNone(cache.get("不存在的查询"))


class TestWebSearch(unittest.TestCase):
    """验证可信域过滤。"""

    def test_filter_trusted_keeps_whitelisted_domains(self) -> None:
        searcher = WebSearch(
            trusted_domains=["zh.wikipedia.org", "baike.baidu.com"]
        )
        urls = [
            "https://zh.wikipedia.org/wiki/商鞅变法",
            "https://baike.baidu.com/item/商鞅变法",
            "https://example.com/unknown",
        ]
        trusted = searcher.filter_trusted(urls)
        self.assertEqual(len(trusted), 2)
        self.assertIn("https://zh.wikipedia.org/wiki/商鞅变法", trusted)
        self.assertIn("https://baike.baidu.com/item/商鞅变法", trusted)


class TestObsidianWriter(unittest.TestCase):
    """验证 frontmatter 合并逻辑（不依赖真实 MCP）。"""

    def test_merge_frontmatter_on_empty_content(self) -> None:
        writer = ObsidianWriter()
        result = writer.merge_frontmatter("", {"title": "商鞅变法", "book": "资治通鉴"})
        self.assertIn("title: 商鞅变法", result)
        self.assertIn("book: 资治通鉴", result)
        self.assertTrue(result.startswith("---\n"))

    def test_merge_frontmatter_overrides_existing_values(self) -> None:
        writer = ObsidianWriter()
        existing = (
            "---\n"
            "title: 旧标题\n"
            "book: 旧书名\n"
            "---\n\n"
            "正文内容。\n"
        )
        result = writer.merge_frontmatter(
            existing, {"title": "商鞅变法", "created_at": "2026-06-21"}
        )
        self.assertIn("title: 商鞅变法", result)
        self.assertIn("book: 旧书名", result)
        self.assertIn("created_at: 2026-06-21", result)
        self.assertIn("正文内容。", result)


if __name__ == "__main__":
    unittest.main()
