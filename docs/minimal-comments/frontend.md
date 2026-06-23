# 极简评论系统前端实现方案

为纯静态古籍阅读站点设计的段落级批注系统。核心目标：手机端优先、只看/只写、B 古籍批注风、解决软键盘弹出后抽屉"落不下去"的问题。

---

## 1. 模块结构

新增两个静态资源，并对 `app.js`、`index.html` 做最小补丁。

```
site/
├── index.html                    + 引入 css/js
├── js/
│   ├── app.js                    + 渲染完笔记后调用 MinimalComments.init()
│   └── minimal-comments.js       新增：IIFE，暴露 window.MinimalComments
└── css/
    ├── style.css                 现有：提供主题变量
    └── minimal-comments.css      新增：评论系统全部样式
```

### 1.1 `site/js/minimal-comments.js`

采用 IIFE，不依赖任何框架，兼容 marked.js v12。

```js
(function (global) {
    'use strict';

    const NS = 'mc';
    const SELECTOR = {
        reader: '#reader',
        article: '#reader .markdown-body',
        paragraphs: '#reader .markdown-body > p'
    };

    const state = {
        articleId: null,      // 当前笔记路径或 id
        comments: {},         // { pid: [comment, ...] }
        activePid: null,      // 当前打开的段落 id
        open: false,          // 抽屉是否打开
        panelHeight: 0.5,     // 抽屉高度占比（0.2~0.8）
        isDragging: false,
        dragStartY: 0,
        dragStartHeight: 0,
        maxChars: 200,
        commentsLimit: 50
    };

    const els = {};

    // ---------- 初始化 ----------
    function init(options) {
        state.articleId = options.articleId || location.pathname;
        ensureCssVariables();
        loadComments(state.articleId).then(() => {
            markParagraphs();
            observeBadges();
            bindGlobalEvents();
        });
    }

    // ---------- 段落标记 ----------
    function markParagraphs() {
        const article = document.querySelector(SELECTOR.article);
        if (!article) return;
        const paragraphs = article.querySelectorAll(':scope > p');
        paragraphs.forEach((p, index) => {
            const pid = `p${String(index + 1).padStart(4, '0')}`;
            p.setAttribute('data-pid', pid);
            if (!p.querySelector('.mc-badge')) {
                const badge = createBadge(pid);
                p.appendChild(badge);
            }
        });
    }

    function createBadge(pid) {
        const count = (state.comments[pid] || []).length;
        const badge = document.createElement('button');
        badge.type = 'button';
        badge.className = 'mc-badge' + (count > 0 ? ' has-comments' : '');
        badge.setAttribute('aria-label', count > 0 ? `${count} 条批注` : '添加批注');
        badge.setAttribute('data-pid', pid);
        badge.innerHTML = `<span class="mc-badge-count">${count || ''}</span>` +
                          `<span class="mc-badge-hint">评</span>`;
        badge.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            openDrawer(pid);
        });
        return badge;
    }

    // ---------- 评论数据 ----------
    async function loadComments(articleId) {
        const safeId = encodeURIComponent(articleId.replace(/[^a-zA-Z0-9\u4e00-\u9fa5_\-/]/g, '_'));
        try {
            const res = await fetch(`data/comments/${safeId}.json`);
            if (!res.ok) throw new Error(res.statusText);
            const data = await res.json();
            state.comments = normalizeComments(data.comments || []);
        } catch (err) {
            state.comments = {};
        }
    }

    function normalizeComments(list) {
        const map = {};
        list.forEach((c) => {
            const pid = c.pid || 'p0001';
            if (!map[pid]) map[pid] = [];
            map[pid].push(c);
        });
        Object.keys(map).forEach((pid) => {
            map[pid].sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
            map[pid] = map[pid].slice(0, state.commentsLimit);
        });
        return map;
    }

    // ---------- 抽屉 ----------
    function openDrawer(pid) {
        if (state.open && state.activePid === pid) return;
        state.activePid = pid;
        state.open = true;
        ensureDrawer();
        renderDrawer();
        showDrawer();
        trapFocus();
    }

    function closeDrawer() {
        state.open = false;
        state.activePid = null;
        hideDrawer();
        releaseFocus();
    }

    // ---------- 渲染 ----------
    function renderDrawer() {
        const pid = state.activePid;
        const paragraph = document.querySelector(`p[data-pid="${CSS.escape(pid)}"]`);
        const quote = paragraph ? paragraph.textContent.trim().slice(0, 80) : '';
        const list = state.comments[pid] || [];

        els.drawerBody.innerHTML = `
            <div class="mc-quote">
                <span class="mc-quote-mark">「</span>
                <p>${escapeHtml(quote)}${quote.length >= 80 ? '…' : ''}</p>
            </div>
            <div class="mc-list" role="list" aria-label="批注列表">
                ${list.length ? list.map(renderComment).join('') : renderEmpty()}
            </div>
        `;

        requestAnimationFrame(() => {
            const items = els.drawerBody.querySelectorAll('.mc-comment');
            items.forEach((item, i) => {
                item.style.animationDelay = `${i * 60}ms`;
            });
        });
    }

    function renderComment(c) {
        const stamp = COMMENT_TYPES.find((t) => t.key === c.type) || COMMENT_TYPES[1];
        return `
            <article class="mc-comment" role="listitem">
                <div class="mc-comment-stamp ${stamp.class}">${stamp.label}</div>
                <p class="mc-comment-text">${escapeHtml(c.text)}</p>
                <footer class="mc-comment-meta">
                    <span class="mc-comment-author">${escapeHtml(c.author || '佚名')}</span>
                    <time datetime="${c.createdAt || ''}">${formatDate(c.createdAt)}</time>
                </footer>
            </article>
        `;
    }

    function renderEmpty() {
        return `
            <div class="mc-empty" role="status">
                <span class="mc-empty-ink">暂无批注</span>
                <p>来做第一位读者</p>
            </div>
        `;
    }

    // ---------- 输入框 ----------
    function submitComment() {
        const text = els.textarea.value.trim();
        if (!text) return;
        const type = els.typeSelect.value || 'discuss';

        // 本地立即显示（后续接入后端时替换为提交后重新加载）
        const comment = {
            pid: state.activePid,
            type,
            text: text.slice(0, state.maxChars),
            author: '我',
            createdAt: Date.now(),
            pending: true
        };
        if (!state.comments[state.activePid]) state.comments[state.activePid] = [];
        state.comments[state.activePid].push(comment);
        updateBadge(state.activePid);
        renderDrawer();

        els.textarea.value = '';
        autoResize();
        els.textarea.blur();

        // 提示待审核
        showToast('批注已提交，审核后显示');
    }

    // ---------- 软键盘适配 ----------
    function listenVisualViewport() {
        if (!global.visualViewport) return;

        const onResize = () => {
            if (!state.open) return;
            const vv = global.visualViewport;
            const drawerBottom = els.drawer.getBoundingClientRect().bottom;
            const inputRect = els.inputWrap.getBoundingClientRect();

            if (inputRect.bottom > vv.height) {
                const offset = inputRect.bottom - vv.height + 16;
                els.drawer.style.transform = `translateY(-${offset}px)`;
            } else {
                els.drawer.style.transform = '';
            }
        };

        global.visualViewport.addEventListener('resize', onResize);
        global.visualViewport.addEventListener('scroll', onResize);
    }

    // ---------- 拖拽 ----------
    function onDragStart(y) {
        state.isDragging = true;
        state.dragStartY = y;
        state.dragStartHeight = els.drawer.offsetHeight;
        els.drawer.style.transition = 'none';
    }

    function onDragMove(y) {
        if (!state.isDragging) return;
        const delta = state.dragStartY - y;
        const h = Math.max(120, Math.min(window.innerHeight * 0.8, state.dragStartHeight + delta));
        els.drawer.style.height = `${h}px`;
    }

    function onDragEnd() {
        if (!state.isDragging) return;
        state.isDragging = false;
        els.drawer.style.transition = '';
        const ratio = els.drawer.offsetHeight / window.innerHeight;
        if (ratio < 0.25) {
            closeDrawer();
        } else {
            state.panelHeight = Math.min(0.8, Math.max(0.3, ratio));
            els.drawer.style.height = `${state.panelHeight * 100}vh`;
        }
    }

    // ---------- 工具函数 ----------
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }

    function formatDate(ts) {
        if (!ts) return '';
        const d = new Date(ts);
        return `${d.getMonth() + 1}月${d.getDate()}日`;
    }

    function ensureCssVariables() { /* 如需要，可在根节点补兜底变量 */ }

    function ensureDrawer() { /* 一次性创建抽屉 DOM */ }

    function showDrawer() { /* 加入 DOM 并打开 */ }

    function hideDrawer() { /* 关闭动画后移除/隐藏 */ }

    function trapFocus() { /* 焦点困在抽屉内 */ }

    function releaseFocus() { /* 焦点回到触发徽章 */ }

    function bindGlobalEvents() { /* ESC、返回键、路由切换 */ }

    function observeBadges() { /* IntersectionObserver 懒加载徽章 */ }

    function updateBadge(pid) { /* 更新段落右侧徽章数字 */ }

    function showToast(msg) { /* 简短提示 */ }

    function autoResize() { /* textarea 自动增高 */ }

    // ---------- 暴露 API ----------
    global.MinimalComments = {
        init,
        open: openDrawer,
        close: closeDrawer,
        refresh: markParagraphs
    };
})(window);
```

