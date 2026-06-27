# HaloRead：个人知识体系生成引擎

> 读完一段材料后输入书名+章节，AI Agent 专家团自主选择可信资料，按"叙事范式"分桶生成 Markdown 笔记，进入 Obsidian Vault + 静态站点阅读器。
> 不做 RAG、不向量化、不存储整书内容。输出固定为 Markdown。目标：**可信、有灵魂、有洞察**。

## 一、项目定位

HaloRead 起于"读古籍后输入书名+章节，AI 生成讲书笔记"，现已演化为**一套引擎、三桶叙事范式**适配多类目的个人知识体系生成器。

- **已覆盖 6 大类目、16+ 专栏、数百篇笔记**：史（资治通鉴/史记/三国/唐纪/宋纪/明纪/孔子传）、经（论语/易经课）、养生（饮食/锻炼/睡眠）、财（理财课）、技（AI 大模型/大厂晋升）、职场（沟通/面试）。
- **本地优先**：所有输出 Markdown，直接进 Obsidian，可链接、可检索、可沉淀。
- **可信闭环**：每个观点有来源，每个名家点评有出处；引用必须具体到原文和书名。
- **辅助开智悟道**：不止于讲故事，更要通过现象看本质，提炼人性、权力、组织的底层规律。

## 二、核心设计理念

四条贯穿全项目的设计哲学：

1. **双维度正交**：`category`（写什么）只服务展示分组与排序；`archetype`（怎么写）才进入生成层与质检层。一个 category 可含多个 archetype——"经"里论语=narrative、易经课=knowledge，因此 archetype 必须独立存在，不能由 category 单值推导。详见 [docs/archetype-design/design.md](docs/archetype-design/design.md)。
2. **共用层厚，差异化层薄**：Orchestrator、LangGraph 编排、Editor 汇总、质检骨架、Skill 入口、结构校验全部共用；三桶差异化只有「结构模板段名 + 提示词子目录 + 文风注入 prompt 版本」三件。不搞多套 agent 系统。
3. **怎么写 vs 怎么查分工**：[rules-*.md](.trae/skills/deep-reading/rules.md) 给 Agent 看的写作骨架与笔法；[content-quality.md §8](.trae/skills/deep-reading/content-quality.md) 给质检引擎看的扣分规则与白名单。两者互相引用不重复，避免双源维护。
4. **沉淀即闭环**：开发产出不只是 commit，还有可校验的开发日志（[loop_log.md](docs/loop_log.md) 索引化 + [check_loop_log.py](scripts/check_loop_log.py) 门禁 + 方案 C 把教训固化为 checklist）。

## 三、整体架构与数据流

```
用户输入（Trae 对话框 / HTML 界面）
    │
    ▼
Trae Skill（deep-reading）   ── 识别 archetype（信源优先级链见下）
    │
    ▼
Python 编排引擎（LangGraph） ── build_workflow(archetype) 动态构建边链
    │
    ├─ Orchestrator（解析输入 / 规划 specialist）
    ├─ ToneSetter（按 archetype 路由定调，narrative/modern/knowledge 三桶）
    ├─ Specialist Agents（动态裁剪：narrative=5 / modern=3 / knowledge=3）
    ├─ Editor（按 archetype 汇总 SECTION_TEMPLATES）
    ├─ ContentReviewer（五维度质检 + 三视角并行）
    └─ ChiefEditor（总编一票否决 / 打回重做）
    │
    ▼
Markdown → output/{书名}/{章节}_{事件}.md → Obsidian Vault + 静态站点
```

**archetype 信源优先级链**：`CLI --archetype` > `_meta.yaml.archetype` > `category → archetype` 默认映射（史/经→narrative、养生/财/职场→modern、技→knowledge）> 经/技混合桶问用户 > narrative 兜底。**保证古籍专栏零回归**。

**关键架构创新——边链裁剪**：`build_workflow` 从 `editor.SECTION_TEMPLATES[archetype]` 的 values 反查所需 specialist 名单，按需 `add_node` + `add_edge`，未映射者不注册。modern 桶不注册 biographer/philosopher，knowledge 桶不注册 critic/philosopher，避免占位节点产空段污染下游汇总。

## 四、内容生成：三桶 archetype

