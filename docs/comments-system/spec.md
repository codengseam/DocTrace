# 静态网站原文批注式评论系统 · 产品规格说明书

> 版本：v1.0 · 日期：2026-06-22
> 适用项目：深度阅读助手静态站点（`site/`，vanilla JS + marked.js，部署于 GitHub Pages）
> 关联代码：`site/index.html`、`site/js/app.js`、`site/css/style.css`、`scripts/build_site.py`、`src/agents/`

---

## 一、产品定位与目标

### 1.1 一句话定位

为「深度阅读助手」静态站点增加**飞书云文档式的原文圈选批注能力**，让作者本人（及少量受邀读者）能针对《资治通鉴》等古籍讲书笔记的任意一段原文，进行错误指正、夸奖、讨论、补充、感想等多类批注，并把批注数据沉淀为可被项目 Python AI 专家团消费的结构化资产，最终辅助人决定是否修订原文。

### 1.2 核心目标

| 编号 | 目标 | 衡量标准 |
|---|---|---|
| G1 | 圈选即评 | 在阅读区用鼠标/触摸选中文本后，1 秒内弹出批注浮层，可写评论并选类型 |
| G2 | 锚定稳定 | 原文小幅修订（个别字词、标点）后，已存在的批注高亮仍能尽量自动重定位，不轻易变成孤儿 |
| G3 | 数据可导出 | 一键导出当前笔记（或全站）的批注为 JSON，格式可直接被 `src/agents/` 专家团读取 |
| G4 | 专家团可触发 | 在站点上手动点「启用专家团评判」，生成一份供本地 Python pipeline 执行的指令包（不自动改原文） |
| G5 | 纯静态零后端 | 全部功能在浏览器内完成，存储用 localStorage，导入导出用 JSON 文件，不引入任何服务端 |
| G6 | 风格协调 | 视觉与现有暖纸色古籍阅读风格（`--bg-paper` `#faf8f5`、宋体、`--accent` `#8b5a2b`）一致 |

### 1.3 非目标（明确不做）

- 不做多人实时协同（本系统主要服务作者本人，单机单用户为主）
- 不做服务端账号体系
- 不做评论自动改写原文（最终修订权在人）
- 不做评论的全文搜索引擎（评论量级小，列表筛选即可）
- 不引入前端框架（React/Vue 等），保持 vanilla JS

---

## 二、用户角色

| 角色 | 描述 | 本系统中的典型行为 |
|---|---|---|
| **作者（主要）** | 笔记的撰写者，即项目所有者 | 圈选原文写批注、补充资料、记录感想；定期导出批注；触发专家团评判；决定是否采纳建议修订原文 |
| **读者（次要）** | 访问 GitHub Pages 站点的任意访客 | 默认只读浏览批注；如需写批注，需作者手动开启「允许访客批注」开关（默认关闭），且数据仅存于该访客本地浏览器，不回传 |
| **AI 专家团（消费者）** | `src/agents/` 下的 historian/biographer/context_analyst/critic/philosopher/editor | 不直接操作 UI；通过消费导出的批注 JSON，结合原文与项目规则，产出评判报告 |

> 说明：因纯静态无后端，访客的批注无法汇总到作者。本系统的「评论数据资产」以**作者本机浏览器**为准，通过导出 JSON 文件流转到 Python pipeline。

---

## 三、核心功能清单

### F1 · 原文圈选批注

- 在阅读区（`#reader .markdown-body`）用鼠标/触摸选中文本，松开后选区附近弹出批注浮层。
- 浮层含：评论输入框（多行）、类型选择器（5 类，见第四节）、提交按钮、取消按钮。
- 提交后：选中文本被高亮（带类型颜色），浮层关闭，评论进入下方评论区。

### F2 · 批注高亮与悬浮卡

- 已批注的原文片段以**带下划线 + 浅色底纹**呈现，颜色随评论类型区分。
- 鼠标悬停高亮片段，弹出**悬浮卡**：显示评论内容、类型、作者、时间、回复数、状态（open/resolved）。
- 点击高亮片段，滚动并聚焦评论区对应条目。

### F3 · 回复

- 评论区每条评论可展开回复列表，支持多级回复（建议最多 2 级，避免过深）。
- 回复同样有作者、时间戳；回复不单独设类型，继承父评论类型。

### F4 · 解决 / 重新打开

- 每条评论有 `status`：`open`（待处理）/ `resolved`（已解决）。
- 作者可点「解决」将评论折叠、高亮降饱和；可「重新打开」恢复。
- 已解决的评论默认在评论区收起，可切换「显示已解决」。

### F5 · 评论区汇总

