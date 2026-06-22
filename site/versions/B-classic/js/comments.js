/* ============================================================
 * 原文批注式评论系统 · 版本B 古籍批注风
 * 纯 vanilla JS，IIFE 封装，暴露 window.DeepReadingComments
 *
 * 核心能力：
 *   - 监听 note:loaded 事件自动接入
 *   - 三级容错文本锚定（精确偏移 → quote 全文匹配 → 前后缀指纹）
 *   - 朱笔波浪下划线高亮、笺纸便笺浮层、右侧 margin notes 批注栏
 *   - 5 种评论类型（error/praise/discussion/supplement/thought），传统色彩
 *   - 回复、解决、删除、编辑
 *   - 导出/导入 JSON（deep-reading-comments/v1 schema）
 *   - 专家团触发：生成 expert_review_request.json
 *   - XSS 防护、孤儿批注降级、键盘可用
 *
 * 依赖：无（仅浏览器原生 API）
 * ============================================================ */

(function () {
    'use strict';

    /* ========================================================
     * 一、常量定义
     * ======================================================== */

    var SCHEMA = 'deep-reading-comments/v1';
    var STORAGE_PREFIX = 'drc:';
    var META_KEY = 'drc:meta';
    var ANCHOR_SCHEMA_VERSION = 1;
    var FINGERPRINT_LEN = 32;
    var MIN_QUOTE_LEN = 2;
    var MAX_QUOTE_LEN = 512;

    // 5 种评论类型 → 传统色彩（朱/赭/青/墨/黛）+ 印章单字
    var COMMENT_TYPES = {
        error:       { label: '错误指正', seal: '误', color: '#c0392b', agent: ['historian', 'context_analyst', 'editor'] },
        praise:      { label: '写得好',   seal: '赞', color: '#a0522d', agent: ['critic'] },
        discussion:  { label: '讨论',     seal: '议', color: '#5a7a8a', agent: ['philosopher', 'critic'] },
        supplement:  { label: '补充',     seal: '补', color: '#5a5651', agent: ['historian', 'context_analyst', 'editor'] },
        thought:     { label: '感想',     seal: '感', color: '#7a5a8a', agent: [] }
    };

    var AGENT_LABELS = {
        historian: '史官',
        biographer: '传记官',
        context_analyst: '背景分析',
        critic: '名家点评',
        philosopher: '问道',
        editor: '编辑'
    };

    var ALL_AGENTS = ['historian', 'biographer', 'context_analyst', 'critic', 'philosopher', 'editor'];

    // 禁批注元素（选区相交则拒绝）
    var FORBIDDEN_TAGS = ['SCRIPT', 'STYLE', 'CODE', 'PRE', 'KBD', 'SAMP', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'];

    /* ========================================================
     * 二、模块私有状态
     * ======================================================== */

    var currentNotePath = null;
    var currentContainer = null;
    var normTextCache = null;       // { normText, charMap, nodeIndex }
    var pendingRange = null;        // 浮层打开时锁定的选区 Range
    var pendingAnchor = null;       // 浮层打开时捕获的锚点
    var selectedType = 'discussion'; // 浮层当前选中的类型
    var sortBy = 'position';
    var showResolved = false;
    var storageAvailable = true;
    var seqCounter = 0;

    // DOM 引用
    var popoverEl = null;
    var popoverInputEl = null;
    var panelEl = null;
    var threadListEl = null;
    var panelCountEl = null;
    var tooltipEl = null;
    var fileInputEl = null;
    var fileImportMode = 'merge';

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
     * 生成唯一评论 ID：c_<timestamp>_<seq>
     */
    function generateId(prefix) {
        var p = prefix || 'c';
        seqCounter++;
        return p + '_' + Date.now() + '_' + seqCounter;
    }

    /**
     * 生成 ISO 8601 带时区时间戳
     */
    function nowISO() {
        return new Date().toISOString();
    }

    /**
     * 防抖
     */
    function debounce(fn, ms) {
        var timer = null;
        return function () {
            var ctx = this, args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
        };
    }

    /**
     * 格式化时间为简短显示
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
     * 简单字符串哈希（用于版本指纹）
     */
    function simpleHash(str) {
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
            hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
        }
        return (hash >>> 0).toString(16).padStart(8, '0');
    }

    /**
     * 安全地设置文本内容（防 XSS）
     */
    function setText(el, text) {
        if (el) el.textContent = text == null ? '' : String(text);
    }

    /**
     * 创建元素并设置属性
     */
    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        if (attrs) {
            for (var k in attrs) {
                if (attrs.hasOwnProperty(k)) {
                    if (k === 'className') node.className = attrs[k];
                    else if (k === 'text') setText(node, attrs[k]);
                    else if (k.indexOf('data-') === 0) node.setAttribute(k, attrs[k]);
                    else if (k === 'aria') {
                        for (var a in attrs.aria) node.setAttribute('aria-' + a, attrs.aria[a]);
                    } else node.setAttribute(k, attrs[k]);
                }
            }
        }
        if (children) {
            if (!Array.isArray(children)) children = [children];
            children.forEach(function (c) {
                if (c == null) return;
                if (typeof c === 'string') setText(node, c);
                else node.appendChild(c);
            });
        }
        return node;
    }

    /**
     * 下载 JSON 文件
     */
    function downloadJSON(data, filename) {
        var json = JSON.stringify(data, null, 2);
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
     * 显示 toast 提示（简易）
     */
    function showToast(message) {
        var existing = document.getElementById('cmtToast');
        if (existing) existing.remove();
        var toast = el('div', { id: 'cmtToast', className: 'cmt-toast' }, message);
        toast.style.cssText = 'position:fixed;top:75px;left:50%;transform:translateX(-50%);' +
            'padding:8px 20px;background:#2c2c2c;color:#fff;border-radius:4px;font-size:0.88rem;' +
            'z-index:200;box-shadow:0 4px 12px rgba(0,0,0,0.2);font-family:var(--font-sans);' +
            'transition:opacity 0.3s ease;';
        document.body.appendChild(toast);
        setTimeout(function () {
            toast.style.opacity = '0';
            setTimeout(function () { toast.remove(); }, 300);
        }, 2500);
    }

    /* ========================================================
     * 四、存储层
     * ======================================================== */

    var Storage = {
        /** 检测 localStorage 是否可用 */
        checkAvailable: function () {
            try {
                var k = '__drc_test__';
                localStorage.setItem(k, '1');
                localStorage.removeItem(k);
                return true;
            } catch (e) {
                return false;
            }
        },

        /** 加载单篇笔记的评论 */
        loadComments: function (notePath) {
            if (!storageAvailable) return [];
            try {
                var raw = localStorage.getItem(STORAGE_PREFIX + notePath);
                return raw ? JSON.parse(raw) : [];
            } catch (e) {
                console.error('[Comments] 加载评论失败:', e);
                return [];
            }
        },

        /** 保存单篇笔记的评论 */
        saveComments: function (notePath, comments) {
            if (!storageAvailable) {
                showToast('本地存储不可用，批注无法保存');
                return false;
            }
            try {
                localStorage.setItem(STORAGE_PREFIX + notePath, JSON.stringify(comments));
                // 配量预警：单笔记 > 200 条
                if (Array.isArray(comments) && comments.length > 200) {
                    showToast('本笔记批注已达 ' + comments.length + ' 条，建议导出后清理');
                }
                // 配量预警：全站总量 > 4MB
                if (this._totalSizeExceeded()) {
                    showToast('本地存储总量已超 4MB，建议导出全站批注后清理');
                }
                return true;
            } catch (e) {
                if (e.name === 'QuotaExceededError') {
                    showToast('存储空间已满，请导出后清理');
                } else {
                    console.error('[Comments] 保存评论失败:', e);
                }
                return false;
            }
        },

        /** 检测 localStorage 总量是否超过 4MB */
        _totalSizeExceeded: function () {
            try {
                var total = 0;
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    if (key && key.indexOf(STORAGE_PREFIX) === 0) {
                        var val = localStorage.getItem(key) || '';
                        total += val.length;
                    }
                }
                return total > 4 * 1024 * 1024;
            } catch (e) {
                return false;
            }
        },

        /** 加载全站评论 */
        loadAllComments: function () {
            var result = {};
            if (!storageAvailable) return result;
            try {
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    if (key && key.indexOf(STORAGE_PREFIX) === 0 && key !== META_KEY) {
                        var notePath = key.slice(STORAGE_PREFIX.length);
                        result[notePath] = JSON.parse(localStorage.getItem(key));
                    }
                }
            } catch (e) {
                console.error('[Comments] 加载全部评论失败:', e);
            }
            return result;
        },

        /** 删除单篇笔记的所有评论 */
        deleteNote: function (notePath) {
            if (!storageAvailable) return;
            try {
                localStorage.removeItem(STORAGE_PREFIX + notePath);
            } catch (e) {
                console.error('[Comments] 删除笔记评论失败:', e);
            }
        },

        /** 加载元信息 */
        loadMeta: function () {
            if (!storageAvailable) return { schema: SCHEMA, lastExportAt: null };
            try {
                var raw = localStorage.getItem(META_KEY);
                return raw ? JSON.parse(raw) : { schema: SCHEMA, lastExportAt: null };
            } catch (e) {
                return { schema: SCHEMA, lastExportAt: null };
            }
        },

        /** 保存元信息 */
        saveMeta: function (meta) {
            if (!storageAvailable) return;
            try {
                localStorage.setItem(META_KEY, JSON.stringify(meta));
            } catch (e) {
                console.error('[Comments] 保存元信息失败:', e);
            }
        }
    };

    /* ========================================================
     * 五、文本锚定算法（核心）
     * ======================================================== */

    /**
     * 判断文本节点是否可批注
     * 排除：script/style/code/pre/kbd/samp/h1-h6 内的文本
     */
    function isAnnotatableText(textNode) {
        if (!textNode || textNode.nodeType !== Node.TEXT_NODE) return false;
        var parent = textNode.parentElement;
        if (!parent) return false;
        var tag = parent.tagName;
        if (FORBIDDEN_TAGS.indexOf(tag) !== -1) return false;
        var raw = textNode.nodeValue;
        if (!raw || raw.replace(/\s+/g, '') === '') return false;
        return true;
    }

    /**
     * 判断选区是否与禁批注元素相交
     */
    function rangeIntersectsForbidden(range) {
        var container = currentContainer;
        if (!container) return true;
        var forbidden = container.querySelectorAll(FORBIDDEN_TAGS.join(','));
        for (var i = 0; i < forbidden.length; i++) {
            if (range.intersectsNode(forbidden[i])) return true;
        }
        return false;
    }

    /**
     * 构建原始文本到归一化文本的偏移映射
     * 返回 rawToNorm 数组（长度 = raw.length + 1）和 normToRaw 数组
     */
    function buildOffsetMaps(raw) {
        var rawLen = raw.length;
        var rawToNorm = new Array(rawLen + 1);
        var normLen = 0;
        var inWs = false;

        rawToNorm[0] = 0;
        for (var i = 0; i < rawLen; i++) {
            if (/\s/.test(raw[i])) {
                if (!inWs) {
                    normLen++;
                    inWs = true;
                }
            } else {
                normLen++;
                inWs = false;
            }
            rawToNorm[i + 1] = normLen;
        }

        // 构建反向映射 normToRaw
        var normToRaw = new Array(normLen + 1);
        var lastRaw = 0;
        for (var j = 0; j <= normLen; j++) {
            // 找到第一个 raw 偏移使得 rawToNorm[raw] === j
            while (lastRaw <= rawLen && rawToNorm[lastRaw] < j) lastRaw++;
            normToRaw[j] = lastRaw;
        }

        return { rawToNorm: rawToNorm, normToRaw: normToRaw, normLen: normLen };
    }

    /**
     * 遍历容器内可批注文本节点，构建规范化纯文本与反向映射
     * @returns {{ normText, charMap, nodeIndex }}
     *   charMap: [{ node, startNorm, length }] 每节点一条
     *   nodeIndex: WeakMap<Text, { startNorm, length, rawToNorm, normToRaw }>
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
            var maps = buildOffsetMaps(raw);

            nodeIndex.set(textNode, {
                startNorm: startNorm,
                length: maps.normLen,
                rawToNorm: maps.rawToNorm,
                normToRaw: maps.normToRaw
            });

            charMap.push({ node: textNode, startNorm: startNorm, length: maps.normLen });
            normText += normalized;
        }

        return { normText: normText, charMap: charMap, nodeIndex: nodeIndex };
    }

    /**
     * 将 DOM 偏移 (node, offset) 映射到规范化文本偏移
     */
    function mapDomOffsetToNorm(node, offset, nodeIndex) {
        if (!node || node.nodeType !== Node.TEXT_NODE) return null;
        var info = nodeIndex.get(node);
        if (!info) return null;
        var rawToNorm = info.rawToNorm;
        var safeOffset = Math.max(0, Math.min(offset, rawToNorm.length - 1));
        return info.startNorm + rawToNorm[safeOffset];
    }

    /**
     * 将规范化文本偏移区间转换为 DOM Range
     */
    function normRangeToDomRange(normStart, normEnd, charMap, nodeIndex) {
        if (!charMap || charMap.length === 0) return null;

        // 找到包含 normStart 的文本节点
        var startEntry = null;
        for (var i = 0; i < charMap.length; i++) {
            var entry = charMap[i];
            if (normStart >= entry.startNorm && normStart < entry.startNorm + entry.length) {
                startEntry = entry;
                break;
            }
        }
        // 如果 normStart 恰好在末尾
        if (!startEntry && charMap.length > 0) {
            var last = charMap[charMap.length - 1];
            if (normStart === last.startNorm + last.length) {
                startEntry = last;
            }
        }
        if (!startEntry) return null;

        // 找到包含 normEnd 的文本节点
        var endEntry = null;
        for (var j = 0; j < charMap.length; j++) {
            var e = charMap[j];
            if (normEnd > e.startNorm && normEnd <= e.startNorm + e.length) {
                endEntry = e;
                break;
            }
        }
        if (!endEntry) {
            // normEnd 可能超出，取最后一个节点末尾
            var lastNode = charMap[charMap.length - 1];
            if (normEnd >= lastNode.startNorm + lastNode.length) {
                endEntry = lastNode;
            }
        }
        if (!endEntry) return null;

        var startInfo = nodeIndex.get(startEntry.node);
        var endInfo = nodeIndex.get(endEntry.node);
        if (!startInfo || !endInfo) return null;

        var localStart = normStart - startInfo.startNorm;
        var localEnd = normEnd - endInfo.startNorm;
        var rawStart = startInfo.normToRaw[localStart];
        var rawEnd = endInfo.normToRaw[localEnd];

        try {
            var range = document.createRange();
            range.setStart(startEntry.node, rawStart);
            range.setEnd(endEntry.node, rawEnd);
            return range;
        } catch (e) {
            console.error('[Comments] 创建 Range 失败:', e);
            return null;
        }
    }

    /**
     * 计算选区所在段落的索引和标题路径
     */
    function computeParagraphInfo(range, container) {
        var blockElements = container.querySelectorAll('p, blockquote, li, td, th, div');
        var paragraphIndex = 0;
        var startNode = range.startContainer;

        // 找到包含选区起点的块级元素
        var startBlock = startNode.nodeType === Node.TEXT_NODE ? startNode.parentElement : startNode;
        while (startBlock && startBlock !== container) {
            if (startBlock.tagName === 'P' || startBlock.tagName === 'BLOCKQUOTE' || startBlock.tagName === 'LI') break;
            startBlock = startBlock.parentElement;
        }

        // 计算段落索引
        if (startBlock) {
            for (var i = 0; i < blockElements.length; i++) {
                if (blockElements[i] === startBlock) {
                    paragraphIndex = i;
                    break;
                }
            }
        }

        // 计算标题路径：从顶层标题到当前段最近的标题
        var headingPath = [];
        var allHeadings = container.querySelectorAll('h1, h2, h3, h4, h5, h6');
        var startRect = range.getBoundingClientRect();
        var precedingHeadings = [];
        for (var h = 0; h < allHeadings.length; h++) {
            var heading = allHeadings[h];
            var headingRect = heading.getBoundingClientRect();
            if (headingRect.top <= startRect.top + 1) {
                precedingHeadings.push(heading);
            } else {
                break;
            }
        }
        // 从最近标题向上追溯，只保留层级严格递增的标题（h1 > h2 > ...）
        var minLevel = 7;
        for (var i = precedingHeadings.length - 1; i >= 0; i--) {
            var level = parseInt(precedingHeadings[i].tagName.charAt(1), 10);
            if (level < minLevel) {
                headingPath.unshift(precedingHeadings[i].textContent.trim());
                minLevel = level;
            }
        }

        return { paragraphIndex: paragraphIndex, headingPath: headingPath };
    }

    /**
     * 从当前选区捕获锚点
     * @returns {Anchor|null}
     */
    function captureAnchor(selection, notePath) {
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
        var range = selection.getRangeAt(0);
        var container = currentContainer;
        if (!container || !container.contains(range.commonAncestorContainer)) return null;

        // 校验选区不落在禁批注元素内
        if (rangeIntersectsForbidden(range)) return null;

        // 构建规范化纯文本
        var built = buildNormalizedText(container);
        var normText = built.normText;
        var charMap = built.charMap;
        var nodeIndex = built.nodeIndex;

        // 计算选区在 normText 中的起止偏移
        var startNorm = mapDomOffsetToNorm(range.startContainer, range.startOffset, nodeIndex);
        var endNorm = mapDomOffsetToNorm(range.endContainer, range.endOffset, nodeIndex);
        if (startNorm == null || endNorm == null || endNorm <= startNorm) return null;

        var rangeStart = startNorm;
        var rangeEnd = endNorm;
        var quote = normText.slice(rangeStart, rangeEnd);

        // 长度校验
        if (quote.length < MIN_QUOTE_LEN) return null;
        if (quote.length > MAX_QUOTE_LEN) {
            quote = quote.slice(0, MAX_QUOTE_LEN);
            rangeEnd = rangeStart + MAX_QUOTE_LEN;
        }

        // 前后缀指纹
        var normTextPrefix = normText.slice(Math.max(0, rangeStart - FINGERPRINT_LEN), rangeStart);
        var normTextSuffix = normText.slice(rangeEnd, rangeEnd + FINGERPRINT_LEN);

        // 段落信息
        var paraInfo = computeParagraphInfo(range, container);

        // 版本指纹
        var version = simpleHash(normText);

        return {
            strategy: 'text+context',
            exact: quote,
            prefix: normTextPrefix,
            suffix: normTextSuffix,
            rangeStart: rangeStart,
            rangeEnd: rangeEnd,
            charOffsetStart: rangeStart,
            charOffsetEnd: rangeEnd,
            paragraphIndex: paraInfo.paragraphIndex,
            headingPath: paraInfo.headingPath,
            version: version,
            schemaVersion: ANCHOR_SCHEMA_VERSION
        };
    }

    /**
     * 模糊定位：用前缀+后缀指纹在 normText 中查找
     * 允许 ≤2 字符编辑距离
     */
    function fuzzyLocateByFingerprints(normText, prefix, suffix, quoteLen) {
        if (!prefix && !suffix) return null;

        // 在 normText 中搜索 prefix 的近似匹配
        var candidates = [];
        if (prefix && prefix.length > 0) {
            // 精确搜索
            var idx = normText.indexOf(prefix);
            while (idx !== -1) {
                candidates.push(idx + prefix.length);
                idx = normText.indexOf(prefix, idx + 1);
            }
            // 若精确无果，尝试缩短前缀
            if (candidates.length === 0 && prefix.length > 8) {
                var shortPrefix = prefix.slice(-8);
                var sIdx = normText.indexOf(shortPrefix);
                while (sIdx !== -1) {
                    candidates.push(sIdx + shortPrefix.length);
                    sIdx = normText.indexOf(shortPrefix, sIdx + 1);
                }
            }
        }

        // 若无前缀候选，用 suffix 反推
        if (candidates.length === 0 && suffix && suffix.length > 0) {
            var sIdx2 = normText.indexOf(suffix);
            while (sIdx2 !== -1) {
                candidates.push(sIdx2 - quoteLen);
                sIdx2 = normText.indexOf(suffix, sIdx2 + 1);
            }
            if (candidates.length === 0 && suffix.length > 8) {
                var shortSuffix = suffix.slice(0, 8);
                var sIdx3 = normText.indexOf(shortSuffix);
                while (sIdx3 !== -1) {
                    candidates.push(sIdx3 - quoteLen);
                    sIdx3 = normText.indexOf(shortSuffix, sIdx3 + 1);
                }
            }
        }

        // 对每个候选，用 suffix 校验
        for (var c = 0; c < candidates.length; c++) {
            var start = candidates[c];
            var end = start + quoteLen;
            if (start < 0 || end > normText.length) continue;
            // 校验 suffix
            if (suffix && suffix.length > 0) {
                var actualSuffix = normText.slice(end, end + suffix.length);
                if (editDistance(actualSuffix, suffix) <= 2) {
                    return { start: start, end: end };
                }
            } else {
                return { start: start, end: end };
            }
        }

        return null;
    }

    /**
     * 简易编辑距离（Levenshtein），限制最大长度 64
     */
    function editDistance(a, b) {
        if (a === b) return 0;
        if (!a) return b ? b.length : 0;
        if (!b) return a.length;
        var maxLen = 64;
        if (a.length > maxLen) a = a.slice(0, maxLen);
        if (b.length > maxLen) b = b.slice(0, maxLen);
        var m = a.length, n = b.length;
        var prev = new Array(n + 1);
        var curr = new Array(n + 1);
        for (var j = 0; j <= n; j++) prev[j] = j;
        for (var i = 1; i <= m; i++) {
            curr[0] = i;
            for (var j = 1; j <= n; j++) {
                var cost = a[i - 1] === b[j - 1] ? 0 : 1;
                curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
            }
            var tmp = prev; prev = curr; curr = tmp;
        }
        return prev[n];
    }

    /**
     * 在当前容器内解析锚点，返回 Range
     * 三级策略：精确偏移 + quote 校验 → quote 全文匹配 → 前后缀指纹模糊匹配
     * @param {Anchor} anchor
     * @param {Element} container
     * @param {object} [builtCache] 可选，预构建的规范化文本缓存
     */
    function resolveAnchor(anchor, container, builtCache) {
        if (!anchor || !container) return null;
        var built = builtCache || buildNormalizedText(container);
        var normText = built.normText;
        var charMap = built.charMap;
        var nodeIndex = built.nodeIndex;

        // —— 级别 1：精确偏移 + quote 校验 ——
        if (anchor.rangeEnd <= normText.length) {
            var slice = normText.slice(anchor.rangeStart, anchor.rangeEnd);
            if (slice === anchor.exact) {
                var r1 = normRangeToDomRange(anchor.rangeStart, anchor.rangeEnd, charMap, nodeIndex);
                if (r1) return r1;
            }
        }

        // —— 级别 2：quote 全文查找 ——
        var idx = normText.indexOf(anchor.exact);
        if (idx !== -1) {
            var r2 = normRangeToDomRange(idx, idx + anchor.exact.length, charMap, nodeIndex);
            if (r2) return r2;
        }

        // —— 级别 3：前缀 + 后缀指纹模糊定位 ——
        var fuzzy = fuzzyLocateByFingerprints(normText, anchor.prefix, anchor.suffix, anchor.exact.length);
        if (fuzzy) {
            var r3 = normRangeToDomRange(fuzzy.start, fuzzy.end, charMap, nodeIndex);
            if (r3) return r3;
        }

        return null; // 解析失败
    }

    /* ========================================================
     * 六、高亮 wrap / unwrap
     * ======================================================== */

    /**
     * 收集 Range 内所有文本节点
     */
    function collectTextNodesInRange(range) {
        var nodes = [];
        var container = range.commonAncestorContainer;
        if (container.nodeType === Node.TEXT_NODE) {
            nodes.push(container);
            return nodes;
        }
        var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
            acceptNode: function (node) {
                if (!range.intersectsNode(node)) return NodeFilter.FILTER_REJECT;
                if (!isAnnotatableText(node)) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        var textNode;
        while ((textNode = walker.nextNode())) {
            nodes.push(textNode);
        }
        return nodes;
    }

    /**
     * 把 Range 包裹成 <mark class="cmt-highlight cmt-type-xxx" data-cm-id="...">
     * 跨多个文本节点时逐节点切分并分别包裹
     * @param {Range} range
     * @param {string} commentId
     * @param {string} type
     * @param {number} [replyCount=0] 回复数，用于 aria-label
     */
    function wrapRangeWithHighlight(range, commentId, type, replyCount) {
        if (!range) return;
        // 提前捕获偏移量，splitText 后 range 可能被浏览器自动更新
        var startContainer = range.startContainer;
        var endContainer = range.endContainer;
        var startOffset = range.startOffset;
        var endOffset = range.endOffset;
        var textNodes = collectTextNodesInRange(range);
        if (textNodes.length === 0) return;

        var typeInfo = COMMENT_TYPES[type] || COMMENT_TYPES.discussion;
        var ariaLabel = '批注：' + typeInfo.label + '，' + (replyCount || 0) + ' 条回复';

        textNodes.forEach(function (node, i) {
            var target = node;
            var isStart = (i === 0);
            var isEnd = (i === textNodes.length - 1);

            // 首节点：从 startOffset 切分
            if (isStart && node === startContainer && startOffset > 0) {
                try {
                    target = node.splitText(startOffset);
                } catch (e) { return; }
            }

            // 末节点：从 endOffset 切分
            if (isEnd) {
                var offset;
                if (node === startContainer) {
                    // 同一节点既是首又是尾
                    offset = endOffset - startOffset;
                } else {
                    offset = endOffset;
                }
                if (offset > 0 && offset < target.length) {
                    try { target.splitText(offset); } catch (e) {}
                }
            }

            // 包裹
            var mark = document.createElement('mark');
            mark.className = 'cmt-highlight cmt-type-' + (type || 'discussion');
            mark.setAttribute('data-cm-id', commentId);
            mark.setAttribute('tabindex', '0');
            mark.setAttribute('role', 'mark');
            mark.setAttribute('aria-label', ariaLabel);
            try {
                target.parentNode.insertBefore(mark, target);
                mark.appendChild(target);
            } catch (e) {
                console.error('[Comments] wrap 失败:', e);
            }
        });
    }

    /**
     * 移除指定评论 ID 的高亮
     */
    function unwrapHighlight(commentId) {
        if (!currentContainer) return;
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        marks.forEach(function (mark) {
            var parent = mark.parentNode;
            if (!parent) return;
            // 将子节点移出 mark
            while (mark.firstChild) {
                parent.insertBefore(mark.firstChild, mark);
            }
            parent.removeChild(mark);
            // 合并相邻文本节点
            parent.normalize();
        });
    }

    /**
     * 更新高亮的类型样式
     */
    function updateHighlightType(commentId, newType) {
        if (!currentContainer) return;
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        marks.forEach(function (mark) {
            mark.className = 'cmt-highlight cmt-type-' + newType;
            var typeInfo = COMMENT_TYPES[newType] || COMMENT_TYPES.discussion;
            mark.setAttribute('aria-label', '批注：' + typeInfo.label);
        });
    }

    /**
     * 更新高亮的解决状态
     */
    function updateHighlightStatus(commentId, resolved) {
        if (!currentContainer) return;
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        marks.forEach(function (mark) {
            if (resolved) {
                mark.classList.add('cmt-resolved');
            } else {
                mark.classList.remove('cmt-resolved');
            }
        });
    }

    /**
     * 更新高亮的 aria-label（含回复数）
     */
    function updateHighlightAriaLabel(commentId, type, replyCount) {
        if (!currentContainer) return;
        var typeInfo = COMMENT_TYPES[type] || COMMENT_TYPES.discussion;
        var label = '批注：' + typeInfo.label + '，' + (replyCount || 0) + ' 条回复';
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        marks.forEach(function (mark) {
            mark.setAttribute('aria-label', label);
        });
    }

    /**
     * 闪烁高亮（跳转时）
     */
    function flashHighlight(commentId) {
        if (!currentContainer) return;
        var mark = currentContainer.querySelector('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        if (mark) {
            mark.classList.add('cmt-flash');
            setTimeout(function () { mark.classList.remove('cmt-flash'); }, 600);
        }
    }

    /* ========================================================
     * 七、浮层（笺纸便笺）
     * ======================================================== */

    /**
     * 创建浮层 DOM
     */
    function createPopover() {
        if (popoverEl) return;
        popoverEl = el('div', {
            id: 'cmtPopover',
            className: 'cmt-popover',
            role: 'dialog',
            'aria-modal': 'true',
            'aria-labelledby': 'cmtPopoverTitle',
            hidden: ''
        });

        // 浮层标题（供 aria-labelledby 引用，视觉隐藏）
        var title = el('span', { id: 'cmtPopoverTitle', className: 'cmt-sr-only' }, '新建批注');
        popoverEl.appendChild(title);

        // 引用原文
        var quote = el('div', { className: 'cmt-popover-quote', id: 'cmtPopoverQuote' });
        popoverEl.appendChild(quote);

        // 输入框
        popoverInputEl = el('textarea', {
            className: 'cmt-popover-input',
            id: 'cmtPopoverInput',
            placeholder: '写下你的批注…（Ctrl+Enter 提交，Esc 关闭）',
            'aria-label': '批注内容'
        });
        popoverEl.appendChild(popoverInputEl);

        // 类型选择
        var typesContainer = el('div', { className: 'cmt-popover-types', role: 'radiogroup', 'aria-label': '批注类型' });
        Object.keys(COMMENT_TYPES).forEach(function (type) {
            var info = COMMENT_TYPES[type];
            var seal = el('span', { className: 'cmt-seal cmt-seal-' + type }, info.seal);
            var btn = el('button', {
                type: 'button',
                className: 'cmt-popover-type',
                role: 'radio',
                'aria-checked': type === selectedType ? 'true' : 'false',
                'data-type': type,
                style: '--cmtB-type-color: ' + info.color + ';'
            });
            btn.appendChild(seal);
            btn.appendChild(document.createTextNode(info.label));
            btn.addEventListener('click', function () {
                selectedType = type;
                typesContainer.querySelectorAll('.cmt-popover-type').forEach(function (b) {
                    b.setAttribute('aria-checked', b.dataset.type === type ? 'true' : 'false');
                });
                popoverInputEl.focus();
            });
            typesContainer.appendChild(btn);
        });
        popoverEl.appendChild(typesContainer);

        // 操作按钮
        var actions = el('div', { className: 'cmt-popover-actions' });
        var cancelBtn = el('button', { type: 'button', className: 'cmt-popover-cancel' }, '取消');
        cancelBtn.addEventListener('click', hidePopover);
        var submitBtn = el('button', { type: 'button', className: 'cmt-popover-submit' }, '提交');
        submitBtn.addEventListener('click', submitComment);
        actions.appendChild(cancelBtn);
        actions.appendChild(submitBtn);
        popoverEl.appendChild(actions);

        document.body.appendChild(popoverEl);

        // 键盘事件
        popoverInputEl.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitComment();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                hidePopover();
            }
        });

        // 焦点陷阱：Tab 在浮层内循环，不跳出
        popoverEl.addEventListener('keydown', function (e) {
            if (e.key !== 'Tab') return;
            var focusables = popoverEl.querySelectorAll(
                'button:not([disabled]), textarea:not([disabled]), input:not([disabled])'
            );
            if (focusables.length === 0) return;
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        });

        // 点击浮层外部关闭
        document.addEventListener('mousedown', function (e) {
            if (popoverEl && !popoverEl.hidden && !popoverEl.contains(e.target)) {
                // 不在浮层内，且不在选区内，则关闭
                var sel = window.getSelection();
                if (!sel || sel.isCollapsed) {
                    hidePopover();
                }
            }
        });
    }

    /**
     * 显示浮层
     */
    function showPopover(range, anchor) {
        createPopover();
        pendingRange = range;
        pendingAnchor = anchor;

        // 显示引用原文
        var quoteEl = popoverEl.querySelector('#cmtPopoverQuote');
        setText(quoteEl, '「' + anchor.exact + '」');

        // 清空输入
        popoverInputEl.value = '';

        // 定位
        positionPopover(range);

        popoverEl.hidden = false;
        setTimeout(function () { popoverInputEl.focus(); }, 50);
    }

    /**
     * 隐藏浮层
     */
    function hidePopover() {
        if (popoverEl) popoverEl.hidden = true;
        pendingRange = null;
        pendingAnchor = null;
    }

    /**
     * 浮层定位
     */
    function positionPopover(range) {
        if (!popoverEl || !range) return;
        var rect = range.getBoundingClientRect();
        var scrollY = window.scrollY;
        var scrollX = window.scrollX;
        var popoverWidth = 340;
        var popoverHeight = 200; // 估计值

        var left = rect.left + scrollX + rect.width / 2 - popoverWidth / 2;
        var top = rect.bottom + scrollY + 8;

        // 边界检查
        if (left < scrollX + 10) left = scrollX + 10;
        if (left + popoverWidth > scrollX + window.innerWidth - 10) {
            left = scrollX + window.innerWidth - popoverWidth - 10;
        }
        if (top + popoverHeight > scrollY + window.innerHeight - 10) {
            // 翻转到上方
            top = rect.top + scrollY - popoverHeight - 8;
            if (top < scrollY + 60) top = scrollY + 60;
        }

        popoverEl.style.left = left + 'px';
        popoverEl.style.top = top + 'px';
        popoverEl.style.transform = 'none';
    }

    /**
     * 提交评论
     */
    function submitComment() {
        if (!pendingAnchor || !pendingRange) return;
        var content = popoverInputEl.value.trim();
        if (!content) {
            popoverInputEl.focus();
            return;
        }

        var comment = {
            id: generateId('c'),
            notePath: currentNotePath,
            anchor: pendingAnchor,
            content: content,
            type: selectedType,
            author: '作者',
            createdAt: nowISO(),
            updatedAt: nowISO(),
            status: 'open',
            replies: [],
            expertReviews: [],
            deleted: false
        };

        // 保存
        var comments = Storage.loadComments(currentNotePath);
        comments.push(comment);
        Storage.saveComments(currentNotePath, comments);

        // 高亮
        wrapRangeWithHighlight(pendingRange, comment.id, comment.type);

        // 清除选区
        var sel = window.getSelection();
        if (sel) sel.removeAllRanges();

        // 隐藏浮层
        hidePopover();

        // 刷新批注栏
        renderPanel();

        showToast('已添加批注');
    }

    /* ========================================================
     * 八、悬浮卡（tooltip）
     * ======================================================== */

    function createTooltip() {
        if (tooltipEl) return;
        tooltipEl = el('div', { id: 'cmtTooltip', className: 'cmt-tooltip', role: 'tooltip', hidden: '' });
        document.body.appendChild(tooltipEl);
    }

    function showTooltip(commentId, x, y) {
        createTooltip();
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;

        var typeInfo = COMMENT_TYPES[comment.type] || COMMENT_TYPES.discussion;
        var content = comment.content.length > 100 ? comment.content.slice(0, 100) + '…' : comment.content;
        tooltipEl.innerHTML = '';
        var seal = el('span', { className: 'cmt-seal cmt-seal-' + comment.type, style: 'width:16px;height:16px;font-size:10px;margin-right:4px;' }, typeInfo.seal);
        tooltipEl.appendChild(seal);
        tooltipEl.appendChild(document.createTextNode(content));
        var meta = el('div', { className: 'cmt-tooltip-meta' },
            comment.author + ' · ' + formatTime(comment.createdAt) +
            ' · ' + (comment.status === 'open' ? '未解决' : '已解决') +
            (comment.replies.length > 0 ? ' · ' + comment.replies.length + ' 回复' : ''));
        tooltipEl.appendChild(meta);

        tooltipEl.style.left = (x + 12) + 'px';
        tooltipEl.style.top = (y + 12) + 'px';
        tooltipEl.hidden = false;
    }

    function hideTooltip() {
        if (tooltipEl) tooltipEl.hidden = true;
    }

    /* ========================================================
     * 九、批注栏（margin notes）
     * ======================================================== */

    function ensurePanel() {
        panelEl = document.getElementById('cmtPanel');
        threadListEl = document.getElementById('cmtThreadList');
        panelCountEl = document.getElementById('cmtPanelCount');
        if (!panelEl) return;
        panelEl.hidden = false;
    }

    /**
     * 渲染批注栏
     */
    function renderPanel() {
        if (!panelEl || !threadListEl) return;
        var comments = Storage.loadComments(currentNotePath);
        // 过滤已删除
        comments = comments.filter(function (c) { return !c.deleted; });

        // 更新计数
        setText(panelCountEl, '(' + comments.length + ')');

        // 排序
        var sorted = comments.slice().sort(function (a, b) {
            if (sortBy === 'time') {
                return a.createdAt < b.createdAt ? -1 : (a.createdAt > b.createdAt ? 1 : 0);
            }
            if (sortBy === 'status') {
                if (a.status !== b.status) return a.status === 'open' ? -1 : 1;
                return (a.anchor ? a.anchor.rangeStart : 0) - (b.anchor ? b.anchor.rangeStart : 0);
            }
            // position
            return (a.anchor ? a.anchor.rangeStart : 999999) - (b.anchor ? b.anchor.rangeStart : 999999);
        });

        // 过滤已解决
        if (!showResolved) {
            sorted = sorted.filter(function (c) { return c.status === 'open'; });
        }

        // 清空
        threadListEl.innerHTML = '';

        if (sorted.length === 0) {
            var empty = el('div', { className: 'cmt-empty' });
            var icon = el('div', { className: 'cmt-empty-icon' }, '〤');
            empty.appendChild(icon);
            empty.appendChild(document.createTextNode('暂无批注，圈选原文即可开始批注'));
            threadListEl.appendChild(empty);
            return;
        }

        sorted.forEach(function (comment) {
            threadListEl.appendChild(renderCard(comment));
        });
    }

    /**
     * 渲染单条便笺卡片
     */
    function renderCard(comment) {
        var typeInfo = COMMENT_TYPES[comment.type] || COMMENT_TYPES.discussion;
        var isOrphan = comment.anchor && comment.anchor._orphan;
        var replyCount = (comment.replies || []).length;
        var statusLabel = comment.status === 'resolved' ? '已解决' : '未解决';

        var card = el('li', {
            className: 'cmt-card' + (isOrphan ? ' cmt-orphan' : ''),
            'data-cm-id': comment.id,
            'data-cm-status': comment.status,
            'aria-label': typeInfo.label + '：' + (comment.content || '').slice(0, 30) + '…，' + replyCount + ' 回复，' + statusLabel
        });

        // 头部：印章 + 作者 + 时间
        var header = el('div', { className: 'cmt-card-header' });
        var seal = el('span', { className: 'cmt-seal cmt-seal-' + comment.type }, typeInfo.seal);
        header.appendChild(seal);
        var author = el('span', { className: 'cmt-card-author' }, comment.author);
        header.appendChild(author);
        var time = el('span', { className: 'cmt-card-time' }, formatTime(comment.createdAt));
        header.appendChild(time);
        card.appendChild(header);

        // 引用原文
        if (comment.anchor && comment.anchor.exact) {
            var quoteText = comment.anchor.exact.length > 80
                ? comment.anchor.exact.slice(0, 80) + '…'
                : comment.anchor.exact;
            var quote = el('div', { className: 'cmt-card-quote' }, '「' + quoteText + '」');
            if (isOrphan) {
                var orphanBadge = el('span', { className: 'cmt-orphan-badge' }, '⚠ 原文已变更');
                quote.appendChild(orphanBadge);
            }
            card.appendChild(quote);
        }

        // 正文
        var content = el('p', { className: 'cmt-card-content' }, comment.content);
        card.appendChild(content);

        // 回复列表
        if (comment.replies && comment.replies.length > 0) {
            var replies = el('ul', { className: 'cmt-card-replies' });
            comment.replies.forEach(function (reply) {
                var li = el('li', { className: 'cmt-reply' });
                var replyAuthor = el('span', { className: 'cmt-reply-author' }, reply.author + '：');
                li.appendChild(replyAuthor);
                li.appendChild(document.createTextNode(reply.content));
                var replyTime = el('span', { className: 'cmt-reply-time' }, formatTime(reply.createdAt));
                li.appendChild(replyTime);
                replies.appendChild(li);
            });
            card.appendChild(replies);
        }

        // 专家评判徽章
        if (comment.expertReviews && comment.expertReviews.length > 0) {
            comment.expertReviews.forEach(function (review) {
                var badge = el('span', {
                    className: 'cmt-expert-badge cmt-verdict-' + review.verdict,
                    title: '点击查看评判详情'
                }, '名家：' + (review.verdict === 'accept' ? '采纳' : review.verdict === 'reject' ? '不采纳' : '待议'));
                badge.addEventListener('click', function () {
                    var detail = card.querySelector('.cmt-expert-detail');
                    if (detail) detail.classList.toggle('cmt-open');
                });
                card.appendChild(badge);

                var detail = el('div', { className: 'cmt-expert-detail' });
                var rationale = el('p', {}, '理由：' + (review.rationale || ''));
                detail.appendChild(rationale);
                if (review.suggestedEdit && review.suggestedEdit.text) {
                    var suggestion = el('p', {}, '建议：' + review.suggestedEdit.text);
                    detail.appendChild(suggestion);
                    var applyBtn = el('button', {
                        type: 'button',
                        className: 'cmt-popover-submit',
                        style: 'padding:2px 8px;font-size:0.72rem;margin-top:4px;'
                    }, '复制建议');
                    applyBtn.addEventListener('click', function () {
                        copyToClipboard(review.suggestedEdit.text);
                        showToast('已复制建议到剪贴板');
                    });
                    detail.appendChild(applyBtn);
                }
                card.appendChild(detail);
            });
        }

        // 已解决"阅"印
        if (comment.status === 'resolved') {
            var readSeal = el('div', { className: 'cmt-read-seal' }, '阅');
            card.appendChild(readSeal);
        }

        // 操作按钮
        var actions = el('div', { className: 'cmt-card-actions' });

        var jumpBtn = el('button', { type: 'button', title: '跳转到原文' }, '跳转');
        jumpBtn.addEventListener('click', function () { jumpToComment(comment.id); });
        actions.appendChild(jumpBtn);

        var replyBtn = el('button', { type: 'button', title: '回复' }, '回复');
        replyBtn.addEventListener('click', function () { toggleReplyForm(card, comment.id); });
        actions.appendChild(replyBtn);

        var editBtn = el('button', { type: 'button', title: '编辑批注' }, '编辑');
        editBtn.addEventListener('click', function () { toggleEditForm(card, comment); });
        actions.appendChild(editBtn);

        var resolveBtn = el('button', {
            type: 'button',
            className: 'cmt-action-resolve',
            'data-resolved': comment.status === 'resolved' ? 'true' : 'false',
            'aria-pressed': comment.status === 'resolved' ? 'true' : 'false',
            title: comment.status === 'open' ? '标记为已解决' : '重新打开'
        }, comment.status === 'open' ? '圈结' : '重开');
        resolveBtn.addEventListener('click', function () { toggleResolve(comment.id); });
        actions.appendChild(resolveBtn);

        var copyBtn = el('button', { type: 'button', title: '复制锚定原文' }, '复制原文');
        copyBtn.addEventListener('click', function () {
            if (comment.anchor && comment.anchor.exact) {
                copyToClipboard(comment.anchor.exact);
                showToast('已复制原文到剪贴板');
            }
        });
        actions.appendChild(copyBtn);

        var deleteBtn = el('button', { type: 'button', title: '删除批注' }, '删除');
        deleteBtn.addEventListener('click', function () { deleteComment(comment.id); });
        actions.appendChild(deleteBtn);

        card.appendChild(actions);

        // 回复表单（默认隐藏）
        var replyForm = createReplyForm(comment.id);
        card.appendChild(replyForm);

        return card;
    }

    /**
     * 创建回复表单
     */
    function createReplyForm(commentId) {
        var form = el('div', { className: 'cmt-reply-form', 'data-comment-id': commentId });
        var textarea = el('textarea', {
            placeholder: '写下回复…（Ctrl+Enter 提交）',
            'aria-label': '回复内容'
        });
        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitReply(commentId, textarea.value);
            }
        });
        form.appendChild(textarea);

        var actions = el('div', { className: 'cmt-reply-form-actions' });
        var cancelBtn = el('button', { type: 'button', className: 'cmt-reply-cancel' }, '取消');
        cancelBtn.addEventListener('click', function () { form.classList.remove('cmt-open'); });
        var submitBtn = el('button', { type: 'button', className: 'cmt-reply-submit' }, '回复');
        submitBtn.addEventListener('click', function () { submitReply(commentId, textarea.value); });
        actions.appendChild(cancelBtn);
        actions.appendChild(submitBtn);
        form.appendChild(actions);

        return form;
    }

    function toggleReplyForm(card, commentId) {
        var form = card.querySelector('.cmt-reply-form');
        if (!form) return;
        form.classList.toggle('cmt-open');
        if (form.classList.contains('cmt-open')) {
            var textarea = form.querySelector('textarea');
            if (textarea) textarea.focus();
        }
    }

    /**
     * 创建编辑表单（编辑评论内容 + 类型）
     */
    function createEditForm(comment) {
        var form = el('div', { className: 'cmt-edit-form', 'data-comment-id': comment.id });
        var textarea = el('textarea', {
            placeholder: '编辑批注内容…（Ctrl+Enter 保存）',
            'aria-label': '编辑批注内容'
        });
        textarea.value = comment.content || '';
        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitEdit(comment.id, textarea.value, form.querySelector('.cmt-edit-type-group'));
            }
        });
        form.appendChild(textarea);

        // 类型选择
        var typeGroup = el('div', { className: 'cmt-edit-type-group', role: 'radiogroup', 'aria-label': '批注类型' });
        Object.keys(COMMENT_TYPES).forEach(function (type) {
            var info = COMMENT_TYPES[type];
            var btn = el('button', {
                type: 'button',
                className: 'cmt-popover-type cmt-edit-type',
                role: 'radio',
                'aria-checked': type === comment.type ? 'true' : 'false',
                'data-type': type,
                style: '--cmtB-type-color: ' + info.color + ';'
            });
            var seal = el('span', { className: 'cmt-seal cmt-seal-' + type }, info.seal);
            btn.appendChild(seal);
            btn.appendChild(document.createTextNode(info.label));
            btn.addEventListener('click', function () {
                typeGroup.querySelectorAll('.cmt-edit-type').forEach(function (b) {
                    b.setAttribute('aria-checked', b.dataset.type === type ? 'true' : 'false');
                });
            });
            typeGroup.appendChild(btn);
        });
        form.appendChild(typeGroup);

        var actions = el('div', { className: 'cmt-reply-form-actions' });
        var cancelBtn = el('button', { type: 'button', className: 'cmt-reply-cancel' }, '取消');
        cancelBtn.addEventListener('click', function () { form.classList.remove('cmt-open'); });
        var submitBtn = el('button', { type: 'button', className: 'cmt-reply-submit' }, '保存');
        submitBtn.addEventListener('click', function () { submitEdit(comment.id, textarea.value, typeGroup); });
        actions.appendChild(cancelBtn);
        actions.appendChild(submitBtn);
        form.appendChild(actions);

        return form;
    }

    function toggleEditForm(card, comment) {
        var form = card.querySelector('.cmt-edit-form');
        if (!form) {
            form = createEditForm(comment);
            card.appendChild(form);
        }
        form.classList.toggle('cmt-open');
        if (form.classList.contains('cmt-open')) {
            var textarea = form.querySelector('textarea');
            if (textarea) { textarea.focus(); textarea.select(); }
        }
    }

    function submitEdit(commentId, newContent, typeGroup) {
        newContent = (newContent || '').trim();
        if (!newContent) {
            showToast('批注内容不能为空');
            return;
        }
        var newType = selectedType;
        if (typeGroup) {
            var checked = typeGroup.querySelector('.cmt-edit-type[aria-checked="true"]');
            if (checked) newType = checked.getAttribute('data-type');
        }
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        var typeChanged = comment.type !== newType;
        comment.content = newContent;
        comment.type = newType;
        comment.updatedAt = nowISO();
        Storage.saveComments(currentNotePath, comments);
        // 类型变更时同步高亮样式
        if (typeChanged) {
            updateHighlightType(commentId, newType);
        }
        renderPanel();
        showToast('已更新批注');
    }


    function submitReply(commentId, content) {
        content = content.trim();
        if (!content) return;
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        if (!comment.replies) comment.replies = [];
        comment.replies.push({
            id: generateId('r'),
            content: content,
            author: '作者',
            createdAt: nowISO()
        });
        comment.updatedAt = nowISO();
        Storage.saveComments(currentNotePath, comments);
        // 同步高亮 aria-label 的回复数
        updateHighlightAriaLabel(commentId, comment.type, comment.replies.length);
        renderPanel();
        showToast('已添加回复');
    }

    /* ========================================================
     * 十、评论操作
     * ======================================================== */

    function toggleResolve(commentId) {
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.status = comment.status === 'open' ? 'resolved' : 'open';
        comment.updatedAt = nowISO();
        if (comment.status === 'resolved') comment.resolvedAt = nowISO();
        Storage.saveComments(currentNotePath, comments);
        updateHighlightStatus(commentId, comment.status === 'resolved');
        renderPanel();
    }

    function deleteComment(commentId) {
        if (!confirm('确定删除此批注？删除后不可恢复。')) return;
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment) return;
        comment.deleted = true;
        Storage.saveComments(currentNotePath, comments);
        unwrapHighlight(commentId);
        renderPanel();
        showToast('已删除批注');
    }

    function jumpToComment(commentId) {
        var comments = Storage.loadComments(currentNotePath);
        var comment = comments.find(function (c) { return c.id === commentId; });
        if (!comment || !comment.anchor) {
            showToast('此批注无法定位原文');
            return;
        }
        var range = resolveAnchor(comment.anchor, currentContainer, normTextCache);
        if (!range) {
            showToast('原文已变更，无法定位');
            return;
        }
        // 滚动到高亮处
        var mark = currentContainer.querySelector('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
        if (mark) {
            mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
            flashHighlight(commentId);
        } else {
            // 高亮不存在，重新 wrap
            wrapRangeWithHighlight(range, commentId, comment.type);
            mark = currentContainer.querySelector('mark.cmt-highlight[data-cm-id="' + CSS.escape(commentId) + '"]');
            if (mark) {
                mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
                flashHighlight(commentId);
            }
        }
    }

    /* ========================================================
     * 十一、选区监听
     * ======================================================== */

    var debouncedSelectionChange = debounce(handleSelectionChange, 200);

    function handleSelectionEnd(e) {
        // 忽略浮层内的鼠标事件
        if (popoverEl && !popoverEl.hidden && popoverEl.contains(e.target)) return;
        var sel = window.getSelection();
        if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
            return;
        }
        var range = sel.getRangeAt(0);
        if (!currentContainer || !currentContainer.contains(range.commonAncestorContainer)) return;
        if (rangeIntersectsForbidden(range)) {
            showToast('标题、代码块暂不支持批注');
            return;
        }
        var anchor = captureAnchor(sel, currentNotePath);
        if (!anchor) return;
        showPopover(range, anchor);
    }

    function handleSelectionChange() {
        // 选区变化时暂不处理，由 mouseup 触发
    }

    function handleHighlightClick(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) return;
        var id = mark.getAttribute('data-cm-id');
        if (!id) return;
        // 滚动到批注栏对应卡片
        var card = threadListEl ? threadListEl.querySelector('.cmt-card[data-cm-id="' + CSS.escape(id) + '"]') : null;
        if (card) {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            card.classList.add('cmt-flash');
            setTimeout(function () { card.classList.remove('cmt-flash'); }, 600);
        } else {
            // 卡片不在当前视图（可能已解决被过滤），临时显示
            showResolved = true;
            var showResolvedCheckbox = document.getElementById('cmtShowResolved');
            if (showResolvedCheckbox) showResolvedCheckbox.checked = true;
            renderPanel();
            setTimeout(function () {
                card = threadListEl ? threadListEl.querySelector('.cmt-card[data-cm-id="' + CSS.escape(id) + '"]') : null;
                if (card) {
                    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    card.classList.add('cmt-flash');
                    setTimeout(function () { card.classList.remove('cmt-flash'); }, 600);
                }
            }, 100);
        }
    }

    function handleHighlightHover(e) {
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) {
            hideTooltip();
            return;
        }
        var id = mark.getAttribute('data-cm-id');
        if (!id) return;
        showTooltip(id, e.clientX, e.clientY);
    }

    function handleHighlightKey(e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var mark = e.target.closest('mark.cmt-highlight');
        if (!mark) return;
        e.preventDefault();
        handleHighlightClick(e);
    }

    /* ========================================================
     * 十二、导出 / 导入
     * ======================================================== */

    /**
     * 获取笔记全文（从 markdown-body 提取）
     */
    function getNoteContent() {
        if (!currentContainer) return '';
        return currentContainer.textContent || '';
    }

    /**
     * 导出单篇笔记批注
     */
    function exportNote(notePath) {
        var path = notePath || currentNotePath;
        if (!path) {
            showToast('请先选择一篇笔记');
            return;
        }
        var comments = Storage.loadComments(path).filter(function (c) { return !c.deleted; });
        var data = {
            schema: SCHEMA,
            exportedAt: nowISO(),
            exportedBy: '作者',
            scope: 'note',
            notePath: path,
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                agents: ALL_AGENTS
            },
            comments: comments
        };
        // 附带笔记全文
        if (path === currentNotePath) {
            data.noteContent = getNoteContent();
        }
        var filename = 'comments_' + path.replace(/[\/\\]/g, '_') + '_' + getDateStr() + '.json';
        downloadJSON(data, filename);

        // 更新元信息
        var meta = Storage.loadMeta();
        meta.lastExportAt = nowISO();
        Storage.saveMeta(meta);

        showToast('已导出 ' + comments.length + ' 条批注');
    }

    /**
     * 导出全站批注
     */
    function exportAll() {
        var allComments = Storage.loadAllComments();
        var notesArray = [];
        var totalCount = 0;
        for (var path in allComments) {
            if (!allComments.hasOwnProperty(path)) continue;
            var comments = allComments[path].filter(function (c) { return !c.deleted; });
            if (comments.length === 0) continue;
            notesArray.push({ notePath: path, comments: comments });
            totalCount += comments.length;
        }
        var data = {
            schema: SCHEMA,
            exportedAt: nowISO(),
            exportedBy: '作者',
            scope: 'all',
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                agents: ALL_AGENTS
            },
            notes: notesArray
        };
        downloadJSON(data, 'comments_all_' + getDateStr() + '.json');

        var meta = Storage.loadMeta();
        meta.lastExportAt = nowISO();
        Storage.saveMeta(meta);

        showToast('已导出 ' + totalCount + ' 条批注');
    }

    /**
     * 导出给专家团（AI 友好格式）
     */
    function exportForAgents(notePath) {
        var path = notePath || currentNotePath;
        if (!path) {
            showToast('请先选择一篇笔记');
            return;
        }
        var comments = Storage.loadComments(path).filter(function (c) { return !c.deleted; });
        if (comments.length === 0) {
            showToast('暂无批注可导出');
            return;
        }

        // 解析 book/chapter/event
        var parts = path.replace(/\.md$/, '').split(/[\/\\]/);
        var book = parts[0] || '';
        var chapter = parts.length > 1 ? parts[1] : '';
        var event = parts.length > 2 ? parts.slice(2).join('_') : '';

        // 按线程组织
        var threads = comments.map(function (c) {
            var typeInfo = COMMENT_TYPES[c.type] || {};
            var messages = [{
                id: c.id,
                author: c.author,
                type: c.type,
                content: c.content,
                createdAt: c.createdAt
            }];
            (c.replies || []).forEach(function (r) {
                messages.push({
                    id: r.id,
                    author: r.author,
                    type: 'comment',
                    content: r.content,
                    createdAt: r.createdAt
                });
            });
            return {
                threadId: c.id,
                anchor: c.anchor ? {
                    quote: c.anchor.exact,
                    rangeStart: c.anchor.rangeStart,
                    rangeEnd: c.anchor.rangeEnd,
                    paragraphIndex: c.anchor.paragraphIndex,
                    headingPath: c.anchor.headingPath
                } : null,
                status: c.status,
                tags: [],
                targetAgent: typeInfo.agent ? typeInfo.agent[0] : null,
                priority: c.type === 'error' ? 'high' : 'normal',
                messages: messages
            };
        });

        var data = {
            schema: SCHEMA,
            exportedAt: nowISO(),
            notePath: path,
            book: book,
            chapter: chapter,
            event: event,
            threads: threads
        };

        var filename = 'comments_' + book + '_' + chapter + '_' + event + '.json';
        downloadJSON(data, filename);
        showToast('已导出专家团评判包');
    }

    /**
     * 复制为 Prompt 上下文
     */
    function copyAsPromptContext(notePath) {
        var path = notePath || currentNotePath;
        if (!path) {
            showToast('请先选择一篇笔记');
            return;
        }
        var comments = Storage.loadComments(path).filter(function (c) { return !c.deleted; });
        if (comments.length === 0) {
            showToast('暂无批注可复制');
            return;
        }
        var lines = ['# 作者批注上下文', '笔记：' + path, ''];
        comments.forEach(function (c, i) {
            var typeInfo = COMMENT_TYPES[c.type] || {};
            lines.push('## 批注 ' + (i + 1) + ' [' + typeInfo.label + ']');
            if (c.anchor && c.anchor.exact) {
                lines.push('原文：「' + c.anchor.exact + '」');
            }
            lines.push('作者：' + c.content);
            (c.replies || []).forEach(function (r) {
                lines.push('回复：' + r.content);
            });
            lines.push('');
        });
        copyToClipboard(lines.join('\n'));
        showToast('已复制 ' + comments.length + ' 条批注到剪贴板');
    }

    /**
     * 导入 JSON
     */
    function importJSON(jsonStr, mode) {
        try {
            var data = JSON.parse(jsonStr);
        } catch (e) {
            showToast('JSON 解析失败：' + e.message);
            return false;
        }

        // 校验 schema
        if (!data.schema || data.schema !== SCHEMA) {
            showToast('schema 不符，期望 ' + SCHEMA);
            return false;
        }

        var importedComments = [];
        if (data.scope === 'all' && data.notes) {
            data.notes.forEach(function (n) {
                (n.comments || []).forEach(function (c) {
                    c.notePath = n.notePath;
                    importedComments.push(c);
                });
            });
        } else if (data.comments) {
            importedComments = data.comments;
        } else if (data.threads) {
            // 专家团导出格式
            data.threads.forEach(function (t) {
                if (t.messages && t.messages.length > 0) {
                    var msg = t.messages[0];
                    importedComments.push({
                        id: t.threadId || msg.id || generateId('c'),
                        notePath: data.notePath || currentNotePath,
                        anchor: t.anchor ? {
                            strategy: 'text+context',
                            exact: t.anchor.quote,
                            prefix: '',
                            suffix: '',
                            rangeStart: t.anchor.rangeStart || 0,
                            rangeEnd: t.anchor.rangeEnd || 0,
                            paragraphIndex: t.anchor.paragraphIndex || 0,
                            headingPath: t.anchor.headingPath || [],
                            version: '',
                            schemaVersion: 1
                        } : null,
                        content: msg.content,
                        type: msg.type || 'discussion',
                        author: msg.author || '作者',
                        createdAt: msg.createdAt || nowISO(),
                        updatedAt: msg.createdAt || nowISO(),
                        status: t.status || 'open',
                        replies: (t.messages || []).slice(1).map(function (m) {
                            return {
                                id: m.id || generateId('r'),
                                content: m.content,
                                author: m.author || '作者',
                                createdAt: m.createdAt || nowISO()
                            };
                        }),
                        expertReviews: [],
                        deleted: false
                    });
                }
            });
        }

        if (importedComments.length === 0) {
            showToast('未找到可导入的批注');
            return false;
        }

        // 校验字段
        var validComments = importedComments.filter(function (c) {
            return c.id && c.content && c.type && COMMENT_TYPES[c.type];
        });

        var skipped = importedComments.length - validComments.length;

        // 按笔记分组
        var byNote = {};
        validComments.forEach(function (c) {
            var np = c.notePath || currentNotePath;
            if (!byNote[np]) byNote[np] = [];
            byNote[np].push(c);
        });

        var totalImported = 0;
        var totalConflicts = 0;
        var overwriteAll = (mode === 'replace');
        var askOnce = true;

        for (var np in byNote) {
            if (!byNote.hasOwnProperty(np)) continue;
            var existing = mode === 'replace' ? [] : Storage.loadComments(np);
            var existingIds = {};
            existing.forEach(function (c) { existingIds[c.id] = c; });

            byNote[np].forEach(function (c) {
                if (existingIds[c.id] && existingIds[c.id] !== c) {
                    // 冲突：同 id 已存在
                    totalConflicts++;
                    if (!overwriteAll && askOnce) {
                        var choice = confirm('检测到 ' + totalConflicts + ' 条批注 ID 冲突。\n\n' +
                            '点击「确定」覆盖所有冲突批注；\n' +
                            '点击「取消」跳过冲突批注（保留原有）。');
                        if (choice) {
                            overwriteAll = true;
                            existingIds[c.id] = c;
                            totalImported++;
                        } else {
                            overwriteAll = true; // 不再询问，后续都跳过
                            askOnce = false;
                        }
                        return;
                    }
                    if (overwriteAll && askOnce === false) {
                        // 跳过模式
                        return;
                    }
                    if (overwriteAll) {
                        existingIds[c.id] = c;
                        totalImported++;
                    }
                } else {
                    existingIds[c.id] = c;
                    totalImported++;
                }
            });

            var merged = Object.keys(existingIds).map(function (k) { return existingIds[k]; });
            Storage.saveComments(np, merged);
        }

        // 刷新当前笔记
        if (currentNotePath) {
            refresh();
        }

        var msg = '已导入 ' + totalImported + ' 条';
        if (skipped > 0) msg += '，跳过 ' + skipped + ' 条无效';
        if (totalConflicts > 0 && totalImported < validComments.length) {
            msg += '，' + (validComments.length - totalImported) + ' 条冲突已跳过';
        }
        showToast(msg);
        return true;
    }

    /**
     * 导入专家评判结果
     */
    function importExpertReview(jsonStr) {
        try {
            var data = JSON.parse(jsonStr);
        } catch (e) {
            showToast('JSON 解析失败：' + e.message);
            return false;
        }
        if (!data.reviews || !Array.isArray(data.reviews)) {
            showToast('未找到 reviews 字段');
            return false;
        }
        var allComments = Storage.loadAllComments();
        var count = 0;
        data.reviews.forEach(function (review) {
            if (!review.commentId) return;
            // 在所有笔记中查找
            for (var np in allComments) {
                if (!allComments.hasOwnProperty(np)) continue;
                var comment = allComments[np].find(function (c) { return c.id === review.commentId; });
                if (comment) {
                    if (!comment.expertReviews) comment.expertReviews = [];
                    comment.expertReviews.push(review);
                    Storage.saveComments(np, allComments[np]);
                    count++;
                    break;
                }
            }
        });
        if (currentNotePath) refresh();
        showToast('已回填 ' + count + ' 条评判');
        return true;
    }

    /* ========================================================
     * 十三、专家团触发
     * ======================================================== */

    function openExpertDialog() {
        var comments = currentNotePath ? Storage.loadComments(currentNotePath).filter(function (c) { return !c.deleted; }) : [];
        if (comments.length === 0) {
            showToast('暂无批注可评判');
            return;
        }

        // 创建模态框
        var overlay = el('div', { className: 'modal-overlay open', id: 'cmtExpertOverlay', 'aria-hidden': 'false' });
        var modal = el('div', { className: 'modal cmt-expert-modal', role: 'dialog', 'aria-modal': 'true' });

        // 头部
        var header = el('div', { className: 'modal-header' });
        header.appendChild(el('h2', {}, '延请名家评判'));
        var closeBtn = el('button', { className: 'modal-close', type: 'button', 'aria-label': '关闭' }, '×');
        closeBtn.addEventListener('click', function () { overlay.remove(); });
        header.appendChild(closeBtn);
        modal.appendChild(header);

        // 正文
        var body = el('div', { className: 'modal-body' });

        // 范围
        body.appendChild(el('div', { className: 'form-group' }, [
            el('label', {}, '评判范围'),
            el('div', { className: 'cmt-radio-group' }, [
                (function () {
                    var l = el('label');
                    var r = el('input', { type: 'radio', name: 'expertScope', value: 'note', checked: '' });
                    l.appendChild(r);
                    l.appendChild(document.createTextNode('当前笔记'));
                    return l;
                })(),
                (function () {
                    var l = el('label');
                    var r = el('input', { type: 'radio', name: 'expertScope', value: 'all' });
                    l.appendChild(r);
                    l.appendChild(document.createTextNode('全站'));
                    return l;
                })()
            ])
        ]));

        // 参与专家
        var checkboxGroup = el('div', { className: 'cmt-checkbox-group' });
        ALL_AGENTS.forEach(function (agent, i) {
            var l = el('label');
            var cb = el('input', { type: 'checkbox', value: agent, checked: '' });
            l.appendChild(cb);
            l.appendChild(document.createTextNode(AGENT_LABELS[agent]));
            checkboxGroup.appendChild(l);
        });
        body.appendChild(el('div', { className: 'form-group' }, [
            el('label', {}, '参与专家'),
            checkboxGroup
        ]));

        // 附加指令
        body.appendChild(el('div', { className: 'form-group' }, [
            el('label', {}, '附加指令（可选）'),
            el('textarea', {
                id: 'expertInstruction',
                placeholder: '如：重点核查引文出处、评估讲道理部分是否过度引申…',
                style: 'width:100%;min-height:60px;padding:0.6rem 0.85rem;font-family:var(--font-sans);font-size:0.9rem;border:1px solid var(--border);border-radius:var(--radius);resize:vertical;'
            })
        ]));

        // 命令提示
        body.appendChild(el('div', { className: 'cmt-cmd-hint' },
            '生成后请在本地执行：\npython src/main.py --expert-review expert_review_request.json'));

        // 操作按钮
        var actions = el('div', { className: 'modal-actions' });
        var cancelBtn = el('button', { type: 'button', className: 'btn-secondary' }, '取消');
        cancelBtn.addEventListener('click', function () { overlay.remove(); });
        var confirmBtn = el('button', { type: 'button', className: 'btn-primary' }, '生成请求包');
        confirmBtn.addEventListener('click', function () {
            var scope = overlay.querySelector('input[name="expertScope"]:checked').value;
            var participants = Array.from(checkboxGroup.querySelectorAll('input:checked')).map(function (cb) { return cb.value; });
            var instruction = document.getElementById('expertInstruction').value.trim();
            generateExpertReviewRequest(scope, participants, instruction);
            overlay.remove();
        });
        actions.appendChild(cancelBtn);
        actions.appendChild(confirmBtn);
        body.appendChild(actions);

        modal.appendChild(body);
        overlay.appendChild(modal);
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) overlay.remove();
        });
        document.body.appendChild(overlay);
    }

    function generateExpertReviewRequest(scope, participants, instruction) {
        var notePath = currentNotePath;
        var comments = [];
        if (scope === 'note') {
            comments = Storage.loadComments(notePath).filter(function (c) { return !c.deleted; });
        } else {
            var all = Storage.loadAllComments();
            for (var np in all) {
                if (!all.hasOwnProperty(np)) continue;
                all[np].filter(function (c) { return !c.deleted; }).forEach(function (c) {
                    comments.push(c);
                });
            }
        }

        var parts = notePath ? notePath.replace(/\.md$/, '').split(/[\/\\]/) : [];
        var data = {
            schema: SCHEMA,
            exportedAt: nowISO(),
            exportedBy: '作者',
            scope: scope,
            notePath: scope === 'note' ? notePath : undefined,
            projectContext: {
                rulesFile: '.trae/rules/rules.md',
                notesDir: 'output/',
                agents: ALL_AGENTS
            },
            comments: comments,
            expertReviewRequest: {
                participants: participants,
                additionalInstruction: instruction,
                rulesReference: '.trae/rules/rules.md'
            }
        };

        var filename = 'expert_review_request.json';
        if (scope === 'note' && parts.length > 0) {
            filename = 'expert_review_request_' + parts.join('_') + '.json';
        }
        downloadJSON(data, filename);
        showToast('已生成专家团请求包，请下载后在本地执行');
    }

    /* ========================================================
     * 十四、主流程：attach / detach / refresh
     * ======================================================== */

    /**
     * 为指定容器初始化高亮 + 选区监听
     */
    function attach(container, notePath) {
        // 先卸载旧的
        detach();

        currentContainer = container;
        currentNotePath = notePath;
        normTextCache = null;

        // 检测 localStorage
        storageAvailable = Storage.checkAvailable();

        // 确保面板可见
        ensurePanel();

        // 渲染已存高亮
        renderExistingHighlights();

        // 渲染批注栏
        renderPanel();

        // 绑定选区监听
        container.addEventListener('mouseup', handleSelectionEnd);
        container.addEventListener('touchend', handleSelectionEnd);
        container.addEventListener('click', handleHighlightClick);
        container.addEventListener('mouseover', handleHighlightHover);
        container.addEventListener('mouseout', function () { hideTooltip(); });
        container.addEventListener('keydown', handleHighlightKey);
        document.addEventListener('selectionchange', debouncedSelectionChange);

        // 绑定面板事件（只绑一次）
        bindPanelEvents();
    }

    /**
     * 卸载当前笔记的监听
     */
    function detach() {
        if (currentContainer) {
            currentContainer.removeEventListener('mouseup', handleSelectionEnd);
            currentContainer.removeEventListener('touchend', handleSelectionEnd);
            currentContainer.removeEventListener('click', handleHighlightClick);
            currentContainer.removeEventListener('mouseover', handleHighlightHover);
            currentContainer.removeEventListener('keydown', handleHighlightKey);
        }
        document.removeEventListener('selectionchange', debouncedSelectionChange);
        hidePopover();
        hideTooltip();
        currentContainer = null;
        currentNotePath = null;
        normTextCache = null;
    }

    /**
     * 重新渲染当前笔记的高亮
     */
    function refresh() {
        if (!currentContainer || !currentNotePath) return;
        // 移除所有现有高亮
        var marks = currentContainer.querySelectorAll('mark.cmt-highlight');
        marks.forEach(function (mark) {
            var parent = mark.parentNode;
            if (!parent) return;
            while (mark.firstChild) {
                parent.insertBefore(mark.firstChild, mark);
            }
            parent.removeChild(mark);
            parent.normalize();
        });
        // 重新渲染
        renderExistingHighlights();
        renderPanel();
    }

    /**
     * 渲染已存评论的高亮
     */
    function renderExistingHighlights() {
        if (!currentContainer || !currentNotePath) return;
        var comments = Storage.loadComments(currentNotePath).filter(function (c) { return !c.deleted && c.anchor; });

        // 构建一次规范化文本缓存，所有 resolveAnchor 复用
        var builtCache = buildNormalizedText(currentContainer);
        normTextCache = builtCache;

        // 按 rangeStart 降序排列（从后往前 wrap，避免偏移影响）
        comments.sort(function (a, b) {
            return (b.anchor.rangeStart || 0) - (a.anchor.rangeStart || 0);
        });

        var orphanChanged = false;
        comments.forEach(function (comment) {
            var wasOrphan = comment.anchor && comment.anchor._orphan;
            if (comment.anchor) delete comment.anchor._orphan;
            var range = resolveAnchor(comment.anchor, currentContainer, builtCache);
            if (range) {
                var replyCount = (comment.replies || []).length;
                wrapRangeWithHighlight(range, comment.id, comment.type, replyCount);
                if (comment.status === 'resolved') {
                    updateHighlightStatus(comment.id, true);
                }
            } else {
                // 孤儿批注
                if (comment.anchor) comment.anchor._orphan = true;
            }
            var isOrphan = comment.anchor && comment.anchor._orphan;
            if (wasOrphan !== isOrphan) orphanChanged = true;
        });

        // 孤儿状态变化时持久化（含从孤儿恢复为正常的情况）
        if (orphanChanged) {
            Storage.saveComments(currentNotePath, comments);
        }
    }

    /* ========================================================
     * 十五、面板事件绑定
     * ======================================================== */

    var panelEventsBound = false;

    function bindPanelEvents() {
        if (panelEventsBound) return;
        panelEventsBound = true;

        // 排序
        var sortRadios = document.querySelectorAll('input[name="cmtSort"]');
        sortRadios.forEach(function (radio) {
            radio.addEventListener('change', function () {
                if (radio.checked) {
                    sortBy = radio.value;
                    renderPanel();
                }
            });
        });

        // 显示已解决
        var showResolvedCheckbox = document.getElementById('cmtShowResolved');
        if (showResolvedCheckbox) {
            showResolvedCheckbox.addEventListener('change', function () {
                showResolved = showResolvedCheckbox.checked;
                renderPanel();
            });
        }

        // 面板操作按钮
        var exportNoteBtn = document.getElementById('cmtExportNote');
        if (exportNoteBtn) exportNoteBtn.addEventListener('click', function () { exportNote(); });

        var exportAllBtn = document.getElementById('cmtExportAll');
        if (exportAllBtn) exportAllBtn.addEventListener('click', function () { exportAll(); });

        var exportAgentsBtn = document.getElementById('cmtExportAgents');
        if (exportAgentsBtn) exportAgentsBtn.addEventListener('click', function () { exportForAgents(); });

        var copyPromptBtn = document.getElementById('cmtCopyPrompt');
        if (copyPromptBtn) copyPromptBtn.addEventListener('click', function () { copyAsPromptContext(); });

        // 导入
        var importBtn = document.getElementById('cmtImport');
        fileInputEl = document.getElementById('cmtFileInput');
        if (importBtn && fileInputEl) {
            importBtn.addEventListener('click', function () {
                fileImportMode = 'merge';
                fileInputEl.click();
            });
            fileInputEl.addEventListener('change', function (e) {
                var file = e.target.files[0];
                if (!file) return;
                var reader = new FileReader();
                reader.onload = function (ev) {
                    importJSON(ev.target.result, fileImportMode);
                };
                reader.readAsText(file);
                fileInputEl.value = '';
            });
        }

        // 导入评判
        var importReviewBtn = document.getElementById('cmtImportReview');
        if (importReviewBtn && fileInputEl) {
            importReviewBtn.addEventListener('click', function () {
                fileInputEl.accept = '.json,application/json';
                fileInputEl.onchange = function (e) {
                    var file = e.target.files[0];
                    if (!file) return;
                    var reader = new FileReader();
                    reader.onload = function (ev) {
                        importExpertReview(ev.target.result);
                    };
                    reader.readAsText(file);
                    fileInputEl.value = '';
                };
                fileInputEl.click();
            });
        }

        // 工具栏按钮
        var toolbarExportBtn = document.getElementById('cmtExportBtn');
        if (toolbarExportBtn) {
            toolbarExportBtn.addEventListener('click', function () { exportNote(); });
        }

        var toolbarExpertBtn = document.getElementById('cmtExpertBtn');
        if (toolbarExpertBtn) {
            toolbarExpertBtn.addEventListener('click', function () { openExpertDialog(); });
        }

        // 多标签页同步
        window.addEventListener('storage', function (e) {
            if (e.key && e.key.indexOf(STORAGE_PREFIX) === 0) {
                if (currentNotePath && e.key === STORAGE_PREFIX + currentNotePath) {
                    refresh();
                }
            }
        });
    }

    /* ========================================================
     * 十六、辅助函数
     * ======================================================== */

    function getDateStr() {
        var d = new Date();
        var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
        return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate());
    }

    function copyToClipboard(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(function () {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
        } catch (e) {}
        document.body.removeChild(textarea);
    }

    /* ========================================================
     * 十七、事件监听 & API 暴露
     * ======================================================== */

    // 监听 note:loaded 事件
    document.addEventListener('note:loaded', function (e) {
        var detail = e.detail || {};
        var notePath = detail.notePath;
        var container = detail.container;
        if (notePath && container) {
            attach(container, notePath);
        }
    });

    // 全局 Esc 关闭浮层
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && popoverEl && !popoverEl.hidden) {
            hidePopover();
        }
    });

    // 暴露 API
    window.DeepReadingComments = {
        /** 兼容 spec 8.6 的 init 接口 */
        init: function (readerEl) {
            // 无需额外初始化，事件监听已在 IIFE 中注册
        },

        /** 兼容 spec 8.6 的 loadForNote 接口 */
        loadForNote: function (notePath) {
            if (!notePath) return;
            var container = document.querySelector('.markdown-body');
            if (container) {
                attach(container, notePath);
            }
        },

        /** 兼容 spec 8.6 的 clear 接口 */
        clear: function () {
            detach();
        },

        // 显式控制
        attach: attach,
        detach: detach,
        refresh: refresh,

        // 状态查询
        getComments: function (notePath) {
            return Storage.loadComments(notePath).filter(function (c) { return !c.deleted; });
        },
        getAllComments: function () {
            return Storage.loadAllComments();
        },

        // 数据操作
        exportNote: exportNote,
        exportAll: exportAll,
        exportForAgents: exportForAgents,
        copyAsPromptContext: copyAsPromptContext,
        importJSON: function (jsonStr, mode) {
            return importJSON(jsonStr, mode || 'merge');
        },
        importExpertReview: importExpertReview,
        clearNote: function (notePath) {
            Storage.deleteNote(notePath);
            if (notePath === currentNotePath) refresh();
        },

        // 专家团
        generateExpertReviewRequest: generateExpertReviewRequest,
        openExpertDialog: openExpertDialog
    };

})();
