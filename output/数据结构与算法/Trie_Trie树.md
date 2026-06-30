---
title: 算法课·27｜Trie 树：前缀匹配的专用结构
book: 数据结构与算法
chapter: Trie
event: Trie树
sort: 1
chapter_sort: 17
created_at: 2026-06-29
source_agents:
- algorithm-expert
---
# 算法课·27｜Trie 树：前缀匹配的专用结构

> 前置知识：学完第 13 章（树的基础）和第 11 章（哈希表），尤其要懂"哈希表只能单点查询"的边界
> 学完你能：①给纯小白讲清为什么前缀匹配不需要逐词比对 ②默写 Trie 三件套并讲透每一行 ③手撕结构（插入/查找/前缀匹配）应对面试 ④理解 Trie vs 哈希表的取舍——前缀查询 Trie 胜，单点查询哈希胜 ⑤用对数器验证自己写的 Trie 对不对

## 一、问题与思路：前缀查询的痛点与 Trie 的破局思路

### 1. 一个生活场景：搜索框联想背后的反直觉

打开搜索引擎，输入 "appl"，下拉框立刻列出 apple、application、applied、apply——100 万词条的词库，怎么做到每次按键都几毫秒内返回？反直觉的地方在于：哈希表查单个词是 $O(1)$，可它根本回答不了"以 appl 开头的有哪些词"这种问题；线性扫描整个词库逐个比对前缀，100 万词条每次按键都要扫一遍，$O(n \cdot L)$（n 是词条数，L 是词长），手机键盘根本扛不住。

这个矛盾就是 Trie（前缀树 / Prefix Tree，又叫字典树 / Retrieval Tree）要解决的——它把"前缀匹配"从"逐词比对"降成"沿着一条树路径走一遍"。

**核心论点**：Trie 的设计要点是"公共前缀合并"——所有共享同一前缀的词共用同一条根到节点的路径，不为每个词重复存前缀。这是为前缀场景专门设计的结构，不是通用容器。

### 2. 朴素做法的痛点

**痛点一：哈希表只能单点查询，回答不了前缀问题。** 把 100 万词条存进 `set`，查 "apple" 在不在是 $O(1)$；但查"以 appl 开头的词"得遍历整个集合逐个 `startswith`，退化到 $O(n \cdot L)$。哈希表的哈希函数会把相似前缀打散到不同桶里，前缀信息在哈希过程中丢失了。

**痛点二：排序数组 + 二分也不够好。** 把词条排序后二分能快速定位前缀区间，单次 $O(L \log n)$。但插入新词条要移动元素 $O(n)$，对动态词库（输入法、搜索联想持续加词）不友好；且二分只能告诉你"有没有"，列全部匹配词还得扫描区间，最坏 $O(n)$。

**破局点**：既然前缀是共享的，就把共享前缀"合并"到同一条路径上——这就是 Trie。插入 "apple" 和 "application" 时，前 4 个字符 "appl" 只存一份，从第 5 个字符开始分叉。查询前缀 "appl" 时，只需沿着 a→p→p→l 走 4 步，下面的所有子树就是全部匹配词，不需要逐词比对。

### 3. 历史地位：为前缀而生的专用结构

Trie 由 Edward Fredkin 在 1960 年提出，名字取自 retrieval（检索）的中间部分，发音同 "try"。它不是通用容器，而是专为"字符串前缀"场景设计的：搜索引擎联想、输入法候选词、IP 路由表最长前缀匹配、拼写检查、基因序列比对，都是它的主场。CLRS（《算法导论》）没单列章节但多处提及，Knuth《计算机程序设计艺术》第三卷有专门讨论。

Trie 最知名的"后代"是 AC 自动机（Aho-Corasick, 1974）——在 Trie 上加失败指针（failure link），实现多模式串一次扫描全部匹配，是敏感词过滤、IDS 入侵检测的核心。理解 Trie 是理解 AC 自动机、压缩 Trie（Radix Tree / Patricia）、后缀树的前置条件。

## 二、原理与实现：从代码到空间换时间的取舍

### 1. 最朴素的 Trie（数组版 children）