关键公开 API：

| 方法 | 签名 | 说明 |
|---|---|---|
| `init` | `init({ articleId: string })` | 加载评论 JSON、给段落打标、初始化抽屉 |
| `open` | `open(pid: string)` | 打开指定段落批注抽屉 |
| `close` | `close()` | 关闭抽屉 |
| `refresh` | `refresh()` | 重新给当前文章段落打标 |

### 1.2 `site/css/minimal-comments.css`

全部样式使用 CSS 变量，自动继承 `style.css` 的日夜主题。

### 1.3 `site/js/app.js` 最小补丁

在 `loadNote` 渲染完正文后调用 `MinimalComments.init`。

```js
// app.js 中，在 elements.reader.innerHTML = `<article class="markdown-body">...` 之后追加：
if (window.MinimalComments) {
    window.MinimalComments.init({ articleId: path });
}
```

如果文章切换时不重新加载页面，可在 `loadNote` 开头先调用一次 `MinimalComments.close()` 避免抽屉残留。

### 1.4 `site/index.html` 最小改动

```html
<head>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/minimal-comments.css">
    <script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js" defer></script>
    <script src="js/minimal-comments.js" defer></script>
    <script src="js/app.js" defer></script>
</head>
```

---

## 2. 段落标记方案

### 2.1 给 `<p>` 加 `data-pid`

