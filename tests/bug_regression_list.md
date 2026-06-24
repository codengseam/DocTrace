# 历史 Bug 回归列表

本文件记录 HaloRead 项目历史上出现过的 bug、根因、复现方式与回归测试。
用于代码改动 / 冲突合并后执行回归测试集，防止同类问题复现。

配套执行脚本：`tests/run_regression_suite.sh`

---

## BUG-001：GitHub Pages 部署失败（Jekyll 渲染异常）

- **首次出现**：2026-06-23
- **现象**：push 后 GitHub Pages 部署失败，魔搭空间部署正常
- **根因**：GitHub Pages 默认对 artifact 执行 Jekyll 构建，`site/notes/` 下大量 Markdown 触发 Jekyll 3.9.x 渲染异常；魔搭不经过 Jekyll 故正常
- **复现**：删除 `site/.nojekyll` 后 push，观察 GitHub Actions 部署步骤报错
- **修复**：`scripts/build_site.py` 生成 `site/.nojekyll` 空文件，让 GitHub Pages 跳过 Jekyll
- **回归测试**：`tests/test_build_site.py::test_build_site_creates_nojekyll`

## BUG-002：手机端吸底栏失效（flex 高度链路塌缩）

- **首次出现**：2026-06-23
- **现象**：手机端「上一章 目录 设置 下一章」吸底栏不显示或位置错乱
- **根因**：原方案靠 `body{height:100%;display:flex}` + `.bottom-bar{flex-shrink:0}`，魔搭 iframe 内 body 高度塌缩导致整条 flex 链失效；iPhone safe-area 双重缺失
- **复现**：在魔搭空间 iframe 内打开站点，观察底栏位置；或 Chrome 安卓动态地址栏伸缩时底栏抖动
- **修复**：`.bottom-bar` 改 `position:fixed; bottom:0; padding-bottom:env(safe-area-inset-bottom)`；viewport 加 `viewport-fit=cover`；`body.ui-hidden .bottom-bar` 用 `transform:translateY(100%)` 替代 `display:none`
- **回归测试**：`tests/test_web_reader.py` 断言 fixed 定位、safe-area、transform 隐藏

## BUG-003：沉浸阅读模式点击后变横屏（本次修复）

- **首次出现**：2026-06-23（首次修复后回归）
- **现象**：手机端点击「沉浸」按钮后屏幕被强制横屏；此前已修复但代码回退后复现
- **根因**：合并冲突未解决 + 沉浸模式 JS 逻辑丢失（`toggleImmersiveMode`/`enterImmersiveMode`/`exitImmersiveMode` 函数缺失，按钮无事件绑定）；早期版本可能用了 `screen.orientation.lock('landscape')`
- **复现**：在 `site/js/app.js` 中搜索 `toggleImmersiveMode`，若不存在则点击沉浸按钮无响应；若存在 `screen.orientation.lock` 则会强制横屏
- **修复**：
  1. 补回 `enterImmersiveMode`/`exitImmersiveMode`/`toggleImmersiveMode`/`initImmersive` 函数
  2. 用 CSS `.immersive-mode` 隐藏 UI + 内容占满，**不调用 `screen.orientation.lock`**
  3. Fullscreen API 作为可选增强（多 vendor 兼容），失败时静默回退到纯 CSS 沉浸
  4. 沉浸按钮显隐统一由 `switchView` 管理（阅读视图显示，首页隐藏）
  5. 返回首页时自动退出沉浸
- **回归测试**：`tests/test_reader_features.js` 测试10/11/12（沉浸模式 + 不锁定方向 + 返回首页退出）

## BUG-004：章节排序错乱（字符串序排）

- **首次出现**：2026-06-23
- **现象**：明纪排序「全乱」（明纪一 < 明纪七 < 明纪三 < 明纪三十）
- **根因**：非资治通鉴书籍未配置 `BOOK_CATEGORY_ORDER`，章节按字符串序排
- **复现**：在 `src/utils/sorting.py` 中删除 `BOOK_CATEGORY_ORDER` 的唐纪/宋纪/明纪配置，运行 `python scripts/build_site.py` 后观察 `site/data/index.json` 章节顺序
- **修复**：双排序字段设计——`chapter_sort`（阶段在书内历史顺序）+ `sort`（事件在阶段内时间顺序）；`sort_notes_tree` 优先用 frontmatter 字段排序
- **回归测试**：`tests/test_sorting.py` + `scripts/check_chapter_order.py`

## BUG-005：重复 Markdown 文件堆积

- **首次出现**：2026-06-23
- **现象**：`output/` 下出现 200+ 重复文件（同一事件既有编号文件又有主题分组文件）
- **根因**：阶段化重构迁移后，旧文件未清理
- **复现**：在 `output/资治通鉴/` 下同时保留 `秦纪一_荆轲刺秦.md` 和 `秦末大乱与楚汉相争_荆轲刺秦.md`，运行 `python scripts/check_duplicates.py`
- **修复**：`scripts/remove_duplicates.py` 基于内容哈希去重，主题分组文件优先保留；CI 构建前强制运行 `check_duplicates.py`
- **回归测试**：`python scripts/check_duplicates.py` 退出码 0

## BUG-006：跨章节内容大篇幅重复

- **首次出现**：2026-06-23
- **现象**：单篇文章内讲事情已叙述的情节在讲人物/讲背景/讲道理又重述；相邻章节重复详述同一战役
- **根因**：生成时未做主场/客场分配
- **复现**：阅读 `output/资治通鉴/周纪五_窃符救赵.md`，检查长平之战是否与 `周纪五_纸上谈兵.md` 大篇幅重复
- **修复**：主场章节详述、客场章节简略提及；同一名家引言单篇只全文出现一次
- **回归测试**：人工 / Agent 编辑层检查（非自动检测，需语义判断）