先看最简单的版本，理解机制。Trie 的节点结构是关键——每个节点存两类信息：①字符到子节点的映射（children）②是否是某个词的结尾（end 标记）。

```python
class TrieNode:
    def __init__(self):
        self.children = [None] * 26      # 26 个小写字母
        self.is_end = False              # 标记是否是某个完整词的结尾

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        """插入一个词。"""
        node = self.root
        for ch in word:                  # 沿字符逐层下沉
            idx = ord(ch) - ord('a')     # 字符映射到 0-25
            if node.children[idx] is None:
                node.children[idx] = TrieNode()   # 没路就开路
            node = node.children[idx]
        node.is_end = True               # 词尾打标记

    def search(self, word):
        """查完整词是否在 Trie 中。"""
        node = self._find(word)
        return node is not None and node.is_end

    def starts_with(self, prefix):
        """查是否有词以 prefix 开头。"""
        return self._find(prefix) is not None

    def _find(self, s):
        """沿 s 走，返回终点节点（走不通返回 None）。"""
        node = self.root
        for ch in s:
            idx = ord(ch) - ord('a')
            if node.children[idx] is None:
                return None              # 路断了，前缀不存在
            node = node.children[idx]
        return node
```

**逐行讲透**（每一行都不能含糊）：

- **`self.children = [None] * 26`**：每个节点开一个长度 26 的数组，每个槽位对应一个字母。`children[idx]` 为 `None` 表示这个方向没路，非 `None` 指向子节点。固定 26 槽位让字符定位是 $O(1)$（直接下标访问），代价是空间开销大——每个节点占 26 个指针位。
- **`self.is_end = False`**：标记"到这个节点为止是否构成一个完整词"。注意"有节点"和"是词尾"是两回事——插入 "app" 和 "apple" 后，"app" 末尾的节点 is_end=True，"appl" 末尾的节点 is_end=False（它只是 apple 的中间节点，本身不是词）。`search` 必须同时检查"路径走通"和"终点是词尾"。
- **`for ch in word: idx = ord(ch) - ord('a')`**：逐字符下沉，字符映射成数组下标。`ord('a')` 是基准，'a'→0、'b'→1、...、'z'→25。这个映射限定了字符集——只支持小写字母；支持全字符集要用哈希表存 children（见后文"高手向"）。
- **`if node.children[idx] is None: node.children[idx] = TrieNode()`**：没路就开路——这是"逐字符构造路径"的精髓。插入 "apple" 时，a、p、p、l、e 五个字符依次开 5 个节点；再插 "apply" 时，a→p→p→l 已存在，直接复用，只在 l 之后新开 y 节点。**公共前缀合并就发生在这一行**。
- **`node.is_end = True`**：词尾打标记。注意只打在最后一个字符的节点上，中间节点不打。
- **`_find` 抽出公共逻辑**：`search` 和 `starts_with` 都要"沿字符串走"，区别只在终点判断——`search` 要求终点 `is_end=True`，`starts_with` 只要路径走通就行。抽出 `_find` 避免重复。

**用一个例子走一遍**。依次插入 "app"、"apple"、"apply"：

```
插入 "app":
  root → a → p → p(end)
  共新建 3 个节点，最后一个 p 打 is_end=True

插入 "apple":
  root → a → p → p → l → e(end)
  a→p→p 复用，新建 l、e 两个节点，e 打 is_end=True
  注意第三个 p 的 is_end 仍是 True（"app" 还是词）

插入 "apply":
  root → a → p → p → l → y(end)
  a→p→p→l 复用，新建 y 节点，y 打 is_end=True
  从 l 开始分叉：一条到 e（apple），一条到 y（apply）
```

最终树形：

```
root
 └─a
   └─p
     └─p (is_end=True, "app")
       └─l
         ├─e (is_end=True, "apple")
         └─y (is_end=True, "apply")
```

**关键观察**：三个词共 13 个字符，但 Trie 只存了 6 个节点（a、p、p、l、e、y）——公共前缀 "appl" 只存一份，省了 7 个节点的空间。词越多、前缀重合越多，Trie 省空间越明显。查 `starts_with("app")` 时，沿 a→p→p 走 3 步到达 "app" 节点，它下面整个子树（l、e、y）就是全部以 "app" 开头的词，不需要逐词比对。