按"怎么写"（叙事范式）分桶，不按"写什么"（主题类目）分桶。三桶结构模板对照：

| 维度 | narrative（古籍叙事） | modern（现代方法论） | knowledge（知识体系） |
|---|---|---|---|
| 段数 | 5 段 + 结语 | 5 段 | 4 段 |
| 段名 | 讲事情 / 讲人物 / 讲背景 / 讲道理 / 问道悟道 | 入戏 / 破题 / 方法论 / 避坑 / 践行 | 概念 / 原理 / 实践 / 速查自测 |
| specialist 数 | 5（historian/biographer/context_analyst/critic/philosopher） | 3（historian/critic/context_analyst） | 3（historian/biographer/context_analyst） |
| 灵魂载体 | 残酷底色 + 史观穿透 | 洞察独家性 + 落地可行性 | 准确性 + 深度独家性 + 可操作性 |
| 写作规则 | [rules.md](.trae/skills/deep-reading/rules.md) | [rules-modern.md](.trae/skills/deep-reading/rules-modern.md) | [rules-knowledge.md](.trae/skills/deep-reading/rules-knowledge.md) |
| 质检分桶 | §8.1（年份/名家/现代术语禁用全检） | §8.2（白名单 + AI 味放宽） | §8.3（术语中英对照 + 准确性核验） |

写作规则三件套分工：narrative 是 [dev-workflow.md](.trae/rules/dev-workflow.md) §四 禁区（正文零改动，仅顶部加适用范围声明）；modern/knowledge 管"怎么写"，content-quality.md §8 管"怎么查"，两者互相引用不重复。

## 五、灵魂注入与总编机制

对标当年明月《明朝那些事儿》笔法，让 AI 内容有"活人感"和史观穿透力。三件套：

- **ToneSetter（定调节点）**：5 Specialist 并行前串行注入五要素大纲（核心史观 / 情感基调 / 核心冲突 / 灵魂锚点 / 风格锚点，300-500 字）。按 archetype 路由 prompt 版本，逐篇换调而非统一个调。
- **ChiefEditor（总编 Agent，一票否决）**：合规质检管"对不对"（错别字/引用/frontmatter），总编管"值不值得发"。灵魂三问（活人测试 / 洞察独家性 / 底色敬畏感）任一 fail 即 REWORK 并附重做方向；试点期只打标记，校准后强制打回。**职责分层不合并**。
- **章回体灵魂标题三维度评分**（[chapter-title-soul SKILL.md](.trae/skills/chapter-title-soul/SKILL.md)）：信息密度(0-2) / 灵魂指向(0-2) / 呼应节奏(0-1)，<3 分必重写；区分"事件标签"与"信息密度不足的诗化标题"双失败模式，5 好 4 坏模式 + 决策树；由 [quality.py](src/utils/quality.py) 的 `check_chapter_title_soul` 自动拦截。

边链按 archetype 决策：`_soul_injection_for_archetype` 控双节点启用（三桶均启），`SOUL_INJECTION_ENABLED=0` 整体回退原管线。试点：明纪·海瑞上疏 AB 盲测 5 轮迭代后固化，参见 [docs/reviews/soul-injection-spec-20260626.md](docs/reviews/soul-injection-spec-20260626.md)。

## 六、内容质检体系

从四维度（真实/可读/顺序/引用）升级为**五维度**（新增"灵魂"15 分）：

| 维度 | 分值 | 检查项 |
|---|---|---|
| 真实性 | 35 | AI 幻觉、编造来源、人物世系、数字事实（`check_numeric_facts`） |
| 可读性 | 25 | AI 套话（`check_ai_cliches`）、现代术语、单章重复 |
| 顺序 | 15 | 叙事与章节排序按故事/时间先后 |
| 引用克制 | 10 | 删除内联跳转、行内引用密度 ≤3/千字 |
| 灵魂 | 15 | 灵魂三问 + 章回体灵魂标题评分 |

≥85 分合格。**双轨质检**：先跑 `run_content_quality_checks` 纯规则检测（含数字事实硬错误 + manual_review 按桶过滤误标），再触发 LangGraph 三视角并行质检（史实核验 / 可读性 / 引用克制 → summarize）。详见 [content-quality.md](.trae/skills/deep-reading/content-quality.md) 与 [src/utils/content_quality.py](src/utils/content_quality.py)。

