---
title: 算法课·20｜树：从二叉树到 B 树，分层思维的进化
book: 数据结构与算法
chapter: 树
event: 从二叉树到B树
sort: 1
chapter_sort: 10
created_at: 2026-06-29
source_agents:
- algorithm-expert
---
# 算法课·20｜树：从二叉树到 B 树，分层思维的进化

> 前置知识：学完链表章节，理解 $O(n)$ 查找的痛点；具备递归基础（能看懂函数自调用）
> 学完你能：①给小白讲清树为什么能把 $O(n)$ 查找压到 $O(\log n)$ ②默写 BST 的插入/删除/查找并讲透每一行 ③手撕四种遍历（前序/中序/后序/层序，递归 + 迭代两套写法）④讲清 AVL 四种旋转的触发条件 ⑤说清红黑树五大性质与工程意义（不手撕）⑥理解 B/B+ 树为什么是磁盘 IO 的产物

## 一、问题与思路：链表的痛点与树的分层破局

### 1. 一个生活场景：查字典的两种方式

假设你要在一本 1000 页的字典里查一个词。

**方式一（链表式）**：从第 1 页逐页翻到第 1000 页，最坏翻 1000 次。这就是链表查找——元素一个挨一个，找第 k 个就得走过前 k-1 个。

**方式二（树式）**：从中间翻开，看目标词在左半还是右半；翻到那一半的中间，再砍一半……每次砍掉一半，$\log_2(1000) \approx 10$ 次就找到。

**这就是树的核心思想：把"逐个比较"升级为"每次砍一半"。** 链表是一维线性结构，查找只能沿一个方向走；树是分层结构，每一层把搜索空间二分，所以高度是 $\log n$ 而不是 $n$。

### 2. 链表的痛点，树怎么破

**痛点：链表查找 $O(n)$。** 链表每个节点只记"下一个"，要找某个值只能从头顺藤摸瓜。100 万个元素的链表，找一个值最坏比 100 万次。

**树的破局：给节点加"两个出口"。** 二叉树每个节点有左右两个孩子，相当于在每个岔路口二选一。如果岔路口的安排满足"左小右大"（这就是 BST），那么每次比较都能砍掉一半候选——这就是 $O(\log n)$ 的来源。

**核心论点**：树是二分思想的数据结构化。二分查找（数组版）要求连续内存、不能动态增删；树把"每次砍一半"固化到节点间的指针关系里，于是既能 $O(\log n)$ 查找，又能 $O(\log n)$ 增删。代价是每个节点多存指针、且需要保持"有序"结构。

### 3. 反直觉点：树比链表"多此一举"，为什么反而更快

链表插入删除是 $O(1)$，看着比树的 $O(\log n)$ 快。但前提是"你已经知道插在哪"。一旦涉及"先找到位置再插"，链表就退化成 $O(n)$（查找）+ $O(1)$（插）= $O(n)$；而树是 $O(\log n)$（查找）+ $O(1)$（插）= $O(\log n)$。

这就是树的立足点：**它把"查找"这个高频操作的代价从 $O(n)$ 压到 $O(\log n)$，付出的代价是插入/删除从 $O(1)$ 涨到 $O(\log n)$**。对"读多写少"的场景（数据库索引、内存目录），这个交易非常划算。

### 4. 历史脉络：从二叉树到 B 树

- **二叉树（Binary Tree）**：最朴素的分层结构，每个节点最多两个孩子。1960 年代随递归理论成熟。
- **二叉搜索树（BST, Binary Search Tree）**：给二叉树加"左小右大"约束，支持 $O(\log n)$ 查找。但最坏退化为 $O(n)$（变成链表）。
- **AVL 树（1962，Adelson-Velsky & Landis）**：第一个自平衡 BST，靠旋转把高度控制在 $1.44 \log n$。
- **红黑树（1972，Bayer；1978，Guibas & Sedgewick 命名）**：工程上更实用的平衡树，C++ `std::map`、Java `TreeMap`、Linux 调度器都用它。
- **B 树 / B+ 树（1972，Bayer & McCreight）**：为磁盘 IO 设计的多路查找树，一个节点存多个关键字，降低树高，是数据库索引的事实标准。

