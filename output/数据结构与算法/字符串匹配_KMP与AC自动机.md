---
title: 算法课·31｜字符串匹配：从暴力到 KMP 到 AC 自动机
book: 数据结构与算法
chapter: 字符串匹配
event: KMP与AC自动机
sort: 1
chapter_sort: 21
created_at: 2026-06-29
source_agents:
- algorithm-expert
---
# 算法课·31｜字符串匹配：从暴力到 KMP 到 AC 自动机

> 前置知识：学完第 13-18 章（数组与指针基础），能熟练用双指针走数组
> 学完你能：①给小白讲清暴力匹配 $O(nm)$ 的痛点在哪 ②默写 KMP 的 next 数组构造与匹配过程，并讲透每一行 ③用 Rabin-Karp 做滚动哈希匹配 ④讲清 AC 自动机 = KMP + Trie 的多模式匹配 ⑤用对数器对比暴力与 KMP ⑥手撕 LeetCode 28/459/1392 三道高频面试题

## 一、问题与思路：暴力匹配的浪费与 KMP 的破局

### 1. 一个生活场景：在长文本里找一个词

在 10 亿字的代码库里搜一个函数名，暴力匹配（Brute-Force）要把每个起点都试一遍，最坏情况下比对次数是文本长度乘以模式长度。你大概觉得这种"笨办法"早就被淘汰了——但直到今天，很多编辑器的查找功能底层仍是暴力匹配。真正的提速来自 1977 年 KMP 那篇论文，而它提速的方式相当反直觉：不靠"比对更快"，靠"失败时也能带走信息"。

把问题形式化一下：给定文本串 `text`（长度 $n$）和模式串 `pattern`（长度 $m$），找出 `pattern` 在 `text` 中首次出现的位置。匹配算法就是围绕"主指针怎么走、模式指针怎么回退"做文章。下面会看到，暴力、KMP、Rabin-Karp、AC 自动机的差别全在这两根指针的回退策略上。

### 2. 暴力匹配的两个痛点

**痛点一：主指针回头，已经比对过的字符被白白丢弃。** 暴力匹配在 `text[i]` 与 `pattern[0]` 对齐开始比对，若比到 `pattern[j]` 失配，就把起点整体右移一位、从 `text[i+1]` 与 `pattern[0]` 重新比对。问题在于：刚才已经比对了 `pattern[0..j-1]` 与 `text[i..i+j-1]` 完全相等，这些信息直接被扔了。

**痛点二：最坏情况退化到 $O(nm)$。** 想象文本是 `aaaaaa...ab`（$n$ 个 a 加一个 b），模式是 `aaaab`。每个起点都要比到第 5 个字符才发现失配，主指针只前进 1，模式指针回到 0，比对次数逼近 $n \times m$。

举个最小例子，`text = "abababc"`，`pattern = "ababc"`：

```
暴力匹配在起点 0：abab|a 比对到第5位 c vs a 失配，主指针回到 1
起点 1：       a|babc  第1位就失配
起点 2：        ababc  全部匹配，返回 2
```

起点 0 已经比对了 `abab` 四个字符，但暴力做法把这些信息全扔了，导致起点 2 还得从头比一遍 `abab`。

### 3. KMP 的破局思路：失败也是信息

KMP 的核心观察一句话能讲完：**失配发生时，已经匹配上的那段前缀里，藏着"下一步该从哪继续"的信息，别浪费它。**

具体说，当 `pattern[j]` 与 `text[i]` 失配时，我们已经知道 `pattern[0..j-1]` == `text[i-j..i-1]`。如果 `pattern[0..j-1]` 这个串本身存在"既是真前缀又是后缀"的最长公共部分（长度记为 $k$），那么 `pattern[0..k-1]` == `pattern[j-k..j-1]` == `text[i-k..i-]`。于是主指针不用动，模式指针直接跳到 `k` 继续比就行——因为 `pattern[0..k-1]` 已经和 `text` 当前位置的左侧对齐了。

这就是 next 数组要存的东西：**next[j] 表示 `pattern[0..j-1]` 这段的最长"真前缀 = 后缀"长度**。失配时模式指针回退到 `next[j]`，主指针不动。这一步把暴力里的"主指针回头"彻底消灭，匹配阶段主指针只前进不回退，所以是 $O(n)$。

注意一个常被混淆的点：next 数组描述的是**模式串自身的结构**，跟文本串无关。所以它可以在匹配前一次性预算好，预算本身也是 $O(m)$。

### 4. 历史地位：第一个把匹配做到线性

1977 年，Knuth、Morris、Pratt 三人在 *SIAM Journal on Computing* 发表 *Fast Pattern Matching in Strings*，把字符串匹配拉到 $O(n+m)$ 线性时间。 Morris 在更早的文本编辑器项目里就独立想到了这个回退策略，Knuth 给出了完整复杂度分析，三人合署发表，所以算法叫 KMP。