- 阅读区下方设独立评论区（`#reader` 之下或滚动到底部），按原文出现顺序排列评论。
- 顶部提供筛选：按类型、按状态（全部 / open / resolved）、按关键词。
- 空状态：显示「暂无批注，圈选原文即可开始批注」。

### F6 · 评论分类标签

- 每条评论必选一个类型（见第四节枚举），类型决定高亮颜色与图标。
- 类型可在创建后由作者修改。

### F7 · 导出给 AI

- 工具栏新增「导出批注」按钮，下拉选项：
  - 导出当前笔记批注（`comments_<notePath>.json`）
  - 导出全站批注（`comments_all.json`）
- 导出格式见第六节，可直接被 Python pipeline 读取。

### F8 · 导入批注

- 提供「导入批注」入口，选择 JSON 文件后合并到 localStorage（按 `id` 去重，冲突时询问覆盖/跳过）。
- 用于跨设备同步、专家团反馈回填。

### F9 · 专家团触发入口

- 评论区顶部设「启用专家团评判」按钮（仅作者模式可见）。
- 点击后弹出确认浮层，选择评判范围（当前笔记 / 全站），生成一份**评判指令包**（`expert_review_request.json`），含：目标笔记路径、相关批注、原文片段、项目规则引用、期望输出格式。
- 该指令包以文件下载形式提供，用户在本地用 `python src/main.py --expert-review expert_review_request.json`（或等价命令）执行，结果以 JSON 形式手动导入回站点展示。详见第七节。

### F10 · 批注管理

- 每条评论支持：编辑（仅作者）、删除（仅作者，软删除带确认）、复制锚定原文、定位到原文。

---

## 四、评论数据模型

### 4.1 评论对象（Comment）

```json
{
  "id": "c_1719012345678_0",
  "notePath": "资治通鉴/周纪一_三家分晋.md",
  "anchor": {
    "strategy": "text+context",
    "exact": "智伯贪而愎，不与，将伐我",
    "prefix": "韩康子不想给，家臣段规劝他：「",
    "suffix": "。」——智伯又贪又倔",
    "paragraphIndex": 3,
    "headingPath": ["讲事情"],
    "charOffsetStart": 0,
    "charOffsetEnd": 11,
    "version": "2026-06-21"
  },
  "content": "此处段规原话见《资治通鉴·周纪一》，但《国语·晋语》亦有近似记载，建议补注出处。",
  "type": "supplement",
  "author": "作者",
  "createdAt": "2026-06-22T14:32:11+08:00",
  "updatedAt": "2026-06-22T14:35:02+08:00",
  "status": "open",
  "replies": [
    {
      "id": "r_1719012400000_0",
      "content": "已查《国语·晋语九》，确有此句，下次修订补上。",
      "author": "作者",
      "createdAt": "2026-06-22T14:40:00+08:00"
    }
  ],
  "expertReviews": [],
  "deleted": false
}
```

### 4.2 字段定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 全局唯一，格式 `c_<timestamp>_<seq>`，前端生成 |
| `notePath` | string | 是 | 笔记相对路径，与 `data/index.json` 的 `notes` key 一致 |
| `anchor` | object | 是 | 锚定信息，见 4.3 |
| `content` | string | 是 | 评论正文，纯文本（支持简单换行，不做 Markdown 渲染，防 XSS） |
| `type` | enum | 是 | `error` / `praise` / `discussion` / `supplement` / `thought` |
| `author` | string | 是 | 默认「作者」；访客模式可填昵称 |
| `createdAt` | string (ISO 8601) | 是 | 创建时间，带时区 |
| `updatedAt` | string (ISO 8601) | 否 | 最后编辑时间 |
| `status` | enum | 是 | `open` / `resolved` |
| `replies` | array | 否 | 回复列表，每项含 `id`/`content`/`author`/`createdAt` |
| `expertReviews` | array | 否 | 专家团评判结果回填，见第七节 |
| `deleted` | boolean | 是 | 软删除标记，默认 `false` |

### 4.3 锚定策略（anchor）

采用**「文本 + 上下文 + 结构提示」三重定位**，兼顾稳定性与可恢复性：