分桶质检核心：古籍专属规则（年份/名家/现代术语禁用）仅 narrative 必检；通用红线（`check_ai_cliches` / `check_numeric_facts`）全桶共享。modern 桶白名单见 `MODERN_ENGLISH_WHITELIST`，避免 KPI/HR/offer 等行业通用词误报。

## 七、阅读器交互体验

静态站点阅读器（`src/web/static-site/` → `site/`）提供番茄小说式移动优先阅读体验：

- **沉浸模式**：纯 CSS 实现（`body.immersive-mode` + `ui-hidden`），点击中央唤出/隐藏 UI。**不调用 Fullscreen API / `screen.orientation.lock`**，避免国产浏览器强制横屏（BUG-021 教训）。
- **翻页**：移动端左 25% 上一屏、中 50% 切 UI、右 25% 下一屏；桌面端仅中央切 UI。touch/click 统一入口 + 位移/时长阈值防双触发，排除链接/按钮/代码块/弹层/文字选中。
- **壁纸 + 自动阅读**：三预设（无/竹简/山水）+ 透明度可调 + 夜间自动覆盖暗色纹理；自动阅读用 rAF 按行/分计速，到末尾/切章/呼出设置自动暂停，遵守 `prefers-reduced-motion`。
- **移动端适配主线**：吸底栏 `position:fixed` + `env(safe-area-inset-bottom)` + `viewport-fit=cover`；UI 隐藏用 `transform` 而非 `display:none`；代码块 `pre-wrap` 自动换行。

回归覆盖：[tests/test_reader_features.js](tests/test_reader_features.js) 79+ 项断言。

## 八、开发协作体系

12 个原生 Skill + 五步协作流程 + 沉淀闭环。Skill 按五步流程归位：

| 阶段 | Skill |
|---|---|
| 规划 | writing-plans / plan-review |
| 并行调度 | dispatching-parallel-agents（适配 Trae Task 工具的并行调度纪律） |
| 执行 | tdd / systematic-debugging / receiving-code-review |
| 验证 | verification-before-completion / dev-selfcheck |
| 合并 | git-merge-guardian |
| 讲书内容 | deep-reading / chapter-title-soul / content-review |

**五步已固化为默认行为**（[.trae/rules/dev-workflow.md](.trae/rules/dev-workflow.md)）：重述需求 → 计划等确认 → 执行（开始前必读 loop_log）→ 自检（对照 checklist）→ 沉淀（loop_log 复盘）。**用户无需再粘贴提示词**。

**Skill 能力边界如实声明**：Skill 不能调度 sub-agents、不能直接调 MCP；真并行有 C/A/B 三路径——C 路径用会话内 Task 工具启动多 subagent（主路径，无需 LLM_API_KEY），A 路径单 Agent 串行切视角，B 路径调 Python 引擎（如 [scripts/review_plan.py](scripts/review_plan.py) 调 LangGraph，需 .env 配置）。能力做不到时如实说明并给替代方案，不假装。

配套：[.trae/rules/](.trae/rules/) 自动加载（dev-workflow + bug-reporting）；[.trae/checklists/](.trae/checklists/) 配合 dev-selfcheck 触发；[bug-reporting.md](.trae/rules/bug-reporting.md) 规范 bug 描述性标题、字段模板、四类必记录情形、与 [bug_regression_list.md](tests/bug_regression_list.md) 联动。

## 九、测试与回归体系

四层防护网，**合并 master 前必须全部清零**（包括非本次引入的问题）：

1. **pytest 单测**：24+ 个测试文件，覆盖 archetype 路由、书籍结构、内容质检、分支治理、loop_log 校验等契约。
2. **回归测试集** [tests/run_regression_suite.sh](tests/run_regression_suite.sh)：11+ 步，明确「代码回归阻塞合并 / 数据质量告警不阻塞」分层。
3. **bug 历史库** [tests/bug_regression_list.md](tests/bug_regression_list.md)：BUG-001~031 共 31 条，根因 → 复现 → 回归测试三段式可追溯。
4. **--strict 门禁** [scripts/check_book_structure.py](scripts/check_book_structure.py)：P0/P1/P2 任一失败都阻断；CI 三道串联（`check_book_structure --strict` → `run_regression_suite.sh` → `pytest -q`）。

