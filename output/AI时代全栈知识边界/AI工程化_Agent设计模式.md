---
title: AI时代全栈知识边界·30|Agent设计模式
book: AI时代全栈知识边界
chapter: AI工程化
event: Agent设计模式
sort: 3
chapter_sort: 14
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·30|Agent设计模式

> 前置知识:读过本专栏第 28 章「Prompt 工程基础」与第 29 章「RAG 与向量数据库」、理解 LLM API 的 messages 数组与 Function Calling 输入输出形态、能读 Python 基本语法与字典操作
> 学完你能:① 用一句话说清 Agent(智能体)与普通 Chain 的本质区别 ② 讲清 ReAct / Plan-and-Execute / Reflection / Multi-Agent 四种模式的适用边界 ③ 用 OpenAI Function Calling 写出最小可运行的 Agent 主循环 ④ 用 LangGraph 搭建带状态机与条件边的 Plan-and-Execute 流程 ⑤ 识别幻觉工具、循环调用、错误传递三类失败模式并给出兜底 ⑥ 判断哪些 Agent 工作可交给 AI、哪些必须自己握住

### 一、概念

Agent 的一句话定义:**以 LLM 为决策大脑,辅以工具调用(Tool Use)、记忆(Memory)与规划(Planning),能在多轮循环中自主决定下一步动作、直到达成任务目标的系统**。它不是"更长的 Prompt",而是把 LLM 嵌进一个控制循环里——由模型决定调用什么工具、读取什么记忆、何时停止,运行时负责执行并把结果回喂给模型。

几个核心术语首次出现时对齐中英对照。ReAct(Reasoning and Acting,推理与行动)是 Yao 等人 2022 年提出的范式,让模型交替输出"思考"与"行动"[1]。Function Calling(函数调用)是 OpenAI 等模型厂商提供的结构化接口,模型按预定义 JSON Schema 输出要调用的函数名与参数[2]。Plan-and-Execute(规划与执行)先让一个 Planner 模型拆解任务,再让 Executor 逐步执行[3]。Reflection(反思)指模型对自己上一轮输出做批评并修正[4]。Multi-Agent(多智能体)是多个具备不同角色或工具的 Agent 协作完成任务[5]。Memory 分短期记忆(对话历史)与长期记忆(向量库 + 摘要)。

理解 Agent 的关键,是抓住它与普通 Chain(链)在**控制权**上的差别。Chain 的流程由开发者写死:第一步做什么、第二步做什么、何时结束,都在代码里;Agent 的下一步由模型决定,开发者只给工具集与停止条件。这条差别决定了它适合的任务类型——开放式、多步骤、需要根据中间结果动态调整策略。一个查天气然后总结的固定流程用 Chain 足够;一个"调研某框架并写出可运行示例"的任务,中间可能要搜索、读文档、试错、改代码,流程无法预先写死,才需要 Agent。

### 二、原理

#### 1. LLM 为什么能驱动 Agent

根本机制有两条。第一是**指令理解**:经过指令微调(Instruction Tuning)的 LLM 能解析自然语言任务描述,识别"目标"与"约束",把模糊的人类意图转成可执行的步骤意图。第二是**结构化输出**:Function Calling 强制模型按预定义 JSON Schema 产出函数名与参数,使下游代码能稳定解析。没有结构化输出,Agent 只能靠正则从自由文本里抠参数,模型偶尔把 Action 写成 markdown 代码块,解析立刻崩。

这两条合起来,LLM 才从"对话引擎"变成"决策引擎":它读懂任务,产出可执行的机器指令(函数名 + 参数),由外部运行时执行后再把结果作为新的观测喂回模型,形成闭环。这个闭环就是 Agent 的核心结构,所有模式都是它的变体。

#### 2. ReAct 为什么优于纯 Chain-of-Thought

Chain-of-Thought(思维链,CoT)让模型"一步步想",但思考全程发生在模型内部,无法接触外部世界。一旦问题需要查数据库、调 API、读文件,纯 CoT 就只能编造答案——模型不知道自己不知道,会把缺信息当成有信息一路推下去。

ReAct 的关键在于引入 Observation(观察)这一步:模型思考后输出一个 Action,运行时执行 Action 并把结果作为 Observation 回填,模型基于真实观测继续思考。这条"Thought → Action → Observation → Thought"的循环让模型从"闭卷答题"变成"开卷答题",幻觉率显著下降,因为每一步推理都有了可验证的事实依据。代价同样真实:每一步都要等模型推理,延迟累积;模型可能在错误方向上多走几步才回头,token 消耗高于单次调用。所以 ReAct 适合"信息不全、需要逐步获取"的任务,不适合"一次调用就能答"的简单任务。