| 字段 | 说明 | 作用 |
|---|---|---|
| `strategy` | 固定 `"text+context"` | 标识锚定策略版本 |
| `exact` | 选中的原文文本（去首尾空白） | 主定位：在渲染后的 DOM 文本中精确匹配 |
| `prefix` | 选中片段前 20 字（不含选中部分） | 辅助定位：当 `exact` 出现多次时消歧 |
| `suffix` | 选中片段后 20 字 | 辅助定位：同上 |
| `paragraphIndex` | 选中片段所在段落索引（按 `.markdown-body` 下 `p`/`blockquote`/`li` 等块级元素顺序） | 结构提示，加速定位 |
| `headingPath` | 从顶层标题到当前段的标题路径，如 `["讲事情"]` | 跨段落大改时的结构兜底 |
| `charOffsetStart` / `charOffsetEnd` | 在该段纯文本中的字符偏移 | 精确切片，仅作辅助 |
| `version` | 创建批注时的笔记版本（取笔记 frontmatter `created_at` 或文件 hash 前 8 位） | 用于检测原文是否变更 |

**定位算法（加载笔记后执行）：**

1. 取 `anchor.exact`，在 `.markdown-body` 内所有文本节点中查找；
2. 若唯一命中 → 高亮该区间；
3. 若多次命中 → 用 `prefix`/`suffix` 比对，选最匹配的一处；
4. 若零命中 → 用 `headingPath` + `paragraphIndex` 定位到段落，在该段内用 `prefix`/`suffix` 模糊匹配；
5. 仍失败 → 标记为 `orphaned`（孤儿批注），不高亮，仅在评论区以灰色「⚠ 原文已变更」标识展示，作者可手动重新锚定或删除。

### 4.4 评论类型枚举

| type | 中文名 | 图标 | 高亮色（建议，需与现有配色协调） | 用途 |
|---|---|---|---|---|
| `error` | 错误指正 | ❗ | 暗红 `#a83232`（低饱和） | 指出史实、引文、字词错误 |
| `praise` | 写得好 | 👍 | 棕金 `#8b5a2b`（同 accent） | 标记精彩段落，供后续提炼风格 |
| `discussion` | 讨论 | 💬 | 青灰 `#5a7a8a` | 提出疑问、展开思辨 |
| `supplement` | 补充 | ➕ | 橄榄 `#6b7a3a` | 补充史料、出处、背景 |
| `thought` | 感想 | ✦ | 紫灰 `#7a5a8a` | 作者自己的灵感、联想 |

> 颜色均需降低饱和度，以底纹/下划线形式呈现，不破坏阅读体验。

---

## 五、交互流程

### 5.1 主流程：圈选 → 批注 → 高亮 → 评论区

```
[用户在阅读区选中文本]
        ↓
[selectionchange / mouseup 检测有效选区]
        ↓
[计算 anchor.exact / prefix / suffix / paragraphIndex / headingPath]
        ↓
[在选区右下方弹出批注浮层]
        ↓
[用户输入评论 + 选择类型] ──取消──→ 关闭浮层，不清除选区
        ↓ 提交
[生成 Comment 对象，写入 localStorage]
        ↓
[用 <mark> 包裹选中文本，加 type 类名，绑定点击]
        ↓
[评论区追加该条评论，按原文顺序插入]
        ↓
[浮层关闭，选区清除]
```

### 5.2 回复流程

- 评论区某条 → 点「回复」→ 该条下方展开输入框 → 提交 → 追加到 `replies[]` → 折叠输入框。
- 回复支持 `@作者` 提及（纯文本，不做联动）。

### 5.3 解决流程

- 评论条目右侧「解决」按钮 → `status = "resolved"` → 高亮降饱和、评论区条目折叠 → 可「重新打开」。

### 5.4 导出流程

- 工具栏「导出批注」→ 选择范围 → 浏览器下载 JSON 文件 → 文件名 `comments_<notePath|all>_<YYYYMMDD>.json`。

### 5.5 专家团触发流程

- 评论区顶部「启用专家团评判」→ 选择范围（当前笔记/全站）→ 选择参与的专家（默认全选 historian/biographer/context_analyst/critic/philosopher/editor）→ 确认 → 下载 `expert_review_request.json` → 用户在本地终端执行 Python 命令 → 得到 `expert_review_result.json` → 在站点「导入专家评判」回填 → 评判结果显示在对应评论的 `expertReviews` 区。

---

## 六、AI 集成接口

### 6.1 导出格式（供 Python pipeline 消费）

导出文件为单个 JSON，顶层结构：

```json
{
  "schema": "deep-reading-comments/v1",
  "exportedAt": "2026-06-22T15:00:00+08:00",
  "exportedBy": "作者",
  "scope": "note",
  "notePath": "资治通鉴/周纪一_三家分晋.md",
  "projectContext": {
    "rulesFile": ".trae/rules/rules.md",
    "notesDir": "output/",
    "agents": ["historian", "biographer", "context_analyst", "critic", "philosopher", "editor"]
  },
  "comments": [ /* Comment 对象数组，见 4.2 */ ]
}
```

