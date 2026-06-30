---
title: 算法课·17｜图的遍历：BFS 与 DFS 背后的两种世界观
book: 数据结构与算法
chapter: 图遍历
event: BFS与DFS
sort: 1
chapter_sort: 7
created_at: 2026-06-29
source_agents:
- algorithm-expert
---
# 算法课·17｜图的遍历：BFS 与 DFS 背后的两种世界观

> 前置知识：学完第 16 章（图的存储），尤其要懂邻接表（Adjacency List）怎么存图、有向图和无向图的差别
> 学完你能：①给小白讲清 BFS 和 DFS 为什么是"两种探索姿态"而不是"两个算法" ②默写两种遍历并讲透每一行 ③用 BFS 求无权图最短路径 ④用 DFS 求连通分量、拓扑排序、环检测 ⑤用对数器在随机图上对比两种遍历的访问顺序 ⑥手撕岛屿数量、克隆图、单词接龙三道面试高频题

## 一、问题与思路：BFS 和 DFS 不是两个算法，是两种探索世界的姿态

### 1. 一个反直觉问题：迷宫找出口该"层层扩展"还是"一路到底"

假设你站在一座陌生城市的地铁站，要去某个目的地，手里只有一张线路图，不知道哪条线最近。你只能逐站探索——这时候你会选哪种策略：先看相邻站，再看两站外的站，再看三站外的站？还是选一条线一路坐到底，走不通再回头换一条线？

前一种就是 BFS（Breadth-First Search，广度优先搜索）的姿态，后一种就是 DFS（Depth-First Search，深度优先搜索）的姿态。这里有个反直觉的事实：BFS 和 DFS 的代码骨架几乎一样，差别只在用一个数据结构——队列（Queue）还是栈（Stack）。但就这一处差别，让它们各自擅长完全不同的问题：BFS 天然能找最短路径，DFS 天然能判连通和检测环。

### 2. BFS：圈层扩展，最短路径的直觉

BFS 的姿态是"圈层扩展"——从起点出发，先访问所有距离为 1 的节点（一圈），再访问所有距离为 2 的节点（两圈），依次向外。就像往水里扔石头，波纹一圈圈扩散。

为什么这个姿态天然能找最短路径？因为 BFS 按"距离"递增的顺序访问节点——第一次到达某个节点时，经过的边数一定是最少的。这是无权图（Unweighted Graph，每条边权重为 1）最短路径的标准解法。注意：有权图就不灵了，有权图要用 Dijkstra（迪杰斯特拉算法），因为 BFS 假设"边数少 = 距离短"，有权图里这条假设不成立。

BFS 用队列实现——先访问的节点先扩展（FIFO，先进先出），保证"先扩展完一圈再扩下一圈"。

### 3. DFS：一路到底，连通性的直觉

DFS 的姿态是"一路到底"——从起点出发，沿着一条路一直走，走不动了（没有未访问的邻居）再回退，换另一条路继续。就像探洞，钻一条岔路到底，发现死路就退回上一个分叉点换路。

为什么这个姿态适合判连通？因为 DFS 会把从起点能到达的所有节点一次性走完——走完之后还没被访问的节点，一定不在同一个连通分量（Connected Component）里。这种"一路走到底再回退"的特性，让 DFS 特别适合做：连通分量计数、拓扑排序（Topological Sort）、环检测（Cycle Detection）。

DFS 用栈实现——后访问的节点先扩展（LIFO，后进先出）。栈可以是显式的，也可以是函数调用栈（递归），递归写法更简洁但深度大时会栈溢出。

### 4. 两种遍历的统一框架

BFS 和 DFS 的代码骨架其实可以统一成一个模板：

```
访问起点（标记已访问）
while 待访问容器非空：
    取出节点 u
    for u 的每个邻居 v：
        if v 未访问：
            标记 v 已访问
            把 v 放进待访问容器
```

