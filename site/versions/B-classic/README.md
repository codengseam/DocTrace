# 版本B · 古籍批注风评论系统

> 与暖纸宋体深度统一的原文批注系统——朱笔赭石、便笺笺纸、眉批夹注，让评论系统本身就是古籍阅读体验的一部分。

## 版本特点

### 视觉语言

- **朱砂赭石主色**：朱砂红 `#c0392b` + 赭石 `#a0522d`，呼应古人"朱墨双色"批注传统
- **朱笔波浪下划线**：高亮用 `text-decoration: underline wavy` 模拟朱批运笔
- **笺纸便笺浮层**：米黄底 `#fdf6e3`，毛笔感赭石边框，右上折角，楷体优先
- **右侧 margin notes 批注栏**：宽 260px，便笺按原文先后纵向排列，仿古籍夹注眉批
- **印章式类型标签**：22×22px 单字阴文（误/赞/议/补/感），朱底白字

### 5 种评论类型 · 传统色彩

| 类型 | 印章 | 色彩 | 色值 | 用途 |
|---|---|---|---|---|
| `error` 错误指正 | 误 | 朱砂 | `#c0392b` | 指出史实、引文、字词错误 |
| `praise` 写得好 | 赞 | 赭石 | `#a0522d` | 标记精彩段落 |
| `discussion` 讨论 | 议 | 青灰 | `#5a7a8a` | 提出疑问、展开思辨 |
| `supplement` 补充 | 补 | 墨色 | `#5a5651` | 补充史料、出处、背景 |
| `thought` 感想 | 感 | 黛紫 | `#7a5a8a` | 作者灵感、联想 |

### 动效设计

- **墨迹晕染淡入**：高亮出现时 `filter: blur(1.5px)→0` + `opacity 0→1`
- **便笺手贴**：浮层/卡片出现时 `translateY(-8px) rotate(-1deg)→0`，轻微倾斜
- **印章盖下**：解决时"阅"字朱印 `scale(1.4)→1` + `opacity 0→0.35`
- **跳转闪烁**：跳转原文时高亮 `cmt-flash` 动画
- 尊重 `prefers-reduced-motion`，开启时禁用非必要动画

## 预览方式

### 方法一：直接打开

由于纯静态站点使用相对路径，直接用浏览器打开 `index.html` 即可。但 `fetch` 加载 `data/index.json` 和 `notes/*.md` 时可能因 `file://` 协议被浏览器拦截，建议用本地服务器：

```bash
# 进入 B-classic 目录
cd site/versions/B-classic

# Python 内置服务器
python -m http.server 8080

# 或 Node.js
npx serve .
```

然后访问 `http://localhost:8080`。

### 方法二：复制到站点根目录

将 `B-classic/` 下的所有文件复制到 `site/` 根目录（覆盖现有文件），即可在现有站点目录结构下运行。

### 目录结构要求

本版本需要与现有站点的 `data/index.json` 和 `notes/` 目录配合使用。如果独立运行，需确保同级目录下有：

```
B-classic/
├── index.html
├── css/
│   ├── style.css
│   └── comments.css
├── js/
│   ├── app.js
│   └── comments.js
├── data/
│   └── index.json        ← 笔记索引（需从 site/data/ 复制）
└── notes/
    └── *.md              ← 笔记内容（需从 site/notes/ 复制）
```

## 功能清单

### 核心功能

- [x] **圈选批注**：鼠标选中文本 → 弹出笺纸浮层 → 输入评论 + 选类型 → 提交
- [x] **朱笔高亮**：`<mark>` 包裹选中文本，朱笔波浪下划线 + 淡底
- [x] **5 种类型**：错误/夸奖/讨论/补充/感想，各有传统色彩与印章标签
- [x] **右侧批注栏**：margin notes 风格，便笺按原文顺序排列
- [x] **回复**：便笺内缩进追加，仿"再批"（前缀 · ）
- [x] **编辑批注**：点"编辑"按钮可修改内容与类型，高亮颜色同步更新
- [x] **解决/重开**：点"圈结"盖"阅"字朱印，原文下划线变虚线
- [x] **跳转原文**：点击便笺"跳转"按钮，平滑滚动 + 闪烁高亮
- [x] **点击高亮**：点击文中朱批处，批注栏对应便笺高亮弹跳
- [x] **复制原文**：点"复制原文"按钮，复制锚定片段到剪贴板
- [x] **删除批注**：软删除（`deleted=true`），带二次确认

### 锚定算法（三级容错）

1. **精确偏移 + quote 校验**：`rangeStart/rangeEnd` 偏移 + `exact` 文本校验
2. **quote 全文匹配**：在规范化纯文本中查找 `exact` 首次出现
3. **前后缀指纹模糊匹配**：用 `prefix/suffix` 32 字符指纹 + ≤2 编辑距离容错

### 数据管理

- [x] **导出本篇**：`comments_<notePath>_<date>.json`
- [x] **导出全部**：`comments_all_<date>.json`
- [x] **导出给专家团**：AI 友好格式，按线程组织
- [x] **复制为 Prompt**：纯文本格式，便于直接喂给 LLM
- [x] **导入批注**：合并/替换模式，按 `id` 去重，冲突时弹窗询问覆盖/跳过
- [x] **导入专家评判**：回填 `expertReviews` 到对应评论
- [x] **配量预警**：单笔记 > 200 条或全站 > 4MB 时提示导出清理

