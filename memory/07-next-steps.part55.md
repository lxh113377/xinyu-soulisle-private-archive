# 07 分卷 55 — 对标轮 r54（对外交付面的安全响应头 / CSP）条目全文

> 迁卷动因：07 主壳收在 4,095/4,096 B，r54 要加一行只能同时瘦身既有条目。
> 全文详证在 `CHANGELOG.md` 的 r54 三段与 `交付物/对标分析报告-2026-09-27-r54.md`；本卷只留**下一轮用得上的**部分。

## r54 安全响应头 / CSP 面（已完成，→ 电池 88）

**换面取证**：`grep -ilE "CSP|内容安全策略|安全头|helmet|X-Frame" 交付物/对标分析报告-*.md` = 十五份全 0，
而本仓从 **r28 起**就在维护 `deploy/xinyu/_headers` —— 典型"配置在册就以为生效"。

**线上实测两条缺陷**（`curl -D -` 逐路径，18:04）
1. `content-security-policy` 在 `/`、`/index.html`、`/sw.js`、`/js/app.js`、`/nope-404` **一条都没有**。
2. r28 只给 `/index.html` 写 `Cache-Control: no-cache`，而 Pages 把它 **308 跳到 `/`** ⇒ 用户真正访问的
   入口拿的是 `public, max-age=0, must-revalidate`。功能上仍回源校验（不是可用性缺陷），但那句声明
   在入口 URL 上不成立，且这样写了 26 天。

**落地三件**
- 全站唯一内联 `<script>`（r28 离线壳注册）外提成 `src/js/sw-register.js` 并补进 SW `PRECACHE`
  （r45 踩过"外提件没进预缓存"）。这是能否开严格 CSP 的**前置**——留着它就只能写 `'unsafe-inline'`。
  ⚠️ 注册路径显式以 `document.baseURI` 定基：外提后按脚本自身 URL 解析会变成 `/js/sw.js`（404），
  而 `.catch(()=>{})` 把它咽成**静默无操作**——症状是"离线壳悄悄没了"而不是报错。
- `_headers` 开 11 条指令的严格 CSP（`default-src 'none'`、`script-src 'self'`、`style-src 'self'`、
  `img-src 'self' data:`、`connect-src 'self' https://api.deepseek.com`、`frame-ancestors 'none'`…）
  + `X-Frame-Options` + `Permissions-Policy`；路径同时写 `/` 与 `/*`。
  **刻意不写 `microphone=()`**：本站 ASR 走 Web Speech 要吃麦克风，写了会当场打断 `voice` 判据。
- 新判据 `_test/headers_csp_check.py`（+2 套件，桩 8 例）：取数手法 = **把同一份 `_headers` 在本地按
  Pages 语义回放**再逐路径逐条对账，然后在施加了 CSP 的服务器上跑真页面。
  **H5 先判**（一段必须被挡下的内联脚本；挡不住 ⇒ 夹具没在施加 CSP，整套读数作废）；
  H0 取数面为空不得判绿；H1 声明⇄回放等值；H2 CSP 下应用可用；H3 严格性棘轮；H4 内联计数须为 0；
  L1 线上复测。修后：`HEADSEC-PASS（路径5 五幕=5 对话=True 异常=0 内联=0 拦截探针真拦下）`、
  `HEADSEC-LIVE-PASS（实测头 12、CSP 指令 11）`。
- 新探针 `_test/peer_sec_headers_probe.py`（桩 6 例）：`csp` ⊄ `.csproj`、`helmet` 不得按散文命中。

**peers 读数与它的天花板** ✅：`结构 0/16｜helmet 依赖 1/16（SillyTavern）｜README 声明 0/16`。
⚠️ **不得读成"防护领先 16 家"**：多数参照是自托管应用，安全头在运维方的 web server 里，
仓库无配置文件是常态。本面只用于反衬自家"写了 `_headers` 所以以为生效了"，`ceiling_note` 随快照交付。

**挂 r55**
- `/api/*` 是 Pages Function，**不吃静态 `_headers`** ⇒ 头要函数自己回。实测该路径 OPTIONS 回
  `Access-Control-Allow-Origin: *`、POST 不回 ACAO（跨源浏览器调用事实上被 CORS 挡，但姿态含糊）。
- `--live` 未进 CI：挂法是**不可达出 rc=2 并单列一行**，既不因网络抖动拦主链，也不永远没人测。
- 老账三条别再抄：`release_cut.py`（r45）｜后端分类腿 `/api/emotion` 挂起注入（r52 §6-2）｜
  真机复跑（连续四轮挂账 ⇒ 要么排上，要么结案为"桌面仿真即验收口径"）。

