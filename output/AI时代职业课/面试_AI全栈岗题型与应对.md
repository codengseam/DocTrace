---
title: 工具八股、风险防御、Vibe Coding：AI 全栈岗的 3% 判断力
book: AI时代职业课
chapter: 面试
event: AI全栈岗题型与应对
sort: 12
chapter_sort: 1
created_at: 2026-06-29
source_agents:
- ai-expert
---

> 本篇为社区面经整理+应对策略，非官方真题。
> 本篇覆盖：AI全栈岗面试题型与应对，不覆盖：岗位现状/学习路径/段位划分（见对应岗位章）

# 工具八股、风险防御、Vibe Coding：AI 全栈岗的 3% 判断力

AI 全栈岗——也叫 Vibe Coding 岗、Agentic Engineering 岗——是 2026 年增长最快、定义最模糊的赛道。岗位的底层假设是：AI 包办了 97% 的样板代码，剩下 3% 是人的判断力。面试官想筛的，正是这 3%。本文按"工具八股—风险与规范—Vibe Coding 四阶段—评估维度—应对"五块拆解社区面经里的真实题型。

## 一、Cursor / Claude Code 八股：会配比会用值钱

以下题目整理自社区面经（来源：博客园 iOS 面试 cnblogs.com/huangzs/p/20711645；Interview Coder 28 题 interviewcoder.co/blog/claude-code-interview-questions；搜狐 Vibe Coding Agent 项目 sohu.com/a/1033744041_122073250；neonwatty Vibe Coding Interview neonwatty.com/posts/vibe-coding-interview-hire-ai-developers/）。

### 1.1 Cursor vs Claude Code 区别

招牌题。标准答法：Cursor 是 AI-first IDE，强项在文件级修改、行内补全、Tab 流；Claude Code 是 CLI 工具，强项在模块级理解、跨文件重构、终端原生集成。能讲清"什么时候用 Cursor、什么时候用 Claude Code"（小改动用 Cursor、大重构用 Claude Code）就过关。

### 1.2 配置文件：.claude/settings.json

这是 Claude Code 八股的高频题。要点：

- **全局 + 项目级**：全局配置在 `~/.claude/settings.json`，项目级在项目根目录的 `.claude/settings.json`，项目级覆盖全局。
- **permissions.allow 锁安全命令**：白名单式授权，把只读命令（`ls`、`cat`、`git status`）放 allow，危险命令不放。
- **permissions.deny 黑名单**：显式禁止 `rm -rf`、`git push --force`、`DROP TABLE` 等。

能讲清"为什么用 allow 白名单而不是 deny 黑名单"（黑名单永远列不全、白名单默认拒绝更安全）是加分项。

### 1.3 /plan mode：先思考再动手

社区面经里的共识："触及超过 2 个文件的改动，先 /plan。" /plan mode 让 Claude 先输出方案、不直接改代码，人 review 后再执行。这是判断"会用 AI"和"被 AI 用"的分水岭。

### 1.4 Hooks：PreToolUse 拦截危险命令

Hooks 是 Claude Code 的生命周期钩子，PreToolUse 在工具执行前触发。经典用法：

- 拦截 `rm -rf`：PreToolUse 检测 Bash 命令包含 `rm -rf` 直接 deny
- 拦截 `git push --force`：保护远端历史
- 拦截 `DROP TABLE`：保护数据库

能现场写一个 PreToolUse hook 阻止危险命令，是 AI 全栈岗的招牌实操题。

### 1.5 MCP 协议：连接 LLM 与外部工具

MCP（Model Context Protocol）类比"AI 工具调用的 USB-C"，标准化 LLM 与外部工具的连接。常见 MCP server：Notion（文档）、Postgres（数据库）、browser（浏览器自动化）。能讲清"为什么需要 MCP"（每个工具单独写 adapter 太碎、MCP 统一接口）就够。

### 1.6 Slash Commands：自定义命令

`.claude/commands/` 下的 md 文件，文件名即命令名。例如 `.claude/commands/ship.md` 定义 `/ship` 命令，内容是一串"lint → build → test → commit → push"的流程。能讲清"什么时候用 slash command 而不是直接对话"（重复流程固化成命令、团队共享）是工程意识。

