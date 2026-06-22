# 静态网站原文批注式评论系统 — 技术架构方案

> 目标读者：实现该系统的前端 agent。
> 约束：纯静态站点（vanilla JS + marked.js CDN），部署 GitHub Pages，无后端，主要服务作者本人。
> 现有代码基线：`site/js/app.js`（IIFE）、`site/index.html`、`site/css/style.css`、`scripts/build_site.py`、`src/agents/`（Python AI 工作流）。

---

## 0. 总体设计原则

1. **零后端**：所有评论数据存 `localStorage`，导出为 JSON 文件供 AI pipeline 消费。
2. **不破坏现有 IIFE**：`app.js` 不做结构性重构，只插入一个事件分发钩子；评论系统作为独立 IIFE 模块通过自定义事件接入。
3. **锚定优先**：评论系统的成败取决于"原文改动后高亮还能不能找回位置"，因此文本锚定算法是核心。
4. **渲染后介入**：所有高亮、wrap 操作都在 `marked.parse` 完成、`sanitizeHtml` 清洗、DOM 注入之后进行，绝不修改 marked 渲染管线。
5. **古籍暖纸风格一致**：评论 UI 复用 `style.css` 的 CSS 变量（`--accent`、`--bg-paper`、`--font-serif` 等），不引入新设计语言。

---

## 1. 模块划分

### 1.1 文件清单

| 文件 | 职责 |
|---|---|
| `site/js/comments.js` | 评论系统主模块（IIFE），暴露 `window.CommentsAPI` |
| `site/css/comments.css` | 评论系统样式（高亮、浮层、面板、线程） |
| `site/data/comments.json` | （可选）构建期生成的导出快照，供 AI 直接读取 |
| `docs/comments-system/architecture.md` | 本文档 |

### 1.2 模块边界与解耦

`comments.js` 是一个独立 IIFE，**不引用** `app.js` 内部的任何私有变量（`state`、`elements`、`loadNote` 等）。它只通过两个渠道与 `app.js` 通信：

- **入站**：监听 `document` 上的自定义事件 `note:loaded`（由 `app.js` 在渲染完成后 dispatch）。
- **出站**：通过 `window.CommentsAPI` 暴露方法，供未来扩展或控制台调试使用。

```
┌─────────────────────────┐      note:loaded (CustomEvent)      ┌────────────────────────┐
│         app.js          │ ─────────────────────────────────▶  │      comments.js       │
│  (现有 IIFE，不动逻辑)  │                                      │  (独立 IIFE，监听事件) │
│                         │ ◀─────────────────────────────────  │                        │
└─────────────────────────┘   window.CommentsAPI.* (可选回调)    └────────────────────────┘
```

### 1.3 `window.CommentsAPI` 接口

```js
window.CommentsAPI = {
  // 状态查询
  getComments(notePath),          // Comment[]
  getAllComments(),               // { [notePath]: Comment[] }
  getIndex(),                     // IndexEntry[]

  // 显式控制（一般由 UI 触发，也供外部调用）
  attach(container, notePath),    // 为指定容器初始化高亮+选区监听
  detach(),                       // 卸载当前笔记的监听
  refresh(),                      // 重新渲染当前笔记的高亮

  // 数据操作
  exportNote(notePath),           // string (JSON)
  exportAll(),                    // string (JSON)
  importJSON(jsonStr, mode),      // mode: 'merge' | 'replace'
  clearNote(notePath),

  // 专家团
  exportForAgents(notePath),      // string (JSON，AI 友好格式)
  copyAsPromptContext(notePath),  // Promise<void>，复制到剪贴板
};
```

### 1.4 `app.js` 需要的最小改动

**仅一处**：在 `loadNote` 函数中，`elements.reader.innerHTML = ...` 注入 HTML 之后，dispatch 一个自定义事件。改动位置在 `app.js` 第 217 行附近：

```js
// 改动前
elements.reader.innerHTML = `<article class="markdown-body">${metaHtml}${html}</article>`;
```

```js
// 改动后
elements.reader.innerHTML = `<article class="markdown-body">${metaHtml}${html}</article>`;

// —— 评论系统接入钩子（开始）——
const article = elements.reader.querySelector('.markdown-body');
if (article) {
    document.dispatchEvent(new CustomEvent('note:loaded', {
        detail: { notePath: path, container: article, meta: meta || null }
    }));
}
// —— 评论系统接入钩子（结束）——
```

> 注意：`loadNote` 的 `catch` 分支（加载失败）**不要** dispatch `note:loaded`，避免评论模块把错误占位符当成正文。

