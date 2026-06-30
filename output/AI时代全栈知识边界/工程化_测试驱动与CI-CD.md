---
title: AI时代全栈知识边界·23|测试驱动与CI-CD
book: AI时代全栈知识边界
chapter: 工程化
event: 测试驱动与CI-CD
sort: 2
chapter_sort: 10
created_at: 2026-06-30
source_agents: [fullstack-expert]
---

# AI时代全栈知识边界·23|测试驱动与CI-CD

> 前置知识:会写 Python 函数、用过 git 提交代码、了解 Docker 镜像基本概念
> 学完你能:① 画出测试金字塔并说清三层为什么是这个比例 ② 用 AAA 模式写 pytest 单元测试并区分 Mock/Stub/Spy ③ 走完 TDD 红-绿-重构三步循环 ④ 写出可运行的 GitHub Actions workflow YAML ⑤ 说清 CI 与 CD 的边界、流水线三大设计原则 ⑥ 识别测试覆盖率陷阱与制品管理要点

## 一、概念

测试驱动与 CI/CD 解决的是同一类问题——怎么让代码改了不崩、发了不炸。两者切入角度不同:TDD 约束的是"写代码的那一刻",CI/CD 约束的是"代码从提交到上线的那条路径"。

- TDD(Test-Driven Development,测试驱动开发):先写测试(测试会失败),再写最小实现让测试通过,最后重构。三步循环反复进行,让代码始终处于"被测试保护"的状态。
- CI/CD(Continuous Integration/Continuous Deployment,持续集成/持续部署):CI 指每次代码提交都自动触发构建和测试,尽早暴露集成问题;CD 指通过测试的制品自动部署到目标环境。两者合起来构成一条从提交到上线的自动化流水线(Pipeline,流水线)。

首次出现的英文术语给中英对照:

- Unit Test:单元测试
- Integration Test:集成测试
- End-to-End Test(简称 E2E):端到端测试
- Mock / Stub / Spy:模拟对象 / 桩对象 / 间谍对象
- AAA:Arrange-Act-Assert(准备-执行-断言)
- Coverage:测试覆盖率
- Artifact:制品
- Rollback:回滚
- Stage:阶段

CI 与 CD 的边界要分清:CI 回答"代码能不能合",CD 回答"合了能不能上"。很多团队只有 CI 没有 CD——提交后自动跑测试,但部署靠人手 SSH 上去敲命令,这种"半自动化"是故障高发区。

## 二、原理

### 测试金字塔为什么这么分层

测试金字塔(Test Pyramid)把测试分三层:底层单元测试最多,中层集成测试其次,顶层端到端测试最少。这个比例不是审美偏好,是成本、速度、稳定性三方权衡的结果。

- 单元测试:验证单个函数或类的行为,不依赖外部(数据库、网络、文件系统)。毫秒级跑完,一个变更改几十个用例也能秒级反馈。成本低、速度快、稳定性高,所以要多写。
- 集成测试:验证多个模块协作,比如"Service + Repository + 真实数据库"。要起依赖、造数据,秒级到分钟级。成本和速度都中等,数量要控制。
- 端到端测试:从用户操作入口一路跑到最底层,比如"打开浏览器 → 登录 → 下单 → 支付"。涉及整条链路,分钟级甚至更慢,任何一个环节抖动都会让用例挂掉,稳定性最差。能少写就少写。

反模式有两种:倒金字塔(端到端测试最多,单元测试最少)和沙漏(单元测试多、集成测试几乎没有、端到端一堆)。两者共同症状是"测试一跑半小时,改一行代码红一片",根因都是把验证成本压在了最贵的那一层。

### TDD 为什么能提升设计

TDD 的核心不是"多写测试",而是"先写测试"。这个顺序倒过来,效果完全不同。

先写实现再补测试,你写的测试天然贴合已实现的接口——因为接口已经定型,测试只是在描述现状。这种测试很难发现设计问题,因为它没有机会提出"如果接口长这样,调用方会很别扭"的质疑。

