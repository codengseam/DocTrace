---
title: AI时代全栈知识边界·31|AI代码校验与选型
book: AI时代全栈知识边界
chapter: AI工程化
event: AI代码校验与选型
sort: 4
chapter_sort: 14
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·31|AI代码校验与选型

> 前置知识:用过至少一款 AI 编程工具(Copilot/Cursor/Cline/Trae)、能读懂 Python 与 YAML、了解 mypy/pylint 这类静态检查工具的基本概念、知道单元测试怎么写
> 学完你能:① 列出 AI 生成代码的 6 类典型问题(幻觉 API/版本错位/逻辑漏洞/性能陷阱/安全漏洞/上下文遗忘)并逐一定位 ② 用编译/单测/集成/静态扫描/性能/安全六层校验搭出可落地的 AI 代码闸门 ③ 配出一份 mypy + pylint + Semgrep 的最小校验配置 ④ 写出一份 AI 代码 review 清单 ⑤ 按任务类型、上下文长度、推理速度、价格、隐私合规六维度做模型选型 ⑥ 对比 Copilot/Cursor/Cline/Trae 四类工具的工程定位 ⑦ 判断什么代码该交给 AI、什么代码必须自己写

### 一、概念

AI 代码校验与选型,一句话定义:**对 AI 生成的代码做多层级校验,并为不同任务选配合适的模型与工具,使 AI 产出的代码达到可上线的质量门槛**。它由两半组成:校验(Verification)回答"这段 AI 写的代码能不能用",选型(Selection)回答"这个任务该交给哪个模型/工具"。

先对齐术语。Hallucination(幻觉)指模型生成看似合理但事实错误的内容,在代码场景里表现为 API 不存在、参数名拼错、版本特性错配;SAST(Static Application Security Testing,静态应用安全测试)是不运行代码、通过扫描源码发现漏洞与坏味道的工具族;LSP(Language Server Protocol,语言服务协议)是编辑器与语言服务器之间的通信标准,代码补全、跳转、诊断都建立在它之上;Context Window(上下文窗口)是模型单次能处理的最大 Token 数,直接决定能塞进多少代码上下文。

要划清两条边界:其一,「AI 代码校验」不是新学科,本质是传统代码审查 + 静态分析 + 测试的组合,只因 AI 生成代码的错误分布与人写的不同(集中在幻觉 API、版本错位、上下文遗忘),才需把校验做成更聚焦的多层闸门。其二,「AI 选型」不等于"选最强的模型",而是在能力、速度、价格、合规四者间权衡——最强的模型未必最适合你的任务,尤其当任务简单、并发高、数据敏感时。

### 二、原理

#### 1. AI 为什么会幻觉

幻觉不是模型"故意的",是两股力量叠加的必然结果。

第一股是训练分布。代码模型在海量公开仓库上训练,这些仓库里同时存在正确、过时、错误、甚至从未存在过的写法(有人写了能跑的占位代码就提交了)。模型学到的是概率分布:"在当前上下文之后,下一个 Token 最可能是什么"。当训练数据里某个错误 API 出现得足够多,或某个正确 API 出现得不够多时,概率分布就把错误选项推到前面。典型例子是 `datetime.utcnow()`:它在 Python 3.12 被弃用,但训练语料里到处都是,模型仍高频产出。

第二股是采样随机。模型在每一步从概率分布里采样(或取 argmax)出下一个 Token。即使正确 API 的概率排第一,只要温度大于 0,低概率候选仍可能被采样到;当几个候选概率接近时,模型会在"正确 API"与"看似合理的幻觉 API"之间横跳,产出语法通顺但语义错误的代码。这就是同一个 Prompt 跑两次一次对一次错的原因——不是 Prompt 写得不好,是采样随机性在边界处把输出带偏了。

工程后果:幻觉无法从模型侧根治,只能从校验侧兜底。你不知道 AI 这次会不会幻觉,所以必须假设它每次都可能幻觉,然后让校验闸门去拦。

#### 2. 为什么多层校验比单层更可靠

单层校验的根本问题是漏报:编译器抓不了 N+1 查询,单测抓不了安全漏洞,静态扫描抓不了新写法导致的逻辑漏洞。把校验压在单层上,等于赌"这一层恰好能覆盖 AI 这次犯的错",而 AI 的错误类型分布很广,这种赌注不划算。