`index.html` 需要追加两行资源引用（在 `app.js` 之后）：

```html
<link rel="stylesheet" href="css/comments.css">
<script src="js/comments.js" defer></script>
```

`scripts/build_site.py` **无需改动**；评论数据是运行时产物，不进入构建期。

---

## 2. 文本锚定算法（核心）

### 2.1 问题陈述

原文是 Markdown 经 `marked.parse` 渲染成的 HTML。评论可能在不同时间、不同笔记版本下被打开。直接用 DOM 节点路径或字符偏移会因以下原因失效：

- marked 版本升级导致输出 HTML 结构变化（如 `<p>` 变 `<p>` 多了空格）。
- 笔记小幅修订（改个标点、加句话）。
- 浏览器对 `innerHTML` 的空白归一化。

因此锚定必须基于**语义文本**而非 DOM 结构。

### 2.2 规范化纯文本（Normalized Text）

定义：把 `.markdown-body` 容器内所有**可批注文本节点**的 `nodeValue` 拼接成一个字符串，拼接时做以下归一化：

- 连续空白（含 `\n`、`\t`、多空格）压缩为单个空格。
- 去除首尾空白。
- 全角/半角不做转换（保留原文，避免误伤）。

**可批注文本节点**的定义（用 `TreeWalker` 过滤）：

- `NodeFilter.SHOW_TEXT`。
- 父节点不是 `<script>`、`<style>`、`<code>`、`<pre>`、`<kbd>`、`<samp>`。
- 父节点不是标签元素（`h1`-`h6`）—— 标题不批注，避免锚点漂移。
- 父节点不是 `<a>` 内的非文本部分（链接文本可批注，但需小心）。
- 文本非空（归一化后长度 > 0）。

> 标题、代码块不批注是产品决策：标题改动频率高、代码块字符精确但语义脆弱。在选区交互层就拦截，不让用户在这些区域创建评论。

### 2.3 数据结构

```ts
interface Anchor {
  notePath: string;            // 所属笔记相对路径，如 "资治通鉴/周纪一_三家分晋.md"
  quote: string;               // 选区原文片段（归一化后），用于校验与模糊匹配
  rangeStart: number;          // 在规范化纯文本中的起始字符偏移
  rangeEnd: number;            // 结束偏移（exclusive）
  normTextPrefix: string;      // 起始位置前 32 字符（归一化后），前缀指纹
  normTextSuffix: string;      // 结束位置后 32 字符（归一化后），后缀指纹
  schemaVersion: 1;            // 锚定结构版本，便于未来迁移
}
```

`quote` 长度限制：建议 8 ~ 256 字符。过短易误匹配，过长不易跨节点 wrap。在选区交互层做截断提示。

### 2.4 锚定建立流程（`captureAnchor`）

```js
/**
 * 从当前 Selection 捕获锚点。
 * @param {Selection} selection
 * @param {string} notePath
 * @returns {Anchor | null} 锚点对象；若选区不在可批注区域则返回 null
 */
function captureAnchor(selection, notePath) {
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  const container = document.querySelector('.markdown-body');
  if (!container || !container.contains(range.commonAncestorContainer)) return null;

  // 1. 校验选区不落在禁批注元素内
  if (rangeIntersectsForbidden(range)) return null;

  // 2. 构建规范化纯文本 + 字符偏移到 (node, offset) 的映射
  const { normText, charMap } = buildNormalizedText(container);

  // 3. 计算选区在 normText 中的起止偏移
  const startInfo = mapDomOffsetToNorm(range.startContainer, range.startOffset, charMap);
  const endInfo   = mapDomOffsetToNorm(range.endContainer, range.endOffset, charMap);
  if (!startInfo || !endInfo || endInfo.normOffset <= startInfo.normOffset) return null;

  const rangeStart = startInfo.normOffset;
  const rangeEnd   = endInfo.normOffset;
  const quote      = normText.slice(rangeStart, rangeEnd);

  // 4. 截取前缀/后缀指纹
  const normTextPrefix = normText.slice(Math.max(0, rangeStart - 32), rangeStart);
  const normTextSuffix = normText.slice(rangeEnd, rangeEnd + 32);

  return { notePath, quote, rangeStart, rangeEnd, normTextPrefix, normTextSuffix, schemaVersion: 1 };
}
```

### 2.5 `buildNormalizedText` 与 `charMap`

