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

## BUG-018：Service Worker 缓存导致手机端看到旧版本（幽灵旧版）

- **首次出现**：2026-06-24
- **现象**：PC 浏览器访问 GitHub Pages / ModelScope 均正常（无蒙层、有自动阅读按钮），但部分手机端用户仍看到旧版本表现：返回书架后蒙层残留、无自动阅读按钮
- **根因**：`site/sw.js` 对核心资源（`index.html` / `style.css` / `app.js`）使用 `cacheFirst` 策略，且缓存名固定为 `halo-read-v1`。手机浏览器/PWA 一旦缓存过旧 `app.js`，即使服务器已部署 BUG-013 修复，仍会优先读取本地旧缓存，造成"代码已更新、用户端仍旧"的幽灵旧版现象
- **复现**：
  1. 在旧版本上线后，用手机浏览器访问站点并缓存资源
  2. 服务器部署新版本 `app.js`（含 BUG-013 修复）
  3. 同一手机再次访问，观察是否仍加载旧 `app.js`（可从控制台 `navigator.serviceWorker.controller.scriptURL` 或缓存内容判断）
- **修复**：将 `CACHE_NAME` 从 `halo-read-v1` 升级为 `halo-read-v2`。新的 Service Worker 安装后会创建 `v2` 缓存并重新预缓存最新核心资源；activate 阶段清理旧 `v1` 缓存，并通过 `clients.claim()` 立即接管所有客户端
- **涉及文件**：`site/sw.js`
- **回归测试**：无专门自动测试；依赖浏览器验收 + 每次关键前端修复后人工升级 `CACHE_NAME`
- **避免措施**：
  1. 每次对 `app.js` / `style.css` / `index.html` 做不兼容或关键修复后，**同步升级 `CACHE_NAME` 版本号**
  2. 在 CI 或回归测试集中增加对 `CACHE_NAME` 变更的提醒（例如对比当前 `site/sw.js` 中版本号与上次发布是否一致）
  3. 长期考虑：构建脚本自动将 `CACHE_NAME` 与 `app.js` 内容哈希绑定，或改用 `staleWhileRevalidate`/`networkFirst` 策略，避免手动维护版本号
- **教训**：`cacheFirst` 策略的 PWA/Service Worker 会把"已部署"和"用户实际看到"分成两个时间线；前端修复必须同时考虑缓存失效策略，否则 PC 端正常、手机端仍旧的 bug 会反复出现。

## BUG-019：章节标题和文件名含「模块N」前缀

- **首次出现**：2026-06-24
- **频次**：1（已修复并补充回归测试）
- **现象**：多本书籍的章节标题（frontmatter `chapter`）和文件名中出现「模块0」「模块1」等前缀，导致目录展示混乱，影响阅读体验
- **根因**：`scripts/rename_modules_with_prefix.py` 脚本为养生类课程批量添加「模块N」前缀；同时提示词与规则未明确禁止该前缀，生成/迁移时未做校验
- **复现**：运行 `python scripts/rename_modules_with_prefix.py` 后，检查 `output/饮食养生课/`、`output/睡眠与精力修复课/` 等目录下的文件名和 frontmatter `chapter` 字段
- **修复**：
  1. 新增 `scripts/remove_module_prefixes.py` 批量清理 frontmatter `chapter` 字段与文件名中的「模块N」前缀，保持 `sort`/`chapter_sort` 不变
  2. `scripts/check_book_structure.py` 新增 P1 级检测规则：文件名章节部分或 frontmatter.chapter 含「模块N」前缀即报 P1 错误
  3. 删除根因脚本 `scripts/rename_modules_with_prefix.py`，防止后续误执行
  4. `README.md` 命名规范、`dev-checklist.md`、`dev-workflow.md` 明确禁止章节名/文件名使用「模块N」前缀
- **涉及文件**：`scripts/remove_module_prefixes.py`、`scripts/check_book_structure.py`、`scripts/rename_modules_with_prefix.py`（已删除）、`tests/test_book_structure.py`、`.trae/rules/dev-workflow.md`、`.trae/checklists/dev-checklist.md`、`README.md`
- **回归测试**：`tests/test_book_structure.py::test_check_file_rejects_module_prefix_in_chapter`
- **教训**：UI 文案类问题同样会反复出现，不能只靠一次性清理；必须把「不准出现」的样式规则落到校验脚本、测试集和开发规范里，才能根除。

## 资治通鉴大章节顺序错乱（汉纪跑到周纪前面）

- **编号**：BUG-022
- **首次出现**：2026-06-24
- **频次**：多次修复后复发
- **现象**：`site/data/index.json` 里「资治通鉴」的章节顺序变成 `周纪一、周纪二、秦纪一、周纪三、汉纪一、汉纪七、汉纪三、汉纪三十…秦纪二、周纪四…`，汉纪插入到周纪前面；手机端书架目录混乱
- **根因**：`sort_notes_tree` 优先使用 frontmatter `chapter_sort` 作为绝对排序，但 `output/资治通鉴/` 各文件的 `chapter_sort` 写得很乱：有的按朝代阶段写（汉纪=3）、有的按绝对顺序写（周纪四=4、秦纪二=3）、有的甚至缺失；结果写了 `chapter_sort` 的章节被当作显式组排在没写的回退组前面，同组内再按中文字符串序排，导致「汉纪十七」排在「汉纪十二」前面。`check_book_structure.py` 只校验章内 `sort`，不校验大章节顺序，所以 CI/pre-push 全部漏掉
- **复现**：运行 `python scripts/build_site.py` 后检查 `site/data/index.json` 中 `books[?id=="资治通鉴"].tree` 的章节顺序
- **修复**：
  1. 新增 `scripts/fix_zizhi_chapter_sort.py`，把资治通鉴所有文件的 `chapter_sort` 统一为朝代/纪阶段序号（周纪=1、秦纪=2、汉纪=3…）
  2. `src/utils/sorting.py` 引入「阶段模式」概念：`STAGE_MODE_BOOKS = {"资治通鉴"}`，阶段模式书籍按 `(chapter_sort, 章节名序号)` 排序，避免字符串序；其他书籍仍按 `(chapter_sort, event sort)` 排序，保持三国、史记、唐纪/宋纪/明纪等现有顺序不变
  3. `scripts/check_book_structure.py` 新增 `_check_stage_mode_order`：阶段模式书籍中，同一朝代/纪的所有文件 `chapter_sort` 必须等于 `BOOK_CATEGORY_ORDER` 配置的阶段序号，否则报 P1
  4. `scripts/build_site.py` 跳过下划线开头的辅助文件（如 `_目录.md`），避免目录中出现空章节
- **涉及文件**：`scripts/fix_zizhi_chapter_sort.py`、`src/utils/sorting.py`、`scripts/check_book_structure.py`、`scripts/build_site.py`、`output/资治通鉴/*.md`
- **回归测试**：
  - `tests/test_sorting.py::test_sort_notes_tree_zizhi_stage_mode_orders_by_ordinal`
  - `tests/test_book_structure.py::test_check_book_structure_detects_zizhi_inconsistent_chapter_sort`
  - `tests/test_book_structure.py::test_output_has_no_structure_issues`
  - `python scripts/check_book_structure.py --output output --strict` 退出码 0
- **教训**：大章节顺序不能仅靠 frontmatter 字段的「约定」来维持；必须给特殊书籍定义明确的排序语义，并用校验脚本把语义固化为 P1 规则，否则数据迁移/重新生成时很容易再次写错。合并前 `--strict` 必须全部通过，包括历史遗留问题。

## 移动端阅读器多项体验问题（壁纸、自动阅读、代码块、沉浸模式白屏、滑条拖拽）

- **编号**：BUG-020
- **首次出现**：2026-06-24
- **频次**：1（已修复并补充回归测试）
- **现象**（5 个关联问题）：
  1. 手机端选择壁纸后，壁纸只覆盖阅读区上半部分，向下滚动即消失
  2. 壁纸预设过多（无/竹简/宣纸/水墨/山水/星空），仅保留「无、竹简、山水」即可
  3. 自动阅读浮动按钮暴露在外不好看，需改到设置面板中作为开关
  4. Markdown 代码块在手机上展示不全，横向滑动困难，甚至误触发翻页
  5. 沉浸模式下系统返回后再进入站点白屏，必须清缓存；设置面板滑条难以拖动
- **根因**：
  1. 壁纸层使用 `.reader::before` + `position:absolute; inset:0`，高度被限制在阅读区可视区域内，不随内容滚动延伸
  2. 产品决策：精简壁纸预设，删除不好看/低质 SVG 纹理
  3. 交互决策：将自动阅读入口从右下角浮钮迁移到设置面板，与速度滑块集中管理
  4. `pre` 缺少 `-webkit-overflow-scrolling: touch` 和合适的宽度约束；`shouldExcludeTap` 未排除 `pre/code`，点击代码块会触发翻页/UI 切换
  5. 页面从手机 bfcache 恢复时，DOM 仍保留 `immersive-mode/ui-hidden/data-view="reader"`，但 JS `state` 已重置，导致渲染错乱白屏；`input[type=range]` 的 track/thumb 过小，触控区域不足
- **修复**：
  1. 将壁纸层改为真实 DOM 元素 `.reader-wallpaper`，`loadNote`/resize/切换壁纸时设置 `height = reader.scrollHeight`
  2. 在 `index.html` 中删除 `xuan/ink/starry` 按钮；`loadSettings`/`applySettings` 中把非法壁纸规范为 `none`；删除对应 CSS 规则
  3. 删除 `.auto-scroll-btn` 浮动按钮；在设置面板新增「自动阅读」开关；`start/pauseAutoScroll` 同步 `settings.autoScroll`
  4. `.markdown-body pre` 增加 `-webkit-overflow-scrolling: touch`、`overscroll-behavior-x: contain`、`max-width:100%`；`shouldExcludeTap` 增加 `pre, code` 排除
  5. `init()` 开头调用 `resetViewState()`；监听 `pageshow`，`event.persisted` 时重置视图并重新加载书架；`sw.js` 升级 `CACHE_NAME` 到 `halo-read-v3`；滑条增大 track/thumb 和触控区域
