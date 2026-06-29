---
title: 第 22 章　全栈现状：从 Vibe Coding 到 Agentic Engineering
book: AI时代职业课
chapter: 全栈
event: 现状从VibeCoding到AgenticEngineering
sort: 1
chapter_sort: 4
created_at: 2026-06-29
source_agents:
- ai-expert
---

# 第 22 章　全栈现状：从 Vibe Coding 到 Agentic Engineering

> **边界声明**：本篇为"全栈章"第一篇，聚焦当下软件开发范式的现状判断——Vibe Coding 正在向 Agentic Engineering 演进，2025 年 12 月是关键拐点。具体的学习路径、技能优先级重塑见第 23 篇"学习"篇，超级个体角色见第 24 篇"进阶"篇，段位体系见第 25 篇"段位"篇。本专栏与《AI 大模型学习》中"程序员转型"系列有明确分工：后者聚焦"程序员怎么用 Cursor 等工具提效"，本专栏聚焦"Agentic Engineering 段位体系 + 超级个体角色"。

## 一、Karpathy 的"被甩在身后"时刻

2026 年 5 月 1 日，Andrej Karpathy 在 Sequoia Ascent 2026 大会炉边谈话中讲了一段后来被反复引用的话。他自己形容这是一种从未有过的体验——不是 AI 不够好，而是 AI 好得太快，快到他这样的资深工程师都感到措手不及：

> "I have never felt more behind as a programmer... the default workflow changed. For much of 2025, tools like Claude Code, Codex, and Cursor-like agents were useful but still required frequent correction. Around December 2025, I felt a step change: the generated chunks got larger, more coherent, and more reliable."
>
> （节选自 Karpathy《Sequoia Ascent 2026 summary》，2026-05-01，karpathy.bearblog.dev/sequoia-ascent-2026/，省略中间过渡句）

来源：karpathy.bearblog.dev/sequoia-ascent-2026/

这段话的核心信息有三层。第一，"the default workflow changed"——默认工作流变了，不再是"AI 辅助、人主导"，而是 AI 主导、人审查。第二，2025 年大部分时间里，Claude Code、Codex、Cursor 这类工具确实有用，但需要频繁纠错（frequent correction），人还得盯得很紧。第三，"Around December 2025, I felt a step change"——大约在 2025 年 12 月，他感到一次阶跃式变化：生成的代码块更大、更连贯、更可靠。

Karpathy 还给出了一个被广泛引用的判断：

> "LLMs are no longer just chatbots or autocomplete. They are becoming a new programmable layer for digital work."

来源：karpathy.bearblog.dev/sequoia-ascent-2026/

这句话意味着 LLM 不再只是聊天机器人或自动补全工具，而正在成为"数字工作的新可编程层"。这与他对 Software 3.0 的论述一脉相承。

## 二、Software 1.0 / 2.0 / 3.0 框架

理解 Agentic Engineering 的现状，绕不开 Karpathy 提出的三段式框架。这是一个把过去三十年软件工程演进压缩成三层的简化模型，但对看清"我们现在站在哪里"非常有效。

**Software 1.0：人类写显式代码。** 程序员用 if/else、循环、函数把逻辑显式写出来，每一行都是人脑想清楚后落成代码。这是过去几十年软件工程的默认形态，程序员的核心能力是"把模糊需求翻译成确定逻辑"。

**Software 2.0：数据集 + 神经网络 + 权重。** 模型即程序。程序员不再写显式逻辑，而是提供数据集，让神经网络通过训练学到权重。"程序"变成了一个由亿级参数组成的张量。这一阶段，核心能力从"写逻辑"转向"准备数据 + 设计训练目标"。

**Software 3.0：用 prompt / context / tools / memory 编程 LLM。** 这是 Karpathy 在 2025 年正式提出的概念。在 Software 3.0 里，编程的对象不再是 CPU，也不是 GPU 上的张量，而是 LLM 本身。你用 prompt 描述意图、用 context 提供背景、用 tools 给 LLM 接入外部能力、用 memory 让它跨会话保持状态。Karpathy 有一个极具传播力的类比：

> 上下文窗口是新 RAM。

这句话的含义是：在传统计算里，RAM 决定了进程能装下多少数据；在 Software 3.0 里，上下文窗口决定了 LLM 一次能"看见"多少信息、做多复杂的事。上下文从 128K 涨到 2M+，本质上就是"AI 程序的内存"在扩容，能处理的任务复杂度也水涨船高。

