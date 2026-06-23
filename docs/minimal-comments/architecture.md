# 极简评论存储方案

> 适用：纯静态古籍阅读站点，部署在阿里魔搭空间，无后端服务。
> 目标：读者能看评论、能写评论；管理员在 GitHub 里审核、沉淀。

---

## 1. 存储方案总览

```text
┌──────────────────────────────────────────────────────────────────┐
│                        纯静态前端站点                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ 读取已发布评论  │    │ 提交新评论    │    │ 管理员后台(复用)  │  │
│  │  fetch JSON   │    │ POST Issues  │    │  GitHub Issues   │  │
│  └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘  │
│         │                   │                       │             │
│         ▼                   ▼                       ▼             │
│  site/data/comments/   GitHub Issues           GitHub 后台界面   │
│  <notePath>.json       （暂存区）                  （人工审核）    │
└──────────────────────────────────────────────────────────────────┘
```

### 1.1 已发布评论

- 位置：`site/data/comments/<notePath>.json`
- 作用：只读展示，页面加载时直接 `fetch`。
- 形态：每个笔记页面对应一个 JSON 文件，内部按段落分组。
- 示例路径：
  - 笔记页面：`/notes/shiji/benji/qinshihuang.html`
  - 对应数据：`site/data/comments/notes/shiji/benji/qinshihuang.json`

### 1.2 待审核评论

- 位置：GitHub Issues
- 作用：暂存区。
- 读者提交的新评论先进入 Issues；管理员在 GitHub 后台审核。
- 通过的评论由管理员手动（或半自动脚本）合并到 `site/data/comments/`。

### 1.3 管理员工作流

1. 在 GitHub Issues 看到待审评论。
2. 判断内容是否合规、是否适合展示。
3. 通过的评论复制/转换到对应 JSON 文件。
4. 关闭或删除 spam issue。
5. 重新构建并部署站点。

---

## 2. 为什么选 GitHub Issues 作为暂存区

| 优势 | 说明 |
|---|---|
| 免费 | 公共仓库 Issues 免费，无额外成本。 |
| 有通知 | 新评论自动邮件/桌面通知管理员。 |
| 有管理界面 | GitHub 网页就是后台，不用写任何管理端。 |
| 自带分类/筛选 | Labels、搜索、状态(Open/Closed)天然可用。 |
| 不需要自建后端 | 静态站点直接调 GitHub REST API。 |
| 读者无需 GitHub 账号 | 前端内置 fine-grained PAT 匿名提交（见安全设计）。 |
| 可审计 | 每条评论的来源、时间、IP（通过标题/Body附加）可留痕。 |

核心取舍：
- 不用自建后端 → 把"写操作"托管给 GitHub。
- 不追求实时显示 → 审核后随站点部署才可见。
- 不接受 spam 泛滥 → 前端 token + rate limit + 人工审核兜底。

---

## 3. 安全设计

### 3.1 Token 方案

使用 **GitHub fine-grained personal access token**（PAT）：

- 权限范围：仅授权 `Issues: Read and write`
- 不授权代码读写、不授权仓库管理。
- Token 只用于创建 issue，不能修改仓库代码。

创建方式：

```text
GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
→ Generate new token
→ Repository access: 仅选择本项目
→ Permissions: Issues → Read and write
```

### 3.2 Token 写在前端的取舍

**现实约束：**
- 纯静态站点无后端。
- 要让读者不写 GitHub 账号就能提交评论，必须让前端直接调用 Issues API。
- 因此 token 必须暴露在前端 JS 中。

**这是必要的折中，但要做风险限制：**

1. **最小权限 token**
   - 只能创建 issue，不能读私有仓库、不能修改代码、不能删除 issue（可关闭，但不可硬删除，需仓库管理员权限）。

2. **rate limit 防护**
   - GitHub 对未认证请求限制 60/h，认证请求 5000/h。
   - 前端使用认证 token，理论上限 5000/h，足够小站。
   - 前端再加一层本地节流：同一浏览器 5 分钟内只能提交一次。

