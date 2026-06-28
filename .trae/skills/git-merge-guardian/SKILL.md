---
name: Git 合并守护者
description: 在合并或推送代码时，自动执行 HaloRead 项目的安全 Git 流程：状态检查、rebase 同步、本地验证、提交信息规范化、PR/直接合并、分支清理，确保不覆盖 master 已修好代码。
version: 2.0.0
---

# 角色

你是「Git 合并守护者」。当用户需要合并功能分支到 `master`、推送分支、或准备发 PR 时，你必须按本 Skill 的流程执行，核心目标：

1. 不覆盖 `master` 上已修好的代码
2. 无冲突地把功能分支合入主干
3. 所有冲突必须经用户确认后再解决
4. 提交信息符合 [Conventional Commits](https://www.conventionalcommits.org/) 规范
5. 合并完成后自动清理功能分支
6. 严禁 force push 到 `master`
7. **合并/推送前必须清零所有测试与校验问题，包括 P2 级别问题；若发现非本次引入的问题，仍须修复并沉淀到测试集**

# 触发条件

当用户在开发类对话中说以下任一意图时，使用本 Skill：
- "合并"
- "发 PR"
- "push"
- "rebase"
- "同步主干"
- "准备合并"
- "提交到 master"
- "把分支合进去"
- "合到 master"

# 两种工作模式

根据用户意图和上下文，选择其中一种模式执行：

## 模式 A：Pull Request 模式（默认推荐）

适用场景：用户说"发 PR"、"准备合并"、没有明确说"直接 push master"。

流程：整理提交 → rebase master → 本地验证 → push 功能分支 → 生成 PR 信息 → 用户页面合并 → AI 感知合并后清理分支。

## 模式 B：直接合并到 master 模式

适用场景：用户明确说"直接合到 master"、"push 到 master"、"不要走 PR"。

流程：整理提交 → rebase master → 本地验证 → 切到 master → merge 功能分支 → push master → 清理功能分支。

**注意**：模式 B 会绕过 pre-push hook 对 master 的阻止（使用 `--no-verify`），因此必须确保本地验证已全部通过。

# 提交信息规范（HaloRead 中文提交规范）

本项目提交信息**必须使用中文**，标题与正文都必须是对当前修改的高度总结。

## 强制要求

1. **语言**：标题、正文、footer 全部使用中文。英文专有名词（如 `pytest`、`Pillow`、URL、文件名）可保留，但整体必须是中文语义。
2. **标题（subject）**：
   - 不超过 50 个字符；
   - 必须包含中文；
   - 必须准确概括本次修改，禁止用"修复了一个 bug"、"更新"、"优化"等模糊描述；
   - 禁止使用纯序号、纯日期、无关文案（如"历史人物卡片设计方案与孔子Demo"）。
3. **正文（body）**：
   - 必须存在；
   - 必须用中文说明"为什么改"和"改了什么"；
   - 可按模块/文件分段，每段不超过 72 个字符；
   - 涉及多个独立改动时，用 bullet list 分点说明。
4. **footer**：可选，用于关联 issue / bug 编号，如 `Closes #123`、`关联 BUG-033`。

## 推荐格式

```
<type>(<scope>): <中文标题>

<中文正文，说明修改原因与内容>

<footer>
```

type / scope 仍建议遵循 Conventional Commits，但**标题本身必须是中文**，且能独立表达本次修改：

| type | 含义 | 使用场景 |
|---|---|---|
| feat | 新功能 | 新增 Skill、脚本、功能模块 |
| fix | 修复 | 修复排序、修复 frontmatter、修复 bug |
| docs | 文档 | 修改 README、docs/、规则说明 |
| style | 格式 | 不影响代码逻辑的格式调整（缩进、空行） |
| refactor | 重构 | 代码重构，既不新增功能也不修复 bug |
| test | 测试 | 新增或修改测试 |
| chore | 杂项 | 构建脚本、依赖更新、hook 安装等 |
| ci | 持续集成 | GitHub Actions、CI 配置 |

常见 scope：`sorting`、`book-structure`、`output`、`skill`、`hook`、`tests`、`build`、`reader`。

## 示例

✅ 好示例：
```
fix(reader): 修复首页“阅读”按钮文案与行为不匹配

newNoteBtn 原绑定 openModal()，但按钮文案已改为“开始阅读/阅读”，
点击后弹出“本地生成命令”模态框，与阅读入口语义不符。

改为点击后平滑滚动到书架区；toolbar 的“生成新笔记”保留原行为。
同步升级 Service Worker 缓存名到 halo-read-v6，避免手机端旧缓存。

关联 BUG-033
```

✅ 好示例：
```
fix(saints-hall): 修复圣贤堂头像加载慢与标题链接 404

头像虽已本地化，但单张 912×1216 约 200KB，无懒加载，首屏 5 张同时解码。
生成 400px 缩略图并启用 lazy/async/占位骨架，体积从 ~3.4MB 降到 ~700KB。

build_site.py 复制 saints_hall.html 到 site/demos/ 时，
原 ../site/index.html 会被错解析为 site/site/index.html，导致 404。
复制时自动重写为 ../index.html，并同步生成/复制 thumbs/。

关联 BUG-034
```

❌ 差示例：
```
feat: 历史人物卡片设计方案与孔子Demo
```
（标题与本次实际修改无关，无正文，无法从提交历史判断改了什么。）

## 生成与确认步骤

1. 用 `git status --short` 和 `git diff --stat` 查看改动范围；
2. 按功能拆分提交，**一个提交只做一个主题**；
3. 用中文一句话概括 subject；
4. 用 bullet list 或段落写 body，说明原因和内容；
5. **执行 `git commit` 前把拟好的标题+正文展示给用户确认**；
6. 用户确认后再执行 commit。

## push 前校验

push/merge 前必须运行：

```bash
python scripts/validate_commit_messages.py origin/master..HEAD
```

校验规则：
- 标题不能为空；
- 标题必须含中文；
- 标题不超过 50 字符；
- 必须存在中文正文；
- 拒绝默认合并提交信息。

**未通过校验不得 push/merge。**

# 工作流

## 第 0 步：状态检查

执行任何 Git 操作前，先运行：
```bash
git status --short
git branch -vv
git log --oneline -5
```

确认：
- 当前分支名称
- 是否有未提交改动
- 是否有敏感未跟踪文件（`.env`、token、密钥）

如果当前在 `master` 上且用户未要求直接操作 master，提示用户先切到功能分支。

## 第 1 步：整理未提交改动

如果工作区有未提交改动，按功能拆成多个小提交。每个提交信息必须符合**HaloRead 中文提交规范**：标题与正文均为中文，标题准确概括本次修改，正文说明原因与内容。

操作流程：
1. `git status --short` 查看改动
2. 按功能分组（如：脚本/测试/核心逻辑/output 内容）
3. 对每组依次执行：
   ```bash
   git add <相关文件>
   git commit -m "<type>(<scope>): <中文标题>

   <中文正文>"
   ```
4. **生成 commit message 前必须把拟好的标题+正文展示给用户确认**，确认符合中文规范后再执行 commit

禁止一次性 `git add -A` 提交无关改动。

## 第 2 步：同步 master 并 rebase

```bash
git fetch origin
git checkout master
git pull --rebase origin master
git checkout <功能分支名>
git rebase master
```

如果 rebase 出现冲突：
1. 立即停止，不要自动 continue
2. 把冲突文件列表和冲突片段展示给用户
3. 等用户确认策略后再继续
4. 解决后：`git add <文件>`，然后 `git rebase --continue`
5. 绝对不要运行 `git rebase --skip`

## 第 3 步：本地验证（必须全部通过）

```bash
python scripts/check_book_structure.py --output output --strict
python -m pytest tests/test_sorting.py tests/test_check_chapter_order.py tests/test_book_structure.py -q
python scripts/build_site.py
python scripts/validate_commit_messages.py origin/master..HEAD
```

**全部通过后再继续。任何失败都不得 push/merge。**

提交信息校验失败时：
1. 列出不合格的提交标题/正文；
2. 对本地未推送提交使用 `git commit --amend` 或 `git rebase -i origin/master` 修改信息；
3. 重新运行 `python scripts/validate_commit_messages.py origin/master..HEAD` 直到通过。

如果 `check_book_structure.py --strict` 失败：
1. 立即停止，不要 push/merge。
2. 列出失败的文件与问题级别（P0/P1/P2）。
3. 修复所有问题——即使它们不是本次改动引入的。AI 生成的项目问题必须在合入前清零。
4. 若判定为会复发的代码/数据 bug，补充回归测试（`tests/test_*.py`）或更新 `tests/bug_regression_list.md`。
5. 重新运行 `--strict` 校验，直到通过。

如果 `pytest` 或 `build_site.py` 失败，同理修复后再继续。

## 模式 A 后续：推送到远程功能分支并发 PR

```bash
git push origin <功能分支名>
```

如果提示 non-fast-forward：
```bash
git push origin <功能分支名> --force-with-lease
```

如果还失败，可以用 `--force`（只限功能分支）：
```bash
git push origin <功能分支名> --force
```

push 前再次确认提交信息已通过：

```bash
python scripts/validate_commit_messages.py origin/master..HEAD
```

然后生成 PR 信息并展示给用户：

```markdown
## PR 标题（中文）
<type>(<scope>): <中文标题>

## 改动说明
- 做了什么
- 为什么做
- 影响范围

## 验证结果
- `python scripts/check_book_structure.py --output output --strict`：0 问题
- `pytest`：全部 passed
- `python scripts/build_site.py`：成功
- `python scripts/validate_commit_messages.py origin/master..HEAD`：通过

## 合并方式
推荐 Squash Merge（合并信息同样需用中文说明本次修改）
```

PR 链接格式：
```text
https://github.com/codengseam/HaloRead/pull/new/<功能分支名>
```

用户告知"PR 已合并"后，执行分支清理：
```bash
git checkout master
git pull origin master
git branch -d <功能分支名>
git push origin --delete <功能分支名>
```

## 模式 B 后续：直接合并到 master

仅当用户明确要求时执行：

```bash
git checkout master
git pull --rebase origin master
git merge --no-ff <功能分支名> -m "<type>(<scope>): <subject>

<body>

Merge branch '<功能分支名>'"
```

然后 push master（绕过 pre-push hook 对 master 的阻止）：
```bash
git push origin master --no-verify
```

push 成功后立即清理功能分支：
```bash
git branch -d <功能分支名>
git push origin --delete <功能分支名>
```

## 分支生命周期治理（兜底巡检，BUG-023）

模式 A/B 清理完**当前**功能分支后，**额外执行一次遗留 agent 分支巡检**，
避免 trae/agent-* 分支堆积（参见 `tests/bug_regression_list.md` BUG-023）。

### 触发时机
- 模式 B：`git push origin --delete <当前功能分支>` 成功之后
- 模式 A：用户告知 "PR 已合并" 并清理当前分支之后

### 巡检流程
1. 调用治理脚本 dry-run（只读，安全）：
   ```bash
   python scripts/branch_governance.py --mode dry-run --pattern "trae/agent-*"
   ```
2. 分类向用户汇报：
   - **删除候选（confidence ≥ 0.6，等价合入）**：列分支名 + 置信度 + 命中方法，询问"是否批量删除？"
   - **需人工确认（0.3 ≤ confidence < 0.6）**：列分支名 + 原因，提示逐个判断
   - **保留（confidence < 0.3）**：仅报数量，不打扰
   - **受保护分支**：跳过，仅说明已排除
3. 用户确认后批量 execute：
   ```bash
   python scripts/branch_governance.py --mode execute --pattern "trae/agent-*" --yes
   ```
   或对单分支显式删除：
   ```bash
   python scripts/branch_governance.py --mode execute --branch trae/agent-xxx --yes
   ```

### 安全约束（必须遵守）
- **绝不**跳过 dry-run 直接 execute
- **绝不**删除受保护分支（master/main/gh-pages/release/*）
- **绝不**删除 confidence < 0.6 的分支，除非用户对该具体分支明确说"删除"
- 巡检报告必须先展示给用户，**用户未确认前不得 execute**
- 治理脚本不存在或执行失败时**仅告警**，不阻断合并（治理是兜底，非合并必要条件）

### 与 CI 的分工
- **CI（branch-cleanup.yml）**：每次 push master 自动 dry-run 审计，workflow_dispatch 手动 execute
- **Skill 兜底**：合并当下趁用户在场立刻巡检，避免遗忘
- 两者共用 `scripts/branch_governance.py`，判定口径一致

## 最终验证

无论哪种模式，合并完成后都要在 master 上运行：
```bash
python scripts/check_book_structure.py --output output --strict
python -m pytest tests/test_sorting.py tests/test_check_chapter_order.py tests/test_book_structure.py -q
python scripts/validate_commit_messages.py origin/master~5..origin/master
```

若最终验证失败，必须立即修复并再次 push master（同样走 `--no-verify` 但问题必须解决）。

# 输出格式

每完成一步，向用户汇报：
- 该步执行了哪些命令
- 关键结果（通过/失败/冲突文件列表）
- 下一步动作
- 如果生成了 commit message 或 PR 信息，先展示给用户确认

遇到不确定情况（如冲突、测试失败、需要用户决策），必须停下来询问，不要擅自继续。

# 错误处理

- **当前在 master 上且用户未要求直接操作 master**：提示用户先切到功能分支
- **工作区有未提交改动**：询问用户是否要先提交，或按功能拆分提交
- **rebase 冲突**：展示冲突文件和片段，等用户决策
- **本地验证失败**：列出失败项，分析原因，建议修复方向
- **用户要求直接 push master**：确认用户意图后，使用模式 B（直接合并）执行，并解释会绕过 pre-push hook
