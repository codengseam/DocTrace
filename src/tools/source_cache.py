"""资料来源缓存。

记录每次查询/事件使用过的资料，避免重复搜索。
数据以 JSON 形式持久化到 /workspace/.cache/source_cache.json，
内部使用 threading.RLock 保证线程安全。
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from ..utils.config import load_config

logger = logging.getLogger(__name__)
DEFAULT_CACHE_PATH = Path("/workspace/.cache/source_cache.json")


def _resolve_cache_path(cache_path: Path | None) -> Path:
    """解析来源缓存路径，优先使用传入值，否则读取 config.yaml 的 cache_dir。"""
    if cache_path is not None:
        return Path(cache_path)
    config = load_config(Path("/workspace/config.yaml"))
    cache_dir = config.get("cache_dir")
    if cache_dir:
        return Path(cache_dir).expanduser().resolve() / "source_cache.json"
    return DEFAULT_CACHE_PATH


class SourceCache:
    """按 event_key 记录已使用来源的线程安全缓存。"""

    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = _resolve_cache_path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, list[dict]] = {}
        self._lock = threading.RLock()
        self.load()

    def _source_url(self, source: str | dict) -> str:
        """从来源对象中提取 URL，用于去重判断。"""
        if isinstance(source, dict):
            return (source.get("url") or "").strip()
        if isinstance(source, str):
            return source.strip()
        return ""

    def _normalize_source(self, source: str | dict) -> str | dict:
        """保持原始来源格式；字典则补齐字段。"""
        if isinstance(source, dict):
            return {
                "url": source.get("url", ""),
                "title": source.get("title", ""),
                "snippet": source.get("snippet", ""),
            }
        return source

    def record(self, event_key: str, source: str | dict | list[str | dict]) -> None:
        """为某个事件记录一条或多条来源。

        支持传入字符串 URL、来源字典或列表。
        """
        sources = source if isinstance(source, list) else [source]

        with self._lock:
            self._data.setdefault(event_key, [])
            for item in sources:
                url = self._source_url(item)
                if not url:
                    logger.warning("Source recorded without url for event %s", event_key)
                    continue
                if not self.exists(event_key, url):
                    self._data[event_key].append(self._normalize_source(item))
            self._save_unsafe()

    def get(self, event_key: str) -> list[str | dict] | None:
        """获取某事件已记录的所有来源；不存在返回 ``None``。"""
        with self._lock:
            if event_key not in self._data:
                return None
            return list(self._data[event_key])

    def exists(self, event_key: str, url: str) -> bool:
        """判断某事件的来源中是否已包含指定 url。"""
        target = (url or "").strip()
        if not target:
            return False

        with self._lock:
            sources = self._data.get(event_key, [])
            return any(self._source_url(s) == target for s in sources)

    def _save_unsafe(self) -> None:
        """实际写入 JSON，调用方需自行持有锁。"""
        temp_path = self.cache_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temp_path.replace(self.cache_path)

    def save(self) -> None:
        """将缓存数据写入 JSON 文件。"""
        try:
            with self._lock:
                self._save_unsafe()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save source cache: %s", exc)

    def load(self) -> None:
        """从 JSON 文件加载缓存数据。"""
        if not self.cache_path.exists():
            self._data = {}
            return

        try:
            with self._lock:
                raw = self.cache_path.read_text(encoding="utf-8")
                data = json.loads(raw) if raw.strip() else {}
                self._data = data if isinstance(data, dict) else {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load source cache: %s", exc)
            self._data = {}

    def clear(self, event_key: Optional[str] = None) -> None:
        """清空某个事件或全部缓存。"""
        with self._lock:
            if event_key is None:
                self._data.clear()
            else:
                self._data.pop(event_key, None)
            self._save_unsafe()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cache = SourceCache()
    event = "资治通鉴/周纪二/商鞅变法"

    cache.record(event, {"url": "https://example.com/a", "title": "示例 A", "snippet": "..."})
    cache.record(event, {"url": "https://example.com/b", "title": "示例 B", "snippet": "..."})
    cache.record(event, {"url": "https://example.com/a", "title": "重复 A", "snippet": "..."})

    print("Exists:", cache.exists(event, "https://example.com/a"))
    print("Sources:", cache.get(event))
