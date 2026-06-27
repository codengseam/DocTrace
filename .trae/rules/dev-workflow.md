# 项目开发协作流程规则

本规则用于指导 Agent 在 Trae IDE 中与用户进行**项目开发协作**时的默认行为。
详细项目背景见 [README.md](../../README.md)。

## 零、适用范围与边界声明

### 1. 适用场景

本规则**仅适用于项目开发协作对话**——即用户在 Trae 中讨论代码改动、功能实现、Bug 修复、流程优化、方案评审等开发类任务时。

**不适用于**：生成古籍讲书笔记。讲书笔记生成由 `.trae/skills/deep-reading/rules.md` 和 `.trae/skills/deep-reading/SKILL.md` 负责，本规则不干预。

### 2. Trae Skill 能力边界（必须如实遵守）

| 能力 | Skill 是否支持 |
|---|---|
| 识别用户意图、加载规范、引导 Agent 行为 | 支持 |
| 让 Agent 调用 RunCommand / Read / Edit 等内置工具 | 支持（通过 Prompt 引导） |
| **创建 / 调度 sub-agents** | **不支持** |
| **直接调用 MCP tools** | **不支持** |
| 执行代码、保存文件、维护状态 | **不支持** |

**重要**：当用户提到"启用多个 agent""专家团并行""多 Agent 评审"时，不要假装 Skill 可以调度子 Agent。可行路径只有两条：
- **路径 A**：由单个 Agent 串行切换视角（架构师→测试→规则），伪并行。
- **路径 B**：Skill 触发本地 Python 脚本（如 `python scripts/review_plan.py`），由 Python 引擎（LangGraph）做真并行。

本项目已为路径 B 配备基础设施：`src/agents/` + `src/core/workflow.py` + `scripts/review_plan.py`。

## 一、默认协作流程（每次开发对话自动生效）

收到用户的开发类需求后，**必须按以下顺序执行**，不可跳步：

### 第一步：重述需求

用一句话重述用户意图，确认理解一致。格式：

> 我理解你要做的是：____（一句话）。核心目标是：____（用户原话或提炼）。

如果用户已明确给出核心目标，直接引用；如果没有，主动提炼并标注"（我提炼的，请确认）"。

### 第二步：生成计划并等确认

围绕核心目标列出计划要点，**等用户确认后再执行**。计划格式：

```
## 计划
- 核心目标：____
- 步骤：
  1. ____
  2. ____
  3. ____
- 涉及文件：____
- 风险点：____
```

**不要在用户确认前开始改代码。** 如果用户说"直接做""开始吧""嗯"等明确同意的话，才进入第三步。

### 第三步：执行

**开始前必读 loop_log**：
1. 用 Grep 工具按本次任务主题关键词检索 `docs/loop_log.md`
2. 若命中相关记录，引用命中的 H2 标题行号作为本次执行的前置参考（格式：`参考历史教训：docs/loop_log.md#L<行号>`）
3. 若无命中，在执行报告中显式声明"本次任务无相关历史教训"，方可进入执行

**禁止**：仅填"未发现相关教训"一句话即过，必须先执行 Grep 检索动作。

执行时遵守以下规范：

- **优先复用现有能力**：先查 `.trae/skills/`、`.trae/rules/`、`.trae/checklists/`、`prompts/`、`src/agents/`、`src/core/` 是否已有可复用的 Skill / 规则 / 提示词 / Agent，避免重复造轮子。
- **并行提速**：能并行的子任务尽量并行（用 Task 工具启动多个 subagent，或调用 Python 脚本做真并行）。
- **遵循现有目录结构与命名规范**：见 README §七、§八；新增/重命名 Markdown 章节时，禁止在 `chapter` 字段或文件名中使用「模块N」前缀（历史问题 BUG-019）。
- **不过度工程化**：只做直接请求或必要的事，不主动加抽象、加配置、加兼容层。
- **合并前必须清零所有校验问题**：执行 `python scripts/check_book_structure.py --output output --strict`，P0/P1/P2 全部通过后方可进入合并/推送。若发现非本次引入的问题，仍须修复；修复后判断是否为会复发的代码/数据 bug，需要补充回归测试并按 `.trae/rules/bug-reporting.md` 更新 `tests/bug_regression_list.md`。

### 第四步：自检

