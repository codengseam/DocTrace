---
title: AI时代全栈知识边界·22|Git工作流与代码评审
book: AI时代全栈知识边界
chapter: 工程化
event: Git工作流与代码评审
sort: 1
chapter_sort: 10
created_at: 2026-06-30
source_agents: [fullstack-expert]
---

# AI时代全栈知识边界·22|Git工作流与代码评审

> 前置知识:命令行基础、至少用过一次 git commit、看过一次 Pull Request
> 学完你能:为团队选对分支模型,用 reset/revert 安全回滚,看懂三方合并原理,写出可执行的 PR 模板与评审清单,用 OpenAPI 把前后端契约钉死

## 一、概念

Git 工作流与代码评审解决的是同一件事——让多人在同一份代码上协作时不互相踩脚。Git 工作流规定"分支怎么开、怎么合、谁有权合",代码评审规定"合之前谁看、看什么、按什么标准放行"。两者必须配套:有工作流没评审,代码质量靠个人自觉;有评审没工作流,评审失去落点。

先把核心术语的中英对照钉死:

- Git:分布式版本控制系统
- PR(Pull Request,拉取请求):GitHub 用语,请求目标分支拉取自己分支的改动
- MR(Merge Request,合并请求):GitLab 用语,语义等同 PR
- Branch(分支):指向某次提交的可移动指针
- Commit(提交):仓库的一次快照记录
- Rebase(变基):把分支起点换到另一条分支的最新提交之上
- Merge(合并):把两条分支的提交汇成一条新提交
- OpenAPI(开放应用编程接口规范):描述 REST 接口的机器可读规范,前身叫 Swagger
- CI(Continuous Integration,持续集成):每次提交自动跑构建与测试
- Code Review(代码评审):合入前由人审查代码改动

代码评审不是"找茬",它的根本机制是"第二双眼睛":写代码的人在写完后大脑已经退出上下文,容易对自己的逻辑盲点视而不见;评审者带着陌生视角进入,反而能看到作者看不见的问题。这也是为什么评审者最好不要只盯着 diff,而要问"这段改动解决什么问题"。

## 二、原理

### Git 的数据模型:快照而非差异

很多人误以为 Git 存的是"每次改了哪些行",其实 Git 存的是"每次提交时整个项目的快照"。每次 commit,Git 会对发生变化的文件存一个新对象(blob),没变的文件只存一个指向旧 blob 的指针。提交对象(commit)记录的是"树根指针 + 父提交指针 + 作者 + 时间 + message"。

这就解释了几个反直觉现象:

- `git log` 看起来是线性的,实际是一张 DAG(有向无环图),每个 commit 可能有 0、1 或 2 个父提交。
- 切分支只是改一个 41 字节文件(把 `refs/heads/xxx` 指向某个 commit),几乎零成本,所以 Git 鼓励频繁开分支。
- `git checkout` 比 SVN 的"切目录"快得多,因为不用从服务器拉,本地对象库已有所有快照。

理解快照模型是理解 reset 与 revert 差别的根本前提。

### reset vs revert:改历史 vs 加反向提交

这是面试高频题,也是生产事故高发点。两者都"撤销改动",但机制完全不同。

`git reset` 是**移动分支指针**,把当前分支的 HEAD 移到指定提交。它有三个常用模式:

- `--soft`:只移 HEAD,工作区、暂存区都不动。结果:改动全部回到"已暂存"状态,可以重新提交。
- `--mixed`(默认):移 HEAD,把暂存区也重置,工作区不动。结果:改动回到"未暂存"状态。
- `--hard`:移 HEAD,暂存区和工作区全清。结果:改动彻底消失,找不回(除非知道 commit hash 或靠 reflog)。

`git revert` 不动历史,而是**新建一个反向提交**,内容是原提交的"相反操作"。比如原提交是"+3 行",revert 会生成一个"-3 行"的新 commit。

差异的本质:

- reset 改写历史,适合"本地未推送"的提交。一旦推送给了别人,reset 会让别人的本地历史和远端分叉,后续 pull 必冲突。
- revert 追加历史,适合"已推送、已有人拉取"的提交。历史保留,所有人 pull 后都能自动看到这次撤销,不会分叉。

铁律:**已推送到共享分支的提交,只能 revert,不能 reset。** 否则就是等着事故。

### 三方合并为什么比两方合并准

合并两条分支时,Git 不是简单"两个文件做 diff",而是做**三方合并(Three-Way Merge)**。三个版本是:

- Base:两条分支的共同祖先(merge base)
- Ours:当前分支的版本
- Theirs:被合入分支的版本

对每个文件区域,Git 看 Base 到 Ours 怎么变、Base 到 Theirs 怎么变。只有当两边改了同一区域且改法不同时才报冲突;只有一边改了,直接采用改了的那版;都没改就保留 Base。

两方合并(只看 Ours 和 Theirs)无法判断"哪边是新改动、哪边是没动",要么无脑取一方,要么把所有重叠都报冲突。三方合并多了 Base 这个参照系,冲突率大幅下降——这是 Git 合并能自动处理绝大多数情况的根本原因。

### rebase vs merge:线性历史 vs 真实拓扑

`git merge feature` 会在 main 上生成一个 merge commit,有两个父提交,历史呈现"分叉再汇合"的真实拓扑。

`git rebase main` 会把 feature 上的每个 commit 重新应用到 main 最新提交之上,历史变成一条直线,没有 merge commit。

差异:

- merge 保留真实拓扑,可追溯"这条分支什么时候开的、合了什么",但历史图复杂。
- rebase 历史干净线性,但每个被 rebase 的 commit 都被改写了 hash,等于重写历史。

铁律:**不要 rebase 已经推送的公共分支。** 因为 rebase 重写 hash,别人的本地会和你彻底分叉。`git pull` 默认是 merge,生产环境推荐改成 `git pull --rebase`(只对本地未推送的提交生效)来保持线性历史。

## 三、实践

### .gitignore 模板

一个典型的全栈项目 .gitignore,覆盖常见语言与工具产物:

```gitignore
# 操作系统
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
*.swp

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.env.local

# Node / 前端
node_modules/
dist/
build/
.next/
.nuxt/
npm-debug.log*

# 日志与临时
*.log
*.pid
tmp/

# 测试与覆盖率
.coverage
htmlcov/
.pytest_cache/
coverage/

# 容器与本地数据
*.local
data/*.sqlite3
```

`.gitignore` 只对未跟踪文件生效。已经被 commit 的文件,后加进 .gitignore 也不会被忽略,需要先 `git rm --cached <file>` 把它从索引移除(但保留本地文件)再提交。

### reset vs revert 对照演示

场景:在 main 分支上做了三次提交,发现第二次(b)是个错误改动。

```bash
# 当前历史
$ git log --oneline
c9f3a21 (HEAD -> main) c: 修复登录样式
3e2b8d0 b: 误把密码明文写入日志
1a0f7c2 a: 新增登录页

# 假设 b 还没推送 → 用 reset
$ git reset --soft HEAD~1     # 撤销 c,改动回到暂存区
$ git reset --mixed HEAD~1    # 撤销 c,改动回到工作区
$ git reset --hard HEAD~2     # 危险!撤销 b 和 c,改动彻底丢
```

`--hard` 之后想找回,只能靠 reflog:

```bash
$ git reflog
c9f3a21 HEAD@{0}: reset: moving to HEAD~2
3e2b8d0 HEAD@{1}: commit: b
1a0f7c2 HEAD@{2}: commit: a
$ git reset --hard 3e2b8d0    # 用 reflog 找回被 reset 丢掉的提交
```

如果 b 已经推送到远端共享分支,只能用 revert:

