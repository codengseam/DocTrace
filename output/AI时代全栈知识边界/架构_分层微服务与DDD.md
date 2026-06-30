---
title: AI时代全栈知识边界·18|分层微服务与DDD
book: AI时代全栈知识边界
chapter: 架构
event: 分层微服务与DDD
sort: 1
chapter_sort: 8
created_at: 2026-06-30
source_agents: [fullstack-expert]
---

# AI时代全栈知识边界·18|分层微服务与DDD

> 前置知识:面向对象基础、HTTP 接口调用、关系型数据库 CRUD、Python 语法
> 学完你能:看懂中大型项目的目录分层,按业务边界拆出微服务,用聚合根保护领域一致性,判断该用单体还是 Serverless

## 一、概念

分层、微服务、DDD 解决的是同一类问题——代码量上去之后怎么不乱。三者切入角度不同:分层是纵向切职责,微服务是横向切部署,DDD 是从业务侧往代码侧建模。

- 分层架构(Layered Architecture):把代码按职责切成竖向几层,上层依赖下层,层与层之间用接口隔离。
- 微服务(Microservices):把一个单体应用按业务边界拆成多个独立部署的小服务,每个服务跑自己的进程、自己的数据库。
- DDD(Domain-Driven Design,领域驱动设计):一套让代码结构对齐业务结构的方法论,核心是用限界上下文、聚合根这些概念把业务模型翻译成代码模型。

英文术语首次出现给中英对照:

- Bounded Context:限界上下文
- Aggregate Root:聚合根
- Domain Event:领域事件
- Value Object:值对象
- Entity:实体
- Repository:仓储
- Ubiquitous Language:统一语言

## 二、原理

### 为什么分层:关注点分离

不分层的时候,一个函数里既校验参数、又查数据库、又拼 HTML 返回。改一个 SQL 要碰渲染逻辑,改一个字段要碰数据库。分层把这三件事物理隔开:

- Presentation(表示层):只管接收请求、返回响应。
- Business(业务层):只管业务规则。
- Data(数据层):只管持久化。

每层只跟相邻层说话,跨层调用是反模式——Controller 直接读 ORM session 就属于这种。这就是关注点分离(Separation of Concerns),本质是让变更的影响范围收敛在单层。

分层不是越多越好。三层够用就别上五层,层数过多会让调用链变长、调试困难,把简单 CRUD 写成俄罗斯套娃。

### 微服务拆分的边界:单一职责 + 独立部署

单体跑得动就别拆。拆的代价是网络调用、分布式事务、链路追踪、运维复杂度全上来。但当出现下面这些信号时,拆分开始有正收益:

- 团队规模超过 8 人,代码合并冲突频繁。
- 某个模块的发布节奏跟主应用不一致(比如支付每周发,商品每月发)。
- 某个模块的资源需求特殊(要 GPU、要大内存、要低延迟连接)。
- 某个模块的可用性要求高于其他模块(支付 99.99%,商品 99.9%)。

拆分边界靠两条原则:

1. 单一职责:一个服务只干一件事,一次业务变更只动一个服务。
2. 独立部署:服务之间不共享数据库、不共享代码,通过 API 通信。

实际拆分经常踩的坑:按技术职能拆(一个服务专门发邮件、一个服务专门算价格)。这种拆法违反业务边界——价格规则变更本来就该在商品域内闭环,拆出去反而要跨服务协调。正确拆法按业务能力或子域拆,这是 DDD 提供的方法论支撑。

### DDD 为什么能解决复杂业务:让代码结构与业务结构对齐

普通 CRUD 项目写 DDD 是过度设计。DDD 的适用场景是业务规则复杂、领域专家深度参与的项目,比如保险核保、供应链调度、金融结算。核心原理是用统一语言让产品和研发说同一套话,然后把业务模型直接映射成代码模型:

