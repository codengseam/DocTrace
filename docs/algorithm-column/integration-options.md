# 数据结构与算法专栏 · 生成管线接入方案

> 状态：策划草案，待用户确认。本文件讨论本专栏是否接入 HaloRead LangGraph 生成管线，以及如何接入。
> 配套：[plan.md](./plan.md) · [prompts-draft.md](./prompts-draft.md) · [outline.md](./outline.md)

## 背景

[plan.md §3](./plan.md) 已决定「复用 knowledge 桶，不新建 archetype」。但「复用 knowledge 桶」有两种执行路径：

- **路径 A（重接入）**：新建 `prompts/algorithm/` 子目录，把 [prompts-draft.md](./prompts-draft.md) 的 7 份草稿落入其中，作为 knowledge 桶的一个子桶，由 LangGraph 自动路由生成
- **路径 B（轻接入）**：不落入 `prompts/`，主 Agent 临时引用 `docs/algorithm-column/prompts-draft.md` 内容，手工调用 LLM 生成，不经过 LangGraph 管线
- **路径 C（混合接入）**：本阶段走 B，等生成几篇验证草稿质量后再升级到 A

本文件列出三条路径的代价与收益，由用户选择。

---

## 路径 A：新建 `prompts/algorithm/` 子目录接入 LangGraph

### A.1 实施步骤

1. 新建 `prompts/algorithm/` 目录，放入 7 份提示词草稿（orchestrator / tone_setter / context_analyst / historian / biographer / editor / chief_editor）
2. 改 `config.yaml`：
   - 在 `section_templates` 下新增 `algorithm` 桶，段名与 knowledge 桶完全一致（概念/原理/实践/速查自测），避免改 `check_book_structure.py`
   - 在 `archetype_defaults` 下新增映射：`算法: "algorithm"`（或将「算法」直接映射到 `knowledge`，见 A.3 取舍）
3. 改 `src/core/workflow.py`：
   - 在 `_VALID_ARCHETYPES` 加 `"algorithm"`
   - 在 `_soul_injection_for_archetype` 把 `algorithm` 加入启用列表
   - 在 `build_workflow` 中，`algorithm` 桶的 specialist 裁剪逻辑复用 knowledge 桶（historian/biographer/context_analyst 三个 specialist），不注册 critic/philosopher
4. 改 `src/utils/content_quality.py`：
   - `KNOWLEDGE_TERMS_WHITELIST` 扩充算法术语（BFS/DFS/DP/Heap/BTree/Hash 等）——大部分已在白名单内，仅需补少数（如「单调栈」「并查集」等中文术语的英文对照不报）
5. 新建 `output/数据结构与算法/` 目录，加 `_meta.yaml`（`category: 技`、`archetype: knowledge` 或 `algorithm`）
6. 跑回归测试：`pytest -q` + `bash tests/run_regression_suite.sh` + `python scripts/check_book_structure.py --output output --strict`

### A.2 代价

- **代码改动**：`config.yaml` + `src/core/workflow.py` + `src/utils/content_quality.py`，约 50-100 行
- **回归风险**：动 `_VALID_ARCHETYPES` 与 `build_workflow` 边链裁剪逻辑，可能影响 modern/knowledge 桶。参考 [loop_log 阶段4](../loop_log.md) 的教训：「新增 archetype 时节点拓扑必须按维度裁剪，否则占位节点产空段污染下游」
- **测试覆盖**：需新增 `tests/test_workflow_archetype.py` 中的 algorithm 契约（specialist 注册 / 边链完整 / soul injection 启用）
- **bug 记录**：若引入新 bug 须按 [bug-reporting.md](../../.trae/rules/bug-reporting.md) 记录到 `tests/bug_regression_list.md`

### A.3 取舍：新建 algorithm 桶 vs 直接复用 knowledge 桶

| 维度 | 新建 algorithm 桶 | 直接复用 knowledge 桶 |
|---|---|---|
| 段名 | 与 knowledge 完全一致（4 段） | 与 knowledge 完全一致 |
| 提示词 | 独立 `prompts/algorithm/`，可定制 | 共用 `prompts/knowledge/`，无法定制 |
| workflow 改动 | 需要（加 `_VALID_ARCHETYPES`） | 不需要 |
| 特化点承载 | 提示词层特化（神和根本 / 思想迁移） | **无法承载**——knowledge 桶原版提示词没有这两个特化点 |
| 推荐度 | ⭐⭐⭐ 推荐 | ⭐ 不推荐（特化点丢失） |

**结论**：如果走路径 A，必须新建 algorithm 桶（不复用 knowledge 桶提示词），否则 [plan.md §4](./plan.md) 的两个加严规约无法落地。

### A.4 收益

- 32 篇正文可由管线自动生成，质量由 `content_quality.py` 与 `chief_editor` 双轨质检守护
- 与项目其他专栏（AI大模型学习等）同源同构，统一阅读体验
- 用户笔记接入可通过 orchestrator 的 `user_notes` 字段标准化

---

## 路径 B：不接入管线，主 Agent 临时引用提示词草稿

### B.1 实施步骤

1. 不动任何代码与配置
2. 主 Agent 生成每篇时，临时从 `docs/algorithm-column/prompts-draft.md` 读取对应子提示词
3. 串行调用 LLM：先按 tone_setter 草稿生成大纲 → 按 context_analyst/historian/biographer 草稿并行生成三段 → 按 editor 草稿汇总并补速查段 → 按 chief_editor 草稿自审
4. 输出 Markdown 文件直接落到 `output/数据结构与算法/{chapter}_{event}.md`，frontmatter 走 knowledge 桶标准
5. 跑 `check_book_structure.py --strict` 校验结构与 P0/P1/P2

