---
title: AI时代全栈知识边界·15|Redis与缓存策略
book: AI时代全栈知识边界
chapter: 数据库
event: Redis与缓存策略
sort: 3
chapter_sort: 6
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·15|Redis与缓存策略

> 前置知识:会用一种后端语言写 CRUD、理解关系库索引与事务的基本概念、知道进程内存与磁盘 IO 的延迟数量级差异
> 学完你能:① 说出 Redis 五种基础数据结构各自适合的场景与典型命令 ② 对比 RDB 与 AOF 的性能、安全权衡,说明 Redis 4.0 混合持久化的取舍 ③ 区分 LRU 与 LFU 淘汰依据,在八种淘汰策略里选出适合业务的那个 ④ 解释缓存雪崩、穿透、击穿三种问题的成因与解法 ⑤ 用 Python redis-py 演示 Cache Aside 模式与布隆过滤器 ⑥ 判断 Redis 集群配置、备份脚本哪些能交给 AI,哪些必须自己握住

### 一、概念

Redis(Remote Dictionary Server,远程字典服务)是基于内存的键值对存储系统,常用作缓存、消息队列与分布式协调中间件。缓存策略(Cache Strategy)是数据库与上层应用之间的一道速度适配层——把磁盘上的慢数据以更快的介质按特定规则复制一份,让读请求尽量不打到数据库。

这两个概念要放到「读写不对称」的语境下理解。绝大多数业务读写比是 10:1 甚至更高,热点数据高度集中。如果每次读都打到关系库,磁盘 IO 与锁竞争会迅速成为瓶颈;引入缓存后,读路径多走一跳内存,数据库压力可降一到两个数量级。代价是数据多了一份,引入一致性、淘汰、雪崩等新问题。

需要先对齐几组术语。Redis 单线程指命令处理串行化,Redis 6.0 引入的多线程仅用于网络 IO 读写,命令执行仍单线程。RDB(Redis DataBase,数据库快照)与 AOF(Append-Only File,追加日志文件)是两种持久化方式。LRU(Least Recently Used,最近最少使用)、LFU(Least Frequently Used,最不经常使用)是两种主流淘汰算法。Cache Aside(旁路缓存)是最常见的缓存读写模式,与 Write Through(直写)、Write Behind(异步写缓存)对应,后文逐一展开。

### 二、原理

#### 1. 五种基础数据结构:不只是「键值」

Redis 的高性能不只是「全内存」一项,更关键是它把不同访问模式封装成五种数据结构,各自配原子命令,免去应用层加锁的复杂度。

- String(字符串):最通用,可存数字、JSON、序列化对象,支持 `INCR`/`DECR` 原子计数。场景:计数器、缓存对象、分布式锁(`SET key value NX PX`)。
- List(列表):双向链表(短列表用 ziplist 压缩,长列表用 quicklist)。两端 `LPUSH`/`RPOP` 是 O(1),适合消息队列、最新 N 条 feed。
- Hash(哈希):字段-值映射,适合存对象。`HSET user:1 name alice age 30` 比把整个对象序列化成 String 省内存,改单字段不必整对象反序列化。
- Set(集合):无序去重,支持交并差运算。场景:标签、共同好友、去重计数。
- ZSet(Sorted Set,有序集合):每个元素带 score,按 score 排序,支持范围查询。是 Redis 独有的强项,排行榜、延迟队列、带权重的去重集合都靠它。

选错数据结构代价显著。对象存成 String 再 `GET` 整体反序列化,改一字段要重写整条记录;换成 Hash,改单字段只需 `HSET` 一次。排行榜用 List 实现插入新分数要全表重排;换成 ZSet,`ZADD` 自动维护顺序,`ZRANGE` 取 Top N 是 O(log N)。

#### 2. RDB vs AOF:性能与安全的权衡

RDB 是某一时刻的全量内存快照,二进制紧凑、恢复快、体积小;AOF 是把每条写命令追加到日志,可读、丢失窗口小、恢复慢。权衡核心是故障恢复时丢多少数据能接受。

RDB 用 `BGSAVE` 通过 fork 子进程做快照,主线程只在 fork 那一瞬间短暂阻塞,子进程借助 COW(Copy-On-Write,写时复制)拿到内存快照。优势是恢复快、文件小;代价是两次 `BGSAVE` 之间写命令可能丢失。Redis 默认 `save 900 1`(900 秒内有 1 次写触发),最坏丢 15 分钟,生产基本不可接受。`SAVE` 阻塞主线程,生产不用。