```bash
# revert 不动历史,而是生成一个反向提交
$ git revert 3e2b8d0
# 自动生成 commit: "Revert: 误把密码明文写入日志"
$ git log --oneline
d4e1c90 (HEAD -> main) Revert "b: 误把密码明文写入日志"
c9f3a21 c: 修复登录样式
3e2b8d0 b: 误把密码明文写入日志   # 历史还在,可追溯
1a0f7c2 a: 新增登录页

$ git push origin main        # 安全,别人 pull 后自动得到这次撤销
```

注意 revert 一个 merge commit 时要带 `-m 1` 参数告诉 Git 保留哪一边,否则会报错或回滚错版本。

### PR 模板(Pull Request Template)

把以下内容存为 `.github/PULL_REQUEST_TEMPLATE.md`,GitHub 会在新建 PR 时自动填入:

```markdown
## 改动背景

<!-- 这次 PR 解决什么问题,关联的 issue 或需求单号 -->

## 改动内容

<!-- 列出主要改动点,3-5 条 -->
- 
- 

## 测试情况

<!-- 跑了哪些测试,结果如何 -->
- [ ] 单元测试通过 `pytest -q`
- [ ] 本地手测主流程通过
- [ ] 新增/更新了对应测试用例

## 风险与回滚

- 风险点:
- 回滚方式:(revert commit hash / 配置开关 / 数据库迁移)

## 评审重点

<!-- 提醒评审者重点看哪里:安全/性能/边界条件 -->
```

模板的核心价值是让作者自己先回答"为什么改、改了什么、怎么验证、怎么回退",这四问答完,一半低级问题就自查掉了,评审者也能聚焦在真正需要人判断的地方。

### 代码评审清单(评审者视角)

把清单贴到团队 Wiki 或 PR 模板里,评审时逐项过:

```markdown
## 评审清单

### 逻辑正确性
- [ ] 核心业务路径是否符合需求
- [ ] 边界条件(空、零、负、最大值、并发)是否处理
- [ ] 异常分支是否有合理兜底,不会吞异常

### 安全
- [ ] 用户输入是否做了校验与转义
- [ ] 敏感信息(密码、token、密钥)未硬编码、未进日志
- [ ] 鉴权与权限校验是否到位(垂直越权、水平越权)

### 性能
- [ ] 是否有 N+1 查询
- [ ] 循环内是否做了可外提的耗时操作
- [ ] 大数据量场景是否会一次拉满内存

### 可读性与可维护性
- [ ] 命名是否表意,无需注释就能读懂
- [ ] 是否引入了不必要的抽象
- [ ] 公共接口变更是否影响调用方

### 测试覆盖
- [ ] 新增逻辑是否有对应测试
- [ ] 测试是否断言了行为而非实现细节
- [ ] 覆盖了失败路径而非只测 happy path
```

清单不是走过场——评审者每勾一项都要在心里给个理由。如果某项无法判断,就明确说"这块我看不懂,请补充说明",而不是默认放行。

### OpenAPI 接口契约示例

前后端契约的核心是"先定义接口、再分头开发"。用 OpenAPI 把契约写成机器可读文件,前端可以 mock、后端可以对照实现、测试可以自动生成:

```yaml
# openapi.yaml
openapi: 3.0.3
info:
  title: 订单服务 API
  version: 1.0.0
paths:
  /orders:
    post:
      summary: 创建订单
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          description: 创建成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Order'
        '400':
          description: 参数错误
        '409':
          description: 库存不足
components:
  schemas:
    CreateOrderRequest:
      type: object
      required: [product_id, quantity]
      properties:
        product_id:
          type: integer
          format: int64
        quantity:
          type: integer
          minimum: 1
          maximum: 99
    Order:
      type: object
      properties:
        order_id:
          type: string
        status:
          type: string
          enum: [created, paid, cancelled]
        total_amount:
          type: number
          format: double
```

这份文件一旦确定,前端用 `openapi-typescript` 生成 TypeScript 类型,后端用 `fastapi-codegen` 生成路由骨架,测试用 `schemathesis` 自动跑契约测试。接口变更必须先改这份文件,PR 里改动 OpenAPI 就是契约变更的明确信号。

