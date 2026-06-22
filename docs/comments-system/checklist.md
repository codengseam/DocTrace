# 静态网站原文批注式评论系统 · 评审 Checklist

> 版本：v1.0 · 日期：2026-06-22
> 配套文档：[spec.md](./spec.md)
> 用途：评审各实现版本是否达标。每条用 `- [ ]` 勾选；评审时逐项验证，未通过项需附说明。

---

## 一、功能完整性

### 1.1 圈选批注

- [ ] 在阅读区（`#reader .markdown-body`）用鼠标选中文本后，1 秒内弹出批注浮层
- [ ] 选区为空或跨段落异常时，不弹浮层（无幽灵浮层）
- [ ] 浮层含：多行评论输入框、5 类类型选择器、提交按钮、取消按钮
- [ ] 取消按钮关闭浮层且不清除当前选区（允许重新打开）
- [ ] 提交后选中文本被 `<mark>` 包裹并高亮，浮层自动关闭
- [ ] 同一段文本被多次圈选批注时，高亮可叠加或并列展示，不互相覆盖
- [ ] 支持触摸设备长按选中文本后弹浮层（移动端降级可用）

### 1.2 高亮与悬浮卡

- [ ] 已批注原文片段有下划线 + 浅色底纹，颜色随 `type` 区分
- [ ] 鼠标悬停高亮片段，弹出悬浮卡：内容、类型、作者、时间、回复数、状态
- [ ] 点击高亮片段，自动滚动并聚焦评论区对应条目
- [ ] 悬浮卡在鼠标移出后延迟关闭（避免抖动）

### 1.3 回复

- [ ] 评论区每条评论可展开回复输入框
- [ ] 支持多级回复（最多 2 级，第 3 级折叠为「查看更多回复」）
- [ ] 回复含 `id` / `content` / `author` / `createdAt`
- [ ] 回复提交后立即追加到 `replies[]` 并刷新计数

### 1.4 解决 / 重新打开

- [ ] 每条评论有「解决」按钮，点击后 `status` 变 `resolved`
- [ ] 已解决评论的高亮降饱和（底纹透明度降低）
- [ ] 已解决评论在评论区默认折叠，可切换「显示已解决」
- [ ] 已解决评论可「重新打开」恢复为 `open`

### 1.5 评论区汇总

- [ ] 阅读区下方有独立评论区，按原文出现顺序排列评论
- [ ] 顶部筛选：按类型（全部/错误/夸奖/讨论/补充/感想）、按状态（全部/open/resolved）、按关键词
- [ ] 筛选结果实时更新，无评论时显示空状态文案
- [ ] 评论条目展示：类型图标、锚定原文摘要、评论正文、作者、时间、回复列表、操作按钮

### 1.6 评论分类标签

- [ ] 创建评论时必选一个类型，未选时提交按钮禁用
- [ ] 5 类类型（error/praise/discussion/supplement/thought）图标与颜色正确
- [ ] 作者可在创建后修改类型，高亮颜色同步更新

### 1.7 导出

- [ ] 工具栏有「导出批注」按钮，下拉含「当前笔记」与「全站」两个选项
- [ ] 导出文件为 JSON，文件名 `comments_<notePath|all>_<YYYYMMDD>.json`
- [ ] 导出 JSON 顶层结构符合 spec 6.1（`schema` / `exportedAt` / `scope` / `comments`）
- [ ] 导出 JSON 可被 Python `json.load` 正常解析，无 BOM、无注释
- [ ] 空评论时导出仍生成合法 JSON（`comments: []`）

### 1.8 导入

- [ ] 提供「导入批注」入口，选择 JSON 文件后合并到 localStorage
- [ ] 按 `id` 去重；冲突时弹窗询问「覆盖 / 跳过 / 全部覆盖」
- [ ] 非法 JSON 或 schema 不符时，拒绝并提示具体错误
- [ ] 导入后高亮与评论区立即刷新

### 1.9 专家团触发入口

