#!/usr/bin/env python3
"""字数核对 skill 目录便捷封装。

实际实现位于 /workspace/scripts/check_char_count.py，此处为 skill 自洽入口。
用户要求"所有脚本放到 skills 目录下"，但核心实现被 tests/ 与 src/ 多处引用，
迁移会破坏包结构，故采用便捷封装模式（与 check_consistency.py 一致）。

用法：
    python .trae/skills/content-review/scripts/check_char_count.py --file output/史记/汉纪/07_鸿门宴.md
    python .trae/skills/content-review/scripts/check_char_count.py --dir output/ --strict
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_REAL_SCRIPT = _ROOT / "scripts" / "check_char_count.py"

if __name__ == "__main__":
    import runpy
    sys.argv[0] = str(_REAL_SCRIPT)
    runpy.run_path(str(_REAL_SCRIPT), run_name="__main__")
