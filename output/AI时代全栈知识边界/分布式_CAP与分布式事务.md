---
title: AI时代全栈知识边界·27|CAP与分布式事务
book: AI时代全栈知识边界
chapter: 分布式
event: CAP与分布式事务
sort: 1
chapter_sort: 13
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·27|CAP与分布式事务

> 前置知识:理解数据库 ACID 事务与隔离级别、知道主从复制的基本形态、会用一门后端语言写带事务的接口、了解网络不可靠是常态而非异常
> 学完你能:① 说清 CAP 三选二的工程含义,并解释为什么分区时只能选 C 或 A ② 区分强一致性、弱一致性、最终一致性三者的一致性强度与典型系统 ③ 画出 Raft 的 Leader-Follower 选主与日志复制流程,说明它为何比 Paxos 易理解 ④ 用 Python 写一个线程安全的 Snowflake ID 生成器并解释时钟回拨处理 ⑤ 写出本地消息表的订单服务 + 消息表 + MQ 投递伪代码 ⑥ 给出 TCC 三个接口的伪代码与异常补偿路径 ⑦ 按一致性强度、性能、业务侵入三个维度为业务选 2PC/TCC/Saga/本地消息表

### 一、概念

CAP(Consistency-Availability-Partition Tolerance,一致性-可用性-分区容错)是分布式系统的一条理论定理:在一个跨网络的分布式系统中,一致性、可用性、分区容错三者不可同时满足,最多选其二。分布式事务(Distributed Transaction)指横跨多个独立服务或多个数据节点的事务,要求这些服务要么一起成功提交、要么一起回滚,把单机 ACID(Atomicity-Consistency-Isolation-Durability,原子性-一致性-隔离性-持久性)的语义延伸到分布式环境。

两者回答同一个核心问题:**数据被复制到多台机器上,面对网络抖动与节点宕机,系统该优先保什么**。CAP 给出理论边界,分布式事务给出工程实现。

先把后文反复出现的术语对齐:

- **C(Consistency,一致性)**:线性一致性,所有节点同一时刻看到相同数据,读总返回最新写入值或失败。
- **A(Availability,可用性)**:每个非故障节点的请求都能收到非错响应(允许不是最新)。
- **P(Partition Tolerance,分区容错)**:网络分区时系统仍能运作。
- **BASE**:CAP 的工程化妥协,放弃强一致换可用性与性能。
- **2PC / 3PC**:协调者驱动的两阶段/三阶段提交协议。
- **TCC(Try-Confirm-Cancel)**:业务层面的两阶段,每个分支需实现 Try/Confirm/Cancel 三个接口。
- **Saga**:长事务拆成多个本地事务,失败时按反序执行补偿事务。
- **Raft / Paxos**:两类共识算法(Consensus Algorithm),解决多节点如何就同一值达成一致。
- **Snowflake**:Twitter 提出的分布式 ID 生成算法,64 位整数由时间戳 + 机器号 + 序列号组成。

### 二、原理

#### 1. CAP 为什么是三选二

很多人记得"CAP 三选二"却讲不清为什么。本质在于:**网络分区不可避免,所以 P 是默认项;真正要选的是分区发生时保 C 还是保 A**。

分布式系统跨网络部署,网络会因交换机故障、机房断网、链路拥塞发生分区(Partition)——A、B 两组节点互不可达。此时一个写请求到了 A 组,数据要复制到 B 组才能保证一致性,但网络不通。系统只有两条路:

- **保 C(拒绝写入)**:A 组拒绝该请求,返回错误或超时。一致性保住了(不会出现 A、B 数据不一致),但牺牲了可用性——分区期间系统不可写。
- **保 A(允许写入)**:A 组接受写入并返回成功,等分区恢复后再同步到 B 组。可用性保住了,但分区期间 B 组读到的还是旧值,违反线性一致性。

因此 CAP 不是"三选二"的并列关系,而是"P 必选,C 与 A 二选一"。Brewer 在 2000 年 PODC 会议上提出 CAP 猜想,Gilbert 与 Lynch 在 2002 年用形式化证明把它定为定理。后来 Brewer 本人在 2012 年撰文澄清:CAP 中"三选二"是过于简化的表述,真实系统在分区未发生时可同时近似 C 与 A,只在分区期间被迫选择。