- **涉及文件**：`src/web/static-site/index.html`、`src/web/static-site/css/style.css`、`src/web/static-site/js/app.js`、`src/web/static-site/sw.js`
- **回归测试**：`tests/test_reader_features.js` 测试1/5/6/7/9/13/14/15/16 + 浏览器移动端验收
- **教训**：移动端交互问题（触控、缓存恢复、视口适配）必须真机或模拟器验收；Service Worker cache-first 策略下，每次前端关键修复都要升级 `CACHE_NAME`，否则手机端会持续看到幽灵旧版。

## 沉浸模式点击后强制横屏 + 代码块无法自动换行

- **编号**：BUG-021
- **首次出现**：2026-06-24（BUG-020 修复后的移动端验收中复现）
- **频次**：1（已修复并补充回归测试）
- **现象**：
  1. 小米原生浏览器点击沉浸按钮后，页面被强制切换为横屏阅读，即便用户已锁定竖屏
  2. Markdown 代码块虽已支持横向滑动，但用户期望在手机上自动换行，无需滑动即可看全
- **根因**：
  1. 之前修复只禁用了 `screen.orientation.lock`，但保留了 `requestFullscreen` 作为「可选增强」；在小米/部分国产浏览器中，`requestFullscreen(document.documentElement)` 会触发系统级全屏并强制横屏
  2. 代码块 `white-space: pre` 阻止自动换行，依赖横向滚动查看长代码
- **修复**：
  1. 彻底移除 Fullscreen API 调用（`requestFullscreen`/`exitFullscreen` 及其 vendor 前缀），沉浸模式改为纯 CSS 实现，不再触发任何系统级方向变化
  2. `.markdown-body pre code` 改为 `white-space: pre-wrap` + `word-wrap: break-word` + `overflow-wrap: break-word` + `word-break: break-word`，让代码根据屏幕宽度自动换行
  3. 回归测试脚本 `run_regression_suite.sh` 增加「不调用 Fullscreen API」断言；`test_reader_features.js` 测试11/15 同步更新
- **涉及文件**：`src/web/static-site/js/app.js`、`src/web/static-site/css/style.css`、`tests/test_reader_features.js`、`tests/test_build_site.py`、`tests/run_regression_suite.sh`
- **回归测试**：`tests/test_reader_features.js` 测试11/15、`tests/run_regression_suite.sh` 第3步
- **教训**：「可选增强」的 Fullscreen API 在国产浏览器上并不安全，任何可能触发方向变化或系统全屏的 API 都应在移动端阅读器中禁用；代码块体验应优先自动换行，其次才保留横向滚动作为兜底。

## agent 分支用完未清理导致远程分支堆积（不走 PR 使 merged 检测失效）

- **编号**：BUG-023
- **首次出现**：2026-06-25
- **频次**：1（首次沉淀治理机制）
- **类型**：构建 / 流程
- **现象**：远程仓库堆积 22 个 `trae/agent-*` 残留分支，导致 `git clone` 体积膨胀。用户工作流为「AI 在 agent 分支工作 → 用户检查 → AI 调用 git-merge-guardian 模式 B 直接合入 master 并 push（不走 PR）」，因不走 PR，`git branch --merged` 显示这些分支「未合并」，但内容其实已等价进入 master，无人清理
- **根因**（两层）：
  1. `git-merge-guardian` SKILL.md 模式 B 合并后只删除**当前**功能分支，不巡检其他遗留 agent 分支
  2. 用户不走 PR 直接合入 master（模式 B），rebase + merge 后分支独有提交不一定作为 ancestor 进入 master 历史，导致传统 `git branch --merged` / `git merge-base --is-ancestor` 失效，无法识别「等价合入」
