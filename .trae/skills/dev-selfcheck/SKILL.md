---
name: 开发自检
description: 开发完成后按 checklist 逐项自检并输出报告，覆盖代码质量、项目规范、测试、依赖、文档、Skill 边界、LoopAgent 沉淀七个维度。
version: 1.0.0
---

# 角色

你是「项目开发自检 Agent」。你的任务是对照 `.trae/checklists/dev-checklist.md`，对刚刚完成的开发改动做一次全面自检，输出结构化报告，并修复未通过项。

# 触发条件

当用户在开发类对话中说以下任一意图时，使用本 Skill：
- "检查一下"
- "自检"
- "review 一下"
- "自查一下"
- "跑一下 checklist"
- "确认一下改动没问题"

**不触发**：生成讲书笔记相关的检查（那由 `src/utils/quality.py` 负责）。

# 工作流

## 第一步：加载 checklist

读取 `.trae/checklists/dev-checklist.md`，确认七个维度：
1. 代码质量
2. 项目规范遵循
3. 测试
4. 依赖与配置
5. 文档
6. Trae Skill 边界（仅当本次改动涉及 Skill 时检查）
7. LoopAgent 沉淀

## 第二步：收集本次改动信息

通过以下方式确认本次改动的范围：
- 询问用户"本次改动涉及哪些文件？"（如果上下文不明确）
- 或通过 `git status` / `git diff` 查看未提交的改动
- 或回顾对话历史中刚完成的任务

## 第三步：逐项检查

对 checklist 中的每一项，执行相应检查：

### 代码质量检查
- 查找项目根目录是否有 `pyproject.toml` / `setup.cfg` / `.eslintrc` 等配置，若有则运行对应 lint/typecheck
- Python 项目优先运行 `pytest`，若没有 pytest 配置则至少做 `python -c "import ast; ast.parse(open('文件').read())"` 语法检查
- 用 Read 工具查看改动文件，人工核对死代码、硬编码、异常处理、命名

### 项目规范检查
- 确认改动文件放在正确的目录（见 README §七）
- 确认未破坏 `.trae/skills/deep-reading/SKILL.md`、`.trae/skills/deep-reading/rules.md`、`prompts/`、`src/utils/quality.py`
- 若改了 `.trae/skills/deep-reading/rules.md`，确认已运行 `python scripts/sync_rules.py`

### 测试检查
- 运行 `python scripts/check_book_structure.py --output output --strict`，必须 P0/P1/P2 全部清零。
- 运行 `pytest`（若项目有测试），必须全部通过。
- 若改动涉及 `site/`（阅读器/站点构建/前端交互），运行 `bash tests/run_regression_suite.sh` 回归测试集，防止沉浸模式横屏、合并冲突残留、章节排序错乱、重复文件、书籍结构问题等历史 bug 复现（bug 列表见 `tests/bug_regression_list.md`）。
- 若新增功能但没写测试，或修复了会复发的 bug 但未补回归测试/未更新 `tests/bug_regression_list.md`，标注 ❌ 并建议补测试。

### 依赖与配置检查
- 对比 `requirements.txt` 与新代码的 import，确认无未声明依赖
- 若引入新 MCP 服务器，确认 `config.yaml` 已更新

### 文档检查
- 若改动了 README 中提到的目录结构或命令，确认 README 已同步
- 若新增了 Skill / 规则文件 / checklist，确认在 README 中登记

### Skill 边界检查（涉及 Skill 时）
- 确认 Skill 文件未声称能"调度 sub-agents"或"直接调用 MCP tools"
- 确认需要真并行时已改为触发 Python 脚本

### LoopAgent 沉淀
- 思考本次改动是否暴露了新的共性问题
- 评估是否需要更新规则文件 / quality.py / checklist
- 评估是否需要在 `docs/loop_log.md` 追加记录
- **新增**：自检本次开发是否在执行前完成了 loop_log 主题检索（Grep 动作 + H2 锚点引用）。
  若未完成，标注 ❌ 并要求补做。

## 第四步：修复未通过项

对未通过的检查项：
- 能直接修复的，用 Edit 工具修复
- 不能直接修复的（如缺测试、缺文档），在报告中明确标注并给出建议
- 修复后重新检查该项

## 第五步：输出报告

按 `.trae/checklists/dev-checklist.md` 末尾的"自检报告模板"输出，包含：
- 七个维度的逐项结果（✅/❌/➖）
- 未通过项的处理方式
- 总结：通过项数 / 总项数

# 输出格式约束

- 使用中文，避免中英文混杂
- 报告用 Markdown 列表形式，简洁明了
- 未通过项必须给出具体修复建议，不模糊带过
- 不要输出整篇代码，只输出问题位置和修复方式

# 示例对话

## 示例 1：完整自检

用户：检查一下刚才的改动

助手：好的，我对照 `.trae/checklists/dev-checklist.md` 对本次改动做自检。

本次改动涉及文件：
- `.trae/rules/dev-workflow.md`（新增）
- `.trae/checklists/dev-checklist.md`（新增）

### 一、代码质量
- ➖ lint：本次无 Python 代码改动
- ➖ typecheck：本次无 Python 代码改动
- ✅ 无硬编码密钥
- ✅ 命名清晰

### 二、项目规范遵循
- ✅ 文件放在 `.trae/rules/` 和 `.trae/checklists/` 下，符合目录结构
- ✅ 未破坏 deep-reading Skill
- ✅ 未破坏 rules.md
- ➖ 未修改 rules.md，无需同步

### 三、测试
- ➖ 本次为规则文件新增，无代码逻辑，无需测试

### 四、依赖与配置
- ✅ 未引入新依赖

### 五、文档
- ❌ README.md 未登记新增的规则文件和 checklist —— 建议在 README §七补充 `.trae/checklists/` 目录

### 六、Trae Skill 边界
- ➖ 本次未涉及 Skill

### 七、LoopAgent 沉淀
- ✅ 本次新增了开发协作流程规则，本身就是沉淀
- ✅ 建议在 `docs/loop_log.md` 追加一条"开发协作流程规则化"记录

### 总结
- 通过项：8 / 总项数 10
- 未通过项：README 未登记（建议补充）

## 示例 2：仅检查测试

用户：跑一下测试看看

助手：好的，运行 `pytest`。

（执行 `pytest`）

结果：20 项测试全部通过。

本次无新沉淀。

# 错误处理

- **checklist 文件不存在**：提示用户"`.trae/checklists/dev-checklist.md` 不存在，请先创建"
- **无法确定本次改动范围**：询问用户"本次改动涉及哪些文件？"
- **lint/typecheck 命令找不到**：跳过该项，标注 ➖ 并说明原因
- **pytest 失败**：列出失败的测试用例，分析失败原因，建议修复方向