唯一区别在"待访问容器"用什么：队列就是 BFS，栈就是 DFS。这个统一视角告诉我们：BFS 和 DFS 不是两个算法，是同一个框架的两种参数选择。理解这一点，就不会把它们当成两套孤立的东西去死记。

## 二、原理与实现：从代码模板到典型应用

### 1. BFS 代码模板（邻接表实现）

```python
from collections import deque

def bfs(graph, start):
    """BFS 遍历，graph 是邻接表（dict[int, list[int]]）。"""
    visited = {start}                  # 入队即标记，避免重复入队
    queue = deque([start])             # 队列：FIFO 保证按圈层扩展
    order = []
    while queue:
        u = queue.popleft()            # 队首出队
        order.append(u)
        for v in graph[u]:             # 遍历邻居
            if v not in visited:       # 未访问才入队，避免重复
                visited.add(v)
                queue.append(v)
    return order
```

**逐行讲透**：

- **`visited = {start}`**：访问标记用集合 $O(1)$ 判断。为什么必须在"入队时"标记而不是"出队时"？如果出队才标记，同一个节点会被多个邻居重复入队，队列膨胀到 $O(E)$，时间也退化到 $O(VE)$。入队时标记，保证每个节点只入队一次。
- **`queue = deque([start])`**：用 `collections.deque` 不用 `list`。`list.pop(0)` 是 $O(n)$，`deque.popleft()` 是 $O(1)$——这是 Python 写 BFS 的硬性要求。
- **`queue.popleft()`**：队首出队。FIFO 保证先入队的先扩展，从而实现"圈层扩展"。
- **`for v in graph[u]`**：遍历 u 的所有邻居。`graph[u]` 是邻接表里 u 的邻居列表。
- **`if v not in visited`**：跳过已访问邻居。无向图里每条边会被两端各看一次，标记保证不会重复入队。

**复杂度**：邻接表存储下，每个节点入队一次 $O(V)$，每条边被检查一次（无向图）或两次（每端各一次），合计 $O(V + E)$。如果是邻接矩阵存储，每次 `for v in graph[u]` 要扫一行 $O(V)$，总 $O(V^2)$——这是邻接矩阵存稀疏图（Sparse Graph，$E \ll V^2$）效率低的原因。

### 2. DFS 代码模板（递归 + 显式栈）

**递归版**（最常用，代码最简）：

```python
def dfs_recursive(graph, start, visited=None, order=None):
    """DFS 递归版。函数调用栈就是隐式栈。"""
    if visited is None:
        visited, order = set(), []
    visited.add(start)                 # 进入函数即标记，避免重复进入
    order.append(start)
    for v in graph[start]:             # 按邻接表顺序探索
        if v not in visited:
            dfs_recursive(graph, v, visited, order)
    return order
```

**显式栈版**（避免栈溢出，处理深度大的图）：

```python
def dfs_iterative(graph, start):
    """DFS 显式栈版。和 BFS 只差 popleft → pop。"""
    visited = set()
    stack = [start]                    # 栈：LIFO 保证一路到底
    order = []
    while stack:
        u = stack.pop()                # 栈顶出栈（注意：不是 popleft）
        if u in visited:               # 入栈时不标记，出栈时才检查
            continue
        visited.add(u)
        order.append(u)
        for v in reversed(graph[u]):   # 反转是为了和递归版访问顺序一致
            if v not in visited:
                stack.append(v)
    return order
```

**关键细节**：

- **递归版"进入即标记"**：和 BFS 的"入队即标记"对应——保证每个节点只被递归进入一次，时间 $O(V + E)$。
- **显式栈版"出栈才标记"**：这里有个坑。如果显式栈版也"入栈即标记"，访问顺序会和递归版不一致——因为栈是 LIFO，后入的先出，但标记已经定死。更稳妥的做法是"入栈时不标记，出栈时再判断是否已访问"，能严格复现递归版的访问顺序。`reversed(graph[u])` 是为了让邻居按原顺序入栈后弹出顺序和递归一致——栈是 LIFO，要正序访问就得反转入栈。
- **栈溢出风险**：递归版在最坏情况（图退化成链）下递归深度等于节点数 $V$。Python 默认递归深度 1000，节点数超过这个值会 `RecursionError`。显式栈版用 `list` 当栈，没有深度限制——这是大图必须用显式栈的原因。

