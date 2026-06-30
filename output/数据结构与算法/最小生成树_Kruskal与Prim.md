---
title: 算法课·29｜最小生成树：Kruskal 与 Prim 的两种切入
book: 数据结构与算法
chapter: 最小生成树
event: Kruskal与Prim
sort: 1
chapter_sort: 19
created_at: 2026-06-29
source_agents:
- algorithm-expert
---
# 算法课·29｜最小生成树：Kruskal 与 Prim 的两种切入

> 前置知识：学完第 17 章（图的遍历）和第 18 章（并查集），尤其要懂并查集的"按秩合并 + 路径压缩"
> 学完你能：①给纯小白讲清 MST 为什么是 n-1 条边 ②默写 Kruskal 和 Prim 并讲透每一行 ③手撕两种算法应对面试 ④理解两种贪心的正确性证明（割性质）⑤用对数器在随机图上验证两种算法结果一致

## 一、问题与思路：MST 为什么需要两个算法

### 1. 一个生活场景：用最少成本把村庄连通

假设你是乡长，管辖 6 个村庄，村与村之间可修路的候选方案有 10 条，每条路造价不同（有的村庄之间山高路远，造价高）。你的目标是用最少的钱让所有村庄都能互相到达——不要求每两村之间都有直达路，只要"绕路能到"就行。

反直觉的地方来了：最优解里**不会有环**。如果 6 个村的最优方案里有 7 条路，那一定存在一个环，删掉环上最贵的一条路，村庄依然互通，但总造价更低——矛盾。所以 6 个村的最优方案**恰好 5 条路**。推广到 n 个顶点的连通图，最小生成树（Minimum Spanning Tree, MST）恰好 n-1 条边。这是 MST 的第一个反直觉点：边数是被锁死的。

### 2. MST 的精确定义

给定一个**连通无向图** $G=(V,E)$，每条边 $e \in E$ 有权值 $w(e)$。MST 是一棵生成树 $T$，使得所有生成树中 $\sum_{e \in T} w(e)$ 最小。三个要点：

- **连通**：图必须连通，否则只能求"最小生成森林"（每个连通分量一棵 MST）。
- **无向**：MST 定义在无向图上；有向图对应的是"最小树形图"（朱-刘算法），是另一类问题。
- **n-1 条边**：n 个顶点的生成树恰好 n-1 条边，这是树的定义决定的（连通且无环）。

**MST 不一定唯一**。当图里有多条权值相同的边时，可能存在多棵权值和相同的 MST。但所有 MST 的权值和相同——这是 MST 的"权值唯一性"。

### 3. 反直觉问题：为什么有两个主流算法

排序有一个主流框架（比较排序），最短路有一个主流框架（Dijkstra/Bellman-Ford 系列），唯独 MST 有两个并驾齐驱的主流算法：Kruskal（1956）和 Prim（1957），相差仅一年发表。**为什么 MST 需要两个？**

因为它们是同一个问题的**两种贪心切入**：

- **Kruskal 按边**：把所有边按权值排序，从小到大挑边，挑进去不构成环就要，构成环就跳过。视角是"全局看边"。
- **Prim 按点**：从一个点出发，每次把"和当前树相邻的最短边"加进来，扩展一个新点。视角是"局部看点"。

两种贪心都是对的（后面会证），但工程性能不同：Kruskal 的瓶颈是排序边（$O(E \log E)$），适合**边少**的稀疏图；Prim 的瓶颈是每次找最短邻边（用优先队列 $O(E \log V)$），适合**边多**的稠密图。同一个问题，两种切入，对应两种图密度下的最优解——这就是 MST 需要两个算法的根因。

### 4. 历史地位：1956 与 1957 的双峰

Kruskal 在 1956 年的论文 *"On the shortest spanning subtree of a graph and the traveling salesman problem"* 中提出按边排序的算法。Prim 在 1957 年的论文 *"Shortest connection networks and some generalizations"* 中提出按点扩展的算法（实际上 Jarník 1930 年更早提出，所以 Prim 也叫 Jarník 算法）。

