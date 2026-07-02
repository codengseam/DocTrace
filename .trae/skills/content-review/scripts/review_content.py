#!/usr/bin/env python3
"""LLM 三视角质检 skill 目录便捷封装。

实际实现位于 /workspace/scripts/review_content.py，此处为 skill 自洽入口。
运行需 LLM_API_KEY + langgraph 已安装；沙箱默认无则降级为 Task 工具启动 subagent。

用法：
    python .trae/skills/content-review/scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md
    DEEP_READING_MOCK=1 python .trae/skills/content-review/scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_REAL_SCRIPT = _ROOT / "scripts" / "review_content.py"

if __name__ == "__main__":
    import runpy
    sys.argv[0] = str(_REAL_SCRIPT)
    runpy.run_path(str(_REAL_SCRIPT), run_name="__main__")