工程上的三类系统对应三种选择:**CP 系统**(如 etcd、ZooKeeper、HBase)分区时拒绝写入以保一致;**AP 系统**(如 Cassandra、Eureka、DynamoDB)分区时继续服务以保可用,接受最终一致;**CA 系统**在分布式语境下几乎不存在,因为只要跨网就必然有 P,单机数据库才是真 CA。

#### 2. BASE 是 CAP 的工程化妥协

互联网业务极少能容忍"分区期间整个系统不可写"。电商大促时某机房网络抖动几十秒,若系统选 CP 直接拒绝下单,损失远大于"短暂数据不一致后修复"。BASE 就是这种业务现实的产物:

- **Basically Available(基本可用)**:故障期间允许响应时间变长、允许非核心功能降级,但不整体下线。
- **Soft State(软状态)**:接受中间状态存在,如"订单已支付但积分未到账"的过渡态。
- **Eventually Consistent(最终一致性)**:不要求实时一致,只要不再有新写入,经过一段时间后所有副本最终收敛到一致。

BASE 不是新理论,而是 AP 系统的工程宣言。它把"一致性"从一个二值开关(强/弱)拆成一条连续谱系,允许业务按需选择"多强、多久收敛"。这条谱系正是下一节要展开的内容。

#### 3. 一致性强度谱系

线性一致性(Linearizability)是最强的强一致性,读必返回最新写入,且操作有全局先后顺序。代价是每次写都要同步到多数派节点,延迟高、可用性受限。典型代表是 etcd、ZooKeeper 这类元数据存储。

弱一致性放宽了"读返回最新"的约束,只保证写成功后某个时刻部分节点能看到。会话一致性(Session Consistency)是常见子类:同一客户端的读能看到自己之前的写,跨客户端则不保证。CDN 与浏览器缓存走的就是这一档。

最终一致性是弱一致性的特例:保证最终收敛,但不保证何时收敛。DNS 是最经典的最终一致系统——一条记录修改后,全球 DNS 服务器最长可能 48 小时才全部刷新。互联网业务里 90% 以上的场景(订单状态、商品库存、用户积分、消息已读)用最终一致性就够。

选型判据只有一个:**业务能否容忍"短暂不一致窗口"**。能容忍就用最终一致换性能,不能容忍才上强一致。金融账户余额、库存扣减到 0 这类场景往往不能容忍,但要付出的代价是吞吐降一个数量级。

#### 4. Raft 为什么比 Paxos 易理解

Paxos 是 Lamport 1998 年正式发表的经典共识算法,理论上完备但极难理解。Raft 是 Stanford 团队 2014 年在 USENIX ATC 上提出的算法,目标明确:**为了可理解性而设计**(designed for understandability)。

两者本质都靠"多数派写"达成共识,差异在于结构:

- **Paxos** 是无主(Leaderless)模型,任何节点都能提案,提案号互相竞争,通过两阶段 Prepare/Accept 收敛。工程实现(如 Multi-Paxos)需要自己补 Leader 选举、日志复制、日志压缩等细节,论文都没明说。
- **Raft** 把共识问题显式拆成三个子问题:**Leader Election(选主)**、**Log Replication(日志复制)**、**Safety(安全性)**。任意时刻只有一个 Leader,所有写都经 Leader,Leader 把日志复制到多数派后提交,再通知 Follower 提交。这种"单点写入 + 多数派复制"把并发问题降到了单线程级别。

Raft 易理解的根本机制是 **Leader 解耦了阶段**:Paxos 里每个提案都要走完整 Prepare-Accept 两阶段,Raft 里 Leader 选出来后,后续写只需 Append + Replicate 一阶段(选主成本摊到很长一段写周期)。这正是 etcd、Consul、TiKV 都选 Raft 的原因。

适用场景:Raft 适合强一致元数据存储、配置中心、分布式锁、SQL 数据库的共识层;Paxos 系列更适合对吞吐有极致要求、能承受实现复杂度的大规模存储(如 Google Chubby、Spanner 的 Paxos 组)。

#### 5. 分布式事务方案的权衡谱系

分布式事务的核心矛盾是 **一致性强度 vs 性能 vs 业务侵入** 三者不可兼得。按这三维度排列主流方案:

**2PC(Two-Phase Commit,两阶段提交)** 是最经典的强一致方案。协调者(Coordinator)先发 Prepare 给所有参与者,参与者锁定资源并预写日志,全部 Yes 才进第二阶段 Commit,任一 No 则 Rollback。优点是强一致、对业务透明;缺点有三个——同步阻塞(参与者锁资源直到第二阶段结束)、协调者单点(协调者在 Commit 前宕机,参与者长期阻塞)、网络分区下数据不一致风险(Commit 阶段部分参与者没收到消息,出现部分提交)。XA 协议是 2PC 在数据库层面的工业标准实现。

**3PC(Three-Phase Commit,三阶段提交)** 在 2PC 中间插入 CanCommit 询问,并把超时引入参与者:参与者超时后自动提交(假设协调者已 Commit)。3PC 缓解了协调者单点导致的阻塞,但引入新问题——网络分区下仍可能不一致,且多一轮 RTT 进一步降吞吐。生产中 3PC 几乎不用,工程界更多直接跳到 TCC 或 Saga。

**TCC(Try-Confirm-Cancel)** 把两阶段从资源层上移到业务层。每个分支服务要实现三个接口:Try(预留资源,如冻结余额)、Confirm(确认提交,真正扣款)、Cancel(释放资源,解冻余额)。优点是无资源锁、性能高;缺点是业务侵入大,每个操作都要写三套代码,且要保证 Confirm/Cancel 幂等。

**本地消息表** 是最终一致性的代表方案。业务表与消息表放在同一数据库,业务事务里同时写业务数据与消息记录,事务保证两者原子落库;后台任务轮询消息表把未投递的消息发到 MQ,下游消费后回写状态。优点是无需协调者、与现有 MQ 体系无缝结合;缺点是只保证最终一致,不适合强一致场景。

**Saga** 适合长事务。把一个分布式事务拆成 N 个本地事务 T1...Tn,每个 Ti 配一个补偿事务 Ci。任一 Ti 失败,按反序执行已成功事务的补偿。Saga 没有锁、吞吐高,但补偿逻辑复杂,且中间状态对业务可见。

**Seata / DTM** 是开源分布式事务框架。Seata 支持 AT、TCC、Saga、XA 四种模式,AT 模式靠自动生成反向 SQL 实现无侵入补偿;DTM 主打 Saga 与 TCC,跨语言支持更好。框架把上述方案的样板代码、失败重试、补偿调度、监控埋点工程化。

### 三、实践

#### 1. 本地消息表:订单服务 + 消息表 + MQ

下面是一个最小可用的本地消息表实现,核心是"业务与消息同库写入 + 后台扫描投递":

```python
import time
import threading
import queue


# 模拟订单表与消息表(实际生产用 MySQL 同库)
class DB:
    def __init__(self):
        self.orders = []          # 订单表
        self.messages = []        # 本地消息表
        self._tx_lock = threading.Lock()

    def transaction(self, order_id, user_id, amount, msg_id, payload):
        """一个本地事务:写订单 + 写消息表,要么都成功要么都回滚"""
        with self._tx_lock:
            self.orders.append({"order_id": order_id, "user_id": user_id,
                                "amount": amount, "status": "created"})
            self.messages.append({"msg_id": msg_id, "payload": payload,
                                  "status": "pending",  # pending/done
                                  "retry": 0, "next_try_at": time.time()})
            # 事务提交点:此处两者原子落库


class MessagePoller(threading.Thread):
    """后台扫描消息表,把 pending 消息投到 MQ"""

    def __init__(self, db, mq):
        super().__init__(daemon=True)
        self.db = db
        self.mq = mq
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            now = time.time()
            for msg in self.db.messages:
                if msg["status"] != "pending":
                    continue
                if msg["next_try_at"] > now:
                    continue
                try:
                    self.mq.publish("order_created", msg["payload"])
                    msg["status"] = "done"
                except Exception:
                    msg["retry"] += 1
                    # 指数退避:1s, 2s, 4s, 8s...上限 60s
                    backoff = min(60, 2 ** msg["retry"])
                    msg["next_try_at"] = now + backoff
            time.sleep(0.5)


class MQ:
    """模拟 MQ,实际生产用 Kafka / RabbitMQ"""
    def __init__(self):
        self._subscribers = []

    def publish(self, topic, payload):
        # 真实 MQ 通过 ack 机制确认投递成功
        for cb in self._subscribers:
            cb(payload)

    def subscribe(self, callback):
        self._subscribers.append(callback)


# 使用:下单 + 异步通知积分服务
db = DB()
mq = MQ()
poller = MessagePoller(db, mq)
poller.start()

# 积分服务订阅消息
def add_points(payload):
    print(f"[积分服务] 为订单 {payload['order_id']} 加 {payload['amount']} 积分")
mq.subscribe(add_points)

# 用户下单(业务事务里同步写订单与消息)
import uuid
db.transaction(
    order_id="ORD-20260630-001",
    user_id="U1001",
    amount=100,
    msg_id=str(uuid.uuid4()),
    payload={"order_id": "ORD-20260630-001", "user_id": "U1001", "amount": 100},
)
```