### B.2 代价

- **无代码改动**，无回归风险
- **无 LangGraph 编排**：并行调用、状态管理、断点续跑都得手工
- **无自动质检**：`content_quality.py` 五维度质检需要手工触发
- **生成质量靠 Agent 自觉**：每篇都得在对话里逐篇 review

### B.3 收益

- 零风险，可立即开始
- 灵活——可逐篇调整提示词，不受管线契约约束
- 适合先做 3-5 篇「试点篇」验证提示词草稿质量

---

## 路径 C：本阶段走 B，验证后升级到 A（推荐）

### C.1 实施步骤

1. **本阶段**：走路径 B，先生成 3-5 篇试点正文（建议选第 1 章开篇、第 6 章二分查找、第 10 章 DP、第 11 章 BFS/DFS、第 27 章 Polya 四步法——覆盖开篇/原理篇/数据结构篇/思想迁移篇各一）
2. **试点评估**：每篇由用户 review，确认「神和根本」「思想迁移」「投入实际」三个特化点是否落地
3. **提示词迭代**：根据试点反馈调整 [prompts-draft.md](./prompts-draft.md)
4. **升级到 A**：提示词稳定后，落入 `prompts/algorithm/`，按 A.1 步骤接入管线
5. **批量生成**：剩余 27 篇由管线自动生成

### C.2 何时升级

升级到 A 的触发条件（任一满足）：
- 试点篇 ≥3 篇通过用户 review，提示词草稿不需大改
- 用户希望批量生成剩余 20+ 篇
- 用户笔记接入需要标准化（路径 B 难以批量化处理用户笔记）

不升级的触发条件（继续走 B）：
- 试点篇提示词需反复迭代
- 用户希望每篇都深度定制
- 总篇数缩减到 10 篇以内

### C.3 风险

- 路径 B 产出的文件可能与未来路径 A 的 frontmatter/段名契约不一致——升级时需要迁移
- 缓解：路径 B 阶段就严格按 knowledge 桶 frontmatter 与段名契约生成，避免迁移成本

---

## 用户笔记接入方案

无论走哪条路径，用户笔记接入都通过 orchestrator 的 `user_notes` 字段。两种处理方式：

### 方式 1：结构化笔记（推荐）

- 用户笔记为 Markdown，按「概念/原理/实践/迁移」分块
- orchestrator 解析后，将每块作为对应 specialist 的辅助信源
- 适用：用户已有结构化笔记

### 方式 2：散乱片段

- 用户笔记为散乱文本/PDF/照片
- orchestrator 不解析，整体作为「用户信源」传入所有 specialist
- specialist 在写作时引用并标注「用户笔记」
- 适用：用户笔记尚未整理

**待用户给出笔记形式后选定方式。**

---

## 三条路径对比

| 维度 | 路径 A 重接入 | 路径 B 轻接入 | 路径 C 混合（推荐） |
|---|---|---|---|
| 代码改动 | 50-100 行 | 0 | 本阶段 0，升级时 50-100 行 |
| 回归风险 | 中（动 workflow） | 无 | 本阶段无 |
| 自动质检 | ✅ 五维度 + chief_editor | ❌ 手工 | 本阶段手工，升级后自动 |
| 批量生成 | ✅ 32 篇可批量 | ❌ 逐篇手工 | 本阶段手工，升级后批量 |
| 提示词迭代 | ❌ 受管线契约约束 | ✅ 灵活 | 本阶段灵活，升级后固化 |
| 试点验证 | ❌ 直接全量风险高 | ✅ 适合试点 | ✅ 适合试点 |
| 推荐度 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 推荐决策

**推荐路径 C（混合接入）**，原因：

1. **降低风险**：本专栏有两个独特特化点（神和根本 / 思想迁移），直接全量接入管线风险高——提示词草稿可能需要多次迭代
2. **保留灵活性**：路径 B 阶段可逐篇调整提示词，不受管线契约约束
3. **不阻塞生成**：用户可以立即开始 review 试点篇，无需等代码改动
4. **升级路径清晰**：试点验证通过后，路径 A 的步骤明确（A.1 已列出）

## 待用户确认事项

1. 选择哪条路径？我推荐路径 C
2. 若选路径 C，试点篇选哪 5 章？我建议：第 1/6/10/11/27 章（覆盖四篇 + 一个开篇）
3. 用户笔记的接入方式（结构化 vs 散乱），等笔记给出后再定
4. 若选路径 A，是否同意新建 `algorithm` 桶（不复用 knowledge 桶提示词）？我建议同意，否则特化点丢失

## 与 dev-workflow 规则的衔接

无论选哪条路径，正文生成阶段都必须遵守 [dev-workflow.md](../../.trae/rules/dev-workflow.md)：

- **第二步生成计划**：每篇正文生成前都要列计划
- **第三步执行**：开始前必读 `docs/loop_log.md`，Grep 检索相关教训
- **第四步自检**：完成后跑 `check_book_structure.py --strict` + `pytest` + 回归集
- **第五步沉淀**：若暴露新共性问题，更新 loop_log；若修复 bug，更新 bug_regression_list