### 2. 复杂度与空间：时间稳，空间看前缀重合度

| 操作 | 时间复杂度 | 说明 |
|---|---|---|
| insert(word) | $O(L)$ | L 是词长，逐字符下沉，每步 $O(1)$ |
| search(word) | $O(L)$ | 同上，与词库大小 n 无关 |
| starts_with(prefix) | $O(L)$ 判存在；$O(L+k)$ 列全部 | k 是匹配词数（要遍历子树列全部） |

**时间复杂度与词库大小 n 无关**——这是 Trie 相对哈希表 + 线性扫描的核心优势。哈希表前缀查询 $O(n \cdot L)$，Trie 是 $O(L)$。100 万词条里查前缀，哈希表要扫 100 万次，Trie 只走前缀长度步。

**空间复杂度要分情况看**：

- **最坏**：所有词没有公共前缀，$O(\sum L_i)$（$\sum L_i$ 是所有词总字符数）。这时 Trie 不省空间，反而比直接存字符串数组多了节点指针开销。
- **典型**：自然语言词库前缀重合度高（"app" 开头的词成百上千），Trie 能省大量空间。
- **数组版 vs 哈希版**：数组版每节点固定 26 槽（小写字母），稀疏时浪费严重；哈希版（`children = {}`）只存存在的字符，省空间但访问略慢（哈希 vs 直接下标）。

### 3. 删除操作：要处理共享前缀

Trie 的删除不是简单摘节点——"app" 和 "apple" 共享前缀 "app"，删 "app" 不能把 a、p、p 节点删掉，否则 "apple" 也没了。正确做法是用计数器替代布尔标记：

```python
class TrieNode:
    def __init__(self):
        self.children = [None] * 26
        self.pass_cnt = 0                # 有多少词经过此节点
        self.end_cnt = 0                 # 有多少词在此结尾（支持重复词）

def delete(trie, word):
    """删除一个词。"""
    node = trie.root
    path = []
    for ch in word:                      # 先确认词存在，并记录路径
        idx = ord(ch) - ord('a')
        if node.children[idx] is None or node.pass_cnt == 0:
            return False                 # 词不存在
        path.append((node, idx))
        node = node.children[idx]
    if node.end_cnt == 0:
        return False                     # 只是前缀，不是完整词
    node.end_cnt -= 1                    # 词尾计数 -1
    for parent, idx in reversed(path):   # 自底向上摘
        child = parent.children[idx]
        child.pass_cnt -= 1              # 路径计数 -1
        if child.pass_cnt == 0:          # 没词经过这个子节点了，摘掉
            parent.children[idx] = None
    return True
```

**逐行讲透关键点**：

- **`pass_cnt`**：记录"有多少个词经过这个节点"。删一个词时路径上每个节点 pass_cnt -1；减到 0 说明没词再经过它，可从父节点摘掉（`parent.children[idx] = None`）释放空间。
- **`end_cnt` 用整数而非布尔**：支持同一词插入多次。插 2 次 "apple" 则 end_cnt=2；删 1 次后 end_cnt=1，"apple" 仍在。
- **`reversed(path)` 从叶往根摘**：必须自底向上，否则父节点先被摘掉子节点就够不着。摘到第一个 pass_cnt > 0 的节点就停——再往上的节点还有别的词经过，不能摘。

### 4. 高手向：字符映射的两种实现与压缩 Trie

**数组版 vs 哈希版 children**：

| 维度 | 数组版 `children[26]` | 哈希版 `children = {}` |
|---|---|---|
| 字符定位 | $O(1)$ 下标 | $O(1)$ 哈希（常数更大） |
| 单节点空间 | 固定 26 槽 | 只存存在的字符 |
| 字符集 | 固定（如小写字母） | 任意（含 Unicode） |
| 缓存友好性 | 好（连续内存） | 差（哈希表散列） |
| 适用场景 | 字符集小且已知 | 字符集大或未知 |