这两个算法奠定了 MST 的贪心范式。后续的 Borůvka（1926，更早但当时未流行）、Sollin、Yao 等改进都建立在"按边或按点贪心"的框架上。CLRS 第 23 章把 Kruskal 和 Prim 并列讲解，正是这种"双切入"地位的体现。

## 二、原理与实现：两种贪心的代码与正确性

### 1. Kruskal：按边排序 + 并查集判环

先看 Kruskal 的代码，理解机制：

```python
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        # 路径压缩
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        # 按秩合并
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False            # 已同属一个集合，合并失败（会成环）
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        return True

def kruskal(n, edges):
    """
    edges: [(w, u, v), ...]，n 个顶点编号 0..n-1
    返回 MST 的边列表和总权值
    """
    edges.sort(key=lambda e: e[0])   # 按权值排序
    uf = UnionFind(n)
    mst, total = [], 0
    for w, u, v in edges:
        if uf.union(u, v):           # u 和 v 不在同一集合，加入这条边
            mst.append((u, v, w))
            total += w
            if len(mst) == n - 1:    # 已选够 n-1 条边，提前结束
                break
    return mst, total
```

**逐行讲透**：

- **`edges.sort(key=lambda e: e[0])`**：按权值从小到大排序。这是 Kruskal 的贪心依据——优先选便宜的边。排序复杂度 $O(E \log E)$，是 Kruskal 的主要开销。
- **`uf = UnionFind(n)`**：初始化并查集，每个顶点自成一个集合。并查集用来快速判断"两个点是否已连通"。
- **`for w, u, v in edges`**：按权值从小到大遍历每条边。
- **`if uf.union(u, v)`**：尝试合并 u 和 v 所在集合。返回 `True` 表示原本不连通、合并成功；返回 `False` 表示已连通——再加这条边会成环，跳过。这是 Kruskal 判环的精妙之处：用并查集的 `union` 把"判环 + 连通"两件事合一。
- **`if len(mst) == n - 1: break`**：选够 n-1 条边就停。这是 MST 边数的硬约束，提前退出能省时间。

**用一个例子走一遍**。图：4 个顶点，边 `(1,0,1), (2,1,2), (3,2,3), (4,0,3), (5,1,3)`（格式 `(w,u,v)`）：

```
排序后：[(1,0,1), (2,1,2), (3,2,3), (4,0,3), (5,1,3)]

边 (1,0,1): 0 和 1 不连通，加入。mst=[(0,1,1)], 集合{0,1},{2},{3}
边 (2,1,2): 1 和 2 不连通，加入。mst=[(0,1,1),(1,2,2)], 集合{0,1,2},{3}
边 (3,2,3): 2 和 3 不连通，加入。mst=[...,(2,3,3)], 集合{0,1,2,3}
len(mst)==3==n-1, 停。总权值 1+2+3=6
```

边的后两条 (4,0,3) 和 (5,1,3) 都没看——因为已经选够。这就是 Kruskal 的效率来源：排序后线性扫描，并查集近乎 $O(1)$ 判环。

### 2. Prim：按点扩展 + 优先队列

再看 Prim 的代码：

```python
import heapq

def prim(n, graph):
    """
    graph: 邻接表 graph[u] = [(v, w), ...]，n 个顶点
    返回 MST 的总权值
    """
    visited = [False] * n
    mst_weight = 0
    # 堆元素：(权值, 起点, 终点)，起点仅用于记录边
    heap = [(0, 0, 0)]              # 从顶点 0 开始，自环权值 0
    edges_used = 0

    while heap and edges_used < n:
        w, u, v = heapq.heappop(heap)
        if visited[v]:
            continue                 # 终点已进入树，跳过（避免环）
        visited[v] = True
        mst_weight += w
        edges_used += 1
        for nb, w2 in graph[v]:      # 把 v 的所有邻边入堆
            if not visited[nb]:
                heapq.heappush(heap, (w2, v, nb))
    return mst_weight
```