#### 3. Multi-Agent 的边界

多智能体协作的收益是"分工":不同 Agent 各自持有不同工具集和系统提示,处理自己擅长的子任务,比如一个负责数据分析、一个负责写报告、一个负责校对。协调成本同样真实存在,主要有三类。

第一是**通信开销**:Agent 之间传递消息要消耗 token,且传递过程中信息会失真——上游 Agent 的口头总结,到下游可能丢了关键细节。第二是**错误传播**:上游 Agent 的错误输出会被下游 Agent 当作事实继续推理,错得越早偏差越大,且很难追溯。第三是**死锁与震荡**:两个 Agent 互相要求对方先行动,或反复修正彼此的输出陷入拉锯。

经验法则是:任务能被一个 Agent 加足够工具搞定时,不要上 Multi-Agent。当任务确实横跨多个领域,且每个领域需要不同的系统提示与工具集时,Multi-Agent 的收益才开始大于协调成本。简单任务硬拆成多 Agent,只会放大延迟与出错面。

#### 4. 记忆与规划的工程约束

记忆机制分两层。短期记忆即当前对话历史,直接放进 messages 数组,受上下文窗口约束——窗口满了就要截断或摘要,否则超出会被拒。长期记忆通常用向量库存储过往交互的摘要化片段,按相似度召回拼进上下文。关键工程点是"摘要时机":不能等窗口爆满才摘要,那样会丢失最近几轮的关键细节;常见的做法是滑动窗口 + 定期摘要,把较早的对话压成一段 summary 放在开头。

规划的核心是任务分解后保留依赖关系,并允许部分回滚。一个写死的线性计划在第二步失败时只能整条重来;好的规划要能识别"哪一步失败、它影响哪些后续步骤",只重做受影响的部分。Plan-and-Execute 模式里,Replanner 节点就是干这件事——根据已完成的步骤与新出现的观测,决定是否调整剩余计划。

### 三、实践

下面三段代码覆盖 Agent 的三种核心形态。第一段是 OpenAI Function Calling 实现的最小 Agent,可直接跑通;第二段是 ReAct 伪代码,展示无 Function Calling 时的 Prompt 引导解析思路;第三段是 LangGraph 实现的 Plan-and-Execute 状态机,展示带条件边的图式编排。

#### 1. 最小 Function Calling Agent(OpenAI SDK)

这段代码实现一个能跑的最小 Agent:它持有两个工具(查天气、算加法),循环调用 OpenAI 的 tools API,直到模型不再请求工具调用为止。

```python
import json
from openai import OpenAI

client = OpenAI()

# 1. 工具的 JSON Schema 定义,喂给模型作为可选项
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市当前天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "两个整数相加",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        },
    },
]

# 2. 工具的真实实现
def get_weather(city: str) -> str:
    return f"{city} 今天晴,25℃"  # 演示用,真实场景应调天气 API

def add(a: int, b: int) -> int:
    return a + b

tool_map = {"get_weather": get_weather, "add": add}

# 3. Agent 主循环:模型决策 -> 运行时执行 -> 结果回喂
def run_agent(user_query: str, max_steps: int = 5):
    messages = [{"role": "user", "content": user_query}]
    for step in range(max_steps):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
        )
        msg = resp.choices[0].message
        messages.append(msg)
        # 模型未请求工具,说明已得出最终答案
        if not msg.tool_calls:
            return msg.content
        # 逐个执行工具调用,结果以 role=tool 回喂
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            result = tool_map[call.function.name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            })
    return "达到最大步数,Agent 未给出最终答案"

print(run_agent("北京天气怎么样?另外 3+5 等于几?"))
```

三个工程要点:max_steps 防止无限循环——这是 Agent 上线必须有的硬上限;tool_call_id 必须回填以维持上下文,缺了模型会报错;工具结果统一转字符串喂回模型,因为 messages 里 content 只接受字符串。生产环境还要加工具异常捕获、单步超时、token 预算统计,这三项机械但必备。

#### 2. ReAct Agent 伪代码

在不支持 Function Calling 的开源模型上,常用 Prompt 引导模型输出固定格式,再用正则解析。下面是 ReAct 范式的伪代码,重点展示"Thought → Action → Observation"循环结构。

