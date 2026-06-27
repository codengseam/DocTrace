"""scripts/check_loop_log.py 的单元测试。

覆盖 6 个用例：
1. 合法 loop_log 通过
2. 日期非倒序失败
3. 非法 #lesson slug 失败
4. 化石标题未迁出（strict 阻断）
5. #lesson 计数告警（P3 不阻断）
6. --strict 模式阻断 P3
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.check_loop_log import (  # noqa: E402
    check_date_descending,
    check_fossil_migrated,
    check_index_anchors,
    check_lesson_count_warning,
    check_lesson_slug_legal,
    run,
)


VALID_LOOP_LOG = """# LoopAgent 循环日志

> 历史测评框架与评分表见 [docs/archive/loop_log_fossils.md](archive/loop_log_fossils.md)。

## 索引区

### 最近 10 条沉淀（按日期倒序）
- [2026-06-26 示例 A](#L16)
- [2026-06-25 示例 B](#L24)

### 主题锚点
- `#reader_interaction`：阅读器/沉浸/翻页

---

## 2026-06-26 示例 A

正文 A。

**教训标签**：`#lesson: git_hygiene`

---

## 2026-06-25 示例 B

正文 B。

**教训标签**：`#lesson: book_structure`
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "loop_log.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------- 1. 合法 loop_log 通过 ----------


def test_valid_loop_log_passes(tmp_path):
    """构造合法 loop_log 内容，run() 返回 0。"""
    p = _write(tmp_path, VALID_LOOP_LOG)
    rc = run(p, strict=False)
    assert rc == 0


# ---------- 2. 日期非倒序失败 ----------


def test_date_not_descending_fails(tmp_path):
    """日期乱序（06-25 在 06-26 之上）应导致核心校验失败。"""
    content = """# LoopAgent 循环日志

## 索引区

---

## 2026-06-25 早的在上

正文。

**教训标签**：`#lesson: git_hygiene`

---

## 2026-06-26 晚的在下

正文。

**教训标签**：`#lesson: git_hygiene`
"""
    p = _write(tmp_path, content)
    errors = check_date_descending(p.read_text(encoding="utf-8"))
    assert any("日期非倒序" in e for e in errors), errors
    rc = run(p, strict=False)
    assert rc == 1


# ---------- 3. 非法 #lesson slug 失败 ----------


def test_invalid_lesson_slug_fails(tmp_path):
    """非法 slug（如 random_text）应触发 P1 失败。"""
    content = """# LoopAgent 循环日志

## 索引区

---

## 2026-06-26 示例

正文。

**教训标签**：`#lesson: random_text`
"""
    p = _write(tmp_path, content)
    errors = check_lesson_slug_legal(p.read_text(encoding="utf-8"))
    assert any("random_text" in e for e in errors), errors
    rc = run(p, strict=False)
    assert rc == 1


# ---------- 4. 化石标题未迁出（strict 阻断） ----------


def test_fossil_section_not_migrated_fails(tmp_path):
    """loop_log.md 中若残留 ## 一、测评框架 等化石标题，--strict 应阻断。"""
    content = """# LoopAgent 循环日志

## 一、测评框架

(化石内容)

## 2026-06-26 示例

正文。

**教训标签**：`#lesson: git_hygiene`
"""
    p = _write(tmp_path, content)
    warnings = check_fossil_migrated(p.read_text(encoding="utf-8"))
    assert any("化石标题未迁出" in w for w in warnings), warnings
    # 非 strict 不阻断
    assert run(p, strict=False) == 0
    # strict 阻断
    assert run(p, strict=True) == 1


# ---------- 5. #lesson 计数告警（P3 不阻断） ----------


def test_lesson_count_warning_p3(tmp_path):
    """同一 slug 出现 ≥3 次且未标'已入checklist: yes'应 P3 告警，但退出码 0。"""
    content = """# LoopAgent 循环日志

## 索引区

---

## 2026-06-26 A

正文。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-25 B

正文。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-24 C

正文。

**教训标签**：`#lesson: book_structure`
"""
    p = _write(tmp_path, content)
    warnings = check_lesson_count_warning(p.read_text(encoding="utf-8"))
    assert any("book_structure" in w and "≥3" in w for w in warnings), warnings
    # 非 strict 退出码 0
    assert run(p, strict=False) == 0


# ---------- 6. --strict 模式阻断 P3 ----------


def test_strict_mode_blocks_p3(tmp_path):
    """--strict 模式下 P3 告警也阻断退出码。"""
    # 复用用例 5 的内容：book_structure 出现 3 次
    content = """# LoopAgent 循环日志

## 索引区

---

## 2026-06-26 A

正文。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-25 B

正文。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-24 C

正文。

**教训标签**：`#lesson: book_structure`
"""
    p = _write(tmp_path, content)
    # strict 应阻断
    assert run(p, strict=True) == 1


# ---------- 补充：索引锚点校验 ----------


def test_index_anchor_target_must_be_h2(tmp_path):
    """索引锚点指向的行不是 H2 应触发 P3 告警。"""
    # L8 不是 ## 开头
    content = """# LoopAgent 循环日志

## 索引区

### 最近 10 条沉淀（按日期倒序）
- [2026-06-26 示例](#L8)

---

正文段落（L8 在这里）。

## 2026-06-26 示例

正文。

**教训标签**：`#lesson: git_hygiene`
"""
    p = _write(tmp_path, content)
    warnings = check_index_anchors(p.read_text(encoding="utf-8"))
    assert any("指向的不是 H2" in w for w in warnings), warnings
