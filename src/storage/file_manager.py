"""本地 Markdown 讲书笔记的文件路径与 IO 管理。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - 可选依赖
    yaml = None  # type: ignore


DEFAULT_CONFIG_PATH = Path("/workspace/config.yaml")
DEFAULT_OUTPUT_DIR = Path("/workspace/output")


def _load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """读取 ``config.yaml``，无 PyYAML 时做最简单的顶层解析。"""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except Exception:
            return {}
    config: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
        config[key] = value
    return config


def _simple_yaml_dump(data: dict[str, Any]) -> str:
    """无 PyYAML 时的极简 YAML 序列化，支持标量、列表和一层嵌套字典。"""

    def _dump_value(value: Any, indent: int = 0) -> str:
        prefix = "  " * indent
        if isinstance(value, dict):
            return "\n".join(f"{prefix}{k}:{_dump_value(v, indent + 1)}" for k, v in value.items())
        if isinstance(value, list):
            if not value:
                return " []"
            items = "\n".join(f"{prefix}- {_dump_value(v, indent + 1).lstrip()}" for v in value)
            return "\n" + items
        if value is None:
            return ""
        text = str(value)
        if any(c in text for c in [":", "#", "'", '"', "\n", "["]):
            text = f'"{text.replace(chr(34), chr(92) + chr(34))}"'
        return f" {text}"

    return "\n".join(f"{k}:{_dump_value(v, 0)}" for k, v in data.items())


def _parse_simple_value(value: str) -> Any:
    """将简单标量解析为 bool/int/float/list/str。"""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")


class FileManager:
    """管理讲书笔记的输出路径、目录创建、文件名规范与 Markdown 读写。

    参数:
        output_dir: 输出根目录。为 ``None`` 时读取 ``config.yaml`` 中的
            ``output_dir``，默认 ``/workspace/output``。
        config_path: 配置文件路径，默认 ``/workspace/config.yaml``。
    """

    def __init__(self, output_dir: str | Path | None = None, config_path: str | Path = DEFAULT_CONFIG_PATH):
        if output_dir is not None:
            self.output_dir = Path(output_dir).expanduser()
        else:
            config = _load_config(Path(config_path))
            root = config.get("output_dir") if isinstance(config.get("output_dir"), str) else None
            self.output_dir = Path(root).expanduser().resolve() if root else DEFAULT_OUTPUT_DIR

    def get_output_path(self, book: str, chapter: str, event: str) -> Path:
        """返回 ``output_dir / 书名 / 章节_事件.md``。"""
        safe_book = self.sanitize_filename(book)
        safe_chapter = self.sanitize_filename(chapter)
        safe_event = self.sanitize_filename(event)
        return self.output_dir / safe_book / f"{safe_chapter}_{safe_event}.md"

    def ensure_dir(self, path: Path) -> Path:
        """确保路径所在目录存在，返回原路径。"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """将字符串转为安全的中文文件名。

        - 移除 Windows / Linux 非法字符与大部分特殊符号
        - 保留中文、字母、数字、下划线、连字符、句点（用于扩展名）
        - 空白替换为下划线，并合并连续下划线
        """
        name = name.strip()
        # 保留中文、日文、韩文、字母、数字、下划线、连字符、句点、空格
        safe = re.sub(r"[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af._-]", "_", name)
        safe = re.sub(r"\s+", "_", safe)
        safe = re.sub(r"_+", "_", safe)
        safe = safe.strip("_-")
        return safe or "untitled"

    def read_markdown(self, path: Path) -> dict[str, Any]:
        """读取 Markdown 文件，分离 frontmatter 和正文。

        返回:
            ``{"frontmatter": dict, "content": str}``
        """
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        return split_markdown(text)

    def write_markdown(self, path: Path, content: str, metadata: dict[str, Any] | None = None) -> Path:
        """写入 Markdown，自动附加 YAML frontmatter，必要时创建父目录。

        返回:
            写入后的绝对路径。
        """
        path = self.ensure_dir(Path(path))
        if metadata:
            fm_body = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) if yaml else _simple_yaml_dump(metadata)
            text = f"---\n{fm_body}---\n\n{content.lstrip()}"
        else:
            text = content
        path.write_text(text, encoding="utf-8")
        return path.resolve()


def split_markdown(text: str) -> dict[str, Any]:
    """切分 Markdown 文本的 frontmatter 与正文。"""
    if not text.startswith("---"):
        return {"frontmatter": {}, "content": text}

    parts = text.split("---", 2)
    if len(parts) < 3 or parts[1].strip() == "":
        return {"frontmatter": {}, "content": text}

    fm_text = parts[1].strip()
    content = parts[2].lstrip("\n")

    if yaml is not None:
        try:
            frontmatter = yaml.safe_load(fm_text) or {}
        except Exception:
            frontmatter = _parse_simple_frontmatter(fm_text)
    else:
        frontmatter = _parse_simple_frontmatter(fm_text)

    return {"frontmatter": frontmatter, "content": content}


def _parse_simple_frontmatter(text: str) -> dict[str, Any]:
    """无 YAML 库时解析简单 frontmatter（顶层标量/列表）。"""
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("- "):
            if current_key is not None:
                value = line[2:].strip().strip('"').strip("'")
                if not isinstance(result[current_key], list):
                    result[current_key] = []
                result[current_key].append(value)
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            result[current_key] = _parse_simple_value(value)
    return result


if __name__ == "__main__":
    fm = FileManager()
    out = fm.get_output_path("资治通鉴", "周纪二", "商鞅变法")
    print("输出路径:", out)

    written = fm.write_markdown(
        out,
        "## 讲事情\n\n商鞅入秦...\n",
        {"title": "商鞅变法", "book": "资治通鉴", "chapter": "周纪二", "event": "商鞅变法"},
    )
    print("已写入:", written)

    data = fm.read_markdown(written)
    print("frontmatter:", data["frontmatter"])
    print("正文长度:", len(data["content"]))