- `scope`：`"note"` 或 `"all"`；为 `all` 时 `notePath` 省略，`comments` 跨笔记汇总。
- 每个 `comment` 额外附带 `noteContent` 字段（该笔记全文，便于专家团对照），仅在 `scope=note` 时附；`scope=all` 时附 `notePath` 即可，专家团按需读取 `output/`。

### 6.2 Python 侧消费约定

- 专家团入口建议在 `src/main.py` 增加 `--expert-review <request.json>` 参数。
- 读取 `request.json` → 按 `comments[].type` 分派给对应专家：
  - `error` / `supplement` → historian + context_analyst + editor
  - `praise` → critic（提炼风格）
  - `discussion` → philosopher + critic
  - `thought` → 不强制分派，由作者自行处理
- 每条评论产出一份 `ExpertReview`：

```json
{
  "commentId": "c_1719012345678_0",
  "verdict": "accept",
  "confidence": 0.85,
  "rationale": "《国语·晋语九》确有近似表述，建议补注。",
  "suggestedEdit": {
    "action": "append_citation",
    "target": "anchor.exact",
    "text": "（参见《国语·晋语九》）"
  },
  "reviewedBy": ["historian", "editor"]
}
```

- `verdict`：`accept`（采纳，建议改原文）/ `reject`（不采纳）/ `needs_discussion`（需作者再判断）。
- 结果汇总为 `expert_review_result.json`，供站点导入。

### 6.3 站点侧导入评判

- 导入后，每条 `ExpertReview` 挂到对应 `comment.expertReviews[]`。
- 评论区条目展示评判徽章（采纳/不采纳/待议），点击展开 `rationale` 与 `suggestedEdit`。
- **评判结果不自动改原文**；作者可点「应用建议」复制 `suggestedEdit.text` 到剪贴板，手动修订 `output/*.md`，再跑 `scripts/build_site.py`。

---

## 七、专家团触发机制

### 7.1 触发入口

- 评论区顶部按钮「启用专家团评判」，仅当 `author === "作者"` 且当前笔记有 ≥1 条评论时可用。
- 点击弹出向导：

| 步骤 | 内容 |
|---|---|
| 1. 范围 | 单选：当前笔记 / 全站 |
| 2. 参与专家 | 多选：historian / biographer / context_analyst / critic / philosopher / editor（默认全选） |
| 3. 附加指令 | 文本框：可填「重点核查引文出处」「评估讲道理部分是否过度引申」等 |
| 4. 确认 | 生成并下载 `expert_review_request.json`，同时显示本地执行命令提示 |

### 7.2 输入（request 包）

见 6.1，额外字段：

```json
{
  "expertReviewRequest": {
    "participants": ["historian", "biographer", "context_analyst", "critic", "philosopher", "editor"],
    "additionalInstruction": "重点核查引文出处",
    "rulesReference": ".trae/rules/rules.md"
  }
}
```

### 7.3 输出（result 包）

见 6.2，顶层：

```json
{
  "schema": "deep-reading-expert-review/v1",
  "requestRef": "expert_review_request.json",
  "reviewedAt": "2026-06-22T16:00:00+08:00",
  "reviews": [ /* ExpertReview 数组 */ ]
}
```

### 7.4 闭环

```
站点导出 request ──→ 本地 Python 执行 ──→ 站点导入 result ──→ 作者人工决定是否修订 ──→ 修订后重建站点
```

> 关键约束：站点永远不直接调用 LLM、不直接改 `output/*.md`。Python pipeline 在本地运行，结果以文件形式回流。

---

## 八、非功能需求

### 8.1 纯静态无后端

- 全部逻辑在浏览器内运行，仅依赖 `marked.js` CDN（已有）。
- 数据存储：`localStorage`，key 命名 `drc:<notePath>` 存该笔记评论数组，`drc:meta` 存元信息（版本、最后导出时间）。
- 不引入任何 fetch 写操作；只读 `data/index.json` 与 `notes/*.md`（已有）。

### 8.2 导入导出

- 导出：`Blob` + `URL.createObjectURL` 触发下载，文件名见 5.4。
- 导入：`<input type="file">` 读取，按 `id` 去重合并，冲突弹窗询问。
- localStorage 容量预警：单笔记评论 > 200 条或总量 > 4MB 时，提示导出后清理。

### 8.3 性能

- 单笔记评论高亮渲染 < 100ms（100 条以内）。
- 选区弹浮层 < 200ms。
- 评论区虚拟滚动：评论 > 50 条时仅渲染可视区域（可选实现，首版可先全量渲染）。

### 8.4 可访问性