同年 Boyer 和 Moore 提出了另一个线性算法（BM 算法），思路相反——从模式末尾往前比，靠"坏字符"和"好后缀"两个启发式跳过更多字符。KMP 走的是"保证最坏线性"的路子，BM 走的是"平均更快但最坏仍可能退化"的路子。工程里很多实际查找工具（如 grep 的某些模式）用 BM 的变种，因为平均更快；KMP 的价值在于**最坏情况可证明的线性**，以及它把"失败信息"显式编码成 next 数组这个思想，直接启发了后来的 AC 自动机。

字符串匹配算法之所以这么多，正是因为不同算法瞄准的痛点不同：暴力瞄准"实现简单"，KMP 瞄准"最坏线性"，Rabin-Karp 瞄准"多模式 + 哈希可滚动"，AC 自动机瞄准"一次扫描匹配海量模式"。每一个都解决了前一个的某个痛点，没有谁能通吃所有场景。

## 二、原理与实现：next 数组、Rabin-Karp 与 AC 自动机

### 1. 暴力匹配代码与最坏 $O(nm)$

先把暴力做法写出来，后面用它做对照基准：

```python
def brute_search(text, pattern):
    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    for i in range(n - m + 1):        # 每个起点
        j = 0
        while j < m and text[i + j] == pattern[j]:
            j += 1
        if j == m:
            return i
    return -1
```

**逐行讲透**：

- **`for i in range(n - m + 1)`**：i 是对齐起点，从 0 到 `n-m`。若模式比文本长直接返回 -1（循环不执行）。
- **`while j < m and text[i + j] == pattern[j]`**：从起点 i 开始逐字符比对，比到末尾或失配为止。
- **`if j == m: return i`**：j 走完整个模式说明全部相等，返回起点。

最坏情况比对次数：每个起点都比到接近 m 才失配，共 $n-m+1$ 个起点，总比对 $O(nm)$。前面那个 `aaaa...ab` 配 `aaaab` 就是教科书级的反例。

### 2. KMP 的 next 数组：构造与匹配逐行讲透

#### 2.1 next 数组定义

`next[i]` = 模式串 `pattern[0..i]` 这段子串里，**最长的"既是真前缀又是后缀"的长度**（真前缀要求长度严格小于子串本身）。

以 `pattern = "ababc"` 为例：

```
子串        最长真前缀=后缀        next
a           无（单字符）            0
ab          无                     0
aba         "a" 既是前缀又是后缀    1
abab        "ab"                   2
ababc       无                     0
```

所以 `next = [0, 0, 1, 2, 0]`。

#### 2.2 构造代码逐行讲透

next 数组的构造本身就是一次"模式串自己跟自己匹配"的 KMP：

```python
def build_next(p):
    m = len(p)
    nxt = [0] * m                 # nxt[i] = pattern[0..i] 的最长真前后缀长度
    k = 0                         # 当前已知的最长前后缀长度
    for i in range(1, m):         # 从第二个字符开始
        while k > 0 and p[i] != p[k]:
            k = nxt[k - 1]        # 失配就沿 next 链回退，和匹配阶段同一招
        if p[i] == p[k]:
            k += 1                # 匹配上，长度 +1
        nxt[i] = k
    return nxt
```

**逐行讲透**（每一行都不能含糊）：

- **`k = 0`**：初始没有任何前后缀信息，长度为 0。
- **`for i in range(1, m)`**：i 是当前要算 next 的位置，从 1 开始（位置 0 单字符，next[0] 必为 0）。
- **`while k > 0 and p[i] != p[k]`**：尝试把"当前最长前后缀"再延长一位，即看 `p[i]` 是否等于 `p[k]`。不等就回退——回退到哪？回退到 `nxt[k-1]`，也就是"前缀 `p[0..k-1]` 的最长真前后缀长度"。这是构造阶段最绕的一行，逻辑和匹配阶段一模一样：失配时沿 next 链跳，不从头开始。
- **`k = nxt[k - 1]`**：把 k 缩小到次优解继续试。循环条件 `k > 0` 保证不会越界；k 归零就退出 while，从 0 重新比。
- **`if p[i] == p[k]: k += 1`**：比上了，最长前后缀长度加 1。
- **`nxt[i] = k`**：记录结果。

用一个例子走一遍 `p = "ababc"`：

```
i=1 (b): k=0, p[1]=b≠p[0]=a → nxt[1]=0
i=2 (a): k=0, p[2]=a==p[0]=a → k=1 → nxt[2]=1
i=3 (b): k=1, p[3]=b==p[1]=b → k=2 → nxt[3]=2
i=4 (c): k=2, p[4]=c≠p[2]=a → k=nxt[1]=0
         p[4]=c≠p[0]=a → k=0 → nxt[4]=0
```