**逐行讲透**：

- **`heap = [(0, 0, 0)]`**：堆里放 `(权值, 起点, 终点)`。初始把顶点 0 放进去，自环权值 0。这一步是"种树"——选一个起点。
- **`while heap and edges_used < n`**：堆不空且还没选够 n 个点（n-1 条边 + 起点那次"假加入"）。注意 `edges_used` 计的是"加入树的顶点数"，到 n 就停。
- **`if visited[v]: continue`**：终点已进树，这条边会成环，跳过。这是 Prim 判环的方式——和 Kruskal 用并查集不同，Prim 用 `visited` 数组。
- **`visited[v] = True; mst_weight += w`**：把 v 加入树，累加权值。第一次循环 v=0、w=0，相当于"种树"，不影响总权值。
- **`for nb, w2 in graph[v]: heapq.heappush(...)`**：把 v 的所有未访问邻居对应的边入堆。堆始终维护"当前树到外部所有顶点的最短候选边"。

**用同一个例子走一遍**。邻接表（无向图，每条边存两次）：

```
graph[0] = [(1,1), (3,4)]
graph[1] = [(0,1), (2,2), (3,5)]
graph[2] = [(1,2), (3,3)]
graph[3] = [(0,4), (1,5), (2,3)]

初始堆 [(0,0,0)]
弹出 (0,0,0): v=0 进树，mst=0。入堆 (1,0,1),(4,0,3)。堆[(1,0,1),(4,0,3)]
弹出 (1,0,1): v=1 进树，mst=1。入堆 (2,1,2),(5,1,3)。堆[(2,1,2),(4,0,3),(5,1,3)]
弹出 (2,1,2): v=2 进树，mst=3。入堆 (3,2,3)。堆[(3,2,3),(4,0,3),(5,1,3)]
弹出 (3,2,3): v=3 进树，mst=6。edges_used=4==n，停。
总权值 6，与 Kruskal 一致
```

两种算法选的边可能不同（这例子图里 MST 唯一，所以相同），但总权值一定相同。

### 3. 两种贪心的正确性证明（高手向）

为什么"按边贪心"和"按点贪心"都能得到 MST？两者都依赖一个共同的基础：**割性质（cut property）**。

**割性质**：把顶点集 V 任意分成两部分 S 和 V-S，所有横跨两部分的边（横割边）中，**权值最小**的那条一定属于某棵 MST。

**证明**（反证法）：设 e 是横割边中最小的，假设 e 不在某棵 MST $T$ 里。由于 $T$ 是生成树，$T$ 里必有一条横割边 f（否则 S 和 V-S 在 $T$ 里不连通）。由于 e 是横割边中最小，$w(e) \le w(f)$。把 f 换成 e，得到新树 $T' = T - \{f\} + \{e\}$，权值不增。如果 $w(e) < w(f)$，$T$ 不是 MST，矛盾；如果 $w(e) = w(f)$，$T'$ 也是 MST，且含 e。所以存在含 e 的 MST。

**Kruskal 的正确性**：Kruskal 每次选的边 e=(u,v)，设此刻 u 和 v 还不连通（否则跳过）。把"u 所在连通分量"看作 S，"其余"看作 V-S，e 是横割边。为什么 e 是最小的横割边？因为 Kruskal 按权值排序处理，所有比 e 小的边已处理完——它们要么已加入（连接了 S 内部某些点），要么被跳过（成环，说明两端都在 S 内）。所以没有任何更小的横割边未被处理，e 就是最小横割边。由割性质，e 在某棵 MST 里。归纳得 Kruskal 输出 MST。

