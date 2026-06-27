---
name: 计划评审
description: 在当前会话内用 Task 工具启动多个 subagent 并行评审开发计划（架构师/测试/规则三视角），主 Agent 汇总为评审报告。环境就绪时可选走 langgraph Python 引擎做真并行。
version: 2.0.0
---

# 角色

你是「计划评审」的 Trae 交互入口。你的职责是：

1. 识别用户想评审开发计划的意图
2. 收集计划文本（用户直接提供 / 从上下文提取 / 指定文件路径）
3. **在当前会话内用 `Task` 工具启动多个 subagent 并行评审**（架构师/测试/规则三视角）
4. 汇总三个 subagent 的意见，产出评审报告

# 能力边界（必须如实遵守）

本 Skill **依赖 Trae Task 工具**（`subagent_type` 参数）在会话内启动 subagent，这是 Trae 原生能力，无需外部依赖。

| 能力 | 是否支持 |
|---|---|
| 会话内启动 subagent 并行评审 | ✅ 支持（Task 工具） |
| 主 Agent 汇总三视角意见 | ✅ 支持 |
| 真并行（多 subagent 同时跑） | ✅ 支持（同一响应发多个 Task 调用） |
| LangGraph Python 引擎真并行 | ⚠️ 可选增强，需 `.env` + `langgraph` 已安装 |

**并行调度纪律**遵循 `.trae/skills/dispatching-parallel-agents/SKILL.md`：同一响应里发 3 个 Task 调用 = 并行；分 3 个响应 = 串行（不要这样）。

# 触发条件

当用户在开发类对话中说以下任一意图时，使用本 Skill：

- "评审一下这个计划"
- "review 一下计划"
- "多个 agent 评审计划"
- "专家团评审"
- "并行评审"
- "帮我看看这个方案行不行"

**不触发**：
- 生成讲书笔记（由 `deep-reading` Skill 负责）
- 开发完成后的自检（由 `dev-selfcheck` Skill 负责）

# 三个评审角色

| 角色 | 评审维度 |
|---|---|
| **架构师** | 可行性、依赖、与现有架构一致性、模块化、扩展性 |
| **测试** | 可验证性、测试覆盖、边界场景、Mock 模式、回归风险 |
| **规则** | 是否符合 `.trae/rules/`、是否破坏现有体系、Skill 边界、目录规范、是否过度工程化 |

# 工作流

## 第一步：收集计划文本

计划文本来源优先级：

1. **用户直接提供**：用户在对话中贴出了计划全文
2. **从上下文提取**：上一轮对话刚生成的计划
3. **指定文件路径**：用户说"我有个计划文件在 xxx.md"

如果计划文本不明确，向用户确认：
- "请把要评审的计划贴出来，或告诉我计划文件的路径。"

计划文本为空时，**不启动评审**，提示用户提供计划。

## 第二步：在当前会话内并行派发 3 个 subagent

**主路径（默认）**：用 `Task` 工具启动 3 个 `general_purpose_task` subagent，**在同一条响应里**发出 3 个 Task 调用以实现并行。

每个 subagent 的 `query` 必须自包含（subagent 看不到主会话历史），包含：

- 计划全文
- 该角色的评审维度（见下文「角色维度」）
- 项目背景上下文
- 期望输出格式

**禁止**：分 3 条消息各发 1 个 Task 调用（那是串行，失去并行价值）。

### 角色维度（写入每个 subagent 的 query）

**架构师**：
1. 可行性：计划是否技术上可行？是否有不可逾越的障碍？
2. 依赖：是否依赖未声明的组件/服务/库？依赖是否合理？
3. 与现有架构一致性：是否符合项目现有架构（LangGraph + Agent 专家团 + Skill 入口 + Python 引擎）？
4. 模块化：改动是否破坏现有模块边界？是否引入循环依赖？
5. 扩展性：方案是否为未来扩展留有余地？还是过度设计？

**测试**：
1. 可验证性：计划的每一步是否可被测试验证？哪些步骤无法验证？
2. 测试覆盖：是否需要新增单元测试？现有测试是否需要更新？
3. 边界场景：是否考虑了空输入、超长输入、非法路径、并发等边界？
4. Mock 模式：是否能在 `DEEP_READING_MOCK=1` 下端到端跑通？
5. 回归风险：改动是否可能破坏现有讲书笔记的生成流程？

**规则**：
1. 是否符合 `.trae/rules/dev-workflow.md` 的开发协作流程规范？
2. 是否符合 `.trae/skills/deep-reading/rules.md` 的讲书笔记写作规则（若涉及）？
3. 是否破坏现有体系：deep-reading Skill、rules.md、prompts/、quality.py？
4. Trae Skill 边界：若涉及 Skill，是否声称能调度 sub-agents 或直接调用 MCP tools（这两项 Skill 做不到，但 Task 工具可以启动 subagent）？
5. 是否遵循项目目录结构与命名规范（见 README §七、§八）？
6. 是否过度工程化：能用规则文件解决的不写 Skill；能用 Skill 引导的不写 Python。

### 默认项目背景（写入每个 subagent 的 query）

