import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]
        default = ""
        if ":-" in inner:
            env_key, default = inner.split(":-", 1)
        else:
            env_key = inner
        return os.getenv(env_key, default)
    return value


def _deep_resolve(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_resolve(v) for v in obj]
    return _resolve_env(obj)


class Config:
    def __init__(self, config_path: str | Path | None = None) -> None:
        load_dotenv(_PROJECT_ROOT / ".env")
        self._config_path = Path(config_path) if config_path else _PROJECT_ROOT / "config.yaml"
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        with open(self._config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return _deep_resolve(raw)

    @property
    def llm(self) -> dict[str, Any]:
        return self._data.get("llm", {})

    @property
    def paths(self) -> dict[str, Any]:
        return self._data.get("paths", {})

    @property
    def rules(self) -> dict[str, Any]:
        return self._data.get("rules", {})

    def path(self, name: str) -> Path:
        p = self.paths.get(name, name)
        path = Path(p)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path


def get_config() -> Config:
    return Config()