### 3. BFS 求无权图最短路径

把 BFS 模板稍作改造，记录每个节点的"前驱"和"距离"：

```python
from collections import deque

def bfs_shortest_path(graph, start, target):
    """求 start 到 target 的最少边数路径。无权图专用。"""
    if start == target:
        return [start]
    visited = {start}
    queue = deque([start])
    prev = {start: None}               # 前驱节点，用于回溯路径
    dist = {start: 0}                  # 到起点的边数距离
    while queue:
        u = queue.popleft()
        for v in graph[u]:
            if v not in visited:
                visited.add(v)
                prev[v] = u
                dist[v] = dist[u] + 1  # 距离 = 前驱距离 + 1
                if v == target:        # 第一次到达即最短
                    path = []
                    cur = v
                    while cur is not None:
                        path.append(cur)
                        cur = prev[cur]
                    return path[::-1]
                queue.append(v)
    return None                        # 不可达
```

**为什么"第一次到达即最短"**：BFS 按距离递增顺序访问节点。距离为 1 的全部访问完，才访问距离为 2 的；距离为 2 的全部访问完，才访问距离为 3 的。所以 target 第一次被访问时，`dist[target]` 一定是最小边数。这是 BFS 在无权图上求最短路径的根本依据。

**注意边界**：有权图不能用这个方法——边的权重不同，"边数少"不一定"距离短"。比如 A→B 边权 100，A→C→B 边权各 1，BFS 会选 A→B（1 条边），但最短是 A→C→B（2 条边，总权 2）。有权图用 Dijkstra（非负权）或 Bellman-Ford（含负权）。

### 4. DFS 求连通分量

```python
def count_components(graph, n):
    """求无向图的连通分量个数。n 是节点数（0 到 n-1）。"""
    visited = set()
    count = 0
    for node in range(n):              # 每个未访问节点启动一次 DFS
        if node not in visited:
            dfs_mark(graph, node, visited)
            count += 1                 # 一次 DFS 走完一个连通分量
    return count

def dfs_mark(graph, u, visited):
    visited.add(u)
    for v in graph.get(u, []):
        if v not in visited:
            dfs_mark(graph, v, visited)
```

**为什么一次 DFS 走完一个连通分量**：DFS 会把从起点能到达的所有节点都访问到。所以从任一未访问节点启动 DFS，走完之后这一片连通区域全部被标记——剩下的未访问节点一定属于其他连通分量。再启动一次 DFS 就能数下一个分量。

**复杂度**：所有节点各被访问一次，所有边各被检查一次（无向图），总 $O(V + E)$。

### 5. DFS 做拓扑排序（仅 DAG）

拓扑排序（Topological Sort）只对 DAG（Directed Acyclic Graph，有向无环图）有意义——把所有节点排成一列，使每条有向边 $(u, v)$ 都满足 $u$ 在 $v$ 之前。常见应用：任务依赖、课程先后顺序。

```python
def topological_sort(graph, n):
    """DFS 版拓扑排序。graph[u] = u 指向的节点列表。"""
    WHITE, GRAY, BLACK = 0, 1, 2       # 三色标记：白未访问，灰在栈中，黑已完成
    color = [WHITE] * n
    result = []
    has_cycle = [False]
    
    def dfs(u):
        if has_cycle[0]:
            return
        color[u] = GRAY                # 进入时染灰，用于环检测
        for v in graph[u]:
            if color[v] == GRAY:       # 遇到灰色节点 = 回边 = 有环
                has_cycle[0] = True
                return
            if color[v] == WHITE:
                dfs(v)
        color[u] = BLACK               # 完成时染黑
        result.append(u)               # 完成顺序入栈
    
    for node in range(n):
        if color[node] == WHITE:
            dfs(node)
    
    if has_cycle[0]:
        return None                    # 有环不能拓扑排序
    return result[::-1]                # 完成顺序的逆序就是拓扑序
```

