/* 心屿 · 只读离线壳（Service Worker）
 *
 * 对标轮 r28 新增。依据：能力矩阵 `pwa_offline=0/16`（r27 已证是"真零"而非漏数：
 * lobehub 递归树 20,740 对象 truncated=false 且无 SW 文件）⇒ 16 个同类都没做离线壳，
 * 而心屿已有 manifest.webmanifest，补一个只读壳是唯一低成本的差异化能力（现场断网也能演五幕）。
 *
 * 三条硬规则（本项目吃过"SW 缓存旧代码导致看不到新东西"的亏，所以规则是保守优先）：
 *   1) 导航与 HTML **network-first**：改了一个字节，下次进入必须看到新版，绝不用旧缓存钉住页面；
 *   2) `/api/**` 与非 GET **完全不碰缓存**（network-only）：对话内容与情绪记录不得被回放或串号；
 *   3) 只有 `vendor/` 与 `assets/`（大且极少变）走 cache-first，且缓存名由 **VENDOR_STAMP** 钉住 ——
 *      该戳必须等于 vendor 内容指纹（判据 O7 复算比对），换 vendor 忘 bump 会直接判红。
 *
 * 另外：`js/demo-config.js` 本地版含密钥 ⇒ **永不预缓存、永不写缓存**（判据 O6 盯着）。
 */
const VENDOR_STAMP = "ca0f2b633c";                       // 由 _test/offline_shell_check.py O7 复算校验（占位值即判红）
const CACHE = "xinyu-shell-" + VENDOR_STAMP;
const PRECACHE = [
  "/", "/index.html", "/manifest.webmanifest",
  "/css/style.css",
  "/js/app.js", "/js/chat-agent.js", "/js/chat-window.js", "/js/chart.js",
  "/js/settings.js", "/js/voice.js", "/js/emotion-engine.js", "/js/emotion-remote.js",
  "/js/memory-store.js", "/js/scroll-story.js", "/js/three-scene.js",
  "/data/emotion-lexicon.js", "/data/emotion-strategy.js",
];
const NO_STORE = ["/js/demo-config.js"];                 // 含本机密钥，绝不落缓存
const NETWORK_ONLY_PREFIX = ["/api/"];
const CACHE_FIRST_PREFIX = ["/vendor/", "/assets/"];

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await Promise.all(PRECACHE.map((u) => c.add(new Request(u, { cache: "reload" }))
        .catch((err) => console.warn("XINYU-PRECACHE-FAIL", u, String(err).slice(0, 120)))));
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

const startsWithAny = (p, list) => list.some((x) => p.startsWith(x));

/** 给响应打来源标记。为什么必须有：被 SW 拦截的请求在页面侧 `transferSize` 恒为 0
 *  （无论 SW 走的是网络还是它自己的 Cache Storage）⇒ 判据若拿 transferSize 当证据，
 *  等于"两种结果都长一样"，是没有判别力的判据（r22 同族）。只能由 SW 自己说清这一发从哪来。 */
async function withSrc(res, src) {
  const body = await res.clone().arrayBuffer();
  const h = new Headers(res.headers);
  h.set("x-xinyu-src", src);
  return new Response(body, { status: res.status, statusText: res.statusText, headers: h });
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                                  // 非 GET 一律不拦（对话是 POST）
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;                   // 第三方域名不接管
  if (startsWithAny(url.pathname, NETWORK_ONLY_PREFIX) || startsWithAny(url.pathname, NO_STORE)) {
    return;                                                          // 交回浏览器直连网络，绝不读写缓存
  }
  if (startsWithAny(url.pathname, CACHE_FIRST_PREFIX)) {
    e.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return withSrc(hit, "cache");
      const res = await fetch(req);
      if (res && res.ok) (await caches.open(CACHE)).put(req, res.clone());
      return withSrc(res, "network");
    })());
    return;
  }
  // HTML / JS / CSS / manifest：network-first，断网时才回退缓存（导航回退到壳 "/"）
  e.respondWith((async () => {
    try {
      const res = await fetch(req);
      if (res && res.ok) (await caches.open(CACHE)).put(req, res.clone());
      return withSrc(res, "network");
    } catch (err) {
      const hit = await caches.match(req) || (req.mode === "navigate" ? await caches.match("/index.html") : null);
      if (hit) return withSrc(hit, "cache-fallback");
      // 断网且壳里没有这一件：必须留痕。否则页面只是"某个模块 undefined"，运维侧看不出是壳缺件
      console.warn("XINYU-SHELL-MISS", url.pathname);
      throw err;
    }
  })());
});
