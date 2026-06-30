#!/usr/bin/env bash
# HaloRead 回归测试集
# 用法：bash tests/run_regression_suite.sh
# 对应 bug 列表：tests/bug_regression_list.md
# 退出码：0 全部通过，非 0 表示有失败

set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
WARN=0
FAILED_STEPS=()
WARNED_STEPS=()

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

# 告警项：只提示不计入失败退出码。
# 用于内容数据质量检查（重复文件、章节排序），与代码回归（BUG-003/011）区分：
# 代码回归必须阻塞合并，数据质量问题只提醒清理，避免卡死债务清理 PR。
warn() {
    local name="$1"
    local ok="$2"
    if [ "$ok" = "1" ]; then
        echo "  ✅ $name"
        PASS=$((PASS + 1))
    else
        echo "  ⚠️  $name（告警，不阻塞）"
        WARN=$((WARN + 1))
        WARNED_STEPS+=("$name")
    fi
}

echo "=== HaloRead 回归测试集 ==="
echo ""

# ---------- 1. 合并冲突标记检查（BUG-011） ----------
echo "[1/13] 合并冲突标记检查"
CONFLICTS=$(grep -rn "^<<<<<<< HEAD\|^>>>>>>> origin/master" \
    --include="*.py" --include="*.yml" --include="*.md" --include="*.js" \
    --include="*.css" --include="*.html" . 2>/dev/null | grep -v node_modules | grep -v "/.git/" | wc -l)
step "无合并冲突标记残留 (found=$CONFLICTS)" "$([ "$CONFLICTS" = "0" ] && echo 1 || echo 0)"

# ---------- 2. app.js 语法检查（BUG-003/008） ----------
echo "[2/13] app.js 语法检查"
if node --check site/js/app.js 2>/dev/null; then
    step "site/js/app.js 语法正确" 1
else
    step "site/js/app.js 语法正确" 0
fi

# ---------- 3. 沉浸模式关键代码 + 防横屏 + 整屏全屏（BUG-003/020/036 回归） ----------
echo "[3/13] 沉浸模式回归检查"
APP_JS="site/js/app.js"
HAS_TOGGLE=$(grep -c "toggleImmersiveMode" "$APP_JS" 2>/dev/null || true)
HAS_ENTER=$(grep -c "enterImmersiveMode" "$APP_JS" 2>/dev/null || true)
HAS_EXIT=$(grep -c "exitImmersiveMode" "$APP_JS" 2>/dev/null || true)
HAS_INIT=$(grep -c "initImmersive" "$APP_JS" 2>/dev/null || true)
NO_LOCK=$(grep -c "screen.orientation.lock\|lockOrientation" "$APP_JS" 2>/dev/null || true)
NO_LOCK=${NO_LOCK:-0}
# BUG-036：重新引入 Fullscreen API 实现整屏全屏，断言从"不调用"改为"调用"
HAS_FULLSCREEN=$(grep -c "requestFullscreen\|webkitRequestFullscreen\|exitFullscreen\|webkitExitFullscreen" "$APP_JS" 2>/dev/null || true)
HAS_FULLSCREEN=${HAS_FULLSCREEN:-0}
# BUG-036：小米浏览器 UA 跳过 Fullscreen API（防 BUG-021 强制横屏重现）
HAS_XIAOMI_CHECK=$(grep -c "isXiaomiBrowser\|MiuiBrowser" "$APP_JS" 2>/dev/null || true)
HAS_XIAOMI_CHECK=${HAS_XIAOMI_CHECK:-0}
step "含 toggleImmersiveMode/enter/exit/initImmersive ($HAS_TOGGLE/$HAS_ENTER/$HAS_EXIT/$HAS_INIT)" \
    "$([ "$HAS_TOGGLE" -ge 1 ] && [ "$HAS_ENTER" -ge 1 ] && [ "$HAS_EXIT" -ge 1 ] && [ "$HAS_INIT" -ge 1 ] && echo 1 || echo 0)"
step "不调用 screen.orientation.lock (防横屏, found=$NO_LOCK)" \
    "$([ "$NO_LOCK" = "0" ] && echo 1 || echo 0)"
step "调用 Fullscreen API 实现整屏全屏 (BUG-036, found=$HAS_FULLSCREEN)" \
    "$([ "$HAS_FULLSCREEN" -ge 1 ] && echo 1 || echo 0)"
step "小米浏览器 UA 跳过 Fullscreen (BUG-036, found=$HAS_XIAOMI_CHECK)" \
    "$([ "$HAS_XIAOMI_CHECK" -ge 1 ] && echo 1 || echo 0)"

# ---------- 4. 构建站点（BUG-011/004） ----------
echo "[4/13] 构建静态站点"
if python3 scripts/build_site.py --output output --site site >/dev/null 2>&1; then
    step "build_site.py 执行成功" 1
else
    step "build_site.py 执行成功" 0
fi
step "site/data/index.json 存在且有效" \
    "$([ -f site/data/index.json ] && python3 -c "import json;json.load(open('site/data/index.json'))" 2>/dev/null && echo 1 || echo 0)"
