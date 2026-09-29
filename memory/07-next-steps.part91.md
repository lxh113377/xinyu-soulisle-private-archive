# 07-next-steps.part91 — r82 轮完整记录（2026-09-29）

> 从 07 壳迁出的长段落全文。壳只留一行摘要 + 本卷指针。

## ① 交付面静默删除**第二次**复发（根因未找到，本轮只修了判据）

一手读数（17:5x 入场实测 `git status --porcelain`）：7 条 ` D`
- `交付物/提交包/application-plan.html`（HEAD blob 37,194 B）
- `交付物/提交包/render-pdf.ps1`（3,197 B）
- `交付物/提交包/演示视频脚本.md`（1,865 B）
- `交付物/提交包/演示视频-录制执行清单.md`
- `交付物/提交包/demo_video_out/subtitle.ass` / `timeline.json`
- `交付物/提交包/demo_video_out/心屿SoulIsle-演示视频.mp4`（**22,954,501 B，唯一参赛成片**）

取证链（三条都过才敢判「是丢不是搬」）：
1. `git ls-tree -r HEAD 交付物/提交包/` = 21 项，7 项全在提交面；
2. 全盘 `find`（含 `archive/`、`交付物/_参考资料-非提交/`）无同名副本；
3. 当天 15:50 生成的 `交付物/提交包.zip`（19 条目）**不含这 7 件** ⇒ 不是「搬进 zip 后删原件」。
最后一次改这些件的是 `ebf0736`（09-25 20:42，成片 r34 再录）；HEAD 提交时刻 15:02，zip 时刻 15:50，
两次 `git rev-parse HEAD` 同值 ⇒ 删除发生在**最后一次提交之后**，且当时无并发写。

处置：`git checkout HEAD -- <7 条逐路径>`（**不用 `git checkout .`**，会连别人在途 hunk 一起冲），
逐件 `git hash-object` 前后同值（`fe77beaa…` 等），`git status --short 交付物/提交包/` 只剩 3 条 `??`。

**为什么判据只抓到 2/7**：`deliverable_inventory_check`（r59 立）三条分母全来自「清单声明」
⇒ 没写进清单的入库件消失了**永远不会红**（本轮只报 `render-pdf.ps1` 与成片）。
新腿（第 4 条取数面）分母 = `git ls-tree -r -l HEAD -- 交付物`（89 条，被检对象写不进去的量），
逐条验在位性与 0 B；git 取不到 ⇒ `UNVERIFIED` 不判绿。演习（删一件未声明的入库件）⇒
`rc=1 · 入库件从工作树消失: …（HEAD blob 37194 B 在，磁盘没有 ⇒ 无人声明也丢）`，随后按字节还原。

**下一刀（本轮未做）**：这条腿现在只在电池/CI 里跑，而本轮 7 件是**会话开场**才看见的
⇒ 真正的出口是把「入库件在位」接到 `pre-commit` 或 `A-memory-start` 的开场实测里。
另一条未闭合：**肇事者没找到** —— 修判据不等于修根因，下轮若再现需按时刻对齐 `提交包.zip` 的生成方。

## ② G2（r81 建议 4）CSP 内联样式本体：修完 + 两面同步 + 预算登记

7 处 markup 内联样式（src 与 deploy 共 14 个整行指纹）改为：静态进类
（`src/css/style.css` 的 `.crisis-chip` / `.crisis-chip .dot` / `.readout-line` / `.readout-lead`）、
动态走 `data-fg`/`data-bg`/`data-w` 由 `src/js/app.js` 新增的 `paint()` 一趟 CSSOM 落属性。
**没有放宽 `deploy/xinyu/_headers` 的 `style-src 'self'`**（那是缺陷本体不是约束；H3 棘轮仍咬 `'unsafe-inline'`）。

字节代价（如实记，不静默）：`style.css` 13,813→14,081（超原预算 13,888）⇒ `size_budget_check` 登记 14,785，
理由写在 BUDGETS 注释里（登记前先把 CSS 注释从 106 B 压到 60 B，解释移进判据注释）；
`app.js` 17,036→17,405，仍在 17,524 内；TOTAL 848,879 / 858,752 未动。
回归：`inline_style_check` `扫描=30｜命中=0｜新增=0`（基线清空 ⇒ 转纯网，任何新写内联样式当场红）；
`deploy_sync_check` rc=0（missing/diff/extra 三类归零）；`browser_check` **ALL-ASSERT-PASS**
且 `LIT: init=0 after1=5 after2=17 reload=17 clear=0` 与既有基线逐字相同（证明没改坏点亮链路）。

## ③ 本轮最值钱的一条：管 CSP 的闸，自己也对 CSP 全盲