这段代码的关键点有三个。第一,**业务表与消息表必须在同一数据库**,靠本地事务保证"订单写入成功"与"消息记录写入成功"原子,这是整个方案成立的前提——如果跨库,业务成功但消息丢失就成了孤儿订单。第二,**后台轮询的退避策略必须指数增长**,固定间隔会导致消息积压时雪崩式重试打爆下游。第三,**消息消费方必须幂等**,因为 MQ 至少一次投递(At-Least-Once),同一条消息可能被消费多次,下游用 msg_id 做去重表是标准做法。

生产中这套机制通常封装在事务消息中间件里(RocketMQ 事务消息、Kafka 事务),原理一致,只是把"消息表 + 轮询"做进了 Broker 内部。

#### 2. Snowflake ID 生成器(Python)

Snowflake 是 Twitter 开源的 64 位分布式 ID 算法,结构为:`1 位符号位 + 41 位时间戳 + 10 位机器号 + 12 位序列号`。41 位时间戳可用约 69 年,10 位机器号支持 1024 个节点,12 位序列号单机每毫秒可生成 4096 个 ID。

```python
import threading
import time


class Snowflake:
    # 位段分配
    WORKER_ID_BITS = 5
    DATACENTER_ID_BITS = 5
    SEQUENCE_BITS = 12

    MAX_WORKER_ID = (1 << WORKER_ID_BITS) - 1          # 31
    MAX_DATACENTER_ID = (1 << DATACENTER_ID_BITS) - 1  # 31
    SEQUENCE_MASK = (1 << SEQUENCE_BITS) - 1           # 4095

    WORKER_ID_SHIFT = SEQUENCE_BITS                    # 12
    DATACENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS  # 17
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATACENTER_ID_BITS  # 22
    # 起始时间戳:2024-01-01 00:00:00 UTC(毫秒)
    EPOCH = 1704067200000

    def __init__(self, worker_id: int, datacenter_id: int):
        if not (0 <= worker_id <= self.MAX_WORKER_ID):
            raise ValueError(f"worker_id 越界,需 0-{self.MAX_WORKER_ID}")
        if not (0 <= datacenter_id <= self.MAX_DATACENTER_ID):
            raise ValueError(f"datacenter_id 越界,需 0-{self.MAX_DATACENTER_ID}")
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _current_ms(self):
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_ts):
        ts = self._current_ms()
        while ts <= last_ts:
            ts = self._current_ms()
        return ts

    def next_id(self) -> int:
        with self.lock:
            now = self._current_ms()
            if now < self.last_timestamp:
                # 时钟回拨:回拨幅度小于 5ms 时等待,否则直接抛错(生产中可切备用机器号)
                drift = self.last_timestamp - now
                if drift <= 5:
                    time.sleep(drift / 1000.0)
                    now = self._current_ms()
                else:
                    raise RuntimeError(
                        f"时钟回拨 {drift}ms,拒绝生成 ID 防止重复")
            if now == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
                if self.sequence == 0:
                    # 当前毫秒序列耗尽,等下一毫秒
                    now = self._wait_next_ms(self.last_timestamp)
            else:
                self.sequence = 0
            self.last_timestamp = now
            return (
                ((now - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.datacenter_id << self.DATACENTER_ID_SHIFT)
                | (self.worker_id << self.WORKER_ID_SHIFT)
                | self.sequence
            )


# 使用
gen = Snowflake(worker_id=1, datacenter_id=1)
for _ in range(5):
    print(gen.next_id())
```