```python
import re

PROMPT = """你是一个 ReAct Agent。每轮输出格式严格如下:
Thought: <你的思考>
Action: <工具名>[<参数>]
当你得到最终答案时,输出:
Thought: <思考>
Final Answer: <最终答案>

可用工具:
- search[query]: 搜索
- calc[expression]: 计算

历史:
{history}
用户问题: {question}
"""

def react_agent(question: str, llm, max_iter: int = 6):
    history = ""
    for _ in range(max_iter):
        out = llm(PROMPT.format(history=history, question=question))
        history += out + "\n"
        # 命中 Final Answer 则终止
        m = re.search(r"Final Answer:\s*(.+)", out)
        if m:
            return m.group(1).strip()
        # 解析 Action,执行后回填 Observation
        action = re.search(r"Action:\s*(\w+)\[(.+?)\]", out)
        if not action:
            break  # 格式错误,无法解析
        tool, arg = action.group(1), action.group(2)
        observation = dispatch(tool, arg)  # 真实工具执行
        history += f"Observation: {observation}\n"
    return "未能得出最终答案"
```

伪代码省略了错误处理与工具实现,重点在循环结构。ReAct 的脆弱点在正则解析——模型偶尔会把 Action 包进 markdown 代码块或换行,导致解析失败。生产环境尽量用 Function Calling 而非 Prompt 引导,只有模型不支持时才退回 ReAct,并配合更鲁棒的解析与重试。

#### 3. LangGraph 实现 Plan-and-Execute 状态机

LangGraph 用图(Graph)和状态(State)描述 Agent 流程,天然适合 Plan-and-Execute:Planner 节点产出任务列表,Executor 节点逐个执行,条件边根据进度决定走向 END 还是继续执行。

```python
from typing import TypedDict, List, Tuple
from langgraph.graph import StateGraph, END

class State(TypedDict):
    input: str
    plan: List[str]
    past_steps: List[Tuple[str, str]]  # (步骤, 结果)
    response: str

def planner(state: State) -> dict:
    """首次进入时生成计划;已有计划则跳过(支持重入)。"""
    if state.get("plan"):
        return {}
    plan = llm_call(f"为以下任务制定步骤列表,返回 JSON 数组。任务:{state['input']}")
    return {"plan": plan, "past_steps": []}

def executor(state: State) -> dict:
    """执行下一个未完成的步骤。"""
    done = {s for s, _ in state["past_steps"]}
    for step in state["plan"]:
        if step not in done:
            result = llm_call(f"执行这一步,返回结果:{step}")
            return {"past_steps": state["past_steps"] + [(step, result)]}
    return {}

def should_continue(state: State) -> str:
    """所有步骤完成则结束,否则继续执行。"""
    if len(state["past_steps"]) >= len(state["plan"]):
        return "end"
    return "execute"

# 构建图:plan -> execute -> plan -> execute -> ... -> end
graph = StateGraph(State)
graph.add_node("plan", planner)
graph.add_node("execute", executor)
graph.set_entry_point("plan")
graph.add_conditional_edges(
    "plan",
    should_continue,
    {"execute": "execute", "end": END},
)
graph.add_edge("execute", "plan")  # 回到 plan 触发重规划判断
app = graph.compile()

result = app.invoke({"input": "调研 LangGraph 并写一段示例代码"})
print(result["response"])
```

关键设计有两条。第一,状态在节点间显式传递,每一步可观测、可回放,出问题时能定位到具体节点;第二,条件边让流程能根据状态动态走向 END,而非写死顺序执行。这是 LangGraph 相对线性 Chain 的核心优势——循环、分支、状态持久化都能用图原生表达。生产中可再加一个 Replanner 节点,在每步执行后判断是否需要调整剩余计划,实现真正的"边执行边重规划"。

#### 4. 失败模式与兜底

Agent 有三类高频失败模式,必须在设计阶段就预留兜底。**幻觉工具**:模型编造一个不存在的工具名调用,运行时找不到对应实现就报错——兜底是 tool_map 查不到时返回一条"工具不存在,可用工具为 X"的提示,让模型自我纠正,而非直接抛异常。**循环调用**:模型反复调用同一工具且参数几乎不变,token 烧光不出结果——兜底是 max_steps 硬上限,以及"连续两次相同调用即终止"的去重检查。**错误传递**:工具返回异常信息(如 API 超时),模型把它当成正常结果继续推理——兜底是把异常包装成明确的"该步骤失败,原因 X"的 Observation,并在 Replanner 里加入失败计数,连续失败超阈值就回退或终止。

### 四、速查/自测

#### Agent 模式对照表