- 限界上下文划清业务边界,一个上下文内术语含义唯一。"商品"在销售上下文里是有价格的售卖单元,在仓储上下文里是物理库存单元,含义不同就分到不同上下文。
- 聚合根保证一致性边界,外部只能通过聚合根修改内部状态,聚合根内部的不变量自己保护。
- 领域事件解耦上下文之间的影响,订单上下文不需要知道支付上下文的内部实现,只消费"订单已支付"这个事件。

这样代码改起来跟业务讨论是同构的——产品说"已支付订单不能加商品",代码里就一行 `if self.status != OrderStatus.CREATED: raise`。不用再做一次翻译,长期维护成本下降。

## 三、实践

### DDD 风格目录结构

下面是一个订单服务的标准 DDD 目录,依赖方向是 `interfaces → application → domain ← infrastructure`,domain 是最内层、不依赖任何框架,infrastructure 实现 domain 定义的接口(依赖倒置)。

```text
order-service/
├── domain/                  # 领域层,纯业务,不依赖框架
│   ├── model/
│   │   ├── order.py         # 聚合根 Order
│   │   ├── order_item.py    # 实体
│   │   ├── address.py       # 值对象
│   │   └── order_event.py   # 领域事件
│   ├── service/             # 领域服务,跨聚合逻辑
│   └── repository.py        # 仓储接口(抽象)
├── application/             # 应用层,编排用例,事务边界
│   ├── command/
│   │   ├── create_order.py
│   │   └── cancel_order.py
│   └── query/
│       └── order_query.py
├── infrastructure/          # 基础设施层,技术实现
│   ├── persistence/
│   │   ├── order_repo_impl.py   # 仓储实现
│   │   └── orm_models.py        # SQLAlchemy 模型
│   ├── messaging/
│   │   └── kafka_producer.py
│   └── config.py
├── interfaces/              # 接口层,对接外部
│   ├── api/
│   │   └── order_routes.py
│   └── grpc/
└── main.py
```

四层职责:

- domain:业务规则的家,聚合根、实体、值对象、领域事件、仓储接口都在这里。这一层不该出现 `import sqlalchemy` 或 `import fastapi`。
- application:用例编排,调聚合根方法、调仓储、发事件、开事务,本身不写业务规则。
- infrastructure:仓储实现、消息生产者、外部 API 客户端,是 domain 接口的具体技术落地。
- interfaces:HTTP 路由、gRPC 服务、CLI 入口,负责协议转换,不写业务。

### 聚合根 Python 代码示例

```python
from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(Enum):
    CREATED = "created"
    PAID = "paid"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Address:
    """值对象:不可变,无唯一标识,用属性判等。"""
    province: str
    city: str
    detail: str


@dataclass
class OrderItem:
    """实体:有唯一标识 item_id,可变。"""
    item_id: str
    product_id: str
    quantity: int
    price: float


class DomainError(Exception):
    pass


@dataclass
class Order:
    """聚合根:外部唯一入口,所有不变量在此保护。"""
    order_id: str
    user_id: str
    items: list[OrderItem] = field(default_factory=list)
    address: Address | None = None
    status: OrderStatus = OrderStatus.CREATED
    events: list = field(default_factory=list)

    def add_item(self, item: OrderItem) -> None:
        # 不变量 1:已支付订单不能加商品
        if self.status != OrderStatus.CREATED:
            raise DomainError("已支付订单不能添加商品")
        # 不变量 2:同一商品累加数量,不重复挂行
        for existing in self.items:
            if existing.product_id == item.product_id:
                existing.quantity += item.quantity
                return
        self.items.append(item)

    def pay(self) -> None:
        if self.status != OrderStatus.CREATED:
            raise DomainError("仅新建订单可支付")
        if not self.items:
            raise DomainError("空订单不能支付")
        self.status = OrderStatus.PAID
        # 领域事件只 append 到列表,实际发送交给应用层
        self.events.append({"type": "OrderPaid", "order_id": self.order_id})

    def cancel(self) -> None:
        if self.status == OrderStatus.PAID:
            raise DomainError("已支付订单不能取消,请走退款流程")
        self.status = OrderStatus.CANCELLED
        self.events.append({"type": "OrderCancelled", "order_id": self.order_id})

    def total_amount(self) -> float:
        return sum(i.price * i.quantity for i in self.items)
```