- [ ] 评论区顶部有「启用专家团评判」按钮，仅作者模式可见
- [ ] 当前笔记无评论时按钮禁用并提示「暂无批注可评判」
- [ ] 点击后弹出向导：范围（当前笔记/全站）、参与专家（多选）、附加指令（文本框）
- [ ] 确认后下载 `expert_review_request.json`，含 spec 7.2 所有字段
- [ ] 向导末尾显示本地执行命令提示（如 `python src/main.py --expert-review expert_review_request.json`）
- [ ] 提供「导入专家评判」入口，导入 `expert_review_result.json` 后回填到 `comment.expertReviews[]`
- [ ] 评判徽章（采纳/不采纳/待议）在评论区正确显示，点击展开 `rationale` 与 `suggestedEdit`
- [ ] 「应用建议」按钮可复制 `suggestedEdit.text` 到剪贴板，不自动改原文

### 1.10 批注管理

- [ ] 作者可编辑自己评论的内容与类型，`updatedAt` 同步更新
- [ ] 作者可删除评论（软删除 `deleted=true`，带二次确认）
- [ ] 每条评论可「复制锚定原文」到剪贴板
- [ ] 每条评论可「定位到原文」，滚动并高亮对应片段

---

## 二、锚定稳定性

### 2.1 锚定数据完整性

- [ ] `anchor` 对象含 `strategy` / `exact` / `prefix` / `suffix` / `paragraphIndex` / `headingPath` / `charOffsetStart` / `charOffsetEnd` / `version` 全部字段
- [ ] `exact` 为选中原文去首尾空白后的精确文本
- [ ] `prefix` / `suffix` 各取选中片段前后约 20 字，不含选中部分
- [ ] `headingPath` 为从顶层标题到当前段的标题路径数组
- [ ] `version` 取笔记 frontmatter `created_at` 或文件 hash 前 8 位

### 2.2 定位算法

- [ ] 加载笔记后，按 spec 4.3 三重定位算法执行：精确匹配 → 上下文消歧 → 结构兜底 → 孤儿标记
- [ ] `exact` 在文中唯一命中时，100% 正确高亮
- [ ] `exact` 多次命中时，用 `prefix`/`suffix` 选最匹配处
- [ ] `exact` 零命中时，用 `headingPath` + `paragraphIndex` 定位段落，段内模糊匹配
- [ ] 全部失败时标记 `orphaned`，不高亮，评论区以灰色「⚠ 原文已变更」标识

### 2.3 原文变更容错

- [ ] 原文个别字词修订（≤ 3 字）后，高亮仍能自动重定位
- [ ] 原文段落顺序调整后，`headingPath` 兜底能定位到正确段落
- [ ] 原文整段删除时，对应评论变孤儿，不崩溃，作者可手动重新锚定或删除
- [ ] 提供「重新锚定」入口：孤儿评论可手动选中新的原文片段重新绑定

### 2.4 版本检测

- [ ] 加载评论时比对 `anchor.version` 与当前笔记版本，不一致时在评论区提示「原文已更新，高亮可能偏移」
- [ ] 版本不一致时仍尝试定位，不直接判为孤儿

---

## 三、数据模型合规

### 3.1 字段齐全

- [ ] 每个 Comment 含 `id` / `notePath` / `anchor` / `content` / `type` / `author` / `createdAt` / `status` / `replies` / `expertReviews` / `deleted`
- [ ] `updatedAt` 在编辑后存在
- [ ] `replies[]` 每项含 `id` / `content` / `author` / `createdAt`
- [ ] `expertReviews[]` 每项含 `commentId` / `verdict` / `confidence` / `rationale` / `suggestedEdit` / `reviewedBy`

### 3.2 类型正确