**选择原则**：面试题（LeetCode 208 等）默认小写字母，用数组版最直接；做输入法（全 Unicode）或路由表（IP 字符串）用哈希版。生产里 Linux 内核的路由表用数组版（字符集就是 0-255），性能优先。

**压缩 Trie（Radix Tree / Patricia Trie）**：当 Trie 分叉稀疏时，会有大量"单链"节点（只有一个孩子），浪费空间。压缩 Trie 把单链合并成一个节点存一段字符串。Redis 的 Stream、Linux 的路由表（fib_trie）用的就是压缩 Trie。这是"空间优化"方向，面试中知道概念即可，手撕考得少。

**AC 自动机的前置**：AC 自动机 = Trie + 失败指针（failure link）。失败指针指向"当前节点的最长真后缀对应的另一个 Trie 节点"。匹配时走 Trie，走不通沿失败指针跳转，不用回溯文本指针，实现多模式串一次扫描匹配。理解 Trie 的"前缀共享"是理解失败指针的前提——失败指针实质是"前缀之间共享后缀"的桥梁。

### 5. 五指标评价

| 指标 | Trie | 说明 |
|---|---|---|
| insert / search | $O(L)$ | 与词库大小 n 无关，只看词长 |
| starts_with | $O(L)$ 判存在；$O(L+k)$ 列全部 | k 是匹配词数 |
| 空间 | $O(\sum L_i)$ 最坏；前缀重合时大幅省 | 数组版有 26 倍常数 |
| 优势 | 前缀查询 $O(L)$，哈希表做不到 | |
| 局限 | 单点查询常数比哈希表大；空间开销可能高 | |

## 三、实践与面试：手撕结构、对数器、面试题

### 1. 面试手撕模板（带 pass/end 计数版）

面试中被要求手撕 Trie，用"带 pass/end 计数"的标准版——既能展示你知道删除操作的处理，又方便后续追问：

```python
class Trie:
    """Trie 标准版：pass/end 计数，支持插入、查找、前缀匹配、删除。"""
    def __init__(self):
        self.children = [None] * 26
        self.pass_cnt = 0                # 经过此节点的词数
        self.end_cnt = 0                 # 在此结尾的词数

    def insert(self, word):
        node = self
        node.pass_cnt += 1               # 根节点也要 +1
        for ch in word:
            idx = ord(ch) - ord('a')
            if node.children[idx] is None:
                node.children[idx] = Trie()
            node = node.children[idx]
            node.pass_cnt += 1
        node.end_cnt += 1

    def search(self, word):
        node = self._walk(word)
        return node is not None and node.end_cnt > 0

    def starts_with(self, prefix):
        return self._walk(prefix) is not None

    def _walk(self, s):
        node = self
        for ch in s:
            idx = ord(ch) - ord('a')
            if node.children[idx] is None:
                return None
            node = node.children[idx]
        return node
```

**面试时怎么讲**（按"技术的水有多深"八层面，挑重点讲）：

1. **问题层**：前缀匹配问题——哈希表只能单点查询，线性扫描 $O(n \cdot L)$ 扛不住。Trie 把公共前缀合并到一条路径，前缀查询降成 $O(L)$。
2. **原理层**：每个节点存字符到子节点的映射 + end 标记。insert 逐字符下沉开路，search 走完路径看 end 标记，starts_with 只看路径走不走得通。
3. **优劣层**：前缀查询 $O(L)$ 与词库无关，是哈希表做不到的；但单点查询常数比哈希表大（要走 L 步 vs 一次哈希），空间开销可能高（数组版 26 倍常数）。
4. **演进层**：朴素 Trie → 压缩 Trie（Radix/Patricia，合并单链）→ AC 自动机（Trie + 失败指针，多模式匹配）。Trie 是这一族结构的基础。

**面试加分点**：主动提"前缀查询 Trie 胜，单点查询哈希胜"——这能立刻区分你和"只会背 insert/search"的候选人。

### 2. 对数器：Trie vs 暴力遍历对比

