#!/usr/bin/env bash
# HaloRead 回归测试集
# 用法：bash tests/run_regression_suite.sh
# 对应 bug 列表：tests/bug_regression_list.md
# 退出码：0 全部通过，非 0 表示有失败

set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
FAILED_STEPS=()

step() {
    local name="$1"
    local ok="$2"
    if [ "$ok" = "1" ]; then
        echo "  ✅ $name"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name"
        FAIL=$((FAIL + 1))
        FAILED_STEPS+=("$name")
    fi
}

echo "=== HaloRead 回归测试集 ==="
echo ""

# ---------- 1. 合并冲突标记检查（BUG-011） ----------
echo "[1/8] 合并冲突标记检查"
CONFLICTS=$(grep -rn "^<<<<<<< HEAD\|^>>>>>>> origin/master" \
    --include="*.py" --include="*.yml" --include="*.md" --include="*.js" \
    --include="*.css" --include="*.html" . 2>/dev/null | grep -v node_modules | grep -v "/.git/" | wc -l)
step "无合并冲突标记残留 (found=$CONFLICTS)" "$([ "$CONFLICTS" = "0" ] && echo 1 || echo 0)"

# ---------- 2. app.js 语法检查（BUG-003/008） ----------
echo "[2/8] app.js 语法检查"
if node --check site/js/app.js 2>/dev/null; then
    step "site/js/app.js 语法正确" 1
else
    step "site/js/app.js 语法正确" 0
fi

# ---------- 3. 沉浸模式关键代码 + 防横屏（BUG-003） ----------
echo "[3/8] 沉浸模式回归检查"
APP_JS="site/js/app.js"
HAS_TOGGLE=$(grep -c "toggleImmersiveMode" "$APP_JS" 2>/dev/null || true)
HAS_ENTER=$(grep -c "enterImmersiveMode" "$APP_JS" 2>/dev/null || true)
HAS_EXIT=$(grep -c "exitImmersiveMode" "$APP_JS" 2>/dev/null || true)
HAS_INIT=$(grep -c "initImmersive" "$APP_JS" 2>/dev/null || true)
NO_LOCK=$(grep -c "screen.orientation.lock\|lockOrientation" "$APP_JS" 2>/dev/null || true)
NO_LOCK=${NO_LOCK:-0}
step "含 toggleImmersiveMode/enter/exit/initImmersive ($HAS_TOGGLE/$HAS_ENTER/$HAS_EXIT/$HAS_INIT)" \
    "$([ "$HAS_TOGGLE" -ge 1 ] && [ "$HAS_ENTER" -ge 1 ] && [ "$HAS_EXIT" -ge 1 ] && [ "$HAS_INIT" -ge 1 ] && echo 1 || echo 0)"
step "不调用 screen.orientation.lock (防横屏, found=$NO_LOCK)" \
    "$([ "$NO_LOCK" = "0" ] && echo 1 || echo 0)"

# ---------- 4. 构建站点（BUG-011/004） ----------
echo "[4/8] 构建静态站点"
if python3 scripts/build_site.py --output output --site site >/dev/null 2>&1; then
    step "build_site.py 执行成功" 1
else
    step "build_site.py 执行成功" 0
fi
step "site/data/index.json 存在且有效" \
    "$([ -f site/data/index.json ] && python3 -c "import json;json.load(open('site/data/index.json'))" 2>/dev/null && echo 1 || echo 0)"
step "site/.nojekyll 存在（BUG-001）" "$([ -f site/.nojekyll ] && echo 1 || echo 0)"

# ---------- 5. 阅读器功能 e2e（BUG-002/003/008） ----------
echo "[5/8] 阅读器功能 e2e (jsdom)"
if [ -d node_modules/jsdom ]; then
    if node tests/test_reader_features.js >/dev/null 2>&1; then
        step "test_reader_features.js 全部通过" 1
    else
        step "test_reader_features.js 全部通过" 0
    fi
else
    echo "  ⚠️  跳过：node_modules/jsdom 未安装（运行 npm install jsdom marked 启用）"
fi

# ---------- 6. 重复文件检查（BUG-005） ----------
echo "[6/8] 重复文件检查"
if python3 scripts/check_duplicates.py >/dev/null 2>&1; then
    step "check_duplicates.py 通过" 1
else
    step "check_duplicates.py 通过" 0
fi

# ---------- 7. 章节排序检查（BUG-004/009） ----------
echo "[7/8] 章节排序检查"
if python3 scripts/check_chapter_order.py >/dev/null 2>&1; then
    step "check_chapter_order.py 通过" 1
else
    step "check_chapter_order.py 通过" 0
fi

# ---------- 8. HTTP 冒烟测试 ----------
echo "[8/8] HTTP 冒烟测试"
python3 -m http.server 8092 --bind 127.0.0.1 --directory site >/dev/null 2>&1 &
SERVER_PID=$!
sleep 1
ALL_200=1
for url in "/" "/js/app.js" "/css/style.css" "/data/index.json"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8092$url" 2>/dev/null)
    if [ "$code" != "200" ]; then
        ALL_200=0
        echo "      $url -> $code"
    fi
done
kill $SERVER_PID 2>/dev/null || true
step "关键资源全部 200" "$ALL_200"

# ---------- 汇总 ----------
echo ""
echo "=== 汇总：通过 $PASS，失败 $FAIL ==="
if [ "$FAIL" -gt 0 ]; then
    echo "失败项："
    for s in "${FAILED_STEPS[@]}"; do
        echo "  - $s"
    done
    exit 1
fi
echo "全部通过 ✅"
exit 0
