---
title: AI课·ReAct范式
book: AI大模型学习
chapter: 模块 4｜Agent 与 RAG
event: ReAct范式
created_at: 2026-06-23
source_agents: ['ai-expert']
---

# 第 20 章：ReAct 范式：思考、行动、观察的循环

> 前置知识：学完第 19 章（Agent 心智模型）即可
> 学完你能：①用大白话讲清 ReAct 范式 ②理解 Thought/Action/Observation 循环 ③看懂 Agent 的"思考过程"

## 一、讲清楚：ReAct 是 Agent 的"操作系统"

上一章我们讲了 Agent 的核心公式：Agent = LLM + Planning + Tool use + Memory。但这个公式只告诉你 Agent 有哪些组件，没告诉你这些组件怎么配合运转。

这一章就讲运转方式——具体说，是 Agent 最经典、最广泛使用的一种运转模式：**ReAct**。

ReAct（Reasoning and Acting，推理与行动）是 2022 年提出的一种范式，几乎所有主流 Agent 框架——LangChain、AutoGPT、Coze 的 Bot、OpenAI 的 Function Calling——底层都能看到 ReAct 的影子。可以说，ReAct 是 Agent 的"操作系统"：它定义了 Agent 怎么思考、怎么行动、怎么观察结果、怎么决定下一步。

本章解决三个问题：ReAct 到底是什么、它的 Thought/Action/Observation 循环怎么转、为什么这个循环能让 Agent 真正"干活"。学完之后，你看 Agent 的执行日志（那一堆 Thought、Action、Observation）就能一眼看懂它在干什么。

## 二、看案例：同一个问题，普通模型 vs ReAct Agent

### 案例：北京今天空气质量如何

我们拿一个具体问题来对比——"北京今天空气质量如何"。

**普通模型的回答**（直接问 ChatGPT，不联网）：

> 北京今天的空气质量总体为良到轻度污染，PM2.5 浓度大约在 50-100 之间，建议敏感人群减少户外活动。

听起来挺像回事。但问题来了：它怎么知道的？它没联网，它的训练数据里根本没有"今天"这个概念。这个回答是它根据"北京空气质量一般是什么样"编出来的——本质是猜。

这就是第 09 章讲的幻觉（Hallucination，模型生成看似合理但实际错误的内容）。普通模型遇到"需要实时信息"的问题，只能瞎猜。

**ReAct Agent 的执行过程**：

```
Thought: 用户问北京今天的空气质量。我不知道今天的实时数据，需要调用空气质量 API 查询。
Action: call_air_quality_api(city="北京")
Observation: {"city": "北京", "date": "2026-06-23", "aqi": 85, "level": "良", "pm25": 42}

Thought: 拿到数据了。AQI 85，等级"良"，PM2.5 是 42。这个数据对用户意味着什么？需要解释一下。
Action: finish(answer="北京今天空气质量为良，AQI 85，PM2.5 浓度 42，适合正常户外活动，敏感人群可适当注意。")
Observation: 任务完成。
```

差别一目了然：

- 普通模型：闭着眼睛猜，听起来像真的，但数据是编的。
- ReAct Agent：先承认自己不知道，主动调 API 查，拿到真实数据，再组织语言回答。

这就是 ReAct 的力量——它让 Agent 从"瞎说"变成"查证后再说"。

## 三、拆原理：ReAct 的 Thought/Action/Observation 循环

### 1. ReAct = Reasoning + Acting

ReAct 这个名字是两个词的拼接：Reasoning（推理）+ Acting（行动）。论文出处是「Yao et al., ReAct: Synergizing Reasoning and Acting in Language Models, ICLR, 2023」。

论文的核心思想一句话能讲清：**让 LLM 在"思考"和"行动"之间交替进行，而不是只思考不行动，或只行动不思考**。

在 ReAct 之前，LLM 解决问题有两条主流路线，都有缺陷：

- **纯推理（CoT，思维链）**：让 LLM 把推理过程一步步写出来。问题是它只能基于模型脑子里的知识推理，没法获取新信息。问它"今天天气"，它推理半天还是猜。CoT 是"闭门思考"。
- **纯行动（Acting）**：让 LLM 直接调工具，不写推理过程。问题是模型不知道为什么要调这个工具、调完之后下一步干什么，结果不符合预期时没法调整。纯行动是"无脑执行"。

ReAct 把两者结合起来：**先想清楚要做什么（Reasoning），再去做（Acting），做完看结果（Observation），再想下一步**。这就是 ReAct 的核心循环。

### 2. 三个动作：Thought → Action → Observation

ReAct 的循环由三个动作组成，反复迭代：