这条演进线的驱动力是同一个问题：**如何让树在更多场景下保持 $O(\log n)$**——AVL/红黑解决"内存中动态数据"，B 树解决"磁盘上大数据"。

## 二、原理与实现：从二叉树到 BST 的代码与数学

### 1. 二叉树与 BST 的定义

**二叉树**：每个节点最多两个子节点（左孩子、右孩子）。形式化：要么为空，要么由一个根节点 + 左子树 + 右子树组成（递归定义）。

```python
class TreeNode:
    def __init__(self, val):
        self.val = val
        self.left = None    # 左孩子
        self.right = None   # 右孩子
```

**BST（二叉搜索树）**：在二叉树基础上加约束——对任意节点，左子树所有值 < 节点值 < 右子树所有值。这个约束让中序遍历得到有序序列，也让查找能"二分"。

### 2. BST 查找：逐行讲透

```python
def search(root, target):
    if root is None:                # 空树或走到叶子之外
        return None
    if target == root.val:          # 命中
        return root
    if target < root.val:           # 比当前小，去左子树
        return search(root.left, target)
    return search(root.right, target)   # 比当前大，去右子树
```

**逐行讲透**：

- **`if root is None`**：递归边界。走到空说明这条路上没找到。每往下一层，候选空间砍一半，所以高度 $h$ 决定比较次数。
- **`if target == root.val`**：命中返回。注意是"等于"才返回，小于/大于都继续往下。
- **`if target < root.val`**：目标比当前小，去左子树。因为 BST 左子树全小于根，目标若存在只能在左边。
- **`return search(root.right, target)`**：目标比当前大，去右子树。

**复杂度**：平衡时 $O(\log n)$（每次砍一半）；最坏 $O(n)$（树退化成链表，比如按顺序插入 1,2,3,...,n）。这就是后面 AVL/红黑树要解决的问题。

### 3. BST 插入：逐行讲透

```python
def insert(root, val):
    if root is None:                # 走到空位，新建节点放这
        return TreeNode(val)
    if val < root.val:              # 比当前小，往左插
        root.left = insert(root.left, val)
    elif val > root.val:            # 比当前大，往右插
        root.right = insert(root.right, val)
    # val == root.val 时不插（去重），或按需放右子树
    return root                     # 返回（可能更新的）子树根
```

**逐行讲透**：

- **`if root is None`**：递归到空位，说明这就是新节点该待的地方，`return TreeNode(val)` 把新节点接回去。
- **`root.left = insert(root.left, val)`**：关键——递归往左插，并用返回值更新 `root.left`。为什么能这么写？因为 `insert` 返回的是"插入后这棵子树的根"，子树根通常不变（除非是空树新建），所以重新赋值是安全的，也是接驳新节点的机制。
- **`elif val > root.val`**：往右插，同理。
- **`val == root.val` 不处理**：BST 通常不允许重复值。若要允许，约定重复值放右子树（或左子树），需在查找/删除时一致处理。
- **`return root`**：把当前（可能更新了孩子的）节点返回给上一层，让上一层接驳。

**走个例子**：往空树依次插入 `[5, 3, 7, 2, 4]`：

```
插 5:        5
插 3:        5
            /
           3
插 7:        5
            / \
           3   7
插 2:        5
            / \
           3   7
          /
         2
插 4:        5
            / \
           3   7
          / \
         2   4
```

每次插入从根开始比较，往下走到空位挂上。平衡时走 $\log n$ 层，最坏走 $n$ 层（退化链表）。

### 4. BST 删除：逐行讲透（最难的点）

删除之所以难，在于删掉节点后要保住 BST 性质。分三种情况：

```python
def delete(root, val):
    if root is None:
        return None
    if val < root.val:
        root.left = delete(root.left, val)
    elif val > root.val:
        root.right = delete(root.right, val)
    else:                           # 找到要删的节点
        # 情况1/2：只有一边孩子或没有孩子
        if root.left is None:
            return root.right       # 用右孩子顶上来（右孩子可能为 None）
        if root.right is None:
            return root.left        # 用左孩子顶上来
        # 情况3：左右孩子都有
        succ = root.right
        while succ.left:            # 找右子树最小值（后继 successor）
            succ = succ.left
        root.val = succ.val         # 用后继值覆盖当前
        root.right = delete(root.right, succ.val)   # 删掉原后继
    return root
```