### 1.7 Subagent：独立上下文并行

Subagent 是 Claude Code 的并行执行单元，有独立上下文、可隔离、可并行。典型用法：主 agent 拆任务、subagent 分头执行、主 agent 汇总。能讲清"什么时候用 subagent"（独立子任务、避免上下文污染）是加分项。

### 1.8 CLAUDE.md / .cursorrules：项目宪法

CLAUDE.md（Claude Code）和 .cursorrules（Cursor）是项目级规则文件，告诉 AI：

- 技术栈版本（如 Swift 5.9）
- 架构模式（MVVM / Clean Architecture）
- 命名规范
- 禁改文件清单（如 `Sources/Auth/**` 禁止 AI 修改）

能讲清"为什么要写 CLAUDE.md"（AI 不知道项目约定、不写就会按通用风格改、破坏一致性）是 AI 全栈岗的入门门票。

## 二、AI 编程风险：能力退化、架构失控、安全漏洞

社区面经里的共识是——AI 编程不是银弹，三类风险必须正视：

### 2.1 能力退化

长期依赖 AI 写代码，工程师的基础能力（数据结构、算法、调试）会退化。面试官会问"你怎么防止自己退化"——标准答法：核心模块手写、AI 只做样板、定期做不依赖 AI的练习。

### 2.2 架构失控

AI 倾向于"加代码"而非"重构"，长期下来架构会腐化。对策：定期让 AI 做重构（不是加功能）、人 review 架构决策、用 CLAUDE.md 约束架构边界。

### 2.3 安全漏洞

AI 生成的代码常见三类漏洞：

- **SQL 注入**：AI 拼接 SQL 字符串而非参数化查询
- **XSS**：AI 直接 innerHTML 渲染用户输入
- **硬编码 key**：AI 把 API key 写进源码

对策：Code Review + SAST 扫描进 CI + 敏感模块禁 AI。

## 三、验证 AI 代码：三层防御

社区面经里的标准答法：

1. **单测**：正常 / 边界 / 异常三套用例，AI 生成代码后必须配测试
2. **Instruments 查内存泄漏**（iOS 场景）：Allocations / Leaks 看 retain cycle
3. **人工 Review 线程安全**：并发访问、锁、原子性，AI 容易漏

能讲清"为什么不能只靠单测"（单测测不出并发问题、内存问题、架构问题）是工程成熟度的体现。

## 四、团队规范：什么不能送 AI

社区面经里的红线：

- **核心鉴权 / 加密 / 支付**：禁止送外网 AI，必须私有化部署或人工写
- **私有化部署**：敏感项目用本地模型或私有化 Claude Code
- **.cursorignore**：排除敏感目录（如 `config/secrets/`、`.env`）

能讲清"怎么划分 AI 可改和不可改的边界"（按风险等级 + 按模块边界）是团队 leader 视角。

## 五、Vibe Coding 面试四阶段

neonwatty 提出的 Vibe Coding 面试框架（来源：neonwatty neonwatty.com/posts/vibe-coding-interview-hire-ai-developers/），已成为 2026 年 AI 全栈岗的标准流程：

### 5.1 Portfolio Review

看候选人过往项目：上线 App、GitHub 活跃度、PR 合并记录、hooks 配置、CI/CD。重点不是"做了什么"，而是"工程化程度"——有没有 CI、有没有测试、有没有 hooks 防御。

### 5.2 Take-Home

给一个真实小项目，限时完成。评估维度：速度 + 质量 + 真测试。陷阱是"速度快但没测试"——Vibe Coding 岗最怕这种"AI 包办但人没把关"的候选人。

### 5.3 Live Coding

1 小时内完成 scope（拆任务）→ build（实现）→ ship（部署）。重点观察候选人怎么跟 AI 协作：是直接接受 AI 输出，还是会 /plan、会 review、会改 prompt？

### 5.4 Session History Review

看候选人的 AI 协作历史（Claude Code session log、Cursor 对话记录）。评估：判断力、架构决策、是否主导而非全盘接受。这是四阶段里最狠的——你的 AI 协作习惯全暴露。

## 六、评估维度：六块能力

社区面经里反复出现的六块评估维度：

