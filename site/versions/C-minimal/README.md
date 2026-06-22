# 深度阅读助手 · 版本 C · 现代极简风批注系统

> 原文批注式评论系统的「现代极简风」实现。大量留白、浮动气泡、底部抽屉式评论区、单色高亮、微动效——最克制最现代，评论系统"在场但不打扰"，把舞台让给原文。

## 版本特点

### 视觉语言
- **极简去装饰**：不引入新色相，全部基于现有 `--ink-primary` 与 `--accent` 的低透明度衍生
- **墨色低透明度中性色系**：高亮底色仅 `rgba(44,44,44,0.055)`，几乎不抢正文
- **类型区分靠左侧 2px 色条**：5 种类型用低饱和色条暗示，无彩色底块
- **大量留白**：正文零挤压，820px 阅读区完全保留

### 交互模式
- **圈选触发**：选区右上方浮出 28×28 极简图标气泡（仅 ✎ 图标），点击展开内联输入条
- **高亮样式**：极淡墨底 + 左侧 2px 类型色条，hover 时墨底加深
- **底部抽屉**：默认收起为 40px 窄条贴底（"评论 N · 未解决 M"），点击上滑展开至 `min(40vh, 360px)`
- **列表+详情**：抽屉内左右分栏，左列表右详情，移动端切换为单栏
- **导出/专家团**：抽屉窄条右侧两个极简文字按钮，无图标无背景

### 5 种评论类型

| type | 中文 | 色条色 | 用途 |
|---|---|---|---|
| `error` | 错误 | `#c0392b` 暗红 | 指出史实、引文、字词错误 |
| `praise` | 夸奖 | `#8b5a2b` 棕金（=accent） | 标记精彩段落 |
| `discussion` | 讨论 | `#5a5651` 青灰 | 提出疑问、展开思辨 |
| `supplement` | 补充 | `#8a8580` 橄榄灰 | 补充史料、出处、背景 |
| `thought` | 感想 | `#a8a29e` 紫灰 | 作者自己的灵感、联想 |

## 目录结构

```
C-minimal/
├── index.html          # 入口页面（含工具栏导出/专家团/导入按钮）
├── css/
│   ├── style.css       # 站点基础样式（复制自 site/css/style.css）
│   └── comments.css    # 评论系统样式（现代极简风，--cmtC- 变量）
├── js/
│   ├── app.js          # 前端逻辑（含 note:loaded 事件 dispatch 补丁）
│   └── comments.js     # 评论系统核心模块（IIFE，window.DeepReadingComments）
└── README.md           # 本文件
```

## 预览方式

### 1. 准备数据
确保 `site/data/index.json` 和 `site/notes/` 已由构建脚本生成。如未生成，在项目根目录运行：
```bash
python scripts/build_site.py
```

### 2. 复制数据到版本目录
将 `site/data/` 和 `site/notes/` 复制（或软链）到 `C-minimal/` 下：
```bash
cp -r site/data site/versions/C-minimal/
cp -r site/notes site/versions/C-minimal/
```

### 3. 启动本地服务器
```bash
python -m http.server 8080 -d site/versions/C-minimal
```

### 4. 浏览器打开
访问 <http://localhost:8080>

## 功能清单

### 核心功能
- [x] **圈选批注**：选中文本 → 图标气泡 → 输入条 → 提交 → 高亮
- [x] **5 种类型**：error / praise / discussion / supplement / thought
- [x] **三级锚定**：精确偏移 + quote 校验 → quote 全文匹配 → 前后缀指纹模糊匹配
- [x] **高亮渲染**：`<mark>` 包裹，左侧 2px 类型色条，跨节点选区逐节点切分包裹
- [x] **悬浮卡**：hover 高亮显示评论摘要
- [x] **底部抽屉**：40px 窄条 ↔ 40vh 展开，列表+详情分栏
- [x] **回复**：详情面板内回复，支持多级
- [x] **解决/重新打开**：状态切换，高亮降饱和
- [x] **编辑/删除**：软删除带二次确认
- [x] **筛选**：按类型、状态、关键词
- [x] **跳转原文**：点击高亮或列表项 → 滚动 + 闪烁

