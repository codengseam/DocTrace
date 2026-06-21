"""Obsidian Vault 写入工具。

优先通过 MCP 服务器 `mcp_mcp-obsidian` 写入/更新笔记；
MCP 不可用时 fallback 为直接文件系统写入到 vault 路径。
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..utils.config import load_config

logger = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path("/workspace/config.yaml")


class ObsidianWriter:
    """将 Markdown 笔记写入 Obsidian Vault，支持 frontmatter。"""

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        mcp_server_name: Optional[str] = None,
        config_path: Path = DEFAULT_CONFIG_PATH,
    ) -> None:
        config = load_config(config_path) if config_path.exists() else {}
        self.mcp_server_name = mcp_server_name or self._resolve_mcp_server(config)
        self.vault_path = self._resolve_vault_path(vault_path, config)

    @staticmethod
    def _resolve_mcp_server(config: dict) -> str:
        """从 config.yaml 的 mcp_servers 节解析 obsidian 服务器名。"""
        mcp_servers = config.get("mcp_servers") or {}
        if isinstance(mcp_servers, dict):
            return mcp_servers.get("obsidian", "mcp_mcp-obsidian")
        return "mcp_mcp-obsidian"

    def _resolve_vault_path(self, vault_path: Optional[Path], config: dict) -> Path:
        """从参数、环境变量或 config.yaml 解析 vault 根目录。"""
        if vault_path is not None:
            return Path(vault_path)

        env_path = os.getenv("OBSIDIAN_VAULT_PATH")
        if env_path:
            return Path(env_path)

        config_vault = config.get("vault_dir")
        if config_vault:
            return Path(config_vault).expanduser().resolve()

        return Path("/workspace/output/obsidian")

    def _to_frontmatter(self, metadata: dict) -> str:
        """将 metadata 字典转为 YAML frontmatter。"""
        if not metadata:
            return ""

        try:
            import yaml  # type: ignore

            yaml_text = yaml.safe_dump(
                metadata,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
            return f"---\n{yaml_text}---\n\n"
        except ImportError:
            logger.debug("PyYAML not installed, using manual frontmatter")
            lines = ["---"]
            for key, value in metadata.items():
                if isinstance(value, list):
                    lines.append(f"{key}:")
                    for item in value:
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"{key}: {value}")
            lines.append("---\n")
            return "\n".join(lines) + "\n"

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """解析已有 frontmatter，返回 (metadata, body)。"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n?"
        match = re.match(pattern, content, re.DOTALL)
        if not match:
            return {}, content

        raw = match.group(1)
        body = content[match.end() :]

        try:
            import yaml  # type: ignore

            return yaml.safe_load(raw) or {}, body
        except ImportError:
            logger.debug("PyYAML not installed, parsing frontmatter manually")
            return self._parse_simple_frontmatter(raw), body

    @staticmethod
    def _parse_simple_frontmatter(raw: str) -> dict:
        """无 PyYAML 时解析简单 frontmatter（顶层标量/列表）。"""
        result: dict = {}
        current_key: str | None = None
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                if current_key is not None:
                    item = stripped[2:].strip().strip('"').strip("'")
                    if not isinstance(result.get(current_key), list):
                        result[current_key] = []
                    result[current_key].append(item)
                continue
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                current_key = key.strip()
                result[current_key] = value.strip().strip('"').strip("'")
        return result

    def _build_note(self, content: str, metadata: Optional[dict]) -> str:
        """合并 metadata frontmatter 与正文。"""
        metadata = metadata or {}
        if "created_at" not in metadata:
            metadata["created_at"] = datetime.now().isoformat(timespec="seconds")
        if "updated_at" not in metadata:
            metadata["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return self._to_frontmatter(metadata) + content

    def merge_frontmatter(self, content: str, metadata: dict) -> str:
        """将 metadata 合并到已有内容的 frontmatter 中，新值覆盖旧值。

        Args:
            content: 已有 Markdown 内容（可包含 frontmatter）。
            metadata: 需要合并或覆盖的 frontmatter 字段。

        Returns:
            合并后的完整 Markdown 字符串。
        """
        existing_meta, body = self._parse_frontmatter(content)
        merged = {**existing_meta, **metadata}
        merged["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return self._to_frontmatter(merged) + body

    def _write_via_mcp(
        self, note_path: str, content: str, metadata: Optional[dict]
    ) -> Optional[dict]:
        """尝试通过 MCP 服务器写入笔记。

        MCP API（``mcp.Client`` / ``client.call``）在当前环境中不可用，
        此处通过 try/except 优雅降级，返回 ``None`` 以触发文件系统 fallback。
        """
        try:
            import mcp  # type: ignore

            client = mcp.Client()
            # 若 content 已包含 frontmatter 且未传入 metadata，直接发送原始内容，
            # 避免重复拼接 frontmatter。
            if metadata is None and content.lstrip().startswith("---"):
                note_content = content
            else:
                note_content = self._build_note(content, metadata)
            result = client.call(
                server=self.mcp_server_name,
                tool="write_note",
                arguments={
                    "path": note_path,
                    "content": note_content,
                },
            )
            return {
                "success": True,
                "path": note_path,
                "updated": False,
                "source": f"mcp:{self.mcp_server_name}",
                "detail": result,
            }
        except Exception as exc:  # noqa: BLE001
            logger.info("MCP not available, falling back to file system: %s", exc)
            return None

    def _full_path(self, note_path: str) -> Path:
        """将 vault 内相对路径转为绝对路径。"""
        relative = Path(note_path)
        if relative.is_absolute():
            return relative
        return self.vault_path / relative

    def write_note(
        self, note_path: str, content: str, metadata: Optional[dict] = None
    ) -> dict:
        """写入新笔记；若 MCP 不可用则写入本地 vault 目录。

        Args:
            note_path: vault 内相对路径，如 `历史/资治通鉴/周纪二_商鞅变法.md`。
            content: Markdown 正文。
            metadata: 将转为 YAML frontmatter 的字典。

        Returns:
            {"success": bool, "path": str, "updated": bool, "source": str}
        """
        mcp_result = self._write_via_mcp(note_path, content, metadata)
        if mcp_result is not None:
            return mcp_result

        target = self._full_path(note_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            target.write_text(self._build_note(content, metadata), encoding="utf-8")
            return {
                "success": True,
                "path": str(target),
                "updated": False,
                "source": "filesystem",
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to write note %s: %s", target, exc)
            return {
                "success": False,
                "path": str(target),
                "updated": False,
                "source": "filesystem",
                "error": str(exc),
            }

    def update_note(
        self, note_path: str, content: str, metadata: Optional[dict] = None
    ) -> dict:
        """更新已有笔记；不存在则创建。

        若笔记已存在，新 metadata 会与旧 frontmatter 合并，新值覆盖旧值。
        """
        target = self._full_path(note_path)
        exists = target.exists()

        if exists:
            try:
                old_note = target.read_text(encoding="utf-8")
                old_meta, _ = self._parse_frontmatter(old_note)
                merged_meta = {**old_meta, **(metadata or {})}
                merged_meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
                new_content = self._to_frontmatter(merged_meta) + content
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse existing note %s: %s", target, exc)
                new_content = self._build_note(content, metadata)
        else:
            new_content = self._build_note(content, metadata)

        mcp_result = self._write_via_mcp(note_path, new_content, metadata=None)
        if mcp_result is not None:
            mcp_result["updated"] = exists
            return mcp_result

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(new_content, encoding="utf-8")
            return {
                "success": True,
                "path": str(target),
                "updated": exists,
                "source": "filesystem",
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to update note %s: %s", target, exc)
            return {
                "success": False,
                "path": str(target),
                "updated": False,
                "source": "filesystem",
                "error": str(exc),
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    writer = ObsidianWriter()
    result = writer.write_note(
        "历史/资治通鉴/周纪二_商鞅变法.md",
        "## 讲事情\n\n商鞅变法始于秦孝公求贤。\n",
        metadata={"title": "周纪二·商鞅变法", "book": "资治通鉴", "chapter": "周纪二"},
    )
    print(result)

    update_result = writer.update_note(
        "历史/资治通鉴/周纪二_商鞅变法.md",
        "## 讲事情\n\n商鞅变法始于秦孝公求贤，商鞅以徙木立信。\n",
        metadata={"event": "商鞅变法"},
    )
    print(update_result)