读这段代码要抓的几个关键点:

- `Order` 是聚合根,外部不能直接改 `items` 或 `status`,必须走 `add_item` / `pay` / `cancel`。这就是一致性边界。
- `Address` 是值对象,`frozen=True`,改地址要换一个新对象而不是改字段——这是值对象的判等靠属性、不靠身份。
- 不变量(已支付不能加商品、空订单不能支付、已支付不能取消)写在聚合根内部,任何调用方都绕不过,业务规则不会被散落在多个 Service 里。
- 领域事件只 append 到列表,实际发送(发 Kafka、调外部 API)交给应用层或基础设施层,聚合根本身不依赖消息中间件。这保证了 domain 层的纯净。

### 微服务拆分前后对比

拆分前(单体):

```text
┌─────────────────────────────────────┐
│           单体应用 monolith          │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  │用户 │ │商品 │ │订单 │ │支付 │   │  ← 共用一个数据库
│  └─────┘ └─────┘ └─────┘ └─────┘   │
│       共用代码、共用部署、共用进程   │
└─────────────────────────────────────┘
```

典型问题:商品团队改商品表结构,订单团队被迫一起发版;支付模块 OOM 把整个应用拖垮;商品做大促要扩容,被迫整体扩容。

拆分后(微服务):

```text
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 用户服务  │  │ 商品服务  │  │ 订单服务  │  │ 支付服务  │
│  user-db │  │ product- │  │  order-  │  │ payment- │
│          │  │   db     │  │   db     │  │   db     │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     └─────────────┴──────┬──────┴─────────────┘
                          │
                   ┌──────┴──────┐
                   │ API 网关 /   │
                   │  消息总线    │
                   └─────────────┘
```

每个服务独立数据库、独立部署、独立技术栈。订单服务调商品服务走 HTTP 或 gRPC(同步),跨上下文一致性靠领域事件 + 最终一致性(异步)。拆分后带来的新成本:链路追踪、服务发现、分布式事务补偿、配置中心,这些在单体里都不存在。

### 跨模块调用设计

服务间调用分两类,选错代价很大:

- 同步调用(HTTP/gRPC):适合需要立即拿到结果的核心链路,比如下单时查商品库存。代价是耦合可用性——下游挂了上游也挂,要配熔断、超时、降级。
- 异步事件(消息队列):适合不需要立即结果的下游影响,比如支付成功后发积分、推通知。代价是最终一致性,要处理幂等、消息重试、乱序。

经验法则:同一个用户请求链路上的核心步骤用同步,周边副作用用异步。订单支付这条链路里,"扣减库存"如果允许短时不一致可以用事件,但"扣款"必须同步,否则用户体验崩。

## 四、速查/自测

### 架构模式适用场景对照表

| 模式 | 适用场景 | 优点 | 缺点 |
|---|---|---|---|
| 单体架构 | 团队 <8 人,业务单一,早期 MVP | 开发部署简单,本地调试方便 | 单点故障,扩展性差,代码互相污染 |
| 分层架构 | 中等规模业务,CRUD 为主 | 关注点分离,结构清晰 | 容易退化成"事务脚本",业务规则散落 |
| 微服务 | 团队多业务线,发布节奏不一,需独立扩展 | 独立部署,故障隔离,技术栈自由 | 运维复杂,分布式事务难,调试链路长 |
| Serverless(FaaS) | 事件驱动,突发流量,后台任务 | 按调用付费,零运维,自动扩缩 | 冷启动延迟,本地难调试,有最长执行时限 |
| DDD | 业务规则复杂,领域专家深度参与 | 代码与业务同构,长期可维护 | 学习成本高,小项目过度设计 |

