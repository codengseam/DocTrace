# 反馈循环规划：写作资产保留与正循环迭代

> 状态：草案 v1（2026-06-27）
> 作者：用户提出想法，主 Agent + 三视角 subagent 摸底，主 Agent 汇总成文
> 关联：本规划是 [archetype-design/design.md](../archetype-design/design.md) 在"反馈回收侧"的对照补全；archetype 升级在生成侧做了正交分层，本规划负责把"产出 → 反馈 → 沉淀 → 反哺"的回路补齐
> 范围声明：本文是**规划文档**，不含代码改动。所有"现状"数据均来自 2026-06-27 三个 subagent 的实测证据，未实测者不写入

---

## 一、背景与缘起

### 1.1 想法来源

用户在 2026-06-27 archetype 架构分类升级完成后提出：

> 我有一个想法，今天不是对架构做了分类和升级吗，我想先看看能不能找到之前的创建的提示词，把历史的提示词、引用的文献，这些对写作比较有用的东西能不能保留下来，包括智能体对产出专栏质量的各个方面的评分，还有就是未来我发到网上后得到的反馈（比如点赞、阅读量、收益、反馈）这些东西，让这套框架更好地正循环反馈快速跑起来。

### 1.2 核心目标

**让这套专栏生产框架能"跑起来"——历史产出 → 沉淀 → 反哺 → 改进 → 更好的产出。**

四类可复用资产 + 反馈数据：

1. 历史提示词（prompts/ 三桶）
2. 引用文献/参考资料
3. 智能体对产出专栏质量的多维度评分
4. 发布后真实读者反馈（点赞/阅读量/收益/反馈）

### 1.3 与 archetype 升级的关系

**archetype 升级是反馈循环的"放大器"，但当前没接电。**

依据 [archetype-design/design.md §五](../archetype-design/design.md)：

- 升级五阶段全部聚焦"生成侧怎么更贴切"，新增字段（`AgentState.archetype`、`_meta.yaml.archetype`、`section_templates`）全部服务生成。
- 数据流是单向的"输入 → 生成 → 质检 → 保存"，**没有"发布 → 反馈 → 回流 → 优化"回路**。
- 好消息：有了 archetype 维度后，反馈数据可按桶分析"哪种范式读者反馈更好"——这种洞察只有升级后才可能做出来。
- 坏消息：archetype 字段当前没在反馈侧承载，如果未来接入反馈数据时不在 schema 里带上 `archetype`，今天的架构升级就白做了。

**本规划的核心约束之一：第三档反馈 schema 设计时，必须把 `archetype` 作为必填维度。**

---

## 二、当前现状（实测依据）

本节所有"现状"陈述均来自 2026-06-27 三个 subagent 实测，附文件路径与行号证据。

### 2.1 四类资产成熟度对照