1. **架构思维**：AI 处理样板代码后，你聚焦什么？（应该是架构、边界、抽象）
2. **Scoping**：怎么把模糊需求拆成 AI 可执行的任务？
3. **速度 AND 质量**：不是二选一，是要两者都要
4. **测试纪律**：AI 生成代码后必配测试，没有例外
5. **沟通与 Prompt 质量**：prompt 写得好不好，直接决定 AI 输出质量
6. **Review 证据**：能不能拿出"我 review 了 AI 的什么、改了什么、为什么"的证据

## 七、字节/阿里新增 AI 协作面试环节

2026 年字节、阿里等大厂在 AI 全栈岗面试里新增"AI 协作环节"（来源：牛客）：给候选人一个 Codex / Claude Code 环境，限时完成一个真实任务，考的不是"做没做出来"，而是"怎么跟 AI 协作"——会不会 /plan、会不会 review、会不会改 prompt、会不会在 AI 错的时候及时纠偏。

社区面经里有个说法（来源：牛客）："AI 包办 97% 编码，考剩下 3% 判断力。" 这 3% 包括：

- 架构决策（用不用某个抽象、加不加某个层）
- 边界识别（AI 改到这里要停，再改就破坏封装）
- 风险预判（这段 AI 生成的代码上线会不会出事）
- 业务对齐（AI 不知道的业务约束，人要补上）

## 八、Claude Code 工程能力清单

社区面经里流传一份"Claude Code 工程能力清单"（来源：小林MewCode），是 AI 全栈岗的"考点大纲"：

- 终端交互
- 6 大编程工具（Read/Edit/Write/Glob/Grep/Bash）
- Agent Loop（ReAct 循环）
- MCP 接入
- Skill 系统
- Slash Command
- Hook 生命周期（PreToolUse / PostToolUse / Stop）
- 5 层权限防御（settings / permissions / hooks / subagent / 人 review）
- 上下文压缩
- 跨会话记忆
- SubAgent 分发
- Git Worktree 并行
- Agent Teams（多 agent 协作）

不必全会，但每块都要知道"它解决什么问题、什么时候用"。面试官追问"你用过哪些"时，能讲 3-5 个有深度的使用案例，比泛泛说"我都用过"值钱。

## 九、应对策略：fluency + 场景题 + 安全边界

### 9.1 展示真实 fluency

AI 全栈岗最怕"ChatGPT 聊天型"候选人——只会对话框里贴需求、复制粘贴。要展示的是"驱动 Agent"的 fluency：

- 会不会用 /plan 先拆任务
- 会不会用 subagent 并行
- 会不会写 slash command 固化流程
- 会不会配 hooks 防御危险命令
- 会不会用 CLAUDE.md 约束 AI 行为

准备时录一段自己的 AI 协作过程，面试时直接展示，比说一百句"我熟练"有用。

### 9.2 场景题：现场重构 + hook 设计

两类高频场景题：

- **现场重构 auth flow**：给一段 AI 生成的 auth 代码，让你 review 出问题（常见：硬编码 token、没有 refresh、并发竞争）并重构
- **设计阻止危险命令的 hook**：现场写 PreToolUse hook，阻止 `rm -rf` / `git push --force` / `DROP TABLE`

准备时把这两类练熟，面试时直接动手。

### 9.3 安全边界意识

AI 全栈岗的"灵魂题"是"什么不能交给 AI"。标准答法按风险分层：

- **不可交给 AI**：鉴权、加密、支付、合规逻辑——必须人写或私有化部署
- **可交给 AI 但必须人 review**：业务逻辑、API 层、数据层
- **可完全交给 AI**：样板代码、CRUD、UI 组件、测试用例

能讲清"为什么这么分层"（风险等级 × 业务影响 × AI 出错概率）是 leader 视角。

---

AI 全栈岗的面试，本质是在筛"AI 包办 97% 后还能守住剩下 3% 判断力"的人。工具八股是门票，风险意识是底线，Vibe Coding 四阶段是分水岭，3% 判断力才是 offer 的决定因素。把"驱动 Agent 的 fluency + 安全边界意识 + 真实协作证据"练成习惯，再去投简历。

> 信息截止：2026-06