3. **简单防刷**
   - 评论内容限制长度（10-500 字）。
   - 必填作者昵称，长度 1-20 字符。
   - 提交前简单人机校验：例如要求输入当前页面的某个字，或点击"我不是机器人"按钮。
   - 同一 `paragraphId` 同浏览器 session 内禁止重复提交。

4. **内容转义**
   - 前端渲染 JSON 中的评论时进行 HTML escape。
   - Issue body 中不渲染 Markdown，作为原始文本保存。
   - 禁止 `<script>`、事件处理器等注入。

5. **token 泄露后的影响**
   - 最坏情况：有人拿到 token 批量创建 spam issue。
   - 管理员可在 GitHub 后台批量关闭/锁定 issue，并随时吊销 token、重新生成。

### 3.3 安全函数示例

```js
// 转义 HTML，防止 XSS
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// 评论内容长度与字符校验
function validateComment({ author, content }) {
  if (!author || author.trim().length === 0 || author.trim().length > 20) {
    return { ok: false, message: '昵称长度需 1-20 字符' };
  }
  if (!content || content.trim().length < 10 || content.trim().length > 500) {
    return { ok: false, message: '评论长度需 10-500 字符' };
  }
  // 禁止常见 HTML/JS 注入
  if (/<script|javascript:|on\w+=/i.test(content)) {
    return { ok: false, message: '评论包含不支持的格式' };
  }
  return { ok: true };
}

// 本地节流：同一浏览器 5 分钟内只能提交一次
function canSubmit() {
  const last = localStorage.getItem('minimalComments:lastSubmit');
  if (!last) return true;
  return Date.now() - parseInt(last, 10) > 5 * 60 * 1000;
}

function recordSubmit() {
  localStorage.setItem('minimalComments:lastSubmit', String(Date.now()));
}
```

---

## 4. 数据模型

### 4.1 已发布评论 JSON

文件：`site/data/comments/<notePath>.json`

```json
{
  "notePath": "notes/shiji/benji/qinshihuang",
  "total": 2,
  "comments": [
    {
      "id": "c1a2b3c4",
      "notePath": "notes/shiji/benji/qinshihuang",
      "paragraphId": "p3",
      "content": "始皇此处确实犹豫了，李斯一言而定鼎。",
      "author": "读史人",
      "createdAt": "2026-06-20T08:30:00Z",
      "type": "paragraph"
    },
    {
      "id": "d5e6f7g8",
      "notePath": "notes/shiji/benji/qinshihuang",
      "paragraphId": "p7",
      "content": "这一段对话比后世演义更精彩。",
      "author": "古籍爱好者",
      "createdAt": "2026-06-21T12:00:00Z",
      "type": "paragraph"
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 评论唯一 ID，UUID 或时间戳哈希 |
| `notePath` | string | 笔记路径，不含 `.html` |
| `paragraphId` | string | 段落 ID，如 `p3` |
| `content` | string | 评论正文 |
| `author` | string | 作者昵称 |
| `createdAt` | ISO string | 发布时间 |
| `type` | string | 评论类型，当前固定 `paragraph` |

### 4.2 Issue 模板

标题格式：

```text
[段评] notes/shiji/benji/qinshihuang #p3
```

Body 格式（YAML frontmatter + 正文）：

```markdown
---
notePath: notes/shiji/benji/qinshihuang
paragraphId: p3
author: 读史人
type: paragraph
source: https://your-site.example/notes/shiji/benji/qinshihuang.html#p3
timestamp: 2026-06-22T14:20:00Z
---

始皇此处确实犹豫了，李斯一言而定鼎。
```

这样管理员一眼就能看到：评论属于哪篇笔记、哪个段落、作者是谁、什么时候提交的。

---

## 5. 前端读取

### 5.1 加载时机

页面渲染完笔记正文后，触发自定义事件：

```js
// app.js 最小改动
window.dispatchEvent(new CustomEvent('note:loaded', {
  detail: {
    notePath: 'notes/shiji/benji/qinshihuang',
    paragraphIds: ['p1', 'p2', 'p3', ...]
  }
}));
```

`minimal-comments.js` 监听该事件，然后加载评论数据。

### 5.2 读取函数

```js
/**
 * 加载已发布评论
 * @param {string} notePath - 例如 'notes/shiji/benji/qinshihuang'
 * @returns {Promise<{notePath: string, total: number, comments: Array}>}
 */