## BUG-007：tests/test_web_reader.py 基线已坏

- **首次出现**：2026-06-23
- **现象**：该测试针对 `src/web/` 旧路径（非 `site/`），引用不存在的元素（`#fullscreenBtn`、`.reader-tap-zones`），且因缺 `langgraph` 模块报 ImportError
- **根因**：测试滞后于实现，路径迁移后未同步
- **复现**：`pytest tests/test_web_reader.py`，观察 ImportError 或断言失败
- **修复**：建议后续统一迁移到 `site/` 或标注废弃；当前以 `tests/test_reader_features.js` 为阅读器功能基线
- **回归测试**：`tests/test_reader_features.js`（jsdom e2e）

## BUG-008：innerHTML 覆盖触控层

- **首次出现**：2026-06-23
- **现象**：阅读器触控层（点击翻页区域）被正文重绘销毁
- **根因**：JS 用 `parent.innerHTML = ...` 重绘，叠加在 parent 上的浮层被一并清除
- **复现**：在 `.reader` 上叠加触控层后，用 `elements.reader.innerHTML = ...` 渲染正文，观察触控层是否消失
- **修复**：正文渲染目标改为独立的内容容器（`.reader-content`），触控层与动态内容分开放置
- **回归测试**：`tests/test_reader_features.js` 测试3/4（翻页点击分区 + 排除可交互元素）

## BUG-009：tuple 解包顺序错误

- **首次出现**：2026-06-23
- **现象**：`migrate_stages.py` 运行后全章事件 sort 值都等于 chapter_sort
- **根因**：`build_event_to_stage` 返回 `(stage_name, chapter_sort, event_sort)`，调用方写成 `new_chapter, sort_val, chapter_sort = ...` 解包，2/3 位互换
- **复现**：在 `scripts/migrate_stages.py` 中将解包顺序写错，运行后检查 frontmatter 的 sort 字段
- **修复**：多字段 tuple 返回时优先用 dict 或 namedtuple，避免位置解包
- **回归测试**：`scripts/check_chapter_order.py` 校验 sort 单调递增

## BUG-010：push 前未 fetch 远程导致被拒

- **首次出现**：2026-06-23
- **现象**：本地 commit 后 push 被拒（non-fast-forward）
- **根因**：远程已有新 commit，本地未 fetch/rebase
- **复现**：本地有 commit 时，远程先 push 一个新 commit，本地直接 `git push` 被拒
- **修复**：push 前先 `git fetch` + `git rebase origin/master`
- **回归测试**：无自动测试（流程规范）

## BUG-011：合并冲突未解决导致代码无法 push + 构建失败（本次发现）

- **首次出现**：2026-06-23
- **现象**：用户以为代码已 push，实际远程只有 1 个提交；本地 `scripts/build_site.py`、`output/资治通鉴/*.md` 等 14 个文件有未解决合并冲突，构建脚本 SyntaxError 无法运行；沉浸模式 JS 逻辑丢失
- **根因**：合并冲突未解决就以为推送成功；`<<<<<<< HEAD` 标记残留导致 Python SyntaxError
- **复现**：在 `scripts/build_site.py` 中保留 `<<<<<<< HEAD` 标记，运行 `python scripts/build_site.py`，观察 SyntaxError
- **修复**：逐文件解决冲突——代码/配置保留 origin/master 侧（有功能），output/ 内容保留 HEAD 侧（符合引用克制规则）
- **回归测试**：`tests/run_regression_suite.sh` 含合并冲突标记检查

## BUG-012：CI 部署失败（重复文件回退 + index.json 结构变更未同步 workflow）

- **首次出现**：2026-06-23
- **现象**：合并到 master 后 GitHub Pages 和魔搭部署都失败
- **根因**（两个独立问题）：
  1. **pages.yml `Check duplicate notes` 失败**：合并冲突解决时，master 侧的编号文件 + feature 侧的主题分组文件同时存在，`output/` 下又出现 220 组重复文件，`check_duplicates.py` 退出码 1
  2. **deploy-modelscope.yml `Verify build output` 失败**：合并冲突解决保留了 origin/master 侧的"拆分搜索索引"改动（`index.json` 不再含 `notes` 键，正文移到 `search-index.json`），但魔搭 workflow 第53行校验脚本仍用 `index.json['notes']` 取笔记数 → `KeyError` → `set -e` 退出
- **复现**：
  1. 在 `output/` 下同时保留编号文件和主题分组文件，运行 `python scripts/check_duplicates.py`，观察退出码 1
  2. 运行 `python -c "import json; print(json.load(open('site/data/index.json'))['notes'])"`，观察 KeyError
- **修复**：
  1. 重新运行 `scripts/remove_duplicates.py` 清理 220 个重复文件
  2. 魔搭 workflow 第53行改用 `stats.notes`（`index.json['stats']['notes']`）
- **回归测试**：`tests/run_regression_suite.sh` 第6步（check_duplicates）+ 新增"index.json 结构校验"（stats.notes 存在且 >0）
- **教训**：合并冲突解决后，必须本地完整复现 CI 流程（不只是 build_site.py 成功），尤其要跑 workflow 里每个 `run:` 步骤的等价命令。数据结构变更（如 index.json 拆分）必须同步所有消费方（workflow 校验脚本、app.js、测试）。