**Prim 的正确性**：Prim 每次选的边 e=(u,v)，u 在树里、v 不在。把"当前树"看作 S，"其余"看作 V-S，e 是横割边。Prim 用优先队列始终取最小的横割边，由割性质，e 在某棵 MST 里。归纳得 Prim 输出 MST。

**对高手的启发**：两种算法看似不同，底层都靠割性质保证贪心正确。这种"不同切入、同一原理"的现象在算法里很常见——Dijkstra 和 Bellman-Ford 都靠"松弛"正确，快排和堆排都靠"比较产生序"。理解割性质，就抓住了 MST 的真正核心，Kruskal 和 Prim 只是它的两种工程化实现。

### 4. 五指标评价与稀疏/稠密选择

| 指标 | Kruskal | Prim（堆优化） | Prim（邻接矩阵） |
|---|---|---|---|
| 最好 | $O(E \log E)$ | $O(E \log V)$ | $O(V^2)$ |
| 平均 | $O(E \log E)$ | $O(E \log V)$ | $O(V^2)$ |
| 最坏 | $O(E \log E)$ | $O(E \log V)$ | $O(V^2)$ |
| 空间 | $O(V + E)$ | $O(V + E)$ | $O(V^2)$ |
| 排序瓶颈 | 是 | 否 | 否 |
| 适合图密度 | 稀疏图 | 稠密图 | 极稠密图 |

**为什么 Kruskal 适合稀疏图**：瓶颈是排序 $O(E \log E)$。稀疏图 $E \approx V$，复杂度 $O(V \log V)$，很快。而且 Kruskal 不需要建邻接表，只遍历边列表，常数小。

**为什么 Prim 适合稠密图**：稠密图 $E \approx V^2$。Kruskal 排序 $O(V^2 \log V)$；堆优化 Prim $O(V^2 \log V)$，差不多；但**邻接矩阵版 Prim** 不用堆，每次线性扫所有顶点找最小邻边，$O(V^2)$，比 Kruskal 的 $O(V^2 \log V)$ 快一个 $\log$。所以稠密图用邻接矩阵版 Prim 最优。

### 5. Kruskal 和 Dijkstra 长得像但不同

新手常把 Kruskal 和 Dijkstra 搞混——都是"贪心 + 堆/排序"。区别在贪心目标：

- **Kruskal** 贪心的是"全局最短边"，目标是**树的总权值最小**，不在乎单源距离。
- **Dijkstra** 贪心的是"当前最短源距离"，目标是**单源到各点距离最短**，路径权值和最小。

Kruskal 选的边构成一棵树，Dijkstra 选的边构成一棵最短路径树（root 到各点路径最短）。两者数学上不等价——MST 不一定是最短路径树，反之亦然。

## 三、实践与面试：手撕模板、对数器、面试题

### 1. 面试手撕模板

面试中 MST 默认考 Kruskal（代码短、考并查集），偶尔考 Prim。两种都要会：

```python
# Kruskal 面试模板（含并查集）
class UF:
    def __init__(self, n):
        self.p = list(range(n))
        self.r = [0] * n
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]   # 路径压缩
            x = self.p[x]
        return x
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b: return False
        if self.r[a] < self.r[b]: a, b = b, a
        self.p[b] = a
        if self.r[a] == self.r[b]: self.r[a] += 1
        return True

def kruskal(n, edges):
    edges.sort()
    uf = UF(n)
    ans, cnt = 0, 0
    for w, u, v in edges:
        if uf.union(u, v):
            ans += w
            cnt += 1
            if cnt == n - 1: break
    return ans if cnt == n - 1 else -1   # -1 表示图不连通
```

**面试时怎么讲**（按"技术的水有多深"八层面，挑重点）：