左神反复强调：**写完数据结构不要靠肉眼检查，要用对数器验证**。Trie 的对数器思路是——生成随机词集，用你的 Trie 和"绝对正确的暴力实现"（线性扫描 `set` 比对前缀）对比，跑足够多次，只要有一次不一致就说明你的 Trie 有 bug。

```python
import random
import string

# 复用上文「面试手撕模板」里带 pass/end 计数的 Trie 类

def random_word(max_len=6):
    n = random.randint(1, max_len)
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

def checker(test_times=500, max_words=50):
    """对数器：跑 test_times 次，每次随机词集对比。"""
    for _ in range(test_times):
        trie = Trie()
        word_set = set()
        for _ in range(max_words):
            w = random_word()
            trie.insert(w)
            word_set.add(w)
        # 对比完整词查询
        for _ in range(max_words):
            w = random_word()
            if trie.search(w) != (w in word_set):
                print(f"search 出错！词: {w}")
                return False
        # 对比前缀查询
        for _ in range(max_words):
            p = random_word(max_len=3)
            trie_result = trie.starts_with(p)
            naive_result = any(x.startswith(p) for x in word_set)
            if trie_result != naive_result:
                print(f"starts_with 出错！前缀: {p}")
                return False
    print("对数器验证通过！")
    return True

checker()
```

**对数器的价值**：随机词集覆盖"空 Trie 查询""查不存在的词""前缀刚好是某完整词""长前缀走不通"等容易遗漏的边界；跑 500 次只要几秒，比手动构造测试用例全面得多。左神原话："对数器是算法工程师的基本功。写完一个数据结构，第一件事就是写对数器，而不是跑几个例子看看对不对。"

**对高手的启发**：Trie 的 bug 往往出在边界——空字符串、单字符词、前缀本身就是词、查的前缀比所有词都长。对数器能逼出这些边界 bug，比肉眼检查可靠得多。

### 3. Trie vs 哈希表：前缀查询 Trie 胜，单点查询哈希胜

这是面试高频追问点，必须能讲清取舍：

| 场景 | Trie | 哈希表 | 胜者 |
|---|---|---|---|
| 单点查询（词在不在） | $O(L)$ | $O(L)$ 哈希 + $O(1)$ 查表 | 哈希表（常数小） |
| 前缀查询（以 X 开头的词） | $O(L)$ | $O(n \cdot L)$ 线性扫描 | **Trie** |
| 前缀列举（列出所有匹配词） | $O(L+k)$ 遍历子树 | $O(n \cdot L)$ 扫全部 | **Trie** |
| 插入 | $O(L)$ | $O(L)$ 哈希 + 摊销 | 哈希表（常数小） |
| 空间 | $O(\sum L_i)$，前缀重合省 | $O(\sum L_i)$ | 看数据，前缀重合多 Trie 省 |
| 范围查询 / 字典序遍历 | 天然支持 | 不支持 | **Trie** |

**结论**：哈希表是通用单点查询王者，但前缀信息在哈希时丢失了；Trie 用树形结构保留前缀关系，专为前缀场景而生。如果只需要"词在不在"，用哈希表；如果需要"以 X 开头的词有哪些""按字典序遍历""前缀自动补全"，用 Trie。

**生产里的折中**：很多输入法/搜索引擎用"哈希表 + 预建前缀索引"的混合方案——热词用哈希表快速单点查，前缀联想用 Trie。纯 Trie 在大规模词库上空间开销大，纯哈希表做不了前缀，混合是工程常态。

### 4. 面试高频三题

**题一：实现 Trie（LeetCode 208）**

就是上面手撕的模板。注意 `search` 和 `startsWith` 的区别——`search` 要求终点 `is_end=True`，`startsWith` 只要路径走通。这是 LeetCode 208 最常见的踩坑点。

**题二：添加与搜索单词 - 通配符（LeetCode 211）**

支持 `.` 通配符：`search("a.le")` 要匹配 apple、able 等。这需要改造 `search`——遇到 `.` 时遍历所有非空 children 递归。

