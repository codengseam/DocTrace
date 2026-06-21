"""网页搜索工具。

支持真实搜索 API（Google Custom Search）和 duckduckgo-search 库；
读取 /workspace/config.yaml 中的 trusted_domains 白名单进行过滤。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from ..utils.config import load_config

logger = logging.getLogger(__name__)


class WebSearch:
    """执行网页搜索并按可信域白名单过滤结果。"""

    def __init__(
        self,
        config_path: Path = Path("/workspace/config.yaml"),
        trusted_domains: list[str] | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = load_config(self.config_path) if self.config_path.exists() else {}
        self.trusted_domains: list[str] = trusted_domains or self.config.get("trusted_domains", [])
        self.api_key: Optional[str] = os.getenv("GOOGLE_SEARCH_API_KEY") or self.config.get(
            "google_search_api_key"
        )
        self.search_engine_id: Optional[str] = os.getenv("GOOGLE_CX") or self.config.get(
            "google_search_engine_id"
        )

    def _search_google(self, query: str, num_results: int) -> list[dict]:
        """使用 Google Custom Search API 搜索。"""
        if not self.api_key or not self.search_engine_id:
            return []

        try:
            params = urllib.parse.urlencode(
                {
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "q": query,
                    "num": min(num_results, 10),
                }
            )
            url = f"https://www.googleapis.com/customsearch/v1?{params}"
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            items = data.get("items", [])
            results = []
            for item in items:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    }
                )
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Custom Search failed: %s", exc)
            return []

    def _search_duckduckgo(self, query: str, num_results: int) -> list[dict]:
        """使用 duckduckgo-search 库搜索。"""
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            logger.warning("duckduckgo-search not installed")
            return []

        try:
            with DDGS() as ddgs:
                responses = ddgs.text(query, max_results=num_results)
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                    for r in responses
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("DuckDuckGo search failed: %s", exc)
            return []

    def search(self, query: str, num_results: int = 5) -> list[dict]:
        """执行网页搜索，优先使用真实 API，否则 fallback 到 DuckDuckGo。

        Args:
            query: 搜索关键词。
            num_results: 期望返回结果数量。

        Returns:
            包含 title、url、snippet 的字典列表。
        """
        results = self._search_google(query, num_results)
        if results:
            logger.debug("Using Google Custom Search results")
            return results

        results = self._search_duckduckgo(query, num_results)
        if results:
            logger.debug("Using DuckDuckGo search results")
            return results

        logger.warning("No search backend available for query: %s", query)
        return []

    def filter_trusted(self, results: list[dict] | list[str]) -> list[dict] | list[str]:
        """只保留域名在白名单内的结果；白名单为空则返回全部。

        支持传入结果字典列表（含 ``url`` 键）或 URL 字符串列表。
        """
        if not self.trusted_domains:
            return results

        trusted = {d.lower().lstrip("www.") for d in self.trusted_domains}
        filtered: list[Any] = []
        for result in results:
            if isinstance(result, dict):
                url = result.get("url", "")
            else:
                url = str(result)
            hostname = urlparse(url).hostname or ""
            if hostname:
                hostname = hostname.lower().lstrip("www.")
                if hostname in trusted:
                    filtered.append(result)
        return filtered

    def search_trusted(self, query: str, num_results: int = 5) -> list[dict]:
        """组合 search + filter_trusted。"""
        return self.filter_trusted(self.search(query, num_results))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    searcher = WebSearch()
    print("Trusted domains:", searcher.trusted_domains)

    results = searcher.search("资治通鉴 商鞅变法", num_results=3)
    print("Raw results:", results)

    trusted = searcher.filter_trusted(results)
    print("Trusted results:", trusted)