1. **问题层**：n 个顶点的连通图，找 n-1 条边权值和最小的生成树。
2. **原理层**：Kruskal 按边排序贪心，用并查集判环；Prim 按点扩展贪心，用优先队列取最短邻边。两者都靠割性质保证正确。
3. **优劣层**：Kruskal $O(E \log E)$ 适合稀疏图，Prim $O(E \log V)$ 适合稠密图；Kruskal 代码短考并查集，Prim 考堆。
4. **演进层**：Kruskal 1956、Prim 1957（实为 Jarník 1930），都建立在割性质上；Borůvka 1926 更早，Sollin 改进。

**面试加分点**：主动讲"为什么 MST 有两个主流算法"——稀疏图用 Kruskal、稠密图用 Prim，并说出割性质是共同基础。这能立刻区分你和"只会背模板"的候选人。

### 2. 对数器：随机图对比 Kruskal 与 Prim

MST 的对数器有个绝佳用法：**两种算法互为对数器**。因为两者输出权值和必然相同（MST 权值唯一），随机生成图，跑两种算法，对比总权值即可。这比"和标准答案比"更优雅——不需要第三方实现，两个独立实现互相校验。

```python
import random
import heapq

# UF 和 kruskal 同上
def prim(n, graph):
    visited = [False] * n
    heap = [(0, 0, 0)]
    ans, cnt = 0, 0
    while heap and cnt < n:
        w, u, v = heapq.heappop(heap)
        if visited[v]: continue
        visited[v] = True
        ans += w
        cnt += 1
        for nb, w2 in graph[v]:
            if not visited[nb]:
                heapq.heappush(heap, (w2, v, nb))
    return ans if cnt == n else -1

def checker(times=2000, max_n=20, max_w=100):
    for _ in range(times):
        n = random.randint(1, max_n)
        # 随机连通图：先建一棵生成树保证连通，再随机加边
        edges = []
        graph = [[] for _ in range(n)]
        for i in range(1, n):
            j = random.randint(0, i - 1)
            w = random.randint(1, max_w)
            edges.append((w, j, i))
            graph[j].append((i, w))
            graph[i].append((j, w))
        # 随机加额外边
        extra = random.randint(0, n * 2)
        for _ in range(extra):
            u, v = random.sample(range(n), 2)
            w = random.randint(1, max_w)
            edges.append((w, u, v))
            graph[u].append((v, w))
            graph[v].append((u, w))
        k = kruskal(n, edges)
        p = prim(n, graph)
        if k != p:
            print(f"出错！n={n}, edges={edges}, kruskal={k}, prim={p}")
            return False
    print("对数器验证通过！两种算法结果一致。")
    return True

checker()
```

**对数器的价值**：

- **互相校验**：两种独立实现，思路完全不同（一个按边一个按点），结果一致说明两者都对——比单一实现对标准答案更可靠。
- **覆盖边界**：随机图包含连通图、含孤立点（n=1）、稠密图、稀疏图，能覆盖手写时容易遗漏的场景。
- **左神原话**：MST 是对数器的经典应用——两个独立贪心互相验证，比"和课本答案比"更能暴露隐藏 bug。

### 3. 教科书做法 vs 生产做法

| 场景 | 教科书做法 | 生产做法 | 原因 |
|---|---|---|---|
| 网络设计/布线 | 手写 Kruskal | `scipy.sparse.csgraph.minimum_spanning_tree` | 生产库已优化，且支持稀疏矩阵 |
| 稠密图 MST | 邻接矩阵 Prim | 同上 | 库内部自动选算法 |
| 面试/竞赛 | 手写 Kruskal | 手写 Kruskal | 考并查集，代码短 |
| 聚类（MST 切割） | 手写后切最长边 | `sklearn.cluster.AgglomerativeClustering` | MST 是单链接聚类的底层 |

**生产里直接手写 MST 较少**，但有两个高频场景：

1. **竞赛/面试**：手写 Kruskal 是基本功，考并查集和贪心。
2. **聚类预处理**：单链接层次聚类的底层就是 MST——求完 MST 后切掉最长的 k-1 条边，得到 k 个簇。理解 MST 能让你看懂这类聚类算法。

