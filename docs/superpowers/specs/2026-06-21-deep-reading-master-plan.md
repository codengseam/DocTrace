# 个人 AI 深度阅读助手 — 总计划

## 1. 项目目标

实现一个 Agent 专家团工作流：用户用自然语言输入阅读内容 → Orchestrator 解析并分配任务 → 多个 Specialist Agent 并行研究 → Editor 汇总润色 → 输出 Markdown 讲书笔记 → 最终进入 Obsidian 知识库并通过 HTML 管理界面展示。

核心原则：可信、深刻、人本、本地优先、不做 RAG、不向量化、不存储整书。

## 2. 全局架构

```
用户输入（Trae / 命令行 / Web）
        │
        ▼
┌───────────────────┐
│   Orchestrator    │  解析输入，确认输出路径，分配任务
│    （调度专家）    │
└─────────┬─────────┘
          │
    ┌─────┼─────┬─────────┐
    ▼     ▼     ▼         ▼
  史料   人物   背景     名家    悟道
  专家   专家   专家     专家    专家
    └─────┬─────┘         │
          ▼               ▼
    ┌─────────────────────────┐
    │   Editor（编辑专家）     │  汇总、润色、统一风格、检查引用
    └───────────┬─────────────┘
                ▼
        Markdown 文件
    output/{书名}/{章节}_{事件}.md
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
Obsidian    HTML 管理     PDF/Web 资料
Vault       界面          （可选输入）
```

## 3. 四个并行轨道

| 轨道 | 名称 | 核心交付 | 推荐执行环境 |
|---|---|---|---|
| 轨道 1 | 核心引擎 | LangGraph 工作流 + 6 个 Agent + Markdown 生成 | 云端/本地 Python |
| 轨道 2 | 工具与存储层 | MCP 接入、Obsidian 写入、文件管理、资料白名单 | 本地 |
| 轨道 3 | Trae Skill 入口 | `.trae/skills/deep-reading/` 交互入口 | 本地 Trae |
| 轨道 4 | Web 管理界面 | HTML + CSS + JS 本地管理界面 | 本地/云端 |

## 4. 跨轨道接口契约（必须提前约定）

| 契约项 | 约定 |
|---|---|
| 输出文件路径 | `output/{书名}/{章节}_{事件}.md` |
| 文件名规范 | 纯中文，`{章节}_{事件}.md` |
| Markdown frontmatter | 必须包含 `title`、`book`、`chapter`、`event`、`created_at`、`source_agents` |
| 正文结构 | 严格按照 RULES.md：讲事情 → 讲人物 → 讲背景 → 讲道理 → 问道悟道 → 结语 |
| Specialist 输出格式 | 每个 Agent 输出带 `section` 标记的文本块，Editor 按标记拼装 |
| 配置文件 | `.env` 存 API Key；`config.yaml` 存模型、输出路径、可信域白名单 |
| 日志规范 | 每个 Agent 输出思考过程到 `logs/YYYY-MM-DD_HH-MM-SS_{event}.log` |
| 用户输入兼容性 | Orchestrator 必须支持：一句话、只有书名、书名+章节、书名+章节+事件等多种形式 |

## 5. 实施原则

- **多 Agent 专家团**：每个 Specialist 是一个独立 Agent，有专属 Prompt 和角色约束。
- **测试驱动**：每个 Agent、每个转换节点都要有单元测试或输出格式校验。
- **质量检查**：生成后自动检查结构完整性、引用真实性、AI 味句式、中英文混杂。
- **迭代优化**：Editor 汇总后，如检查不通过，触发修订 Agent 二次生成。

## 6. 验收标准（总）

- [ ] 输入 `python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法` 能生成符合 RULES.md 的 Markdown。
- [ ] 用户输入自然语言（如"我刚读完资治通鉴周纪二商鞅变法"）也能被正确解析并生成。
- [ ] 文件保存路径正确，frontmatter 完整。
- [ ] 各 Specialist Agent 输出可被 Editor 正确汇总。
- [ ] 支持通过 Trae Skill 触发。
- [ ] HTML 界面能按书/章节分类展示已生成笔记。
- [ ] Obsidian MCP 能自动写入 Vault。

## 7. 子计划间依赖图

```
子计划 1：核心引擎  ──┬──→ 子计划 2：工具与存储
                    ├──→ 子计划 3：Trae Skill
                    └──→ 子计划 4：Web 界面
```

**关键路径**：子计划 1 必须先完成或至少约定好输出契约，其他子计划才能并行启动。

## 8. 风险管理

| 风险 | 应对 |
|---|---|
| Agent 输出质量不稳定 | 每个 Specialist 有独立 Prompt + 示例；Editor 做质量检查；不通过则修订 |
| 名家点评编造 | 只引用明确出处；检查 Agent 不通过则要求提供原文上下文 |
| 文件路径/编码问题 | 统一用 UTF-8，路径用 pathlib |
| 多窗口并行时接口不一致 | 严格执行 frontmatter 和 Agent 输出格式契约 |
| 用户输入形式多样 | Orchestrator 使用 LLM 做意图识别和槽位填充，fallback 到交互式询问 |

## 9. 文档清单

- [总计划](./2026-06-21-deep-reading-master-plan.md)
- [子计划 1：核心引擎](./2026-06-21-track-01-core-engine.md)
- [子计划 2：工具与存储层](./2026-06-21-track-02-tools-storage.md)
- [子计划 3：Trae Skill 入口](./2026-06-21-track-03-trae-skill.md)
- [子计划 4：Web 管理界面](./2026-06-21-track-04-web-interface.md)