多层校验的核心原理是**每层捕获不同类型的错误,且层与层之间正交**。具体对应关系:

- **编译/语法层**:抓 API 不存在(导入失败)、参数名错、类型不匹配。这一层最便宜,几秒出结果。
- **单元测试层**:抓逻辑漏洞、边界条件缺失、空值未处理。这一层性价比最高,AI 最容易在边界处翻车。
- **集成层**:抓上下文遗忘——单看每个函数都对,拼起来跑不通端到端,因为 AI 忘了前文约定的接口形状。
- **静态扫描层**:抓安全漏洞(注入、明文密钥)、坏味道、已知反模式。Semgrep/Bandit/pylint/mypy 都在这层。
- **性能层**:抓 N+1 查询、不必要的循环、内存泄漏。靠 profile + 压测。
- **安全层**:抓静态扫不出的逻辑漏洞(越权、鉴权缺失),靠扫描 + 人工审计。

这六层不是平行罗列,是一条流水线:越靠前越便宜、越靠后越贵;前层拦截了大多数低级错误,后层才能聚焦在真正需要人判断的问题上。工程上把前四层做成 CI 自动跑,后两层在关键模块上人工介入,这是性价比最高的组合。

#### 3. 模型选型的权衡:规模 vs 速度 vs 价格

模型选型不是"选参数量最大的",而是在四个维度间做权衡。

- **能力上限**:大模型(GPT-4o、Claude 3.5 Sonnet、DeepSeek V3)在复杂推理、长上下文、跨文件重构上明显更强;小模型(7B 量级开源模型)在简单函数、模板代码上已够用。能力差距在"简单任务"上很小,在"复杂任务"上很大——所以判断要不要花大模型的钱,先看任务复杂度。
- **推理速度**:大模型延迟高(几秒到十几秒),小模型延迟低(几百毫秒)。代码补全这种要实时响应的场景,延迟比能力更重要,用小模型;Agent 这种多步推理的场景,延迟可以接受,用大模型。
- **价格**:大模型按 Token 计费且贵,小模型便宜(自建摊薄后接近零)。批量任务(一次生成几百个测试用例)用小模型,单次关键任务用大模型。
- **隐私合规**:涉及客户隐私、内部机密的代码不能出境,必须选可私有化部署的开源模型(DeepSeek、Qwen Coder、Llama)。这是硬门槛,过不了直接排除,不进入后三个维度的权衡。

四个维度的优先级:合规 > 能力 > 价格 > 速度。合规是硬约束,先筛掉过不了合规的候选;再按任务复杂度选能力够用的最小模型;能力够用后在价格与速度间权衡。常见误判是"无脑用最强的",结果在简单任务上烧预算、在批量任务上被延迟拖垮。

### 三、实践

#### 实验 1:一段带幻觉 API 的 AI 代码 + 校验发现过程

下面这段是让 AI「写一个带重试与超时的 GET 请求,失败时记录时间戳」的典型产物。语法过、能 import,但含两处幻觉:

```python
# ai_generated.py —— AI 生成,含 2 处幻觉 API
import datetime
import requests

def fetch_with_retry(url: str, max_retry: int = 3) -> dict:
    """带重试与超时的 GET 请求,失败时打印时间戳。"""
    for i in range(max_retry):
        try:
            # 幻觉1:requests.get 没有 retry 参数
            resp = requests.get(url, retry=max_retry, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except requests.ConnectionError:
            continue
    # 幻觉2:utcnow() 在 Python 3.12 已弃用
    logged_at = datetime.utcnow().isoformat()
    print(f"[{logged_at}] 全部重试失败")
    return {}
```

校验发现过程,按六层闸门逐层走:

**第一层 编译/import**:`python -c "import ai_generated"` 通过。这层什么都抓不到——幻觉 API 的可怕之处正在于此,它语法完全正确。

**第二层 静态扫描**:跑 ruff 与 mypy。ruff 的 `UP` 规则集会报 `datetime.utcnow()` 已弃用;pylint 的 `W1518` 也标同一个问题。但 `requests.get(retry=...)` 抓不到,因为 requests 的类型存根里 `get` 签名带 `**kwargs`,SAST 不会对未声明的 kwargs 报错。

