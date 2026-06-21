"""Track 2 工具与存储层单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.storage.file_manager import FileManager, split_markdown
from src.storage.metadata_store import MetadataStore
from src.storage.vault_sync import VaultSync
from src.tools.obsidian_writer import ObsidianWriter
from src.tools.pdf_reader import PDFReader
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

    def test_write_and_read_markdown_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fm = FileManager(output_dir=tmp)
            path = fm.get_output_path("资治通鉴", "周纪一", "三家分晋")
            content = "## 讲事情\n\n三家分晋...\n"
            metadata = {
                "title": "三家分晋",
                "book": "资治通鉴",
                "chapter": "周纪一",
                "event": "三家分晋",
                "source_agents": ["historian"],
            }
            written = fm.write_markdown(path, content, metadata)
            self.assertTrue(written.exists())

            data = fm.read_markdown(written)
            self.assertEqual(data["frontmatter"]["book"], "资治通鉴")
            self.assertEqual(data["frontmatter"]["event"], "三家分晋")
            self.assertIn("## 讲事情", data["content"])

            # 验证 frontmatter 格式合法：能被 split_markdown 重新切分
            text = written.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            split = split_markdown(text)
            self.assertEqual(split["frontmatter"]["title"], "三家分晋")


class TestMetadataStore(unittest.TestCase):
    """验证元数据增删改查。"""

    def test_add_or_update_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataStore(Path(tmp) / "metadata.json")
            store.add_or_update("周纪二_商鞅变法", {"book": "资治通鉴", "chapter": "周纪二", "event": "商鞅变法"})
            result = store.get("周纪二_商鞅变法")
            self.assertIsNotNone(result)
            self.assertEqual(result["book"], "资治通鉴")
            self.assertEqual(result["event"], "商鞅变法")
            self.assertIn("created_at", result)
            self.assertIn("updated_at", result)

            store.add_or_update("周纪二_商鞅变法", {"event": "卫鞅变法"})
            result = store.get("周纪二_商鞅变法")
            self.assertEqual(result["event"], "卫鞅变法")
            self.assertIn("updated_at", result)

    def test_get_missing_key_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataStore(Path(tmp) / "metadata.json")
            self.assertIsNone(store.get("不存在的键"))

    def test_list_books_and_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataStore(Path(tmp) / "metadata.json")
            store.add_or_update({"book": "资治通鉴", "chapter": "周纪一", "event": "三家分晋"})
            store.add_or_update({"book": "资治通鉴", "chapter": "周纪二", "event": "商鞅变法"})
            store.add_or_update({"book": "史记", "chapter": "项羽本纪", "event": "鸿门宴"})
            self.assertEqual(store.list_books(), ["史记", "资治通鉴"])
            self.assertEqual(store.list_chapters("资治通鉴"), ["周纪一", "周纪二"])


class TestSourceCache(unittest.TestCase):
    """验证资料来源缓存读写。"""

    def test_record_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(Path(tmp) / "cache.json")
            cache.record("商鞅变法", ["https://zh.wikipedia.org/wiki/商鞅变法"])
            sources = cache.get("商鞅变法")
            self.assertEqual(sources, ["https://zh.wikipedia.org/wiki/商鞅变法"])

    def test_record_dict_and_deduplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(Path(tmp) / "cache.json")
            cache.record("商鞅变法", {"url": "https://a.com", "title": "A", "snippet": "..."})
            cache.record("商鞅变法", {"url": "https://a.com", "title": "A2", "snippet": "..."})
            sources = cache.get("商鞅变法")
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["url"], "https://a.com")

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

    def test_filter_trusted_dict_results(self) -> None:
        searcher = WebSearch(trusted_domains=["zh.wikipedia.org"])
        results = [
            {"title": "A", "url": "https://zh.wikipedia.org/wiki/A", "snippet": "..."},
            {"title": "B", "url": "https://example.com/B", "snippet": "..."},
        ]
        trusted = searcher.filter_trusted(results)
        self.assertEqual(len(trusted), 1)
        self.assertEqual(trusted[0]["url"], "https://zh.wikipedia.org/wiki/A")


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
        import re
        self.assertIn("title: 商鞅变法", result)
        self.assertIn("book: 旧书名", result)
        # PyYAML 可能给日期字符串加引号，两种格式都接受
        self.assertTrue(
            re.search(r"created_at: ['\"]?2026-06-21['\"]?", result),
            f"created_at not found as expected in: {result}",
        )
        self.assertIn("正文内容。", result)
        # 确保只有一份 frontmatter
        self.assertEqual(result.count("---"), 2)

    def test_update_note_does_not_create_double_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = ObsidianWriter(vault_path=tmp)
            writer.write_note(
                "历史/资治通鉴/周纪二_商鞅变法.md",
                "## 讲事情\n\n商鞅入秦。\n",
                {"title": "商鞅变法", "book": "资治通鉴"},
            )
            result = writer.update_note(
                "历史/资治通鉴/周纪二_商鞅变法.md",
                "## 讲事情\n\n商鞅入秦，徙木立信。\n",
                {"event": "商鞅变法"},
            )
            self.assertTrue(result["success"])
            self.assertTrue(result["updated"])
            written = Path(tmp) / "历史/资治通鉴/周纪二_商鞅变法.md"
            text = written.read_text(encoding="utf-8")
            # 只有开始和结束两处 ---，共 2 次
            self.assertEqual(text.count("---"), 2)
            self.assertIn("event: 商鞅变法", text)
            self.assertIn("title: 商鞅变法", text)


class TestVaultSync(unittest.TestCase):
    """验证 Vault 同步与去重。"""

    def test_sync_to_vault_creates_and_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            vault_dir = Path(tmp) / "vault"
            fm = FileManager(output_dir=output_dir)
            note_path = fm.get_output_path("资治通鉴", "周纪一", "三家分晋")
            fm.write_markdown(
                note_path,
                "## 讲事情\n\n三家分晋...\n",
                {
                    "title": "三家分晋",
                    "book": "资治通鉴",
                    "chapter": "周纪一",
                    "event": "三家分晋",
                    "source_agents": ["historian"],
                },
            )

            sync = VaultSync(vault_root=vault_dir, file_manager=fm)
            result1 = sync.sync_to_vault(note_path)
            self.assertEqual(result1["status"], "created")

            result2 = sync.sync_to_vault(note_path)
            self.assertEqual(result2["status"], "skipped")

            # 验证本地 frontmatter 被写回 vault_path 和 sources
            data = fm.read_markdown(note_path)
            self.assertEqual(data["frontmatter"]["vault_path"], "资治通鉴/周纪一_三家分晋.md")
            self.assertIn("资治通鉴/周纪一_三家分晋.md", data["frontmatter"]["vault_path"])

    def test_sync_book_index_moc_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            vault_dir = Path(tmp) / "vault"
            fm = FileManager(output_dir=output_dir)
            note_path = fm.get_output_path("资治通鉴", "周纪一", "三家分晋")
            fm.write_markdown(
                note_path,
                "## 讲事情\n\n三家分晋...\n",
                {
                    "title": "三家分晋",
                    "book": "资治通鉴",
                    "chapter": "周纪一",
                    "event": "三家分晋",
                    "source_agents": ["historian"],
                },
            )

            sync = VaultSync(vault_root=vault_dir, file_manager=fm)
            sync.sync_to_vault(note_path)
            index_result = sync.sync_book_index("资治通鉴", [note_path])
            self.assertIn(index_result["status"], ("created", "updated"))

            moc_file = vault_dir / "资治通鉴/MOC.md"
            self.assertTrue(moc_file.exists())
            moc_text = moc_file.read_text(encoding="utf-8")
            # 同一目录下链接应为文件名，而非完整相对路径
            self.assertIn("[[周纪一_三家分晋.md|三家分晋]]", moc_text)


class TestPDFReader(unittest.TestCase):
    """验证 PDF 读取 fallback（无真实 MCP 环境）。"""

    def test_read_missing_pdf_returns_empty_result(self) -> None:
        reader = PDFReader()
        result = reader.read_pdf(Path("/workspace/data/不存在的文件.pdf"))
        self.assertEqual(result["text"], "")
        self.assertEqual(result["pages"], 0)

    def test_read_non_pdf_file_returns_empty_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_pdf = Path(tmp) / "fake.pdf"
            fake_pdf.write_text("这不是 PDF 内容", encoding="utf-8")
            reader = PDFReader()
            result = reader.read_pdf(fake_pdf)
            # 无本地 PDF 库时返回空结果
            self.assertEqual(result["pages"], 0)


if __name__ == "__main__":
    unittest.main()