- **修复**（三组件长远方案，B+C）：
  1. **治理脚本 `scripts/branch_governance.py`**：CI 与 skill 共用的判定引擎，支持 dry-run / execute 两种模式；用「patch-id 比对(0.3) + 文件 blob 内容比对(0.5) + commit message 匹配(0.2)」三方法综合判定「等价合入」，输出置信度；merge-base ancestor 命中直接 confidence=1.0；受保护分支白名单（master/main/gh-pages/release/*）永不删除；execute 必须带 `--yes`
  2. **CI 主触发 `.github/workflows/branch-cleanup.yml`**：push to master 自动 dry-run 报告（只读权限）；workflow_dispatch 手动 execute（绑定 GitHub Environment `branch-cleanup-execute` 审批 + `contents: write` 权限）
  3. **Skill 兜底扩展 `.trae/skills/git-merge-guardian/SKILL.md`**：模式 A/B 清理当前分支后，额外执行一次遗留分支巡检，dry-run 报告展示给用户，确认后才 execute
- **涉及文件**：
  - 新增：`scripts/branch_governance.py`、`.github/workflows/branch-cleanup.yml`、`tests/test_branch_governance.py`
  - 修改：`.trae/skills/git-merge-guardian/SKILL.md`（新增「分支生命周期治理」段落）、`tests/run_regression_suite.sh`（新增第 10 步分支治理回归断言，原 `[1/9]~[9/9]` 同步改为 `[1/10]~[10/10]`）
- **回归测试**：
  - `tests/test_branch_governance.py`：
    - `test_ancestor_fast_path_confidence_one`：merge-base ancestor 命中 → confidence=1.0
    - `test_dry_run_identifies_equivalent_merged_branch`：分支独有提交的文件内容在 master 一致但非 ancestor → 标记删除候选
    - `test_dry_run_keeps_branch_with_unique_changes`：分支含 master 未应用改动 → 标记保留
    - `test_protected_branches_never_deleted`：master/gh-pages 即便匹配 pattern 也不被 execute 删除
    - `test_execute_requires_yes_flag`：execute 无 `--yes` → 退出码非 0，无删除
    - `test_pattern_filter_excludes_unrelated`：pattern=`trae/agent-*` 时 `feature/other` 不进报告
  - `tests/run_regression_suite.sh` 第 10 步（脚本级冒烟）：
    - `python scripts/branch_governance.py --help` 退出码 0
    - `python scripts/branch_governance.py --mode dry-run --pattern "trae/agent-*"` 退出码 0
    - dry-run 报告含「保护分支」段落，master 出现在保留列表
    - execute 无 `--yes` 时拒绝执行（退出码非 0）
- **复现步骤**：
  1. 在远程创建若干 `trae/agent-test-*` 分支并合入 master（不走 PR，用 `git merge --no-ff` 后 `git push origin master --no-verify`）
  2. 删除当前分支后，观察其他 agent 分支是否仍残留
  3. 运行 `git branch --merged origin/master`，观察是否漏报这些已等价合入的分支
- **教训/沉淀**：当工作流绕过 PR（直接合入 master）时，传统 git 合并检测（`--merged`、merge-base ancestor）会失效，所有依赖「分支是否已合入」的工具（分支清理、stale bot、覆盖率统计）都需要补一套「等价合入」判定逻辑。Skill 的分支清理不能只盯当前分支，必须做一次全局巡检；CI 与 skill 共用同一治理脚本，保证判定口径一致。

## 现代职场专栏质检规则误报与内容残留问题（引用冗余、术语硬套、白名单缺失）

- **编号**：BUG-024
- **首次出现**：2026-06-25
- **类型**：数据 / 兼容性
- **环境**：《职场沟通课》67 章内容质检
- **现象**：67 章中 13-17 篇停留在 93-96 分（目标 ≥97）。具体表现：①12 处「大意据《XX》」引用标注冗余（正文已写"XX在《YY》里/中讲过…"，句末又挂"（大意据《YY》）"）；②2 处「底层操作系统」现代术语硬套；③`check_mixed_language` 把 KPI/HR/offer/bug/BATNA 等行业通用词误报为中英文混杂；④`check_ai_tone` 把"不是X而是Y""可见""第X层""容易被忽略"等常见中文误报为 AI 味；⑤`REDUNDANT_CITATION_PATTERN` 只匹配「在《XX》里」，漏掉「在《XX》中」句式，导致 4 处冗余漏报。
- **根因**：
  1. `src/utils/content_quality.py` 的 `REDUNDANT_CITATION_PATTERN` 正则只覆盖「里」字，漏「中」字。
  2. `check_mixed_language` / `check_ai_tone` 继承自 `quality.py`，原为古籍讲书设计，对现代职场专栏未做白名单/过滤，产生大量误报。
  3. 内容侧子 Agent 生成时倾向在"XX在《YY》里讲过…"句末再挂"（大意据《YY》）"以求严谨，反成冗余；"底层操作系统"比喻虽生动但属现代术语硬套。
- **修复**：
  1. 内容修复 14 处：12 处删除句末「（大意据《XX》）」冗余标注（保留正文出处）；2 处「底层操作系统」重写为「人品是底子」，比喻改为「楼上的装饰/地基」。
  2. 规则优化 `src/utils/content_quality.py`：
     - `REDUNDANT_CITATION_PATTERN` 扩展为 `在《[^》]+》[里中]…`，覆盖两种句式。
     - 新增 `MODERN_ENGLISH_WHITELIST`（22 个行业通用词）和 `check_mixed_language_modern()`。
     - 新增 `MODERN_AI_OVERSTRICT_PATTERNS`（8 个敏感模式）和 `filter_ai_tone_for_modern()`。
     - `run_content_quality_checks()` 在 `is_modern` 时改用上述新函数。
  3. 文档/技能同步：`content-quality.md` §8.2、`content-review/SKILL.md` 现代职场额外检查项补充白名单和 AI 味放宽说明。
- **涉及文件**：`src/utils/content_quality.py`、`.trae/skills/deep-reading/content-quality.md`、`.trae/skills/content-review/SKILL.md`、`output/职场沟通课/` 下 13 个 .md 文件（终极意义_职场的终极是人品.md + 12 个冗余修复文件）
- **回归测试**：
  - `python scripts/check_book_structure.py --output output --strict`：0 问题
  - `run_content_quality_checks` 全 67 章：最低 97，最高 100，平均 99.4，≥97 分 67/67
  - 分类排序核对：`_meta.yaml sort=103` 无冲突；10 组 `chapter_sort` 0-9 连续；组内 `sort` 1 起递增无跳号
- **教训**：
  1. 质检规则按内容类型分化——古籍与现代专栏的"正常表达"边界不同（如「不是X而是Y」对古籍是 AI 味，对现代职场是常见判断句）。未来新增非史类专栏应先识别内容类型再套用对应规则集，避免一刀切误报。
  2. 子 Agent 修复后报告"已修"不可轻信，主流程必须重跑 `run_content_quality_checks` 验证分数达标（本次「底层操作系统」第一次 Agent 只改 1 处变体，漏 2 处）。
  3. 引用标注冗余是子 Agent 通病，写作规范应明确「正文已写明出处的，句末不再挂大意据标注」。

---

## branch_governance dry-run 无候选时输出缺失保护分支段落

- **编号**：BUG-025
- **首次出现**：2026-06-26
- **类型**：构建
- **现象**：`python scripts/branch_governance.py --mode dry-run --pattern "trae/agent-*" --no-fetch` 在无远端分支时只输出"未找到远端分支"，不含"保护分支"或"protected"段落，导致 `tests/run_regression_suite.sh` 第 10 步失败。
- **根因**：`branch_governance.py` 第 479-481 行，当 `all_branches` 为空时直接 `print("未找到远端分支"); return 0`，跳过了 `format_report()`，而 `format_report()` 才是输出"保护分支"段落的函数。
- **修复**：无候选分支时仍调用 `format_report(reports=[], protected=protected, ...)` 输出完整报告（含保护分支段落），再 return 0。
- **涉及文件**：`scripts/branch_governance.py`
- **回归测试**：`tests/run_regression_suite.sh` 第 10 步"dry-run 报告含保护分支段落"现已通过（18/18）

---

## 内容中"N 个字：X"等数字事实硬错误

- **编号**：BUG-026
- **首次出现**：2026-06-26
- **类型**：数据
- **现象**：灵魂注入试点（明纪·海瑞上疏）中，AI 写出"靠的就是两个字：刚"（刚是一个字）、"得从二十年前说起"（实际 17 年）、"嘉靖四十五年二月上疏"（实际嘉靖四十四年冬）等数字事实硬错误。
- **根因**：
  1. AI 在写作时套用"N 个字：X"句式模板时未核对实际字数。
  2. 涉及年份/年龄时靠估算而非核对史料。
  3. 现有 `quality.py` 无数字事实检查函数。
- **修复**：
  1. `src/utils/quality.py` 新增 `check_numeric_facts(text)`：自动检测"N 个字：X"且 `len(X) != N` 的硬错误；标记"N 年前/N 岁/N 品官"供 Agent 复核。
  2. `.trae/skills/deep-reading/rules.md` §6.5 新增"数字事实硬约束"：涉及数字必须核对，不能靠估算。
  3. `.trae/skills/deep-reading/content-quality.md` §9.3 新增"数字事实检查"扣分规则。
- **涉及文件**：`src/utils/quality.py`、`.trae/skills/deep-reading/rules.md`、`.trae/skills/deep-reading/content-quality.md`、`output/明纪/嘉靖隆庆与张居正改革_海瑞上疏.md`
- **回归测试**：`check_numeric_facts` 已接入 `run_quality_check` / `run_quality_checks` 主质检流程；`check_ai_cliches` 同步接入。
- **教训**：
  1. AI 写作的"低级事实错误"（字数/年份/年龄）不该靠人工 review 发现，必须有自动化拦截。
  2. 灵魂注入（活人感/史观穿透）与合规（数字事实）是两类独立问题，不能互相替代——灵魂再好，数字错了仍是 P0。
  3. superpowers 的 `verification-before-completion` 技能对此有直接指导：声称完成前必须运行验证命令并确认输出，证据先于断言。

---

## 质检规则一刀切误报非史类专栏（archetype 分桶修复）

- **编号**：BUG-027
- **首次出现**：2026-06-26
- **类型**：数据 / 兼容性
- **现象**：理财课被报"缺年份/缺名家/时间线缺失"，AI 课被报"中英文混杂"——均因质检层用古籍规则一刀切。`_is_modern_column` 关键词列表仅 8 词（职场/沟通/面试/商科/心理学/管理/营销/销售），漏掉财/技/养生三类；`_is_philosophy_or_classic` 9 词同样不全。同时 BUG-026 新增的 `check_numeric_facts`/`check_ai_cliches` 根本没接入 `run_content_quality_checks`，通用检查形同虚设。
- **根因**：
  1. 类型信号未进质检层：`category`/`archetype` 只在展示层和生成层用，质检层靠书名子串匹配做"逃生阀"，新增专栏必漏。
  2. `run_content_quality_checks` 缺 archetype 参数，无法按桶路由规则集。
  3. `check_numeric_facts` 的 manual_review（N年前后/N岁）对 modern/knowledge 误标（现代语境"10年前""30岁"是正常表达）。
- **修复**：
  1. `src/utils/content_quality.py`：删除 `_is_modern_column`/`_is_philosophy_or_classic`，`run_content_quality_checks(content, archetype="narrative")` 按 design.md §8 路由表分桶。narrative 全开古籍规则；modern/knowledge 跳过年份/名家/时间线/现代术语禁用。
  2. 通用检查全桶共享：`check_ai_cliches`/`check_numeric_facts` auto_errors 全桶都跑（接入时 `_strip_frontmatter` 避免 frontmatter 数字误标）。
  3. 新增 `_filter_numeric_manual(manual, archetype)`：narrative 保留 N年前后/N岁，modern/knowledge 过滤误标。
  4. 新增 `KNOWLEDGE_TERMS_WHITELIST`（27 词）和 `check_mixed_language_knowledge()`，按长度降序替换避免短词破坏长词。
  5. 非法 archetype 抛 `ValueError`（fail-fast），不静默走混合态。
  6. `scripts/review_content.py` 加 `--archetype` CLI + `_meta.yaml` 读取，规则化质检报告并入输出。
  7. `.trae/skills/deep-reading/content-quality.md` §8 从"补救条款"重构为"多桶并行规则集"。
- **涉及文件**：`src/utils/content_quality.py`、`src/agents/content_reviewer.py`、`scripts/review_content.py`、`.trae/skills/deep-reading/content-quality.md`
- **回归测试**：`tests/test_content_quality_archetype.py` 34 项契约测试。质检分数对比：理财课·ETF 84→100（+16）；AI课·Transformer 81→97（+16）；资治通鉴·三家分晋 100（无回归）。
- **教训**：
  1. 关键词逃生阀是"没接类型信号的补丁"，新增专栏必漏——必须用显式 archetype 字段做路由信源。
  2. 禁区红线（quality.py 零改动）能用调用层路由守住：manual_review 过滤放 `_filter_numeric_manual`，不碰 quality.py 内部。
  3. 通用检查（数字/套话）全桶共享是 BUG-026 教训的延续：合规类不分桶，灵魂类才分桶。

---

## check_temporal_order 首段拆分失败（正则未匹配行首 ##）

- **编号**：BUG-028
- **首次出现**：2026-06-26
- **类型**：数据
- **现象**：narrative 桶对"## 讲事情\n这里没写年份。"应报"讲事情段落缺少时间/年份标注"，但实际未报（sequence 为空）。黄金样本虽过，但缺年份的讲事情段落漏检。
- **根因**：`check_temporal_order` 用 `re.split(r"\n## ", body)` 拆分章节，但 `_strip_frontmatter` 后 body 以 `## ` 开头（首段前无 `\n`），导致首段 `## 讲事情` 未被拆分，`section.startswith("讲事情")` 在 `"## 讲事情..."` 上失败。
- **修复**：`src/utils/content_quality.py` 的 `check_temporal_order` 拆分正则改为 `re.split(r"(?:^|\n)## ", body)`，用 `(?:^|\n)` 兜底首段无前缀换行的情况。
- **涉及文件**：`src/utils/content_quality.py`
- **回归测试**：`tests/test_content_quality_archetype.py::TestNarrativeBucketKeepsAncientRules::test_narrative_reports_temporal_order` 断言首段 `## 讲事情` 无年份时必报。
- **教训**：`re.split(r"\n## ", body)` 这类"按换行+标记拆分"的模式要考虑首段无前缀换行的情况，统一用 `(?:^|\n)` 兜底。

## --archetype fiction 触发 build_workflow ValueError（跨层 archetype 白名单不一致）

- **编号**：BUG-029
- **首次出现**：2026-06-27
- **类型**：兼容性
- **现象**：执行 `src/main.py --archetype fiction` 时，`build_workflow(archetype="fiction")` 抛 `ValueError: 非法 archetype: 'fiction'` 崩溃，CLI 直接退出非 0。
- **根因**：`src/utils/prompts._VALID_ARCHETYPES` 含 `"fiction"`（design.md §5.2 预留桶），但 `src/core/workflow._VALID_ARCHETYPES` 只含 `narrative/modern/knowledge`（fiction 未落地）。两层白名单不一致；`resolve_archetype` 认 `fiction` 合法并透传，`build_workflow` 却拒绝。原回落逻辑放在 stub 分支之后，stub 路径走不到。
- **修复**：`src/main.py` 将 fiction→narrative 回落统一移到 `resolve_archetype` 之后、stub/真实分支之前（单一拦截点），未落地 archetype 一律回落 narrative 并打 stderr 警告。
- **涉及文件**：`src/main.py`
- **回归测试**：`tests/test_workflow_archetype.py::TestStubModeArchetype::test_fiction_falls_back_to_narrative` 断言 `--archetype fiction` 退出码 0、生成 narrative 6 段、stderr 含回落警告。
- **教训**：跨层枚举白名单必须单一信源；预留桶在 CLI 层应 fail-soft 回退（回落 + 警告）而非透传到下游崩溃。回落逻辑要放在所有分支之前，不能放在某个分支之后。

## PyYAML 未装时 stub 路径读取 quality_check 崩溃（_get_stub_sections 对 list 不兜底）

- **编号**：BUG-030
- **首次出现**：2026-06-27
- **类型**：兼容性 / 环境
- **现象**：在未安装 PyYAML 的环境跑 `python src/main.py --archetype narrative --stub`，`_get_stub_sections` 抛 `AttributeError: 'list' object has no attribute 'get'`，stub 路径崩溃退出非 0。
- **复现步骤**：
  1. `pip uninstall pyyaml -y`
  2. `python src/main.py --book 资治通鉴 --chapter 周纪二 --event 测试 --archetype narrative --stub --dry-run`
  3. 退出码非 0，stderr 含 `AttributeError: 'list' object has no attribute 'get'`
- **根因**：`src/utils/config.load_config` 在 PyYAML 未装时 fallback 到内置简单 YAML 解析器，该解析器无法处理 `quality_check` 的嵌套结构（`enabled: true` + `required_sections: [...]`），把整段解析成 list `["enabled", "required_sections"]`。`_get_stub_sections` 和 `workflow.get_required_sections` 直接 `qc.get("required_sections", ...)`，list 无 `.get` 方法 → AttributeError。
- **修复**：`src/main.py:_get_stub_sections` 加 isinstance 兜底——`cfg` 非 dict 或 `quality_check` 非 dict 时，直接返回 narrative 默认六段（保证 stub 路径不崩）。这是防御性修复，不改主流程。
- **涉及文件**：`src/main.py`（`_get_stub_sections` 加 isinstance 兜底）
- **回归测试**：`tests/test_skill_archetype_routing.py::test_get_stub_sections_pyyaml_missing_does_not_crash` 用 monkeypatch 模拟 PyYAML 未装时 `load_config` 返回的异常结构（`quality_check` 是 list），断言返回 narrative 默认六段不抛异常。
- **教训**：
  1. 环境降级路径（PyYAML 未装 fallback 内置解析器）的产物类型与正常路径不一致（dict vs list），下游消费者必须 isinstance 兜底，不能假设结构。
  2. 内置简单 YAML 解析器对嵌套结构的处理是脆弱点，未来应评估是否强制 PyYAML 依赖或重写解析器。
- **待办**：`src/core/workflow.py:get_required_sections`（行 65-66）有相同 bug，在会话A+B 范围内，本会话不修（避禁区冲突）。装 PyYAML 后该路径不触发，CI 装依赖则不暴露。

## plan-review skill 环境缺失时硬阻塞无降级路径

- **编号**：BUG-031
- **首次出现**：2026-06-27
- **类型**：兼容性 / 工具链
- **现象**：每次调用 `plan-review` skill 都会硬阻塞在两个点：
  1. 默认模式：`scripts/review_plan.py` 检测到 `LLM_API_KEY` 未配置，直接 `return 1` 退出。
  2. Mock 模式：`from src.core.plan_review_workflow import build_review_workflow` 触发 `ModuleNotFoundError: No module named 'langgraph'`，裸 traceback 后退出。
  skill v1.0.0 仅设计了路径 B（langgraph Python 引擎），无任何降级路径，环境不满足时评审完全跑不起来。skill 文档「错误处理」章节还含 `scripts/review_plan.py 不存在` 的误导条目——但文件实际存在（commit `bfd342c` 添加，git 历史从未删除）。
- **根因**：
  1. skill v1.0.0 把路径 B（langgraph 真并行）当成唯一路径，未考虑 `.env` / `langgraph` 缺失场景。
  2. dev-workflow.md §零虽规定 Skill 不能调度 sub-agents（指 Skill 文件本身不能），但 Trae 的 `Task` 工具（`subagent_type` 参数）支持会话内启动 subagent——这条原生能力未被 skill 利用。
  3. `scripts/review_plan.py` 延迟导入 `langgraph` 时未捕获 `ImportError`，直接抛裸 traceback。
  4. skill 文档「错误处理」章节把不存在的 `scripts/review_plan.py 不存在` 当作分支处理，与实际文件状态不符，误导调用方。
- **修复**：
  1. `.trae/skills/plan-review/SKILL.md` 升级到 v2.0.0：主路径改为**会话内用 `Task` 工具启动 3 个 `general_purpose_task` subagent 并行评审**（架构师/测试/规则），主 Agent 汇总；路径 B 降级为可选增强；环境缺失时不硬阻塞，自动走主路径。
  2. 新增 `.trae/skills/dispatching-parallel-agents/SKILL.md`：原生自 `obra/superpowers`（MIT），适配 Trae Task 工具，提供并行调度纪律（同一响应多 Task = 并行、subagent 指令自包含、返回后检查冲突）。
  3. `scripts/review_plan.py` 延迟导入 `langgraph` 处加 `try/except ImportError`，输出友好提示（含主路径替代方案）而非裸 traceback。
  4. 删除 skill 文档「错误处理」里 `scripts/review_plan.py 不存在` 的误导条目。
- **涉及文件**：`.trae/skills/plan-review/SKILL.md`、`.trae/skills/dispatching-parallel-agents/SKILL.md`（新增）、`scripts/review_plan.py`
- **回归测试**：
  - `tests/test_plan_review_skill.py`：19 项测试（18 项文档契约 + 1 项 review_plan.py 降级行为测试），覆盖主路径定义、并行调度、路径 B 降级、错误处理无误导条目、三角色齐备、报告结构、版本历史、langgraph 缺失时退出码 1 + 友好提示 + 无裸 traceback。
  - `tests/run_regression_suite.sh` 第 11 步：脚本级断言 SKILL.md 含「主路径」「Task」「subagent_type」「不硬阻塞」关键词。
- **教训**：
  1. Skill 设计要区分「Skill 文件本身的能力」与「Trae 原生工具的能力」——Skill 不能调度 sub-agents，但 Skill 可以引导主 Agent 使用 `Task` 工具。dev-workflow.md §零的「Skill 不能调度 sub-agents」不等于「会话内不能并行」。
  2. 任何依赖外部环境（`.env` / 第三方包）的 skill 必须有降级路径，禁止硬阻塞。主路径应优先选择无外部依赖的方案。
  3. skill 文档的「错误处理」章节必须与实际文件/环境状态一致，不能写「文件不存在」这种与 git 历史不符的分支。
  4. obra/superpowers 当时判定 `dispatching-parallel-agents`「依赖原生 subagent 调度，Trae 做不到」已过时——Trae Task 工具支持 `subagent_type`，会话内并行是原生能力。技术判定需要随工具能力更新而复核。

## 专栏正文方括号引用编号打断阅读体验

- **编号**：BUG-032
- **首次出现**：2026-06-28
- **类型**：UI / 内容可读性
- **环境**：高考志愿填报前置认知专栏，全平台（站点 + 源 Markdown）
- **现象**：16 章正文里穿插 `[OFFICIAL-x]/[EXPERT-x]/[INDUSTRY-x]/[PSYCH-x]/[BOOK-x]/[VIDEO-x]` 编号共 407 处，高三学生和家长看不懂是什么，需要去 `_参考资料.md`（`_` 前缀被 build_site 跳过，根本没出现在站点里）查编号才能知道信源是谁，打断阅读。
- **根因**：Phase 1 设计的"置信度溯源范式"（loop_log L1205）把引用编号当学术论文引用写进正文，但专栏面向 C 端读者而非学术读者，编号体系未考虑读者体验；`_参考资料.md` 用 `_` 前缀导致站点不收录，编号失去对应入口。
- **修复**：
  1. 16 章正文里所有 `[XXX-x]` 编号从行文中删除，信源信息以作者/书名/机构名内联说明（如"张雪峰在《选择比努力更重要》中指出"），保留信源对应的内容（金句/数据本身）不删。
  2. 每章末尾新增 `## 本章参考资料` 小节，按出现顺序去重列出本章引用的信源（用作者/书名/机构名而非编号）。
  3. `_参考资料.md` 从"编号清单"改为"按类别列出主要参考资料"清单，不再参与编号对应。
- **涉及文件**：`output/高考志愿填报前置认知/` 下 16 章正文 + `_参考资料.md`
- **回归测试**：
  - Grep 确认 16 章正文无残留 `[(OFFICIAL|EXPERT|INDUSTRY|PSYCH|BOOK|VIDEO)-\d+]` 编号
  - Grep 确认每章末尾有 `## 本章参考资料` 小节
  - 抽查 3 章确认正文语义连贯（无"据[]数据显示"空引用）
  - `check_book_structure.py --strict` 通过
  - `pytest` 通过
- **教训**：C 端专栏的引用溯源不能照搬学术论文的编号体系——编号适合内部审稿，不适合面向读者。信源应以作者/书名/机构名内联说明或集中放章末，让读者一眼知道出处。`_` 前缀文件被 build_site 跳过的机制要纳入引用体系设计考虑。

## 书架首页“阅读”按钮文案与行为不匹配

- **编号**：BUG-033
- **首次出现**：2026-06-28
- **类型**：UI / 交互
- **环境**：豪书斋静态站点首页，移动端与桌面端
- **现象**：顶部 header 的“开始阅读”（移动端显示为“阅读”）按钮点击后弹出模态框，提示“静态站点不支持在线生成。请在本地运行以下命令生成笔记后，重新构建站点……”，而非进入阅读流程；按钮文案像阅读入口，实际行为却是“生成新笔记”命令。
- **复现步骤**：
  1. 打开豪书斋首页
  2. 点击顶部“开始阅读”或“阅读”按钮
  3. 观察到弹出模态框，内容是本地生成命令
- **根因**：`newNoteBtn` 最初是“生成新笔记”按钮，事件处理器绑定 `openModal()`；后续 commit `14fbe69` 把按钮文案改为“开始阅读/阅读”，但 `src/web/static-site/js/app.js` 中的 `addEventListener('click', openModal)` 未同步替换为跳转行为，导致文案与行为脱节。
- **修复**：
  1. 新增 `scrollToBookshelf()` 函数，平滑滚动到 `#bookshelf` 区域。
  2. 将 header 中 `newNoteBtn` 与 `newNoteLink` 的点击处理器从 `openModal()` 改为 `scrollToBookshelf()`。
  3. 保留 toolbar 中“生成新笔记”按钮（`newNoteBtnToolbar`）的 `openModal()` 行为，避免误改。
  4. 同步更新 `src/web/static/js/app.js`、`site/js/app.js` 与 `site/sw.js`、`src/web/static-site/sw.js` 缓存版本号（`halo-read-v6`），确保移动端旧缓存失效。
- **涉及文件**：`src/web/static-site/js/app.js`、`site/js/app.js`、`src/web/static/js/app.js`、`src/web/static-site/sw.js`、`site/sw.js`
- **回归测试**：
  - `tests/test_reader_features.js` 测试18：点击首页 `newNoteBtn` 后，`#bookshelf` 的 `scrollIntoView` 被调用
  - `tests/run_regression_suite.sh` 第2步：`site/js/app.js` 语法检查
  - `tests/run_regression_suite.sh` 第4步：构建静态站点后校验关键资源
  - `python scripts/check_book_structure.py --output output --strict` 通过
  - `pytest -q` 通过
- **教训**：按钮文案变更必须同步审视其事件处理器；静态站点/PWA 的前端行为修复必须同步升级 Service Worker 缓存名，否则 PC 端正常、手机端仍旧的“幽灵版本”会反复出现。

## 圣贤堂图片加载慢且标题链接 404

- **编号**：BUG-034
- **首次出现**：2026-06-28
- **类型**：性能 / 链接 / 部署
- **环境**：圣贤堂展厅页 `demos/saints_hall.html`，部署到 `site/demos/saints_hall.html`
- **现象**：
  1. 圣贤堂人物头像加载慢，首屏 5 张卡片同时加载时感知明显。
  2. 点击有链接的圣人名言/事迹标题，跳转后显示 404，无法进入对应章节阅读页。
- **复现步骤**：
  1. 打开圣贤堂页面（本地 `demos/saints_hall.html` 或部署后 `site/demos/saints_hall.html`）。
  2. 观察头像加载：无占位、无懒加载，5 张高分辨率图片同时请求。
  3. 点击孔子“学而时习之”或“夹谷之会”等带 ↗ 标记的链接，部署版本会跳转到不存在的 `/site/index.html?book=...`。
- **根因**：
  1. **图片慢**：头像虽已本地化（`demos/images/*.jpg`），但单张 912×1216 约 200KB，无懒加载、无占位骨架、无缩略图，首屏 5 张同时解码渲染。
  2. **404**：`saints_hall.html` 内部链接写死 `../site/index.html?...`，适合在本地 `demos/` 目录打开；但 `build_site.py` 会把它复制到 `site/demos/`，相对路径被错解析为 `site/site/index.html`，导致部署后 404。
- **修复**：
  1. 图片优化：
     - 为头像生成 400px 宽缩略图到 `demos/images/thumbs/`（体积从 ~3.4MB 降到 ~700KB）。
     - `saints_hall.html` 默认加载缩略图，并通过 `srcset` 在 2x/高清屏回退到原图。
     - 添加 `loading="lazy"`、`decoding="async"`、width/height 属性减少 CLS。
     - 添加占位骨架与渐显动画，预加载首屏孔子头像。
  2. 链接修复：
     - 源文件保留 `../site/index.html?...`，保证本地直接打开可用。
     - `build_site.py` 复制到 `site/demos/` 时自动把 `../site/index.html?` 重写为 `../index.html?`。
  3. 构建脚本：`build_site.py` 新增 `_ensure_sage_portrait_thumbnails()` 自动生成/更新缩略图，并复制 `images/thumbs/` 到 `site/demos/images/thumbs/`。
  4. 依赖：`requirements.txt` 新增 `Pillow>=10.0`。
- **涉及文件**：`demos/saints_hall.html`、`scripts/build_site.py`、`requirements.txt`、`site/demos/saints_hall.html`（构建产物）、`site/demos/images/thumbs/`（构建产物）
- **回归测试**：
  - `tests/run_regression_suite.sh` 第4步：构建静态站点成功
  - `tests/run_regression_suite.sh` 第9步：HTTP 冒烟测试关键资源 200
  - 部署后检查 `site/demos/saints_hall.html` 中链接为 `../index.html?book=`
  - `pytest -q` 通过
  - `python scripts/check_book_structure.py --output output --strict` 通过
- **教训**：
  1. 独立演示页被复制到 `site/` 下部署时，必须处理相对路径变化；源文件路径与部署路径不一致时，应通过构建脚本重写而非要求源文件同时适配两种路径。
  2. 图片本地化不等于性能合格：还需匹配显示尺寸的缩略图、懒加载、占位骨架，才能避免首屏同时下载多张高清图。
  3. 新依赖（Pillow）必须落到 `requirements.txt`，否则 CI/新环境构建时会跳过缩略图生成。

## 夸克浏览器阅读模式无法识别 SPA 动态正文

- **编号**：BUG-035
- **首次出现**：2026-06-29
- **类型**：兼容性 / 架构
- **环境**：夸克浏览器（移动端为主）、所有不执行 JS 的浏览器/搜索引擎爬虫
- **现象**：用户用夸克浏览器打开章节阅读页，夸克阅读模式不识别正文，提示"暂不支持"或书本图标不出现；手动切换也失败。但 PC Chrome / 微信内置浏览器均正常。
- **复现步骤**：
  1. 夸克浏览器打开任意章节页（如 `/site/index.html?book=明纪&path=明纪/永乐盛世与仁宣之治_永乐盛世.md`）。
  2. 观察地址栏：无书本图标。
  3. 菜单强制启用"阅读模式"：提示"暂不支持此页面"。
  4. 查看原始 HTML 源码：`<body>` 中正文区为空 div，仅 `<script src="js/app.js">`。
- **根因**（第一性原理分析）：
  1. **SPA 动态渲染**：`src/web/static-site/index.html` 的正文区是空 `<div id="readerView">`；正文由 `src/web/static-site/js/app.js` 的 `loadNote()` 通过 `fetch + marked.parse` 异步注入。原始 HTML 不含正文文本。
  2. **夸克阅读模式不执行 JS**：夸克阅读模式基于原始 HTML 的语义识别（要求 `<article>` 包裹、`<h1>` 标题层级、`<p>` 段落、正文占比 ≥70%、连续段落 ≥800 字符），不渲染 JS 动态内容。SPA 模式下夸克看到的"正文区"为空，故判定"无有效正文"。
  3. 仅优化现有 `<article>` 标签或加 `og:` 元数据无法解决——根因是正文根本不在原始 HTML 里。
- **修复**（SSG 静态生成方案）：
  1. **新增构建期 SSG**：`scripts/build_site.py` 新增 `_build_ssg_pages()`，为每篇笔记渲染独立静态 HTML 到 `site/reader/{书}/{章节}_{事件}.html`，原始 HTML 直接含 `<article>` + `<h1>` + `<p>` + 正文（构建期由 Python `markdown` 库渲染 + `bleach` 净化）。873 篇笔记全部生成。
  2. **SSG 模板不引 app.js**：避免与 SPA 形成双渲染路径分叉；SSG 页面是"无 JS 降级入口"，浏览器/搜索引擎/夸克可直接消费。
  3. **CSS 复用**：SSG 模板引用现有 `css/style.css`（相对路径 `../../css/style.css`），与 SPA 共享视觉风格。
  4. **SW 缓存策略**：`src/web/static-site/sw.js` bump `CACHE_NAME` v6→v7（避免幽灵旧版，BUG-018 教训），新增 `isReaderHtmlRequest()` 对 `/reader/*.html` 走 cacheFirst。
  5. **依赖**：`requirements.txt` 新增 `markdown>=3.6` + `bleach>=6.1`；CI 安装后自动启用 SSG。
  6. **index 页**：每本书生成 `site/reader/{书}/index.html` 目录页；全站生成 `site/reader/index.html` 全章节总索引页。
- **涉及文件**：
  - `scripts/build_site.py`（新增 SSG 模块 + build_site 调用）
  - `src/web/static-site/sw.js`（CACHE_NAME v7 + isReaderHtmlRequest cacheFirst）
  - `requirements.txt`（markdown + bleach）
  - `.gitignore`（排除 site/reader/）
- **回归测试**：
  - `tests/test_ssg_chapter_pages.py`：20 项断言，覆盖生成性/语义结构/不引 app.js/正文内联/SSG vs marked.js 一致性/bleach 净化/索引页/幂等性/prev-next 导航
  - `tests/run_regression_suite.sh` 第9步：新增 `/reader/index.html` HTTP 200 + SSG HTML `<article>`/`<h1>`/`<p>` grep 断言 + 反向断言"不引 app.js / 不依赖 fetch"
  - `python scripts/check_book_structure.py --output output --strict` 通过
  - `pytest -q` 通过
- **教训**：
  1. **第一性原理**：兼容性问题的根因若在架构层（SPA vs SSG），仅做表面优化（加 `<article>` 标签、加 meta）无效；必须从"原始 HTML 是否含正文"这个根本问题入手。
  2. **不引 app.js 是关键决策**：SSG 模板若引 app.js，会产生"SSG 也走 SPA 动态渲染"的双渲染路径分叉，违背 SSG 的存在意义；模板必须独立、静态、可被无 JS 浏览器消费。
  3. **MD 是唯一真源**：SSG HTML 不需要单独维护，跑 `build_site.py` 自动从 `output/` 的 MD 重新渲染；MD 改了 SSG 自动同步。
  4. **缓存必须 bump**：SW cacheFirst 资源变更时必须升级 `CACHE_NAME`，否则手机端会持续看到旧 SSG（BUG-018 教训的延续）。
  5. **bleach 净化是底线**：构建期把 MD 渲染成 HTML 时必须经过 bleach 白名单净化，避免历史 MD 中可能藏的 `<script>` 注入到 SSG 页面。

## 移动端沉浸模式丢失整屏全屏（BUG-021 副作用回归）

- **编号**：BUG-036
- **首次出现**：2026-06-29
- **类型**：兼容性 / UI
- **环境**：移动端浏览器（Chrome、夸克、UC 等），小米浏览器需特殊处理
- **现象**：用户点击"沉浸"按钮后，仅浏览器视口内全屏（body 隐藏 UI），但浏览器地址栏和底部操作栏仍可见；此前是整个屏幕全屏（地址栏/操作栏自动隐藏）。
- **根因**：BUG-021 修复"沉浸模式强制横屏"时，**彻底移除了 Fullscreen API**（requestFullscreen / exitFullscreen 及 webkit 前缀），改为纯 CSS 沉浸（`body.immersive-mode` + `body.ui-hidden` 隐藏内部 UI）。副作用是丢失了"隐藏浏览器 chrome（地址栏/操作栏）"的能力，沉浸模式从"整屏全屏"退化为"视口内全屏"。
- **修复**（BUG-021 修正版，重新引入 Fullscreen API 但加三重护栏）：
  1. `src/web/static-site/js/app.js` 的 `enterImmersiveMode` 重新调用 `requestFullscreen`（含 `webkitRequestFullscreen` 前缀）实现整屏全屏；`exitImmersiveMode` 对应调用 `exitFullscreen`。
  2. **不调用 `screen.orientation.lock`**——这是 BUG-021 强制横屏的真正根因之一，本次严格保持禁用。
  3. **小米浏览器 UA 跳过 Fullscreen API**：新增 `isXiaomiBrowser()` 检测 `MiuiBrowser` 关键字，小米浏览器 `requestFullscreen` 会强制横屏（BUG-021 现象），故仅用纯 CSS 沉浸。
  4. **Fullscreen 失败时 fallback 到纯 CSS 沉浸**：保留 `body.immersive-mode` + `body.ui-hidden`，`.catch` 静默回退，不影响用户进入沉浸。
  5. `resetViewState`（bfcache 恢复兜底）补充：若仍处于 Fullscreen 状态则退出，避免 bfcache 恢复后卡在全屏。
  6. `src/web/static-site/sw.js` 与 `site/sw.js` bump `CACHE_NAME` v7→v8，规避手机端旧 app.js 缓存。
- **涉及文件**：
  - `src/web/static-site/js/app.js`（沉浸模式函数重写 + resetViewState 全屏退出兜底）
  - `src/web/static-site/sw.js`、`site/sw.js`（CACHE_NAME v8）
  - `site/js/app.js`（由 `build_site.py` 自动同步）
- **回归测试**：
  - `tests/test_reader_features.js` 测试11：断言从"不调用 Fullscreen API"改为"调用 Fullscreen API + 不调用 orientation.lock + 含 isXiaomiBrowser/MiuiBrowser"
  - `tests/run_regression_suite.sh` 第3步：同步更新为"调用 Fullscreen + 小米 UA 跳过"两个断言
- **教训**：
  1. **bug 修复要区分"问题 API"与"问题 API 的滥用方式"**：BUG-021 把 Fullscreen API 整体禁用是过度反应，真正的根因是 `orientation.lock` + 小米浏览器的 `requestFullscreen` 副作用。正确做法是禁用 orientation.lock、对问题浏览器 UA 跳过、其余浏览器正常使用 Fullscreen API。
  2. **副作用回归要主动追踪**：BUG-021 修复后丢失"整屏全屏"是可预见的副作用，但当时未补"整屏全屏能力"的回归断言，导致用户再次反馈才发现。修复副作用类 bug 时应同步评估被牺牲的能力是否需要替代方案。
  3. **小米浏览器是国产兼容性重灾区**：其 `requestFullscreen` 行为与标准不符（强制横屏），UA 识别 + 跳过是务实方案。

## GitHub Actions 部署 workflow 语法错误 + SSG 依赖缺失

- **编号**：BUG-037
- **首次出现**：2026-06-29
- **类型**：构建 / 部署
- **环境**：GitHub Actions（push to master 触发 `branch-cleanup.yml`）
- **现象**：用户反馈 GitHub Pages 部署"偶现"失败，错误信息：`Invalid workflow file: .github/workflows/branch-cleanup.yml#L1 (Line: 38, Col: 17): Unrecognized named-value: 'github'`。
- **复现规律**：并非真正偶现——仅 `push` 事件触发时报错；`workflow_dispatch` 手动触发不报错。根因是 `github.event.inputs.mode` 在 push 事件下 `inputs` 为空，深层嵌套访问失败导致整个 `github` 命名值在 `permissions` 字段上下文被标为未识别。
- **根因**（两个独立问题）：
  1. **`branch-cleanup.yml` 第 36、38 行**：`environment` 和 `permissions.contents` 字段使用 `github.event.inputs.mode == 'execute' && ... `，GitHub Actions 在 `permissions` 字段的表达式上下文中无法可靠解析 `github.event.inputs` 的深层嵌套访问。
  2. **`pages.yml` / `deploy-modelscope.yml` 的 `pip install pyyaml`**：commit `ae56541` 引入的 SSG 章节页（BUG-035）依赖 `markdown` + `bleach`，但这两个部署 workflow 只装 `pyyaml`，导致 `build_site.py` 静默跳过 SSG 生成（打印告警但不报错），SSG 功能无法部署到 GitHub Pages / ModelScope。不报错但功能缺失，更隐蔽。
- **修复**：
  1. `branch-cleanup.yml` 第 36、38 行：`github.event.inputs.mode` → `inputs.mode`。`inputs` 是 workflow_dispatch 的官方推荐上下文，push 事件下 `inputs.mode` 为 null，`null == 'execute'` 为 false，安全回退到默认值（environment 为 ''，permissions.contents 为 'read'）。文件第 60 行原本就用 `inputs.mode`，本次修复消除了文件内不一致。
  2. `pages.yml` 第 42 行、`deploy-modelscope.yml` 第 27 行：`pip install pyyaml` → `pip install -r requirements.txt`，与 `regression.yml` 第 38 行保持一致，确保 SSG 依赖完整。
- **涉及文件**：
  - `.github/workflows/branch-cleanup.yml`（第 36、38 行表达式上下文修正）
  - `.github/workflows/pages.yml`（依赖安装改为 requirements.txt）
  - `.github/workflows/deploy-modelscope.yml`（依赖安装改为 requirements.txt）
- **回归测试**：
  - 本次未新增 workflow 语法 lint 脚本（GitHub 自带 yaml 解析校验，本地无等价工具；可后续考虑加 `actionlint`）
  - 通过本地模拟 `pages.yml` 完整步骤（`pip install -r requirements.txt` → `check_book_structure --strict` → `check_duplicates` → `build_site.py` → 校验 `site/data/index.json`）验证 SSG 生成 873 个 HTML
- **教训**：
  1. **`github.event.inputs` 在 `permissions`/`environment` 字段不可靠**：GitHub Actions 表达式上下文有限制，访问 workflow_dispatch inputs 应优先用 `inputs` 上下文（官方推荐），它在所有事件类型下都可安全求值（非 dispatch 事件下为 null）。
  2. **新增功能依赖必须同步更新所有 workflow 的依赖安装步骤**：BUG-035 在 `requirements.txt` 加了 `markdown`/`bleach`，但只更新了 `regression.yml`，遗漏了 `pages.yml` 和 `deploy-modelscope.yml`。`build_site.py` 的"静默跳过 + 打印告警"容错策略反而掩盖了这个问题（不报错但功能缺失）。新增构建依赖时，应 grep 所有 workflow 的 `pip install` 并统一更新。
  3. **"偶现失败"要查触发事件差异**：用户报"偶现"时，第一步应对比成功/失败两次的触发事件类型（push vs workflow_dispatch vs schedule），事件类型差异往往就是根因。

---

## 专栏字数声称前后不一致（大模型 token 统计误差）

- **编号**：BUG-038
- **首次出现**：2026-06-30
- **类型**：内容数据 / 质量
- **现象**：专栏中存在大量"某某某"四个字、"某某某某"这五个字、"五个字：某某某" 这类字数声称，但大模型生成时是按 token 统计而非按字符统计，导致声称字数与实际字数频繁对不上（多 1 个/少 1 个/完全错位）。这种低价数数错误让专栏显得 AI 味浓、质量差。
- **复现规律**：扫描全专栏 1112 个 Markdown 文件，发现 90 处字数声称与实际字符数不一致，覆盖模式 A（`N 个字：X`）、模式 B（`「X」这 N 个字`）、模式 C（`N 个字：「X」`）三种写法。
- **根因**（从第一性原理出发）：
  1. **字数是确定性事实**——任何中文文本的实际字数都可用 `len()` 精确算出，本不该交给会数错 token 的 LLM 来"声称"。
  2. **原 `check_numeric_facts`（BUG-026 引入）只覆盖一种写法**：`N 个字：X`，且 `N` 只匹配阿拉伯数字（`(\d+)`），对"这八个字"等中文数字完全失效；对引号引文（`「X」这 N 个字`、`N 个字："X"`）也完全漏检。
  3. **质检 skill 此前没有"字数核对"前置步骤**——内容质检直接走 LLM 三视角并行，LLM 同样会数错 token，等于让"嫌疑人审嫌疑人"。
- **修复**（从第一性原理：字数用 Python `len()` 数，不交给 LLM）：
  1. **新增独立脚本 `scripts/check_char_count.py`**：
     - 三种模式正则：A=`N 个字：X`、B=`「X」这 N 个字`、C=`N 个字：「X」`
     - `strip_punct` 移除中英文标点、空白、Markdown 符号，**字数不含标点**
     - `cn_to_int` 支持中文数字（"八/十二/二十三/一百二十"等）
     - `(?<!第)` 负向后看排除"第 N 个字"序号
     - `actual == 0` 跳过空引文或纯 Markdown 符号引文
     - CLI：`--file` / `--dir` / `--glob` / `--strict` / `--verbose`
  2. **增强 `src/utils/quality.py` 的 `check_numeric_facts`**：
     - 新增 `_strip_punct_for_char_count`、`_cn_to_int`、`_NUM_RE`（与脚本单一信源）
     - 三种模式自动检测（去重 + cn_to_int 解析 + actual==0 跳过）
     - 保留 BUG-026 的 "5个字：你好世" 契约（模式A正则不变）
     - manual_review 路径（N 年前/N 岁/N 品官）保持不变，仍由 Agent 复核
  3. **更新 `.trae/skills/deep-reading/content-quality.md` §9.3**：扩展"N 个字"项为三种写法 + 脚本引用子列表
  4. **更新 `.trae/skills/content-review/SKILL.md`**：在「调用 Python 引擎」前新增「前置：字数核对（确定性，无需 LLM）」子节
  5. **修复全专栏 90 处字数错误**：用脚本输出清单逐个 Edit 修正字数声称（优先改声称以匹配实际，避免改动原文引文）
- **涉及文件**：
  - `scripts/check_char_count.py`（新增）
  - `src/utils/quality.py`（增强 check_numeric_facts）
  - `tests/test_char_count.py`（新增，23 用例）
  - `tests/run_regression_suite.sh`（新增第 13 步冒烟）
  - `.trae/skills/deep-reading/content-quality.md`（§9.3 扩展）
  - `.trae/skills/content-review/SKILL.md`（新增字数核对前置步骤）
  - `output/**/*.md`（90 处字数声称修正）
- **回归测试**：
  - `tests/test_char_count.py`：覆盖 strip_punct / cn_to_int / 三种模式 / frontmatter 跳过 / 序号排除 / 空引文跳过 / check_file / check_dir / quality.py 联动（共 23 用例）
  - `tests/run_regression_suite.sh` 第 13 步：脚本 `--help` 退出码 0 + 三种模式 self-test 检出已知错误
  - `python scripts/check_char_count.py --dir output/ --strict` 全专栏扫描退出码 0
- **教训**：
  1. **第一性原理：确定性事实不交给概率模型**。字数、行数、文件数这类可精确计算的事实，应当用 Python `len()` 等确定性工具核对，不该让 LLM 用 token 统计来"声称"——这是低价错误的高发区。
  2. **质检前置分层**：能确定的事实先跑脚本核对（秒级、零成本、零误判），再让 LLM 跑主观维度（史实/可读性/引用克制）。本次在 content-review skill 增加"字数核对前置"子节，把字数从 LLM 质检中剥离。
  3. **正则覆盖要全模式**：BUG-026 只覆盖模式 A 一种写法，本次扩展到 A/B/C 三种。中文数字（"八个字"）和阿拉伯数字（"8 个字"）必须同时支持，否则会漏检一半。
  4. **单一信源**：`scripts/check_char_count.py` 与 `src/utils/quality.py` 共用同一套 `strip_punct`/`cn_to_int` 逻辑（手抄一份并注释"保持一致"），避免脚本说没错、quality.py 报有错的尴尬。后续可考虑抽公共模块。
  5. **BUG-026 的延续**：BUG-026 引入 `check_numeric_facts` 是对的，但只覆盖一种写法且只支持阿拉伯数字，是"半成品"。本次 BUG-038 是它的完整化，不是新造轮子。

## check_internal_repetition 误报 knowledge/modern 桶的「」中英对照与章节引用

- **编号**：BUG-039
- **首次出现**：2026-06-30
- **类型**：数据 / 兼容性
- **现象**：AI 时代全栈知识边界专栏首轮流式质检中，`开篇_怎么用这份专栏.md` 80 分 passed=False，含 7 条「单章内重复古文/金句」误报。被误报的内容包括「GIL(Global Interpreter Lock,全局解释器锁)」「Python必须掌握的内核」「概念 → 原理 → 实践 → 速查/自测」等——这些在 knowledge 桶中是中英对照术语与章节标题引用的常态用法，不是古文金句重复。
- **根因**：`check_internal_repetition` 在 `run_content_quality_checks` 中对所有 archetype 都跑，但该函数设计初衷是检测 narrative 桶的「古文/金句重复」（如「天下兴亡,匹夫有责」出现 2 次）。knowledge 桶用「」做中英对照（「GIL(...)」）和章节标题引用（「Python必须掌握的内核」）是常态，modern 桶用「」引书名（「代码整洁之道」）也是常态，不应被报为"古文/金句重复"。这是 BUG-027 archetype 分桶修复的遗漏：路由了年份/名家/时间线/中英混杂，但漏了 check_internal_repetition。
- **修复**：`src/utils/content_quality.py` 的 `run_content_quality_checks` 中，把 `check_internal_repetition` 调用限定为 `if archetype == "narrative":` 才跑。knowledge/modern 桶跳过。
- **涉及文件**：`src/utils/content_quality.py`（`run_content_quality_checks` 内 `check_internal_repetition` 路由）
- **回归测试**：`tests/test_content_quality_archetype.py` 新增 `TestCheckInternalRepetitionArchetypeRouting` 类，4 个测试用例：
  1. narrative 桶：同一「...」金句出现 2 次应被报重复
  2. knowledge 桶：同一「中英对照术语」出现 2 次不应报重复
  3. knowledge 桶：同一「章节标题」出现 2 次不应报重复
  4. modern 桶：同一「书名」出现 2 次不应报重复
- **教训**：
  1. **archetype 分桶修复要遍历所有 archetype 专属检查函数**。BUG-027 路由了 4 类检查（年份/名家/时间线/中英混杂），但 check_internal_repetition 也是古籍专属（用「」做古文引用是 narrative 桶特征），漏了它。**教训：archetype 路由审查要列全所有"仅 narrative 合理"的检查项，不能只看 design.md §8 路由表是否显式列出。**
  2. **「」书名号在三个桶里语义不同**：narrative 桶引古文金句、knowledge 桶做中英对照/章节引用、modern 桶引书名。检测规则不能跨桶一刀切。
  3. 与 BUG-027 教训延续：每开新 knowledge 桶专栏不仅要扩展 `KNOWLEDGE_TERMS_WHITELIST`，还要复查所有 archetype 专属检查函数的路由是否齐全。

## fiction 桶首次落地暴露的"内容质量三风险"（史实人物名、OPC 桥重复、章节格式漂移）

- **编号**：BUG-040
- **首次出现**：2026-07-01
- **类型**：数据 / 内容质量
- **环境**：《洛克菲勒：账本A里的帝国》32 章专栏，fiction 桶（项目第 4 个 archetype 桶）首次落地
- **现象**：三专家并行评审（史实核验/小说技法/OPC 财商教育）共报 0 P0、11 项 P1，去重后归为三类反复痛点：
  1. **史实人物名错误**（3 处）：卷四"詹姆斯·汉迪（James Handy）"应为"T. P. 汉迪（Truman P. Handy）"；卷七芝加哥大学章递提案人"布朗"应为"盖茨（Frederick Taylor Gates）"；附录第25条"弗兰克·塔贝尔 油桶制造商"应为"油井主"、"二十三篇报道"应为"十九篇报道"（与卷六正文统一）。
  2. **OPC 翻译桥重复/抽象**（4 处）：卷六 1911 拆分令章与 1916 拆分翻倍章 OPC 桥近乎逐字重复（都以"分项之和大于整体"开头，"一个产品值一百，打包卖八十"完全一致）；卷三弗拉格勒章、卷七钩虫病章 OPC 桥偏抽象缺具体动作；附录第5条与第13条证据都用"39 滴焊锡"重复。
  3. **章节格式漂移**（4 个文件×6 处）：卷七3章 + 附录的二级标题用 `## 入戏`（无序号），与卷一至卷六 `## 一、入戏`（带中文序号）不统一；OPC 桥用 `> **OPC 翻译桥**：`（引用块前缀），与卷一至卷六 `**OPC 翻译桥**：`（加粗段落）不统一。
