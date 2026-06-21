# 子计划 1：核心引擎（LangGraph + Agent 专家团）

## 上下文

本项目是个人 AI 深度阅读助手，目标是让用户输入一段阅读内容后，自动生成 Markdown 讲书笔记。核心引擎是整个系统的关键路径，其他子计划都依赖它生成的 Markdown 文件格式。

详见：
- [总计划](./2026-06-21-deep-reading-master-plan.md)
- [RULES.md](../../../../RULES.md)
- [README.md](../../../../README.md)

## 目标

实现整个 Agent 工作流的核心：Orchestrator + 5 个 Specialist + Editor，输出 Markdown。

## 范围

1. 搭建项目骨架
   - `src/agents/`：各 Agent 定义
   - `src/core/`：LangGraph 工作流编排
   - `src/utils/`：公共工具（配置加载、日志、Markdown 渲染）
   - `prompts/`：Agent Prompt 文件
   - `templates/`：Markdown 输出模板
   - `tests/`：单元测试
   - `output/`：生成的笔记目录
   - `logs/`：运行日志

2. 实现 Orchestrator Agent
   - 接收用户输入（自然语言、CLI 参数均可）
   - 支持多种形式：
     - 一句话："我刚读完资治通鉴周纪二商鞅变法"
     - 只有书名："资治通鉴"
     - 书名+章节："资治通鉴 周纪二"
     - 完整信息："资治通鉴 周纪二 商鞅变法"
   - 当信息不足时，以交互方式询问用户
   - 输出：规范化的 `book`、`chapter`、`event`、`output_path`

3. 实现 5 个 Specialist Agent
   - `historian.py`：史料专家，负责"讲事情"
   - `biographer.py`：人物专家，负责"讲人物"
   - `context_analyst.py`：背景专家，负责"讲背景"
   - `critic.py`：名家专家，负责"讲道理"
   - `philosopher.py`：悟道专家，负责"问道悟道"
   - 每个 Agent 读取对应 Prompt 文件，输出带 `section` 标记的内容

4. 实现 Editor Agent
   - 汇总 5 段 Specialist 输出
   - 统一语气、补齐引用、生成结语
   - 输出完整 Markdown（含 frontmatter）

5. 使用 LangGraph 编排
   - Orchestrator → 并行 Specialist → Editor → 输出
   - 支持 checkpoint 和重试

6. 实现 Markdown 保存
   - 路径：`output/{书名}/{章节}_{事件}.md`
   - 文件名纯中文

7. 实现基础质量检查
   - 结构完整性：5 段 + 结语
   - frontmatter 完整性
   - AI 味句式检查
   - 中英文混杂检查
   - 引用格式检查

## 依赖

- 无（本轨道不依赖 MCP、Web、Skill）
- 其他轨道依赖本轨道的输出格式

## 输入输出

- 输入：
  - CLI：`python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法`
  - 自然语言：`python src/main.py --input "我刚读完资治通鉴周纪二商鞅变法"`
- 输出：
  - `output/{书名}/{章节}_{事件}.md`
  - `logs/YYYY-MM-DD_HH-MM-SS_{event}.log`

## 关键设计决策

- 使用 LangGraph 作为编排框架。
- Specialist Agent 输出统一格式：每个 Agent 返回 `{"section": "...", "content": "...", "sources": [...]}`。
- Orchestrator 使用 LLM 做意图识别 + 槽位填充，fallback 到交互式询问。
- Editor 不负责查资料，只负责润色、拼接、检查、生成结语。
- 质量检查不通过时，触发修订 Agent 针对性修改，而不是从头生成。

## 验收标准

- [ ] 能成功运行 `python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法`
- [ ] 能成功运行自然语言输入并正确解析
- [ ] 输出 Markdown 包含完整 5 段 + 结语
- [ ] 每个 Specialist 有独立 Prompt 文件
- [ ] Editor 能汇总并润色
- [ ] 有基础单元测试覆盖 Agent 输出格式
- [ ] 质量检查能识别常见 AI 味句式和结构缺失

## 建议执行方式

可在云端 AI 环境完成，因为主要是 Python + LLM 调用。完成后需本地验证文件保存和路径处理。