**第三层 单元测试**:写一个用 mock 模拟 `requests.get` 抛 `ConnectionError` 的测试,期望重试 3 次后返回 `{}`。跑测试直接 `TypeError: get() got an unexpected keyword argument 'retry'`——这个异常不是 `ConnectionError`,不会被 `except` 捕获,函数第一次循环就崩,重试逻辑根本没生效。这层把幻觉 1 抓了出来。

**第四层 文档对照**:查 requests 官方文档,`get()` 的签名只有 `url/params/headers/cookies/auth/timeout/allow_redirects/proxies/verify/stream/cert/hooks`,没有 `retry`。正确做法是配 `urllib3.util.retry.Retry` + `HTTPAdapter`,挂到 Session 上。

修复版:

```python
# ai_hardened.py —— 校验修复版
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def fetch_with_retry(url: str, max_retry: int = 3) -> dict:
    """带重试与超时的 GET 请求,失败时打印时间戳。"""
    session = requests.Session()
    retry = Retry(
        total=max_retry,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    logged_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"[{logged_at}] 全部重试失败")
    return {}
```

关键认知:幻觉 API 既不是"语法错"也不是"已知反模式",编译层与通用 SAST 都抓不到,只能靠**单测 + 文档对照**抓。这就是六层闸门缺一不可的原因——删掉单测,这类幻觉会一路溜到生产环境,在第一次真实调用时炸出来。

#### 实验 2:AI 代码 review 清单

下面这份清单用于人审 AI 生成代码,按 6 类风险组织,每项配一个"怎么查"的动作。建议做成 PR 模板,AI 生成的 PR 必须逐项打勾。

```markdown
## AI 代码 Review 清单

### 幻觉 API
- [ ] 所有 import 的包名拼写正确(`requests` 不是 `request`),`pip install` 实测一遍
- [ ] 所有调用的方法/参数名在官方文档里能查到,不靠"看起来像"
- [ ] 关键 API 调用配一条单测,mock 其行为

### 版本错位
- [ ] 用的 API 在目标运行环境版本里存在(查 `python --version` 与框架版本)
- [ ] 没用已弃用 API(ruff UP 规则集 / pylint W1xxx 报警清零)
- [ ] 没用未发布特性(对照官方发布说明,而不是模型"知道"的)

### 逻辑漏洞
- [ ] 边界条件有测试:空集合、单元素、极大值、负数、None
- [ ] 空值/缺字段有处理,不靠 `[]` 取值导致 500
- [ ] 异常分支被测到,不只是 happy path

### 性能陷阱
- [ ] 循环里没有 N+1 查询(看 ORM 调用是否在循环内)
- [ ] 没有不必要的全表扫描与全量加载
- [ ] 大列表操作用了合适的数据结构(查重用 set、有序用 list)

### 安全漏洞
- [ ] 无明文密钥(环境变量 + 缺失即报错)
- [ ] SQL 用参数化查询,不拼字符串
- [ ] 用户输入进了 os.system / eval / pickle.loads 的,Semgrep + Bandit 必须清零

### 上下文遗忘
- [ ] 函数签名与前文约定一致(参数名、返回类型、异常)
- [ ] 命名风格与项目既有代码一致,不"自创一套"
- [ ] 引用的模块/服务真实存在,不是模型"以为有"的
```

清单的使用纪律:不是"打勾就过",而是"每项都要有证据"——"边界条件有测试"贴出用例名,"无明文密钥"贴 Semgrep 报告。打勾无证据等于没查。

#### 实验 3:mypy / pylint / Semgrep 最小配置

下面这套配置可直接落到 `pyproject.toml`,覆盖类型、风格、安全三维度。先看 mypy(类型检查,抓参数错配与隐式 Any):

```yaml
# pyproject.toml 的 [tool.mypy] 段
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
# 第三方库无类型存根时不要报错,避免噪声
ignore_missing_imports = true
# 关键:把 AI 高频误用的库设为严格
[[tool.mypy.overrides]]
module = ["requests.*", "openai.*"]
disallow_untyped_defs = true
warn_return_any = true
```