| 资产 | 现状 | 成熟度 | 关键缺口 |
|---|---|---|---|
| **① 智能体质量评分** | [content_quality.py](../../src/utils/content_quality.py) 已有 0-100 分四维度引擎；但[生成管线 workflow.py](../../src/core/workflow.py#L19) 调的是 legacy `run_quality_checks`（无 score），[save_node 不记 score](../../src/core/workflow.py#L198)，frontmatter 八字段无 score，无 score_history 文件 | **引擎已就绪，只差接线** | 评分跑完即丢、不落盘、无历史、无趋势 |
| **② 历史提示词** | [prompts/](../../prompts/) 三桶共 28 文件，无 version/changelog/AB 对照字段；只靠 git commit 留痕；rules.md 里散见 inline「v1.1 新增」注释但无集中 changelog | **半结构化** | 无版本机制、无 AB 对照、无失效归档 |
| **③ 引用文献** | 完全 inline 在 output 里（行内 `——《XX·XX》` + 文末 `## 参考来源`），[_meta.yaml](../../output/史记/_meta.yaml) 无 bibliography 字段；[quality.py check_citations](../../src/utils/quality.py#L181) 只判有没有书名号，不核验真实性 | **完全 inline** | 无结构化、无版本/底本、无准确性核验 |
| **④ 发布后反馈** | 全项目搜 feedback/analytics/metrics/revenue 60 个命中全是正文词，无任何基础设施；无公众号/知乎/小红书/Medium 对接；[_meta.yaml](../../output/AI大模型学习/_meta.yaml) 无反馈字段占位 | **完全空白** | schema 未定、平台未对接、回流路径未设计 |

### 2.2 质量评分机制详情

**已有引擎**：

- [src/utils/content_quality.py](../../src/utils/content_quality.py) 的 `run_content_quality_checks(content, archetype)` 返回 `ContentQualityReport{passed, score, issues, details}`，是项目里唯一带 0-100 数值分数的质检接口
- 四维度计分（从 100 起扣）：真实性 `truth`（上限扣 20）/ 可读性 `readability`（上限 20）/ 顺序 `sequence`（上限 10）/ 引用克制 `citation`（上限 15），`passed = score >= 85`，按 archetype 路由
- [src/utils/quality.py](../../src/utils/quality.py) 的 `check_chapter_title_soul` 对单个分节标题打 0-5 分（三维度：信息密度/灵魂指向/呼应节奏）

**关键债**：

1. **生成管线与质检引擎脱节**：[workflow.py quality_node](../../src/core/workflow.py#L19) 调的是 legacy `run_quality_checks`（无 score），不是 `run_content_quality_checks`（带 score）。生成时只做 pass/fail 门控，分数根本没进入管线状态。
2. **save_node 不记 score**：[workflow.py save_node](../../src/core/workflow.py#L198) 写的 log 文件只记录"质量问题: [errors]"列表，不记录 score。
3. **frontmatter 不含 score**：产出文章 frontmatter 八字段（title/book/chapter/event/created_at/source_agents/sort/chapter_sort）无 score，事后无法回查某篇文章当时评分。
4. **规则与实现不一致**：[content-quality.md §一](../../.trae/skills/deep-reading/content-quality.md) 写五维度（真实性 35/可读性 25/顺序 15/引用克制 10/灵魂 15），但 [content_quality.py](../../src/utils/content_quality.py) 实际只四维度自动计分，灵魂维度（§9 灵魂三问）没有自动算分逻辑，只能由 Agent/人工判断。直接落盘 score 会让"灵魂分"漂移。
5. **无历史/趋势文件**：score_history / quality_log / metrics 三类文件均不存在；[docs/reviews/](../../docs/reviews/) 下只有 8 个临时报告，无按文章持续记录的评分历史。
6. **专栏级无聚合**：[scripts/check_book_structure.py](../../scripts/check_book_structure.py) 合并门只数 P0/P1/P2 问题不算分；无任何脚本批量遍历 `output/**/*.md` 跑 `run_content_quality_checks` 求平均/最低/趋势；[loop_log.md L264](../../docs/loop_log.md#L264) 写"全 67 章最低 97 最高 100 平均 99.4"是**人工手写**的聚合数字，无可追溯数字源文件。

### 2.3 提示词与文献详情

**提示词资产**：

- [prompts/](../../prompts/) 三桶布局：根目录 narrative 桶（12 文件）+ [prompts/modern/](../../prompts/modern/)（8 文件）+ [prompts/knowledge/](../../prompts/knowledge/)（8 文件）
- 加载器 [src/utils/prompts.py](../../src/utils/prompts.py) 的 `load_prompt(name, variables, archetype="narrative")`：modern/knowledge 缺文件时 fallback 到 narrative 原路径并打 UserWarning
- persona/system prompt 不在 [src/agents/](../../src/agents/) 的 .py 文件里，全部在 prompts/*.md 中；.py 文件只含 run 逻辑
- **缺口**：prompts/ 全目录零 version/changelog 命中；modern/knowledge 子目录各缺 orchestrator/content_reviewer/content_reviewer_sub/plan_reviewer 这 4 个；rules.md 里散见「v1.1 新增」「LoopAgent 第 N 章测评后新增」这类 inline 注释，但**没有集中的 changelog 文件**

**引用文献**：

- 全项目搜 bibliography/references/citations/sources，**没有任何独立目录或文件**
- 引用信息**完全 inline** 在 output md 里：
  - 行内引用：散落正文，格式「原文上下文——《书名·篇名》」
  - 文末 `## 参考来源` 章节：纯文本列表 `- 《书名·篇名》（对应内容）`，非结构化字段，无法批量检索
  - [_meta.yaml](../../output/史记/_meta.yaml) 仅含 6-7 字段（title/category/archetype/author/description/cover/sort），无 bibliography/references/版本/底本/译本字段
- **缺口**：
  - [quality.py check_citations](../../src/utils/quality.py#L181) 极弱，只判 content 里有没有 `《` 或 `原文` 二字，**无法识别编造的来源**（LLM 编一个不存在的《XX·XX》也 pass）
  - [check_famous_critics](../../src/utils/content_quality.py) 只做**名单字符串匹配**，不核验引文真实性
  - 引用校验全靠 [content_reviewer Agent](../../prompts/content_reviewer.md) 用 LLM 复核，是人工+LLM 流程，不是代码层硬校验

### 2.4 反馈循环基础设施详情

**LoopAgent 思维（开发侧）已成熟**：

- [docs/loop_log.md](../../docs/loop_log.md) 已建立"索引区 + 教训计数表 + #lesson slug 体系 + 方案 C 手册"四件套
- 7 个受控 slug（loop_log.md L1066-1074）：`git_hygiene` / `reader_interaction` / `content_quality` / `book_structure` / `deployment` / `soul_injection` / `ai_course`
- 教训计数（loop_log.md L30-38）：`book_structure` 11 次、`reader_interaction` 10 次、`content_quality` 6 次等
- [dev-workflow.md §五](../../.trae/rules/dev-workflow.md) 第五步"沉淀"定义了启发式写入门槛
- [dev-checklist.md](../../.trae/checklists/dev-checklist.md) 七维度检查清单（代码质量/项目规范/测试/依赖/文档/Skill 边界/LoopAgent 沉淀）
- **关键缺口**：loop_log 只记"开发教训"，**完全不记"内容效果反馈"**——没有"某篇笔记读者反馈如何""哪类内容阅读量高""哪条灵魂注入被读者点赞"这类记录；7 个 slug 主题表里没有任何与"反馈/效果/收益"相关的 slug

**外部反馈数据接入（完全空白）**：

- 全项目搜 feedback/analytics/metrics/revenue/engagement/阅读量/点赞/收藏/转化/收益/粉丝/互动/曝光，命中 60 个文件**全部是 output/ 下的讲书正文内容文件**（正文里提到这些词），**没有任何 src/、scripts/、site/js/、config.yaml、.trae/ 下的基础设施文件命中**
- [config.yaml](../../config.yaml) 只有 `trusted_domains`（搜索白名单）、`mcp_servers`（pdf_reader / obsidian）、`google_search_api_key`、`archetype_defaults`、`section_templates`、`quality_check`
- **没有任何外部发布平台的接口、配置、同步逻辑**——没有微信公众号 API、没有知乎专栏 API、没有小红书/Medium/掘金对接；当前"发布"只等于 GitHub Pages + 魔搭 ModelScope 部署静态站点，这是内容托管，不是反馈回收

**评论系统的概念边界（必须澄清）**：

项目已有一套 [docs/comments-system/](../../docs/comments-system/) 评论系统设计 + [site/versions/](../../site/versions/A-feishu/js/comments.js) 三个视觉方向的完整原型，但**这不是本规划说的"反馈循环"**：

- 服务对象：作者本人及少量受邀读者，**不是公开读者反馈回收**
- 闭环是"作者批注 → 导出 JSON → 本地跑 Python 专家团 → 回填评判 → 作者人工决定是否修订"，**完全不涉及发布后的真实读者数据**
- 评论类型：error/praise/discussion/supplement/thought（作者对原文的批注），**不是读者阅读后的效果反馈**
- 三个原型在 `site/versions/` 隔离区未合入主线，Python 侧消费链路（`src/main.py --expert-review` 入口、`load_author_comments`、`AgentState.author_comments` 字段、`prompts/*.md` 的 `{{author_comments}}` 占位符）**完全未实现**

**结论**：评论系统回收的是"内容质量维度的反馈"，本规划要回收的是"阅读量/点赞/收益/转化这类效果反馈"——是两件事，定位必须分清，别让概念混淆把方向带偏。

---

## 三、目标收益

### 3.1 短期收益（第一档做完即得）

1. **可追溯的评分历史**：每篇产出自动落盘 score，回答"最近 N 篇评分趋势如何""哪类 archetype 评分更稳""哪类问题反复扣分"——这是反馈循环唯一不需要外部数据就能跑起来的部分
2. **专栏级聚合能力**：批量遍历 output/ 跑评分引擎，自动产出"全 X 章最低 Y 最高 Z 平均 W"——替代 [loop_log L264](../../docs/loop_log.md#L264) 当前的人工手写
3. **生成管线数据自洽**：管线跑出来的 score 进入 AgentState 和 frontmatter，事后可回查某篇文章当时评分，不再"跑完即丢"

### 3.2 中期收益（第二档做完即得）

1. **提示词演进可追溯**：建立 prompts/CHANGELOG.md 后，能回答"上次改 chief_editor.md 是为什么改、AB 结果如何、改了之后分数变化多少"
2. **文献可检索**：把文末 `## 参考来源` 抽成 frontmatter 结构化字段后，[sources.py extract_sources](../../src/utils/sources.py) 能批量检索"哪些文章引用了《史记·项羽本纪》"，支撑后续引用核验
3. **灵魂维度规范化**：补齐 content-quality.md 五维度 vs 实现四维度的不一致，让评分落盘的数据有规范语义

### 3.3 长期收益（第三档做完即得）

1. **真正的反馈闭环**：发布后真实读者数据回流，能回答"读者到底买不买账"——前两档的"评分历史"和"提示词版本"才能从内部自评升级为外部反馈校准
2. **archetype 维度洞察**：按 archetype 切分反馈数据，能回答"narrative 桶的史记类比 modern 桶的理财课，点赞率高多少"——这是 archetype 升级红利的兑现
3. **内容侧 LoopAgent 落地**：在 [loop_log.md](../../docs/loop_log.md) 新增 `content_feedback` / `engagement` 等 slug，让"内容效果"也能像"开发教训"一样沉淀迭代

### 3.4 整体目标（一句话版）

**让"开发侧 LoopAgent"（已成熟）和"内容侧反馈循环"（当前空白）形成双轮驱动，让框架产出从"每次从零开始"升级为"基于历史和反馈持续优化"。**

---

## 四、优先级与实施路径

按"价值/成本"排序，三档递进，**不要一锅烩**。

### 4.1 第一档｜立即值得做：质量评分接入生成管线 + 落盘 + score_history

**为什么是第一档**：引擎已存在（[content_quality.py](../../src/utils/content_quality.py) 返回 `{passed, score, issues, details}`），缺的只是接线。这是反馈循环唯一不需要外部数据就能跑起来的部分。

**实施清单**：

1. [src/core/workflow.py quality_node](../../src/core/workflow.py#L19) 从 `run_quality_checks` 换成 `run_content_quality_checks`，把 score 灌进 AgentState
2. [src/core/workflow.py save_node](../../src/core/workflow.py#L198) 把 score 写进单篇 frontmatter（新增 `quality_score` / `quality_dimensions` 字段）和书级 [_meta.yaml](../../output/史记/_meta.yaml)（新增 `avg_score` / `min_score` 聚合字段）
3. 新增 `docs/reviews/score_history_{书名}.yaml`，每篇产出 append 一条 `{date, book, chapter, archetype, score, dimensions}`，攒趋势
4. 新增 `scripts/score_aggregate.py` 批量遍历 output/ 跑评分引擎，输出专栏级聚合报告
5. 顺手修规则与实现不一致：[content-quality.md §一](../../.trae/skills/deep-reading/content-quality.md) 五维度 vs [content_quality.py](../../src/utils/content_quality.py) 四维度——要么补齐灵魂维度自动算分，要么在 score_history 里标注"灵魂维度为人工评分"

**前置依赖**：无

**风险**：换 quality_node 接口可能影响 [check_book_structure.py](../../scripts/check_book_structure.py) 的 pass/fail 门控逻辑，需要回归测试集验证

### 4.2 第二档｜值得做但要先想清楚：提示词版本化 + 文献结构化

**提示词版本化**：

- 引入 `prompts/CHANGELOG.md`（轻量，记录"哪天改了哪个 prompt 的哪段、为什么改、AB 结果如何"）
- **不上重型的版本号系统**——依据：第一个 subagent 报告"prompts/ 全目录零 version/changelog 命中"，说明当前没必要复杂机制，能记录演进即可
- 若有 AB 对照，对照结果回流到 [score_history](#41第一档立即值得做质量评分接入生成管线--落盘--score_history)（第一档产出），形成"改了 prompt → 看分数变化"的闭环

**文献结构化**：

- 把文末 `## 参考来源`（纯文本 `- 《书名·篇名》（对应内容）`）抽成 frontmatter 里的 `references: [{book, chapter, anchor}]` 结构化字段
- 让 [sources.py extract_sources](../../src/utils/sources.py) 能批量检索
- **不上准确性核验引擎**——依据：当前 [check_citations](../../src/utils/quality.py#L181) 极弱（只判有没有书名号），准确性核验需要外部古籍文本库，超出本规划范围

**前置依赖**：第一档的 score_history 落地（提示词 AB 结果要回流到 score_history 才有意义）

**风险**：现有 output 下所有 .md 文件需要迁移 frontmatter，工作量大；建议只对新增产出启用，历史产出按需补

### 4.3 第三档｜最关键但风险最大：发布后反馈接入

**为什么最关键**：没有真实读者数据，前两档的"评分历史"和"提示词版本"都只是内部自评，无法回答"读者到底买不买账"。

**为什么风险最大**：四件事必须先想清楚再动——

1. **平台选哪个**：公众号/知乎/小红书/Medium 各家 API 烟囱式不互通，**先选 1-2 个高频发布平台**，别一上来铺 6 个对接
2. **schema 先定**：点赞/阅读量/收益这些字段在不同平台语义不同（公众号"在看"≠知乎"赞同"≠小红书"赞+收藏"），不要直接照搬字段名，要先抽象成 `engagement_score` / `reach` / `revenue` 三类内部指标
3. **回流路径**：手动填（你每天看后台填进 yaml）还是 API 自动同步？**建议先手动填 + 字段占位**，跑通闭环再考虑 API——依据：手动填启动成本低、API 同步维护成本高，且不同平台 API 政策会变
4. **反馈怎么用**：回收的数据要能反哺生成侧才有意义。建议接到 archetype 维度——"narrative 桶哪类标题阅读量高""modern 桶哪类开头留存好"

**关键约束**：反馈 schema 设计时，**必须把 `archetype` 作为必填维度**——这是今天 archetype 升级红利兑现的唯一路径。

**前置依赖**：第一档的 score_history（反馈数据要和评分历史一起看才有意义）

**风险**：外部平台 API 政策变化、数据合规、不同平台指标不可比

---

## 五、三个必须避开的陷阱

### 5.1 别把"评论系统"误当成"反馈循环基础设施"

[docs/comments-system/](../../docs/comments-system/) 那套是"**作者对原文的批注**"反馈（error/praise/discussion/supplement/thought），不是"读者阅读后的效果"反馈。三个原型在 [site/versions/](../../site/versions/A-feishu/js/comments.js) 未合入主线，Python 侧消费链路完全没接。**它和你要的"点赞/阅读量/收益"是两件事**。

依据：第三个 subagent 报告，评论系统 spec.md §1.1、§二 明确写"服务对象是作者本人及少量受邀读者""纯静态零后端，访客的批注无法汇总到作者"。

### 5.2 评分引擎和生成管线脱节是当前最大债

[workflow.py](../../src/core/workflow.py#L19) 用 legacy 接口不算 score——这意味着即使建了 score_history 文件，里面也是空的。第一档的三件事里，"换接口"必须先做，否则后续都无数据可落盘。

依据：第二个 subagent 报告，[content_review_workflow.py](../../src/core/content_review_workflow.py) 的 state 只存 `final_report`（Markdown 文本），没有 score 字段，没有持久化到磁盘的步骤。

### 5.3 规则与实现不一致会污染评分历史

[content-quality.md §一](../../.trae/skills/deep-reading/content-quality.md) 写五维度（含灵魂 15 分），但 [content_quality.py](../../src/utils/content_quality.py) 实际只四维度自动计分，灵魂维度靠人工/Agent 判断。如果直接落盘 score，"灵魂分"会漂移——要么先补齐灵魂维度的自动算分，要么在 score_history 里标注"灵魂维度为人工评分"。

依据：第二个 subagent 报告，规则文件声称五维度，但 `run_content_quality_checks` 实际只对四维度自动计分（truth/readability/sequence/citation），灵魂维度（§9 灵魂三问）没有自动算分逻辑。

---

## 六、核心建议（一句话版）

**先做第一档（评分接入管线 + 落盘 + score_history），这是唯一不需要外部数据就能跑起来的反馈循环种子；第二档看精力；第三档动手前必须先定 schema 和平台，且必须把 archetype 作为反馈数据的必填维度。**

---

## 七、后续动作

本规划文档落地后，下一步建议：

1. **就第一档出详细实施计划**：具体改 [workflow.py](../../src/core/workflow.py) 哪几行、frontmatter 加哪个字段、score_history 文件结构怎么设计、要不要顺带把"五维度 vs 四维度不一致"先修了
2. **第二档暂不动**：等第一档跑稳、有 score_history 数据后再判断是否值得做提示词版本化
3. **第三档先做调研**：用户先想清楚发到哪个平台（公众号/知乎/小红书），再决定 schema 怎么定；动手前必须先和 archetype 维度绑定

---

## 八、本文档的约束与边界

- **本规划是规划文档，不含代码改动**。所有"现状"陈述均来自 2026-06-27 三个 subagent 实测，未实测者不写入。
- 本规划**不修改** [deep-reading/rules.md](../../.trae/skills/deep-reading/rules.md) / [content-quality.md](../../.trae/skills/deep-reading/content-quality.md) / [prompts/](../../prompts/) 下 7 份讲书提示词 / [src/utils/quality.py](../../src/utils/quality.py)（这些在 [dev-workflow.md §四](../../.trae/rules/dev-workflow.md) 禁区范围内）。
- 本规划**不替代** [archetype-design/design.md](../archetype-design/design.md)，是其"反馈回收侧"的对照补全。
- 本规划**不等同于** [comments-system/](../../docs/comments-system/) 评论系统，两者反馈来源不同（作者批注 vs 读者效果），定位要分清。