结果 `[0, 0, 1, 2, 0]`，与手算一致。

#### 2.3 匹配代码逐行讲透

```python
def kmp_search(text, pattern):
    if not pattern:
        return 0
    nxt = build_next(pattern)
    j = 0                          # 模式指针，指向下一个要比对的位置
    for i in range(len(text)):     # 主指针 i 只前进不回退
        while j > 0 and text[i] != pattern[j]:
            j = nxt[j - 1]         # 失配：模式指针回退到 next[j-1]，主指针不动
        if text[i] == pattern[j]:
            j += 1                 # 匹配：模式指针前进
        if j == len(pattern):
            return i - j + 1       # 找到，返回起点
    return -1
```

**逐行讲透**：

- **`j = 0`**：模式指针从 0 开始。
- **`for i in range(len(text))`**：主指针 i 单调递增，这是 KMP 线性的关键。
- **`while j > 0 and text[i] != pattern[j]`**：失配且 j 还没退到 0 时，沿 next 链回退。注意是 `nxt[j-1]`——因为当前已匹配的是 `pattern[0..j-1]`，要查的是这一段的最长真前后缀。
- **`if text[i] == pattern[j]: j += 1`**：比上了，j 前进。注意这里 if 不用 else——while 退出后要么 j=0 要么已匹配，再统一判一次。
- **`if j == len(pattern): return i - j + 1`**：模式走完，匹配成功。起点 = 当前 i - 已匹配长度 + 1。

走一遍 `text="abababc"`, `pattern="ababc"`，`nxt=[0,0,1,2,0]`：

```
i=0 a: j=0, t[0]=a==p[0] → j=1
i=1 b: j=1, t[1]=b==p[1] → j=2
i=2 a: j=2, t[2]=a==p[2] → j=3
i=3 b: j=3, t[3]=b==p[3] → j=4
i=4 a: j=4, t[4]=a≠p[4]=c → j=nxt[3]=2
       j=2, t[4]=a==p[2]=a → j=3
i=5 b: j=3, t[5]=b==p[3]=b → j=4
i=6 c: j=4, t[6]=c==p[4]=c → j=5 == len(p) → 返回 6-5+1=2
```

注意 i=4 这一步：失配后 j 从 4 跳到 2（不是 0），主指针 i 没动，直接用 `p[2]=a` 跟 `t[4]=a` 续上。这正是"失败带走了信息"——已匹配的 `ab`（pattern 的真前缀）被复用，不用重比。

#### 2.4 复杂度

匹配阶段主指针 i 从 0 走到 n，只前进；模式指针 j 每次失配回退，但 j 总共增加的次数不超过 i 前进的次数（j 每次 +1 都对应一次 i 前进），所以 j 回退总次数也不超过 n。匹配阶段均摊 $O(n)$。构造阶段同理 $O(m)$。合计 $O(n+m)$，空间 $O(m)$ 存 next。

### 3. Rabin-Karp：用哈希做匹配

Rabin-Karp 走的是另一条路：不逐字符比，而是把模式和一个滑动窗口都算成哈希值，哈希相等再逐字符确认。

```python
def rabin_karp(text, pattern):
    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    if m > n:
        return -1
    base, mod = 256, 10**9 + 7
    # 模式哈希
    p_hash = 0
    for ch in pattern:
        p_hash = (p_hash * base + ord(ch)) % mod
    # 第一个窗口哈希
    t_hash = 0
    for i in range(m):
        t_hash = (t_hash * base + ord(text[i])) % mod
    if t_hash == p_hash and text[:m] == pattern:
        return 0
    # base^(m-1) 用于滚动时减去离开的字符
    high = pow(base, m - 1, mod)
    for i in range(m, n):
        # 滚动：减去离开字符的贡献，整体左移，加上新字符
        t_hash = (t_hash - ord(text[i - m]) * high) % mod
        t_hash = (t_hash * base + ord(text[i])) % mod
        if t_hash == p_hash and text[i - m + 1:i + 1] == pattern:
            return i - m + 1
    return -1
```

**逐行讲透关键点**：

- **`base, mod`**：把字符串当成 base 进制数取模。base 取字符集大小（256 覆盖 ASCII），mod 取大质数降低冲突。
- **`high = pow(base, m-1, mod)`**：窗口最高位的权重，滚动时要用它把离开的字符"移出"。
- **滚动公式**：`t_hash = ((t_hash - ord(leave)*high) * base + ord(enter)) % mod`。这是 Rabin-Karp 的精髓——新窗口哈希能在 $O(1)$ 内从旧窗口推出，不用重算 $O(m)$。

