# 内容质检多 Agent 架构

本文件描述内容质检 Skill 的多 Agent 协作架构。**Skill 文件本身不调度 sub-agents**——真并行由本地 Python 引擎（LangGraph）或主 Agent 经 Trae `Task` 工具完成。Skill 只负责触发和返回结果。

## 一、两层架构

```
                ┌─────────────────────────────────────┐
                │  Skill 入口（SKILL.md）              │
                │  识别意图 → 收集内容 → 触发引擎        │
                └─────────────┬───────────────────────┘
                              │
                ┌─────────────▼───────────────────────┐
                │  Layer 1: 规则层（确定性，无需 LLM）  │
                │  Step 1: check_char_count.py        │
                │  Step 2: check_consistency.py       │ ← v1.2 新增
                │  Step 3: content_quality.py 六维度   │
                └─────────────┬───────────────────────┘
                              │
                              │ 硬错误清零后
                              ▼
                ┌─────────────────────────────────────┐
                │  Layer 2: LLM 层（语义级深审，可并行）│
                │  ┌─────────┬─────────┬─────────┐    │
                │  │ 史实核验 │ 可读性  │ 引用克制 │    │
                │  └─────────┴─────────┴─────────┘    │
                │  通过 LangGraph content_review_     │
                │  workflow 并行执行                   │
                └─────────────────────────────────────┘
```

**Layer 术语约定**：本文件与 SKILL.md 统一使用「Layer 1 = 规则层 / Layer 2 = LLM 层」两层架构。规则层内部的三步检测用「Step 1/2/3」表示，避免与 Layer 1/2 冲突。

## 二、Layer 1 规则层 Agent（确定性）

### Step 1: 字数核对 Agent

- **入口**：`scripts/check_char_count.py`
- **能力**：检测三种字数声明模式（A/B/C），字数不含标点
- **触发**：质检前置，发现 P0 字数错误即阻断后续流程
- **输出**：文件路径 + 错误字数 + 应有字数

### Step 2: 一致性检测 Agent（v1.2 新增）

- **入口**：`.trae/skills/content-review/scripts/check_consistency.py`
- **底层模块**：`src/utils/consistency.py`
- **能力**：四类矛盾检测
  1. 数值交叉矛盾（年龄-年份/在位时长/损失-剩余）
  2. 同事件异值（同引文异字数/同战役异兵力/同典故异出处）
  3. 实体别名冲突（字号/谥号/籍贯）
  4. 时间线倒置（年份逆序且无倒叙标注）
- **设计依据**：CoV 离线 claim 提取 + Self-Consistency 思想
- **误报防护**：攻防动词豁免、虚数前后缀豁免、倒叙标注词豁免、句界窗口限定（详见 [rules/consistency-rules.md](rules/consistency-rules.md) §二）
- **archetype 路由**：narrative（古籍基线）/ modern（职场商科）/ knowledge（技术）

### Step 3: 六维度规则质检 Agent

- **入口**：`src/utils/content_quality.py:run_content_quality_checks()`
- **能力**：六维度规则质检（真实性/可读性/顺序/引用克制/灵魂/一致性）
- **集成**：一致性维度已合并到此层，`passed = score >= 85 and consistency_report.passed`（双门控，详见 `content_quality.py`）

## 三、Layer 2 LLM 层 Agent（语义级深审）—— 代码已交付

> **交付状态**：下列 LLM 层文件均已实现（v1.2 已交付），但运行需 `LLM_API_KEY` + `langgraph` 已安装。
> 沙箱默认无这两项，降级方案：由主 Agent 经 Trae `Task` 工具启动 subagent 并行执行（路径 C）。
> - `src/agents/content_reviewer_sub.py`（三视角 specialist，75 行）
> - `src/agents/content_reviewer.py`（主 reviewer，56 行）
> - `src/core/content_review_workflow.py`（LangGraph 工作流，93 行）
> - `scripts/review_content.py`（CLI 入口，192 行）

### 三视角并行 Agent

由 `src/agents/content_reviewer_sub.py` 实现（`ROLE_DIMENSIONS`），经 `src/core/content_review_workflow.py` 用 LangGraph 并行调度：

| Agent | 职责 | 满分 | 检查项 |
|---|---|---|---|
| 史实核验 specialist | 内容真实性 | 40 | 人名/时间/地点/因果、关键年份、典故出处、名家点评真实性、跨文化映照、史料层累 |
| 可读性 specialist | 故事感与重复 | 30 | 场景对话戏剧性、重复控制、AI 套路句、现代术语硬套、段尾升华 |
| 引用克制 specialist | 引用规范 | 15 | 内联跳转、行内引用密度、文末来源完整性 |
| **合计** | — | **85** | — |