这段代码的关键点有三个。第一,**位段移位拼接**是 Snowflake 的核心,时间戳在高位保证 ID 趋势递增(对 B+ 树索引友好,避免页分裂),机器号 + 序列号在低位保证同毫秒内不冲突。第二,**时钟回拨必须处理**,NTP 同步可能导致系统时钟往回跳,若不处理会生成与历史重复的 ID——这里用"小回拨等待、大回拨抛错"的策略,生产中还可切换到备用 worker_id 或借用上次时间戳。第三,**锁保护 last_timestamp 与 sequence 的原子性**,否则并发下两线程拿到相同 sequence 产生重复 ID。百度 UidGenerator、美团 Leaf、Vesta 都是 Snowflake 的工业级变种,核心都是这套位段设计。

#### 3. TCC 三接口伪代码

TCC 的关键不在三个接口本身,而在 Confirm/Cancel 的幂等与最终一致性保证。下面以"扣款 + 加积分"为例:

```python
class AccountService:
    """账户服务:实现 TCC 三接口"""

    def try_deduct(self, user_id: str, amount: int) -> bool:
        """Try:冻结金额,不真正扣减"""
        # 1. 幂等检查:try_id 是否已处理(防重复 Try)
        if self._is_try_done(user_id, amount):
            return True
        # 2. 检查余额是否够冻结
        balance = self._get_balance(user_id)
        frozen = self._get_frozen(user_id)
        if balance - frozen < amount:
            return False  # 资源不足,主事务将走 Cancel
        # 3. 冻结金额:balance 不变,frozen += amount
        self._add_frozen(user_id, amount)
        # 4. 记录 try 状态(防 Confirm/Cancel 找不到上下文)
        self._mark_try_done(user_id, amount)
        return True

    def confirm_deduct(self, user_id: str, amount: int) -> bool:
        """Confirm:真正扣减,消耗冻结额度"""
        # 幂等:重复 Confirm 不重复扣
        if self._is_confirmed(user_id, amount):
            return True
        # 空回滚保护:Try 未执行就收到 Cancel/Confirm,直接拒绝
        if not self._is_try_done(user_id, amount):
            return False
        # balance -= amount, frozen -= amount
        self._do_deduct(user_id, amount)
        self._mark_confirmed(user_id, amount)
        return True

    def cancel_deduct(self, user_id: str, amount: int) -> bool:
        """Cancel:解冻,归还金额"""
        # 幂等:重复 Cancel 不重复解冻
        if self._is_canceled(user_id, amount):
            return True
        # 空回滚保护
        if not self._is_try_done(user_id, amount):
            # Try 未执行,记录空回滚标记防止后续 Try 再生效
            self._mark_empty_cancel(user_id, amount)
            return True
        # frozen -= amount
        self._release_frozen(user_id, amount)
        self._mark_canceled(user_id, amount)
        return True

    # 下划线方法省略,实际为 SQL 操作与状态表读写


class TccCoordinator:
    """TCC 协调者:编排 Try-Confirm-Cancel"""

    def execute(self, user_id, amount):
        try_id = "TX-" + user_id + "-" + str(amount)
        # 阶段一:Try 所有分支
        ok_account = account.try_deduct(user_id, amount)
        ok_points = points.try_add(user_id, amount)
        # 阶段二:全部 Try 成功则 Confirm,任一失败则 Cancel 全部
        if ok_account and ok_points:
            account.confirm_deduct(user_id, amount)
            points.confirm_add(user_id, amount)
        else:
            # 注意:Cancel 也要对"Try 成功的分支"执行,Try 失败的分支走空回滚
            account.cancel_deduct(user_id, amount)
            points.cancel_add(user_id, amount)
```

TCC 落地有三个工程坑必须知道。第一,**Confirm/Cancel 必须幂等**,因为协调者重试时可能多次调用同一接口,用 try_id 做去重表是标准做法。第二,**空回滚保护**:网络超时导致 Try 没真正到达参与者,协调者却以为失败发起 Cancel,参与者收到 Cancel 时 Try 还没来,必须能识别"这是空 Cancel"并直接返回成功,否则后续迟到的 Try 会把资源永久冻结。第三,**悬挂保护**:Cancel 先于 Try 到达(网络乱序),若不拦截,Cancel 走空回滚后,Try 才到,会冻结资源却再无 Confirm 释放——悬挂的解法是 Cancel 时记录"已 Cancel"标记,Try 时先检查该标记。这三个坑是 TCC 工程实现的核心难点,Seata TCC 模式都把它们封装在框架里。