**逐行讲透**：

- **前半段查找**：和插入一样，递归定位要删的节点。
- **`if root.left is None: return root.right`**：情况 1（叶子，两边都空）和情况 2（只有右孩子）合并处理——左空就把右孩子顶上来。右孩子为 None 时正好处理叶子。
- **`if root.right is None: return root.left`**：只有左孩子，左孩子顶上来。
- **情况 3（两边都有）**：不能直接删，否则两棵子树断开。做法是用"后继"（右子树最小值）覆盖当前节点的值，再删掉原后继节点。后继一定在右子树最左下，最多只有一个右孩子，所以删它退化成情况 1/2。
- **`root.val = succ.val`**：值替换。注意是替换值，不是替换节点指针——这样不用动左右子树指针。
- **`root.right = delete(root.right, succ.val)`**：去右子树删掉那个后继（它的值已经被搬上来了）。

**为什么用后继而不用前驱（predecessor，左子树最大值）**？都行。后继或前驱都能保住 BST 性质。选后继是常见约定。

### 5. 四种遍历：递归 + 迭代两套写法

遍历是树的高频操作，面试必考。四种遍历的区别在于"根"的访问时机：

| 遍历 | 根的位置 | 顺序（对 `5(3,7)` 这棵树） | 典型用途 |
|---|---|---|---|
| 前序 | 根-左-右 | 5 3 7 | 拷贝树、序列化 |
| 中序 | 左-根-右 | 3 5 7 | BST 得有序序列 |
| 后序 | 左-右-根 | 3 7 5 | 释放树、计算子树信息 |
| 层序 | 按层从左到右 | 5 3 7 | BFS、最短距离 |

**递归写法（前/中/后只差一行顺序）**：

```python
def preorder(root):       # 前序
    if not root: return
    print(root.val)              # 根
    preorder(root.left)          # 左
    preorder(root.right)         # 右

def inorder(root):        # 中序
    if not root: return
    inorder(root.left)           # 左
    print(root.val)              # 根
    inorder(root.right)          # 右

def postorder(root):      # 后序
    if not root: return
    postorder(root.left)         # 左
    postorder(root.right)        # 右
    print(root.val)              # 根
```

递归版好写，但面试官常追"不用递归写一遍"——考你对栈的理解。

**迭代写法（用显式栈模拟递归）**：

```python
def preorder_iter(root):       # 前序迭代
    if not root: return []
    stack, res = [root], []
    while stack:
        node = stack.pop()
        res.append(node.val)
        if node.right: stack.append(node.right)   # 右先入栈，左后入栈，这样左先出
        if node.left: stack.append(node.left)
    return res

def inorder_iter(root):        # 中序迭代：一路向左压栈
    stack, res, cur = [], [], root
    while cur or stack:
        while cur:              # 左链全部压栈
            stack.append(cur)
            cur = cur.left
        cur = stack.pop()       # 弹出最左
        res.append(cur.val)     # 访问根
        cur = cur.right         # 转右子树
    return res
```

**层序遍历（用队列，BFS）**：

```python
from collections import deque
def levelorder(root):
    if not root: return []
    q, res = deque([root]), []
    while q:
        node = q.popleft()
        res.append(node.val)
        if node.left: q.append(node.left)
        if node.right: q.append(node.right)
    return res
```

**逐行讲透（中序迭代）**：

- **`while cur: stack.append(cur); cur = cur.left`**：一路向左把左链全压栈。为什么？中序是"左-根-右"，要访问根必须先访问完左子树，所以先把左链压着。
- **`cur = stack.pop()`**：弹出栈顶（当前最左未访问节点），访问它。
- **`cur = cur.right`**：访问完根，转向右子树。右子树若有左链，下一轮外层 while 又会把它压栈；若为空，下一轮直接弹栈顶（回溯到上一层根）。

**关键观察**：前序/中序/后序的迭代写法中，前序最容易（根先访问，孩子入栈即可），中序要"左链压栈"技巧，后序最难（要用"根-右-左"反序或双栈）。层序则完全不同，用队列（FIFO）而非栈（LIFO）。

### 6. 复杂度：为什么是 O(log n)，最坏为什么退化