```js
/**
 * 遍历容器内可批注文本节点，构建规范化纯文本与反向映射。
 * @returns {{
 *   normText: string,
 *   charMap: Array<{ node: Text, nodeOffset: number, normOffset: number, length: number }>,
 *   nodeIndex: WeakMap<Text, { startNorm: number, segments: Array<{nodeOffset:number, normOffset:number, len:number}> }>
 * }}
 */
function buildNormalizedText(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      return isAnnotatableText(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    }
  });

  const charMap = [];   // 按字符粒度记录来源（稀疏：每个文本节点一条记录）
  const nodeIndex = new WeakMap();
  let normText = '';

  let textNode;
  while ((textNode = walker.nextNode())) {
    const raw = textNode.nodeValue;
    // 归一化：连续空白压成单空格，首尾去
    const normalized = raw.replace(/\s+/g, ' ');
    if (normalized === '') continue;

    // 记录该文本节点的映射段
    const startNorm = normText.length;
    // 注意：归一化会改变字符与原 nodeOffset 的对应关系，需逐段映射
    const segments = mapRawToNormalized(raw, normalized, startNorm);
    nodeIndex.set(textNode, { startNorm, segments });

    charMap.push({ node: textNode, startNorm, length: normalized.length });
    normText += normalized;
    if (!normText.endsWith(' ') && !normText.endsWith('')) {
      // 节点之间默认不加分隔（原文已有空白被归一化）；若两节点文本直接相邻且都非空格结尾，补一个空格分隔
      // 实际上 marked 输出里 <p> 之间会有换行，归一化后已是空格，这里不额外处理
    }
  }

  return { normText, charMap, nodeIndex };
}
```

`mapRawToNormalized` 处理"原文本中第 i 个字符对应归一化文本第 j 个字符"的映射（因为 `\s+` 压缩会丢弃字符）。实现要点：遍历原文本，遇到连续空白记为一次"压缩"，非空白字符 1:1 映射。

### 2.6 锚定解析流程（`resolveAnchor`）

重新渲染后，已保存的 `rangeStart/rangeEnd` 可能因原文改动而漂移。解析采用**三级容错**：

```js
/**
 * 在当前容器内解析锚点，返回一个 Range（用于 wrap 高亮）。
 * 三级策略：精确偏移 → quote 全文匹配 → 前缀+后缀指纹模糊匹配。
 * @param {Anchor} anchor
 * @param {Element} container
 * @returns {Range | null}
 */
function resolveAnchor(anchor, container) {
  const { normText, charMap, nodeIndex } = buildNormalizedText(container);

  // —— 级别 1：精确偏移 + quote 校验 ——
  if (anchor.rangeEnd <= normText.length) {
    const slice = normText.slice(anchor.rangeStart, anchor.rangeEnd);
    if (slice === anchor.quote) {
      return normRangeToDomRange(anchor.rangeStart, anchor.rangeEnd, charMap, nodeIndex);
    }
  }

  // —— 级别 2：quote 全文查找（首次出现位置）——
  const idx = normText.indexOf(anchor.quote);
  if (idx !== -1) {
    return normRangeToDomRange(idx, idx + anchor.quote.length, charMap, nodeIndex);
  }

  // —— 级别 3：前缀 + 后缀指纹模糊定位 ——
  // 在 normText 中找到 prefix 出现的位置 p，则锚点起点应在 p + prefix.length 附近；
  // 再用 suffix 校验终点。允许 prefix/suffix 各有少量字符偏差（用滑动窗口 + 编辑距离阈值）。
  const fuzzy = fuzzyLocateByFingerprints(normText, anchor.normTextPrefix, anchor.normTextSuffix, anchor.quote.length);
  if (fuzzy) {
    return normRangeToDomRange(fuzzy.start, fuzzy.end, charMap, nodeIndex);
  }

  return null; // 解析失败，评论以"未定位"状态展示
}
```

`fuzzyLocateByFingerprints` 关键策略：

1. 在 `normText` 中搜索 `normTextPrefix` 的最近匹配（允许 ≤2 字符编辑距离），得候选起点集 `P`。
2. 对每个候选起点 `p`，预期终点 `e = p + quote.length`，检查 `normText.slice(e, e + suffix.length)` 与 `normTextSuffix` 的编辑距离是否 ≤2。
3. 取第一个同时满足前缀和后缀的候选。
4. 若都失败，回退为"未定位"，评论仍可显示在汇总区，但不高亮。

### 2.7 高亮 wrap（不破坏 marked 渲染）

**核心约束**：marked 输出的 HTML 已注入 DOM，**不能**重新 `innerHTML`。所有高亮通过 Range API 在文本节点上切分 + 包裹。