### 四、速查/自测

#### 分布式事务方案对照表

| 方案 | 一致性强度 | 性能 | 业务侵入 | 协调者 | 典型场景 |
|---|---|---|---|---|---|
| 2PC / XA | 强一致 | 低(同步阻塞) | 低(资源层) | 必需,单点风险 | 传统金融跨库转账 |
| 3PC | 强一致 | 更低(多一轮 RTT) | 低 | 必需 | 几乎无生产落地 |
| TCC | 强一致(最终) | 高(无锁) | 高(三接口) | 必需 | 电商扣库存、支付扣款 |
| 本地消息表 | 最终一致 | 高 | 中(写消息表) | 无,靠 MQ | 异步解耦:下单后加积分、发短信 |
| Saga | 最终一致 | 高(无锁) | 中(写补偿) | 必需 | 长流程:旅行预订、订单履约 |
| Seata AT | 最终一致 | 较高 | 低(自动反向 SQL) | 必需 | 中小业务快速接入分布式事务 |
| 事务消息(RocketMQ) | 最终一致 | 高 | 中 | Broker 内置 | 异步解耦,比本地消息表少一张表 |

#### 自测题

**问题一(原理层):** CAP 定理说"三选二",为什么实际工程中几乎看不到 CA 系统?CP 和 AP 分别用于什么场景?

参考答案:跨网部署必有 P,真正的 CA 只存在于单机数据库。CP 系统分区时拒绝写入保一致,适合元数据、配置、分布式锁(如 etcd、ZooKeeper);AP 系统分区时继续服务保可用,适合容忍短暂不一致的业务数据(如 Cassandra、Eureka)。多数互联网系统是 AP 为主、CP 为辅:业务数据走 AP,Leader 选举与配置走 CP。

**问题二(实践层):** Snowflake 发生 50ms 时钟回拨,直接生成 ID 会出现什么问题?如何处理?

参考答案:回拨后当前时间戳小于上次,直接生成会产生与历史重复的 ID(三段都可能重合)。处理三档:小回拨(<5ms)等待回拨时长再生成;中回拨(秒级)切备用 worker_id 或借用上次时间戳继续累加序列号;大回拨直接抛错告警人工介入,避免污染整段 ID 空间。UidGenerator 用时间戳借用,Leaf-Snowflake 用 ZooKeeper 持久化上次时间戳做回拨检测。

**问题三(思路层):** TCC 的 Cancel 接口为什么必须做空回滚保护?不做会出现什么故障?

参考答案:针对"Try 未到达但 Cancel 已到达"的乱序。若 Cancel 时无 Try 上下文直接报错,迟到的 Try 到达后会冻结资源,但协调者已走完 Cancel 不会再 Confirm,资源永久冻结,表现为用户余额被冻结却查不到订单。正确做法是 Cancel 时若无 Try 上下文,记录"已 Cancel"标记并返回成功,后续 Try 检查到该标记后拒绝执行,同时解决悬挂问题。

**问题四(实践层):** 本地消息表若改成"先写订单表、事务提交后再写消息表",会出现什么问题?

参考答案:出现"孤儿订单"——订单写成功后、写消息表前进程崩溃,订单已落库但消息永远没产生,下游积分服务收不到事件。本地消息表的核心价值是用本地事务把"业务写入"与"消息记录写入"绑成原子,改成两步就破坏了这个原子性。RocketMQ 事务消息本质也是把"消息准备"与"业务事务"绑定,任何两步写都无法保证一致性。

**问题五(思路层):** 同样是最终一致性,Saga 与本地消息表如何区分选型?

参考答案:三个判据。事务边界:Saga 适合"跨多服务的完整业务事务"(如旅行预订=订机票+订酒店+租车,任一步失败整体回滚),本地消息表适合"主事务 + 异步通知"(下单后异步加积分)。失败语义:Saga 补偿是反向操作(退订),语义复杂;本地消息表失败是重试(重投),语义简单。流程长度:Saga 适合 3-7 步中等流程,本地消息表适合"1 主 + N 异步"扇出。简言之,业务有"要么全成功要么全回滚"语义用 Saga,业务是"主流程 + 异步副作用"用本地消息表。

