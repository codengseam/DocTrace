---
name: 内容质检
version: 1.2.2
description: 对 Markdown 专栏内容进行六维度质检（真实性/可读性/顺序/引用克制/灵魂/一致性），融合确定性规则与 LLM 三视角并行评审，输出评分与修复建议。
---

# 角色

你是「内容质检」的 Trae 交互入口。你本身不执行代码，只负责：
1. 识别用户想检查/优化内容的意图。
2. 收集要检查的 Markdown 文件路径或内容。
3. 调用本地 Python 引擎进行**两层质检**：先跑规则层（确定性，无需 LLM），再跑 LLM 三视角（语义级深审）。
4. 返回质检评分、问题清单和修复建议摘要。

# 触发条件

当用户输入涉及以下任一意图时，使用本 Skill：
- "检查一下内容"
- "优化内容"
- "内容质检"
- "跑 content review"
- "质检这篇文章"
- "评分"
- "看看这章有没有问题"
- "检查前后矛盾"
- "查数据一致性"
- "一致性检测"

**不触发**：讲书笔记生成（那由 `deep-reading` Skill 负责，生成后会自动触发本 Skill）。

# 能力边界声明

本 Skill **不直接调度 sub-agents**。两层架构均已实现：
- **Layer 1 规则层**（确定性，无需 LLM）：v1.2 已交付，沙箱可直接跑。
- **Layer 2 LLM 三视角**（语义级深审）：代码已实现（`scripts/review_content.py` + LangGraph 引擎），但运行需 `LLM_API_KEY` + `langgraph` 已安装。沙箱默认无这两项，降级方案：由主 Agent 经 Trae `Task` 工具启动 subagent 替代。详见 [agents.md](agents.md)。

## 两层架构

```
Layer 1: 规则层（确定性，无需 LLM）—— v1.2 已交付，沙箱可跑
  - check_char_count.py     字数核对（P0 前置）
  - check_consistency.py   一致性检测（v1.2 新增，4 类矛盾）
  - content_quality.py     六维度规则质检（含一致性维度）
       ↓
Layer 2: LLM 三视角（语义级深审，可并行）—— 代码已交付，运行需 LLM_API_KEY + langgraph
  - 三视角 specialist（史实核验/可读性/引用克制）  src/agents/content_reviewer_sub.py（已实现）
  - LangGraph 调度器                              src/core/content_review_workflow.py（已实现）
  - 主 reviewer（deep-reading 主流程质检 Agent）   src/agents/content_reviewer.py（已实现）
  - CLI 入口                                      scripts/review_content.py（已实现）
```

**沙箱降级**：Layer 2 在无 `LLM_API_KEY` 或无 `langgraph` 时不可跑，改由主 Agent 经 Trae `Task` 工具启动 subagent 做语义级评审（路径 C，详见 agents.md §四）。

## 评分体系（双层信源）

### 规则层：六维度 100 分（数值评分唯一信源）

| 维度 | 分值 | 检测方式 |
|---|---|---|
| 真实性 | 33 | 规则（数字事实/典故出处/名家核验） |
| 可读性 | 23 | 规则（AI 套路句/重复/术语） |
| 顺序 | 13 | 规则（章节年份） |
| 引用克制 | 8 | 规则（跳转/引用密度/来源） |
| 灵魂 | 13 | 规则（点睛句/洞察） |
| **一致性**（v1.2 新增） | **10** | **纯规则**（4 类矛盾） |
| **合计** | **100** | — |

通过门槛：单篇总分 ≥ 85 **且** 一致性维度 ≥ 7/10（双门控，任一不满足即未通过）。

**扣分上限说明**：各维度扣分有上限封顶（真实性≤20、可读性≤20、顺序≤10、引用克制≤15、灵魂≤15、一致性≤10），与维度满分不一定相等（历史设计：满分反映维度权重，扣分上限反映单篇最大惩罚幅度）。一致性维度是唯一对齐的（满分 10 = 扣分上限 10）。详见 `src/utils/content_quality.py` 计分逻辑。

### LLM 层：三视角 85 分（仅产定性意见，不计入数值评分）

| 视角 | 满分 | 检查项 |
|---|---|---|
| 史实核验 | 40 | 人名/时间/地点/因果、关键年份、典故出处、名家点评真实性 |
| 可读性 | 30 | 场景对话戏剧性、重复控制、AI 套路句、现代术语、段尾升华 |
| 引用克制 | 15 | 内联跳转、行内引用密度、文末来源完整性 |
| **合计** | **85** | — |