**关键点**：节点在"DFS 完成"时入栈，最后整体反转——这就是拓扑序。为什么？因为如果 $u \to v$ 是边，DFS 一定会先访问 $v$ 再完成 $v$，最后才完成 $u$（$u$ 必须等所有后继完成才能完成）。所以"完成顺序"里 $v$ 在 $u$ 前面，反转后 $u$ 在 $v$ 前面，符合拓扑序定义。

**三色标记**：WHITE/GRAY/BLACK 不仅是为了避免重复访问，GRAY 还用来检测环——遇到 GRAY 节点说明存在回边（从当前路径上的节点指回当前路径上的另一个节点），即环。如果图有环，就不存在拓扑序（环上的节点互相依赖，无法排序）。

### 6. DFS 做环检测

上面拓扑排序里已经包含了环检测（GRAY 回边）。单独的无向图环检测更简单：

```python
def has_cycle_undirected(graph, n):
    """无向图环检测。"""
    visited = set()
    def dfs(u, parent):
        visited.add(u)
        for v in graph[u]:
            if v not in visited:
                if dfs(v, u):          # 递归发现环
                    return True
            elif v != parent:          # 已访问且不是父节点 = 找到环
                return True
        return False
    for node in range(n):
        if node not in visited:
            if dfs(node, -1):
                return True
    return False
```

**为什么无向图要传 `parent`**：无向图里每条边 $(u, v)$ 实际是两条有向边 $u \to v$ 和 $v \to u$。如果不传 parent，DFS 从 $u$ 走到 $v$ 后会看到 $u$ 是 $v$ 的邻居，误判为环。传 parent 就能跳过"刚来的那条边"，只对其他已访问邻居报环。

**有向图环检测**：用上面拓扑排序的三色标记法，GRAY 回边即环。不能传 parent——有向图里 $u \to v$ 不代表 $v \to u$，父节点概念不成立。

### 7. 五指标对比

| 指标 | BFS | DFS |
|---|---|---|
| 时间 | $O(V + E)$ | $O(V + E)$ |
| 空间 | $O(V)$（队列 + visited） | $O(V)$（栈/递归深度 + visited） |
| 最短路径（无权） | 直接支持 | 不直接支持 |
| 连通分量 | 支持 | 支持（更顺手） |
| 拓扑排序 | 不支持 | 支持 |
| 环检测 | 支持（较繁琐） | 支持（三色标记顺手） |
| 大图栈溢出 | 不会（队列深度 ≤ $V$） | 递归版会，显式栈版不会 |

## 三、实践与面试：对数器、工程取舍、面试高频题

### 1. 对数器：随机图对比两种遍历的访问顺序

写完 BFS 和 DFS 不要靠肉眼检查正确性——用对数器验证。验证两件事：①两种遍历访问的节点集合相同（都等于整个连通分量）；②起点必须是访问顺序的第一个。

```python
import random
from collections import deque

def bfs(graph, start):
    visited = {start}
    queue = deque([start])
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in sorted(graph[u]):          # 排序保证可复现
            if v not in visited:
                visited.add(v)
                queue.append(v)
    return order

def dfs(graph, start):
    visited = set()
    order = []
    def _dfs(u):
        visited.add(u)
        order.append(u)
        for v in sorted(graph[u]):          # 排序保证可复现
            if v not in visited:
                _dfs(v)
    _dfs(start)
    return order

def checker(test_times=500, max_n=20, edge_prob=0.3):
    """对数器：随机无向图，验证 BFS 和 DFS 访问集合一致。"""
    for _ in range(test_times):
        n = random.randint(1, max_n)
        graph = {i: [] for i in range(n)}
        for i in range(n):
            for j in range(i + 1, n):
                if random.random() < edge_prob:
                    graph[i].append(j)
                    graph[j].append(i)
        start = random.randint(0, n - 1)
        bfs_order = bfs(graph, start)
        dfs_order = dfs(graph, start)
        # 验证：访问集合必须相同（都等于从 start 出发的连通分量）
        if set(bfs_order) != set(dfs_order):
            print(f"出错！graph={graph}, start={start}")
            print(f"BFS: {bfs_order}")
            print(f"DFS: {dfs_order}")
            return False
        # 验证：起点必须是访问顺序的第一个
        if bfs_order[0] != start or dfs_order[0] != start:
            print(f"起点错误！start={start}")
            return False
    print("对数器验证通过！")
    return True

checker()
```