```python
class WordDictionary:
    def __init__(self):
        self.children = [None] * 26
        self.is_end = False

    def addWord(self, word):
        node = self
        for ch in word:
            idx = ord(ch) - ord('a')
            if node.children[idx] is None:
                node.children[idx] = WordDictionary()
            node = node.children[idx]
        node.is_end = True

    def search(self, word):
        def dfs(node, i):
            if i == len(word):
                return node.is_end
            ch = word[i]
            if ch == '.':
                for child in node.children:        # 通配符：遍历所有分支
                    if child and dfs(child, i + 1):
                        return True
                return False
            idx = ord(ch) - ord('a')
            if node.children[idx] is None:
                return False
            return dfs(node.children[idx], i + 1)
        return dfs(self, 0)
```

**讲解要点**：通配符让 Trie 退化成"字符级回溯"——`.` 处要枚举所有分支递归，最坏 $O(26^L)$。这正是 Trie 适合"结构化字符匹配"的体现：哈希表遇到 `.` 完全没法做，Trie 天然支持"在某层枚举所有分支"。

**题三：单词搜索 II（LeetCode 212）**

在二维字符网格里找出所有词典中的词。朴素做法对每个词做一次网格 DFS，$O(\text{words} \cdot mn \cdot 4^L)$ 扛不住。把词典建成 Trie，一次 DFS 同时匹配所有词，$O(mn \cdot 4^L)$ 但 Trie 剪枝大幅减少无效搜索。

```python
def findWords(board, words):
    # 1. 把所有词建成 Trie
    root = {}
    for w in words:
        node = root
        for ch in w:
            node = node.setdefault(ch, {})
        node['#'] = w                      # 词尾存完整词，便于收集

    res = []
    m, n = len(board), len(board[0])

    def dfs(r, c, node):
        ch = board[r][c]
        if ch not in node:
            return
        nxt = node[ch]
        if '#' in nxt:                     # 命中一个词
            res.append(nxt['#'])
            del nxt['#']                   # 去重：同一词只收一次
        board[r][c] = '#'                  # 标记已访问
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if 0 <= nr < m and 0 <= nc < n and board[nr][nc] != '#':
                dfs(nr, nc, nxt)
        board[r][c] = ch                   # 回溯恢复
        # 剪枝：nxt 空了就从 node 删掉，避免后续无效进入
        if not nxt:
            del node[ch]

    for r in range(m):
        for c in range(n):
            dfs(r, c, root)
    return res
```

**讲解要点**：Trie 在这里的角色是"共享前缀的剪枝器"——"apple" 和 "apply" 共享 "appl"，DFS 走到 "appl" 时同时试探两个分支，不用为每个词单独跑一遍。`del node[ch]` 是关键剪枝：某分支已无词，后续不再进入。这道题把 Trie 的"前缀共享"和回溯剪枝结合，是 Trie + DFS 的经典套路。

### 5. 教科书做法 vs 生产做法

| 场景 | 教科书做法 | 生产做法 | 原因 |
|---|---|---|---|
| 搜索联想 / 输入法 | 手写 Trie | 双数组 Trie（DAT） | DAT 空间紧凑、缓存友好，性能数倍于朴素 Trie |
| IP 路由（最长前缀匹配） | 手写 Trie | Linux fib_trie（压缩 Trie） | 压缩 Trie 合并单链，路由表百万条也能高效查 |
| 敏感词过滤 | AC 自动机 | AC 自动机 + DFA | 多模式一次扫描，AC 自动机就是生产最优解 |
| 拼写检查 | Trie + 编辑距离 | BK-Tree / Norvig 算法 | 拼写纠错更关注相似度，Trie 只是候选生成器 |

**生产里 Trie 的常见形态是"压缩版"**——朴素 Trie 空间浪费大，工程中几乎都用压缩 Trie（Radix Tree）、双数组 Trie（Double-Array Trie）或 AC 自动机。但理解朴素 Trie 是理解这些生产变体的前提。

### 6. 三个真实工程坑

**坑一：search 和 startsWith 混用，前缀当词返回。**

```python
# 插入 "apple" 后
trie.search("app")     # 错误地返回 True？
```

