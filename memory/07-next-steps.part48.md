# 卷48 — r49 收口：公网部署与三重复验（2026-09-27）

> 上卷 `part47`：改法、回执、自犯、四条收尾账。本卷单开是因为并入卷47 后达 4,712B
> 越过 4,096B 封顶（本仓惯例：建卷被封顶拦下就按语义拆卷，不压缩事实）。

## 5. 公网部署（老大 12:02 用手机截图追问「还没显示」后补做）

线上那份是**在我 11:57 那笔之前发的**，不是缓存玄学：按文件逐个 sha256 比对，
`deploy/xinyu` 23 项里 20 项逐字节一致、只有 `style.css`/`index.html`/`js/app.js` 三项落后
（线上 13,502/9,580/14,024B = r49 之前的尺寸）⇒ 爆炸半径恰为本轮改动，不含他人未入库内容。
走临时前缀 wrangler 部署（全局那份 workerd 仍缺二进制，不动共享面）：上传 3 个文件，
preview `66fc3669.xinyu-soulisle.pages.dev`。复验三重：三文件线上 hash == 本地、
旧规则 `btn-lightshow{display:none}` 已不在公网 CSS 里、`live_sync_check` 20 项零漂移；
公网真点回执 390/320 两档入口 44x44、可访问名命中 1、`LIT 0->900`、console 0 报错，
截图 `_test/_shots/r49_online_390.png` 目检为六色星雾 + 退出口。`public_check` 亦 PASS。
手机侧无需清缓存：`sw.js` 对 HTML/JS/CSS 是 network-first（只有 vendor/assets 才 cache-first，本轮未动）。