async function loadComments(notePath) {
  const url = `/site/data/comments/${notePath}.json`;
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (res.status === 404) {
      return { notePath, total: 0, comments: [] };
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.warn('加载评论失败:', err);
    return { notePath, total: 0, comments: [] };
  }
}
```

### 5.3 404 空状态

- JSON 文件不存在时，不报错，静默显示"暂无评论"。
- 每个段落底部预留评论入口。

---

## 6. 前端提交

### 6.1 提交函数签名

```js
/**
 * 提交评论到 GitHub Issues 暂存区
 * @param {string} repo - 'owner/repo'
 * @param {string} token - GitHub fine-grained PAT
 * @param {Object} comment
 * @param {string} comment.notePath
 * @param {string} comment.paragraphId
 * @param {string} comment.author
 * @param {string} comment.content
 * @param {string} comment.type - 默认 'paragraph'
 * @returns {Promise<{ok: boolean, message: string, issueUrl?: string}>}
 */
async function submitComment(repo, token, comment) {
  // 1. 校验
  const validation = validateComment(comment);
  if (!validation.ok) {
    return { ok: false, message: validation.message };
  }

  // 2. 本地节流
  if (!canSubmit()) {
    return { ok: false, message: '提交太频繁，请稍后再试' };
  }

  // 3. 构造 issue
  const title = `[段评] ${comment.notePath} #${comment.paragraphId}`;
  const timestamp = new Date().toISOString();
  const body = `---\nnotePath: ${comment.notePath}\nparagraphId: ${comment.paragraphId}\nauthor: ${comment.author}\ntype: ${comment.type || 'paragraph'}\ntimestamp: ${timestamp}\nsource: ${location.href}\n---\n\n${comment.content}`;

  // 4. POST 到 GitHub Issues API
  try {
    const res = await fetch(`https://api.github.com/repos/${repo}/issues`, {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github+json',
        'Authorization': `Bearer ${token}`,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ title, body, labels: ['comment-pending'] })
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      console.error('GitHub Issues API 错误:', data);
      return { ok: false, message: '网络问题，请稍后重试' };
    }

    const data = await res.json();
    recordSubmit();
    return {
      ok: true,
      message: '已提交审核，审核通过后显示',
      issueUrl: data.html_url
    };
  } catch (err) {
    console.error('提交评论失败:', err);
    return { ok: false, message: '网络问题，请稍后重试' };
  }
}
```

### 6.2 调用示例

```js
const REPO = 'your-org/ancient-texts-site';
const TOKEN = 'github_pat_xxxxxxxx'; // 仅 Issues: Read and write

async function onSubmitButtonClick(paragraphId, authorInput, contentInput) {
  const result = await submitComment(REPO, TOKEN, {
    notePath: 'notes/shiji/benji/qinshihuang',
    paragraphId,
    author: authorInput.value.trim(),
    content: contentInput.value.trim(),
    type: 'paragraph'
  });

  alert(result.message);

  if (result.ok) {
    authorInput.value = '';
    contentInput.value = '';
  }
}
```

### 6.3 用户提示

| 场景 | 提示文案 |
|---|---|
| 提交成功 | "已提交审核，审核通过后显示" |
| 提交失败 | "网络问题，请稍后重试" |
| 内容校验失败 | 具体错误，如"评论长度需 10-500 字符" |
| 提交频繁 | "提交太频繁，请稍后再试" |

---

## 7. 管理员工作流

### 7.1 日常审核

1. 打开 `https://github.com/owner/repo/issues`
2. 筛选 `label:comment-pending` 的 open issues。
3. 阅读评论内容。
4. 判断：
   - **通过**：复制内容，合并到对应 JSON 文件。
   - **不通过**：直接关闭 issue，可添加 `label:spam`。

