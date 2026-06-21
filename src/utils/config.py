"""配置与环境变量加载工具。"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any


def load_config(path: Path = Path("config.yaml")) -> dict[str, Any]:
    """读取 YAML 配置文件。

    若已安装 PyYAML，则使用标准 YAML 解析；否则使用内置的简单解析器
    处理本项目用到的基本键值（字符串、列表、单层字典）。
    """
    try:
        import yaml

        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        warnings.warn("PyYAML 未安装，使用内置简单 YAML 解析器", RuntimeWarning)
    except FileNotFoundError:
        warnings.warn(f"配置文件不存在: {path}", RuntimeWarning)
        return {}

    return _parse_simple_yaml(path)


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """极简 YAML 解析，仅支持顶层 key: value / list / dict。"""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[Any] | None = None
    current_dict: dict[str, Any] | None = None

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.split("#", 1)[0].rstrip("\n\r")
            if not line.strip():
                continue

            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            if indent == 0:
                current_key = None
                current_list = None
                current_dict = None
                if ":" not in stripped:
                    continue
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                if value == "":
                    result[key] = None
                    current_key = key
                elif value.startswith('"') and value.endswith('"'):
                    result[key] = value[1:-1]
                elif value in ("true", "True"):
                    result[key] = True
                elif value in ("false", "False"):
                    result[key] = False
                elif re.fullmatch(r"-?\d+", value):
                    result[key] = int(value)
                else:
                    result[key] = value
                continue

            if current_key is None:
                continue

            if stripped.startswith("-"):
                item = stripped[1:].strip()
                if item.startswith('"') and item.endswith('"'):
                    item = item[1:-1]
                if current_list is None:
                    current_list = []
                    result[current_key] = current_list
                current_list.append(item)
            elif ":" in stripped:
                sub_key, _, sub_value = stripped.partition(":")
                sub_key = sub_key.strip()
                sub_value = sub_value.strip()
                if sub_value.startswith('"') and sub_value.endswith('"'):
                    sub_value = sub_value[1:-1]
                if current_dict is None:
                    current_dict = {}
                    result[current_key] = current_dict
                current_dict[sub_key] = sub_value

    return result


def load_env(path: Path = Path(".env")) -> dict[str, str]:
    """读取 .env 文件为键值对字典。

    忽略空行与以 # 开头的注释行；值两端的引号会被去除。
    """
    env: dict[str, str] = {}
    if not path.exists():
        return env

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            env[key] = value

    return env