先写测试,你被迫站在调用方角度想:这个函数该叫什么名字、接收什么参数、返回什么、什么时候抛异常。这个"先想用法再写实现"的过程,逼出更小的函数、更清晰的入参、更少的副作用。这就是 TDD 提升设计的根本机制——它把"接口设计"从脑内模拟变成了可执行的断言。

红-绿-重构(Refactor,重构)三步循环:

1. 红:写一个会失败的测试。失败说明测试本身有效(否则永远绿,等于没测)。
2. 绿:写最小代码让测试通过。注意是"最小",不要顺手把下一个测试的代码也写了,否则测试就没机会再红一次。
3. 重构:在测试保护下清理代码——抽函数、改命名、消除重复。重构期间测试必须保持全绿。

三步循环的关键节奏是"小步快走",每轮循环控制在几分钟内。一轮拖半小时就违背了 TDD 的初衷。

### CI/CD 为什么能降低发布风险

发布风险的本质是"变更量越大,出错概率越高"。一次性攒两周代码再发,出错后定位困难、回滚困难。CI/CD 的核心原理是"小步快跑 + 自动化":

- 小步快跑:每次提交都触发流水线,变更被切成原子小步。单步变更的影响范围小,出问题容易定位。
- 自动化:构建、测试、部署全由流水线执行,不依赖人手操作。人手操作是高发故障源——敲错命令、漏跑脚本、环境不一致,这些问题自动化后自然消失。
- 可回滚(Rollback):每次部署都对应一个可追溯的制品(Artifact)。出问题时能快速回退到上一个稳定版本,而不是"紧急改代码再发一次"。

CI/CD 不是"上了就不出 bug",而是"出 bug 后能快速发现、快速定位、快速恢复"。这三快才是它真正的价值。

### 流水线设计三大原则

把 CI/CD 落成具体流水线时,有三条原则必须守住:

1. 快速反馈:提交后几分钟内就要给出"能不能合"的信号。做不到这点,开发者会切去干别的,等回来看到红灯已经忘了改了啥。落地上,慢测试单独拆到后置 job,主链路只跑单元测试和 lint。
2. 阶段化(Stage):流水线切成"构建 → 测试 → 打包 → 部署"几个阶段,后阶段依赖前阶段成功。阶段化的好处是失败定位快——挂在测试阶段还是部署阶段一眼可见,而不是一锅粥。
3. 可回滚:每次部署都留存上一版制品,部署脚本内置回滚命令。生产事故时"先回滚再排查",比"边排查边修"安全得多。

这三条原则是后续选工具、写 YAML 的判断依据。工具可以换,原则不能丢。

## 三、实践

### 主流 CI/CD 工具选型

落地前先选工具。Jenkins、GitHub Actions、GitLab CI 三者定位不同:

- Jenkins:老牌开源,插件生态最全,能搭复杂流水线。代价是自建服务器、运维成本高,配置偏脚本化(Jenkinsfile 用 Groovy 写),适合有专职运维的团队。
- GitHub Actions:仓库托管在 GitHub 即可直接用,无需自建服务器,YAML 配置上手快,社区 Action 多。适合开源项目和小中型团队。
- GitLab CI:与 GitLab 代码仓库深度集成,内置 `.gitlab-ci.yml`,容器化执行器原生支持。适合用 GitLab 自托管的中大型团队。

选型核心看"代码托管在哪 + 团队是否愿意自建"。中小团队优先 GitHub Actions 或 GitLab CI,省运维;有复杂定制需求且已有运维力量的团队再考虑 Jenkins。

### pytest 单元测试示例(用 Mock)

场景:一个 `UserService` 依赖 `UserRepository` 查数据库。单元测试不该真的连数据库,所以用 Mock 把 Repository 替换掉,只验证 Service 的业务逻辑。

先看被测代码:

```python
# user_service.py
class UserNotFoundError(Exception):
    pass


class UserService:
    def __init__(self, repository):
        self.repository = repository

    def get_display_name(self, user_id: str) -> str:
        user = self.repository.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if user.get("nickname"):
            return user["nickname"]
        return user["email"].split("@")[0]
```