- **根因**（三类问题三个根因）：
  1. **史实人物名错误**：fiction 桶允许"七实三虚"（参考《三国演义》），但"实"的部分（人物姓名/身份/篇数/年份）必须核对一手史料。本次子 Agent 生成时把"Frank Tarbell 是油桶制造商"（实为油井主）、"塔贝尔连载 23 篇"（实为 19 篇）、"递提案人布朗"（实为盖茨）等关键史实写错，靠专家团评审才发现。check_book_structure.py 只校验结构，不校验史实。
  2. **OPC 翻译桥重复**：OPC 翻译桥是 fiction 桶核心创新（把帝国级启示下沉到一人公司量级），但同卷相邻章节 OPC 桥主题相近时，子 Agent 容易逐字复用而非差异化。rules-fiction.md §一规定了五段结构，但未规定"相邻章节 OPC 桥必须差异化"。
  3. **章节格式漂移**：32 章由多个子 Agent 分卷并行生成，卷一至卷六遵循"`## 一、入戏` + 加粗段落 OPC 桥"格式，卷七3章+附录遵循"`## 入戏` + 引用块 OPC 桥"格式——多 Agent 并行时格式约定未在 prompt 里强制约束，导致漂移。
- **修复**（11 项 P1 全部修复）：
  1. **史实**：卷四汉迪改名；卷七盖茨改名 + "布朗的提案"→"盖茨的提案"；附录第25条"油桶制造商"→"油井主"、"二十三篇"→"十九篇"。
  2. **OPC 桥**：卷六 1911 拆分令章改写为聚焦"被强制拆分时的应对心态与法律策略"；1916 拆分翻倍章改写为聚焦"拆分后市场重新定价的财务机制"；卷三弗拉格勒章补充三步具体动作（列清单打分/列候选互补人/小项目试合作）；卷七钩虫病章补充三步具体动作（列普遍痛点/做 MVP/做可复制模板）；附录第5条换证据（39 滴焊锡→一桶煤油成本结构六子项拆解）。
  3. **格式**：卷七3章+附录的 `## 入戏/破题/推进/高潮/余味` 全部加中文序号；`> **OPC 翻译桥**：` 引用块前缀全部去掉，改为 `**OPC 翻译桥**：` 加粗段落 + 空行 + 正文。
