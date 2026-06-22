(function () {
    'use strict';

    const state = {
        treeData: [],
        notesIndex: {},
        activePath: null,
        searchQuery: '',
        searchMode: false
    };

    const elements = {
        treeNav: document.getElementById('treeNav'),
        reader: document.getElementById('reader'),
        searchInput: document.getElementById('searchInput'),
        newNoteBtn: document.getElementById('newNoteBtn'),
        refreshBtn: document.getElementById('refreshBtn'),
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
        // 移除 script 标签
        html = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        // 移除 on* 事件属性
        html = html.replace(/\son\w+\s*=\s*"[^"]*"/gi, '');
        html = html.replace(/\son\w+\s*=\s*'[^']*'/gi, '');
        html = html.replace(/\son\w+\s*=\s*[^\s>]+/gi, '');
        return html;
    }

    function showError(message, err) {
        console.error(message, err || '');
        alert(message);
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
                leaf.addEventListener('click', () => loadNote(node.path, leaf));
                if (state.activePath && state.activePath === node.path) {
                    leaf.classList.add('active');
                }
                li.appendChild(leaf);
            }

            ul.appendChild(li);
        });

        return ul;
    }

    async function loadTree() {
        try {
            const response = await fetch('data/index.json');
            if (!response.ok) {
                throw new Error(`请求失败 (${response.status}): ${response.statusText}`);
            }
            const data = await response.json();
            state.treeData = data.tree || [];
            state.notesIndex = data.notes || {};
            state.searchMode = false;
            refreshTreeView();
        } catch (err) {
            elements.treeNav.innerHTML = '';
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = '加载目录失败';
            elements.treeNav.appendChild(empty);
            showError('无法加载笔记目录，请检查 data/index.json 是否存在。', err);
        }
    }

    function refreshTreeView() {
        const filtered = filterTree(state.treeData, state.searchQuery);
        const rendered = renderTree(filtered);
        elements.treeNav.innerHTML = '';
        elements.treeNav.appendChild(rendered);
        expandMatchedNodes(elements.treeNav);
    }

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
        try {
            const content = await fetch('notes/' + encodeURI(path)).then((r) => {
                if (!r.ok) {
                    throw new Error(`请求失败 (${r.status}): ${r.statusText}`);
                }
                return r.text();
            });
            const { meta, body } = parseFrontmatter(content || '');
            const html = sanitizeHtml(marked.parse(body, { gfm: true }));

            let metaHtml = '';
            if (meta && (meta.title || meta.created_at)) {
                metaHtml = '<div class="note-meta">';
                if (meta.title) metaHtml += `<span class="note-meta-title">${escapeHtml(meta.title)}</span>`;
                if (meta.book || meta.chapter) {
                    metaHtml += `<span class="note-meta-path">${escapeHtml([meta.book, meta.chapter].filter(Boolean).join(' / '))}</span>`;
                }
                if (meta.created_at) metaHtml += `<span class="note-meta-date">${escapeHtml(meta.created_at)}</span>`;
                metaHtml += '</div>';
            }

            elements.reader.innerHTML = `<article class="markdown-body">${metaHtml}${html}</article>`;

            // —— 评论系统接入钩子（开始）——
            const article = elements.reader.querySelector('.markdown-body');
            if (article) {
                document.dispatchEvent(new CustomEvent('note:loaded', {
                    detail: { notePath: path, container: article, meta: meta || null }
                }));
            }
            // —— 评论系统接入钩子（结束）——
        } catch (err) {
            elements.reader.innerHTML = '<div class="reader-placeholder">加载失败，请重试。</div>';
            showError('无法加载笔记内容。', err);
        }
    }

    function openModal() {
        elements.modalOverlay.classList.add('open');
        elements.modalOverlay.setAttribute('aria-hidden', 'false');
    }

    function closeModal() {
        elements.modalOverlay.classList.remove('open');
        elements.modalOverlay.setAttribute('aria-hidden', 'true');
    }

    function handleSearch(event) {
        state.searchQuery = event.target.value.trim().toLowerCase();
        if (!state.searchQuery) {
            state.searchMode = false;
            refreshTreeView();
            return;
        }
        if (state.searchMode) {
            state.searchMode = false;
            refreshTreeView();
        } else {
            refreshTreeView();
        }
    }

    async function handleSearchEnter(event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        const query = elements.searchInput.value.trim().toLowerCase();
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

            let matched = false;
            let snippet = '';

            if (titleLower.includes(query)) {
                matched = true;
                snippet = content.slice(0, 100).replace(/\n/g, ' ');
                if (content.length > 100) snippet += '…';
            } else if (contentLower.includes(query)) {
                matched = true;
                const idx = contentLower.indexOf(query);
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
        renderSearchResults(results, elements.searchInput.value.trim());
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
            title.addEventListener('click', () => loadNote(item.path));
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
        if (event.key === 'Escape' && elements.modalOverlay.classList.contains('open')) {
            closeModal();
        }
    }

    function init() {
        if (typeof marked === 'undefined') {
            elements.reader.innerHTML = '<div class="reader-placeholder">Markdown 渲染组件加载失败，请检查网络连接。</div>';
            console.error('marked.js is not loaded');
        }

        elements.searchInput.addEventListener('input', handleSearch);
        elements.searchInput.addEventListener('keydown', handleSearchEnter);
        elements.newNoteBtn.addEventListener('click', openModal);
        if (elements.refreshBtn) {
            elements.refreshBtn.addEventListener('click', loadTree);
        }
        elements.modalClose.addEventListener('click', closeModal);
        if (elements.cancelBtn) {
            elements.cancelBtn.addEventListener('click', closeModal);
        }
        elements.modalOverlay.addEventListener('click', (event) => {
            if (event.target === elements.modalOverlay) {
                closeModal();
            }
        });
        document.addEventListener('keydown', handleKeyDown);

        loadTree();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