再配 pylint(风格与坏味道,抓魔法数字、过长函数、弃用方法):

```yaml
# pyproject.toml 的 [tool.pylint] 段
[tool.pylint."MESSAGES CONTROL"]
disable = [
    "C0114",  # missing-module-docstring,AI 生成的工具函数不必每个都写模块docstring
    "R0903",  # too-few-public-methods,数据类常被误报
]
enable = [
    "W1518",  # deprecated-method,抓 datetime.utcnow 这类弃用
    "E1136",  # unsubscriptable-object,抓幻觉的类型下标
]
[tool.pylint."FORMAT"]
max-line-length = 100
max-args = 6  # AI 倾向堆参数,卡紧一点逼它重构
```

最后配 Semgrep(安全与 AI 模式,抓注入、明文密钥、不安全反序列化):

```yaml
# semgrep_rules/ai_code.yml
rules:
  - id: ai-deprecated-utcnow
    pattern: datetime.utcnow()
    message: utcnow() 在 3.12 已弃用,改用 datetime.now(timezone.utc)
    languages: [python]
    severity: WARNING

  - id: ai-requests-get-retry-kwarg
    pattern: requests.get(..., retry=$X, ...)
    message: requests.get 没有 retry 参数,这是 AI 幻觉,用 Retry+HTTPAdapter
    languages: [python]
    severity: ERROR

  - id: ai-hardcoded-secret
    pattern-regex: '(?i)(api_key|secret|token|password)\s*=\s*["''][^"'']{8,}["'']'
    message: 疑似硬编码密钥,改用环境变量
    languages: [python]
    severity: ERROR

  - id: ai-sql-fstring
    pattern: $CUR.execute(f"...")
    message: f-string 拼 SQL 有注入风险,改参数化查询
    languages: [python]
    severity: ERROR
```

CI 里串成一条流水线:

```bash
ruff check .                 # 语法 + 风格 + 弃用,最快
mypy src/                    # 类型检查,抓参数错配
pylint src/                  # 坏味道 + 弃用方法
semgrep --config semgrep_rules/ai_code.yml --config p/owasp-top-ten src/
pytest -q                    # 单测,抓逻辑与幻觉 API
```

顺序有讲究:ruff/mypy/pylint 秒级出结果,先跑,失败直接停;Semgrep 在分钟级;pytest 最慢放最后。这样含幻觉 API 的 PR 前几秒就被 ruff 拦下,不用等 pytest 跑完。

### 四、速查/自测

#### AI 代码风险 vs 校验方法对照表

| 风险类型 | 典型表现 | 校验层 | 工具 |
|---|---|---|---|
| 幻觉 API | `requests.get(retry=3)`、`import request` | 单测 + 文档对照 | pytest + 人工查文档 |
| 版本错位 | `datetime.utcnow()`(3.12 弃用)、用了未发布特性 | 静态扫描 | ruff UP / pylint W1518 |
| 逻辑漏洞 | 边界缺失、空值未处理、None 解引用 | 单元测试 | pytest(边界用例) |
| 性能陷阱 | N+1 查询、循环内全量加载 | 性能层 | cProfile + 压测 |
| 安全漏洞 | 明文密钥、SQL 注入、pickle 反序列化 | 静态扫描 + 安全层 | Semgrep / Bandit + 人工审计 |
| 上下文遗忘 | 函数签名与约定不符、命名风格不一致 | 集成层 + 人审 | 端到端测试 + review 清单 |

#### 模型选型维度对照表

| 维度 | 闭源旗舰(GPT-4o/Claude 3.5) | 专用编程模型(DeepSeek V3/Qwen Coder) | 开源自建(Llama/Qwen) |
|---|---|---|---|
| 能力上限 | 复杂推理、跨文件重构领先 | 编程任务逼近旗舰,通用略弱 | 简单任务够用,复杂任务有差距 |
| 推理速度 | 秒级,受网络与限流影响 | 秒级,国内访问稳定 | 自建可控,可做批处理 |
| 价格 | 高,按 Token 计费 | 中等,性价比高 | 自建摊薄后接近零 |
| 隐私合规 | 数据需出境 | 看厂商,部分提供私有化 | 可私有化部署,数据不出内网 |
| 适用场景 | 复杂架构、关键算法、跨文件重构 | 日常编程、补全、生成测试 | 高并发批量、敏感代码 |

