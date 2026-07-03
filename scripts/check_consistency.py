#!/usr/bin/env python3
"""一致性检测根目录入口（便捷封装）。

实际实现位于 .trae/skills/content-review/scripts/check_consistency.py，
此处仅为与 scripts/check_char_count.py 等保持一致的根目录入口。

用法：
    python scripts/check_consistency.py --file output/史记/汉纪/07_鸿门宴.md
    python scripts/check_consistency.py --dir output/ --strict
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 直接复用 skill 目录下的实现
_SKILL_SCRIPT = _ROOT / ".trae" / "skills" / "content-review" / "scripts" / "check_consistency.py"

if __name__ == "__main__":
    # 把 skill 脚本的目录加入 path 并 exec
    import runpy
    sys.argv[0] = str(_SKILL_SCRIPT)
    runpy.run_path(str(_SKILL_SCRIPT), run_name="__main__")
