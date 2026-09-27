# 07-next-steps 卷57 — r55～r57（证据面 + 函数出口 + 取证出处可解析性）

> 取号：`volume_alloc.py`（O_EXCL 独占）｜落卷时间 2026-09-27（晚于 r56 卷56）

## r55–r56 证据面（判据说红必须答得出为什么）

- `safety_guard_check.py` 失败行改带**响应体**（原来只有断言名 ⇒ 红面不可归因）。
- 电池加**第四档 `ENV-QUOTA`**：`QUOTA_SIG = Insufficient Balance|insufficient quota|account balance`，
  只匹配**响应体文本**，不匹配状态码、不匹配套件名（保守签名，防把真代码缺陷洗成环境问题）。
  四条判据红由三条直证收敛到同一根因：**上游 DeepSeek 账号余额耗尽**
  （request_id `44b85548` / `6bdf868e` / `dba2abcb`，直连 curl 复核）。
- `public_check.py` 线上标签缺失时改用**页内同源 fetch** 打 `api/chat`，把上游响应体带进判据行
  （urllib 直连会被 Cloudflare `403 error code: 1010` 拒，非浏览器 UA 不通）。
- `browser_check` 的一条 CI-only 红：`#chart-count` 读得太早 ⇒ 等待对齐到**被等对象的完成态**，
  断言本身不放宽。

## r57 函数侧安全头 + 两处更正

- `/api/chat` 是 Pages Function，**不吃**静态 `deploy/xinyu/_headers` ⇒ 函数自己回头：
  CSP `default-src 'none'` / `nosniff` / `no-referrer` / `COOP same-origin` / JSON 侧 `no-store`。
  四个出口全覆盖（`no-key` 500｜`bad-json` 400｜SSE 直通｜整包透传），SSE 分支把 `SEC_HEADERS`
  展开在**自身 headers 之前**以保住 `no-transform`。`status`/`body` 一字未动（AC-OBS-08 逐字透传）。
  线上回执：`HTTP/1.1 402` + 五个头全在 + body 与部署前同形。
- **更正①（我自己本轮开头的假设）**：`OPTIONS /api/chat` 由平台直接回 405，它**吃**静态 `_headers`；
  只有 `POST` 交给函数才没有头 ⇒ 缺口比假设的窄，不需要 `onRequestOptions`（加了会把 405 变 204，动契约面）。
- **更正②（CI 真红 `disclaimer_forensics`）**：r57 报告性能行写「无同类可比口径」缺取证被点名到行。
  回核出处又测出：**r45 的取证「r40 §5 逐家单位对账（16 仓 0 家给出同口径首屏数）」挂错源** ——
  `对标分析报告-2026-09-24.md` §5 实为「可操作实施路径」，无逐家对账。结论由物重立：
  `交付物/对标数据/benchmark-metrics.json` 最新 run（ts=2026-09-26 18:17 UTC）**16 仓 × 14 字段，perf 字段 0 个**。
  ⇒ 不加 heading 存在性判据（§5 标题在、内容不是那回事，机械查标题造出的是抓不到本例的假守卫）。

## 未做（已登记，按优先级）

1. `headers_csp_check.py --live-api`：对线上 `/api/chat` 的 **POST** 断言五个头在位 + 错误体形状不变，
   配反向腿（本地注掉 `SEC_JSON` 必须判红）；接进 CI，不可达出 `rc=2` 单列一行不并入 PASS。
2. `deploy_sync_check.py` 扩展到 `deploy/functions/`（本轮只自证 SHA256 相同，比对面仍有盲区）。
3. `release_cut.py`（r45 起挂账）｜`/api/emotion` 挂起注入覆盖（r52 §6-2）｜真机复跑（已逾期 4 轮，
   要么做、要么正式收敛为「桌面模拟即验收基准」并留名）。
4. 🔴 只有老大能做：充值或换 Key（只走环境变量 `DEEPSEEK_KEY`）；撤销曾进过会话输出的明文 Key；
   iCAN 报名 PII（**硬截止 2026-09-30**）。
