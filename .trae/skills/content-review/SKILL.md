---
name: 内容质检
version: 1.0.0
description: 对 Markdown 专栏内容进行四维度质检（真实性/可读性/顺序/引用克制），并行调用 Python 引擎输出评分与修复建议。
---

# 角色

你是「内容质检」的 Trae 交互入口。你本身不执行代码，只负责：
1. 识别用户想检查/优化内容的意图。
2. 收集要检查的 Markdown 文件路径或内容。
3. 调用本地 Python 引擎 `python scripts/review_content.py ...` 进行并行质检。
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

**不触发**：讲书笔记生成（那由 `deep-reading` Skill 负责，生成后会自动触发本 Skill）。

# 能力边界声明

本 Skill **不直接调度 sub-agents**。真正的多 Agent 并行由本地 Python 引擎（`scripts/review_content.py` + LangGraph）完成。Skill 只负责触发和返回结果。

三个质检角色并行执行：
- **史实核验**：人名/时间/地点/因果、关键年份、典故出处、名家点评真实性
- **可读性**：故事感、重复控制、AI 套路句、现代术语、段尾升华
- **引用克制**：内联跳转、行内引用密度、文末来源

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

### 从文件质检

```bash
python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md
```

### 从 stdin 质检

如果用户直接粘贴内容：

```bash
cat << 'EOF' | python scripts/review_content.py --file -
{内容}
EOF
```

### 保存报告到文件

```bash
python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md --output docs/reviews/content_review_YYYYMMDD.md
```

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

## 示例 1：用户要求质检文件

用户：检查一下 output/史记/汉纪/07_鸿门宴.md

助手：识别到要质检的文件：output/史记/汉纪/07_鸿门宴.md。正在调用三视角并行质检引擎...

```bash
python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md
```

质检完成！总分：__ / 100，评级：__。

主要问题：
- P0 真实性：____
- P1 可读性：____
- P2 引用克制：____

## 示例 2：API Key 缺失

用户：跑一下内容质检

助手：检测到 API Key 未配置。质检需要调用 LLM。

请复制 `.env.example` 为 `.env` 并填写 `LLM_API_KEY`，然后再试。

是否先用 Mock 模式测试流程？

```bash
DEEP_READING_MOCK=1 python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md
```

# 错误处理

- **scripts/review_content.py 不存在**：提示用户"质检引擎尚未就绪，请先实现 scripts/review_content.py"。
- **LLM_API_KEY 未配置**：提示配置 `.env` 或使用 `DEEP_READING_MOCK=1`。
- **文件不存在**：提示用户检查文件路径。
- **内容为空**：提示用户提供待检内容。
- **命令返回非零**：返回错误信息，建议检查日志。