### 4. 三个真实工程坑

**坑一：Kruskal 忘了判图是否连通。**

```python
def kruskal_bad(n, edges):
    edges.sort()
    uf = UF(n)
    ans, cnt = 0, 0
    for w, u, v in edges:
        if uf.union(u, v):
            ans += w
            cnt += 1
    return ans   # 没有 cnt == n-1 的判断
```

症状：图不连通时返回一个错误答案（部分森林的权值和），不报错。根因：没检查选够 n-1 条边。修复：返回前判 `if cnt != n - 1: return -1`。

**坑二：Prim 堆里放已访问顶点的边，导致重复处理。**

```python
def prim_bad(n, graph):
    visited = [False] * n
    heap = [(0, 0, 0)]
    ans = 0
    while heap:
        w, u, v = heapq.heappop(heap)
        visited[v] = True            # 漏了 if visited[v]: continue
        ans += w
        for nb, w2 in graph[v]:
            heapq.heappush(heap, (w2, v, nb))   # 漏了 if not visited[nb]
    return ans
```

症状：权值重复累加，结果偏大；可能死循环（已访问顶点的边反复入堆）。根因：没跳过已访问终点。修复：弹堆后先 `if visited[v]: continue`，入堆前判 `if not visited[nb]`。

**坑三：把 MST 和最短路径混为一谈。**

```python
# 误以为 MST 就是从某点出发的最短路径树
# 用 Dijkstra 求最短路径树，当 MST 用
```

症状：答案错。根因：MST 最小化的是"树的总权值"，Dijkstra 最短路径树最小化的是"root 到各点距离和"，两者数学不等价。反例：图 `0-1(1), 1-2(1), 0-2(10)`，MST 选前两条边（总 2），从 0 出发的最短路径树到 2 是直接边 0-2(10)（总距离 10）——完全不同。修复：搞清问题，MST 用 Kruskal/Prim，单源最短路用 Dijkstra。

### 5. 面试高频题：连接所有点的最小费用（LeetCode 1584）

**题目**：给定平面上 n 个点，连接所有点的最小费用，费用是曼哈顿距离。点 i 和点 j 的曼哈顿距离是 $|x_i - x_j| + |y_i - y_j|$。

**思路**：这是一个完全图 MST——每对点都有一条边，边权是曼哈顿距离。n 个点的完全图有 $n(n-1)/2$ 条边，稠密。所以选 Prim（邻接矩阵版），不要选 Kruskal（排序 $O(n^2 \log n)$）。

```python
def minCostConnectPoints(points):
    n = len(points)
    visited = [False] * n
    # min_dist[i]: 顶点 i 到当前树的最短距离
    min_dist = [float('inf')] * n
    min_dist[0] = 0
    ans = 0
    for _ in range(n):
        # 找未访问中 min_dist 最小的顶点（邻接矩阵版 Prim）
        u = -1
        for i in range(n):
            if not visited[i] and (u == -1 or min_dist[i] < min_dist[u]):
                u = i
        visited[u] = True
        ans += min_dist[u]
        # 用 u 更新所有未访问顶点的 min_dist
        for v in range(n):
            if not visited[v]:
                d = abs(points[u][0] - points[v][0]) + abs(points[u][1] - points[v][1])
                if d < min_dist[v]:
                    min_dist[v] = d
    return ans
```

**复杂度**：$O(n^2)$，邻接矩阵版 Prim。如果用堆优化 Prim，是 $O(n^2 \log n)$，反而慢——稠密图上邻接矩阵版更优。这是"按图密度选算法"的典型应用。

**面试官追问"为什么不用 Kruskal"**：完全图有 $O(n^2)$ 条边，Kruskal 排序 $O(n^2 \log n)$；邻接矩阵版 Prim $O(n^2)$，省一个 $\log$。n=1000 时差距明显。

