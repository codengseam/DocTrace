# LoopAgent 循环日志

> 历史测评框架与评分表见 [docs/archive/loop_log_fossils.md](archive/loop_log_fossils.md)（不再更新）。
> 本文件仅记录开发沉淀。每次开发前请先 Grep 检索本文件（见 `.trae/rules/dev-workflow.md` 第三步）。

## 索引区

### 最近 10 条沉淀（按日期倒序）
- [2026-06-28 BUG-032 专栏正文方括号引用编号打断阅读体验](#L1279)
- [2026-06-28 高考志愿填报前置认知 Phase 2 升级 - 精准100/质量98/落地99三终审闭环](#L1225)
- [2026-06-27 高考志愿填报前置认知科普专栏 + 多 agent 打分闭环](#L1178)
- [2026-06-27 首页圣贤堂入口优化 + 内置 YAML 解析器嵌套结构支持](#L1135)
- [2026-06-27 阶段4 边链裁剪完成 - 解除 modern/knowledge soul injection 架构债](#L44)
- [2026-06-27 阶段5 Skill 入口分流与沉淀落地 - 会话C](#L77)
- [2026-06-26 superpowers 原生技能化 + 明纪阶段校验 + 章回体灵魂标题自动化](#L118)
- [2026-06-26 灵魂注入专项 - 明纪·海瑞上疏 AB 盲测](#L183)
- [2026-06-25 现代职场专栏质检规则适配与内容修复](#L233)
- [2026-06-24 章节标题禁止「模块N」前缀](#L286)
- [2026-06-24 合并前必须清零所有校验问题](#L329)
- [2026-06-24 Service Worker 缓存导致手机端"幽灵旧版"](#L382)
- [2026-06-24 返回书架蒙层残留回归修复](#L421)

### 主题锚点
- `#reader_interaction`：阅读器/沉浸/翻页/吸底栏/SW 缓存
- `#content_quality`：质检规则/灵魂注入/标题评分
- `#book_structure`：排序/校验/命名/去重/双源同步
- `#deployment`：GitHub Pages/魔搭/.nojekyll/SW
- `#soul_injection`：灵魂注入/章回体/总编Agent
- `#git_hygiene`：推送/合并/冲突/分支治理/commit 覆盖

### 教训计数表（≥3 次且未入 checklist 即触发方案 C，见文件末"方案 C 手册"）

| #lesson slug | 出现次数 | 已入 checklist |
|---|---|---|
| `book_structure`（双源同步 3 次 / 排序校验已固化 / 命名去重反复） | 11 | no（双源同步未入） |
| `reader_interaction`（沉浸模式反复修复 4 次 / 防横屏已入 / Hero 移动端瘦身） | 11 | no（双源同步未入） |
| `content_quality`（质检规则分化 / 灵魂注入 / 标题评分 / 写作规则分工） | 6 | no |
| `git_hygiene`（推送前 fetch / 冲突标记 / commit 覆盖） | 4 | no（fetch/commit 未入） |
| `deployment`（SW CACHE_NAME 升级 / .nojekyll / 无 PyYAML 解析器兜底） | 4 | no（SW 版本未入） |
| `soul_injection`（灵魂注入 / 章回体标题 / 边链裁剪） | 3 | no |
| `ai_course`（专栏批量生成 / subagent 结果丢失） | 2 | no |

> 备注：`book_structure` 与 `reader_interaction` 出现次数高，部分教训点已固化（排序校验→`check_book_structure.py`、防横屏→`run_regression_suite.sh`），但"site/ 与 src/web/static/ 双源同步"未入 checklist，仍标 no。

---

## 阶段4 边链裁剪完成（2026-06-27，解除 modern/knowledge soul injection 架构债）

### 触发问题
阶段4 A+B 落地 modern/knowledge 桶 prompt + specialist 接入 archetype 后，遗留架构债：`build_workflow` 边链硬编码 5 个 specialist 节点，若开启 modern/knowledge 的 soul injection（走 if 分支 orchestrator→tone_setter→5 Specialist），会调用 modern 不需要的 biographer/philosopher（产空段），editor 汇总时把空段收入 sections 导致 quality 失败。因此 `_soul_injection_for_archetype` 暂时只对 narrative 返回 True，modern/knowledge 的 tone_setter/chief_editor prompt 虽已建却未接入边链。

### 根因与修复
1. **动态 specialist 构建**：`build_workflow` 从 `editor.SECTION_TEMPLATES[archetype]` 的 values 去重得到需要的 agent 名集合，去掉 editor（汇总节点单独加），得到 specialist 名单。narrative=5, modern=3, knowledge=3。用 `specialist_fns` 字典按需 `add_node` + `add_edge`，取代硬编码。
2. **开启 modern/knowledge soul injection**：`_soul_injection_for_archetype` 去掉 `archetype == "narrative"` 限制，改为 `archetype in _VALID_ARCHETYPES + 三开关`。三桶 quality 通过均走 chief_editor→save。
3. **边链裁剪验证**：modern 边链 orchestrator→tone_setter→{historian,critic,context_analyst}→editor→quality→chief_editor→save→END，不注册 biographer/philosopher；knowledge 同理不注册 critic/philosopher；narrative 零回归（5 specialist + 完整边链）。

### 架构教训（已沉淀）
- **TDD Green 阶段会揭示 Red 阶段遗漏的过时契约**：Red 阶段写了 8 个新失败测试（modern/knowledge 注册 soul 节点 + specialist 裁剪），但漏改了 2 个阶段3 旧测试（`test_modern_pass_goes_to_save` 断言 modern 不走 chief_editor）。Green 修改 `_soul_injection_for_archetype` 后这两个旧测试必然失败——因为 modern 启用 soul injection 后 quality 通过应走 chief_editor。**教训：改一个函数的返回值契约时，要全局搜索所有依赖该契约的测试，不只看新增的 Red 测试。TDD 的 Red 不只是写新失败，还包括把旧契约的过时断言一并改成失败。**
- **占位资产转正式接入要清偿拓扑债**：阶段4 A+B 建 modern/knowledge 的 tone_setter/chief_editor prompt 作为"前置资产"，但 workflow 边链没裁剪就无法接入。本次裁剪后才真正闭环。**教训：新增维度（archetype）时，节点拓扑（workflow 边链）必须按维度裁剪，否则占位节点产空段污染下游。前置资产只有在拓扑就绪后才是真资产，否则是死代码。**
- **git log 的 Revert 链是历史债信号**：本次三件套验证发现 7 个测试失败，基线对比确认零回归后，查 git log 发现 `46ab54d add --strict` 被 `052d772 Revert`、`c834d3f 清理模块N前缀` 被 revert、`74ed951 修复章节顺序` 被 revert——BUG-017/019 的修复全部丢失。`tests/bug_regression_list.md` 仍记录"已修复"，形成"文档说修了、代码说没修"的双真相漂移。**教训：回归测试失败时，若 bug_regression_list 标注"已修复"，要查 git log 确认修复是否被 revert；bug_regression_list 应记录修复 commit hash，便于快速定位回退。**

### 测试覆盖
- `tests/test_workflow_archetype.py`：67 项全绿（契约7 modern/knowledge 注册 soul 节点 + specialist 裁剪 + 完整边链；契约8 过时 router 断言修正；契约9 `_soul_injection_for_archetype` 三桶均 True）。
- 全量 pytest 零新增失败（master 基线 7 failed = 改动后 7 failed，7 个为历史回退问题）。

### 已更新规则/checklist
- `docs/archetype-design/design.md` 阶段4 追加"边链裁剪完成"验收块，标记架构债清偿。

### 待办（历史回退，单独 PR）
1. 恢复 `check_book_structure.py` 的 `--strict` 参数（BUG-017 修复被 revert）。
2. 重编号养生课（睡眠/饮食养生课/饮食养生课第二版）章内 sort 为 1-based 连续。
3. 清理 `output/` 下残留的「模块N」前缀（BUG-019 修复被 revert）。
4. 修复前先查清当初 revert 原因（冲突解决失误 or 有意回退），避免再次冲突。
5. `tests/bug_regression_list.md` 的 BUG-017/19 补充修复 commit hash 字段，便于回退检测。

**教训标签**：`#lesson: soul_injection`

---

## 阶段5 Skill 入口分流与沉淀落地（2026-06-27，会话C）

### 触发问题
阶段4 基础设施完成后，archetype 信号在 Python 层已贯通（CLI > _meta.yaml > category 默认映射 > narrative），但 Skill 入口（`.trae/skills/deep-reading/SKILL.md`）仍是 narrative 单桶流程：不识别 archetype、命令模板无 `--archetype` 参数、质检命令无 `--archetype`。同时 `rules.md` 顶部无适用范围声明，modern/knowledge 桶无独立写作规则文件，Agent 调用 modern/knowledge 桶时只能"野生绕开 rules.md"（loop_log.md:59 已记录理财课/AI课早有此现象）。这是阶段1-4 数据流打通后"最后一公里"——让 Skill 入口也能按 archetype 分流。

### 根因与修复
1. **SKILL.md 入口改造**：在「第二步信息确认」与「原第三步加载规则」之间插入新的「第三步：识别 archetype」，信源优先级与 design.md §5.6 对齐（`_meta.yaml.archetype` > category 默认映射 > 问用户 > narrative 兜底）。关键设计：「问用户」仅在 category 未知或 category=经/技且无 `_meta.yaml.archetype` 时触发——避免古籍专栏（category=史/经 直接命中 narrative）被打断，保证 narrative 零回归。第四步命令模板加 `--archetype {archetype}`，narrative 桶可不传（main.py 已兜底），modern/knowledge 必传。
2. **rules.md 顶部声明（正文不动）**：narrative 是 dev-workflow.md §四禁区，只允许在 §一之前加 blockquote 声明适用范围 + 引用 rules-modern.md/rules-knowledge.md/design.md §5.6/content-quality.md §8。用 `git diff` 验证正文（§一及之后）与 origin/master 完全一致。
3. **rules-modern.md / rules-knowledge.md 分工（R-R1）**：确立"怎么写 vs 怎么查"分工边界——rules-*.md 管「怎么写」（写作风格/结构模板/引用格式/叙事方法），content-quality.md §8.2/§8.3 管「怎么查」（白名单清单/阈值/扣分规则）。两者互相引用不重复，避免双源维护。具体：
   - rules-modern.md：五段结构（入戏/破题/方法论/避坑/践行）+ 现代场景化叙事 + 名家点评放宽（鬼谷子/德鲁克/卡尼曼等）+ 现代术语边界（指向 MODERN_ENGLISH_WHITELIST 常量引用，不复制词表）
   - rules-knowledge.md：四段结构（概念/原理/实践/速查自测）+ 术语首次出现给中英对照 + KNOWLEDGE_TERMS_WHITELIST 引用 + 技术原理/复杂度/命令须准确可核验
4. **BUG-030 修复（PyYAML 未装时 stub 路径崩溃）**：执行中发现 `_get_stub_sections` 在 PyYAML 未装时崩——内置简单 YAML 解析器把 `quality_check` 嵌套结构解析成 list，`qc.get` 触发 AttributeError。最小防御性修复：加 isinstance 兜底，list 情况返回 narrative 默认六段。`workflow.get_required_sections` 有相同 bug，在 A+B 范围内不修（登记 BUG-030 待办）。

### 架构教训（已沉淀）
- **"怎么写"与"怎么查"必须分工**：rules-*.md 若整段复制 content-quality.md §8.2/§8.3 的白名单清单/阈值，会产生双源——改一处忘另一处。确立分工：rules-*.md 管「怎么写」（给 Agent 看的写作指导），§8.2/§8.3 管「怎么查」（给质检引擎看的扣分规则）。两者互相引用不重复。**教训：多桶规则文件的边界要按"读者"切分——写作规则给 Agent 看，质检规则给引擎看，不混在一起。**
- **narrative 零回归护栏要落到行号**：rules.md 顶部加声明后，§一标题行号从 5 推到 11，但正文内容零变化。光看 diff 不够，必须用 `git show origin/master:... | tail -n +5` 与当前 `tail -n +11` 对比验证正文完全一致。**教训：禁区文件的"零改动"承诺要有自动化断言（test_rules_md_body_unchanged_vs_master），不能靠人眼。**
- **环境降级路径的产物类型不一致是隐患**：PyYAML 未装时内置解析器返回 list，正常路径返回 dict，下游消费者假设 dict 就崩。**教训：所有 fallback/降级路径的产物类型必须与正常路径一致，否则下游消费者必须 isinstance 兜底；环境降级是"隐性双源"，比代码双源更隐蔽。**
- **Skill 不能调度 sub-agents 要如实说明**：本次需三视角评审，但 `scripts/review_plan.py` 和 `.env` 均缺失，无法跑 LangGraph 真并行。按 dev-workflow.md §零能力边界，走路径 A（单 agent 串行切换三视角），并在报告开头如实说明。**教训：能力边界做不到时如实说明并给替代方案，不假装能调度 sub-agents。**

### 测试覆盖
- `tests/test_skill_archetype_routing.py`：14 项契约测试（SKILL.md 命令模板含 --archetype / 信源优先级关键词 / 三选一话术 / 三套 rules-*.md 顶部互相引用 / rules.md 正文零改动 git diff 断言 / 16 专栏 archetype 字段现状 / main.py argparse 支持 / narrative stub 零回归运行时 / rules-*.md 分工不复制词表 / BUG-030 PyYAML 未装不崩）。
- 三件套：`check_book_structure.py --strict` 0 问题；pytest 306 passed 15 skipped（新增 14 项，原 292 → 306）；`run_regression_suite.sh` 18/18。

### 已更新规则/checklist
- `.trae/skills/deep-reading/SKILL.md`：新增第三步 archetype 识别 + 命令模板加 `--archetype`。
- `.trae/skills/deep-reading/rules.md`：顶部加适用范围声明（正文不动）。
- `.trae/skills/deep-reading/rules-modern.md`、`rules-knowledge.md`：新建（怎么写 vs 怎么查 分工）。
- `src/main.py`：`_get_stub_sections` 加 isinstance 兜底（BUG-030）。
- `tests/bug_regression_list.md`：新增 BUG-030。
- `docs/archetype-design/design.md`：阶段5 标记完成（待 PR 合并后补验收块）。

### 待办（下一 Loop）
1. **会话A+B 已合并 + 边链裁剪已完成（PR #18）**：modern/knowledge soul injection 已开启，三桶 quality 通过均走 chief_editor→save。
2. **历史回退修复**：BUG-017（`--strict` 被 revert）/ BUG-019（模块N前缀被 revert）/ `workflow.get_required_sections` 同款 PyYAML bug（BUG-030 待办）需修，详见上方"阶段4 边链裁剪完成"待办块。
3. **fiction 桶**：rules-fiction.md 待用户开始写小说时设计（design.md §5.2、§10.4 预留）。
4. **真并行评审复核**：配置 `.env` 的 `LLM_API_KEY` 后跑 `scripts/review_plan.py` 对阶段5 做真并行复核（当前为路径 A 单 agent 串行三视角）。

**教训标签**：`#lesson: content_quality`

---

## 2026-06-26 superpowers 原生技能化 + 明纪阶段校验 + 章回体灵魂标题自动化

### 背景
接续上一条 Loop 的待办第 4 条，把 superpowers 5 个纯方法论技能（verification/systematic-debugging/TDD/receiving-review/writing-plans）原生化；同时解决用户提出的"九个字/那支流矢"等无灵魂标题问题。

### 完成事项

**工程沉淀（superpowers 原生技能化）**
- 新增 `.trae/skills/verification-before-completion/SKILL.md`：5 核心纪律（每个断言要证据 / 验证必须执行 / 三层覆盖 / 失败即停 / 报告里带证据）
- 新增 `.trae/skills/systematic-debugging/SKILL.md`：5 纪律（先复现 / 二分定位 / 可证伪假设 / 最小修复 / 回归测试）+ 6 步流程
- 新增 `.trae/skills/tdd/SKILL.md`：Red-Green-Refactor 循环 + 5 纪律 + 契约表
- 新增 `.trae/skills/receiving-code-review/SKILL.md`：5 纪律（每条都回应 / 反馈是事实不是攻击 / 修复前先验证 / 修复后验证+沉淀 / 复杂反馈批处理）
- 新增 `.trae/skills/writing-plans/SKILL.md`：5 纪律（核心目标 / 五要素 / 等确认 / 回滚思维 / 并行化）

**明纪阶段模式强校验**
- `src/utils/sorting.py`：`BOOK_CATEGORY_ORDER["明纪"]` 从 `{"明纪": 1}` 扩展为 8 模块映射；`STAGE_MODE_BOOKS` 新增 `"明纪"`
- `tests/test_sorting.py`：更新 `test_chapter_sort_key_tang_song_ming` 适配新模块名格式
- `tests/test_book_structure.py`：新增 2 个回归测试（明纪一致 sort 通过 / 不一致报 P1）

**章回体灵魂标题方法论 + 自动化检测**
- 新增 `.trae/skills/chapter-title-soul/SKILL.md`：三维度评分法（信息密度 0-2 / 灵魂指向 0-2 / 呼应节奏 0-1，满分 5，<3 必重写）+ 5 种好模式 + 4 种坏模式 + 重写决策树 + 7 步重写流程
- `src/utils/quality.py` 新增 `check_chapter_title_soul`：自动检测 4 种坏模式（事件标签/数字量词/孤立物件/装饰诗化）+ 8 种好模式命中加分
- `tests/test_quality.py`：新增 9 个 TDD 测试覆盖好/坏/边界
- `.trae/skills/deep-reading/rules.md` §6.4：从"不是事件标签"升级为"不是事件标签，也不是诗化装饰"，补 5 种好模式
- `.trae/skills/deep-reading/content-quality.md` §9.4：从二元判定升级为三维度评分表

**明纪 41 篇标题批量重写**
- 扫描 261 个标题，发现 17 个 <3 分（修复误判后从 46 降到 17）
- 按 5 种好模式重写：4 颠覆句式 + 3 反差对比 + 6 悖论词 + 3 必然性词 + 1 收束词
- 重写后 261 个标题全部 ≥3 分（其中 34 个命中好模式得 5 分）

### 关键教训
1. **自动化检测先看误判率，再决定扣分粒度**。`check_chapter_title_soul` 初版对"XX的YY"自动扣分，56% 误判率（举人的命/干净的武器/纸糊的盛世都是好标题）。修复后只对 4 字景物短语自动扣分，"XX的YY"留给人工。检测函数宁缺毋滥，误判比漏判更打击内容作者。
2. **TDD 在内容质检函数上同样有效**。先写 9 个失败测试（好标题应高分/坏标题应低分/边界）→ 再写实现 → 修误判时加新测试锁定行为。Red-Green-Refactor 不限于业务代码。
3. **标题句式多样性是隐性约束**。17 个重写标题初版 65% 用"不是X是Y"句式，虽然单篇不违反"每篇≤3处"的硬约束，但读者读完整本会腻。最终平衡为：颠覆 4 / 反差对比 3 / 悖论词 6 / 必然性词 3 / 收束词 1。
4. **superpowers 的价值在纪律不在工具**。5 个技能的核心都是"反直觉的纪律"（先复现再修 / 先写测试再写代码 / 每条反馈都回应），Trae 原生化时只保留纪律部分，不照搬 prompt 模板。
5. **阶段模式（STAGE_MODE_BOOKS）从"资治通鉴"扩展到"明纪"**。明纪 8 个模块名（元末群雄与明朝建立 → 明亡与清军入关）作为朝代阶段，chapter_sort 一致即可通过校验。这套路可推广到所有按朝代/阶段分模块的书。

### 规则/checklist/Skill 更新
- `.trae/skills/{verification-before-completion,systematic-debugging,tdd,receiving-code-review,writing-plans}/SKILL.md`（5 个新增）
- `.trae/skills/chapter-title-soul/SKILL.md`（新增）
- `.trae/skills/deep-reading/rules.md` §6.4（增强）
- `.trae/skills/deep-reading/content-quality.md` §9.4（升级三维度评分）
- `src/utils/sorting.py`（明纪阶段模式）
- `src/utils/quality.py`（check_chapter_title_soul）
- `tests/test_sorting.py` / `tests/test_book_structure.py` / `tests/test_quality.py`（回归测试）
- `output/明纪/*.md`（17 个标题重写）

### 可复用资产
- "三维度评分法（信息密度/灵魂指向/呼应节奏）"可推广到史记/资治通鉴/易经课所有专栏
- `check_chapter_title_soul` 函数可直接接入 ChiefEditor Agent 的终审环节
- "扫描→列低分→批量重写→句式多样性平衡→重扫验证"流程可复用
- superpowers 5 原生技能可作为后续所有开发对话的纪律底座

### 待办（下一 Loop）
1. 灵魂注入推广到史记/资治通鉴（各选 1 篇对标当年明月盲测）
2. 总编Agent 校准：首 5 篇只打标记不强制打回，跑 20 篇后定阈值
3. 存量 686 篇按"总编 GO/REWORK"分级，REWORK 进重做队列
4. 把 check_chapter_title_soul 接入 ChiefEditor Agent 终审（<3 分自动打回重写）
5. 标题"灵魂"扩展到史记/资治通鉴（先扫描存量低分标题清单）

**教训标签**：`#lesson: soul_injection` `#lesson: content_quality`

---

## 2026-06-26 灵魂注入专项 - 明纪·海瑞上疏 AB 盲测

### 背景
千问/coze/智谱联合给出"注入灵魂"计划，Claude Code 给出 review_system.py 审查产物。用户要求把 HaloRead 从"及格 AI 流水线产物"提升到"有当年明月灵魂的顶流水准"。方法论参考 obra/superpowers（MIT），用其 5 个纯方法论技能。

### 核心改动
1. **试点选样**：明纪·海瑞上疏（对标当年明月《明朝那些事儿》海瑞章节，可盲测）
2. **AB 盲测 5 轮迭代**：v1（1900字太瘦）→ v1.1（修数字错误）→ v2（5400字+网文技巧）→ v2.1（加章回体小标题）→ v2.2（小标题从"事件标签"升级为"灵魂点睛"）
3. **固化产物**：
   - rules.md §6：灵魂注入约束（三约束+网文六技巧+章回体灵魂标题+数字事实硬约束）
   - content-quality.md §9：灵魂维度（灵魂三问+AI套话黑名单+数字事实检查），质检从四维度升五维度
   - tone_setter.py + chief_editor.py：定调节点+总编Agent
   - workflow.py：双节点接入，SOUL_INJECTION_ENABLED 开关
   - quality.py：check_ai_cliches + check_numeric_facts

### 关键教训
1. **灵魂注入与合规是两类独立问题，不能互相替代**。灵魂再好（活人感/史观穿透），数字错了（"两个字：刚"实际一字）仍是 P0。check_numeric_facts 必须自动化拦截，不能靠人工 review。
2. **小标题是"事件标签"还是"灵魂点睛"决定文章质感**。"备棺/上疏/退田"只告诉读者"讲什么"；"不能不刚/天下人不直陛下/撬不动"告诉读者"要刺什么"。后者才是当年明月笔法。
3. **网文技巧（起承转合+埋钩子）服务于"读起来停不下来"，但不能滑向爽文化**。残酷底色仍为最高优先级——不能用网文的"爽"消解历史的"残酷"。
4. **ToneSetter 不能定一个调，要定"核心冲突+情感锚点"**。5 个 Specialist 拿同一份基调大纲容易写出同质化的"冰冷残酷"。当年明月的魅力在于逐篇换调（朱元璋冷峻/海瑞悲悯/于谦激昂）。
5. **总编Agent不是二次质检员，是"一票否决/打回重做"决策者**。合规质检（content_reviewer）管"对不对"，总编管"值不值得发"。两者职责分层，不能合并。
6. **superpowers 在 Trae 中只能当方法论参考，不能当原生技能**。Trae 不支持 /superpowers:xxx 斜杠命令。实际有效的 5 个纯方法论技能（verification/systematic-debugging/TDD/receiving-review/writing-plans）已被吸收进 HaloRead 自己的 rules/checklist，不需要把 superpowers 原文 push 到仓库（vendor/ 已 gitignore）。
7. **Trae 会自动 commit，覆盖手动 commit message**。本次 commit message 被 Trae 默认的"feat: 优化读书网站内容策略"覆盖，需用 git commit --amend 修正。后续开发若需规范 commit message，应在 add 后立即 amend。

### 规则/checklist/Skill 更新
- `.trae/skills/deep-reading/rules.md` §6（新增）
- `.trae/skills/deep-reading/content-quality.md` §9（新增）+ §一维度表（四维度→五维度）
- `src/agents/tone_setter.py`（新增）
- `src/agents/chief_editor.py`（新增）
- `src/core/workflow.py`（双节点+开关）
- `src/utils/quality.py`（双函数）
- `scripts/branch_governance.py`（BUG-025 修复）
- `tests/bug_regression_list.md`（BUG-025/026）

### 可复用资产
- "AB 盲测+对标原文+5轮迭代"流程可复用到其他专栏的灵魂注入推广（下一步：史记/资治通鉴）
- "灵魂三问"（活人测试/洞察独家性/底色敬畏感）可作为所有历史类专栏的终审标准
- "章回体灵魂标题"设计法（标题点"要刺什么"而非"讲什么"+ 首尾呼应构成命运闭环）可复用
- check_numeric_facts 的正则模式可扩展（N年/N岁/N品官 → N月/N日/N里/N石等）

### 待办（下一 Loop）
1. 灵魂注入推广到史记/资治通鉴（各选 1 篇对标当年明月盲测）
2. 总编Agent 校准：首 5 篇只打标记不强制打回，跑 20 篇后定阈值
3. 存量 686 篇按"总编 GO/REWORK"分级，REWORK 进重做队列
4. 考虑把 superpowers 5 个有效技能的核心纪律写成 HaloRead 自己的 .trae/skills/ 原生技能（避免依赖 vendor/）

**教训标签**：`#lesson: soul_injection` `#lesson: git_hygiene`

---

## 2026-06-25 现代职场专栏质检规则适配与内容修复

### 触发问题
《职场沟通课》67 章内容质检时，13-17 篇文件停留在 93-96 分（目标 ≥97）。定位发现两类问题混在一起：
1. **真实内容问题**：「大意据《XX》」引用标注冗余 12 处（正文已写明出处，句末又挂标注）、「底层操作系统」现代术语硬套 2 处。
2. **规则误报（false positive）**：`check_mixed_language` 把 KPI/HR/offer/bug/BATNA 等行业通用词报为中英文混杂；`check_ai_tone` 把「不是X而是Y」「可见」「第X层」「容易被忽略」等常见中文判断句报为 AI 味。这些规则原为古籍讲书设计，对现代职场专栏过严。

### 根因定位
1. `src/utils/content_quality.py` 的 `REDUNDANT_CITATION_PATTERN` 只匹配「在《XX》里」，漏掉「在《XX》中」句式，导致 4 处冗余漏报。
2. `check_mixed_language` / `check_ai_tone` 来自 `quality.py`，对古籍专栏敏感是对的，但直接复用到现代专栏时未做白名单/过滤，产生大量误报。
3. 内容侧：子 Agent 生成时倾向在「XX在《YY》里讲过…」句末再挂「（大意据《YY》）」以求严谨，反成冗余；「底层操作系统」比喻虽生动但属现代术语硬套。

### 修复方案
**内容修复（14 处）**：
- 12 处「大意据《XX》」冗余：删除句末标注，保留正文出处（涉及职场协作 5 篇、职场规划 5 篇、职场协作跨部门/向上汇报 2 篇）。
- 2 处「底层操作系统」：重写「人品是底层操作系统」段为「人品是底子」，比喻改为「楼上的装饰/地基」。

**规则优化（`src/utils/content_quality.py`）**：
- 扩展 `REDUNDANT_CITATION_PATTERN` 为 `在《[^》]+》[里中]…`，覆盖「里」「中」两种句式。
- 新增 `MODERN_ENGLISH_WHITELIST`（KPI/OKR/HR/PR/CEO/CFO/CTO/COO/offer/bug/BATNA/CRIB/PPT/DNA/ID/APP/API/PDF/MBA/EMBA/VIP/360度 共 22 个行业通用词）。
- 新增 `MODERN_AI_OVERSTRICT_PATTERNS`（不是.*而是/他不是.*是/容易被忽略/可见/第[一二三四五六]层/最关键的.*是/这说明/这事说明 共 8 个敏感模式）。
- 新增 `check_mixed_language_modern()`：先剔除白名单词再跑中英混杂正则。
- 新增 `filter_ai_tone_for_modern()`：现代专栏过滤掉敏感 AI 味模式（由 `check_soft_ai_pattern` 接管「不是X是Y」控量）。
- `run_content_quality_checks()` 在 `is_modern` 时改用上述两个新函数。

**文档/规则/技能同步**：
- `.trae/skills/deep-reading/content-quality.md` §8.2 补充白名单、AI 味放宽、冗余正则扩展说明。
- `.trae/skills/content-review/SKILL.md` 现代职场额外检查项补充白名单和 AI 味放宽两条。

### 验证结果
- `python scripts/check_book_structure.py --output output --strict`：0 问题（P0/P1/P2 全清零）。
- `run_content_quality_checks` 全 67 章：最低 97，最高 100，平均 99.4，≥97 分 67/67。
- 分类排序核对：`_meta.yaml sort=103` 与他书无冲突；10 组 `chapter_sort` 0-9 连续；组内 `sort` 从 1 递增无跳号；`chapter` 与文件名下划线前部分完全一致。

### 新共性问题
1. **质检规则按内容类型分化**：古籍专栏与现代专栏的"正常表达"边界不同（如「不是X而是Y」对古籍是 AI 味，对现代职场是常见判断句）。未来新增非史类专栏（如心理学、商科）时，应先识别内容类型再套用对应规则集，避免一刀切误报。
2. **子 Agent 易产生引用标注冗余**：生成「XX在《YY》里讲过…」时倾向句末再挂「（大意据《YY》）」以求严谨，反成冗余。应在写作规范中明确「正文已写明出处的，句末不再挂大意据标注」。
3. **并行质检后必须重跑分数**：Task Agent 修复后报告"已修"，但实际可能漏修（本次「底层操作系统」第一次 Agent 只改 1 处变体）。主流程必须重跑 `run_content_quality_checks` 验证分数达标，不能轻信子 Agent 报告。

### 规则/checklist/Skill 更新
- `src/utils/content_quality.py`
- `.trae/skills/deep-reading/content-quality.md`
- `.trae/skills/content-review/SKILL.md`
- `tests/bug_regression_list.md`（BUG-024）

### 可复用资产
- `MODERN_ENGLISH_WHITELIST` / `MODERN_AI_OVERSTRICT_PATTERNS` 模式可复用到其他现代非史类专栏（商科/心理学/管理）的白名单与过滤设计。
- "区分真实问题 vs 误报 → 先修真实问题 → 再优化规则消误报 → 重跑分数验证"的流程可复用于所有质检规则调优场景。

**教训标签**：`#lesson: content_quality`

---

## 2026-06-24 章节标题禁止「模块N」前缀

### 触发问题
用户发现多本书籍的目录大标题里出现「模块0」「模块1」等前缀，影响目录展示。此前虽清理过一次，但只改了一本书，问题在其他书中反复出现。

### 根因定位
1. **`scripts/rename_modules_with_prefix.py` 脚本自动添加前缀**：该脚本把养生类课程文件名统一为「模块N模块名_章节名.md」，并同步把 frontmatter `chapter` 也改成带前缀的形式。
2. **规范未禁止、校验未拦截**：README 命名规范、写作规则、校验脚本均未将「模块N」前缀列为禁止项，导致问题可以持续产生并合入。

### 修复方案
1. **全面清理**：新增 `scripts/remove_module_prefixes.py`，遍历所有书籍，移除 frontmatter `chapter` 字段与文件名中的「模块N」前缀，保持 `sort`/`chapter_sort` 不变，共处理 146 个文件。
2. **删除根因脚本**：删除 `scripts/rename_modules_with_prefix.py`，避免再次被执行。
3. **校验拦截**：`scripts/check_book_structure.py` 新增 P1 规则，文件名章节部分或 frontmatter.chapter 含「模块N」前缀即报 P1 错误，`--strict` 模式下会阻断合并。
4. **回归测试**：`tests/test_book_structure.py` 新增 `test_check_file_rejects_module_prefix_in_chapter`，确保检测规则长期有效。
5. **规范固化**：
   - `README.md` §八命名规范明确禁止「模块N」前缀
   - `.trae/rules/dev-workflow.md` 新增命名约束
   - `.trae/checklists/dev-checklist.md` 新增对应检查项
   - `tests/bug_regression_list.md` 新增 BUG-019

### 验证结果
- `python scripts/check_book_structure.py --output output --strict`：0 问题，退出码 0
- `grep -r "模块[0-9]" output/`：无匹配
- `pytest tests/test_book_structure.py::test_check_file_rejects_module_prefix_in_chapter`：通过

### 新共性问题
1. **一次性清理脚本无法防止复发**：如果没有校验脚本和测试集兜底，类似的 UI 文案问题会在新的生成/迁移中重新出现。
2. **根因脚本长期留在仓库是隐患**：即使已经修复，只要 `rename_modules_with_prefix.py` 还存在，就可能被误执行或复制到别处使用。

### 规则/checklist/Skill 更新
- `.trae/rules/dev-workflow.md`
- `.trae/checklists/dev-checklist.md`
- `README.md`
- `tests/bug_regression_list.md`

### 可复用资产
- `scripts/remove_module_prefixes.py` 可作为批量重命名/清理 frontmatter 的模板。
- "发现 UI 文案问题 → 一次性清理 → 校验脚本拦截 → 回归测试兜底 → 规范固化"的流程可复用于其他文案/命名类问题。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-24 合并前必须清零所有校验问题

### 触发问题
本次合并 `master` 时，`check_book_structure.py` 报出 39 个 P2 问题（养生类书籍 `sort` 值不连续）。这些 P2 问题虽非本次代码改动直接引入，但属于 AI 生成的数据债务，按旧流程会被默认放行，导致问题持续堆积。

### 根因定位
1. **P2 默认不阻断**：`scripts/check_book_structure.py` 默认只在 P0/P1 时返回 1，P2 仅提示。
2. **合并流程缺失零缺陷要求**：规则、Skill、checklist 没有明确要求"合并前必须解决所有问题（包括非本次引入）"。
3. **问题未沉淀到测试集**：类似的数据生成 bug 没有回归测试和 bug 回归记录，容易反复出现。

### 修复方案
1. **`scripts/check_book_structure.py` 新增 `--strict` 参数**：P0/P1/P2 任一失败都返回 1。
2. **CI/Hooks/回归测试集统一使用 `--strict`**：
   - `.github/workflows/regression.yml`
   - `.github/workflows/pages.yml`
   - `githooks/pre-push`
   - `tests/run_regression_suite.sh`
3. **规则/Skill/checklist 同步更新**：
   - `.trae/rules/dev-workflow.md`：明确合并前清零所有问题，禁止以"非本次引入"跳过。
   - `.trae/skills/git-merge-guardian/SKILL.md`：本地验证改用 `--strict`，失败必须修复并沉淀。
   - `.trae/skills/dev-selfcheck/SKILL.md`：自检必须跑 `--strict` 并补充回归测试。
   - `.trae/checklists/dev-checklist.md`：新增结构校验清零与 bug 回归记录检查项。
4. **修复 wellness books sort 不连续问题**：按章重新编号为 1,2,3...。
5. **补充测试与回归记录**：
   - `tests/test_book_structure.py::test_output_has_no_structure_issues`
   - `tests/test_sorting.py::test_wellness_book_sort_values_are_continuous_per_chapter`
   - `tests/bug_regression_list.md` BUG-017
6. **文档更新**：`README.md` 新增「合并前强制检查」章节。

### 验证结果
- `python scripts/check_book_structure.py --output output --strict`：0 问题，退出码 0。
- `pytest -q`：全部通过。
- `bash tests/run_regression_suite.sh`：全部通过。

### 新共性问题
1. **AI 生成的数据问题必须在合并前清零**：不能因"不是这次引入"就放行。未来任何合并都要把 `--strict` 作为门禁。
2. **规则/Skill/checklist/CI/Hooks 必须联动更新**：只改一处很难坚持，需要把流程固到多个层次。

### 规则/checklist/Skill 更新
- `.trae/rules/dev-workflow.md`
- `.trae/skills/git-merge-guardian/SKILL.md`
- `.trae/skills/dev-selfcheck/SKILL.md`
- `.trae/checklists/dev-checklist.md`
- `README.md`

### 可复用资产
- `--strict` 模式可复用到所有需要"默认告警、合并门禁"的校验脚本。
- "问题修复 + 回归测试 + bug 回归记录"三段式沉淀方法，可复用于所有 AI 引入的数据/代码缺陷。

**教训标签**：`#lesson: git_hygiene` `#lesson: book_structure`

---

## 2026-06-24 Service Worker 缓存导致手机端"幽灵旧版"

### 触发问题
BUG-013 修复并部署后，PC 浏览器访问 GitHub Pages / ModelScope 均正常，但部分手机端用户反馈：返回书架后蒙层仍残留、且无自动阅读按钮。多 Agent 排查后确认不是两套代码，而是 Service Worker 缓存未刷新。

### 根因定位
- `site/sw.js` 对核心静态资源（`index.html` / `style.css` / `app.js`）使用 `cacheFirst` 策略。
- 缓存名固定为 `halo-read-v1`，只要手机浏览器/PWA 曾经缓存过旧 `app.js`，后续访问会优先读取本地缓存。
- 服务器端虽已部署新版，但用户设备上的 SW 仍服务旧缓存，形成"代码已更新、用户端仍旧"的幽灵旧版。

### 修复方案
将 `CACHE_NAME` 从 `halo-read-v1` 升级为 `halo-read-v2`：
- 新的 SW install 阶段创建 `v2` 缓存并重新预缓存最新核心资源。
- activate 阶段清理所有非当前名的旧缓存（包括 `v1`）。
- `clients.claim()` 立即接管所有已打开页面，强制刷新。

### 验证结果
- GitHub Pages 与 ModelScope 桌面/移动视口浏览器验收：返回书架无蒙层、自动阅读按钮存在。
- 本地回归套件 `bash tests/run_regression_suite.sh` 通过。
- 已记录为 `tests/bug_regression_list.md` BUG-018。

### 新共性问题
1. **Service Worker 缓存版本需要人工维护**：目前靠注释和开发者记忆来升级 `CACHE_NAME`，容易遗漏。
2. **回归测试集未覆盖 SW 缓存失效**：自动测试难以模拟真实手机 SW 生命周期，目前依赖浏览器验收。
3. **前端产物同步问题**：`site/sw.js` 与 `src/web/static/js/app.js` 等前端文件是否为双源？实际上当前 `site/` 是手工维护的部署产物（BUG-016 已部分解决），SW 也属于其中一员；若构建脚本不能自动同步 SW，则版本号管理更容易出错。

### 规则/checklist/quality.py 更新
- 无需更新讲书规则。
- 建议后续在 `.trae/checklists/dev-checklist.md` 增加"前端关键修复时是否同步升级 SW 缓存版本"检查项；若再次出现同类问题，应补充。
- 可考虑在回归测试集中增加简单检查：对比 `site/sw.js` 中 `CACHE_NAME` 与最近一次 tag/release 是否变化，提醒开发者。

### 可复用资产
- BUG-018 记录了一套"PC 正常、手机异常"的排查路径：先确认是否多套代码 → 再确认部署产物是否同步 → 再确认浏览器/Service Worker 缓存。
- 升级 `CACHE_NAME` 是处理 `cacheFirst` PWA 缓存的最快修复；长期更优方案是构建时自动注入内容哈希，或改用 `staleWhileRevalidate`/`networkFirst`。

**教训标签**：`#lesson: deployment` `#lesson: reader_interaction` `#lesson: book_structure`

---

## 2026-06-24 返回书架蒙层残留回归修复

### 触发问题
用户反馈：在阅读视图中打开目录抽屉后点击"返回书架"，回到首页时页面被半透明蒙层覆盖，必须再点击一次蒙层才会消失。该问题此前修复过，后被重新引入。

### 根因定位
- `backToHome()` 只重置了阅读状态（currentBook/currentBookTree/activePath/searchQuery）并切换视图，**没有关闭 `sidebarOverlay`**。
- `sidebarOverlay` 位于 `#readerView` 之外，即使阅读视图隐藏，只要仍带 `open` class，就会继续覆盖在首页之上。
- 同类的 `settingsOverlay`/`modalOverlay` 也存在同样隐患（设置面板、生成笔记弹窗打开时返回书架同样会留下蒙层）。

### 修复方案
在 `site/js/app.js` 和 `src/web/static/js/app.js` 的 `backToHome()` 返回首页前，统一调用：
- `closeSidebar()`
- `closeSettings()`
- `closeModal()`

确保所有遮罩层随视图切换一并关闭。

### 测试驱动（TDD）
1. 先在 `tests/test_reader_features.js` 新增测试13：打开目录抽屉 → 点击返回书架 → 断言 `sidebarOverlay` 不再含 `open` class 且回到 `home` 视图。
2. 运行测试，确认失败（复现 bug）。
3. 修改实现后再次运行，测试通过。
4. 运行完整回归套件 `bash tests/run_regression_suite.sh`，全部通过。

### 验证结果
- `node tests/test_reader_features.js`：79 项全部通过。
- `bash tests/run_regression_suite.sh`：12 项全部通过。
- `pytest tests/`：114 passed, 15 skipped。
- `node --check site/js/app.js && node --check src/web/static/js/app.js`：语法 OK。
- 已将此 bug 记录进 `tests/bug_regression_list.md`（BUG-013）。

### 新共性问题
1. **`src/web/static/js/app.js` 与 `site/js/app.js` 已分叉**：diff 显示两者差异显著（site 版包含自动阅读、沉浸模式、搜索索引拆分等功能，src/web 版为旧版）。本次 bug 修复必须同步修改两处，未来任何前端改动都容易漏改。建议后续明确 `site/` 为唯一部署源，或将 `src/web/static/` 作为源通过构建脚本同步到 `site/`，避免双源维护。
2. **视图切换时清理 overlay 是反复出现的模式问题**：此前沉浸模式也专门在 `switchView('home')` 中退出沉浸。未来若再新增遮罩层，应考虑统一在 `switchView('home')` 中关闭所有 overlay，而不是依赖每个返回入口（backToHome / brandLockup / 键盘 ESC 等）各自处理。

### 规则/checklist/quality.py 更新
- 本次为前端 bug 修复，未涉及讲书笔记写作规则，无需更新 `.trae/rules/rules.md`、`content-quality.md`、`quality.py`。
- `.trae/checklists/dev-checklist.md` 暂无"视图切换清理 overlay"专项，可在后续若再出现同类问题时考虑补充。

### 可复用资产
- `tests/test_reader_features.js` 中的回归测试模式：先写失败断言 → 改实现 → 全量回归，适用于所有"曾修复后回归"的 UI bug。
- 双源同步检查建议：未来涉及 `site/js/app.js` 或 `src/web/static/js/app.js` 的改动，diff 两者差异应成为默认检查项。

**教训标签**：`#lesson: reader_interaction` `#lesson: book_structure`

---

## 2026-06-24 资治通鉴专栏续写至 50 章

### 任务概述
《资治通鉴》专栏原有 20 章（周纪一→汉纪三），续写至 50 章，新增 30 章，覆盖汉纪三→隋纪八（白登之围→隋亡唐兴），按编年顺序排列。完成后按 content-quality.md 四维度质检。

### 执行流程
1. **规划**：盘点现有 20 章，按《资治通鉴》原著编年顺序规划 30 个新章节（汉纪三→隋纪八）。
2. **并行写作**：6 批 × 5 个 subagent 并行写作，每批 5 章。Batch A 首次结果丢失后重做。
3. **章节名更正**：写作中发现"汉纪六十七_诸葛亮北伐"章节名错误（《资治通鉴》汉纪仅 60 卷，诸葛亮北伐在魏纪），更正为"魏纪三_诸葛亮北伐"。
4. **并行质检**：3 个 subagent 各负责 10 篇，按四维度（真实性40/可读性30/顺序15/引用克制15）评分，不合格直接修复。

### 质检结果
30 篇全部 ≥85 分合格，平均分约 95。共修复 14 处问题：
- **P0 真实性（5处）**：李陵世系（李广是祖父非父）、霍光与霍去病关系（同父异母兄弟非姐弟）、王莽篇伪民谣"五侯九伯"（张冠李戴《左传》）、岑彭"理财名将"（实为军功名将）、班超年龄（七十三→七十一）、元嘉北伐"刘濞"（应为刘濬）。
- **P1 可读性（7处）**：AI 模板过渡句"这条道理在历史上反复应验"、现代术语"零和博弈"、金句单章内重复（食少事烦/司马昭之心/千里绝烟等）。
- **P2 引用克制（2处）**：内联出处跳转提示、同一出处连续出现。

### 新共性问题
1. **subagent 结果偶发丢失**：Batch A 首次执行结果未返回，需重做。大规模并行时应有结果校验机制。
2. **章节编号与原著卷次错位**：写作 agent 对《资治通鉴》卷次划分不熟，将魏纪事件误标汉纪。需在写作 prompt 中强调卷次核验。
3. **人物世系/关系易错**：李广-李陵（祖孙）、霍去病-霍光（同父异母兄弟）、刘濞-刘濬（不同朝代不同人）等关系易混淆，需在质检环节重点核验。
4. **金句单章内重复**：同一金句（如"食少事烦其能久乎""司马昭之心路人所知"）在讲事情和讲人物/讲道理中重复出现，写作时需强化"单章内同一金句只出现一次"规则。

### 规则更新建议（未执行，记录待办）
- content-quality.md §3.2 重复控制：可补充"金句/古文在讲事情已出现，讲人物/讲道理引用时须改写或用'前面说过'一笔带过"。
- 写作 prompt 模板：可补充"章节编号须与《资治通鉴》原著卷次核验，汉纪60卷、魏纪10卷、晋纪40卷、宋纪10卷、齐纪10卷、梁纪56卷、陈纪10卷、隋纪8卷"。
- 质检 checklist：可补充"人物世系关系核验项"（祖孙/父子/兄弟/姐弟易混）。

### 产出
- 新增 30 个 Markdown 文件于 `output/资治通鉴/`
- 专栏总计 50 章，覆盖三家分晋（前403）→隋亡唐兴（618），跨千余年编年
- 30 篇质检全部合格，可直接发布

**教训标签**：`#lesson: ai_course` `#lesson: content_quality`

---

## 2026-06-24 阅读器 UI/交互修复与浏览器验收

### 触发问题
用户反馈阅读器存在三类问题：
1. 沉浸按钮在左侧章节名过长时被撑成竖排，样式崩坏。
2. 进入沉浸模式后无法退出，也无法打开章节目录。
3. master 分支 GitHub Pages 部署版本缺少自动阅读和壁纸切换功能。

### 修复内容
1. **沉浸按钮布局**：`.immersive-btn` 增加 `flex-shrink: 0; white-space: nowrap;`，防止在 `toolbar-brand` 占据空间后被挤压换行。
2. **沉浸模式交互**：
   - CSS 隐藏 UI 的条件从单一 `.immersive-mode` 改为 `.immersive-mode.ui-hidden`，让点击阅读区中央可唤出/隐藏工具栏与目录。
   - JS 补全 `enterImmersiveMode`/`exitImmersiveMode`/`toggleImmersiveMode`，进入沉浸默认隐藏 UI，点击沉浸按钮或返回首页可退出。
   - Fullscreen API 仅作为可选增强，失败时回退到纯 CSS 沉浸；新增 `immersiveEnterLock` 防止进入瞬间被同步事件错误移除沉浸类。
3. **静态产物同步**：`scripts/build_site.py` 新增 `_copy_static_assets()`，构建时自动把 `src/web/static-site/` 的 `index.html/css/style.css/js/app.js/sw.js` 复制到 `site/`，避免 GitHub Pages 部署版本滞后于源码。
4. **壁纸按钮文案**：设置面板中的「默认」改为「无」，与 `data-wallpaper="none"` 语义一致。

### 测试与验证
- `pytest` 全量 114 项通过（补装 `PyYAML`/`langgraph` 后）。
- `node tests/test_reader_features.js` 12 组 76 项全部通过。
- `bash tests/run_regression_suite.sh` 12 项全部通过。
- 浏览器验收：进入沉浸、中央唤出 UI、打开章节目录、退出沉浸、壁纸切换、自动阅读均正常。

### 暴露的共性问题
1. **jsdom 测试双实例**：`site/index.html` 已自带 `<script src="js/app.js" defer>`，测试又手动注入 app.js，导致事件监听器双注册，沉浸按钮触发两次（进入后立即退出）。修复方式：测试 `buildDom()` 中先移除 HTML 里的外部脚本引用再注入单实例。
2. **测试断言滞后于实现**：`test_reader_features.js` 测试11 仍断言 `.immersive-mode .toolbar`，但实现已改为 `.immersive-mode.ui-hidden .toolbar`，已同步更新测试。
3. **环境依赖缺失**：`PyYAML` 与 `langgraph` 未安装时 pytest 部分测试失败；CI 中应确保 `requirements.txt` 完整安装。

### 后续约束
- 修改 `src/web/static-site/` 后必须运行 `python scripts/build_site.py` 验证 `site/` 产物同步。
- 涉及沉浸/全屏的改动必须同时跑 jsdom 回归与浏览器验收。

**教训标签**：`#lesson: reader_interaction` `#lesson: book_structure`

---

## 2026-06-24 养生类课程目录重构与分类归并

> 本条合并自原 L108（养生类课程目录重构与排序修复）与 L256（养生类课程目录重构与分类归并）两条记录，两者为同一批重构的不同侧面。

### 改动范围
- 将《饮食养生课》《饮食养生课第二版》《睡眠与精力修复课》统一归入 `category: 养生`。
- 按「模块名_章节名」结构重命名全部养生类笔记，与远端 master 上其他专栏保持一致。
- 将《饮食养生课》两套模块拆分为两本书，其中一套命名为《饮食养生课第二版》。
- 修复 `src/utils/sorting.py` 的章节排序：优先使用 `chapter_sort`（模块顺序）与 `sort`（章内事件顺序）。
- 修复 `scripts/build_site.py`：当环境缺少 PyYAML 时，`_load_book_meta` 也能正确解析 `_meta.yaml`，避免分类被误判为「未分类」。
- 新增 `scripts/migrate_wellness_books.py` 迁移脚本与 `scripts/rename_modules_with_prefix.py` 统一命名脚本（注：后者后因 BUG-019 删除）。
- 新增 `tests/test_migrate_wellness_books.py` 覆盖模块映射逻辑。
- 修复 `tests/conftest.py`：当环境缺少 `langgraph` 等依赖时，跳过 workflow mock，避免阻塞无关测试。

### 验证结果
- `python scripts/check_book_structure.py --output output`：通过。
- `python scripts/check_chapter_order.py --output output`：通过。
- `python scripts/build_site.py --output output --site site`：通过。
- `python scripts/check_duplicates.py`：无重复。
- `bash tests/run_regression_suite.sh`：通过。
- `pytest tests/test_book_structure.py tests/test_sorting.py tests/test_check_chapter_order.py`：通过。
- 构建后 `index.json` 中「养生」分类包含：睡眠与精力修复课、饮食养生课、锻炼养生课、饮食养生课第二版。

### 暴露的共性问题
1. 测试环境依赖不完整：`yaml`/`langgraph` 未安装时，原有 `autouse=True` 的 fixture 会强制加载 `src.core.workflow`，导致所有测试失败。
2. PR 与 master 并行修改同一份笔记目录，容易产生重命名冲突。

### 后续行动
- 已在 `tests/conftest.py` 中做最小修复：导入 workflow 失败时跳过 mock。
- 建议在 CI 中安装完整依赖，确保 regression 测试有效；大规模目录重构前先同步 master 状态。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-24 资治通鉴大章节顺序错乱修复（BUG-022）

### 改动范围
- `src/utils/sorting.py`：引入「阶段模式」`STAGE_MODE_BOOKS = {"资治通鉴"}`，阶段模式书籍按 `(chapter_sort, 章节名序号)` 排序，避免中文字符串序；其他书籍保持 `(chapter_sort, event sort)` 不变。
- `scripts/check_book_structure.py`：新增 `_check_stage_mode_order`，对阶段模式书籍校验同一朝代/纪的 `chapter_sort` 必须等于 `BOOK_CATEGORY_ORDER` 配置的阶段序号。
- `scripts/build_site.py`：跳过下划线开头的辅助文件（如 `_目录.md`），避免目录中出现空章节。
- `scripts/fix_zizhi_chapter_sort.py`：新增一次性修复脚本，把 `output/资治通鉴/` 下所有文件的 `chapter_sort` 统一为朝代阶段序号。
- `tests/test_sorting.py`、`tests/test_book_structure.py`、`tests/bug_regression_list.md`：补充回归测试与 BUG-022 记录。

### 验证结果
- `python scripts/check_book_structure.py --output output --strict`：0 问题，退出码 0。
- `pytest -q`：127 passed, 15 skipped。
- `bash tests/run_regression_suite.sh`：12/12 通过（jsdom 未安装跳过 1 项，不阻塞）。
- 构建后 `site/data/index.json` 中「资治通鉴」顺序：周纪一→周纪五→秦纪一→秦纪三→汉纪一→汉纪五十七→魏纪三→隋纪八，符合编年顺序。

### 暴露的共性问题
1. **排序语义只靠 frontmatter 字段约定不够**：`chapter_sort` 在不同书里被当成阶段序号或绝对顺序，缺乏代码层显式声明，导致数据迁移/重新生成时容易写错。
2. **校验脚本未覆盖大章节顺序**：`check_book_structure.py` 原本只校验章内 `sort` 和单章 `chapter_sort` 一致性，不校验跨章的大章节顺序，导致排序 bug 能穿过 CI/pre-push。
3. **下划线辅助文件被误纳入站点构建**：`_目录.md` 无 frontmatter，被 `build_site.py` 解析为空章节，与 `check_book_structure.py` 的跳过逻辑不一致。

### 后续行动
- 阶段模式语义已通过 `STAGE_MODE_BOOKS` 和 `_check_stage_mode_order` 固化，未来新增「阶段模式」书籍只需加入集合并配置 `BOOK_CATEGORY_ORDER`。
- `--strict` 模式下大章节顺序错误会被 P1 阻断，需在 CI/pre-push 中保持启用。
- 建议后续所有下划线开头的 `output/` 辅助文件统一由构建脚本跳过，与校验脚本行为一致。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-24 移动端阅读器多项体验问题修复（BUG-020）

### 改动范围
- `src/web/static-site/index.html`：删除宣纸/水墨/星空壁纸按钮；删除右下角自动阅读浮动按钮；设置面板新增「自动阅读」开关；阅读区添加 `.reader-wallpaper` 真实壁纸层。
- `src/web/static-site/css/style.css`：壁纸层样式改为 `.reader-wallpaper` 并铺满滚动内容；删除已删壁纸的 CSS 预设与 `.auto-scroll-btn` 样式；代码块增加横向滚动触控；设置面板 range 滑条增大触控区域。
- `src/web/static-site/js/app.js`：`loadNote` 后重建壁纸层并同步 `scrollHeight`；`shouldExcludeTap` 排除 `pre/code`；`start/pauseAutoScroll` 与设置开关状态同步；`init()` 强制重置视图状态并监听 `pageshow` 防止 bfcache 白屏。
- `src/web/static-site/sw.js`：`CACHE_NAME` 升级到 `halo-read-v3`。
- `tests/test_reader_features.js`、`tests/test_build_site.py`、`tests/bug_regression_list.md`：补充回归测试与 BUG-020 记录。

### 验证结果
- `python scripts/check_book_structure.py --output output --strict`：✅ 通过
- `pytest -q`：✅ 124 passed, 15 skipped
- `node tests/test_reader_features.js`：✅ 99 passed, 0 failed
- `bash tests/run_regression_suite.sh`：✅ 13/13 通过
- `git push origin master`：✅ 已推送

### 暴露的共性问题
- 测试环境依赖不完整：初始 `pytest` 因 `langgraph` 未安装失败；已安装 `requirements.txt`，但 CI 应确保依赖完整，避免本地/云端测试结果不一致。
- Service Worker cache-first 策略下，前端关键修复必须同步升级 `CACHE_NAME`，否则手机端会出现「幽灵旧版」。

### 后续行动
- 在 CI workflow 中增加 `pip install -r requirements.txt` 与 `npm install` 步骤，确保回归测试可执行。
- 前端关键改动后， checklist 强制提醒升级 `CACHE_NAME`。

**教训标签**：`#lesson: reader_interaction` `#lesson: deployment`

---

## 2026-06-24 沉浸模式点击后强制横屏 + 代码块无法自动换行修复（BUG-021）

### 改动范围
- `src/web/static-site/js/app.js`：彻底移除 Fullscreen API 调用（requestFullscreen/exitFullscreen 及 vendor 前缀），沉浸模式改为纯 CSS 实现，避免小米等浏览器强制横屏。
- `src/web/static-site/css/style.css`：`.markdown-body pre code` 改为 `white-space: pre-wrap` 与断词属性，让代码块在手机端自动换行。
- `tests/test_reader_features.js`、`tests/test_build_site.py`、`tests/run_regression_suite.sh`：补充「不调用 Fullscreen API」与「代码块自动换行」回归断言。
- `tests/bug_regression_list.md`、`docs/loop_log.md`：新增 BUG-021 记录与开发沉淀。

### 验证结果
- `python scripts/check_book_structure.py --output output --strict`：✅ 通过
- `pytest -q`：✅ 通过
- `node tests/test_reader_features.js`：✅ 通过
- `bash tests/run_regression_suite.sh`：✅ 通过

### 暴露的共性问题
- 之前把 Fullscreen API 当作「可选增强」，实际在国产浏览器上并不安全，会强制横屏；移动端阅读器应彻底禁用任何可能影响方向的系统 API。
- 代码块体验应优先自动换行，横向滚动仅作为兜底。

### 后续行动
- 在 `.trae/checklists/dev-checklist.md` 中增加移动端验收项：禁用 Fullscreen API / orientation.lock，代码块优先 pre-wrap。

**教训标签**：`#lesson: reader_interaction`

---

## 2026-06-23 沉浸模式回归修复 + 合并冲突清理 + 历史 bug 回归测试集

### 触发问题
用户反馈"之前让 AI 在云端沙箱做了自动阅读和更换背景的功能，说已经合并 master 并完成代码 push，代码真的 push 了吗？为啥没展示自动阅读这些功能，反而把沉浸阅读改坏了，现在手机端点击沉浸又变成横屏了"。

### 核实结果
- `git log --all` 只有 1 个提交 `ef9cee7 feat: 新增饮食养生课专栏`，loop_log 提到的 `de8bb9d feat: Implement Immersive Full-Screen Reading` 和"阅读器三功能"提交在远程**完全不存在**。
- 本地有 **14 个文件未解决合并冲突**（`<<<<<<< HEAD` 标记残留）：`scripts/build_site.py`、`.github/workflows/pages.yml`、`.trae/checklists/dev-checklist.md`、`README.md`、`output/资治通鉴/` 下 13 个 md。
- `scripts/build_site.py` 因冲突标记 SyntaxError 无法运行，站点无法构建，所以自动阅读/换背景功能"没展示"。
- `site/js/app.js` 壁纸/翻页/自动阅读三功能代码完整（916-1219行），但**沉浸模式 JS 逻辑完全缺失**（只有按钮注册和 CSS，无 `toggleImmersiveMode` 函数、无事件绑定），点击沉浸按钮无响应。

### 修复
1. **合并冲突解决**（14 文件）：
   - 代码/配置（build_site.py/pages.yml/dev-checklist/README）：保留 origin/master 侧（含 `_to_int` 排序函数、去重检查步骤、.nojekyll 生成、搜索索引拆分等功能）
   - output/资治通鉴/ 13 个 md：保留 HEAD 侧（符合 content-quality.md 引用克制规则，去除冗余行内引用）
2. **沉浸模式 JS 逻辑补回**（site/js/app.js）：
   - 新增 `enterImmersiveMode`/`exitImmersiveMode`/`toggleImmersiveMode`/`updateImmersiveBtn`/`initImmersive` 函数
   - **关键：不调用 `screen.orientation.lock`**，避免手机端被强制横屏；用 CSS `.immersive-mode` 隐藏 UI + 内容占满
   - Fullscreen API 作为可选增强（多 vendor 兼容：`requestFullscreen`/`webkitRequestFullscreen`/`msRequestFullscreen`），失败时静默回退到纯 CSS 沉浸
   - 监听 `fullscreenchange` 同步状态（ESC 退出系统全屏时同步移除 CSS class）
   - 沉浸按钮显隐统一由 `switchView` 管理（阅读视图显示，首页隐藏），移除 `detectModelScopeEmbed` 里的按钮显示控制
   - 返回首页时自动退出沉浸模式
3. **历史遗留清理**：
   - 运行 `scripts/remove_duplicates.py` 删除 220 个重复文件（编号文件 + 主题分组文件并存）
   - 给 16 个资治通鉴编号文件补 `sort` frontmatter 字段（按历史时间序：商鞅变法=1/孙庞斗智=2、苏秦合纵=1/张仪连横=2 等）
4. **回归测试集**：
   - 新增 `tests/bug_regression_list.md`：11 个历史 bug 列表 + 根因 + 复现步骤 + 回归测试方式
   - 新增 `tests/run_regression_suite.sh`：一键执行 8 大类 11 项检查（合并冲突标记、app.js 语法、沉浸模式防横屏、站点构建、阅读器 e2e、重复文件、章节排序、HTTP 冒烟）
   - `tests/test_reader_features.js` 新增测试 10/11/12（沉浸模式交互、不锁定方向、返回首页退出）

### 关键教训
- **"已 push"不能只信汇报，必须 `git log --all` 核实**：本次远程只有 1 个提交，loop_log 却记录了多个"已推送"的 commit。合并冲突未解决时 git 不允许 commit/push，但执行者可能误以为成功。后续涉及"代码已合并/push"的断言，必须用 `git log --all --oneline` 和 `git status` 核实。
- **合并冲突标记会阻断 Python 构建**：`<<<<<<< HEAD` 在 Python 里是 SyntaxError，在 Markdown 里会被当作正文渲染。合并后必须全局搜索冲突标记，不能只靠 IDE 提示。
- **沉浸模式不能依赖 `screen.orientation.lock`**：该 API 在手机端会强制横屏，且需要 fullscreen 权限，兼容性差。正确做法是用 CSS `.immersive-mode` 隐藏 UI + 内容占满，Fullscreen API 仅作可选增强且失败静默回退。
- **按钮显隐应统一由视图切换管理**：之前沉浸按钮只在 `detectModelScopeEmbed`（魔搭嵌入）里显示，导致非魔搭环境（普通手机浏览器）按钮永远 hidden。按钮显隐应集中在 `switchView`，按视图决定，不按环境决定。
- **回归测试集应包含"合并冲突标记检查"**：这是本次最大的坑，后续每次合并后必须跑 `grep -rn "^<<<<<<< HEAD"` 确认无残留。

### 测试覆盖
- `tests/test_reader_features.js`：76 项全通过（含新增沉浸模式 22 项断言）
- `tests/run_regression_suite.sh`：11 项全通过
- HTTP 冒烟：index.html / app.js / style.css / index.json 全 200
- `node --check site/js/app.js`：语法 OK

### 配套改动
- 修改：`site/js/app.js`（沉浸逻辑 + 按钮显隐）、`scripts/build_site.py`（冲突解决）、`.github/workflows/pages.yml`（冲突解决）、`.trae/checklists/dev-checklist.md`（冲突解决）、`README.md`（冲突解决）、`output/资治通鉴/*.md`（13 文件冲突解决 + 16 文件补 sort）
- 删除：220 个重复 Markdown 文件（由 remove_duplicates.py 清理）
- 新增：`tests/bug_regression_list.md`、`tests/run_regression_suite.sh`

### 待用户决策
本地有大量改动未 commit/push。用户若要发布，需 `git add` 相关文件 + `git commit` + `git push`（push 前先 `git fetch` 确认远程无新提交）。

**教训标签**：`#lesson: git_hygiene` `#lesson: reader_interaction`

---

## 2026-06-23 阅读器三功能（壁纸/翻页/自动阅读）

### 背景
为静态站点阅读器新增三个阅读增强功能：阅读壁纸切换、上下滑动+点击翻页、番茄式自动阅读。

### 流程
1. 启用计划评审技能，因 LLM_API_KEY 未配置，改用 Task 工具并行启动 3 个专家子代理（架构师/测试/规则）做真实并行评审，报告存于 `docs/reviews/plan_review_20260623_reader_features.md`。
2. 按评审意见实现：桌面端 tap 模式仅中央点击切换 UI（避免破坏桌面体验）、行高取 `.markdown-body` 计算值、rAF deltaTime clamp、touch/click 用 `tapHandled` 标志防双触发、夜间壁纸用 CSS 覆盖。
3. 测试驱动：先确认 `site_e2e_test.js` 基线通过，再新增 `tests/test_reader_features.js`（54 项），覆盖壁纸/翻页/自动阅读/排除元素/末尾暂停/切章暂停。
4. 真实测试：jsdom e2e（执行真实 app.js）+ HTTP 服务器冒烟（全 200）+ 语法检查。沙箱无系统浏览器，Puppeteer 下载失败，jsdom 为最接近真实浏览器的可行方案。

### 新共性问题
1. **`tests/test_web_reader.py` 基线已坏**：该测试针对 `src/web/` 旧路径（非 `site/`），且因缺 `langgraph` 模块直接报 ImportError，与本次改动无关但易误导。建议后续统一迁移到 `site/` 或标注废弃。
2. **jsdom 测试需 polyfill**：rAF/TouchEvent/matchMedia 在 jsdom 缺失，测试需在入口注入 fake 实现，否则自动阅读与移动端翻页无法测。
3. **评审技能的两条路径**：LLM_API_KEY 未配置时 plan-review Skill 的 Python 引擎不可用，退化为 Task 工具并行子代理（路径 A 增强版），效果接近但非 LangGraph 真并行。

### 规则/工具更新
- `.gitignore` 新增 `node_modules/`（测试时本地安装 jsdom/marked，避免误提交）。
- 无需更新 `config.yaml`/`.env.example`（前端纯静态站点，无后端配置）。
- 无需更新 `content-quality.md`/`quality.py`（本次为代码改动，非讲书内容）。

### 可复用资产
- `tests/test_reader_features.js` 的 rAF polyfill（`__rafQueue`/`__flushRaf`）可作为后续 jsdom 测试动画/滚动的模板。
- `handleReaderTap` 的 touch/click 防双触发模式（`tapHandledByTouch` 标志 + 位移/时长阈值）可复用于其他移动端点击场景。
- 壁纸用 CSS 渐变 + 内联 SVG data URI 实现的方案，无外部图片依赖，可复用于其他需要纹理背景的场景。

**教训标签**：`#lesson: reader_interaction`

---

## 2026-06-23 内容质检体系构建

### 任务概述
用户希望建立一套自动化的内容质检与修复体系，解决生成内容中的核心问题：
1. **真实性**：AI 幻觉、编造来源、无据设定。
2. **可读性**：AI 套路句、现代术语、单章/章节间重复。
3. **顺序**：叙事与章节排序按故事/时间先后。
4. **引用克制**：删除「（见讲故事）」「（详见下章）」等内联跳转，减少行内「——《XX》」引用密度。

### 交付物
| 文件 | 类型 | 作用 |
|---|---|---|
| `.trae/rules/content-quality.md` | 规则 | 质检四维度、评分标准、修复优先级 |
| `.trae/checklists/content-checklist.md` | Checklist | 逐项检查 + 打分模板 |
| `.trae/skills/content-review/SKILL.md` | Skill | Trae 入口，触发 Python 引擎 |
| `src/utils/content_quality.py` | 工具 | 规则化四维度检测 + 自动计分 |
| `src/agents/content_reviewer.py` | Agent | 汇总质检 Agent |
| `src/agents/content_reviewer_sub.py` | Agent | 史实核验/可读性/引用克制三视角子 Agent |
| `src/core/content_review_workflow.py` | 工作流 | LangGraph 三视角并行质检 |
| `scripts/review_content.py` | 脚本 | 内容质检命令行入口 |
| `prompts/content_reviewer.md` | 提示词 | 汇总质检 LLM 提示词 |
| `prompts/content_reviewer_sub.md` | 提示词 | 三视角子 Agent LLM 提示词 |

### 样本优化结果
使用 Task 工具并行优化 4 篇样本，规则化质检均达到 100 分：
- `output/史记/汉纪/07_鸿门宴.md`：删除冗余行内引用，补充时间与苏轼《范增论》点评。
- `output/孔子传/孔子18_见南子.md`：删除「（详见下章）」，替换现代术语「话术」为「辞令」。
- `output/孔子传/孔子19_匡地桓魋.md`：删除「——这一段，详见卷六相关章节，此处不赘」。
- `output/论语/07_启发式教学.md`：删除「（详见前一章）」，改写 AI 套路句。

### 新共性问题
1. **规则化检测的误报**：早期 `check_cross_chapter_jump` 把古籍引用括号误判为跳转提示；`check_years_present`/`check_famous_critics` 对《论语》《孔子传》等哲学经典不适用。
2. **AI 句式检测的边界**：「他不是不知道」「他不是不懂」等自然口语判断句被 pattern 误伤。
3. **引用密度阈值**：史记类叙事本身引用密集，每千字 ≤3 处的阈值需结合 LLM 二次判断，避免过度删除影响可信度。

### 规则/工具更新
1. `content-quality.md` 明确：引用资料统一放文末，关键名句可保留行内引用，每千字 ≤3 处。
2. `content_quality.py` 增加豁免逻辑：哲学/经典解读类内容不强制要求历史年份和司马光/司马迁名家。
3. `content_quality.py` 增加 `_filter_natural_expressions` 过滤自然口语中的「他不是 X，是 Y」误报。
4. `deep-reading SKILL.md` 更新：生成后自动触发 `scripts/review_content.py`。
5. `README.md` 更新：登记新增 Skill、规则、Agent、脚本、工具。

### checklist 更新
新增 `.trae/checklists/content-checklist.md`，覆盖真实性/可读性/顺序/引用克制四维度，含评分表与修复记录模板。

### 可复用资产
- `content_quality.py` 可作为其他 Markdown 内容质检的底层检测库。
- `content_review_workflow.py` 可作为「三视角并行质检」的 LangGraph 模板复用。

**教训标签**：`#lesson: content_quality`

---

## 2026-06-23 沉浸模式修复、全站去重与防重复检查机制固化

### 触发问题
用户反馈沉浸阅读模式点击后仍展示目录且横屏（期望竖屏无目录）；此前合并带入大量重复 Markdown（如孔子传、论语、三国、史记、唐宋明纪）；主题分组文件需要按时间线/故事线排序，子章节同样规则。

### 多 Agent 执行结果
- **沉浸模式**：远程已推送 `de8bb9d feat: Implement Immersive Full-Screen Reading`，本地滞后导致首次 push 被拒；rebase 后合并本地去重/排序改动。
- **重复文件清理**：`scripts/remove_duplicates.py` 基于内容哈希（忽略 frontmatter）分组，按优先级保留主题分组文件；清理三国、史记、唐纪、宋纪、明纪、孔子传、论语等 200+ 重复文件。
- **防重复检查**：新增 `scripts/check_duplicates.py`；CI workflow（`.github/workflows/pages.yml`）构建前强制运行；`.trae/checklists/dev-checklist.md` 增加提交前检查项；README.md 登记使用方式。
- **排序修复**：`src/utils/sorting.py` 补全 `is_flat_book` 函数并扩展 `BOOK_CATEGORY_ORDER`（史记加秦纪/汉纪、唐纪/宋纪/明纪独立配置）；`sort_notes_tree` 优先按 `chapter_sort`/`sort` frontmatter 字段排序；验证论语/资治通鉴/明纪等主题与章节均按时间线/故事线排列。

### 关键教训
- **推送前必须先 fetch 远程**：本地开发时远程可能已有新 commit，直接 push 会被拒；应养成 `git fetch` 习惯，或设置 push 前自动检查。
- **去重优先级规则**：主题分组文件（frontmatter chapter 与文件名 chapter 一致、带 sort/chapter_sort、中文主题名长）优先保留；含阿拉伯数字的文件名倾向于低优先级。
- **双字段排序职责不变**：`chapter_sort` 控制阶段/主题在书内顺序，`sort` 控制事件在主题内顺序；两者都是 frontmatter 标量，构建脚本需透传到 index.json。
- **测试与实现同步**：`tests/test_sorting.py` 原本引用不存在的 `is_flat_book`，补全函数的同时也扩展了排序配置测试，避免测试滞后于实现。

### 测试覆盖
全量 pytest 103 项通过；`check_duplicates.py` 全站无重复；`build_site.py` 生成 `site/data/index.json` 主题与子章节排序正确；本次改动文件 ruff 检查通过。

### 配套改动
- 新增 `scripts/check_duplicates.py`、`scripts/remove_duplicates.py`
- 修改 `scripts/build_site.py`、`src/utils/sorting.py`、`.github/workflows/pages.yml`、`.trae/checklists/dev-checklist.md`、`README.md`
- 删除 output/ 下 200+ 重复 Markdown 文件及空目录

**教训标签**：`#lesson: reader_interaction` `#lesson: book_structure` `#lesson: git_hygiene`

---

## 2026-06-23 全站内容去重（单章内 + 跨章节）

### 触发问题
用户读到窃符救赵，发现单篇文章内大量重复（讲事情已叙述的情节，讲人物/讲背景/讲道理/问道悟道又重述一遍）；前后连续章节也存在大篇幅重复（如长平之战在纸上谈兵与窃符救赵两章都详述）。重复影响阅读体验，要求可简略提起或注明在哪些章节出现过，启用多 Agent 专家团优化。

### 多 Agent 执行（2 调查 Agent + 6 编辑 Agent 并行）
- 调查 Agent 1：扫描资治通鉴 20 篇，定位单章内重复（讲事情情节在后续模块重述）+ 跨章节重复簇（完璧归赵/渑池之会/负荆请罪三连章、纸上谈兵/窃符救赵长平之战簇、张仪连横/苏秦合纵马王堆帛书簇、沙丘之谋/大泽乡起义二世昏庸簇、大泽乡起义/破釜沉舟项羽起兵簇、韩信拜将/垓下之围/鸟尽弓藏韩信三章簇）
- 调查 Agent 2：扫描明纪/三国/唐纪，定位张居正改革 vs 死后清算、万历怠政/三大征/萨尔浒之战财政判语簇、东林党争/魏忠贤专权杨涟左光斗簇、诸葛亮治蜀/北伐中原马谡蜀汉国力簇、贞观开局/纳谏与用人魏征隋亡教训簇
- 编辑 Agent 1-6：按"主场章节详述、客场章节简略提及+交叉引用"策略并行改写

### 去重策略（已沉淀为可复用模式）
1. **单章内去重**：讲事情已叙述的情节，讲人物/讲背景/讲道理/问道悟道不再重述，改用"（情节详见讲事情）"交叉引用；同一名家引言单篇只全文出现一次，他处用"曾说过的那句话"或概述。
2. **跨章节去重**：相邻章节共享背景只在"主场章节"详述，客场章节用"（详见《某某》）"简略带过。主场判定原则——该背景/人物/典故在哪章是核心就归哪章主场（如长平之战归纸上谈兵、信陵君归窃符救赵、魏征登场归贞观开局）。
3. **五段结构不可破坏**：去重只精简重复内容并加交叉引用，不删除模块、不破坏 rules.md 五段结构。

### 关键教训
- **主场/客场分配是去重的关键**：跨章节重复不能两边都删（会丢失信息），也不能两边都留（重复依旧）。必须先判定主场（核心章节详述），客场（关联章节简略+交叉引用），才能既去重又保完整。
- **单章内交叉引用用"（详见讲事情）"，跨章用"（详见《某某》）"**：两种引用格式区分单章内与跨章，读者一眼能分辨是同篇内还是跨篇引用。
- **名家引言单篇只全文一次**：同一引言（如赵奢"兵，死地也，而括易言之"）在单篇内多处引用时，只在首次全文引用，他处用概述或"曾说过的话"，避免同一句古文反复出现。
- **去重不得删除章节独有内容**：每章必须保留独有史料（如窃符救赵保留侯嬴下交毛公薛公、纸上谈兵保留赵奢阏与之战），只去重复部分，否则会损失信息密度。

### 测试覆盖
check_chapter_order.py 校验通过；全量 pytest 109 项通过；quality.py 资治通鉴 20/20 + 明纪三国唐纪 100/100 全 PASS；build_site.py 静态站点生成成功。

**教训标签**：`#lesson: content_quality` `#lesson: book_structure`

---

## 2026-06-23 非资治通鉴书籍阶段化重构 + 全站排序修复

### 触发问题
用户发现明纪排序"全乱"，且除资治通鉴外其他书目录拆分过细（一章一事件），要求按历史阶段合并大章节，阶段内按时间排小标题。

### 多 Agent 分析结果（历史专家 Agent 设计阶段映射）
- 根因1：唐纪/宋纪/明纪/史记未配置 `BOOK_CATEGORY_ORDER`，章节按字符串序排（明纪一<明纪七<明纪三<明纪三十）
- 根因2：非资治通鉴 7 本书（三国/史记/唐纪/宋纪/明纪/孔子传/论语）原为"一章一事件"结构，目录层级冗余
- 方案：7 本书按历史阶段重构为多事件大章节（三国6阶段/史记7阶段/唐纪6阶段/宋纪6阶段/明纪8阶段/孔子传6阶段/论语7阶段），阶段内事件按时间序排

### 修复
1. `src/utils/sorting.py`：BOOK_CATEGORY_ORDER 补唐纪/宋纪/明纪配置；`sort_notes_tree` chapter 排序改为优先用 `chapter_sort` 字段（阶段历史顺序），无则回退 `chapter_sort_key`（朝代纪号）
2. `scripts/migrate_stages.py`（新增）：一次性迁移脚本，STAGE_MAP 定义 7 本书阶段映射，重命名文件 + 更新 frontmatter（chapter/sort/chapter_sort 三字段）
3. `scripts/build_site.py` + `src/web/app.py`：event 节点注入 chapter_sort，chapter 节点取首个事件的 chapter_sort，两端同步
4. `tests/test_sorting.py`：更新史记配置测试，新增唐纪/宋纪/明纪测试

### 关键教训
- **双排序字段设计**：`chapter_sort`（阶段在书内的历史顺序，跨章）+ `sort`（事件在阶段内的时间顺序，章内）。两者职责分离，避免单字段既表达跨章又表达章内导致冲突。
- **迁移脚本必须幂等**：migrate_stages.py 以 event 名为 key 查 STAGE_MAP，重命名文件 + 覆写 frontmatter，可重复运行。前几次运行因 tuple 解包顺序 bug 产生错误 sort 值，第 5 次修复后正确——幂等性让重跑成本极低。
- **tuple 解包顺序 bug 是高频低级错误**：`build_event_to_stage` 返回 `(stage_name, chapter_sort, event_sort)`，但调用方写成 `new_chapter, sort_val, chapter_sort = ...` 解包，2/3 位互换导致全章事件 sort 值都等于 chapter_sort。教训：多字段 tuple 返回时优先用 dataclass/namedtuple 或 dict，避免位置解包。
- **sort_notes_tree 两个消费者必须同步**：`build_site.py`（静态站点）和 `src/web/app.py`（Flask API）都调用 sort_notes_tree，但 chapter_sort 字段的注入逻辑需各自实现（build_site 从 frontmatter 解析，app.py 从 content 正则解析），两端解析逻辑必须一致。
- **阶段划分以原书叙事时间线为准**：明纪 8 阶段（元末群雄→洪武之治→永乐盛世→土木之变→成弘正之治→嘉靖隆庆→万历怠政→明亡清军入关）严格按明代历史时间序，不按重要性排序。

### 测试覆盖
全量 pytest 109 项通过；check_chapter_order.py 校验全站通过；7 本书 234 个文件迁移成功，阶段排序与事件排序全部正确。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-23 全站章内事件时间排序修正 + 校验机制固化

### 触发问题
用户发现周纪五"窃符救赵"应在"纸上谈兵"后（当前在前），判断同章节内小标题排序还有类似问题，要求逐本逐章检查并固化检查机制到文档。

### 多 Agent 考证结果（历史专家 Agent）
- 周纪三：苏秦合纵(1)→张仪连横(2)（原张仪在前，错）
- 周纪五：纸上谈兵(1)→窃符救赵(2)（原窃符在前，错，用户指出）
- 秦纪二：沙丘之谋(1)→大泽乡起义(2)（原大泽乡在前，错）
- 汉纪一：鸿门宴(1)→韩信拜将(2)（原韩信在前，错）
- 周纪二、秦纪一：原顺序已对，补 sort 字段保持一致

### 修复
12 篇笔记 frontmatter 加 sort 字段（4 章修正 + 2 章补全 + 周纪四已修）。

### 校验机制固化（文档专家 Agent 分析落点，构建与校验分离原则）
- 新建 `scripts/check_chapter_order.py`：跨文件校验同章 sort 单调递增、无重复、多事件章节不缺 sort
- `.trae/rules/rules.md` 新增"§五 frontmatter 与排序"小节（写作要求层），sync_rules 同步到 RULES.md
- `prompts/editor.md` frontmatter 模板加 `sort: {sort}` 字段（生成层）
- `.trae/checklists/dev-checklist.md` 加"涉及 output/ 改动须跑 check_chapter_order.py"检查项
- `.trae/skills/dev-selfcheck/SKILL.md` 加"笔记排序检查"小节（自检触发入口）
- `README.md` 本地预览流程登记校验步骤
- 新增 `tests/test_check_chapter_order.py` 15 项测试

### 关键教训
- **构建与校验分离**：校验脚本（check_chapter_order.py）独立于构建脚本（build_site.py），校验失败不阻断站点构建，CI 部署不被阻断。
- **单篇校验 vs 跨文件校验**：quality.py 保持单篇 content 输入定位，不塞跨文件校验（章内排序需遍历同 chapter 多文件）；跨文件校验用独立脚本。
- **sort 字段是人工事后补的**：`src/utils/markdown.py` 的 build_frontmatter 不生成 sort，`prompts/editor.md` 模板原本无 sort。本次把 sort 加入 editor 模板，未来生成的笔记会带 sort，但 LLM 填的 sort 值仍需校验脚本兜底。
- **历史时间排序以原书叙事为准**：苏秦张仪年代有学术争议（马王堆帛书），但章内排序以《资治通鉴》叙事顺序为准，不擅自用现代考证推翻（rules.md §五已写明）。

### 测试覆盖
全量 pytest 108 项通过（含新增 15 项 check_chapter_order 测试）；check_chapter_order.py 校验全站通过；7 个多事件章节排序全部正确。

**教训标签**：`#lesson: book_structure`

---

## 2026-06-23 阅读器沉浸式全屏与点击翻页（番茄小说式交互）

### 触发问题
用户在吸底栏修复基础上，要求新增沉浸式全屏阅读模式，并模仿番茄小说 APP 的点击翻页交互（左侧上一页、右侧下一页、中间唤出/隐藏菜单）。

### 多 Agent 分析要点
1. **吸底栏定位的本质**：延续此前结论，移动端吸底必须 `position:fixed` + `env(safe-area-inset-bottom)`，滚动区补 `padding-bottom`，不依赖 body flex 链路。
2. **全屏实现策略**：优先使用 HTML5 Fullscreen API（`requestFullscreen`/`exitFullscreen`）加 vendor 前缀兼容；但无头/iframe 环境可能因安全策略无法真正进入系统全屏，因此 CSS 沉浸式状态（`.immersive-mode`）必须独立生效，不能依赖 fullscreenchange。
3. **点击翻页区域划分**：阅读区按 33% / 34% / 33% 分为左/中/右三区（`.tap-zone.prev/menu/next`），中央区切换 `ui-hidden`，两侧区按可视高度翻页，到底/到顶时自动切换章节。
4. **触控层与内容层分离**：新增 `.reader-content` 容器，把正文渲染目标从 `.reader` 改为 `.reader-content`，避免 `innerHTML` 覆盖覆盖在上面的 `.reader-tap-zones`。
5. **层级管理**：沉浸式模式下 `.reader-view` 固定全屏（`z-index:50`）；UI 唤出时 `.toolbar`/`.bottom-bar` 提升为 `z-index:70`，确保按钮可点而不被触控层拦截。

### 修复与实现
- `index.html`：viewport 加 `viewport-fit=cover`；toolbar 与底栏各加一个「⛶」全屏按钮；`.reader` 内新增 `.reader-tap-zones` 三区触控层，正文移入 `.reader-content`。
- `style.css`：
  - 底栏 `position:fixed; bottom:0; padding-bottom:env(safe-area-inset-bottom)`；
  - 移动端 `.reader` 底部补 `calc(50px + env(safe-area-inset-bottom))`；
  - 新增 `.immersive-mode`、三区触控层、翻页动画 `@keyframes pageTurnNext/Prev`；
  - 沉浸式模式下 `ui-hidden` 才隐藏 UI，非 `ui-hidden` 时 toolbar/bottom-bar `z-index:70`。
- `app.js`：
  - 封装 `requestFullscreen`/`exitFullscreen` 多 vendor 兼容；
  - `enterImmersiveMode`/`exitImmersiveMode`/`toggleImmersiveMode`；
  - `goPrevPage`/`goNextPage` + `triggerPageTurnAnimation`；
  - `handleTapZone` 分发三区点击，并排除 `a/button/input/textarea/select/.modal/.settings-panel/.sidebar`；
  - 所有正文 `innerHTML` 写入 `elements.readerContent`，保护触控层。
- `tests/test_web_reader.py`：新增 10 项测试，断言 fixed 定位、安全区、transform 隐藏、触控层 HTML、Fullscreen API、翻页函数、可交互元素排除等。

### 关键教训
- 只要 JS 用 `parent.innerHTML = ...` 重绘，任何叠加在 `parent` 上的浮层/触控层都会被销毁。后续若再添加覆盖层，必须把它与动态内容分开放置在不同父级，或让 JS 只更新指定的内容容器。
- 沉浸式/全屏不能只靠 Fullscreen API，必须有一套 CSS 状态兜底；否则在 iframe、安全策略限制或用户按 ESC 后界面会处于不一致状态。
- 固定全屏层（`position:fixed; z-index:50`）之上的 UI 控件，需要显式提升 `z-index` 并验证点击不被下层触控层拦截；仅凭 DOM 顺序容易遗漏。
- 三区触控交互要排除可交互元素，否则链接、按钮、设置面板会被误拦截。

### 测试与验证
- `pytest` 全量 119 项通过；`tests/test_web_reader.py` 10 项全部通过。
- 浏览器自动化验证：移动端样式下底栏固定吸底、ESC 退出、左右翻页、中间唤出/隐藏 UI、UI 显示时按钮可点均正常。

**教训标签**：`#lesson: reader_interaction`

---

## 2026-06-23 手机端吸底栏专项优化（魔搭空间版本）

### 触发问题
用户反馈"上一章 目录 设置 下一章"吸底栏在手机端仍有问题。魔搭空间版本 = site/ 主版本（经 `.github/workflows/deploy-modelscope.yml` 部署到 ModelScope Studio，用 iframe/WebView 嵌入）。

### 多 Agent 分析根因（前端专家视角）
1. **魔搭 iframe 内 body height:100% 塌缩**（最严重）：原吸底靠 `body{height:100%;display:flex;flex-direction:column}` + `.bottom-bar{flex-shrink:0}`，iframe 高度异常时整条 flex 链塌缩，底栏失效。本地无法复现。
2. **iPhone safe-area 双重缺失**：viewport 无 `viewport-fit=cover` + `.bottom-bar` 无 `padding-bottom:env(safe-area-inset-bottom)`，home indicator 遮挡按钮且点击被系统拦截。
3. **Chrome 安卓动态地址栏抖动**：body 100% 随地址栏伸缩变化，底栏位置抖动。
4. **display 硬切**：`body.ui-hidden .bottom-bar{display:none}` 瞬变无过渡，且 flex 链重算导致阅读区跳变。
5. **transition:transform 死代码**：声明了过渡但 JS 从未修改 transform。

### 修复方案
放弃 flex 吸底，改 `position:fixed` + safe-area（移动端吸底导航工业标准，不依赖 body 高度链路）。
- `index.html` viewport 加 `viewport-fit=cover`
- `.bottom-bar` 改 `position:fixed; bottom:0; padding-bottom:env(safe-area-inset-bottom)`
- 移动端 `.reader` 加 `padding-bottom:calc(50px + env(safe-area-inset-bottom))` 防遮挡
- `body.ui-hidden .bottom-bar` 改 `transform:translateY(100%)`（滑出动画，复活死代码 transition）
- 首页仍 `display:none`（不占位）

### 关键教训
- 移动端吸底栏**不能依赖 body flex 高度链路**——iframe 嵌入环境（魔搭/飞书/企微）和动态地址栏都会让 `height:100%` 塌缩/抖动。`position:fixed` 脱离文档流，不受 body 高度影响，是唯一可靠方案。
- `100dvh` 在 iframe 内参考的仍是 iframe 高度而非可视高度，救不了 flex 方案。
- iPhone 全面屏必须 `viewport-fit=cover` + `env(safe-area-inset-bottom)` 双管齐下，缺一个则 safe-area 返回 0。
- fixed 元素脱离 flex 链后，滚动区（`.reader`）必须补 `padding-bottom` 让出底栏高度，否则内容被遮挡。
- 显隐切换用 `transform` 而非 `display:none`，可配合 `transition` 实现平滑动画，且不触发 flex 链重算。

**教训标签**：`#lesson: reader_interaction`

---

## 2026-06-23 GitHub Pages 部署失败修复（.nojekyll 跳过 Jekyll）

### 触发问题
用户发现最近多次 push 后 GitHub Pages 部署均失败（错误日志显示 Jekyll 在渲染 `output/` 下的 Markdown 文件时异常），而魔搭空间部署始终成功。

### 多 Agent 定位结果
- **Workflow 差异**：GitHub Pages workflow（`.github/workflows/pages.yml`）将 `site/` 作为 artifact 上传给 GitHub Pages；魔搭 workflow（`.github/workflows/deploy-modelscope.yml`）将 `site/` 内容推送到 ModelScope Studio 作为静态服务。
- **构建差异**：GitHub Pages 默认会对 artifact 执行 Jekyll 构建，`site/notes/` 下复制了大量 Markdown，Jekyll 3.9.x（GitHub Pages 固定版本）渲染时失败；魔搭空间不经过 Jekyll，直接 serve 静态文件，因此成功。
- **Markdown 文件本身**：frontmatter 合法、无 Liquid 冲突字符、无非法命名，问题不在内容。
- **本地复现**：本地 Jekyll 4.4.1 构建 `site/` 成功，无法 1:1 复现 GitHub Pages 的 Jekyll 3.9.x 环境；但确认 `.nojekyll` 文件在 artifact 根目录可让 GitHub Pages 跳过 Jekyll。

### 修复方案
1. `scripts/build_site.py` 在生成 `site/` 后，在 `site/` 根目录写入空文件 `.nojekyll`。
2. `tests/test_build_site.py` 新增 `test_build_site_creates_nojekyll` 测试，TDD 保证 `.nojekyll` 必然生成。
3. 清理本地 Jekyll 测试遗留的 `site/.jekyll-cache/`。

### 关键教训
- **GitHub Pages 上传的 artifact 会被 Jekyll 二次处理**：即使站点已由 Python 脚本预构建，只要 artifact 根目录没有 `.nojekyll`，GitHub Pages 就会用 Jekyll 重新构建。预构建静态站点必须在 artifact 根目录显式声明 `.nojekyll`。
- `.nojekyll` 的位置必须对应上传路径：workflow 上传 `path: site`，则 `.nojekyll` 必须生成在 `site/.nojekyll`，仓库根目录的 `.nojekyll` 对 GitHub Pages 无效。
- **Jekyll 本身不会把 `.nojekyll` 复制到 `_site/`**：`.nojekyll` 不是 Jekyll 配置，而是 GitHub Pages 部署层的跳过标记；本地 Jekyll 构建时会忽略它，但不影响 GitHub Pages 识别。
- **测试驱动修复**：新增测试先失败、再改实现、再全量回归，能避免"修完忘记验证"的问题；构建脚本的产物约束（如 `.nojekyll`、index.json、notes 目录）适合用单元测试兜底。
- **魔搭空间不受影响**：魔搭部署同样调用 `build_site.py`，`site/.nojekyll` 是空文件，不破坏魔搭侧的文件校验（index.html/css/style.css/js/app.js/data/index.json 均仍在）。

### 测试覆盖
`tests/test_build_site.py` 新增 1 项，全量 23 项通过；本地 `python scripts/build_site.py --output output --site site` 验证 `site/.nojekyll` 生成且 `site/data/index.json` 有效；Jekyll 本地构建 `site/` 成功。

### 配套改动
`.gitignore` 新增 `site/.nojekyll`，避免本地构建生成的该文件被误提交；实际部署时由 CI 中的 `build_site.py` 动态生成。

**教训标签**：`#lesson: deployment`

---

## 2026-06-23 AI 大模型学习专栏生成

### 任务概述
基于 xmind 知识图谱（环境不可访问，改用网络研究）+ 菜鸟教程 + 吴恩达课程，生成面向普通人与程序员的 AI 学习专栏。最终产出 36 章正文 + 1 附录，总计约 25 万字符。

### 执行流程
1. **专家团评审**：启动 3 个并行 subagent（架构师/测试/规则）评审章节方案，汇总意见后调整（补多模态章、模块5扩到4章、加端到端实战、合并模型选型、速查降附录、理论类加自测三问、字数分档）。
2. **并行生成**：4 轮 × 5 个 subagent，每 subagent 写 2 章，共 19 个 subagent 调用完成 36 章 + 附录。
3. **自检**：37 个文件全部含 YAML front matter，36 个含前置知识声明，总字符数 249,046。

### 新共性问题
1. **大规模内容并行生成的风格一致性问题**：19 个 subagent 各自生成，虽共享同一份写作规范文件（.cache/ai_course_style.md），但各章在细节风格上仍有细微差异（如标题格式、引用位置）。
2. **rules.md 适用范围错位**：项目现有 rules.md 是为"古籍讲书笔记"设计的，AI 专栏采用了自定义结构（理论类/应用类），存在规则真空。
3. **xmind 文件环境隔离**：用户本地路径的 xmind 文件在沙箱环境不可访问，需降级为网络研究 + 知识库。

### 规则更新建议
- 建议新增 `.trae/rules/ai-course.md`，将本次的写作规范（.cache/ai_course_style.md）固化为正式规则文件，覆盖：语言风格、理论类/应用类章节结构、字数分档、引用规范、质量保障条款。
- 在 rules.md 中明确声明其适用范围仅限"古籍讲书笔记"，AI 等其他类型内容采用各自专用规则。

### checklist 更新
- 无需更新 dev-checklist.md（本次为内容生成，非代码开发）。

### 可复用资产
- `.cache/ai_course_style.md`：AI 专栏写作规范，可作为后续同类任务的模板。
- `.cache/ai_course_plan.md`：章节方案模板，含模块划分、字数预估、文件命名规范。
- 专家团评审模式（3 subagent 并行评审）可复用于其他方案评估场景。

**教训标签**：`#lesson: ai_course`

---

## 方案 C 手册（教训入 checklist）

当"教训计数表"中某 `#lesson` slug 出现 ≥3 次且 `已入 checklist = no` 时，执行以下 5 步：

1. 在 `.trae/checklists/dev-checklist.md` 新增一条检查项（≤2 行，可执行，带验证命令）
2. 在对应 Skill（如 `git-merge-guardian/SKILL.md` 或 `dev-selfcheck/SKILL.md`）的执行步骤中引用此检查项
3. 在 loop_log.md 对应记录的底部把 `已入checklist` 改为 `yes`（在 #lesson 标签行下方加一行 `已入checklist: yes`）
4. 在"教训计数表"中把对应行的"已入 checklist"列改为 `yes`
5. 跑一遍 `bash tests/run_regression_suite.sh` 确认 checklist 新增不破坏现有流程

### slug 主题表（受控，新增需在此登记）

- `git_hygiene`：推送/合并/冲突标记/分支治理/commit 覆盖
- `reader_interaction`：阅读器/沉浸/翻页/吸底栏
- `content_quality`：质检规则/AI 套路句/现代术语
- `book_structure`：排序/校验/命名/去重/双源同步
- `deployment`：GitHub Pages/魔搭/.nojekyll/SW 缓存
- `soul_injection`：灵魂注入/章回体标题/总编Agent
- `ai_course`：AI 专栏生成/批量并行

---

## plan-review skill 硬阻塞修复 + dispatching-parallel-agents 原生化（2026-06-27，BUG-031）

### 背景

用户反馈：每次调用 `plan-review` skill 都硬阻塞在 `.env` 缺失 + `langgraph` 未安装，评审跑不起来。用户要求"会话内启用多个 subagent 并行执行+汇总"，并指出 plan-review skill 来自 superpowers（核实后：plan-review 是项目自建，superpowers 里相关的是 `dispatching-parallel-agents`）。

### 核心改动

1. **plan-review SKILL.md v1.0.0 → v2.0.0**：主路径从"路径 B（langgraph Python 引擎，环境缺失硬阻塞）"改为"路径 C（会话内 Task 工具启动 3 个 `general_purpose_task` subagent 并行评审：架构师/测试/规则，主 Agent 汇总）"。路径 B 降级为可选增强，环境缺失时不硬阻塞自动走主路径。删除"错误处理"里 `scripts/review_plan.py 不存在` 的误导条目（文件实际存在，commit `bfd342c` 添加）。

2. **新增 `.trae/skills/dispatching-parallel-agents/SKILL.md`**：原生自 `obra/superpowers`（MIT），适配 Trae Task 工具（`subagent_type: search / general_purpose_task`）。保留核心纪律：同一响应多 Task 调用 = 并行、subagent 指令必须自包含（subagent 看不到主会话）、返回后必须检查冲突 + 跑全测。作为 plan-review 并行评审的调度底座。

3. **`scripts/review_plan.py` 加固**：延迟导入 `langgraph` 处加 `try/except ImportError`，输出友好提示（含主路径替代方案）而非裸 traceback。

4. **`dev-workflow.md §零` 更新**：原"可行路径只有两条（A 串行 / B langgraph）"改为三条——路径 C（Task 工具，主路径）/ 路径 A（串行，降级）/ 路径 B（langgraph，可选增强）。加"能力边界澄清"脚注：Skill 文件本身不调度 sub-agents，但主 Agent 经 Skill 引导可用 Task 工具，不违反 §零。

5. **`docs/reviews/soul-injection-spec-20260626.md` 更新**：原判定"`dispatching-parallel-agents` 仅参考不 push（依赖原生 subagent 调度，Trae 做不到）"已过时——Task 工具支持 `subagent_type`，会话内并行是原生能力。加"2026-06-27 复核更新"注。

6. **测试**：新增 `tests/test_plan_review_skill.py` 19 项（18 文档契约 + 1 review_plan.py 降级行为测试）；给 `tests/test_plan_review.py` / `test_workflow.py` / `test_workflow_e2e.py` / `test_workflow_output_dir.py` 加 `pytest.importorskip("langgraph")`，避免无 langgraph 时收集期 ImportError 中断 pytest；修 `test_workflow_archetype.py` 的全局 fake langgraph mock 加 `_FAKE=True` 自标识，让 `test_workflow_e2e.py` 检测到 fake 时 skip。`run_regression_suite.sh` 加第 11 步（6 项 plan-review skill 路径契约断言）。

7. **dogfood 验证**：用新主路径（同一响应发 3 个 Task 调用：架构师/测试/规则 subagent）评审本次修复计划本身。三 subagent 并行返回，输出三视角评审报告，暴露 5 个问题（R1-R5），逐条修复后三件套全绿。证明不再硬阻塞。

### 三件套验证

- `pytest`：345 passed, 19 skipped（无 langgraph 环境下，路径 B 测试优雅 skip）
- `check_book_structure.py --strict`：0 问题
- `run_regression_suite.sh`：24/24 通过

### 沉淀

1. **Skill 能力边界 ≠ Trae 原生工具能力**。dev-workflow.md §零"Skill 不能调度 sub-agents"指 Skill **文件本身**（它是 prompt，不主动调度）；但主 Agent 经 Skill 引导后调用 `Task` 工具（`subagent_type`）启动 subagent 是 Trae 原生能力，不违反 §零。这条区分此前没写清，导致 plan-review v1.0.0 只设计了路径 B，错过路径 C。今后设计 Skill 时要问："这步是 Skill 文件自己做，还是引导主 Agent 用原生工具做？"

2. **技术判定需随工具能力更新而复核**。obra/superpowers 适配时（2026-06-26）判定 `dispatching-parallel-agents`"依赖原生 subagent 调度，Trae 做不到"——当时可能 Task 工具未暴露 `subagent_type`，或评估者未注意到。今日复核发现 Task 工具支持 `subagent_type`，判定过时。教训：外部能力判定有保质期，依赖"工具不支持"的结论要定期复核。

3. **dogfood 是 skill 修复的最强验证**。本次用修复后的新主路径评审修复计划本身，3 个 subagent 真并行返回评审意见，既证明不再硬阻塞，又暴露了 5 个计划缺陷（R1-R5）。比单纯跑测试更有效——测试只能验证文档契约，dogfood 验证了实际并行执行 + 汇总流程。

4. **全局 sys.modules mock 必须自标识**。`test_workflow_archetype.py` 的 `_ensure_langgraph_available()` 在模块顶部往 `sys.modules` 注入 fake langgraph，污染整个 pytest 进程，让后续测试的 `pytest.importorskip("langgraph")` 失效。修法：给 fake 模块加 `_FAKE=True` 标记，依赖真实 langgraph 的测试（e2e）检测后 skip。教训：模块级 sys.modules 注入要有自标识 + 作用域控制，否则会污染其他测试。

5. **依赖外部环境的 skill 必须有降级路径**。plan-review v1.0.0 的硬阻塞根因是只设计了路径 B，没考虑 `.env`/`langgraph` 缺失。今后任何依赖外部环境的 skill，主路径必须优先选无外部依赖的方案（如 Task 工具），环境依赖方案降为可选增强。

### 规则/checklist/Skill 更新

- `.trae/rules/dev-workflow.md §零`：路径列表 A/B → C(主)/A(降级)/B(可选)，加能力边界澄清脚注
- `.trae/checklists/dev-checklist.md §六`：第 59 行"真并行改触发 Python 脚本（路径 B）"→"优先引导主 Agent 用 Task 工具（路径 C 主路径）；或触发 Python 脚本（路径 B 可选增强）"
- `.trae/skills/plan-review/SKILL.md`：v1.0.0 → v2.0.0
- `.trae/skills/dispatching-parallel-agents/SKILL.md`：新增
- `tests/bug_regression_list.md`：追加 BUG-031
- `README.md`：skills 目录树补登 plan-review + dispatching-parallel-agents

### 待办（下一 Loop）

1. dispatching-parallel-agents SKILL.md 篇幅偏大（~145 行），后续视使用反馈精简"常见错误表/验证清单"
2. superpowers 其余 6 个"仅参考"技能是否随 Task 工具能力复核（`subagent-driven-development` 等）
3. plan-review 路径 B（langgraph）若长期不用，考虑是否废弃以减少维护面

---

## 首页圣贤堂入口优化 + 内置 YAML 解析器嵌套结构支持（2026-06-27）

### 触发问题

1. 用户反馈首页 Hero 区域在手机上占比过大，"深读一部经典，看见千年人心" 与副标题都折成两行，有效信息被挤到下方。
2. 「圣贤堂」导航按钮不够醒目，需要 icon、背景色、背景图。
3. 跑 `pytest` 时发现 `tests/test_workflow_archetype.py` 9 项失败：沙箱未安装 PyYAML，调用内置简单 YAML 解析器时把 `config.yaml` 中的 `section_templates`（dict 内含 list）解析成了平铺列表。

### 修复方案

1. **Hero 区域瘦身**：
   - 移动端（≤480px）padding 从 `40px 24px 32px` 降到 `24px 16px 18px`。
   - `.hero-title` 降到 18px（≤360px 再降到 16px），加 `white-space: nowrap`，确保 13 字标题单行。
   - `.hero-subtitle` 降到 11px（≤360px 降到 10px），加 `white-space: nowrap`，确保 24 字副标题单行。
   - `.hero-stats` 间距与字号同步缩小。

2. **圣贤堂按钮视觉强化**：
   - 保留「圣」字圆形 icon。
   - 背景改为双层：底层渐变（红褐→金），上层 repeating SVG 祥云纹理（inline data URI，无外部依赖）。
   - 边框、阴影、hover 态统一提升对比度。

3. **简单 YAML 解析器增强**：
   - `_parse_simple_yaml()` 新增对「dict 内含 list」的支持（indent 2 识别 dict key，indent 4 识别 list item）。
   - 抽出 `_coerce_scalar()` 统一处理 bool/int/quoted string，减少重复。
   - 保证 PyYAML 缺失时 `section_templates` 仍能正确解析为 `{narrative: [...], modern: [...], knowledge: [...]}`。

### 关键教训

- **移动端 Hero 要按"有效信息优先"设计**：大标题在窄屏上折行会浪费首屏。用 `white-space: nowrap` 强制单行时，必须同步降字号并测最小屏宽（360px）。
- **装饰性背景图优先用 inline SVG data URI**：避免外部图片请求、CORS、部署路径问题，同时体积小、可随 CSS 缓存。
- **"非本次引入"的测试失败也要修**：`pytest` 全绿是合并/推送的硬门槛。本次失败根因是环境差异暴露了解析器鲁棒性缺口，修好它让项目在无 PyYAML 环境也能正常启动测试。
- **内置 fallback 解析器必须覆盖真实配置结构**：`config.yaml` 早就用了 dict-nested-list，但简单解析器只支持顶层 list/dict，二者长期不匹配，只是被 PyYAML 掩盖了。

### 测试覆盖

- `python scripts/check_book_structure.py --output output --strict`：0 问题
- `pytest -q`：369 passed, 19 skipped
- `bash tests/run_regression_suite.sh`：25/25 通过

**教训标签**：`#lesson: reader_interaction`

**教训标签**：`#lesson: deployment`

## 高考志愿填报前置认知科普专栏 + 多 agent 打分闭环（2026-06-27）

### 触发问题

用户要做"2026高考志愿填报前置认知科普站"——静态网页 + Markdown 专栏双交付，资料须 2026 最新权威源，最终启用多 agent 智能打分且总分≥95。涉及高考学生报名，置信度要求极高。

### 执行方案（路径 C：主 Agent + Task 工具并行）

1. **写计划 skill 重述需求**：把"还没想好帮忙设计"的模糊需求转成核心目标（前置认知科普站，不做分数匹配，与阳光志愿错位）+ 五要素计划，等用户确认 3 个关键决策（定位/测评深度/站点承载）后执行。
2. **架构确认**：Grep app.js 确认已支持 `?book=&chapter=` URL 参数深跳转（L543/L734）；Grep check_book_structure.py 确认不强校验 category 枚举；category 用「升学」新类目，archetype 用 modern 走质检白名单（避免 MBTI/RIASEC 等术语误报，参考 L233 教训）。
3. **3 调研 subagent 并行**：① MBTI 16型专业适配 ② 2026新增38专业+十五五产业 ③ 名师方法论+书籍课程。每份调研报告自带置信度自评（7-8分）和"待核实"标注。
4. **4 撰写 subagent 并行**：A 写 1-4章、B 写 5-8章、C 写 9-11章、D 搭落地页。引用规范统一为 [源编号] 体系对应参考资料.md。
5. **3 评审 subagent 并行**：真实性核查 / 可读性与结构 / 引用与置信度，五维度打分。

### 关键 bug 与修复

1. **落地页 book 参数错用 title 而非目录名**：subagent D 用 `book=2026高考志愿填报前置认知`（_meta.yaml title），但 app.js L546 `bookId = params.get('book')`，L551 `chapterPath = bookId + '/' + chapter + '.md'`，bookId 必须是 notes 目录名 `高考志愿填报前置认知`（无"2026"前缀）。全部 12 个链接 fallback 到第一章。修复：Edit 全量替换 book 参数。**教训：落地页深跳转的 book 参数必须等于 build_site 生成的 notes 目录名（= output 子目录名），不是 _meta.yaml 的 title 字段。**
2. **三轮打分-修复闭环**：72→86→93→95。
   - 第一轮 72 分：真实性 28/可读性 16/顺序 9/引用 7/置信度 12。问题集中在源编号归类错误、sort6 与 sort8 大面积重复、跨章呼应断裂。
   - 第二轮 86 分：修复 P0 源编号归类（PSYCH-3 改 1991 NRC、INDUSTRY-6→OFFICIAL-8、位次浮动 OFFICIAL-3→EXPERT-2）+ 结构重写（开篇 7 部分、sort6 去重、晨雾六步法补齐第六步）。差 9 分。
   - 第三轮 93 分：修复 6 项残留（任务书内部话术清理、欧阳文邦身份同步、开篇+选专业引用归类、84.7%/湖南投档线补免责）。差 2 分。
   - 第四轮 95 分达标：P1 补 5 处具体数字"待官方核实"标注 + P2 未来产业表 2 项交叉来源。

### 沉淀方法论

1. **多 agent 打分闭环比单 agent 自检更严**：3 个评审 subagent 并行从不同维度打分，互相不干扰，问题暴露更彻底。72→95 的 23 分差距全部来自评审发现的具体问题，而非凭空提分。
2. **高考报名场景的置信度处理范式**：① 关键政策以官方为准（OFFICIAL-x）② 名师观点标"经验性建议非官方规定"③ 存疑数据标"行业统计待官方核实"④ 名人引言区分原话与引申 ⑤ MBTI 科学性争议诚实交代（1991 NRC 评估、重测信度约 50%、巴纳姆效应）⑥ 免责声明覆盖官方/天价服务/AI 工具三方面。这套范式可复用到所有"高置信度要求"的科普专栏。
3. **"任务书"等内部话术不能进正文**：调研 subagent 写的"任务书原写 XXX"是给主编看的内部话术，面向读者的专栏正文必须改为"早期公开口径曾载 XXX"等中性表达。多 agent 并行撰写时，主编整合阶段必须扫描这类内部话术。
4. **源编号体系必须跨文件同步**：参考资料.md 改了 [PSYCH-3] 描述，章节正文和免责声明都要同步；欧阳文邦头衔在参考资料.md 改了，资料汇编章的名师对照表也要同步。单点修改≠全局一致，整合阶段必须 Grep 同名实体跨文件核验。

### 涉及文件

- `output/高考志愿填报前置认知/`：_meta.yaml + 参考资料.md + 11 章正文 + 3 份 _research_*.md 调研稿（build_site 自动跳过 _ 开头文件）
- `src/web/static-site/gaokao.html`：落地页，12 模块卡片跳转阅读器
- `scripts/build_site.py`：L209 新增 gaokao.html 到 assets 同步列表
- `docs/loop_log.md`：本条沉淀

### 测试覆盖

- `python scripts/build_site.py`：站点生成成功，12 篇笔记入库
- 落地页 12 个跳转链接 book/chapter 参数与 index.json 路径精确匹配
- 浏览器打开 gaokao.html 无错误
- 多 agent 终审打分 95/100 达标

**教训标签**：`#lesson: content_quality` `#lesson: book_structure`

## 高考志愿填报前置认知 Phase 2 升级 - 精准100/质量98/落地99三终审闭环（2026-06-28）

### 触发问题

Phase 1 达 95 分后，用户要求 Phase 2 升级到"精准度100/质量98/可落地99"，且要：①结合十五五+就业情况给深层建议 ②提取机构/老师引导心法与照抄方法论 ③教获取行业一手信息 ④压到"半小时到1小时读完" ⑤同时是报考指南和就业指南。

### 执行方案（路径 C 三轮并行闭环）

1. **三轮并行终审**：精准度100/质量98/落地99 三个 subagent 并行评审，分别得 80/85/81 分，暴露 5 项精准度 P1 + 4 项质量必修复 + 9 项落地 P0。
2. **三轮并行修复**（按文件分工避免冲突）：
   - subagent A：精准度 P1（5项）+ 开篇路线图重写 + 结尾回扣三问 + 跨章去重
   - subagent B：照抄即用章 9 项 P0（决策表补概率算法+3列/24小时清单补3项/双漏斗补查询入口+阈值+消歧/讨论清单补2问+时点）
   - subagent C：引导心法+一手信息+落地页（机构SOP时间节点/家长分工/31省入口/实习跟岗/落地页导航+NEW角标+独立色调）
3. **整体压缩**：11 个文件压缩，总字符 64233→58000（中文约 35000 字/70 分钟）。

### 关键修复（5 项精准度 P1）

1. **集成电路缺口 30万→50万 引用源错误**：3 处 [INDUSTRY-2] → [INDUSTRY-10]（产业深读已正确，其他章漏改）
2. **低空经济 1.5万亿引用源矛盾**：[INDUSTRY-6] 描述"2030破万亿"与正文"2025年1.5万亿"矛盾，新增 [INDUSTRY-13] 民航局预测源
3. **郑栅洁 2026年3月发言引用源时间矛盾**：[INDUSTRY-2]（2025-11 报道）→ [OFFICIAL-8]（国新办发布会）
4. **"219个点位"无出处**：改为定性表述"教育部新批复一批聚焦AI/芯片的中外合作办学点位"
5. **"连续8年破千万"应为"连续5年"**：2022届首次破千万，2026届是连续5年

### 落地 P0 修复亮点（照抄即用章 9 项）

- 决策表候选院校表补"录取概率算法"+3列核对字段（家庭底线/专业级差/选科匹配）
- 24小时清单补"专业组内核查""志愿顺序""双签字"3项
- 双漏斗 L1 补"霍兰德代码查询入口"、L2 补"能力量化阈值"（数学<100慎选微电子等）、L1"位次±20%"消歧
- 讨论清单补"分数/位次"和"学校维度"2问+使用时点说明

### 沉淀方法论

1. **多终审并行比单终审串行更彻底**：精准度/质量/落地三视角并行评审，互不干扰，问题暴露更彻底。80/85/81 三个分数叠加后暴露 18 项必修复，单视角评审容易遗漏。
2. **"照抄即用"的硬标准是"零门槛"**：决策表不能只给字段不给算法，讨论清单不能漏核心维度，双漏斗不能无量化阈值，24小时清单不能漏关键核对项。"差不多能用"≠99分，必须"零门槛照抄"。
3. **跨章引用源必须全局一致**：同一数据（如集成电路缺口 30万→50万）在多章出现时，引用编号必须统一，不能产业深读用 [INDUSTRY-10] 而其他章用 [INDUSTRY-2]。整合阶段必须 Grep 同数据跨文件核验引用编号。
4. **压缩的边界**：表格/金句/操作步骤/引用编号一字不删，只压解释性文字。11 文件压缩 17% 后总字符 58000（约 35000 中文字），核心章节约 50 分钟符合"半小时到1小时"，全专栏精读 70 分钟是合理范围。继续压缩边际效益递减且易破坏内容。
5. **开篇路线图必须随章节增减同步**：Phase 2 新增 5 章后开篇路线图未更新，导致"开篇承诺的旅程"与"实际旅程"不一致，削弱首尾一体感。章节增减后必须同步更新开篇路线图。

### 涉及文件

- `output/高考志愿填报前置认知/`：16 章正文 + _参考资料.md（新增 [INDUSTRY-13]）+ 3 份 _research_*.md
- `src/web/static-site/gaokao.html`：落地页 7 模块 16 卡片 + 快速导航 + 5 个 NEW 角标 + 模块⑥独立色调
- `docs/loop_log.md`：本条沉淀

### 测试覆盖

- `python scripts/check_book_structure.py --output output --strict`：0 问题
- `pytest -q`：394 passed, 19 skipped
- 落地页 16 个跳转链接 100% 正确（subagent 逐条验证）
- 三终审得分：精准度 80→修复 5 项 P1 / 质量 85→修复 4 项必修复 / 落地 81→修复 9 项 P0+9 项 P1

**教训标签**：`#lesson: content_quality` `#lesson: book_structure`

## BUG-032 专栏正文方括号引用编号打断阅读体验（2026-06-28）

### 触发问题
用户反馈专栏正文里穿插 `[OFFICIAL-x]/[EXPERT-x]/[INDUSTRY-x]/[PSYCH-x]/[BOOK-x]/[VIDEO-x]` 编号共 407 处，高三学生和家长看不懂是什么，要去 `_参考资料.md`（`_` 前缀被 build_site 跳过，根本没出现在站点里）查编号才能知道信源，打断阅读。

### 根因
Phase 1 设计的"置信度溯源范式"（loop_log L1205）把引用编号当学术论文引用写进正文，但专栏面向 C 端读者而非学术读者；`_参考资料.md` 用 `_` 前缀导致站点不收录，编号失去对应入口。

### 修复方案（用户选择"保留编号但移到章末脚注"）
1. 16 章正文里所有 `[XXX-x]` 编号从行文中删除，按三情况处理：
   - 情况A（编号后紧跟信源名）：直接删编号
   - 情况B（编号是唯一信源标识）：替换为内联说明（如 `[INDUSTRY-13]`→"民航局预测"）
   - 情况C（多编号并列）：合并说明（如 `[INDUSTRY-2][INDUSTRY-5][INDUSTRY-6]`→"综合新华社、卫健委、赛迪研究院数据"）
2. 每章末尾新增 `## 本章参考资料` 小节，按出现顺序去重列出本章引用的信源（用作者/书名/机构名而非编号）。
3. `_参考资料.md` 从"编号清单"改为"按类别列出主要参考资料"清单，删除所有编号列。

### 执行（路径 C 三轮并行）
3 个 subagent 按文件分组（6/5/5 章）并行处理，共删除 288 处编号，章末新增 132 条参考资料。`_参考资料.md` 由主 Agent 重写。

### 验证
- Grep 确认 16 章正文零残留 `[(OFFICIAL|EXPERT|INDUSTRY|PSYCH|BOOK|VIDEO)-\d+]`
- `check_book_structure.py --strict`：0 问题
- `pytest`：394 passed, 19 skipped
- 抽查 3 章（开篇/认识产业/心法与避坑）确认正文语义连贯 + 章末有参考资料小节

### 沉淀方法论
1. **C 端专栏的引用溯源不能照搬学术论文的编号体系**——编号适合内部审稿，不适合面向读者。信源应以作者/书名/机构名内联说明或集中放章末，让读者一眼知道出处。
2. **`_` 前缀文件被 build_site 跳过的机制要纳入引用体系设计考虑**——如果引用溯源依赖一个站点不收录的文件，编号就失去了对应入口，等于"读者看不懂、查不到"。
3. **删除编号的三情况判定法可复用**：A 跟信源名→直接删 / B 唯一标识→内联替换 / C 多编号并列→合并说明。这套判定法适用于所有"内部编号体系要面向化"的场景。
4. **章末脚注式参考资料比全文统一编号清单更友好**——读者读完一章就能看到本章引用了谁，不用跳到全书末尾查编号表。

### 涉及文件
- `output/高考志愿填报前置认知/`：16 章正文 + `_参考资料.md`
- `tests/bug_regression_list.md`：新增 BUG-032
- `docs/loop_log.md`：本条沉淀

**教训标签**：`#lesson: content_quality` `#lesson: book_structure`