把 HEAD 未修版（7 处内联样式）放回 `deploy/xinyu/js/app.js` 跑 `headers_csp_check` ⇒
**`HEADSEC-PASS … CSP 下应用可用（五幕=5 对话=True 异常=0）`**。即 r81 那句「本地判据全盲」
不止说中 `browser_check`（Java 服务不发 CSP 头），也说中了这道 r54 就在的、**本该**管 CSP 的闸。
两条根因：① `probe["app"]` 只带 `errors`（pageerror），从不读收集 console violation 的 `vios`
—— 内联样式被拦**只写 violation、不抛 pageerror**；② H2 探针只加载页面 + 发一句话，不驱动第二幕读数/危机条。

补 **H6**（夹具 `--selftest` 8→13 腿，`expected` 由 `ok+len(fail)==expected` 双向钉）：
- 驱动普通轮 + **危机轮**，词面必须取自 `src/data/emotion-lexicon.js` 的 crisis 表（实测「跳楼」**不在表内**，
  它是 `SafetyGuard` 的输出高危词 —— 拿输出词当输入探针会让这条腿永远打不到分支，本轮第一版就是这么写的）；
- 断言 `csp_vios=0`、色点背景色非 transparent、`.crisis-chip` 边框色 == `rgb(255,122,122)`；
- **强度条宽度必须与 `data-w × 轨道宽` 成比例（±2.5px）**。这一条是自纠出来的：第一版只断言「宽度>0」，
  B 面**没红** —— 被拦时 `<i>` 靠 `display:block` 把轨道**撑成满格**，「有宽度」不等于「宽度对」。

**异步落点必须等被等对象**：`chat_ok` 只看 `#chat-log` 子节点数，读数是随后落的 ⇒ 第一版量到
`面板结构=chips=0 bars=0 … html-len=24` 与 `宽度=-1`，看着像缺陷其实是没等到。加 20s 轮询等色点出现后
再量，并把 `readout_wait`/`readout_shape` 作诊断面随判红印出（红因是「还没渲染」还是「渲染了但宽度不对」必须分得开）。

**夹具噪声不得洗成产品清白**：H5 的 `inline_blocked` 探针**自己**注入一段会被拦的 `<style>`，
那条 violation 落进 `vios` 会让 H6 误判红（本轮第一条判红的样本 url 为空、行号 5 ⇒ 出处在 `pg.evaluate`）。
处置不是静默 clear：先计数成 `harness_vios` 再清。violation 现带出处，B 面实测 `@./js/app.js:94`。

## ④ 电池去单点（r81 建议 6）与 103 套件

`run_all_suites.py` 自管 8123：`serve_plan`（纯决策：复用/自管/如实跳过）+ `ensure_server`
（fat 且新于源码由 `jar_shape_check.inspect` 判；解释器顺序 `XINYU_JAVA→PATH→实测 JDK17→JAVA_HOME`
且**必过 `java_major>=17`** —— 本机 `JAVA_HOME` 默认 JDK 8，`1.8.0_504` 要算成 8 不能算成 1）
+ `stop_server`（terminate→wait→kill 兜底）经 `atexit` 收口。
实测：停掉人工服务 → `--only preflight` ⇒ `SELF-HOST: start ｜ 已起并等到 status=UP` rc=0，
跑完 `tasklist` 无 java.exe、端口只剩 TIME_WAIT、`server_preflight` 随后如实回 rc=2；
整跑电池 `BATTERY: 95/100 rc=1`，`SELF-HOST: start` 同轮打出 ⇒ 21 格不再依赖人工起进程。
CI 侧走 `reuse`（job 自己先起了 jar），**不停别人的进程**。

套件数 101→**103**（新增 `measure_entry` + `measure_entry_selftest`）⇒ README 的声称数由 `repo_config_check` G4
对账、新脚本由 G16 双向对账（漏登/幽灵登都红）⇒ 两处都要同步改，本轮改完 16/16 PASS。

## ⑤ peers 尺的收口崩（A9 钉住这一族）

`benchmark_metrics.py:1752` 仍按 3 值解包，而 `classify_drift` 自 r79-D 起返回四档
⇒ 每次真跑把 16 仓采完印完才 `ValueError: too many values to unpack`，**漂移一条都没落进台账**，
而 `--selftest` 全绿（全文 10 处 `classify_drift(`，1 定义 + 9 调用，**8 处已改、漏的正是真面走的那处**）。
这是 R238「用单测掩盖接线错误」的又一形态：签名演进的爆炸半径只在**没人跑的那条路**上显形。
除改解包外加 **A9 静态腿**：枚举本文件所有 `classify_drift(` 解包赋值，逐条验 LHS 恰为 4 个标识符，
且命中数 <2 即判「正则失效、这条腿恒真」。

配套一条归因纪律：第一次取数时后台包装器报 `completed (exit code 0)`，真 rc=**1** 只在被重定向的 stdout 里
⇒ **判取数/发布绿只读被等对象自己的退出回执**（本轮台账留 `PEERS_RC=1` 原文）。

