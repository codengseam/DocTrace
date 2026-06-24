# 项目规划：个人 AI 深度阅读助手

## 一、项目定位

个人深度阅读研究助手。用户读完一段古籍（如《资治通鉴》）后，输入书名和章节，AI Agent 自主选择可信资料，生成 Markdown 讲书笔记，最终进入 Obsidian 知识库。

- 不做 RAG，不向量化，不存储整书内容。
- 输出格式固定为 Markdown。
- 目标：好看、有料、通透、有洞察。

## 二、项目背景

用户日常阅读古籍，每读完一个章节或事件，希望 AI 能自动完成：

- 收集可信资料，补充相关史料和不同视角；
- 用白话讲书的方式还原故事、分析人物、讲清背景；
- 引用真正有明确点评的名家之言；
- 从事件中提炼本质规律，达到"开智悟道"的效果；
- 输出 Markdown 文档，按书籍/章节分类存入 Obsidian；
- 提供一个 HTML 页面，用于管理、分类和阅读这些笔记。

核心是一个简洁的 Agent 专家团工作流：用户输入 → Orchestrator 分配任务 → 多个 Specialist Agent 并行生成 → 汇总为 Markdown → HTML 管理界面展示。

## 三、项目目标

1. **降低深度阅读门槛**：把古籍事件变成好看、有料、通透的讲书笔记。
2. **构建个人知识库**：所有输出为 Markdown，直接进入 Obsidian，可链接、可检索、可沉淀。
3. **辅助开智悟道**：不止于讲故事，更要通过现象看本质，提炼人性、权力、组织的底层规律。
4. **可控可信**：不依赖无目的联网搜索，Agent 自主选择可信资料；引用必须具体到原文和书名。

## 四、Agent 专家团设计

```
用户输入：读了《资治通鉴·周纪二》商鞅变法
    │
    ▼
Orchestrator Agent（调度专家）
  - 解析用户输入：书名、章节、事件
  - 确认输出路径和文件名
  - 分配任务给其他 Specialist Agents
    │
    ▼
Specialist Agents 并行工作：
  - 史料专家：搜集事件相关正史记载，还原关键情节
  - 人物专家：挖掘主角团的人性画像，用外部史料佐证
  - 背景专家：梳理前因后果、制度环境、历史机会
  - 名家专家：筛选真正有明确点评的名家之言
  - 悟道专家：提炼本质规律，寻找跨文化映照
    │
    ▼
编辑专家：汇总、润色、统一风格、检查引用
    │
    ▼
输出 Markdown → 按书籍/章节分类保存 → 更新 HTML 管理界面
```

## 五、核心工作流程

1. 用户输入书名、章节、事件（可选个人感悟）。
2. Orchestrator 确认事件范围，规划各 Specialist Agent 任务。
3. Specialist Agents 并行工作，各自按 `.trae/rules/rules.md` 中对应模块要求产出内容。
4. 编辑专家汇总五段内容，统一语气，补齐引用，生成结语。
5. 保存到 `output/{书名}/{章节}_{事件}.md`。
6. **自动触发内容质检**：调用 `scripts/review_content.py`，按 `.trae/rules/content-quality.md` 四维度（真实性/可读性/顺序/引用克制）评分，≥85 分合格。
7. HTML 管理界面读取目录结构，按书分类、章节排序展示。

## 六、输出规范

详见 [`.trae/rules/rules.md`](./.trae/rules/rules.md)。根目录 [`RULES.md`](./RULES.md) 是从库副本，用于兼容其他 IDE/工具。

> 修改规则时只编辑 `.trae/rules/rules.md`，然后运行 `python scripts/sync_rules.py` 同步到根目录 `RULES.md`。

固定结构：

1. 讲事情
2. 讲人物
3. 讲背景
4. 讲道理
5. 问道悟道
6. 结语（超级总结）

## 七、文件结构