BST 各操作复杂度 = 树高 $h$。平衡时 $h = \log n$，最坏 $h = n$。

**为什么平衡是 $\log n$**：平衡二叉树每层节点数翻倍（第 0 层 1 个，第 1 层 2 个，...），$n$ 个节点的高度 $\approx \log_2 n$。查找沿一条路径走，最多走 $h$ 步。

**为什么最坏退化成 $O(n)$**：按顺序插入 `1,2,3,...,n`，每个都比根大，全往右走，树变成一条右链，高度 $n$。这就是 BST 的致命缺陷——**性能依赖数据，恶意输入能让它退化成链表**。

这正是 AVL 和红黑树存在的理由：通过旋转强制保持平衡，把最坏也压到 $O(\log n)$。

### 7. 五指标评价（普通 BST）

| 指标 | BST（普通） | 说明 |
|---|---|---|
| 查找 | 平均 $O(\log n)$，最坏 $O(n)$ | 依赖树形 |
| 插入 | 同上 | 同上 |
| 删除 | 同上 | 同上 |
| 空间 | $O(n)$ | 存节点 + 指针 |
| 平衡性 | 否 | 退化为链表 |

### 8. 高手向：AVL 树的四种旋转

AVL 树（Adelson-Velsky & Landis, 1962）是第一个自平衡 BST。它给每个节点记"平衡因子（balance factor，左子树高 - 右子树高）"，一旦某节点平衡因子绝对值超过 1，就旋转修复。

失衡分四种，对应四种旋转：

| 失衡类型 | 触发场景 | 修复 |
|---|---|---|
| LL | 在左孩子的左子树插入 | 右旋（一次） |
| RR | 在右孩子的右子树插入 | 左旋（一次） |
| LR | 在左孩子的右子树插入 | 先左旋左孩子，再右旋根（两次） |
| RL | 在右孩子的左子树插入 | 先右旋右孩子，再左旋根（两次） |

**右旋示意（LL 修复）**：

```
      y                x
     / \              / \
    x   T3   -->    T1   y
   / \                  / \
  T1  T2              T2  T3
```

y 失衡（左子树高太多），把左孩子 x 提上来当新根，y 降为 x 的右孩子，x 原来的右子树 T2 接到 y 的左边。旋转后仍是 BST（中序不变：T1 < x < T2 < y < T3）。

**判断哪种失衡**：从插入点往上找第一个失衡节点 z，看插入点在 z 的哪边、又在 z 那边孩子的哪边——两次方向决定 LL/RR/LR/RL。

AVL 严格平衡（高度差 ≤1），查找极快，但插入/删除可能要多次旋转，写操作多时不如红黑树。所以 AVL 适合"读多写少"，红黑树适合"读写均衡"。

### 9. 高手向：红黑树五大性质与工程意义

红黑树不追求严格平衡，只保证"大致平衡"——任何路径长度不超过另一条的 2 倍。这让它旋转次数少（插入最多 2 次旋转、删除最多 3 次），写性能比 AVL 稳。

**五大性质**：

1. 每个节点是红色或黑色。
2. 根节点是黑色。
3. 每个叶子（NIL 空节点）是黑色。
4. 红色节点的孩子必须是黑色（即不能有连续两个红节点）。
5. 从任一节点到其所有叶子节点的路径，包含相同数目的黑色节点（黑高相同）。

**为什么不手撕**：红黑树的插入/删除涉及染色 + 旋转 + 叔叔节点判断，情况繁多（插入 3 种情况循环、删除 4 种情况循环），手撕极易出错，面试也几乎不要求默写。但要能讲清五大性质和"为什么大致平衡就够 $O(\log n)$"。

**为什么五大性质保证 $O(\log n)$**：性质 4+5 共同约束——最长路径（红黑相间）不超过最短路径（全黑）的 2 倍，所以树高 $\leq 2\log(n+1)$，查找 $O(\log n)$。

**工程意义**：红黑树是工程界最常用的平衡树——C++ `std::map`/`std::set`、Java `TreeMap`/`HashMap`（链表长度超 8 转红黑树）、Linux 内核 CFS 调度器、Nginx timer 都用它。原因就是"写性能稳定 + 实现比 AVL 更适合工程"。

