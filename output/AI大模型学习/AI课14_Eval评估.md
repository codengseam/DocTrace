---
title: AI课·Eval评估
book: AI大模型学习
chapter: 模块 2｜提示词工程
event: Eval评估
created_at: 2026-06-23
source_agents: ['ai-expert']
---

# 第 14 章：Eval 评估：怎么知道提示词写得好

> 前置知识：学完第 11 章（核心技巧）即可
> 学完你能：①理解为什么需要 Eval ②掌握 3 种轻量 Eval 方法 ③能对自己的提示词做迭代

## 一、讲清楚：靠"感觉"调提示词，是玄学

提示词工程有个反直觉的现象：**你改了一版提示词，感觉更好了，实际可能更差了**。

"感觉更好"通常是因为新提示词在你能想到的几个例子里表现更好。但这几个例子是你自己想的，你下意识会挑新提示词能处理的那些。真正的盲区——你没试到的场景——可能恰恰是新提示词搞砸的。

这就是为什么需要 Eval（Evaluation，评估，用一套固定的、可量化的方法测出提示词在不同输入下的表现）：把"感觉"变成"分数"。

第 11 章讲了提示词的核心技巧（角色设定、few-shot、思维链等）。这一章讲的是：技巧用上去之后，怎么知道真的有效。没有 Eval 的提示词工程，就像不看仪表盘开车——你以为在加速，可能在掉沟里。

本章只讲轻量方法，不涉及大模型评测平台（OpenAI Evals、Promptfoo、LangSmith 这些工具能做规模化评测，但学习曲线陡，不适合个人开发者起步）。先掌握三种最轻量的方法，能解决 80% 的日常需求。

## 二、看案例：一版"感觉更好"的客服提示词，跑分反而更差

某电商团队有一个客服 Bot，提示词 v1 长这样：

```
你是一位电商客服，负责回答用户关于订单、物流、退换货的问题。请用中文，礼貌简洁。
```

产品经理觉得回答太干巴，让运营改一版。运营加了 few-shot 示例和情绪安抚，提示词 v2：

```
你是一位电商客服，负责回答用户关于订单、物流、退换货的问题。请用中文，礼貌简洁。
回答时先安抚情绪，再给解决方案。

示例：
用户：我的快递三天没动了，怎么办？
客服：非常抱歉给您带来困扰，理解您的着急。我马上帮您查询物流，请稍等。建议您先核对单号是否正确，如果单号无误，我会为您催办物流。
```

v2 上线后，产品经理自己试了几个问题，感觉"明显更专业了"。运营也试，感觉"更有人情味了"。于是全量推送。

三天后数据出来：用户满意度从 78% 掉到 71%，转人工率从 12% 升到 19%。

为什么？因为 v2 的示例里"先安抚情绪再给方案"被模型学过头了——遇到任何问题都先来一段"非常抱歉给您带来困扰"，包括"我的订单号是多少"这种根本不需要安抚的问题。用户问个简单事实，Bot 先道歉 30 字，用户烦得直接转人工。

产品经理自己试的几个问题恰好都是"需要安抚"的场景，所以感觉好；真实流量里大量是"不需要安抚"的场景，v2 全搞砸了。

如果上线前做过 Eval——准备 20 个覆盖各类场景的测试用例，跑一遍打分——这个回归本可以在上线前被发现。

## 三、上手步骤：三种轻量 Eval 方法

### 方法 1：人工评估（适合小批量，最可靠）

最朴素也最可靠的方法：人准备一批测试用例，人打分。

**步骤 1：准备测试集**

挑 10-20 个测试用例，覆盖典型场景、边界场景、对抗场景。比如客服 Bot 的测试集：

| 编号 | 类型 | 用户输入 | 期望回答要点 |
|---|---|---|---|
| T01 | 典型 | 我的订单到哪了？ | 引导提供订单号 |
| T02 | 典型 | 怎么退货？ | 给退货流程 |
| T03 | 边界 | 订单号是多少？ | 直接问订单号，不要安抚 |
| T04 | 边界 | 你们几点下班？ | 给营业时间 |
| T05 | 对抗 | 你是机器人吗？ | 透明承认 + 引导回业务 |
| T06 | 对抗 | 我要投诉你 | 不对抗，给投诉渠道 |

关键是要覆盖"对抗场景"和"边界场景"——这些是最容易出问题的，也是人最容易漏掉的场景。

**步骤 2：定义打分维度**

不要只打一个总分，要分维度。客服 Bot 常见的维度：

- 准确性（1-5）：回答是否正确？
- 相关性（1-5）：是否切题？
- 礼貌度（1-5）：语气是否合适？
- 简洁度（1-5）：是否啰嗦？
- 安全性（1-5）：有没有不当承诺？

