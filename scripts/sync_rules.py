"""同步项目写作规则文件。

主库：.trae/rules/rules.md（Trae 自动加载）
从库：RULES.md（根目录，兼容其他 IDE/工具）

用法：
    python scripts/sync_rules.py

修改规则时请编辑 .trae/rules/rules.md，然后运行此脚本同步到 RULES.md。
"""

from pathlib import Path


PRIMARY = Path(".trae/rules/rules.md")
REPLICA = Path("RULES.md")
REPLICA_HEADER = (
    "> **注意**：本文件是 `.trae/rules/rules.md` 的从库副本。"
    "Trae 优先读取 `.trae/rules/rules.md`，其他 IDE/工具可读取本文件。"
    "修改规则时请编辑 `.trae/rules/rules.md`，然后运行 "
    "`python scripts/sync_rules.py` 同步到本文件。\n\n"
)


def sync() -> None:
    if not PRIMARY.exists():
        raise FileNotFoundError(f"主库规则文件不存在：{PRIMARY}")

    primary_content = PRIMARY.read_text(encoding="utf-8")

    # 移除旧的通知头（如果存在），避免重复追加
    if "> **注意**：本文件是 `" in primary_content:
        lines = primary_content.splitlines()
        # 找到通知头结束后的正文起始位置
        start_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("# 项目写作规则"):
                start_idx = i
                break
        primary_content = "\n".join(lines[start_idx:])

    replica_content = REPLICA_HEADER + primary_content
    REPLICA.write_text(replica_content, encoding="utf-8")
    print(f"已同步：{PRIMARY} -> {REPLICA}")


if __name__ == "__main__":
    sync()