marked.js 渲染后，正文段落直接作为 `.markdown-body > p`。方案不侵入 marked 渲染器，而是在 `loadNote` 完成后统一遍历打标：

```js
const paragraphs = article.querySelectorAll(':scope > p');
paragraphs.forEach((p, index) => {
    const pid = `p${String(index + 1).padStart(4, '0')}`;
    p.setAttribute('data-pid', pid);
});
```

规则：
- 仅给直接子级 `<p>` 打标，跳过引用块、列表、标题等。
- pid 从 `p0001` 开始，按 DOM 顺序递增。
- 同一篇文章路径不变时，pid 稳定；文章重新构建后若段落顺序变化，pid 重新对齐。

### 2.2 段落右侧徽章 `.mc-badge`

徽章作为段落的最后一个子元素插入，采用绝对定位固定在段落右侧。

```html
<p data-pid="p0003">
    建安五年，曹操与袁绍相持于官渡……
    <button type="button" class="mc-badge has-comments" data-pid="p0003" aria-label="3 条批注">
        <span class="mc-badge-count">3</span>
        <span class="mc-badge-hint">评</span>
    </button>
</p>
```

CSS 结构要点：

```css
.markdown-body p {
    position: relative;
    padding-right: 2.2em; /* 给徽章留空 */
}

.mc-badge {
    position: absolute;
    right: 0;
    top: 0.1em;
    width: 1.6em;
    height: 1.6em;
    border: 1px solid var(--mc-vermilion);
    border-radius: 50%;
    background: transparent;
    color: var(--mc-vermilion);
    font-family: var(--mc-font-kai);
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    transition: transform 0.2s ease, background 0.2s ease;
}

.mc-badge.has-comments {
    background: var(--mc-vermilion);
    color: #fff;
}

.mc-badge .mc-badge-hint {
    display: none;
}

.mc-badge:not(.has-comments) .mc-badge-count {
    display: none;
}

.mc-badge:not(.has-comments) .mc-badge-hint {
    display: inline;
}

/* hover 时无评论也显示"评" */
.mc-badge:hover {
    transform: scale(1.1);
    box-shadow: 0 0 0 4px var(--mc-vermilion-10);
}

/* 有评论时脉冲 */
.mc-badge.has-comments {
    animation: mc-pulse 2s ease-in-out infinite;
}
```