**对数器的价值**：

- **覆盖边界**：随机图覆盖稀疏图、稠密图、孤立节点、单链等结构，比手工构造全面
- **不依赖人工**：跑 500 次几秒内完成，能撞出大多数边界 bug
- **可复现**：`sorted(graph[u])` 保证遍历顺序确定，便于复现 bug

**对高手的启发**：图的算法比排序更容易写错——边界（孤立点、自环、重边、不连通）多，调试靠肉眼看不出。对数器在图算法里的价值比排序更高，是工程化验证的标配。

### 2. 教科书做法 vs 生产做法

| 场景 | 教科书做法 | 生产做法 | 原因 |
|---|---|---|---|
| 无权图最短路径 | 手写 BFS | `networkx.single_source_shortest_path` | 库经过测试，省心 |
| 大规模图遍历 | 递归 DFS | 显式栈或 `networkx.dfs_preorder_nodes` | 递归深度大易栈溢出 |
| 拓扑排序 | 手写 DFS 三色 | `graphlib.TopologicalSorter`（Python 3.9+） | 标准库已支持 |
| 连通分量 | 手写 DFS | `scipy.sparse.csgraph.connected_components` | 稀疏矩阵实现更快 |

**生产里手写图算法的残留场景**：①面试必须手写 ②受限环境不能用第三方库 ③性能极致优化（库的通用实现可能有冗余）。其他场景优先用标准库或 `networkx`——别重复造轮子。

### 3. BFS vs DFS 的工程取舍

**选 BFS 的场景**：

- 求"最少步数""最少操作""最短路径"——只要每步权重相同（无权图模型），BFS 是首选
- 求"最近的 X"——如最近的关键节点、最近的出口
- 分层处理——如按层级遍历树、按距离分桶

**选 DFS 的场景**：

- 判连通、找连通分量
- 拓扑排序、环检测
- 找"所有路径"或"所有方案"（回溯就是 DFS）
- 拓扑结构深、分支少的图——DFS 栈深但队列窄

**两者都行但 DFS 更顺的场景**：迷宫找"任意一条出路"（不需要最短）——DFS 一路到底可能更快撞到出口，BFS 要扫完一层层。

**两者都行但 BFS 更顺的场景**：社交网络里"几度好友关系"——BFS 按距离分层天然给出"几度"。

### 4. 面试高频题一：岛屿数量（LeetCode 200）

> 给一个 `m × n` 的二维网格，`'1'` 是陆地，`'0'` 是水，相邻（上下左右）的 `'1'` 算一个岛屿。求岛屿数量。

**思路**：把网格看成图，每个 `'1'` 是节点，上下左右相邻的 `'1'` 之间有边。岛屿数 = 连通分量数。用 DFS 每次把一个岛屿"淹掉"（访问过的 `'1'` 改成 `'0'`），计数即可。

```python
def num_islands(grid):
    """LeetCode 200。grid 是 list[list[str]]。"""
    if not grid:
        return 0
    m, n = len(grid), len(grid[0])
    count = 0
    
    def dfs(i, j):
        if i < 0 or i >= m or j < 0 or j >= n:
            return
        if grid[i][j] != '1':           # 不是陆地（水或已访问）直接返回
            return
        grid[i][j] = '0'                # 淹掉，避免重复访问
        dfs(i - 1, j)                   # 上下左右四个方向
        dfs(i + 1, j)
        dfs(i, j - 1)
        dfs(i, j + 1)
    
    for i in range(m):
        for j in range(n):
            if grid[i][j] == '1':       # 发现新岛屿，DFS 淹掉整个岛
                dfs(i, j)
                count += 1
    return count
```

