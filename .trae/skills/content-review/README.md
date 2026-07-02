# 内容质检 Skill

对 Markdown 专栏内容进行**六维度质检**，融合确定性规则与 LLM 三视角并行评审，输出评分与修复建议。

## 目录结构

```
.trae/skills/content-review/
├── SKILL.md              # Skill 入口：触发条件、工作流、能力边界
├── README.md             # 本文件：概览、用法、参考来源
├── rules/
│   └── consistency-rules.md   # 一致性检测规则（新增维度）
├── scripts/
│   └── check_consistency.py   # 一致性检测 CLI（纯规则，无需 LLM）
├── agents.md             # 多 Agent 质检架构说明
└── checklist.md           # 六维度质检清单（含一致性维度）
```

## 六维度评分体系（v1.2.2）

| 维度 | 分值 | 检测方式 | 检测脚本/Agent |
|---|---|---|---|
| 真实性 | 33 | LLM 三视角 | 史实核验 specialist |
| 可读性 | 23 | LLM 三视角 | 可读性 specialist |
| 顺序 | 13 | 规则 + LLM | `check_book_structure.py` + LLM |
| 引用克制 | 8 | 规则 + LLM | `check_char_count.py` + LLM |
| 灵魂 | 13 | 规则 + LLM | `_check_soul_dimension` + LLM |
| **一致性**（新增） | **10** | **纯规则** | `check_consistency.py` |
| **合计** | **100** | — | — |

通过门槛：单篇总分 ≥ 85，一致性维度 ≥ 7/10。

## 检测流水线

```
1. 字数核对（check_char_count.py）         ── 确定性 P0 前置
   ↓
2. 一致性检测（check_consistency.py）       ── 确定性 4 类矛盾
   ↓
3. 规则化质检（content_quality.py 五维度）   ── 确定性 + 模式匹配
   ↓
4. LLM 三视角并行（content_review_workflow）── 语义级深审
   ↓
5. 汇总报告
```

**确定性优先**：步骤 1-3 无需 LLM，结果可复现；步骤 4 调 LLM 做语义级深审。
即使 API Key 未配，前 3 步也能跑完拿到硬错误清单。

## 一致性检测四类矛盾（新增）

详见 [rules/consistency-rules.md](rules/consistency-rules.md)。

| 类型 | 优先级 | 检测内容 | 典型示例 |
|---|---|---|---|
| 数值交叉矛盾 | P0 | 年龄-年份/在位时长/损失-剩余的数学矛盾 | "生于前155年"+"前140年继位"+"25岁继位"（应 15 岁） |
| 同事件异值 | P0/P1 | 同引文异字数/同战役异兵力/同典故异出处 | 前文"「唇亡齿寒」出自《左传》"，后文"出自《谷梁传》" |
| 实体别名冲突 | P0/P1 | 字号/谥号/籍贯冲突 | 前文"曹操字孟德"，后文"曹操字子建" |
| 时间线倒置 | P2 | 年份逆序且无倒叙标注 | 赤壁之战（208）写在隆中对（207）之前，无"此前" |

## 用法

### 单文件质检

```bash
# 完整六维度（含 LLM 三视角）
python scripts/review_content.py --file output/史记/汉纪/07_鸿门宴.md

# 仅一致性检测（纯规则，无需 LLM）
python scripts/check_consistency.py --file output/史记/汉纪/07_鸿门宴.md

# 仅字数核对
python scripts/check_char_count.py --file output/史记/汉纪/07_鸿门宴.md
```

### 批量扫描

```bash
# 全 output 目录一致性检测，--strict 命中 P0/P1 即退出码 1
python scripts/check_consistency.py --dir output/ --strict

# 全 output 目录字数核对
python scripts/check_char_count.py --dir output/ --strict
```

### 从 stdin

```bash
cat << 'EOF' | python scripts/check_consistency.py --file -
曹操生于前155年，前140年继位时25岁，明显与生年矛盾。
EOF
```

## 设计原则

1. **确定性优先**：能用规则解决的不交 LLM，结果可复现、可批量。
2. **误报优于漏报**：宁可标记需人工复核，也不静默放过矛盾。
3. **单一信源**：YAML frontmatter 解析、字数剥离逻辑统一从 `quality.py` 复用。
4. **能力边界清晰**：Skill 文件本身不调度 sub-agents，真并行由 Python 引擎 + Task 工具完成。
5. **规则可演进**：`rules/` 下每条规则独立成文件，新增维度只加文件不动主库。

## 参考来源（方法论支撑，非文字引用）

权威理论与方法论：
- **Chain-of-Verification (CoV)**：Jason Weston 等，"生成后自检"思想 → 离线 claim 提取 + 交叉验证
- **Self-Consistency**：Wang et al. 2022 → 同一事实多次出现应一致
- **Chain-of-Thought (CoT)**：Wei et al. Google 2022 → 三视角 Prompt "先列核验步骤再下结论"结构（v1.2.2 落地）
- **ReAct**：Yao et al. 2022 → "质检→修复→再质检"反馈循环（离线变体，v1.2.2 在 agents.md §五 显式标注）
- **Grounding/Citations**：溯源校验 → 典故出处一致性检测
- **Vectara HHEM-2.1**：幻觉量化框架 → 一致性维度量化扣分
- **TruthfulQA / HELM**：模型评估基准，六维度评分体系理论参考（非直接调用）

权威著作（理论支撑）：
- 王国平《AI 提示工程必知必会》（清华，2024）
- 周明《大语言模型可靠性评测与幻觉治理》（电子工业，2026）
- 苏海波、刘译璟《数据科学技术：文本分析和知识图谱》（清华，2025）
- 黄飞等《A Survey on Hallucination in Large Language Models》（arXiv:2311.05232）

行业报告：
- 网易号《从源头到闭环：AI 生成长文本如何避免错误与前后矛盾》——"全文唯一真源机制"
- 科大讯飞星火研究院《中文 AI 生成内容矛盾检测白皮书 2026》
- 中国信通院《可信 AI 大模型评测体系白皮书》（2024-2025）

详见 [rules/consistency-rules.md §六](rules/consistency-rules.md)。