视觉要求：
- 有评论时显示数字，底色朱砂，文字白色。
- 无评论时 hover 显示"评"字，平时可完全透明或只留细边框。
- 桌面端徽章常驻；手机端徽章默认半透明，点击段落任意位置也可打开抽屉。

---

## 3. 底部抽屉组件

### 3.1 DOM 结构

```html
<div id="mc-overlay" class="mc-overlay" aria-hidden="true"></div>

<div id="mc-drawer" class="mc-drawer" role="dialog" aria-modal="true" aria-labelledby="mc-drawer-title" tabindex="-1">
    <div class="mc-drawer-handle" role="button" tabindex="0" aria-label="拖动调整高度">
        <span class="mc-handle-bar"></span>
    </div>

    <div class="mc-drawer-header">
        <h2 id="mc-drawer-title" class="mc-drawer-title">段落批注</h2>
        <button type="button" class="mc-close" aria-label="关闭批注">×</button>
    </div>

    <div class="mc-drawer-body">
        <!-- 动态插入：引用、评论列表 -->
    </div>

    <div class="mc-input-wrap">
        <select class="mc-type-select" aria-label="批注类型">
            <option value="discuss">讨论</option>
            <option value="erratum">勘误</option>
            <option value="note">感想</option>
        </select>
        <div class="mc-input-row">
            <textarea
                class="mc-textarea"
                rows="1"
                maxlength="200"
                placeholder="写下你的批注…"
                aria-label="批注内容，最多 200 字"
            ></textarea>
            <button type="button" class="mc-submit" aria-label="提交批注">发送</button>
        </div>
        <div class="mc-input-count">0 / 200</div>
    </div>
</div>
```

### 3.2 尺寸与位置

```css
.mc-drawer {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1100;
    height: 50vh;
    max-height: 80vh;
    min-height: 120px;
    background: var(--mc-paper-note);
    border-radius: 18px 18px 0 0;
    box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.12);
    display: flex;
    flex-direction: column;
    transform: translateY(100%);
    transition: transform 200ms ease-out, height 200ms ease-out;
}

.mc-drawer.open {
    transform: translateY(0);
}

.mc-overlay {
    position: fixed;
    inset: 0;
    z-index: 1050;
    background: rgba(0, 0, 0, 0.35);
    opacity: 0;
    pointer-events: none;
    transition: opacity 200ms ease-out;
}

.mc-overlay.open {
    opacity: 1;
    pointer-events: auto;
}
```

行为：
- 默认高度 `50vh`，最大 `80vh`，最小 `120px`。
- 打开时抽屉从底部滑入，遮罩同步淡入。
- 关闭方式：点击遮罩、点击关闭按钮、下滑拖拽到底、按 `Esc`、按手机返回键。

### 3.3 顶部拖拽条

```css
.mc-drawer-handle {
    width: 100%;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: grab;
    flex-shrink: 0;
}

.mc-handle-bar {
    width: 40px;
    height: 4px;
    border-radius: 2px;
    background: var(--mc-ochre);
}
```

拖拽逻辑（兼容鼠标与触摸）：

```js
function bindDrag(handle) {
    const start = (y) => onDragStart(y);
    const move = (y) => onDragMove(y);
    const end = () => onDragEnd();

    handle.addEventListener('mousedown', (e) => start(e.clientY));
    handle.addEventListener('touchstart', (e) => start(e.touches[0].clientY), { passive: true });

    window.addEventListener('mousemove', (e) => move(e.clientY));
    window.addEventListener('touchmove', (e) => move(e.touches[0].clientY), { passive: true });

    window.addEventListener('mouseup', end);
    window.addEventListener('touchend', end);
}
```

拖拽结束判定：
- 当前高度 < `25vh` → 关闭抽屉。
- 否则吸附到最近的 `10vh` 刻度，但不超 `80vh`。

---

## 4. 输入框设计

### 4.1 结构与定位

输入区固定在抽屉底部，不随内容滚动。

