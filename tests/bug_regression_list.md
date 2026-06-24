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

## BUG-013：目录中点击返回书架后首页出现蒙层（回归）

- **首次出现**：2026-06-24（此前修复过，后被重新引入）
- **现象**：在阅读视图中打开目录抽屉（sidebar）后点击"返回书架"，回到首页时 `sidebarOverlay` 蒙层仍覆盖页面，需再点击一次才会消失
- **根因**：`backToHome()` 仅重置 state 并切换视图，未关闭 `sidebarOverlay`；该遮罩元素位于 `readerView` 之外，即使阅读视图隐藏仍保持 `open` 状态，从而遮挡首页
- **复现**：
  1. 打开任意书籍进入阅读视图
  2. 点击底部"目录"按钮（或顶部 ☰）打开目录抽屉
  3. 点击"返回书架"
  4. 观察首页是否被半透明蒙层覆盖，且点击蒙层后才消失
- **修复**：在 `backToHome()` 返回首页前统一调用 `closeSidebar()`、`closeSettings()`、`closeModal()`，确保所有遮罩层随视图切换一并关闭
- **涉及文件**：`site/js/app.js`、`src/web/static/js/app.js`
- **回归测试**：`tests/test_reader_features.js` 测试13（返回书架时关闭目录蒙层）

## BUG-016：GitHub Pages 部署版本缺失自动阅读/壁纸切换（静态产物未同步）

- **首次出现**：2026-06-24
- **现象**：master 分支最新 GitHub Pages 里阅读器没有自动阅读按钮和壁纸切换选项，但本地源码 `src/web/static-site/js/app.js` 已包含相关功能
- **根因**：`site/` 目录下的 `index.html/css/js/sw.js` 靠手工维护，与 `src/web/static-site/` 源文件不同步；CI 构建只生成 `data/` 和 `notes/`，没有自动把新前端产物复制到 `site/`
- **复现**：修改 `src/web/static-site/js/app.js` 后运行 `python scripts/build_site.py`，检查 `site/js/app.js` 是否包含新代码；或对比两个目录的 `index.html`
- **修复**：`scripts/build_site.py` 新增 `_copy_static_assets()`，构建时把 `src/web/static-site/` 的 `index.html/css/style.css/js/app.js/sw.js` 复制到 `site/`，保证 GitHub Pages 部署与源文件一致
- **回归测试**：`tests/test_build_site.py::test_build_site_copies_static_assets` + `tests/run_regression_suite.sh` 第4步（构建静态站点后校验关键资源）
- **教训**：静态站点的前端产物必须纳入构建脚本自动同步，不能依赖手动复制；CI artifact 的每个文件都应在构建脚本里有明确来源。

## BUG-014：沉浸按钮被长章节名撑成竖排

- **首次出现**：2026-06-24
- **现象**：阅读器顶栏左侧章节名过长时，右侧「⛶ 沉浸」按钮被挤扁、文字竖排，极不美观
- **根因**：`.immersive-btn` 参与 flex 布局但没有声明 `flex-shrink: 0` 和 `white-space: nowrap`，在 `toolbar-brand` 占据剩余空间后被挤压换行
- **复现**：把 `toolbar-chapter` 文字设为非常长，或切换到一个章节名很长的笔记，观察按钮形态
- **修复**：`.immersive-btn` 增加 `flex-shrink: 0; white-space: nowrap;`
- **回归测试**：浏览器验收 + `tests/test_reader_features.js` 测试10（检查按钮存在且可见）

## BUG-015：沉浸模式无法退出/无法选章节目录

- **首次出现**：2026-06-24
- **现象**：点击沉浸按钮进入沉浸后，无法退出沉浸模式，也打不开章节目录；用户期望仿番茄阅读，点击中央唤出 UI 后再操作
- **根因**：早期 CSS 在 `body.immersive-mode` 下单方面隐藏 `.toolbar/.sidebar/.bottom-bar`，导致没有任何入口可操作；且退出逻辑依赖 Fullscreen API 状态，在 iframe/安全策略拒绝时状态不一致
- **复现**：进入沉浸模式后尝试点击屏幕、按 ESC、点击目录按钮，观察是否可退出或打开目录
- **修复**：
  1. CSS 改为仅在 `body.immersive-mode.ui-hidden` 时隐藏 UI，点击阅读区中央切换 `ui-hidden`
  2. JS 增加 `enterImmersiveMode`/`exitImmersiveMode`/`toggleImmersiveMode`，进入沉浸时默认隐藏 UI，但点击中央可唤出
  3. 全屏 API 作为可选增强，失败时回退到纯 CSS 沉浸；增加 `immersiveEnterLock` 防止进入瞬间被同步事件错误移除沉浸类
  4. 返回首页时自动退出沉浸
- **回归测试**：`tests/test_reader_features.js` 测试10/11/12 + 浏览器验收（进入/唤出 UI/打开目录/退出）
- **教训**：沉浸/全屏不能只靠系统 API，必须有独立 CSS 状态；UI 隐藏状态要可切换，否则用户会陷入"无入口"的死胡同。

## BUG-017：养生类书籍章内 sort 值不连续

- **首次出现**：2026-06-24
- **频次**：1（已修复并补充回归测试）
- **现象**：`check_book_structure.py` 报出 39 个 P2 问题，集中在 `睡眠与精力修复课`、`饮食养生课`、`饮食养生课第二版`
- **根因**：AI 生成 frontmatter 时把 `sort` 按全书全局编号，未按章内 1-based 连续编号；合并流程中 P2 问题默认不阻断，导致问题堆积
- **复现**：把任意养生类书籍某章内的 `sort` 改为不连续（如 1,3,4），运行 `python scripts/check_book_structure.py --output output --strict`，退出码 1
- **修复**：
  1. 按章重新编号 wellness books 的 `sort` 为 1,2,3...
  2. `scripts/check_book_structure.py` 新增 `--strict` 参数，P0/P1/P2 任一级别失败返回 1
  3. CI、pre-push hook、回归测试集统一使用 `--strict`
  4. 规则/Skill/checklist 明确：合并前必须清零所有校验问题，包括非本次引入的问题
- **涉及文件**：`scripts/check_book_structure.py`、`.github/workflows/*.yml`、`githooks/pre-push`、`.trae/rules/dev-workflow.md`、`.trae/skills/git-merge-guardian/SKILL.md`、`.trae/skills/dev-selfcheck/SKILL.md`、`.trae/checklists/dev-checklist.md`
- **回归测试**：
  - `tests/test_book_structure.py::test_output_has_no_structure_issues`
  - `tests/test_sorting.py::test_wellness_book_sort_values_are_continuous_per_chapter`
- **教训**：P2 问题也是 AI 引入的项目债务，不能在合并时默认放行；必须阻断并沉淀到测试集，才能维持项目长期稳定。