**复杂度**：$O(m \times n)$，每个格子最多访问一次。

**面试怎么讲**：①把网格转成隐式图（邻居是上下左右） ②岛屿 = 连通分量 ③DFS 每次淹掉一个岛 ④不另开 visited 数组，直接改 grid 省空间（如果要求不改原数据，则用 visited）。

### 5. 面试高频题二：克隆图（LeetCode 133）

> 给一个无向连通图的某个节点引用，返回整张图的深拷贝。

**思路**：用 BFS 遍历原图，遍历过程中一边建新节点一边建新边。关键是用一个 `dict` 记录"原节点 → 新节点"的映射，避免重复克隆。

```python
from collections import deque

class Node:
    def __init__(self, val=0, neighbors=None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []

def clone_graph(node):
    """LeetCode 133。node 是图的任意一个节点。"""
    if not node:
        return None
    cloned = {node: Node(node.val)}      # 映射：原节点 → 克隆节点
    queue = deque([node])
    while queue:
        u = queue.popleft()
        for v in u.neighbors:
            if v not in cloned:          # 邻居还没克隆，先克隆入队
                cloned[v] = Node(v.val)
                queue.append(v)
            cloned[u].neighbors.append(cloned[v])   # 建新边
    return cloned[node]
```

**为什么 BFS 适合**：图的克隆需要"原节点和新节点一一对应"，BFS 按圈层处理，能在访问每个节点时同时处理它的所有邻居，建立边的关系。DFS 也能做，但 BFS 的迭代写法不会栈溢出。

**坑**：不能在 `cloned` 里只存新节点——必须存"原→新"映射，因为建边时要根据原邻居找到对应的新邻居。

### 6. 面试高频题三：单词接龙（LeetCode 127）

> 给两个单词 `beginWord` 和 `endWord`，和一个字典 `wordList`。每次变换一个字母，且变换后的词必须在字典里。求从 `beginWord` 到 `endWord` 的最短变换序列长度。

**思路**：把每个单词看成图的节点，两个单词只差一个字母就连一条边。问题变成"无权图最短路径"——BFS。

```python
from collections import deque

def ladder_length(begin_word, end_word, word_list):
    """LeetCode 127。"""
    word_set = set(word_list)
    if end_word not in word_set:
        return 0
    queue = deque([(begin_word, 1)])     # (当前词, 步数)
    visited = {begin_word}
    while queue:
        word, step = queue.popleft()
        if word == end_word:
            return step
        for i in range(len(word)):       # 枚举所有"差一个字母"的候选词
            for c in 'abcdefghijklmnopqrstuvwxyz':
                next_word = word[:i] + c + word[i+1:]
                if next_word in word_set and next_word not in visited:
                    visited.add(next_word)
                    queue.append((next_word, step + 1))
    return 0
```

**复杂度**：$O(N \cdot L \cdot 26)$，$N$ 是字典大小，$L$ 是单词长度。比"两两比较建图 + BFS"的 $O(N^2 L)$ 快很多——后者在 $N$ 大时退化严重。

**为什么 BFS 是首选**：题目要"最短变换序列"，每步变换权重相同，就是无权图最短路径。DFS 找的路径不一定最短，要找最短得穷举所有路径，复杂度爆炸。

**面试加分点**：①主动说"双向 BFS"能加速（从 beginWord 和 endWord 同时 BFS，相遇即停）②主动说"建图策略选枚举字符而不是两两比较"——这能展示对 $O(N \cdot L \cdot 26)$ vs $O(N^2 L)$ 的复杂度权衡。

## 四、速查与自测

### 速查表：BFS vs DFS

