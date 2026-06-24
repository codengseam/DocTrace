# 开发自检 Checklist

本 checklist 用于开发完成后的自检。配合 `.trae/rules/dev-workflow.md` 第四步使用，也可由 `.trae/skills/dev-selfcheck/SKILL.md` 触发。

**使用方式**：逐项检查，标注 ✅ 通过 / ❌ 未通过 / ➖ 不适用。未通过项必须修复或说明原因。

---

## 一、代码质量

- [ ] 代码通过 lint 检查（如有配置）
- [ ] 代码通过 typecheck（如有配置，如 `mypy` / `pyright`）
- [ ] 无明显死代码、未使用的 import、未使用的变量
- [ ] 无硬编码的密钥、路径、URL（应走配置或环境变量）
- [ ] 异常处理合理：不吞异常、不裸 `except`、边界场景有覆盖
- [ ] 函数/类/模块职责单一，未出现"上帝对象"
- [ ] 命名清晰，无 `temp` / `foo` / `data2` 这类模糊命名

## 二、项目规范遵循

- [ ] 遵循现有目录结构（见 README §七），未在根目录乱放文件
- [ ] 文件命名遵循规范：Python 用 `snake_case`，Markdown 用中文或下划线
- [ ] 未破坏 `.trae/skills/deep-reading/SKILL.md` 的行为
- [ ] 未破坏 `.trae/rules/rules.md`（讲书笔记写作规则）
- [ ] 未破坏 `prompts/` 下 7 份讲书提示词
- [ ] 未破坏 `src/utils/quality.py` 的检测逻辑
- [ ] 若修改了 `.trae/rules/rules.md`，已运行 `python scripts/sync_rules.py` 同步到 `RULES.md`
- [ ] 提交前已运行 `python scripts/check_duplicates.py`，`output/` 目录无重复 Markdown 文件

## 三、测试

- [ ] 新功能有对应的单元测试
- [ ] 修改现有逻辑后，相关测试已更新
- [ ] 运行 `pytest` 全部通过（或明确说明跳过原因）
- [ ] 运行 `python scripts/check_book_structure.py --output output --strict`，P0/P1/P2 全部清零（合并前必须完成）
- [ ] 边界场景有覆盖：空输入、超长输入、非法路径、并发等
- [ ] Mock 模式（`DEEP_READING_MOCK=1`）下端到端流程能跑通
- [ ] 修复了会复发的代码/数据 bug 时，已补充回归测试或更新 `tests/bug_regression_list.md`

## 四、依赖与配置

- [ ] 未引入未声明的新依赖（若引入，已更新 `requirements.txt`）
- [ ] 未引入未声明的 MCP 服务器（若引入，已更新 `config.yaml` 的 `mcp_servers`）
- [ ] 新增配置项已加入 `config.yaml` 和 `.env.example`
- [ ] 新增的可信搜索域已加入 `config.yaml` 的 `trusted_domains`

## 五、文档

- [ ] README.md 是否需要更新（新功能、新命令、新目录）
- [ ] 新增的 Skill / 规则文件 / checklist 是否需要在 README 中登记
- [ ] 重要的设计决策是否记录在 `docs/` 下
- [ ] API 变更是否更新了相关文档

## 六、Trae Skill 边界（新增/修改 Skill 时检查）

- [ ] Skill 文件未声称能"调度 sub-agents"或"直接调用 MCP tools"（Skill 做不到）
- [ ] Skill 需要真并行时，已改为触发 Python 脚本（路径 B）
- [ ] Skill 的触发条件清晰、不与现有 Skill 重叠
- [ ] Skill 与 `.trae/rules/dev-workflow.md` 声明的边界一致

## 七、LoopAgent 沉淀（每次开发完成后必做）

- [ ] 本次改动是否暴露了新的共性问题？
- [ ] 是否需要更新 `.trae/rules/` 下的规则文件？
- [ ] 是否需要更新 `src/utils/quality.py` 的检测项？
- [ ] 是否需要更新本 checklist（`dev-checklist.md`）？
- [ ] 是否需要在 `docs/loop_log.md` 追加一条开发沉淀记录？
- [ ] 若修复了历史遗留 bug，是否已记录到 `tests/bug_regression_list.md` 并更新频次？
- [ ] 本次无新沉淀时，明确说明"本次无新沉淀"

---

## 自检报告模板

```
## 自检报告

### 一、代码质量
- ✅/❌ lint：____
- ✅/❌ typecheck：____
- ...

### 二、项目规范遵循
- ...

### 三、测试
- pytest 结果：____
- ...

### 四、依赖与配置
- ...

### 五、文档
- ...

### 六、Trae Skill 边界
- ...

### 七、LoopAgent 沉淀
- 新共性问题：____
- 规则更新：____
- checklist 更新：____
- loop_log 追加：____

### 总结
- 通过项：__ / 总项数 __
- 未通过项及处理：____
```