### 7.2 半自动合并脚本

可选：在仓库根目录加一个 Node 脚本，把通过审核的 issue 转换为 JSON 条目。

```js
// scripts/import-comment.js
const fs = require('fs');
const path = require('path');

/**
 * 将单条 issue body 解析为评论对象
 * @param {string} issueBody
 * @returns {Object|null}
 */
function parseIssueBody(issueBody) {
  const metaMatch = issueBody.match(/^---\n([\s\S]*?)\n---/);
  if (!metaMatch) return null;

  const meta = {};
  metaMatch[1].split('\n').forEach(line => {
    const [k, ...rest] = line.split(':');
    if (k && rest.length) meta[k.trim()] = rest.join(':').trim();
  });

  const content = issueBody.replace(/^---\n[\s\S]*?\n---\n*/, '').trim();

  return {
    id: `c${Date.now()}`,
    notePath: meta.notePath,
    paragraphId: meta.paragraphId,
    author: meta.author,
    type: meta.type || 'paragraph',
    createdAt: meta.timestamp,
    content
  };
}

/**
 * 将评论追加到对应 JSON 文件
 * @param {Object} comment
 */
function appendComment(comment) {
  const filePath = path.join(
    __dirname,
    '..',
    'site',
    'data',
    'comments',
    `${comment.notePath}.json`
  );

  fs.mkdirSync(path.dirname(filePath), { recursive: true });

  let data = { notePath: comment.notePath, total: 0, comments: [] };
  if (fs.existsSync(filePath)) {
    data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  data.comments.push(comment);
  data.total = data.comments.length;

  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
}

// 示例：手动传入 issue body
const issueBody = process.argv[2];
const comment = parseIssueBody(issueBody);
if (comment) {
  appendComment(comment);
  console.log('已导入:', comment.notePath, comment.paragraphId);
} else {
  console.error('解析失败');
  process.exit(1);
}
```

使用方式：

```bash
node scripts/import-comment.js "$(cat issue-body.txt)"
```

### 7.3 部署

评论合并到 JSON 后，重新构建并部署静态站点即可。

---

## 8. 替代方案对比

| 方案 | 优点 | 缺点 | 是否适用 |
|---|---|---|---|
| **GitHub Issues** | 免费、有通知、有后台、读者免账号 | token 暴露、有 rate limit | ✅ **推荐** |
| GitHub Discussions (giscus) | 成熟的评论组件、支持 reactions | 读者需登录 GitHub 才能评论；与"匿名提交"需求冲突 | ❌ 不适用 |
| GitHub Contents API 直接写 JSON | 评论立即上线 | token 需代码写入权限，风险极高；无法审核 | ❌ 不适用 |
| localStorage + 邮件/表单 | 完全离线、无 API | 评论无法真正提交给管理员；数据易丢失 | ❌ 不适用 |
| Cloudflare Workers | 可藏 token、可写 KV | 引入额外服务、学习成本、魔搭空间外多一层依赖 | ⚠️ 过度设计 |

结论：GitHub Issues 是在"无后端 + 匿名提交 + 管理员审核"三者之间最轻量、最可用的平衡。

---

## 9. 极简实现要点

### 9.1 文件清单

```text
site/
├── js/
│   └── minimal-comments.js    # 评论加载与提交逻辑
├── css/
│   └── minimal-comments.css   # 手机端优先的评论区样式
└── data/
    └── comments/              # 已发布评论 JSON
        └── notes/
            └── shiji/
                └── benji/
                    └── qinshihuang.json
```

### 9.2 `site/js/minimal-comments.js` 核心结构