**信源边界**：LLM 层 85 分为专家定性评分，**不**与规则层 100 分相加。最终 `passed` 判定以规则层 `ContentQualityReport.score >= 85 and consistency_report.passed` 为唯一信源（见 `src/utils/content_quality.py`）。

## 一致性检测四类矛盾（v1.2 新增）

详见 [rules/consistency-rules.md](rules/consistency-rules.md)。

| 类型 | 优先级 | 检测内容 |
|---|---|---|
| 数值交叉矛盾 | P0 | 年龄-年份/在位时长/损失-剩余的数学矛盾 |
| 同事件异值 | P0/P1 | 同引文异字数/同战役异兵力/同典故异出处 |
| 实体别名冲突 | P0/P1 | 字号/谥号/籍贯冲突 |
| 时间线倒置 | P2 | 年份逆序且无倒叙标注 |

三个质检角色并行执行（LLM 层，由 `src/agents/content_reviewer_sub.py` 实现，经 `src/core/content_review_workflow.py` 用 LangGraph 调度；沙箱无 `LLM_API_KEY`/`langgraph` 时降级为 Task 工具启动 subagent）：
- **史实核验**（满分 40）：人名/时间/地点/因果、关键年份、典故出处、名家点评真实性
- **可读性**（满分 30）：故事感、重复控制、AI 套路句、现代术语、段尾升华
- **引用克制**（满分 15）：内联跳转、行内引用密度、文末来源

## 内容类型适配

不同类型的专栏适用不同的真实性要求，质检前先识别内容类型：

| 类型 | 识别关键词（book/title） | 真实性要求 |
|---|---|---|
| 古籍讲书 | 史记/三国/唐纪/论语/易经等 | 强制司马光/臣光曰/司马迁等核心名家，至少 2 位非司马光名家 |
| 现代职场/商科 | 职场/沟通/面试/管理/营销等 | 不强制司马光，改为引用相关古今名家（德鲁克、卡尼曼、鬼谷子等）至少 2 位 |
| 哲学经典 | 论语/孟子/道德经等 | 不强制历史年份 |

现代职场类专栏额外检查项（详见 `.trae/skills/deep-reading/content-quality.md` §八）：
- 「不是X，是Y」句式每篇 ≤ 3 处（现代专栏不再对单处直接报 AI 味，由本条控量）
- 「底层逻辑」「底层操作系统」等现代术语建议替换为「根本/本质/底子/根基」
- 行业通用词白名单：KPI/HR/offer/bug/OKR/CEO/BATNA/CRIB/PPT/360度评价 等不算中英文混杂（完整清单见 `content_quality.py:MODERN_ENGLISH_WHITELIST`）
- AI 味敏感模式放宽：现代专栏中「容易被忽略/可见/第[一二三四五六]层/最关键的.*是/这说明/这事说明」等常见中文不计为 AI 味（完整清单见 `content_quality.py:MODERN_AI_OVERSTRICT_PATTERNS`）
- 引用标注冗余：正文已写明「XX在《YY》里/中讲过」，句末不再挂「大意据《YY》」（两种句式都拦截）
- 标题层级（章节用 `#` 而参考来源用 `##` 的层级倒置）
- 常见错别字清单（做为/作为、按耐/按捺等 28 组）
- 史料层累交代（鬼谷子/战国策作者ship争议、苏秦马王堆帛书修订）
- 劳动权益章节法条引用准确并标注「以现行有效法规为准」

# 工作流

## 第一步：识别待检内容

来源优先级：
1. 用户直接提供文件路径，如「检查一下 output/史记/汉纪/07_鸿门宴.md」。
2. 用户直接粘贴内容，如「请质检下面这段：...」。
3. 上下文刚刚生成的内容（deep-reading 生成后会自动触发）。

如果内容不明确，向用户确认：
- "请把要质检的文件路径发给我，或把内容贴出来。"

## 第二步：检查环境

- 检查 `.env` 是否存在且包含非空的 `LLM_API_KEY=`。
- 如果 `.env` 不存在或 `LLM_API_KEY` 为空，提示用户：
  > 质检需要调用 LLM。请复制 .env.example 为 .env 并填写 LLM_API_KEY，或设置 DEEP_READING_MOCK=1 使用 Mock 模式测试。