### 10. 高手向：B 树 / B+ 树——磁盘 IO 的产物

前面 AVL/红黑都是二叉，每个节点最多 2 个孩子。但数据库索引动辄上亿条记录，二叉树高度 $\log_2(10^8) \approx 27$，意味着找一条记录要 27 次节点访问。如果每次节点访问都是一次磁盘 IO（毫秒级），27 次就是几十毫秒，太慢。

**B 树的破局：让一个节点存多个关键字，降低树高。** 一个 m 阶 B 树每个节点最多 m-1 个关键字、m 个孩子。比如 1000 阶 B 树，3 层就能存 $1000^3 = 10^9$ 条记录——3 次 IO 找到任意记录。

**B 树性质（m 阶）**：

- 每个节点最多 m 个孩子、m-1 个关键字。
- 根节点至少 2 个孩子（除非是叶）。
- 非根非叶节点至少 $\lceil m/2 \rceil$ 个孩子。
- 所有叶子在同一层（绝对平衡）。
- 节点内关键字有序，关键字之间的孩子指针划分子区间。

**B+ 树（B 树变种，数据库索引主力）**：

- 非叶节点只存关键字（索引），数据全在叶子。
- 叶子之间用链表串起来（范围查询友好）。
- MySQL InnoDB、PostgreSQL、MongoDB 索引都是 B+ 树。

**为什么 B/B+ 树适合磁盘**：磁盘按"块"读取（典型 4KB-16KB），一次 IO 读一块。B 树把一个节点设计成一个块大小，一次 IO 读入一个节点（含多个关键字），在内存里二分查找定位孩子指针，再 IO 读下一层。这样树高 = IO 次数，3-4 层就能覆盖亿级数据。这是"算法结构匹配硬件特性"的典范——树高不是目的，IO 次数才是。

## 三、实践与面试：手撕结构、对数器、面试题

### 1. 手撕结构：BST 实现 + 四种遍历

面试中"手撕树"的标准要求：能默写 BST 的插入/删除/查找，外加四种遍历。下面是完整模板：

```python
class TreeNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, val):
        self.root = self._insert(self.root, val)

    def _insert(self, root, val):
        if root is None:
            return TreeNode(val)
        if val < root.val:
            root.left = self._insert(root.left, val)
        elif val > root.val:
            root.right = self._insert(root.right, val)
        return root

    def search(self, val):
        return self._search(self.root, val)

    def _search(self, root, val):
        if root is None or root.val == val:
            return root
        if val < root.val:
            return self._search(root.left, val)
        return self._search(root.right, val)

    def delete(self, val):
        self.root = self._delete(self.root, val)

    def _delete(self, root, val):
        if root is None:
            return None
        if val < root.val:
            root.left = self._delete(root.left, val)
        elif val > root.val:
            root.right = self._delete(root.right, val)
        else:
            if root.left is None:
                return root.right
            if root.right is None:
                return root.left
            succ = root.right
            while succ.left:
                succ = succ.left
            root.val = succ.val
            root.right = self._delete(root.right, succ.val)
        return root

# 四种遍历（递归版）
def preorder(root):
    if not root: return []
    return [root.val] + preorder(root.left) + preorder(root.right)

def inorder(root):
    if not root: return []
    return inorder(root.left) + [root.val] + inorder(root.right)

def postorder(root):
    if not root: return []
    return postorder(root.left) + postorder(root.right) + [root.val]

from collections import deque
def levelorder(root):
    if not root: return []
    q, res = deque([root]), []
    while q:
        node = q.popleft()
        res.append(node.val)
        if node.left: q.append(node.left)
        if node.right: q.append(node.right)
    return res
```

**面试时怎么讲**（按"技术的水有多深"八层面，挑重点讲）：

1. **问题层**：链表查找 $O(n)$，树靠分层把每次比较砍一半，压到 $O(\log n)$。
2. **原理层**：BST 加"左小右大"约束，查找/插入/删除都沿一条路径走，复杂度 = 树高。
3. **优劣层**：平均 $O(\log n)$，最坏退化 $O(n)$（顺序插入）；要靠 AVL/红黑保平衡。
4. **演进层**：BST → AVL（严格平衡）→ 红黑（大致平衡，工程主力）→ B/B+ 树（磁盘适配）。