### 可交给 AI 的部分

这一章里,**Raft/Paxos 的完整算法编码、Snowflake 的位段计算与回拨处理代码、TCC 三接口的样板代码、Seata/DTM 的配置文件、本地消息表的后台轮询脚本**这几块可以放心交给 AI 生成。给定业务场景(如"支付扣款 TCC,要求幂等 + 空回滚保护"),AI 能给出可直接落地的 Python/Java 代码骨架,准确率较高。分布式 ID 的位段设计、对照表、架构拓扑图这类机械产出,AI 输出可用率也不错,适合直接放进设计文档。

但有几类内容**必须自己掌握、不能盲信 AI**,边界与风险如下。

第一类是 **CAP/BASE 的业务选型决策**。AI 能背"金融用 CP、互联网用 AP",但具体业务选 CP 还是 AP 涉及一致性要求、可用性承诺、成本预算的综合判断。把账户余额选成 AP 会让用户看到不一致余额,把商品评论选成 CP 会让大促时评论服务不可用——这类决策必须架构师基于业务语义拍板。

第二类是 **TCC 的工程坑处理**。AI 写的三接口骨架通常正确,但空回滚保护、悬挂保护、幂等去重这三个坑 AI 容易漏,除非 prompt 里明确要求。漏掉这些保护,TCC 上线后网络抖动时会出资金冻结、资源悬挂这类难复现故障。架构师必须能识别 AI 输出的 TCC 代码是否补齐了三层防御。

第三类是 **Saga 补偿事务的设计**。AI 能列步骤,但"每个 Ti 的补偿 Ci 如何设计才能业务可逆"是高度业务相关的推理。"已发货订单"的补偿是召回快递还是等用户退货后退款,AI 不知道你的业务流程,给的补偿往往不可执行。补偿设计必须由懂业务的人做,AI 最多帮补代码框架。

第四类是 **分布式事务故障的现场应急**。TCC 卡在 Confirm、Saga 补偿链断在中途、本地消息表积压百万条,这类故障必须几分钟内决策且不可回退。AI 在这种高压场景下来不及响应,也缺乏对全局数据状态的认知。Runbook 可以让 AI 提前起草,执行判断必须是人。

区分"能交"与"不能交"的本质是:**算法代码、配置文件、对照表是机械产出,AI 强;业务语义判断、工程防御补全、补偿逻辑设计、应急现场决策是经验推理,AI 弱**。把机械产出交给 AI 加速落地,把经验推理留给自己练成现场判断力,这是 AI 时代分布式系统工程师的知识边界。

## 参考来源

- [1] Eric Brewer:CAP Twelve Years Later(2012 年对原 CAP 猜想的澄清) https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/
- [2] Seth Gilbert, Nancy Lynch:Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services(CAP 定理形式化证明,ACM SIGACT News 2002)
- [3] Martin Kleppmann:《数据密集型应用系统设计》第 5 章"复制"、第 7 章"事务"、第 9 章"一致性与共识",中国电力出版社,2018(线性一致性、因果一致性、2PC、Raft 的工程化论述)
- [4] Diego Ongaro, John Ousterhout:In Search of an Understandable Consensus Algorithm(Raft 论文,USENIX ATC 2014) https://raft.github.io/raft.pdf
- [5] Leslie Lamport:The Part-Time Parliament(Paxos 原始论文,ACM TOCS 1998) https://lamport.azurewebsites.net/pubs/lamport-paxos.pdf
- [6] Pat Helland:Life beyond Distributed Transactions(本地消息表与 Saga 的思想源头,CIDR 2007)
- [7] Apache Seata 官方文档:AT / TCC / Saga / XA 四种模式 https://seata.apache.org/docs/overview/what-is-seata
- [8] DTM 官方文档:Saga、TCC、二阶段消息 https://en.dtm.pub/
- [9] Twitter Engineering:Announcing Snowflake(Snowflake ID 算法起源) https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake
- [10] Neil Conway 等:Consistency and Availability in Distributed Systems(CAP 工程权衡综述) https://www.cs.berkeley.edu/~brewer/cs262b/
- 本专栏第 14 章「事务锁与隔离级别」(本章分布式事务的一致性强度选择依赖单机 ACID 与隔离级别理解,TCC 的资源冻结本质是单机事务的应用)
