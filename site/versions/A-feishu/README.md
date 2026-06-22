# 版本 A · 飞书云文档风批注系统

> 深度阅读助手静态站点的原文批注式评论系统实现之一，采用飞书云文档风视觉语言。

## 版本特点

- **冷色工具层 + 暖纸内容层**：阅读区保留暖纸色 `#faf8f5` 与宋体正文不变；评论 UI 作为"工具层"引入飞书蓝 `#3370ff` 点缀与无衬线字体，形成现代/古典对比。
- **右侧悬浮面板**：340px 宽白色面板浮于 reader 右侧，可折叠为 44px 窄条；窄屏（<1024px）自动转为底部抽屉。
- **气泡式选区工具条**：圈选原文后，选区上方弹出横向气泡（评论 / 复制 / 引用），点"评论"展开输入浮层。
- **5 种评论类型**：错误指正 ❗ / 写得好 👍 / 讨论 💬 / 补充 ➕ / 感想 ✦，各有独立高亮色与图标。
- **三级容错锚定**：精确偏移 + quote 校验 → quote 全文匹配 → 前后缀指纹模糊定位，原文小幅修订后高亮仍能找回。
- **完整评论生命周期**：圈选批注 → 高亮 → 回复 → 解决/重开 → 编辑 → 软删除。
- **导出/导入**：符合 `deep-reading-comments/v1` schema，可被 Python AI 专家团消费。
- **专家团触发**：生成 `expert_review_request.json` 供本地 Python pipeline 执行，结果可回填。
- **纯 vanilla JS**：无框架依赖，仅 marked.js CDN（已有）。

## 如何预览

### 方式一：直接预览（需先准备 data/ 与 notes/）

由于本版本目录是 `site/versions/A-feishu/`，而 `app.js` 会 fetch `data/index.json` 与 `notes/*.md`（相对路径），需先把数据目录软链或复制进来：

```bash
# 在项目根目录执行
cd site/versions/A-feishu
ln -s ../../../data data
ln -s ../../../notes notes
# 或复制：
# cp -r ../../../data ./data
# cp -r ../../../notes ./notes

# 启动静态服务器
python -m http.server 8080
```

浏览器打开 `http://localhost:8080/`。

### 方式二：用项目根脚本（若存在）

```bash
python scripts/preview_version.py A
```

### 方式三：从项目根目录预览

```bash
# 在项目根目录启动服务器，访问 /site/versions/A-feishu/
python -m http.server 8080
# 浏览器打开 http://localhost:8080/site/versions/A-feishu/
```

> 注意：方式三下，`app.js` 的 `fetch('data/index.json')` 会解析为 `/data/index.json`（项目根），而非 `/site/versions/A-feishu/data/index.json`。若数据在 `site/data/` 下，请用方式一。

## 功能清单

### 核心功能

- [x] 圈选原文 → 气泡工具条 → 评论浮层 → 提交 → 高亮
- [x] 5 种评论类型（error/praise/discussion/supplement/thought），各有高亮色与图标
- [x] 三级容错文本锚定（精确偏移 → quote 匹配 → 指纹模糊）
- [x] 高亮 mark 包裹（跨节点选区支持）
- [x] 点击高亮 → 面板定位 + 原文闪烁
- [x] 高亮 hover → 悬浮卡（内容/类型/作者/时间/回复数/状态）
- [x] 回复（多级，Enter 提交，Shift+Enter 换行）
- [x] 解决 / 重新打开（高亮降饱和 + 划线）
- [x] 编辑评论内容
- [x] 软删除（带二次确认）
- [x] 复制锚定原文
- [x] 定位到原文（scrollIntoView + flash 动画）

### 面板功能

- [x] 右侧 340px 悬浮面板，可折叠
- [x] 按位置/时间/状态排序
- [x] 按类型/状态/关键词筛选
- [x] 显示/隐藏已解决
- [x] 空状态引导
- [x] 孤儿批注标记（原文已变更）
- [x] 移动端转底部抽屉

### 数据功能

- [x] localStorage 持久化（key: `drc:<notePath>`）
- [x] 全局索引（`drc:index`）
- [x] 导出当前笔记 / 全站（`deep-reading-comments/v1` schema）
- [x] 导入合并（按 id 去重）
- [x] 多标签页同步（storage 事件）

### 专家团功能

- [x] 启用专家团向导（范围 / 参与专家 / 附加指令）
- [x] 生成 `expert_review_request.json` 下载
- [x] 导入 `expert_review_result.json` 回填评判
- [x] 评判徽章（采纳/不采纳/待议）展示
- [x] 复制为 Prompt 上下文

### 交互细节