- **涉及文件**：`output/洛克菲勒/` 下 7 个文件（卷四九十大屠杀章、卷六1911拆分令章、卷六1916拆分翻倍章、卷七芝加哥大学章、卷七钩虫病章、卷七财富接力章、附录_33条硬核财商启示录）
- **回归测试**：
  - `python scripts/check_book_structure.py --output output --strict` 通过（0 P0/P1/P2，无回潮）
  - 史实人物名错误、OPC 桥差异化这两类**无自动化断言可落地**——前者需史实知识库、后者需语义判断，均超出 check_book_structure.py 的能力边界；继续靠"三专家并行评审"在 fiction 桶每开新书/每写新章前必跑来防回潮。
  - 章节格式漂移**可加自动断言**（如检查 `^## (入戏|破题|推进|高潮|余味)$` 无序号二级标题、`^> \*\*OPC 翻译桥\*\*` 引用块前缀），但本次未补充——fiction 桶目前只此一本专栏，加规则的边际收益低于改动 check_book_structure.py 的成本；若 fiction 桶开第二本再评估。
- **教训/沉淀**：
  1. **fiction 桶"七实三虚"的边界要前置约束**：写作 prompt 必须明确"实"的部分（人物姓名/身份/年份/篇数/数字事实）一律核对一手史料，"虚"的部分（对话/心理/细节场景）才允许艺术加工。本次 3 处史实错误都是"实"的部分写错。
  2. **多 Agent 并行写作必须强制格式约定**：在子 Agent prompt 里写明"二级标题用 `## 一、入戏` 带中文序号、OPC 桥用 `**OPC 翻译桥**：` 加粗段落"，否则多 Agent 各自遵循本地 convention 必然漂移。这是 BUG-019（"模块N"前缀）的同类问题——格式约定不能靠默契，必须落到 prompt + 校验脚本。
  3. **相邻章节 OPC 桥必须差异化**：rules-fiction.md 应补充"相邻章节 OPC 桥主题相近时，必须从不同切口切入（如心态/财务机制/法律策略/动作清单），禁止逐字复用"。
  4. **专家团评审是 fiction 桶内容质量的最后防线**：史实核验和 OPC 桥差异化这两类问题无法靠 Python 断言自动检测，必须靠"史实核验+小说技法+OPC 财商教育"三视角并行评审来兜底。这与 narrative 桶的"质检脚本前置+LLM 主观维度后置"分层不同——fiction 桶的"实"部分必须靠史实专家核验，不能交给 LLM 自检。