## ⑥ 取数入口前置自证（r81 建议 5 落地）

`_test/measure_entry.py`（新）：`ast` 解析 + **归属面**（同一件再解析 `git show HEAD:<path>`：
工作树坏而 HEAD 好 ⇒ 判「未入库改动把它写坏了」，交持有者自收；两边都坏 ⇒ 判「已入库的坏尺，
此前任何跑在树上的读数不可信」）+ 口径面把 `repo_config_check` 的 rc 原样并入（不另写一套「什么算好尺」）。
真面 `点名 15 件｜解析坏 0｜归属失明 0｜体检 rc=0`；演习注入 r81 那一形 ⇒
`rc=1 · 401:28 invalid syntax` + 「未入库改动把它写坏了」，随后按字节还原。

## ⑦ 建议 8（T8 具名缺口）的归因结论：**结构不可达，不虚报覆盖**

`LlmProxy.call`(漏 6 指令) / `openStream`(漏 8 指令) 逐行复算后全落在 `LlmProxy.java:95` 与 `:126`
的 `payload == null → bad-json`，唯一来源是 `:166-167` 的 `writeValueAsString` catch。
而 `toMessageList` 把任何入参形状都归一成 `Map<String,String>`（非对象跳过、`hasNonNull` 挡 null、其余 `asText()`）
⇒ 该 catch 不可能触发。沿用 r77「不为凑数写反射」：**BRANCH 仍 96.28%（LINE 97.75 / METHOD 96.43 与 r81 逐项相等）**，
用例数 82→**83**。替代交付 = 把这条原本只有散文的不变量钉成用例
（畸形四类入参走两条公开出口，断言字段皆字符串且状态码仍是上游的而非 500）。
要真提 BRANCH 只能动**真分支**：`MemoryController`（分支漏 3/30）、`ChatController`（分支漏 2/30）仍是活靶。

## ⑧ 我自己造的两处红（先记再修，别只记别人的）

1. `eol_parity` 被我判红：用 `Path.write_text()` 打补丁 3 处，Windows 下 `newline=None` 把 `\n`→`\r\n`
   ⇒ `_test/run_all_suites.py` 工作树 785 条 CRLF、HEAD blob 0 条 ⇒ 他人 clone 字节不可复算。
   按字节归一后 `EOL-PARITY-PASS（text=405 binary=20 total=425）`。与既有记忆「记 sha 的写入器必须锁 newline」同源。
2. **夹具与解析器按同一个假设写** ⇒ 自证体系内部一致、外部全错：我给 `git ls-tree -l -z` 写解析时按
   「sha\tpath\tsize」造夹具，结果 `--selftest` 全绿而真面 89/89 判废；`od -c` 实测字段序是
   `100644 blob <40hex>` + **空格填充** + `<size>` + **单个 TAB** + path + `\0`。
   修法是换一条**独立取数通道**对账（`--name-only -z` 再数一遍条目数），而不是给夹具补一条同假设的用例。
   另：`-l` 与 `--name-only` **互斥**（实测 git 报错），首版就是混用了 —— fail-closed 判 UNVERIFIED 是对的。

## ⑨ 本轮没做成的两件（不折叠）

- **发版（G6）没做，拦在凭据不在授权**：`CLOUDFLARE_API_TOKEN`/`CF_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` 均未设、
  `~/.wrangler` 登录态不存在（仓里只有缓存的 `wrangler-account.json` 账号 id），且临时前缀装 wrangler 两次失败
  （npm `Exit handler never called`，日志显示 workerd 各平台包对 `registry.npmmirror.com` 先 ECONNREFUSED 重试再 200）。
  ⇒ 公网仍是 r79 之前的构建，`public_check`/`live_sync`/`ci_status` 三条红同源不解。
  **需要老大给的只有 Cloudflare API Token（或一次交互式 `wrangler login`）**；拿到后按
  `cd deploy` → `pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true`（日志须见 `Uploading Functions bundle`）
  → 先记回滚锚 deployment id → 复算 `live_sync_check` + `public_check`。
- **推送要靠内联关代理**：`.gitconfig` 的 `http(s).proxy=http://127.0.0.1:7897` 在跑的时刻代理客户端没起，
  `git push` 报 `Failed to connect to github.com port 443 via 127.0.0.1`，而 curl 直连 github/api/pages.dev 全 200。
  处置**不改配置**（改共享配置属他人可见状态），只对该条命令内联：
  `git -c http.proxy= -c https.proxy= push origin main` ⇒ `9e3c94f..c38f97a`，`ls-remote` 与 HEAD 同值。
  下轮遇到同类失败先按「域名×时刻」测直连，再决定内联关代理；别把「代理在配置里」当成「代理在跑」。