**面试加分点**：主动提"普通 BST 会退化，工程上用红黑树/跳表替代"，并说出红黑树五大性质里的任意两条——这能立刻区分你和"只会背模板"的候选人。

### 2. 对数器：随机数据验证 BST 性质

写完 BST 别靠肉眼检查，用对数器验证三件事：①插入后中序有序 ②删除后仍是 BST ③查找正确。左神反复强调对数器是基本功。

```python
import random

def is_bst(root, lo=float('-inf'), hi=float('inf')):
    """验证 root 是否为合法 BST：左子树 < 根 < 右子树。"""
    if not root:
        return True
    if not (lo < root.val < hi):
        return False
    return is_bst(root.left, lo, root.val) and is_bst(root.right, root.val, hi)

def checker(test_times=2000, max_n=100, max_val=1000):
    for _ in range(test_times):
        bst = BST()
        vals = [random.randint(0, max_val) for _ in range(random.randint(0, max_n))]
        for v in vals:
            bst.insert(v)
        if not is_bst(bst.root):
            print(f"插入后非 BST！输入: {vals}")
            return False
        # 删一半，再验证仍是 BST
        to_delete = random.sample(vals, len(vals) // 2)
        for v in to_delete:
            bst.delete(v)
        if not is_bst(bst.root):
            print(f"删除后非 BST！")
            return False
        # 验证查找：未删的唯一值应能找到
        for v in set(vals) - set(to_delete):
            if bst.search(v) is None:
                print(f"查找失败：{v} 应在树中却找不到")
                return False
    print("BST 对数器验证通过！")
    return True

checker()
```

**对数器的价值**：随机长度含 0 和 1，随机值含重复——覆盖手写易漏的边界。删一半再验证，能抓出"删除破坏 BST 性质"的隐蔽 bug。比手动构造用例全面得多。

**注意**：`is_bst` 函数本身也是下面面试题一"验证 BST"的标准解法——对数器和面试题在这里合流。

### 3. 面试高频题

**题一：验证 BST（LeetCode 98）**

判断一棵二叉树是不是合法 BST。陷阱：只比"左孩子 < 根 < 右孩子"不够——要保证整个左子树都小于根，不只是直接左孩子。

```python
def is_valid_bst(root, lo=float('-inf'), hi=float('inf')):
    if not root:
        return True
    if not (lo < root.val < hi):
        return False
    return is_valid_bst(root.left, lo, root.val) and is_valid_bst(root.right, root.val, hi)
```

**关键**：传上下界 `(lo, hi)`，每个节点必须在 `(lo, hi)` 内。错误写法是只比 `root.left.val < root.val`，会放过"右子树里有比根小的"这种整体性违规。

**题二：最近公共祖先 LCA（LeetCode 236）**

找两个节点 p、q 的最近公共祖先（Lowest Common Ancestor）。

```python
def lowest_common_ancestor(root, p, q):
    if root is None or root == p or root == q:
        return root
    left = lowest_common_ancestor(root.left, p, q)
    right = lowest_common_ancestor(root.right, p, q)
    if left and right:        # p、q 分布在两侧，当前就是 LCA
        return root
    return left if left else right   # 都在一侧，往那边找
```

**思路**：后序遍历——先在左右子树里找 p、q。若 p、q 分别在左右子树，当前节点就是 LCA；若都在同侧，LCA 在那侧。这是树形 DP 的雏形：子问题结果向上汇聚。

**题三：二叉树最大路径和（LeetCode 124）**

任意两节点路径的最大权和。难点：路径可以"拐弯"经过某节点。

```python
def max_path_sum(root):
    ans = float('-inf')
    def gain(node):
        nonlocal ans
        if not node: return 0
        left = max(gain(node.left), 0)    # 负贡献不要
        right = max(gain(node.right), 0)
        ans = max(ans, node.val + left + right)   # 经过当前节点的路径
        return node.val + max(left, right)         # 只能选一侧向上贡献
    gain(root)
    return ans
```

**关键区分**：`gain` 返回的是"以 node 为端点向上能贡献的最大值"（只能选一侧），而 `ans` 记录的是"以 node 为最高点的路径和"（可以两侧都走）。这个"返回值 vs 全局答案"的分离是树形 DP 的通用模式。