### 项目目录规范与需求拆解

一个中型全栈项目的目录约定(以 Python 后端 + Vue 前端为例):

```text
project/
├── backend/
│   ├── app/
│   │   ├── api/          # 路由层,只管参数校验与调用
│   │   ├── service/      # 业务编排
│   │   ├── domain/       # 领域模型与不变量
│   │   ├── repository/   # 数据访问
│   │   └── schemas/      # Pydantic 模型,对齐 OpenAPI
│   ├── tests/
│   ├── openapi.yaml
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── views/        # 页面
│   │   ├── components/   # 复用组件
│   │   ├── api/          # 由 OpenAPI 生成的客户端
│   │   └── stores/       # 状态管理
│   └── package.json
├── docs/
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/ci.yml
├── .gitignore
└── README.md
```

需求拆解的工程化做法:把一个需求拆成"接口契约 + 任务卡"两份产物。

- 接口契约:就是上面的 OpenAPI 文件,前后端共同评审,定稿后冻结。
- 任务卡:每个任务对应一个 feature 分支,分支名 `feat/order-create-<issue号>`,任务卡里写"实现哪个接口、依赖哪些表、需要哪些测试"。

契约先行的好处是前后端不再互相等——前端用 mock 跑通页面,后端按 schema 实现,联调时只对齐契约差异,不会出现"接口字段名不一致导致全链路返工"。

## 四、速查/自测

### Git 工作流选型对照表

| 工作流 | 分支模型 | 适用场景 | 优点 | 缺点 |
|---|---|---|---|---|
| Git Flow | main/develop/feature/release/hotfix | 有正式版本发布、需维护多个线上版本的产品(C 端 App、桌面软件) | 版本管理严格,hotfix 路径清晰 | 分支多、合并频繁,对小型团队过重 |
| GitHub Flow | main + feature | 持续部署的 Web 产品、SaaS | 简单,只有两条分支,合即发 | 无 release 分支,线上回滚靠 revert |
| Trunk-Based | 单 main + 短命 feature | 高频部署、强 CI、Feature Flag 成熟团队 | 集成冲突最小,部署最快 | 对 CI 与特性开关要求高,不适合长周期功能 |
| GitLab Flow | main + feature + environment(预发/生产) | 多环境部署、需环境隔离 | 环境与分支对应,部署可追溯 | 环境分支同步靠 cherry-pick,易遗漏 |

选型核心原则:分支数与团队成熟度成反比。CI 不强、特性开关没建好,别上 Trunk-Based;发布频率低、需多版本并存,Git Flow 仍有价值;大多数中小团队用 GitHub Flow 就够。

### 自测题

1. **原理层**:为什么 `git reset --hard` 删掉的提交还能被 `git reflog` 找回?
   <details><summary>参考答案</summary>reset 只移动分支指针,提交对象本身没被删除,只是变成"不可达"。Git 默认 90 天内保留不可达对象,reflog 记录了 HEAD 的所有移动历史,用 reflog 找到原 commit hash 后 `git reset --hard <hash>` 即可恢复。</details>

2. **思路层**:已推送到团队 main 分支的提交发现写错了,该用 reset 还是 revert?为什么?
   <details><summary>参考答案</summary>必须用 revert。reset 会改写历史,导致其他协作者本地与远端分叉,pull 时报冲突或丢失提交。revert 追加反向提交,所有协作者 pull 后自动同步,历史可追溯。</details>

3. **思路层**:三方合并相比两方合并,为什么冲突率更低?
   <details><summary>参考答案</summary>三方合并引入共同祖先 Base 作为参照:两边相对 Base 都没改的区域保留 Base;只有一边改了直接采用改了的那版;只有两边都改且改法不同才报冲突。两方合并没有 Base,无法区分"新改动"和"未改动",冲突率显著更高。</details>