再看测试。用 `unittest.mock.Mock` 造一个假 Repository,用 `assert_called_once_with` 验证调用参数(Spy 的能力),用预设返回值控制行为(Stub 的能力):

```python
# test_user_service.py
from unittest.mock import Mock
import pytest
from user_service import UserService, UserNotFoundError


def test_get_display_name_uses_nickname_when_present():
    # Arrange:造一个返回带昵称用户的假 Repository
    repo = Mock()
    repo.find_by_id.return_value = {"email": "alice@example.com", "nickname": "爱丽丝"}
    service = UserService(repo)

    # Act
    name = service.get_display_name("u-001")

    # Assert:返回昵称,且 Repository 被以正确参数调用了一次
    assert name == "爱丽丝"
    repo.find_by_id.assert_called_once_with("u-001")


def test_get_display_name_falls_back_to_email_prefix():
    repo = Mock()
    repo.find_by_id.return_value = {"email": "bob@example.com", "nickname": ""}
    service = UserService(repo)

    assert service.get_display_name("u-002") == "bob"


def test_get_display_name_raises_when_user_not_found():
    repo = Mock()
    repo.find_by_id.return_value = None
    service = UserService(repo)

    with pytest.raises(UserNotFoundError):
        service.get_display_name("u-404")
```

Mock / Stub / Spy 三者差别要分清,面试常考:

- Stub(桩):预设返回值,让被测代码能往下走。上面的 `repo.find_by_id.return_value = {...}` 就是 Stub 用法。
- Mock(模拟对象):在 Stub 基础上还能验证交互——"这个方法被调了吗?参数对吗?调了几次?"。`assert_called_once_with` 是 Mock 独有的能力。
- Spy(间谍):包裹真实对象,既调用真实逻辑,又记录调用情况。`Mock(spec=RealRepository)` 或 `patch` 的 `wraps` 参数属于这类。

经验:能用 Stub 验证的别用 Mock,能用 Mock 的别用 Spy。验证越多,测试越脆——重构内部实现就要改测试,违背了"测试保护行为而非实现"的原则。

### TDD 红-绿-重构小例子

需求:写一个 `format_discount_price`,接收原价和会员等级,返回折扣后保留两位小数的价格字符串。规则:普通会员 9 折,银卡 8 折,金卡 7 折;负数价格抛异常。

第一步:红。先写测试,此时函数还不存在,运行必然报错。

```python
# test_price.py
import pytest
from price import format_discount_price, InvalidPriceError


def test_normal_member_gets_10_percent_off():
    assert format_discount_price(100.0, "normal") == "90.00"


def test_silver_member_gets_20_percent_off():
    assert format_discount_price(100.0, "silver") == "80.00"


def test_gold_member_gets_30_percent_off():
    assert format_discount_price(100.0, "gold") == "70.00"


def test_negative_price_raises():
    with pytest.raises(InvalidPriceError):
        format_discount_price(-10.0, "normal")
```

运行 `pytest`,报 `ModuleNotFoundError`——红。

第二步:绿。写最小实现让测试通过。注意"最小",不要顺手加重构、加配置。

```python
# price.py
class InvalidPriceError(Exception):
    pass


def format_discount_price(price: float, level: str) -> str:
    if price < 0:
        raise InvalidPriceError()
    rates = {"normal": 0.9, "silver": 0.8, "gold": 0.7}
    final = price * rates[level]
    return f"{final:.2f}"
```

运行 `pytest`,四个用例全绿。

第三步:重构。在测试保护下清理代码——把折扣率抽成模块级常量,把未知等级的处理显式化:

```python
# price.py(重构后)
class InvalidPriceError(Exception):
    pass


DISCOUNT_RATES = {"normal": 0.9, "silver": 0.8, "gold": 0.7}


def format_discount_price(price: float, level: str) -> str:
    if price < 0:
        raise InvalidPriceError()
    if level not in DISCOUNT_RATES:
        raise ValueError(f"未知会员等级: {level}")
    final = price * DISCOUNT_RATES[level]
    return f"{final:.2f}"
```