**Thought（思考）**：LLM 用自然语言写下"我现在想什么"。比如"用户问北京今天空气质量，我不知道，需要查 API"。Thought 是 LLM 的"内心独白"，让它把推理过程显式化，避免乱来。

**Action（行动）**：LLM 决定"接下来做什么"。Action 通常是调用一个工具，比如 `call_air_quality_api(city="北京")`。Action 必须是预先定义好的工具之一，LLM 不能凭空发明 Action。

**Observation（观察）**：Action 执行后，把结果返回给 LLM。比如 API 返回 `{"aqi": 85, "level": "良"}`。这个结果会成为下一轮 Thought 的输入。

一轮 Thought → Action → Observation 叫一个"step"。Agent 可以连续跑多个 step，直到 LLM 觉得"任务完成了"，输出最终答案，循环结束。

用伪代码表示这个循环：

```python
def react_loop(question, tools, max_steps=10):
    messages = [system_prompt, user_question]
    for step in range(max_steps):
        # 1. LLM 生成 Thought 和 Action
        response = llm.generate(messages)
        thought, action = parse(response)
        print(f"Thought: {thought}")
        print(f"Action: {action}")

        # 2. 判断是否结束
        if action.name == "finish":
            return action.args["answer"]

        # 3. 执行 Action，拿到 Observation
        observation = execute_tool(action.name, action.args)
        print(f"Observation: {observation}")

        # 4. 把这一轮结果加入上下文，进入下一轮
        messages.append(f"Thought: {thought}\nAction: {action}")
        messages.append(f"Observation: {observation}")

    return "达到最大步数，任务未完成。"
```

这段伪代码就是 ReAct 的骨架。所有 ReAct 风格的 Agent 框架，底层都是这个循环。

### 3. 一个完整的 ReAct 执行轨迹

我们用一个稍微复杂点的例子，看 ReAct 完整跑一遍。

问题："对比北京和上海今天的空气质量，哪个更适合户外运动？"

Agent 的执行轨迹：

```
=== Step 1 ===
Thought: 用户要对比北京和上海今天的空气质量。我需要分别查两个城市的实时数据。先查北京。
Action: call_air_quality_api(city="北京")
Observation: {"city": "北京", "aqi": 85, "level": "良", "pm25": 42}

=== Step 2 ===
Thought: 北京 AQI 85，良。现在查上海。
Action: call_air_quality_api(city="上海")
Observation: {"city": "上海", "aqi": 52, "level": "良", "pm25": 28}

=== Step 3 ===
Thought: 两个城市都是"良"，但上海 AQI 52 比北京 85 低，PM2.5 也更低。从空气质量看，上海更适合户外运动。可以给用户一个明确的对比结论了。
Action: finish(answer="北京今天 AQI 85、PM2.5 42；上海 AQI 52、PM2.5 28。两座城市都是良，但上海空气更干净，更适合户外运动。")
Observation: 任务完成。
```

注意几个细节：

- **每一步都有 Thought**：LLM 不是直接调 API，而是先想"为什么要调、调完之后意味着什么"。这让它的行为可解释、可调试。
- **Action 是逐步执行的**：先查北京，拿到结果，再查上海。不是一次性查两个城市——因为 LLM 一次只能生成一个 Action（在标准 ReAct 里）。
- **Observation 影响下一步**：第 1 步拿到北京的数据后，第 2 步的 Thought 才能说"现在查上海"。如果第 1 步 API 报错，第 2 步的 Thought 会变成"北京查不到，换个数据源试试"。
- **最后一步是 finish**：LLM 自己判断"信息够了，可以回答了"，主动调用 finish 工具结束循环。

这个轨迹就是 Agent 的"思考过程"。看懂这个轨迹，你就看懂了所有 ReAct 风格 Agent 在干什么。

### 4. ReAct 和 CoT 的区别：闭门思考 vs 边查边想

很多人会问：ReAct 和 CoT（Chain of Thought，思维链）有什么区别？两者都是让 LLM 把推理过程写出来啊。

区别在于"信息来源"。

**CoT 是闭门思考**：LLM 只用自己脑子里的知识推理，不获取任何外部信息。问它"今天天气"，它只能根据"北京天气一般是什么样"猜。问它"某公司去年营收"，它只能根据训练数据里可能有的财报信息答——可能对，可能错，没法验证。

**ReAct 是边查边想**：LLM 在推理过程中可以调用工具获取实时信息。问"今天天气"，它先调 API 拿到真实数据，再基于数据推理。问"某公司营收"，它先查财报数据库，拿到准确数字，再分析。

打个比方：CoT 像闭卷考试，你只能靠记忆答题；ReAct 像开卷考试，你可以查资料再答题。开卷不一定比闭卷分高（如果你不会查、不会用资料），但至少不会因为记错而瞎编。