AOF 把每条写命令以协议格式追加到文件,恢复时回放整个日志。`appendfsync` 决定刷盘策略:`always`(每条刷盘,最安全最慢)、`everysec`(每秒刷盘,折中,最多丢 1 秒,生产默认)、`no`(由 OS 决定)。AOF 文件会持续膨胀,Redis 通过 `BGREWRITEAOF` 重写,同样借助 fork 子进程重新生成最小命令集。

Redis 4.0 引入混合持久化(`aof-use-rdb-preamble yes`):AOF 重写时前半段用 RDB 快照,后半段追加增量 AOF 命令。恢复时先加载 RDB 段(快),再回放 AOF 增量(只重放最后一小段),兼顾恢复速度与数据完整性。Redis 5.0 起默认。

#### 3. LRU vs LFU:时间局部性 vs 频率局部性

淘汰策略本质是「内存满了丢谁」。Redis 默认 `maxmemory` 不设上限,生产必须显式配置,否则 OOM 会让 Redis 被操作系统杀掉。`maxmemory-policy` 有八种取值,分四类:

- `noeviction`:不淘汰,写满直接报错。适合做绝对不能丢数据的场景,如分布式锁。
- `allkeys-lru` / `volatile-lru`:LRU 淘汰。前者在所有 key 里淘汰,后者只在设了过期时间的 key 里淘汰。
- `allkeys-lfu` / `volatile-lfu`:LFU 淘汰(Redis 4.0+ 引入)。
- `allkeys-random` / `volatile-random`:随机淘汰。
- `volatile-ttl`:优先淘汰离过期时间最近的 key。

LRU 淘汰「最近最少访问」的 key,假设「最近访问过的将来还会访问」(时间局部性)。Redis 的 LRU 不是严格 LRU——精确实现要维护双向链表,每次访问移动节点,内存开销大;Redis 用近似 LRU,随机采样 N 个(`maxmemory-samples`,默认 5),从这 N 个里淘汰最久未访问的。

LFU 淘汰「访问频率最低」的 key,假设「过去访问频繁的将来也频繁」(频率局部性)。LFU 解决了 LRU 的典型问题:偶尔被访问的冷 key 在某次扫描中突然被访问一次,LRU 会把它当热数据保留很久;LFU 看历史频率,单次访问不会让它翻身。

实际选型经验:缓存场景用 `allkeys-lru`,默认且广泛验证;热点集中且有偶发扫描访问,改 `allkeys-lfu`;只在带过期 key 里淘汰用 `volatile-*` 变体(配合把持久数据不设 TTL,确保不被淘汰)。

#### 4. 过期策略:定期删除 + 惰性删除

给 key 设 `EXPIRE` 只是把 key 标记为「到期应删」,Redis 不会主动盯着每个 key 到点删除——那样开销巨大。真正的删除走两条策略并行:

- 惰性删除(Lazy Expiration):每次 `GET` 等访问时检查 key 是否过期,过期则删并返回 nil。CPU 友好,但冷数据不被访问就一直占内存。
- 定期删除(Active Expiration):Redis 每秒执行 10 次(`hz` 配置),每次随机抽 20 个设了过期的 key 检查,删掉过期的;过期比例超过 25% 则继续抽,直到低于 25% 或时间用完。

两条策略结合,既保证热 key 到期立即可见,又防止冷 key 堆积。极端情况仍可能漏——一批设了相同 TTL 的 key 同时到期但都没被访问,会积压到定期删除慢慢清,这是缓存雪崩成因之一。

#### 5. 缓存雪崩、穿透、击穿的根本成因

三个问题名字相似,根因完全不同,对应解法也不同。

缓存雪崩(Cache Avalanche)指大量 key 同一时刻集体失效,或 Redis 整体宕机,大量请求瞬间打到数据库。根因是「失效时间集中」或「缓存层整体不可用」。解法:给 TTL 加随机偏移(`expire = base + random(0, 300)`)避免同时到期;Redis 高可用(主从 + 哨兵 + Cluster);数据库层熔断限流。

缓存穿透(Cache Penetration)指查询一个数据库里也不存在的 key,缓存永远查不到、永远回源数据库。根因是「缓存只缓存存在的数据,不存在的不缓存」。常见诱因是恶意攻击(用大量不存在的 ID 探测接口)。解法:查询为空的结果也缓存(nil 缓存,设短 TTL 如 60 秒);上布隆过滤器(Bloom Filter)前置挡一道,query 时先过布隆判断 key 是否可能存在,不可能存在直接返回,不打缓存也不打数据库。