#### AI 编程工具工程定位对照表

| 工具 | 形态 | 工程定位 | 适用场景 |
|---|---|---|---|
| Copilot | IDE 插件 | 代码补全为主,集成 GitHub 生态 | 补全、单函数生成、注释转代码 |
| Cursor | AI-native IDE | chat + agent,基于 VS Code fork | 多文件编辑、对话式重构 |
| Cline | VS Code 插件 | 开源 autonomous agent | 自动化多步任务、可定制工具链 |
| Trae | AI-native IDE | agent + MCP,国内生态 | 端到端开发、集成 MCP 工具 |

工具选型核心判断:补全为主选 Copilot,对话式重构选 Cursor/Cline,要端到端 agent 与 MCP 集成选 Trae。但工具只是入口,代码质量仍由校验闸门兜底——再强的工具也救不了不跑校验的团队。

#### 自测题

**问题一(原理层):** 为什么编译能通过的 AI 代码仍可能含幻觉 API?哪一层校验能抓到它?

参考答案:幻觉 API 的特征是"语法正确但语义错误"——包名拼对、方法名像个真方法、参数语法合法,所以 import 与编译都过得去。编译层只能抓语法错和类型错,抓不了"这个参数名在这个库的这个方法里不存在"。能稳定抓到它的是单测层(运行即抛 TypeError)和文档对照层(查官方签名)。

**问题二(实践层):** 下面这段 AI 生成的代码有几种风险?分别属于哪一类?

```python
def get_users(ids):
    import pymysql
    conn = pymysql.connect(host="db", user="root", password="123456")
    users = []
    for uid in ids:
        row = conn.cursor().execute(f"SELECT * FROM users WHERE id={uid}")
        users.append(row)
    return users
```

参考答案:四处。① 明文密钥 `password="123456"`,属安全漏洞;② f-string 拼 SQL,属安全漏洞(SQL 注入);③ 循环内逐条查询,属性能陷阱(N+1);④ `import pymysql` 在函数内且无连接关闭,属逻辑漏洞(资源泄漏)。修复:密钥走环境变量、SQL 参数化、改成 `WHERE id IN (...)` 一次查、用 `with` 管理连接。

**问题三(原理层):** 多层校验为什么不能合并成"一层最强的 SAST"?举例说明 SAST 抓不到的错。

参考答案:每层校验有正交的盲区,SAST 抓不到的典型是逻辑漏洞与性能陷阱。比如 AI 写的 `def first_or_default(xs): return xs[0] if xs else None`,SAST 不报错,但若业务要求"空列表返回空字典而不是 None",这是语义错,只能靠单测断言 `assert first_or_default([]) == {}` 抓到。N+1 查询 SAST 也看不出,只能靠 profile + 压测发现。合并成单层等于放弃这些盲区。

**问题四(选型层):** 团队要为内部代码库做一个"自然语言查代码"的功能,代码库含客户敏感信息不能出境。该选哪类模型?给出判断依据。

参考答案:合规是硬门槛,代码不能出境直接排除所有闭源 API(GPT-4o/Claude)。候选是可私有化部署的开源模型(DeepSeek、Qwen Coder、Llama)。在这类里按能力选:自然语言查代码涉及语义理解与代码理解,选编程能力较强的 DeepSeek Coder 或 Qwen Coder;若并发高,选参数量较小的版本自建推理集群。最终判断:私有化部署的编程专用模型,合规优先于能力。

**问题五(思路层):** 有人说"AI 生成的代码只要 ruff + mypy + pytest 全过就能合",这条规则哪里不够?

参考答案:三层都不够。ruff/mypy 抓语法、类型、弃用,抓不了逻辑漏洞与安全漏洞;pytest 只覆盖写出来的用例,AI 常在"没写测试的边界"翻车;且三层都不含安全扫描与人工 review。最小闸门应是六层:编译/import + 单测 + 集成 + 静态扫描 + 性能 + 安全,缺安全扫描会让明文密钥、注入这类高频 AI 漏洞溜进主线。