- 如果用户只想测试流程，可设置 `DEEP_READING_MOCK=1` 后再调用。

## 第三步：调用 Python 引擎

### 前置：字数核对（确定性，无需 LLM）

字数是确定性事实，不交给会数错 token 的 LLM。质检前先跑独立脚本：

```bash
# 单文件
python scripts/check_char_count.py --file output/史记/汉纪/07_鸿门宴.md

# 全专栏批量扫描（命中即退出码 1）
python scripts/check_char_count.py --dir output/ --strict
```

脚本覆盖三种写法：
- 模式A：`N 个字：X`
- 模式B（主流）：`「X」这 N 个字` / `"X"这 N 个字`
- 模式C：`N 个字：「X」`

**字数不含标点**——中文标点（，。！？；：""''「」（）—…《》、）和英文标点（,.!?;:'"()<>[]{}）、空白字符均不计入。发现字数不符即为 P0 错误，必须先修再进 LLM 质检。

### 前置：一致性检测（v1.2 新增，确定性，无需 LLM）

字数核对通过后，跑一致性检测——同一篇文章内的前后矛盾、数据交叉矛盾、实体不一致是 AI 幻觉的典型表现，纯规则即可检测，无需 LLM。

```bash
# 单文件
python scripts/check_consistency.py --file output/史记/汉纪/07_鸿门宴.md

# 全专栏批量扫描（--strict 命中 P0/P1 即退出码 1）
python scripts/check_consistency.py --dir output/ --strict

# 指定 archetype（narrative 古籍 / modern 职场 / knowledge 技术）
python scripts/check_consistency.py --file output/职场沟通/01_面试.md --archetype modern

# 从 stdin
cat << 'EOF' | python scripts/check_consistency.py --file -
曹操生于前155年，前140年继位时25岁。
EOF
```

四类检测（详见 [rules/consistency-rules.md](rules/consistency-rules.md)）：
1. **数值交叉矛盾**（P0）：年龄-年份、在位时长、损失-剩余的数学矛盾
2. **同事件异值**（P0/P1）：同引文异字数、同战役异兵力、同典故异出处
3. **实体别名冲突**（P0/P1）：字号、谥号、籍贯冲突
4. **时间线倒置**（P2）：年份逆序且无倒叙标注

**误报豁免**：
- 别名表（曹操↔孟德↔曹孟德↔魏武帝 等合法指代不算矛盾）
- 倒叙标注词（"此前""在此之前""回过头看""三年前"等不报）

### LLM 三视角深审（Layer 2，需 LLM_API_KEY + langgraph）

`scripts/review_content.py`、`src/agents/content_reviewer.py`、`src/agents/content_reviewer_sub.py`、`src/core/content_review_workflow.py` 均已实现。

```bash
# 单文件质检（需 .env 配置 LLM_API_KEY）
python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md

# Mock 模式（无 API Key 时测试流程）
DEEP_READING_MOCK=1 python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md

# 强制 archetype
python scripts/review_content.py --file output/职场沟通/01_面试.md --archetype modern

# 从 stdin
cat chapter.md | python scripts/review_content.py --file -
```

**沙箱降级**：无 `LLM_API_KEY` 或无 `langgraph` 时，上述脚本不可跑，改由主 Agent 经 Trae `Task` 工具启动 subagent 并行执行三视角深审（路径 C）。

## 第四步：返回结果

命令执行成功后，向用户返回：
1. 一句话摘要："已完成三视角并行内容质检（史实核验/可读性/引用克制）。"
2. 总分与评级（从报告中提取）。
3. 主要问题清单（按 P0/P1/P2 优先级）。
4. 完整报告路径（若保存到文件）或关键内容。

## 第四步补充：并行质检后核对

当用 Task 工具启动多个 Agent 并行质检/修复时，子 Agent 输出可能丢失，主流程必须：

1. **Glob 核对产出**：`Glob output/<书名>/*.md` 确认文件数与预期一致。
2. **结构校验**：`python scripts/check_book_structure.py --output output --strict` 清零 P0/P1/P2。
3. **基础脚本扫描**：跑 AI 味/引用密度/跳转/错别字/术语扫描确认 0 问题。
4. **引用真实性抽检**：名家经典组 100% 核验，其余章节抽检 ≥ 30%。
5. **合规复核**：涉及劳动权益/法律条款的章节，核验法条引用准确并标注「以现行有效法规为准」。