合并纪律：**禁止以「问题非本次引入」为由跳过修复**。修复后判断是否为会复发的代码/数据 bug，需要补充回归测试并更新 bug_regression_list.md。

## 十、目录结构与命名规范

```
.
├── README.md / RULES.md           # 项目规划 / rules.md 同步副本（sync_rules.py）
├── .trae/
│   ├── skills/                    # 12 个原生 Skill（见 §八）
│   ├── rules/                     # 自动加载规则（dev-workflow / bug-reporting）
│   └── checklists/                # dev / content / book-structure 三类 checklist
├── docs/
│   ├── loop_log.md                # LoopAgent 循环日志（索引化，见 §十二）
│   ├── archetype-design/design.md # archetype 范式分桶设计
│   ├── feedback-loop/design.md    # 反馈循环规划（与 archetype-design 对照，见 §十六）
│   ├── superpowers/specs/         # 原始 5 轨道总体规划
│   ├── reviews/                   # 灵魂注入 spec / AB 盲测 / 评审记录
│   ├── comments-system/           # 评论系统规划
│   └── archive/loop_log_fossils.md # 历史测评框架与评分表（不再更新）
├── output/                        # 16 本专栏、数百篇 Markdown 笔记
│   └── {书名}/{章节}_{事件}.md     # 仅两级路径，下划线分隔章节与事件
├── prompts/                       # narrative/modern/knowledge 三套并行提示词
├── scripts/                       # build_site / check_* / review_* / migrate_*
├── src/
│   ├── agents/                    # 13 个 Agent（orchestrator + 5 specialist + editor + tone_setter + chief_editor + 2 content_reviewer + plan_reviewer）
│   ├── core/                      # workflow.py 编排 + content_review_workflow.py
│   ├── utils/                     # quality.py / content_quality.py / sorting.py / markdown.py
│   ├── tools/                     # obsidian_writer / pdf / web 搜索
│   └── web/static-site/           # 静态站点源码（由 build_site.py 同步到 site/）
├── site/                          # 部署产物（部分入库，data/notes/.nojekyll 由 CI 生成）
├── tests/                         # pytest + 回归集 + bug_regression_list
├── .github/workflows/             # pages / deploy-modelscope / regression / branch-cleanup
└── config.yaml / .env.example / requirements.txt
```

**双字段排序**：`chapter_sort`（跨章/阶段历史顺序）+ `sort`（章内事件时间顺序）。`STAGE_MODE_BOOKS = {资治通鉴, 明纪}` 走阶段模式（chapter_sort = 朝代阶段号）。

**`_meta.yaml`**：`title / category / author / description / cover / sort`，可选 `archetype`。category 取值枚举：史/经/技/职场/养生/财。

**Obsidian 集成链路**：vault 路径解析顺序 `参数 > OBSIDIAN_VAULT_PATH > config.yaml: vault_dir`；优先 MCP `mcp_mcp-obsidian`，fallback 文件系统。

**禁止项**（已被 `check_book_structure.py --strict` P1 阻断）：
- 路径多级嵌套（仅 `<book>/<chapter>_<event>.md` 两级）
- 章节名/文件名含「模块N」前缀（BUG-019）
- 章内 sort 重复/非递增
- frontmatter 与路径不一致

## 十一、部署与发布

**双部署源同源同构**：master push 同时触发 GitHub Pages（[pages.yml](.github/workflows/pages.yml)）与魔搭 ModelScope Studio（[deploy-modelscope.yml](.github/workflows/deploy-modelscope.yml)）。构建脚本唯一入口 [scripts/build_site.py](scripts/build_site.py)，两源产物完全一致。

**构建产物边界**：
- 入库（源）：`site/index.html` / `site/css/` / `site/js/` / `site/sw.js` / `site/versions/`
- CI 生成（产物，已 ignore）：`site/data/` / `site/notes/` / `site/.nojekyll`