```css
.mc-input-wrap {
    position: sticky;
    bottom: 0;
    flex-shrink: 0;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
    background: var(--mc-paper-note);
    border-top: 1px solid var(--mc-border);
}

.mc-input-row {
    display: flex;
    align-items: flex-end;
    gap: 8px;
}

.mc-textarea {
    flex: 1;
    min-height: 40px;
    max-height: calc(1.5em * 3 + 22px); /* 3 行 */
    padding: 10px 12px;
    border: 1px solid var(--mc-border);
    border-radius: 10px;
    background: var(--bg-paper);
    color: var(--ink-primary);
    font-family: var(--font-sans);
    font-size: 16px; /* 防止 iOS 缩放 */
    line-height: 1.5;
    resize: none;
    overflow-y: auto;
}

.mc-submit {
    height: 40px;
    padding: 0 16px;
    border: none;
    border-radius: 10px;
    background: var(--mc-vermilion);
    color: #fff;
    font-size: 15px;
    cursor: pointer;
}
```

### 4.2 单行 textarea、自动增高到 3 行

```js
function autoResize() {
    const ta = els.textarea;
    ta.style.height = 'auto';
    const maxH = parseFloat(getComputedStyle(ta).maxHeight);
    ta.style.height = Math.min(ta.scrollHeight, maxH) + 'px';
}

els.textarea.addEventListener('input', () => {
    autoResize();
    updateCharCount();
});
```

限制：
- `maxlength="200"`。
- 最多显示 3 行，超出的行滚动。
- 字数计数实时显示在输入框下方：`0 / 200`。

### 4.3 软键盘适配（核心）

问题：手机键盘弹起时，fixed 定位的抽屉可能被键盘顶起或遮挡；键盘收起后若用 `window.innerHeight` 计算，抽屉可能卡在屏幕中间。

解决：使用 `visualViewport` API 监听可视区域变化。

```js
function listenVisualViewport() {
    if (!window.visualViewport) return;

    const adjust = () => {
        if (!state.open) return;
        const vv = window.visualViewport;
        const drawerBottom = els.drawer.getBoundingClientRect().bottom;
        const inputBottom = els.inputWrap.getBoundingClientRect().bottom;

        if (inputBottom > vv.height) {
            const offset = inputBottom - vv.height + 16;
            els.drawer.style.transform = `translateY(-${offset}px)`;
        } else if (drawerBottom > vv.height) {
            const offset = drawerBottom - vv.height;
            els.drawer.style.transform = `translateY(-${offset}px)`;
        } else {
            els.drawer.style.transform = '';
        }
    };

    window.visualViewport.addEventListener('resize', adjust);
    window.visualViewport.addEventListener('scroll', adjust);
}
```

补充策略：
- 输入框 `font-size: 16px`，避免 iOS 聚焦时自动缩放页面。
- 使用 `env(safe-area-inset-bottom)` 兼容刘海屏底部。
- 提交后主动 `textarea.blur()` 收起键盘。

### 4.4 提交流程

```js
function submitComment() {
    const text = els.textarea.value.trim();
    if (!text) return;

    const comment = {
        pid: state.activePid,
        type: els.typeSelect.value,
        text: text.slice(0, 200),
        author: '我',
        createdAt: Date.now(),
        pending: true
    };

    // 本地缓存，更新徽章
    if (!state.comments[state.activePid]) state.comments[state.activePid] = [];
    state.comments[state.activePid].push(comment);
    updateBadge(state.activePid);
    renderDrawer();

    // 清空输入、收起键盘
    els.textarea.value = '';
    autoResize();
    updateCharCount();
    els.textarea.blur();

    showToast('批注已提交，审核后显示');
}
```

提交后抽屉保持打开，列表滚动到最底部显示最新提交的占位项（带 `pending` 样式）。

---

## 5. 评论列表

### 5.1 单条评论结构

```html
<article class="mc-comment" role="listitem">
    <div class="mc-comment-stamp mc-stamp-discuss">讨论</div>
    <p class="mc-comment-text">此处"挟天子以令诸侯"应作"奉天子以令不臣"，裴注有辨。</p>
    <footer class="mc-comment-meta">
        <span class="mc-comment-author">陈寅恪</span>
        <time datetime="2026-06-20">6月20日</time>
    </footer>
</article>
```

### 5.2 空状态

```html
<div class="mc-empty" role="status">
    <span class="mc-empty-ink">暂无批注</span>
    <p>来做第一位读者</p>
</div>
```