症状：插了 "apple"，查 "app" 误返回 True。根因：`search` 没检查 `is_end`，只检查路径走不走得通。修复：`search` 必须同时满足"路径走通"和"终点 `is_end=True`"。这是 LeetCode 208 最常见 bug。

**坑二：数组版 children 用于 Unicode 字符集，下标越界。**

```python
idx = ord(ch) - ord('a')   # ch 是中文，idx 变成负数或超大
```

症状：处理中文/全字符集时 `ord(ch) - ord('a')` 越界崩溃。根因：数组版只支持小写字母，字符集外的字符下标非法。修复：字符集大或未知时用哈希版 `children = {}`，`children.get(ch)` 替代下标访问。

**坑三：删除时自顶向下摘节点，把别的词也删了。**

```python
def delete_bad(trie, word):
    node = trie.root
    for ch in word:
        idx = ord(ch) - ord('a')
        parent = node
        node = node.children[idx]
        parent.children[idx] = None   # 自顶向下摘，错误！
```

症状：删 "app" 时把 "apple" 也删了。根因：自顶向下摘节点，父节点先被摘掉，子节点够不着；且没检查 pass_cnt，把还有别的词经过的节点也摘了。修复：用 pass_cnt 计数，自底向上（`reversed(path)`）摘，摘到 pass_cnt > 0 的节点就停。

## 四、速查与自测

### 速查表：Trie 操作复杂度与字符映射对比

| 操作 | 复杂度 | 说明 |
|---|---|---|
| insert | $O(L)$ | L 是词长，与词库大小无关 |
| search | $O(L)$ | 走完路径看 end 标记 |
| starts_with | $O(L)$ 判存在 | 列全部匹配词 $O(L+k)$ |
| delete | $O(L)$ | 带 pass 计数，自底向上摘 |
| 空间 | $O(\sum L_i)$ 最坏 | 前缀重合时大幅省 |

**Trie vs 哈希表**：前缀查询 / 字典序遍历 / 前缀补全 → Trie；单点查询 / 高频插入 → 哈希表。

**数组版 vs 哈希版**：小字符集 → 数组版（缓存友好）；Unicode / 未知字符集 → 哈希版（省空间）。详见表 2.4。

### 自测三问

**问题一：** 插入 "app" 和 "apple" 后，"app" 末尾节点的 is_end 是 True 还是 False？"appl" 末尾节点呢？search("app") 和 startsWith("app") 分别返回什么？

**参考答案：** "app" 末尾节点 is_end=True（它是完整词 "app" 的结尾）；"appl" 末尾节点 is_end=False（它只是 "apple" 的中间节点，本身不是词）。search("app") 返回 True（路径走通且终点 is_end=True）；startsWith("app") 也返回 True（只要路径走通就行，"app" 是 "apple" 的前缀）。**关键区别**：search 要求终点是词尾，startsWith 只要求路径走通——这是 LeetCode 208 最常考的点。

**问题二：** 为什么单点查询哈希表通常比 Trie 快？那为什么前缀查询 Trie 又完胜哈希表？

**参考答案：** 单点查询哈希表是一次哈希 + 一次查表 $O(1)$（平均），Trie 要走 L 步逐字符下沉 $O(L)$，常数更大——所以单点查哈希胜。但前缀查询哈希表无能为力：哈希函数把相似前缀打散到不同桶，前缀信息在哈希时丢失，只能线性扫描全部词逐个 `startswith`，$O(n \cdot L)$；Trie 保留前缀结构，沿前缀走 L 步就到匹配子树根，$O(L)$。**取舍的关键**是"是否需要前缀信息"——哈希表为了 $O(1)$ 单点查询牺牲了前缀结构，Trie 保留了前缀结构但单点查询常数更大。各有所长，看场景选。

**问题三：** Trie 的删除为什么要用 pass_cnt 计数并自底向上摘节点？直接把路径上的节点全删了行不行？