- [ ] `id` / `notePath` / `content` / `author` 为 string
- [ ] `type` 取值限于 `error` / `praise` / `discussion` / `supplement` / `thought`
- [ ] `status` 取值限于 `open` / `resolved`
- [ ] `createdAt` / `updatedAt` 为 ISO 8601 字符串，带时区（如 `+08:00`）
- [ ] `deleted` 为 boolean
- [ ] `replies` / `expertReviews` 为数组（可为空）
- [ ] `anchor.charOffsetStart` / `charOffsetEnd` 为非负整数

### 3.3 可被 AI pipeline 消费

- [ ] 导出 JSON 顶层含 `schema: "deep-reading-comments/v1"`
- [ ] 导出 JSON 含 `projectContext`（`rulesFile` / `notesDir` / `agents`）
- [ ] `scope=note` 时每条 comment 附 `noteContent`（笔记全文）
- [ ] `scope=all` 时 `notePath` 省略，每条 comment 含 `notePath` 字段
- [ ] JSON 无循环引用、无 `undefined`、无 NaN
- [ ] 文件 UTF-8 无 BOM，`ensure_ascii=False`（中文不转义）

### 3.4 存储与去重

- [ ] localStorage key 命名 `drc:<notePath>` 存该笔记评论数组
- [ ] localStorage key `drc:meta` 存元信息（schema 版本、最后导出时间）
- [ ] `id` 全局唯一，格式 `c_<timestamp>_<seq>`
- [ ] 导入时按 `id` 去重，不产生重复条目

---

## 四、交互体验（飞书级手感）

### 4.1 浮层定位

- [ ] 浮层出现在选区右下方，不超出视口边界（自动翻转到左下方/上方）
- [ ] 浮层定位跟随选区，滚动时关闭
- [ ] 浮层有箭头指向选区
- [ ] 浮层宽度固定（如 320px），高度自适应内容，最大高度限制 + 内部滚动

### 4.2 键盘支持

- [ ] Tab 键可在浮层内按顺序聚焦：类型选择器 → 输入框 → 提交按钮 → 取消按钮
- [ ] Enter 提交评论，Shift+Enter 换行
- [ ] Esc 关闭浮层（不清除选区）
- [ ] 评论区条目可用上下方向键聚焦（可选）
- [ ] 高亮片段可 Tab 聚焦，Enter 打开悬浮卡

### 4.3 空状态与提示

- [ ] 评论区无评论时显示「暂无批注，圈选原文即可开始批注」+ 引导图标
- [ ] 笔记未加载时评论区隐藏或提示「请先选择一篇笔记」
- [ ] 导出成功提示「已导出 N 条批注」
- [ ] 导入成功提示「已导入 N 条，跳过 M 条冲突」
- [ ] 专家团评判导入成功提示「已回填 N 条评判」

### 4.4 loading 与错误

- [ ] 加载评论时评论区显示骨架屏或「加载中…」
- [ ] localStorage 读写异常时捕获，提示「本地存储不可用，批注无法保存」
- [ ] localStorage 配量预警：单笔记 > 200 条或总量 > 4MB 时提示导出清理
- [ ] 导入文件解析失败时提示具体错误（如「第 3 行 JSON 语法错误」）

### 4.5 反馈动效

- [ ] 浮层弹出/关闭有 150-200ms 过渡（opacity + transform）
- [ ] 高亮片段出现有淡入动效
- [ ] 评论区条目新增有滑入动效
- [ ] 解决/重新打开有状态切换动效
- [ ] 动效尊重 `prefers-reduced-motion`，开启时禁用非必要动画

---

## 五、视觉设计（与暖纸色古籍风格协调）

### 5.1 配色

- [ ] 复用 `style.css` 的 CSS 变量：`--bg-paper` / `--bg-sidebar` / `--accent` / `--accent-hover` / `--border` / `--ink-primary` / `--ink-secondary` / `--ink-muted`
- [ ] 5 类评论高亮色低饱和，底纹透明度 ≤ 0.18，不抢正文
- [ ] 高亮下划线 1px，颜色同类型色
- [ ] 浮层、悬浮卡用白底（`#fff`）+ `--shadow`，与现有 modal 一致
- [ ] 评论区背景用 `--bg-paper`，与阅读区一致