step "site/.nojekyll 存在（BUG-001）" "$([ -f site/.nojekyll ] && echo 1 || echo 0)"
# BUG-012 回归：index.json 拆分后不再含 notes 键，但必须含 stats.notes
step "index.json 含 stats.notes 且 >0（BUG-012）" \
    "$(python3 -c "import json,sys; d=json.load(open('site/data/index.json')); sys.exit(0 if d.get('stats',{}).get('notes',0)>0 else 1)" 2>/dev/null && echo 1 || echo 0)"

# ---------- 5. 阅读器功能 e2e（BUG-002/003/008） ----------
echo "[5/13] 阅读器功能 e2e (jsdom)"
if [ -d node_modules/jsdom ]; then
    if node tests/test_reader_features.js >/dev/null 2>&1; then
        step "test_reader_features.js 全部通过" 1
    else
        step "test_reader_features.js 全部通过" 0
    fi
else
    echo "  ⚠️  跳过：node_modules/jsdom 未安装（运行 npm install jsdom marked 启用）"
fi

# ---------- 6. 书籍结构严格校验（BUG-017，合并前必须清零 P0/P1/P2） ----------
echo "[6/13] 书籍结构严格校验"
if python3 scripts/check_book_structure.py --output output --strict >/dev/null 2>&1; then
    step "check_book_structure.py --strict 通过" 1
else
    step "check_book_structure.py --strict 通过" 0
fi

# ---------- 7. 重复文件检查（BUG-005，数据质量，告警） ----------
echo "[7/13] 重复文件检查"
if python3 scripts/check_duplicates.py >/dev/null 2>&1; then
    warn "check_duplicates.py 通过" 1
else
    warn "check_duplicates.py 通过" 0
fi

# ---------- 8. 章节排序检查（BUG-004/009，数据质量，告警） ----------
echo "[8/13] 章节排序检查"
if python3 scripts/check_chapter_order.py >/dev/null 2>&1; then
    warn "check_chapter_order.py 通过" 1
else
    warn "check_chapter_order.py 通过" 0
fi

# ---------- 9. HTTP 冒烟测试 ----------
echo "[9/13] HTTP 冒烟测试"
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
# BUG-035：SSG 全局索引页 HTTP 200
SSG_INDEX_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8092/reader/index.html" 2>/dev/null)
if [ "$SSG_INDEX_CODE" != "200" ]; then
    ALL_200=0
    echo "      /reader/index.html -> $SSG_INDEX_CODE"
fi
kill $SERVER_PID 2>/dev/null || true
step "关键资源全部 200" "$ALL_200"

# BUG-035：SSG 章节静态页（夸克阅读模式入口）冒烟
echo "  -> SSG 章节静态页冒烟 (BUG-035)"
step "site/reader/index.html 存在（全局索引）" "$([ -f site/reader/index.html ] && echo 1 || echo 0)"
# 取第一篇 SSG 章节页做语义结构断言
SSG_SAMPLE=$(find site/reader -mindepth 2 -name '*.html' -type f 2>/dev/null | head -1)
step "site/reader/{书}/{章节}_{事件}.html 至少 1 个" "$([ -n "$SSG_SAMPLE" ] && echo 1 || echo 0)"
if [ -n "$SSG_SAMPLE" ]; then
    SSG_HTML=$(cat "$SSG_SAMPLE")
    # 夸克阅读模式触发条件：必须含 <article> + <h1> + <p>
    step "SSG HTML 含 <article> 包裹（夸克硬性条件）" \
        "$(echo "$SSG_HTML" | grep -q '<article' && echo 1 || echo 0)"
    step "SSG HTML 含 <h1> 主标题" \
        "$(echo "$SSG_HTML" | grep -qE '<h1[ >]' && echo 1 || echo 0)"
    step "SSG HTML 含 <p> 段落" \
        "$(echo "$SSG_HTML" | grep -q '<p>' && echo 1 || echo 0)"
    # 反向断言：不引 app.js，避免 SPA 双渲染路径分叉
    step "SSG HTML 不引用 app.js" \
        "$(echo "$SSG_HTML" | grep -q 'app.js' && echo 0 || echo 1)"
    # 反向断言：不依赖 fetch / marked.parse
    step "SSG HTML 不依赖 fetch/marked.parse" \
        "$(echo "$SSG_HTML" | grep -qE 'fetch\(|marked\.parse' && echo 0 || echo 1)"
fi

# ---------- 10. 分支治理脚本冒烟（BUG-023） ----------
echo "[10/13] 分支治理脚本冒烟 (BUG-023)"
if [ -f scripts/branch_governance.py ]; then
    step "branch_governance.py 存在" 1
else
    step "branch_governance.py 存在" 0
fi
if python3 scripts/branch_governance.py --help >/dev/null 2>&1; then
    step "branch_governance.py --help 退出码 0" 1
else
    step "branch_governance.py --help 退出码 0" 0