```js
/**
 * 把一个 Range 包裹成 <mark class="cm-highlight" data-cm-id="...">。
 * 跨多个文本节点时，逐节点切分并分别包裹，保持原 DOM 结构。
 * @param {Range} range
 * @param {string} commentId
 */
function wrapRangeWithHighlight(range, commentId) {
  // 若起止在同一文本节点，先 splitText 切出精确区间
  const startContainer = range.startContainer;
  const endContainer   = range.endContainer;

  // 收集范围内所有文本节点
  const textNodes = collectTextNodesInRange(range);
  if (textNodes.length === 0) return;

  // 对第一个节点：从 startOffset 切分，取后半段
  // 对最后一个节点：从 endOffset 切分，取前半段
  // 中间节点：整段包裹
  textNodes.forEach((node, i) => {
    let target = node;
    if (i === 0 && node === startContainer && range.startOffset > 0) {
      target = node.splitText(range.startOffset);
    }
    if (i === textNodes.length - 1 && node === endContainer) {
      // 注意：若同一节点既是首又是尾，上面 splitText 后 endOffset 需修正
      const offset = (node === startContainer) ? range.endOffset - range.startOffset : range.endOffset;
      if (offset < target.length) target.splitText(offset);
    }
    const mark = document.createElement('mark');
    mark.className = 'cm-highlight';
    mark.dataset.cmId = commentId;
    target.parentNode.insertBefore(mark, target);
    mark.appendChild(target);
  });
}
```

**unwrap（删除评论或解决时）**：用 `querySelectorAll(mark[data-cm-id="..."])` 找到所有 mark，将其子节点 `replaceChild` 回父节点，再 normalize 父节点合并相邻文本节点。

> 同一锚点被多个评论引用时，`data-cm-id` 存主评论 ID；线程内其他评论通过 `data-cm-thread` 关联。视觉上只 wrap 一次，点击展开整个线程。

### 2.8 关键函数签名汇总

```js
// 锚定
buildNormalizedText(root): { normText, charMap, nodeIndex }
isAnnotatableText(textNode): boolean
rangeIntersectsForbidden(range): boolean
captureAnchor(selection, notePath): Anchor | null
resolveAnchor(anchor, container): Range | null
fuzzyLocateByFingerprints(normText, prefix, suffix, quoteLen): { start, end } | null
normRangeToDomRange(normStart, normEnd, charMap, nodeIndex): Range | null

// 高亮
wrapRangeWithHighlight(range, commentId): void
unwrapHighlight(commentId): void
collectTextNodesInRange(range): Text[]
```

---

## 3. 存储方案

### 3.1 localStorage 键设计

| Key | 值 | 说明 |
|---|---|---|
| `cm:index` | `IndexEntry[]` | 全局索引，列出所有有评论的 notePath 及统计 |
| `cm:comments:<notePath>` | `Comment[]` | 单篇笔记的评论数组，按 `createdAt` 升序 |
| `cm:meta` | `{ schemaVersion, lastExportAt, settings }` | 元信息 |

`<notePath>` 中的 `/` 保留原样（localStorage key 允许任意字符），无需转义。例：`cm:comments:资治通鉴/周纪一_三家分晋.md`。

### 3.2 `IndexEntry` 结构

```ts
interface IndexEntry {
  notePath: string;
  count: number;          // 评论总数（含回复）
  threadCount: number;    // 主评论数
  unresolvedCount: number;// 未解决的主评论数
  lastUpdatedAt: string;  // ISO 8601
}
```

### 3.3 `Comment` 完整 JSON Schema

```ts
interface Comment {
  id: string;             // UUID v4，主键
  notePath: string;       // 所属笔记
  parentId: string | null;// 顶级评论为 null；回复指向被回复评论的 id
  type: 'comment' | 'question' | 'insight' | 'critique';
  // type 语义：
  //   comment  普通评论
  //   question 提问
  //   insight  洞察
  //   critique 批评/质疑（供 critic agent 消费）
  status: 'open' | 'resolved';
  anchor: Anchor | null;  // 顶级评论有锚点；回复无锚点（parentId 非空时为 null）
  content: string;        // 评论正文（纯文本，渲染时转义）
  author: string;         // 作者标识，默认 "author"
  createdAt: string;      // ISO 8601
  updatedAt: string;      // ISO 8601
  resolvedAt: string | null;
  tags: string[];         // 自由标签，如 ["人物:智伯", "待查"]
  // AI 消费用
  agentHints?: {
    targetAgent?: 'historian' | 'biographer' | 'context_analyst' | 'critic' | 'philosopher' | 'editor';
    priority?: 'low' | 'normal' | 'high';
  };
}
```