## loop_log 跨月分片日期倒序校验设计缺陷（shard 升序导致必然失败）

- **编号**：BUG-041
- **首次出现**：2026-07-01
- **类型**：构建
- **环境**：`docs/loop_log/` 首次出现两个月份分片（2026-06.md + 2026-07.md）
- **现象**：在 `docs/loop_log/2026-07.md` 新建当月分片并写入 07-01 沉淀后，运行 `python scripts/check_loop_log.py` 报 P1 失败：`日期非倒序：2026-07.md '...' (2026-07-01) 晚于前一条 2026-06.md '...' (2026-06-23)`。即只要存在 ≥2 个月份分片，该核心校验必然失败，阻断 dev-workflow 第五步沉淀闭环。
- **根因**：`scripts/check_loop_log.py` 的 `check_date_descending` 按 `(shard, h2_start)` 升序排序后逐对比较日期是否倒序。分片文件名升序意味着 `2026-06.md`（六月，日期较旧）排在 `2026-07.md`（七月，日期较新）之前；而六月分片内最后一条沉淀是六月最旧的一天（如 06-23），七月分片第一条是 07-01——从 06-23 到 07-01 日期递增，被判为"非倒序"。这违反了 loop_log 的阅读语义：日志应"最新在前、最旧在后"，即最新月份分片应先被读到。原测试 `test_date_not_descending_across_shards_fails` 还把这一正常跨月场景固化为"应失败"，放大了设计缺陷。
- **修复**：
  1. `check_date_descending` 改为按分片文件名**降序**（最新月份在前）+ 同分片内 `h2_start` 升序排列，利用 Python 稳定排序实现（先按 h2_start 升序，再按 shard 降序）。阅读顺序变为 2026-07.md（07-01）→ 2026-06.md（06-30…06-23），日期严格倒序。
  2. 更新 `tests/test_check_loop_log.py`：原 `test_date_not_descending_across_shards_fails`（把正常跨月判为失败）改为 `test_date_descending_across_shards_passes`（期望通过）；新增 `test_date_not_descending_across_shards_fails` 覆盖真正的跨分片乱序（旧月份分片混入比新月份分片更新的日期）。
