# LoopAgent 循环日志

> 历史测评框架与评分表见 [docs/archive/loop_log_fossils.md](archive/loop_log_fossils.md)（不再更新）。
> 本文件仅记录开发沉淀。每次开发前请先 Grep 检索本文件（见 `.trae/rules/dev-workflow.md` 第三步）。


## 索引区

<!-- AUTOGEN START: loop_log index -->

### 最近 20 条沉淀（按日期倒序）

- [2026-06-29 中国礼仪课专栏深度质检二轮闭环 95.6→97.5](loop_log/2026-06.md#loop-20260629-2670c0)
- [2026-06-29 心之力与强者思维双专栏并行生成](loop_log/2026-06.md#loop-20260629-e68bdf)
- [2026-06-29 夸克阅读模式不识别 SPA 动态正文（SSG 静态生成）](loop_log/2026-06.md#loop-20260629-909ab9)
- [2026-06-28 高考志愿填报前置认知 Phase 2 升级 - 精准100/质量98/落地99三终审闭环](loop_log/2026-06.md#loop-20260628-cd76f7)
- [2026-06-28 财务自由课专栏 40 篇道术器行四层生成](loop_log/2026-06.md#loop-20260628-a5caff)
- [2026-06-28 现代人富贵病防治手册专栏生成 - 多 subagent 并行 + 医学术语中文化策略](loop_log/2026-06.md#loop-20260628-4b2494)
- [2026-06-28 提交信息必须用中文且准确概括当前修改](loop_log/2026-06.md#loop-20260628-c328ca)
- [2026-06-28 富贵病手册新增「当代人的习惯账本」章节 - 章节插入与已有方法论复用](loop_log/2026-06.md#loop-20260628-6c0dee)
- [2026-06-28 中国礼仪课专栏 + 多 agent 并行生成 + 三视角评审闭环](loop_log/2026-06.md#loop-20260628-06cdcb)
- [2026-06-28 docs/loop_log.md 手写索引区引发合并冲突](loop_log/2026-06.md#loop-20260628-e289de)
- [2026-06-28 MySQL 实战专栏 32 篇并行生成的 subagent 写作规范盲区](loop_log/2026-06.md#loop-20260628-34f7cd)
- [2026-06-28 BUG-032 专栏正文方括号引用编号打断阅读体验](loop_log/2026-06.md#loop-20260628-5d5433)
- [2026-06-27 高考志愿填报前置认知科普专栏 + 多 agent 打分闭环](loop_log/2026-06.md#loop-20260627-ed8f29)
- [2026-06-27 首页圣贤堂入口优化 + 内置 YAML 解析器嵌套结构支持](loop_log/2026-06.md#loop-20260627-c1182f)
- [2026-06-27 阶段5 Skill 入口分流与沉淀落地（2026-06-27，会话C）](loop_log/2026-06.md#loop-20260627-9b6339)
- [2026-06-27 阶段4 边链裁剪完成（2026-06-27，解除 modern/knowledge soul injection 架构债）](loop_log/2026-06.md#loop-20260627-2f800a)
- [2026-06-27 资治通鉴续写至 77 章 + 提示词/引用沉淀（2026-06-27，覆盖完整 1362 年通鉴）](loop_log/2026-06.md#loop-20260627-182485)
- [2026-06-27 plan-review skill 硬阻塞修复 + dispatching-parallel-agents 原生化（2026-06-27，BUG-031）](loop_log/2026-06.md#loop-20260627-f6a702)
- [2026-06-26 灵魂注入专项 - 明纪·海瑞上疏 AB 盲测](loop_log/2026-06.md#loop-20260626-735fb0)
- [2026-06-26 superpowers 原生技能化 + 明纪阶段校验 + 章回体灵魂标题自动化](loop_log/2026-06.md#loop-20260626-8cb5f6)

### 主题锚点

- `#git_hygiene`：推送/合并/冲突/分支治理/commit 覆盖
- `#reader_interaction`：阅读器/沉浸/翻页/吸底栏/SW 缓存
- `#content_quality`：质检规则/灵魂注入/标题评分
- `#book_structure`：排序/校验/命名/去重/双源同步
- `#deployment`：GitHub Pages/魔搭/.nojekyll/SW
- `#soul_injection`：灵魂注入/章回体/总编Agent
- `#ai_course`：专栏批量生成 / subagent 结果丢失

### 教训计数表（≥3 次且未入 checklist 即触发方案 C，见文件末"方案 C 手册"）

| #lesson slug | 出现次数 | 说明 |
|---|---|---|
| `#git_hygiene`（推送/合并/冲突/分支治理/commit 覆盖） | 6 | — |
| `#reader_interaction`（阅读器/沉浸/翻页/吸底栏/SW 缓存） | 12 | — |
| `#content_quality`（质检规则/灵魂注入/标题评分） | 16 | — |
| `#book_structure`（排序/校验/命名/去重/双源同步） | 20 | — |
| `#deployment`（GitHub Pages/魔搭/.nojekyll/SW） | 5 | — |
| `#soul_injection`（灵魂注入/章回体/总编Agent） | 3 | — |
| `#ai_course`（专栏批量生成 / subagent 结果丢失） | 9 | — |

> 共 42 条沉淀，按月份分片存储于 `docs/loop_log/`。

<!-- AUTOGEN END: loop_log index -->

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