复杂度：平均 $O(n+m)$（哈希几乎不冲突时滚动是 $O(1)$，命中再 $O(m)$ 确认）；最坏 $O(nm)$——若构造大量哈希冲突，每个窗口都要逐字符确认。Rabin-Karp 的真正价值在**多模式匹配**和**二维匹配**：要同时找 $k$ 个模式，把每个模式的哈希存进哈希表，文本每个窗口查一次表即可，这是 KMP 做不到的。

注意工程坑：Python 的 `%` 对负数返回非负，C++/Java 取模可能出负数，滚动后要 `((t_hash % mod) + mod) % mod` 兜底。

### 4. AC 自动机：KMP + Trie 的多模式匹配

#### 4.1 为什么需要 AC 自动机

KMP 一次只匹配一个模式。要在文本里同时找 10000 个敏感词，跑 10000 次 KMP 是 $O(10000 \cdot n)$，太慢。AC 自动机（Aho-Corasick，1975）解决这个问题：把所有模式建成一棵 Trie，给 Trie 上每个节点配一个"fail 指针"——本质是把 KMP 的 next 数组从"一条链"推广到"一棵树"。

#### 4.2 三步走

```python
from collections import deque, defaultdict

class ACNode:
    __slots__ = ("children", "fail", "end")
    def __init__(self):
        self.children = defaultdict(ACNode)  # 子节点
        self.fail = None                      # 失配指针
        self.end = False                      # 是否为某模式结尾

def build_ac(patterns):
    root = ACNode()
    # 第一步：建 Trie
    for p in patterns:
        node = root
        for ch in p:
            node = node.children[ch]
        node.end = True
    # 第二步：BFS 建 fail 指针
    root.fail = root
    q = deque()
    for ch, child in root.children.items():
        child.fail = root
        q.append(child)
    while q:
        cur = q.popleft()
        for ch, child in cur.children.items():
            # 沿父节点的 fail 链找，直到能接上 ch
            f = cur.fail
            while f is not root and ch not in f.children:
                f = f.fail
            if ch in f.children and f.children[ch] is not child:
                child.fail = f.children[ch]
            else:
                child.fail = root
            # 顺带继承 fail 节点的 end 标记（后缀链接优化）
            child.end = child.end or child.fail.end
            q.append(child)
    return root

def ac_search(text, root):
    node = root
    hits = []
    for i, ch in enumerate(text):
        while node is not root and ch not in node.children:
            node = node.fail          # 沿 fail 链回退，等价于 KMP 的 next 回退
        if ch in node.children:
            node = node.children[ch]
        if node.end:
            hits.append(i)            # 命中某个模式（结束位置）
    return hits
```

**逐行讲透关键点**：

- **第一步建 Trie**：把所有模式插进去，公共前缀共享节点，这是"多模式"省空间的根基。
- **第二步 fail 指针**：节点 `x` 的 fail 指针指向" Trie 中另一个深度更浅、且从根到它的路径是 `x` 路径的最长真后缀"的节点。逻辑跟 KMP 的 next 完全同构——next 是"模式串自身的最长真前后缀"，fail 是"所有模式组成的 Trie 里的最长真后缀节点"。用 BFS 逐层建，因为 fail 一定指向更浅的层。
- **`child.end = child.end or child.fail.end`**：后缀链接优化。如果 fail 指向的节点是某模式结尾，那当前节点匹配时也要算命中（因为当前路径的后缀就是那个模式）。
- **匹配阶段**：主指针 i 只前进，失配时沿 fail 链回退。跟 KMP 匹配阶段一一对应。

复杂度：建 Trie $O(\sum |p_i|)$，建 fail 指针 $O(\sum |p_i| \cdot |\Sigma|)$（用 defaultdict 优化到接近线性），匹配 $O(n + \text{命中数})$。一次扫描就能找出所有模式的所有出现位置。

#### 4.3 一句话总结 AC 自动机

**AC 自动机 = Trie（组织多模式）+ fail 指针（KMP 的失配回退推广到树上）**。Trie 解决"多个模式怎么共享前缀"，fail 指针解决"失配后回退到哪"。理解了 KMP 的 next 数组，AC 自动机的 fail 指针就是它的多模式版本。

### 5. 高手向：后缀数组与 Z 函数（提及不展开）

字符串匹配还有一大家子算法，这里只点名，不展开：

