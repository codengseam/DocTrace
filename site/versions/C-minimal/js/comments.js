/* ============================================================
 * 原文批注式评论系统 · 方向 C · 现代极简风
 *
 * 模块用途：
 *   为「深度阅读助手」静态站点提供飞书云文档式的原文圈选批注能力。
 *   通过监听 app.js dispatch 的 `note:loaded` 自定义事件接入，
 *   不引用 app.js 内部私有变量，完全独立 IIFE。
 *
 * 暴露 API：window.DeepReadingComments
 *   init(readerEl)              在指定阅读区容器内启用批注
 *   loadForNote(notePath)       加载某笔记的评论并渲染高亮
 *   clear()                     切换笔记时清理
 *   attach(container, notePath) 为指定容器初始化高亮+选区监听
 *   detach()                    卸载当前笔记的监听
 *   refresh()                   重新渲染当前笔记的高亮
 *   getComments(notePath)       获取指定笔记的评论列表
 *   getAllComments()            获取全部笔记的评论
 *   getIndex()                  获取评论索引
 *   exportNote(notePath)        导出单篇笔记评论 JSON
 *   exportAll()                 导出全站评论 JSON
 *   importJSON(jsonStr, mode)   导入评论（merge/replace）
 *   clearNote(notePath)         清空指定笔记评论
 *   exportForAgents(notePath)   导出 AI 友好格式
 *   copyAsPromptContext(notePath) 复制为 Prompt 上下文
 *   triggerExpertReview()       触发专家团评判向导
 *
 * 数据模型：deep-reading-comments/v1
 *   Comment = { id, notePath, anchor, content, type, author,
 *               createdAt, updatedAt, status, replies[], expertReviews[], deleted }
 *
 * 锚定算法：规范化纯文本 + 偏移 + quote 校验 + 前后缀指纹（三级容错）
 * ============================================================ */