每个维度 1-5 分，每个测试用例打 5 个分。

**步骤 3：跑两版提示词，对比打分**

把同一批测试用例分别喂给 v1 和 v2，把回答打乱顺序（避免打分时知道是哪版产生偏见），人工打分。

汇总时算每个维度的平均分。如果 v2 在"礼貌度"上比 v1 高 0.8 分，但在"简洁度"上低 1.5 分，你就知道 v2 的问题在哪——和真实数据反映的"啰嗦"完全对得上。

**适用范围**：测试集 10-20 条，一个人半天能跑完。超过 50 条就太耗时，该上自动化了。

### 方法 2：用 AI 评估 AI（LLM-as-a-Judge）

人工评估可靠但慢。一个折中方案：让另一个模型当裁判。

这个思路来自 MT-Bench 和 Chatbot Arena 的研究：用 GPT-4 级别的模型给被测模型的回答打分，和人类裁判的相关性可以达到 0.8 以上。「Zheng et al., Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena, NeurIPS, 2023」

**步骤 1：准备裁判提示词**

```
你是一位严格的客服质量评估员。请对下面这个客服回答打分。

【用户问题】
{user_input}

【客服回答】
{bot_response}

【期望回答要点】
{expected_points}

请按以下维度打分（1-5 分）：
- 准确性：是否覆盖了期望要点？
- 礼貌度：语气是否合适？
- 简洁度：是否啰嗦？

输出 JSON：
{
  "accuracy": 分数,
  "politeness": 分数,
  "conciseness": 分数,
  "reason": "一句话说明扣分原因"
}
```

**步骤 2：批量调用裁判模型**

把测试集里每一条 `{user_input, bot_response, expected_points}` 喂给裁判模型，拿到 JSON 结果。

用 Python 写个循环就能跑：

```python
import anthropic
import json

client = anthropic.Anthropic(api_key="your-api-key")

def judge(user_input, bot_response, expected_points):
    prompt = f"""你是一位严格的客服质量评估员。
    用户问题：{user_input}
    客服回答：{bot_response}
    期望要点：{expected_points}
    请按准确性、礼貌度、简洁度打 1-5 分，输出 JSON。"""
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.content[0].text)

# test_cases 是测试集列表
results = [judge(c["input"], c["response"], c["expected"]) for c in test_cases]
```

**步骤 3：汇总分数**

把所有测试用例的分数取平均，对比 v1 和 v2。

**关键细节**：

- 裁判模型要比被测模型强。被测是 GPT-3.5，裁判用 GPT-4；被测是 Claude Haiku，裁判用 Claude Sonnet。让弱模型评强模型不可靠。
- 裁判温度设 0，保证打分稳定。
- 裁判也会有自己的偏见（比如偏好长回答、偏好结构化回答）。重要决策建议人工抽检 20% 的裁判结果，校准偏差。
- 同一个模型不能既当被测又当裁判——它会偏好自己的回答。

**适用范围**：测试集 20-200 条，自动化跑完，适合迭代期频繁评估。

### 方法 3：自动化指标（适合有标准答案的任务）

如果任务有明确的"标准答案"，可以用程序化指标，连裁判模型都不需要。

**精确匹配（Exact Match）**：回答和标准答案完全一致才算对。适合分类、抽取这类任务。

```python
def exact_match(prediction, ground_truth):
    return 1.0 if prediction.strip() == ground_truth.strip() else 0.0
```

**包含检查（Contains）**：回答里包含某个关键词就算对。适合"必须提到 XX"这类规则。

```python
def contains(prediction, keyword):
    return 1.0 if keyword in prediction else 0.0
```

**BLEU / ROUGE**：机器翻译和文本摘要的经典指标，衡量生成文本和参考文本的 n-gram 重合度。一句话带过——这两个指标在 LLM 时代用得少了，因为它们只看表面词重合，不看语义。模型换个说法表达同样的意思，BLEU 就给低分。了解即可，日常 Eval 不推荐作为主指标。

自动化指标的最大优势是**便宜、快、可重复**。劣势是**只覆盖有标准答案的任务**——客服对话、创意写作这类没有标准答案的任务，自动化指标无能为力，还得回到方法 1 和方法 2。

### 在 Coze / Claude 里搭一个简单 Eval 流程

**Coze**：

- Coze 的"工作流"功能可以串起"测试集 → 被测 Bot → 裁判 Bot → 汇总"的流水线。
- 测试集用 Coze 的"数据集"功能上传（CSV 格式，列：input, expected）。
- 被测 Bot 和裁判 Bot 都是 Coze 里的 Bot，工作流里串联调用。
- 汇总结果用 Coze 的"代码节点"算平均分，输出到表格。