- **Boyer-Moore（BM）**：从模式末尾往前比，靠坏字符表和好后缀表跳过字符，平均比 KMP 快但最坏仍 $O(nm)$（有变种能保证线性）。
- **Z 函数（Z-algorithm）**：$z[i]$ 表示 `s[i..]` 与 `s` 的最长公共前缀长度。把 pattern + '#' + text 拼起来算 Z 函数，$z[i] = m$ 的位置就是匹配点。和 KMP 等价但常数更小，竞赛常用。
- **后缀数组（Suffix Array）+ LCP**：把文本所有后缀排序，配合 LCP 数组做二分查找，能在 $O(n \log n)$ 预处理后支持任意模式 $O(m \log n)$ 查询。适合"文本固定、模式频繁变"的场景（如生物信息里对同一条基因组反复查询）。
- **后缀自动机（SAM）**：能接受文本所有子串的最小 DFA，匹配 $O(n)$，是后缀结构的终极形态。

这些结构各有适用场景，工程里按"模式数、文本是否固定、是否需要在线"选型。日常面试掌握 KMP + AC 自动机已经够用，后缀结构属于竞赛/生物信息方向。

### 6. 五指标对比

| 指标 | 暴力 | KMP | Rabin-Karp | AC 自动机 |
|---|---|---|---|---|
| 预处理 | $O(1)$ | $O(m)$ | $O(m)$ | $O(\sum \|p_i\|)$ |
| 匹配最好 | $O(n)$ | $O(n)$ | $O(n+m)$ | $O(n)$ |
| 匹配最坏 | $O(nm)$ | $O(n)$ | $O(nm)$ | $O(n+\text{命中})$ |
| 空间 | $O(1)$ | $O(m)$ | $O(1)$ | $O(\sum \|p_i\|)$ |
| 多模式 | 不支持 | 不支持 | 支持（哈希表） | 原生支持 |

KMP 的优势在最坏线性且常数小；Rabin-Karp 的优势在多模式 + 滚动哈希便于改造成二维/多维匹配；AC 自动机是多模式的原生解，敏感词过滤的事实标准。

## 三、实践与面试：对数器、工程坑、面试高频题

### 1. 对数器：对比暴力与 KMP

左神的规矩：写完 KMP 不要靠几个例子肉眼检查，用对数器拿暴力做法（绝对正确）当基准，跑足够多次随机数据：

```python
import random

def build_next(p):
    m = len(p)
    nxt = [0] * m
    k = 0
    for i in range(1, m):
        while k > 0 and p[i] != p[k]:
            k = nxt[k - 1]
        if p[i] == p[k]:
            k += 1
        nxt[i] = k
    return nxt

def kmp_search(text, pattern):
    if not pattern:
        return 0
    nxt = build_next(pattern)
    j = 0
    for i in range(len(text)):
        while j > 0 and text[i] != pattern[j]:
            j = nxt[j - 1]
        if text[i] == pattern[j]:
            j += 1
        if j == len(pattern):
            return i - j + 1
    return -1

def brute_search(text, pattern):
    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    for i in range(n - m + 1):
        j = 0
        while j < m and text[i + j] == pattern[j]:
            j += 1
        if j == m:
            return i
    return -1

def checker(times=10000, max_n=50, alpha="ab"):
    """对数器：随机文本/模式，对比暴力与 KMP。"""
    for _ in range(times):
        n = random.randint(0, max_n)
        text = "".join(random.choice(alpha) for _ in range(n))
        m = random.randint(0, max_n)
        pattern = "".join(random.choice(alpha) for _ in range(m))
        if brute_search(text, pattern) != kmp_search(text, pattern):
            print(f"出错！text={text!r} pattern={pattern!r}")
            print(f"暴力={brute_search(text, pattern)} KMP={kmp_search(text, pattern)}")
            return False
    print("对数器验证通过！")
    return True

checker()
```

**对数器要点**：

- **字符集用 `"ab"` 而非全字母**：小字符集更容易触发 KMP 的回退链（重复子串多），覆盖边界更狠。
- **长度含 0**：空模式、空文本都要覆盖，这是手写时最容易漏的分支。
- **基准用暴力**：暴力做法逻辑直白、可信，是验证 KMP 的天然标尺。

**对高手的启发**：对数器思想不止验证匹配算法——任何"有朴素正确解可对照"的问题都能用。写完线段树对数器对比暴力区间求和；写完并查集对数器对比每次全连通检查。这是工程化验证思维，比"跑几个例子看对不对"可靠得多。

### 2. 教科书做法 vs 生产做法

| 场景 | 教科书做法 | 生产做法 | 原因 |
|---|---|---|---|
| 编辑器查找单词 | 手写 KMP | 调用 `str.find` / `str.index` | CPython 底层用 Fast Search（混合 BM 思想），常数比手写 KMP 小 |
| 单模式海量匹配 | 手写 KMP | 正则引擎 / BM 变种 | BM 平均更快，grep 系工具多用 BM 族 |
| 敏感词过滤（多模式） | 手写 AC 自动机 | DAG / `ahocorasick` 库 | AC 是事实标准，但生产用成熟库，避免手写 fail 指指出 bug |
| 防哈希碰撞的匹配 | 手写 Rabin-Karp | 双哈希 / 直接逐字符 | 单哈希有被构造碰撞攻击的风险 |