### 3.4 存储读写函数

```js
const Storage = {
  SCHEMA_VERSION: 1,

  loadComments(notePath) {
    try {
      const raw = localStorage.getItem(`cm:comments:${notePath}`);
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  },

  saveComments(notePath, comments) {
    localStorage.setItem(`cm:comments:${notePath}`, JSON.stringify(comments));
    this.updateIndex(notePath, comments);
  },

  loadIndex() {
    try {
      const raw = localStorage.getItem('cm:index');
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  },

  updateIndex(notePath, comments) {
    const idx = this.loadIndex().filter(e => e.notePath !== notePath);
    const threads = comments.filter(c => c.parentId === null);
    idx.push({
      notePath,
      count: comments.length,
      threadCount: threads.length,
      unresolvedCount: threads.filter(t => t.status === 'open').length,
      lastUpdatedAt: new Date().toISOString(),
    });
    localStorage.setItem('cm:index', JSON.stringify(idx));
  },

  deleteNote(notePath) {
    localStorage.removeItem(`cm:comments:${notePath}`);
    const idx = this.loadIndex().filter(e => e.notePath !== notePath);
    localStorage.setItem('cm:index', JSON.stringify(idx));
  },
};
```

### 3.5 导出 / 导入

**导出单篇**（`exportNote`）：

```json
{
  "schemaVersion": 1,
  "exportedAt": "2026-06-22T10:00:00+08:00",
  "notePath": "资治通鉴/周纪一_三家分晋.md",
  "comments": [ /* Comment[] */ ]
}
```

**导出全部**（`exportAll`）：

```json
{
  "schemaVersion": 1,
  "exportedAt": "2026-06-22T10:00:00+08:00",
  "notes": [
    { "notePath": "...", "comments": [ /* ... */ ] }
  ]
}
```

**导入**（`importJSON(jsonStr, mode)`）：

- `mode: 'merge'`：按 `id` 去重合并，已存在的 `id` 用新数据覆盖（`updatedAt` 更新），不存在的追加。
- `mode: 'replace'`：清空目标 notePath 的评论后写入。

导入完成后立即 `refresh()` 当前笔记高亮。

### 3.6 AI 消费的导出格式

`exportForAgents(notePath)` 产出 AI 友好结构（与 `src/agents/` 的 `AgentState` 字段对齐）：

```json
{
  "schemaVersion": 1,
  "exportedAt": "2026-06-22T10:00:00+08:00",
  "notePath": "资治通鉴/周纪一_三家分晋.md",
  "book": "资治通鉴",
  "chapter": "周纪一",
  "event": "三家分晋",
  "threads": [
    {
      "threadId": "uuid",
      "anchor": {
        "quote": "智伯贪而愎，不与，将伐我。",
        "rangeStart": 1234,
        "rangeEnd": 1245
      },
      "status": "open",
      "tags": ["人物:智伯"],
      "targetAgent": "critic",
      "priority": "high",
      "messages": [
        {
          "id": "uuid",
          "author": "author",
          "type": "critique",
          "content": "这里段规的判断是否过于绝对？",
          "createdAt": "2026-06-22T09:00:00+08:00"
        },
        {
          "id": "uuid",
          "author": "author",
          "type": "comment",
          "content": "补充：《国语》原文还有……",
          "createdAt": "2026-06-22T09:05:00+08:00"
        }
      ]
    }
  ]
}
```

**落盘建议**：

- 用户点击"导出给 AI"按钮 → 浏览器下载 `comments_<notePath>.json`。
- 用户手动放到 `output/.comments/` 目录（与 `output/*.md` 同级但隔离）。
- Python pipeline 通过 `src/storage/file_manager.py` 读取该目录，把 `threads` 注入 `AgentState` 作为 `user_input` 或新增字段 `author_comments`。

> 不强制写入 `site/data/comments.json`，因为 GitHub Pages 是只读部署，运行时数据不应进仓库。若作者希望版本化评论，可手动把导出文件提交到 `output/.comments/`。

---

## 4. 高亮渲染与选区交互

### 4.1 事件监听

```js
function attachSelectionListeners(container) {
  // 用 mouseup + selectionchange 双保险
  container.addEventListener('mouseup', handleSelectionEnd);
  document.addEventListener('selectionchange', handleSelectionChange);
  // 点击已有高亮
  container.addEventListener('click', handleHighlightClick);
}
```

`handleSelectionEnd`：

