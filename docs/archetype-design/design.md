# 专栏形态范式分层设计（Archetype Design）

> **状态**：草案 v2，待合并实施
> **日期**：2026-06-26（v2 修订于同日，对照 Soul Injection 改造）
> **分支**：`feature/column-archetype-design`（基于最新 master `e982da1`）
> **说明**：本方案已通过专家团三视角（架构师/测试/规则）分析。当前仅文档存档，**不进入实现**。等另一个改进（Soul Injection，已合入 master PR #14）完成后，再与本方案合并实施——实际上 Soul Injection 已合入，本 v2 已据此修订。
> **背景**：用户提出"不同类型专栏用同一套方法论=不管什么菜都用一把菜刀"，要求按类型分支、共用层保留、差异化层专业化，目标是产出更高质、更贴切、更吸引对应人群的内容。

---

## 目录

- [一、背景](#一背景)
- [二、问题（一刀切现象）](#二问题一刀切现象)
- [三、面临挑战](#三面临挑战)
- [四、分析（专家团三视角结论）](#四分析专家团三视角结论)
- [五、设计方案](#五设计方案)
- [六、与 Soul Injection 改造的关系（v2 新增）](#六与-soul-injection-改造的关系v2-新增)
- [七、实施计划（五阶段迁移）](#七实施计划五阶段迁移)
- [八、质检规则分桶细则](#八质检规则分桶细则)
- [九、提示词分桶细则](#九提示词分桶细则)
- [十、结构模板分桶细则](#十结构模板分桶细则)
- [十一、测试与回归策略](#十一测试与回归策略)
- [十二、风险与约束](#十二风险与约束)
- [十三、沉淀计划](#十三沉淀计划)
- [附录 A：archetype 判定伪代码](#附录-aarchetype-判定伪代码)
- [附录 B：评审路径](#附录-b评审路径)

---

## 一、背景

HaloRead 原定位是"读完古籍后输入书名+章节，AI 生成 Markdown 讲书笔记进入 Obsidian"。但随着项目生长，专栏已事实多类型化：

- **史**：资治通鉴、史记、三国、唐纪、宋纪、明纪、孔子传
- **经**：论语、易经课
- **养生**：饮食养生课（含第二版）、锻炼养生课、睡眠与精力修复课
- **财**：理财课
- **技**：AI 大模型学习、大厂晋升指南
- **职场**：职场沟通课、面试现场

共 6 大类目、16+ 专栏。`_meta.yaml` 已普遍存在 `category` 字段，且该字段已被展示层（`scripts/build_site.py`、`src/web/app.py`、前端 `app.js`）读取用于分类 tab 和排序。

**但生成层和质检层仍是"一套古籍方法论打天下"**——这是本方案要解决的核心矛盾。

> 注：master PR #14（Soul Injection）已于 2026-06-26 合入，新增 `tone_setter`/`chief_editor` 两个节点和 `check_ai_cliches`/`check_numeric_facts` 两个通用检查。这些改动**强化了"古籍叙事向"的默认假设**（详见 §六），反而使 archetype 分桶更迫切。

---

## 二、问题（一刀切现象）

一刀切在五个层面有据可查：

| 层 | 现状 | 证据 |
|---|---|---|
| 生成层 | 7 份 prompt 全古籍化（臣光曰/王夫之/文言≤20字）；6 段结构三重锁死 | `src/agents/editor.py:33-40`、`src/core/workflow.py:94-114`、`config.yaml:40-46` |
| 质检层 | 仅 2 处关键词"逃生阀"，只覆盖职场+哲学，**漏掉财/技/养生** | `src/utils/content_quality.py:75,315-323,433` |
| 数据流 | `category` 字段只在展示层用，**从未回流生成/质检层** | `scripts/build_site.py:348` vs 生成层无 type |
| 实际产出 | 理财课早已用「入戏/破题/经典时刻/故事展开/拆解」自定义结构，AI 课用「原理直觉/提示词工程」知识模块——**野生绕开 rules.md** | `output/理财课/兵器与阵法_ETF与场内基金.md:10-60` |
| 已有沉淀 | loop_log 两次明确写"一刀切"和"规则真空" | `docs/loop_log.md:281-306`、`docs/loop_log.md:850-897` |

**根因**：类型信号没有进入主数据流。`book/chapter/event` 三槽位从 `SKILL.md → main.py → orchestrator → workflow → agents → prompts` 全程无 type；`category` 只活在 `_meta.yaml` 和展示层。

**v2 补充证据**：Soul Injection 引入的 `tone_setter`（核心史观/《明朝那些事儿》笔法）和 `chief_editor`（活人测试，举例比干/杨椒山/杨涟）两个节点的 prompt 是**纯古籍叙事向**，被无条件接入全管线（`_USE_SOUL_INJECTION` 开关只看环境变量，不看 archetype）——这意味着理财课/AI 课也会被套上"生死悲剧底色敬畏感"终审，进一步加剧一刀切。

**已有局部补救**（说明团队已感知问题但未系统化）：
- `content-quality.md §8`（行 200-265）的"现代职场/非史类专栏适配"补救条款，定位是"例外"而非"类型化方法论"
- `content_quality.py` 的 `_is_modern_column` / `_is_philosophy_or_classic` 靠书名子串匹配，是质检层的"逃生阀"
- `loop_log.md` 至少两次明确写到"一刀切"问题，但未落地系统方案

---

## 三、面临挑战

把"按类型分支"这件事做对，有五个挑战：

### 挑战 1：按什么维度分桶？
按主题（史/经/财/技…）分会越分越碎（史-编年/史-纪传/经-哲学/经-经典…），维护成本爆炸。必须找到更稳定的分桶维度——本方案选"叙事范式（怎么写）"而非"主题（写什么）"。

### 挑战 2：混合类目如何处理？
"经"里论语是叙事讲书、易经课是知识体系；"技"里 AI 课是知识体系、大厂晋升指南是现代方法。一个 category 下可含多个范式，因此范式维度必须独立存在，不能由 category 单值推导。

### 挑战 3：古籍专栏占大多数，改造不能误伤
现有 7+ 古籍专栏是项目基线。任何分桶改造必须保证古籍桶零改动，否则会破坏已验收的内容与测试。

### 挑战 4：未来类型如何容纳而不无限开桶？
未来会写小说（虚构创作）、数据结构/算法/Python/Redis（技术教程）等。三桶不能覆盖虚构创作，但也不能每来一个新类型就开一桶。需要明确的"开桶判定标准"。

### 挑战 5：与已合入的 Soul Injection 改造协同（v2 新增）
Soul Injection 已在 master 上落地 `tone_setter`/`chief_editor` 节点和 `SOUL_INJECTION_ENABLED` 开关。archetype 分桶不能无视它们，必须：(a) 把这俩节点的古籍向 prompt 纳入分桶；(b) 把二元开关升级为按 archetype 决策；(c) 复用其兜底机制（ImportError 跳过）。

---

## 四、分析（专家团三视角结论）

> 说明：评审引擎 `scripts/review_plan.py` 需 `LLM_API_KEY`，本结论由单 agent 串行切换架构师/测试/规则三视角完成（路径 A，符合 `dev-workflow.md §零` 能力边界）。补 `.env` 后可跑真并行复核。

### 🔵 架构师视角：可行性 / 分层 / 数据流 / 扩展性
**结论：方向正确，是补全已断裂的数据流，不是新建系统。**
- 根因诊断准确：类型信号没进主数据流是核心病灶，补的代价低、收益高。
- 分层原则要对：按"怎么写"（叙事范式）分桶，不按"写什么"（主题类目）分桶。
- 共用层要足够大：Orchestrator、Editor 机制、LangGraph 编排、四维度质检骨架、结构校验、Skill 入口全部共用，只换"桶内模板和规则集"。
- **v2 协同性**：Soul Injection 的 `_USE_SOUL_INJECTION` 开关机制（`workflow.py:42-44`）正好是 archetype 路由的现成挂载点——把"二元开关"升级为"按 archetype 选 tone_setter/chief_editor 的启用与 prompt 版本"，改动面小。
- 风险：`editor.py` 的 `SECTION_TO_AGENT` 和 `config` 的 `required_sections` 是硬编码，改造时容易破坏古籍专栏。必须"古籍桶=现状不动"作基线。

### 🟢 测试视角：可验证性 / 回归 / 边界
**结论：需补类型识别测试和分桶质检回归，否则重蹈 BUG-024 覆辙。**
- 类型识别本身要可测：archetype 判定逻辑必须有单测，覆盖 16 专栏归类。
- 质检分桶回归：BUG-024（`loop_log.md:850-897`）已证明"规则误报"是高频痛点。分桶后古籍桶规则不放松、现代桶白名单不串桶。
- **v2 补充**：Soul Injection 已新增 `check_numeric_facts`（`quality.py:285`），其 manual_review 项（N 年前/N 岁/N 品官）对 modern（"N 年收益率"）、knowledge（"N 个 token"）可能误标，分桶时必须按 archetype 调整触发词。
- 边界场景：跨桶专栏（经/技混合）必须支持显式覆盖。
- 收益指标：分桶前后对理财课/AI课跑质检分数对比，误报应显著下降——这是"更高质"的硬证据。

### 🟡 规则视角：规范符合 / Skill 边界 / 过度工程化
**结论：符合规则方向，但要警惕"类型注册系统"式过度工程化。**
- 符合 `dev-workflow.md`：把已有的"野生"结构收编为正式规则，是"沉淀"而非"新增"。
- **v2 禁区边界修正**：`dev-workflow.md §四` 原列 `src/utils/quality.py` 为禁区。master PR #14 已对其新增 `check_ai_cliches`/`check_numeric_facts`（通用检查）。本方案对 quality.py 的处理红线是：**函数内部零改动，只在调用层（content_quality.py）按 archetype 路由与过滤**。narrative 桶的古籍专属规则（`MODERN_JARGON`/`check_ai_tone` 严格档）不碰；通用检查全桶共享。这样既守住禁区，又落地分桶——论证收窄为"调用层路由"，而非宽泛的"顺应现状"。
- Skill 边界：`dev-workflow.md §零` 明确 Skill 不能调度 sub-agent、不能直接调 MCP。类型分支逻辑必须落在 Python 层，Skill 只做"识别意图 + 传 type 给引擎"。
- 过度工程化红线：桶数要克制，需有开桶标准。

### 汇总
三视角一致通过，无否决意见。关键约束：共用层要大、开桶需过标准、古籍桶零改动、类型识别必须可测、与 Soul Injection 协同而非冲突。

---

## 五、设计方案

### 5.1 category × archetype 正交

引入两个正交维度，避免"按主题分桶"导致越分越碎：

| 维度 | 含义 | 用途 | 现状 |
|---|---|---|---|
| `category` | 主题类目（写什么） | 前台展示分组、排序 | 已有（史/经/养生/财/技/职场） |
| `archetype` | 叙事范式（怎么写） | 生成层选 prompt、质检层选规则集、决定 soul injection 启用 | **新增** |

**关键原则**：方法论按"怎么写"分桶，不按"写什么"分桶。一个 `category` 下可含多个 `archetype`（如"经"里论语是叙事讲书、易经课是知识体系），因此 `archetype` 必须作为独立字段，不能由 `category` 单值推导。

### 5.2 桶定义（三桶 + fiction 预留）

| Archetype | 写作骨架 | 语气/引用 | tone_setter/chief_editor | 目标人群 | 状态 |
|---|---|---|---|---|---|
| `narrative`（叙事讲书） | 事件/人物/背景/道理/悟道 + 结语 | 白话小说笔法、文言≤20字、名家点评、年份必填 | **启用**（现版古籍 prompt） | 读史、悟道者 | 现有，零改动 |
| `modern`（现代方法） | 场景入戏/破题/方法论拆解/避坑/践行清单 | 现代白话、行业术语白名单、场景化、可操作 | **用 modern 版 prompt 或跳过** | 职场人、理财小白、养生人群 | 新建 |
| `knowledge`（知识体系） | 概念/原理/工程实践/速查 | 模块化教学、术语密集、强调准确与递进、术语白名单最宽 | **用 knowledge 版 prompt 或跳过** | 技术学习者、体系建构者 | 新建 |
| `fiction`（虚构创作） | 情节/人物弧光/冲突/伏笔回收 | 视角节奏、"套路/金手指/爽点"是技巧而非问题、世界观自洽 | 待设计（fiction 版） | 小说读者 | **预留，待实现** |

> **tone_setter/chief_editor 列说明（v2 核心）**：Soul Injection 的这俩节点 prompt 是纯古籍向（`src/agents/tone_setter.py`、`src/agents/chief_editor.py`，prompt 内联在代码 PROMPT 常量中）。直接套到 modern/knowledge 桶会扭曲（理财课无"生死悲剧底色"、AI 课无"比干"）。因此 archetype 必须决定：narrative 桶启用现版；modern/knowledge 桶用对应版本 prompt，或直接跳过这俩节点。

### 5.3 开桶判定标准（4 条硬标准）

为防止桶数膨胀，**全部命中以下 4 条**才开新桶：

1. **写作骨架根本不同**——不是同一组段落换皮，而是段落定义本身不同（讲书的"事件"≠小说的"情节"）。
2. **质检规则有本质冲突**——同一规则在新形态下必然误报，且无法靠加白名单解决（小说的"套路"是技巧，质检不能报）。
3. **目标人群的阅读期待根本不同**——读史者求悟道、读者求消遣/共鸣，评判标准不同。
4. **真实性的定义根本不同**——虚构 vs 非虚构，引用/核验机制不同。

**候选拓展桶验证**：

| 候选 | 标准1骨架 | 标准2质检 | 标准3人群 | 标准4真实性 | 结论 |
|---|---|---|---|---|---|
| 小说 | ✅不同 | ✅冲突 | ✅不同 | ✅不同 | 4/4，开 `fiction` |
| 数据结构 | ❌同 knowledge | ❌不冲突 | ❌同学习者 | ❌同可核验 | 0/4，归 `knowledge` |
| Python/Redis | ❌同 | ❌ | ❌ | ❌ | 0/4，归 `knowledge` |
| 诗集/散文 | 待具体看 | 待定 | ✅ | ✅ | 待定，可能需 `literary` 桶 |

> 数据结构/算法/Python/Redis 完全契合 `knowledge` 桶：概念（栈/队列/树定义）→原理（复杂度证明）→实践（代码实现）→速查（复杂度表/命令表）。术语白名单（RDBMS/ACID/CAP/LSM-Tree…）正好容纳，无需新桶。

### 5.4 现有 16 专栏归类

| 专栏 | category | archetype | 依据 |
|---|---|---|---|
| 资治通鉴 / 史记 / 三国 / 唐纪 / 宋纪 / 明纪 / 孔子传 | 史 | `narrative` | 编年/纪传叙事 |
| 论语 | 经 | `narrative` | 经典解读，叙事讲书 |
| 易经课 | 经 | `knowledge` | 原理/概念体系，覆盖默认 |
| 理财课 | 财 | `modern` | 已用「兵器/心法/守正/觉醒/践行」自定义结构 |
| 职场沟通课 / 面试现场 | 职场 | `modern` | 已有白名单沉淀（BUG-024） |
| 饮食养生课 / 饮食养生课第二版 / 锻炼养生课 / 睡眠与精力修复课 | 养生 | `modern` | 科普方法论 |
| AI大模型学习 | 技 | `knowledge` | 已用「原理直觉/提示词工程/上下文工程」知识模块 |
| 大厂晋升指南 | 技 | `modern` | 技术管理方法论，覆盖默认 |

**category → archetype 默认映射**（可被 `_meta.yaml` 显式覆盖）：

| category | 默认 archetype | 需显式覆盖的专栏 |
|---|---|---|
| 史 | `narrative` | — |
| 经 | `narrative` | 易经课 → `knowledge` |
| 养生 | `modern` | — |
| 财 | `modern` | — |
| 职场 | `modern` | — |
| 技 | `knowledge` | 大厂晋升指南 → `modern` |

> "经"和"技"是混合桶——这正是 `archetype` 必须独立存在的硬证据。

### 5.5 共用层 vs 差异化层

| 层 | 共用（所有桶） | 差异化（按桶） |
|---|---|---|
| 入口 | `SKILL.md` 交互、Orchestrator 三槽位解析 | 识别 archetype 并传入引擎 |
| 编排 | LangGraph workflow、Editor 汇总机制 | 章节模板（六段 / 现代五段 / 知识模块 / 情节模块） |
| 文风注入 | tone_setter/chief_editor 节点机制、兜底跳过 | 按桶选 prompt 版本或跳过（v2） |
| 提示词 | 提示词加载框架、写作通用约束 | 各桶专用 prompt 子目录 |
| 质检 | 四维度骨架、引用克制基础版、错别字、标题层级、结构校验、**套话黑名单/数字事实（v2 通用）** | 名家/年份要求、AI味阈值、中英文白名单、术语规则、numeric manual_review 触发词 |
| 配置 | frontmatter、命名、output 结构 | `required_sections` 按桶读 |
| 展示 | `category` 分组（已有） | — |

**原则**：共用层尽量大，差异化层只分"模板 + 规则集 + 文风注入版本"三件。不搞多套独立 agent 系统。

### 5.6 数据流设计

```
_meta.yaml (archetype 字段)
   │
   ├─→ SKILL.md 入口识别 → main.py --archetype 参数
   │
   └─→ AgentState.archetype（新增字段）
         │
         ├─→ workflow.tone_setter_node：按 archetype 决定启用/跳过/选 prompt 版本
         ├─→ workflow.quality_node：按 archetype 读 required_sections
         ├─→ workflow.chief_editor_node：按 archetype 决定启用/跳过/选 prompt 版本
         ├─→ editor.run：按 archetype 读 SECTION_TO_AGENT 结构模板
         ├─→ specialist agents：load_prompt(name, archetype) 加载对应桶 prompt
         └─→ content_quality.run_content_quality_checks：按 archetype 路由规则集
```

archetype 信源优先级（v2 修订，与附录A伪代码统一）：
1. CLI `--archetype` 参数（手动覆盖，最高优先，用于一次性强制生成）
2. `_meta.yaml` 的 `archetype` 字段（显式声明，专栏级默认）
3. `category → archetype` 默认映射表（兜底）
4. `narrative`（最终兜底，古籍基线）

> 说明：CLI 优先是为了支持"一次性强制覆盖"场景（如临时用 modern 桶生成某个史类章节做对比）。`_meta.yaml` 是专栏级常态声明，覆盖 category 默认映射。附录A的 `resolve_archetype(category, explicit)` 中 `explicit` 参数在 main.py 实现里接收 `cli_archetype or meta_archetype`，即 CLI 与 _meta.yaml 显式声明合并为 explicit 信源，CLI 优先。

---

## 六、与 Soul Injection 改造的关系（v2 新增）

master PR #14（Soul Injection）已合入，与本方案的协同关系如下：

### 6.1 Soul Injection 改动清单
| 改动 | 位置 | 性质 |
|---|---|---|
| `tone_setter` 节点（定调：核心史观/情感基调/灵魂锚点，对标《明朝那些事儿》） | `src/agents/tone_setter.py`、`workflow.py:60-68` | 古籍叙事向，prompt 内联 |
| `chief_editor` 节点（终审：活人测试/洞察独家性/底色敬畏感，举例比干/杨椒山/杨涟） | `src/agents/chief_editor.py`、`workflow.py:116-136` | 古籍叙事向，prompt 内联 |
| `SOUL_INJECTION_ENABLED` 二元开关 | `workflow.py:23` | 全开/全关 |
| `_USE_SOUL_INJECTION` 接入判定 | `workflow.py:42-44` | 只看开关+Import，不看 archetype |
| `check_ai_cliches`（套话黑名单） | `quality.py:253,268` | **通用检查**，全桶适用 |
| `check_numeric_facts`（数字事实硬错误） | `quality.py:285` | **通用检查**，全桶适用 |
| `check_chapter_title_soul` | `quality.py:328` | 古籍向 |
| rules.md §6.5 / content-quality.md §9.3 | 数字事实硬约束 | 古籍向 |
| BUG-026 沉淀 | `tests/bug_regression_list.md` | "灵魂注入与合规是两类独立问题" |

### 6.2 七处协同结论（影响本方案）

1. **workflow.py 行号全部更新**：阶段 3 引用从旧 `62-65/116-139` 改为 `94-114`（quality_node，required_sections 读取在 98-101）/`174-214`（节点注册与边）。
2. **tone_setter / chief_editor 纳入 archetype 分桶**（最重要）：这俩节点是 narrative 桶专属。narrative 桶启用现版；modern/knowledge 桶用对应版本 prompt 或跳过。纳入 §5.2 桶定义表和 §5.5 共用/差异化层。
3. **`SOUL_INJECTION_ENABLED` 开关升级**：从二元全开/全关升级为按 archetype 决策（narrative 启用现版；modern/knowledge 选版本或跳过）。复用其 ImportError 兜底机制。
4. **quality.py 禁区边界修正**：`check_ai_cliches`/`check_numeric_facts` 是通用检查，全桶共享；narrative 桶零改动仅指古籍专属规则（`MODERN_JARGON`/`check_ai_tone` 严格档）。已更新 §四规则视角和 §5.5。
5. **`check_numeric_facts` manual_review 跨桶误报**：其 manual_review 项（N 年前/N 岁/N 品官）对 modern/knowledge 可能误标，阶段 2 必须按 archetype 调整触发词。
6. **阶段顺序调整：prompt 迁移与分桶合并**：tone_setter/chief_editor 的 prompt 现内联在代码（有 TODO 要迁到 `prompts/`），正好与阶段 4（提示词分桶）合并做——迁移时直接按 archetype 分桶，避免返工。
7. **BUG-026 教训直接支撑质检分桶**："灵魂注入与合规是两类独立问题"印证：灵魂类检查（tone_setter/chief_editor）按桶路由，合规类检查（数字/套话）全桶共享。

### 6.3 不受影响的部分
- `content_quality.py`/`prompts.py`/`editor.py`/`config.yaml` 未被 Soul Injection 改动 → 阶段 1/2/4 的行号引用仍有效。
- 三桶定义、category×archetype 正交、开桶标准、16 专栏归类、fiction 预留 → 仍然成立。

---

## 七、实施计划（五阶段迁移）

> 原则：每阶段独立可交付、可回滚；古籍桶全程零改动；每阶段完成后跑 `check_book_structure.py --strict` + `pytest` + 回归集全绿。
> **当前状态：阶段1（数据流）✅ 已完成；阶段2（质检分桶）✅ 已完成；阶段3（结构模板分桶 + 文风注入按桶路由）✅ 已完成；阶段4-5 待实施。**

### 阶段 1：打通数据流（最小改动，先让类型信号流动）

| 文件 | 改动 |
|---|---|
| `output/{各书}/_meta.yaml` | 16 个文件新增 `archetype` 字段（按 §5.4 归类） |
| `src/core/state.py:11-20` | `AgentState` 新增 `archetype: str` 字段 |
| `src/main.py:99-109` | CLI 新增 `--archetype` 参数；`initial_state` 注入 `archetype` |
| `src/utils/prompts.py` | 新增 `resolve_archetype(category, explicit=None) -> str`，封装默认映射 + 覆盖逻辑 |
| `config.yaml` | 新增 `archetype_defaults` 映射表（§5.4 的 6 条规则） |

**验收**：`pytest` 全绿；`resolve_archetype("经")` 返回 `narrative`，`resolve_archetype("经", explicit="knowledge")` 返回 `knowledge`。

### 阶段 2：质检分桶（消除误报，收益最直接）✅ 已完成（2026-06-26）

| 文件 | 改动 |
|---|---|
| `src/utils/content_quality.py:315-323` | 删除 `_is_philosophy_or_classic` / `_is_modern_column` 的关键词判定，改为接收 `archetype` 参数 |
| `src/utils/content_quality.py:427-484` | `run_content_quality_checks(content, archetype="narrative")`：按 archetype 路由规则集 |
| `src/utils/content_quality.py` | 现有 `MODERN_ENGLISH_WHITELIST` 归入 `modern` 桶规则集；新增 `knowledge` 桶术语白名单；**按 archetype 过滤 `check_numeric_facts` 的 manual_review 结果**（v2，避免 modern/knowledge 误标） |
| `scripts/review_content.py:48-92` | 读取 `_meta.yaml` 的 archetype 传入质检函数 |
| `.trae/skills/deep-reading/content-quality.md` | §8 从"补救条款"重构为"多桶规则集"；§9.3 数字事实检查标注"通用，全桶共享" |

**v2 说明（禁区红线）**：`check_ai_cliches`（`quality.py:268`）和 `check_numeric_facts`（`quality.py:285`）是 master 已落地的通用检查，**所有桶都跑，不跳过，函数内部不动**。numeric 的 manual_review 误标问题**不在 quality.py 改触发词**，而是在 `content_quality.py` 调用层按 archetype 过滤掉误标的 manual_review 项——这样 `quality.py` 完全零改动，守住 `dev-workflow.md §四` 禁区。
**验收**：理财课/AI课跑质检，误报较改造前显著下降；古籍专栏分数不降。

> **阶段2 完成验收（2026-06-26）**：
> - 质检分数对比：理财课·ETF 84→100（+16，消除 5 误报）；AI课·Transformer 81→97（+16，消除 5 误报）；资治通鉴·三家分晋 100（无回归）。
> - `tests/test_content_quality_archetype.py` 34 项契约测试全过。
> - 三件套：`check_book_structure.py --strict` 0 问题；pytest 221 passed 15 skipped；`run_regression_suite.sh` 18/18。
> - `content-quality.md` §8 重构为多桶并行规则集；`scripts/review_content.py` 接线 `--archetype`；`tests/bug_regression_list.md` 登记 BUG-027/028。详见 `docs/loop_log.md` 阶段2沉淀。

### 阶段 3：结构模板分桶 + 文风注入按桶路由（v2 合并）✅ 已完成（2026-06-27）

| 文件 | 改动 |
|---|---|
| `src/agents/editor.py:33-40` | `SECTION_TO_AGENT` 从硬编码字典改为按 archetype 读取结构模板 |
| `config.yaml:40-46` | `required_sections` 从全局列表改为按 archetype 的字典 |
| `src/core/workflow.py:94-114` | `quality_node` 读 `state["archetype"]` 取对应 `required_sections`（行号已更新） |
| `src/core/workflow.py:42-44,138-143,174-214` | `_USE_SOUL_INJECTION` 升级为按 archetype 决策：narrative 启用现版 tone_setter/chief_editor；**modern/knowledge 一律跳过**（阶段4落地对应版 prompt 后才启用，见 §10.6） |
| `src/core/workflow.py:188-214` | 节点注册与边按 archetype 决定：narrative 走 `orchestrator→tone_setter→specialists` + `quality→chief_editor→save`；modern/knowledge 走原 else 分支 `orchestrator→specialists` + `quality→save`（不断链） |
| `src/main.py:76` | stub 模式的 `sections` 列表按 archetype 取 |

**v2 链路明确**：阶段3 modern/knowledge 跳过两个 soul 节点，走原 else 分支边，save 链路完整；阶段4迁出对应版 prompt 后才对 modern/knowledge 开启 tone_setter/chief_editor。
**验收**：理财课新章节用 `modern` 模板生成、跳过 soul 节点、结构校验通过、save 正常；古籍专栏仍走六段+全 soul injection 不变。

> **阶段3 完成验收（2026-06-27）**：
> - `config.yaml` 新增 `section_templates`（narrative 6 段 / modern 5 段 / knowledge 4 段），narrative 与 legacy `quality_check.required_sections` 完全一致（古籍零回归护栏）。
> - `src/core/workflow.py`：`build_workflow(output_base, archetype="narrative")` + 纯函数 `get_required_sections(archetype)` + `_soul_injection_for_archetype(archetype)`（narrative 启用 tone_setter/chief_editor，modern/knowledge 走原 else 分支不断链）；`quality_node` 闭包按 archetype 注入 `required_sections`。
> - `src/agents/editor.py`：`SECTION_TO_AGENT` → `SECTION_TEMPLATES`（三桶映射），`_section_to_agent_map(archetype)` 按 `state["archetype"]` 路由。
> - `src/main.py`：`--archetype` CLI + `_get_stub_sections(archetype)`（stub 路径直读 config 不依赖 langgraph）+ fiction→narrative 统一回落（BUG-029）。
> - `tests/test_workflow_archetype.py`：64 项契约测试全过（含 P0-1 真实模式回落、P1-1 modern/knowledge 边链对称断言、P1-2 config fallback 路径、P1-3 editor 兜底、P1-4 双真相源一致性、P1-5 router_fn 反断言、BUG-029 fiction 回归）。
> - 三件套：`check_book_structure.py --strict` 0 问题；pytest 275 passed 15 skipped（忽略 4 个 langgraph 依赖测试文件）；`run_regression_suite.sh` 18/18。
> - 专家团三视角评审（架构/测试/规则）首轮均分 7.5，修复 P0-1（真实模式回落）+ P1-1~5 后复评。
> - `tests/bug_regression_list.md` 登记 BUG-029（跨层 archetype 白名单不一致）。详见 `docs/loop_log.md` 阶段3沉淀。

### 阶段 4：提示词分桶 + soul injection prompt 迁移（v2 合并）

| 文件 | 改动 |
|---|---|
| `prompts/` | 新建子目录 `modern/`、`knowledge/`（`narrative` 桶维持原 `prompts/{name}.md` 路径兼容） |
| `prompts/modern/` | 新建 modern 版 prompt（含 `tone_setter.md`/`chief_editor.md`，v2） |
| `prompts/knowledge/` | 新建 knowledge 版 prompt（含 `tone_setter.md`/`chief_editor.md`，v2） |
| `src/agents/tone_setter.py` | 把内联 PROMPT 迁到 `prompts/{archetype}/tone_setter.md`，用 `load_prompt("tone_setter", archetype=...)` 加载（落实其 TODO，v2） |
| `src/agents/chief_editor.py` | 同上，迁到 `prompts/{archetype}/chief_editor.md`（v2） |
| `src/utils/prompts.py:20-28` | `load_prompt(name, variables, archetype="narrative")`：按 archetype 选子目录 |
| `src/agents/*.py` | 各 agent 的 `load_prompt` 调用传入 `state["archetype"]` |

**约束**：`narrative` 桶 prompt 原封不动（`dev-workflow.md §四` 禁区）。
**v2 价值**：把 soul injection 的"内联 prompt 迁移"TODO 与 archetype 分桶一次性完成，避免返工。
**验收**：`load_prompt("tone_setter", archetype="modern")` 加载 `prompts/modern/tone_setter.md`；`archetype="narrative"` 加载 `prompts/narrative/tone_setter.md`（或兼容原路径）。

> **阶段4 基础设施完成（2026-06-27）**：
> - `src/utils/prompts.py`：`load_prompt(name, variables, archetype="narrative")` 改造完成。narrative 读原 `prompts/{name}.md`（兼容，禁区不动）；modern/knowledge 读 `prompts/{archetype}/{name}.md`，文件不存在时 fallback 到 narrative 原路径 + `UserWarning`（不静默，渐进迁移友好）；非法 archetype（含 fiction 未落地）兜底 narrative。
> - `tests/test_prompt_archetype.py`：17 项契约测试全过（archetype 路由 / 默认 narrative / fallback+警告 / 非法兜底 / variables 替换 / 文件不存在 raise）。
> - 三件套：`check_book_structure.py --strict` 0 问题；pytest 292 passed 15 skipped；`run_regression_suite.sh` 18/18。
> - **未完成（留并行会话）**：`prompts/modern/`、`prompts/knowledge/` 子目录与 prompt 内容；specialist agents 接入 `state["archetype"]` 调 `load_prompt(name, archetype=...)`；tone_setter/chief_editor 内联 prompt 迁文件；`main.py` 真实模式 `exec_archetype` 回落解除（需 specialist 改造后）。

> **阶段4 内容工作完成（2026-06-27）**：
> - `src/agents/{historian,biographer,context_analyst,critic,philosopher,editor}.py`：6 个 specialist 接入 `archetype`，`load_prompt(name, vars, archetype=state.get("archetype","narrative"))`，段名从 `SECTION_TEMPLATES` 反查（非硬编码）。
> - `src/agents/{tone_setter,chief_editor}.py`：内联 `PROMPT` 常量删除，迁到 `prompts/tone_setter.md` + `prompts/chief_editor.md`（narrative 原内容零改动），`run()` 改用 `load_prompt(name, vars, archetype=...)`。
> - `prompts/modern/`（8 文件）：historian(入戏)/critic(破题)/context_analyst(方法论)/editor(践行+汇总)/biographer(占位)/philosopher(占位)/tone_setter(核心洞察·实用基调·核心矛盾·操作锚点)/chief_editor(实用价值测试·方法独家性·落地可行性)。
> - `prompts/knowledge/`（8 文件）：context_analyst(概念)/historian(原理)/biographer(实践)/editor(速查自测+汇总)/critic(占位)/philosopher(占位)/tone_setter(核心原理·认知基调·核心难点·示例锚点)/chief_editor(准确性测试·深度独家性·可操作性)。
> - `src/main.py`：`exec_archetype` 回落解除（specialist 已按 archetype 路由 prompt+段名，quality 检查段名匹配），`build_workflow(archetype=archetype)` 直接用用户意图。
> - `tests/test_specialist_archetype.py`：34 项契约测试（archetype 传参/段名反查/默认 narrative/fallback 警告/PROMPT 迁文件/main 无回落）。
> - `tests/test_workflow_archetype.py`：契约12 更新（原 P0-1 回落断言改为阶段4 直接执行断言）。
> - 三件套：`check_book_structure.py --strict` 0 问题；pytest 326 passed 15 skipped；`run_regression_suite.sh` 18/18。
> - **架构决策（未开启 modern/knowledge soul injection）**：`_soul_injection_for_archetype` 保持 modern/knowledge 返回 False。原因：开启需先解决边链按桶裁剪 specialist 的架构问题（modern 不需 biographer/philosopher，knowledge 不需 critic/philosopher），否则会调用占位 agent 产空段导致 quality 失败。modern/knowledge 的 tone_setter/chief_editor prompt 已建作为前置资产，待阶段5/单独任务解决边链裁剪后开启。

### 阶段 5：Skill 入口分流与沉淀

| 文件 | 改动 |
|---|---|
| `.trae/skills/deep-reading/SKILL.md` | 入口识别 archetype（读 `_meta.yaml` 或问用户），传给 Python 引擎 |
| `.trae/skills/deep-reading/rules.md` | 顶部声明"本规则仅适用 `narrative` 桶"；落实 `loop_log.md:298` 未做项 |
| `.trae/skills/deep-reading/` | 新增 `rules-modern.md`、`rules-knowledge.md`（fiction 桶待实现时再加 `rules-fiction.md`） |
| `docs/loop_log.md` | 追加本次分桶改造沉淀 |
| `tests/bug_regression_list.md` | 若期间修复复发 bug，按 `bug-reporting.md` 登记 |

**验收**：Skill 能正确分流；多套规则文件边界清晰。

---

## 八、质检规则分桶细则

将 `run_content_quality_checks` 的检查项按桶分档：

| 检查项 | narrative | modern | knowledge | fiction（预留） |
|---|---|---|---|---|
| `check_years_present`（年份必填） | ✅ 必检 | ⏭ 跳过 | ⏭ 跳过 | ⏭ 跳过 |
| `check_famous_critics`（古籍名家） | ✅ 必检 | ⏭ 跳过 | ⏭ 跳过 | ⏭ 跳过 |
| `check_temporal_order`（时间线） | ✅ 必检 | ⏭ 跳过 | ⏭ 跳过 | ➡️ 改检情节因果链 |
| `check_modern_jargon`（现代术语禁用） | ✅ 必检 | ⏭ 跳过 | ⏭ 跳过 | ⏭ 跳过 |
| `check_mixed_language`（中英混杂） | ✅ 严格 | ➡️ modern 白名单 | ➡️ knowledge 术语白名单最宽 | ➡️ 视题材定 |
| `check_ai_tone`（AI味） | ✅ 严格 | ➡️ 放宽 | ➡️ 放宽 | ➡️ 放宽 |
| `check_ai_cliches`（套话黑名单，v2 通用） | ✅ | ✅ | ✅ | ✅ |
| `check_numeric_facts` auto（数字硬错误，v2 通用） | ✅ | ✅ | ✅ | ✅ |
| `check_numeric_facts` manual（N年/岁/品，v2） | ✅ 标记 | ➡️ content_quality 层过滤误标项 | ➡️ content_quality 层过滤误标项 | ⏭ 跳过 |
| `check_soft_ai_pattern` | ✅ | ✅ | ✅ | ✅ |
| `check_redundant_citation` | ✅ | ✅ | ✅ | ⏭ 跳过 |
| `check_inline_references` / `check_sources_section` | ✅ | ✅ | ✅ | ⏭ 跳过 |
| `check_modern_jargon_terms`（硬套术语） | ✅ | ✅ | ✅ | ✅ |
| `check_chapter_title_soul`（v2，古籍向） | ✅ | ⏭ 跳过 | ⏭ 跳过 | ⏭ 跳过 |
| 术语白名单 | — | `MODERN_ENGLISH_WHITELIST`（已有 22 词） | 新增 `KNOWLEDGE_TERMS_WHITELIST` | — |
| fiction 专属 | — | — | — | 视角一致性、人物弧光、伏笔回收（待设计） |

> **v2 关键**：`check_ai_cliches` 和 `check_numeric_facts` 的 auto_errors 是通用检查（BUG-026 教训：灵魂再好数字错了仍是 P0），**所有桶都跑**；只有 numeric 的 manual_review 触发词按桶调整。现有 `_is_modern_column` 的关键词列表（8 词）漏掉财/技/养生，本质就是没接 archetype——阶段 2 彻底解决。

---

## 九、提示词分桶细则

### 9.1 narrative 桶（原封不动）
保留 `prompts/{historian,biographer,context_analyst,critic,philosopher,editor,orchestrator}.md`，内容不动。
**v2**：tone_setter/chief_editor 的古籍版 prompt 从代码内联迁到 `prompts/narrative/tone_setter.md`、`prompts/narrative/chief_editor.md`（内容不变，只是位置迁移）。

### 9.2 modern 桶（新建 `prompts/modern/`）
- 去掉：臣光曰、王夫之、文言≤20字、《资治通鉴》卷次核验、白话小说笔法
- 保留并改造：场景化入戏、方法论拆解、避坑清单、践行行动项
- 引用：现代财经/管理/科普来源（格雷厄姆、达利欧、塔勒布…），不强制古籍名家
- **v2 tone_setter 版**：核心洞察/实用基调/核心矛盾/操作锚点（替换"核心史观/情感基调/灵魂锚点"）
- **v2 chief_editor 版**：实用价值测试/方法独家性/落地可行性（替换"活人测试/洞察独家性/底色敬畏感"）
- 参考已有资产：理财课已自发形成的「入戏/破题/经典时刻/故事展开/拆解与连接」结构

### 9.3 knowledge 桶（新建 `prompts/knowledge/`）
- 去掉：叙事人物背景骨架、文言、名家点评
- 强调：概念定义准确、原理递进、工程实践、术语首次出现给中英对照、自测三问
- **v2 tone_setter 版**：核心原理/认知基调/核心难点/示例锚点
- **v2 chief_editor 版**：准确性测试/深度独家性/可操作性
- 参考已有资产：`.cache/ai_course_style.md`（`loop_log.md:304` 提到的 AI 专栏写作规范）
- 结构按知识模块（如 AI 课的「原理直觉/提示词工程/上下文工程/Agent与RAG」）

### 9.4 fiction 桶（预留 `prompts/fiction/`，待实现）
- 骨架：情节/人物弧光/冲突/伏笔回收
- 不要求史料核验、年份、名家点评
- 质检关注：视角一致性、人物动机、戏剧冲突、世界观自洽
- 待用户开始写小说时再设计

---

## 十、结构模板分桶细则

### 10.1 narrative 桶（原封不动）
```yaml
required_sections:
  - 讲事情
  - 讲人物
  - 讲背景
  - 讲道理
  - 问道悟道
  - 结语
```

### 10.2 modern 桶
```yaml
required_sections:
  - 入戏        # 场景化引入
  - 破题        # 核心论点
  - 方法论      # 拆解工具/方法
  - 避坑        # 常见误区
  - 践行        # 行动清单
```
> 理财课现有的「兵器与阵法/心法与避坑/守正与筑基/觉醒与破局/践行与自由」是 chapter 分组（大类），单篇内部结构收敛为上述 5 段。

### 10.3 knowledge 桶
```yaml
required_sections:
  - 概念        # 是什么
  - 原理        # 为什么
  - 实践        # 怎么用
  - 速查/自测   # 检索与巩固
```

### 10.4 fiction 桶（预留，待实现）
```yaml
required_sections:
  - 情节        # 推演与冲突
  - 人物        # 弧光与动机
  - 场景        # 世界观落地
  - 回收        # 伏笔回收
```

### 10.5 editor.py 改造
```python
SECTION_TEMPLATES = {
    "narrative": {"讲事情": "historian", "讲人物": "biographer", "讲背景": "context_analyst", "讲道理": "critic", "问道悟道": "philosopher", "结语": "editor"},
    "modern":    {"入戏": "historian", "破题": "critic", "方法论": "context_analyst", "避坑": "critic", "践行": "editor"},
    "knowledge": {"概念": "context_analyst", "原理": "historian", "实践": "biographer", "速查/自测": "editor"},
    # "fiction": {...},  # 待实现
}
# editor.run 读取 state["archetype"] 选模板
```
> modern/knowledge 桶复用现有 5 个 agent 的能力定位（讲事情→historian 的叙事能力转译为"入戏"），不新增 agent，符合"不过度工程化"。

### 10.6 workflow 文风注入按桶路由（v2 新增）
```python
# 替换 workflow.py:42-44 的 _USE_SOUL_INJECTION
def _soul_injection_for_archetype(archetype: str) -> str:
    """返回 'narrative' | 'modern' | 'knowledge' | 'skip'。
    narrative: 启用现版 tone_setter/chief_editor
    modern/knowledge: 启用对应桶版 prompt（阶段4落地后）
    未落地前或 fiction: skip
    """
    if archetype in ("narrative", "modern", "knowledge"):
        return archetype
    return "skip"
```
> 阶段 3 先做"narrative 启用 / 其他跳过"的最小版本；阶段 4 落地 modern/knowledge 版 prompt 后再开启对应桶。

---

## 十一、测试与回归策略

### 11.1 类型识别测试（阶段 1 必做）
- `tests/test_archetype.py`：`resolve_archetype` 覆盖 6 个 category 默认值 + 显式覆盖路径
- 16 个现有专栏的 archetype 归类断言（防止理财课误判为 narrative）

### 11.2 质检分桶回归（阶段 2 必做）
- 每桶一份黄金样本 + 分数断言
- 对比指标：理财课/AI课改造前后质检误报数应显著下降
- 古籍专栏分数不降（防回归）
- **v2**：`check_numeric_facts` manual_review 误标用例（modern 的"N 年收益率"、knowledge 的"N 个 token"）必须有断言
- 落实 BUG-024 教训：`loop_log.md:887`"并行质检后必须重跑分数"

### 11.3 结构模板 + 文风注入测试（阶段 3）
- `modern` 桶生成结果含 5 段、`knowledge` 桶含 4 段
- `narrative` 桶仍 6 段不变
- **v2**：narrative 桶走 tone_setter→chief_editor 全链路；modern/knowledge 桶在阶段4前跳过这俩节点（不断链）

### 11.4 提示词加载测试（阶段 4）
- `load_prompt("historian", archetype="modern")` 命中 `prompts/modern/historian.md`
- `load_prompt("historian", archetype="narrative")` 命中 `prompts/historian.md`（兼容）
- **v2**：`load_prompt("tone_setter", archetype="narrative")` 命中迁出的 `prompts/narrative/tone_setter.md`，内容与原内联 PROMPT 一致

### 11.5 全量回归（每阶段结束）
- `python scripts/check_book_structure.py --output output --strict`
- `pytest -q`
- `bash tests/run_regression_suite.sh`
- **v2 已知**：`langgraph` 未安装时 4 个测试 collection error（`loop_log.md:276`），属环境依赖，非本次引入

---

## 十二、风险与约束

| 风险 | 缓解 |
|---|---|
| 古籍专栏被误改 | narrative 桶 prompt/config/规则全程零改动，作为基线护栏 |
| 桶数膨胀 | 4 条开桶硬标准把关；更细差异交给桶内章节模板，不轻易开新桶 |
| archetype 判定错配（理财课被判 narrative） | 16 专栏归类断言 + `_meta.yaml` 显式声明优先 |
| editor 模板改造破坏现有六段 | 阶段 3 前先加 narrative 桶六段回归测试 |
| Skill 边界越界 | archetype 路由逻辑只在 Python 层，Skill 仅识别并传参（`dev-workflow.md §零`） |
| 跨桶专栏（经/技混合） | 显式覆盖机制（`_meta.yaml` archetype 字段 > 默认映射） |
| fiction 桶设计与现有 agent 能力错位 | fiction 桶预留，待真要写小说时单独评估是否新增 agent |
| **v2：soul injection 节点断链** | modern/knowledge 桶在阶段4前"跳过"tone_setter/chief_editor，走原 else 分支边保持 save 链路完整（复用现有 ImportError 兜底） |
| **v2：quality.py 禁区** | 红线：quality.py 函数内部零改动；numeric manual_review 误标在 content_quality.py 调用层过滤，不碰 quality.py |

**禁区遵守**（`dev-workflow.md §四`，v2 修正）：
- `deep-reading/rules.md`、`prompts/` 7 份古籍提示词、`quality.py` 的**古籍专属规则**不在"修改"范围——本方案是**新增** modern/knowledge 桶文件，narrative 桶原封不动。
- `quality.py` 的 `check_ai_cliches`/`check_numeric_facts` 是 master 已落地的通用检查，全桶共享，不归禁区。

---

## 十三、沉淀计划

1. `docs/loop_log.md` 追加分桶改造沉淀记录。
2. `.trae/rules/` 评估是否新增 `archetype-routing.md` 规则（如复用频率高）。
3. `.trae/checklists/dev-checklist.md` 评估是否新增"新专栏需声明 archetype"检查项。
4. 落实 `loop_log.md:298` 早就建议但未做的"rules.md 声明适用范围"。
5. **v2**：落实 `src/agents/tone_setter.py` / `chief_editor.py` 的 TODO（内联 prompt 迁到 `prompts/`），与阶段 4 合并完成。

---

## 附录 A：archetype 判定伪代码

```python
ARCHETYPE_DEFAULTS = {
    "史": "narrative",
    "经": "narrative",
    "养生": "modern",
    "财": "modern",
    "职场": "modern",
    "技": "knowledge",
}

VALID_ARCHETYPES = {"narrative", "modern", "knowledge", "fiction"}

def resolve_archetype(category: str, explicit: str | None = None) -> str:
    if explicit in VALID_ARCHETYPES:
        return explicit
    value = ARCHETYPE_DEFAULTS.get(category, "narrative")
    # config 值合法性校验（防笔误脏值污染下游），与生产实现 src/utils/prompts.py:56-60 对齐
    return value if value in VALID_ARCHETYPES else "narrative"
```

---

## 附录 B：评审路径

本草案如需真并行评审：配置 `.env` 的 `LLM_API_KEY` 后执行
```bash
python scripts/review_plan.py --plan docs/archetype-design/design.md --output docs/reviews/archetype_review_YYYYMMDD.md
```
将触发架构师/测试/规则三 Agent 真并行评审。
当前 v2 结论由路径 A（单 agent 串行三视角）完成，符合 `dev-workflow.md §零` 能力边界。

---

## 修订记录

- **2026-06-26 v1**：三桶（narrative/modern/knowledge）+ 五阶段迁移。
- **2026-06-26 v1 修订**：补充 `fiction` 桶预留 + 4 条开桶判定标准（回应"未来写小说/数据结构/算法/Python/Redis 归哪类"）。
- **2026-06-26 v2**：对照 Soul Injection 改造（master PR #14）修订。新增 §六（与 Soul Injection 协同关系）、七处变更融入各章节：workflow.py 行号更新（94-114/174-214）、tone_setter/chief_editor 纳入分桶、`SOUL_INJECTION_ENABLED` 升级为按 archetype 决策、quality.py 禁区边界修正（通用检查全桶共享）、`check_numeric_facts` manual_review 按桶调整、阶段 3/4 合并 prompt 迁移、BUG-026 教训纳入质检分桶。基于最新 master `e982da1` 重建分支。