| 维度 | BFS | DFS |
|---|---|---|
| 数据结构 | 队列（FIFO） | 栈（LIFO）/ 递归 |
| 访问顺序 | 圈层扩展（按距离递增） | 一路到底再回退 |
| 时间复杂度 | $O(V + E)$ | $O(V + E)$ |
| 空间复杂度 | $O(V)$（队列最宽） | $O(V)$（栈最深） |
| 最短路径（无权） | 直接支持 | 不直接 |
| 连通分量 | 支持 | 支持 |
| 拓扑排序 | 不支持 | 支持 |
| 环检测 | 支持（繁琐） | 支持（三色顺手） |
| 大图风险 | 不会栈溢出 | 递归版会栈溢出 |
| 适用问题 | 最少步数、最近距离、分层 | 连通性、拓扑、所有方案 |

**两种遍历的统一框架**：

```
访问起点（标记已访问）
while 容器非空：
    u = 容器.pop()
    for v in graph[u]:
        if v 未访问：
            标记 v 已访问
            容器.push(v)
```

容器是队列（FIFO）= BFS；容器是栈（LIFO）= DFS。一个数据结构的差别，决定了两种姿态。

### 自测三问

**问题一：** 为什么 BFS 求无权图最短路径时，"第一次到达目标"就是最短？请用 BFS 的访问顺序特性解释，并说明有权图为什么不灵。

**参考答案：** BFS 按距离递增顺序访问节点——先把所有距离为 1 的节点访问完，再访问距离为 2 的，依次类推。所以目标节点第一次被访问时，`dist[target]` 一定是最小边数。有权图不灵的原因是 BFS 假设"边数少 = 距离短"，但有权图里每条边权重不同——比如 A→B 边权 100，A→C→B 边权各 1，BFS 会选 A→B（1 条边）但实际最短是 A→C→B（2 条边，总权 2）。有权图要用 Dijkstra（非负权）或 Bellman-Ford（含负权），它们用优先队列按"累计权重"排序，而不是按"边数"排序。

**问题二：** 显式栈版 DFS 为什么要在"出栈时"判断 visited，而不是"入栈时"标记？请说明两种做法的差别。

**参考答案：** 如果显式栈版"入栈即标记"，会破坏 DFS 的访问顺序——因为栈是 LIFO，后入的先出，但入栈时已经标记，等于把访问顺序定死在入栈那一刻。结果是某些节点的访问顺序和递归版不一致。正确做法是"入栈时不标记，出栈时判断是否已访问"——如果已访问就跳过，否则处理。这样能严格复现递归版的访问顺序。配合 `reversed(graph[u])` 让邻居按原顺序入栈，弹出顺序就和递归版一致。这个细节看似多余，但在调试访问顺序敏感的算法（如拓扑排序）时很关键。

**问题三：** 什么时候选 BFS、什么时候选 DFS？请从"问题类型""图结构""工程约束"三个维度给出判断框架。

**参考答案：** ①问题类型：求"最少步数/最短路径/最近 X"用 BFS（无权图前提）；判连通/拓扑/环/找所有方案用 DFS。②图结构：宽而浅的图 BFS 队列宽但深度小，DFS 栈浅更省；窄而深的图 BFS 队列窄，DFS 栈深可能溢出——大图优先 BFS 或显式栈 DFS。③工程约束：递归深度受限（Python 默认 1000）的大图不能用递归 DFS，必须显式栈或 BFS；不能改原数据时不能像"岛屿数量"那样直接改 grid，要用 visited 集合。判断框架是：先看问题类型选算法，再看图规模选实现方式（递归 vs 显式栈 vs 库函数），最后看约束（内存、不改原数据）调整细节。

### 算法思想 × 生活迁移

BFS 和 DFS 的核心思想是"两种探索世界的姿态"——圈层扩展 vs 一路到底。这种姿态差异不止用于图遍历，在生活中也无处不在。