1. 取 `window.getSelection()`。
2. 若 `isCollapsed` → 隐藏浮层，返回。
3. 取 `getRangeAt(0)`，校验 `commonAncestorContainer` 在 `.markdown-body` 内。
4. 调 `rangeIntersectsForbidden(range)`：若选区与 `h1-h6`、`pre`、`code`、`blockquote > cite` 等相交，**不弹浮层**（可选用 toast 提示"标题/代码块暂不支持批注"）。
5. 调 `captureAnchor`，成功则显示浮层。

### 4.2 浮层定位

```js
function positionPopover(popover, range) {
  const rect = range.getBoundingClientRect();
  const scrollY = window.scrollY;
  popover.style.left = `${rect.left + rect.width / 2}px`;
  popover.style.top  = `${rect.bottom + scrollY + 8}px`;
  popover.style.transform = 'translateX(-50%)';
}
```

浮层 DOM：

```html
<div class="cm-popover" id="cmPopover" hidden>
  <textarea class="cm-popover-input" placeholder="写下你的批注…"></textarea>
  <div class="cm-popover-actions">
    <select class="cm-popover-type">
      <option value="comment">评论</option>
      <option value="question">提问</option>
      <option value="insight">洞察</option>
      <option value="critique">质疑</option>
    </select>
    <select class="cm-popover-agent">
      <option value="">不指定专家</option>
      <option value="historian">史官</option>
      <option value="biographer">传记官</option>
      <option value="context_analyst">背景分析</option>
      <option value="critic">名家点评</option>
      <option value="philosopher">问道</option>
      <option value="editor">编辑</option>
    </select>
    <button class="cm-popover-submit btn-primary">提交</button>
  </div>
</div>
```

提交逻辑：

1. 读取 textarea 内容，trim 后非空。
2. 生成 `Comment`（`parentId: null`，`status: 'open'`，`anchor: captureAnchor(...)`）。
3. `Storage.saveComments`。
4. `wrapRangeWithHighlight(range, comment.id)`。
5. 隐藏浮层，清空 textarea。
6. 触发 `comments:changed` 事件，刷新汇总面板。

### 4.3 点击高亮 → 展开线程

```js
function handleHighlightClick(e) {
  const mark = e.target.closest('mark.cm-highlight');
  if (!mark) return;
  const id = mark.dataset.cmId;
  openThreadPanel(id); // 在右侧/底部展开该评论线程
}
```

线程面板内可：回复、改状态（open/resolved）、改 type、改 tags、删除、跳转锚点（`scrollIntoView` + 闪烁动画）。

### 4.4 边界处理

- **跨节点选区**：`wrapRangeWithHighlight` 已处理（逐节点切分包裹）。
- **选中标题/代码**：`rangeIntersectsForbidden` 拦截。
- **选中整段含禁批注元素**：用 `Range.intersectsNode` 逐个检查禁批注元素是否与选区相交，相交则拒绝。
- **选区跨越 `.markdown-body` 边界**：`commonAncestorContainer` 不在容器内即拒绝。
- **二次提交同一选区**：允许，生成新评论，但视觉上第二个 mark 会紧贴第一个（CSS 用 `box-shadow` 而非 `background` 区分）。

---

## 5. 评论区汇总

### 5.1 当前笔记汇总面板

布局：`.markdown-body` 右侧增加一个可折叠的 `aside.cm-panel`（窄屏下移到底部）。结构：

```html
<aside class="cm-panel" id="cmPanel">
  <header class="cm-panel-header">
    <h3>批注 <span class="cm-panel-count">0</span></h3>
    <div class="cm-panel-actions">
      <button id="cmExportNote">导出本篇</button>
      <button id="cmExportAgents">导出给专家团</button>
      <button id="cmCopyPrompt">复制为 Prompt</button>
    </div>
  </header>
  <div class="cm-panel-sort">
    <label><input type="radio" name="cmSort" value="position" checked> 按位置</label>
    <label><input type="radio" name="cmSort" value="time"> 按时间</label>
    <label><input type="radio" name="cmSort" value="status"> 按状态</label>
  </div>
  <ul class="cm-thread-list" id="cmThreadList"></ul>
</aside>
```

每个线程条目：

```html
<li class="cm-thread" data-cm-id="..." data-cm-status="open">
  <div class="cm-thread-quote">「智伯贪而愎…」</div>
  <div class="cm-thread-meta">
    <span class="cm-thread-type">质疑</span>
    <span class="cm-thread-status">未解决</span>
    <span class="cm-thread-time">2026-06-22 09:00</span>
  </div>
  <ul class="cm-thread-messages">
    <li class="cm-msg">...</li>
  </ul>
  <div class="cm-thread-actions">
    <button>回复</button>
    <button>解决</button>
    <button>跳转</button>
    <button>删除</button>
  </div>
</li>
```

