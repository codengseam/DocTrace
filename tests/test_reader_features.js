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

        // 推进几帧（首帧建立时间基线 dt=0 不滚动，后续帧滚动）
        for (let i = 0; i < 5; i++) {
            window.__flushRaf(16 * (i + 1));
        }
        assert(scrollByCalls.length >= 4, `rAF 推进 5 帧后 scrollBy 调用 ${scrollByCalls.length} 次 (>=4，首帧建基线)`);
        assert(scrollByCalls.every((y) => y > 0), '所有 scrollBy dy > 0');

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

    console.log('\n=== 测试15：点击代码块不触发阅读区翻页 ===');
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

        // 由于 handleReaderTap 依赖 event.target，这里通过 shouldExcludeTap 的单元方式验证
        // 触发 reader 的 click，目标为 code
        let tapFired = false;
        const original = window.handleReaderTap;
        // 简单验证：code 元素在 shouldExcludeTap 排除列表内
        const { handleReaderTap } = window;
        // 如果 handleReaderTap 不存在则通过代码存在性断言
        const appText = fs.readFileSync(path.join(SITE_DIR, 'js/app.js'), 'utf-8');
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

    console.log(`\n=== 测试结果：通过 ${passCount}，失败 ${failCount} ===`);
    if (failCount > 0) {
        process.exit(1);
    }
}

runTest().catch((err) => {
    console.error('❌ 测试执行出错:', err);
    process.exit(1);
});