完成后**主动启用自检**，对照 `.trae/checklists/dev-checklist.md` 逐项检查并修复。也可由用户触发 `.trae/skills/dev-selfcheck/SKILL.md`。

自检必须包含：
- `python scripts/check_book_structure.py --output output --strict` 通过。
- `pytest` 全部通过。
- 若修复了历史遗留或会复发的 bug，已补充回归测试或更新 `tests/bug_regression_list.md`。

### 第五步：沉淀（LoopAgent 思维）

每次开发完成后，做一次沉淀复盘：

- 本次改动是否暴露了新的共性问题？
- 是否需要更新 `.trae/rules/` 或 `src/utils/quality.py`？
- 是否需要更新 `.trae/checklists/dev-checklist.md`？
- 是否需要在 `docs/loop_log.md` 追加一条开发沉淀记录？

**loop_log 写入门槛**（启发式，不强制白名单）：

写了不亏的（建议写）：
- 暴露了新的共性/反复问题（非单次 bug）
- 产出了可复用资产/方法论（如三维度评分法、主场客场去重策略）
- 触发了规则/checklist/Skill 的实际更新

别往 loop_log 写的（去对应文件）：
- 纯内容生成日志 → 去 `output/` 自身或 commit message
- 单点 bug 修复 → 去 `tests/bug_regression_list.md`
- 纯部署配置调整 → 去 commit message 或 README

**写 loop_log 时必带的 #lesson slug**（从下表选，多选用空格分隔）：
- `git_hygiene` / `reader_interaction` / `content_quality` / `book_structure` / `deployment` / `soul_injection` / `ai_course`

完整 slug 主题表与方案 C 手册见 `docs/loop_log.md` 文件末尾。

**目标**：让开发协作本身也变成可迭代的 Loop，沉淀经验，避免同类问题反复出现。

## 二、提示词固化（无需用户每次粘贴）

用户此前每次对话都要粘贴下面这段提示词：

> 启用多个 agent 组成专家团理解下面的需求，并使用 skills 和 checklist 规范执行，用多个 agent 并行提速，完成后启用专家团检查并修复完成，采用 loop agent 的思维来开发优化这个项目；主要是得添加核心目标，然后围绕目标去实现

本规则已将这段提示词拆解为上述五个步骤并固化为默认行为。**用户不再需要手动粘贴**。

对应关系：

| 提示词原文 | 固化到 |
|---|---|
| "启用多个 agent 组成专家团理解下面的需求" | 第一步重述需求 + 第二步生成计划；如需真并行评审，触发 `.trae/skills/plan-review/SKILL.md` |
| "使用 skills 和 checklist 规范执行" | 第三步执行中的"优先复用现有能力" + 第四步自检对照 checklist |
| "用多个 agent 并行提速" | 第三步执行中的"并行提速" |
| "完成后启用专家团检查并修复完成" | 第四步自检 |
| "采用 loop agent 的思维来开发优化这个项目" | 第五步沉淀 |
| "主要是得添加核心目标，然后围绕目标去实现" | 第一步重述需求中的"核心目标" + 第二步计划中的"围绕核心目标" |

## 三、语言风格

- 中文为主，自然口语化。
- 重述需求时简洁明了，不堆砌背景。
- 计划要点用列表，不用大段文字。
- 执行过程中及时汇报进度，不沉默操作。
- 自检报告用清单形式，标注通过/未通过。

## 四、禁止事项

- **不在用户确认前改代码**。
- **不假装 Skill 可以调度 sub-agents**——做不到就如实说明，给出路径 A 或路径 B 的替代方案。
- **不破坏现有体系**：`.trae/skills/deep-reading/`（含 rules.md、content-quality.md）、`prompts/` 下 7 份讲书提示词、`src/utils/quality.py` 不在本规则的修改范围内。
- **不过度工程化**：能用规则文件解决的不写 Skill；能用 Skill 引导的不写 Python；只有真需要多 Agent 并行时才动用 LangGraph。
- **不跳过沉淀**：每次开发完成后都要做第五步沉淀复盘，哪怕只是"本次无新沉淀"也要说明。
- **禁止以「问题非本次引入」为由跳过修复**：合并/推送前 `check_book_structure.py --strict`、`pytest`、回归测试集必须全部通过。
- **禁止在存在任何校验问题时执行 push/merge**：包括 P2 级别问题。
