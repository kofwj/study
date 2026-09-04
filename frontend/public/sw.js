// 阳光学习工作台 service worker：静态资源离线缓存，API 一律走网络（保证数据新鲜）
// __BUILD__ 由 vite 构建时替换为时间戳，使每次发版都会更新 SW 并提示刷新
const BUILD = '__BUILD__'
const CACHE = 'sunshine-' + BUILD
const PRECACHE = ['/', '/manifest.webmanifest']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)))
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api')) return
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const clone = res.clone()
        caches.open(CACHE).then((c) => c.put(e.request, clone))
        return res
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('/')))
  )
})