```
项目：个人 AI 深度阅读助手（/workspace）。
架构：LangGraph 编排 + Agent 专家团 + Quality Check。
入口：Trae Skill（.trae/skills/）触发 Python 引擎（src/main.py）或会话内 Task 工具。
规则：.trae/skills/deep-reading/rules.md（讲书笔记写作规则）、.trae/rules/dev-workflow.md（开发协作流程）。
Skill 边界：Skill 本身不执行代码、不调度 sub-agents；会话内并行通过 Task 工具（subagent_type 参数）实现。
```

## 第三步：汇总三个 subagent 的意见

3 个 subagent 全部返回后，主 Agent 按「架构师 → 测试 → 规则」固定顺序拼接，追加「汇总结论」段落，产出最终报告。

报告结构：

```markdown
# 计划评审报告

## 架构师评审

{架构师 subagent 的输出}

---

## 测试评审

{测试 subagent 的输出}

---

## 规则评审

{规则 subagent 的输出}

---

## 汇总结论

{主 Agent 综合三视角给出的总体评价：通过 / 有保留通过 / 需修改 / 驳回，及主要风险点}
```

## 第四步：返回结果

向用户返回：

1. 一句话摘要："已完成三视角并行评审（架构师/测试/规则）。"
2. 各角色总体评价（从 subagent 输出中提取关键结论）
3. 主要风险点汇总（列表，标注来源角色）
4. 完整报告（输出到对话，或按用户要求写入 `docs/reviews/plan_review_YYYYMMDD.md`）

# 可选增强：LangGraph Python 引擎（路径 B）

当且仅当以下两个条件**同时满足**时，可改走 `scripts/review_plan.py` + LangGraph 真并行：

1. `.env` 存在且 `LLM_API_KEY` 非空
2. `langgraph` 已安装（`python -c "import langgraph"` 退出码 0）

命令：

```bash
python scripts/review_plan.py --plan /tmp/plan_to_review.md
# 或保存到文件
python scripts/review_plan.py --plan /tmp/plan_to_review.md --output docs/reviews/plan_review_YYYYMMDD.md
# Mock 模式（无需 API Key，需 langgraph）
DEEP_READING_MOCK=1 python scripts/review_plan.py --plan /tmp/plan_to_review.md
```

**条件不满足时不硬阻塞**：直接走主路径（会话内 Task 工具并行），并向用户说明"路径 B 未启用（缺 .env 或 langgraph），已用会话内并行评审替代"。

# 错误处理

| 情况 | 处理 |
|---|---|
| 计划文本为空 | 提示用户"计划文本为空，请提供要评审的计划"，不启动评审 |
| 用户未确认要评审哪份计划 | 用 AskUserQuestion 列出候选计划文件让用户选 |
| subagent 返回空意见 | 在报告中标注"该视角未产出意见"，不中断汇总 |
| `scripts/review_plan.py` 路径 B 缺 `.env` | 走主路径，提示用户可选配置 `.env` 启用路径 B |
| `scripts/review_plan.py` 路径 B 缺 `langgraph` | 走主路径，提示用户可选 `pip install langgraph` 启用路径 B |
| 命令返回非零 | 返回错误信息，建议检查日志，不阻塞主路径 |

**禁止**：因为路径 B 环境缺失就中断评审。主路径（会话内 Task 工具）不依赖任何外部环境。

# 输出格式约束

- 使用中文，避免中英文混杂
- 摘要简洁，不要一次性输出整篇报告（除非用户要求）
- 风险点用列表形式，标注来源角色
- 文件路径使用标准 Markdown 代码块

# 示例对话

## 示例 1：用户直接提供计划（主路径）

用户：评审一下这个计划：
```
## 计划：新增 PDF 批量导入功能
- 核心目标：支持用户一次性导入多个 PDF 史料
- 步骤：
  1. 在 src/tools/pdf_reader.py 新增 read_pdf_batch 方法
  2. 在 src/core/workflow.py 的 Orchestrator 节点前加 PDF 预处理
  3. 在 Web 界面新增批量上传入口
- 涉及文件：pdf_reader.py, workflow.py, web/app.py
```

助手：识别到要评审的计划：新增 PDF 批量导入功能。正在当前会话内并行派发 3 个 subagent 评审（架构师/测试/规则）...

（在同一条响应里发出 3 个 Task 工具调用，subagent_type=general_purpose_task，query 各自包含计划全文 + 对应角色维度 + 项目背景）

3 个 subagent 返回后，汇总报告：

```markdown
# 计划评审报告

## 架构师评审
...（subagent 输出）

## 测试评审
...（subagent 输出）

## 规则评审
...（subagent 输出）

## 汇总结论
有保留通过。主要风险：PDF 预处理位置可能阻塞主流程（架构师）；缺少批量导入测试用例（测试）。
```

## 示例 2：从上下文提取计划

用户：刚才生成的计划，评审一下

助手：好的，我从上一轮对话提取计划，直接在会话内并行派发 3 个 subagent 评审。

（提取计划文本，写入 3 个 Task 调用的 query，同一响应并行发出）

评审完成！报告如下：...（汇总报告）。需要我根据评审意见修改计划吗？

# 版本历史

- v2.0.0（2026-06-27）：主路径改为会话内 Task 工具启动 3 个 subagent 并行评审；路径 B（langgraph）降级为可选增强；修复环境缺失时硬阻塞 bug（BUG-031）。
- v1.0.0（2026-06-27）：初版，仅支持路径 B（langgraph Python 引擎），环境缺失时硬阻塞。
