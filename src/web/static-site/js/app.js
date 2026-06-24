(function () {
    'use strict';

    const SETTINGS_KEY = 'reader-settings';
    const DEFAULT_SETTINGS = {
        theme: 'day',
        font: 'serif',
        fontSize: 18,
        lineHeight: 1.9,
        paragraphSpacing: 1.0,
        wallpaper: 'none',
        wallpaperOpacity: 0.6,
        pageMode: 'tap',
        autoScroll: false,
        autoScrollSpeed: 50
    };

    // 本地缓存键
    const CACHE_PREFIX = 'halo-';
    const CACHE_VERSION = 'v1';
    const INDEX_CACHE_KEY = CACHE_PREFIX + 'index';
    const INDEX_META_KEY = CACHE_PREFIX + 'index-meta';
    const SEARCH_CACHE_KEY = CACHE_PREFIX + 'search-index';
    const SEARCH_META_KEY = CACHE_PREFIX + 'search-meta';
    const NOTE_CACHE_PREFIX = CACHE_PREFIX + 'note-';
    const MAX_CACHED_NOTES = 50;

    const state = {
        booksData: [],
        categories: [],
        treeData: [],
        notesIndex: {},
        flatNotes: [],
        currentView: 'home', // 'home' | 'reader'
        currentBook: null,
        currentBookTree: [],
        activePath: null,
        searchQuery: '',
        selectedCategory: 'all',
        bookshelfQuery: '',
        searchMode: false,
        searchIndexLoaded: false,
        searchNotes: []
    };

    const elements = {
        homeView: document.getElementById('homeView'),
        readerView: document.getElementById('readerView'),
        bookshelfGrid: document.getElementById('bookshelfGrid'),
        categoryTabs: document.getElementById('categoryTabs'),
        bookshelfSearchInput: document.getElementById('bookshelfSearchInput'),
        heroStats: document.getElementById('heroStats'),
        treeNav: document.getElementById('treeNav'),
        reader: document.getElementById('reader'),
        readerWallpaper: document.querySelector('.reader-wallpaper'),
        backBtn: document.getElementById('backBtn'),
        currentBookTitle: document.getElementById('currentBookTitle'),
        newNoteBtn: document.getElementById('newNoteBtn'),
        newNoteLink: document.getElementById('newNoteLink'),
        newNoteBtnToolbar: document.getElementById('newNoteBtnToolbar'),
        searchInput: document.getElementById('searchInput'),
        refreshBtn: document.getElementById('refreshBtn'),
        menuBtn: document.getElementById('menuBtn'),
        sidebar: document.querySelector('.reader-view .sidebar'),
        sidebarOverlay: document.getElementById('sidebarOverlay'),
        toolbarChapter: document.getElementById('toolbarChapter'),
        settingsBtn: document.getElementById('settingsBtn'),
        settingsBtnBottom: document.getElementById('settingsBtnBottom'),
        settingsPanel: document.getElementById('settingsPanel'),
        settingsOverlay: document.getElementById('settingsOverlay'),
        settingsClose: document.getElementById('settingsClose'),
        fontBtns: document.getElementById('fontBtns'),
        themeBtns: document.getElementById('themeBtns'),
        fontSizeRange: document.getElementById('fontSizeRange'),
        fontSizeVal: document.getElementById('fontSizeVal'),
        lineHeightRange: document.getElementById('lineHeightRange'),
        lineHeightVal: document.getElementById('lineHeightVal'),
        paragraphSpacingRange: document.getElementById('paragraphSpacingRange'),
        paragraphSpacingVal: document.getElementById('paragraphSpacingVal'),
        resetSettingsBtn: document.getElementById('resetSettingsBtn'),
        prevBtnBottom: document.getElementById('prevBtnBottom'),
        nextBtnBottom: document.getElementById('nextBtnBottom'),
        tocBtnBottom: document.getElementById('tocBtnBottom'),
        modalOverlay: document.getElementById('modalOverlay'),
        modalClose: document.getElementById('modalClose'),
        cancelBtn: document.getElementById('cancelBtn'),
        immersiveBtn: document.getElementById('immersiveBtn'),
        wallpaperBtns: document.getElementById('wallpaperBtns'),
        wallpaperOpacityRange: document.getElementById('wallpaperOpacityRange'),
        wallpaperOpacityVal: document.getElementById('wallpaperOpacityVal'),
        pageModeBtns: document.getElementById('pageModeBtns'),
        autoScrollBtns: document.getElementById('autoScrollBtns'),
        autoScrollSpeedRange: document.getElementById('autoScrollSpeedRange'),
        autoScrollSpeedVal: document.getElementById('autoScrollSpeedVal')
    };

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function sanitizeHtml(html) {
        html = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        html = html.replace(/\son\w+\s*=\s*"[^"]*"/gi, '');
        html = html.replace(/\son\w+\s*=\s*'[^']*'/gi, '');
        html = html.replace(/\son\w+\s*=\s*[^\s>]+/gi, '');
        return html;
    }

    function showError(message, err) {
        console.error(message, err || '');
        alert(message);
    }

    /* ============ 本地缓存工具 ============ */
    function getCachedJson(key) {
        try {
            const raw = localStorage.getItem(key);
            return raw ? JSON.parse(raw) : null;
        } catch (err) {
            return null;
        }
    }

    function setCachedJson(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (err) {
            // 存储配额不足时静默失败
        }
    }

    function getCachedText(key) {
        try {
            return localStorage.getItem(key);
        } catch (err) {
            return null;
        }
    }

    function setCachedText(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (err) {
            // 存储配额不足时静默失败
        }
    }

    function clearOutdatedCache() {
        const versionKey = CACHE_PREFIX + 'cache-version';
        try {
            const stored = localStorage.getItem(versionKey);
            if (stored === CACHE_VERSION) return;
        } catch (err) {
            return;
        }
        for (let i = localStorage.length - 1; i >= 0; i--) {
            const key = localStorage.key(i);
            if (key && key.startsWith(CACHE_PREFIX)) {
                localStorage.removeItem(key);
            }
        }
        try {
            localStorage.setItem(versionKey, CACHE_VERSION);
        } catch (err) {
            // ignore
        }
    }

    function cleanupNoteCache(maxCount) {
        const entries = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith(NOTE_CACHE_PREFIX) && !key.endsWith('-meta')) {
                const meta = getCachedJson(key + '-meta') || {};
                entries.push({ key: key, loadedAt: meta.loaded_at || 0 });
            }
        }
        if (entries.length <= maxCount) return;
        entries.sort((a, b) => a.loadedAt - b.loadedAt);
        entries.slice(0, entries.length - maxCount).forEach((item) => {
            localStorage.removeItem(item.key);
            localStorage.removeItem(item.key + '-meta');
        });
    }

    async function loadCachedThenFetch(url, cacheKey, metaKey, onData) {
        const cached = getCachedJson(cacheKey);
        const meta = getCachedJson(metaKey);

        // 有缓存先渲染，后台静默更新
        if (cached && meta && meta.generated_at) {
            onData(cached);
        }

        try {
            const data = await fetchJson(url, { cache: 'no-cache' });
            setCachedJson(cacheKey, data);
            setCachedJson(metaKey, {
                version: data.version || '',
                generated_at: data.generated_at || ''
            });
            // 只有数据变化才再次触发渲染，避免闪烁
            if (!cached || meta?.generated_at !== data.generated_at) {
                onData(data);
            }
            return data;
        } catch (err) {
            if (cached) {
                console.warn('[豪书斋] 网络请求失败，使用缓存数据:', url, err);
                return cached;
            }
            throw err;
        }
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
            const detail = await response.text().catch(() => '');
            throw new Error(`请求失败 (${response.status}): ${detail || response.statusText}`);
        }
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return await response.json();
        }
        return await response.text();
    }

    function flattenTree(nodes) {
        const result = [];
        function walk(list) {
            if (!list) return;
            for (const node of list) {
                if (Array.isArray(node.children) && node.children.length > 0) {
                    walk(node.children);
                } else if (node.path) {
                    result.push(node);
                }
            }
        }
        walk(nodes);
        return result;
    }

    function nodeMatches(node, query) {
        const text = (node.title || '').toLowerCase();
        return text.includes(query);
    }

    function filterTree(nodes, query) {
        if (!query) return nodes;
        const result = [];
        for (const node of nodes) {
            const children = node.children ? filterTree(node.children, query) : [];
            const matched = nodeMatches(node, query);
            if (matched || children.length > 0) {
                const clone = Object.assign({}, node);
                if (children.length > 0) {
                    clone.children = children;
                }
                result.push(clone);
            }
        }
        return result;
    }

    function expandMatchedNodes(container) {
        if (!state.searchQuery) return;
        const matchedLeaves = container.querySelectorAll('.tree-leaf');
        matchedLeaves.forEach((leaf) => {
            let parent = leaf.closest('.tree-node');
            while (parent) {
                parent.classList.add('expanded');
                parent = parent.parentElement.closest('.tree-node');
            }
        });
    }

    function getNodeIcon(node, isLeaf) {
        if (isLeaf) return '📝';
        if (node.type === 'book') return '📖';
        if (node.type === 'chapter') return '📑';
        return '📁';
    }

    function renderTree(nodes, depth = 0) {
        if (!nodes || nodes.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = '暂无笔记';
            return empty;
        }
        const ul = document.createElement('ul');
        ul.className = 'tree-list';

        nodes.forEach((node) => {
            const hasChildren = Array.isArray(node.children) && node.children.length > 0;
            const li = document.createElement('li');
            li.className = 'tree-node' + (hasChildren ? ' expanded' : '');
            li.dataset.depth = String(depth);

            const icon = getNodeIcon(node, !hasChildren);
            const title = escapeHtml(node.title || '未命名');

            if (hasChildren) {
                const toggle = document.createElement('button');
                toggle.className = 'tree-toggle';
                toggle.type = 'button';
                toggle.innerHTML = `<span class="tree-arrow" aria-hidden="true">▶</span><span class="tree-icon">${icon}</span><span>${title}</span>`;
                toggle.addEventListener('click', () => {
                    li.classList.toggle('expanded');
                });
                li.appendChild(toggle);

                const childrenContainer = document.createElement('ul');
                childrenContainer.className = 'tree-children';
                childrenContainer.appendChild(renderTree(node.children, depth + 1));
                li.appendChild(childrenContainer);
            } else {
                const leaf = document.createElement('button');
                leaf.className = 'tree-leaf';
                leaf.type = 'button';
                leaf.dataset.path = node.path || '';
                leaf.innerHTML = `<span class="tree-icon">${icon}</span><span>${title}</span>`;
                leaf.addEventListener('click', () => {
                    loadNote(node.path, leaf);
                    closeSidebar();
                });
                if (state.activePath && state.activePath === node.path) {
                    leaf.classList.add('active');
                }
                li.appendChild(leaf);
            }

            ul.appendChild(li);
        });

        return ul;
    }

    function refreshTreeView() {
        const filtered = filterTree(state.currentBookTree, state.searchQuery);
        const rendered = renderTree(filtered);
        elements.treeNav.innerHTML = '';
        elements.treeNav.appendChild(rendered);
        expandMatchedNodes(elements.treeNav);
    }

    /* ============ 首页 / 书架 ============ */
    function renderHeroStats(stats) {
        if (!stats) {
            elements.heroStats.innerHTML = '<span>正在统计书目…</span>';
            return;
        }
        elements.heroStats.innerHTML = `
            <div class="stat"><span class="stat-value">${stats.books || 0}</span><span class="stat-label">部典籍</span></div>
            <div class="stat"><span class="stat-value">${stats.notes || 0}</span><span class="stat-label">篇笔记</span></div>
            <div class="stat"><span class="stat-value">${stats.categories || 0}</span><span class="stat-label">个分类</span></div>
        `;
    }

    function renderCategoryTabs() {
        const container = elements.categoryTabs;
        container.innerHTML = '';

        const allBtn = document.createElement('button');
        allBtn.className = 'category-tab' + (state.selectedCategory === 'all' ? ' active' : '');
        allBtn.textContent = '全部';
        allBtn.dataset.category = 'all';
        allBtn.type = 'button';
        allBtn.role = 'tab';
        allBtn.setAttribute('aria-selected', state.selectedCategory === 'all' ? 'true' : 'false');
        allBtn.addEventListener('click', () => selectCategory('all'));
        container.appendChild(allBtn);

        state.categories.forEach((cat) => {
            const btn = document.createElement('button');
            btn.className = 'category-tab' + (state.selectedCategory === cat ? ' active' : '');
            btn.textContent = cat;
            btn.dataset.category = cat;
            btn.type = 'button';
            btn.role = 'tab';
            btn.setAttribute('aria-selected', state.selectedCategory === cat ? 'true' : 'false');
            btn.addEventListener('click', () => selectCategory(cat));
            container.appendChild(btn);
        });
    }

    function selectCategory(category) {
        state.selectedCategory = category;
        renderCategoryTabs();
        renderBookshelf();
    }

    function filterBooks() {
        let books = state.booksData;

        if (state.selectedCategory !== 'all') {
            books = books.filter((book) => book.category === state.selectedCategory);
        }

        const query = state.bookshelfQuery.trim().toLowerCase();
        if (query) {
            books = books.filter((book) => {
                const title = (book.title || '').toLowerCase();
                const author = (book.author || '').toLowerCase();
                const category = (book.category || '').toLowerCase();
                const description = (book.description || '').toLowerCase();
                return title.includes(query) || author.includes(query) || category.includes(query) || description.includes(query);
            });
        }

        return books;
    }

    function renderBookshelf() {
        const container = elements.bookshelfGrid;
        container.innerHTML = '';

        const books = filterBooks();

        if (books.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = state.bookshelfQuery ? '未找到匹配的书籍' : '书架暂无书籍';
            container.appendChild(empty);
            return;
        }

        books.forEach((book) => {
            const card = document.createElement('button');
            card.className = 'book-card';
            card.type = 'button';
            card.dataset.bookId = book.id;

            const cover = document.createElement('div');
            cover.className = 'book-cover';
            cover.textContent = book.cover || '📖';
            card.appendChild(cover);

            const info = document.createElement('div');
            info.className = 'book-info';

            const category = document.createElement('div');
            category.className = 'book-category';
            category.textContent = book.category || '未分类';
            info.appendChild(category);

            const title = document.createElement('div');
            title.className = 'book-title';
            title.textContent = book.title || book.id;
            info.appendChild(title);

            if (book.author) {
                const author = document.createElement('div');
                author.className = 'book-author';
                author.textContent = book.author;
                info.appendChild(author);
            }

            if (book.description) {
                const desc = document.createElement('div');
                desc.className = 'book-description';
                desc.textContent = book.description;
                info.appendChild(desc);
            }

            const stats = document.createElement('div');
            stats.className = 'book-stats';
            stats.textContent = `章节 ${book.chapter_count || 0} · 笔记 ${book.note_count || 0}`;
            info.appendChild(stats);

            card.appendChild(info);
            card.addEventListener('click', () => openBook(book.id));
            container.appendChild(card);
        });
    }

    function handleBookshelfSearch(event) {
        state.bookshelfQuery = event.target.value;
        renderBookshelf();
    }

    /* ============ 视图切换 ============ */
    function switchView(view) {
        state.currentView = view;
        document.body.dataset.view = view;
        if (view === 'home') {
            pauseAutoScroll();
            // 返回首页时退出沉浸模式，避免 immersive-mode 影响 home 视图布局
            if (document.body.classList.contains('immersive-mode')) {
                exitImmersiveMode();
            }
            elements.homeView.hidden = false;
            elements.readerView.hidden = true;
            document.body.style.overflow = '';
            if (elements.immersiveBtn) elements.immersiveBtn.hidden = true;
        } else {
            elements.homeView.hidden = true;
            elements.readerView.hidden = false;
            document.body.style.overflow = 'hidden';
            // 沉浸按钮在阅读视图可见（所有环境，不限于魔搭嵌入）
            if (elements.immersiveBtn) elements.immersiveBtn.hidden = false;
        }
    }

    function openBook(bookId) {
        const book = state.booksData.find((b) => b.id === bookId);
        if (!book) {
            const bookNode = state.treeData.find((b) => b.title === bookId);
            if (!bookNode) return;
            state.currentBook = bookId;
            state.currentBookTree = [bookNode];
        } else {
            state.currentBook = bookId;
            state.currentBookTree = book.tree || [];
        }
        state.activePath = null;

        switchView('reader');
        if (elements.currentBookTitle) {
            elements.currentBookTitle.textContent = (book && book.title) || bookId;
        }
        elements.reader.innerHTML = '<div class="reader-placeholder"><p>正在加载…</p></div>';
        refreshTreeView();

        // 优先跳转到缓存页，无缓存则打开第一章
        const cachedPath = getCachedPosition(bookId);
        const bookNotes = flattenTree(state.currentBookTree);
        if (cachedPath && bookNotes.some((n) => n.path === cachedPath)) {
            loadNote(cachedPath);
        } else if (bookNotes.length > 0) {
            loadNote(bookNotes[0].path);
        }
    }

    function backToHome() {
        state.currentBook = null;
        state.currentBookTree = [];
        state.activePath = null;
        state.searchQuery = '';
        if (elements.searchInput) elements.searchInput.value = '';
        // 返回书架时强制关闭所有遮罩层，避免 sidebar/settings/modal 的蒙层残留在首页
        closeSidebar();
        closeSettings();
        closeModal();
        switchView('home');
        renderBookshelf();
    }

    /* ============ 笔记加载 ============ */
    function parseFrontmatter(content) {
        const match = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n*/);
        if (!match) return { meta: null, body: content };
        const metaBlock = match[1];
        const body = content.slice(match[0].length);
        const meta = {};
        metaBlock.split('\n').forEach((line) => {
            const idx = line.indexOf(':');
            if (idx === -1) return;
            const key = line.slice(0, idx).trim();
            const value = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
            if (key) meta[key] = value;
        });
        return { meta, body };
    }

    function buildMetaHtml(meta) {
        if (!meta || (!meta.title && !meta.created_at)) return '';
        let html = '<div class="note-meta">';
        if (meta.title) html += `<span class="note-meta-title">${escapeHtml(meta.title)}</span>`;
        if (meta.book || meta.chapter) {
            html += `<span class="note-meta-path">${escapeHtml([meta.book, meta.chapter].filter(Boolean).join(' / '))}</span>`;
        }
        if (meta.created_at) html += `<span class="note-meta-date">${escapeHtml(meta.created_at)}</span>`;
        html += '</div>';
        return html;
    }

    function buildChapterNavHtml(prevNode, nextNode) {
        const prevDisabled = prevNode ? '' : 'disabled';
        const nextDisabled = nextNode ? '' : 'disabled';
        const prevLabel = prevNode ? `上一章 · ${escapeHtml(prevNode.title || '')}` : '已是第一章';
        const nextLabel = nextNode ? `下一章 · ${escapeHtml(nextNode.title || '')}` : '已是最后一章';
        return `<nav class="chapter-nav">` +
            `<button type="button" class="chapter-btn prev" id="prevChapterBtn" ${prevDisabled}>${prevLabel}</button>` +
            `<button type="button" class="chapter-btn next" id="nextChapterBtn" ${nextDisabled}>${nextLabel}</button>` +
            `</nav>`;
    }

    function updateChapterNav() {
        const list = state.flatNotes;
        const idx = list.findIndex((n) => n.path === state.activePath);
        const prev = idx > 0 ? list[idx - 1] : null;
        const next = idx >= 0 && idx < list.length - 1 ? list[idx + 1] : null;

        const prevBtn = document.getElementById('prevChapterBtn');
        const nextBtn = document.getElementById('nextChapterBtn');
        if (prevBtn) {
            prevBtn.disabled = !prev;
            prevBtn.textContent = prev ? `上一章 · ${prev.title || ''}` : '已是第一章';
        }
        if (nextBtn) {
            nextBtn.disabled = !next;
            nextBtn.textContent = next ? `下一章 · ${next.title || ''}` : '已是最后一章';
        }

        if (elements.prevBtnBottom) {
            elements.prevBtnBottom.disabled = !prev;
        }
        if (elements.nextBtnBottom) {
            elements.nextBtnBottom.disabled = !next;
        }
    }

    function bindChapterNavButtons() {
        const prevBtn = document.getElementById('prevChapterBtn');
        const nextBtn = document.getElementById('nextChapterBtn');
        if (prevBtn) {
            prevBtn.addEventListener('click', goPrevChapter);
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', goNextChapter);
        }
    }

    function goPrevChapter() {
        const idx = state.flatNotes.findIndex((n) => n.path === state.activePath);
        if (idx > 0) {
            pauseAutoScroll();
            loadNote(state.flatNotes[idx - 1].path);
        }
    }

    function goNextChapter() {
        const idx = state.flatNotes.findIndex((n) => n.path === state.activePath);
        if (idx >= 0 && idx < state.flatNotes.length - 1) {
            pauseAutoScroll();
            loadNote(state.flatNotes[idx + 1].path);
        }
    }

    async function loadNote(path, targetElement) {
        if (!path) return;
        pauseAutoScroll();
        state.activePath = path;

        const allLeaves = elements.treeNav.querySelectorAll('.tree-leaf');
        allLeaves.forEach((leaf) => leaf.classList.remove('active'));
        if (targetElement) {
            targetElement.classList.add('active');
        } else {
            const match = elements.treeNav.querySelector(`.tree-leaf[data-path="${CSS.escape(path)}"]`);
            if (match) match.classList.add('active');
        }

        elements.reader.innerHTML = '<div class="reader-placeholder">正在加载笔记…</div>';
        elements.reader.scrollTop = 0;
        try {
            const content = await fetchJson('notes/' + encodeURI(path));
            const { meta, body } = parseFrontmatter(content || '');
            const html = sanitizeHtml(marked.parse(body, { gfm: true }));
            const metaHtml = buildMetaHtml(meta);

            const idx = state.flatNotes.findIndex((n) => n.path === path);
            const prev = idx > 0 ? state.flatNotes[idx - 1] : null;
            const next = idx >= 0 && idx < state.flatNotes.length - 1 ? state.flatNotes[idx + 1] : null;
            const navHtml = buildChapterNavHtml(prev, next);

            elements.reader.innerHTML = `<div class="reader-wallpaper" aria-hidden="true"></div><article class="markdown-body">${metaHtml}${html}</article>${navHtml}`;
            // 重新获取壁纸层引用（innerHTML 会重建 DOM）
            elements.readerWallpaper = elements.reader.querySelector('.reader-wallpaper');
            bindChapterNavButtons();
            updateReaderWallpaperHeight();

            if (elements.toolbarChapter) {
                const chapterText = meta && meta.title ? meta.title : (state.flatNotes[idx] && state.flatNotes[idx].title) || '';
                elements.toolbarChapter.textContent = chapterText;
            }
            updateChapterNav();

            // 缓存当前阅读位置
            if (state.currentBook) {
                saveCachedPosition(state.currentBook, path);
            }
        } catch (err) {
            elements.reader.innerHTML = '<div class="reader-placeholder">加载失败，请重试。</div>';
            showError('无法加载笔记内容。', err);
        }
    }

    /* ============ 数据加载（静态站点） ============ */
    function applyIndexData(data) {
        state.booksData = data.books || [];
        state.categories = data.categories || [];
        state.treeData = data.tree || [];
        state.flatNotes = flattenTree(state.treeData);
        state.searchMode = false;
    }

    async function loadIndex() {
        try {
            await loadCachedThenFetch(
                'data/index.json',
                INDEX_CACHE_KEY,
                INDEX_META_KEY,
                (data) => {
                    applyIndexData(data);
                    renderHeroStats(data.stats);
                    renderCategoryTabs();
                    renderBookshelf();
                    updateChapterNav();
                }
            );
        } catch (err) {
            elements.bookshelfGrid.innerHTML = '';
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = '加载书架失败';
            elements.bookshelfGrid.appendChild(empty);
            showError('无法加载书架数据，请检查 data/index.json 是否存在。', err);
        }
    }

    async function loadTree() {
        try {
            await loadCachedThenFetch(
                'data/index.json',
                INDEX_CACHE_KEY,
                INDEX_META_KEY,
                (data) => {
                    applyIndexData(data);
                    if (state.currentBook) {
                        const bookNode = state.treeData.find((b) => b.title === state.currentBook);
                        state.currentBookTree = bookNode ? [bookNode] : state.treeData;
                    } else {
                        state.currentBookTree = state.treeData;
                    }
                    refreshTreeView();
                    updateChapterNav();
                }
            );
        } catch (err) {
            showError('无法加载笔记目录，请检查 data/index.json 是否存在。', err);
        }
    }

    async function ensureSearchIndex() {
        if (state.searchIndexLoaded) return state.searchNotes;
        await loadCachedThenFetch(
            'data/search-index.json',
            SEARCH_CACHE_KEY,
            SEARCH_META_KEY,
            (data) => {
                state.searchNotes = data.notes || [];
                state.searchIndexLoaded = true;
            }
        );
        if (!state.searchIndexLoaded) {
            state.searchNotes = [];
            state.searchIndexLoaded = true;
        }
        return state.searchNotes;
    }

    /* ============ 阅读设置 ============ */
    const VALID_WALLPAPERS = ['none', 'bamboo', 'landscape'];

    function normalizeSettings(settings) {
        const s = Object.assign({}, settings);
        // 已删除的壁纸回退到无
        if (!VALID_WALLPAPERS.includes(s.wallpaper)) {
            s.wallpaper = 'none';
        }
        return s;
    }

    function loadSettings() {
        try {
            const raw = localStorage.getItem(SETTINGS_KEY);
            if (!raw) return Object.assign({}, DEFAULT_SETTINGS);
            const parsed = JSON.parse(raw);
            return normalizeSettings(Object.assign({}, DEFAULT_SETTINGS, parsed));
        } catch (err) {
            return Object.assign({}, DEFAULT_SETTINGS);
        }
    }

    function saveSettings(settings) {
        try {
            localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
        } catch (err) {
            // 存储失败时静默处理
        }
    }

    /* ============ 阅读位置缓存 ============ */
    function getCachedPosition(bookId) {
        try {
            return localStorage.getItem('reader-position-' + bookId);
        } catch (err) {
            return null;
        }
    }

    function saveCachedPosition(bookId, path) {
        try {
            if (bookId && path) {
                localStorage.setItem('reader-position-' + bookId, path);
            }
        } catch (err) {
            // 存储失败时静默处理
        }
    }

    function applySettings(settings) {
        const s = normalizeSettings(settings);
        document.body.setAttribute('data-theme', s.theme);
        document.body.setAttribute('data-font', s.font);
        document.body.setAttribute('data-wallpaper', s.wallpaper);
        document.body.setAttribute('data-page-mode', s.pageMode);
        document.documentElement.style.setProperty('--reader-font-size', s.fontSize + 'px');
        document.documentElement.style.setProperty('--reader-line-height', String(s.lineHeight));
        document.documentElement.style.setProperty('--reader-paragraph-spacing', s.paragraphSpacing + 'em');
        document.documentElement.style.setProperty('--reader-wallpaper-opacity', String(s.wallpaperOpacity));

        if (elements.fontSizeRange) elements.fontSizeRange.value = s.fontSize;
        if (elements.lineHeightRange) elements.lineHeightRange.value = s.lineHeight;
        if (elements.paragraphSpacingRange) elements.paragraphSpacingRange.value = s.paragraphSpacing;
        if (elements.fontSizeVal) elements.fontSizeVal.textContent = s.fontSize + 'px';
        if (elements.lineHeightVal) elements.lineHeightVal.textContent = s.lineHeight;
        if (elements.paragraphSpacingVal) elements.paragraphSpacingVal.textContent = s.paragraphSpacing.toFixed(1) + 'em';
        if (elements.wallpaperOpacityRange) elements.wallpaperOpacityRange.value = s.wallpaperOpacity;
        if (elements.wallpaperOpacityVal) elements.wallpaperOpacityVal.textContent = s.wallpaperOpacity.toFixed(1);
        if (elements.autoScrollSpeedRange) elements.autoScrollSpeedRange.value = s.autoScrollSpeed;
        if (elements.autoScrollSpeedVal) elements.autoScrollSpeedVal.textContent = String(s.autoScrollSpeed);

        if (elements.fontBtns) {
            elements.fontBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.font === s.font);
            });
        }
        if (elements.themeBtns) {
            elements.themeBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.theme === s.theme);
            });
        }
        if (elements.wallpaperBtns) {
            elements.wallpaperBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.wallpaper === s.wallpaper);
            });
        }
        if (elements.pageModeBtns) {
            elements.pageModeBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.pageMode === s.pageMode);
            });
        }
        if (elements.autoScrollBtns) {
            elements.autoScrollBtns.querySelectorAll('button').forEach((btn) => {
                const isActive = (btn.dataset.autoScroll === 'true') === Boolean(s.autoScroll);
                btn.classList.toggle('active', isActive);
            });
        }
        updateReaderWallpaperHeight();
    }

    function updateReaderWallpaperHeight() {
        if (!elements.readerWallpaper || !elements.reader) return;
        // 让壁纸层高度始终等于阅读区滚动内容高度，保证长文壁纸铺满
        elements.readerWallpaper.style.height = elements.reader.scrollHeight + 'px';
    }

    function openSettings() {
        pauseAutoScroll();
        elements.settingsPanel.classList.add('open');
        elements.settingsPanel.setAttribute('aria-hidden', 'false');
        elements.settingsOverlay.classList.add('open');
    }

    function closeSettings() {
        elements.settingsPanel.classList.remove('open');
        elements.settingsPanel.setAttribute('aria-hidden', 'true');
        elements.settingsOverlay.classList.remove('open');
    }

    function initSettings() {
        const settings = loadSettings();
        applySettings(settings);

        if (elements.settingsBtn) {
            elements.settingsBtn.addEventListener('click', openSettings);
        }
        if (elements.settingsBtnBottom) {
            elements.settingsBtnBottom.addEventListener('click', openSettings);
        }
        if (elements.settingsClose) {
            elements.settingsClose.addEventListener('click', closeSettings);
        }
        if (elements.settingsOverlay) {
            elements.settingsOverlay.addEventListener('click', closeSettings);
        }

        if (elements.fontBtns) {
            elements.fontBtns.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-font]');
                if (!btn) return;
                const s = loadSettings();
                s.font = btn.dataset.font;
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.themeBtns) {
            elements.themeBtns.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-theme]');
                if (!btn) return;
                const s = loadSettings();
                s.theme = btn.dataset.theme;
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.fontSizeRange) {
            elements.fontSizeRange.addEventListener('input', (e) => {
                const s = loadSettings();
                s.fontSize = parseInt(e.target.value, 10);
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.lineHeightRange) {
            elements.lineHeightRange.addEventListener('input', (e) => {
                const s = loadSettings();
                s.lineHeight = parseFloat(e.target.value);
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.paragraphSpacingRange) {
            elements.paragraphSpacingRange.addEventListener('input', (e) => {
                const s = loadSettings();
                s.paragraphSpacing = parseFloat(e.target.value);
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.wallpaperBtns) {
            elements.wallpaperBtns.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-wallpaper]');
                if (!btn) return;
                const s = loadSettings();
                s.wallpaper = btn.dataset.wallpaper;
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.wallpaperOpacityRange) {
            elements.wallpaperOpacityRange.addEventListener('input', (e) => {
                const s = loadSettings();
                s.wallpaperOpacity = parseFloat(e.target.value);
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.pageModeBtns) {
            elements.pageModeBtns.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-page-mode]');
                if (!btn) return;
                const s = loadSettings();
                s.pageMode = btn.dataset.pageMode;
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.autoScrollSpeedRange) {
            elements.autoScrollSpeedRange.addEventListener('input', (e) => {
                const s = loadSettings();
                s.autoScrollSpeed = parseInt(e.target.value, 10);
                saveSettings(s);
                applySettings(s);
            });
        }

        if (elements.autoScrollBtns) {
            elements.autoScrollBtns.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-auto-scroll]');
                if (!btn) return;
                const s = loadSettings();
                s.autoScroll = btn.dataset.autoScroll === 'true';
                saveSettings(s);
                applySettings(s);
                if (s.autoScroll) {
                    startAutoScroll();
                } else {
                    pauseAutoScroll();
                }
            });
        }

        if (elements.resetSettingsBtn) {
            elements.resetSettingsBtn.addEventListener('click', () => {
                pauseAutoScroll();
                saveSettings(DEFAULT_SETTINGS);
                applySettings(DEFAULT_SETTINGS);
            });
        }
    }

    /* ============ 移动端抽屉 ============ */
    function openSidebar() {
        if (!elements.sidebar) return;
        elements.sidebar.classList.add('open');
        if (elements.sidebarOverlay) elements.sidebarOverlay.classList.add('open');
    }

    function closeSidebar() {
        if (!elements.sidebar) return;
        elements.sidebar.classList.remove('open');
        if (elements.sidebarOverlay) elements.sidebarOverlay.classList.remove('open');
    }

    function initSidebarDrawer() {
        if (elements.menuBtn) {
            elements.menuBtn.addEventListener('click', openSidebar);
        }
        if (elements.tocBtnBottom) {
            elements.tocBtnBottom.addEventListener('click', openSidebar);
        }
        if (elements.sidebarOverlay) {
            elements.sidebarOverlay.addEventListener('click', closeSidebar);
        }
    }

    /* ============ 翻页交互（点击分区 + 滑动） ============ */
    // 模块级标志：touch 触发的轻点已处理时，阻止后续 click 重复触发
    let tapHandledByTouch = false;
    // touchstart 起点信息，用于 touchend 判断轻点 vs 滑动
    let touchStartInfo = null;
    const TAP_MOVE_THRESHOLD = 10; // 位移阈值（px）
    const TAP_TIME_THRESHOLD = 300; // 时长阈值（ms）

    // 是否应排除当前点击目标（链接/按钮/输入/弹层打开/文字选中）
    function shouldExcludeTap(target) {
        if (!target) return true;
        const tag = target.tagName;
        if (tag === 'A' || tag === 'BUTTON' || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
            return true;
        }
        // 排除书架卡片、目录叶子、章末导航按钮、搜索结果、代码块等可交互/可滚动元素
        if (target.closest('a, button, input, textarea, select, pre, code, .book-card, .tree-leaf, .chapter-btn, .search-result-title')) {
            return true;
        }
        // 弹层打开时不翻页
        if (elements.settingsPanel && elements.settingsPanel.classList.contains('open')) return true;
        if (elements.sidebar && elements.sidebar.classList.contains('open')) return true;
        if (elements.modalOverlay && elements.modalOverlay.classList.contains('open')) return true;
        // 文字选中时不翻页
        try {
            if (window.getSelection && window.getSelection().toString()) return true;
        } catch (err) {
            // 跨域 iframe 可能抛错，忽略
        }
        return false;
    }

    // 翻页：滚动一屏的 85%
    function pageByDirection(direction) {
        if (!elements.reader) return;
        const distance = elements.reader.clientHeight * 0.85;
        const top = direction === 'prev' ? -distance : distance;
        const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        elements.reader.scrollBy({
            top: top,
            behavior: prefersReduced ? 'auto' : 'smooth'
        });
    }

    // 统一点击处理入口
    function handleReaderTap(e) {
        if (!elements.reader) return;
        // 仅阅读视图响应
        if (state.currentView !== 'reader') return;
        if (shouldExcludeTap(e.target)) return;

        const isMobile = window.innerWidth <= 768;
        const rect = elements.reader.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const width = rect.width;

        if (isMobile) {
            // 移动端：左 25% 上一屏、中 50% 切换 UI、右 25% 下一屏
            if (x < width * 0.25) {
                pauseAutoScroll();
                pageByDirection('prev');
            } else if (x > width * 0.75) {
                pauseAutoScroll();
                pageByDirection('next');
            } else {
                document.body.classList.toggle('ui-hidden');
            }
        } else {
            // 桌面端：仅中央点击切换 UI（沿用原行为，避免破坏桌面阅读体验）
            const vh = window.innerHeight;
            const y = e.clientY;
            if (y < vh * 0.35 || y > vh * 0.65) return;
            document.body.classList.toggle('ui-hidden');
        }
    }

    function initReaderTap() {
        if (!elements.reader) return;

        // click 统一入口（桌面端主要走这里）
        elements.reader.addEventListener('click', (e) => {
            if (tapHandledByTouch) {
                // 本次点击已由 touchend 处理，跳过
                tapHandledByTouch = false;
                return;
            }
            handleReaderTap(e);
        });

        // touch 区分轻点与滑动（移动端）
        elements.reader.addEventListener('touchstart', (e) => {
            if (e.touches.length !== 1) {
                touchStartInfo = null;
                return;
            }
            const t = e.touches[0];
            touchStartInfo = {
                x: t.clientX,
                y: t.clientY,
                time: Date.now()
            };
        }, { passive: true });

        elements.reader.addEventListener('touchend', (e) => {
            if (!touchStartInfo) return;
            const start = touchStartInfo;
            touchStartInfo = null;
            const t = e.changedTouches[0];
            if (!t) return;
            const dx = t.clientX - start.x;
            const dy = t.clientY - start.y;
            const moved = Math.sqrt(dx * dx + dy * dy);
            const elapsed = Date.now() - start.time;

            // 位移小且时长短视为轻点
            if (moved < TAP_MOVE_THRESHOLD && elapsed < TAP_TIME_THRESHOLD) {
                // 排除可交互元素
                if (shouldExcludeTap(e.target)) return;
                // 标记已处理，阻止后续 click 重复触发
                tapHandledByTouch = true;
                handleReaderTap(e);
            }
            // 位移超阈值视为滑动，不触发翻页，让原生滚动
        }, { passive: true });
    }

    /* ============ 番茄式自动阅读 ============ */
    let autoScrollRafId = null;
    let autoScrollLastTs = 0;

    function getReaderLineHeightPx() {
        // 取 .markdown-body 的计算行高（像素值），避免取 .reader 本身的继承值
        const md = elements.reader && elements.reader.querySelector('.markdown-body');
        if (md) {
            const lh = parseFloat(getComputedStyle(md).lineHeight);
            if (!isNaN(lh) && lh > 0) return lh;
        }
        // 回退：用 CSS 变量计算
        const root = document.documentElement;
        const cs = getComputedStyle(root);
        const lhVar = parseFloat(cs.getPropertyValue('--reader-line-height'));
        const fsVar = parseFloat(cs.getPropertyValue('--reader-font-size'));
        if (!isNaN(lhVar) && !isNaN(fsVar) && lhVar > 0 && fsVar > 0) {
            return lhVar * fsVar;
        }
        return 28; // 最终回退
    }

    function autoScrollLoop(ts) {
        if (!autoScrollRafId) return;
        if (!autoScrollLastTs) autoScrollLastTs = ts;
        // clamp deltaTime，防止后台切回瞬移
        const dt = Math.min(ts - autoScrollLastTs, 100);
        autoScrollLastTs = ts;

        const reader = elements.reader;
        if (!reader) {
            pauseAutoScroll();
            return;
        }

        // 到达章节末尾自动暂停
        if (reader.scrollHeight - reader.scrollTop - reader.clientHeight < 2) {
            pauseAutoScroll();
            return;
        }

        // 速度：行/分钟 → 像素/毫秒
        const s = loadSettings();
        let speed = s.autoScrollSpeed || 50;
        // 遵守 prefers-reduced-motion：降速到最慢
        const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReduced) speed = Math.min(speed, 24);

        const lineHeightPx = getReaderLineHeightPx();
        const pxPerMs = (speed * lineHeightPx) / 60000;
        const dy = pxPerMs * dt;
        if (dy > 0) {
            reader.scrollBy(0, dy);
        }

        autoScrollRafId = window.requestAnimationFrame(autoScrollLoop);
    }

    function startAutoScroll() {
        if (autoScrollRafId) return;
        if (!elements.reader) return;
        if (state.currentView !== 'reader') return;
        autoScrollLastTs = 0;
        autoScrollRafId = window.requestAnimationFrame(autoScrollLoop);
        const s = loadSettings();
        if (!s.autoScroll) {
            s.autoScroll = true;
            saveSettings(s);
            applySettings(s);
        } else {
            updateAutoScrollBtn(true);
        }
    }

    function pauseAutoScroll() {
        if (autoScrollRafId) {
            window.cancelAnimationFrame(autoScrollRafId);
            autoScrollRafId = null;
        }
        autoScrollLastTs = 0;
        const s = loadSettings();
        if (s.autoScroll) {
            s.autoScroll = false;
            saveSettings(s);
            applySettings(s);
        } else {
            updateAutoScrollBtn(false);
        }
    }

    function toggleAutoScroll() {
        if (autoScrollRafId) {
            pauseAutoScroll();
        } else {
            startAutoScroll();
        }
    }

    function updateAutoScrollBtn(isPlaying) {
        if (elements.autoScrollBtns) {
            elements.autoScrollBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', (btn.dataset.autoScroll === 'true') === isPlaying);
            });
        }
    }

    function initAutoScroll() {
        // 手动滚动（wheel/touchmove）时暂停自动阅读
        if (elements.reader) {
            elements.reader.addEventListener('wheel', () => {
                if (autoScrollRafId) pauseAutoScroll();
            }, { passive: true });
            elements.reader.addEventListener('touchmove', () => {
                if (autoScrollRafId) pauseAutoScroll();
            }, { passive: true });
        }
    }

    /* ============ 沉浸阅读模式 ============ */
    // 仅用 CSS .immersive-mode 隐藏 UI + 内容占满；不锁定 screen.orientation，避免手机端被强制横屏。
    // Fullscreen API 作为可选增强（多 vendor 兼容），失败时回退到纯 CSS 沉浸状态。
    function getFullscreenElement() {
        return document.fullscreenElement ||
            document.webkitFullscreenElement ||
            document.msFullscreenElement ||
            null;
    }

    function requestFullscreenSafe(el) {
        const fn = el.requestFullscreen ||
            el.webkitRequestFullscreen ||
            el.msRequestFullscreen;
        if (typeof fn === 'function') {
            try {
                const ret = fn.call(el);
                if (ret && typeof ret.then === 'function') {
                    ret.catch(function () { /* 安全策略拒绝时静默回退到 CSS 沉浸 */ });
                }
            } catch (e) { /* 静默回退 */ }
        }
    }

    function exitFullscreenSafe() {
        const fn = document.exitFullscreen ||
            document.webkitExitFullscreen ||
            document.msExitFullscreen;
        if (typeof fn === 'function') {
            try {
                const ret = fn.call(document);
                if (ret && typeof ret.then === 'function') {
                    ret.catch(function () { /* 静默 */ });
                }
            } catch (e) { /* 静默 */ }
        }
    }

    // 进入沉浸后的短暂保护期，避免某些环境（jsdom / 旧浏览器 / iframe）
    // 在 requestFullscreen 调用后立即触发 fullscreenchange 且 fullscreenElement 为空，
    // 导致状态被错误地同步回非沉浸。
    let immersiveEnterLock = false;

    function enterImmersiveMode() {
        document.body.classList.add('immersive-mode');
        // 进入沉浸时隐藏 UI 工具栏，让正文占满
        document.body.classList.add('ui-hidden');
        updateImmersiveBtn(true);
        // 尝试请求系统全屏作为增强（iframe 内可能被拒，不影响 CSS 沉浸）
        immersiveEnterLock = true;
        requestFullscreenSafe(document.documentElement);
        // 100ms 后解除保护，正常响应 ESC 退出全屏的同步事件
        setTimeout(() => { immersiveEnterLock = false; }, 100);
    }

    function exitImmersiveMode() {
        document.body.classList.remove('immersive-mode');
        document.body.classList.remove('ui-hidden');
        updateImmersiveBtn(false);
        if (getFullscreenElement()) {
            exitFullscreenSafe();
        }
    }

    function toggleImmersiveMode() {
        if (document.body.classList.contains('immersive-mode')) {
            exitImmersiveMode();
        } else {
            enterImmersiveMode();
        }
    }

    function updateImmersiveBtn(isActive) {
        if (!elements.immersiveBtn) return;
        elements.immersiveBtn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        elements.immersiveBtn.textContent = isActive ? '✕ 退出' : '⛶ 沉浸';
    }

    function initImmersive() {
        if (elements.immersiveBtn) {
            // 初始化 aria-pressed（HTML 未声明时 getAttribute 返回 null）
            elements.immersiveBtn.setAttribute('aria-pressed', 'false');
            elements.immersiveBtn.addEventListener('click', toggleImmersiveMode);
        }
        // ESC 退出系统全屏时，浏览器会触发 fullscreenchange；同步 CSS 沉浸状态，避免界面不一致
        function syncFullscreenState() {
            if (immersiveEnterLock) return;
            if (!getFullscreenElement() && document.body.classList.contains('immersive-mode')) {
                document.body.classList.remove('immersive-mode');
                document.body.classList.remove('ui-hidden');
                updateImmersiveBtn(false);
            }
        }
        document.addEventListener('fullscreenchange', syncFullscreenState);
        document.addEventListener('webkitfullscreenchange', syncFullscreenState);
        document.addEventListener('msfullscreenchange', syncFullscreenState);
    }

    /* ============ 弹窗（静态站点提示） ============ */
    function openModal() {
        elements.modalOverlay.classList.add('open');
        elements.modalOverlay.setAttribute('aria-hidden', 'false');
    }

    function closeModal() {
        elements.modalOverlay.classList.remove('open');
        elements.modalOverlay.setAttribute('aria-hidden', 'true');
    }

    /* ============ 树内搜索 ============ */
    function handleTreeSearch(event) {
        state.searchQuery = event.target.value.trim().toLowerCase();
        if (state.searchQuery) {
            state.searchMode = false;
        }
        refreshTreeView();
    }

    async function handleTreeSearchEnter(event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        const query = elements.searchInput.value.trim();
        if (!query) {
            state.searchMode = false;
            refreshTreeView();
            return;
        }

        elements.treeNav.innerHTML = '<div class="empty-state">正在加载搜索结果…</div>';
        try {
            const searchNotes = await ensureSearchIndex();
            const results = [];
            const queryLower = query.toLowerCase();

            for (const note of searchNotes) {
                const title = note.title || note.event || '';
                const snippet = note.snippet || '';
                const titleLower = title.toLowerCase();
                const snippetLower = snippet.toLowerCase();

                let matched = false;
                let displaySnippet = snippet.slice(0, 100);
                if (snippet.length > 100) displaySnippet += '…';

                if (titleLower.includes(queryLower)) {
                    matched = true;
                } else if (snippetLower.includes(queryLower)) {
                    matched = true;
                    const idx = snippetLower.indexOf(queryLower);
                    const start = Math.max(0, idx - 30);
                    const end = Math.min(snippet.length, idx + query.length + 60);
                    displaySnippet = snippet.slice(start, end);
                    if (start > 0) displaySnippet = '…' + displaySnippet;
                    if (end < snippet.length) displaySnippet += '…';
                }

                if (matched) {
                    results.push({
                        path: note.path,
                        book: note.book,
                        chapter: note.chapter,
                        event: note.event,
                        title: title,
                        snippet: displaySnippet
                    });
                }
            }
            state.searchMode = true;
            renderSearchResults(results, query);
        } catch (err) {
            elements.treeNav.innerHTML = '<div class="empty-state">搜索索引加载失败</div>';
            showError('无法加载搜索索引，请检查 data/search-index.json 是否存在。', err);
        }
    }

    function renderSearchResults(results, query) {
        elements.treeNav.innerHTML = '';
        if (results.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = `未找到与「${query}」相关的笔记`;
            elements.treeNav.appendChild(empty);
            return;
        }
        const header = document.createElement('div');
        header.className = 'search-results-header';
        header.textContent = `找到 ${results.length} 条结果`;
        elements.treeNav.appendChild(header);

        const list = document.createElement('ul');
        list.className = 'search-results';
        results.forEach((item) => {
            const li = document.createElement('li');
            li.className = 'search-result-item';

            const title = document.createElement('button');
            title.className = 'search-result-title';
            title.type = 'button';
            title.textContent = item.title || item.path;
            title.addEventListener('click', () => {
                loadNote(item.path);
                closeSidebar();
            });
            li.appendChild(title);

            if (item.book || item.chapter) {
                const meta = document.createElement('div');
                meta.className = 'search-result-meta';
                meta.textContent = [item.book, item.chapter].filter(Boolean).join(' / ');
                li.appendChild(meta);
            }

            if (item.snippet) {
                const snippet = document.createElement('div');
                snippet.className = 'search-result-snippet';
                snippet.textContent = item.snippet;
                li.appendChild(snippet);
            }

            list.appendChild(li);
        });
        elements.treeNav.appendChild(list);
    }

    function handleKeyDown(event) {
        if (event.key === 'Escape') {
            if (elements.settingsPanel && elements.settingsPanel.classList.contains('open')) {
                closeSettings();
            } else if (elements.modalOverlay && elements.modalOverlay.classList.contains('open')) {
                closeModal();
            } else if (elements.sidebar && elements.sidebar.classList.contains('open')) {
                closeSidebar();
            }
        }
        if (state.activePath) {
            if (event.key === 'ArrowLeft' && elements.prevBtnBottom && !elements.prevBtnBottom.disabled) {
                goPrevChapter();
            } else if (event.key === 'ArrowRight' && elements.nextBtnBottom && !elements.nextBtnBottom.disabled) {
                goNextChapter();
            } else if (state.currentView === 'reader' && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
                // 桌面端键盘翻页（一屏 85%）
                if (window.innerWidth > 768) {
                    event.preventDefault();
                    pauseAutoScroll();
                    pageByDirection(event.key === 'ArrowUp' ? 'prev' : 'next');
                }
            } else if (state.currentView === 'reader' && event.key === ' ') {
                // 空格键切换自动阅读播放/暂停
                event.preventDefault();
                toggleAutoScroll();
            }
        }
    }

    function detectModelScopeEmbed() {
        // 检测是否被嵌入魔搭创空间 iframe，启用嵌入适配 UI
        let inIframe = false;
        try {
            inIframe = window.self !== window.top;
        } catch (e) {
            inIframe = true;
        }

        const referrer = document.referrer || '';
        const urlParams = new URLSearchParams(window.location.search);
        const isModelScope = referrer.includes('modelscope.cn') ||
                             referrer.includes('modelscope.aliyuncs.com') ||
                             window.location.hostname.includes('.ms.show') ||
                             urlParams.get('embed') === '1' ||
                             urlParams.get('minimal') === '1';

        if (inIframe && isModelScope) {
            document.body.classList.add('modelscope-embedded');
            // 沉浸按钮显隐统一由 switchView 管理（阅读视图显示，首页隐藏）
            requestModelScopeMinimalChrome();
        }
    }

    function requestModelScopeMinimalChrome() {
        const targets = ['https://www.modelscope.cn', 'https://modelscope.cn'];
        const messages = [
            { type: 'ms:studio:hideChrome', value: true },
            { type: 'ms:studio:requestMinimal', value: true },
            { type: 'modelscope:hideHeader', value: true },
            { type: 'hideHeader', value: true }
        ];
        targets.forEach(target => {
            messages.forEach(msg => {
                try {
                    window.parent.postMessage(msg, target);
                } catch (e) {
                    // 跨域或父页面未监听时静默失败
                }
            });
        });
    }

    function resetViewState() {
        // 防止从 bfcache 恢复或异常退出后，DOM 仍保留沉浸/阅读状态导致白屏
        document.body.classList.remove('immersive-mode', 'ui-hidden');
        document.body.dataset.view = 'home';
        document.body.style.overflow = '';
    }

    function init() {
        resetViewState();

        if (typeof marked === 'undefined') {
            elements.reader.innerHTML = '<div class="reader-placeholder">Markdown 渲染组件加载失败，请检查网络连接。</div>';
            console.error('marked.js is not loaded');
        }

        detectModelScopeEmbed();
        initSettings();
        initSidebarDrawer();
        initReaderTap();
        initAutoScroll();
        initImmersive();

        if (elements.bookshelfSearchInput) {
            elements.bookshelfSearchInput.addEventListener('input', handleBookshelfSearch);
        }
        if (elements.searchInput) {
            elements.searchInput.addEventListener('input', handleTreeSearch);
            elements.searchInput.addEventListener('keydown', handleTreeSearchEnter);
        }
        if (elements.newNoteBtn) {
            elements.newNoteBtn.addEventListener('click', openModal);
        }
        if (elements.newNoteLink) {
            elements.newNoteLink.addEventListener('click', (event) => {
                event.preventDefault();
                openModal();
            });
        }
        if (elements.newNoteBtnToolbar) {
            elements.newNoteBtnToolbar.addEventListener('click', openModal);
        }
        if (elements.backBtn) {
            elements.backBtn.addEventListener('click', backToHome);
        }
        const brandLockup = document.querySelector('.brand-lockup');
        if (brandLockup) {
            brandLockup.addEventListener('click', backToHome);
        }
        if (elements.refreshBtn) {
            elements.refreshBtn.addEventListener('click', async () => {
                await loadIndex();
                if (state.currentBook) {
                    refreshTreeView();
                }
            });
        }
        if (elements.modalClose) {
            elements.modalClose.addEventListener('click', closeModal);
        }
        if (elements.cancelBtn) {
            elements.cancelBtn.addEventListener('click', closeModal);
        }
        if (elements.modalOverlay) {
            elements.modalOverlay.addEventListener('click', (event) => {
                if (event.target === elements.modalOverlay) {
                    closeModal();
                }
            });
        }

        if (elements.prevBtnBottom) {
            elements.prevBtnBottom.addEventListener('click', goPrevChapter);
        }
        if (elements.nextBtnBottom) {
            elements.nextBtnBottom.addEventListener('click', goNextChapter);
        }

        document.addEventListener('keydown', handleKeyDown);

        // 从 bfcache 恢复时（如手机系统返回后再进），强制重置视图状态，避免白屏
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                resetViewState();
                // 重新加载书架数据，确保 state 与 DOM 一致
                loadIndex();
                if (state.currentBook) {
                    state.currentBook = null;
                    state.currentBookTree = [];
                    state.activePath = null;
                }
            }
        });

        loadIndex();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