**迁移一：找工作是 BFS 还是 DFS。** BFS 式找工作：先广撒网投一批简历（圈层扩展），看哪些有回音，再从有回音的里面选；优点是信息全，能比较多个 offer，缺点是周期长。DFS 式找工作：看中一家就全力攻，被拒了再投下一家；优点是专注度高，缺点是错过其他机会。哪种好取决于你的偏好——信息敏感型选 BFS，专注型选 DFS。但要注意：BFS 的"广"有上限（精力有限），DFS 的"深"也有上限（时间有限），实际操作是两者混合——先用 BFS 粗筛目标公司，再用 DFS 深攻少数几家。

**迁移二：学习新技术是 BFS 还是 DFS。** BFS 式学习：先把某个领域（如机器学习）的所有相关概念（监督/无监督/强化/深度/迁移）都浏览一遍，知道全貌，再挑感兴趣的方向深入。优点是视野广，缺点是每个方向都浅。DFS 式学习：选定一个方向（如深度学习）一路学到 Transformer、Attention、BERT、GPT，再回头看其他方向。优点是深度够，缺点是可能错过更适合的方向。技术快速变化时建议 BFS（先广撒网避免押错赛道），技术稳定时建议 DFS（深耕一个方向建立壁垒）。

**迁移三：旅行规划是 BFS 还是 DFS。** BFS 式旅行：到一个城市，把周边景点都逛一遍再换城市——像绕着一个中心画圈。优点是不用长途奔波，缺点是每个景点停留短。DFS 式旅行：选一个景点深玩几天，再去下一个——像沿着一条线深入。优点是体验深，缺点是交通成本高。短假建议 BFS（一个城市周边），长假建议 DFS（深入一个地区）。

**为什么这些迁移成立：** BFS 和 DFS 是"探索策略"的两个极端——"广度优先"用更宽的视野换更浅的深度，"深度优先"用更深的专注换更窄的视野。任何需要"在广度和深度之间权衡"的探索任务，都可以套用这个框架。关键是认清自己当前的约束（时间、精力、信息）和目标（视野 vs 深度），选合适的姿态。多数情况下不是二选一，而是 BFS 粗筛 + DFS 精攻的混合策略——这也是为什么很多算法题用 BFS 找候选解、DFS 精确求解。

## 参考来源

- [1] Cormen, T. H. et al. *Introduction to Algorithms*. MIT Press, 4th ed., 2022. 第 22 章（图遍历 BFS/DFS 的标准定义、复杂度证明、拓扑排序、连通分量）
- [2] Sedgewick, R. & Wayne, K. *Algorithms*. Addison-Wesley, 4th ed., 2011. 第 4 章（图的遍历实现、应用案例）
- [3] 邓俊辉. 数据结构（C++语言版）. 清华大学出版社, 第 3 版, 2013.（图遍历的国内教学参考）
- [29] Abdul Bari. *Graph Algorithms* 系列. [YouTube 播放列表](https://www.youtube.com/playlist?list=PLDN4rrl48XKuZtkRfYK2pSnHkdV2ZyAji).（BFS/DFS 的视频讲解，含拓扑排序、环检测推导）
- [30] William Fiset. *Graph Algorithms* 系列. [github.com/williamfiset/Algorithms](https://github.com/williamfiset/Algorithms).（BFS/DFS 的多语言实现，含对数器风格验证）
- [7-补充] krahets. *Hello 算法*. [hello-algo.com/chapter_graph/graph_traversal](https://www.hello-algo.com/chapter_graph/graph_traversal/).（图遍历的图示与多语言代码）
- [17] TheAlgorithms/Python. [github.com/TheAlgorithms/Python](https://github.com/TheAlgorithms/Python).（BFS/DFS 可运行实现对照）
- [23] 左程云. 程序员代码面试指南. 电子工业出版社.（"对数器"验证方法、"按数据状况选算法"的工程视角，本文对数器与"工程取舍"参考此框架）
- LeetCode 200/133/127 题目来源：[leetcode.com](https://leetcode.com/)（岛屿数量、克隆图、单词接龙三道面试高频题）
- 用户信源：`book-sources/面试现场/技术表达（表达方法+面试官视角）.md`（"技术的水有多深"八层面表达框架，本文"面试怎么讲"参考此框架）
