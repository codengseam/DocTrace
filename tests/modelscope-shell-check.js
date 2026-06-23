/**
 * 本地模拟测试：验证魔搭创空间嵌入优化是否生效
 *
 * 由于魔搭平台外壳（顶部标题条、左上角×、右上角⋮、右下角平台悬浮按钮）
 * 位于 modelscope.cn 父页面，无法本地复现，本脚本只做两件事：
 * 1. 模拟注入魔搭外壳风格的 DOM 到当前页面；
 * 2. 验证我们自己的嵌入优化类（.modelscope-embedded）能正确隐藏自有冗余 UI。
 *
 * 使用方法：
 *   1. 本地启动站点：python -m http.server 8080 --directory site
 *   2. 浏览器打开 http://localhost:8080
 *   3. 在 Console 中执行：fetch('/../tests/modelscope-shell-check.js').then(r=>r.text()).then(t=>eval(t))
 *   4. 或直接用 Node + Playwright 运行自动化版本（见 README）。
 */

(function checkModelScopeEmbedOptimization() {
    'use strict';

    // 1. 模拟魔搭创空间的外壳 DOM（与平台真实类名无关，仅用于触发/验证自身样式）
    const shellStub = document.createElement('div');
    shellStub.id = 'modelscope-shell-stub';
    shellStub.innerHTML = `
        <div class="ms-header-bar" style="position:fixed;top:0;left:0;right:0;height:48px;background:#1a1a1a;color:#fff;z-index:9999;display:flex;align-items:center;justify-content:center;">
            <span>豪书斋 / 创空间</span>
        </div>
        <button class="ms-close-btn" style="position:fixed;top:8px;left:8px;z-index:10000;width:32px;height:32px;background:#333;color:#fff;border:none;border-radius:50%;">×</button>
        <button class="ms-menu-btn" style="position:fixed;top:8px;right:8px;z-index:10000;width:32px;height:32px;background:#333;color:#fff;border:none;border-radius:50%;">⋮</button>
        <div class="ms-bottom-nav" style="position:fixed;bottom:0;left:0;right:0;height:56px;background:#1a1a1a;color:#fff;z-index:9999;display:flex;align-items:center;justify-content:space-around;">
            <span>上一章</span><span>目录</span><span>设置</span><span>下一章</span>
        </div>
        <button class="ms-float-btn" style="position:fixed;bottom:72px;right:16px;z-index:9999;width:56px;height:56px;border-radius:50%;background:#f5f5f5;border:1px solid #ddd;box-shadow:0 2px 8px rgba(0,0,0,0.15);">ℹ</button>
        <button class="ms-like-btn" style="position:fixed;bottom:72px;right:80px;z-index:9999;width:56px;height:56px;border-radius:50%;background:#f5f5f5;border:1px solid #ddd;box-shadow:0 2px 8px rgba(0,0,0,0.15);">♡</button>
    `;
    document.body.appendChild(shellStub);

    // 2. 强制给 body 加上嵌入标记类，模拟 detectModelScopeEmbed() 的判定结果
    document.body.classList.add('modelscope-embedded');

    // 3. 验证我们自己的 UI 是否被正确隐藏/适配
    const checks = [
        {
            name: '自有首页品牌栏隐藏',
            selector: '.brand-header',
            expect: 'none'
        },
        {
            name: '自有移动端底部栏隐藏',
            selector: '.bottom-bar',
            expect: 'none'
        },
        {
            name: '沉浸阅读按钮显示',
            selector: '#immersiveBtn',
            expect: 'visible'
        },
        {
            name: '阅读视图高度适配 iframe',
            selector: '.reader-view',
            expect: 'height-adapted'
        }
    ];

    const results = checks.map(check => {
        const el = document.querySelector(check.selector);
        if (!el) {
            return { name: check.name, ok: false, reason: '元素未找到' };
        }

        const style = window.getComputedStyle(el);
        let ok = false;
        let detail = '';

        if (check.expect === 'none') {
            ok = style.display === 'none';
            detail = `display: ${style.display}`;
        } else if (check.expect === 'visible') {
            ok = style.display !== 'none' && style.visibility !== 'hidden' && parseFloat(style.opacity) > 0;
            detail = `display: ${style.display}, visibility: ${style.visibility}, opacity: ${style.opacity}`;
        } else if (check.expect === 'height-adapted') {
            const height = style.height;
            ok = height.includes('calc') || height.includes('vh');
            detail = `height: ${height}`;
        }

        return { name: check.name, ok, detail };
    });

    // 4. 检查 postMessage 是否已尝试发送（通过包装 window.parent.postMessage 实现）
    let postMessageCalled = false;
    const originalPostMessage = window.parent.postMessage;
    window.parent.postMessage = function (...args) {
        postMessageCalled = true;
        console.log('[模拟] postMessage 已发送:', args[0]);
        // 不要真正发送，避免跨域报错
    };

    // 重新触发一次请求
    if (typeof requestModelScopeMinimalChrome === 'function') {
        requestModelScopeMinimalChrome();
    }

    window.parent.postMessage = originalPostMessage;
    results.push({
        name: 'postMessage 请求已尝试',
        ok: postMessageCalled,
        detail: postMessageCalled ? '已调用' : '未调用'
    });

    const allOk = results.every(r => r.ok);
    console.log('===== 魔搭创空间嵌入优化自检 =====');
    console.table(results);
    console.log(allOk ? '✅ 全部通过' : '❌ 存在未通过项');

    return { pass: allOk, details: results };
})();
