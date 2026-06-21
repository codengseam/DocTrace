"""本地讲书笔记与 Obsidian Vault 的同步逻辑。"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..tools.obsidian_writer import ObsidianWriter
from .file_manager import FileManager


logger = logging.getLogger(__name__)


class VaultSync:
    """将生成的 Markdown 讲书笔记同步到 Obsidian Vault，并处理更新去重。

    参数:
        vault_root: Obsidian Vault 根目录，默认从 ``OBSIDIAN_VAULT_PATH`` /
            ``config.yaml`` / ``/workspace/output/obsidian`` 读取。
        output_dir: 本地输出根目录，默认 ``/workspace/output``。
        file_manager: 可注入的 ``FileManager`` 实例。
        writer: 可注入的 ``ObsidianWriter`` 实例。
    """

    def __init__(
        self,
        vault_root: str | Path | None = None,
        output_dir: str | Path | None = None,
        file_manager: FileManager | None = None,
        writer: ObsidianWriter | None = None,
    ):
        self.fm = file_manager or FileManager(output_dir=output_dir)
        self.writer = writer or ObsidianWriter(vault_path=vault_root)

    def _vault_abs(self, relative_path: str) -> Path:
        """将 Vault 相对路径解析为绝对路径。"""
        relative_path = relative_path.strip("/\\").replace("\\", "/")
        if not relative_path:
            raise ValueError("relative_path 不能为空")
        if self.writer.vault_path is None:
            raise RuntimeError("ObsidianWriter 未配置 vault_path")
        return self.writer.vault_path / relative_path

    def sync_to_vault(self, local_path: Path, vault_relative_path: str | None = None) -> dict[str, Any]:
        """将本地 Markdown 同步到 Vault。

        去重逻辑:
            1. 若 Vault 中不存在，直接创建。
            2. 若存在，比较正文 SHA-256 hash；相同则跳过。
            3. 若 hash 不同，再比较 frontmatter 中的 ``updated_at``；相同则跳过。
            4. 否则合并更新（保留 Vault 中已有的 frontmatter 修改）。

        同步成功后，会在本地 Markdown 的 frontmatter 中记录 ``vault_path`` 和
        ``sources``（若尚未记录）。
        """
        local_path = Path(local_path)
        data = self.fm.read_markdown(local_path)
        content = data["content"]
        frontmatter = data["frontmatter"]

        if vault_relative_path is None:
            try:
                rel = local_path.relative_to(self.fm.output_dir)
            except ValueError:
                rel = Path(local_path.name)
            vault_relative_path = str(rel).replace("\\", "/")

        # 将实际使用的 Vault 路径与来源回写到本地 frontmatter
        frontmatter.setdefault("vault_path", vault_relative_path)
        if not frontmatter.get("sources"):
            frontmatter["sources"] = frontmatter.get("source_agents", [])
        self.fm.write_markdown(local_path, content, frontmatter)

        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        exists = self.note_exists(vault_relative_path)

        if exists:
            existing = self.fm.read_markdown(self._vault_abs(vault_relative_path))
            existing_hash = hashlib.sha256(existing["content"].encode("utf-8")).hexdigest()

            if existing_hash == current_hash:
                logger.info("Vault 笔记未变化，跳过同步: %s", vault_relative_path)
                return {
                    "status": "skipped",
                    "reason": "content_hash_match",
                    "vault_path": vault_relative_path,
                }

            existing_updated = existing["frontmatter"].get("updated_at") or existing["frontmatter"].get("created_at")
            new_updated = frontmatter.get("updated_at") or frontmatter.get("created_at")
            if existing_updated and new_updated and existing_updated == new_updated:
                logger.info("Vault 笔记 updated_at 未变化，跳过同步: %s", vault_relative_path)
                return {
                    "status": "skipped",
                    "reason": "updated_at_unchanged",
                    "vault_path": vault_relative_path,
                }

            # 笔记已存在且内容有变化：使用 update_note 合并 frontmatter，
            # 避免覆盖 Vault 中已有的 frontmatter 修改。
            result = self.writer.update_note(vault_relative_path, content, frontmatter)
            status = "updated"
        else:
            result = self.writer.write_note(vault_relative_path, content, frontmatter)
            status = "created"
        logger.info("同步到 Vault: %s (%s)", vault_relative_path, status)
        return {
            "status": status,
            "vault_path": vault_relative_path,
            "details": result,
        }

    def sync_book_index(self, book: str, notes: list[Path]) -> dict[str, Any]:
        """为某本书生成/更新 MOC（Map of Content）索引笔记。

        索引路径: ``{书名}/MOC.md``
        """
        safe_book = self.fm.sanitize_filename(book)
        moc_path = f"{safe_book}/MOC.md"

        now = datetime.now().isoformat(timespec="seconds")
        lines = [f"# 《{book}》讲书笔记索引", "", "## 章节", ""]

        for note in sorted(notes):
            note_data = self.fm.read_markdown(note)
            fm = note_data["frontmatter"]
            title = fm.get("title") or note.stem
            chapter = fm.get("chapter") or note.stem
            event = fm.get("event") or ""
            # 链接使用笔记在 Vault 内的相对路径，与 MOC 同目录时只保留文件名
            try:
                rel = note.relative_to(self.fm.output_dir)
                rel_str = str(rel).replace("\\", "/")
            except ValueError:
                rel_str = str(note)
            # MOC 位于 {book}/MOC.md，同一目录下的笔记链接无需前缀
            if "/" in rel_str:
                parts = rel_str.rsplit("/", 1)
                link = parts[1] if parts[0] == safe_book else rel_str
            else:
                link = rel_str
            lines.append(f"- [[{link}|{title}]]（{chapter} {event}）".strip())

        lines.extend(["", "## 标签", "", f"#{safe_book} #MOC"])
        moc_content = "\n".join(lines)

        metadata = {
            "title": f"《{book}》MOC",
            "book": book,
            "type": "moc",
            "created_at": now,
            "updated_at": now,
        }
        result = self.writer.write_note(moc_path, moc_content, metadata)
        status = "updated" if self.note_exists(moc_path) else "created"
        logger.info("生成 MOC 索引: %s (%s)", moc_path, status)
        return {
            "status": status,
            "vault_path": moc_path,
            "details": result,
        }

    def note_exists(self, vault_relative_path: str) -> bool:
        """判断 Vault 中是否已存在指定笔记。"""
        if self.writer.vault_path is None:
            return False
        return self._vault_abs(vault_relative_path).exists()


if __name__ == "__main__":
    fm = FileManager()
    note_path = fm.get_output_path("资治通鉴", "周纪一", "三家分晋")
    fm.write_markdown(
        note_path,
        "## 讲事情\n\n三家分晋...\n",
        {"title": "三家分晋", "book": "资治通鉴", "chapter": "周纪一", "event": "三家分晋"},
    )

    sync = VaultSync()
    result1 = sync.sync_to_vault(note_path)
    print("第一次同步:", result1)
    result2 = sync.sync_to_vault(note_path)
    print("第二次同步:", result2)

    index_result = sync.sync_book_index("资治通鉴", [note_path])
    print("MOC 索引:", index_result)