### 5.3 数据项

单条评论 JSON：

```json
{
    "pid": "p0003",
    "type": "erratum",
    "text": "此处年代似有出入。",
    "author": "读者甲",
    "createdAt": 1750329600000
}
```

前端最多展示 50 条，超出按时间截断。

---

## 6. 评论类型

只保留三种，用印章式小图标呈现。

```js
const COMMENT_TYPES = [
    { key: 'erratum', label: '勘误', class: 'mc-stamp-erratum', color: 'var(--mc-vermilion)' },
    { key: 'discuss', label: '讨论', class: 'mc-stamp-discuss', color: 'var(--mc-cyan)' },
    { key: 'note',    label: '感想', class: 'mc-stamp-note',    color: 'var(--mc-ink)' }
];
```

```css
.mc-comment-stamp {
    display: inline-block;
    padding: 2px 8px;
    border: 1px solid currentColor;
    border-radius: 4px;
    font-family: var(--mc-font-kai);
    font-size: 12px;
    font-weight: 600;
    line-height: 1.4;
}

.mc-stamp-erratum { color: var(--mc-vermilion); background: rgba(199, 56, 35, 0.08); }
.mc-stamp-discuss { color: var(--mc-cyan);      background: rgba(42, 128, 132, 0.08); }
.mc-stamp-note    { color: var(--mc-ink);       background: rgba(44, 44, 44, 0.06); }
```

视觉要求：
- 印章风格：圆角小边框，无阴影，不抢眼。
- 类型色与徽章、按钮的朱砂主色形成统一语义。

---

## 7. 视觉 token（CSS 变量）

在 `minimal-comments.css` 中声明，同时与 `style.css` 已有变量对齐。

```css
:root {
    /* 古籍批注主色 */
    --mc-vermilion: #c73823;
    --mc-vermilion-10: rgba(199, 56, 35, 0.10);
    --mc-ochre: #a67c52;
    --mc-cyan: #2a8084;
    --mc-ink: #2c2c2c;

    /* 便笺底色 */
    --mc-paper-note: #fffbf2;
    --mc-paper-note-dark: #2d2a24;

    /* 边框与分隔 */
    --mc-border: rgba(139, 90, 43, 0.18);
    --mc-divider: rgba(139, 90, 43, 0.10);

    /* 字体 */
    --mc-font-kai: "Kaiti SC", "STKaiti", "KaiTi", serif;
    --mc-font-song: "Songti SC", "Source Han Serif SC", "Noto Serif SC", serif;
}

/* 与现有主题融合：夜间/护眼模式覆盖 */
body[data-theme="night"] {
    --mc-paper-note: var(--mc-paper-note-dark);
    --mc-vermilion: #e06652;
    --mc-ochre: #c8a06a;
    --mc-cyan: #5bbec2;
    --mc-ink: #c8c8c8;
    --mc-border: rgba(200, 160, 106, 0.22);
}

body[data-theme="sepia"] {
    --mc-paper-note: #faf0d8;
    --mc-border: rgba(139, 90, 43, 0.22);
}
```

对齐策略：
- 背景色优先使用 `--mc-paper-note`，使抽屉看起来像一张浮起的便笺。
- 文字色使用 `style.css` 已有的 `--ink-primary`，保证主题切换一致。
- 按钮、徽章统一使用 `--mc-vermilion`。

---

## 8. 动效

### 8.1 抽屉滑入

```css
.mc-drawer {
    transform: translateY(100%);
    transition: transform 200ms ease-out, height 200ms ease-out;
}

.mc-drawer.open {
    transform: translateY(0);
}

.mc-overlay {
    opacity: 0;
    transition: opacity 200ms ease-out;
}

.mc-overlay.open {
    opacity: 1;
}
```

### 8.2 评论淡入 stagger

```css
.mc-comment {
    opacity: 0;
    transform: translateY(8px);
    animation: mc-fade-in 240ms ease-out forwards;
}

@keyframes mc-fade-in {
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

JS 动态设置 `animation-delay`：

```js
items.forEach((item, i) => {
    item.style.animationDelay = `${i * 60}ms`;
});
```

### 8.3 徽章脉冲

```css
@keyframes mc-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(199, 56, 35, 0.25); }
    50% { box-shadow: 0 0 0 6px rgba(199, 56, 35, 0); }
}