**生产里手写 KMP 几乎绝迹**，但有两个残留价值：

1. **面试硬通货**：LeetCode 28、459、1392 三题直接考 KMP，不会就过不了。
2. **理解 AC 自动机的前置**：AC 自动机的 fail 指针是 next 数组的推广，不懂 KMP 就看不懂 AC 的回退逻辑。

### 3. 真实工程坑

**坑一：next 数组用 `nxt[j]` 还是 `nxt[j-1]`， Convention 一错全盘崩。**

```python
# 错误：失配时回退到 nxt[j] 而非 nxt[j-1]
while j > 0 and text[i] != pattern[j]:
    j = nxt[j]        # ❌ 应该是 nxt[j-1]
```

症状：某些用例返回错误位置或死循环。根因：当前已匹配段是 `pattern[0..j-1]`，要查的是这段的真前后缀，对应 `nxt[j-1]`。用 `nxt[j]` 查的是 `pattern[0..j]`，含义错了。修复：统一用 `nxt[j-1]`，构造和匹配保持同一个约定。

**坑二：构造 next 时忘了 while 循环，只 if 一次。**

```python
# 错误：失配只回退一次
for i in range(1, m):
    if k > 0 and p[i] != p[k]:    # ❌ 应该是 while
        k = nxt[k - 1]
    if p[i] == p[k]:
        k += 1
    nxt[i] = k
```

症状：`pattern = "aabaaab"` 这类用例 next 算错。根因：失配后可能要连跳几次 next 链才能找到能接上的位置，单次 if 只跳一步不够。修复：`if` 改 `while`。

**坑三：Rabin-Karp 不做哈希冲突确认，直接信哈希。**

```python
# 错误：哈希相等就返回，不逐字符确认
if t_hash == p_hash:
    return i - m + 1            # ❌ 没确认 text[i-m+1:i+1] == pattern
```

症状：构造碰撞数据能让算法返回错误位置（哈希攻击）。根因：取模哈希必然有冲突，哈希相等不代表字符串相等。修复：哈希相等后再 `text[...]==pattern` 确认；安全敏感场景用双哈希（两个不同 base/mod）。

### 4. 面试高频题：strStr(28)、重复的子字符串(459)、最长快乐前缀(1392)

#### 4.1 LeetCode 28 实现 strStr()

就是单模式匹配，KMP 标准模板，返回首次出现下标，找不到返回 -1，空模式返回 0。直接套 §2.3 的 `kmp_search` 即可。

**面试讲解要点**：先说"暴力 $O(nm)$ 最坏会退化"，再说"KMP 用 next 数组把主指针回退消灭，做到 $O(n+m)$"，最后提一句"工程里调 `find` 即可，因为 CPython 用 Fast Search 常数更小"。这三层递进能体现深度。

#### 4.2 LeetCode 459 重复的子字符串

判断字符串 $s$ 是否能由某个子串重复多次构成。经典技巧：若 $s$ 由子串 $t$ 重复 $k$ 次（$k \ge 2$）构成，则 $s$ 一定是 $(s + s)$ 去掉首尾字符后的子串。KMP 解法更直接：

```python
def repeated_substring_pattern(s):
    n = len(s)
    nxt = build_next(s)
    # 最长相等前后缀长度
    l = nxt[n - 1]
    # 若 n 能被 (n - l) 整除且 l > 0，说明 s 由长度 (n-l) 的子串重复构成
    return l > 0 and n % (n - l) == 0
```

**讲解要点**：`nxt[n-1]` 是整个 $s$ 的最长相等前后缀长度 $l$。若 $s$ 由长度 $p$ 的子串重复构成，则 $l = n - p$（前 $n-p$ 个和后 $n-p$ 个相等），且 $p = n - l$ 能整除 $n$。反过来，若 $l > 0$ 且 $n \bmod (n-l) = 0$，就能还原出重复子串。这是 next 数组"自匹配结构"的妙用。

#### 4.3 LeetCode 1392 最长快乐前缀

求 $s$ 的最长"既是真前缀又是后缀"的子串。这正是 next 数组的定义本身——`nxt[n-1]` 就是答案长度：

```python
def longest_prefix(s):
    nxt = build_next(s)
    return s[:nxt[len(s) - 1]]
```

**讲解要点**：一行代码体现对 next 数组定义的把握。注意"真前缀"要求长度严格小于 $n$，而 `nxt[n-1]` 本身就保证是真前后缀（构造时 k 不会等于子串长度），所以无需额外判断。

### 5. 面试手撕模板与讲解要点

面试被要求手写 KMP 时，背下面这套（next 构造 + 匹配），边写边讲：