**信源边界**：LLM 层 85 分为专家定性评分，**不**与规则层 100 分相加。最终 `passed` 判定以规则层 `ContentQualityReport` 为唯一信源。LLM 层仅产定性意见与修复建议。

### 三视角 Prompt 加载

- 模板文件：`prompts/content_reviewer_sub.md`（narrative 默认路径）
- archetype 路由：当前所有 archetype 均回退到 narrative 路径的 `content_reviewer_sub.md`（`prompts/{archetype}/content_reviewer_sub.md` 未创建，`load_prompt` 自动 fallback 并打印 UserWarning）
- CoT 增强（v1.2.2）：模板内含"先列核验步骤，再下结论"的 Chain-of-Thought 结构（Wei et al. Google 2022），提升史实核验可靠性

## 四、并行调度路径

按 dev-workflow.md §零「能力边界声明」，路径有三：

- **路径 B（已交付，需环境）**：Skill 触发 `python scripts/review_content.py`，由 LangGraph 引擎做真并行。
  - **当前状态**：代码已实现，需 `LLM_API_KEY` + `langgraph` 已安装。
  - 环境缺失时降级到路径 C 或路径 A（串行）。
- **路径 C（沙箱降级主路径）**：主 Agent 经 Skill 引导，用 Trae `Task` 工具启动多个 subagent 并行执行 LLM 语义级深审。无需 langgraph，但仍需 LLM 能力（subagent 自带）。
- **路径 A（降级）**：单 Agent 串行切换三视角，伪并行。仅在 Task 工具与 LangGraph 均不可用时使用。

## 五、与 deep-reading Skill 的关系（ReAct 离线变体）

```
deep-reading（生成）→ content-review（质检）→ 修复 → 再质检
       ↑                                          │
       └────────────── 反馈循环 ─────────────────────┘
```

**方法论溯源**：本闭环是 ReAct（Reasoning and Acting，Yao et al. 2022）在离线质检场景的变体——"Reasoning"对应规则层 claim 提取与交叉验证，"Acting"对应触发修复与再质检。与 CoV/Self-Consistency 的溯源风格一致，此处显式标注以完善方法论透明度。

- `deep-reading` 生成讲书笔记后自动触发 `content-review` 质检。
- 质检发现问题 → 反馈给 deep-reading 重生成或人工修复 → 再质检。
- 一致性维度新增后，deep-reading 的 prompt 应避免生成前后矛盾内容（防优于治）。

## 六、专家团评审机制（用户要求 ≥ 99 分）

完成质检后启用三视角评审：

1. **架构师视角**：评估规则与 LLM 分层是否合理、误报率、可扩展性
2. **测试视角**：评估回归测试覆盖率、边界用例、archetype 路由正确性
3. **规则视角**：评估规则完整度、与权威资料对齐度、能力边界声明

主 Agent 汇总三视角意见，输出评分报告，目标 ≥ 99 分。

## 七、相关文件清单

| 类别 | 文件路径 | 状态 |
|---|---|---|
| Skill 入口 | `.trae/skills/content-review/SKILL.md` | v1.2.1 已交付 |
| 一致性规则 | `.trae/skills/content-review/rules/consistency-rules.md` | v1.2 已交付 |
| 一致性 CLI | `.trae/skills/content-review/scripts/check_consistency.py` | v1.2 已交付 |
| 一致性根入口 | `scripts/check_consistency.py`（便捷封装） | v1.2 已交付 |
| 一致性核心模块 | `src/utils/consistency.py` | v1.2.1 已交付 |
| 六维度质检模块 | `src/utils/content_quality.py` | v1.2 已交付 |
| 字数核对 CLI | `scripts/check_char_count.py` | v1.2 已交付 |
| 书籍结构校验 CLI | `scripts/check_book_structure.py` | v1.2 已交付 |
| frontmatter 剥离公共函数 | `src/utils/quality.py:strip_frontmatter` | v1.2 已交付 |
| 质检 CLI（全维度） | `scripts/review_content.py` | v1.2 已交付（需 LLM_API_KEY + langgraph） |
| 三视角 specialist | `src/agents/content_reviewer_sub.py` | v1.2 已交付（需 LLM_API_KEY + langgraph） |
| 主 reviewer | `src/agents/content_reviewer.py` | v1.2 已交付（需 LLM_API_KEY + langgraph） |
| LangGraph workflow | `src/core/content_review_workflow.py` | v1.2 已交付（需 LLM_API_KEY + langgraph） |
| 六维度清单 | `.trae/skills/content-review/checklist.md` | v1.2.1 已交付 |
| **测试** | | |
| 一致性检测回归测试 | `tests/test_consistency.py` | 101 测试（4 类矛盾 + 7 类豁免 + 门控 + 路由） |
| 一致性 CLI 测试 | `tests/test_check_consistency_cli.py` | 27 测试（四入口 + 子目录递归 + 混合原型 + category） |