## 三、Macro Action：Agentic Engineering 的核心概念

Karpathy 在 Sequoia Ascent 谈话中提出了一个对工程师影响深远的概念——**macro action（宏观动作）**。这是理解 Agentic Engineering 与 Vibe Coding 本质区别的关键。

在传统的 AI 编程工具里，AI 的作用方式是"微观动作"：一次对话、一轮补全、一个函数的生成。开发者每写一段就需要下一轮提示，AI 像一个反应迅速但视野狭窄的助手。

Agentic Engineering 的核心，是把这种"一次对话一轮"的微观动作，升级为"一次完成一个大任务"的宏观动作。Karpathy 列举了 macro action 的典型形态：

- **实现一个完整功能**：不是补全一个函数，而是从需求理解到代码落地一次完成
- **重构一个子系统**：跨多个文件、多个模块的系统性重构
- **调研一个库**：自主检索文档、读源码、给出对比结论
- **部署一个服务**：从构建到上线全流程
- **写测试套件**：理解代码意图后批量生成有覆盖率的测试
- **比较多个方案**：自主跑实验、给出取舍建议

来源：karpathy.bearblog.dev/sequoia-ascent-2026/

从微观到宏观的跃迁，背后是模型能力的提升（生成更连贯）、上下文窗口的扩大（能装下整个项目）、工具调用的成熟（能自主读写文件、执行命令）。这三件事在 2025 年 12 月前后同时到位，于是 Karpathy 感受到了那次 step change。

## 四、Vibe Coding vs Agentic Engineering：Floor 与 Ceiling

要讲清现状，必须先厘清两个常被混用的概念。

**Vibe Coding（氛围编程）** 是 Karpathy 在 2025 年 2 月提出的说法，原意是"完全顺着感觉走、完全接受 AI 生成的代码、不去细看"的编程方式。他当时半玩笑地说这是"给周末项目写的"。但这个概念迅速破圈，被广泛用来指代"用自然语言描述意图，让 AI 生成可运行代码"这一类工作方式。

**Agentic Engineering（智能体工程）** 是 2025 年底到 2026 年初逐渐成型的范式，指开发者通过编排 Agent——给 LLM 配上下文、工具、记忆、目标——让 Agent 在更长的时间尺度上自主完成 macro action。

两者不是替代关系，而是分工关系。一个被反复引用的判断是（此为 wakatchi.dev 对 Karpathy 观点的解读提炼，非 Karpathy 原话）：

> "Vibe coding 抬高下限（floor），Agentic engineering 抬高上限（ceiling）。"

来源：wakatchi.dev 2026 wakatchi.dev/karpathy-agentic-engineering-software-3/

这句话的内涵值得展开。Vibe Coding 的价值在于**降低门槛**：哪怕是不太懂代码的人，也能用自然语言"驱动"出一个能跑的小工具、一个 demo、一个原型。它把"能不能写出第一版"这个下限拉高了。

Agentic Engineering 的价值在于**拉升上限**：让资深工程师借助 Agent 团队，完成原本需要多人协作才能搞定的事情——重构一个百万行级别的子系统、为整个项目补齐测试套件、并行调研五个候选库。它把"一个人能干多大的事"这个上限推高了。

理解这一点非常重要：**Agentic Engineering 不是 Vibe Coding 的"进阶版"**，而是两条不同的能力曲线。Vibe Coding 解决"从 0 到 1"，Agentic Engineering 解决"从 1 到 N"。一个完整的现代开发者，往往两者并用：用 Vibe Coding 快速验证想法，用 Agentic Engineering 系统化推进工程。

## 五、2025 年 12 月：Agentic 拐点

Karpathy 反复强调的那个时间点——"Around December 2025"——值得单独拎出来看。Karpathy 在文中将 2025 年 12 月称为"agentic 拐点"（来源：karpathy.bearblog.dev/sequoia-ascent-2026/，2026-05-01）。

为什么是 2025 年 12 月？从工程视角看，至少三件事在这一时期同时成熟：

**第一，模型本身的"长程连贯性"到位了。** 2025 年上半年，AI 生成的代码块往往在 50-200 行内连贯，再长就开始漂移、自相矛盾。到 2025 年底，主流模型已经能在数千行尺度上保持意图一致，生成的 chunk "larger, more coherent, more reliable"。