- **涉及文件**：`scripts/check_loop_log.py`、`tests/test_check_loop_log.py`
- **回归测试**：
  - `python scripts/check_loop_log.py --strict` 通过（51 条沉淀，2 个分片，0 P1/P3）。
  - `python -m pytest tests/test_check_loop_log.py -q` 10 passed。
  - `python -m pytest -q` 531 passed, 20 skipped（新增 1 个跨分片正向用例）。
- **教训/沉淀**：
  1. **"日期倒序"校验的阅读顺序必须与日志语义一致**：日志是"最新在前"，分片按文件名升序排列恰好与该语义相反。设计校验脚本时不能想当然地用 `sorted(shard)` 升序当作"阅读顺序"，必须先明确阅读语义再定排序键。
  2. **测试用例不能把"设计缺陷"固化为"期望行为"**：原 `test_date_not_descending_across_shards_fails` 的 docstring 写"新月份分片排在旧月份之后应失败"，但这正是正常的文件系统行为，把缺陷固化成测试会让缺陷更难被发现。写测试时要分清"正常场景"与"乱序场景"。
  3. 此缺陷自 loop_log 分片化（2026-06 月底）起就潜伏，只是直到 2026-07-01 首次跨月才暴露——跨月分片类校验应在引入分片结构的同一 Loop 就构造双分片用例验证。