```python
def build_next(p):
    m = len(p)
    nxt = [0] * m
    k = 0
    for i in range(1, m):
        while k > 0 and p[i] != p[k]:
            k = nxt[k - 1]
        if p[i] == p[k]:
            k += 1
        nxt[i] = k
    return nxt

def kmp_search(text, pattern):
    if not pattern:
        return 0
    nxt = build_next(pattern)
    j = 0
    for i in range(len(text)):
        while j > 0 and text[i] != pattern[j]:
            j = nxt[j - 1]
        if text[i] == pattern[j]:
            j += 1
        if j == len(pattern):
            return i - j + 1
    return -1
```

**面试讲解四层**（按"技术的水有多深"框架挑重点）：

1. **问题层**：暴力最坏 $O(nm)$，痛点是主指针回头丢弃已比对信息。
2. **原理层**：next 数组存"模式串自身的最长真前后缀"，失配时模式指针跳到 next 位置，主指针不动，已匹配前缀被复用。
3. **优劣层**：最坏线性 $O(n+m)$、空间 $O(m)$；常数比 BM 大，单模式工程里不占优，价值在最坏可证明线性 + 是 AC 自动机的前置。
4. **演进层**：暴力 → KMP（1977，单模式线性）→ AC 自动机（1975 实际更早，多模式线性）→ 后缀结构（文本固定反复查询）。每个解决了前一个的痛点。

**面试加分点**：主动提"next 数组的构造本身就是模式串自己跟自己做 KMP 匹配"，并指出构造和匹配两段代码的 while 回退逻辑完全同构——这能立刻区分你和"只会背模板"的候选人。

## 四、速查与自测

### 速查表：四大匹配算法对比

| 算法 | 预处理 | 匹配最坏 | 空间 | 多模式 | 一句话定位 |
|---|---|---|---|---|---|
| 暴力 | $O(1)$ | $O(nm)$ | $O(1)$ | 否 | 实现简单，编辑器查找底层 |
| KMP | $O(m)$ | $O(n)$ | $O(m)$ | 否 | 最坏可证明线性，面试硬通货 |
| Rabin-Karp | $O(m)$ | $O(nm)$ | $O(1)$ | 支持 | 滚动哈希，多模式 + 二维匹配 |
| AC 自动机 | $O(\sum\|p_i\|)$ | $O(n+\text{命中})$ | $O(\sum\|p_i\|)$ | 原生 | 敏感词过滤事实标准 |

**next 数组速记**：

| 项 | 说明 |
|---|---|
| 定义 | `nxt[i]` = `pattern[0..i]` 最长"真前缀=后缀"长度 |
| 构造 | 模式串自己跟自己 KMP，while 沿 next 链回退 |
| 匹配 | 失配时 `j = nxt[j-1]`，主指针不动 |
| 复杂度 | 构造 $O(m)$，匹配 $O(n)$ |
| 与 fail 指针 | AC 自动机的 fail = next 推广到 Trie |

### 自测三问

**问题一：** KMP 为什么能把匹配做到 $O(n)$？请用"主指针不回退"和"已匹配前缀的复用"两点解释，并对比暴力做法。

**参考答案：** 暴力做法失配时主指针退回起点+1、模式指针归零，已经比对过的 `pattern[0..j-1]` 信息被丢弃，最坏 $O(nm)$。KMP 的 next 数组记录了 `pattern[0..j-1]` 的最长相等前后缀长度 $k$。失配时，因为 `pattern[0..k-1]` == `pattern[j-k..j-1]` == `text` 当前位置左侧，模式指针直接跳到 $k$ 续比，主指针 $i$ 不动。这样主指针在整个匹配过程中只前进不回退，而模式指针 $j$ 的总增加量不超过主指针前进次数 $n$，所以 $j$ 回退总次数也不超过 $n$，匹配阶段均摊 $O(n)$。**关键不是"比对更快"，是"失败时也不浪费已比对信息"**。

**问题二：** next 数组的构造为什么是 $O(m)$ 而不是 $O(m^2)$？外层 for 里套了 while，看起来像二重循环。

**参考答案：** 用均摊分析。外层 for 让 $i$ 从 1 走到 $m-1$，每次 `if p[i]==p[k]: k+=1` 让 $k$ 至多 +1，所以 $k$ 在整个构造过程中总增加量不超过 $m$。内层 while 每次执行 `k = nxt[k-1]` 让 $k$ 至少 -1。$k$ 不能为负（循环条件 `k>0`），所以 $k$ 减少的总次数不超过它增加的总次数 $m$。因此内层 while 总执行次数 $O(m)$，构造整体 $O(m)$。这是"指针增量均摊"的经典分析，和 KMP 匹配阶段的 $O(n)$ 分析完全同构。

