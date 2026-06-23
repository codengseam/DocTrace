(function (global) {
  'use strict';

  /**
   * 极简古籍段评系统
   * 读者：看 JSON 中的已审核评论；写评论提交到 GitHub Issues 暂存。
   * 管理员：在 GitHub Issues 审核，通过的写入 site/data/comments/<notePath>.json。
   */

  // ==================== 默认配置 ====================
  // 使用前请填写 owner / repo / token。
  // token 获取方式：GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
  // → Generate new token → Repository access: 仅选择本项目 → Permissions: Issues → Read and write
  const DEFAULT_CONFIG = {
    owner: '',   // 仓库所有者，如 'codengseam'
    repo: '',    // 仓库名，如 'HaloRead'
    token: '',   // fine-grained PAT，仅授权 Issues: Read and write
    dataDir: 'data/comments', // 已审核评论 JSON 存放目录（相对站点根目录）
    maxChars: 200,
    submitInterval: 5 * 60 * 1000 // 同一浏览器 5 分钟内限提交一次
  };

  const COMMENT_TYPES = [
    { key: 'erratum', label: '勘误' },
    { key: 'discuss', label: '讨论' },
    { key: 'note',    label: '感想' }
  ];

  const NS = 'mc';
  const SELECTOR = {
    reader: '#reader',
    article: '#reader .markdown-body',
    paragraphs: '#reader .markdown-body > p'
  };

  // 兼容部署在子目录（如 site/versions/<ver>/）
  const SITE_BASE = (() => {
    if (!global.location) return '';
    const p = global.location.pathname.replace(/\/[^/]*$/, '/');
    const idx = p.indexOf('/versions/');
    if (idx >= 0) return p.slice(0, idx) + '/';
    return '';
  })();

  // ==================== 内部状态 ====================
  const state = {
    config: null,
    notePath: null,
    paragraphIds: [],
    comments: {},        // { pid: [comment, ...] }
    activePid: null,
    open: false,
    panelHeight: 0.5,    // 抽屉高度占视口比例
    isDragging: false,
    dragStartY: 0,
    dragStartHeight: 0,
    focusTrapHandler: null,
    previouslyFocused: null,
    els: {}
  };

  // ==================== 工具函数 ====================

  /**
   * HTML 转义，防止 XSS
   */
  function escapeHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  /**
   * 生成安全的段落 ID 选择器
   */
  function pidSelector(pid) {
    return `p[data-pid="${CSS.escape(String(pid))}"]`;
  }

  /**
   * 规范化评论数据，按 pid 分组并排序
   */
  function normalizeComments(list) {
    const map = {};
    (list || []).forEach((c) => {
      const pid = c.pid || c.paragraphId;
      if (!pid) return;
      if (!map[pid]) map[pid] = [];
      map[pid].push(c);
    });
    Object.keys(map).forEach((pid) => {
      map[pid].sort((a, b) => {
        const ta = a.createdAt ? new Date(a.createdAt).getTime() : 0;
        const tb = b.createdAt ? new Date(b.createdAt).getTime() : 0;
        return ta - tb;
      });
    });
    return map;
  }

  /**
   * 本地提交节流
   */
  function canSubmit() {
    try {
      const last = localStorage.getItem('minimalComments:lastSubmit');
      if (!last) return true;
      const interval = state.config ? state.config.submitInterval : DEFAULT_CONFIG.submitInterval;
      return Date.now() - parseInt(last, 10) > interval;
    } catch (e) {
      return true;
    }
  }

  function recordSubmit() {
    try {
      localStorage.setItem('minimalComments:lastSubmit', String(Date.now()));
    } catch (e) {
      // 忽略存储失败
    }
  }

  /**
   * 校验评论
   */
  function validateComment({ author, content }) {
    const authorTrim = String(author || '').trim();
    const contentTrim = String(content || '').trim();
    if (authorTrim.length === 0 || authorTrim.length > 20) {
      return { ok: false, message: '昵称长度需 1-20 字符' };
    }
    if (contentTrim.length === 0 || contentTrim.length > 200) {
      return { ok: false, message: '批注长度需 1-200 字符' };
    }
    // 禁止常见 HTML/JS 注入
    if (/<script|javascript:|on\w+=/i.test(contentTrim)) {
      return { ok: false, message: '批注包含不支持的格式' };
    }
    return { ok: true };
  }

  /**
   * 格式化日期：M月D日
   */
  function formatDate(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '';
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  }

  /**
   * 获取评论类型标签
   */
  function getTypeLabel(key) {
    const found = COMMENT_TYPES.find((t) => t.key === key);
    return found ? found.label : '讨论';
  }

  /**
   * 去除路径扩展名，保证 notePath 稳定
   */
  function stripExt(path) {
    return String(path || '').replace(/\.(md|html|txt)$/i, '');
  }

  // ==================== 初始化 ====================

  /**
   * 初始化评论系统
   * @param {Object} config - 配置对象，会合并到 DEFAULT_CONFIG
   */
  function init(config) {
    state.config = Object.assign({}, DEFAULT_CONFIG, config || {});

    // 监听笔记渲染完成事件
    global.addEventListener('note:loaded', onNoteLoaded);

    // 如果 DOM 中已有文章，立即初始化（兼容非事件调用）
    const article = document.querySelector(SELECTOR.article);
    if (article) {
      const path = state.config.notePath || stripExt(location.pathname);
      bootstrap(path, article);
    }
  }

  /**
   * 笔记加载完成回调
   */
  function onNoteLoaded(event) {
    const detail = event.detail || {};
    const notePath = stripExt(detail.notePath || location.pathname);
    const article = document.querySelector(SELECTOR.article);
    if (article) {
      bootstrap(notePath, article);
    }
  }

  /**
   * 启动：打标、加载评论、渲染徽章
   */
  async function bootstrap(notePath, article) {
    state.notePath = notePath;
    injectParagraphIds(article);
    await loadComments(notePath);
    renderBadges(article);
    bindParagraphClicks(article);
  }

  // ==================== 段落标记 ====================

  /**
   * 给 .markdown-body 内直接子级 <p> 添加 data-pid
   * @param {HTMLElement} container
   */
  function injectParagraphIds(container) {
    if (!container) return [];
    const paragraphs = container.querySelectorAll(':scope > p');
    const ids = [];
    paragraphs.forEach((p, index) => {
      const pid = `p${String(index + 1).padStart(4, '0')}`;
      p.setAttribute('data-pid', pid);
      ids.push(pid);
    });
    state.paragraphIds = ids;
    return ids;
  }

  /**
   * 绑定段落点击打开抽屉（点击段落本身，徽章单独处理）
   */
  function bindParagraphClicks(article) {
    if (!article) return;
    article.addEventListener('click', (e) => {
      const p = e.target.closest('p[data-pid]');
      if (!p) return;
      // 若点击的是徽章，徽章自己处理
      if (e.target.closest('.mc-badge')) return;
      openDrawer(p.dataset.pid);
    });
  }

  // ==================== 评论数据 ====================

  /**
   * 加载已审核评论 JSON
   * @param {string} notePath
   * @returns {Promise<{notePath: string, total: number, comments: Array}>}
   */
  async function loadComments(notePath) {
    notePath = stripExt(notePath || state.notePath || '');
    const safePath = notePath.replace(/[^a-zA-Z0-9\u4e00-\u9fa5_\-\/]/g, '_').replace(/^\/+/, '');
    const dataDir = (state.config ? state.config.dataDir : DEFAULT_CONFIG.dataDir).replace(/^\/+/, '');
    const base = SITE_BASE ? SITE_BASE.replace(/\/$/, '') : '';
    const url = (base ? base + '/' : '') + dataDir + '/' + safePath + '.json';

    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (res.status === 404) {
        state.comments = {};
        return { notePath, total: 0, comments: [] };
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      state.comments = normalizeComments(data.comments || []);
      return {
        notePath,
        total: Object.values(state.comments).reduce((sum, arr) => sum + arr.length, 0),
        comments: data.comments || []
      };
    } catch (err) {
      console.warn('[MinimalComments] 加载评论失败:', err);
      state.comments = {};
      return { notePath, total: 0, comments: [] };
    }
  }

  // ==================== 徽章 ====================

  /**
   * 给有评论的段落添加/更新右侧朱砂徽章
   * @param {HTMLElement} container
   */
  function renderBadges(container) {
    if (!container) return;
    const paragraphs = container.querySelectorAll(':scope > p[data-pid]');
    paragraphs.forEach((p) => {
      const pid = p.dataset.pid;
      let badge = p.querySelector('.mc-badge');
      if (!badge) {
        badge = createBadge(pid);
        p.appendChild(badge);
      }
      updateBadge(badge, pid);
    });
  }

  function createBadge(pid) {
    const badge = document.createElement('button');
    badge.type = 'button';
    badge.className = 'mc-badge';
    badge.setAttribute('data-pid', pid);
    badge.setAttribute('aria-label', '添加批注');

    const countSpan = document.createElement('span');
    countSpan.className = 'mc-badge-count';

    const hintSpan = document.createElement('span');
    hintSpan.className = 'mc-badge-hint';
    hintSpan.textContent = '评';

    badge.appendChild(countSpan);
    badge.appendChild(hintSpan);

    badge.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openDrawer(pid);
    });

    return badge;
  }

  function updateBadge(badge, pid) {
    if (typeof badge === 'string') {
      const p = document.querySelector(pidSelector(badge));
      badge = p ? p.querySelector('.mc-badge') : null;
      pid = badge ? badge.dataset.pid : pid;
    }
    if (!badge) return;

    const list = state.comments[pid] || [];
    const count = list.length;
    const countSpan = badge.querySelector('.mc-badge-count');
    const hintSpan = badge.querySelector('.mc-badge-hint');

    if (count > 0) {
      badge.classList.add('has-comments');
      badge.setAttribute('aria-label', `${count} 条批注`);
      countSpan.textContent = String(count);
      countSpan.style.display = '';
      hintSpan.style.display = 'none';
    } else {
      badge.classList.remove('has-comments');
      badge.setAttribute('aria-label', '添加批注');
      countSpan.style.display = 'none';
      hintSpan.style.display = '';
    }
  }

  // ==================== 抽屉 ====================

  /**
   * 打开指定段落的批注抽屉
   * @param {string} pid
   */
  function openDrawer(pid) {
    if (state.open && state.activePid === pid) return;

    state.activePid = pid;
    state.open = true;
    ensureDrawer();
    renderDrawer();
    showDrawer();
    trapFocus();
    pushHistory();
  }

  /**
   * 关闭抽屉
   */
  function closeDrawer() {
    if (!state.open) return;
    state.open = false;
    state.activePid = null;
    hideDrawer();
    releaseFocus();
    popHistory();
  }

  function ensureDrawer() {
    if (state.els.drawer) return;

    const overlay = document.createElement('div');
    overlay.id = 'mc-overlay';
    overlay.className = 'mc-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.addEventListener('click', closeDrawer);

    const drawer = document.createElement('div');
    drawer.id = 'mc-drawer';
    drawer.className = 'mc-drawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-labelledby', 'mc-drawer-title');
    drawer.setAttribute('tabindex', '-1');

    drawer.innerHTML = `
      <div class="mc-drawer-handle" role="button" tabindex="0" aria-label="拖动调整高度">
        <span class="mc-handle-bar"></span>
      </div>
      <div class="mc-drawer-header">
        <h2 id="mc-drawer-title" class="mc-drawer-title">段落批注</h2>
        <button type="button" class="mc-close" aria-label="关闭批注">×</button>
      </div>
      <div class="mc-drawer-body"></div>
      <div class="mc-input-wrap">
        <div class="mc-input-meta">
          <select class="mc-type-select" aria-label="批注类型"></select>
          <input type="text" class="mc-author" placeholder="昵称" maxlength="20" aria-label="昵称" />
        </div>
        <div class="mc-input-row">
          <textarea class="mc-textarea" rows="1" maxlength="200" placeholder="在此写下批注…" aria-label="批注内容，最多 200 字"></textarea>
          <button type="button" class="mc-submit" aria-label="提交批注">发送</button>
        </div>
        <div class="mc-input-count">0 / 200</div>
      </div>
    `;

    document.body.appendChild(overlay);
    document.body.appendChild(drawer);

    const typeSelect = drawer.querySelector('.mc-type-select');
    COMMENT_TYPES.forEach((t) => {
      const opt = document.createElement('option');
      opt.value = t.key;
      opt.textContent = t.label;
      typeSelect.appendChild(opt);
    });

    state.els = {
      overlay,
      drawer,
      handle: drawer.querySelector('.mc-drawer-handle'),
      closeBtn: drawer.querySelector('.mc-close'),
      drawerBody: drawer.querySelector('.mc-drawer-body'),
      inputWrap: drawer.querySelector('.mc-input-wrap'),
      typeSelect,
      authorInput: drawer.querySelector('.mc-author'),
      textarea: drawer.querySelector('.mc-textarea'),
      submitBtn: drawer.querySelector('.mc-submit'),
      countEl: drawer.querySelector('.mc-input-count')
    };

    bindDrawerEvents();
    listenVisualViewport();
  }

  function bindDrawerEvents() {
    const { handle, closeBtn, textarea, submitBtn } = state.els;

    closeBtn.addEventListener('click', closeDrawer);

    // 拖拽条事件（鼠标 + 触摸）
    handle.addEventListener('mousedown', onDragMouseDown);
    handle.addEventListener('touchstart', onDragTouchStart, { passive: false });
    handle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        closeDrawer();
      }
    });

    // 全局拖拽释放
    window.addEventListener('mousemove', onDragMouseMove);
    window.addEventListener('touchmove', onDragTouchMove, { passive: false });
    window.addEventListener('mouseup', onDragEnd);
    window.addEventListener('touchend', onDragEnd);

    // 输入框自动增高、字数统计
    textarea.addEventListener('input', () => {
      autoResize();
      updateCharCount();
    });

    submitBtn.addEventListener('click', onSubmit);
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        onSubmit();
      }
    });

    // ESC 关闭
    document.addEventListener('keydown', onKeyDown);

    // 返回键关闭
    global.addEventListener('popstate', onPopState);
  }

  function onKeyDown(e) {
    if (e.key === 'Escape' && state.open) {
      e.preventDefault();
      closeDrawer();
    }
  }

  function onPopState(e) {
    if (state.open && e.state && e.state.mcDrawer) {
      closeDrawer();
    }
  }

  function pushHistory() {
    if (!state.open) return;
    try {
      global.history.pushState({ mcDrawer: true }, '');
    } catch (err) {
      // 某些环境不支持 pushState，静默忽略
    }
  }

  function popHistory() {
    try {
      if (global.history.state && global.history.state.mcDrawer) {
        global.history.back();
      }
    } catch (err) {
      // 忽略
    }
  }

  function showDrawer() {
    const { overlay, drawer } = state.els;
    drawer.style.height = `${state.panelHeight * 100}vh`;
    drawer.style.transform = '';
    requestAnimationFrame(() => {
      overlay.classList.add('open');
      drawer.classList.add('open');
      overlay.setAttribute('aria-hidden', 'false');
    });
  }

  function hideDrawer() {
    const { overlay, drawer } = state.els;
    drawer.classList.remove('open');
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    drawer.style.transform = '';
  }

  // ==================== 抽屉渲染 ====================

  function renderDrawer() {
    const pid = state.activePid;
    const { drawerBody, textarea, authorInput } = state.els;
    const paragraph = document.querySelector(pidSelector(pid));
    const quote = paragraph ? paragraph.textContent.trim().replace(/\s+/g, ' ') : '';
    const quoteShort = quote.slice(0, 80);

    drawerBody.innerHTML = '';

    // 引用原文
    const quoteEl = document.createElement('div');
    quoteEl.className = 'mc-quote';
    const mark = document.createElement('span');
    mark.className = 'mc-quote-mark';
    mark.textContent = '「';
    const quoteP = document.createElement('p');
    quoteP.textContent = quoteShort + (quote.length > 80 ? '…' : '');
    quoteEl.appendChild(mark);
    quoteEl.appendChild(quoteP);
    drawerBody.appendChild(quoteEl);

    // 评论列表
    const list = state.comments[pid] || [];
    if (list.length === 0) {
      drawerBody.appendChild(renderEmpty());
    } else {
      const listEl = document.createElement('div');
      listEl.className = 'mc-list';
      listEl.setAttribute('role', 'list');
      listEl.setAttribute('aria-label', '批注列表');
      list.forEach((c, i) => {
        listEl.appendChild(renderComment(c, i));
      });
      drawerBody.appendChild(listEl);
    }

    // 重置输入框
    textarea.value = '';
    authorInput.value = '';
    autoResize();
    updateCharCount();
  }

  function renderComment(c, index) {
    const article = document.createElement('article');
    article.className = 'mc-comment';
    article.setAttribute('role', 'listitem');
    article.style.animationDelay = `${index * 60}ms`;

    const stamp = document.createElement('div');
    stamp.className = 'mc-comment-stamp mc-stamp-' + (c.type || 'discuss');
    stamp.textContent = getTypeLabel(c.type);

    const text = document.createElement('p');
    text.className = 'mc-comment-text';
    text.textContent = c.text || c.content || '';

    const footer = document.createElement('footer');
    footer.className = 'mc-comment-meta';

    const author = document.createElement('span');
    author.className = 'mc-comment-author';
    author.textContent = c.author || '佚名';

    const time = document.createElement('time');
    time.setAttribute('datetime', c.createdAt || '');
    time.textContent = formatDate(c.createdAt);

    footer.appendChild(author);
    if (time.textContent) footer.appendChild(time);

    article.appendChild(stamp);
    article.appendChild(text);
    article.appendChild(footer);

    return article;
  }

  function renderEmpty() {
    const empty = document.createElement('div');
    empty.className = 'mc-empty';
    empty.setAttribute('role', 'status');

    const ink = document.createElement('span');
    ink.className = 'mc-empty-ink';
    ink.textContent = '此段尚无批注';

    const p = document.createElement('p');
    p.textContent = '留下第一笔';

    empty.appendChild(ink);
    empty.appendChild(p);
    return empty;
  }

  // ==================== 输入框 ====================

  function autoResize() {
    const ta = state.els.textarea;
    ta.style.height = 'auto';
    const maxH = parseFloat(getComputedStyle(ta).maxHeight) || 120;
    ta.style.height = Math.min(ta.scrollHeight, maxH) + 'px';
  }

  function updateCharCount() {
    const len = state.els.textarea.value.length;
    const max = state.config ? state.config.maxChars : DEFAULT_CONFIG.maxChars;
    state.els.countEl.textContent = `${len} / ${max}`;
  }

  async function onSubmit() {
    const content = state.els.textarea.value.trim();
    const type = state.els.typeSelect.value || 'discuss';
    const author = state.els.authorInput.value.trim() || '匿名';
    const pid = state.activePid;

    const validation = validateComment({ author, content });
    if (!validation.ok) {
      toast(validation.message);
      return;
    }

    if (!canSubmit()) {
      toast('提交太频繁，请稍后再试');
      return;
    }

    state.els.submitBtn.disabled = true;
    state.els.submitBtn.textContent = '发送中…';

    const result = await submitComment(pid, content, type, author);

    state.els.submitBtn.disabled = false;
    state.els.submitBtn.textContent = '发送';

    toast(result.message);

    if (result.ok) {
      recordSubmit();
      state.els.textarea.value = '';
      state.els.textarea.blur();
      autoResize();
      updateCharCount();
    }
  }

  // ==================== 提交到 GitHub Issues ====================

  /**
   * 提交评论到 GitHub Issues 暂存区
   * @param {string} pid - 段落 ID
   * @param {string} content - 评论内容
   * @param {string} type - 评论类型
   * @param {string} [author] - 作者昵称
   * @returns {Promise<{ok: boolean, message: string, issueUrl?: string}>}
   */
  async function submitComment(pid, content, type, author) {
    if (!state.config) {
      return { ok: false, message: '评论系统尚未初始化' };
    }
    const { owner, repo, token } = state.config;
    if (!owner || !repo || !token) {
      return { ok: false, message: '评论功能未配置，请联系管理员' };
    }

    const notePath = state.notePath || '';
    const paragraph = document.querySelector(pidSelector(pid));
    const paragraphPreview = paragraph
      ? paragraph.textContent.trim().replace(/\s+/g, ' ').slice(0, 80)
      : '';

    const title = `[段评] ${notePath} #${pid}`;
    const body = `**段落**：${paragraphPreview}${paragraphPreview.length >= 80 ? '…' : ''}\n**类型**：${getTypeLabel(type)}\n**作者**：${author || '匿名'}\n**内容**：\n\n${content}`;

    try {
      const res = await fetch(`https://api.github.com/repos/${owner}/${repo}/issues`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28'
        },
        body: JSON.stringify({
          title,
          body,
          labels: ['段评', '待审核']
        })
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        console.error('[MinimalComments] GitHub Issues API 错误:', data);
        return { ok: false, message: '提交失败，请稍后重试' };
      }

      const data = await res.json();
      return {
        ok: true,
        message: '已提交，审核后显示',
        issueUrl: data.html_url
      };
    } catch (err) {
      console.error('[MinimalComments] 提交评论失败:', err);
      return { ok: false, message: '网络问题，请稍后重试' };
    }
  }

  // ==================== 拖拽 ====================

  function onDragMouseDown(e) {
    e.preventDefault();
    onDragStart(e.clientY);
  }

  function onDragTouchStart(e) {
    e.preventDefault();
    if (e.touches && e.touches[0]) {
      onDragStart(e.touches[0].clientY);
    }
  }

  function onDragStart(y) {
    if (!state.open) return;
    state.isDragging = true;
    state.dragStartY = y;
    state.dragStartHeight = state.els.drawer.offsetHeight;
    state.els.drawer.style.transition = 'none';
  }

  function onDragMouseMove(e) {
    onDragMove(e.clientY);
  }

  function onDragTouchMove(e) {
    if (!state.isDragging) return;
    e.preventDefault();
    if (e.touches && e.touches[0]) {
      onDragMove(e.touches[0].clientY);
    }
  }

  function onDragMove(y) {
    if (!state.isDragging) return;
    const delta = state.dragStartY - y;
    const maxH = window.innerHeight * 0.8;
    const h = Math.max(120, Math.min(maxH, state.dragStartHeight + delta));
    state.els.drawer.style.height = `${h}px`;
  }

  function onDragEnd() {
    if (!state.isDragging) return;
    state.isDragging = false;
    state.els.drawer.style.transition = '';

    const ratio = state.els.drawer.offsetHeight / window.innerHeight;
    if (ratio < 0.15) {
      closeDrawer();
    } else {
      state.panelHeight = Math.min(0.8, Math.max(0.3, Math.round(ratio * 10) / 10));
      state.els.drawer.style.height = `${state.panelHeight * 100}vh`;
    }
  }

  // ==================== 软键盘适配 ====================

  function listenVisualViewport() {
    if (!global.visualViewport) return;

    const adjust = () => {
      if (!state.open) return;
      const vv = global.visualViewport;
      const drawer = state.els.drawer;
      const inputWrap = state.els.inputWrap;

      const drawerBottom = drawer.getBoundingClientRect().bottom;
      const inputBottom = inputWrap.getBoundingClientRect().bottom;

      if (inputBottom > vv.height) {
        const offset = inputBottom - vv.height + 16;
        drawer.style.transform = `translateY(-${offset}px)`;
      } else if (drawerBottom > vv.height) {
        const offset = drawerBottom - vv.height;
        drawer.style.transform = `translateY(-${offset}px)`;
      } else {
        drawer.style.transform = '';
      }
    };

    global.visualViewport.addEventListener('resize', adjust);
    global.visualViewport.addEventListener('scroll', adjust);
  }

  // ==================== 焦点陷阱 ====================

  function trapFocus() {
    const drawer = state.els.drawer;
    const focusable = drawer.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable.length) return;

    const focusables = Array.from(focusable);
    state.previouslyFocused = document.activeElement;
    focusables[0].focus();

    state.focusTrapHandler = (e) => {
      if (e.key !== 'Tab') return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', state.focusTrapHandler);
  }

  function releaseFocus() {
    if (state.focusTrapHandler) {
      document.removeEventListener('keydown', state.focusTrapHandler);
      state.focusTrapHandler = null;
    }
    if (state.previouslyFocused && typeof state.previouslyFocused.focus === 'function') {
      state.previouslyFocused.focus();
    }
  }

  // ==================== Toast ====================

  /**
   * 显示简短提示
   * @param {string} msg
   */
  function toast(msg) {
    let toastEl = document.getElementById('mc-toast');
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.id = 'mc-toast';
      toastEl.className = 'mc-toast';
      toastEl.setAttribute('role', 'status');
      toastEl.setAttribute('aria-live', 'polite');
      document.body.appendChild(toastEl);
    }

    toastEl.textContent = msg;
    toastEl.classList.add('show');

    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(() => {
      toastEl.classList.remove('show');
    }, 2200);
  }

  // ==================== 暴露 API ====================

  global.MinimalComments = {
    init,
    injectParagraphIds,
    loadComments,
    renderBadges,
    openDrawer,
    closeDrawer,
    submitComment,
    toast
  };
})(window);