fi
# dry-run 必须不报错（即便无候选分支也要退出 0）
DRY_OUT=$(python3 scripts/branch_governance.py --mode dry-run --pattern "trae/agent-*" --no-fetch 2>&1) && DRY_RC=0 || DRY_RC=$?
step "dry-run 退出码 0 (rc=$DRY_RC)" "$([ "$DRY_RC" = "0" ] && echo 1 || echo 0)"
# 受保护分支必须出现在报告
step "dry-run 报告含保护分支段落" \
    "$(echo "$DRY_OUT" | grep -q "保护分支\|protected" && echo 1 || echo 0)"
# execute 无 --yes 必须失败
python3 scripts/branch_governance.py --mode execute --pattern "trae/agent-*" --no-fetch >/dev/null 2>&1
step "execute 无 --yes 时拒绝执行 (rc!=0)" "$([ "$?" -ne "0" ] && echo 1 || echo 0)"

# ---------- 11. loop_log 结构校验 ----------
echo "[11/13] loop_log 结构校验"
if python3 scripts/check_loop_log.py >/dev/null 2>&1; then
    step "check_loop_log.py 通过" 1
else
    step "check_loop_log.py 通过" 0
fi

# ---------- 12. plan-review skill 路径契约（BUG-031） ----------
echo "[12/13] plan-review skill 路径契约 (BUG-031)"
PLAN_REVIEW_SKILL=".trae/skills/plan-review/SKILL.md"
DISPATCH_SKILL=".trae/skills/dispatching-parallel-agents/SKILL.md"
step "plan-review SKILL.md 存在" "$([ -f "$PLAN_REVIEW_SKILL" ] && echo 1 || echo 0)"
step "dispatching-parallel-agents SKILL.md 存在" "$([ -f "$DISPATCH_SKILL" ] && echo 1 || echo 0)"
# 主路径必须使用 Task 工具 + subagent_type
HAS_TASK=$(grep -c "Task 工具\|subagent_type" "$PLAN_REVIEW_SKILL" 2>/dev/null || true)
HAS_TASK=${HAS_TASK:-0}
step "plan-review 主路径含 Task 工具 + subagent_type (count=$HAS_TASK)" "$([ "$HAS_TASK" -ge 2 ] && echo 1 || echo 0)"
# 必须声明不硬阻塞
step "plan-review 声明不硬阻塞" "$(grep -q "不硬阻塞" "$PLAN_REVIEW_SKILL" && echo 1 || echo 0)"
# 错误处理章节不再含误导条目 scripts/review_plan.py 不存在
NO_MISLEAD=$(grep -c "scripts/review_plan.py 不存在" "$PLAN_REVIEW_SKILL" 2>/dev/null || true)
NO_MISLEAD=${NO_MISLEAD:-0}
step "plan-review 不含 'scripts/review_plan.py 不存在' 误导条目 (found=$NO_MISLEAD)" "$([ "$NO_MISLEAD" = "0" ] && echo 1 || echo 0)"
# scripts/review_plan.py langgraph ImportError 必须有友好提示
step "review_plan.py 含 langgraph ImportError 友好提示" \
    "$(grep -q "路径 B（LangGraph 真并行）依赖未就绪" scripts/review_plan.py && echo 1 || echo 0)"

# ---------- 13. 字数事实核对脚本冒烟（BUG-038） ----------
echo "[13/13] 字数事实核对脚本冒烟 (BUG-038)"
if [ -f scripts/check_char_count.py ]; then
    step "check_char_count.py 存在" 1
else
    step "check_char_count.py 存在" 0
fi
if python3 scripts/check_char_count.py --help >/dev/null 2>&1; then
    step "check_char_count.py --help 退出码 0" 1
else
    step "check_char_count.py --help 退出码 0" 0
fi
# 三种模式 self-test：构造已知错误，断言脚本能检出
SELF_TEST_OUT=$(python3 -c "
import sys; sys.path.insert(0,'scripts')
import check_char_count as m
e1 = m.check_text('5个字：你好世')
e2 = m.check_text('「太子」这三个字')
e3 = m.check_text('三个字：「太子」')
ok = len(e1)==1 and e1[0]['expected']==5 and len(e2)==1 and e2[0]['expected']==3 and len(e3)==1 and e3[0]['expected']==3
print('OK' if ok else 'FAIL')
" 2>&1)
step "三种模式 self-test 检出已知错误 ($SELF_TEST_OUT)" "$(echo "$SELF_TEST_OUT" | grep -q '^OK$' && echo 1 || echo 0)"

# ---------- 汇总 ----------
echo ""
echo "=== 汇总：通过 $PASS，失败 $FAIL，告警 $WARN ==="
if [ "$WARN" -gt 0 ]; then
    echo "告警项（数据质量，不阻塞合并，建议清理）："
    for s in "${WARNED_STEPS[@]}"; do
        echo "  - $s"
    done
fi
if [ "$FAIL" -gt 0 ]; then
    echo "失败项（代码回归，阻塞合并）："
    for s in "${FAILED_STEPS[@]}"; do
        echo "  - $s"
    done
    exit 1
fi
echo "代码回归检查全部通过 ✅（数据质量告警 $WARN 项不阻塞）"
exit 0