**面试官追问"为什么不用堆优化 Prim"**：堆优化 Prim $O(E \log V) = O(n^2 \log n)$，邻接矩阵版 $O(V^2) = O(n^2)$。稠密图 $E \approx V^2$，堆优化的 $\log V$ 因子反而拖累——堆里有 $O(E)$ 条边，每次 pop 是 $O(\log E) = O(\log V)$。所以稠密图用朴素 Prim，稀疏图用堆优化 Prim 或 Kruskal。

**扩展题：最优连通子集**。给一个图，每个点有权值（可正可负），求一个连通子集使权值和最大。这类题的变体很多，本质是 MST 的衍生——如果权值在边上、求最小连通，就是 MST；如果在点上、求最大连通，需要转化。面试中遇到"连通子集"类问题，先想清楚权值在边还是点、求最大还是最小，再决定用 MST 还是别的算法。

## 四、速查与自测

### 速查表：Kruskal 与 Prim 对比

| 维度 | Kruskal | Prim |
|---|---|---|
| 切入 | 按边 | 按点 |
| 数据结构 | 排序 + 并查集 | 优先队列 / 邻接矩阵 |
| 复杂度 | $O(E \log E)$ | $O(E \log V)$（堆）/ $O(V^2)$（矩阵） |
| 适合图 | 稀疏图 | 稠密图 |
| 判环方式 | 并查集 union | visited 数组 |
| 代码量 | 短 | 中 |
| 历史年份 | 1956 | 1957（Jarník 1930） |
| 共同基础 | 割性质 | 割性质 |

**选型口诀**：边少用 Kruskal，边多用 Prim；面试默认 Kruskal（考并查集），稠密完全图用矩阵 Prim。

### 自测三问

**问题一：** 为什么 MST 恰好有 n-1 条边？请用"环"和"连通"两个概念解释。

**参考答案：** 生成树要满足"连通"和"无环"。n 个顶点的连通图至少要 n-1 条边才能连通（少一条就不连通）；而 n-1 条边的连通图必然无环（再多一条边必成环）。所以生成树恰好 n-1 条边——这是"连通且无环"的硬约束。MST 是权值最小的生成树，边数也是 n-1。这个性质是 Kruskal 提前终止（`len(mst) == n-1`）和 Prim 计数（`edges_used < n`）的依据。

**问题二：** Kruskal 和 Prim 都靠割性质保证正确，请说明割性质是什么，并解释为什么 Kruskal 每次选的边满足割性质。

**参考答案：** 割性质：把顶点集 V 任意分成 S 和 V-S，所有横割边中权值最小的那条一定属于某棵 MST。Kruskal 每次选边 e=(u,v) 时，u 和 v 还不连通（否则跳过）。把"u 所在连通分量"看作 S，"其余"看作 V-S，e 是横割边。因为 Kruskal 按权值排序处理，所有比 e 小的边已处理完——它们要么已加入（连接 S 内部），要么被跳过（成环说明两端都在 S 内）。所以没有更小的横割边未处理，e 就是最小横割边，由割性质必在某棵 MST 里。归纳得 Kruskal 输出 MST。

**问题三：** LeetCode 1584（连接所有点的最小费用）为什么用邻接矩阵版 Prim 而不用堆优化 Prim 或 Kruskal？

**参考答案：** 1584 是完全图，有 $O(n^2)$ 条边。Kruskal 排序 $O(n^2 \log n)$；堆优化 Prim $O(E \log V) = O(n^2 \log n)$，因为堆里有 $O(E) = O(n^2)$ 条边，每次 pop 是 $O(\log V)$；邻接矩阵版 Prim 每轮线性扫所有顶点找最小，$O(V^2) = O(n^2)$，省一个 $\log$。稠密图（$E \approx V^2$）上朴素 Prim 比堆优化快，这是"按图密度选算法"的典型——稀疏图才用堆优化 Prim 或 Kruskal。

### 算法思想 × 生活迁移