重构后再跑一次 `pytest`,仍然全绿,说明重构没破坏行为。这就是 TDD 给重构的底气——没有测试保护的重构叫"裸奔"。

### GitHub Actions workflow YAML

一个覆盖"测试 → 构建 → 打镜像"的完整 workflow。文件放在仓库 `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: 设置 Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 安装依赖
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: 跑测试并收集覆盖率
        run: pytest --cov=src --cov-report=xml --cov-report=term

      - name: 上传覆盖率报告
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: 登录镜像仓库
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USER }}
          password: ${{ secrets.DOCKER_TOKEN }}

      - name: 构建并推送镜像
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            myrepo/app:${{ github.sha }}
            myrepo/app:latest
```

读这份 YAML 要抓几个关键点:

- `on` 触发器:push 到 main/develop 或对 main 提 PR 时触发。流水线第一道闸门就在这里。
- `jobs.test` 与 `jobs.build` 是两个 job,`build` 用 `needs: test` 声明依赖,测试不通过就不构建。这就是阶段化——后一步依赖前一步的成功。
- `if: always()` 让覆盖率报告即使测试失败也上传,方便排查。
- `${{ secrets.XXX }}` 引用仓库密钥,密码不会写进 YAML、不会出现在日志里。这是 CI 安全的基本要求。
- 镜像 tag 同时打 `github.sha`(可追溯,对应某次提交)和 `latest`(便于拉取)。生产环境应优先用 sha tag,避免 `latest` 漂移。

### 制品管理:Docker 镜像与 Helm Chart

CI 跑完产出的可部署物叫制品(Artifact)。后端常见制品是 Docker 镜像, Kubernetes 部署还会配 Helm Chart。

制品管理三条铁律:

1. 制品不可变:同一个 tag 对应的内容必须恒定。`latest` 是反模式——今天拉的 latest 和明天拉的可能完全不同,出问题无法复现。正确做法用 git commit sha 或语义化版本做 tag。
2. 制品有唯一来源:镜像只能由 CI 构建,不允许人手 `docker build` 后推送。人手构建的镜像没法保证和 CI 环境一致,是"在我机器上能跑"问题的根源。
3. 制品可追溯:每个镜像能反查到构建它的 commit、流水线编号、时间戳。Docker 镜像的 label 字段就是干这个的,建议至少打 `org.opencontainers.image.revision` 和 `org.opencontainers.image.created`。

Helm Chart 是 Kubernetes 应用的打包格式,把 Deployment、Service、ConfigMap 这些 YAML 模板和可配置参数打包在一起。版本管理上,Chart 版本和镜像版本要分开维护——Chart 改了模板就升 Chart 版本,应用代码变了升镜像 tag,两者独立演进。

## 四、速查/自测

### 测试类型对照表

| 类型 | 验证范围 | 依赖外部 | 速度 | 数量建议 | 稳定性 |
|---|---|---|---|---|---|
| 单元测试 | 单个函数/类 | 否(Mock 掉) | 毫秒级 | 多 | 高 |
| 集成测试 | 多模块协作 | 部分(真实 DB/中间件) | 秒级 | 中 | 中 |
| 接口测试 | API 入口到业务层 | 是(起服务) | 秒级 | 中 | 中 |
| 端到端测试 | 用户操作全链路 | 全部(浏览器+全栈) | 分钟级 | 少 | 低 |

接口测试与集成测试容易混。区分标准:集成测试关注"模块之间协作对不对"(Service 调 Repository),接口测试关注"对外暴露的 API 契约对不对"(请求格式、状态码、响应结构)。一个偏内部组装,一个偏外部契约。

### 测试覆盖率陷阱

覆盖率(Coverage)分三种:行覆盖(执行到的代码行)、分支覆盖(if/else 各分支是否都走到)、函数覆盖(函数是否被调用过)。