### 4. 教科书做法 vs 生产做法

| 场景 | 教科书 | 生产 | 原因 |
|---|---|---|---|
| 内存中动态有序表 | 手撕 BST | C++ `std::map`/Java `TreeMap`（红黑树） | 手撕 BST 退化风险，红黑树保平衡 |
| 数据库索引 | 手撕 B+ 树 | InnoDB/PostgreSQL 内置索引 | 引擎已优化页大小、缓冲池 |
| 有序集合 + 范围查询 | BST | 跳表（Redis `zset`） | 跳表实现更简、并发友好 |

**生产里几乎不手撕 BST**，因为普通 BST 有退化风险。要平衡就上红黑树/跳表，标准库都有。但面试要手撕，因为它是理解红黑树、B 树的基础。

### 5. 真实工程坑

**坑一：用普通 BST 存顺序数据，退化成链表。**

```python
bst = BST()
for i in range(10000):   # 顺序插入
    bst.insert(i)
# 树变成右链，查找从 O(log n) 退化到 O(n)
```

症状：查找变慢。根因：普通 BST 不自平衡，顺序输入退化。修复：用红黑树（`sortedcontainers.SortedDict`）或 AVL。

**坑二：递归遍历大树导致栈溢出。**

```python
def inorder(root):           # 递归
    ...
# 树高 10000 时，Python 递归深度超限（默认 1000）
```

症状：`RecursionError`。根因：递归深度 = 树高，退化链表时深度 = n。修复：①用迭代版（显式栈）②`sys.setrecursionlimit` 抬高上限（治标）③用平衡树避免退化（治本）。

**坑三：以为 BST 中序遍历一定有序，忽略重复值处理。**

如果插入时重复值放右子树，中序遍历会出现重复；若约定去重，查找时要一致。不一致会导致"插入成功但查不到"的诡异 bug。

## 四、速查与自测

### 速查表：树家族复杂度对比

| 结构 | 查找 | 插入 | 删除 | 平衡性 | 典型用途 |
|---|---|---|---|---|---|
| 二叉树（无序） | $O(n)$ | $O(n)$ | $O(n)$ | 否 | 教学仅 |
| BST | 平均 $O(\log n)$，最坏 $O(n)$ | 同 | 同 | 否 | 教学仅 |
| AVL | $O(\log n)$ | $O(\log n)$ | $O(\log n)$ | 严格 | 读多写少 |
| 红黑树 | $O(\log n)$ | $O(\log n)$ | $O(\log n)$ | 大致 | 工程主力 |
| B 树 | $O(\log_m n)$ | 同 | 同 | 绝对 | 磁盘索引 |
| B+ 树 | $O(\log_m n)$ | 同 | 同 | 绝对 | 数据库索引 |

**四种遍历速记**：

| 遍历 | 顺序 | 数据结构 | BST 中序结果 |
|---|---|---|---|
| 前序 | 根-左-右 | 栈 | — |
| 中序 | 左-根-右 | 栈 | 有序 |
| 后序 | 左-右-根 | 栈 | — |
| 层序 | 逐层 | 队列 | — |

### 自测三问

**问题一：** 树为什么能把查找从 $O(n)$ 压到 $O(\log n)$？请用"分层二分"解释，并指出代价。

**参考答案：** 链表是一维线性，查找只能沿一个方向走 $n$ 步。二叉树每个节点有左右两个分支，BST 加"左小右大"约束后，每次比较砍掉一半候选，所以高度是 $\log n$。代价是每个节点要多存左右指针（空间），且插入/删除从 $O(1)$ 涨到 $O(\log n)$（要先查找定位）。对读多写少场景（数据库索引）这个交易划算。

**问题二：** BST 删除有三种情况，最复杂的是哪种？怎么处理？

**参考答案：** 最复杂的是"被删节点有两个孩子"。不能直接删（两棵子树会断开），做法是用后继（右子树最小值）覆盖被删节点的值，再去右子树删掉那个后继。后继一定在右子树最左下，最多只有一个右孩子，所以删它退化成"无孩子或单孩子"的简单情况。也可以用前驱（左子树最大值），效果对称。

**问题三：** 红黑树和 AVL 树都自平衡，工程上为什么红黑树更常用？