**SW 缓存版本治理**：`sw.js` 中 `CACHE_NAME`（当前 `halo-read-v3`）核心资源 cacheFirst、数据 staleWhileRevalidate。**前端关键修复后必须手动 bump `CACHE_NAME`**，否则手机端会出现"幽灵旧版"（BUG-018 教训）。这是项目最易踩的发布坑。

**CI 门禁链条**：PR 必过 [regression.yml](.github/workflows/regression.yml) 三道（check_book_structure --strict → 回归集 → pytest）；master push 触发双部署；分支治理 dry-run 需 Environment 审批。

## 十二、LoopAgent 循环日志体系

把开发沉淀从被动记录升级为**可校验、可触发的开发闭环**。详见 [docs/loop_log.md](docs/loop_log.md)。

- **索引化结构**：顶部三件套——最近 10 条沉淀（按日期倒序锚点）+ 主题锚点（6 个 slug）+ 教训计数表（≥3 次且未入 checklist 即触发方案 C）。化石区已迁出至 [docs/archive/loop_log_fossils.md](docs/archive/loop_log_fossils.md)。
- **可校验**：[scripts/check_loop_log.py](scripts/check_loop_log.py) 把"被动记录"变成门禁——P1 核心阻断（日期倒序 + #lesson slug 受控清单），P3 提示（索引锚点 / slug 计数告警 / 化石标题未迁出），`--strict` 模式 P3 也阻断。配套 7 个单元测试。
- **写入门槛**（dev-workflow 第五步）：写了不亏（共性反复问题 / 可复用资产 / 触发规则更新）；别往 loop_log 写（内容日志→output、单点 bug→bug_regression_list、部署配置→commit）。
- **方案 C 手册**：5 步流程——新增 checklist 项 → Skill 引用 → 记录标 `已入checklist: yes` → 计数表改 yes → 跑回归套件。
- **#lesson slug 受控清单**：`git_hygiene` / `reader_interaction` / `content_quality` / `book_structure` / `deployment` / `soul_injection` / `ai_course`，新增需在文件末主题表登记。

## 十三、快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env   # 编辑 .env，填入大模型 API Key

# 3. 生成一篇笔记（按 archetype 自动路由，narrative 可省略 --archetype）
python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法
python src/main.py --book 职场沟通课 --chapter 向上汇报 --event 周报 --archetype modern

# 4. 启动 HTML 管理界面
python src/web/app.py