缓存击穿(Cache Breakdown)指某个热点 key 突然失效,瞬间大量请求同时打到数据库重新加载。与雪崩区别:雪崩是「大量 key 同时失效」,击穿是「单个热点 key 失效」。根因是「热点 key 失效瞬间没有互斥,所有请求都回源」。解法:热点 key 永不过期(物理不过期,业务层异步刷新);或加互斥锁(`SET lock NX PX 1000`)只让一个请求回源,其他请求等待或返回旧值。

#### 6. 缓存与数据库一致性:Cache Aside 为主流

缓存与数据库双写一致性三种主流模式:

- Cache Aside(旁路缓存):读先查缓存,未命中查数据库再回填缓存;写先更新数据库再删除缓存。删除而非更新,避免并发下「A 先更新库、B 后更新库、B 更新缓存、A 更新缓存」导致缓存与库不一致。是绝大多数互联网业务的事实标准。
- Write Through(直写):写请求同时更新缓存与数据库,缓存层作数据库代理。一致性最强,但写性能差,依赖缓存中间件支持。
- Write Behind(异步写缓存):写只更新缓存,异步刷回数据库。写性能极高,但缓存宕机数据可能丢,适合容忍数据丢失的高写场景(如日志、计数)。

Cache Aside 在极端并发下仍可能出现短暂不一致:缓存恰好失效的瞬间,线程 A 查库读到旧值,线程 B 更新库并删缓存,线程 A 把旧值回填缓存。概率极低(需读库与写库的时间窗口交叉),工程上通过延迟双删(写后睡 500ms 再删一次缓存)兜底。要求强一致的场景应避免引入缓存。

#### 7. 数据库连接池:复用连接降低开销

连接池(Connection Pool)预先建立一批 TCP 连接复用,避免每次请求都走 TCP 三次握手 + 鉴权的开销。一次 MySQL 连接建立可能耗 10-50ms,连接池把这部分摊到首次启动。核心参数是最大连接数(`maxsize`):设小了请求排队,设大了数据库 `max_connections` 被打满。生产经验是 `maxsize = (数据库 max_connections / 应用实例数) - 安全余量`,留出 DBA 维护连接。Redis 也有连接池,redis-py 默认 `ConnectionPool(max_connections=50)`。

### 三、实践

#### 1. Redis 五种数据结构基础命令

```bash
# String:计数器与对象缓存
SET user:1:name "alice" EX 3600    # 带 60 分钟过期
GET user:1:name
INCR counter:page_view             # 原子自增
INCRBY counter:stock 100           # 一次加 100

# List:消息队列
LPUSH queue:task "task-1" "task-2"
RPOP queue:task                    # 取队尾
LRANGE queue:task 0 -1             # 查看全部

# Hash:对象存储
HSET user:1 name "alice" age 30 city "beijing"
HGET user:1 name
HINCRBY user:1 age 1               # 字段级原子自增
HGETALL user:1

# Set:标签与去重
SADD tag:python user:1 user:2 user:3
SADD tag:redis user:2 user:3 user:4
SINTER tag:python tag:redis        # 交集:同时打了两个标签
SCARD tag:python                   # 集合大小

# ZSet:排行榜
ZADD rank:score 100 "alice" 200 "bob" 150 "carol"
ZREVRANGE rank:score 0 9 WITHSCORES    # Top 10(降序)
ZINCRBY rank:score 50 "alice"          # 给 alice 加 50 分
ZRANGEBYSCORE rank:score 100 200       # 分数在 [100,200] 的成员
```

注意版本差异:Redis 7 的 AOF 文件格式与 RDB 版本号变了,不能直接用 7 的 RDB 启动 6 的实例,跨版本升级要走「6 主从挂 7 从库,等同步完成切主」流程。Redis 6 引入 ACL,生产应给应用账号限定可执行命令前缀,禁用 `FLUSHALL`/`CONFIG` 高危命令。

#### 2. Python redis-py 演示 Cache Aside 模式

下面这段代码演示「读穿缓存、写删缓存」的标准 Cache Aside 实现,含缓存击穿的互斥锁兜底。