这也解释了为什么 ReAct 能减少幻觉——因为它不靠记忆，靠查证。当然，前提是工具返回的数据是准的。如果工具本身有问题（比如 API 返回错误数据），ReAct 也会跟着错。所以 Observation 的质量很关键，后面避坑指南会讲。

### 5. 为什么 ReAct 是 Agent 的"操作系统"

前面说 ReAct 是 Agent 的"操作系统"，这里展开讲讲为什么。

回顾上一章的 Agent 公式：Agent = LLM + Planning + Tool use + Memory。ReAct 恰好把这四个组件串起来：

- **LLM**：每个 Thought 都是 LLM 在推理。
- **Planning**：多步 ReAct 循环本身就是规划——LLM 在每一步决定"接下来做什么"，等于动态生成执行计划。
- **Tool use**：每个 Action 都是调用一个工具。
- **Memory**：前面所有 step 的 Thought/Action/Observation 都拼在上下文里，作为下一步的输入——这就是短期记忆。

ReAct 不是一个"额外的东西"，它是 Agent 公式的具体运转方式。你搭一个 Agent，底层用什么模式让组件配合？最常见的就是 ReAct。

这也是为什么几乎所有 Agent 框架都基于 ReAct：LangChain 的 Agent 默认就是 ReAct 模式，日志里能看到 Thought/Action/Observation；OpenAI 的 Function Calling 虽然接口形式不同（用 function_call 字段而不是文本），但本质还是 ReAct——模型决定调哪个函数、拿到结果、再决定下一步；Coze 的 Bot 底层链路也是 ReAct 风格，只是把 Thought 对用户隐藏了，只展示 Action 和结果。

理解了 ReAct，你就理解了这些框架的"内核"。后面不管学哪个框架，都是在学"它怎么封装 ReAct"——工具怎么定义、循环怎么调度、上下文怎么管理、错误怎么处理。万变不离其宗。

## 四、避坑指南：ReAct 的三个常见坑

### 1. 让 Agent 陷入无限循环

ReAct 是循环，循环就有可能停不下来。

典型表现：Agent 反复调用同一个工具，或者在不同步骤间来回跳，永远不调用 finish。比如：

```
Step 1: Thought: 查北京天气。 Action: weather_api(北京)
Step 2: Thought: 拿到了，再查一次确认。 Action: weather_api(北京)
Step 3: Thought: 再确认一次。 Action: weather_api(北京)
...（无限循环）
```

原因通常是：LLM 不确定结果对不对，反复查；或者 LLM 忘了调用 finish，一直在"准备回答"。

避坑方法：

- **设最大步数**：`max_steps=10` 或更小。达到上限强制结束，返回"任务未完成"。这是兜底。
- **检测重复 Action**：如果连续 3 步调同一个工具、同样的参数，强制中断。
- **在 system prompt 里强调"信息够了就 finish"**：让 LLM 知道何时该停。
- **用更好的 LLM**：弱模型更容易陷入循环，强模型的"停止判断"更准。

### 2. 忽视 Observation 的质量

ReAct 的循环依赖 Observation——如果工具返回的结果是错的或乱的，LLM 的下一步 Thought 就会跟着错。

典型表现：

- 工具返回一堆 HTML 原始代码，LLM 解析不了，下一步 Thought 就乱了。
- 工具返回的数据格式不稳定（有时是 JSON，有时是字符串），LLM 抓不住关键字段。
- 工具返回的数据本身就是错的（比如 API 数据源有问题），LLM 基于错数据推理，结果全错。

避坑方法：

- **工具返回结构化数据**：尽量返回 JSON，字段清晰，不要返回原始 HTML 或长文本。
- **工具做预处理**：比如爬虫工具不要返回整个网页，而是返回"标题 + 正文 + 关键字段"。
- **加数据校验**：工具内部检查返回数据是否合理（比如 AQI 应该是 0-500 的数字），不合理就返回错误而不是脏数据。
- **Observation 要简洁**：太长的 Observation 会撑爆上下文窗口，把关键信息淹没。能截断就截断。

### 3. 让 Agent 一次做太多步

ReAct 循环越多，每一步出错的概率越大，上下文也越长（所有 Thought/Action/Observation 都要拼在上下文里）。一个跑 20 步的 Agent，几乎一定会出问题——要么上下文超限，要么中间某步跑偏，要么 Token 费用爆炸。

避坑方法：

