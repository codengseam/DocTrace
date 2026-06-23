(function () {
    'use strict';

    const SETTINGS_KEY = 'reader-settings';
    const DEFAULT_SETTINGS = {
        theme: 'day',
        font: 'serif',
        fontSize: 18,
        lineHeight: 1.9,
        paragraphSpacing: 1.0
    };

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
        searchMode: false
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
        cancelBtn: document.getElementById('cancelBtn')
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
            elements.homeView.hidden = false;
            elements.readerView.hidden = true;
            document.body.style.overflow = '';
        } else {
            elements.homeView.hidden = true;
            elements.readerView.hidden = false;
            document.body.style.overflow = 'hidden';
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
            loadNote(state.flatNotes[idx - 1].path);
        }
    }

    function goNextChapter() {
        const idx = state.flatNotes.findIndex((n) => n.path === state.activePath);
        if (idx >= 0 && idx < state.flatNotes.length - 1) {
            loadNote(state.flatNotes[idx + 1].path);
        }
    }

    async function loadNote(path, targetElement) {
        if (!path) return;
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

            elements.reader.innerHTML = `<article class="markdown-body">${metaHtml}${html}</article>${navHtml}`;
            bindChapterNavButtons();

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
    async function loadIndex() {
        try {
            const data = await fetchJson('data/index.json');
            state.booksData = data.books || [];
            state.categories = data.categories || [];
            state.treeData = data.tree || [];
            state.notesIndex = data.notes || {};
            state.flatNotes = flattenTree(state.treeData);
            state.searchMode = false;

            renderHeroStats(data.stats);
            renderCategoryTabs();
            renderBookshelf();
            updateChapterNav();
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
            const data = await fetchJson('data/index.json');
            state.treeData = data.tree || [];
            state.flatNotes = flattenTree(state.treeData);
            if (state.currentBook) {
                const bookNode = state.treeData.find((b) => b.title === state.currentBook);
                state.currentBookTree = bookNode ? [bookNode] : state.treeData;
            } else {
                state.currentBookTree = state.treeData;
            }
            state.searchMode = false;
            refreshTreeView();
            updateChapterNav();
        } catch (err) {
            showError('无法加载笔记目录，请检查 data/index.json 是否存在。', err);
        }
    }

    /* ============ 阅读设置 ============ */
    function loadSettings() {
        try {
            const raw = localStorage.getItem(SETTINGS_KEY);
            if (!raw) return Object.assign({}, DEFAULT_SETTINGS);
            const parsed = JSON.parse(raw);
            return Object.assign({}, DEFAULT_SETTINGS, parsed);
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
        document.body.setAttribute('data-theme', settings.theme);
        document.body.setAttribute('data-font', settings.font);
        document.documentElement.style.setProperty('--reader-font-size', settings.fontSize + 'px');
        document.documentElement.style.setProperty('--reader-line-height', String(settings.lineHeight));
        document.documentElement.style.setProperty('--reader-paragraph-spacing', settings.paragraphSpacing + 'em');

        if (elements.fontSizeRange) elements.fontSizeRange.value = settings.fontSize;
        if (elements.lineHeightRange) elements.lineHeightRange.value = settings.lineHeight;
        if (elements.paragraphSpacingRange) elements.paragraphSpacingRange.value = settings.paragraphSpacing;
        if (elements.fontSizeVal) elements.fontSizeVal.textContent = settings.fontSize + 'px';
        if (elements.lineHeightVal) elements.lineHeightVal.textContent = settings.lineHeight;
        if (elements.paragraphSpacingVal) elements.paragraphSpacingVal.textContent = settings.paragraphSpacing.toFixed(1) + 'em';

        if (elements.fontBtns) {
            elements.fontBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.font === settings.font);
            });
        }
        if (elements.themeBtns) {
            elements.themeBtns.querySelectorAll('button').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.theme === settings.theme);
            });
        }
    }

    function openSettings() {
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

        if (elements.resetSettingsBtn) {
            elements.resetSettingsBtn.addEventListener('click', () => {
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

    /* ============ 点击中央切换 UI（移动端） ============ */
    function initTapToggle() {
        if (!elements.reader) return;
        elements.reader.addEventListener('click', (e) => {
            if (window.innerWidth > 768) return;
            const vh = window.innerHeight;
            const y = e.clientY;
            if (y < vh * 0.35 || y > vh * 0.65) return;
            const tag = e.target.tagName;
            if (tag === 'A' || tag === 'BUTTON' || e.target.closest('a, button')) return;
            document.body.classList.toggle('ui-hidden');
        });
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

    function handleTreeSearchEnter(event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        const query = elements.searchInput.value.trim();
        if (!query) {
            state.searchMode = false;
            refreshTreeView();
            return;
        }
        const results = [];
        for (const [path, note] of Object.entries(state.notesIndex || {})) {
            const title = note.title || note.event || '';
            const content = note.content || '';
            const titleLower = title.toLowerCase();
            const contentLower = content.toLowerCase();
            const queryLower = query.toLowerCase();

            let matched = false;
            let snippet = '';
            if (titleLower.includes(queryLower)) {
                matched = true;
                snippet = content.slice(0, 100).replace(/\n/g, ' ');
                if (content.length > 100) snippet += '…';
            } else if (contentLower.includes(queryLower)) {
                matched = true;
                const idx = contentLower.indexOf(queryLower);
                const start = Math.max(0, idx - 30);
                const end = Math.min(content.length, idx + query.length + 60);
                snippet = content.slice(start, end).replace(/\n/g, ' ');
                if (start > 0) snippet = '…' + snippet;
                if (end < content.length) snippet += '…';
            }

            if (matched) {
                results.push({
                    path: path,
                    book: note.book,
                    chapter: note.chapter,
                    event: note.event,
                    title: title,
                    snippet: snippet
                });
            }
        }
        state.searchMode = true;
        renderSearchResults(results, query);
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
            }
        }
    }

    function init() {
        if (typeof marked === 'undefined') {
            elements.reader.innerHTML = '<div class="reader-placeholder">Markdown 渲染组件加载失败，请检查网络连接。</div>';
            console.error('marked.js is not loaded');
        }

        initSettings();
        initSidebarDrawer();
        initTapToggle();

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

        loadIndex();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
