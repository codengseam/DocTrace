/**
 * 豪书斋 Service Worker
 * 缓存策略：核心资源预缓存 + 数据/笔记运行时缓存
 */
const CACHE_NAME = 'halo-read-v11'; // 2026-07-02 首页分类固定为「人/事/财/世」四类并加缓存破坏参数
const PRECACHE_ASSETS = [
    './',
    './index.html',
    './css/style.css',
    './js/app.js'
];

const CDN_ASSETS = [
    'https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(PRECACHE_ASSETS).then(() => {
                // CDN 资源单独缓存，避免一个失败导致全部失败
                return Promise.all(
                    CDN_ASSETS.map((url) =>
                        fetch(url, { mode: 'cors' })
                            .then((response) => cache.put(url, response))
                            .catch((err) => console.warn('[SW] CDN 缓存失败:', url, err))
                    )
                );
            });
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

function isDataRequest(url) {
    return url.pathname.includes('/data/');
}

function isNoteRequest(url) {
    return url.pathname.includes('/notes/') && url.pathname.endsWith('.md');
}

// BUG-035：SSG 章节静态页（site/reader/*.html），夸克/搜索引擎/无 JS 降级入口
// cacheFirst 策略与 notes 一致：HTML 不可变，构建期已固化
function isReaderHtmlRequest(url) {
    return url.pathname.includes('/reader/') && url.pathname.endsWith('.html');
}

function isCoreAsset(url) {
    return PRECACHE_ASSETS.some((path) => {
        const absolute = new URL(path, self.registration.scope).href;
        return url.href === absolute;
    });
}

function isCdnAsset(url) {
    return CDN_ASSETS.includes(url.href);
}

// 缓存优先：适合不常变更的核心静态资源
async function cacheFirst(request, cache) {
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        if (cached) return cached;
        throw err;
    }
}

// 网络优先：适合需要最新数据，但失败时回退缓存
async function networkFirst(request, cache) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        const cached = await cache.match(request);
        if (cached) return cached;
        throw err;
    }
}

// 过时再用：先返回缓存，后台更新缓存（适合首页数据，极速首屏）
async function staleWhileRevalidate(request, cache) {
    const cached = await cache.match(request);
    const fetchPromise = fetch(request).then((response) => {
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    }).catch((err) => {
        console.warn('[SW] 后台更新失败:', request.url, err);
    });

    if (cached) {
        // 确保后台 fetch 启动
        fetchPromise.catch(() => {});
        return cached;
    }
    return fetchPromise;
}

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
            if (isDataRequest(url)) {
                return staleWhileRevalidate(request, cache);
            }
            if (isNoteRequest(url)) {
                return cacheFirst(request, cache);
            }
            if (isReaderHtmlRequest(url)) {
                return cacheFirst(request, cache);
            }
            if (isCoreAsset(url) || isCdnAsset(url)) {
                return cacheFirst(request, cache);
            }
            // 其他请求保持默认
            return fetch(request);
        })
    );
});