### 专家团触发

- [x] **启用专家团**按钮：弹出向导（范围/参与专家/附加指令）
- [x] 生成 `expert_review_request.json`，含 `projectContext` 与 `expertReviewRequest`
- [x] 显示本地执行命令提示：`python src/main.py --expert-review expert_review_request.json`
- [x] 导入评判结果后显示徽章（采纳/不采纳/待议），可展开查看理由与建议

### 交互体验

- [x] **键盘可用**：浮层 Tab 切换、Ctrl+Enter 提交、Esc 关闭
- [x] **高亮可聚焦**：`tabindex=0`，Enter 打开
- [x] **悬浮卡**：鼠标悬停高亮显示评论摘要
- [x] **排序**：按位置/按时间/按状态
- [x] **显示已解决**开关
- [x] **空状态**：无批注时显示引导文案
- [x] **Toast 提示**：操作反馈

### 安全与健壮性

- [x] **XSS 防护**：所有用户输入用 `textContent` 渲染，`escapeHtml` 转义
- [x] **localStorage 容错**：检测可用性，配额满时提示导出
- [x] **孤儿批注降级**：锚定失败时标记"⚠ 原文已变更"，仍显示在批注栏
- [x] **多标签页同步**：监听 `storage` 事件自动刷新
- [x] **禁批注区域**：标题/代码块选区拦截

### 响应式

- **桌面端（>1024px）**：右侧 260px 批注栏，正文 `margin-right: 280px`
- **平板端（≤1024px）**：批注栏变底部，最大高度 45vh
- **移动端（≤768px）**：批注栏最大高度 35vh，浮层全宽

## 技术架构

### 文件清单

| 文件 | 职责 |
|---|---|
| `index.html` | 入口，引入资源，含批注栏容器与工具栏按钮 |
| `css/style.css` | 现有站点样式（直接复制） |
| `css/comments.css` | 古籍批注风评论系统样式 |
| `js/app.js` | 现有前端逻辑 + `note:loaded` 事件分发 |
| `js/comments.js` | 评论系统核心模块（IIFE） |

### 模块解耦

```
app.js (IIFE)  ──note:loaded 事件──▶  comments.js (IIFE)
                                        │
                                        ▼
                              window.DeepReadingComments API
```

- `app.js` 仅在 `loadNote` 成功后 dispatch `note:loaded`，携带 `{ notePath, container, meta }`
- `comments.js` 监听该事件，自动 `attach(container, notePath)`
- 两模块通过自定义事件解耦，互不引用内部变量

### 数据模型

评论对象遵循 `deep-reading-comments/v1` schema，含 `id`/`notePath`/`anchor`/`content`/`type`/`author`/`createdAt`/`updatedAt`/`status`/`replies`/`expertReviews`/`deleted` 字段。

锚点对象含 `strategy`/`exact`/`prefix`/`suffix`/`rangeStart`/`rangeEnd`/`paragraphIndex`/`headingPath`/`version`/`schemaVersion` 字段，支持三级容错定位。

### localStorage 键设计

| Key | 值 |
|---|---|
| `drc:<notePath>` | 该笔记的评论数组 |
| `drc:meta` | 元信息（schema 版本、最后导出时间） |

## API 参考

```js
// 状态查询
window.DeepReadingComments.getComments(notePath)
window.DeepReadingComments.getAllComments()

// 显式控制
window.DeepReadingComments.attach(container, notePath)
window.DeepReadingComments.detach()
window.DeepReadingComments.refresh()

// 数据操作
window.DeepReadingComments.exportNote(notePath)
window.DeepReadingComments.exportAll()
window.DeepReadingComments.exportForAgents(notePath)
window.DeepReadingComments.copyAsPromptContext(notePath)
window.DeepReadingComments.importJSON(jsonStr, mode)  // mode: 'merge' | 'replace'
window.DeepReadingComments.importExpertReview(jsonStr)
window.DeepReadingComments.clearNote(notePath)

// 专家团
window.DeepReadingComments.generateExpertReviewRequest(scope, participants, instruction)
window.DeepReadingComments.openExpertDialog()

// 兼容 spec 8.6
window.DeepReadingComments.init(readerEl)
window.DeepReadingComments.loadForNote(notePath)
window.DeepReadingComments.clear()
```

## 与现有站点的集成

### app.js 改动（仅一处）

在 `loadNote` 函数成功分支末尾，`elements.reader.innerHTML = ...` 之后：

```js
const article = elements.reader.querySelector('.markdown-body');
if (article) {
    document.dispatchEvent(new CustomEvent('note:loaded', {
        detail: { notePath: path, container: article, meta: meta || null }
    }));
}
```

### index.html 改动

- `<head>` 追加 `<link rel="stylesheet" href="css/comments.css">`
- `<body>` 末尾追加 `<script src="js/comments.js" defer></script>`
- 工具栏追加"导出评论""启用专家团"按钮
- 追加批注栏 `<aside class="cmt-panel">` 容器