## 自动阅读速度调节无效（亚像素 scrollBy 被浏览器取整为 0）

- **编号**：BUG-042
- **首次出现**：2026-07-01
- **类型**：兼容性
- **环境**：移动端浏览器（小米/夸克等）、桌面 Chrome 不可复现
- **现象**：自动阅读功能在设置面板调整速度（24~100 行/分）后，实际滚动速度完全一致，无论设快设慢都是同一档速度，速度调节形同虚设。
- **复现步骤**：
  1. 移动端浏览器打开阅读页，进入任一章节
  2. 点击设置按钮，开启自动阅读
  3. 将速度滑条分别设为 24（最慢）和 100（最快）
  4. 观察两次滚动速度无差异
- **根因**：`autoScrollLoop` 中按「行/分 → 像素/毫秒」算出每帧位移 `dy`，在常用区间内 `dy < 1px`（例：50 行/分 × 28px 行高 ÷ 60000ms × 16ms ≈ 0.37px）。原代码直接 `reader.scrollBy(0, dy)`，而部分移动端浏览器对亚像素 `scrollBy(0, 0.xx)` 会取整为 0，导致每帧实际不滚动；浏览器最终依赖自身节流偶发滚动，速度差异被抹平。
- **修复**：在 `autoScrollLoop` 中引入整数累积器 `autoScrollPxAccumulator`：每帧将亚像素 `dy` 累加进去，仅当累积值 ≥ 1px 时才 `scrollBy(0, Math.floor(accumulated))` 并扣除已滚动整像素，余数继续累积。这样不同速度对应的累积速率不同，到达 1px 阈值的频率不同，滚动速度差异得以保留。同时在 `startAutoScroll` / `pauseAutoScroll` 中重置累积器，避免暂停恢复后出现跳变。
- **涉及文件**：`src/web/static-site/js/app.js`
- **回归测试**：
  - `tests/test_reader_features.js` 测试5：断言更新为「推进 30 帧后 scrollBy 调用 ≥4 次，且每次 dy 为 ≥1 的整数」
  - `tests/test_reader_features.js` 测试28（新增）：分别以 24 行/分和 100 行/分跑 60 帧，断言快速滚动距离 > 慢速滚动距离，且快速 ≥ 慢速的 2 倍
- **教训**：移动端浏览器对亚像素滚动 API（`scrollBy`/`scrollTop` 赋值）的取整行为比桌面端激进。任何依赖「逐帧小幅滚动」的动画（自动阅读、视差、惯性滚动）都应使用整数累积器模式，避免亚像素值被静默吞掉。速度参数的回归测试不能只验证「有滚动」，必须验证「不同速度产生不同距离」。