# 5. 构建静态站点（GitHub Pages / 魔搭部署前置）
python scripts/build_site.py
python -m http.server 8080 -d site
```

`--stub` 可无需 API Key 生成占位笔记。生成或提交笔记前建议运行 `python scripts/check_duplicates.py` 避免重复文件。

## 十四、相关项目与 Skill 参考

### 可借鉴的 AI 阅读/研究项目

| 项目 | 核心借鉴点 |
|---|---|
| **识典古籍 / 中华古籍智慧化服务平台** | 把专业古籍整理工具与大众阅读场景打通，垂直领域模型降低古文门槛。 |
| **AI 太炎** | 古汉语领域专用小模型在字词释义、句读、用典分析上远超通用模型。 |
| **Aeneas（DeepMind）** | 对残本/缺字古籍，可采用多模态 + 相似文本检索的修复与考证工作流。 |
| **Google NotebookLM** | 以"源材料为唯一信源"，输出带原文引用的多格式学习材料。 |
| **Rebind AI** | 将专家知识封装为可交互的 Agent 人格，降低用户提问门槛。 |
| **Atlas** | 用 Knowledge Map 呈现论点-证据关系，强调可审计的引证链路。 |
| **Elicit** | 把非结构化文献转化为结构化表格与矩阵，便于横向对比和综述。 |
| **Perplexity / Perplexity Pages** | 检索-生成-引用链路，适合需要实时资料的研究场景。 |
| **Obsidian + AI 插件生态** | 本地优先、数据自主、与现有知识库无缝集成。 |
| **Zotero + AI 插件生态** | 文献管理器是研究者最高频入口，AI 能力嵌入 PDF 阅读场景。 |

### 可能适用的 Skills / Tools

- **WebSearch / WebFetch**：获取可信史料和名家点评。
- **mcp_pdf-reader-mcp**：读取用户本地 PDF 史料。
- **mcp_mcp-obsidian**：与 Obsidian Vault 交互。
- **mcp_context7**：查询古籍/学术资料（若后续接入知识库）。
- **TRAE-code-review / TRAE-security-review**：代码审查与安全扫描。

### 多 Agent 框架选型参考

| 框架 | 适用场景 | 本项目评估 |
|---|---|---|
| **LangGraph** | 复杂生产级工作流、状态管理、可观测性 | **首选**。适合长文本 + 多 Agent 并行 + 质量校验。 |
| **CrewAI** | 角色清晰、快速原型 | 次选。代码量少，但复杂流程控制弱。 |
| **AutoGen / Microsoft Agent Framework** | 对话式、探索式生成 | 微软已合并为 Microsoft Agent Framework，适合研究/对话场景。 |
| **MetaGPT** | 软件工程 SOP | 不适用。 |

## 十五、核心原则

- **简洁**：不堆技术，能用提示词和简单流程解决就不用复杂架构。
- **可信**：每个观点要有来源，每个名家点评要有出处。
- **深刻**：不止于故事，要挖掘本质。
- **人本**：AI 是阅读伴侣，不是百科检索器；目标是开智悟道，不是信息搬运。
- **沉淀**：每一次开发都产出可校验的教训，让协作本身也变成可迭代的 Loop。

## 十六、反馈循环规划（写作资产保留与正循环迭代）

详细规划见 [`docs/feedback-loop/design.md`](./docs/feedback-loop/design.md)。本节为索引与核心摘要。

### 缘起

archetype 架构升级（见 [`docs/archetype-design/design.md`](./docs/archetype-design/design.md)）完成后，生成侧已按 narrative/modern/knowledge 三桶正交分层；但反馈回收侧完全空白——数据流单向（输入→生成→质检→保存），没有"发布→反馈→回流→优化"回路。本规划负责把回路补齐，让框架产出从"每次从零开始"升级为"基于历史和反馈持续优化"。

### 四类可复用资产 + 反馈数据

1. **历史提示词**（[prompts/](./prompts/) 三桶共 28 文件）
2. **引用文献**（当前完全 inline 在 output 里）
3. **智能体质量评分**（[content_quality.py](./src/utils/content_quality.py) 已有 0-100 分四维度引擎，但生成管线没接线）
4. **发布后真实读者反馈**（点赞/阅读量/收益/反馈）

### 现状一句话

四类资产成熟度差异巨大，**不能一锅烩**：

- 质量评分：引擎已就绪，只差接线（[workflow.py quality_node](./src/core/workflow.py) 调的是 legacy 无 score 接口）
- 历史提示词：半结构化，无版本机制
- 引用文献：完全 inline，无结构化字段
- 发布后反馈：完全空白，无任何基础设施

### 三档优先级

| 档位 | 内容 | 前置依赖 | 风险 |
|---|---|---|---|
| **第一档**（立即做） | 质量评分接入生成管线 + 落盘 + score_history | 无 | 换接口可能影响结构校验门控 |
| **第二档**（看精力） | 提示词版本化 + 文献结构化 | 第一档 score_history | 历史 output 迁移工作量大 |
| **第三档**（最关键但风险最大） | 发布后反馈接入 | 第一档 + 用户先定平台 | API 烟囱、指标不可比、必须绑定 archetype |

### 核心约束

- 第三档反馈 schema 设计时，**必须把 `archetype` 作为必填维度**——这是 archetype 升级红利兑现的唯一路径
- **不要把 [comments-system/](./docs/comments-system/) 评论系统误当成反馈循环基础设施**——它回收的是"作者批注"反馈，不是"读者效果"反馈
- 规则与实现不一致（[content-quality.md](./.trae/skills/deep-reading/content-quality.md) 五维度 vs [content_quality.py](./src/utils/content_quality.py) 四维度）必须先修，否则评分历史会被"灵魂分漂移"污染

### 一句话结论

**先做第一档（评分接入管线 + 落盘 + score_history），这是唯一不需要外部数据就能跑起来的反馈循环种子。**

完整背景、现状实测、目标收益、三个必避陷阱、实施路径详见 [`docs/feedback-loop/design.md`](./docs/feedback-loop/design.md)。
