"""讲书笔记元数据的持久化存储，支持按书/章节/事件检索。"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .file_manager import FileManager


DEFAULT_STORE_PATH = Path("/workspace/.cache/metadata_store.json")


class MetadataStore:
    """以 JSON 文件为后端的笔记元数据存储，线程安全。

    参数:
        store_path: 元数据文件路径，默认 ``/workspace/.cache/metadata_store.json``。
    """

    def __init__(self, store_path: str | Path | None = None):
        self.path = Path(store_path or DEFAULT_STORE_PATH)
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self.load()

    @staticmethod
    def _key(record: dict[str, Any]) -> str:
        """唯一键：书名::章节::事件。"""
        return "::".join(str(record.get(k, "")) for k in ("book", "chapter", "event"))

    def add_or_update(
        self, key_or_record: str | dict[str, Any], record: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """添加或更新一条笔记元数据记录，自动维护 ``created_at`` / ``updated_at``。

        支持两种调用方式：
            - ``add_or_update(record_dict)``：自动根据 book/chapter/event 生成键。
            - ``add_or_update(key, record_dict)``：使用传入的键。
        """
        now = datetime.now().isoformat(timespec="seconds")

        if isinstance(key_or_record, str) and record is not None:
            key = key_or_record
            data = record
            add_timestamps = False
        elif isinstance(key_or_record, dict):
            key = self._key(key_or_record)
            data = key_or_record
            add_timestamps = True
        else:
            raise TypeError("add_or_update 接受 (record) 或 (key, record) 两种调用方式")

        with self._lock:
            existing = self._records.get(key)
            if existing and add_timestamps:
                merged = {**existing, **data, "updated_at": now}
            elif existing:
                merged = dict(data)
            else:
                merged = dict(data)
                if add_timestamps:
                    merged.setdefault("created_at", now)
                    merged.setdefault("updated_at", now)
            self._records[key] = merged
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._save_unsafe()
        return merged

    def get(
        self, book_or_key: str, chapter: str | None = None, event: str | None = None
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """查询元数据记录。

        - ``get(key)``：按唯一键返回单条记录；不存在返回 ``None``。
        - ``get(book, chapter=None, event=None)``：按书名/章节/事件筛选，返回列表。
        """
        if chapter is None and event is None:
            with self._lock:
                return self._records.get(book_or_key)

        with self._lock:
            records = list(self._records.values())

        results = records
        if book_or_key is not None:
            results = [r for r in results if r.get("book") == book_or_key]
        if chapter is not None:
            results = [r for r in results if r.get("chapter") == chapter]
        if event is not None:
            results = [r for r in results if r.get("event") == event]
        return results

    def list_books(self) -> list[str]:
        """返回所有书籍名称，排序后返回。"""
        with self._lock:
            books = {r["book"] for r in self._records.values() if r.get("book")}
        return sorted(books)

    def list_chapters(self, book: str) -> list[str]:
        """返回某本书下的所有章节名称，排序后返回。"""
        with self._lock:
            chapters = {
                r["chapter"]
                for r in self._records.values()
                if r.get("book") == book and r.get("chapter")
            }
        return sorted(chapters)

    def _save_unsafe(self) -> None:
        """实际写入 JSON，调用方需自行持有锁。"""
        data = list(self._records.values())
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save(self) -> None:
        """将当前记录持久化到 JSON 文件。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._save_unsafe()

    def load(self) -> None:
        """从 JSON 文件加载记录；文件不存在或损坏时初始化为空。"""
        if not self.path.exists():
            self._records = {}
            return
        try:
            with self._lock:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if isinstance(data, list):
                self._records = {
                    self._key(r): r
                    for r in data
                    if all(r.get(k) for k in ("book", "chapter", "event"))
                }
            else:
                self._records = {}
        except Exception:
            self._records = {}

    def build_from_output_dir(self, output_dir: str | Path | None = None) -> dict[str, Any]:
        """扫描 ``output/`` 目录，从现有 Markdown 的 frontmatter 重建索引。

        返回:
            ``{"scanned": 扫描路径, "count": 新增/更新记录数}``
        """
        root = Path(output_dir) if output_dir else Path("/workspace/output")
        fm = FileManager(output_dir=str(root))
        count = 0
        if not root.exists():
            return {"scanned": str(root), "count": 0}

        for path in root.rglob("*.md"):
            try:
                data = fm.read_markdown(path)
                fm_data = data["frontmatter"]
                if not all(fm_data.get(k) for k in ("book", "chapter", "event")):
                    continue
                record = {
                    "book": fm_data.get("book"),
                    "chapter": fm_data.get("chapter"),
                    "event": fm_data.get("event"),
                    "title": fm_data.get("title") or path.stem,
                    "output_path": str(path.resolve()),
                    "vault_path": fm_data.get("vault_path"),
                    "created_at": fm_data.get("created_at"),
                    "updated_at": fm_data.get("updated_at"),
                    "sources": fm_data.get("sources") or fm_data.get("source_agents") or [],
                    "tags": fm_data.get("tags") or [],
                }
                self.add_or_update(record)
                count += 1
            except Exception:
                continue
        return {"scanned": str(root), "count": count}


if __name__ == "__main__":
    store = MetadataStore()
    rec = {
        "book": "资治通鉴",
        "chapter": "周纪一",
        "event": "三家分晋",
        "title": "三家分晋",
        "output_path": "/workspace/output/资治通鉴/周纪一_三家分晋.md",
    }
    store.add_or_update(rec)
    print("书目:", store.list_books())
    print("章节:", store.list_chapters("资治通鉴"))
    print("查询结果:", store.get("资治通鉴", "周纪一", "三家分晋"))
