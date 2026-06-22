/* ============================================================
 * 原文批注式评论系统 · 核心模块（飞书云文档风）
 * ------------------------------------------------------------
 * 设计依据：
 *   - docs/comments-system/architecture.md（锚定算法、存储、模块划分）
 *   - docs/comments-system/spec.md（评论数据模型、AI 导出格式、5 类评论枚举）
 *   - docs/comments-system/design_directions.md（方向 A 飞书云文档风）
 *
 * 模块边界：
 *   - 独立 IIFE，挂到 window.DeepReadingComments
 *   - 不引用 app.js 内部私有变量，仅通过 document 自定义事件 note:loaded 接入
 *   - 所有 DOM 操作在 marked 渲染、sanitizeHtml 清洗之后进行
 *
 * 公开 API（window.DeepReadingComments）：
 *   init() / loadForNote(path) / clear()
 *   getComments(path) / getAllComments() / getIndex()
 *   attach(container, path) / detach() / refresh()
 *   exportNote(path) / exportAll() / importJSON(str, mode) / clearNote(path)
 *   exportForAgents(path) / copyAsPromptContext(path)
 *   exportExpertReviewRequest(path, participants, instruction) / importExpertReview(str)
 * ============================================================ */
(function () {
    'use strict';

    /* ========================================================
     * 一、常量定义
     * ======================================================== */

    // 存储键前缀（遵循 spec.md 8.1 约定）
    var STORAGE_PREFIX = 'drc:';
    var INDEX_KEY = 'drc:index';
    var META_KEY = 'drc:meta';
    var SCHEMA_VERSION = 1;
    var EXPORT_SCHEMA = 'deep-reading-comments/v1';

    // 5 种评论类型（遵循 spec.md 4.4 枚举）：图标 + 颜色 + 中文标签
    var COMMENT_TYPES = {
        error: { label: '错误指正', icon: '❗', color: '#f54a45' },
        praise: { label: '写得好', icon: '👍', color: '#00b42a' },
        discussion: { label: '讨论', icon: '💬', color: '#3370ff' },
        supplement: { label: '补充', icon: '➕', color: '#ff7d00' },
        thought: { label: '感想', icon: '✦', color: '#722ed1' }
    };

    // 专家团 agent 列表（遵循 spec.md 6.1 projectContext.agents）
    var AGENTS = ['historian', 'biographer', 'context_analyst', 'critic', 'philosopher', 'editor'];

    // 禁批注元素：选区与这些元素相交则拒绝（architecture.md 2.2）
    var FORBIDDEN_TAGS = ['SCRIPT', 'STYLE', 'CODE', 'PRE', 'KBD', 'SAMP', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'];

    // 锚定参数
    var FINGERPRINT_LEN = 32;   // 前后缀指纹长度
    var PREFIX_SUFFIX_LEN = 20; // spec.md anchor.prefix/suffix 长度
    var FUZZY_MAX_DISTANCE = 2; // 模糊匹配最大编辑距离
    var QUOTE_MIN_LEN = 2;      // 最短选区长度
    var QUOTE_MAX_LEN = 256;    // 最长选区长度

    /* ========================================================
     * 二、模块状态
     * ======================================================== */

    var state = {
        container: null,        // 当前 .markdown-body 元素
        notePath: null,         // 当前笔记路径
        noteMeta: null,         // 当前笔记 frontmatter
        noteVersion: null,      // 当前笔记版本（用于比对 anchor.version，checklist 2.4）
        comments: [],           // 当前笔记评论数组
        normTextCache: null,    // 规范化纯文本缓存 { normText, charMap, nodeIndex }
        pendingRange: null,     // 当前选区 Range（用于提交时 wrap）
        pendingAnchor: null,    // 当前选区捕获的锚点
        activeThreadId: null,   // 当前激活的线程 ID
        panelCollapsed: false,  // 面板是否折叠
        sortMode: 'position',   // 排序模式：position / time / status
        filterType: 'all',      // 类型筛选
        filterStatus: 'all',    // 状态筛选
        filterKeyword: '',      // 关键词筛选
        showResolved: false,    // 已解决评论默认折叠（spec.md F4 / checklist 1.4）
        storageAvailable: true, // localStorage 是否可用
        selectionTimer: null,   // selectionchange 防抖计时器
        boundHandlers: {}       // 已绑定的事件处理器引用（用于 detach）
    };

    /* ========================================================
     * 三、工具函数
     * ======================================================== */

    /**
     * HTML 转义，防 XSS。
     * @param {string} text
     * @returns {string}
     */
    function escapeHtml(text) {
        if (text == null) return '';
        var div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    /**
     * 生成评论 ID，格式 c_<timestamp>_<seq>（spec.md 4.2）。
     * @returns {string}
     */
    var _idSeq = 0;
    function genId() {
        _idSeq = (_idSeq + 1) % 100000;
        return 'c_' + Date.now() + '_' + _idSeq;
    }

    /**
     * 生成回复 ID，格式 r_<timestamp>_<seq>。
     */
    function genReplyId() {
        _idSeq = (_idSeq + 1) % 100000;
        return 'r_' + Date.now() + '_' + _idSeq;
    }

    /**
     * 当前 ISO 8601 时间戳（带时区）。
     * @returns {string}
     */
    function nowIso() {
        return new Date().toISOString();
    }

    /**
     * 格式化时间为「YYYY-MM-DD HH:mm」。
     * @param {string} iso
     * @returns {string}
     */
    function formatTime(iso) {
        if (!iso) return '';
        try {
            var d = new Date(iso);
            var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
            return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
                ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
        } catch (e) {
            return iso;
        }
    }

    /**
     * 相对时间（如「2 分钟前」）。
     * @param {string} iso
     * @returns {string}
     */
    function relativeTime(iso) {
        if (!iso) return '';
        var diff = Date.now() - new Date(iso).getTime();
        var sec = Math.floor(diff / 1000);
        if (sec < 60) return '刚刚';
        var min = Math.floor(sec / 60);
        if (min < 60) return min + ' 分钟前';
        var hr = Math.floor(min / 60);
        if (hr < 24) return hr + ' 小时前';
        var day = Math.floor(hr / 24);
        if (day < 30) return day + ' 天前';
        return formatTime(iso);
    }

    /**
     * 显示 toast 提示。
     * @param {string} msg
     * @param {string} [type=info] success / error / info / warn
     */
    function toast(msg, type) {
        type = type || 'info';
        var container = document.querySelector('.cmt-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'cmt-toast-container';
            document.body.appendChild(container);
        }
        var icons = { success: '✓', error: '✕', info: 'ℹ', warn: '⚠' };
        var el = document.createElement('div');
        el.className = 'cmt-toast cmt-toast-' + type;
        el.setAttribute('role', 'status');
        var icon = document.createElement('span');
        icon.className = 'cmt-toast-icon';
        icon.textContent = icons[type] || icons.info;
        var text = document.createElement('span');
        text.textContent = msg;
        el.appendChild(icon);
        el.appendChild(text);
        container.appendChild(el);
        setTimeout(function () {
            el.classList.add('cmt-toast-out');
            setTimeout(function () {
                if (el.parentNode) el.parentNode.removeChild(el);
            }, 220);
        }, 2600);
    }

    /**
     * 触发文件下载。
     * @param {string} jsonStr
     * @param {string} filename
     */
    function downloadJSON(jsonStr, filename) {
        var blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
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
     * 安全读取 localStorage（带配额/可用性检测）。
     */
    function lsGet(key) {
        if (!state.storageAvailable) return null;
        try {
            return localStorage.getItem(key);
        } catch (e) {
            state.storageAvailable = false;
            return null;
        }
    }

    function lsSet(key, value) {
        if (!state.storageAvailable) return false;
        try {
            localStorage.setItem(key, value);
            return true;
        } catch (e) {
            if (e && (e.name === 'QuotaExceededError' || e.code === 22)) {
                state.storageAvailable = false;
                toast('本地存储已满，请导出批注后清理', 'warn');
            } else {
                state.storageAvailable = false;
            }
            return false;
        }
    }

    function lsRemove(key) {
        if (!state.storageAvailable) return;
        try {
            localStorage.removeItem(key);
        } catch (e) {
            state.storageAvailable = false;
        }
    }

    /* ========================================================
     * 四、存储层（architecture.md 3.x + spec.md 8.1）
     * ======================================================== */

    var Storage = {
        SCHEMA_VERSION: SCHEMA_VERSION,

        /**
         * 加载某笔记的评论数组。
         * @param {string} notePath
         * @returns {Comment[]}
         */
        loadComments: function (notePath) {
            try {
                var raw = lsGet(STORAGE_PREFIX + notePath);
                var arr = raw ? JSON.parse(raw) : [];
                if (!Array.isArray(arr)) return [];
                return arr.filter(isValidComment);
            } catch (e) {
                return [];
            }
        },

        /**
         * 保存某笔记的评论数组并更新索引。
         * @param {string} notePath
         * @param {Comment[]} comments
         */
        saveComments: function (notePath, comments) {
            var ok = lsSet(STORAGE_PREFIX + notePath, JSON.stringify(comments));
            if (ok) this.updateIndex(notePath, comments);
            this.updateMeta();
            return ok;
        },

        /**
         * 加载全局索引。
         * @returns {IndexEntry[]}
         */
        loadIndex: function () {
            try {
                var raw = lsGet(INDEX_KEY);
                return raw ? JSON.parse(raw) : [];
            } catch (e) {
                return [];
            }
        },

        /**
         * 更新某笔记的索引条目。
         */
        updateIndex: function (notePath, comments) {
            var idx = this.loadIndex().filter(function (e) { return e.notePath !== notePath; });
            var threads = comments.filter(function (c) { return !c.parentId && !c.deleted; });
            idx.push({
                notePath: notePath,
                count: comments.filter(function (c) { return !c.deleted; }).length,
                threadCount: threads.length,
                unresolvedCount: threads.filter(function (t) { return t.status === 'open'; }).length,
                lastUpdatedAt: nowIso()
            });
            lsSet(INDEX_KEY, JSON.stringify(idx));
        },

        /**
         * 删除某笔记全部评论。
         */
        deleteNote: function (notePath) {
            lsRemove(STORAGE_PREFIX + notePath);
            var idx = this.loadIndex().filter(function (e) { return e.notePath !== notePath; });
            lsSet(INDEX_KEY, JSON.stringify(idx));
        },

        /**
         * 加载元信息。
         */
        loadMeta: function () {
            try {
                var raw = lsGet(META_KEY);
                return raw ? JSON.parse(raw) : { schemaVersion: SCHEMA_VERSION, lastExportAt: null };
            } catch (e) {
                return { schemaVersion: SCHEMA_VERSION, lastExportAt: null };
            }
        },

        updateMeta: function () {
            var meta = this.loadMeta();
            meta.schemaVersion = SCHEMA_VERSION;
            lsSet(META_KEY, JSON.stringify(meta));
        }
    };

    /**
     * 校验 Comment 对象基本结构（导入时用）。
     */
    function isValidComment(c) {
        if (!c || typeof c !== 'object') return false;
        if (typeof c.id !== 'string' || typeof c.notePath !== 'string') return false;
        if (typeof c.content !== 'string') return false;
        if (!COMMENT_TYPES[c.type]) return false;
        if (c.status !== 'open' && c.status !== 'resolved') return false;
        return true;
    }

    /* ========================================================
     * 五、文本锚定算法（architecture.md 2.x 核心）
     * ======================================================== */

    /**
     * 判断文本节点是否可批注（architecture.md 2.2）。
     * 排除：script/style/code/pre/kbd/samp/h1-h6 内的文本。
     * @param {Text} node
     * @returns {boolean}
     */
    function isAnnotatableText(node) {
        if (!node || node.nodeType !== Node.TEXT_NODE) return false;
        var parent = node.parentNode;
        if (!parent || parent.nodeType !== Node.ELEMENT_NODE) return false;
        var tag = parent.tagName;
        if (FORBIDDEN_TAGS.indexOf(tag) !== -1) return false;
        // 排除评论系统自身注入的 mark 内的已有高亮文本？不排除——允许在高亮上再批注
        var raw = node.nodeValue;
        if (!raw) return false;
        return raw.replace(/\s+/g, ' ').length > 0;
    }

    /**
     * 判断 Range 是否与禁批注元素相交（architecture.md 2.6 / 4.4）。
     * @param {Range} range
     * @param {Element} container
     * @returns {boolean} true 表示相交（应拒绝）
     */
    function rangeIntersectsForbidden(range, container) {
        var forbidden = container.querySelectorAll(FORBIDDEN_TAGS.join(','));
        for (var i = 0; i < forbidden.length; i++) {
            try {
                if (range.intersectsNode(forbidden[i])) return true;
            } catch (e) {
                // intersectsNode 在某些边界情况抛错，忽略
            }
        }
        return false;
    }

    /**
     * 把原文本映射到归一化文本，记录每个原字符对应的归一化偏移。
     * 处理 \s+ 压缩为单空格的字符丢失。
     * @param {string} raw 原文本
     * @param {string} normalized 归一化后文本
     * @param {number} startNorm 该节点在 normText 中的起始偏移
     * @returns {Array<{nodeOffset:number, normOffset:number, len:number}>}
     */
    function mapRawToNormalized(raw, normalized, startNorm) {
        var segments = [];
        var i = 0, j = 0; // i=raw 索引, j=normalized 索引
        while (i < raw.length) {
            if (/\s/.test(raw[i])) {
                // 跳过连续空白，归一化为一个空格
                var segStart = i;
                while (i < raw.length && /\s/.test(raw[i])) i++;
                // normalized 在此处应有一个空格（除非是首尾，已被 trim）
                if (j < normalized.length && normalized[j] === ' ') {
                    segments.push({ nodeOffset: segStart, normOffset: startNorm + j, len: i - segStart });
                    j++;
                }
            } else {
                segments.push({ nodeOffset: i, normOffset: startNorm + j, len: 1 });
                i++;
                j++;
            }
        }
        return segments;
    }

    /**
     * 构建规范化纯文本与字符映射（architecture.md 2.5）。
     * @param {Element} root
     * @returns {{normText:string, charMap:Array, nodeIndex:WeakMap}}
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
            var raw = textNode.nodeValue;
            var normalized = raw.replace(/\s+/g, ' ');
            if (normalized === '') continue;

            var startNorm = normText.length;
            var segments = mapRawToNormalized(raw, normalized, startNorm);
            nodeIndex.set(textNode, { startNorm: startNorm, segments: segments });

            charMap.push({ node: textNode, startNorm: startNorm, length: normalized.length });
            normText += normalized;
        }

        return { normText: normText, charMap: charMap, nodeIndex: nodeIndex };
    }

    /**
     * 把 DOM 偏移 (node, offset) 映射到规范化文本偏移。
     * @param {Node} node
     * @param {number} offset
     * @param {WeakMap} nodeIndex
     * @returns {{normOffset:number}|null}
     */
    function mapDomOffsetToNorm(node, offset, nodeIndex) {
        if (node.nodeType === Node.TEXT_NODE) {
            var info = nodeIndex.get(node);
            if (!info) return null;
            var segs = info.segments;
            // 在 segments 中找到 nodeOffset <= offset 的最后一段
            var normOff = info.startNorm;
            for (var i = 0; i < segs.length; i++) {
                var s = segs[i];
                if (s.nodeOffset <= offset) {
                    // 若 offset 落在该段内或刚好在段尾
                    if (offset < s.nodeOffset + s.len) {
                        // 段内偏移：空白段无论 offset 在哪都映射到该空格；非空白段 1:1
                        if (s.len === 1 && !/\s/.test(node.nodeValue[s.nodeOffset])) {
                            return { normOffset: s.normOffset };
                        } else if (s.len > 1) {
                            // 空白压缩段，offset 落在其中任一位置都映射到该空格
                            return { normOffset: s.normOffset };
                        } else {
                            return { normOffset: s.normOffset };
                        }
                    }
                } else {
                    break;
                }
                normOff = s.normOffset + 1;
            }
            // offset 在节点末尾
            return { normOffset: info.startNorm + (info.segments.length > 0 ? info.segments[info.segments.length - 1].normOffset - info.startNorm + 1 : 0) };
        } else {
            // 元素节点：offset 是子节点索引，需找到对应文本节点
            var child = node.childNodes[offset];
            if (child && child.nodeType === Node.TEXT_NODE) {
                return mapDomOffsetToNorm(child, 0, nodeIndex);
            }
            // 尝试前一个文本节点末尾
            if (offset > 0) {
                var prev = node.childNodes[offset - 1];
                if (prev) {
                    var lastText = findLastText(prev);
                    if (lastText) {
                        var ni = nodeIndex.get(lastText);
                        if (ni) {
                            var lastSeg = ni.segments[ni.segments.length - 1];
                            return { normOffset: lastSeg.normOffset + 1 };
                        }
                    }
                }
            }
            return null;
        }
    }

    /**
     * 在元素内找最后一个文本节点。
     */
    function findLastText(el) {
        if (el.nodeType === Node.TEXT_NODE) return el;
        if (!el.childNodes || el.childNodes.length === 0) return null;
        for (var i = el.childNodes.length - 1; i >= 0; i--) {
            var t = findLastText(el.childNodes[i]);
            if (t) return t;
        }
        return null;
    }

    /**
     * 把规范化文本偏移区间转换为 DOM Range（architecture.md 2.6）。
     * @param {number} normStart
     * @param {number} normEnd
     * @param {Array} charMap
     * @param {WeakMap} nodeIndex
     * @returns {Range|null}
     */
    function normRangeToDomRange(normStart, normEnd, charMap, nodeIndex) {
        var startInfo = normOffsetToDom(normStart, charMap, nodeIndex, false);
        var endInfo = normOffsetToDom(normEnd, charMap, nodeIndex, true);
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
     * 把单个规范化偏移转为 (node, offset)。
     * @param {number} normOff
     * @param {Array} charMap
     * @param {WeakMap} nodeIndex
     * @param {boolean} isEnd 是否是区间终点（影响偏移取前/后）
     */
    function normOffsetToDom(normOff, charMap, nodeIndex, isEnd) {
        // 在 charMap 中找到包含 normOff 的节点
        for (var i = 0; i < charMap.length; i++) {
            var entry = charMap[i];
            var nodeStart = entry.startNorm;
            var nodeEnd = entry.startNorm + entry.length;
            if (normOff >= nodeStart && normOff <= nodeEnd) {
                var node = entry.node;
                var info = nodeIndex.get(node);
                if (!info) return null;
                var segs = info.segments;
                // 找到 normOffset 对应的 segment
                for (var j = 0; j < segs.length; j++) {
                    var s = segs[j];
                    if (normOff === s.normOffset) {
                        // 命中段首
                        if (isEnd && j > 0) {
                            // 终点取前一段末尾
                            var prev = segs[j - 1];
                            return { node: node, offset: prev.nodeOffset + prev.len };
                        }
                        return { node: node, offset: s.nodeOffset };
                    }
                    if (normOff > s.normOffset && normOff < (j + 1 < segs.length ? segs[j + 1].normOffset : s.normOffset + 1)) {
                        // 段内（仅非空白段可能，空白段长度为 1）
                        return { node: node, offset: s.nodeOffset + (normOff - s.normOffset) };
                    }
                }
                // normOff 落在节点末尾
                var lastSeg = segs[segs.length - 1];
                if (normOff === lastSeg.normOffset + 1 || normOff === nodeEnd) {
                    return { node: node, offset: lastSeg.nodeOffset + lastSeg.len };
                }
                // 兜底：返回最后一段起始位置
                return { node: node, offset: lastSeg ? lastSeg.nodeOffset : 0 };
            }
        }
        // 超出范围：取最后一个节点末尾
        if (charMap.length > 0 && isEnd) {
            var last = charMap[charMap.length - 1];
            var li = nodeIndex.get(last.node);
            if (li && li.segments.length > 0) {
                var ls = li.segments[li.segments.length - 1];
                return { node: last.node, offset: ls.nodeOffset + ls.len };
            }
        }
        return null;
    }

    /**
     * 计算两个字符串的编辑距离（Levenshtein）。
     * 用于模糊匹配前缀/后缀指纹。
     * @param {string} a
     * @param {string} b
     * @returns {number}
     */
    function editDistance(a, b) {
        if (a === b) return 0;
        var la = a.length, lb = b.length;
        if (Math.abs(la - lb) > FUZZY_MAX_DISTANCE) return FUZZY_MAX_DISTANCE + 1;
        var prev = new Array(lb + 1);
        var curr = new Array(lb + 1);
        for (var j = 0; j <= lb; j++) prev[j] = j;
        for (var i = 1; i <= la; i++) {
            curr[0] = i;
            for (j = 1; j <= lb; j++) {
                var cost = a[i - 1] === b[j - 1] ? 0 : 1;
                curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
            }
            var tmp = prev; prev = curr; curr = tmp;
        }
        return prev[lb];
    }

    /**
     * 用前缀+后缀指纹模糊定位（architecture.md 2.6 级别 3）。
     * @param {string} normText
     * @param {string} prefix
     * @param {string} suffix
     * @param {number} quoteLen
     * @returns {{start:number, end:number}|null}
     */
    function fuzzyLocateByFingerprints(normText, prefix, suffix, quoteLen) {
        if (!prefix && !suffix) return null;
        var candidates = [];

        // 用 prefix 找候选起点
        if (prefix) {
            // 滑动窗口找编辑距离 ≤ 2 的位置
            var plen = prefix.length;
            for (var i = 0; i + plen <= normText.length; i++) {
                var slice = normText.slice(i, i + plen);
                if (editDistance(slice, prefix) <= FUZZY_MAX_DISTANCE) {
                    candidates.push(i + plen);
                }
            }
        }

        // 若无 prefix 候选，用 suffix 反推
        if (candidates.length === 0 && suffix) {
            var slen = suffix.length;
            for (var j = 0; j + slen <= normText.length; j++) {
                var sSlice = normText.slice(j, j + slen);
                if (editDistance(sSlice, suffix) <= FUZZY_MAX_DISTANCE) {
                    candidates.push(j - quoteLen);
                }
            }
        }

        // 对每个候选起点，用 suffix 校验
        for (var k = 0; k < candidates.length; k++) {
            var start = candidates[k];
            if (start < 0) continue;
            var end = start + quoteLen;
            if (end > normText.length) continue;
            if (suffix) {
                var actualSuffix = normText.slice(end, end + suffix.length);
                if (editDistance(actualSuffix, suffix) <= FUZZY_MAX_DISTANCE) {
                    return { start: start, end: end };
                }
            } else {
                return { start: start, end: end };
            }
        }

        return null;
    }

    /**
     * 从当前 Selection 捕获锚点（architecture.md 2.4）。
     * @param {Selection} selection
     * @param {string} notePath
     * @param {Element} container
     * @returns {Anchor|null}
     */
    function captureAnchor(selection, notePath, container) {
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
        var range = selection.getRangeAt(0);
        if (!container || !container.contains(range.commonAncestorContainer)) return null;

        // 1. 校验选区不落在禁批注元素内
        if (rangeIntersectsForbidden(range, container)) return null;

        // 2. 构建规范化纯文本 + 字符偏移映射
        var built = buildNormalizedText(container);
        var normText = built.normText;
        var charMap = built.charMap;
        var nodeIndex = built.nodeIndex;

        // 3. 计算选区在 normText 中的起止偏移
        var startInfo = mapDomOffsetToNorm(range.startContainer, range.startOffset, nodeIndex);
        var endInfo = mapDomOffsetToNorm(range.endContainer, range.endOffset, nodeIndex);
        if (!startInfo || !endInfo) return null;
        if (endInfo.normOffset <= startInfo.normOffset) return null;

        var rangeStart = startInfo.normOffset;
        var rangeEnd = endInfo.normOffset;
        var quote = normText.slice(rangeStart, rangeEnd);

        // 选区过短或过长
        if (quote.length < QUOTE_MIN_LEN) return null;

        // 4. 截取前缀/后缀指纹（architecture.md 用 32 字符）
        var normTextPrefix = normText.slice(Math.max(0, rangeStart - FINGERPRINT_LEN), rangeStart);
        var normTextSuffix = normText.slice(rangeEnd, rangeEnd + FINGERPRINT_LEN);

        // 5. spec.md 的 prefix/suffix（20 字符）+ paragraphIndex + headingPath
        var specPrefix = normText.slice(Math.max(0, rangeStart - PREFIX_SUFFIX_LEN), rangeStart);
        var specSuffix = normText.slice(rangeEnd, rangeEnd + PREFIX_SUFFIX_LEN);
        var paraInfo = computeParagraphInfo(range, container);
        var version = computeNoteVersion();

        return {
            // architecture.md 字段
            notePath: notePath,
            quote: quote,
            rangeStart: rangeStart,
            rangeEnd: rangeEnd,
            normTextPrefix: normTextPrefix,
            normTextSuffix: normTextSuffix,
            schemaVersion: 1,
            // spec.md 字段（导出合规）
            strategy: 'text+context',
            exact: quote,
            prefix: specPrefix,
            suffix: specSuffix,
            paragraphIndex: paraInfo.paragraphIndex,
            headingPath: paraInfo.headingPath,
            charOffsetStart: rangeStart,
            charOffsetEnd: rangeEnd,
            version: version
        };
    }

    /**
     * 计算选区所在段落索引与标题路径（spec.md 4.3）。
     * @param {Range} range
     * @param {Element} container
     * @returns {{paragraphIndex:number, headingPath:string[]}}
     */
    function computeParagraphInfo(range, container) {
        var blockTags = ['P', 'BLOCKQUOTE', 'LI', 'TD', 'TH', 'DD', 'DT', 'FIGCAPTION'];
        var blocks = container.querySelectorAll(blockTags.join(','));
        var paragraphIndex = -1;
        var startNode = range.startContainer;

        // 找到选区起点所在的块级元素
        var startBlock = startNode;
        if (startBlock.nodeType === Node.TEXT_NODE) startBlock = startBlock.parentNode;
        while (startBlock && startBlock !== container) {
            if (startBlock.nodeType === Node.ELEMENT_NODE && blockTags.indexOf(startBlock.tagName) !== -1) break;
            startBlock = startBlock.parentNode;
        }

        if (startBlock) {
            for (var i = 0; i < blocks.length; i++) {
                if (blocks[i] === startBlock) { paragraphIndex = i; break; }
            }
        }

        // 计算 headingPath：从顶层到选区所在位置经过的标题
        var headingPath = [];
        var headings = container.querySelectorAll('h1, h2, h3, h4, h5, h6');
        var allElements = container.querySelectorAll('*');
        var startIdx = -1;
        for (var k = 0; k < allElements.length; k++) {
            if (allElements[k] === startBlock) { startIdx = k; break; }
        }
        if (startIdx !== -1) {
            for (var m = 0; m < allElements.length && m <= startIdx; m++) {
                var el = allElements[m];
                if (el.tagName && /^H[1-6]$/.test(el.tagName)) {
                    headingPath.push(el.textContent.trim());
                }
            }
        }

        return { paragraphIndex: paragraphIndex, headingPath: headingPath };
    }

    /**
     * 计算笔记版本（取 frontmatter created_at 或文件 hash 前 8 位）。
     * 简化实现：用 created_at，无则用 notePath。
     */
    function computeNoteVersion() {
        if (state.noteMeta && state.noteMeta.created_at) return state.noteMeta.created_at;
        return state.notePath || 'unknown';
    }

    /**
     * 在当前容器内解析锚点，返回 Range（spec.md 4.3 四级容错）。
     * 级别 1：精确偏移 + quote 校验
     * 级别 2：quote 全文查找；唯一命中直接用，多次命中用 prefix/suffix 消歧
     * 级别 3：零命中 → headingPath + paragraphIndex 定位段落，段内精确/模糊匹配
     * 级别 4：全局前缀 + 后缀指纹模糊定位
     * @param {Anchor} anchor
     * @param {Element} container
     * @param {{normText:string,charMap:Array,nodeIndex:WeakMap}} [built] 可选的预构建缓存
     * @returns {Range|null}
     */
    function resolveAnchor(anchor, container, built) {
        if (!anchor || !container) return null;
        // 若未提供缓存则现场构建（性能略差，批量场景应传入 built）
        var normText, charMap, nodeIndex;
        if (built) {
            normText = built.normText;
            charMap = built.charMap;
            nodeIndex = built.nodeIndex;
        } else {
            built = buildNormalizedText(container);
            normText = built.normText;
            charMap = built.charMap;
            nodeIndex = built.nodeIndex;
        }

        var quote = anchor.quote || anchor.exact || '';
        if (!quote) return null;

        // —— 级别 1：精确偏移 + quote 校验 ——
        if (typeof anchor.rangeStart === 'number' && typeof anchor.rangeEnd === 'number' &&
            anchor.rangeEnd <= normText.length) {
            var slice = normText.slice(anchor.rangeStart, anchor.rangeEnd);
            if (slice === quote) {
                var r1 = normRangeToDomRange(anchor.rangeStart, anchor.rangeEnd, charMap, nodeIndex);
                if (r1) return r1;
            }
        }

        // —— 级别 2：quote 全文查找；多次命中用 prefix/suffix 消歧 ——
        var hits = [];
        var from = 0, idx;
        while ((idx = normText.indexOf(quote, from)) !== -1) {
            hits.push(idx);
            from = idx + 1;
        }
        if (hits.length === 1) {
            var r2 = normRangeToDomRange(hits[0], hits[0] + quote.length, charMap, nodeIndex);
            if (r2) return r2;
        } else if (hits.length > 1) {
            var best = pickBestHitByContext(hits, quote, normText, anchor);
            if (best >= 0) {
                var r2b = normRangeToDomRange(hits[best], hits[best] + quote.length, charMap, nodeIndex);
                if (r2b) return r2b;
            }
        }

        // —— 级别 3：零命中 → headingPath + paragraphIndex 定位段落，段内匹配 ——
        var paraRange = locateParagraphRange(anchor, container, built);
        if (paraRange) {
            var paraHit = paraRange.normText.indexOf(quote);
            if (paraHit !== -1) {
                var r3 = normRangeToDomRange(paraRange.normStart + paraHit,
                    paraRange.normStart + paraHit + quote.length, charMap, nodeIndex);
                if (r3) return r3;
            }
            // 段内指纹模糊
            var paraFuzzy = fuzzyLocateByFingerprints(
                paraRange.normText,
                anchor.normTextPrefix || anchor.prefix,
                anchor.normTextSuffix || anchor.suffix,
                quote.length
            );
            if (paraFuzzy) {
                var r3b = normRangeToDomRange(paraRange.normStart + paraFuzzy.start,
                    paraRange.normStart + paraFuzzy.end, charMap, nodeIndex);
                if (r3b) return r3b;
            }
        }

        // —— 级别 4：全局前缀 + 后缀指纹模糊定位 ——
        var fuzzy = fuzzyLocateByFingerprints(
            normText,
            anchor.normTextPrefix || anchor.prefix,
            anchor.normTextSuffix || anchor.suffix,
            quote.length
        );
        if (fuzzy) {
            return normRangeToDomRange(fuzzy.start, fuzzy.end, charMap, nodeIndex);
        }

        return null;
    }

    /**
     * 多命中时用 prefix/suffix 指纹挑选最匹配的命中位置。
     * @param {number[]} hits normText 中的命中起点数组
     * @param {string} quote 锚定原文
     * @param {string} normText 规范化全文
     * @param {Anchor} anchor
     * @returns {number} hits 数组的索引；-1 表示无候选
     */
    function pickBestHitByContext(hits, quote, normText, anchor) {
        var prefix = anchor.normTextPrefix || anchor.prefix || '';
        var suffix = anchor.normTextSuffix || anchor.suffix || '';
        var bestIdx = -1, bestScore = Infinity;
        for (var i = 0; i < hits.length; i++) {
            var h = hits[i];
            var actualPrefix = normText.slice(Math.max(0, h - prefix.length), h);
            var actualSuffix = normText.slice(h + quote.length, h + quote.length + suffix.length);
            var score = editDistance(actualPrefix, prefix) + editDistance(actualSuffix, suffix);
            if (score < bestScore) {
                bestScore = score;
                bestIdx = i;
            }
        }
        return bestIdx;
    }

    /**
     * 用 headingPath + paragraphIndex 定位段落，返回该段在 normText 中的范围。
     * @param {Anchor} anchor
     * @param {Element} container
     * @param {{normText:string,charMap:Array,nodeIndex:WeakMap}} built
     * @returns {{normStart:number, normEnd:number, normText:string}|null}
     */
    function locateParagraphRange(anchor, container, built) {
        if (typeof anchor.paragraphIndex !== 'number' || anchor.paragraphIndex < 0) return null;
        var blockTags = ['P', 'BLOCKQUOTE', 'LI', 'TD', 'TH', 'DD', 'DT', 'FIGCAPTION'];
        var blocks = container.querySelectorAll(blockTags.join(','));
        if (anchor.paragraphIndex >= blocks.length) return null;
        var block = blocks[anchor.paragraphIndex];
        var range = getBlockNormRange(block, built);
        if (!range) return null;
        return {
            normStart: range.start,
            normEnd: range.end,
            normText: built.normText.slice(range.start, range.end)
        };
    }

    /**
     * 计算一个块级元素在 normText 中的字符范围。
     * @param {Element} blockEl
     * @param {{normText:string,charMap:Array,nodeIndex:WeakMap}} built
     * @returns {{start:number, end:number}|null}
     */
    function getBlockNormRange(blockEl, built) {
        var nodeIndex = built.nodeIndex;
        var firstNorm = null, lastNorm = null;
        var walker = document.createTreeWalker(blockEl, NodeFilter.SHOW_TEXT, {
            acceptNode: function (node) {
                return isAnnotatableText(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
            }
        });
        var n;
        while ((n = walker.nextNode())) {
            var info = nodeIndex.get(n);
            if (!info || info.segments.length === 0) continue;
            var segStart = info.segments[0].normOffset;
            var segEnd = info.segments[info.segments.length - 1].normOffset + 1;
            if (firstNorm === null || segStart < firstNorm) firstNorm = segStart;
            if (lastNorm === null || segEnd > lastNorm) lastNorm = segEnd;
        }
        if (firstNorm === null) return null;
        return { start: firstNorm, end: lastNorm };
    }

    /* ========================================================
     * 六、高亮 wrap / unwrap（architecture.md 2.7）
     * ======================================================== */

    /**
     * 收集 Range 内所有文本节点。
     * @param {Range} range
     * @returns {Text[]}
     */
    function collectTextNodesInRange(range) {
        var nodes = [];
        var walker = document.createTreeWalker(range.commonAncestorContainer, NodeFilter.SHOW_TEXT, {
            acceptNode: function (node) {
                if (!isAnnotatableText(node)) return NodeFilter.FILTER_REJECT;
                // 检查 node 是否与 range 相交
                var nodeRange = document.createRange();
                nodeRange.selectNodeContents(node);
                var comparison = range.compareBoundaryPoints(Range.END_TO_START, nodeRange);
                if (comparison > 0) return NodeFilter.FILTER_REJECT; // node 在 range 之前
                comparison = range.compareBoundaryPoints(Range.START_TO_END, nodeRange);
                if (comparison < 0) return NodeFilter.FILTER_REJECT; // node 在 range 之后
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        var n;
        while ((n = walker.nextNode())) nodes.push(n);
        return nodes;
    }

    /**
     * 把 Range 包裹成 <mark class="cmt-highlight">（architecture.md 2.7）。
     * 跨多个文本节点时逐节点切分并分别包裹。
     * @param {Range} range
     * @param {string} commentId
     * @param {string} type 评论类型
     */
    function wrapRangeWithHighlight(range, commentId, type) {
        var startContainer = range.startContainer;
        var endContainer = range.endContainer;
        var textNodes = collectTextNodesInRange(range);
        if (textNodes.length === 0) return;

        textNodes.forEach(function (node, i) {
            var target = node;
            var needWrap = true;

            // 第一个节点：从 startOffset 切分
            if (i === 0 && node === startContainer && range.startOffset > 0) {
                try {
                    target = node.splitText(range.startOffset);
                } catch (e) {
                    return;
                }
            }

            // 最后一个节点：从 endOffset 切分
            if (i === textNodes.length - 1 && node === endContainer) {
                var offset;
                if (node === startContainer) {
                    // 同一节点既是首又是尾
                    offset = range.endOffset - range.startOffset;
                } else {
                    offset = range.endOffset;
                }
                if (offset < target.length) {
                    try {
                        target.splitText(offset);
                    } catch (e) { /* ignore */ }
                }
            }

            if (!needWrap || !target.parentNode) return;

            // 若该文本节点已被同一评论的 mark 包裹，跳过
            if (target.parentNode && target.parentNode.tagName === 'MARK' &&
                target.parentNode.dataset && target.parentNode.dataset.cmtId === commentId) {
                return;
            }

            var mark = document.createElement('mark');
            mark.className = 'cmt-highlight';
            mark.dataset.cmtId = commentId;
            mark.dataset.cmtType = type;
            mark.setAttribute('role', 'mark');
            mark.setAttribute('tabindex', '0');
            var typeInfo = COMMENT_TYPES[type] || COMMENT_TYPES.discussion;
            mark.setAttribute('aria-label', '批注：' + typeInfo.label + '，点击查看详情');
            target.parentNode.insertBefore(mark, target);
            mark.appendChild(target);
        });
    }

    /**
     * 移除某评论的所有高亮 mark，把文本节点还原（architecture.md 2.7 unwrap）。
     * @param {string} commentId
     */
    function unwrapHighlight(commentId) {
        if (!state.container) return;
        var marks = state.container.querySelectorAll('mark.cmt-highlight[data-cmt-id="' + CSS.escape(commentId) + '"]');
        marks.forEach(function (mark) {
            var parent = mark.parentNode;
            if (!parent) return;
            while (mark.firstChild) {
                parent.insertBefore(mark.firstChild, mark);
            }
            parent.removeChild(mark);
            // 合并相邻文本节点
            try { parent.normalize(); } catch (e) { /* ignore */ }
        });
    }

    /**
     * 更新某评论高亮的类型/状态属性（不重新 wrap）。
     */
    function updateHighlightAttrs(commentId, type, status) {
        if (!state.container) return;
        var marks = state.container.querySelectorAll('mark.cmt-highlight[data-cmt-id="' + CSS.escape(commentId) + '"]');
        marks.forEach(function (mark) {
            if (type) mark.dataset.cmtType = type;
            if (status) mark.dataset.cmtStatus = status;
        });
    }

    /**
     * 重新渲染当前笔记所有评论的高亮。
     * 切换笔记或导入后调用。
     * 优化：一次性构建规范化文本缓存，所有锚点解析复用，避免重复 TreeWalker 遍历。
     * 批量 wrap 按 rangeStart 降序（从后往前），避免前面的 wrap 影响后面文本节点偏移。
     */
    function refreshHighlights() {
        if (!state.container) return;

        // 先清除所有已有 mark
        var existing = state.container.querySelectorAll('mark.cmt-highlight');
        existing.forEach(function (mark) {
            var parent = mark.parentNode;
            if (!parent) return;
            while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
            parent.removeChild(mark);
            try { parent.normalize(); } catch (e) { /* ignore */ }
        });

        // 一次性构建规范化文本缓存，所有 resolveAnchor 复用
        var built = buildNormalizedText(state.container);
        state.normTextCache = built;

        // 收集所有需要 wrap 的线程
        var threads = state.comments.filter(function (c) {
            return !c.parentId && !c.deleted && c.anchor;
        });

        // 先用缓存解析所有锚点，收集 Range
        var resolved = [];
        threads.forEach(function (c) {
            var range = resolveAnchor(c.anchor, state.container, built);
            if (range) resolved.push({ comment: c, range: range });
        });

        // 按 rangeStart 降序排序（从后往前 wrap）
        resolved.sort(function (a, b) {
            var ra = a.comment.anchor.rangeStart || 0;
            var rb = b.comment.anchor.rangeStart || 0;
            return rb - ra;
        });

        // 从后往前 wrap
        resolved.forEach(function (item) {
            try {
                wrapRangeWithHighlight(item.range, item.comment.id, item.comment.type);
                var marks = state.container.querySelectorAll('mark.cmt-highlight[data-cmt-id="' + CSS.escape(item.comment.id) + '"]');
                var typeInfo = COMMENT_TYPES[item.comment.type] || COMMENT_TYPES.discussion;
                var replyCount = (item.comment.replies || []).length;
                var ariaLabel = '批注：' + typeInfo.label + '，' + replyCount + ' 条回复';
                marks.forEach(function (m) {
                    m.dataset.cmtStatus = item.comment.status;
                    m.setAttribute('aria-label', ariaLabel);
                });
            } catch (e) {
                console.warn('[comments] wrap failed for', item.comment.id, e);
            }
        });
    }

    /* ========================================================
     * 七、选区监听 + 气泡工具条
     * ======================================================== */

    /**
     * mouseup / touchend 处理：检测有效选区，弹出气泡。
     */
    function handleSelectionEnd(e) {
        // 点击气泡/浮层内部不处理
        if (e.target.closest && (e.target.closest('.cmt-bubble') || e.target.closest('.cmt-popover'))) return;

        // 延迟一帧让 selection 更新
        setTimeout(checkSelection, 10);
    }

    /**
     * selectionchange 处理（带防抖）。
     */
    function handleSelectionChange() {
        if (state.selectionTimer) clearTimeout(state.selectionTimer);
        state.selectionTimer = setTimeout(checkSelection, 200);
    }

    /**
     * 检查当前选区，有效则显示气泡。
     */
    function checkSelection() {
        var sel = window.getSelection();
        if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
            hideBubble();
            return;
        }
        var range = sel.getRangeAt(0);
        if (!state.container || !state.container.contains(range.commonAncestorContainer)) {
            hideBubble();
            return;
        }
        // 选区与禁批注元素相交
        if (rangeIntersectsForbidden(range, state.container)) {
            hideBubble();
            return;
        }
        var text = sel.toString();
        if (!text || text.trim().length < QUOTE_MIN_LEN) {
            hideBubble();
            return;
        }
        if (text.length > QUOTE_MAX_LEN) {
            // 选区过长，仍允许但提示
            toast('选区较长（' + text.length + ' 字），建议缩短以便锚定稳定', 'warn');
        }

        state.pendingRange = range;
        state.pendingAnchor = captureAnchor(sel, state.notePath, state.container);
        if (state.pendingAnchor) {
            showBubble(range);
        } else {
            hideBubble();
        }
    }

    /**
     * 显示气泡工具条。
     */
    function showBubble(range) {
        var bubble = getOrCreateBubble();
        var rect = range.getBoundingClientRect();
        var scrollY = window.scrollY;
        var scrollX = window.scrollX;
        bubble.style.left = (rect.left + rect.width / 2 + scrollX) + 'px';
        bubble.style.top = (rect.top + scrollY - 44) + 'px';
        bubble.style.transform = 'translateX(-50%)';
        bubble.hidden = false;
    }

    function hideBubble() {
        var bubble = document.getElementById('cmtBubble');
        if (bubble) bubble.hidden = true;
    }

    function getOrCreateBubble() {
        var bubble = document.getElementById('cmtBubble');
        if (bubble) return bubble;
        bubble = document.createElement('div');
        bubble.className = 'cmt-bubble';
        bubble.id = 'cmtBubble';
        bubble.setAttribute('role', 'toolbar');
        bubble.hidden = true;

        var commentBtn = document.createElement('button');
        commentBtn.className = 'cmt-bubble-btn cmt-bubble-primary';
        commentBtn.type = 'button';
        commentBtn.innerHTML = '<span class="cmt-bubble-icon">✎</span><span>评论</span>';
        commentBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (state.pendingRange && state.pendingAnchor) {
                showPopover(state.pendingRange, state.pendingAnchor);
            }
        });

        var copyBtn = document.createElement('button');
        copyBtn.className = 'cmt-bubble-btn';
        copyBtn.type = 'button';
        copyBtn.innerHTML = '<span class="cmt-bubble-icon">⧉</span><span>复制</span>';
        copyBtn.addEventListener('click', function () {
            var sel = window.getSelection();
            var text = sel ? sel.toString() : '';
            if (text) {
                copyToClipboard(text);
                toast('已复制选区文本', 'success');
            }
        });

        var quoteBtn = document.createElement('button');
        quoteBtn.className = 'cmt-bubble-btn';
        quoteBtn.type = 'button';
        quoteBtn.innerHTML = '<span class="cmt-bubble-icon">"</span><span>引用</span>';
        quoteBtn.addEventListener('click', function () {
            var sel = window.getSelection();
            var text = sel ? sel.toString() : '';
            if (text) {
                copyToClipboard('「' + text + '」');
                toast('已复制为引用格式', 'success');
            }
        });

        bubble.appendChild(commentBtn);
        bubble.appendChild(copyBtn);
        bubble.appendChild(quoteBtn);
        document.body.appendChild(bubble);
        return bubble;
    }

    /* ========================================================
     * 八、评论输入浮层
     * ======================================================== */

    var popoverState = { selectedType: 'discussion', selectedAgent: '' };

    function showPopover(range, anchor) {
        hideBubble();
        var popover = getOrCreatePopover();
        // 填充引用
        var quoteEl = popover.querySelector('.cmt-popover-quote');
        quoteEl.textContent = '「' + (anchor.quote.length > 80 ? anchor.quote.slice(0, 80) + '…' : anchor.quote) + '」';

        // 重置
        var textarea = popover.querySelector('.cmt-popover-textarea');
        textarea.value = '';
        popoverState.selectedType = 'discussion';
        popoverState.selectedAgent = '';
        updateTypeSelection();
        var agentSelect = popover.querySelector('.cmt-agent-select');
        if (agentSelect) agentSelect.value = '';

        // 定位
        var rect = range.getBoundingClientRect();
        var scrollY = window.scrollY;
        var scrollX = window.scrollX;
        var top = rect.top + scrollY - 8;
        var left = rect.left + scrollX + rect.width / 2;

        // 翻转：若上方空间不足，放下方
        var popoverHeight = 280;
        if (top - popoverHeight < scrollY) {
            top = rect.bottom + scrollY + 8;
        }
        popover.style.left = left + 'px';
        popover.style.top = top + 'px';
        popover.style.transform = 'translateX(-50%)';
        popover.hidden = false;

        setTimeout(function () { textarea.focus(); }, 50);
    }

    function hidePopover() {
        var popover = document.getElementById('cmtPopover');
        if (popover) popover.hidden = true;
        state.pendingRange = null;
        state.pendingAnchor = null;
    }

    function getOrCreatePopover() {
        var popover = document.getElementById('cmtPopover');
        if (popover) return popover;

        popover = document.createElement('div');
        popover.className = 'cmt-popover';
        popover.id = 'cmtPopover';
        popover.setAttribute('role', 'dialog');
        popover.setAttribute('aria-modal', 'true');
        popover.setAttribute('aria-labelledby', 'cmtPopoverTitle');
        popover.hidden = true;

        // 不可见标题，供 aria-labelledby 引用
        var popoverTitle = document.createElement('span');
        popoverTitle.id = 'cmtPopoverTitle';
        popoverTitle.textContent = '批注输入';
        popoverTitle.style.position = 'absolute';
        popoverTitle.style.width = '1px';
        popoverTitle.style.height = '1px';
        popoverTitle.style.overflow = 'hidden';
        popoverTitle.style.clip = 'rect(0 0 0 0)';
        popover.appendChild(popoverTitle);

        var arrow = document.createElement('div');
        arrow.className = 'cmt-popover-arrow';

        var quote = document.createElement('div');
        quote.className = 'cmt-popover-quote';

        var body = document.createElement('div');
        body.className = 'cmt-popover-body';

        var textarea = document.createElement('textarea');
        textarea.className = 'cmt-popover-textarea';
        textarea.placeholder = '写下你的批注…（Enter 提交，Shift+Enter 换行）';
        textarea.setAttribute('aria-label', '批注内容');

        // 类型选择（5 类 pill）
        var typeGroup = document.createElement('div');
        typeGroup.className = 'cmt-type-group';
        typeGroup.setAttribute('role', 'radiogroup');
        typeGroup.setAttribute('aria-label', '批注类型');
        Object.keys(COMMENT_TYPES).forEach(function (t) {
            var pill = document.createElement('button');
            pill.type = 'button';
            pill.className = 'cmt-type-pill';
            pill.dataset.type = t;
            pill.setAttribute('role', 'radio');
            pill.setAttribute('aria-checked', t === popoverState.selectedType ? 'true' : 'false');
            pill.innerHTML = '<span class="cmt-type-icon">' + COMMENT_TYPES[t].icon + '</span><span>' + COMMENT_TYPES[t].label + '</span>';
            pill.addEventListener('click', function () {
                popoverState.selectedType = t;
                updateTypeSelection();
            });
            typeGroup.appendChild(pill);
        });

        // 操作行
        var actions = document.createElement('div');
        actions.className = 'cmt-popover-actions';

        var agentSelect = document.createElement('select');
        agentSelect.className = 'cmt-agent-select';
        agentSelect.setAttribute('aria-label', '指派专家');
        var opt0 = document.createElement('option');
        opt0.value = '';
        opt0.textContent = '不指定专家';
        agentSelect.appendChild(opt0);
        var agentLabels = {
            historian: '史官', biographer: '传记官', context_analyst: '背景分析',
            critic: '名家点评', philosopher: '问道', editor: '编辑'
        };
        AGENTS.forEach(function (a) {
            var opt = document.createElement('option');
            opt.value = a;
            opt.textContent = agentLabels[a] || a;
            agentSelect.appendChild(opt);
        });
        agentSelect.addEventListener('change', function () {
            popoverState.selectedAgent = agentSelect.value;
        });

        var btns = document.createElement('div');
        btns.className = 'cmt-popover-btns';

        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'cmt-btn cmt-btn-ghost';
        cancelBtn.textContent = '取消';
        cancelBtn.addEventListener('click', hidePopover);

        var submitBtn = document.createElement('button');
        submitBtn.type = 'button';
        submitBtn.className = 'cmt-btn cmt-btn-primary';
        submitBtn.textContent = '提交';
        submitBtn.addEventListener('click', submitComment);

        btns.appendChild(cancelBtn);
        btns.appendChild(submitBtn);

        actions.appendChild(agentSelect);
        actions.appendChild(btns);

        body.appendChild(textarea);
        body.appendChild(typeGroup);
        body.appendChild(actions);

        popover.appendChild(arrow);
        popover.appendChild(quote);
        popover.appendChild(body);

        // 键盘：Enter 提交，Shift+Enter 换行，Esc 关闭
        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                submitComment();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                hidePopover();
            }
        });

        popover.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                e.preventDefault();
                hidePopover();
            }
        });

        document.body.appendChild(popover);
        return popover;
    }

    function updateTypeSelection() {
        var popover = document.getElementById('cmtPopover');
        if (!popover) return;
        var pills = popover.querySelectorAll('.cmt-type-pill');
        pills.forEach(function (p) {
            p.setAttribute('aria-checked', p.dataset.type === popoverState.selectedType ? 'true' : 'false');
        });
    }

    /**
     * 提交评论：生成 Comment，wrap 高亮，持久化，刷新面板。
     */
    function submitComment() {
        if (!state.pendingRange || !state.pendingAnchor) {
            toast('选区已失效，请重新选择', 'warn');
            hidePopover();
            return;
        }
        var popover = document.getElementById('cmtPopover');
        var textarea = popover.querySelector('.cmt-popover-textarea');
        var content = textarea.value.trim();
        if (!content) {
            toast('请输入批注内容', 'warn');
            textarea.focus();
            return;
        }

        var now = nowIso();
        var comment = {
            id: genId(),
            notePath: state.notePath,
            parentId: null,
            type: popoverState.selectedType,
            status: 'open',
            anchor: state.pendingAnchor,
            content: content,
            author: '作者',
            createdAt: now,
            updatedAt: now,
            resolvedAt: null,
            tags: [],
            replies: [],
            expertReviews: [],
            deleted: false
        };
        if (popoverState.selectedAgent) {
            comment.agentHints = {
                targetAgent: popoverState.selectedAgent,
                priority: 'normal'
            };
        }

        state.comments.push(comment);

        // wrap 高亮
        try {
            wrapRangeWithHighlight(state.pendingRange, comment.id, comment.type);
        } catch (e) {
            console.warn('[comments] wrap failed', e);
        }

        // 保存
        if (state.storageAvailable) {
            Storage.saveComments(state.notePath, state.comments);
        } else {
            toast('本地存储不可用，批注仅本次会话有效', 'warn');
        }

        // 清除选区
        var sel = window.getSelection();
        if (sel) sel.removeAllRanges();

        hidePopover();
        hideBubble();
        renderPanel();
        toast('批注已添加', 'success');
    }

    /* ========================================================
     * 九、点击高亮 → 展开线程
     * ======================================================== */

    function handleHighlightClick(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) return;
        var id = mark.dataset.cmtId;
        if (id) {
            openThreadInPanel(id);
        }
    }

    /**
     * 高亮 hover 显示悬浮卡。
     */
    var hoverCardTimer = null;
    function handleHighlightHover(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) {
            if (hoverCardTimer) clearTimeout(hoverCardTimer);
            hideHoverCard();
            return;
        }
        var id = mark.dataset.cmtId;
        var comment = state.comments.find(function (c) { return c.id === id; });
        if (!comment) return;

        if (hoverCardTimer) clearTimeout(hoverCardTimer);
        hoverCardTimer = setTimeout(function () {
            showHoverCard(comment, e.clientX, e.clientY);
        }, 200);
    }

    function handleHighlightMouseLeave(e) {
        // 若 relatedTarget 仍在某个 mark 内（如从 mark 移到其子文本节点），不隐藏
        var related = e.relatedTarget;
        if (related && related.closest && related.closest('mark.cmt-highlight')) {
            return;
        }
        if (hoverCardTimer) clearTimeout(hoverCardTimer);
        hoverCardTimer = setTimeout(hideHoverCard, 300);
    }

    function showHoverCard(comment, x, y) {
        var card = getOrCreateHoverCard();
        var typeInfo = COMMENT_TYPES[comment.type] || COMMENT_TYPES.discussion;

        var quoteEl = card.querySelector('.cmt-hovercard-quote');
        quoteEl.textContent = comment.anchor ? '「' + truncate(comment.anchor.quote, 80) + '」' : '';

        var contentEl = card.querySelector('.cmt-hovercard-content');
        contentEl.textContent = comment.content;

        var metaEl = card.querySelector('.cmt-hovercard-meta');
        metaEl.innerHTML = '';
        var typeTag = document.createElement('span');
        typeTag.className = 'cmt-type-tag';
        typeTag.dataset.type = comment.type;
        typeTag.innerHTML = '<span class="cmt-type-icon">' + typeInfo.icon + '</span>' + typeInfo.label;
        metaEl.appendChild(typeTag);

        var statusTag = document.createElement('span');
        statusTag.className = 'cmt-status-tag';
        statusTag.dataset.status = comment.status;
        statusTag.textContent = comment.status === 'open' ? '未解决' : '已解决';
        metaEl.appendChild(statusTag);

        var replyCount = (comment.replies || []).length;
        var countSpan = document.createElement('span');
        countSpan.textContent = replyCount + ' 回复 · ' + relativeTime(comment.createdAt);
        metaEl.appendChild(countSpan);

        // 定位
        card.hidden = false;
        var rect = card.getBoundingClientRect();
        var left = x + 12;
        var top = y + 12;
        if (left + rect.width > window.innerWidth - 8) left = x - rect.width - 12;
        if (top + rect.height > window.innerHeight - 8) top = y - rect.height - 12;
        card.style.left = left + 'px';
        card.style.top = top + 'px';
    }

    function hideHoverCard() {
        var card = document.getElementById('cmtHoverCard');
        if (card) card.hidden = true;
    }

    function getOrCreateHoverCard() {
        var card = document.getElementById('cmtHoverCard');
        if (card) return card;
        card = document.createElement('div');
        card.className = 'cmt-hovercard';
        card.id = 'cmtHoverCard';
        card.setAttribute('role', 'tooltip');
        card.hidden = true;

        var quote = document.createElement('div');
        quote.className = 'cmt-hovercard-quote';
        var content = document.createElement('div');
        content.className = 'cmt-hovercard-content';
        var meta = document.createElement('div');
        meta.className = 'cmt-hovercard-meta';

        card.appendChild(quote);
        card.appendChild(content);
        card.appendChild(meta);

        card.addEventListener('mouseenter', function () {
            if (hoverCardTimer) clearTimeout(hoverCardTimer);
        });
        card.addEventListener('mouseleave', handleHighlightMouseLeave);

        document.body.appendChild(card);
        return card;
    }

    /* ========================================================
     * 十、右侧评论面板
     * ======================================================== */

    function getOrCreatePanel() {
        var panel = document.getElementById('cmtPanel');
        if (panel) return panel;

        panel = document.createElement('aside');
        panel.className = 'cmt-panel';
        panel.id = 'cmtPanel';
        panel.setAttribute('aria-label', '批注列表');

        // 折叠按钮
        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'cmt-panel-toggle';
        toggle.setAttribute('aria-label', '折叠/展开批注面板');
        toggle.innerHTML = '<span class="cmt-panel-toggle-icon">›</span>';
        toggle.addEventListener('click', function () {
            state.panelCollapsed = !state.panelCollapsed;
            panel.classList.toggle('cmt-collapsed', state.panelCollapsed);
        });

        // 折叠态窄条
        var collapsedBar = document.createElement('div');
        collapsedBar.className = 'cmt-panel-collapsed-bar';
        collapsedBar.innerHTML = '<span>💬</span><span class="cmt-collapsed-count">0</span>';
        collapsedBar.addEventListener('click', function () {
            state.panelCollapsed = false;
            panel.classList.remove('cmt-collapsed');
        });

        // 头部
        var header = document.createElement('div');
        header.className = 'cmt-panel-header';
        var title = document.createElement('h3');
        title.className = 'cmt-panel-title';
        title.innerHTML = '批注 <span class="cmt-panel-count">0</span>';
        header.appendChild(title);

        // 工具栏
        var toolbar = document.createElement('div');
        toolbar.className = 'cmt-panel-toolbar';

        var exportNoteBtn = document.createElement('button');
        exportNoteBtn.type = 'button';
        exportNoteBtn.className = 'cmt-btn';
        exportNoteBtn.textContent = '导出本篇';
        exportNoteBtn.addEventListener('click', function () { doExportNote(); });

        var exportAllBtn = document.createElement('button');
        exportAllBtn.type = 'button';
        exportAllBtn.className = 'cmt-btn';
        exportAllBtn.textContent = '导出全部';
        exportAllBtn.addEventListener('click', function () { doExportAll(); });

        var importBtn = document.createElement('button');
        importBtn.type = 'button';
        importBtn.className = 'cmt-btn';
        importBtn.textContent = '导入';
        importBtn.addEventListener('click', function () { doImport(); });

        var expertBtn = document.createElement('button');
        expertBtn.type = 'button';
        expertBtn.className = 'cmt-btn';
        expertBtn.textContent = '启用专家团';
        expertBtn.addEventListener('click', function () { openExpertWizard(); });

        var importExpertBtn = document.createElement('button');
        importExpertBtn.type = 'button';
        importExpertBtn.className = 'cmt-btn';
        importExpertBtn.textContent = '导入评判';
        importExpertBtn.title = '导入 expert_review_result.json';
        importExpertBtn.addEventListener('click', function () { doImportExpertReview(); });

        toolbar.appendChild(exportNoteBtn);
        toolbar.appendChild(exportAllBtn);
        toolbar.appendChild(importBtn);
        toolbar.appendChild(expertBtn);
        toolbar.appendChild(importExpertBtn);

        // 筛选行
        var filter = document.createElement('div');
        filter.className = 'cmt-panel-filter';

        var typeSelect = document.createElement('select');
        typeSelect.className = 'cmt-filter-select';
        typeSelect.setAttribute('aria-label', '类型筛选');
        var typeOpts = [['all', '全部类型']].concat(Object.keys(COMMENT_TYPES).map(function (t) { return [t, COMMENT_TYPES[t].label]; }));
        typeOpts.forEach(function (o) {
            var opt = document.createElement('option');
            opt.value = o[0]; opt.textContent = o[1];
            typeSelect.appendChild(opt);
        });
        typeSelect.value = state.filterType;
        typeSelect.addEventListener('change', function () {
            state.filterType = typeSelect.value;
            renderThreadList();
        });

        var statusSelect = document.createElement('select');
        statusSelect.className = 'cmt-filter-select';
        statusSelect.setAttribute('aria-label', '状态筛选');
        [['all', '全部状态'], ['open', '未解决'], ['resolved', '已解决']].forEach(function (o) {
            var opt = document.createElement('option');
            opt.value = o[0]; opt.textContent = o[1];
            statusSelect.appendChild(opt);
        });
        statusSelect.value = state.filterStatus;
        statusSelect.addEventListener('change', function () {
            state.filterStatus = statusSelect.value;
            renderThreadList();
        });

        var keywordInput = document.createElement('input');
        keywordInput.type = 'text';
        keywordInput.className = 'cmt-filter-input';
        keywordInput.placeholder = '搜索批注…';
        keywordInput.value = state.filterKeyword;
        keywordInput.addEventListener('input', function () {
            state.filterKeyword = keywordInput.value.trim().toLowerCase();
            renderThreadList();
        });

        var resolvedLabel = document.createElement('label');
        resolvedLabel.className = 'cmt-filter-checkbox';
        var resolvedCb = document.createElement('input');
        resolvedCb.type = 'checkbox';
        resolvedCb.checked = state.showResolved;
        resolvedCb.addEventListener('change', function () {
            state.showResolved = resolvedCb.checked;
            renderThreadList();
        });
        resolvedLabel.appendChild(resolvedCb);
        resolvedLabel.appendChild(document.createTextNode('显示已解决'));

        filter.appendChild(typeSelect);
        filter.appendChild(statusSelect);
        filter.appendChild(keywordInput);
        filter.appendChild(resolvedLabel);

        // 列表容器
        var body = document.createElement('div');
        body.className = 'cmt-panel-body';

        var list = document.createElement('div');
        list.className = 'cmt-thread-list';
        list.id = 'cmtThreadList';
        list.setAttribute('role', 'list');
        body.appendChild(list);

        panel.appendChild(toggle);
        panel.appendChild(collapsedBar);
        panel.appendChild(header);
        panel.appendChild(toolbar);
        panel.appendChild(filter);
        panel.appendChild(body);

        return panel;
    }

    /**
     * 渲染面板：更新计数、列表。
     * 若面板尚未挂载到 DOM，自动创建并挂载。
     */
    function renderPanel() {
        var panel = document.getElementById('cmtPanel');
        if (!panel) {
            // 面板不存在，创建并挂载
            panel = getOrCreatePanel();
            var layout = document.querySelector('.layout');
            if (layout) layout.appendChild(panel);
            else document.body.appendChild(panel);
        }

        var threads = state.comments.filter(function (c) { return !c.parentId && !c.deleted; });
        var unresolved = threads.filter(function (t) { return t.status === 'open'; }).length;

        // 计数
        var countEl = panel.querySelector('.cmt-panel-count');
        if (countEl) countEl.textContent = String(threads.length);
        var collapsedCount = panel.querySelector('.cmt-collapsed-count');
        if (collapsedCount) collapsedCount.textContent = String(unresolved);

        renderThreadList();
    }

    /**
     * 渲染线程列表（按筛选 + 排序）。
     */
    function renderThreadList() {
        var list = document.getElementById('cmtThreadList');
        if (!list) return;
        list.innerHTML = '';

        // 笔记未加载时提示（checklist 4.3）
        if (!state.notePath) {
            var noNote = document.createElement('div');
            noNote.className = 'cmt-panel-empty';
            noNote.innerHTML = '<div class="cmt-panel-empty-icon">📖</div>' +
                '<div>请先选择一篇笔记</div>' +
                '<div class="cmt-panel-empty-hint">在左侧目录中选择笔记后即可批注</div>';
            list.appendChild(noNote);
            return;
        }

        var threads = state.comments.filter(function (c) {
            return !c.parentId && !c.deleted;
        });

        // 筛选
        threads = threads.filter(function (c) {
            if (state.filterType !== 'all' && c.type !== state.filterType) return false;
            if (state.filterStatus !== 'all' && c.status !== state.filterStatus) return false;
            if (!state.showResolved && c.status === 'resolved') return false;
            if (state.filterKeyword) {
                var hay = (c.content + ' ' + (c.anchor ? c.anchor.quote : '') + ' ' + (c.tags || []).join(' ')).toLowerCase();
                if (hay.indexOf(state.filterKeyword) === -1) return false;
            }
            return true;
        });

        // 排序
        threads.sort(function (a, b) {
            if (state.sortMode === 'time') {
                return new Date(a.createdAt) - new Date(b.createdAt);
            }
            if (state.sortMode === 'status') {
                if (a.status !== b.status) return a.status === 'open' ? -1 : 1;
                return (a.anchor ? a.anchor.rangeStart : 0) - (b.anchor ? b.anchor.rangeStart : 0);
            }
            // position
            return (a.anchor ? a.anchor.rangeStart : Infinity) - (b.anchor ? b.anchor.rangeStart : Infinity);
        });

        if (threads.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'cmt-panel-empty';
            empty.innerHTML = '<div class="cmt-panel-empty-icon">💬</div>' +
                '<div>暂无批注</div>' +
                '<div class="cmt-panel-empty-hint">圈选原文即可开始批注</div>';
            list.appendChild(empty);
            return;
        }

        threads.forEach(function (c) {
            list.appendChild(renderThread(c));
        });
    }

    /**
     * 渲染单条线程卡片。
     */
    function renderThread(comment) {
        var li = document.createElement('article');
        li.className = 'cmt-thread';
        li.dataset.cmtId = comment.id;
        li.dataset.cmtStatus = comment.status;
        li.setAttribute('role', 'listitem');
        var typeInfoForLabel = COMMENT_TYPES[comment.type] || COMMENT_TYPES.discussion;
        var ariaLabel = typeInfoForLabel.label + '：' + truncate(comment.content, 30);
        if (comment.anchor && comment.anchor.quote) {
            ariaLabel += '（原文：「' + truncate(comment.anchor.quote, 20) + '」）';
        }
        li.setAttribute('aria-label', ariaLabel);
        if (state.activeThreadId === comment.id) li.classList.add('cmt-active');

        // 检查是否能定位（孤儿标记）
        var isOrphaned = false;
        if (comment.anchor && state.container) {
            var testRange = resolveAnchor(comment.anchor, state.container);
            if (!testRange) isOrphaned = true;
        }
        if (isOrphaned) li.classList.add('cmt-orphaned');

        var typeInfo = COMMENT_TYPES[comment.type] || COMMENT_TYPES.discussion;

        // 孤儿标记
        if (isOrphaned) {
            var orphanFlag = document.createElement('div');
            orphanFlag.className = 'cmt-thread-orphan-flag';
            orphanFlag.textContent = '⚠ 原文已变更，未能定位';
            li.appendChild(orphanFlag);
        }

        // 版本不一致提示（checklist 2.4：版本不一致时仍尝试定位，不直接判为孤儿）
        // 仅当 anchor.version 存在且与当前笔记版本不同时提示，孤儿已单独标记则不重复
        if (!isOrphaned && comment.anchor && comment.anchor.version &&
            state.noteVersion && comment.anchor.version !== state.noteVersion) {
            var verFlag = document.createElement('div');
            verFlag.className = 'cmt-thread-version-flag';
            verFlag.setAttribute('role', 'status');
            verFlag.textContent = '⤴ 原文已更新，高亮可能偏移';
            li.appendChild(verFlag);
        }

        // 头部
        var header = document.createElement('div');
        header.className = 'cmt-thread-header';

        var avatar = document.createElement('span');
        avatar.className = 'cmt-avatar';
        avatar.textContent = (comment.author || '作').charAt(0);

        var meta = document.createElement('div');
        meta.className = 'cmt-thread-meta';

        var author = document.createElement('span');
        author.className = 'cmt-author';
        author.textContent = comment.author || '作者';

        var typeTag = document.createElement('span');
        typeTag.className = 'cmt-type-tag';
        typeTag.dataset.type = comment.type;
        typeTag.innerHTML = '<span class="cmt-type-icon">' + typeInfo.icon + '</span>' + typeInfo.label;

        var time = document.createElement('span');
        time.className = 'cmt-thread-time';
        time.textContent = relativeTime(comment.createdAt);
        time.title = formatTime(comment.createdAt);

        meta.appendChild(author);
        meta.appendChild(typeTag);
        meta.appendChild(time);

        // 状态标签
        var statusTag = document.createElement('span');
        statusTag.className = 'cmt-status-tag';
        statusTag.dataset.status = comment.status;
        statusTag.textContent = comment.status === 'open' ? '未解决' : '已解决';

        header.appendChild(avatar);
        header.appendChild(meta);
        header.appendChild(statusTag);
        li.appendChild(header);

        // 引用原文
        if (comment.anchor && comment.anchor.quote) {
            var quote = document.createElement('div');
            quote.className = 'cmt-thread-quote';
            quote.textContent = '「' + truncate(comment.anchor.quote, 60) + '」';
            quote.setAttribute('tabindex', '0');
            quote.setAttribute('role', 'button');
            quote.setAttribute('aria-label', '跳转到原文位置');
            quote.addEventListener('click', function () { jumpToComment(comment.id); });
            quote.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); jumpToComment(comment.id); }
            });
            li.appendChild(quote);
        }

        // 正文
        var content = document.createElement('div');
        content.className = 'cmt-thread-content';
        content.textContent = comment.content;
        li.appendChild(content);

        // 标签
        if (comment.tags && comment.tags.length > 0) {
            var tagsWrap = document.createElement('div');
            tagsWrap.className = 'cmt-thread-tags';
            comment.tags.forEach(function (t) {
                var tag = document.createElement('span');
                tag.className = 'cmt-tag';
                tag.textContent = t;
                tagsWrap.appendChild(tag);
            });
            li.appendChild(tagsWrap);
        }

        // 回复列表
        if (comment.replies && comment.replies.length > 0) {
            var replies = document.createElement('div');
            replies.className = 'cmt-replies';
            comment.replies.forEach(function (r) {
                replies.appendChild(renderReply(r));
            });
            li.appendChild(replies);
        }

        // 专家评判
        if (comment.expertReviews && comment.expertReviews.length > 0) {
            var reviewsWrap = document.createElement('div');
            reviewsWrap.className = 'cmt-expert-reviews';
            comment.expertReviews.forEach(function (rv) {
                var badge = document.createElement('span');
                badge.className = 'cmt-expert-badge';
                badge.dataset.verdict = rv.verdict;
                var verdictLabel = { accept: '✓ 采纳', reject: '✕ 不采纳', needs_discussion: '⚠ 待议' };
                badge.textContent = verdictLabel[rv.verdict] || rv.verdict;
                badge.setAttribute('tabindex', '0');
                badge.addEventListener('click', function () {
                    var detail = badge.nextElementSibling;
                    if (detail) detail.classList.toggle('cmt-open');
                });
                reviewsWrap.appendChild(badge);

                var detail = document.createElement('div');
                detail.className = 'cmt-expert-detail';
                var detailText = '';
                if (rv.rationale) detailText += '理由：' + rv.rationale + '\n';
                if (rv.suggestedEdit && rv.suggestedEdit.text) {
                    detailText += '建议：' + rv.suggestedEdit.text + '\n';
                }
                if (rv.reviewedBy && rv.reviewedBy.length) {
                    detailText += '评审：' + rv.reviewedBy.join(', ');
                }
                detail.textContent = detailText;

                // 「应用建议」按钮：复制 suggestedEdit.text 到剪贴板，不自动改原文（spec.md 6.3）
                if (rv.suggestedEdit && rv.suggestedEdit.text) {
                    var applyBtn = document.createElement('button');
                    applyBtn.type = 'button';
                    applyBtn.className = 'cmt-btn cmt-btn-ghost cmt-expert-apply';
                    applyBtn.textContent = '⧉ 应用建议';
                    applyBtn.title = '复制建议文本到剪贴板，手动修订原文';
                    applyBtn.addEventListener('click', function () {
                        copyToClipboard(rv.suggestedEdit.text).then(function (ok) {
                            if (ok) toast('建议文本已复制到剪贴板，请手动修订原文', 'success');
                            else toast('复制失败，请手动复制', 'error');
                        });
                    });
                    detail.appendChild(applyBtn);
                }

                reviewsWrap.appendChild(detail);
            });
            li.appendChild(reviewsWrap);
        }

        // 操作按钮
        var actions = document.createElement('div');
        actions.className = 'cmt-thread-actions';

        var replyBtn = document.createElement('button');
        replyBtn.type = 'button';
        replyBtn.className = 'cmt-action-btn';
        replyBtn.textContent = '💬 回复';
        replyBtn.addEventListener('click', function () { toggleReplyInput(li, comment.id); });

        var resolveBtn = document.createElement('button');
        resolveBtn.type = 'button';
        resolveBtn.className = 'cmt-action-btn cmt-action-resolve';
        resolveBtn.textContent = comment.status === 'open' ? '✓ 解决' : '↻ 重新打开';
        resolveBtn.setAttribute('aria-pressed', comment.status === 'resolved');
        resolveBtn.addEventListener('click', function () {
            if (comment.status === 'open') resolveComment(comment.id);
            else reopenComment(comment.id);
        });

        var jumpBtn = document.createElement('button');
        jumpBtn.type = 'button';
        jumpBtn.className = 'cmt-action-btn';
        jumpBtn.textContent = '↗ 定位';
        jumpBtn.addEventListener('click', function () { jumpToComment(comment.id); });

        var copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'cmt-action-btn';
        copyBtn.textContent = '⧉ 复制原文';
        copyBtn.addEventListener('click', function () {
            var text = comment.anchor ? comment.anchor.quote : comment.content;
            copyToClipboard(text);
            toast('已复制原文', 'success');
        });

        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'cmt-action-btn';
        editBtn.textContent = '✎ 编辑';
        editBtn.addEventListener('click', function () { startEdit(li, comment); });

        var deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'cmt-action-btn cmt-action-danger';
        deleteBtn.textContent = '🗑 删除';
        deleteBtn.addEventListener('click', function () { deleteComment(comment.id); });

        actions.appendChild(replyBtn);
        actions.appendChild(resolveBtn);
        actions.appendChild(jumpBtn);
        actions.appendChild(copyBtn);
        actions.appendChild(editBtn);
        actions.appendChild(deleteBtn);
        li.appendChild(actions);

        return li;
    }

    /**
     * 渲染单条回复。
     */
    function renderReply(reply) {
        var div = document.createElement('div');
        div.className = 'cmt-reply';

        var header = document.createElement('div');
        header.className = 'cmt-reply-header';

        var avatar = document.createElement('span');
        avatar.className = 'cmt-avatar';
        avatar.textContent = (reply.author || '作').charAt(0);

        var author = document.createElement('span');
        author.className = 'cmt-author';
        author.textContent = reply.author || '作者';

        var time = document.createElement('span');
        time.className = 'cmt-thread-time';
        time.textContent = relativeTime(reply.createdAt);
        time.title = formatTime(reply.createdAt);

        header.appendChild(avatar);
        header.appendChild(author);
        header.appendChild(time);
        div.appendChild(header);

        var content = document.createElement('div');
        content.className = 'cmt-reply-content';
        content.textContent = reply.content;
        div.appendChild(content);

        return div;
    }

    /**
     * 切换回复输入框。
     */
    function toggleReplyInput(threadEl, commentId) {
        var existing = threadEl.querySelector('.cmt-reply-input-wrap');
        if (existing) {
            existing.remove();
            return;
        }
        var wrap = document.createElement('div');
        wrap.className = 'cmt-reply-input-wrap';

        var textarea = document.createElement('textarea');
        textarea.className = 'cmt-reply-textarea';
        textarea.placeholder = '写下回复…（Enter 提交）';

        var actions = document.createElement('div');
        actions.className = 'cmt-reply-actions';
        var cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'cmt-btn cmt-btn-ghost';
        cancel.textContent = '取消';
        cancel.addEventListener('click', function () { wrap.remove(); });

        var submit = document.createElement('button');
        submit.type = 'button';
        submit.className = 'cmt-btn cmt-btn-primary';
        submit.textContent = '回复';
        submit.addEventListener('click', function () {
            var text = textarea.value.trim();
            if (!text) { toast('请输入回复内容', 'warn'); return; }
            addReply(commentId, text);
        });

        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                var text = textarea.value.trim();
                if (text) addReply(commentId, text);
            }
        });

        actions.appendChild(cancel);
        actions.appendChild(submit);
        wrap.appendChild(textarea);
        wrap.appendChild(actions);

        threadEl.appendChild(wrap);
        setTimeout(function () { textarea.focus(); }, 50);
    }

    /**
     * 编辑评论：内联展开 textarea + 类型 pills，支持改 content 与 type。
     */
    function startEdit(threadEl, comment) {
        // 已存在编辑框则关闭
        var existing = threadEl.querySelector('.cmt-edit-wrap');
        if (existing) { existing.remove(); return; }

        var wrap = document.createElement('div');
        wrap.className = 'cmt-edit-wrap';

        var textarea = document.createElement('textarea');
        textarea.className = 'cmt-reply-textarea cmt-edit-textarea';
        textarea.value = comment.content;
        textarea.setAttribute('aria-label', '编辑批注内容');

        // 类型 pills
        var typeGroup = document.createElement('div');
        typeGroup.className = 'cmt-type-group cmt-edit-type-group';
        typeGroup.setAttribute('role', 'radiogroup');
        typeGroup.setAttribute('aria-label', '批注类型');
        var selectedType = comment.type;
        Object.keys(COMMENT_TYPES).forEach(function (t) {
            var pill = document.createElement('button');
            pill.type = 'button';
            pill.className = 'cmt-type-pill';
            pill.dataset.type = t;
            pill.setAttribute('role', 'radio');
            pill.setAttribute('aria-checked', t === selectedType ? 'true' : 'false');
            pill.innerHTML = '<span class="cmt-type-icon">' + COMMENT_TYPES[t].icon + '</span><span>' + COMMENT_TYPES[t].label + '</span>';
            pill.addEventListener('click', function () {
                selectedType = t;
                typeGroup.querySelectorAll('.cmt-type-pill').forEach(function (p) {
                    p.setAttribute('aria-checked', p.dataset.type === selectedType ? 'true' : 'false');
                });
            });
            typeGroup.appendChild(pill);
        });

        var actions = document.createElement('div');
        actions.className = 'cmt-reply-actions';
        var cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'cmt-btn cmt-btn-ghost';
        cancel.textContent = '取消';
        cancel.addEventListener('click', function () { wrap.remove(); });

        var submit = document.createElement('button');
        submit.type = 'button';
        submit.className = 'cmt-btn cmt-btn-primary';
        submit.textContent = '保存';
        submit.addEventListener('click', function () {
            var text = textarea.value.trim();
            if (!text) { toast('请输入批注内容', 'warn'); textarea.focus(); return; }
            editComment(comment.id, text, selectedType);
        });

        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                var text = textarea.value.trim();
                if (text) editComment(comment.id, text, selectedType);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                wrap.remove();
            }
        });

        actions.appendChild(cancel);
        actions.appendChild(submit);
        wrap.appendChild(textarea);
        wrap.appendChild(typeGroup);
        wrap.appendChild(actions);

        threadEl.appendChild(wrap);
        setTimeout(function () { textarea.focus(); }, 50);
    }

    /* ========================================================
     * 十一、评论操作
     * ======================================================== */

    function addReply(commentId, text) {
        var comment = state.comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        if (!comment.replies) comment.replies = [];
        comment.replies.push({
            id: genReplyId(),
            content: text,
            author: '作者',
            createdAt: nowIso()
        });
        comment.updatedAt = nowIso();
        if (state.storageAvailable) Storage.saveComments(state.notePath, state.comments);
        renderPanel();
        toast('回复已添加', 'success');
    }

    function resolveComment(commentId) {
        var comment = state.comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.status = 'resolved';
        comment.resolvedAt = nowIso();
        comment.updatedAt = nowIso();
        if (state.storageAvailable) Storage.saveComments(state.notePath, state.comments);
        updateHighlightAttrs(commentId, null, 'resolved');
        renderPanel();
        toast('已标记为解决', 'success');
    }

    function reopenComment(commentId) {
        var comment = state.comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.status = 'open';
        comment.resolvedAt = null;
        comment.updatedAt = nowIso();
        if (state.storageAvailable) Storage.saveComments(state.notePath, state.comments);
        updateHighlightAttrs(commentId, null, 'open');
        renderPanel();
        toast('已重新打开', 'info');
    }

    function deleteComment(commentId) {
        if (!window.confirm('确定删除这条批注吗？（软删除，可从导出数据恢复）')) return;
        var comment = state.comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.deleted = true;
        comment.updatedAt = nowIso();
        if (state.storageAvailable) Storage.saveComments(state.notePath, state.comments);
        unwrapHighlight(commentId);
        renderPanel();
        toast('已删除', 'info');
    }

    function editComment(commentId, newContent, newType) {
        var comment = state.comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.content = newContent;
        if (newType && COMMENT_TYPES[newType] && newType !== comment.type) {
            comment.type = newType;
            updateHighlightAttrs(commentId, newType, null);
        }
        comment.updatedAt = nowIso();
        if (state.storageAvailable) Storage.saveComments(state.notePath, state.comments);
        renderPanel();
        toast('已更新', 'success');
    }

    /**
     * 在面板中定位并高亮某线程。
     */
    function openThreadInPanel(commentId) {
        state.activeThreadId = commentId;
        renderThreadList();
        var threadEl = document.querySelector('.cmt-thread[data-cmt-id="' + CSS.escape(commentId) + '"]');
        if (threadEl) {
            threadEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        // 同时跳转到原文
        jumpToComment(commentId);
    }

    /**
     * 跳转到原文位置并闪烁高亮。
     */
    function jumpToComment(commentId) {
        var comment = state.comments.find(function (c) { return c.id === commentId; });
        if (!comment || !comment.anchor || !state.container) {
            toast('无法定位原文', 'warn');
            return;
        }
        var range = resolveAnchor(comment.anchor, state.container);
        if (!range) {
            toast('原文已变更，未能定位', 'warn');
            return;
        }
        // 重新 wrap（若 mark 不存在）
        var existingMark = state.container.querySelector('mark.cmt-highlight[data-cmt-id="' + CSS.escape(commentId) + '"]');
        if (!existingMark) {
            try { wrapRangeWithHighlight(range, commentId, comment.type); } catch (e) { /* ignore */ }
        }
        var mark = state.container.querySelector('mark.cmt-highlight[data-cmt-id="' + CSS.escape(commentId) + '"]');
        if (mark) {
            mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
            mark.classList.add('cmt-flash');
            setTimeout(function () { mark.classList.remove('cmt-flash'); }, 1200);
        }
    }

    /* ========================================================
     * 十二、导出 / 导入
     * ======================================================== */

    /**
     * 构造导出 JSON 对象（符合 spec.md 6.1 deep-reading-comments/v1）。
     * @param {string} notePath
     * @param {boolean} includeNoteContent
     */
    function buildExportObject(notePath, includeNoteContent) {
        var comments = notePath ? Storage.loadComments(notePath) : getAllCommentsFlat();
        var filtered = comments.filter(function (c) { return !c.deleted; });

        var obj = {
            schema: EXPORT_SCHEMA,
            exportedAt: nowIso(),
            exportedBy: '作者',
            scope: notePath ? 'note' : 'all',
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                agents: AGENTS.slice()
            },
            comments: filtered
        };
        if (notePath) {
            obj.notePath = notePath;
            if (includeNoteContent) {
                obj.noteContent = getNoteContentForExport(notePath);
            }
        }
        return obj;
    }

    /**
     * 获取笔记全文（用于导出，scope=note 时附 noteContent）。
     * 简化：从当前 DOM 读取纯文本；若不是当前笔记则返回空。
     */
    function getNoteContentForExport(notePath) {
        if (notePath === state.notePath && state.container) {
            return state.container.textContent || '';
        }
        return '';
    }

    /**
     * 获取所有笔记的评论（扁平化，每条带 notePath）。
     */
    function getAllCommentsFlat() {
        var idx = Storage.loadIndex();
        var all = [];
        idx.forEach(function (entry) {
            var arr = Storage.loadComments(entry.notePath);
            all = all.concat(arr);
        });
        return all;
    }

    function doExportNote() {
        if (!state.notePath) { toast('请先选择一篇笔记', 'warn'); return; }
        var obj = buildExportObject(state.notePath, true);
        var date = dateStamp();
        var filename = 'comments_' + sanitizeFilename(state.notePath) + '_' + date + '.json';
        downloadJSON(JSON.stringify(obj, null, 2), filename);
        var meta = Storage.loadMeta();
        meta.lastExportAt = nowIso();
        lsSet(META_KEY, JSON.stringify(meta));
        toast('已导出 ' + obj.comments.length + ' 条批注', 'success');
    }

    function doExportAll() {
        var obj = buildExportObject(null, false);
        var date = dateStamp();
        var filename = 'comments_all_' + date + '.json';
        downloadJSON(JSON.stringify(obj, null, 2), filename);
        var meta = Storage.loadMeta();
        meta.lastExportAt = nowIso();
        lsSet(META_KEY, JSON.stringify(meta));
        toast('已导出 ' + obj.comments.length + ' 条批注（全站）', 'success');
    }

    function doImport() {
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json,application/json';
        input.addEventListener('change', function () {
            var file = input.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function () {
                try {
                    var jsonStr = String(reader.result);
                    // 预检测冲突，弹窗询问覆盖/跳过（spec.md F8 / checklist 1.8）
                    var preview = countImportConflicts(jsonStr);
                    var strategy = 'overwrite';
                    if (preview.conflicts > 0) {
                        var ok = window.confirm(
                            '检测到 ' + preview.conflicts + ' 条冲突批注（id 已存在）。\n' +
                            '点击「确定」覆盖冲突项，点击「取消」跳过冲突项。'
                        );
                        strategy = ok ? 'overwrite' : 'skip';
                    }
                    var imported = importJSON(jsonStr, 'merge', strategy);
                    toast('已导入 ' + imported.added + ' 条，跳过 ' + imported.skipped + ' 条冲突', 'success');
                } catch (e) {
                    toast('导入失败：' + (e.message || '文件格式错误'), 'error');
                }
            };
            reader.onerror = function () { toast('文件读取失败', 'error'); };
            reader.readAsText(file);
        });
        input.click();
    }

    /**
     * 预检测导入文件中的冲突数量（id 已存在的条数）。
     * @param {string} jsonStr
     * @returns {{conflicts:number, total:number}}
     */
    function countImportConflicts(jsonStr) {
        var data;
        try { data = JSON.parse(jsonStr); } catch (e) { return { conflicts: 0, total: 0 }; }
        var incoming = data.comments || data.threads || [];
        if (!Array.isArray(incoming)) return { conflicts: 0, total: 0 };
        var conflicts = 0;
        incoming.forEach(function (c) {
            if (!isValidComment(c)) return;
            var np = c.notePath || data.notePath;
            if (!np) return;
            var existing = Storage.loadComments(np);
            for (var i = 0; i < existing.length; i++) {
                if (existing[i].id === c.id) { conflicts++; break; }
            }
        });
        return { conflicts: conflicts, total: incoming.length };
    }

    /**
     * 导入专家评判结果（spec.md 7.3 / 6.3）。
     * 读取 expert_review_result.json，回填到对应 comment.expertReviews[]。
     */
    function doImportExpertReview() {
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json,application/json';
        input.addEventListener('change', function () {
            var file = input.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function () {
                try {
                    var count = importExpertReview(String(reader.result));
                    toast('已回填 ' + count + ' 条评判', 'success');
                } catch (e) {
                    toast('导入评判失败：' + (e.message || '文件格式错误'), 'error');
                }
            };
            reader.onerror = function () { toast('文件读取失败', 'error'); };
            reader.readAsText(file);
        });
        input.click();
    }

    /**
     * 导入 JSON（architecture.md 3.5）。
     * @param {string} jsonStr
     * @param {string} mode merge | replace
     * @param {string} [conflictStrategy=overwrite] overwrite | skip 冲突处理策略
     * @returns {{added:number, skipped:number, conflicts:number}}
     */
    function importJSON(jsonStr, mode, conflictStrategy) {
        var data = JSON.parse(jsonStr);
        var incomingComments = data.comments || data.threads || [];
        if (!Array.isArray(incomingComments)) throw new Error('comments 字段不是数组');

        conflictStrategy = conflictStrategy || 'overwrite';

        // 按笔记分组
        var byNote = {};
        incomingComments.forEach(function (c) {
            if (!isValidComment(c)) return;
            var np = c.notePath || data.notePath;
            if (!np) return;
            if (!byNote[np]) byNote[np] = [];
            byNote[np].push(c);
        });

        var added = 0, skipped = 0, conflicts = 0;
        Object.keys(byNote).forEach(function (np) {
            var existing = Storage.loadComments(np);
            if (mode === 'replace') {
                existing = [];
            }
            var idMap = {};
            existing.forEach(function (c) { idMap[c.id] = c; });

            byNote[np].forEach(function (c) {
                if (idMap[c.id]) {
                    conflicts++;
                    if (conflictStrategy === 'skip') {
                        // 跳过冲突项
                        skipped++;
                    } else {
                        // 覆盖冲突项
                        Object.assign(idMap[c.id], c, { updatedAt: nowIso() });
                        skipped++;
                    }
                } else {
                    existing.push(c);
                    idMap[c.id] = c;
                    added++;
                }
            });

            Storage.saveComments(np, existing);
        });

        // 若当前笔记受影响，刷新
        if (state.notePath && byNote[state.notePath]) {
            state.comments = Storage.loadComments(state.notePath);
            refreshHighlights();
            renderPanel();
        }
        return { added: added, skipped: skipped, conflicts: conflicts };
    }

    /* ========================================================
     * 十三、专家团
     * ======================================================== */

    function openExpertWizard() {
        var threads = state.comments.filter(function (c) { return !c.parentId && !c.deleted; });
        if (threads.length === 0) {
            toast('暂无批注可评判', 'warn');
            return;
        }

        var overlay = document.createElement('div');
        overlay.className = 'modal-overlay open';
        overlay.style.zIndex = '150';
        var modal = document.createElement('div');
        modal.className = 'modal cmt-modal-content';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');

        var header = document.createElement('div');
        header.className = 'modal-header';
        var title = document.createElement('h2');
        title.textContent = '启用专家团评判';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'modal-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', function () { document.body.removeChild(overlay); });
        header.appendChild(title);
        header.appendChild(closeBtn);

        var body = document.createElement('div');
        body.className = 'modal-body';

        // 范围
        var step1 = document.createElement('div');
        step1.className = 'cmt-wizard-step';
        var label1 = document.createElement('label');
        label1.className = 'cmt-wizard-step-label';
        label1.textContent = '1. 评判范围';
        var rg1 = document.createElement('div');
        rg1.className = 'cmt-wizard-radio-group';
        var scopeCurrent = document.createElement('label');
        scopeCurrent.className = 'cmt-wizard-radio';
        scopeCurrent.innerHTML = '<input type="radio" name="cmtScope" value="note" checked> 当前笔记';
        var scopeAll = document.createElement('label');
        scopeAll.className = 'cmt-wizard-radio';
        scopeAll.innerHTML = '<input type="radio" name="cmtScope" value="all"> 全站';
        rg1.appendChild(scopeCurrent);
        rg1.appendChild(scopeAll);
        step1.appendChild(label1);
        step1.appendChild(rg1);

        // 专家
        var step2 = document.createElement('div');
        step2.className = 'cmt-wizard-step';
        var label2 = document.createElement('label');
        label2.className = 'cmt-wizard-step-label';
        label2.textContent = '2. 参与专家';
        var cg = document.createElement('div');
        cg.className = 'cmt-wizard-checkbox-group';
        var agentLabels = {
            historian: '史官', biographer: '传记官', context_analyst: '背景分析',
            critic: '名家点评', philosopher: '问道', editor: '编辑'
        };
        AGENTS.forEach(function (a) {
            var lbl = document.createElement('label');
            lbl.className = 'cmt-wizard-checkbox';
            lbl.innerHTML = '<input type="checkbox" value="' + a + '" checked> ' + agentLabels[a];
            cg.appendChild(lbl);
        });
        step2.appendChild(label2);
        step2.appendChild(cg);

        // 附加指令
        var step3 = document.createElement('div');
        step3.className = 'cmt-wizard-step';
        var label3 = document.createElement('label');
        label3.className = 'cmt-wizard-step-label';
        label3.textContent = '3. 附加指令（可选）';
        var ta = document.createElement('textarea');
        ta.className = 'cmt-wizard-textarea';
        ta.placeholder = '如：重点核查引文出处、评估讲道理部分是否过度引申…';
        step3.appendChild(label3);
        step3.appendChild(ta);

        // 命令提示
        var cmd = document.createElement('div');
        cmd.className = 'cmt-wizard-cmd';
        cmd.textContent = '下载后本地执行：python src/main.py --expert-review expert_review_request.json';

        // 操作
        var actions = document.createElement('div');
        actions.className = 'modal-actions';
        var cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'btn-secondary';
        cancel.textContent = '取消';
        cancel.addEventListener('click', function () { document.body.removeChild(overlay); });
        var confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'btn-primary';
        confirm.textContent = '生成并下载';
        confirm.addEventListener('click', function () {
            var scope = overlay.querySelector('input[name="cmtScope"]:checked').value;
            var participants = Array.from(overlay.querySelectorAll('.cmt-wizard-checkbox input:checked')).map(function (cb) { return cb.value; });
            var instruction = ta.value.trim();
            var request = exportExpertReviewRequest(scope === 'note' ? state.notePath : null, participants, instruction);
            var filename = 'expert_review_request.json';
            downloadJSON(JSON.stringify(request, null, 2), filename);
            document.body.removeChild(overlay);
            toast('已生成专家团指令包，请下载后本地执行', 'success');
        });
        actions.appendChild(cancel);
        actions.appendChild(confirm);

        body.appendChild(step1);
        body.appendChild(step2);
        body.appendChild(step3);
        body.appendChild(cmd);
        body.appendChild(actions);

        modal.appendChild(header);
        modal.appendChild(body);
        overlay.appendChild(modal);
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) document.body.removeChild(overlay);
        });
        document.body.appendChild(overlay);
    }

    /**
     * 生成专家团评判请求包（spec.md 7.2）。
     */
    function exportExpertReviewRequest(notePath, participants, instruction) {
        var comments = notePath ?
            Storage.loadComments(notePath).filter(function (c) { return !c.deleted; }) :
            getAllCommentsFlat().filter(function (c) { return !c.deleted; });

        var threads = comments.filter(function (c) { return !c.parentId; }).map(function (c) {
            return {
                threadId: c.id,
                anchor: c.anchor ? {
                    quote: c.anchor.quote || c.anchor.exact,
                    rangeStart: c.anchor.rangeStart,
                    rangeEnd: c.anchor.rangeEnd
                } : null,
                status: c.status,
                tags: c.tags || [],
                targetAgent: c.agentHints ? c.agentHints.targetAgent : null,
                priority: c.agentHints ? c.agentHints.priority : 'normal',
                messages: [c].concat(c.replies || []).map(function (m) {
                    return {
                        id: m.id,
                        author: m.author,
                        type: c.type,
                        content: m.content,
                        createdAt: m.createdAt
                    };
                })
            };
        });

        return {
            schema: 'deep-reading-expert-review-request/v1',
            exportedAt: nowIso(),
            scope: notePath ? 'note' : 'all',
            notePath: notePath || undefined,
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                rulesSummary: '本规则用于指导生成 Markdown 讲书笔记，固定五段正文加一段结语。详见 .trae/rules/rules.md。'
            },
            expertReviewRequest: {
                participants: participants || AGENTS.slice(),
                additionalInstruction: instruction || '',
                rulesReference: '.trae/rules/rules.md'
            },
            threads: threads
        };
    }

    /**
     * 导入专家评判结果（spec.md 7.3）。
     */
    function importExpertReview(jsonStr) {
        var data = JSON.parse(jsonStr);
        if (!data.reviews || !Array.isArray(data.reviews)) throw new Error('reviews 字段缺失或不是数组');
        var count = 0;
        data.reviews.forEach(function (rv) {
            if (!rv.commentId) return;
            // 在所有笔记中查找该评论
            var idx = Storage.loadIndex();
            for (var i = 0; i < idx.length; i++) {
                var arr = Storage.loadComments(idx[i].notePath);
                var comment = arr.find(function (c) { return c.id === rv.commentId; });
                if (comment) {
                    if (!comment.expertReviews) comment.expertReviews = [];
                    comment.expertReviews.push({
                        commentId: rv.commentId,
                        verdict: rv.verdict,
                        confidence: rv.confidence,
                        rationale: rv.rationale,
                        suggestedEdit: rv.suggestedEdit,
                        reviewedAt: data.reviewedAt || nowIso(),
                        reviewedBy: rv.reviewedBy || []
                    });
                    comment.updatedAt = nowIso();
                    Storage.saveComments(idx[i].notePath, arr);
                    count++;
                    break;
                }
            }
        });
        if (state.notePath) {
            state.comments = Storage.loadComments(state.notePath);
            renderPanel();
        }
        return count;
    }

    /**
     * 导出给 AI（architecture.md 3.6 exportForAgents）。
     */
    function exportForAgents(notePath) {
        var comments = notePath ? Storage.loadComments(notePath) : getAllCommentsFlat();
        var filtered = comments.filter(function (c) { return !c.deleted; });
        var threads = filtered.filter(function (c) { return !c.parentId; }).map(function (c) {
            return {
                threadId: c.id,
                anchor: c.anchor ? {
                    quote: c.anchor.quote || c.anchor.exact,
                    rangeStart: c.anchor.rangeStart,
                    rangeEnd: c.anchor.rangeEnd
                } : null,
                status: c.status,
                tags: c.tags || [],
                targetAgent: c.agentHints ? c.agentHints.targetAgent : null,
                priority: c.agentHints ? c.agentHints.priority : 'normal',
                messages: [c].concat(c.replies || []).map(function (m) {
                    return {
                        id: m.id,
                        author: m.author,
                        type: c.type,
                        content: m.content,
                        createdAt: m.createdAt
                    };
                })
            };
        });
        return JSON.stringify({
            schemaVersion: SCHEMA_VERSION,
            exportedAt: nowIso(),
            notePath: notePath || undefined,
            threads: threads
        }, null, 2);
    }

    /**
     * 复制为 Prompt 上下文（architecture.md 6.2）。
     */
    function copyAsPromptContext(notePath) {
        var text = formatCommentsAsPrompt(notePath);
        return copyToClipboard(text).then(function (ok) {
            if (ok) toast('已复制 Prompt 上下文到剪贴板', 'success');
            else toast('复制失败，请手动复制', 'error');
        });
    }

    function formatCommentsAsPrompt(notePath) {
        var comments = notePath ? Storage.loadComments(notePath) : getAllCommentsFlat();
        var threads = comments.filter(function (c) { return !c.parentId && !c.deleted; });
        var lines = ['# 作者批注上下文'];
        lines.push('笔记：' + (notePath || '（全站）'));
        lines.push('');
        threads.forEach(function (c, i) {
            var typeInfo = COMMENT_TYPES[c.type] || { label: c.type };
            var agentHint = c.agentHints && c.agentHints.targetAgent ? ' [目标专家: ' + c.agentHints.targetAgent + ']' : '';
            var priority = c.agentHints && c.agentHints.priority ? ' [优先级: ' + c.agentHints.priority + ']' : '';
            lines.push('## 批注 ' + (i + 1) + ' [' + typeInfo.label + ']' + agentHint + priority);
            if (c.anchor && c.anchor.quote) {
                lines.push('原文：「' + c.anchor.quote + '」');
            }
            lines.push('作者：' + c.content);
            (c.replies || []).forEach(function (r) {
                lines.push('回复：' + r.content);
            });
            lines.push('');
        });
        return lines.join('\n');
    }

    /* ========================================================
     * 十四、辅助函数
     * ======================================================== */

    function truncate(s, n) {
        if (!s) return '';
        return s.length > n ? s.slice(0, n) + '…' : s;
    }

    function dateStamp() {
        var d = new Date();
        var pad = function (x) { return x < 10 ? '0' + x : '' + x; };
        return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate());
    }

    function sanitizeFilename(name) {
        return String(name).replace(/[\\/:*?"<>|/]/g, '_').slice(0, 60);
    }

    function copyToClipboard(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () {
                return legacyCopy(text);
            });
        }
        return Promise.resolve(legacyCopy(text));
    }

    function legacyCopy(text) {
        try {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            var ok = document.execCommand('copy');
            document.body.removeChild(ta);
            return ok;
        } catch (e) {
            return false;
        }
    }

    /* ========================================================
     * 十五、事件处理与生命周期
     * ======================================================== */

    /**
     * note:loaded 事件处理：初始化当前笔记的评论系统。
     */
    function onNoteLoaded(e) {
        var detail = e.detail || {};
        var container = detail.container;
        var notePath = detail.notePath;
        if (!container || !notePath) return;
        attach(container, notePath, detail.meta);
    }

    /**
     * 为指定容器初始化高亮 + 选区监听。
     * @param {Element} container
     * @param {string} notePath
     * @param {object} meta
     */
    function attach(container, notePath, meta) {
        // 先 detach 旧的
        detach();

        state.container = container;
        state.notePath = notePath;
        state.noteMeta = meta || null;
        state.noteVersion = computeNoteVersion();
        state.comments = Storage.loadComments(notePath);
        state.normTextCache = null;
        state.activeThreadId = null;

        // 渲染高亮
        refreshHighlights();

        // 绑定选区监听
        state.boundHandlers.mouseup = handleSelectionEnd;
        state.boundHandlers.selectionchange = handleSelectionChange;
        state.boundHandlers.click = handleHighlightClick;
        state.boundHandlers.mouseover = handleHighlightHover;
        state.boundHandlers.mouseout = handleHighlightMouseLeave;

        container.addEventListener('mouseup', state.boundHandlers.mouseup);
        container.addEventListener('touchend', state.boundHandlers.mouseup);
        document.addEventListener('selectionchange', state.boundHandlers.selectionchange);
        container.addEventListener('click', state.boundHandlers.click);
        container.addEventListener('mouseover', state.boundHandlers.mouseover);
        container.addEventListener('mouseout', state.boundHandlers.mouseout);

        // 渲染面板
        renderPanel();
    }

    /**
     * 卸载当前笔记的监听。
     */
    function detach() {
        if (state.container && state.boundHandlers.mouseup) {
            state.container.removeEventListener('mouseup', state.boundHandlers.mouseup);
            state.container.removeEventListener('touchend', state.boundHandlers.mouseup);
            state.container.removeEventListener('click', state.boundHandlers.click);
            state.container.removeEventListener('mouseover', state.boundHandlers.mouseover);
            state.container.removeEventListener('mouseout', state.boundHandlers.mouseout);
        }
        if (state.boundHandlers.selectionchange) {
            document.removeEventListener('selectionchange', state.boundHandlers.selectionchange);
        }
        state.boundHandlers = {};
        state.container = null;
        state.notePath = null;
        state.noteMeta = null;
        state.noteVersion = null;
        state.normTextCache = null;
        hideBubble();
        hidePopover();
        hideHoverCard();
    }

    /**
     * 重新渲染当前笔记的高亮。
     */
    function refresh() {
        if (state.notePath && state.container) {
            state.comments = Storage.loadComments(state.notePath);
            refreshHighlights();
            renderPanel();
        }
    }

    /**
     * 加载某笔记的评论（spec.md 8.6 公开 API）。
     */
    function loadForNote(notePath) {
        if (!notePath) return;
        var container = document.querySelector('.markdown-body');
        if (container) attach(container, notePath, null);
    }

    /**
     * 清空当前评论视图（切换笔记时）。
     */
    function clear() {
        detach();
        var panel = document.getElementById('cmtPanel');
        if (panel) {
            var list = panel.querySelector('.cmt-thread-list');
            if (list) list.innerHTML = '';
        }
    }

    /**
     * storage 事件：多标签页同步。
     */
    function onStorageChange(e) {
        if (e.key && e.key.indexOf(STORAGE_PREFIX) === 0 && state.notePath && e.key === STORAGE_PREFIX + state.notePath) {
            state.comments = Storage.loadComments(state.notePath);
            refreshHighlights();
            renderPanel();
        }
    }

    /**
     * 全局键盘：Esc 关闭浮层。
     */
    function onKeydown(e) {
        if (e.key === 'Escape') {
            var popover = document.getElementById('cmtPopover');
            if (popover && !popover.hidden) {
                hidePopover();
                return;
            }
            var bubble = document.getElementById('cmtBubble');
            if (bubble && !bubble.hidden) {
                hideBubble();
                return;
            }
        }
    }

    /**
     * 滚动时关闭气泡与浮层（architecture.md 4.2：浮层定位跟随选区，滚动时关闭）。
     */
    function onScroll() {
        hideBubble();
        hidePopover();
    }

    /* ========================================================
     * 十六、初始化
     * ======================================================== */

    function init() {
        // 检测 localStorage 可用性
        try {
            var k = '__drc_test__';
            localStorage.setItem(k, '1');
            localStorage.removeItem(k);
            state.storageAvailable = true;
        } catch (e) {
            state.storageAvailable = false;
            console.warn('[comments] localStorage 不可用，批注仅本次会话有效');
        }

        // 监听 note:loaded（由 app.js dispatch）
        document.addEventListener('note:loaded', onNoteLoaded);

        // 多标签页同步
        window.addEventListener('storage', onStorageChange);

        // 全局键盘
        document.addEventListener('keydown', onKeydown);

        // 滚动关闭气泡
        window.addEventListener('scroll', onScroll, true);

        // 把面板挂到 .layout 内
        var layout = document.querySelector('.layout');
        if (layout) {
            var panel = getOrCreatePanel();
            layout.appendChild(panel);
            // 初次渲染：未加载笔记时显示「请先选择一篇笔记」
            renderPanel();
        }

        // 工具栏按钮（若 index.html 中已存在则绑定，否则跳过）
        var exportBtn = document.getElementById('cmtExportBtn');
        if (exportBtn) exportBtn.addEventListener('click', doExportNote);
        var expertBtn = document.getElementById('cmtExpertBtn');
        if (expertBtn) expertBtn.addEventListener('click', openExpertWizard);
        var importBtn = document.getElementById('cmtImportBtn');
        if (importBtn) importBtn.addEventListener('click', doImport);

        console.info('[comments] 评论系统已初始化，storage =', state.storageAvailable);
    }

    /* ========================================================
     * 十七、公开 API
     * ======================================================== */

    window.DeepReadingComments = {
        // 生命周期
        init: init,
        loadForNote: loadForNote,
        clear: clear,
        attach: attach,
        detach: detach,
        refresh: refresh,

        // 查询
        getComments: function (notePath) { return Storage.loadComments(notePath); },
        getAllComments: function () {
            var result = {};
            Storage.loadIndex().forEach(function (e) {
                result[e.notePath] = Storage.loadComments(e.notePath);
            });
            return result;
        },
        getIndex: function () { return Storage.loadIndex(); },

        // 导出导入
        exportNote: function (notePath) {
            return JSON.stringify(buildExportObject(notePath, true), null, 2);
        },
        exportAll: function () {
            return JSON.stringify(buildExportObject(null, false), null, 2);
        },
        importJSON: importJSON,
        clearNote: function (notePath) { Storage.deleteNote(notePath); },

        // 专家团
        exportForAgents: exportForAgents,
        copyAsPromptContext: copyAsPromptContext,
        exportExpertReviewRequest: exportExpertReviewRequest,
        importExpertReview: importExpertReview,

        // 内部暴露（供控制台调试）
        _state: state,
        _resolveAnchor: resolveAnchor,
        _captureAnchor: captureAnchor,
        _buildNormalizedText: buildNormalizedText
    };

    // 自动初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