### 5.2 字体与排版

- [ ] 评论正文用 `--font-sans`（与正文宋体区分，便于扫读）
- [ ] 评论区标题、类型标签用 `--font-serif`
- [ ] 评论区条目间距 12-16px，行高 1.6
- [ ] 锚定原文摘要用 `--font-serif` + 斜体 + `--ink-secondary`
- [ ] 时间戳、作者名用 `--font-sans` + `--ink-muted` + 小字号（0.82rem）

### 5.3 间距与圆角

- [ ] 圆角统一用 `--radius`（6px）
- [ ] 浮层内边距 12-16px，与现有 modal-body 一致
- [ ] 评论区条目内边距 12-16px，条目间用 1px `--border` 分隔
- [ ] 按钮高度、内边距与现有 `.btn-primary` / `.btn-secondary` 一致

### 5.4 图标

- [ ] 5 类评论图标（❗👍💬➕✦）统一风格，可用 emoji 或 SVG
- [ ] 图标颜色与类型色一致
- [ ] 图标尺寸 14-16px，垂直对齐文字

### 5.5 整体协调

- [ ] 评论系统 UI 不引入新色系（除 5 类低饱和高亮色）
- [ ] 评论系统 UI 不引入新字体
- [ ] 浮层、悬浮卡、评论区视觉风格与现有 modal/sidebar/toolbar 协调，无突兀感
- [ ] 暗色模式不支持（与现有站点一致，不做）

---

## 六、代码质量

### 6.1 无框架依赖

- [ ] 仅用 vanilla JS，不引入 React/Vue/jQuery 等框架
- [ ] 仅依赖 `marked.js`（已有），不新增 CDN 依赖
- [ ] 无 `npm install` / `package.json` 新增依赖

### 6.2 模块化

- [ ] 评论系统为独立模块 `site/js/comments.js`，IIFE 封装
- [ ] 通过 `window.DeepReadingComments` 暴露最小 API：`init` / `loadForNote` / `clear`
- [ ] 不污染全局变量（仅 `DeepReadingComments` 一个命名空间）
- [ ] 内部状态用模块级私有变量，不暴露

### 6.3 不破坏现有 app.js

- [ ] `app.js` 现有函数签名与 `state` 结构不变
- [ ] `loadNote` 末尾仅追加一行 `if (window.DeepReadingComments) window.DeepReadingComments.loadForNote(path);`
- [ ] `index.html` 仅追加 `<script src="js/comments.js" defer>` 与评论区容器
- [ ] 现有搜索、目录树、modal 功能不受影响

### 6.4 安全（无 XSS）

- [ ] 评论 `content` 渲染强制 `escapeHtml`（复用 `app.js` 的 `escapeHtml` 或自实现等价函数）
- [ ] 不使用 `innerHTML` 拼接用户输入
- [ ] 评论区 DOM 用 `createElement` + `textContent` 构建
- [ ] 导入 JSON 时校验 schema 与字段类型，非法字段拒绝
- [ ] 高亮 `<mark>` 的 `class` 仅用白名单类型，不拼用户输入

### 6.5 健壮性

- [ ] 所有 `localStorage` 读写包裹 try-catch
- [ ] 所有 DOM 查询返回 null 时有兜底
- [ ] 选区 API（`window.getSelection`）异常时静默退出，不报错
- [ ] 评论数据迁移：检测 `drc:meta.schema` 版本，旧版自动升级

### 6.6 可维护性

- [ ] 代码有清晰分段注释（与 `app.js` 风格一致）
- [ ] 关键函数有 JSDoc 注释（参数、返回值）
- [ ] 无魔法数字，常量提取（如类型枚举、颜色映射）
- [ ] 无超过 80 行的函数，复杂逻辑拆分

---

## 七、可访问性

### 7.1 键盘