4. **实践层**:一个 feature 分支落后 main 30 个 commit,合并前用 merge 还是 rebase?各有什么代价?
   <details><summary>参考答案</summary>若 feature 是私人分支未推送,rebase 更干净,代价是要解决 30 次潜在冲突(每个 commit 重放时都可能冲突);若 feature 已被他人拉取或协作,用 merge 生成 merge commit,冲突一次性解决,代价是历史有分叉。生产中常用 `git pull --rebase` 同步远端再合并,保持线性。</details>

5. **实践层**:PR 模板里"回滚方式"为什么是必填项?
   <details><summary>参考答案</summary>线上故障时最贵的是判断时间。提前写明回滚方式(revert hash / 配置开关 / 数据库迁移),值班同学不用读代码就能执行,把 MTTR(平均恢复时间)从小时级压到分钟级。没有回滚预案的 PR 不应被合入。</details>

### 可交给 AI 的部分

哪些内容可以放心交给 AI:

- Git 复杂命令脚本:把"找出最近一周谁提交了哪些未合并的 feature 分支""批量清理已合并的远端分支"这种重复性脚本交给 AI 写,人只需审查脚本是否含 `--force` / `--hard` 等破坏性操作。
- 完整接口自动化测试代码:把 OpenAPI 文件喂给 AI,生成契约测试、边界用例、参数 fuzz 用例,覆盖 happy path 与常见边界,人工只补业务专属用例。
- 生成 commit message:`git diff` 喂给 AI,生成符合 Conventional Commits 规范的中文 message 初稿,人工校验后采用。
- PR 描述与评审清单初稿:AI 按 diff 自动填充 PR 模板的"改动内容""测试情况",生成评审重点提示。
- .gitignore 模板:按技术栈生成,几乎零风险。

风险提示:

- AI 写的 commit message 容易只描述"改了什么"而漏掉"为什么改"。message 的价值在 why 不在 what,必须人工补上下文与关联 issue,否则半年后没人看得懂这次提交。
- AI 写的接口测试常漏边界:它会覆盖 `minimum: 1` 这类显式约束,但漏掉"并发下单同一商品""支付回调重复到达"这类业务时序边界。契约测试只能保证"接口符合 schema",保证不了"业务正确"。
- AI 生成的 Git 脚本可能误用 `--force` 或 `git clean -fd`,在共享仓库上跑会清掉他人未提交工作。任何含破坏性 flag 的脚本必须人工逐行核对,先在 dry-run 或测试仓库验证。
- AI 做 PR 评审能查出命名、格式、明显空指针,但看不出业务逻辑漏洞与安全越权——这些需要领域知识与威胁建模,AI 当前只能当辅助不能当 gatekeeper。
- AI 生成的 OpenAPI 容易把 `integer` 写成 `number`、漏掉 `required` 字段、把枚举写成自由字符串。契约文件一旦定稿下游全靠它生成代码,错一处全链路返工,必须人工对照需求逐字段复核。

## 参考来源

- [1] Scott Chacon, Ben Straub:《Pro Git》2024
- [2] Vincent Driessen:A Successful Git Branching Model https://nvie.com/posts/a-successful-git-branching-model/
- [3] GitHub Docs:About pull requests https://docs.github.com/pull-requests
- [4] GitLab Docs:Merge requests https://docs.gitlab.com/user/project/merge_requests/
- [5] OpenAPI Initiative:OpenAPI Specification 3.1 https://spec.openapis.org/oas/v3.1.0
- [6] Google:Trunk Based Development https://trunkbaseddevelopment.com/
- [7] Robert C. Martin:《代码整洁之道》2008
- [8] Atlassian:Comparing Git workflows https://www.atlassian.com/git/tutorials/comparing-workflows
- 本专栏第 23 章「测试驱动与 CI-CD」(本文 PR 模板与评审清单的自动化落地续篇)
- 本专栏第 32 章「需求建模与接口设计」(OpenAPI 契约与需求拆解的纵深展开)