- **按位置排序**：用 `anchor.rangeStart` 升序；无锚点的（解析失败）排末尾。
- **按时间**：`createdAt`。
- **按状态**：`open` 在前，`resolved` 在后。
- **点击跳转**：`resolveAnchor` → `scrollIntoView({behavior:'smooth', block:'center'})` → 给 mark 加 `cm-flash` 类，500ms 后移除。

### 5.2 全局视图（可选）

在工具栏增加"批注总览"按钮，打开模态框（复用现有 `.modal-overlay` 结构），列出 `cm:index` 中所有笔记的评论统计，点击跳转到对应笔记。

---

## 6. 专家团触发

### 6.1 触发流程

纯静态站点无法直接调用 Python，因此采用"导出 → 手动运行"模式：

```
[前端] 点击"导出给专家团"
   ↓
[前端] 生成 exportForAgents(notePath) JSON
   ↓
[前端] 触发浏览器下载 comments_<book>_<chapter>_<event>.json
   ↓
[用户] 将文件放到 output/.comments/ 目录
   ↓
[用户] 运行: python src/main.py --book ... --chapter ... --event ... --with-comments
   ↓
[Python] file_manager 读取 output/.comments/*.json，注入 AgentState
   ↓
[Agents] 各 agent 在生成段落时参考 author_comments
```

### 6.2 "复制为 Prompt 上下文"按钮

为方便快速喂给 LLM，提供一键复制纯文本格式：

```
# 作者批注上下文
笔记：资治通鉴/周纪一_三家分晋.md

## 批注 1 [质疑] [目标专家: critic] [优先级: high]
原文：「智伯贪而愎，不与，将伐我。」
作者：这里段规的判断是否过于绝对？
回复：补充：《国语》原文还有……

## 批注 2 [提问] [目标专家: historian]
原文：「城不浸者三版」
作者：三版具体多高？换算成现在多少米？
```

格式由 `formatCommentsAsPrompt(notePath)` 生成，复制到剪贴板。

### 6.3 Python 侧消费建议

在 `src/storage/file_manager.py` 增加读取函数（实现 agent 自行落地）：

```python
def load_author_comments(output_dir: Path, book: str, chapter: str, event: str) -> list[dict]:
    """读取 output/.comments/ 下对应笔记的作者批注。"""
    comments_dir = output_dir.parent / ".comments"
    # 文件名约定: comments_<book>_<chapter>_<event>.json
    candidates = list(comments_dir.glob(f"comments_{book}_{chapter}_{event}*.json"))
    if not candidates:
        return []
    with open(candidates[0], encoding="utf-8") as f:
        data = json.load(f)
    return data.get("threads", [])
```

在 `src/core/state.py` 的 `AgentState` 增加可选字段：

```python
class AgentState(TypedDict, total=False):
    # ... 现有字段 ...
    author_comments: list[dict]  # 作者批注线程
```

各 agent 的 prompt 模板（`prompts/*.md`）在合适位置插入 `{{author_comments}}` 占位符，由 `src/utils/prompts.py` 渲染。批注按 `targetAgent` 过滤后只传给对应 agent；未指定 `targetAgent` 的传给所有 agent。

---

## 7. 与现有 `app.js` 的集成点（清单）

| # | 位置 | 改动 | 说明 |
|---|---|---|---|
| 1 | `app.js` `loadNote` 成功分支末尾（约第 217 行后） | dispatch `note:loaded` 事件 | 携带 `{ notePath, container, meta }` |
| 2 | `app.js` `loadNote` 失败分支 | **不** dispatch 事件 | 避免误触发 |
| 3 | `index.html` `<head>` | 追加 `<link rel="stylesheet" href="css/comments.css">` | 在 `style.css` 之后 |
| 4 | `index.html` `<body>` 末尾 | 追加 `<script src="js/comments.js" defer>` | 在 `app.js` 之后 |
| 5 | `index.html` 工具栏 `.toolbar-actions` | （可选）追加"批注总览"按钮 | 触发全局视图模态框 |

**`comments.js` 内部监听**：

```js
document.addEventListener('note:loaded', (e) => {
  const { notePath, container, meta } = e.detail;
  CommentsAPI.attach(container, notePath);
  // attach 内部：渲染已存高亮、绑定选区监听、刷新汇总面板
});
```

**无需改动**：`scripts/build_site.py`、`src/agents/*`（除非实现 AI 消费侧）、`site/css/style.css`（评论样式独立文件）。

---

## 8. 性能与边界