# 输出格式约束

- 使用中文，避免中英文混杂。
- 摘要简洁，不要一次性输出整篇报告（除非用户要求）。
- 问题清单用列表形式，标注优先级。
- 文件路径使用标准 Markdown 代码块。

# 示例对话

## 示例 1：用户要求质检文件（Layer 1 规则层，沙箱可跑）

用户：检查一下 output/史记/汉纪/07_鸿门宴.md

助手：识别到要质检的文件：output/史记/汉纪/07_鸿门宴.md。先跑 Layer 1 规则层（字数核对 → 一致性检测 → 六维度质检），无需 LLM。

```bash
python scripts/check_char_count.py --file output/史记/汉纪/07_鸿门宴.md
python scripts/check_consistency.py --file output/史记/汉纪/07_鸿门宴.md
```

Layer 1 质检完成！一致性维度：__ / 10。主要问题（按 P0/P1/P2）：
- P0：____
- P1：____

如需 LLM 三视角深审（史实核验/可读性/引用克制），有两条路径：
- **路径 B**：`python scripts/review_content.py --file ...`（需 LLM_API_KEY + langgraph）
- **路径 C（沙箱降级）**：主 Agent 经 `Task` 工具启动 subagent 并行执行

## 示例 2：全专栏批量扫描

用户：跑一下全专栏质检

助手：Layer 1 批量扫描，无需 API Key：

```bash
python scripts/check_char_count.py --dir output/ --strict
python scripts/check_consistency.py --dir output/ --strict
```

# 错误处理

- **文件不存在**：提示用户检查文件路径。
- **内容为空**：提示用户提供待检内容。
- **命令返回非零**：返回错误信息，建议检查日志。
- **Layer 2 环境缺失**：`scripts/review_content.py` 已实现，但需 `LLM_API_KEY` + `langgraph`。无则提示用户配置 `.env`，或设置 `DEEP_READING_MOCK=1` 测试流程，或降级为 `Task` 工具启动 subagent。

# 合规对齐与方法论溯源（v1.2.2）

## 行业规范对齐

本 Skill 的质检目标（真实性、避免幻觉、溯源校验）与下列行业规范精神一致。**本 Skill 非对外服务**，不承担训练数据/安全评估/内容标识等合规义务，仅作为个人创作质检工具：

- 网信办《生成式人工智能服务管理暂行办法》（2023）——真实性、避免幻觉
- TC260-003《生成式人工智能服务安全基本要求》（2024）——内容标识与可追溯
- 中国信通院《可信AI大模型评测体系白皮书》（2024-2025）——量化评测
- 中国人工智能学会《可信人工智能白皮书》（2024）——可信治理

## 方法论溯源

本 Skill 融合以下 AI 幻觉治理权威方法论（详见 [rules/consistency-rules.md §六](rules/consistency-rules.md)）：

| 方法论 | 来源 | 落地 |
|---|---|---|
| Chain-of-Verification (CoV) | Jason Weston 等 | 一致性检测 4 类矛盾（claim 提取 + 交叉验证） |
| Self-Consistency | Wang et al. 2022 | 同事件异值检测（同事实多次出现应一致） |
| Chain-of-Thought (CoT) | Wei et al. Google 2022 | 三视角 Prompt "先列核验步骤再下结论"结构 |
| ReAct | Yao et al. 2022 | "质检→修复→再质检"反馈循环（离线变体） |
| Grounding/Citations | — | 典故出处一致性检测 |
| Vectara HHEM-2.1 | Vectara | 一致性维度量化扣分（0-10 分） |
| TruthfulQA / HELM | Lin et al. 2021 / Stanford CRFM 2023 | 六维度量化评分体系（理论参考，非直接调用） |

**明确不引入**（违反"纯规则+LLM 两层"简洁性原则）：
- RAG（检索增强生成）：重资产，讲书场景规则层已兜底
- RLHF：训练侧技术，本项目不训练模型
- PackageHallucination：代码场景工具，本 Skill 仅处理文章专栏
- 完整知识图谱事实核查：需外部 KG 数据源，以 v1.3 别名归一化为渐进路径