**第二，上下文窗口从 128K 跃升到 2M+。** 来源：掘金 juejin.cn/post/7639199528151449651。128K 大概能装下一个中等项目的核心文件，2M+ 则意味着 Agent 可以"一眼看穿"大型代码库。上下文是 Agent 的"工作记忆"，工作记忆一扩，能处理的任务复杂度就指数级上升。

**第三，工具调用与 Agent 框架标准化。** 到 2025 年底，Function Call、MCP（Model Context Protocol）、各类 Agent 编排框架趋于稳定，Agent 不再是"调一调 API"，而是有了相对成熟的工作骨架。这三件事叠加，让 macro action 从"偶尔能成"变成"稳定能成"，于是拐点出现。

## 六、行业转向：从模型中心到上下文中心

拐点之后，行业的注意力也在迁移。占冰强在 2026 年初提出了一个被广泛引用的判断：

> "2026 年是 Vibe Coding 创作者经济元年。"

来源：CSDN 占冰强 2026-02-06 libin9ioak.blog.csdn.net/article/details/157812498

这句话指向的是另一个维度——当 Vibe Coding 把"写出能跑的代码"门槛降到足够低，会催生出一批"以创意而非编码能力为核心"的创作者。他们不需要是传统意义上的程序员，但能借助 AI 把想法变成产品。

更值得技术从业者关注的是占冰强的另一个判断：**行业正从"模型中心"转向"上下文中心"。**

模型中心时代的核心问题是"哪个模型最强"，大家盯着 benchmark、参数量、跑分。上下文中心时代的核心问题变成了"如何为 LLM 构造最有价值的上下文"——包括哪些文档要喂进去、哪些工具要接进来、哪些历史会话要保留、哪些记忆要持久化。模型能力趋同后，决定 Agent 表现的，是上下文工程做得有多扎实。

这个转向对工程师意味着什么？意味着**懂模型的人很多，懂上下文工程的人稀缺**。如何为 Agent 设计一个高信噪比的上下文，如何让 Agent 在长任务里不"失忆"、不"跑偏"，正在成为新的核心技能。这也是本专栏第 23 篇"学习"篇要重点展开的内容。

## 七、现状判断：三种工程师的处境

把上面这些信号拼在一起，可以做一个相对清晰的现状判断。当下工程师大致分三种处境：

**处境一：还在 Software 1.0 思维里的人。** 他们把 AI 工具当作"高级补全"，偶尔用一下 Copilot 写几行，主体工作流仍是手写 + 搜索 + Stack Overflow。对这部分人，2025 年 12 月的拐点几乎是"无感"的，因为他们没有触及 macro action 的可能性。他们的风险最大——不是因为会被 AI 直接替代，而是因为同行正在用新范式把产能拉到一个他们追不上的量级。

**处境二：停留在 Vibe Coding 层的人。** 他们能用自然语言生成完整功能，能快速做原型，但一旦任务复杂度上来——需要跨模块重构、需要长程一致性、需要工程化部署——就开始失速。他们的下限被 Vibe Coding 抬高了，但天花板还没被 Agentic Engineering 撑起来。

**处境三：已经摸到 Agentic Engineering 门槛的人。** 他们让 Agent 自主完成跨文件任务，做编排、做审查、做决策。他们的产出不再受限于"自己敲键盘的速度"，而受限于"判断力和编排能力"。这是当下最稀缺也最有杠杆的位置。

本专栏"全栈章"接下来的三篇，正是为这三种处境分别给出路径：学习篇讲如何从 Vibe Coding 走向 Agentic Engineering，进阶篇讲如何成为"超级个体"四大角色，段位篇讲从 L1 码农到 L5 智能体编排者的完整跃迁地图。

## 八、本篇小结

把现状一句话压缩：**2025 年 12 月是 Agentic 拐点，Vibe Coding 抬高下限、Agentic Engineering 抬高上限，行业从模型中心转向上下文中心，Software 3.0 把 LLM 变成新的可编程层。**

对在岗进阶者来说，关键不是"要不要用 AI"——这个选择窗口已经关闭——而是"在哪个段位用 AI、用得有多深"。这正是后续篇章要回答的问题。

---

> 信息截止：2026-06