### 可交给 AI 的部分

这一章里,以下内容可以放心交给 AI:

- **生成测试用例初稿**:给定一个函数签名,AI 能快速产出正常路径、边界(空、单元素、极大值)、异常路径的测试用例,人审后补业务特定断言。这是 AI 最擅长的机械劳动。
- **生成 review 清单初稿**:让 AI 按框架(Flask/Django/FastAPI)生成对应的 review 清单,人审补充项目特定项。AI 给的是通用清单,项目特定项(比如"必须经过某中间件")得人补。
- **生成扫描规则草稿**:把"扫所有用 f-string 拼 SQL 的地方"这类自然语言需求交给 AI,它能给出 Semgrep YAML 草稿,用 semgrep 跑一遍验证误报率后人审落地。
- **生成 mypy/pylint 配置初稿**:告诉 AI 项目的 Python 版本与依赖,AI 能给出基础配置,人审后微调 disable/enable 列表。
- **弃用与 CVE 报告解读**:把一段弃用说明或 CVE 描述丢给 AI,让它总结"影响版本、触发条件、修复版本、是否影响我们",人做最终判定。

但有几类内容**必须自己握住**,边界与风险如下。

第一类是**风险接受决策**。AI 能告诉你"这里有 SQL 注入风险",但要不要修、优先级多高、能否用 WAF 兜底代替改代码,是结合业务上下文与威胁模型的判断,AI 给不出负责任的答案。把这类决策交给 AI 等于让概率模型替你担责。

第二类是**模型选型的合规判断**。AI 不会替你判断"客户数据能不能出境""某厂商私有化部署是否满足等保",这些是法务与合规问题,必须人定。AI 的选型建议常基于"能力最强",而合规是硬门槛,优先级反过来。

第三类是**校验闸门本身的设计**。AI 倾向于"能跑就行",不会主动建议加六层闸门;让它设计 CI,它给你一个 `pytest` 就完事。闸门几层、每层用什么工具、失败如何阻断,是工程质量决策,必须人定。让 AI 设计闸门,等于让被校验方设计校验规则,有结构性利益冲突。

第四类是**核心算法、安全关键、性能关键代码的最终判定**。这三类代码即使全过校验,也必须人逐行读懂后才能合。校验能抓"错",抓不了"不够好"——一个能跑但复杂度 O(n²) 的算法,校验不报错,性能却在数据量大时崩。这类代码的"够不够好"必须人判。

区分"能交"与"不能交"的本质是:**输入输出可复现、错误可被工具二次验证的生成性任务能交;涉及风险接受、合规判断、质量判定的语义决策不能交**。把生成性劳动交给 AI,把语义决策留给自己,这是 AI 代码校验与选型在 AI 时代必须握住的知识边界。

## 参考来源

- [1] Steve McConnell:《Code Complete(代码大全)》2nd ed,Microsoft Press 2004(第 4 章构建质量、第 20 章软件质量工具,多层校验的工程传统来源)
- [2] Robert C. Martin:《Clean Code(代码整洁之道)》Prentice Hall 2008(代码审查清单与坏味道分类)
- [3] OpenAI 官方文档:GPT-4o 与 API,https://platform.openai.com/docs
- [4] Anthropic:Claude 模型文档,https://docs.anthropic.com
- [5] DeepSeek 官方文档:DeepSeek V3 与 API,https://api-docs.deepseek.com
- [6] GitHub Copilot 官方文档,https://docs.github.com/copilot
- [7] Cursor 官方文档,https://docs.cursor.com
- [8] Semgrep 官方文档,https://semgrep.dev/docs
- [9] mypy 官方文档,https://mypy.readthedocs.io
- [10] pylint 官方文档,https://pylint.readthedocs.io
- 本专栏第 26 章「AI代码安全审计」(本章安全层的深入展开,覆盖 Semgrep/SCA/密钥扫描/提示词注入的完整工程实践)
- 本专栏第 28 章「Prompt工程基础」(Prompt 工程与基础模型选型,本章在选型维度上进一步落到编程任务)
- 本专栏第 23 章「测试驱动与CI-CD」(单测与 CI 流水线的工程基础,本章六层闸门前四层依赖它)