(function () {
    'use strict';

    /* ========================================================
     * 一、常量与类型定义
     * ======================================================== */

    var SCHEMA_VERSION = 1;
    var STORAGE_PREFIX = 'drc:';           // localStorage key 前缀
    var META_KEY = 'drc:meta';             // 元信息 key
    var INDEX_KEY = 'drc:index';           // 全局索引 key
    var COMMENT_ID_PREFIX = 'c_';          // 评论 ID 前缀
    var REPLY_ID_PREFIX = 'r_';            // 回复 ID 前缀
    var MAX_QUOTE_LEN = 256;               // quote 最大长度
    var MIN_QUOTE_LEN = 1;                 // quote 最小长度
    var FINGERPRINT_LEN = 32;              // 前后缀指纹长度
    var MAX_EDIT_DIST = 2;                 // 模糊匹配最大编辑距离

    // 5 种评论类型
    var TYPES = {
        error: { key: 'error', label: '错误', icon: '❗' },
        praise: { key: 'praise', label: '夸奖', icon: '👍' },
        discussion: { key: 'discussion', label: '讨论', icon: '💬' },
        supplement: { key: 'supplement', label: '补充', icon: '➕' },
        thought: { key: 'thought', label: '感想', icon: '✦' }
    };

    // 专家团成员
    var AGENTS = ['historian', 'biographer', 'context_analyst', 'critic', 'philosopher', 'editor'];

    // 禁批注元素标签
    var FORBIDDEN_TAGS = ['script', 'style', 'code', 'pre', 'kbd', 'samp'];

    /* ========================================================
     * 二、模块私有状态
     * ======================================================== */

    var currentContainer = null;   // 当前 .markdown-body 元素
    var currentNotePath = null;    // 当前笔记路径
    var currentMeta = null;        // 当前笔记 frontmatter
    var normTextCache = null;      // 规范化文本缓存 { normText, charMap, nodeIndex }
    var selectionDebounceTimer = null;
    var activeBubble = null;       // 当前选区图标气泡
    var activePopover = null;      // 当前输入浮层
    var activeSelection = null;    // 当前选区 Range 快照
    var activeAnchor = null;       // 当前选区捕获的锚点
    var drawerEl = null;           // 底部抽屉元素
    var drawerExpanded = false;    // 抽屉是否展开
    var activeThreadId = null;     // 当前选中的评论 ID
    var filterState = { type: 'all', status: 'all', keyword: '' };
    var hoverCardEl = null;
    var hoverCardTimer = null;

    /* ========================================================
     * 三、工具函数
     * ======================================================== */

    /**
     * HTML 转义，防 XSS
     */
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    /**
     * 生成评论 ID：c_<timestamp>_<seq>
     */
    var idSeq = 0;
    function genCommentId() {
        idSeq++;
        return COMMENT_ID_PREFIX + Date.now() + '_' + idSeq;
    }

    function genReplyId() {
        idSeq++;
        return REPLY_ID_PREFIX + Date.now() + '_' + idSeq;
    }

    /**
     * 当前时间 ISO 8601（带时区）
     */
    function nowIso() {
        var d = new Date();
        var tzOffset = -d.getTimezoneOffset();
        var tzSign = tzOffset >= 0 ? '+' : '-';
        var tzHours = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, '0');
        var tzMins = String(Math.abs(tzOffset) % 60).padStart(2, '0');
        var iso = d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0') + 'T' +
            String(d.getHours()).padStart(2, '0') + ':' +
            String(d.getMinutes()).padStart(2, '0') + ':' +
            String(d.getSeconds()).padStart(2, '0');
        return iso + tzSign + tzHours + ':' + tzMins;
    }

    /**
     * 格式化时间显示
     */
    function formatTime(iso) {
        if (!iso) return '';
        try {
            var d = new Date(iso);
            if (isNaN(d.getTime())) return iso;
            var now = new Date();
            var diff = (now - d) / 1000;
            if (diff < 60) return '刚刚';
            if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
            if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
            if (diff < 86400 * 7) return Math.floor(diff / 86400) + ' 天前';
            return d.getFullYear() + '-' +
                String(d.getMonth() + 1).padStart(2, '0') + '-' +
                String(d.getDate()).padStart(2, '0') + ' ' +
                String(d.getHours()).padStart(2, '0') + ':' +
                String(d.getMinutes()).padStart(2, '0');
        } catch (e) {
            return iso;
        }
    }

    /**
     * Toast 提示
     */
    var toastEl = null;
    var toastTimer = null;
    function toast(msg) {
        if (!toastEl) {
            toastEl = document.createElement('div');
            toastEl.className = 'cmt-toast';
            document.body.appendChild(toastEl);
        }
        toastEl.textContent = msg;
        toastEl.classList.add('cmt-visible');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            toastEl.classList.remove('cmt-visible');
        }, 2500);
    }

    /**
     * 触发文件下载
     */
    function downloadJSON(filename, data) {
        var json = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        var blob = new Blob([json], { type: 'application/json;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    /**
     * 文件名安全化
     */
    function safeFilename(name) {
        return String(name || '').replace(/[\/\\:*?"<>|]/g, '_').replace(/\.md$/i, '');
    }

    /**
     * 今日日期 YYYYMMDD
     */
    function todayStr() {
        var d = new Date();
        return d.getFullYear() +
            String(d.getMonth() + 1).padStart(2, '0') +
            String(d.getDate()).padStart(2, '0');
    }

    /* ========================================================
     * 四、存储层
     * ======================================================== */

    var Storage = {
        /**
         * 加载指定笔记的评论
         */
        loadComments: function (notePath) {
            try {
                var raw = localStorage.getItem(STORAGE_PREFIX + notePath);
                if (!raw) return [];
                var arr = JSON.parse(raw);
                if (!Array.isArray(arr)) return [];
                // 过滤软删除
                return arr.filter(function (c) { return !c.deleted; });
            } catch (e) {
                console.error('[Comments] loadComments error:', e);
                return [];
            }
        },

        /**
         * 加载全部评论（含软删除的，用于内部操作）
         */
        loadAllCommentsRaw: function (notePath) {
            try {
                var raw = localStorage.getItem(STORAGE_PREFIX + notePath);
                if (!raw) return [];
                var arr = JSON.parse(raw);
                return Array.isArray(arr) ? arr : [];
            } catch (e) {
                return [];
            }
        },

        /**
         * 保存评论（含软删除标记）
         */
        saveComments: function (notePath, comments) {
            try {
                localStorage.setItem(STORAGE_PREFIX + notePath, JSON.stringify(comments));
                this.updateIndex(notePath, comments);
                return true;
            } catch (e) {
                if (e && e.name === 'QuotaExceededError') {
                    toast('本地存储已满，请导出后清理');
                } else {
                    console.error('[Comments] saveComments error:', e);
                }
                return false;
            }
        },

        loadIndex: function () {
            try {
                var raw = localStorage.getItem(INDEX_KEY);
                return raw ? JSON.parse(raw) : [];
            } catch (e) {
                return [];
            }
        },

        updateIndex: function (notePath, comments) {
            var idx = this.loadIndex().filter(function (e) { return e.notePath !== notePath; });
            var visible = comments.filter(function (c) { return !c.deleted; });
            var threads = visible.filter(function (c) { return !c.parentId; });
            idx.push({
                notePath: notePath,
                count: visible.length,
                threadCount: threads.length,
                unresolvedCount: threads.filter(function (t) { return t.status === 'open'; }).length,
                lastUpdatedAt: nowIso()
            });
            try {
                localStorage.setItem(INDEX_KEY, JSON.stringify(idx));
            } catch (e) {
                console.error('[Comments] updateIndex error:', e);
            }
        },

        deleteNote: function (notePath) {
            try {
                localStorage.removeItem(STORAGE_PREFIX + notePath);
                var idx = this.loadIndex().filter(function (e) { return e.notePath !== notePath; });
                localStorage.setItem(INDEX_KEY, JSON.stringify(idx));
            } catch (e) {
                console.error('[Comments] deleteNote error:', e);
            }
        },

        loadMeta: function () {
            try {
                var raw = localStorage.getItem(META_KEY);
                return raw ? JSON.parse(raw) : { schemaVersion: SCHEMA_VERSION, lastExportAt: null };
            } catch (e) {
                return { schemaVersion: SCHEMA_VERSION, lastExportAt: null };
            }
        },

        saveMeta: function (meta) {
            try {
                localStorage.setItem(META_KEY, JSON.stringify(meta));
            } catch (e) {
                console.error('[Comments] saveMeta error:', e);
            }
        }
    };

    /* ========================================================
     * 五、文本锚定算法（核心）
     * ======================================================== */

    /**
     * 判断文本节点是否可批注
     * 排除：script/style/code/pre/kbd/samp、标题 h1-h6、mark 内（避免嵌套）
     */
    function isAnnotatableText(textNode) {
        if (!textNode || textNode.nodeType !== Node.TEXT_NODE) return false;
        var parent = textNode.parentElement;
        if (!parent) return false;
        var tag = parent.tagName.toLowerCase();
        if (FORBIDDEN_TAGS.indexOf(tag) !== -1) return false;
        if (/^h[1-6]$/.test(tag)) return false;
        var raw = textNode.nodeValue || '';
        if (raw.replace(/\s+/g, '').length === 0) return false;
        return true;
    }

    /**
     * 判断 Range 是否与禁批注元素相交
     */
    function rangeIntersectsForbidden(range) {
        var container = currentContainer;
        if (!container) return true;
        var forbidden = container.querySelectorAll('h1, h2, h3, h4, h5, h6, pre, code, kbd, samp');
        for (var i = 0; i < forbidden.length; i++) {
            try {
                if (range.intersectsNode(forbidden[i])) return true;
            } catch (e) {
                // intersectsNode 可能在边界情况报错，忽略
            }
        }
        return false;
    }

    /**
     * 构建原始文本到规范化文本的段映射
     * 将 \s+ 压缩为单空格，记录每个原始片段对应的规范化位置
     */
    function buildSegments(raw, startNorm) {
        var segments = [];
        var rawIdx = 0;
        var normRelIdx = 0;
        while (rawIdx < raw.length) {
            if (/\s/.test(raw[rawIdx])) {
                var wsStart = rawIdx;
                while (rawIdx < raw.length && /\s/.test(raw[rawIdx])) rawIdx++;
                segments.push({ rawStart: wsStart, rawEnd: rawIdx, normStart: normRelIdx, normLen: 1 });
                normRelIdx += 1;
            } else {
                segments.push({ rawStart: rawIdx, rawEnd: rawIdx + 1, normStart: normRelIdx, normLen: 1 });
                rawIdx++;
                normRelIdx++;
            }
        }
        return segments;
    }

    /**
     * 遍历容器内可批注文本节点，构建规范化纯文本与反向映射
     * @returns {{ normText, charMap, nodeIndex }}
     */
    function buildNormalizedText(root) {
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
            acceptNode: function (node) {
                return isAnnotatableText(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
            }
        });

        var charMap = [];
        var nodeIndex = new WeakMap();
        var normText = '';
        var textNode;

        while ((textNode = walker.nextNode())) {
            var raw = textNode.nodeValue || '';
            var normalized = raw.replace(/\s+/g, ' ');
            if (normalized === '') continue;

            var startNorm = normText.length;
            var segments = buildSegments(raw, startNorm);
            nodeIndex.set(textNode, { startNorm: startNorm, segments: segments });
            charMap.push({ node: textNode, startNorm: startNorm, length: normalized.length });
            normText += normalized;
        }

        return { normText: normText, charMap: charMap, nodeIndex: nodeIndex };
    }

    /**
     * 获取规范化文本缓存（避免重复遍历）
     */
    function getNormTextCache() {
        if (!normTextCache && currentContainer) {
            normTextCache = buildNormalizedText(currentContainer);
        }
        return normTextCache;
    }

    /**
     * 将 DOM 偏移（node, offset）映射到规范化文本偏移
     */
    function mapDomOffsetToNorm(node, offset, nodeIndex) {
        if (!node || node.nodeType !== Node.TEXT_NODE) {
            // 可能是元素节点，需要找到其内部第一个/最后一个文本节点
            if (node && node.nodeType === Node.ELEMENT_NODE) {
                var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
                var first = walker.nextNode();
                if (first) {
                    var info = nodeIndex.get(first);
                    if (info) return info.startNorm;
                }
            }
            return null;
        }
        var info = nodeIndex.get(node);
        if (!info) return null;
        var segments = info.segments;
        if (segments.length === 0) return info.startNorm;

        for (var i = 0; i < segments.length; i++) {
            var seg = segments[i];
            if (offset >= seg.rawStart && offset < seg.rawEnd) {
                if (seg.normLen === 1 && seg.rawEnd > seg.rawStart) {
                    // 空白段：映射到该单空格位置
                    return info.startNorm + seg.normStart;
                }
                return info.startNorm + seg.normStart + (offset - seg.rawStart);
            }
        }
        // offset 在节点末尾
        var last = segments[segments.length - 1];
        return info.startNorm + last.normStart + last.normLen;
    }

    /**
     * 将规范化偏移映射回 DOM 偏移
     */
    function findNodeForNormOffset(normOffset, charMap, nodeIndex) {
        for (var i = 0; i < charMap.length; i++) {
            var entry = charMap[i];
            var entryEnd = entry.startNorm + entry.length;
            if (normOffset >= entry.startNorm && normOffset <= entryEnd) {
                var info = nodeIndex.get(entry.node);
                if (!info) return null;
                var relNorm = normOffset - entry.startNorm;
                var rawOffset = normRelToRawOffset(info.segments, relNorm);
                return { node: entry.node, offset: rawOffset };
            }
        }
        return null;
    }

    function normRelToRawOffset(segments, relNorm) {
        for (var i = 0; i < segments.length; i++) {
            var seg = segments[i];
            var segEnd = seg.normStart + seg.normLen;
            if (relNorm >= seg.normStart && relNorm <= segEnd) {
                if (seg.normLen === 1 && seg.rawEnd > seg.rawStart) {
                    // 空白段
                    if (relNorm === seg.normStart) return seg.rawStart;
                    return seg.rawEnd;
                }
                return seg.rawStart + (relNorm - seg.normStart);
            }
        }
        var last = segments[segments.length - 1];
        return last ? last.rawEnd : 0;
    }

    /**
     * 将规范化文本范围转换为 DOM Range
     */
    function normRangeToDomRange(normStart, normEnd, charMap, nodeIndex) {
        var startInfo = findNodeForNormOffset(normStart, charMap, nodeIndex);
        var endInfo = findNodeForNormOffset(normEnd, charMap, nodeIndex);
        if (!startInfo || !endInfo) return null;
        try {
            var range = document.createRange();
            range.setStart(startInfo.node, startInfo.offset);
            range.setEnd(endInfo.node, endInfo.offset);
            return range;
        } catch (e) {
            return null;
        }
    }

    /**
     * 计算选区的结构信息（段落索引 + 标题路径）
     */
    function computeStructuralInfo(range, container) {
        var el = range.startContainer;
        if (el.nodeType === Node.TEXT_NODE) el = el.parentElement;

        var headingPath = [];
        var paragraphIndex = 0;
        var foundParagraph = false;

        var walker = document.createTreeWalker(container, NodeFilter.SHOW_ELEMENT, {
            acceptNode: function (node) {
                var tag = node.tagName.toLowerCase();
                if (/^h[1-6]$/.test(tag)) return NodeFilter.FILTER_ACCEPT;
                if (['p', 'blockquote', 'li', 'pre', 'td', 'th'].indexOf(tag) !== -1) return NodeFilter.FILTER_ACCEPT;
                return NodeFilter.FILTER_SKIP;
            }
        });

        var node;
        while ((node = walker.nextNode())) {
            var tag = node.tagName.toLowerCase();
            if (/^h[1-6]$/.test(tag)) {
                if (foundParagraph) break;
                var level = parseInt(tag[1], 10);
                while (headingPath.length > 0 && headingPath[headingPath.length - 1].level >= level) {
                    headingPath.pop();
                }
                headingPath.push({ level: level, text: node.textContent.trim() });
            } else {
                if (!foundParagraph) {
                    if (node === el || node.contains(el)) {
                        foundParagraph = true;
                    } else {
                        paragraphIndex++;
                    }
                }
            }
        }

        return {
            paragraphIndex: paragraphIndex,
            headingPath: headingPath.map(function (h) { return h.text; })
        };
    }

    /**
     * 从当前 Selection 捕获锚点
     * @returns {Anchor | null}
     */
    function captureAnchor(selection, notePath) {
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
        var range = selection.getRangeAt(0);
        var container = currentContainer;
        if (!container || !container.contains(range.commonAncestorContainer)) return null;

        if (rangeIntersectsForbidden(range)) return null;

        var cache = getNormTextCache();
        if (!cache || !cache.normText) return null;

        var startInfo = mapDomOffsetToNorm(range.startContainer, range.startOffset, cache.nodeIndex);
        var endInfo = mapDomOffsetToNorm(range.endContainer, range.endOffset, cache.nodeIndex);
        if (startInfo === null || endInfo === null || endInfo <= startInfo) return null;

        var rangeStart = startInfo;
        var rangeEnd = endInfo;
        var quote = cache.normText.slice(rangeStart, rangeEnd);

        if (quote.length < MIN_QUOTE_LEN) return null;
        if (quote.length > MAX_QUOTE_LEN) {
            quote = quote.slice(0, MAX_QUOTE_LEN);
            rangeEnd = rangeStart + MAX_QUOTE_LEN;
        }

        var normTextPrefix = cache.normText.slice(Math.max(0, rangeStart - FINGERPRINT_LEN), rangeStart);
        var normTextSuffix = cache.normText.slice(rangeEnd, rangeEnd + FINGERPRINT_LEN);

        var structInfo = computeStructuralInfo(range, container);
        var version = (currentMeta && (currentMeta.created_at || currentMeta.version)) || todayStr();

        return {
            notePath: notePath,
            strategy: 'text+context',
            exact: quote,
            prefix: normTextPrefix.slice(-20),
            suffix: normTextSuffix.slice(0, 20),
            paragraphIndex: structInfo.paragraphIndex,
            headingPath: structInfo.headingPath,
            charOffsetStart: rangeStart,
            charOffsetEnd: rangeEnd,
            version: version,
            // architecture.md 字段（用于解析）
            quote: quote,
            rangeStart: rangeStart,
            rangeEnd: rangeEnd,
            normTextPrefix: normTextPrefix,
            normTextSuffix: normTextSuffix,
            schemaVersion: SCHEMA_VERSION
        };
    }

    /**
     * 编辑距离（Levenshtein），带最大距离早退
     */
    function editDistance(a, b, maxDist) {
        if (a === b) return 0;
        var la = a.length, lb = b.length;
        if (Math.abs(la - lb) > maxDist) return maxDist + 1;
        if (la === 0) return lb;
        if (lb === 0) return la;

        var prev = new Array(lb + 1);
        var curr = new Array(lb + 1);
        for (var j = 0; j <= lb; j++) prev[j] = j;

        for (var i = 1; i <= la; i++) {
            curr[0] = i;
            var rowMin = curr[0];
            for (var j = 1; j <= lb; j++) {
                var cost = a[i - 1] === b[j - 1] ? 0 : 1;
                curr[j] = Math.min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + cost
                );
                if (curr[j] < rowMin) rowMin = curr[j];
            }
            if (rowMin > maxDist) return maxDist + 1;
            var tmp = prev; prev = curr; curr = tmp;
        }
        return prev[lb];
    }

    /**
     * 前缀+后缀指纹模糊定位
     */
    function fuzzyLocateByFingerprints(normText, prefix, suffix, quoteLen) {
        if (!prefix && !suffix) return null;

        // 用前缀前 8 字符做探针，找候选位置
        var probe = prefix ? prefix.slice(0, Math.min(8, prefix.length)) : suffix.slice(0, Math.min(8, suffix.length));
        if (!probe) return null;

        var candidates = [];
        var searchFrom = 0;
        while (true) {
            var idx = normText.indexOf(probe, searchFrom);
            if (idx === -1) break;
            candidates.push(idx);
            searchFrom = idx + 1;
            if (candidates.length > 200) break; // 防止过多候选
        }

        for (var ci = 0; ci < candidates.length; ci++) {
            var p = candidates[ci];
            if (prefix) {
                var prefixSlice = normText.slice(p, p + prefix.length);
                if (editDistance(prefixSlice, prefix, MAX_EDIT_DIST) > MAX_EDIT_DIST) continue;
                var expectedStart = p + prefix.length;
                var expectedEnd = expectedStart + quoteLen;
                if (suffix) {
                    var suffixSlice = normText.slice(expectedEnd, expectedEnd + suffix.length);
                    if (editDistance(suffixSlice, suffix, MAX_EDIT_DIST) <= MAX_EDIT_DIST) {
                        return { start: expectedStart, end: expectedEnd };
                    }
                } else {
                    return { start: expectedStart, end: expectedEnd };
                }
            }
        }

        // 仅用后缀尝试
        if (suffix) {
            var sProbe = suffix.slice(0, Math.min(8, suffix.length));
            var sSearchFrom = 0;
            while (true) {
                var sIdx = normText.indexOf(sProbe, sSearchFrom);
                if (sIdx === -1) break;
                // 后缀位置 = 锚点结束位置
                var sExpectedEnd = sIdx;
                var sExpectedStart = sExpectedEnd - quoteLen;
                if (sExpectedStart >= 0) {
                    var sSuffixSlice = normText.slice(sIdx, sIdx + suffix.length);
                    if (editDistance(sSuffixSlice, suffix, MAX_EDIT_DIST) <= MAX_EDIT_DIST) {
                        return { start: sExpectedStart, end: sExpectedEnd };
                    }
                }
                sSearchFrom = sIdx + 1;
            }
        }

        return null;
    }

    /**
     * 解析锚点，返回 DOM Range（三级容错）
     */
    function resolveAnchor(anchor, container) {
        if (!anchor || !container) return null;
        var cache = buildNormalizedText(container);
        var normText = cache.normText;

        var rangeStart = anchor.rangeStart !== undefined ? anchor.rangeStart : anchor.charOffsetStart;
        var rangeEnd = anchor.rangeEnd !== undefined ? anchor.rangeEnd : anchor.charOffsetEnd;
        var quote = anchor.quote || anchor.exact || '';
        var prefix = anchor.normTextPrefix || anchor.prefix || '';
        var suffix = anchor.normTextSuffix || anchor.suffix || '';

        // 级别 1：精确偏移 + quote 校验
        if (rangeStart !== undefined && rangeEnd !== undefined && rangeEnd <= normText.length) {
            var slice = normText.slice(rangeStart, rangeEnd);
            if (slice === quote) {
                return normRangeToDomRange(rangeStart, rangeEnd, cache.charMap, cache.nodeIndex);
            }
        }

        // 级别 2：quote 全文查找
        if (quote) {
            var idx = normText.indexOf(quote);
            if (idx !== -1) {
                return normRangeToDomRange(idx, idx + quote.length, cache.charMap, cache.nodeIndex);
            }
        }

        // 级别 3：前缀+后缀指纹模糊定位
        var fuzzy = fuzzyLocateByFingerprints(normText, prefix, suffix, quote.length || (rangeEnd - rangeStart) || 10);
        if (fuzzy) {
            return normRangeToDomRange(fuzzy.start, fuzzy.end, cache.charMap, cache.nodeIndex);
        }

        return null;
    }

    /* ========================================================
     * 六、高亮 wrap / unwrap
     * ======================================================== */

    /**
     * 收集 Range 内所有可批注文本节点
     */
    function collectTextNodesInRange(range) {
        var textNodes = [];
        var root = range.commonAncestorContainer;
        var walkerRoot = root.nodeType === Node.TEXT_NODE ? root.parentNode : root;
        if (!walkerRoot) return textNodes;

        var walker = document.createTreeWalker(walkerRoot, NodeFilter.SHOW_TEXT, {
            acceptNode: function (node) {
                if (!isAnnotatableText(node)) return NodeFilter.FILTER_REJECT;
                try {
                    if (range.intersectsNode(node)) return NodeFilter.FILTER_ACCEPT;
                } catch (e) { /* ignore */ }
                return NodeFilter.FILTER_REJECT;
            }
        });

        var node;
        while ((node = walker.nextNode())) {
            textNodes.push(node);
        }
        return textNodes;
    }

    /**
     * 把 Range 包裹成 <mark class="cmt-highlight">
     * 跨多个文本节点时逐节点切分并分别包裹
     */
    function wrapRangeWithHighlight(range, commentId, type, status) {
        var textNodes = collectTextNodesInRange(range);
        if (textNodes.length === 0) return;

        var startContainer = range.startContainer;
        var endContainer = range.endContainer;
        var startOffset = range.startOffset;
        var endOffset = range.endOffset;

        for (var i = 0; i < textNodes.length; i++) {
            var node = textNodes[i];
            var wrapStart = 0;
            var wrapEnd = node.length;

            if (i === 0 && node === startContainer) {
                wrapStart = startOffset;
            }
            if (i === textNodes.length - 1 && node === endContainer) {
                wrapEnd = endOffset;
            }
            if (node === startContainer && node === endContainer) {
                wrapStart = startOffset;
                wrapEnd = endOffset;
            }

            if (wrapStart >= wrapEnd) continue;

            // 先在 wrapEnd 处切分（如果不是末尾）
            if (wrapEnd < node.length) {
                node.splitText(wrapEnd);
            }
            // 再在 wrapStart 处切分（如果不是开头）
            var target = node;
            if (wrapStart > 0) {
                target = node.splitText(wrapStart);
            }

            // 包裹 target
            var mark = document.createElement('mark');
            mark.className = 'cmt-highlight';
            mark.setAttribute('data-cm-id', commentId);
            mark.setAttribute('data-cmt-type', type);
            mark.setAttribute('data-cmt-status', status || 'open');
            mark.setAttribute('role', 'mark');
            mark.setAttribute('tabindex', '0');
            var label = TYPES[type] ? TYPES[type].label : '批注';
            mark.setAttribute('aria-label', label + '，点击查看');

            target.parentNode.insertBefore(mark, target);
            mark.appendChild(target);
        }
    }

    /**
     * 移除指定评论 ID 的高亮
     */
    function unwrapHighlight(commentId) {
        if (!currentContainer) return;
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        for (var i = 0; i < marks.length; i++) {
            var mark = marks[i];
            var parent = mark.parentNode;
            while (mark.firstChild) {
                parent.insertBefore(mark.firstChild, mark);
            }
            parent.removeChild(mark);
            // 合并相邻文本节点
            parent.normalize();
        }
    }

    /**
     * 更新高亮状态（解决/重开）
     */
    function updateHighlightStatus(commentId, status) {
        if (!currentContainer) return;
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        for (var i = 0; i < marks.length; i++) {
            marks[i].setAttribute('data-cmt-status', status);
        }
    }

    /**
     * 渲染所有评论的高亮（从后往前 wrap，避免偏移影响）
     */
    function renderAllHighlights() {
        if (!currentContainer || !currentNotePath) return;
        var comments = Storage.loadComments(currentNotePath);
        // 只处理顶级评论（有锚点的）
        var threaded = comments.filter(function (c) {
            return !c.parentId && c.anchor && c.status;
        });

        // 按 rangeStart 排序，从后往前 wrap
        threaded.sort(function (a, b) {
            var aStart = a.anchor.rangeStart || a.anchor.charOffsetStart || 0;
            var bStart = b.anchor.rangeStart || b.anchor.charOffsetStart || 0;
            return bStart - aStart;
        });

        for (var i = 0; i < threaded.length; i++) {
            var c = threaded[i];
            var range = resolveAnchor(c.anchor, currentContainer);
            if (range) {
                try {
                    wrapRangeWithHighlight(range, c.id, c.type, c.status);
                } catch (e) {
                    console.error('[Comments] wrap error for', c.id, e);
                }
            }
            // 解析失败的（孤儿）不高亮，仅在评论区标识
        }
    }

    /* ========================================================
     * 七、选区监听 + 浮层
     * ======================================================== */

    function handleSelectionChange() {
        if (selectionDebounceTimer) clearTimeout(selectionDebounceTimer);
        selectionDebounceTimer = setTimeout(handleSelectionEnd, 200);
    }

    function handleSelectionEnd() {
        var selection = window.getSelection();
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
            hideBubble();
            return;
        }

        var range = selection.getRangeAt(0);
        if (!currentContainer || !currentContainer.contains(range.commonAncestorContainer)) {
            hideBubble();
            return;
        }

        if (rangeIntersectsForbidden(range)) {
            hideBubble();
            return;
        }

        // 选区太短不弹
        var text = selection.toString();
        if (text.replace(/\s+/g, '').length < MIN_QUOTE_LEN) {
            hideBubble();
            return;
        }

        showBubble(range);
    }

    /**
     * 显示极简图标气泡
     */
    function showBubble(range) {
        if (!activeBubble) {
            activeBubble = document.createElement('button');
            activeBubble.className = 'cmt-bubble';
            activeBubble.type = 'button';
            activeBubble.setAttribute('aria-label', '添加批注');
            activeBubble.textContent = '✎';
            activeBubble.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                openPopover();
            });
            document.body.appendChild(activeBubble);
        }

        var rect = range.getBoundingClientRect();
        var scrollY = window.scrollY;
        var scrollX = window.scrollX;
        activeBubble.style.left = (rect.right + scrollX - 14) + 'px';
        activeBubble.style.top = (rect.top + scrollY - 32) + 'px';
        activeBubble.classList.add('cmt-visible');
        activeSelection = range;
    }

    function hideBubble() {
        if (activeBubble) {
            activeBubble.classList.remove('cmt-visible');
        }
    }

    /**
     * 打开输入浮层
     */
    function openPopover() {
        if (!activeSelection) return;

        // 捕获锚点
        var selection = window.getSelection();
        activeAnchor = captureAnchor(selection, currentNotePath);
        if (!activeAnchor) {
            toast('该区域暂不支持批注');
            return;
        }

        if (!activePopover) {
            activePopover = createPopover();
            document.body.appendChild(activePopover);
        }

        // 填充引用
        var quoteEl = activePopover.querySelector('.cmt-popover-quote');
        quoteEl.textContent = activeAnchor.quote;

        // 重置输入
        var input = activePopover.querySelector('.cmt-popover-input');
        input.value = '';
        var typeSelect = activePopover.querySelector('.cmt-popover-type');
        typeSelect.value = 'discussion';
        updateSubmitState();

        // 定位
        positionPopover(activePopover, activeSelection);
        activePopover.classList.add('cmt-visible');
        hideBubble();

        setTimeout(function () { input.focus(); }, 100);
    }

    function createPopover() {
        var popover = document.createElement('div');
        popover.className = 'cmt-popover';
        popover.setAttribute('role', 'dialog');
        popover.setAttribute('aria-modal', 'false');
        popover.setAttribute('aria-label', '新建批注');
        popover.innerHTML =
            '<div class="cmt-popover-quote"></div>' +
            '<textarea class="cmt-popover-input" placeholder="写下你的批注…" rows="3"></textarea>' +
            '<div class="cmt-popover-actions">' +
                '<select class="cmt-popover-type" aria-label="批注类型">' +
                    '<option value="error">❗ 错误</option>' +
                    '<option value="praise">👍 夸奖</option>' +
                    '<option value="discussion">💬 讨论</option>' +
                    '<option value="supplement">➕ 补充</option>' +
                    '<option value="thought">✦ 感想</option>' +
                '</select>' +
                '<div class="cmt-spacer"></div>' +
                '<button type="button" class="cmt-btn cmt-btn-ghost cmt-popover-cancel">取消</button>' +
                '<button type="button" class="cmt-btn cmt-btn-primary cmt-popover-submit" disabled>提交</button>' +
            '</div>';

        var input = popover.querySelector('.cmt-popover-input');
        var submitBtn = popover.querySelector('.cmt-popover-submit');
        var cancelBtn = popover.querySelector('.cmt-popover-cancel');
        var typeSelect = popover.querySelector('.cmt-popover-type');

        input.addEventListener('input', updateSubmitState);
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitComment();
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                hidePopover();
            }
        });
        typeSelect.addEventListener('change', updateSubmitState);
        submitBtn.addEventListener('click', submitComment);
        cancelBtn.addEventListener('click', hidePopover);

        return popover;
    }

    function updateSubmitState() {
        if (!activePopover) return;
        var input = activePopover.querySelector('.cmt-popover-input');
        var submitBtn = activePopover.querySelector('.cmt-popover-submit');
        submitBtn.disabled = input.value.trim().length === 0;
    }

    function positionPopover(popover, range) {
        var rect = range.getBoundingClientRect();
        var scrollY = window.scrollY;
        var scrollX = window.scrollX;
        var popoverWidth = 320;
        var popoverHeight = 220; // 估算

        var left = rect.left + scrollX + rect.width / 2 - popoverWidth / 2;
        var top = rect.bottom + scrollY + 8;

        // 边界翻转
        if (top + popoverHeight > scrollY + window.innerHeight) {
            top = rect.top + scrollY - popoverHeight - 8;
        }
        if (left < scrollX + 16) left = scrollX + 16;
        if (left + popoverWidth > scrollX + window.innerWidth - 16) {
            left = scrollX + window.innerWidth - popoverWidth - 16;
        }

        popover.style.left = left + 'px';
        popover.style.top = top + 'px';
        popover.style.transform = 'none';
    }

    function hidePopover() {
        if (activePopover) {
            activePopover.classList.remove('cmt-visible');
        }
        activeAnchor = null;
        // 不清除选区，允许重新打开
    }

    /**
     * 提交评论
     */
    function submitComment() {
        if (!activeAnchor || !activePopover) return;
        var input = activePopover.querySelector('.cmt-popover-input');
        var typeSelect = activePopover.querySelector('.cmt-popover-type');
        var content = input.value.trim();
        if (!content) return;

        var type = typeSelect.value;
        var comment = {
            id: genCommentId(),
            notePath: currentNotePath,
            parentId: null,
            anchor: activeAnchor,
            content: content,
            type: type,
            author: '作者',
            createdAt: nowIso(),
            updatedAt: nowIso(),
            status: 'open',
            replies: [],
            expertReviews: [],
            deleted: false
        };

        // 保存
        var all = Storage.loadAllCommentsRaw(currentNotePath);
        all.push(comment);
        Storage.saveComments(currentNotePath, all);

        // 高亮
        var range = resolveAnchor(activeAnchor, currentContainer);
        if (range) {
            try {
                wrapRangeWithHighlight(range, comment.id, type, 'open');
            } catch (e) {
                console.error('[Comments] wrap on submit error:', e);
            }
        }

        // 清除选区
        var selection = window.getSelection();
        if (selection) selection.removeAllRanges();

        hidePopover();
        hideBubble();
        renderDrawer();
        toast('已添加批注');
    }

    /* ========================================================
     * 八、高亮交互（点击/悬浮）
     * ======================================================== */

    function handleContainerClick(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) return;
        var id = mark.getAttribute('data-cm-id');
        if (!id) return;
        e.preventDefault();
        // 展开抽屉并定位
        expandDrawer();
        selectThread(id);
    }

    function handleHighlightMouseOver(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) return;
        var id = mark.getAttribute('data-cm-id');
        if (!id) return;
        showHoverCard(id, mark);
    }

    function handleHighlightMouseOut(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) return;
        scheduleHideHoverCard();
    }

    function showHoverCard(commentId, mark) {
        if (hoverCardTimer) clearTimeout(hoverCardTimer);
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;

        if (!hoverCardEl) {
            hoverCardEl = document.createElement('div');
            hoverCardEl.className = 'cmt-hover-card';
            hoverCardEl.setAttribute('role', 'tooltip');
            document.body.appendChild(hoverCardEl);
        }

        var typeInfo = TYPES[comment.type] || { label: '批注', icon: '' };
        hoverCardEl.innerHTML =
            '<div class="cmt-hover-card-type">' + escapeHtml(typeInfo.icon + ' ' + typeInfo.label) +
                (comment.status === 'resolved' ? ' · 已解决' : '') +
            '</div>' +
            '<div class="cmt-hover-card-content">' + escapeHtml(comment.content) + '</div>' +
            '<div class="cmt-hover-card-meta">' +
                escapeHtml(comment.author) + ' · ' + escapeHtml(formatTime(comment.createdAt)) +
                (comment.replies && comment.replies.length ? ' · ' + comment.replies.length + ' 条回复' : '') +
            '</div>';

        var rect = mark.getBoundingClientRect();
        var scrollY = window.scrollY;
        var scrollX = window.scrollX;
        hoverCardEl.style.left = (rect.left + scrollX) + 'px';
        hoverCardEl.style.top = (rect.bottom + scrollY + 6) + 'px';
        hoverCardEl.classList.add('cmt-visible');
    }

    function scheduleHideHoverCard() {
        if (hoverCardTimer) clearTimeout(hoverCardTimer);
        hoverCardTimer = setTimeout(function () {
            if (hoverCardEl) hoverCardEl.classList.remove('cmt-visible');
        }, 200);
    }

    /* ========================================================
     * 九、底部抽屉评论区
     * ======================================================== */

    function ensureDrawer() {
        if (drawerEl) return drawerEl;
        drawerEl = document.createElement('aside');
        drawerEl.className = 'cmt-drawer';
        drawerEl.setAttribute('aria-label', '批注列表');
        drawerEl.innerHTML =
            '<div class="cmt-drawer-header" role="button" tabindex="0" aria-label="展开/收起批注">' +
                '<span class="cmt-drawer-title">评论</span>' +
                '<span class="cmt-drawer-count">0 · 未解决 0</span>' +
                '<div class="cmt-drawer-actions">' +
                    '<button type="button" class="cmt-btn-text cmt-drawer-export">导出</button>' +
                    '<button type="button" class="cmt-btn-text cmt-drawer-expert">专家团</button>' +
                '</div>' +
                '<button type="button" class="cmt-drawer-toggle" aria-label="展开">▲</button>' +
            '</div>' +
            '<div class="cmt-drawer-body">' +
                '<div class="cmt-version-warning" id="cmtVersionWarning" role="alert" hidden>' +
                    '<span class="cmt-version-warning-icon">⚠</span>' +
                    '<span class="cmt-version-warning-text">原文已更新，部分高亮可能偏移</span>' +
                    '<button type="button" class="cmt-version-warning-close" aria-label="关闭提示">×</button>' +
                '</div>' +
                '<div class="cmt-filter-bar">' +
                    '<select class="cmt-filter-select cmt-filter-type" aria-label="按类型筛选">' +
                        '<option value="all">全部类型</option>' +
                        '<option value="error">❗ 错误</option>' +
                        '<option value="praise">👍 夸奖</option>' +
                        '<option value="discussion">💬 讨论</option>' +
                        '<option value="supplement">➕ 补充</option>' +
                        '<option value="thought">✦ 感想</option>' +
                    '</select>' +
                    '<select class="cmt-filter-select cmt-filter-status" aria-label="按状态筛选">' +
                        '<option value="all">全部状态</option>' +
                        '<option value="open">未解决</option>' +
                        '<option value="resolved">已解决</option>' +
                    '</select>' +
                    '<input type="text" class="cmt-filter-input" placeholder="搜索关键词…" aria-label="搜索批注">' +
                '</div>' +
                '<div class="cmt-drawer-content">' +
                    '<ul class="cmt-thread-list" id="cmtThreadList"></ul>' +
                    '<div class="cmt-detail" id="cmtDetail"></div>' +
                '</div>' +
            '</div>';
        document.body.appendChild(drawerEl);

        // 事件绑定
        var header = drawerEl.querySelector('.cmt-drawer-header');
        header.addEventListener('click', toggleDrawer);
        header.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleDrawer();
            }
        });

        drawerEl.querySelector('.cmt-drawer-toggle').addEventListener('click', function (e) {
            e.stopPropagation();
            toggleDrawer();
        });

        drawerEl.querySelector('.cmt-drawer-export').addEventListener('click', function (e) {
            e.stopPropagation();
            if (currentNotePath) {
                exportNote(currentNotePath);
            } else {
                exportAll();
            }
        });

        drawerEl.querySelector('.cmt-drawer-expert').addEventListener('click', function (e) {
            e.stopPropagation();
            triggerExpertReview();
        });

        drawerEl.querySelector('.cmt-filter-type').addEventListener('change', function (e) {
            filterState.type = e.target.value;
            renderThreadList();
        });

        drawerEl.querySelector('.cmt-filter-status').addEventListener('change', function (e) {
            filterState.status = e.target.value;
            renderThreadList();
        });

        drawerEl.querySelector('.cmt-filter-input').addEventListener('input', function (e) {
            filterState.keyword = e.target.value.trim().toLowerCase();
            renderThreadList();
        });

        // 版本警告关闭按钮
        var warnClose = drawerEl.querySelector('.cmt-version-warning-close');
        if (warnClose) {
            warnClose.addEventListener('click', function (e) {
                e.stopPropagation();
                var w = drawerEl.querySelector('#cmtVersionWarning');
                if (w) w.hidden = true;
            });
        }

        return drawerEl;
    }

    function toggleDrawer() {
        if (drawerExpanded) {
            collapseDrawer();
        } else {
            expandDrawer();
        }
    }

    function expandDrawer() {
        ensureDrawer();
        drawerEl.classList.add('cmt-expanded');
        drawerExpanded = true;
        renderThreadList();
    }

    function collapseDrawer() {
        if (!drawerEl) return;
        drawerEl.classList.remove('cmt-expanded');
        drawerExpanded = false;
    }

    function renderDrawer() {
        ensureDrawer();
        var comments = Storage.loadComments(currentNotePath);
        var threads = comments.filter(function (c) { return !c.parentId; });
        var unresolved = threads.filter(function (t) { return t.status === 'open'; }).length;
        var countEl = drawerEl.querySelector('.cmt-drawer-count');
        countEl.textContent = threads.length + ' · 未解决 ' + unresolved;
        updateVersionWarning(comments);
        renderThreadList();
    }

    /**
     * 比对 anchor.version 与当前笔记版本，不一致时在抽屉顶部提示
     * checklist 2.4：加载评论时检测版本偏移
     */
    function updateVersionWarning(comments) {
        var warnEl = drawerEl.querySelector('#cmtVersionWarning');
        if (!warnEl) return;
        var currentVersion = (currentMeta && (currentMeta.created_at || currentMeta.version)) || todayStr();
        var mismatch = false;
        for (var i = 0; i < comments.length; i++) {
            var c = comments[i];
            if (c.deleted) continue;
            if (c.anchor && c.anchor.version && c.anchor.version !== currentVersion) {
                mismatch = true;
                break;
            }
        }
        warnEl.hidden = !mismatch;
    }

    /**
     * 渲染评论列表
     */
    function renderThreadList() {
        if (!drawerEl) return;
        var listEl = drawerEl.querySelector('#cmtThreadList');
        var detailEl = drawerEl.querySelector('#cmtDetail');
        listEl.innerHTML = '';

        var comments = Storage.loadComments(currentNotePath);
        var threads = comments.filter(function (c) { return !c.parentId; });

        // 筛选
        threads = threads.filter(function (c) {
            if (filterState.type !== 'all' && c.type !== filterState.type) return false;
            if (filterState.status !== 'all' && c.status !== filterState.status) return false;
            if (filterState.keyword) {
                var hay = (c.content + ' ' + (c.anchor ? c.anchor.quote : '')).toLowerCase();
                if (hay.indexOf(filterState.keyword) === -1) return false;
            }
            return true;
        });

        // 排序：按位置（rangeStart）升序，无锚点排末尾
        threads.sort(function (a, b) {
            var aStart = a.anchor ? (a.anchor.rangeStart || a.anchor.charOffsetStart || 0) : Infinity;
            var bStart = b.anchor ? (b.anchor.rangeStart || b.anchor.charOffsetStart || 0) : Infinity;
            if (aStart === Infinity && bStart === Infinity) {
                return new Date(a.createdAt) - new Date(b.createdAt);
            }
            return aStart - bStart;
        });

        if (threads.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'cmt-empty';
            empty.innerHTML = '<div class="cmt-empty-icon">✎</div>' +
                (comments.length === 0 ? '暂无批注，圈选原文即可开始批注' : '没有符合条件的批注');
            listEl.appendChild(empty);
            detailEl.classList.remove('cmt-visible');
            detailEl.innerHTML = '';
            listEl.classList.remove('has-detail');
            return;
        }

        // 检查是否有详情打开
        var hasDetail = activeThreadId && threads.some(function (t) { return t.id === activeThreadId; });
        if (hasDetail) {
            listEl.classList.add('has-detail');
            detailEl.classList.add('cmt-visible');
        } else {
            listEl.classList.remove('has-detail');
            detailEl.classList.remove('cmt-visible');
            detailEl.innerHTML = '';
            activeThreadId = null;
        }

        for (var i = 0; i < threads.length; i++) {
            listEl.appendChild(renderThreadItem(threads[i]));
        }

        if (hasDetail) {
            renderThreadDetail(activeThreadId);
        }
    }

    function renderThreadItem(comment) {
        var li = document.createElement('li');
        li.className = 'cmt-thread';
        li.setAttribute('data-cm-id', comment.id);
        li.setAttribute('data-cmt-type', comment.type);
        li.setAttribute('data-cmt-status', comment.status);
        li.setAttribute('tabindex', '0');
        li.setAttribute('role', 'button');
        li.setAttribute('aria-label', (TYPES[comment.type] || {}).label + ' 批注');

        if (comment.id === activeThreadId) {
            li.classList.add('cmt-active');
        }

        var typeInfo = TYPES[comment.type] || { label: '批注', icon: '' };
        var quote = comment.anchor ? comment.anchor.quote : '';
        var isOrphan = comment.anchor && !hasHighlight(comment.id);

        var head = document.createElement('div');
        head.className = 'cmt-thread-head';
        head.innerHTML =
            '<span class="cmt-thread-type">' + escapeHtml(typeInfo.icon + ' ' + typeInfo.label) + '</span>' +
            '<span class="cmt-thread-meta">' + escapeHtml(comment.author + ' · ' + formatTime(comment.createdAt)) + '</span>' +
            '<span class="cmt-thread-status">' + (comment.status === 'resolved' ? '✓ 已解决' : '') + '</span>';

        li.appendChild(head);

        if (quote) {
            var quoteEl = document.createElement('div');
            quoteEl.className = 'cmt-thread-quote';
            quoteEl.textContent = '「' + quote + '」';
            li.appendChild(quoteEl);
        }

        var contentEl = document.createElement('div');
        contentEl.className = 'cmt-thread-content';
        contentEl.textContent = comment.content;
        li.appendChild(contentEl);

        if (isOrphan) {
            var orphanEl = document.createElement('div');
            orphanEl.className = 'cmt-thread-orphan';
            orphanEl.textContent = '⚠ 原文已变更，未能定位';
            li.appendChild(orphanEl);
        }

        if (comment.replies && comment.replies.length > 0) {
            var repliesEl = document.createElement('div');
            repliesEl.className = 'cmt-thread-replies-count';
            repliesEl.textContent = '💬 ' + comment.replies.length + ' 条回复';
            li.appendChild(repliesEl);
        }

        li.addEventListener('click', function (e) {
            e.stopPropagation();
            selectThread(comment.id);
        });
        li.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectThread(comment.id);
            }
        });

        return li;
    }

    function hasHighlight(commentId) {
        if (!currentContainer) return false;
        return currentContainer.querySelector('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]') !== null;
    }

    function selectThread(commentId) {
        activeThreadId = commentId;
        renderThreadList();
        renderThreadDetail(commentId);
        // 滚动到原文
        scrollToHighlight(commentId);
    }

    function scrollToHighlight(commentId) {
        if (!currentContainer) return;
        var mark = currentContainer.querySelector('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        if (mark) {
            mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
            mark.classList.add('cmt-flash');
            setTimeout(function () { mark.classList.remove('cmt-flash'); }, 600);
        }
    }

    /**
     * 渲染详情面板
     */
    function renderThreadDetail(commentId) {
        if (!drawerEl) return;
        var detailEl = drawerEl.querySelector('#cmtDetail');
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) {
            detailEl.classList.remove('cmt-visible');
            detailEl.innerHTML = '';
            return;
        }

        detailEl.classList.add('cmt-visible');
        detailEl.innerHTML = '';

        var typeInfo = TYPES[comment.type] || { label: '批注', icon: '' };

        // 头部
        var header = document.createElement('div');
        header.className = 'cmt-detail-header';
        header.innerHTML =
            '<span class="cmt-detail-type">' + escapeHtml(typeInfo.icon + ' ' + typeInfo.label) + '</span>' +
            '<span class="cmt-detail-meta">' + escapeHtml(comment.author + ' · ' + formatTime(comment.createdAt)) + '</span>' +
            '<button type="button" class="cmt-detail-close" aria-label="关闭详情">×</button>';
        detailEl.appendChild(header);
        header.querySelector('.cmt-detail-close').addEventListener('click', function () {
            activeThreadId = null;
            renderThreadList();
        });

        // 内容区
        var body = document.createElement('div');
        body.className = 'cmt-detail-body';

        // 引用原文
        if (comment.anchor && comment.anchor.quote) {
            var quoteEl = document.createElement('div');
            quoteEl.className = 'cmt-detail-quote';
            quoteEl.textContent = '「' + comment.anchor.quote + '」';
            body.appendChild(quoteEl);
        }

        // 正文
        var contentEl = document.createElement('div');
        contentEl.className = 'cmt-detail-content';
        contentEl.textContent = comment.content;
        body.appendChild(contentEl);

        // 专家评判
        if (comment.expertReviews && comment.expertReviews.length > 0) {
            var expertSection = document.createElement('div');
            expertSection.style.marginBottom = '10px';
            var expertTitle = document.createElement('div');
            expertTitle.style.fontSize = '0.78rem';
            expertTitle.style.color = 'var(--ink-muted)';
            expertTitle.style.marginBottom = '4px';
            expertTitle.textContent = '专家评判：';
            expertSection.appendChild(expertTitle);
            for (var ei = 0; ei < comment.expertReviews.length; ei++) {
                expertSection.appendChild(renderExpertBadge(comment.expertReviews[ei], comment.id, ei));
            }
            body.appendChild(expertSection);
        }

        // 回复列表
        if (comment.replies && comment.replies.length > 0) {
            var replyList = document.createElement('ul');
            replyList.className = 'cmt-reply-list';
            for (var ri = 0; ri < comment.replies.length; ri++) {
                replyList.appendChild(renderReplyItem(comment.replies[ri]));
            }
            body.appendChild(replyList);
        }

        // 回复输入
        var replyInput = document.createElement('textarea');
        replyInput.className = 'cmt-reply-input';
        replyInput.placeholder = '回复…（Ctrl+Enter 提交）';
        body.appendChild(replyInput);

        var replyBtnRow = document.createElement('div');
        replyBtnRow.style.textAlign = 'right';
        replyBtnRow.style.marginBottom = '8px';
        var replyBtn = document.createElement('button');
        replyBtn.type = 'button';
        replyBtn.className = 'cmt-btn cmt-btn-primary';
        replyBtn.textContent = '回复';
        replyBtn.style.fontSize = '0.8rem';
        replyBtn.style.padding = '3px 10px';
        replyBtnRow.appendChild(replyBtn);
        body.appendChild(replyBtnRow);

        replyInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                doReply(commentId, replyInput);
            }
        });
        replyBtn.addEventListener('click', function () {
            doReply(commentId, replyInput);
        });

        // 操作按钮
        var actions = document.createElement('div');
        actions.className = 'cmt-detail-actions';

        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'cmt-btn cmt-btn-ghost';
        editBtn.textContent = '编辑';
        editBtn.addEventListener('click', function () { startEdit(commentId, body); });
        actions.appendChild(editBtn);

        var statusBtn = document.createElement('button');
        statusBtn.type = 'button';
        statusBtn.className = 'cmt-btn cmt-btn-ghost';
        statusBtn.textContent = comment.status === 'open' ? '解决' : '重新打开';
        statusBtn.setAttribute('aria-pressed', comment.status === 'resolved');
        statusBtn.addEventListener('click', function () {
            toggleResolve(commentId);
        });
        actions.appendChild(statusBtn);

        var jumpBtn = document.createElement('button');
        jumpBtn.type = 'button';
        jumpBtn.className = 'cmt-btn cmt-btn-ghost';
        jumpBtn.textContent = '跳转原文';
        jumpBtn.addEventListener('click', function () { scrollToHighlight(commentId); });
        actions.appendChild(jumpBtn);

        var copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'cmt-btn cmt-btn-ghost';
        copyBtn.textContent = '复制原文';
        copyBtn.addEventListener('click', function () {
            var text = comment.anchor ? comment.anchor.quote : '';
            copyToClipboard(text);
        });
        actions.appendChild(copyBtn);

        var delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'cmt-btn cmt-btn-ghost';
        delBtn.textContent = '删除';
        delBtn.style.color = 'var(--cmtC-bar-error)';
        delBtn.addEventListener('click', function () { deleteComment(commentId); });
        actions.appendChild(delBtn);

        body.appendChild(actions);
        detailEl.appendChild(body);
    }

    function renderReplyItem(reply) {
        var li = document.createElement('li');
        li.className = 'cmt-reply';
        li.innerHTML =
            '<div class="cmt-reply-head">' + escapeHtml(reply.author + ' · ' + formatTime(reply.createdAt)) + '</div>' +
            '<div class="cmt-reply-content"></div>';
        li.querySelector('.cmt-reply-content').textContent = reply.content;
        return li;
    }

    function renderExpertBadge(review, commentId, idx) {
        var verdictMap = { accept: '采纳', reject: '不采纳', needs_discussion: '待议' };
        var wrapper = document.createElement('div');
        var badge = document.createElement('span');
        badge.className = 'cmt-expert-badge';
        badge.setAttribute('data-verdict', review.verdict);
        badge.textContent = verdictMap[review.verdict] || review.verdict;
        badge.style.cursor = 'pointer';
        badge.addEventListener('click', function () {
            var detail = wrapper.querySelector('.cmt-expert-detail');
            if (detail) detail.classList.toggle('cmt-visible');
        });
        wrapper.appendChild(badge);

        var detail = document.createElement('div');
        detail.className = 'cmt-expert-detail';

        if (review.rationale) {
            var rRow = document.createElement('div');
            rRow.appendChild(makeStrong('理由：'));
            rRow.appendChild(document.createTextNode(review.rationale));
            detail.appendChild(rRow);
        }
        if (review.suggestedEdit && review.suggestedEdit.text) {
            var sRow = document.createElement('div');
            sRow.style.marginTop = '4px';
            sRow.appendChild(makeStrong('建议：'));
            sRow.appendChild(document.createTextNode(review.suggestedEdit.text));
            detail.appendChild(sRow);

            // 「应用建议」按钮：复制 suggestedEdit.text 到剪贴板
            var applyBtn = document.createElement('button');
            applyBtn.type = 'button';
            applyBtn.className = 'cmt-btn-apply-suggestion';
            applyBtn.textContent = '应用建议';
            applyBtn.style.marginTop = '4px';
            applyBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                copyToClipboard(review.suggestedEdit.text);
            });
            detail.appendChild(applyBtn);
        }
        if (review.reviewedBy && review.reviewedBy.length) {
            var rvRow = document.createElement('div');
            rvRow.style.marginTop = '4px';
            rvRow.style.fontSize = '0.76rem';
            rvRow.appendChild(makeStrong('评审：'));
            rvRow.appendChild(document.createTextNode(review.reviewedBy.join(', ')));
            detail.appendChild(rvRow);
        }
        wrapper.appendChild(detail);
        return wrapper;
    }

    // 创建 <strong> 文本节点工具
    function makeStrong(text) {
        var s = document.createElement('strong');
        s.textContent = text;
        return s;
    }

    /* ========================================================
     * 十、评论操作
     * ======================================================== */

    function doReply(commentId, inputEl) {
        var content = inputEl.value.trim();
        if (!content) return;
        var all = Storage.loadAllCommentsRaw(currentNotePath);
        var comment = all.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        if (!comment.replies) comment.replies = [];
        comment.replies.push({
            id: genReplyId(),
            content: content,
            author: '作者',
            createdAt: nowIso()
        });
        comment.updatedAt = nowIso();
        Storage.saveComments(currentNotePath, all);
        inputEl.value = '';
        renderDrawer();
        renderThreadDetail(commentId);
        toast('已回复');
    }

    function toggleResolve(commentId) {
        var all = Storage.loadAllCommentsRaw(currentNotePath);
        var comment = all.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        if (comment.status === 'open') {
            comment.status = 'resolved';
            comment.resolvedAt = nowIso();
        } else {
            comment.status = 'open';
            comment.resolvedAt = null;
        }
        comment.updatedAt = nowIso();
        Storage.saveComments(currentNotePath, all);
        updateHighlightStatus(commentId, comment.status);
        renderDrawer();
        renderThreadDetail(commentId);
        toast(comment.status === 'resolved' ? '已标记为解决' : '已重新打开');
    }

    function deleteComment(commentId) {
        if (!confirm('确认删除这条批注？')) return;
        var all = Storage.loadAllCommentsRaw(currentNotePath);
        var comment = all.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.deleted = true;
        comment.updatedAt = nowIso();
        Storage.saveComments(currentNotePath, all);
        unwrapHighlight(commentId);
        activeThreadId = null;
        renderDrawer();
        toast('已删除');
    }

    function startEdit(commentId, bodyEl) {
        var all = Storage.loadAllCommentsRaw(currentNotePath);
        var comment = all.find(function (c) { return c.id === commentId; });
        if (!comment) return;

        var contentEl = bodyEl.querySelector('.cmt-detail-content');
        if (!contentEl) return;

        // 类型选择器
        var typeRow = document.createElement('div');
        typeRow.style.marginBottom = '6px';
        var typeLabel = document.createElement('span');
        typeLabel.style.fontSize = '0.8rem';
        typeLabel.style.color = 'var(--ink-muted)';
        typeLabel.style.marginRight = '6px';
        typeLabel.textContent = '类型：';
        var typeSelect = document.createElement('select');
        typeSelect.className = 'cmt-popover-select';
        typeSelect.style.fontSize = '0.8rem';
        var typeKeys = Object.keys(TYPES);
        for (var i = 0; i < typeKeys.length; i++) {
            var opt = document.createElement('option');
            opt.value = typeKeys[i];
            opt.textContent = TYPES[typeKeys[i]].icon + ' ' + TYPES[typeKeys[i]].label;
            if (comment.type === typeKeys[i]) opt.selected = true;
            typeSelect.appendChild(opt);
        }
        typeRow.appendChild(typeLabel);
        typeRow.appendChild(typeSelect);

        var input = document.createElement('textarea');
        input.className = 'cmt-detail-edit-input';
        input.value = comment.content;

        var btnRow = document.createElement('div');
        btnRow.style.textAlign = 'right';
        btnRow.style.marginBottom = '8px';

        var saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'cmt-btn cmt-btn-primary';
        saveBtn.textContent = '保存';
        saveBtn.style.fontSize = '0.8rem';
        saveBtn.style.padding = '3px 10px';

        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'cmt-btn cmt-btn-ghost';
        cancelBtn.textContent = '取消';
        cancelBtn.style.fontSize = '0.8rem';
        cancelBtn.style.marginRight = '6px';

        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(saveBtn);

        contentEl.style.display = 'none';
        contentEl.parentNode.insertBefore(typeRow, contentEl.nextSibling);
        typeRow.parentNode.insertBefore(input, typeRow.nextSibling);
        input.parentNode.insertBefore(btnRow, input.nextSibling);

        saveBtn.addEventListener('click', function () {
            var newContent = input.value.trim();
            if (!newContent) return;
            var newType = typeSelect.value;
            var typeChanged = newType !== comment.type;
            comment.content = newContent;
            comment.type = newType;
            comment.updatedAt = nowIso();
            Storage.saveComments(currentNotePath, all);
            // 类型变更时重新高亮
            if (typeChanged) {
                unwrapHighlight(commentId);
                var range = resolveAnchor(comment.anchor, currentContainer);
                if (range) {
                    try {
                        wrapRangeWithHighlight(range, comment.id, comment.type, comment.status);
                    } catch (e) { /* ignore */ }
                }
            }
            renderDrawer();
            renderThreadDetail(commentId);
            toast('已更新');
        });
        cancelBtn.addEventListener('click', function () {
            typeRow.remove();
            input.remove();
            btnRow.remove();
            contentEl.style.display = '';
        });
        input.focus();
    }

    /* ========================================================
     * 十一、导出 / 导入
     * ======================================================== */

    /**
     * 导出单篇笔记评论
     */
    function exportNote(notePath) {
        // 异步获取笔记原文，再生成导出 JSON
        fetchNoteContent(notePath).then(function (noteContent) {
            var comments = Storage.loadComments(notePath);
            // spec 6.1：scope=note 时，每条 comment 附 noteContent 字段（笔记全文）
            var commentsWithContent = comments.map(function (c) {
                var copy = Object.assign({}, c);
                copy.noteContent = noteContent;
                return copy;
            });
            var meta = Storage.loadMeta();
            var data = {
                schema: 'deep-reading-comments/v1',
                schemaVersion: SCHEMA_VERSION,
                exportedAt: nowIso(),
                exportedBy: '作者',
                scope: 'note',
                notePath: notePath,
                noteContent: noteContent,
                projectContext: {
                    rulesFile: '.trae/rules/rules.md',
                    notesDir: 'output/',
                    agents: AGENTS
                },
                comments: commentsWithContent
            };
            var filename = 'comments_' + safeFilename(notePath) + '_' + todayStr() + '.json';
            downloadJSON(filename, data);
            meta.lastExportAt = nowIso();
            Storage.saveMeta(meta);
            toast('已导出 ' + comments.length + ' 条批注');
        }).catch(function (err) {
            toast('导出失败：' + (err && err.message ? err.message : err));
        });
    }

    /**
     * 读取笔记原文（Markdown），用于导出时附 noteContent 字段
     * 与 app.js 的 fetch 路径保持一致：notes/<path>
     */
    function fetchNoteContent(notePath) {
        return fetch('notes/' + encodeURI(notePath))
            .then(function (r) {
                if (!r.ok) throw new Error('请求失败 (' + r.status + ')');
                return r.text();
            })
            .then(function (text) {
                // 剥离 frontmatter，仅保留正文（与渲染逻辑一致）
                var fmMatch = text.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/);
                return fmMatch ? text.slice(fmMatch[0].length) : text;
            });
    }

    /**
     * 导出全站评论
     */
    function exportAll() {
        var index = Storage.loadIndex();
        var notes = [];
        var totalComments = 0;
        for (var i = 0; i < index.length; i++) {
            var np = index[i].notePath;
            var comments = Storage.loadComments(np);
            if (comments.length > 0) {
                notes.push({ notePath: np, comments: comments });
                totalComments += comments.length;
            }
        }
        var meta = Storage.loadMeta();
        var data = {
            schema: 'deep-reading-comments/v1',
            schemaVersion: SCHEMA_VERSION,
            exportedAt: nowIso(),
            exportedBy: '作者',
            scope: 'all',
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                agents: AGENTS
            },
            notes: notes
        };
        var filename = 'comments_all_' + todayStr() + '.json';
        downloadJSON(filename, data);
        meta.lastExportAt = nowIso();
        Storage.saveMeta(meta);
        toast('已导出 ' + totalComments + ' 条批注');
    }

    /**
     * 导入评论 JSON
     */
    function importJSON(jsonStr, mode) {
        try {
            var data = JSON.parse(jsonStr);
        } catch (e) {
            toast('JSON 解析失败：' + e.message);
            return { success: false, imported: 0, skipped: 0 };
        }

        // 兼容两种格式：单篇（comments 数组）或全站（notes 数组）
        var noteGroups = [];
        if (data.notes && Array.isArray(data.notes)) {
            noteGroups = data.notes;
        } else if (data.comments && Array.isArray(data.comments)) {
            noteGroups = [{ notePath: data.notePath, comments: data.comments }];
        } else if (Array.isArray(data)) {
            // 直接是评论数组
            var grouped = {};
            for (var i = 0; i < data.length; i++) {
                var np = data[i].notePath;
                if (!grouped[np]) grouped[np] = [];
                grouped[np].push(data[i]);
            }
            for (var k in grouped) {
                noteGroups.push({ notePath: k, comments: grouped[k] });
            }
        } else {
            toast('JSON 格式不符，缺少 comments 或 notes 字段');
            return { success: false, imported: 0, skipped: 0 };
        }

        var imported = 0;
        var skipped = 0;

        for (var gi = 0; gi < noteGroups.length; gi++) {
            var group = noteGroups[gi];
            if (!group.notePath || !Array.isArray(group.comments)) continue;

            var existing = mode === 'replace' ? [] : Storage.loadAllCommentsRaw(group.notePath);
            var existingIds = {};
            for (var ei = 0; ei < existing.length; ei++) {
                existingIds[existing[ei].id] = true;
            }

            for (var ci = 0; ci < group.comments.length; ci++) {
                var c = group.comments[ci];
                // 校验必填字段
                if (!c.id || !c.content) {
                    skipped++;
                    continue;
                }
                // 校验 type
                if (c.type && !TYPES[c.type]) {
                    c.type = 'discussion';
                }
                // 确保字段完整
                if (!c.status) c.status = 'open';
                if (!c.replies) c.replies = [];
                if (!c.expertReviews) c.expertReviews = [];
                if (c.deleted === undefined) c.deleted = false;
                if (!c.createdAt) c.createdAt = nowIso();
                if (!c.author) c.author = '作者';
                if (!c.notePath) c.notePath = group.notePath;

                if (mode === 'merge' && existingIds[c.id]) {
                    // 覆盖已有
                    for (var ri = 0; ri < existing.length; ri++) {
                        if (existing[ri].id === c.id) {
                            existing[ri] = Object.assign({}, existing[ri], c, { updatedAt: nowIso() });
                            break;
                        }
                    }
                } else {
                    existing.push(c);
                }
                imported++;
            }
            Storage.saveComments(group.notePath, existing);
        }

        // 刷新当前视图
        if (currentNotePath) {
            refresh();
            renderDrawer();
        }
        toast('已导入 ' + imported + ' 条' + (skipped > 0 ? '，跳过 ' + skipped + ' 条' : ''));
        return { success: true, imported: imported, skipped: skipped };
    }

    /**
     * 导出 AI 友好格式
     */
    function exportForAgents(notePath) {
        var comments = Storage.loadComments(notePath);
        var threads = [];
        for (var i = 0; i < comments.length; i++) {
            var c = comments[i];
            if (c.parentId) continue;
            var messages = [{
                id: c.id,
                author: c.author,
                type: c.type,
                content: c.content,
                createdAt: c.createdAt
            }];
            if (c.replies) {
                for (var ri = 0; ri < c.replies.length; ri++) {
                    messages.push({
                        id: c.replies[ri].id,
                        author: c.replies[ri].author,
                        type: c.type,
                        content: c.replies[ri].content,
                        createdAt: c.replies[ri].createdAt
                    });
                }
            }
            threads.push({
                threadId: c.id,
                anchor: c.anchor ? {
                    quote: c.anchor.quote || c.anchor.exact,
                    rangeStart: c.anchor.rangeStart || c.anchor.charOffsetStart,
                    rangeEnd: c.anchor.rangeEnd || c.anchor.charOffsetEnd,
                    prefix: c.anchor.prefix,
                    suffix: c.anchor.suffix,
                    headingPath: c.anchor.headingPath
                } : null,
                status: c.status,
                tags: c.tags || [],
                targetAgent: c.agentHints ? c.agentHints.targetAgent : null,
                priority: c.agentHints ? c.agentHints.priority : null,
                messages: messages
            });
        }

        // 解析 book/chapter/event
        var parts = notePath.replace(/\.md$/i, '').split(/[\/\\]/);
        var book = parts[0] || '';
        var chapter = parts.length > 1 ? parts[1] : '';
        var event = parts.length > 2 ? parts.slice(2).join('_') : '';

        return JSON.stringify({
            schema: 'deep-reading-comments/v1',
            schemaVersion: SCHEMA_VERSION,
            exportedAt: nowIso(),
            notePath: notePath,
            book: book,
            chapter: chapter,
            event: event,
            threads: threads
        }, null, 2);
    }

    /**
     * 复制为 Prompt 上下文
     */
    function copyAsPromptContext(notePath) {
        var text = formatCommentsAsPrompt(notePath);
        return copyToClipboard(text);
    }

    function formatCommentsAsPrompt(notePath) {
        var comments = Storage.loadComments(notePath);
        var lines = ['# 作者批注上下文', '笔记：' + notePath, ''];
        var idx = 0;
        for (var i = 0; i < comments.length; i++) {
            var c = comments[i];
            if (c.parentId) continue;
            idx++;
            var typeInfo = TYPES[c.type] || { label: '批注' };
            var header = '## 批注 ' + idx + ' [' + typeInfo.label + ']';
            if (c.agentHints && c.agentHints.targetAgent) {
                header += ' [目标专家: ' + c.agentHints.targetAgent + ']';
            }
            if (c.agentHints && c.agentHints.priority) {
                header += ' [优先级: ' + c.agentHints.priority + ']';
            }
            lines.push(header);
            if (c.anchor && c.anchor.quote) {
                lines.push('原文：「' + c.anchor.quote + '」');
            }
            lines.push('作者：' + c.content);
            if (c.replies) {
                for (var ri = 0; ri < c.replies.length; ri++) {
                    lines.push('回复：' + c.replies[ri].content);
                }
            }
            lines.push('');
        }
        return lines.join('\n');
    }

    function copyToClipboard(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(function () {
                toast('已复制到剪贴板');
            }).catch(function () {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
            return Promise.resolve();
        }
    }

    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            toast('已复制到剪贴板');
        } catch (e) {
            toast('复制失败');
        }
        document.body.removeChild(ta);
    }

    /* ========================================================
     * 十二、专家团触发
     * ======================================================== */

    function triggerExpertReview() {
        if (!currentNotePath) {
            toast('请先选择一篇笔记');
            return;
        }
        var comments = Storage.loadComments(currentNotePath);
        if (comments.length === 0) {
            toast('暂无批注可评判');
            return;
        }
        openExpertWizard();
    }

    function openExpertWizard() {
        // 移除已有
        var existing = document.getElementById('cmtWizard');
        if (existing) existing.remove();

        var wizard = document.createElement('div');
        wizard.id = 'cmtWizard';
        wizard.className = 'cmt-wizard';
        wizard.innerHTML =
            '<div class="cmt-wizard-dialog" role="dialog" aria-modal="true" aria-labelledby="cmtWizardTitle">' +
                '<div class="cmt-wizard-header">' +
                    '<h2 id="cmtWizardTitle">启用专家团评判</h2>' +
                    '<button type="button" class="modal-close cmt-wizard-close" aria-label="关闭">&times;</button>' +
                '</div>' +
                '<div class="cmt-wizard-body">' +
                    '<div class="cmt-wizard-field">' +
                        '<label>评判范围</label>' +
                        '<select class="cmt-wizard-scope cmt-popover-select" style="width:100%">' +
                            '<option value="note">当前笔记</option>' +
                            '<option value="all">全站</option>' +
                        '</select>' +
                    '</div>' +
                    '<div class="cmt-wizard-field">' +
                        '<label>参与专家</label>' +
                        '<div class="cmt-wizard-checkbox-group">' +
                            AGENTS.map(function (a) {
                                return '<label><input type="checkbox" value="' + a + '" checked> ' + a + '</label>';
                            }).join('') +
                        '</div>' +
                    '</div>' +
                    '<div class="cmt-wizard-field">' +
                        '<label>附加指令</label>' +
                        '<textarea class="cmt-wizard-textarea" placeholder="如：重点核查引文出处、评估讲道理部分是否过度引申…"></textarea>' +
                    '</div>' +
                    '<div class="cmt-wizard-field">' +
                        '<label>本地执行命令</label>' +
                        '<div class="cmt-wizard-cmd">python src/main.py --expert-review expert_review_request.json</div>' +
                    '</div>' +
                    '<div class="cmt-wizard-actions">' +
                        '<button type="button" class="cmt-btn cmt-btn-ghost cmt-wizard-cancel">取消</button>' +
                        '<button type="button" class="cmt-btn cmt-btn-primary cmt-wizard-confirm">生成指令包</button>' +
                    '</div>' +
                '</div>' +
            '</div>';
        document.body.appendChild(wizard);
        setTimeout(function () { wizard.classList.add('cmt-visible'); }, 10);

        var closeFn = function () {
            wizard.classList.remove('cmt-visible');
            setTimeout(function () { wizard.remove(); }, 200);
        };

        wizard.querySelector('.cmt-wizard-close').addEventListener('click', closeFn);
        wizard.querySelector('.cmt-wizard-cancel').addEventListener('click', closeFn);
        wizard.addEventListener('click', function (e) {
            if (e.target === wizard) closeFn();
        });

        wizard.querySelector('.cmt-wizard-confirm').addEventListener('click', function () {
            var scope = wizard.querySelector('.cmt-wizard-scope').value;
            var participants = Array.from(wizard.querySelectorAll('.cmt-wizard-checkbox-group input:checked')).map(function (cb) { return cb.value; });
            var instruction = wizard.querySelector('.cmt-wizard-textarea').value.trim();

            generateExpertRequest(scope, participants, instruction);
            closeFn();
        });

        // Esc 关闭
        var escHandler = function (e) {
            if (e.key === 'Escape') {
                closeFn();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    function generateExpertRequest(scope, participants, instruction) {
        var notePath = currentNotePath;
        var comments = Storage.loadComments(notePath);
        var request = {
            schema: 'deep-reading-expert-review/v1',
            schemaVersion: SCHEMA_VERSION,
            generatedAt: nowIso(),
            scope: scope,
            notePath: scope === 'note' ? notePath : null,
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                agents: AGENTS
            },
            expertReviewRequest: {
                participants: participants.length > 0 ? participants : AGENTS,
                additionalInstruction: instruction || '',
                rulesReference: '.trae/rules/rules.md'
            },
            comments: comments
        };
        var filename = 'expert_review_request_' + safeFilename(notePath) + '_' + todayStr() + '.json';
        downloadJSON(filename, request);
        toast('已生成专家团指令包');
    }

    /* ========================================================
     * 十三、初始化与生命周期
     * ======================================================== */

    /**
     * 为指定容器初始化高亮+选区监听
     */
    function attach(container, notePath) {
        // 先卸载旧的
        detach();

        currentContainer = container;
        currentNotePath = notePath;
        normTextCache = null;

        // 渲染已存高亮
        renderAllHighlights();

        // 选区监听
        container.addEventListener('mouseup', handleSelectionChange);
        container.addEventListener('touchend', handleSelectionChange);
        document.addEventListener('selectionchange', handleSelectionChange);

        // 高亮交互
        container.addEventListener('click', handleContainerClick);
        container.addEventListener('mouseover', handleHighlightMouseOver);
        container.addEventListener('mouseout', handleHighlightMouseOut);

        // 滚动时隐藏气泡
        container.addEventListener('scroll', hideBubble);

        // 渲染抽屉
        ensureDrawer();
        renderDrawer();
    }

    /**
     * 卸载当前笔记的监听
     */
    function detach() {
        if (currentContainer) {
            currentContainer.removeEventListener('mouseup', handleSelectionChange);
            currentContainer.removeEventListener('touchend', handleSelectionChange);
            currentContainer.removeEventListener('click', handleContainerClick);
            currentContainer.removeEventListener('mouseover', handleHighlightMouseOver);
            currentContainer.removeEventListener('mouseout', handleHighlightMouseOut);
            currentContainer.removeEventListener('scroll', hideBubble);
        }
        document.removeEventListener('selectionchange', handleSelectionChange);

        currentContainer = null;
        currentNotePath = null;
        currentMeta = null;
        normTextCache = null;
        activeThreadId = null;

        hideBubble();
        hidePopover();
        if (hoverCardEl) hoverCardEl.classList.remove('cmt-visible');
    }

    /**
     * 重新渲染当前笔记的高亮
     */
    function refresh() {
        if (!currentContainer || !currentNotePath) return;
        // 移除所有高亮
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight');
        for (var i = 0; i < marks.length; i++) {
            var mark = marks[i];
            var parent = mark.parentNode;
            while (mark.firstChild) {
                parent.insertBefore(mark.firstChild, mark);
            }
            parent.removeChild(mark);
            parent.normalize();
        }
        normTextCache = null;
        renderAllHighlights();
        renderDrawer();
    }

    /**
     * spec.md API：初始化
     */
    function init(readerEl) {
        // readerEl 可选，默认用 #reader
        if (!readerEl) {
            readerEl = document.getElementById('reader');
        }
        // 绑定工具栏按钮
        bindToolbarButtons();
    }

    /**
     * spec.md API：加载某笔记的评论
     */
    function loadForNote(notePath) {
        if (!notePath) return;
        var container = document.querySelector('.markdown-body');
        if (container) {
            attach(container, notePath);
        }
    }

    /**
     * spec.md API：清理
     */
    function clear() {
        detach();
    }

    /**
     * 绑定工具栏按钮
     */
    function bindToolbarButtons() {
        var exportBtn = document.getElementById('cmtExportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', function () {
                if (currentNotePath) {
                    exportNote(currentNotePath);
                } else {
                    exportAll();
                }
            });
        }

        var expertBtn = document.getElementById('cmtExpertBtn');
        if (expertBtn) {
            expertBtn.addEventListener('click', triggerExpertReview);
        }

        var importBtn = document.getElementById('cmtImportBtn');
        var importFile = document.getElementById('cmtImportFile');
        if (importBtn && importFile) {
            importBtn.addEventListener('click', function () {
                importFile.click();
            });
            importFile.addEventListener('change', function (e) {
                var file = e.target.files[0];
                if (!file) return;
                var reader = new FileReader();
                reader.onload = function (ev) {
                    var mode = confirm('点击「确定」合并导入（保留已有），点击「取消」替换当前笔记评论') ? 'merge' : 'replace';
                    importJSON(ev.target.result, mode);
                };
                reader.readAsText(file);
                importFile.value = '';
            });
        }
    }

    /* ========================================================
     * 十四、API 查询
     * ======================================================== */

    function getComments(notePath) {
        return Storage.loadComments(notePath);
    }

    function getAllComments() {
        var index = Storage.loadIndex();
        var result = {};
        for (var i = 0; i < index.length; i++) {
            var np = index[i].notePath;
            result[np] = Storage.loadComments(np);
        }
        return result;
    }

    function getIndex() {
        return Storage.loadIndex();
    }

    function clearNote(notePath) {
        Storage.deleteNote(notePath);
        if (notePath === currentNotePath) {
            refresh();
        }
    }

    /* ========================================================
     * 十五、事件监听与启动
     * ======================================================== */

    // 监听 note:loaded 事件（由 app.js dispatch）
    document.addEventListener('note:loaded', function (e) {
        var detail = e.detail || {};
        var notePath = detail.notePath;
        var container = detail.container;
        currentMeta = detail.meta || null;
        if (notePath && container) {
            attach(container, notePath);
        }
    });

    // 多标签页同步
    window.addEventListener('storage', function (e) {
        if (e.key && e.key.indexOf(STORAGE_PREFIX) === 0) {
            if (currentNotePath && e.key === STORAGE_PREFIX + currentNotePath) {
                refresh();
            }
        }
    });

    // Esc 关闭浮层
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            if (activePopover && activePopover.classList.contains('cmt-visible')) {
                hidePopover();
                hideBubble();
            }
        }
    });

    // 初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { init(); });
    } else {
        init();
    }

    /* ========================================================
     * 十六、暴露 API
     * ======================================================== */

    window.DeepReadingComments = {
        // spec.md API
        init: init,
        loadForNote: loadForNote,
        clear: clear,
        // architecture.md API
        attach: attach,
        detach: detach,
        refresh: refresh,
        // 查询
        getComments: getComments,
        getAllComments: getAllComments,
        getIndex: getIndex,
        // 数据操作
        exportNote: exportNote,
        exportAll: exportAll,
        importJSON: importJSON,
        clearNote: clearNote,
        // 专家团
        exportForAgents: exportForAgents,
        copyAsPromptContext: copyAsPromptContext,
        triggerExpertReview: triggerExpertReview
    };

})();