```
.
├── README.md              # 项目规划与背景
├── .trae/
│   ├── skills/
│   │   ├── deep-reading/   # Trae Skill 交互入口（生成讲书笔记）
│   │   └── content-review/ # Trae Skill 交互入口（内容质检）
│   ├── rules/
│   │   ├── rules.md        # 内容生成规则
│   │   └── content-quality.md  # 内容质检规则
│   └── checklists/
│       └── content-checklist.md  # 内容质检 checklist
├── .env.example           # 环境变量示例（API Key 等）
├── output/                # 生成的讲书笔记，按书分类、章节排序
│   ├── 资治通鉴/
│   │   ├── 周纪一_三家分晋.md
│   │   ├── 周纪二_商鞅变法.md
│   │   └── ...
│   └── 史记/
│       └── ...
├── src/                   # 源代码
│   ├── agents/            # 专家团 Agent 定义
│   │   ├── orchestrator.py
│   │   ├── historian.py           # 史料专家
│   │   ├── biographer.py          # 人物专家
│   │   ├── context_analyst.py     # 背景专家
│   │   ├── critic.py              # 名家专家
│   │   ├── philosopher.py         # 悟道专家
│   │   ├── editor.py              # 编辑专家
│   │   ├── content_reviewer.py    # 内容质检 Agent（汇总）
│   │   ├── content_reviewer_sub.py # 内容质检 Agent（三视角子节点）
│   │   └── plan_reviewer.py       # 计划评审 Agent
│   ├── core/              # 工作流编排
│   ├── storage/           # 文件与元数据存储
│   ├── tools/             # MCP / PDF / Obsidian / Web 搜索工具
│   ├── utils/             # 公共工具
│   │   ├── quality.py         # AI 套路句/现代术语/升华配额检测
│   │   ├── content_quality.py # 内容质检四维度检测（真实/可读/顺序/引用）
│   │   └── ...
│   └── web/               # Flask Web 管理界面（静态资源、模板、API）
│       └── static-site/   # GitHub Pages 静态站点源码（由 build_site.py 同步到 site/）
├── prompts/               # Agent 提示词文件
│   ├── content_reviewer.md      # 内容质检汇总提示词
│   ├── content_reviewer_sub.md  # 内容质检三视角提示词
│   └── ...                      # 其他讲书 Agent 提示词
├── scripts/               # 辅助脚本
│   ├── build_site.py
│   ├── review_plan.py
│   ├── review_content.py  # 内容质检并行引擎入口
│   └── ...
├── site/                  # 静态站点产物（由 scripts/build_site.py 生成）
├── tests/                 # 测试用例
├── .github/               # GitHub Actions 配置（Pages 自动部署）
├── config.yaml            # 项目配置
└── requirements.txt       # Python 依赖
```

## 八、命名规范

- 文件夹：`output/{书名}/`
- 文件名：`{章节}_{事件}.md`，纯中文
- 示例：`output/资治通鉴/周纪二_商鞅变法.md`

## 九、技术栈

- **后端**：Python
- **前端**：HTML + CSS + JavaScript（本地管理界面）
- **存储**：Markdown 文件 + Obsidian Vault
- **AI 调用**：大模型 API（如 Alibaba DashScope Qwen）
- **不做**：RAG、向量数据库、整书存储

## 十、相关项目与 Skill 参考

### 可借鉴的 AI 阅读/研究项目

| 项目 | 核心借鉴点 |
|---|---|---|
| **识典古籍 / 中华古籍智慧化服务平台** | 把专业古籍整理工具与大众阅读场景打通，垂直领域模型降低古文门槛。 |
| **AI 太炎** | 古汉语领域专用小模型在字词释义、句读、用典分析上远超通用模型。 |
| **Aeneas（DeepMind）** | 对残本/缺字古籍，可采用多模态 + 相似文本检索的修复与考证工作流。 |
| **Google NotebookLM** | 以"源材料为唯一信源"，输出带原文引用的多格式学习材料（FAQ、时间线、播客）。 |
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

## 十一、Skill 设计方案（已决策）

### 关键发现

根据对 Trae Skill 机制的调研：

- **Skill 本身不能创建或调度 sub-agents**，也不能直接调用 MCP tools。
- Skill 是一份结构化的高级 Prompt，被 Agent 加载后影响 Agent 行为。
- 在 Trae 中，只有 **SOLO Agent** 可以调用自定义智能体（sub-agents）。
- 因此，"写一个大的 Skill 来调用 Agent 和 Skills"在 Trae 当前机制下**不可行**。

### 推荐方案：混合架构

```
┌─────────────────────────────────────────┐
│  用户输入（Trae 对话框 / HTML 界面）      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Trae Skill（深度阅读助手）              │
│  - 识别用户意图                          │
│  - 加载 `.trae/rules/rules.md` 规范      │
│  - 触发 Python 编排引擎或 SOLO Agent     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Python 编排引擎（LangGraph）            │
│  - Orchestrator 调度                     │
│  - Specialist Agents 并行执行            │
│  - 结果汇总与质量校验                    │
│  - 生成 Markdown 并保存                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Obsidian Vault + HTML 管理界面          │
└─────────────────────────────────────────┘
```

### 各层职责

| 层级 | 职责 | 形式 |
|---|---|---|
| **Trae Skill** | 人机交互入口、识别意图、加载规范、触发执行 | `.trae/skills/deep-reading/SKILL.md` |
| **Python 编排引擎** | 确定性流程控制、Agent 编排、文件保存、质量校验 | `src/core/` + `src/agents/` |
| **SOLO Agent + 子 Agent** | 复杂任务时，由 SOLO Agent 调用自定义 Specialist Agent | Trae 内置 |
| **MCP Tools** | 读取 PDF、读写 Obsidian、网页搜索等 | 按需接入 |

### 为什么不直接用大 Skill？