覆盖率不是越高越好。盲目追 100% 行覆盖会逼出大量"为了覆盖而覆盖"的无意义测试——比如给 getter/setter 写测试、给异常分支塞一个永远走不到的用例。这种测试不保护行为,只保护数字。

经验阈值:核心业务模块分支覆盖率 80% 以上有意义,工具脚本、原型代码追 60% 即可。比覆盖率更重要的是"关键路径有没有被测到"——下单、支付、鉴权这些路径,哪怕整体覆盖率只有 50%,这几条必须全覆盖。用覆盖率找"没测到的代码",而不是拿覆盖率当 KPI。

### 自测题

1. 一个团队抱怨"测试套件跑 40 分钟,大家都不愿意本地跑"。你会从测试金字塔的哪一层开始排查?为什么?
2. `Mock` 和 `Stub` 都能预设返回值,为什么说"能用 Stub 别用 Mock"?给出一个 Mock 用多了导致测试变脆的具体场景。
3. TDD 三步循环里,为什么"绿"阶段要求写最小实现?如果顺手把下个测试的代码也写了,会破坏什么?
4. 上面的 GitHub Actions YAML 里,`build` job 用了 `needs: test`。如果去掉这行,两个 job 并行跑,会出什么问题?
5. 同一个 Docker 镜像 tag `myrepo/app:latest` 被两个不同的 commit 构建推送过,生产环境用它部署后出 bug。这个问题在制品管理上违反了哪条铁律?怎么修?

### 可交给 AI 的部分

- 完整单元测试用例:给 AI 一段函数实现和它的边界条件,让它生成 AAA 模式的 pytest 用例,覆盖正常路径、边界值、异常分支。研发只做复核,确认断言符合业务语义。
- Jenkins Pipeline 脚本:Jenkins 的 declarative pipeline 语法繁琐,把构建/测试/部署阶段描述清楚,AI 能直接生成可用的 `Jenkinsfile`。
- 项目脚手架:CI 配置、Dockerfile、Helm Chart 模板、测试目录结构这种套路化产物可以让 AI 一次生成,研发按项目实际微调。
- 测试数据工厂:让 AI 根据数据模型生成构造测试数据的工厂函数,覆盖各种字段组合。

风险提示:

- AI 生成的测试容易出现"复制实现逻辑当断言"的反模式——测试里把被测代码的逻辑又写了一遍,等于用同一份逻辑验证同一份逻辑,bug 会两边一起漏。必须人工核对断言是基于"期望行为"还是"实现细节"。
- AI 写的覆盖率高的测试常常是无效测试:给每个分支塞一个用例,但断言空洞(`assert result is not None`),数字漂亮却保护不了行为。要看断言强度,不看用例数量。
- AI 生成的 CI YAML 容易把密钥硬编码或权限开过大(比如 `permissions: write-all`)。安全相关字段必须人工审查,默认最小权限。
- AI 不擅长判断"哪些路径是关键路径",会平均用力。核心业务和工具脚本一视同仁地追覆盖率,产出大量低价值测试。优先级判断必须由人定。

## 参考来源

- [1] Kent Beck:《测试驱动开发》2002
- [2] Jez Humble, David Farley:《持续交付:发布可靠软件的系统方法》2010
- [3] Martin Fowler:Test Pyramid https://martinfowler.com/articles/practical-test-pyramid.html
- [4] pytest 官方文档:https://docs.pytest.org/
- [5] GitHub Actions 官方文档:https://docs.github.com/actions
- [6] Jenkins 官方文档:https://www.jenkins.io/doc/
- [7] unittest.mock 官方文档:https://docs.python.org/3/library/unittest.mock.html
- [8] GitLab CI/CD 官方文档:https://docs.gitlab.com/ee/ci/
- 本专栏第 12 章「Linux与容器基础」(Docker 镜像分层与制品管理的前置)
- 本专栏第 18 章「分层微服务与DDD」(微服务独立部署依赖 CI/CD 流水线)