MST 的核心思想是"**用最小成本连通所有节点**"——不追求每两点直达，只要"绕路能到"，且总成本最小。

**迁移一：城市路网规划。** 新城要修路连通所有功能区，不需要每两区都直达——只要"能到达"。先列所有候选路段和造价，按造价排序，从便宜的修起，修到某条路会发现"两区已能绕路到达"——这条路就不修了。这就是 Kruskal 思路。现实里城市规划正是这种"主干 + 支路"模式，不是两两直达的网格。

**迁移二：团队协作的最小沟通成本。** n 个人的团队，要让信息能传到每个人。不需要每两人都直接沟通（成本 $O(n^2)$），只要建一棵"沟通树"——每人只和少数几人常沟通，信息通过树传递。选沟通对象时优先选"沟通顺畅（成本低）"的对，避免冗余链路。这就是 MST 思路——用 n-1 条沟通关系覆盖 n 个人，总摩擦最小。

**迁移三：仓库选址与配送网络。** n 个仓库要互相调货，建立调货关系。每对仓库的运输成本不同（距离、路况）。用 MST 选 n-1 条调货路线，总运输成本最小，且任两仓库都能通过调货网络互通。这正是物流网络设计的底层逻辑——主干线路 + 二级配送，而非两两直达。

**为什么这些迁移成立：** MST 成立的前提是"连通即可，不要求直达"且"成本可加权累加"。这个前提在路网、沟通网络、物流网络里都成立——都是"用最少的关系覆盖所有节点"。迁移成立的关键是"问题能抽象成加权连通图"——如果问题要求每两点直达（如实时同步的数据库），MST 思路就不适用，那属于"完全图"问题。

## 参考来源

- Kruskal, J. B. *On the shortest spanning subtree of a graph and the traveling salesman problem*. Proceedings of the American Mathematical Society, 1956.（Kruskal 算法原始论文，按边排序 + 判环的贪心框架）
- Prim, R. C. *Shortest connection networks and some generalizations*. Bell System Technical Journal, 1957.（Prim 算法原始论文，按点扩展的贪心框架；Jarník 1930 更早提出）
- Jarník, V. *O jistém problému minimálním*. Práce Moravské Přírodovědecké Společnosti, 1930.（Prim 算法的最早提出，捷克语，后被 Prim 独立发现）
- [1] Cormen, T. H. et al. *Introduction to Algorithms*. MIT Press, 4th ed., 2022. 第 23 章（MST 的权威讨论，Kruskal 与 Prim 并列，割性质证明）
- [2] Sedgewick, R. & Wayne, K. *Algorithms*. Addison-Wesley, 4th ed., 2011. 第 4 章（MST 实现，Kruskal 与 Prim 的工程对比）
- [3] 邓俊辉. 数据结构（C++语言版）. 清华大学出版社, 第 3 版, 2013.（国内教学参考，MST 章节）
- [7-补充] krahets. *Hello 算法*. [hello-algo.com/chapter_graph/mst](https://www.hello-algo.com/chapter_graph/mst/).（MST 图示与多语言代码）
- [17] TheAlgorithms/Python. [github.com/TheAlgorithms/Python](https://github.com/TheAlgorithms/Python).（Kruskal/Prim 可运行实现对照）
- [23] 左程云. 程序员代码面试指南. 电子工业出版社.（"对数器"验证方法、"按数据状况选算法"的工程视角）
- LeetCode 1584. *Connecting Cities With Minimum Cost*.（完全图 MST，邻接矩阵版 Prim 的典型应用）
- 用户信源：`book-sources/面试现场/技术表达（表达方法+面试官视角）.md`（"技术的水有多深"八层面表达框架，本文"面试时怎么讲"参考此框架）
- 用户信源：`book-sources/面试现场/考察标准（编程能力+软性能力）.md`（"贪心思维""图论建模"的面试考查视角，本文"面试高频题"参考此标准）