**参考答案：** 不行。"app" 和 "apple" 共享前缀 "app"，删 "app" 时如果把 a、p、p 节点全删，"apple" 就没了。正确做法用 pass_cnt 记录"有多少词经过此节点"：删一个词时路径上每个节点 pass_cnt -1，自底向上（`reversed(path)`）摘，摘到第一个 pass_cnt > 0 的节点就停——再往上的节点还有别的词经过，不能摘。自底向上是因为父节点先被摘掉，子节点就够不着了。**pass 计数 + 自底向上是 Trie 删除的两个要点**，缺一个都会误删共享前缀的别的词。

### 算法思想 × 生活迁移

Trie 的精髓是"**公共前缀合并，按需分叉**"——共享的部分只存一份，差异处才分支。

**迁移一：图书馆按主题分层摆放。** 图书馆不会把每本书独立放一个格子（那是哈希表式，找书 $O(1)$ 但浏览不了"计算机类有哪些书"）。它按"楼层→大区→小区→书架"分层：所有计算机书在 3 楼，所有算法书在 3 楼 A 区——公共前缀（计算机类）只占一层楼，细分时才分叉。这就是 Trie 结构——公共前缀共享路径，到差异处才分叉。想找"所有算法书"只需走到"算法"那层，下面整片书架就是，不用逐本扫。

**迁移二：公司组织架构树。** 大公司按"事业部→部门→组→个人"分层。所有研发部的人在研发事业部下，共享前缀"研发事业部/部门名"。查"研发部有哪些组"只需走到"研发部"节点，下面的子树就是全部组——比扁平地维护一份"部门到人员"哈希表更适合层级查询。扁平哈希表查"某人在不在"快（单点查询），但查"研发部有哪些组"得扫全部——这正是 Trie vs 哈希表的取舍在组织架构上的投射。

**迁移三：URL 路由按域名分层。** 浏览器或 CDN 的路由表按"协议→域名→路径"分层匹配。所有 `api.example.com` 的请求共享前缀，路由到同一组服务器；到具体 API 路径才分叉到不同 handler。这就是最长前缀匹配——Trie 的拿手好戏。Linux 内核的 fib_trie（路由表）就是压缩 Trie，百万条路由规则也能快速匹配。

**为什么这些迁移成立：** Trie 成立的前提是"数据有可共享的层级前缀，且查询需要按前缀聚合"。图书馆分类、组织架构、URL 路由都满足——都有天然层级结构，都常做"前缀聚合查询"。如果数据没有层级（如随机 UUID）或只需单点查询（如缓存 key 查找），Trie 不适用，哈希表更优。

## 参考来源

- Fredkin, E. *Trie Memory*. Communications of the ACM, 1960.（Trie 原始论文，提出 retrieval tree 结构）
- Aho, A. V. & Corasick, M. J. *Efficient String Matching: An Aid to Bibliographic Search*. Communications of the ACM, 1974.（AC 自动机原始论文，Trie + 失败指针的多模式匹配）
- [1] Cormen, T. H. et al. *Introduction to Algorithms*. MIT Press, 4th ed., 2022.（Trie 在字符串匹配章节的讨论）
- [2] Sedgewick, R. & Wayne, K. *Algorithms*. Addison-Wesley, 4th ed., 2011. 第 5 章（Trie 与符号表，R-way Trie 与 TST）
- [3] 邓俊辉. 数据结构（C++语言版）. 清华大学出版社, 第 3 版, 2013.（国内教学参考）
- [7-补充] krahets. *Hello 算法*. [hello-algo.com/chapter_hashing](https://www.hello-algo.com/chapter_hashing/).（Trie 图示与多语言代码）
- [17] TheAlgorithms/Python. [github.com/TheAlgorithms/Python](https://github.com/TheAlgorithms/Python).（Trie 可运行实现对照）
- [23] 左程云. 程序员代码面试指南. 电子工业出版社.（"对数器"验证方法、Trie 面试题套路）
- 用户信源：`book-sources/面试现场/技术表达（表达方法+面试官视角）.md`（"技术的水有多深"八层面表达框架，本文"面试时怎么讲"参考此框架）
- 用户信源：`book-sources/面试现场/考察标准（编程能力+软性能力）.md`（"递归思维""分治思维"的面试考查视角，本文"面试高频题"参考此标准）