### 8.1 大量评论时的渲染策略

- **高亮 wrap 延迟**：`attach` 时先 `buildNormalizedText` 一次（缓存到模块变量），所有 `resolveAnchor` 复用该缓存，避免重复 TreeWalker 遍历。
- **批量 wrap**：用 `DocumentFragment` 思路不行（mark 要插入到现有 DOM），但可批量读取、按 `rangeStart` 排序后**从后往前** wrap，避免前面的 wrap 影响后面文本节点的偏移。
- **虚拟线程列表**：单笔记评论 > 100 条时，`cm-thread-list` 用简易虚拟滚动（只渲染可视区 ± 10 条），`IntersectionObserver` 触发加载。
- **防抖**：`selectionchange` 用 200ms 防抖，避免拖拽选区时频繁触发。
- **避免重渲染**：评论增删只操作对应 DOM 节点，不重写 `.markdown-body` innerHTML。

### 8.2 localStorage 容量限制

- 单域名 localStorage 约 5–10 MB。单条评论约 0.5–2 KB，可存数千条。
- **配额监控**：`saveComments` 时 `try/catch`，捕获 `QuotaExceededError` 后提示用户导出并清理。
- **分片**：已按 notePath 分片，单篇过大时仍可独立导出删除。
- **压缩**：可选，对 `quote` 和 `content` 做 LZString 压缩（CDN 引入 `lz-string`）。一期不做。
- **备份提醒**：`cm:meta` 记录 `lastExportAt`，超过 7 天未导出时在面板顶部提示。

### 8.3 XSS 防护

- **评论内容**：渲染时强制 `textContent` 赋值，**绝不** `innerHTML`。所有用户输入（content、tags、author）走 `escapeHtml`（复用 `app.js` 同名函数，或在 `comments.js` 内重写一份）。
- **浮层 textarea**：原生控件，无 XSS 风险。
- **导出 JSON**：`JSON.stringify` 自动转义。
- **导入 JSON**：`JSON.parse` 后逐字段校验类型；`anchor.quote` 在 `resolveAnchor` 中只用于字符串比较，不注入 DOM。
- **高亮 mark 元素**：`document.createElement` 创建，`dataset.cmId` 赋值，不接触 HTML 字符串。
- **与 `sanitizeHtml` 协作**：`app.js` 的 `sanitizeHtml` 在 marked 输出后执行，会移除 `on*` 属性和 `<script>`。评论系统在 `sanitizeHtml` 之后介入，注入的 `mark` 元素自带 `data-*` 属性，不触发 `sanitizeHtml`（因为 sanitize 只跑一次）。但若未来 `app.js` 重新 `innerHTML`，`mark` 会被保留（`sanitizeHtml` 不删 `mark`），`data-cm-id` 也保留——需确保重新渲染后 `comments.js` 重新 `attach`（由 `note:loaded` 事件保证）。

### 8.4 其他边界

- **笔记删除/重命名**：`cm:index` 会残留条目。提供"清理无效索引"按钮，比对 `data/index.json` 的 `notes` 字段，删除不存在的 notePath 评论。
- **多标签页同步**：监听 `window.addEventListener('storage', ...)`，当其他标签页修改评论时刷新当前视图。
- **移动端**：选区交互在移动端体验差，`@media (max-width: 768px)` 下隐藏选区浮层，仅保留汇总面板查看与回复。
- **无痕模式**：localStorage 可能不可用，`attach` 时 `try/catch`，降级为"只读不存"模式并提示。

---

## 9. 落地顺序建议（给实现 agent）

1. **先做存储层**：`Storage` 对象 + `Comment`/`Anchor` 数据结构 + 单元自测（控制台手动调）。
2. **再做锚定**：`buildNormalizedText` + `captureAnchor` + `resolveAnchor`，用一个固定笔记手测选区→保存→刷新→高亮找回。
3. **再做高亮 wrap/unwrap**：`wrapRangeWithHighlight` + 点击展开线程。
4. **再做选区浮层**：`mouseup` 监听 + 浮层定位 + 提交流程。
5. **再做汇总面板**：列表渲染 + 排序 + 跳转。
6. **再做导出/导入**：`exportNote`/`exportAll`/`importJSON`。
7. **最后做专家团**：`exportForAgents` + `copyAsPromptContext` + Python 侧 `load_author_comments`。
8. **集成测试**：修改 `app.js` 加 `note:loaded` 事件，`index.html` 加资源引用，端到端验证。

每一步都可在浏览器控制台通过 `window.CommentsAPI.*` 独立验证，不依赖前序 UI。