- [ ] 所有交互元素（浮层、悬浮卡、评论区按钮、高亮片段）可 Tab 聚焦
- [ ] 焦点可见（`:focus-visible` 有 outline，颜色用 `--accent`）
- [ ] 浮层打开时焦点陷阱（Tab 不跳出浮层，Esc 关闭）
- [ ] 评论区可用上下方向键浏览条目（可选）

### 7.2 ARIA

- [ ] 浮层 `role="dialog"` `aria-modal="true"` `aria-labelledby`
- [ ] 悬浮卡 `role="tooltip"` `aria-describedby`
- [ ] 高亮片段 `role="mark"` `aria-label="批注：{type}，{N} 条回复"`
- [ ] 评论区 `<section aria-label="批注列表">`
- [ ] 每条评论 `<article>`，含 `aria-label` 摘要
- [ ] 类型选择器用 `role="radiogroup"` + `role="radio"` `aria-checked`
- [ ] 解决/重新打开按钮 `aria-pressed` 反映状态
- [ ] 加载状态 `aria-busy="true"`

### 7.3 对比度

- [ ] 评论正文文字与背景对比度 ≥ 4.5:1（WCAG AA）
- [ ] 类型标签文字与底色对比度 ≥ 4.5:1
- [ ] 时间戳、作者名等辅助文字对比度 ≥ 3:1（WCAG AA 大字号/辅助）

---

## 八、兼容性

### 8.1 浏览器

- [ ] Chrome / Edge 最新两个大版本可用
- [ ] Firefox 最新两个大版本可用
- [ ] Safari 最新两个大版本可用（macOS + iOS）
- [ ] 不支持 IE（与现有站点一致）
- [ ] 不使用实验性 CSS/JS 特性（如需使用，有 fallback）

### 8.2 移动端

- [ ] 768px 以下布局自适应：浮层全宽、评论区全宽
- [ ] 触摸选区可触发浮层（`selectionchange` 监听）
- [ ] 触摸选区体验差时，提供「手动输入锚定文本」兜底入口
- [ ] 浮层在移动端不遮挡选区（定位到选区上方或底部）
- [ ] 评论区条目在移动端可折叠展开，避免过长

### 8.3 GitHub Pages 部署

- [ ] 所有资源用相对路径（`js/comments.js`、`css/comments.css`），不依赖根路径
- [ ] 无服务端依赖，纯静态可部署
- [ ] localStorage 在 GitHub Pages 域名下正常工作
- [ ] 导出/导入文件功能在 HTTPS 下正常工作

### 8.4 性能

- [ ] 单笔记 100 条评论，高亮渲染 < 100ms
- [ ] 选区弹浮层 < 200ms
- [ ] 评论区 50 条以上时考虑虚拟滚动（首版可全量，但需评估）
- [ ] 无内存泄漏：切换笔记时清理事件监听与 DOM 引用
- [ ] localStorage 读写不阻塞主线程（大数据量时分片处理）

---

## 九、文档与交付

- [ ] `docs/comments-system/spec.md` 存在且与实现一致
- [ ] `docs/comments-system/checklist.md` 存在且可执行
- [ ] `site/js/comments.js` 有文件头注释说明模块用途与 API
- [ ] `site/index.html` 变更可追溯到 spec 第八节
- [ ] `site/js/app.js` 变更仅限 `loadNote` 末尾一行调用
- [ ] 不引入未在 spec 中声明的文件或依赖

---

## 评审记录模板

| 维度 | 通过项数 / 总项数 | 结论 | 备注 |
|---|---|---|---|
| 一、功能完整性 | / 40+ | 通过/有条件通过/不通过 | |
| 二、锚定稳定性 | / 12 | | |
| 三、数据模型合规 | / 16 | | |
| 四、交互体验 | / 18 | | |
| 五、视觉设计 | / 18 | | |
| 六、代码质量 | / 18 | | |
| 七、可访问性 | / 11 | | |
| 八、兼容性 | / 14 | | |
| 九、文档与交付 | / 6 | | |

评审人：__________  评审日期：__________  实现版本：__________