- 浮层、悬浮卡、评论区均需键盘可达：Tab 顺序合理，Esc 关闭浮层，Enter 提交（Shift+Enter 换行）。
- 高亮片段用 `<mark>` 语义标签，加 `aria-label` 描述评论类型与数量。
- 评论区用 `<section aria-label="批注列表">`，每条用 `<article>`。
- 颜色对比度满足 WCAG AA（暗红/青灰等低饱和色用于底纹时，文字仍用 `--ink-primary`）。

### 8.5 视觉协调

- 复用 `style.css` 的 CSS 变量：`--bg-paper`、`--accent`、`--border`、`--radius`、`--font-serif`、`--font-sans`。
- 浮层、悬浮卡用白底 + `--shadow`，圆角 `--radius`，与现有 modal 风格一致。
- 高亮底纹透明度 ≤ 0.18，下划线 1px，不抢正文阅读。
- 评论区字体：评论正文用 `--font-sans`（与正文宋体区分，便于扫读），标题用 `--font-serif`。

### 8.6 与现有 app.js 的集成约束

- 评论系统作为**独立模块** `site/js/comments.js`，通过全局命名空间 `window.DeepReadingComments` 暴露最小 API：
  - `init(readerEl)`：在指定阅读区容器内启用批注。
  - `loadForNote(notePath)`：加载某笔记的评论并渲染高亮。
  - `clear()`：切换笔记时清理。
- `app.js` 的 `loadNote()` 在渲染完 `<article class="markdown-body">` 后调用 `window.DeepReadingComments.loadForNote(path)`。
- 不修改 `app.js` 现有函数签名与 state 结构，仅在 `loadNote` 末尾追加一行调用（用 `if (window.DeepReadingComments)` 守卫）。
- `index.html` 追加 `<script src="js/comments.js" defer></script>`，置于 `app.js` 之前或之后均可（用 `init` 时机解耦）。

### 8.7 安全

- 评论 `content` 渲染时强制 `escapeHtml`（复用 `app.js` 现有 `escapeHtml`），禁止 HTML 注入。
- 不使用 `innerHTML` 拼接用户输入；评论区 DOM 用 `createElement` + `textContent` 构建。
- 导入 JSON 时校验 schema 与字段类型，非法文件拒绝并提示。

---

## 九、边界与不做事项

| 项 | 决策 | 理由 |
|---|---|---|
| 多人协同 | 不做 | 纯静态无后端，协同需服务端 |
| 评论富文本/图片 | 不做 | 防 XSS，保持纯文本 |
| 评论点赞/投票 | 不做 | 主要服务作者本人，无社交需求 |
| 评论全文搜索 | 不做 | 量级小，列表筛选足够 |
| 自动同步到 git | 不做 | 由作者手动导出 JSON 提交 |
| 自动改原文 | 不做 | 修订权在人，专家团仅给建议 |
| 跨笔记批注（一条评论锚定多笔记） | 不做 | 锚定复杂度爆炸，单笔记内闭环 |
| 移动端圈选 | 支持但降级 | 触摸选区体验差，提供「手动输入锚定文本」兜底入口 |
| 评论版本历史 | 不做（首版） | 仅保留 `updatedAt`，不存全量历史 |
| 实时专家团（站点内直接调 LLM） | 不做 | 纯静态约束，专家团在本地 Python 跑 |

---

## 十、交付物清单

| 文件 | 说明 |
|---|---|
| `site/js/comments.js` | 评论系统主模块（vanilla JS，IIFE） |
| `site/css/comments.css` | 评论系统样式（可并入 `style.css` 或独立文件） |
| `site/index.html` | 追加 `comments.js` 引用与评论区容器 |
| `site/js/app.js` | `loadNote` 末尾追加 `DeepReadingComments.loadForNote` 调用 |
| `docs/comments-system/spec.md` | 本文件 |
| `docs/comments-system/checklist.md` | 评审 checklist |
| `src/main.py`（建议） | 增加 `--expert-review` 入口（由 Python 侧实现，非本规格强制） |

---

## 十一、验收口径（与 checklist.md 对齐）

- 圈选 → 浮层 → 提交 → 高亮 → 评论区，全链路在 vanilla JS 下可用。
- 关闭并重开浏览器，评论与高亮仍存在（localStorage）。
- 修改原文个别字词后重开，高亮仍能定位（三重锚定）。
- 导出 JSON 可被 Python 脚本 `json.load` 正常解析，字段齐全。
- 专家团触发可生成 `expert_review_request.json`，导入 `expert_review_result.json` 后评判徽章正确显示。
- 视觉与现有暖纸色风格协调，无突兀感。
- 移动端可读、可写评论（圈选降级可用）。
