#!/usr/bin/env python3
"""检查 output/ 目录下是否存在内容重复的 Markdown 笔记。

忽略 YAML frontmatter，仅对正文做 SHA256 哈希分组。
有重复时打印分组并以退出码 1 结束；无重复则退出码 0。
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
FRONTMATTER_PATTERN = re.compile(rb"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _note_body(path: Path) -> bytes:
    """读取 md 文件并去掉 frontmatter 后的正文。"""
    content = path.read_bytes()
    return FRONTMATTER_PATTERN.sub(b"", content, count=1).strip()


def find_duplicates() -> dict[str, list[str]]:
    """返回 {sha256: [相对路径列表]}，仅包含重复组。"""
    groups: dict[str, list[str]] = {}
    if not OUTPUT_DIR.exists():
        return groups
    for md_path in sorted(OUTPUT_DIR.rglob("*.md")):
        rel = md_path.relative_to(ROOT)
        body = _note_body(md_path)
        # 空文件或只有 frontmatter 的文件也参与分组
        h = hashlib.sha256(body).hexdigest()
        groups.setdefault(h, []).append(str(rel).replace("\\", "/"))
    return {h: files for h, files in groups.items() if len(files) > 1}


def main(argv: list[str] | None = None) -> int:
    dups = find_duplicates()
    if not dups:
        print("✅ output/ 下未发现重复的 Markdown 文件。")
        return 0

    print(f"❌ 发现 {len(dups)} 组重复 Markdown 文件（按正文内容）：\n")
    for idx, files in enumerate(sorted(dups.values()), 1):
        print(f"组 {idx}:")
        for f in files:
            print(f"  - {f}")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
