# 数据结构与算法专栏 · 参考文献清单

> 状态：策划草案，待用户确认。引用条目均经 WebSearch 核验，可点击链接直达。
> 配套：[plan.md](./plan.md) · [outline.md](./outline.md)

## 使用说明

文献分五类，每条给「为什么引 + 用在哪章」。视频/GitHub 项目作为「辅助信源」与「工程信源」，**不作唯一依据**，必须有书面文献配套。

- 📘 教材类：作为「概念准确性」的最终依据
- 📄 论文原典：作为「神和根本」的源头——回到发明者最初的想法
- 🛠️ 工程与 GitHub 项目：作为「投入实际」的真实代码佐证
- 🎬 视频专栏：作为「教学直觉」的辅助，必须有书面文献配套
- 🧭 思想迁移类：作为「算法思想 × 生活迁移」的方法论支撑

---

## 一、📘 教材类（概念准确性的最终依据）

### 1. CLRS《Introduction to Algorithms》（算法导论）

- **作者**：Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein
- **出版社**：MIT Press，第 4 版 2022
- **为什么引**：算法领域最权威教材，复杂度证明严谨，覆盖最全
- **用在哪章**：贯穿全专栏。复杂度分析、所有经典算法的权威定义来源
- **链接**：[MIT Press 官方页面](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/)

### 2. Sedgewick & Wayne《Algorithms》