- **任务拆分**：不要让一个 Agent 解决所有问题。把大任务拆成几个小任务，每个 Agent 跑 3-5 步。
- **用子 Agent**：主 Agent 负责拆解和调度，子 Agent 负责执行具体子任务。LangGraph、AutoGen 这些框架就是干这个的。
- **设合理的 max_steps**：简单任务 3-5 步，复杂任务 10 步封顶。超过就重新设计任务结构，而不是放任 Agent 跑下去。
- **定期总结**：每跑几步，让 Agent 把中间结果总结成简短摘要，避免上下文无限膨胀。

## 五、悟本质：ReAct 是"想一步做一步"的交替

讲了这么多，ReAct 的本质可以用一句话概括：**思考与行动的交替——像人一样，想一步做一步，做完再想下一步**。

人解决陌生问题的方式就是这样。你问一个程序员"怎么部署一个网站"，他不会一口气写完所有代码，而是：先想"先确认需求"（Thought），去问用户几个问题（Action），看到用户说"要支持高并发"（Observation），再想"高并发得用负载均衡"（Thought），去查方案（Action），看到 Nginx 和 HAProxy 都行（Observation），再想"选 Nginx，社区大"（Thought），去写配置（Action）……

人不是一次性想清楚所有事，而是边想边做、边做边调整。ReAct 让 LLM 也具备了这种能力。

这个本质有几个推论：

**推论 1：ReAct 适合"不确定"的任务，不适合"确定"的任务。**

如果任务步骤是固定的（比如"每次都按 A→B→C 顺序执行"），用 ReAct 是浪费——直接写脚本就行，不用让 LLM 每步都"想一下"。ReAct 的价值在于"下一步做什么需要根据上一步结果动态决定"，这种不确定性才需要 LLM 来推理。

**推论 2：ReAct 的质量，取决于 Thought 的质量。**

Action 是 Thought 的执行，Observation 是 Action 的结果。如果 Thought 想错了（比如该查 A 却查了 B），后面全错。所以提升 ReAct Agent 的关键之一，是让 LLM 的 Thought 更准——用更强的 LLM、给更清晰的 system prompt、提供更结构化的工具描述。

**推论 3：ReAct 不是唯一范式，但是基础范式。**

除了 ReAct，Agent 还有别的范式：Plan-and-Execute（先规划完再执行）、Tree of Thoughts（树状探索多条思路）、Reflection（执行后反思再重试）。但这些范式要么是 ReAct 的变体，要么在 ReAct 之上叠加。理解 ReAct 是理解所有 Agent 范式的起点。

**推论 4：ReAct 让 Agent 的行为可解释。**

这是 ReAct 一个被低估的优点。因为每一步都有 Thought（自然语言写的推理过程），Agent 的行为是可读、可调试的。出了问题，看一眼 Thought 链路就知道哪步想错了。这比一个黑盒模型直接给答案要可控得多——尤其在企业场景里，"可解释"往往比"准确率"更重要。

## 六、结语

ReAct 让 LLM 在思考和行动之间交替——想一步，做一步，看结果，再想下一步。这个简单的循环，就是 Agent 能"干活"的底层引擎。

## 七、自测三问

**问题 1：用大白话讲清 ReAct 和 CoT 的区别。**

参考答案要点：CoT 是闭门思考，LLM 只用自己脑子里的知识一步步推理，不获取外部信息，遇到需要实时数据的问题只能猜。ReAct 是边查边想，LLM 在推理过程中可以调用工具获取真实数据，基于数据再推理。CoT 像闭卷考试，ReAct 像开卷考试。ReAct 因为能查证，所以能减少幻觉。

**问题 2：ReAct 循环里 Thought、Action、Observation 各自的作用是什么？为什么缺一不可？**

参考答案要点：Thought 是 LLM 的推理过程，决定"接下来做什么、为什么这么做"，让行为可解释、可调试；Action 是具体行动，调用一个工具执行；Observation 是 Action 的结果，作为下一轮 Thought 的输入。缺 Thought，Agent 变成无脑执行，不会调整；缺 Action，Agent 只能想不能做；缺 Observation，Agent 拿不到反馈，无法迭代。三者形成闭环，Agent 才能逐步推进任务。

**问题 3：你搭一个 ReAct Agent，发现它跑了 15 步还没结束，反复调同一个工具。你会怎么排查和修复？**

参考答案要点：①先看 Thought 链路，定位它为什么反复调——是不确定结果对不对，还是忘了 finish，还是工具返回的数据它解析不了；②兜底措施是设 max_steps（比如 10），达到上限强制结束；③加重复 Action 检测，连续 3 步调同样工具同样参数就中断；④检查 Observation 质量，看工具返回的数据是否结构化、是否清晰，必要时改工具让返回数据更易解析；⑤在 system prompt 里强调"信息够了就 finish"，引导 LLM 主动停止；⑥如果任务本身复杂，考虑拆成多个子 Agent，每个跑 3-5 步，避免单 Agent 步数过多。