### 数据功能
- [x] **localStorage 存储**：`drc:<notePath>` 存评论，`drc:index` 存索引，`drc:meta` 存元信息
- [x] **导出单篇**：`comments_<notePath>_<YYYYMMDD>.json`（deep-reading-comments/v1 schema）
- [x] **导出全站**：`comments_all_<YYYYMMDD>.json`
- [x] **导入**：支持 merge / replace 模式，按 id 去重
- [x] **导出给 AI**：`exportForAgents` 生成 AI 友好格式
- [x] **复制为 Prompt**：一键复制纯文本格式

### 专家团
- [x] **触发向导**：选择范围、参与专家、附加指令
- [x] **生成指令包**：`expert_review_request_<notePath>_<YYYYMMDD>.json`
- [x] **本地执行提示**：显示 `python src/main.py --expert-review expert_review_request.json`
- [x] **评判回填**：导入 `expert_review_result.json` 后显示评判徽章

### 工程质量
- [x] **纯 vanilla JS**：无框架依赖，仅 marked.js CDN
- [x] **IIFE 封装**：`window.DeepReadingComments` 唯一全局命名空间
- [x] **XSS 防护**：所有用户输入 `escapeHtml` + `textContent`，绝不 `innerHTML` 拼接
- [x] **键盘可用**：Tab 聚焦、Enter 提交、Esc 关闭、Ctrl+Enter 快捷提交
- [x] **响应式**：移动端天然友好（底部抽屉自适应）
- [x] **reduced-motion**：尊重 `prefers-reduced-motion`
- [x] **孤儿批注降级**：解析失败时不高亮，评论区灰色标识
- [x] **多标签页同步**：监听 `storage` 事件

## API 参考

```js
// 初始化（通常自动调用）
window.DeepReadingComments.init(readerEl?)

// 加载笔记评论
window.DeepReadingComments.loadForNote(notePath)

// 清理
window.DeepReadingComments.clear()

// 重新渲染高亮
window.DeepReadingComments.refresh()

// 查询
window.DeepReadingComments.getComments(notePath)
window.DeepReadingComments.getAllComments()
window.DeepReadingComments.getIndex()

// 导出
window.DeepReadingComments.exportNote(notePath)
window.DeepReadingComments.exportAll()
window.DeepReadingComments.exportForAgents(notePath)
window.DeepReadingComments.copyAsPromptContext(notePath)

// 导入
window.DeepReadingComments.importJSON(jsonStr, mode)  // mode: 'merge' | 'replace'

// 专家团
window.DeepReadingComments.triggerExpertReview()
```

## 设计决策说明

### 为什么选底部抽屉而非右侧面板？
- **正文零挤压**：820px 阅读区完全保留，可读性最佳
- **移动端友好**：底部抽屉在移动端天然适配，无需降级方案
- **沉浸感**：抽屉收起时几乎"隐形"，沉浸阅读与批注切换干净

### 为什么用单色高亮而非彩色底块？
- **不打扰阅读**：极淡墨底（5.5% 透明度）几乎不影响正文视觉
- **类型暗示**：左侧 2px 色条提供类型区分，但不抢眼
- **气质协调**：中性墨色与暖纸底不冲突，无突兀感

### 为什么用图标气泡而非直接弹输入框？
- **克制**：选区后只出现一个 28px 小圆点，不打断阅读流
- **明确意图**：用户主动点击才进入批注模式，避免误触
- **现代感**：类似 Medium / Linear 的极简交互模式

## 与其他版本的差异

| 维度 | A 飞书云文档风 | B 古籍批注风 | **C 现代极简风** |
|---|---|---|---|
| 主色 | 飞书蓝（冷） | 朱砂+赭石（暖） | **墨色低透明度（中性）** |
| 高亮 | 类型色底块 16% | 朱笔波浪下划线 | **极淡墨底+左2px色条** |
| 评论位置 | 右侧悬浮面板 340px | 右侧 margin notes 240px | **底部抽屉 40vh** |
| 正文影响 | 不挤压 | 挤压（margin-right 260px） | **零挤压** |
| 移动端 | 需降级 | 需降级 | **天然友好** |
| 协作感 | 强 | 弱 | 中 |