- **作者**：Robert Sedgewick, Kevin Wayne
- **出版社**：Addison-Wesley，第 4 版 2011
- **为什么引**：Java 实现典范，图示清晰，工程视角强
- **用在哪章**：排序、查找、图论章节的代码实现参考
- **配套网站**：[algs4.cs.princeton.edu](https://algs4.cs.princeton.edu/)（含代码与可视化）

### 3. 邓俊辉《数据结构（C++语言版）》

- **作者**：邓俊辉（清华大学）
- **出版社**：清华大学出版社，第 3 版 2013
- **为什么引**：国内数据结构教学的标杆，叙事严谨且兼顾工程
- **用在哪章**：数据结构篇（链表/树/图/堆）主要参考
- **配套**：[清华在线课本](https://dsa.cs.tsinghua.edu.cn/~deng/ds/dsacpp/)（含课件与习题）

### 4. 《算法图解》

- **作者**：Aditya Bhargava
- **出版社**：人民邮电出版社（中文版），原版 Manning 2016
- **为什么引**：图示直觉极佳，适合「神和根本」的入门直觉铺垫
- **用在哪章**：开篇篇、第一性原理篇作直觉引子
- **注意**：仅作直觉铺垫，复杂度证明仍以 CLRS 为准

### 5. Dasgupta, Papadimitriou, Vazirani《Algorithms》

- **作者**：Sanjoy Dasgupta, Christos Papadimitriou, Umesh Vazirani
- **出版社**：McGraw-Hill，2006
- **为什么引**：薄而精，强调「为什么这个算法是对的」而非「怎么实现」，与本专栏「神和根本」理念高度契合
- **用在哪章**：第一性原理篇、思想迁移篇的核心方法论参考
- **链接**：[Berkeley 课程页](https://people.eecs.berkeley.edu/~vazirani/algorithms.html)（作者提供 PDF）

### 6. Kleinberg & Tardos《Algorithm Design》

- **作者**：Jon Kleinberg, Éva Tardos
- **出版社**：Pearson，2005
- **为什么引**：算法设计与问题归约的典范，DP/贪心/网络流章节尤其精彩
- **用在哪章**：经典算法篇的 DP/贪心/网络流章节

### 7. 严蔚敏《数据结构（C语言版）》

- **作者**：严蔚敏、吴伟民
- **出版社**：清华大学出版社
- **为什么引**：国内考研与课堂最常用教材，读者认知度极高
- **用在哪章**：作为「读者熟悉度对照」参考，不作为主要引用源
- **注意**：伪代码风格偏旧，工程实现以 Sedgewick 为准

### 7-补充. 《Hello 算法》（hello-algo）

- **作者**：krahets（闫小勇）
- **仓库**：[github.com/krahets/hello-algo](https://github.com/krahets/hello-algo)
- **在线版**：[hello-algo.com](https://www.hello-algo.com/)
- **简介**：国内最火开源算法教程，GitHub 12 万+ stars，被译为多语言。以「动画图解 + 多语言代码（Python/Java/C++/Go/JS/Rust 等十余种）」为核心特色
- **为什么引**：用户明确指定参考。图示直觉极佳，与「神和根本」理念契合；多语言代码对照适合「投入实际」段。本专栏以它作为**主要教学骨架**之一
- **用在哪章**：贯穿数据结构篇与经典算法篇。排序章（[选择排序示例](https://www.hello-algo.com/chapter_sorting/selection_sort/)）、链表/树/图/堆/哈希章的图示与代码对照
- **注意**：hello-algo 偏教学直觉，复杂度严格证明与论文出处仍以 CLRS [1] 与论文原典 [9]-[16] 为准。**当与其他文献有出入时，以核心专业名家书籍（CLRS/Sedgewick/邓俊辉）与论文原典为准**

---

## 二、📄 论文原典（神和根本的源头）

回到发明者最初的想法，理解「人类为什么会想到它」。每篇给原始出处与可访问链接。

### 8. Dijkstra 最短路径算法

- **论文**：Edsger W. Dijkstra, *"A Note on Two Problems in Connexion with Graphs"*, **Numerische Mathematik**, 1959
- **为什么引**：Dijkstra 当年手算设计了这套算法，揭示「贪心 + 松弛」的起源
- **用在哪章**：图论章·Dijkstra 节
- **链接**：[DOI 10.1007/BF01386390](https://doi.org/10.1007/BF01386390)

### 9. Kruskal 最小生成树

- **论文**：Joseph B. Kruskal, *"On the Shortest Spanning Subtree of a Graph"*, **Proceedings of the AMS**, 1956
- **为什么引**：贪心思想的纯粹体现，与 Prim 对比可看清「贪心策略的两种切入」
- **用在哪章**：图论章·最小生成树节
- **链接**：[AMS 全文](https://www.ams.org/proc/1956-007-01/S0002-9939-1956-0078686-7/)

### 10. Tarjan 强连通分量

- **论文**：Robert E. Tarjan, *"Depth-First Search and Linear Graph Algorithms"*, **SIAM Journal on Computing**, 1972
- **为什么引**：单次 DFS 求 SCC 的精妙，体现「图遍历 + 时间戳」的范式
- **用在哪章**：图论章·强连通分量节
- **链接**：[DOI 10.1137/0201010](https://doi.org/10.1137/0201010)

### 11. KMP 字符串匹配

- **论文**：Donald E. Knuth, James H. Morris, Vaughan R. Pratt, *"Fast Pattern Matching in Strings"*, **SIAM Journal on Computing**, 1977
- **为什么引**：「不浪费已匹配信息」思想的鼻祖，next 数组的本质是「失败也是信息」
- **用在哪章**：字符串章·KMP 节
- **链接**：[DOI 10.1137/0206024](https://doi.org/10.1137/0206024)

### 12. Bloom Filter

- **论文**：Burton H. Bloom, *"Space/Time Trade-offs in Hash Coding with Allowable Errors"*, **Communications of the ACM**, 1970
- **为什么引**：「允许少量错误换取巨大空间节省」的工程哲学典范
- **用在哪章**：哈希章·Bloom Filter 节，思想迁移篇
- **链接**：[ACM 全文](https://dl.acm.org/doi/10.1145/362686.362692)

### 13. Skip List

- **论文**：William Pugh, *"Skip Lists: A Probabilistic Alternative to Balanced Trees"*, **Communications of the ACM**, 1990
- **为什么引**：「用概率换平衡树复杂度」的精妙设计，Redis zset 的底层之一
- **用在哪章**：树/有序表章·跳表节
- **链接**：[ACM 全文](https://dl.acm.org/doi/10.1145/78973.78977)

### 14. B-Tree

- **论文**：Rudolf Bayer, Edward M. McCreight, *"Organization and Maintenance of Large Ordered Indices"*, **Acta Informatica**, 1972
- **为什么引**：磁盘 I/O 友好的数据结构鼻祖，数据库索引基石
- **用在哪章**：树章·B 树节
- **链接**：[DOI 10.1007/BF00288683](https://doi.org/10.1007/BF00288683)

### 15. Quicksort

- **论文**：C. A. R. Hoare, *"Quicksort"*, **The Computer Journal**, 1962
- **为什么引**：分治 + 原地排序的典范，理解随机化为何能避免最坏情况
- **用在哪章**：排序章·快速排序节
- **链接**：[DOI 10.1093/comjnl/5.1.10](https://doi.org/10.1093/comjnl/5.1.10)

### 16. Heapsort & Heap 数据结构

- **论文**：J. W. J. Williams, *"Algorithm 232: Heapsort"*, **Communications of the ACM**, 1964
- **为什么引**：堆这种「完全二叉树 + 数组实现」的发明，启发优先队列
- **用在哪章**：堆章·堆排序与优先队列节
- **链接**：[ACM 全文](https://dl.acm.org/doi/10.1145/512274.512284)

---

## 三、🛠️ 工程与 GitHub 项目（投入实际的真实代码佐证）

### 17. TheAlgorithms/Python

- **仓库**：[github.com/TheAlgorithms/Python](https://github.com/TheAlgorithms/Python)
- **简介**：印度程序员 Anup Karottu 创建，用 Python 实现常见算法与数据结构，GitHub 18 万+ stars
- **为什么引**：代码可读性高，覆盖广，适合作为「最小可运行示例」的对照
- **用在哪章**：实践段代码示例的对照来源（不直接抄，对照实现风格）
- **配套**：姊妹项目 [TheAlgorithms/Java](https://github.com/TheAlgorithms/Java)

### 18. doocs/leetcode

- **仓库**：[github.com/doocs/leetcode](https://github.com/doocs/leetcode)
- **简介**：中文社区维护的多语言 LeetCode 题解（Python/Java/C++/Go/TS/Rust），分类清晰
- **为什么引**：题解质量高，按主题分类，是「面试高频题」的工程级对照
- **用在哪章**：实践段 LeetCode 题对照、速查段高频题清单
- **配套站点**：[leetcode.doocs.org](https://leetcode.doocs.org/)

### 19. algorithm-visualizer/algorithm-visualizer

- **仓库**：[github.com/algorithm-visualizer/algorithm-visualizer](https://github.com/algorithm-visualizer/algorithm-visualizer)
- **简介**：交互式算法可视化平台，运行时实时显示数据结构状态
- **为什么引**：算法可视化降低理解门槛，与「神和根本」理念契合
- **用在哪章**：原理段的视觉辅助说明（文中描述可去看可视化）
- **配套站点**：[algorithm-visualizer.org](https://algorithm-visualizer.org/)

### 20. neetcode-gh/leetcode（NeetCode 150）

- **仓库**：[github.com/neetcode-gh/leetcode](https://github.com/neetcode-gh/leetcode)
- **简介**：NeetCode 维护的 150 道按模式分类的 LeetCode 题解
- **为什么引**：「按模式学习」而非「按题目学习」的方法论，与本专栏「神和根本」高度契合
- **用在哪章**：速查段高频模式清单、思想迁移篇
- **配套**：[neetcode.io](https://neetcode.io/)（含视频与路线图）

### 21. labuladong/fucking-algorithm（labuladong 算法小抄）

- **仓库**：[github.com/labuladong/fucking-algorithm](https://github.com/labuladong/fucking-algorithm)
- **简介**：国内著名算法专栏，强调「框架思维」而非具体题目
- **为什么引**：「框架思维」与本专栏「神和根本」理念可对话——都是抽象模式而非记题
- **用在哪章**：经典算法篇的方法论对照
- **配套**：[labuladong.github.io/algo](https://labuladong.github.io/algo/)

### 22. Halfrost/LeetCode-Go

- **仓库**：[github.com/halfrost/LeetCode-Go](https://github.com/halfrost/LeetCode-Go)
- **简介**：Halfrost（霜神）的 Go 版 LeetCode 题解，附详细笔记与图示
- **为什么引**：图示精良，解法严谨，适合作为「原理可视化」的辅助参考
- **用在哪章**：原理段图示对照
- **配套**：[books.halfrost.com/leetcode](https://books.halfrost.com/leetcode/)

### 23. 左程云算法代码合集

- **仓库**：[github.com/algorithmzuo](https://github.com/algorithmzuo)（多仓库总入口）
- **主要仓库**：
  - [coding-for-great-offer](https://github.com/algorithmzuo/coding-for-great-offer) — 大厂面试题代码
  - [class-notes](https://github.com/algorithmzuo/class-notes) — 课件文字与脑图
- **作者**：左程云（左神），《程序员代码面试指南》作者，京东 99%，豆瓣 9.2
- **为什么引**：左神的「对数器」思想与「按数据状况选算法」的工程视角，是中文圈算法教学的标杆
- **用在哪章**：思想迁移篇「按数据状况归约」节、经典算法篇的工程实践对照
- **配套书**：《程序员代码面试指南：IT 名企算法与数据结构题目最优解》（电子工业出版社）

### 24. Striver A2Z DSA Sheet（takeUforward）

- **网站**：[takeuforward.org/strivers-a2z-dsa-course](https://takeuforward.org/strivers-a2z-dsa-course/strivers-a2z-dsa-course-sheet-2/)
- **作者**：Raj Vikramaditya（Striver），印度算法教学博主，YouTube 100 万+ 订阅
- **为什么引**：18 大步骤的 A2Z 学习路线（基础→排序→数组→二分→字符串→链表→栈队列→滑动窗口→堆→贪心→二叉树→BST→图→DP→Trie），是当前最系统化的免费 DSA 路线
- **用在哪章**：大纲参考（[outline.md](./outline.md) 的篇-章结构借鉴其覆盖度）
- **GitHub 解题参考**：[es-amit/Striver-A2Z-DSA-Sheet](https://github.com/es-amit/Striver-A2Z-DSA-Sheet) 等多个社区解题仓库

### 25. donnemartin/system-design-primer（系统设计入门）

- **仓库**：[github.com/donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer)
- **简介**：GitHub 27 万+ stars，系统设计领域最火开源项目
- **为什么引**：算法不脱离系统——本专栏「投入实际」要呼应真实工程的系统约束（缓存/索引/限流都依赖数据结构）
- **用在哪章**：实践段的「工程场景」对照、思想迁移篇

### 26. 《编程珠玑》Programming Pearls

- **作者**：Jon Bentley
- **出版社**：Addison-Wesley，第 2 版 1999（中文版：人民邮电出版社）
- **为什么引**：把算法从抽象概念拉回真实工程问题的典范，每章都是「一个真实问题 + 算法解法」
- **用在哪章**：思想迁移篇、实践段的真实问题对照

### 27. 《算法之美》Algorithms to Live By

- **作者**：Brian Christian, Tom Griffiths
- **出版社**：William Morrow，2016（中文版：中信出版集团）
- **为什么引**：直接把算法思想映射到生活决策（最优停止→找房子；探索 vs 利用→餐厅选择；缓存→工作记忆），是「思想迁移」章节的现成方法论
- **用在哪章**：思想迁移篇的核心方法论参考

---

## 四、🎬 视频专栏（教学直觉辅助，必须有书面文献配套）

> 视频仅作「教学直觉辅助信源」，**不作唯一依据**。引用视频时，必须配套教材或论文作为准确性背书。

### 28. 左程云 B 站算法课

- **频道**：[space.bilibili.com/1899706498](https://space.bilibili.com/1899706498)（马士兵教育-左程云）
- **代表课**：《一周刷爆 LeetCode》《算法与数据结构体系学习班》《大厂算法和数据结构刷题班》
- **为什么引**：左神讲课强调「代码每一行都讲清楚」+「对数器验证」，是中文圈最系统的视频算法课
- **用在哪章**：所有章节的「教学直觉辅助」，配套书为 [23] 左程云代码合集
- **引用方式**：「左程云 B 站课程，[视频标题]」+ 链接

### 29. Abdul Bari YouTube 频道

- **频道**：[youtube.com/@abdulbari](https://www.youtube.com/@abdul_bari)
- **代表内容**：Algorithms Series、Graph Algorithms、Dynamic Programming
- **为什么引**：数学严谨性 + 板书推导，与 CLRS 同源，适合复杂度推导的视觉辅助
- **用在哪章**：原理段的推导辅助，配套 CLRS [1] 为准

### 30. WilliamFiset YouTube 频道

- **频道**：[youtube.com/@WilliamFiset-videos](https://www.youtube.com/@WilliamFiset-videos)
- **代表内容**：Graph Theory、Tree、Advanced Data Structures 系列
- **为什么引**：高级数据结构（线段树/树状数组/并查集/网络流）的可视化教学最强
- **用在哪章**：图论章、树章的高级数据结构节
- **配套 GitHub**：[github.com/williamfiset/Algorithms](https://github.com/williamfiset/Algorithms)（Java 实现）

### 31. NeetCode YouTube 频道

- **频道**：[youtube.com/@NeetCode](https://youtube.com/@NeetCode)
- **代表内容**：NeetCode 150 walkthrough、按 pattern 分类的 LeetCode 题解
- **为什么引**：「按 pattern 学习」而非「按题目学习」的方法论视频化，每个 pattern 给模板代码
- **用在哪章**：经典算法篇的「模式识别」辅助、速查段模板对照

### 32. mycodeschool YouTube 频道

- **频道**：[youtube.com/@mycodeschool](https://www.youtube.com/@mycodeschool)
- **代表内容**：Linked List、Binary Tree、Sorting 等基础数据结构
- **为什么引**：基础数据结构的视觉化讲解最清晰，虽已停更但内容不过时
- **用在哪章**：数据结构篇基础章节（链表/树/排序）的入门辅助

### 33. Tushar Roy - Coding Made Simple

- **频道**：[youtube.com/@tusharroy2525](https://www.youtube.com/@tusharroy2525)
- **代表内容**：Dynamic Programming、Graph 系列
- **为什么引**：DP 与图论的板书推导经典，配合代码逐步演算
- **用在哪章**：DP 章、图论章的推导辅助

### 34. 3Blue1Brown

- **频道**：[youtube.com/@3blue1brown](https://www.youtube.com/@3blue1brown)
- **代表内容**：But what is an algorithm? 等数学/算法可视化
- **为什么引**：Grant Sanderson 的可视化是数学直觉的天花板，适合「神和根本」起手
- **用在哪章**：开篇篇、第一性原理篇的直觉铺垫

---

## 五、🧭 思想迁移与方法论类（思想迁移章节的方法论支撑）

### 35. Polya《How to Solve It》

- **作者**：George Pólya
- **出版社**：Princeton University Press，1945（中文版：上海科技教育出版社）
- **为什么引**：数学解题方法论的鼻祖，「理解问题→制定计划→执行计划→回顾」四步法是算法思维的元方法
- **用在哪章**：开篇篇、第一性原理篇的方法论核心
- **核心贡献**：「启发式思维」「逆向工作」「类比」等通用解题策略

### 36. 《编程珠玑》续编 More Programming Pearls

- **作者**：Jon Bentley
- **出版社**：Addison-Wesley，1988
- **为什么引**：续编更聚焦「算法在真实工程的取舍」，与 [26] 配套
- **用在哪章**：思想迁移篇「算法与工程取舍」节

### 37. 《算法设计手册》The Algorithm Design Manual

- **作者**：Steven S. Skiena
- **出版社**：Springer，第 3 版 2020
- **为什么引**：第二部分「算法问题归类与归约」是「按问题找算法」的实战指南，与本专栏「神和根本」理念契合
- **用在哪章**：思想迁移篇「问题归约」节
- **配套**：[算法问题分类在线版](https://www.algorist.com/algorist.html)

### 38. 《人月神话》

- **作者**：Fred Brooks
- **出版社**：Addison-Wesley，1975（中文版：清华大学出版社）
- **为什么引**：算法之外的工程哲学对照——有些问题不能靠算法解决，只能靠组织
- **用在哪章**：思想迁移篇「算法的边界」节
- **核心引文**：「没有银弹」——算法不是万能的

---

## 六、补充：用户笔记接入位

用户已有学习笔记沉淀在 `book-sources/` 目录，并会陆续提供更多。接入规则：

- 用户笔记标记为「**用户信源**」，与上述公开文献区分
- 用户笔记与公开文献冲突时，以公开文献为准，文中标注争议
- 用户笔记覆盖度高的章节，在 [outline.md](./outline.md) 中标记「用户笔记接入位：是」
- 用户笔记作为提示词的 `user_notes` 字段传入（见 [prompts-draft.md](./prompts-draft.md) 的 orchestrator）

### 已知用户笔记（`book-sources/` 目录）

| 目录 | 内容 | 与算法专栏的关系 |
|---|---|---|
| `book-sources/大厂晋升指南/` | 技术提升方法论、Play&Teach 学习法、能力模型 | **写作风格与学习方法论参考**——尤其「Play 学习法」（模拟场景训练）与「Teach 学习法」（讲给别人听）契合本专栏「投入实际」与「思想迁移」理念 |
| `book-sources/面试现场/` | 技术表达、回答策略、考察标准 | **「技术的水有多深」八维度（应用维度/设计维度）参考**——面试场景的算法问答对照 |
| `book-sources/cctest/` | 校验与 review 脚本 | 工程实现参考，非算法内容 |

**用户笔记的算法相关内容目前较少**（主要是学习方法论与面试表达），算法核心知识仍以公开文献为主。用户后续若提供专门的算法学习笔记，按上述接入规则处理。

---

## 引用优先级链

写作时的引用优先级（高→低）：

1. **论文原典**（[8]-[16]）— 神和根本的源头
2. **教材类**（[1]-[7]、[7-补充]）— 概念准确性的最终依据
3. **工程与 GitHub 项目**（[17]-[27]）— 投入实际的真实代码佐证
4. **思想迁移类**（[35]-[38]）— 思想迁移章节的方法论支撑
5. **视频专栏**（[28]-[34]）— 教学直觉辅助，必须有书面文献配套
6. **用户笔记**（`book-sources/`）— 写作风格与学习方法论参考，辅助信源，不替代公开文献

> 视频与用户笔记永远不能成为唯一信源。每条引用必须可在正文中找到具体出处（论文章节/书页/仓库路径/视频时间戳）。
> **冲突裁决原则**：当 hello-algo [7-补充] 与核心名家书籍（CLRS[1]/Sedgewick[2]/邓俊辉[3]）或论文原典有出入时，以核心名家书籍与论文原典为准。