**问题三：** AC 自动机和 KMP 是什么关系？为什么说 AC 自动机是多模式版的 KMP？

**参考答案：** AC 自动机 = Trie + fail 指针。Trie 把所有模式组织成树，公共前缀共享节点，解决"多模式怎么存"。fail 指针是 KMP next 数组在树上的推广：KMP 的 next 描述"模式串这一条链上的最长真前后缀"，AC 的 fail 描述"Trie 中当前节点路径的最长真后缀节点"。失配时两者都沿回退链跳——KMP 跳 `nxt[j-1]`，AC 跳 `node.fail`。匹配阶段主指针都只前进不回退，复杂度都是线性。区别只是 KMP 处理一个模式（一条链），AC 处理多个模式（一棵树）。理解了 KMP，AC 的 fail 指针就是它的自然推广。

### 算法思想 × 生活迁移

KMP 的思想是"**失败时也要带走信息，不从头再来**"。

**迁移一：调试程序用二分定位，不要每次从头跑。** 复现一个 bug，暴力做法是每次改完从头重跑全流程，浪费时间。KMP 式做法是：记住"已经验证过没问题的前半段"，每次只从中断点附近继续定位，已经排查的区间不重复查。这就是二分调试、git bisect 的内核——已确认正确的部分当 next 数组存着，不回退。

**迁移二：背单词用间隔重复，不每次从第一个重背。** 暴力背单词是每天从第一页重背，已经记住的也重过一遍，$O(n \times \text{天数})$。间隔重复（Anki 式）记住"哪些已经记牢"，只复习快忘的——已掌握的部分当已匹配前缀，不重复消耗。这是"已匹配信息复用"在记忆里的体现。

**迁移三：面试复盘按"已掌握 / 待加强"分流。** 刷完一题不要每次都重刷全部。把题目按"已能默写 / 思路会但写不顺 / 完全不会"分流，只反复练中间那档——已掌握的当 next 数组跳过，时间花在"稍一失配就要回退"的薄弱处。

**为什么这些迁移成立：** KMP 成立的前提是"已完成的工作里蕴含着可复用的结构（相等前后缀）"。调试、记忆、复盘里都存在这种结构——已验证正确的部分、已记住的单词、已掌握的题目，都是可以跳过的"已匹配前缀"。迁移成立的关键是"能识别出哪些工作可复用"。若问题每次都是全新的、无任何结构可复用（如纯随机噪声），KMP 式思路就退化为暴力。

## 参考来源

- Knuth, D. E., Morris, J. H., Pratt, V. R. *Fast Pattern Matching in Strings*. SIAM Journal on Computing, 6(2):323-350, 1977.（KMP 原始论文，把字符串匹配拉到线性时间，next 数组（论文中称 failure function）的首次形式化）
- Aho, A. V., Corasick, M. J. *Efficient String Matching: An Aid to Bibliographic Search*. Communications of the ACM, 18(6):333-340, 1975.（AC 自动机原始论文，Trie + fail 指针的多模式匹配，发表早于 KMP 但思想同源）
- Karp, R. M., Rabin, M. O. *Efficient Randomized Pattern-Matching Algorithms*. IBM Journal of Research and Development, 31(2):249-260, 1987.（Rabin-Karp 滚动哈希匹配，随机化算法在串匹配上的应用）
- Boyer, R. S., Moore, J. S. *A Fast String Searching Algorithm*. Communications of the ACM, 20(10):762-772, 1977.（BM 算法，坏字符 + 好后缀启发式，与 KMP 同年发表的另一条线性路线）
- [1] Cormen, T. H. et al. *Introduction to Algorithms*. MIT Press, 4th ed., 2022. 第 32 章（字符串匹配：暴力、Rabin-Karp、KMP、BM 的系统讲解与复杂度证明）
- [11] Knuth, D. E. *The Art of Computer Programming, Vol. 3: Sorting and Searching*. Addison-Wesley, 1998. 字符串匹配章节（KMP 的权威分析与 next 数组构造）
- [23] 左程云. 程序员代码面试指南. 电子工业出版社.（字符串匹配专题，"对数器对比暴力"的工程验证视角，next 数组构造的逐行讲解风格）
- [7-补充] krahets. *Hello 算法*. [hello-algo.com/chapter_string_matching](https://www.hello-algo.com/chapter_string_matching/).（KMP 与 Rabin-Karp 的图示与多语言代码对照）
- 用户信源：`book-sources/面试现场/技术表达（表达方法+面试官视角）.md`（"技术的水有多深"八层面表达框架，本文"面试讲解四层"参考此框架）
- 用户信源：`book-sources/面试现场/考察标准（编程能力+软性能力）.md`（"问题层 / 原理层 / 优劣层 / 演进层"的面试考查视角，本文面试题讲解参考此标准）