.mc-badge.has-comments {
    animation: mc-pulse 2s ease-in-out infinite;
}
```

### 8.4 减少动画偏好

```css
@media (prefers-reduced-motion: reduce) {
    .mc-drawer,
    .mc-overlay,
    .mc-badge,
    .mc-comment {
        transition: none !important;
        animation: none !important;
    }
}
```

---

## 9. 性能

### 9.1 评论 JSON 按需加载

按当前文章路径请求 `data/comments/{articleId}.json`，失败则视为无评论。

```js
const safeId = encodeURIComponent(articleId.replace(/[^a-zA-Z0-9\u4e00-\u9fa5_\-/]/g, '_'));
fetch(`data/comments/${safeId}.json`)
```

### 9.2 段落徽章懒加载

使用 `IntersectionObserver` 只在段落进入视口时才渲染/更新徽章数字，避免长文一次性操作大量 DOM。

```js
function observeBadges() {
    if (!('IntersectionObserver' in window)) {
        document.querySelectorAll('[data-pid]').forEach(updateBadge);
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                updateBadge(entry.target.dataset.pid);
                observer.unobserve(entry.target);
            }
        });
    }, { rootMargin: '100px' });

    document.querySelectorAll('[data-pid]').forEach((p) => observer.observe(p));
}
```

### 9.3 无虚拟列表

评论数量上限 50 条，直接 DOM 渲染，不引入虚拟列表。

---

## 10. 可访问性

### 10.1 ARIA

- 抽屉：`role="dialog"`、`aria-modal="true"`、`aria-labelledby="mc-drawer-title"`。
- 遮罩：`aria-hidden="true"`（关闭时）。
- 徽章：有评论时 `aria-label="{n} 条批注"`，无评论时 `aria-label="添加批注"`。
- 评论列表：`role="list"`，单条 `role="listitem"`。
- 空状态：`role="status"`。

### 10.2 键盘关闭

```js
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.open) {
        e.preventDefault();
        closeDrawer();
    }
});
```

### 10.3 焦点陷阱（Focus Trap）

抽屉打开后，Tab 键只在抽屉内循环；关闭后焦点回到触发徽章。

```js
function trapFocus() {
    const focusable = els.drawer.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable.length) return;

    state.focusables = Array.from(focusable);
    state.firstFocusable = state.focusables[0];
    state.lastFocusable = state.focusables[state.focusables.length - 1];
    state.previouslyFocused = document.activeElement;

    state.firstFocusable.focus();

    state.focusTrapHandler = (e) => {
        if (e.key !== 'Tab') return;
        if (e.shiftKey && document.activeElement === state.firstFocusable) {
            e.preventDefault();
            state.lastFocusable.focus();
        } else if (!e.shiftKey && document.activeElement === state.lastFocusable) {
            e.preventDefault();
            state.firstFocusable.focus();
        }
    };

    document.addEventListener('keydown', state.focusTrapHandler);
}

function releaseFocus() {
    if (state.focusTrapHandler) {
        document.removeEventListener('keydown', state.focusTrapHandler);
    }
    if (state.previouslyFocused) {
        state.previouslyFocused.focus();
    }
}
```

### 10.4 手机返回键

监听 `popstate`，抽屉打开时阻止返回上一页，改为关闭抽屉。

```js
function bindGlobalEvents() {
    if (state.open) {
        history.pushState({ mcDrawer: true }, '');
    }

    window.addEventListener('popstate', (e) => {
        if (state.open && e.state && e.state.mcDrawer) {
            closeDrawer();
        }
    });
}
```

---

## 11. 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `site/js/minimal-comments.js` | 新增 | 评论系统主模块 |
| `site/css/minimal-comments.css` | 新增 | 全部样式 |
| `site/js/app.js` | 修改 | 笔记加载完成后调用 `MinimalComments.init({ articleId: path })` |
| `site/index.html` | 修改 | 引入新 css/js |
| `site/data/comments/*.json` | 新增（可选） | 每篇文章对应一份评论数据 |

---

## 12. 后续可扩展点（不在本次范围）

- 评论提交后端：目前为静态站，提交后仅本地展示并提示"审核后显示"。后续可接入 Netlify Forms、Cloudflare Workers 或自研评论服务。
- 排序方式：目前按时间正序；未来可增加"热门"排序。
- 回复功能：保持极简，暂不支持楼中楼。