- [x] Esc 关闭浮层/气泡
- [x] Enter 提交，Shift+Enter 换行
- [x] 浮层定位自动翻转（上方空间不足时翻下方）
- [x] selectionchange 防抖（200ms）
- [x] Toast 提示（成功/错误/警告/信息）
- [x] `prefers-reduced-motion` 降级
- [x] XSS 防护（escapeHtml + textContent，无 innerHTML 拼接用户输入）

## 文件说明

```
A-feishu/
├── index.html          # 入口，引入 style.css + comments.css + app.js + comments.js
├── css/
│   ├── style.css       # 现有暖纸色基线样式（直接复制自 site/css/style.css）
│   └── comments.css    # 飞书风评论系统样式（CSS 变量 --cmtA- 前缀）
├── js/
│   ├── app.js          # 现有逻辑 + note:loaded 事件 dispatch（最小补丁）
│   └── comments.js     # 评论系统核心模块（IIFE，挂 window.DeepReadingComments）
└── README.md           # 本文件
```

## 与现有 app.js 的集成

仅一处改动：`loadNote` 成功渲染 markdown 后，dispatch `note:loaded` 自定义事件，携带 `{ notePath, container, meta }`。`comments.js` 监听该事件初始化。失败分支不 dispatch，避免误触发。

```js
// app.js loadNote 成功分支末尾
const article = elements.reader.querySelector('.markdown-body');
if (article) {
    document.dispatchEvent(new CustomEvent('note:loaded', {
        detail: { notePath: path, container: article, meta: meta || null }
    }));
}
```

## 公开 API

`window.DeepReadingComments` 暴露：

| 方法 | 说明 |
|---|---|
| `init()` | 初始化（自动调用） |
| `loadForNote(path)` | 加载某笔记评论 |
| `clear()` | 清空当前视图 |
| `attach(container, path, meta)` | 为容器初始化高亮+选区监听 |
| `detach()` | 卸载监听 |
| `refresh()` | 重新渲染高亮 |
| `getComments(path)` | 获取某笔记评论数组 |
| `getAllComments()` | 获取全站评论 `{ notePath: Comment[] }` |
| `getIndex()` | 获取全局索引 |
| `exportNote(path)` | 导出单篇 JSON 字符串 |
| `exportAll()` | 导出全站 JSON 字符串 |
| `importJSON(str, mode)` | 导入合并（mode: merge/replace） |
| `clearNote(path)` | 删除某笔记全部评论 |
| `exportForAgents(path)` | AI 友好格式导出 |
| `copyAsPromptContext(path)` | 复制为 Prompt 上下文 |
| `exportExpertReviewRequest(path, participants, instruction)` | 生成专家团请求包 |
| `importExpertReview(str)` | 导入专家评判结果 |

## 数据模型

评论对象（Comment）遵循 spec.md 4.2，融合 architecture.md 3.3：

```json
{
  "id": "c_<timestamp>_<seq>",
  "notePath": "资治通鉴/周纪一_三家分晋.md",
  "parentId": null,
  "type": "discussion",
  "status": "open",
  "anchor": {
    "notePath": "...",
    "quote": "智伯贪而愎",
    "rangeStart": 1234,
    "rangeEnd": 1245,
    "normTextPrefix": "...前 32 字...",
    "normTextSuffix": "...后 32 字...",
    "schemaVersion": 1,
    "strategy": "text+context",
    "exact": "智伯贪而愎",
    "prefix": "...前 20 字...",
    "suffix": "...后 20 字...",
    "paragraphIndex": 3,
    "headingPath": ["讲事情"],
    "charOffsetStart": 1234,
    "charOffsetEnd": 1245,
    "version": "2026-06-21"
  },
  "content": "此处段规原话见《资治通鉴·周纪一》...",
  "author": "作者",
  "createdAt": "2026-06-22T14:32:11+08:00",
  "updatedAt": "2026-06-22T14:35:02+08:00",
  "resolvedAt": null,
  "tags": [],
  "replies": [],
  "expertReviews": [],
  "deleted": false,
  "agentHints": { "targetAgent": "critic", "priority": "normal" }
}
```

## 设计取舍

- ✅ 协作流程最顺，学习成本最低（飞书/Notion 心智）
- ✅ 冷色工具层与暖纸内容层对比清晰，评论不会"糊"在原文里
- ✅ 右侧面板不挤压正文（max-width 820px 不变，面板 absolute 浮于右侧）
- ⚠️ 蓝色品牌色与站点棕色 accent 是两套色系，"现代工具感"会盖过"古籍气质"
- ⚠️ 窄屏（<1024px）面板转底部抽屉，<768px 浮层全屏化

## 自检结果

对照 `docs/comments-system/checklist.md` 逐项自查通过，详见实现报告。
