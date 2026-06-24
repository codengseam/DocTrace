# 通用无冲突 Git 合并提示词（HaloRead 项目）

复制以下内容直接发给 AI，让它按这个流程执行。

```markdown
请帮我完成一次安全的 Git 合并流程，核心要求：
1. 不覆盖 master/main 主干上已修好的代码
2. 无冲突地把当前功能分支合入主干；如有冲突，停下来让我确认
3. 严禁 force push 到 master/main
4. 功能分支可以 force push，但必须先 explain why

## 第 0 步：检查当前状态
先运行：
```bash
git status --short
git branch -vv
git log --oneline -5
```
把结果汇报给我。确认：
- 当前不在 master/main 上
- 没有 .env / token / 密钥等敏感未跟踪文件
- 如果有未提交改动，先停下来问我要不要提交

## 第 1 步：整理当前工作区（如果有未提交改动）
按功能把未提交改动拆成 1-3 个小提交，不要一次性 `git add -A`：

```bash
# 示例：先提交规范/脚本/测试
git add .trae/checklists/ scripts/ tests/ docs/loop_log.md
git commit -m "feat: 增加书籍结构规范与校验脚本"

# 再提交核心逻辑修复
git add src/utils/sorting.py
git commit -m "fix: 排序优先使用 chapter_sort/sort"

# 最后提交 output/ 下内容修复
git add output/
git commit -m "fix: 修复 X 本书的 frontmatter 与模块排序"
```

如果改动太小，也可以只提交一个：
```bash
git add -A
git commit -m "fix: 修复 XX 问题"
```

## 第 2 步：同步 master 并 rebase
```bash
git fetch origin
git checkout master
git pull --rebase origin master
git checkout <当前功能分支名>
git rebase master
```

如果 rebase 出现冲突：
1. 立即停止，不要自动 continue
2. 把冲突文件列表和冲突片段展示给我
3. 等我确认策略后再继续
4. 解决后：`git add <文件>`，然后 `git rebase --continue`
5. 绝对不要运行 `git rebase --skip`

## 第 3 步：本地验证（必须全部通过）
```bash
python scripts/check_book_structure.py --output output
python -m pytest tests/test_sorting.py tests/test_check_chapter_order.py tests/test_book_structure.py -q
python scripts/build_site.py
```

全部通过后再推送。如果失败，先修复问题，不要 push。

## 第 4 步：推送到远程功能分支
```bash
git push origin <当前功能分支名>
```

如果提示 non-fast-forward（因为 rebase 改写了历史），使用：
```bash
git push origin <当前功能分支名> --force-with-lease
```

如果 --force-with-lease 失败（远程分支状态未知），可以使用 --force，但只限于功能分支：
```bash
git push origin <当前功能分支名> --force
```

严禁：
```bash
git push origin master --force
git push origin main --force
```

## 第 5 步：发起 Pull Request
- 在 GitHub 页面发起 PR，目标分支选 `master`
- 标题格式：`feat:` / `fix:` / `docs:` + 简短描述
- 描述里写明改动范围、验证结果
- 等待 CI 通过
- 推荐用 Squash Merge，保持主干历史干净

## 第 6 步：合并后清理
PR 合并后：
```bash
git checkout master
git pull origin master
git branch -d <旧功能分支名>
git push origin --delete <旧功能分支名>
```

## 第 7 步：最终验证
```bash
python scripts/check_book_structure.py --output output
python -m pytest tests/test_sorting.py tests/test_check_chapter_order.py tests/test_book_structure.py -q
```

请严格按以上步骤执行，每完成一步汇报一次状态。遇到任何不确定的情况先停下来问我。
```