### SOLID 设计原则速查

| 原则 | 中文 | 一句话 |
|---|---|---|
| SRP | 单一职责 | 一个类只为一个变更原因而改 |
| OCP | 开闭原则 | 扩展开放,修改关闭,靠抽象实现 |
| LSP | 里氏替换 | 子类能无缝替换父类,行为不变形 |
| ISP | 接口隔离 | 不强迫依赖用不到的方法 |
| DIP | 依赖倒置 | 高层不依赖低层,都依赖抽象 |

### 耦合与内聚速查

- 耦合:模块之间相互依赖的程度,越低越好。从坏到好:内容耦合 > 公共耦合 > 控制耦合 > 数据耦合。
- 内聚:模块内部元素相关联的程度,越高越好。从坏到好:偶然内聚 < 逻辑内聚 < 时间内聚 < 通信内聚 < 顺序内聚 < 功能内聚。
- 目标:高内聚低耦合,DDD 的聚合根就是功能内聚的极致体现。

### 自测题

1. 一个聚合根内同时有"订单"和"收货地址",收货地址应该建模成实体还是值对象?为什么?
2. 微服务拆分时,"用户服务"和"订单服务"都需要用户信息,该共享数据库还是通过 API 调用?理由是什么?
3. 订单支付成功后要扣减库存,这个操作如果跨"订单"和"库存"两个聚合根,应该用同步调用还是领域事件?各自的代价是什么?
4. Serverless 函数处理一个耗时 5 分钟的视频转码任务,直接用 FaaS 会有什么问题?怎么改?
5. 一个三层架构项目,Controller 里直接调用了 SQLAlchemy 的 `session.execute()`,这违反了哪条原则?怎么修?

### 可交给 AI 的部分

- 完整架构图绘制:给 AI 一段业务描述,让它输出 PlantUML 或 Mermaid 的架构图、时序图,人工只需校验边界是否合理。
- UML 类图与领域模型草图:把领域名词列表喂给 AI,生成聚合关系图作为讨论起点,研发再按业务规则修正。
- CRUD 模板生成:Repository 接口、ORM 模型、Controller 路由这种套路化代码可以让 AI 直接生成,研发只关心聚合根内的不变量。
- 分层脚手架:让 AI 生成一个 DDD 四层目录骨架 + 依赖注入配置,省去搭项目的时间。

风险提示:

- AI 容易把聚合边界划得过粗或过细,需要领域专家复核。常见错误是把所有相关实体塞进一个聚合根,导致聚合过大、并发冲突严重。
- AI 生成的微服务拆分方案经常忽略分布式事务代价,要先评估一致性需求再采纳,别被"高内聚低耦合"的话术带跑。
- AI 画的架构图可能"看起来很对"但违反依赖方向(比如 domain 反向依赖 infrastructure),必须人工审查 import 关系。
- AI 不擅长判断业务复杂度,会无脑推荐 DDD。CRUD 项目用了 DDD 反而拖慢开发,决策权必须在人手里。

## 参考来源

- [1] Eric Evans:《领域驱动设计:软件核心复杂性应对之道》2003
- [2] Robert C. Martin:《架构整洁之道》2017
- [3] Sam Newman:《微服务设计》2015
- [4] Vaughn Vernon:《实现领域驱动设计》2013
- [5] Martin Fowler:Patterns of Enterprise Application Architecture https://martinfowler.com/books/eaa.html
- [6] 微软 Azure 架构中心:Cloud Design Patterns https://learn.microsoft.com/azure/architecture/patterns/
- [7] Richardson Chris:《微服务架构设计模式》2018
- 本专栏第 17 章「RESTful API 与接口契约」(微服务间通信的基础)
- 本专栏第 19 章「分布式一致性协议」(微服务拆分后的数据一致性续篇)