- Skill 不能执行代码、不能保存文件、不能维护状态。
- 古籍讲书需要严格的多阶段流程和质量校验，不适合用纯 Prompt 描述。
- Python + LangGraph 能提供 checkpoint、并发、错误恢复、可观测性。

### 实施路径

1. **第一阶段**：用 Python + LangGraph 实现最小可用原型（Orchestrator + 5 个 Specialist + Editor）。
2. **第二阶段**：接入 MCP tools（PDF 读取、Obsidian 写入）。
3. **第三阶段**：封装 Trae Skill 作为交互入口，Skill 中说明何时调用 Python 引擎。
4. **第四阶段**：构建 HTML 管理界面，与 Python 引擎联动。

## 十二、后续开发方向

1. **Agent 工作流工程化**
   - 实现 Orchestrator + Specialist Agents 的调用逻辑；
   - 每个 Agent 对应 `.trae/rules/rules.md` 中的一个模块；
   - 支持用户输入 → 自动生成 → 保存 Markdown 的完整流程。
2. **HTML 管理界面**
   - 按书籍/卷/章分类浏览笔记；
   - 显示生成历史、阅读进度；
   - 提供"生成新笔记"入口；
   - 支持引用原文的快速查看。
3. **资料来源白名单**
   - 配置可信搜索域，限制 Agent 的搜索范围；
   - 记录每次查询用过的资料，避免重复搜索。
4. **Obsidian 集成**
   - 自动生成标签、双向链接、MOC 索引；
   - 支持主笔记 + 引文汇编文档的拆分。
5. **质量校验**
   - 生成后自动检查：结构完整性、引用真实性、中英文混杂、AI 味句式等；
   - 必要时触发二次修订 Agent。

## 十三、快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入大模型 API Key

# 3. 生成一篇笔记
python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法

# 使用 --stub 无需 API Key 生成占位笔记
python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法 --stub

# 4. 启动 HTML 管理界面
python src/web/app.py
```

## 十四、静态站点部署

### 本地预览

```bash
# 1. 生成笔记（需要配置 API Key 或使用 --stub）
python src/main.py --book 资治通鉴 --chapter 周纪二 --event 商鞅变法

# 2. 构建静态站点
python scripts/build_site.py

# 构建时会自动将 src/web/static-site/ 下的 index.html/css/js/sw.js
# 同步到 site/，保证 GitHub Pages 产物与前端源码一致。

# 3. 本地预览
python -m http.server 8080 -d site
```

### GitHub Pages 部署

项目已配置 GitHub Actions（`.github/workflows/pages.yml`），push 到 master 分支后自动构建并部署。

1. 在仓库 Settings → Pages → Source 选择 "GitHub Actions"
2. push 代码到 master 分支
3. Actions 自动运行：安装依赖 → 构建站点 → 部署到 GitHub Pages

注意：`output/` 目录默认会提交到仓库以保存生成的笔记。CI 构建静态站点时会直接读取仓库中的 `output/`。如需在 CI 中重新生成笔记，请通过 `workflow_dispatch` 手动触发并配置 Secrets。

生成或提交笔记前，建议运行重复检查脚本，避免 `output/` 下出现重复 Markdown 文件：

```bash
python scripts/check_duplicates.py
```

### 合并前强制检查

本项目要求：合并或 push 到 `master` 前，必须清零所有校验问题（包括 P2 级别），无论问题是否由本次改动引入。

```bash
# 1. 严格模式校验 output/ 目录结构（P0/P1/P2 任一失败都会退出码 1）
python scripts/check_book_structure.py --output output --strict

# 2. 运行 pytest
pytest -q

# 3. 运行回归测试集
bash tests/run_regression_suite.sh
```

若发现 AI 引入的数据/代码问题，修复后必须补充回归测试或更新 [tests/bug_regression_list.md](tests/bug_regression_list.md)。目标不是把每次生成的内容合入就好，而是共同维护一个稳定运行的项目。

### 回归测试集

代码改动或冲突合并后，运行回归测试集防止历史 bug 复现（沉浸模式横屏、合并冲突残留、章节排序错乱、重复文件、书籍结构问题等）：

```bash
bash tests/run_regression_suite.sh
```

历史 bug 列表与复现方式见 [tests/bug_regression_list.md](tests/bug_regression_list.md)。阅读器功能 e2e 需先安装依赖：`npm install jsdom marked`。

最近一次阅读器修复已通过全量验收：沉浸按钮长标题不被挤竖排、沉浸模式可中央唤出 UI 并打开目录/退出、自动阅读与壁纸切换正常、`site/` 与 `src/web/static-site/` 产物同步。

## 十五、核心原则

- **简洁**：不堆技术，能用提示词和简单流程解决就不用复杂架构。
- **可信**：每个观点要有来源，每个名家点评要有出处。
- **深刻**：不止于故事，要挖掘本质。
- **人本**：AI 是阅读伴侣，