| 模式 | 核心结构 | 适用场景 | 主要风险 |
|---|---|---|---|
| ReAct | Thought → Action → Observation 循环 | 需外部信息的开放问答 | 循环调用、解析失败 |
| Plan-and-Execute | 先全局规划再逐步执行 | 步骤多、依赖明确的复杂任务 | 计划僵化、重规划成本高 |
| Reflection | 生成 → 自我批评 → 修正 | 写作、代码生成等质量敏感任务 | 反思也犯错时双重幻觉 |
| Multi-Agent | 多角色分工协作 | 跨领域、需不同工具集的任务 | 通信开销、错误传播 |

#### 框架对照表

| 框架 | 核心抽象 | 适合场景 |
|---|---|---|
| LangChain | Chain + Agent Executor | 快速搭建线性流程 |
| LangGraph | 状态图 + 条件边 | 需循环、分支、状态持久化 |
| AutoGen | 对话式多 Agent | 多 Agent 讨论与代码执行 |
| CrewAI | 角色 + 任务 + 流程 | 业务流程式协作 |
| LlamaIndex Agents | 数据 Agent | 强 RAG 与数据查询导向 |

#### 自测题

1. ReAct 相比纯 CoT 多了哪个关键环节?这个环节解决了什么问题?
2. Function Calling 出现前,Agent 如何从模型输出中提取工具调用?这种方式的主要缺陷是什么?
3. Plan-and-Execute 在 Executor 执行到一半发现计划有误时,有哪两种处理策略?各自代价是什么?
4. Multi-Agent 系统中"错误传播"指什么?给出一种缓解手段。
5. 一个 Agent 在循环中反复调用同一个工具且参数几乎不变,可能的原因有哪些?如何兜底?

### 可交给 AI 的部分

本章"必须掌握"的部分是 **Agent 与 Chain 的控制权差别、ReAct 引入 Observation 的核心原理、Multi-Agent 的协调成本边界、三类失败模式的识别与兜底、记忆摘要时机与规划可回滚的工程约束**——这些是工程师在白板上能讲清、在故障时能定位的内核,不能外包给 AI。

可以放心交给 AI 的有:**Agent 流程编排代码**——用 LangGraph 或 LangChain 搭建状态机骨架、节点函数签名、条件边判断逻辑,模板化程度高,AI 生成后人工核对状态字段与边定义即可;**Prompt 模板**——ReAct 的格式约束、Reflection 的批评提示、Planner 的拆解提示,都可交给 AI 起草,再由人工微调措辞与 few-shot 示例;**工具 JSON Schema 草稿**——根据函数签名生成 Function Calling 的参数描述,属于机械转换工作。

风险提示有三条。第一,**AI 倾向过度复杂化**:让它设计 Agent,它常给你套上五层抽象、三个 Planner、两个 Reviewer,实际任务一个 ReAct 循环就够。务必按真实任务复杂度裁剪,先跑通最小闭环再加节点。第二,**健壮性逻辑需人工补全**:max_steps 上限、工具异常处理、超时熔断、去重检查这些兜底逻辑,AI 写出来的版本通常缺漏,必须人工逐项补齐并测试。第三,**不要让 AI 替你判断"是否需要 Agent"**:很多任务用一次 RAG 或一条 Chain 就够了,Agent 是有延迟和成本代价的方案。架构选型这一步留给人,执行细节交给 AI,这是 Agent 工程在 AI 时代必须握住的知识边界。

## 参考来源

- [1] Shunyu Yao 等:《ReAct: Synergizing Reasoning and Acting in Language Models》2022(ReAct 范式的提出论文, Thought-Action-Observation 循环的原始定义)
- [2] OpenAI 官方文档:Function Calling 与 tools API,https://platform.openai.com/docs/guides/function-calling
- [3] LangChain 官方文档:Plan-and-Execute Agent,https://python.langchain.com/docs/modules/agents/agent_types/plan_and_execute
- [4] Noah Shinn 等:《Reflexion: Language Agents with Verbal Reinforcement Learning》2023(Reflection 自我反思机制的提出论文)
- [5] Qingyun Wu 等:《AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation》2023(多智能体对话式协作框架)
- [6] Chip Huyen:《Designing Machine Learning Systems》O'Reilly 2022 年版(第 9 章在线推理与延迟权衡, Agent 多步调用的工程约束来源)
- [7] LangGraph 官方文档:State Graph 与条件边,https://langchain-ai.github.io/langgraph/
- [8] CrewAI 官方文档:角色、任务与流程,https://docs.crewai.com/
- 本专栏第 28 章「Prompt 工程基础」(Agent 的 system 消息设计、结构化输出约束、Prompt 注入防御均沿用此章原则)
- 本专栏第 29 章「RAG 与向量数据库」(Agent 长期记忆的向量召回与切分策略,直接复用 RAG 的工程范式)
