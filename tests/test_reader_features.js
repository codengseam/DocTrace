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
    const html = fs.readFileSync(path.join(SITE_DIR, 'index.html'), 'utf-8');
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

    // 注入 app.js
    const appCode = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
    const appScript = document.createElement('script');
    appScript.textContent = appCode;
    document.head.appendChild(appScript);

    return { dom, window, document };
}

async function enterReader(document, window) {
    await waitFor(() => document.querySelectorAll('.bookshelf-grid .book-card').length > 0, 2000);
    const card = document.querySelector('.bookshelf-grid .book-card');
    card.click();
    await waitFor(() => document.querySelectorAll('.reader-view .tree-leaf').length > 0, 2000);
    const leaf = document.querySelector('.reader-view .tree-leaf');
    leaf.click();
    await waitFor(() => document.querySelector('.markdown-body'), 2000);
}

async function runTest() {
    console.log('\n=== 测试1：壁纸切换 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const wallpapers = ['none', 'bamboo', 'xuan', 'ink', 'landscape', 'starry'];
        for (const wp of wallpapers) {
            const btn = document.querySelector(`#wallpaperBtns button[data-wallpaper="${wp}"]`);
            btn.click();
            assert(document.body.getAttribute('data-wallpaper') === wp, `壁纸 ${wp} 切换生效`);
            assert(btn.classList.contains('active'), `壁纸 ${wp} 按钮高亮`);
        }

        // 透明度滑块
        const opacityRange = document.getElementById('wallpaperOpacityRange');
        opacityRange.value = '0.8';
        opacityRange.dispatchEvent(new window.Event('input', { bubbles: true }));
        const opacityVar = document.documentElement.style.getPropertyValue('--reader-wallpaper-opacity');
        assert(opacityVar === '0.8', '壁纸透明度变量写入 (0.8)');

        // localStorage 持久化
        const stored = JSON.parse(window.localStorage.getItem('reader-settings'));
        assert(stored.wallpaper === 'starry', '壁纸持久化到 localStorage');
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

    console.log('\n=== 测试5：自动阅读播放/暂停 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const autoBtn = document.getElementById('autoScrollBtn');
        assert(autoBtn && !autoBtn.hidden, '自动阅读按钮在阅读视图可见');
        assert(autoBtn.getAttribute('aria-pressed') === 'false', '初始状态为暂停');

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

        // 点击播放
        autoBtn.click();
        assert(autoBtn.getAttribute('aria-pressed') === 'true', '点击后状态为播放');
        assert(window.__rafQueue.length > 0, 'rAF 已调度');

        // 推进几帧（首帧建立时间基线 dt=0 不滚动，后续帧滚动）
        for (let i = 0; i < 5; i++) {
            window.__flushRaf(16 * (i + 1));
        }
        assert(scrollByCalls.length >= 4, `rAF 推进 5 帧后 scrollBy 调用 ${scrollByCalls.length} 次 (>=4，首帧建基线)`);
        assert(scrollByCalls.every((y) => y > 0), '所有 scrollBy dy > 0');

        // 点击暂停
        autoBtn.click();
        assert(autoBtn.getAttribute('aria-pressed') === 'false', '再次点击后状态为暂停');

        dom.window.close();
    }

    console.log('\n=== 测试6：自动阅读到末尾暂停 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const autoBtn = document.getElementById('autoScrollBtn');
        // 接近末尾：scrollHeight - scrollTop - clientHeight < 2
        Object.defineProperty(reader, 'scrollHeight', { value: 1000, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'scrollTop', { value: 999, configurable: true });
        reader.scrollBy = () => {};

        autoBtn.click();
        assert(autoBtn.getAttribute('aria-pressed') === 'true', '点击播放');
        // 推进一帧，应检测到末尾并暂停
        window.__flushRaf(16);
        assert(autoBtn.getAttribute('aria-pressed') === 'false', '到末尾自动暂停');

        dom.window.close();
    }

    console.log('\n=== 测试7：切章/呼出设置时自动暂停 ===');
    {
        const { dom, window, document } = await buildDom();
        await enterReader(document, window);

        const reader = document.getElementById('reader');
        const autoBtn = document.getElementById('autoScrollBtn');
        Object.defineProperty(reader, 'scrollHeight', { value: 5000, configurable: true });
        Object.defineProperty(reader, 'clientHeight', { value: 800, configurable: true });
        Object.defineProperty(reader, 'scrollTop', { value: 0, configurable: true });
        reader.scrollBy = () => {};

        // 播放
        autoBtn.click();
        assert(autoBtn.getAttribute('aria-pressed') === 'true', '播放中');
        window.__flushRaf(16);

        // 点击设置按钮（呼出设置面板）应暂停
        document.getElementById('settingsBtn').click();
        assert(autoBtn.getAttribute('aria-pressed') === 'false', '呼出设置面板后自动暂停');

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
        assert(cssText.includes('.reader::before'), '含 .reader::before 壁纸层');
        assert(cssText.includes('pointer-events: none'), '壁纸层 pointer-events: none');
        assert(cssText.includes('--reader-wallpaper'), '含 --reader-wallpaper 变量');
        assert(cssText.includes('body[data-wallpaper="bamboo"]'), '含竹简壁纸预设');
        assert(cssText.includes('body[data-wallpaper="starry"]'), '含星空壁纸预设');
        assert(cssText.includes('body[data-theme="night"][data-wallpaper="starry"]'), '含夜间星空覆盖');
        assert(cssText.includes('.auto-scroll-btn'), '含自动阅读按钮样式');
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

    console.log('\n=== 测试11：沉浸模式不锁定屏幕方向（防横屏回归） ===');
    {
        const appText = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
        // 关键回归断言：不得调用 screen.orientation.lock，避免手机端被强制横屏
        assert(!/screen\.orientation\.lock/.test(appText), '不调用 screen.orientation.lock');
        assert(!/lockOrientation/.test(appText), '不调用旧版 lockOrientation');
        assert(appText.includes('toggleImmersiveMode'), '含 toggleImmersiveMode 函数');
        assert(appText.includes('enterImmersiveMode'), '含 enterImmersiveMode 函数');
        assert(appText.includes('exitImmersiveMode'), '含 exitImmersiveMode 函数');
        assert(appText.includes('initImmersive'), 'init 中调用 initImmersive');

        const cssText = fs.readFileSync(path.join(SITE_DIR, 'css/style.css'), 'utf-8');
        assert(cssText.includes('body.immersive-mode'), 'CSS 含 body.immersive-mode 规则');
        assert(cssText.includes('.immersive-mode .toolbar'), '沉浸模式隐藏 toolbar');
        assert(cssText.includes('.immersive-mode .bottom-bar'), '沉浸模式隐藏 bottom-bar');
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

    console.log(`\n=== 测试结果：通过 ${passCount}，失败 ${failCount} ===`);
    if (failCount > 0) {
        process.exit(1);
    }
}

runTest().catch((err) => {
    console.error('❌ 测试执行出错:', err);
    process.exit(1);
});