```python
import json
import time
import redis

# 连接池:复用 TCP 连接,生产建议 max_connections 按应用并发设
pool = redis.ConnectionPool(host="127.0.0.1", port=6379, db=0, max_connections=20)
r = redis.Redis(connection_pool=pool, decode_responses=True)

CACHE_TTL = 3600          # 缓存默认 1 小时
LOCK_TTL = 5              # 击穿互斥锁 5 秒,防止回源雪崩
NIL_CACHE_TTL = 60        # 空值缓存 60 秒,防穿透


def get_user(user_id: int) -> dict | None:
    """Cache Aside 读:缓存 -> 互斥回源 -> 库"""
    key = f"user:{user_id}"
    cached = r.get(key)
    if cached is not None:
        if cached == "__nil__":
            return None             # 空值缓存命中,直接返回,不打库
        return json.loads(cached)

    # 缓存未命中,加互斥锁防止击穿:只让一个请求回源
    lock_key = f"lock:{key}"
    acquired = r.set(lock_key, "1", nx=True, px=LOCK_TTL * 1000)
    if not acquired:
        # 没抢到锁,短退避后重读缓存(等抢到锁的请求回填)
        time.sleep(0.05)
        return get_user(user_id)

    try:
        user = db_query_user(user_id)       # 真正查数据库
        if user is None:
            r.set(key, "__nil__", ex=NIL_CACHE_TTL)   # 防穿透:空值也缓存
            return None
        r.set(key, json.dumps(user), ex=CACHE_TTL)
        return user
    finally:
        r.delete(lock_key)                  # 释放锁,finally 保证异常也释放


def update_user(user_id: int, payload: dict) -> None:
    """Cache Aside 写:先更库,再删缓存(延迟双删兜底)"""
    db_update_user(user_id, payload)
    r.delete(f"user:{user_id}")             # 删除而非更新
    # 延迟双删:再起一个异步任务,500ms 后再删一次
    # 防止「A 读旧值 -> B 更新库删缓存 -> A 回填旧值」的并发不一致
    time.sleep(0.5)
    r.delete(f"user:{user_id}")


# 占位:真实业务里替换为 ORM 调用
def db_query_user(user_id: int) -> dict | None: ...
def db_update_user(user_id: int, payload: dict) -> None: ...
```

几个要点:删除而非更新,避免并发下后写覆盖先写;空值缓存要给短 TTL(60 秒),否则恶意攻击撑爆缓存;延迟双删要异步执行,示例用 `sleep` 仅讲清逻辑,生产应丢消息队列;互斥锁用 `SET NX PX`,既原子加锁又超时释放,避免锁泄露。

#### 3. 用布隆过滤器解决缓存穿透

布隆过滤器(Bloom Filter)是概率型数据结构,能判断「某元素一定不在集合中」或「可能在集合中」。底层是位数组 + 多个哈希函数:插入时把元素经 k 个哈希函数映射到 k 个位置置 1;查询时检查这 k 个位置,全为 1 才「可能存在」,有 0 则「一定不存在」。优点是省内存(1 亿 ID 约 100MB)、查询 O(k);缺点是有误判率(假阳性,可调),标准实现不能删。

下面用 redis-py + redisbloom 演示的伪代码:

```python
from redisbloom.client import Client as BloomClient

b = BloomClient(host="127.0.0.1", port=6379, db=0, decode_responses=True)
BF_KEY = "bf:user_ids"
# 初始化:容量 1 亿,误判率 0.1%,约 143MB 内存


def init_bloom():
    """启动时把数据库所有用户 ID 灌入布隆过滤器"""
    for user_id in db_iter_all_user_ids():
        b.bfAdd(BF_KEY, str(user_id))


def get_user_with_bf(user_id: int) -> dict | None:
    """先过布隆过滤器,不存在直接返回,防穿透"""
    if not b.bfExists(BF_KEY, str(user_id)):
        # 布隆说不存在,百分百不存在,直接返回
        return None
    # 布隆说可能存在,走正常 Cache Aside 流程
    return get_user(user_id)


def add_user_to_bf(user_id: int):
    """新增用户时同步写入布隆过滤器"""
    b.bfAdd(BF_KEY, str(user_id))


# 占位
def db_iter_all_user_ids(): ...
```

布隆过滤器要解决两个工程问题。初始数据加载:启动时把数据库全量 ID 灌入,1 亿数据约耗 1-2 分钟,要异步预热不能阻塞启动。增量同步:新增用户时要同时调 `add_user_to_bf`,否则新用户第一次查会被布隆拦掉。删除用户不能从布隆删(标准实现不支持),「用户注销」要么接受「布隆仍说可能存在」(查询回源返回 nil),要么改用 Counting Bloom Filter。