**参考答案：** AVL 严格平衡（高度差 ≤1），查找极快但插入/删除可能多次旋转（最坏 $O(\log n)$ 次旋转），写多时旋转开销大。红黑树只保证"大致平衡"（最长路径 ≤ 最短路径 2 倍），插入最多 2 次旋转、删除最多 3 次旋转，写性能稳定。工程场景多为读写均衡，红黑树写性能稳定 + 实现可控，被 C++ `std::map`、Java `TreeMap`、Linux CFS 选用。AVL 适合读极多写极少的场景。

### 算法思想 × 生活迁移

树的核心思想是"**分层决策，每次砍一半**"——把一个 $O(n)$ 的逐个判断，变成 $O(\log n)$ 的逐层二分。

**迁移一：猜数字游戏。** 想一个 1-100 的数，对方猜你只说"大了/小了"。从 50 开始猜，每次取中间，7 次以内必中。这就是 BST 查找——每次比较砍一半。如果从 1 开始逐个猜（链表式），最坏 100 次。

**迁移二：决策树与问诊。** 医生问诊不是"把所有病逐个排除"（$O(n)$），而是"先问发烧吗→再问咳嗽吗→再问具体症状"，每问一句把候选疾病砍一半。这就是树的分层决策——20 个问题能区分 $2^{20} \approx 100$ 万种情况。机器学习的决策树、二十问游戏都源于此。

**迁移三：组织架构与权限继承。** 公司组织架构是树——CEO 在根，往下部门、小组、个人。权限/信息沿树向下传递，查找某人的汇报路径只需从根走 $\log$ 层（假设每层分叉均衡）。如果组织是扁平链表（所有人平级），传达信息要逐个通知 $O(n)$。这就是为什么大型组织必然是树形——分层让管理成本 $O(\log n)$ 而非 $O(n)$。

**为什么这些迁移成立：** 树成立的条件是"决策可以分层，且每层能成倍缩减候选"。猜数字（每次砍一半）、问诊（每个症状砍一半疾病）、组织架构（每个层级分叉）都满足。若问题不能有效二分（比如候选间无序、无法比较），树就不适用——这也是为什么哈希表（靠哈希函数而非比较）在某些场景比树快。

## 参考来源

- [1] Cormen, T. H. et al. *Introduction to Algorithms*（CLRS）. MIT Press, 4th ed., 2022. 第 12 章（二叉搜索树）、第 13 章（红黑树）、第 18 章（B 树）.（BST 操作、红黑树性质、B 树定义的权威来源）
- [14] Bayer, R. & McCreight, E. *Organization and Maintenance of Large Ordered Indices*. Acta Informatica, 1972.（B 树原始论文，提出多路平衡查找树，数据库索引的理论基础）
- [3] 邓俊辉. 数据结构（C++语言版）. 清华大学出版社, 第 3 版, 2013. 第 7 章（二叉搜索树）、第 8 章（平衡二叉树）.（国内教学参考，AVL 旋转与红黑树的中文权威讲解）
- Adelson-Velsky, G. M. & Landis, E. M. *An Algorithm for the Organization of Information*. 1962.（AVL 树原始论文，第一个自平衡 BST）
- Guibas, L. & Sedgewick, R. *A Dichromatic Framework for Balanced Trees*. FOCS, 1978.（红黑树的命名与系统化形式化）
- [2] Sedgewick, R. & Wayne, K. *Algorithms*. Addison-Wesley, 4th ed., 2011. 第 3 章（平衡搜索树、B 树）.
- [7-补充] krahets. *Hello 算法*. [hello-algo.com/chapter_tree](https://www.hello-algo.com/chapter_tree/).（二叉树、BST、AVL 的图示与多语言代码）
- [17] TheAlgorithms/Python. [github.com/TheAlgorithms/Python](https://github.com/TheAlgorithms/Python).（BST、AVL、红黑树可运行实现对照）
- [23] 左程云. 程序员代码面试指南. 电子工业出版社.（对数器方法、LCA/最大路径和等树形 DP 题的讲解思路）
- 用户信源：`book-sources/面试现场/技术表达（表达方法+面试官视角）.md`（"技术的水有多深"八层面表达框架，本文"面试时怎么讲"参考此框架）
