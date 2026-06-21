(function () {
    'use strict';

    const state = {
        treeData: [],
        activePath: null,
        searchQuery: ''
    };

    const elements = {
        treeNav: document.getElementById('treeNav'),
        reader: document.getElementById('reader'),
        searchInput: document.getElementById('searchInput'),
        newNoteBtn: document.getElementById('newNoteBtn'),
        modalOverlay: document.getElementById('modalOverlay'),
        modalClose: document.getElementById('modalClose'),
        cancelBtn: document.getElementById('cancelBtn'),
        generateForm: document.getElementById('generateForm'),
        bookInput: document.getElementById('bookInput'),
        chapterInput: document.getElementById('chapterInput'),
        eventInput: document.getElementById('eventInput'),
        submitBtn: document.getElementById('submitBtn')
    };

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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

    function normalizeTree(data) {
        if (!data) return [];
        if (Array.isArray(data)) return data;
        if (data.notes && Array.isArray(data.notes)) return data.notes;
        if (data.tree && Array.isArray(data.tree)) return data.tree;
        return [];
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
            return '<div class="empty-state">暂无笔记</div>';
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
                const childrenHtml = renderTree(node.children, depth + 1);
                if (typeof childrenHtml === 'string') {
                    childrenContainer.innerHTML = childrenHtml;
                } else {
                    childrenContainer.appendChild(childrenHtml);
                }
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
            const data = await fetchJson('/api/notes');
            state.treeData = normalizeTree(data);
            refreshTreeView();
        } catch (err) {
            elements.treeNav.innerHTML = '<div class="empty-state">加载目录失败</div>';
            showError('无法加载笔记目录，请检查后端服务是否正常运行。', err);
        }
    }

    function refreshTreeView() {
        const filtered = filterTree(state.treeData, state.searchQuery);
        const rendered = renderTree(filtered);
        elements.treeNav.innerHTML = '';
        if (typeof rendered === 'string') {
            elements.treeNav.innerHTML = rendered;
        } else {
            elements.treeNav.appendChild(rendered);
        }
        expandMatchedNodes(elements.treeNav);
    }

    async function loadNote(path, targetElement) {
        if (!path) return;
        state.activePath = path;

        const allLeaves = elements.treeNav.querySelectorAll('.tree-leaf');
        allLeaves.forEach((leaf) => leaf.classList.remove('active'));
        if (targetElement) {
            targetElement.classList.add('active');
        }

        elements.reader.innerHTML = '<div class="reader-placeholder">正在加载笔记…</div>';
        try {
            const encodedPath = encodeURI(path);
            const content = await fetchJson(`/api/notes/${encodedPath}`);
            const html = marked.parse(content || '', { gfm: true });
            elements.reader.innerHTML = `<article class="markdown-body">${html}</article>`;
        } catch (err) {
            elements.reader.innerHTML = '<div class="reader-placeholder">加载失败，请重试。</div>';
            showError('无法加载笔记内容。', err);
        }
    }

    function openModal() {
        elements.modalOverlay.classList.add('open');
        elements.modalOverlay.setAttribute('aria-hidden', 'false');
        elements.bookInput.focus();
    }

    function closeModal() {
        elements.modalOverlay.classList.remove('open');
        elements.modalOverlay.setAttribute('aria-hidden', 'true');
    }

    function resetForm() {
        elements.generateForm.reset();
    }

    async function handleGenerate(event) {
        event.preventDefault();
        const book = elements.bookInput.value.trim();
        const chapter = elements.chapterInput.value.trim();
        const eventName = elements.eventInput.value.trim();

        if (!book || !chapter || !eventName) {
            alert('请填写完整的书名、章节和事件信息。');
            return;
        }

        const originalText = elements.submitBtn.textContent;
        elements.submitBtn.disabled = true;
        elements.submitBtn.textContent = '生成中…';

        try {
            await fetchJson('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ book, chapter, event: eventName })
            });
            closeModal();
            resetForm();
            await loadTree();
            alert('笔记生成成功，目录已刷新。');
        } catch (err) {
            showError('笔记生成失败，请检查后端服务或输入内容。', err);
        } finally {
            elements.submitBtn.disabled = false;
            elements.submitBtn.textContent = originalText;
        }
    }

    function handleSearch(event) {
        state.searchQuery = event.target.value.trim().toLowerCase();
        refreshTreeView();
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
        elements.newNoteBtn.addEventListener('click', openModal);
        elements.modalClose.addEventListener('click', closeModal);
        elements.cancelBtn.addEventListener('click', closeModal);
        elements.generateForm.addEventListener('submit', handleGenerate);
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