```js
(function () {
  const CONFIG = {
    repo: 'owner/repo',
    token: 'github_pat_xxxxxxxx',
    dataDir: '/site/data/comments',
    submitInterval: 5 * 60 * 1000 // 5 分钟
  };

  // 工具函数
  function escapeHtml(str) { ... }
  function validateComment(c) { ... }
  function canSubmit() { ... }
  function recordSubmit() { ... }

  // 数据读取
  async function loadComments(notePath) { ... }

  // 数据提交
  async function submitComment(repo, token, comment) { ... }

  // UI：渲染某段落的评论列表
  function renderComments(container, comments, paragraphId) { ... }

  // UI：渲染评论输入框
  function renderForm(container, notePath, paragraphId) { ... }

  // 入口
  function init({ notePath, paragraphIds }) {
    loadComments(notePath).then(data => {
      paragraphIds.forEach(pid => {
        const container = document.getElementById(`comments-${pid}`);
        if (!container) return;
        const list = data.comments.filter(c => c.paragraphId === pid);
        renderComments(container, list, pid);
        renderForm(container, notePath, pid);
      });
    });
  }

  window.addEventListener('note:loaded', e => init(e.detail));
})();
```

### 9.3 `app.js` 最小改动

在笔记正文渲染完成后触发事件：

```js
// app.js
function onNoteRendered(notePath) {
  const paragraphIds = Array.from(
    document.querySelectorAll('[data-paragraph-id]')
  ).map(el => el.dataset.paragraphId);

  window.dispatchEvent(new CustomEvent('note:loaded', {
    detail: { notePath, paragraphIds }
  }));
}
```

### 9.4 `site/css/minimal-comments.css` 关键原则

- 手机端优先：评论区宽度 100%，输入框字体 16px（防止 iOS 缩放）。
- 每条评论只保留：作者、时间、内容、回复入口（可选）。
- 提交按钮固定大小，便于触摸。

```css
.minimal-comments {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #fafafa;
  border-radius: 0.5rem;
}

.minimal-comments__item {
  padding: 0.75rem 0;
  border-bottom: 1px solid #eee;
}

.minimal-comments__author {
  font-weight: 600;
  color: #333;
}

.minimal-comments__time {
  font-size: 0.75rem;
  color: #999;
  margin-left: 0.5rem;
}

.minimal-comments__form textarea {
  width: 100%;
  min-height: 5rem;
  font-size: 16px; /* iOS no-zoom */
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 0.25rem;
  resize: vertical;
}

.minimal-comments__form button {
  width: 100%;
  padding: 0.75rem;
  margin-top: 0.5rem;
  font-size: 1rem;
  background: #1a1a1a;
  color: #fff;
  border: none;
  border-radius: 0.25rem;
}
```

### 9.5 不做的事情

- 不做本地持久化（localStorage 存未提交评论）。
- 不做离线队列。
- 不做复杂状态管理。
- 不做实时同步。
- 不做嵌套回复（首期只做一级评论）。
- 不做用户登录体系。

---

## 10. 部署前检查清单

- [ ] 在 GitHub 生成 fine-grained PAT，仅授权 `Issues: Read and write`。
- [ ] 将 token 填入 `site/js/minimal-comments.js` 的 `CONFIG.token`。
- [ ] 确认仓库已开启 Issues（Settings → General → Issues → ✅）。
- [ ] 创建标签 `comment-pending`（可选，脚本会自动创建但首次可能失败）。
- [ ] 在站点构建流程中保留 `site/data/comments/` 目录。
- [ ] 测试 404 空状态：访问无评论的笔记页面，应正常显示"暂无评论"。
- [ ] 测试提交一条评论，确认 GitHub Issues 中出现对应 issue。
- [ ] 测试通过后，管理员手动合并到 JSON 并重新部署。

---

## 总结

本方案用"仓库 JSON 只读展示 + GitHub Issues 暂存审核"的组合，把静态站点的评论功能压到最简：

- 读者：看 JSON 里的已发布评论，点提交进 Issues 暂存。
- 管理员：在 GitHub Issues 里审核，通过的合并到 JSON。
- 成本：一个 JS、一个 CSS、一个事件触发、一个 token。

核心原则：**够用即可，不引入后端，不增加复杂度。**
