#!/usr/bin/env bash
# 安装 HaloRead 项目的 Git hooks
# 用法：bash scripts/install-git-hooks.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SRC="$ROOT/githooks/pre-push"
HOOK_DST="$ROOT/.git/hooks/pre-push"

if [ ! -d "$ROOT/.git/hooks" ]; then
    echo "[ERROR] 未找到 .git/hooks 目录，请在项目根目录运行此脚本。"
    exit 1
fi

if [ ! -f "$HOOK_SRC" ]; then
    echo "[ERROR] 未找到 hook 源文件: $HOOK_SRC"
    exit 1
fi

cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "[OK] 已安装 pre-push hook 到 $HOOK_DST"
echo "     现在每次 git push 都会自动运行项目级校验。"