### 四、速查/自测

#### 缓存问题 vs 解决方案对照表

| 问题 | 根因 | 典型现象 | 解决方案 | 兜底措施 |
|---|---|---|---|---|
| 缓存雪崩 | 大量 key 同时失效 / Redis 宕机 | 数据库瞬时压力暴涨,响应变慢 | TTL 加随机偏移;Redis 高可用 | 数据库熔断限流;服务降级 |
| 缓存穿透 | 查询不存在的 key,缓存永不命中 | 数据库持续被无效 ID 探测 | 空值缓存(短 TTL);布隆过滤器前置 | 接口限流;异常 ID 黑名单 |
| 缓存击穿 | 单个热点 key 失效瞬间大量回源 | 某一接口 QPS 突增,数据库 CPU 飙升 | 互斥锁回源;热点 key 永不过期 | 旧值兜底返回 |
| 缓存与库不一致 | Cache Aside 并发窗口 | 偶发读到旧值,数秒后自愈 | 写后删缓存;延迟双删 | 强一致场景不引入缓存 |
| 缓存大 Value | 单 key 存大对象(>10KB) | 单条命令阻塞主线程,集群倾斜 | 拆分;压缩;改用 Hash 分字段 | 监控 bigkey,定期治理 |

#### 自测题

**问题一(原理层):** Redis 6.0 引入多线程后,还是单线程吗?为什么多线程只做网络 IO 不做命令执行?

参考答案:Redis 6.0 多线程仅用于网络 IO 读写,命令执行仍单线程。根本原因:Redis 全内存操作极快,瓶颈在网络 IO 而非 CPU,多线程处理 IO 能显著提升吞吐;命令执行单线程化,所有命令天然串行,无需加锁,数据结构操作保持原子性。若命令执行也多线程化,要为每个数据结构加锁,锁竞争开销往往大于串行。这是 Redis 的核心权衡。

**问题二(思路层):** 业务要做排行榜,选 List 还是 ZSet?为什么?

参考答案:必须用 ZSet。List 是双向链表,插入新分数要找插入位置(O(N)),无法按 score 范围查询。ZSet 自带 score 排序,`ZADD` 是 O(log N),`ZRANGEBYSCORE` 也是 O(log N + M)。1000 万用户排行榜,ZSet 一次 Top 10 查询是毫秒级,List 实现卡到秒级。代价是 ZSet 内存比 List 大(每元素多 8 字节 score),但查询性能收益值得。

**问题三(实践层):** 用 redis-py 实现「热点 key 永不过期 + 异步刷新」的核心逻辑。

参考答案:核心是不设 TTL,改由业务判断逻辑过期。每个 value 存 `{data, expire_at}`,读取时检查 `expire_at`,过期不直接删,异步触发刷新、本次返回旧值:

```python
import json, time, threading

def get_hot(key, loader, ttl=3600):
    raw = r.get(key)
    if raw is None:
        return loader_and_set(key, loader, ttl)
    val = json.loads(raw)
    if val["expire_at"] < time.time():
        # 逻辑过期:异步刷新,本次返回旧值
        threading.Thread(target=loader_and_set, args=(key, loader, ttl), daemon=True).start()
    return val["data"]

def loader_and_set(key, loader, ttl):
    data = loader()
    r.set(key, json.dumps({"data": data, "expire_at": time.time() + ttl}))
    return data
```

这种模式牺牲一致性换可用性,适合排行榜、热门商品等容忍分钟级延迟场景。

**问题四(原理层):** RDB 与 AOF 各自最坏丢多少数据?混合持久化为什么能兼顾?

参考答案:RDB 默认 `save 900 1`,最坏丢 15 分钟(两次 BGSAVE 之间写命令)。AOF `appendfsync everysec`,最坏丢 1 秒(`fsync` 之间写命令)。混合持久化在 AOF 重写时前半段写 RDB 快照、后半段追加 AOF 增量,恢复时先加载 RDB,再回放 AOF 增量(只重放最后一小段,丢失窗口等于 AOF 的 1 秒),兼顾恢复速度与完整性。

**问题五(思路层):** 公司要把单 Redis 升级到 Redis Cluster,业务代码要不要改?有哪些坑?