**Claude API**：

- 用 Python 脚本串起来：读测试集 → 调被测模型 → 调裁判模型 → 算分 → 输出报告。
- 不需要任何平台，一个 `.py` 文件就能跑。适合个人开发者起步。
- 进阶可以用 Promptfoo 或 LangSmith 这类工具，但学习曲线陡，建议先把裸脚本跑通再考虑。

一个最小可跑的 Eval 脚本结构：

```python
# eval.py
import anthropic
import json

client = anthropic.Anthropic()

def run_target(prompt, user_input):
    """被测模型"""
    r = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        temperature=0.3,
        system=prompt,
        messages=[{"role": "user", "content": user_input}]
    )
    return r.content[0].text

def run_judge(user_input, response, expected):
    """裁判模型"""
    r = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        temperature=0,
        messages=[{"role": "user", "content": f"""
        用户问题：{user_input}
        回答：{response}
        期望：{expected}
        按准确性、礼貌度、简洁度打 1-5 分，输出 JSON。
        """}]
    )
    return json.loads(r.content[0].text)

def evaluate(prompt, test_cases):
    results = []
    for c in test_cases:
        resp = run_target(prompt, c["input"])
        scores = run_judge(c["input"], resp, c["expected"])
        results.append({"input": c["input"], "response": resp, "scores": scores})
    return results

if __name__ == "__main__":
    test_cases = json.load(open("test_cases.json"))
    prompt_v1 = open("prompt_v1.txt").read()
    prompt_v2 = open("prompt_v2.txt").read()

    results_v1 = evaluate(prompt_v1, test_cases)
    results_v2 = evaluate(prompt_v2, test_cases)

    # 算平均分对比（汇总代码略）
```

跑一次就知道 v2 是真的更好还是只是"感觉更好"。

## 四、验收标准

学完这一章，你应该能做到下面两件事。

1. **能为一个提示词准备至少 10 个测试用例**。测试集要覆盖典型、边界、对抗三类场景，每个用例有明确的"期望回答要点"。
2. **能用 LLM-as-a-Judge 跑一次完整评估**。用 Python 脚本调被测模型 + 裁判模型，对两版提示词打分对比，输出分数差异。

如果两项都过，你就有了自己的第一个 Eval 流程。后续每次改提示词，都先跑 Eval 再决定上不上线——这是从"业余调 prompt"到"专业提示词工程"的分水岭。

## 五、悟本质：Eval 的本质是"把主观感受变成客观分数"

提示词工程最大的敌人不是"提示词写得差"，而是"不知道写得差不差"。

没有 Eval 时，你对提示词的判断完全靠感觉。感觉是不可靠的——它会受你当时心情、你试的几个例子、你对新版本的期待影响。同一个提示词，你今天觉得好，明天可能觉得差。

Eval 做的事情，是把这种主观感受"外化"成客观分数：

- 测试集是固定的，不能挑软柿子捏。
- 打分维度是固定的，不能凭印象打。
- 跑分流程是自动的，不能人为调整。

一旦感受变成分数，几个推论就清楚了：

**推论 1：Eval 让迭代有了方向。**

没有 Eval，改提示词是"瞎改"——你不知道改了之后是变好还是变差。有 Eval，每次改动都对应一个分数变化，你能看到"加 few-shot 让礼貌度涨了 0.5 分，但简洁度掉了 1.2 分"，下一步该补什么一目了然。

**推论 2：Eval 让团队协作有了共同语言。**

产品经理说"这版感觉不行"，运营说"我觉得挺好"——这种争论没有 Eval 永远吵不完。有 Eval，大家看分数："v2 简洁度比 v1 低 1.5 分，主要扣在'过度安抚'上，要不要把示例里的安抚话术删掉？"讨论立刻从主观变客观。

**推论 3：Eval 本身也需要被 Eval。**

测试集挑得不好，打分维度定得不对，裁判模型有偏见——Eval 自己也会出错。所以 Eval 不是"绝对真理"，它是"比感觉更可靠的参考"。重要决策建议 Eval + 人工抽检双保险。

**推论 4：没有 Eval 的提示词工程是玄学。**

这一条是给所有"凭感觉调 prompt"的人的提醒。如果你改了 10 版提示词，没有一版跑过 Eval，那这 10 版之间的差异，可能只是你的错觉。

## 六、结语

Eval 不是评估提示词好坏的工具，是评估你自己判断力的工具。先把它跑起来，再谈"提示词写得好不好"。
