/**
 * 阅读器三个增强功能测试（壁纸 / 翻页 / 自动阅读）
 * 基于 jsdom + 本地 fetch mock，验证：
 *   1. 壁纸切换：6 种预设、透明度、夜间覆盖、localStorage 持久化
 *   2. 翻页：tap 模式分区翻页、排除可交互元素、scroll 模式不翻页
 *   3. 自动阅读：播放/暂停、到末尾暂停、切章暂停、rAF 调用
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');
const { TextEncoder, TextDecoder } = require('util');

global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

const SITE_DIR = path.resolve(__dirname, '../site');
const INDEX_JSON = JSON.parse(fs.readFileSync(path.join(SITE_DIR, 'data/index.json'), 'utf-8'));
const SEARCH_JSON = JSON.parse(fs.readFileSync(path.join(SITE_DIR, 'data/search-index.json'), 'utf-8'));

function readNote(relPath) {
    return fs.readFileSync(path.join(SITE_DIR, 'notes', relPath), 'utf-8');
}

let passCount = 0;
let failCount = 0;
function assert(cond, msg) {
    if (cond) {
        passCount++;
        console.log('  ✅', msg);
    } else {
        failCount++;
        console.error('  ❌', msg);
    }
}

function waitFor(fn, timeout) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const timer = setInterval(() => {
            try {
                if (fn()) { clearInterval(timer); resolve(); return; }
            } catch (e) { clearInterval(timer); reject(e); return; }
            if (Date.now() - start > timeout) { clearInterval(timer); reject(new Error('等待超时')); }
        }, 20);
    });
}

async function buildDom() {
    let html = fs.readFileSync(path.join(SITE_DIR, 'index.html'), 'utf-8');
    // index.html 已自带 <script src="js/app.js" defer>，测试时手动注入单实例，
    // 避免 jsdom 把外部脚本也加载进来导致 app.js 双实例、事件监听器重复注册。
    html = html.replace(/<script[^>]*src="js\/app\.js"[^>]*>\s*<\/script>/, '');
    const dom = new JSDOM(html, {
        url: 'http://localhost:8080/',
        runScripts: 'dangerously',
        resources: 'usable',
        pretendToBeVisual: true,
        storageQuota: 100 * 1024 * 1024,
    });
    const { window } = dom;
    const { document } = window;

    // fetch mock
    window.fetch = async (url) => {
        const u = new URL(url, window.location.href);
        const pathname = u.pathname.replace(/^\/HaloRead\//, '/');
        let body; let contentType = 'application/json';
        if (pathname.endsWith('/data/index.json')) body = JSON.stringify(INDEX_JSON);
        else if (pathname.endsWith('/data/search-index.json')) body = JSON.stringify(SEARCH_JSON);
        else if (pathname.includes('/notes/') && pathname.endsWith('.md')) {
            contentType = 'text/markdown';
            body = readNote(decodeURI(pathname.replace(/^.*\/notes\//, '')));
        } else throw new Error('未 mock 的请求: ' + url);
        return Promise.resolve({
            ok: true, status: 200,
            headers: { get: (n) => n.toLowerCase() === 'content-type' ? contentType : null },
            json: async () => JSON.parse(body), text: async () => body,
            clone: function () { return this; }
        });
    };

    window.CSS = window.CSS || { escape: (s) => String(s).replace(/"/g, '\\"') };
    window.marked = require('marked');

    // rAF polyfill：用 setTimeout 模拟，可控推进
    window.__rafQueue = [];
    window.requestAnimationFrame = (cb) => {
        const id = window.__rafQueue.length + 1;
        window.__rafQueue.push({ id, cb });
        return id;
    };
    window.cancelAnimationFrame = (id) => {
        window.__rafQueue = window.__rafQueue.filter((r) => r.id !== id);
    };
    window.__flushRaf = (ts) => {
        const queue = window.__rafQueue.slice();
        window.__rafQueue = [];
        queue.forEach((r) => r.cb(ts || 16));
    };

    // matchMedia polyfill
    window.matchMedia = window.matchMedia || ((q) => ({
        matches: false, media: q, addListener() {}, removeListener() {},
        addEventListener() {}, removeEventListener() {},
    }));

    // IntersectionObserver polyfill（jsdom 不实现，bindScrollSpy 渲染书架时依赖）
    if (!window.IntersectionObserver) {
        window.IntersectionObserver = class {
            constructor(cb) { this.cb = cb; this.els = []; }
            observe(el) { this.els.push(el); }
            unobserve() {}
            disconnect() { this.els = []; }
            takeRecords() { return []; }
        };
    }

    // CSS.escape polyfill（jsdom 部分版本缺失，loadNote 高亮路径用到）
    if (!window.CSS) window.CSS = {};
    if (!window.CSS.escape) window.CSS.escape = (s) => String(s).replace(/[^a-zA-Z0-9_\u4e00-\u9fa5\-]/g, (c) => '\\' + c);

    // 注入 app.js
    const appCode = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
    const appScript = document.createElement('script');
    appScript.textContent = appCode;
    document.head.appendChild(appScript);

    return { dom, window, document };
}

async function enterReader(document, window) {
    await waitFor(() => document.querySelectorAll('.bookshelf-grid .book-card').length > 0, 5000);
    const card = document.querySelector('.bookshelf-grid .book-card');
    card.click();
    await waitFor(() => document.querySelectorAll('.reader-view .tree-leaf').length > 0, 5000);
    const leaf = document.querySelector('.reader-view .tree-leaf');
    leaf.click();
    await waitFor(() => document.querySelector('.markdown-body'), 5000);
}

async function runTest() {
    console.log('\n=== 测试1：壁纸切换 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const wallpapers = ['none', 'bamboo', 'landscape'];
        for (const wp of wallpapers) {
            const btn = document.querySelector(`#wallpaperBtns button[data-wallpaper="${wp}"]`);
            assert(btn !== null, `壁纸按钮 ${wp} 存在`);
            btn.click();
            assert(document.body.getAttribute('data-wallpaper') === wp, `壁纸 ${wp} 切换生效`);
            assert(btn.classList.contains('active'), `壁纸 ${wp} 按钮高亮`);
        }

        // 已删除的壁纸按钮不应存在
        assert(document.querySelector('#wallpaperBtns button[data-wallpaper="xuan"]') === null, '宣纸壁纸按钮已删除');
        assert(document.querySelector('#wallpaperBtns button[data-wallpaper="ink"]') === null, '水墨壁纸按钮已删除');
        assert(document.querySelector('#wallpaperBtns button[data-wallpaper="starry"]') === null, '星空壁纸按钮已删除');

        // 透明度滑块
        const opacityRange = document.getElementById('wallpaperOpacityRange');
        opacityRange.value = '0.8';
        opacityRange.dispatchEvent(new window.Event('input', { bubbles: true }));
        const opacityVar = document.documentElement.style.getPropertyValue('--reader-wallpaper-opacity');
        assert(opacityVar === '0.8', '壁纸透明度变量写入 (0.8)');

        // localStorage 持久化
        const stored = JSON.parse(window.localStorage.getItem('reader-settings'));
        assert(stored.wallpaper === 'landscape', '壁纸持久化到 localStorage');
        assert(stored.wallpaperOpacity === 0.8, '透明度持久化到 localStorage');

        // 夜间主题覆盖：data-theme=night + data-wallpaper=bamboo 时壁纸变量应被覆盖
        document.body.setAttribute('data-theme', 'night');
        document.body.setAttribute('data-wallpaper', 'bamboo');
        // 这里只能验证属性已设置（CSS 解析在 jsdom 不完整），验证规则存在性
        const cssText = fs.readFileSync(path.join(SITE_DIR, 'css/style.css'), 'utf-8');
        assert(cssText.includes('body[data-theme="night"][data-wallpaper="bamboo"]'), '夜间主题 + 壁纸覆盖规则存在');

        dom.window.close();
    }

    console.log('\n=== 测试2：翻页模式 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        // 默认 pageMode=tap
        assert(document.body.getAttribute('data-page-mode') === 'tap', '默认翻页模式为 tap');

        // 切换到 scroll
        const scrollBtn = document.querySelector('#pageModeBtns button[data-page-mode="scroll"]');
        scrollBtn.click();
        assert(document.body.getAttribute('data-page-mode') === 'scroll', '切换到 scroll 模式');
        assert(scrollBtn.classList.contains('active'), 'scroll 模式按钮高亮');

        // 切回 tap
        const tapBtn = document.querySelector('#pageModeBtns button[data-page-mode="tap"]');
        tapBtn.click();
        assert(document.body.getAttribute('data-page-mode') === 'tap', '切回 tap 模式');

        // localStorage 持久化
        const stored = JSON.parse(window.localStorage.getItem('reader-settings'));
        assert(stored.pageMode === 'tap', '翻页模式持久化');

        dom.window.close();
    }

    console.log('\n=== 测试3：翻页点击分区（移动端模拟） ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        // 模拟移动端宽度
        Object.defineProperty(window, 'innerWidth', { value: 400, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'getBoundingClientRect', {
            value: () => ({ left: 0, top: 0, width: 400, height: 800 }),
            configurable: true
        });

        let scrollByCalls = [];
        reader.scrollBy = (opts) => { scrollByCalls.push(opts); };

        // 点击右侧 25% → 下一屏
        const mdBody = document.querySelector('.markdown-body');
        const clickRight = new window.MouseEvent('click', { bubbles: true, clientX: 360, clientY: 400 });
        Object.defineProperty(clickRight, 'target', { value: mdBody, configurable: true });
        reader.dispatchEvent(clickRight);
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollByCalls.length === 1 && scrollByCalls[0].top > 0, '点击右侧 25% 触发下一屏');

        // 点击左侧 25% → 上一屏
        scrollByCalls = [];
        const clickLeft = new window.MouseEvent('click', { bubbles: true, clientX: 40, clientY: 400 });
        Object.defineProperty(clickLeft, 'target', { value: mdBody, configurable: true });
        reader.dispatchEvent(clickLeft);
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollByCalls.length === 1 && scrollByCalls[0].top < 0, '点击左侧 25% 触发上一屏');

        // 点击中间 50% → 切换 ui-hidden
        scrollByCalls = [];
        const uiBefore = document.body.classList.contains('ui-hidden');
        const clickMid = new window.MouseEvent('click', { bubbles: true, clientX: 200, clientY: 400 });
        Object.defineProperty(clickMid, 'target', { value: mdBody, configurable: true });
        reader.dispatchEvent(clickMid);
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollByCalls.length === 0, '点击中间 50% 不翻页');
        assert(document.body.classList.contains('ui-hidden') !== uiBefore, '点击中间 50% 切换 ui-hidden');

        dom.window.close();
    }

    console.log('\n=== 测试4：翻页排除可交互元素 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        Object.defineProperty(window, 'innerWidth', { value: 400, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'getBoundingClientRect', {
            value: () => ({ left: 0, top: 0, width: 400, height: 800 }),
            configurable: true
        });
        let scrollByCalls = [];
        reader.scrollBy = (opts) => { scrollByCalls.push(opts); };

        // 在 markdown-body 内插入链接和按钮
        const mdBody = document.querySelector('.markdown-body');
        const link = document.createElement('a');
        link.href = '#';
        link.textContent = '链接';
        mdBody.appendChild(link);
        const btn = document.createElement('button');
        btn.textContent = '按钮';
        mdBody.appendChild(btn);

        // 点击链接不翻页
        const clickLink = new window.MouseEvent('click', { bubbles: true, clientX: 360, clientY: 400 });
        Object.defineProperty(clickLink, 'target', { value: link, configurable: true });
        reader.dispatchEvent(clickLink);
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollByCalls.length === 0, '点击链接不翻页');

        // 点击按钮不翻页
        const clickBtn = new window.MouseEvent('click', { bubbles: true, clientX: 360, clientY: 400 });
        Object.defineProperty(clickBtn, 'target', { value: btn, configurable: true });
        reader.dispatchEvent(clickBtn);
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollByCalls.length === 0, '点击按钮不翻页');

        // 设置面板打开时不翻页
        document.getElementById('settingsPanel').classList.add('open');
        const clickOpen = new window.MouseEvent('click', { bubbles: true, clientX: 360, clientY: 400 });
        Object.defineProperty(clickOpen, 'target', { value: mdBody, configurable: true });
        reader.dispatchEvent(clickOpen);
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollByCalls.length === 0, '设置面板打开时不翻页');

        dom.window.close();
    }

    console.log('\n=== 测试5：自动阅读播放/暂停（设置面板开关） ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const onBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="true"]');
        const offBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="false"]');
        assert(onBtn !== null, '设置面板存在自动阅读「开启」按钮');
        assert(offBtn !== null, '设置面板存在自动阅读「关闭」按钮');
        assert(document.getElementById('autoScrollBtn') === null, '右下角浮动自动阅读按钮已删除');
        assert(offBtn.classList.contains('active'), '初始状态「关闭」高亮');

        // 模拟可滚动内容
        Object.defineProperty(reader, 'scrollHeight', { value: 5000, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'scrollTop', { value: 0, configurable: true });
        let scrollByCalls = [];
        reader.scrollBy = (x, y) => {
            if (typeof x === 'number' && typeof y === 'number') {
                // 旧式调用 reader.scrollBy(0, dy)
                reader.scrollTop = (reader.scrollTop || 0) + y;
                scrollByCalls.push(y);
            }
        };

        // 点击开启
        onBtn.click();
        assert(onBtn.classList.contains('active'), '开启后「开启」按钮高亮');
        assert(!offBtn.classList.contains('active'), '开启后「关闭」按钮不高亮');
        assert(window.__rafQueue.length > 0, 'rAF 已调度');

        // 推进足够多帧以触发整数累积器产出多次 scrollBy（BUG-042：亚像素 dy 累积到 >=1px 才滚动）
        // 默认速度 50 行/分，lineHeight≈28px → 每帧 dy≈0.37px，约每 3 帧触发 1 次整数滚动
        for (let i = 0; i < 30; i++) {
            window.__flushRaf(16 * (i + 1));
        }
        assert(scrollByCalls.length >= 4, `rAF 推进 30 帧后 scrollBy 调用 ${scrollByCalls.length} 次 (>=4，整数累积模式)`);
        assert(scrollByCalls.every((y) => y >= 1), '所有 scrollBy dy 为 >=1 的整数（亚像素累积修复 BUG-042）');

        // localStorage 持久化
        let stored = JSON.parse(window.localStorage.getItem('reader-settings'));
        assert(stored.autoScroll === true, '自动阅读开启状态持久化');

        // 点击关闭
        offBtn.click();
        assert(offBtn.classList.contains('active'), '关闭后「关闭」按钮高亮');
        assert(!onBtn.classList.contains('active'), '关闭后「开启」按钮不高亮');

        // localStorage 持久化
        stored = JSON.parse(window.localStorage.getItem('reader-settings'));
        assert(stored.autoScroll === false, '自动阅读关闭状态持久化');

        dom.window.close();
    }

    console.log('\n=== 测试6：自动阅读到末尾暂停 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const onBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="true"]');
        const offBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="false"]');
        // 接近末尾：scrollHeight - scrollTop - clientHeight < 2
        Object.defineProperty(reader, 'scrollHeight', { value: 1000, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'scrollTop', { value: 999, configurable: true });
        reader.scrollBy = () => {};

        onBtn.click();
        assert(onBtn.classList.contains('active'), '点击开启后高亮');
        // 推进一帧，应检测到末尾并暂停
        window.__flushRaf(16);
        assert(offBtn.classList.contains('active'), '到末尾自动暂停');
        assert(!onBtn.classList.contains('active'), '到末尾后开启按钮不高亮');

        dom.window.close();
    }

    console.log('\n=== 测试7：切章/呼出设置时自动暂停 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const onBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="true"]');
        const offBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="false"]');
        Object.defineProperty(reader, 'scrollHeight', { value: 5000, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'scrollTop', { value: 0, configurable: true });
        reader.scrollBy = () => {};

        // 播放
        onBtn.click();
        assert(onBtn.classList.contains('active'), '播放中');
        window.__flushRaf(16);

        // 点击设置按钮（呼出设置面板）应暂停
        document.getElementById('settingsBtn').click();
        assert(offBtn.classList.contains('active'), '呼出设置面板后自动暂停');
        assert(!onBtn.classList.contains('active'), '呼出设置面板后开启按钮不高亮');

        dom.window.close();
    }

    console.log('\n=== 测试8：DEFAULT_SETTINGS 含所有新字段 ===');
    {
        const cssText = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
        assert(cssText.includes('wallpaper:'), 'DEFAULT_SETTINGS 含 wallpaper');
        assert(cssText.includes('wallpaperOpacity:'), 'DEFAULT_SETTINGS 含 wallpaperOpacity');
        assert(cssText.includes('pageMode:'), 'DEFAULT_SETTINGS 含 pageMode');
        assert(cssText.includes('autoScroll:'), 'DEFAULT_SETTINGS 含 autoScroll');
        assert(cssText.includes('autoScrollSpeed:'), 'DEFAULT_SETTINGS 含 autoScrollSpeed');
        assert(cssText.includes('handleReaderTap'), '含 handleReaderTap 统一入口');
        assert(!cssText.includes('function initTapToggle'), '已移除旧 initTapToggle');
        assert(cssText.includes('requestAnimationFrame'), '自动阅读使用 rAF');
    }

    console.log('\n=== 测试9：CSS 壁纸层与夜间覆盖 ===');
    {
        const cssText = fs.readFileSync(path.join(SITE_DIR, 'css/style.css'), 'utf-8');
        assert(cssText.includes('.reader-wallpaper'), '含 .reader-wallpaper 壁纸层');
        assert(cssText.includes('pointer-events: none'), '壁纸层 pointer-events: none');
        assert(cssText.includes('--reader-wallpaper'), '含 --reader-wallpaper 变量');
        assert(cssText.includes('body[data-wallpaper="bamboo"]'), '含竹简壁纸预设');
        assert(cssText.includes('body[data-wallpaper="landscape"]'), '含山水壁纸预设');
        assert(!cssText.includes('body[data-wallpaper="starry"]'), '星空壁纸预设已删除');
        assert(!cssText.includes('body[data-wallpaper="ink"]'), '水墨壁纸预设已删除');
        assert(!cssText.includes('body[data-wallpaper="xuan"]'), '宣纸壁纸预设已删除');
        assert(cssText.includes('body[data-theme="night"][data-wallpaper="bamboo"]'), '含夜间竹简覆盖');
        assert(!cssText.includes('.auto-scroll-btn'), '浮动自动阅读按钮样式已删除');
    }

    console.log('\n=== 测试10：沉浸阅读模式（回归测试） ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const immersiveBtn = document.getElementById('immersiveBtn');
        assert(immersiveBtn !== null, '沉浸按钮存在于 DOM');
        assert(immersiveBtn.hidden === false, '阅读视图下沉浸按钮可见（非 hidden）');
        assert(immersiveBtn.getAttribute('aria-pressed') === 'false', '初始状态未激活');

        // 点击进入沉浸
        immersiveBtn.click();
        assert(document.body.classList.contains('immersive-mode'), '点击后 body 含 immersive-mode');
        assert(document.body.classList.contains('ui-hidden'), '沉浸时隐藏 UI 工具栏');
        assert(immersiveBtn.getAttribute('aria-pressed') === 'true', '按钮 aria-pressed=true');
        assert(immersiveBtn.textContent.includes('退出'), '按钮文案变为退出');

        // 再次点击退出沉浸
        immersiveBtn.click();
        assert(!document.body.classList.contains('immersive-mode'), '再次点击移除 immersive-mode');
        assert(immersiveBtn.getAttribute('aria-pressed') === 'false', '按钮 aria-pressed=false');
        assert(immersiveBtn.textContent.includes('沉浸'), '按钮文案恢复为沉浸');

        dom.window.close();
    }

    console.log('\n=== 测试11：沉浸模式调用 Fullscreen API 但不锁定方向，小米浏览器跳过（BUG-036） ===');
    {
        const appText = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
        // BUG-021 教训修正：重新引入 Fullscreen API 实现"整屏全屏"（隐藏浏览器地址栏/操作栏），
        // 但必须满足三个安全约束：
        //   1. 不调用 screen.orientation.lock / lockOrientation（强制横屏根因）
        //   2. 小米浏览器 UA 识别跳过 Fullscreen API（小米 requestFullscreen 会强制横屏）
        //   3. Fullscreen 失败时 fallback 到纯 CSS 沉浸（body.immersive-mode + ui-hidden）
        assert(!/screen\.orientation\.lock/.test(appText), '不调用 screen.orientation.lock');
        assert(!/lockOrientation/.test(appText), '不调用旧版 lockOrientation');
        // BUG-036：重新引入 Fullscreen API（与 BUG-021 不同，此处允许调用）
        assert(/requestFullscreen|webkitRequestFullscreen/.test(appText), '调用 requestFullscreen 系列实现整屏全屏');
        assert(/exitFullscreen|webkitExitFullscreen/.test(appText), '调用 exitFullscreen 系列退出整屏全屏');
        // 小米 UA 跳过是关键回归约束（防止 BUG-021 强制横屏重现）
        assert(/isXiaomiBrowser/.test(appText), '含 isXiaomiBrowser 检测函数');
        assert(/MiuiBrowser/.test(appText), '小米浏览器 UA 识别使用 MiuiBrowser 关键字');
        assert(appText.includes('toggleImmersiveMode'), '含 toggleImmersiveMode 函数');
        assert(appText.includes('enterImmersiveMode'), '含 enterImmersiveMode 函数');
        assert(appText.includes('exitImmersiveMode'), '含 exitImmersiveMode 函数');
        assert(appText.includes('initImmersive'), 'init 中调用 initImmersive');

        const cssText = fs.readFileSync(path.join(SITE_DIR, 'css/style.css'), 'utf-8');
        assert(cssText.includes('body.immersive-mode'), 'CSS 含 body.immersive-mode 规则');
        // 沉浸模式下 UI 隐藏需同时满足 .immersive-mode + .ui-hidden，
        // 这样点击中央区域可唤出工具栏/目录，再点隐藏，仿番茄阅读交互。
        assert(cssText.includes('.immersive-mode.ui-hidden .toolbar'), '沉浸+ui-hidden 时隐藏 toolbar');
        assert(cssText.includes('.immersive-mode.ui-hidden .bottom-bar'), '沉浸+ui-hidden 时隐藏 bottom-bar');
    }

    console.log('\n=== 测试12：返回首页退出沉浸模式 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const immersiveBtn = document.getElementById('immersiveBtn');
        immersiveBtn.click();
        assert(document.body.classList.contains('immersive-mode'), '进入沉浸');

        // 点击返回按钮回到首页
        const backBtn = document.getElementById('backBtn');
        backBtn.click();
        assert(!document.body.classList.contains('immersive-mode'), '返回首页后退出沉浸模式');
        assert(immersiveBtn.hidden === true, '返回首页后沉浸按钮隐藏');

        dom.window.close();
    }

    console.log('\n=== 测试13：非法壁纸设置回退到无 ===');
    {
        const { dom, window, document } = await buildDom();
        // 先写入旧的非法壁纸
        window.localStorage.setItem('reader-settings', JSON.stringify({ wallpaper: 'starry' }));
        // 重新触发 loadSettings / applySettings：需要重新进入阅读视图
        await enterReader(document, window);
        assert(document.body.getAttribute('data-wallpaper') === 'none', 'body 壁纸属性为 none');
        // 触发一次设置保存（applySettings 读取后已规范化，但需保存才持久化）
        document.querySelector('#wallpaperBtns button[data-wallpaper="none"]').click();
        const stored = JSON.parse(window.localStorage.getItem('reader-settings'));
        assert(stored.wallpaper === 'none', '非法壁纸 starry 被规范为 none');
        dom.window.close();
    }

    console.log('\n=== 测试14：壁纸层高度跟随阅读内容 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        Object.defineProperty(reader, 'scrollHeight', { value: 3500, configurable: true });
        // 切换壁纸触发 updateReaderWallpaperHeight
        document.querySelector('#wallpaperBtns button[data-wallpaper="landscape"]').click();
        const wallpaper = reader.querySelector('.reader-wallpaper');
        assert(wallpaper !== null, '阅读区存在壁纸层');
        assert(wallpaper.style.height === '3500px', '壁纸层高度等于 reader.scrollHeight');

        dom.window.close();
    }

    console.log('\n=== 测试15：代码块移动端自动换行且点击不翻页 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const article = reader.querySelector('.markdown-body');
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.textContent = 'const veryLongLine = "a".repeat(200);';
        pre.appendChild(code);
        article.appendChild(pre);

        // 点击 code 元素不应触发 UI 切换
        const clickEvent = new window.MouseEvent('click', { bubbles: true, clientX: 150, clientY: 300 });
        Object.defineProperty(clickEvent, 'target', { value: code, enumerable: true });
        code.dispatchEvent(clickEvent);

        // 验证 CSS 代码块自动换行
        const cssText = fs.readFileSync(path.join(SITE_DIR, 'css/style.css'), 'utf-8');
        const appText = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
        assert(cssText.includes('.markdown-body pre code'), '含 .markdown-body pre code 规则');
        assert(cssText.includes('white-space: pre-wrap'), '代码块 white-space 为 pre-wrap');
        assert(/word-wrap:\s*break-word|overflow-wrap:\s*break-word/.test(cssText), '代码块允许换行断词');
        assert(appText.includes("pre, code"), 'shouldExcludeTap 排除 pre/code');

        dom.window.close();
    }

    console.log('\n=== 测试16：pageshow persisted 时重置视图状态 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const immersiveBtn = document.getElementById('immersiveBtn');
        immersiveBtn.click();
        assert(document.body.classList.contains('immersive-mode'), '已进入沉浸');

        // 模拟从 bfcache 恢复
        const pageshowEvent = new window.Event('pageshow', { bubbles: false });
        Object.defineProperty(pageshowEvent, 'persisted', { value: true });
        window.dispatchEvent(pageshowEvent);

        assert(!document.body.classList.contains('immersive-mode'), 'pageshow 后退出沉浸');
        assert(!document.body.classList.contains('ui-hidden'), 'pageshow 后移除 ui-hidden');
        assert(document.body.dataset.view === 'home', 'pageshow 后回到 home 视图');

        dom.window.close();
    }

    console.log('\n=== 测试17：返回书架时关闭目录蒙层（回归测试） ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        // 打开目录抽屉（移动端目录按钮同样会触发 openSidebar）
        document.getElementById('tocBtnBottom').click();
        assert(document.getElementById('sidebarOverlay').classList.contains('open'), '点击目录按钮后 sidebarOverlay 打开');

        // 点击返回书架
        document.getElementById('backBtn').click();
        assert(!document.getElementById('sidebarOverlay').classList.contains('open'), '返回书架后 sidebarOverlay 关闭');
        assert(document.body.dataset.view === 'home', '返回书架后回到 home 视图');

        dom.window.close();
    }

    console.log('\n=== 测试18：首页“阅读”按钮跳转书架区（回归测试） ===');
    {
        const { dom, window, document } = await buildDom();
        await waitFor(() => document.querySelectorAll('.bookshelf-grid .book-card').length > 0, 5000);

        const newNoteBtn = document.getElementById('newNoteBtn');
        const bookshelf = document.getElementById('bookshelf');
        assert(newNoteBtn !== null, '首页存在 newNoteBtn（开始阅读/阅读）按钮');
        assert(bookshelf !== null, '首页存在 #bookshelf 锚点');

        let scrollIntoViewCalled = false;
        bookshelf.scrollIntoView = (opts) => {
            scrollIntoViewCalled = true;
        };

        newNoteBtn.click();
        await new Promise((r) => setTimeout(r, 10));
        assert(scrollIntoViewCalled, '点击“阅读”按钮后滚动到书架区');

        dom.window.close();
    }

    console.log('\n=== 测试19：离线下载入口与 DOM 结构 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        // 设置面板内含离线下载入口
        const offlineExportBtn = document.getElementById('offlineExportBtn');
        assert(offlineExportBtn !== null, '设置面板内存在 #offlineExportBtn 按钮');
        assert(offlineExportBtn.textContent.includes('导出'), '按钮文案含「导出」');

        // 导出 modal 骨架
        const exportOverlay = document.getElementById('exportOverlay');
        const exportTree = document.getElementById('exportTree');
        const exportConfirmBtn = document.getElementById('exportConfirmBtn');
        const exportSelectAllBtn = document.getElementById('exportSelectAllBtn');
        const exportClearBtn = document.getElementById('exportClearBtn');
        const exportCounter = document.getElementById('exportCounter');
        const exportProgress = document.getElementById('exportProgress');
        assert(exportOverlay !== null, '存在 #exportOverlay');
        assert(exportTree !== null, '存在 #exportTree');
        assert(exportConfirmBtn !== null, '存在 #exportConfirmBtn');
        assert(exportSelectAllBtn !== null, '存在 #exportSelectAllBtn');
        assert(exportClearBtn !== null, '存在 #exportClearBtn');
        assert(exportCounter !== null, '存在 #exportCounter');
        assert(exportProgress !== null, '存在 #exportProgress');
        assert(!exportOverlay.classList.contains('open'), '初始 modal 未打开');
        assert(exportConfirmBtn.disabled === true, '初始导出按钮 disabled（未选笔记）');

        // 点击入口打开 modal
        offlineExportBtn.click();
        assert(exportOverlay.classList.contains('open'), '点击入口后 modal 打开');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);
        const noteCbs = exportTree.querySelectorAll('.export-checkbox-note');
        assert(noteCbs.length > 0, '已打开书籍时复选树渲染出笔记条目');
        assert(exportCounter.textContent.includes('已选 0 篇'), '初始计数为 0');

        dom.window.close();
    }

    console.log('\n=== 测试20：离线下载不调用危险系统 API（防横屏回归，BUG-021/036） ===');
    {
        const appText = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
        // BUG-021 教训：移动端阅读器不得调用 orientation.lock（强制横屏根因）
        // BUG-036 修正：允许 Fullscreen API（用于在线沉浸整屏全屏），但必须有小米 UA 跳过护栏
        assert(!/screen\.orientation\.lock/.test(appText), '导出代码不调用 screen.orientation.lock');
        assert(!/lockOrientation/.test(appText), '导出代码不调用 lockOrientation');
        // Fullscreen API 已在 BUG-036 重新引入，此处不再禁止，改由测试11 验证三重护栏
        assert(/isXiaomiBrowser/.test(appText), '含 isXiaomiBrowser 检测（小米 UA 跳过 Fullscreen）');
        assert(/MiuiBrowser/.test(appText), '小米浏览器 UA 识别使用 MiuiBrowser 关键字');
        // 导出只允许用 Blob + a[download] 触发下载
        assert(appText.includes('new Blob('), '使用 Blob 构造下载内容');
        assert(appText.includes('URL.createObjectURL'), '使用 URL.createObjectURL 生成下载链接');
        assert(/a\.download\s*=/.test(appText), '使用 a.download 触发文件下载');
        // 必须含并发限流，避免一次拉几十个文件压垮浏览器
        assert(appText.includes('EXPORT_CONCURRENCY'), '导出含并发限流常量 EXPORT_CONCURRENCY');
        // 必须含标题降级函数
        assert(appText.includes('function downgradeHeadings'), '含 downgradeHeadings 函数');
    }

    console.log('\n=== 测试21：单章/多章/全本选择与计数联动 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        document.getElementById('offlineExportBtn').click();
        const exportTree = document.getElementById('exportTree');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);
        const noteCbs = Array.from(exportTree.querySelectorAll('.export-checkbox-note'));
        const totalNotes = noteCbs.length;
        assert(totalNotes > 0, '本书至少有 1 篇笔记可选');

        // 单章：勾选第一个笔记
        noteCbs[0].checked = true;
        noteCbs[0].dispatchEvent(new window.Event('change', { bubbles: true }));
        assert(document.getElementById('exportCounter').textContent === '已选 1 篇', '勾选 1 篇后计数为 1');
        assert(document.getElementById('exportConfirmBtn').disabled === false, '勾选后导出按钮启用');

        // 清空
        document.getElementById('exportClearBtn').click();
        assert(document.getElementById('exportCounter').textContent === `已选 0 篇`, '清空后计数归 0');
        assert(document.getElementById('exportConfirmBtn').disabled === true, '清空后导出按钮 disabled');
        assert(noteCbs.every((cb) => cb.checked === false), '清空后所有笔记复选框未选中');

        // 全选
        document.getElementById('exportSelectAllBtn').click();
        assert(document.getElementById('exportCounter').textContent === `已选 ${totalNotes} 篇`, `全选后计数为 ${totalNotes}`);
        assert(noteCbs.every((cb) => cb.checked === true), '全选后所有笔记复选框选中');

        // 多章：取消第一个，保留其余
        noteCbs[0].checked = false;
        noteCbs[0].dispatchEvent(new window.Event('change', { bubbles: true }));
        assert(document.getElementById('exportCounter').textContent === `已选 ${totalNotes - 1} 篇`, `取消首篇后计数为 ${totalNotes - 1}`);

        dom.window.close();
    }

    console.log('\n=== 测试22：导出 Markdown 三级标题层级与正文标题降级 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        // 拦截下载：把 Blob 内容存到 captured，阻止真实下载
        let captured = null;
        const origBlob = window.Blob;
        window.Blob = function (parts, opts) {
            captured = { content: parts.join(''), type: opts && opts.type };
            return { size: captured.content.length, type: captured.type };
        };
        window.URL.createObjectURL = () => 'blob:fake';
        window.URL.revokeObjectURL = () => {};
        // 阻止 a.click 真实触发导航
        const origCreateElement = document.createElement.bind(document);
        document.createElement = function (tag) {
            const el = origCreateElement(tag);
            if (tag.toLowerCase() === 'a') {
                el.click = () => {};
            }
            return el;
        };

        document.getElementById('offlineExportBtn').click();
        const exportTree = document.getElementById('exportTree');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);
        const noteCbs = Array.from(exportTree.querySelectorAll('.export-checkbox-note'));

        // 只选前 2 篇做单章+多章混合验证
        const pickCount = Math.min(2, noteCbs.length);
        for (let i = 0; i < pickCount; i++) {
            noteCbs[i].checked = true;
            noteCbs[i].dispatchEvent(new window.Event('change', { bubbles: true }));
        }

        document.getElementById('exportConfirmBtn').click();
        await waitFor(() => captured !== null, 3000);

        assert(captured !== null, '导出触发并捕获到 Blob 内容');
        assert(captured.type === 'text/markdown;charset=utf-8', 'Blob 类型为 markdown');

        const md = captured.content;
        // 第一行必须是书名 H1
        assert(/^# .+/.test(md.split('\n')[0]), '文档首行为书名 H1');
        // 含目录段
        assert(md.includes('## 目录'), '文档含「## 目录」段');
        // 含可点击目录条目
        assert(/\- \[.+\]\(#.+\)/.test(md), '目录含可点击锚点条目');
        // 章节用 H2
        assert(/^## .+/m.test(md), '文档含章节 H2');
        // 笔记标题用 H3 + 锚点
        assert(/<a id="[^"]+"><\/a>\n### .+/m.test(md), '笔记标题为 H3 且前置锚点');
        // 三级层级唯一：所有 ### 必须紧跟在 <a id> 后（正文 H3 已降级）
        const h3Lines = md.split('\n').filter((l) => /^###\s/.test(l));
        const anchoredH3 = md.split('\n').filter((l, i, arr) => /^###\s/.test(l) && i > 0 && /<a id="[^"]+"><\/a>/.test(arr[i - 1]));
        assert(h3Lines.length === anchoredH3.length, `所有 H3 均为笔记标题（共 ${h3Lines.length} 个，全部前置锚点），正文 H3 已降级`);

        // 关键：TOC 锚点与正文锚点必须一一对应（防 slugify 双调用 bug 回归）
        const tocAnchors = [...md.matchAll(/^\- \[.+?\]\(#([^)]+)\)/gm)].map((m) => m[1]);
        const bodyAnchors = [...md.matchAll(/<a id="([^"]+)"><\/a>/g)].map((m) => m[1]);
        assert(tocAnchors.length === bodyAnchors.length, `TOC 锚点数(${tocAnchors.length}) === 正文锚点数(${bodyAnchors.length})`);
        assert(tocAnchors.every((a, i) => a === bodyAnchors[i]), 'TOC 锚点与正文锚点一一对应且顺序一致（防 slugify 双调用 bug）');

        // 还原
        window.Blob = origBlob;
        document.createElement = origCreateElement;
        dom.window.close();
    }

    console.log('\n=== 测试23：downgradeHeadings 代码块内 # 不被误降级 ===');
    {
        // 通过端到端验证：构造一篇含代码块的笔记，导出后检查代码块内 # 注释保持原样
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        let captured = null;
        const origBlob = window.Blob;
        window.Blob = function (parts, opts) {
            captured = { content: parts.join(''), type: opts && opts.type };
            return { size: captured.content.length, type: captured.type };
        };
        window.URL.createObjectURL = () => 'blob:fake';
        window.URL.revokeObjectURL = () => {};
        const origCreateElement = document.createElement.bind(document);
        document.createElement = function (tag) {
            const el = origCreateElement(tag);
            if (tag.toLowerCase() === 'a') el.click = () => {};
            return el;
        };

        // 拦截 fetch，给第一篇笔记注入含代码块的正文
        const origFetch = window.fetch;
        window.fetch = async (url) => {
            const u = new URL(url, window.location.href);
            const pathname = u.pathname.replace(/^\/HaloRead\//, '/');
            if (pathname.includes('/notes/') && pathname.endsWith('.md')) {
                const relPath = decodeURI(pathname.replace(/^.*\/notes\//, ''));
                // 只对第一篇笔记注入代码块测试内容
                const firstLeaf = document.querySelector('.reader-view .tree-leaf');
                if (firstLeaf && relPath === firstLeaf.dataset.path) {
                    const body = '正文标题测试\n\n## 二级标题\n\n### 三级标题\n\n```python\n# 这是代码注释，不应被降级\nx = 1\n```\n\n```\n---\n```\n\n正文末尾。';
                    return Promise.resolve({
                        ok: true, status: 200,
                        headers: { get: (n) => n.toLowerCase() === 'content-type' ? 'text/markdown' : null },
                        json: async () => body, text: async () => body,
                        clone: function () { return this; }
                    });
                }
                const fs = require('fs');
                const body = fs.readFileSync(path.join(SITE_DIR, 'notes', relPath), 'utf-8');
                return Promise.resolve({
                    ok: true, status: 200,
                    headers: { get: (n) => n.toLowerCase() === 'content-type' ? 'text/markdown' : null },
                    json: async () => body, text: async () => body,
                    clone: function () { return this; }
                });
            }
            return origFetch(url);
        };

        document.getElementById('offlineExportBtn').click();
        const exportTree = document.getElementById('exportTree');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);
        const noteCbs = Array.from(exportTree.querySelectorAll('.export-checkbox-note'));
        // 只选第一篇（注入了代码块的）
        noteCbs[0].checked = true;
        noteCbs[0].dispatchEvent(new window.Event('change', { bubbles: true }));

        document.getElementById('exportConfirmBtn').click();
        await waitFor(() => captured !== null, 3000);

        const md = captured.content;
        // 代码块内的 # 注释保持原样
        assert(md.includes('# 这是代码注释，不应被降级'), '代码块内 # 注释未被降级');
        assert(!md.includes('#### 这是代码注释'), '代码块内 # 未被误转为 H4');
        // 正文标题被降级
        assert(/####\s+二级标题/.test(md), '正文 H2 降级为 H4');
        assert(/#####\s+三级标题/.test(md), '正文 H3 降级为 H5');
        // 围栏代码块内的 --- 不被误转为 Setext
        assert(md.includes('```\n---\n```'), '代码块内 --- 未被误转为 Setext H2');

        window.Blob = origBlob;
        document.createElement = origCreateElement;
        window.fetch = origFetch;
        dom.window.close();
    }

    console.log('\n=== 测试24：导出中 UI 状态机（防重入/不可关闭/进度推进） ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        let capturedCount = 0;
        const origBlob = window.Blob;
        window.Blob = function (parts, opts) {
            capturedCount++;
            return { size: parts.join('').length, type: opts && opts.type };
        };
        window.URL.createObjectURL = () => 'blob:fake';
        window.URL.revokeObjectURL = () => {};
        const origCreateElement = document.createElement.bind(document);
        document.createElement = function (tag) {
            const el = origCreateElement(tag);
            if (tag.toLowerCase() === 'a') el.click = () => {};
            return el;
        };

        document.getElementById('offlineExportBtn').click();
        const exportTree = document.getElementById('exportTree');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);
        const noteCbs = Array.from(exportTree.querySelectorAll('.export-checkbox-note'));
        noteCbs[0].checked = true;
        noteCbs[0].dispatchEvent(new window.Event('change', { bubbles: true }));

        const confirmBtn = document.getElementById('exportConfirmBtn');
        const cancelBtn = document.getElementById('exportCancelBtn');
        const closeBtn = document.getElementById('exportClose');
        const selectAllBtn = document.getElementById('exportSelectAllBtn');

        // 用 fetch gate 阻塞 performExport 在 fetchAllWithConcurrency 阶段，
        // 这样能稳定观察"导出中"状态（mock fetch 太快会一气呵成跳过中间态）
        let fetchGateResolve;
        const fetchGate = new Promise((r) => { fetchGateResolve = r; });
        const origFetch = window.fetch;
        window.fetch = async (url) => {
            const u = new URL(url, window.location.href);
            if (u.pathname.includes('/notes/') && u.pathname.endsWith('.md')) {
                await fetchGate;
            }
            return origFetch(url);
        };

        // 触发导出
        confirmBtn.click();
        // 让 performExport 推进到 fetchAllWithConcurrency 的 await fetch 处
        await new Promise((r) => setTimeout(r, 30));
        assert(confirmBtn.disabled === true, '导出中确认按钮 disabled');
        assert(selectAllBtn.disabled === true, '导出中全选按钮 disabled');
        assert(cancelBtn.textContent === '关闭', '导出中取消按钮文案为「关闭」');

        // 导出中点击关闭/取消/遮罩不应关闭 modal
        closeBtn.click();
        assert(document.getElementById('exportOverlay').classList.contains('open'), '导出中点击关闭按钮不关闭 modal');
        cancelBtn.click();
        assert(document.getElementById('exportOverlay').classList.contains('open'), '导出中点击取消按钮不关闭 modal');

        // 释放 gate，让导出完成
        fetchGateResolve();
        await waitFor(() => capturedCount > 0, 3000);
        await new Promise((r) => setTimeout(r, 100));
        // 完成后：取消文案恢复，确认按钮恢复（仍有选中则 enabled）
        assert(cancelBtn.textContent === '取消', '完成后取消按钮文案恢复「取消」');
        assert(selectAllBtn.disabled === false, '完成后全选按钮恢复 enabled');
        assert(capturedCount === 1, `仅触发一次下载（防重入，actual=${capturedCount})`);

        // 完成后可关闭
        closeBtn.click();
        assert(!document.getElementById('exportOverlay').classList.contains('open'), '完成后可关闭 modal');

        window.fetch = origFetch;

        window.Blob = origBlob;
        document.createElement = origCreateElement;
        dom.window.close();
    }

    console.log('\n=== 测试25：单篇 fetch 失败不阻断整体导出 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        let captured = null;
        const origBlob = window.Blob;
        window.Blob = function (parts, opts) {
            captured = { content: parts.join(''), type: opts && opts.type };
            return { size: captured.content.length, type: captured.type };
        };
        window.URL.createObjectURL = () => 'blob:fake';
        window.URL.revokeObjectURL = () => {};
        const origCreateElement = document.createElement.bind(document);
        document.createElement = function (tag) {
            const el = origCreateElement(tag);
            if (tag.toLowerCase() === 'a') el.click = () => {};
            return el;
        };

        // 拦截 fetch：第二篇笔记抛错
        const origFetch = window.fetch;
        let failedPath = null;
        window.fetch = async (url) => {
            const u = new URL(url, window.location.href);
            const pathname = u.pathname.replace(/^\/HaloRead\//, '/');
            if (pathname.includes('/notes/') && pathname.endsWith('.md')) {
                const relPath = decodeURI(pathname.replace(/^.*\/notes\//, ''));
                const noteCbs = Array.from(document.querySelectorAll('.export-checkbox-note'));
                if (noteCbs.length >= 2 && relPath === noteCbs[1].dataset.path) {
                    failedPath = relPath;
                    throw new Error('模拟网络错误');
                }
                const fs = require('fs');
                const body = fs.readFileSync(path.join(SITE_DIR, 'notes', relPath), 'utf-8');
                return Promise.resolve({
                    ok: true, status: 200,
                    headers: { get: (n) => n.toLowerCase() === 'content-type' ? 'text/markdown' : null },
                    json: async () => body, text: async () => body,
                    clone: function () { return this; }
                });
            }
            return origFetch(url);
        };

        document.getElementById('offlineExportBtn').click();
        const exportTree = document.getElementById('exportTree');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);
        const noteCbs = Array.from(exportTree.querySelectorAll('.export-checkbox-note'));
        // 选前 2 篇（第二篇会失败）
        noteCbs[0].checked = true;
        noteCbs[0].dispatchEvent(new window.Event('change', { bubbles: true }));
        noteCbs[1].checked = true;
        noteCbs[1].dispatchEvent(new window.Event('change', { bubbles: true }));

        document.getElementById('exportConfirmBtn').click();
        await waitFor(() => captured !== null, 3000);

        assert(captured !== null, '单篇失败仍完成整体导出');
        assert(failedPath !== null, '确实触发了失败分支');
        // 失败占位用引用块而非 H1，不污染大纲
        assert(captured.content.includes('⚠️ 本篇笔记加载失败'), '失败占位含错误提示');
        assert(!/^# 加载失败/m.test(captured.content), '失败占位不用 H1（不污染大纲）');
        // 失败笔记仍出现在 TOC（标题来自 tree，不依赖 fetch）
        const tocAnchors = [...captured.content.matchAll(/^\- \[.+?\]\(#([^)]+)\)/gm)].map((m) => m[1]);
        assert(tocAnchors.length === 2, `TOC 仍含 2 篇笔记（actual=${tocAnchors.length}）`);

        window.Blob = origBlob;
        document.createElement = origCreateElement;
        window.fetch = origFetch;
        dom.window.close();
    }

    console.log('\n=== 测试26：章节级复选框联动与 indeterminate 半选态 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        document.getElementById('offlineExportBtn').click();
        const exportTree = document.getElementById('exportTree');
        await waitFor(() => exportTree.querySelectorAll('.export-checkbox-note').length > 0, 5000);

        const chapterCbs = Array.from(exportTree.querySelectorAll('.export-checkbox-chapter'));
        assert(chapterCbs.length > 0, '存在章节级复选框');

        const firstChapterCb = chapterCbs[0];
        const firstChapterLi = firstChapterCb.closest('.export-node');
        const noteCbsInChapter = firstChapterLi.querySelectorAll('.export-checkbox-note');
        const notesCount = noteCbsInChapter.length;
        assert(notesCount > 0, '首章节有笔记');

        // 勾选章节 → 自动勾选其下所有笔记
        firstChapterCb.checked = true;
        firstChapterCb.dispatchEvent(new window.Event('change', { bubbles: true }));
        assert(Array.from(noteCbsInChapter).every((cb) => cb.checked), '勾选章节后其下所有笔记被勾选');
        assert(document.getElementById('exportCounter').textContent === `已选 ${notesCount} 篇`, `章节勾选后计数为 ${notesCount}`);

        // 取消一个笔记 → 章节变为 indeterminate
        if (notesCount >= 2) {
            noteCbsInChapter[0].checked = false;
            noteCbsInChapter[0].dispatchEvent(new window.Event('change', { bubbles: true }));
            assert(firstChapterCb.indeterminate === true, '部分取消后章节复选框为 indeterminate');
            assert(firstChapterCb.checked === false, '部分取消后章节复选框 checked=false');
        }

        // 再勾选剩余 → 章节恢复 checked
        if (notesCount >= 2) {
            noteCbsInChapter[0].checked = true;
            noteCbsInChapter[0].dispatchEvent(new window.Event('change', { bubbles: true }));
            assert(firstChapterCb.indeterminate === false, '全选后章节 indeterminate=false');
            assert(firstChapterCb.checked === true, '全选后章节 checked=true');
        }

        dom.window.close();
    }

    console.log('\n=== 测试27：Escape 键关闭导出 modal + 未开书时禁用态 ===');
    {
        const { dom, window, document } = await buildDom();
        // 等 init 完成（书架渲染）后再点击，确保 initOfflineExport 已绑定事件
        await waitFor(() => document.querySelectorAll('.bookshelf-grid .book-card').length > 0, 5000);

        // 未开书时打开导出 modal
        const offlineExportBtn = document.getElementById('offlineExportBtn');
        offlineExportBtn.click();
        const exportOverlay = document.getElementById('exportOverlay');
        assert(exportOverlay.classList.contains('open'), '未开书时 modal 仍可打开');
        assert(document.getElementById('exportConfirmBtn').disabled === true, '未开书时导出按钮 disabled');
        assert(document.getElementById('exportSelectAllBtn').disabled === true, '未开书时全选按钮 disabled');
        assert(document.getElementById('exportBookTip').textContent.includes('打开一本书'), '未开书时提示「打开一本书」');

        // Escape 键关闭导出 modal
        document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        assert(!exportOverlay.classList.contains('open'), 'Escape 键关闭导出 modal');

        dom.window.close();
    }

    console.log('\n=== 测试28：自动阅读速度调节生效（BUG-042 回归测试） ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const onBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="true"]');
        const offBtn = document.querySelector('#autoScrollBtns button[data-auto-scroll="false"]');
        const speedRange = document.getElementById('autoScrollSpeedRange');

        // 足够长的内容，确保不会触发到末尾暂停
        Object.defineProperty(reader, 'scrollHeight', { value: 50000, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'scrollTop', { value: 0, configurable: true });

        // 统计总滚动像素
        let totalScrolled = 0;
        reader.scrollBy = (x, y) => {
            if (typeof x === 'number' && typeof y === 'number') {
                reader.scrollTop = (reader.scrollTop || 0) + y;
                totalScrolled += y;
            }
        };

        // 辅助：以指定速度跑 N 帧并返回总滚动像素
        function runAtSpeed(speed, frames) {
            speedRange.value = String(speed);
            speedRange.dispatchEvent(new window.Event('input', { bubbles: true }));
            // 重置阅读器位置与统计
            Object.defineProperty(reader, 'scrollTop', { value: 0, configurable: true });
            totalScrolled = 0;
            onBtn.click();
            // 清空可能残留的 rAF 队列（startAutoScroll 会新调度一个）
            window.__rafQueue = window.__rafQueue || [];
            for (let i = 0; i < frames; i++) {
                window.__flushRaf(16 * (i + 1));
            }
            const scrolled = totalScrolled;
            offBtn.click();
            return scrolled;
        }

        // 慢速 24 行/分 vs 快速 100 行/分，各跑 60 帧（~960ms）
        const slowTotal = runAtSpeed(24, 60);
        const fastTotal = runAtSpeed(100, 60);

        assert(slowTotal > 0, `慢速(24)有滚动距离 ${slowTotal}px (>0)`);
        assert(fastTotal > 0, `快速(100)有滚动距离 ${fastTotal}px (>0)`);
        assert(fastTotal > slowTotal, `快速滚动距离 ${fastTotal}px > 慢速 ${slowTotal}px（速度调节生效，BUG-042）`);
        // 100/24 ≈ 4.17，宽松断言快速至少是慢速的 2 倍（避免环境抖动误报）
        assert(fastTotal >= slowTotal * 2, `快速 ${fastTotal}px >= 慢速 ${slowTotal}px 的 2 倍（速度差异显著）`);

        dom.window.close();
    }

    console.log(`\n=== 测试结果：通过 ${passCount}，失败 ${failCount} ===`);
    if (failCount > 0) {
        process.exit(1);
    }
}

runTest().catch((err) => {
    console.error('❌ 测试执行出错:', err);
    process.exit(1);
});