参考答案:要改。Cluster 用 16384 个槽位分片,每个 key 经 CRC16 取模定位到槽,客户端必须用支持 Cluster 协议的客户端。四个坑:多 key 操作受限(`MGET k1 k2 k3` 不在同槽报错,要用 hash tag `{user}:1` 强制同槽或拆多次);事务与 Lua 脚本只能操作同槽 key;扩缩容迁移 key 时出现 `MOVED` 重定向;Cluster 只支持 db 0,原按 db 隔离业务要改前缀。建议先在从库验证客户端兼容性,再灰度切流。

### 可交给 AI 的部分

能放心交给 AI 的是「配置脚本、备份脚本、监控告警模板」这类结构确定、可执行验证的活儿。给定业务规模和峰值 QPS,AI 能产出 Redis 主从配置、哨兵配置、Cluster 节点拓扑、`redis.conf` 参数、RDB/AOF 备份脚本、Prometheus + redis_exporter 监控面板。`redis-cli --bigkeys`、`MEMORY USAGE` 这类排查命令模板,AI 给的也是标准答案。

但有几类内容必须自己握住,边界与风险如下。

第一类是淘汰策略与 `maxmemory` 的选型决策。AI 会列八种策略区别,但「该用 `allkeys-lru` 还是 `volatile-lfu`」涉及业务访问模式、内存预算、可接受的命中率波动,AI 无从知晓。设错了会导致命中率骤降或正常 key 被误淘汰,生产事故往往是「AI 配置看着没问题,实际跑挂了」的类型。

第二类是缓存与数据库一致性的边界判断。AI 能讲清 Cache Aside 的标准实现,但「业务能不能接受偶发不一致」「是否需要延迟双删、延迟多久」要结合业务对一致性的容忍度判断。金融、库存这类强一致场景盲目引入缓存,AI 给的标准 Cache Aside 仍可能造成资损,架构决策必须人来定。

第三类是缓存击穿/雪崩的现场处置。线上告警「数据库 CPU 100%、缓存命中率从 95% 跌到 30%」,根因可能是热点 key 失效、大量 key 同时到期、或 Redis 主库宕机从库未切。AI 来不及响应,值班 DBA 要第一时间 `redis-cli INFO`、`SLOWLOG GET` 看现场,判断熔断还是降级。AI 可提前把排查脚本写进 runbook,判断必须人来做。

第四类是布隆过滤器的容量与误判率规划。AI 能给标准 API,但「1 亿 ID 选 0.1% 还是 0.01% 误判率」涉及内存预算(0.1% 约 143MB、0.01% 约 228MB)与误判代价。这个权衡 AI 给不了答案,业务方拍板。

第五类是 Redis Cluster 迁移方案。AI 给的是标准流程,但「现网几百实例、跨槽多 key 操作有多少、Lua 脚本用了多少」这些上下文 AI 看不到,迁移方案要 DBA 自己审计代码、定灰度策略。盲信 AI 迁移脚本,跨槽 `MGET` 一报错业务就崩。

区分「能交」与「不能交」的本质:配置和备份脚本是机械劳动,AI 强;选型决策、一致性边界、现场处置、容量规划是业务上下文 + 工程判断,AI 弱。机械劳动交 AI 写进 runbook,架构决策和现场判断留给自己。

## 参考来源

- [1] 黄健宏:《Redis设计与实现》机械工业出版社 2014(RDB/AOF 持久化、五种数据结构内部实现、过期与淘汰策略)
- [2] Martin Kleppmann:《数据密集型应用系统设计》第 1 章「可靠性、可扩展性、可维护性」、第 9 章「一致性与共识」中国电力出版社 2018(缓存一致性与权衡的理论框架)
- [3] Redis 官方文档:Persistence(RDB 与 AOF 持久化机制) https://redis.io/docs/management/persistence/
- [4] Redis 官方文档:Key eviction(八种淘汰策略与 LRU/LFU 实现) https://redis.io/docs/reference/eviction/
- [5] Redis 官方文档:Replication(主从复制与哨兵) https://redis.io/docs/management/replication/
- [6] Josiah L. Carlson:《Redis in Action》Manning Publications 2013(Cache Aside 模式、布隆过滤器防穿透、排行榜实现)
- [7] redis-py 官方文档:Connection Pool 与客户端用法 https://redis-py.readthedocs.io/en/stable/
- [8] RedisBloom 官方文档:Bloom Filter 命令与容量规划 https://redis.io/docs/stack/bloom/
- [9] 本专栏第 13 章「关系库与索引原理」(本章缓存层与关系库索引配合,决定读路径性能上限)
- [10] 本专栏第 14 章「事务锁与隔离级别」(本章双写一致性的边界依赖关系库事务隔离级别)
