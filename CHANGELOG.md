# Changelog

本项目所有值得注意的变更都记录在此。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]
### Added（r55 · 判据失败明细的证据面）
- **`safety_guard_check.brief()`**：失败行从只有 `http=402` 改成**带响应体前 96 字**（先脱敏 `sk-`
  形态再截断，空体给 `<无响应体>`；失败路径自己不许崩）。动因是 r54 收尾时的一条真判断：
  三条判红的真因是**上游余额耗尽**，而电池的分档器 `split_quota()` 只认响应体原文（不认套件名，
  否则换个名字就漏）—— `api_contract` 因带体被归 ENV-QUOTA(未验)，本套件因**只印状态码**被保守地
  留在 `RED(必须修)`。那不是分档器错，是**判据答不出"为什么红"**，会诱导下一轮去修一段没坏的产品代码。
- **`public_check` 的在线断言带取数证据**：`AssertionError: 对话未走在线（proxy）` 现在附带
  CHAT_TAG 与首条 console 文本（实测输出 `tag=大模型暂不可用 · 离线共情模板 …｜console=…status of 402 ()`）。
- **验收口径写死**：本轮在**上游仍无余额**的条件下复跑，看到
  `BATTERY: … ENV-QUOTA(上游余额/计费阻塞：响应体自证，非本仓缺陷，但仍不得记为已验): safety_guard`
  —— 分档从 RED 变 ENV-QUOTA 就是这条改动的回执；**rc=2 不是通过**。
  ⬜ 未完成的一半：`public_check` 仍留 RED，因为它取的是**浏览器 console 文本**，里面只有
  `status of 402` 而没有响应体。正解是给该套件补一次对 `/api/chat` 的直连 POST 并把 `brief(body)`
  带进断言（**不是**把 `402` 加进签名 —— 真契约缺陷也会回 402 类状态码，那条能力由
  `quota_selftest` 的「无签名一律留红」钉住）。

### Added（r54 · 对外交付面的安全响应头 / CSP 面）
- **`_test/headers_csp_check.py`（+2 套件，`--selftest` 8/8）**：取数手法是**把同一份 `_headers` 在本地
  按 Cloudflare Pages 的路径语义回放**（`/*` 通配 + 字面路径合并），再拿真实响应逐条对账，然后在
  施加了 CSP 的那个服务器上跑真页面。六条：H5 先判「拦截探针」——一段必须被挡下的内联脚本，
  挡不住就说明夹具没在施加 CSP，**整套读数作废**（判夹具不判产品）｜H0 取数面为空不得判绿｜
  H1 声明⇄回放逐路径等值｜H2 CSP 下应用可用（WebGL/五幕/对话/异常 0）｜H3 严格性棘轮
  （script-src、style-src 禁 `'unsafe-inline'`/`'unsafe-eval'`，放宽须改判据留名）｜
  H4 前置不变量（index.html 内联 script 计数须为 0）｜L1 线上入口复测（不可达按 UNVERIFIED 带状态码）。
- **`_test/peer_sec_headers_probe.py`（+1 套件，桩 6 例）**：peers 两通道（结构面配置文件 / README 锚定词组）。
  歧义形状两连反例：`csp` 是 `.csproj` 的子串、`helmet` 在散文里满地都是 ⇒ 路径与依赖通道一律锚定正则。
  快照 `peer-sec-headers-2026-09-27.json` 带 `ceiling_note`。

### Fixed（r54 · 两条实测缺陷）
- **整站零 CSP，而 `_headers` 从 r28 就存在**：✅ 线上 `curl -D -` 逐路径实测
  `/`、`/index.html`、`/sw.js`、`/js/app.js`、`/nope-404` 的 `content-security-policy` **一条都没有**。
  唯一挡着严格 CSP 的是 r28 那段**全站仅存的内联 `<script>`**（离线壳注册）——留着它就只能写
  `script-src 'unsafe-inline'`，等于把 CSP 最有价值的指令作废。处置：外提成 `src/js/sw-register.js`
  （并补进 SW `PRECACHE`——r45 踩过"外提件没进预缓存"）+ 开 11 条指令的严格 CSP。
  ⚠️ 注册相对路径显式以 `document.baseURI` 为基：外提后按脚本自身 URL 解析会变成 `/js/sw.js`（404），
  而 `.catch(()=>{})` 会把它咽成**静默无操作**——症状是"离线壳悄悄没了"而不是报错。
- **r28 的声明没落在生效路径上（26 天）**：那版只给 `/index.html` 写 `Cache-Control: no-cache`，
  而 Pages 把 `/index.html` **308 跳到 `/`** ⇒ 用户真正访问的入口拿的是
  `public, max-age=0, must-revalidate`。功能上仍回源校验（不是可用性缺陷），但"我给入口 HTML 加了
  no-cache"这句话在入口 URL 上不成立。现 `/` 与 `/*` 都写，线上复测 `/` 已回 `no-cache`。
- **`offline_shell_check` A7 取数面**从"只搜 index.html"扩成"页面 + 页面列出的 `js/*`"：
  注册语义未变只换文件，**修判据取数面而不是回退产品改动**（R263）；反向能力保留（合成用例不列
  脚本时 A7 照样红，`SELFTEST-PASS 13 类`）。

### 度量学（r54 · 判据自己被抓三条）
- **把"我的 UA 被 Cloudflare 挡"读成"线上没有 CSP"**：`urllib` 默认 UA 得 403，而同 URL 的 curl 得 200。
  更根本的是 **HTTPError 是带响应头的异常**，首版只记异常类型 ⇒ 状态码丢了，"不可达"与"可达但 403"同形
  （盲区不得读成零）。现带浏览器 UA + 把 `http=<code>` 回传并进结论行。
- **`assess()` 在取数面为空时判绿**：`_headers` 解析出 0 条规则时 H1 循环不产 miss，直接印 PASS。
  由 selftest 的边界用例当场抓出（R247 一族：0 命中须先证输入非空）⇒ 补 H0 显式守卫。
- **H1 首版拿通配模式 `/*` 当路径去要响应** ⇒ `/* 未取到响应` 假红；改为按 Pages 语义把声明**展开到
  每个被测路径**再对账。另：`/sw.js` 的第二份 CSP 变体删掉（同路径两处规则的合并顺序不可验证 =
  测不准的复杂度）；`Permissions-Policy` **故意不写 `microphone=()`**（本站 ASR 要吃麦克风，
  写了会当场打断 `voice` 判据）。

### 未做（诚实登记）
- `/api/*` 是 Pages Function，**不吃静态 `_headers`** ⇒ 它的头要由函数自己回，本轮未做（挂 §6-2）。
  实测该路径 OPTIONS 回 `Access-Control-Allow-Origin: *` 而 POST 不回 ACAO（跨源浏览器调用事实上被
  CORS 挡，但姿态含糊）；判据对它单独取数，取不到记 UNVERIFIED 不记 0。
- `--live` 尚未进 CI（只有本轮我手跑过一次 PASS）：挂 §6-1，做法是不可达出 rc=2 单列一行，
  既不因网络抖动拦主链，也不永远没人测。
- peers 侧 `结构 0/16｜helmet 依赖 1/16｜README 声明 0/16` —— **不得**读成"防护领先 16 家"：
  多数参照是自托管应用，安全头在运维方的 web server 里，仓库无配置文件是常态。

### Added（r53 · 上下文窗口预算与截断损失面）
- **`_test/context_budget_check.py`（+2 套件，`--selftest` 10/10）**：量「本机攒下的对话，
  模型这一轮真看到了多少」。取数面 = 拦 `/api/chat` 读 `request.post_data` 反解 messages；
  **截断条数由判据自己**用「发该轮之前本机 history 条数 − 窗口」算出，不采信产品报给自己的数
  （`measure()` 自比是登记在册的假反例形态）。六条：X1 覆盖率棘轮（下限 0.30）／X2 截断必须由
  概要注意送达**且条数对得上**／X3 system 段 ≤1,600 字符／X4 首轮与零截断不得有任何注入（反向腿）／
  X5 概要内不得出现用户原话／X6 未捕获异常 0。
- **`summaryOfDropped()` + `droppedCount()` 实装**：滑出 `HISTORY_MAX=10` 窗口的那段历史压成一行
  结构化概要（条数 + 情绪分布 top3 + 危机次数），**不抄原话**；界面加标「早前 N 条已概要」。
- **`peer_memory_probe` 换到逐类读数**：上轮只报"四类里有几类"的合计，本轮逐类拆
  （`memory 10/16｜summary 4/16｜ctx 窗口管理 3/16｜retrieval 3/16`）——合计会把三件不同的事糊成一个分数。

### Fixed（r53 · 一条实测缺陷 + 一条度量学自打）
- **14 轮对话里 16 条消息对模型永久不可见且零补偿**：`chat-agent.js:11` `HISTORY_MAX=10`、
  第 159 行 `history.slice(-HISTORY_MAX)` 是历史进 messages 的唯一入口 ⇒ 聊到第 6 轮前面全丢。
  演示与答辩现场一次正常对话就是 10–15 轮，而"情感陪伴"的叙事恰建立在模型看不见的部分上。
  修前该套件以 `X2 截断了 16 条历史，但 system 里没有「早前对话概要」段` **真判红**，修后送达且条数对账通过。
- **我自己写的一个测试脚本给产品充上了能力**：新增 `_test/context_budget_check.py` 的词元正好是
  `context`+`budget` ⇒ 结构探针把它算成"本仓有上下文窗口管理器"，self 从 1/4 虚高到 2/4。
  探针的 `NOISE` 加了测试/夹具目录排除（对 self 与 peers 同尺生效），并配**对偶**用例
  （产品目录里的同名文件必须照常命中，防止"一删了了"把真能力也排除掉）；桩 9→11。
  ⚠️ 诚实结论：self 在**结构面仍不在** summary/ctx 两格（摘要是函数级、藏在 chat-agent.js 里，
  按文件粒度的探针取不到），本轮只主张行为面 X2 已过。

### 度量学（r53 · 两处实跑前就拦下的）
- 首版 `assess()` 用**发完之后**的 history 条数算截断数 ⇒ 与产品"发之前"的口径差一条，
  概要与判据各算一套永远对不上；写完先手算 14 轮的两个数才发现，改为每轮记 `before`。
- 概要注意一度想写"首个话题=答辩"——那是用户原话的关键词，撞 r52 的 R7 隐私口径；
  改成只扫情绪标签，并给判据补 X2-INVARIANT（概要里出现独有词即红）。

### 环境（r53 登记，不归本会话修）
- `A-project-handoff/scripts/handoff_lib/volumegov.py:3456` SyntaxError（print 里嵌套 ASCII 引号）
  ⇒ `handoff.py` 整体跑不动、`savepoint` 链断。该文件 mtime=**16:53（当分钟）**、
  `D:\global_skills` 内另有 3 个在途改动 ⇒ **并行会话正在写**，按其自身纪律不代修。
  本轮手工完成 savepoint 的等价校验（07 P0 非空 / P-1 在册 / 07 全卷 ≤4,096 B / 文本 LF）。

### Fixed（r52 收口 · 切版之后落地的两处）
- **生产方 `Path.write_text()` 在 Windows 下把 CRLF 写进自家快照**：`peer_memory_probe --json`
  产出的 `对标数据/peer-memory-*.json` 工作树字节 ≠ git blob 字节，同族两处是切版时用
  `write_text` 改 `ROADMAP.md` / `server/pom.xml`。本仓 `.gitattributes` 明写 `* text=auto eol=lf`
  就是为了让"逐字节 / SHA256 / 字节预算"类主张在他人 clone 上可复算 —— 我把它破坏了三处。
  处置顺序：先按字节归一回 LF（改后与 blob 逐字节等值：21530 / 3145 / 11177），
  **再改生产方**为 `write_bytes(...encode)`（只还原产物不改生产方 ⇒ 下一跑还会再脏）。
  由 `eol_parity` 在全量电池第二跑抓出（第一跑全绿是在我引入它之前）。
- **切版结论回写三处**：报告 §5/§6、`memory/07-next-steps.md` 主壳、`part53` 里原先写的
  "r53 硬前置 = 切 v1.6.0"已改成"本轮末已切"，并补两条本轮自抓（footer 文法连犯三次、
  自己的产物写脏自己）。⚠️ v1.6.0 的 fat jar **未在本轮重构建**：`server/target/` 被在跑的 8123
  进程持有，且该产物 gitignored、可再生；本轮 Java 源码零改动。

## [1.6.0] - 2026-09-27 — 对标轮 r46–r52 收口（许可合规 / 移动端几何 / 窄屏入口 / 协作治理 / 故障注入 / 记忆召回 随版发布）

### Added（r52 · 长期记忆召回与上下文管理面）
- **`_test/memory_recall_check.py`（+2 套件，`--selftest` 9/9）**：量的是**「落库的记忆有没有回到发给模型的那条 messages」**——
  取数面 = 拦 `/api/chat` 读 `request.post_data`（真流量出口，不是读源码字符串）。五类用例：
  空记忆不得注入 ／ 播 3 条必须注入且带条数 ／ 刷新后仍召回 ／ **清库后必须消失（反向腿）** ／ 危机不发请求。
  另两条：R6 在线召回须在界面标注「已带入 N 条记忆」，R7 召回段内**不得出现任何用户原话**（只做聚合）。
- **`_test/peer_memory_probe.py`**：peers 16 仓三通道（结构面按**路径段词元**分类、README 锚定词组、
  以及「装配件 import 记忆件」的**正向引用边**）。引用边三态 `yes / none-in-sample(n) / NA` 分开记，
  只有 yes 算证据 —— 抽到 6 个装配件没看见 ≠ 该仓没做。快照 `交付物/对标数据/peer-memory-2026-09-27.json`。
- **`_test/readme_troubleshooting_check.py`（+2 套件，`--selftest` 5/5）**：新排障段 ⇄ 代码状态标签**双向**对账。
  正向取数面只认两个"决定状态的产地"（`modeLabel` 映射 + `refreshBadge()` 内的 `textContent` 赋值），
  按文件扫会被注释里的话污染（实测把「禁伪装在线」当成要求文档化的状态）。
- **实装召回**：`MemoryStore.recall()/count()`（次数/跨度/高频情绪三量，不含原话）→ `SYSTEM(emo)` 末尾拼接 →
  `respond()` 返回 `memory` 计数（**只在真发给模型时非零**，降级/离线标了就是说谎）→ `app.js` 气泡尾注。

### Fixed（r52 · 三条实测缺陷）
- **「记忆系统 ✅」是存在性结论而非能力**：十三份对标把 J4 双表记成强项，但 `memory-store.js` 导出面
  实测**零召回项**、`chat-agent.js` 只喂 `history.slice(-10)` ⇒ "跨设备记住你"当时**只成立在星图展示层**，
  模型侧对用户历史一无所知。现在召回真的进 prompt，且有常驻判据双向钉住（有=必须注入，清=必须消失）。
- **挂起型 30.2 s 里那 ~15 s 已归因**（r51 挂了整轮的 P1-2）：黑洞计数单位从「accept 次数」改成
  **「POST 请求数」**后看见 2 条腿 —— classify 腿与 reply 腿**各吃满一个 15 s 熔断后串行相加**
  （实测两腿间隔 15.0 s、已归因 30.0 s／30.2 s）。分类腿只回 ~20 token ⇒ 单独给 6 s，
  整轮 **30.2 s → 21.3 s**；`HANG_BUDGET_S` 随之 35 → **25**（实测上界 + 17% 余量，同一把尺）。
- **README 排障段首跑即抓到两处漂移**：我自己写了代码里根本不存在的徽章 `● 已离线`（真文案是
  `● 离线共情模板`），同时逼出一个真实但从未文档化的第四态 `● 网络不可用（配置为在线）`。
  ⚠️ 这不是"文档写好了"，是**判据把文档按回产品**。

### 度量学（r52 · 三条自己抓自己的）
- **`highlight` 同族第二例：词元不匹配致 self 假阴**。引用边首版拿"去掉扩展名的段名"（`memory-store`）
  当 needle，而调用点是 `window.MemoryStore.record`（归一化后 `memorystore`）⇒ 两串永不相等，
  **本仓被判成"没做回灌"**。改成三形状（连写形／原段名／词元本身）+ 成员访问（`x.y`）与 import 两条边，
  并补正例②（全局对象形）与反例⓪（注释里提一句 memory 不算边）。
- **歧义形状四连**：`storage` 含子串 `rag`、React `createContext` 目录、`memory-leak.spec.ts` 是泄漏测试件、
  README 里 "GPU memory" —— 每一条形成本探针的一条反向断言（`--selftest` 9/9 全打这四形）。
- **文本启发式重造词法器不成立**：Java 逐行引号奇偶判据实测**误报 6/20**（`{\\"emotion\\"}` 这类
  反斜杠-引号交替 + 跨行 `+` 拼接），已**撤出判定集合**并写明理由：该事实的权威判据是 javac，
  java-build 在 CI 链上且 T4 盯住构建步不得加 `-DskipTests`。留作手工诊断用（`java_quote_parity`）。
- **`--selftest` 里用了不存在的计数器**（`ok += 1` 而该 selftest 只有 `bad` 列表）⇒ `UnboundLocalError`；
  以及**失败出口自己会崩**：`repo_config_check` 的结论行对 tuple 调 `f.split()`，一旦真有判据红就
  抛 `AttributeError` 把红因盖掉 —— 两处都是"判据坏了长得像被测对象坏了"，已各自补反例。

### 未做（诚实登记，不写成已建议即完成）
- **不引入第三方错误监控**（Sentry/Datadog）：与产品隐私承诺直接冲突，属**主动不对标**（沿用 r51 裁决）。
- **peers 侧无行为注入条件**：`peer_memory_probe` 的引用边只到"结构与声明"，快照头 `ceiling_note` 写死。

### Added（r51 · 故障注入与错误可见性面）
- **`_test/fault_injection_check.py`（+2 套件，`--selftest` 9/9）**：把上游真打挂再读界面 ——
  F1 `HTTP 500` ／ F2 200+非 JSON（网关吐 HTML）／ F3 连接被断 ／ F4 黑洞不返回 ／ F5 故障后一次成功。
  每类都断言三件事：**界面有与故障同类的降级标注**、**输入框恢复可用**、**未捕获异常恒 0**；
  F5 反向断言徽章必须翻回「● 在线 AI」（否则我只是把开关焊死在另一侧）。
- **`_test/peer_fault_probe.py`**：peers 侧只取结构与声明证据（error-monitoring 配置、troubleshooting 段）。
  ⚠️ 天花板如实写进快照头：**故障注入不能对他人站点做** ⇒ 本面对 peers 只出"有没有做"，不出"做得好不好"。

### Fixed（r51 · 两条实测缺陷）
- **徽章在故障下说谎**：四类故障（500/非JSON/断连/挂起）下气泡如实写「大模型暂不可用 · 离线共情模板」，
  而全局 `#mode-badge` 仍停在 **「● 在线 AI」** —— 同一屏两句话互相打脸，撞本仓红线"禁伪装在线"。
  现由 `ChatAgent.llmBad()` 记录最近一次是否"配了在线却降级"，`refreshBadge()` 每轮 respond 后同帧翻面。
- **挂起型空转 60.6s**：`LLM_TIMEOUT_MS=60000` 实测让演示现场等**一分钟**才见兜底（气泡自己印 60,604ms）。
  该 timer 只约束"响应头到达"（收到即 clearTimeout），不影响已开始吐字的长回答 ⇒ 降到 **15s**；
  复测 30.2s（多出的 ~15s 归属未定，见下），仍是一半的改善。

### 度量学（r51 · 夹具把自己骗了两次）
- **playwright-python 按回调参数个数决定传几个实参**：首版 `def handler(route, m=mode, st=...)`
  被传入 `(route, request)` ⇒ `m` 被 request 顶掉，五类故障**全部掉进 else 分支被喂了成功响应**，
  判据于是报"四类故障都没降级、徽章都称在线"。那是**夹具坏了不是产品坏了**。
  改法：闭包工厂只收 `route`；并加**注入有效性正对照**（recover 必须出现 GOOD_BODY 指纹，否则整轮判
  INVALID、所有故障读数作废）——这条正对照正是拦住假读数的东西。
- **黑洞挂起不能用 `route` 回调里 `time.sleep(400)`**：同步 API 的回调跑在分发绿点上，
  睡 400s 会把分发循环一起占住 ⇒ 我自己的轮询取到 `None` 而不是"慢"。改真黑洞 socket 服务器
  （accept 后一个字节不回），顺带得到一个诚实的 hit 计数。
- **未归因的 30.2s 不写成机制**：黑洞只 `accept` 到 1 次连接，我却量到 30.2s（≠ 2×15s 的"重试"故事）。
  按"先归因再降级"的规矩，F4 预算按**实测上界 + 余量**定（35s），差额登记为 P1 待查，不编解释。

### Added（r50 · 协作治理与健康度面）
- **`_test/peer_community_probe.py`（`--selftest` 入电池 74→75，17/17）**：三通道独立取数 ——
  A 声明面（git tree 扫 CONTRIBUTING/SECURITY/CODEOWNERS/CODE_OF_CONDUCT/ISSUE_TEMPLATE/PR模板/dependabot）、
  B 平台面（GitHub 自己算的 `community/profile` health_percentage）、**C 行为面（dependabot 真开过几张、合并几张）**。
  实测 `CONTRIBUTING 10/16｜SECURITY 6/16｜CODEOWNERS 1/16｜conduct 2/16｜dependabot 件 1/16`；
  health min 28／中位 62／max 100；**有行为回执的只有 2 家**（lobehub 开 30 合 18、SillyTavern 开 7 合 7）。
  self：health 71、dependabot 开 4 合 3。
- **`G1b`（并入既有 `validate_dependabot`，不另造判据）**：maven 必须配 `ignore` 大版本。
  自测 48→50 条且**双向**：摘掉 ignore 判红；actions 侧无 ignore **不得**判红（防策略无据扩面）。

### Fixed（r50 · 两个"看着已覆盖、其实没生效"的洞）
- **🔴 漏洞告警整条是关的**：`gh api repos/{slug}/dependabot/alerts` 实测回
  `Dependabot alerts are disabled for this repository`（HTTP 403）。而 `dependabot.yml` 自 r21 在册、
  也确实开过 4 张 PR ⇒ **任何"文件在不在"式检查都看不见这个洞**。
  已 `PUT /repos/{slug}/vulnerability-alerts` 开启并**读回证明**：`GET` 从 `404(disabled)` 变
  **`HTTP 204(enabled)`**，alerts 端点从 403 变可读、**当前告警数 0**。
  ⇒ 修正结论：停在 Spring Boot 3.2.5 并无已知未修 CVE 压力（此前我把"该不该升"只当技术债评估，
  漏了"平台本来就能告诉我们"这一格）。
- **常红的 dependabot PR #2 已带证据关闭**：`spring-boot-starter-parent 3.2.5→4.1.1` 跨大版本，
  java-build 与浏览器回归两条 job 直接 fail，自 09-24 挂到 r50；而同期另两张 major
  （`actions/checkout 4→7`、`setup-python 5→7`）**已正常合并** ⇒ 问题不是"major 危险"，
  是 Spring Boot 大版本升级属**需人工评估的迁移**，不该由自动直送。策略已落 `dependabot.yml`（只对 maven），
  升 4.x 转为截止日（09-30）后的评估项。

### 度量学（r50 · 被自己的工具骗了三次，全部当场纠正）
- **org 级配置会让声明面假阴性**：lobehub 有 30 张 dependabot PR，其 tree 里却**没有** `dependabot.yml`
  （配置挂在组织级）⇒ "仓内找不到 = 没挂 dependabot" 是错的，**行为面才是权威**。
- **search 端点的 secondary rate limit 会造出假结论**：首版走 `search/issues?q=author:app/dependabot`，
  单次成功后续即 403（同一请求走 `gh api` 与 core `/pulls` 都 200）⇒ 16 仓 15 个 NA，
  汇总据此打印**"配了 dependabot 的 1 家里 0 家真跑过"**这个假结论。改走 `/pulls` + 按 `Retry-After`
  退避后 NA 14→5；并修 `verdict()` 把 `None`（未取到）**塌缩成"无 PR 回执"**的缺陷 —— NA 必须有自己的形状。
- **我的 `throttle()` 从来没生效过**：每次调用先 `del CALLS[:]` 清空历史再算"最近调用" = 不限流。
  这才是换端点后仍全 403 的真因；我前两版分别怀疑"权限不足"和"间隔不够"，都被实测否证。

### Fixed（r49 · 手机端「✨ 一键点亮」入口恢复，撤掉窄屏豁免账）
- **窄屏不再整块藏这个能力**：480 档的 `#btn-lightshow{display:none}`（`6cae042` 对标轮 M6 引入，行上无注释）
  改为「收图标」——文案拆 `.ls-ico` / `.ls-word` 两段，窄屏只把文字做 sr-only 裁切，
  所以**可访问名与桌面档逐字相同**（四档 `get_by_role(name="✨ 一键点亮")` 均命中 1，`a11y` 12 单元违规 0）。
  实测：触屏档入口 44×44、1280 档 87×27 与改前逐像素一致；点下去 `LIT 0→900`、退出保留 900、回记忆清零，
  320/390 零横向溢出、console 0 报错。
- **为什么此前没人发现**：`lightshow_check` 视口固定 1280×800，而 `mobile_check` 的 M2 只量**可见**目标
  （它自带反例「隐藏元素不得判」）⇒「由可见变不可见」对两条判据都天然豁免。
  现由常驻判据 `_test/entry_reach_check.py` 盯「可见性单调性」，豁免账已清空（gap 必须为 0）。


### Added（r47 · 移动端与触屏可达性面，量真实几何而不是"有没有写 @media"）
- **`_test/mobile_check.py`（+2 套件，`--selftest` 14/14）**：把页面渲进 4 档真视口
  （320×568 / 360×640 / 390×844 / 768×1024，`has_touch=True`）测四件事 ——
  M1 零横向溢出、M2 交互目标尺寸、M3 文本输入字号、M4 viewport 不得禁缩放；
  **M5 会把设置面板与对话坞点开再复检一遍**（默认折叠的控件里藏着 `set-provider` 的 14px，
  只测默认态就是漏判）。
  ⚠️ 关键实现事实：`(pointer:coarse)` **只在触屏上下文里匹配**。探针首版没开 `has_touch`
  ⇒ 改完 CSS 数字一动不动，差点误判成"我改错了"。
- **`_test/peer_mobile_probe.py`（+1 套件，`--selftest` 11/11）**：16 仓双通道（结构 + 声明）。
  实测 **有 HTML 入口 12/16 ｜ 有 viewport 11 ｜ 禁缩放 3 ｜ 按指针类型适配仅 2 ｜ 有 manifest 4**。
  **诚实边界写进快照头**：对手的真实触控几何静态取不到（那要渲进真视口），
  所以本面只出结构与声明证据，禁止据此写"对手移动端体验更差"。
  恒等式按轴成立：应测 16 = 可用 10 + NA 2 + 范围外(非 Web) 4，三者不并入彼此的 0。

### Fixed（r47 · 首跑实测三条，全部闭合）
- **7 个触控目标高 27–35px**（`btn-lightshow` 87×27、`btn-dock` 58×28、`btn-settings` 97×35、
  `btn-theme` 67×35、`btn-clear`/`btn-export` 108×35、`btn-demo-clear` ×42）
  ⇒ 新增 `@media (pointer:coarse)` 块统一抬到 ≥44×44。**用 pointer 媒体特性而不是宽度断点**：
  要大目标的是手指不是窄屏，桌面观感与像素标定零改动。
- **文本输入框 14–15px** ⇒ iOS Safari 聚焦时自动放大整页（用户被横向推走）。现全部 ≥16px。
  修法踩到一个真坑：裸 `input{font-size:16px}` 特异度 (0,0,1) **抢不过**基线
  `input[type=text]{font-size:15px}` 的 (0,1,1)，首版改完实测仍是 15px（只有 checkbox 变 16px，
  因为它没被类型规则盖）⇒ 按同等特异度补齐选择器后才生效。
- **判据标准被我引错并已改对**：首版把 44px 写成"WCAG 2.5.8 的要求"，而 **2.5.8 的 AA 底线是 24×24**，
  44 来自 iOS HIG / Material（WCAG 里对应 2.5.5 AAA）。真跑同时暴露我把原生 checkbox 的 13px
  一刀切判红。现改双层口径：**24 = AA 硬底线（任何人不得低）**，**44 = 本仓对独占型控件自选并钉住的红线**，
  `label` 内的 checkbox/radio 按**等效控件**豁免（但 label 自身 <24 时豁免不成立），
  且豁免个数**打印在 PASS 行里**不静默。
- 三处探针自犯（全部由反例钉住）：`css_largest` 名为最大实为"最浅"（抓到 reset 小文件、漏掉真样式表）；
  `\.cssx?` 是我臆造的后缀面；"无 CSS"被并入"0 条媒体查询"（NA 与 0 混同）。
  顺序教训：范围判定必须在取数失败判定**之前**，否则我自己塞进 errs 的 `css:NA` 会把非 Web 仓
  抢先判成"取数失败"—— 那是拿顺序冒充语义。

### 登记（r47 · 预算与既有裁定的对账）
- `src/css/style.css` 预算 13,368 → **13,888**（实测 13,502，+134B 含 5% 余量）。
  **先把注释压到 3 行再登记**，不是"装不下就抬上限"；块内容由 M2/M3 实测驱动。
- 与并行会话的既有裁定对账：`_test/entry_reach_check.py` 复跑
  `ENTRY-REACH-PASS … btn-lightshow@<=480px 已登记豁免｜stale=0` ——
  本面的 coarse 块**只加尺寸不动 display**，老大裁定的"窄屏藏入口是设计内取舍"没被我的样式改动悄悄推翻。

### Added（r46 · 许可与供给链面）
- **`_test/peer_license_probe.py`（`--selftest` 入电池，21/21，电池 70→71）**：双通道量 16 仓的许可合规形状
  （通道 A = GitHub 自己检测的 `license.spdx_id`，不用"有 LICENSE 文件就算"这种自证；通道 B = 递归文件树）。
  实测：**有 LICENSE 类件 14/16 ｜ 检测为 MIT 6/16 ｜ 带 vendored 第三方代码的只有 3/16 ｜
  三者中带归属件的只有 1/3**。⇒ 这一维对手普遍缺位，真正的对手是我们自己的声明与实物是否一致。
- **G6 的两条新断言（防伪登记）**：① 表行的**授权列**必须含许可 token（写"见上游"即红）；
  ② 表里所写许可必须与**文件 banner 实测串**一致（把 GSAP 伪写成 MIT ⇒ 翻红，夹具 ⑤e）。
  取交集而非全等，因为 GSAP 那行合法地写着「非 MIT、非 OSI」。自测断言 42 → **48** 条。

### Fixed（r46 · 判据盲区让最好的那份文档带上假陈述）
- **`_test/repo_config_check.py` 的 G6 分母从写死目录改名册现读**：原实现是
  `sorted(x.name for x in (ROOT / "src" / "vendor").glob("*.js"))`，于是 `_test/vendor/axe-core-4.10.2.min.js`
  （553,290B，banner 自证 **MPL-2.0**）对 G6 **永久隐形** —— 归属表不登记它也全绿。
  这是 r43 在 `vendor_freshness_check.py` 上治过的**同一个盲区的第二处**（当时只修了一处，注记还留在名册里）。
  本轮把活分母与自测夹具两处一起改成读 `vendor-manifest.json`，分母打印在 PASS 行里（`分母=4(名册现读)`）。
- **更正归属表的假陈述**：正文原写"`src/`、`server/`、`_test/`、`deploy/functions/` 等全部由本团队原创"，
  而 `_test/vendor/` 里坐着 Deque 的代码 ⇒ r42 之后即为假。现改为"四个文件除外，`_test/`（`_test/vendor/` 除外）原创"，
  并补 axe-core 的逐件行（含"MPL 是文件级 copyleft，不修改即无义务外溢"的再分发注记）。
- **README 授权口径行**同步到 4 件 / 两个目录（+4 B，未抬 16,384 B 预算）。
- 一条**无效反例**被自己的前置条件检查抓住：篡改⑤b 首版只替换 `**MPL-2.0**` 五个字，而同一列里还留着
  banner 原文 `Mozilla Public License, v. 2.0` ⇒ 反例没造成缺陷却期望判红（表现为"判据漏抓"）。
  改为整列抹除，并加**夹具失效守卫**（锚点不命中时直接报"夹具失效"，禁静默跳过）。

### Added（r45 · 发布治理常驻判据——把"别忘了切版"从记性活变成闸）
- **`_test/release_governance_check.py`（+2 套件，电池 68→70，`--selftest` 12/12）**：R1 距上次切版的 feat 增量
  ≤ 5（当前值与余量一起印在 PASS 行里，不做零余量地板）；R2 `[Unreleased]` ⇄ git 增量**双向**对账
  （有 feat 零 bullet 判红 / 有 bullet 零 commit 判红 / **R2c 逐轮点名**：commit 里的轮次号必须在 changelog 出现）；
  R3 已发布 tag 必须有对应版本段。**首跑即真判红**：`feats=11（上限 5）` + `r42,r43 漏记`，逼出 v1.5.0 切版。
- 一条自己的口径错被反向用例抓出：R2c 初版把 `docs/chore` 尾巴也算漏记，于是 v1.4.3 段标题里的 r38
  被误判（它的功能早已随版发布）。分母收窄到 feat/fix/perf/refactor 后 r38 自然消失、r41–r43 仍咬住，
  并补「正例③：docs/chore 尾巴免登记」钉住这个边界。
- **R4 发布滞后按天数「只报不拦」**：墙钟判据会在零提交的情况下自己从绿翻红，那是时间的颜色不是代码的颜色，
  不进默认阻断链（本机既有铁律）。取不到 tag（浅克隆）回落 `ls-remote`，两通道皆否 ⇒ **rc=2 UNVERIFIED**，
  不把"读不到"判成"违规"。

## [1.5.0] - 2026-09-27 — 对标轮 r39–r45 收口（11 个 feat / 44 个 commit 随版发布）

> 切版由本轮新上的 `_test/release_governance_check.py` 逼出：R1 实测「距 v1.4.3 已攒 11 个 feat（上限 5）」，
> R2c 实测「r41/r42/r43 三轮 feat 级提交压根没进 changelog」（下方已按轮次补齐）。
> 上一版 v1.4.3 的段标题写着「对标轮 r38 续」，所以 r38 只在 tag 之后留了 docs 尾巴 —— 那条**不算漏记**，
> 判据的分母因此收窄到 feat/fix/perf/refactor。

### Added（r45 · 发布治理对标探针，先量别人再被自己量）
- **`_test/peer_release_probe.py`（`--selftest` 入电池，13/13）**：16 仓同尺量「有公开 release / tag 合 semver /
  有 CHANGELOG 类件 / 发布滞后」四问，实测 **11/16 有 release、11/16 semver 合规、只有 4/16 带 CHANGELOG 类件、
  11 个有 release 的家里 4 家滞后 >30 天（min 0 / 中位 9 / max 261）**，BLIND 0 且恒等式自证。
  自犯一处并已修：`lag` 首版按**整数天**截断，把一个 22 小时前的发布读成 `lag=0`（假新鲜）——
  改小数天并补「30 小时 = 1.25」专用用例。

### Fixed（r45 · 公网离线态直接报错：外提的新模块没进 SW 预缓存）
- **现象**：`_test/offline_shell_check.py` R9a 报「公网壳 17/18 缺 `/js/data-rights.js`」，R7 同期在公网断网重载阶段
  抛 `TypeError: Cannot read properties of undefined (reading 'init') at js/app.js:208`。两条**同一根因**：
  离线时 SW 供不出该模块 ⇒ `window.DataRights` 未定义 ⇒ 编排脚本报错。公网用户断网打开即坏，不是"少缓存一个文件"那么轻。
- **根因**：r45 为修字节预算把模块外提，只改了 `index.html` 的 `<script>` 与 `src/`，**没同步 `src/sw.js` 的 PRECACHE**；
  而本仓判据 R8 早就"复算清单自 sw.js 源码"，A10 也盯"页面引用必须被壳覆盖" —— 我本地跳过了全量电池就推，两条闸一起在网上判红。
- **处置**：`PRECACHE` 补 `/js/data-rights.js` + 同步 `deploy/xinyu/sw.js` + 重部署公网壳（部署→判据复验 17 项全过、
  R8 入缓存 18/18、R7 零异常），**再**推送。教训回写：改 `src/` 的模块增删，SW 预缓存清单属同一改动面，不是独立运维项。

### Changed（r45 · 修 r44 造成的受理面红：单文件字节预算被顶穿）
- **真因**：r44 把「披露翻转 / 清除回执 / 导出下载」全塞进 `app.js` 与 `memory-store.js`，
  两文件分别到 16,815 / 7,550 B，超各自预算（14,390 / 4,844），CI `size_budget` 判红 2 项
  （run `36282517198`，`BATTERY: 63/64 RED: size_budget`）。
- **修法**：按本仓既有外提先例（`voice.js`/`chart.js`）新增 `src/js/data-rights.js` 承载 UI，
  `app.js` 回到 14,281 B（限内，未动其预算）；`memory-store.js` 因确实新增了两个数据动作
  （复核式删除 + 导出），预算 4,844 → 7214 B（实测 +5%），并同步登记新文件预算。
  **没有放宽任何判据的余量比例，也没有删断言求绿。**
### Added（r44 · 数据主体权利面）
- **`_test/data_rights_check.py` + `_test/peer_data_rights_probe.py`（电池 64→67）**：把「你的数据归你」从口号变成
  三条可判据的行为 —— ① 披露语**随真实模式翻转**（`remote:true` 才说"同步到服务端"，本机态说"不上传"，两态互斥
  且双向测）；② **清除带回执**：删完读 `/stats` 复核归零，把"我删了"变成"我删了 N 条并验证为 0"；
  ③ **导出对齐计数**：打包内容与 `/stats` 计数一致，不给人一份缺斤短两的 JSON。
  首跑踩中两处：回执写 `#probe-result` 被情绪探针覆写（改占自己的槽）、反向腿 `add_init_script` 每次导航重跑致 cfg 被重置（改用第二个 context）。

### Added（r43 · 可复现面）
- **`_test/clean_clone_check.py` + `_test/peer_repro_probe.py`（电池 61→64）**：证明「交出去的那份能跑」，
  而不是「我这台机器恰好有一份被 `.gitignore` 掉的文件」那一版能跑。从 **HEAD** 克隆到临时目录、起服、Playwright 真加载。
  归因口径：Chrome 的 404 console 行**不含 URL**，故按 `requestfailed` 的 URL 分类；已登记缺口取零命中即报警。
- **闭合 r42 自己造出的治理面外资产**：r42 为了让 a11y 判据能跑，把 axe-core 放进 `_test/vendor/` 却没登记进
  `vendor-manifest.json` —— 等于自己造了一个无人对账的 vendored 依赖。现已登记（sha256 + size），并把
  `vendor_freshness_check.py` 的对账单位从 basename 改成**全相对路径**（否则 `a/x.js` 与 `b/x.js` 可跨目录互相洗白）。

### Added（r42 · 无障碍面装上常驻门禁）
- **`_test/a11y_check.py` + `_test/peer_a11y_probe.py`（电池 58→61）**：12 个审计单元 = 6 状态 × 2 主题，axe-core
  规则集**必须含 `experimental`** —— 默认集看不见 `label-content-name-mismatch`，首跑就以 `violations=0` 骗过了我。
  另配注入式正对照（A3）证明判据会咬人。
- **闭合三条实测缺口**：`prefers-reduced-motion` 下星雾停掉持续动效（像素级验证降档倍数）/ 图标按钮补
  WCAG 2.5.3 label-in-name / 装饰字符 `⚙` 归 `aria-hidden` 并给 `aria-label`。
- 一处假反例入册：用截断 PNG 冒充"尺寸不符"是无效反例（M5④⑧ 第 4 次复发），改做真 16×16 图。

### Added（r41 · 测试资产面，兑现决策 #1 的空头主张）
- **in-build 单测 0 → 4 类 30 用例**（`EmotionLexiconTest` / `EmotionEngineTest` / `EmotionClassifierTest` /
  `SafetyGuardTest`），`mvn package` 从此自带门禁。此前从 09-20 立「可单测」为选 Java 的三条理由之一，
  到 09-26 实测 `server/src` 下 JUnit 用例数仍为 **0**、`pom.xml` 连 junit 依赖都没有 —— 是**能力声称**不是**产物**。
- **`_test/java_test_guard.py` 常驻**（盯用例数下限、`pom` 里 starter-test 在位、**CI 构建步不得带 `-DskipTests`**
  —— 否则门禁会在受理面上静默消失而本地仍看到"CI 全绿"）+ 新观测面 `peer_test_asset_probe`（实测 peers 有 in-build 单测 9/16、self 0）。
- 顺带两处：聚合器折叠补 `-` 续行与 stderr；`online_check` 的固定 sleep 改完成态轮询、整跑加并发锁。

### Added（r40d · 交付面九项覆盖机器化 + AGENTS.md 陈旧 P0 更正）
- **`_test/plan_pdf_coverage_check.py`（两条套件，电池 52→54）**：把清单第 1 行「官方 9 项逐项齐全」
  从人眼对照升级为常驻判据。九项**从 `应用方案大纲.md` 现读**（分母不手抄），页数由 pypdf 实数（20 ≤ 20），
  匹配按「章节序号 + 词块重叠」—— 首版按整串相等把已在的两项报成缺失（大纲与 PDF 同义不同字，M5⑧ 同族）。
  九向自证：误伤 1 / 漏报 4（删章、换无关标题、超页、缺项）/ 读空气 2（空文本层、空分母、取不到页数）
  / **取数形状 2**：`extract_text` 首版用 `""` 连页，把每页首行的章节标题粘到上一行 ⇒ 九章全部"查无"，
  判据差点把完好的 PDF 报成缺九章；改为 `
` 连接并加"非锚定扫描"守卫（形状可疑只能 UNVERIFIED，不判缺也不判绿）。
  依赖 pypdf 已登记 `_test/requirements.txt`（G11 会盯）。
- **`AGENTS.md` 07 段三行陈旧 P0 就地更正**：它写「缺件风险=PDF」「PDF 起草冻结待解冻」「前端未切 /api/emotion」，
  而 `memory/07-next-steps.md` 早已更正 —— 根因是 `handoff.py sync` 对本项目结构检测部分失效（08 已登记），
  07 段是 **09-22 快照**。已在文中显式写明"读 P0 以 memory/07 为准"，避免下一个 agent 又照快照行动。


### Added（r40c · 用户回传四条未闭环建议 → 全部落条 + push 后 CI 看守）
- **`_test/disclaimer_forensics_lint.py`（套件 +2）**：报告里 `不可比 / 无可比口径 / 受限于 / 仅保证 / 无法做到`
  类边界结论必须同句带实证标记（实测 · 逐文件 · 命令 · run 号 · 计数+单位 · sha/CRC），拿不出就改写成
  `未实测 + 取证路径`；`未实测`/`❌` 属诚实缺口，**不在拦截面**。8 类桩 + 恒绿守卫；
  **首跑就在自己报告里点名一处 r35 遗留**（§3.3 性能句），补上取证指向 §14.1 后才转绿；
  还自抓判据自身缺陷：`口径` 同时在被拦词表与白名单 ⇒ 句子会自己洗白，已移除。规则侧落 consulting-analysis V1.16.0（M5⑫）。
- **`_test/ci_watch.py` + `_test/push_and_watch.sh`（套件 +1：纯判定桩 6 态）**：把"push 后查 CI"从人脑挪到脚本——
  等结论 → 逐 job 点名 → `--log-failed` 抓失败面末 40 行 → 印四条下一步指令。
  退出码沿用电池约定：0 绿 / 1 红 / **2 未验证（无 run、超时、gh 不可用一律不当通过）**。
  实测 `CI-WATCH-GREEN | a6c4dc1d`；Trae 侧 IDE hook 需本机配置（无既定 schema，不猜格式），
  现以 `bash _test/push_and_watch.sh` 为强制收尾步（已写进 `memory/AGENTS.md` 推送纪律）。
- 其余三处规则落条：A-skill-manager **1.8.0**（铁律10 补"回落只读通道也要留实测证据"，
  反例＝只读门禁的 pass 其实是别人的合规）、cross-platform-agent-sync **1.5.0**
  （共写文件暂存面归属核对：numstat 只防多行裹挟，**同行覆盖时读数与自己一致、完全看不出**，夹具实测）、
  GM `scripts/secret_scan.py`（两类假阳性根除，selftest 5→9，`--all` 699 文件 0 命中）。

### Added（r40b · 判据可观测性 + 危机短路两侧合围）
- **G15 进 `repo_config_check.py`：AC 追溯键唯一性棘轮**（新增待办见 `07` 卷32）。
  起因是给自己加的 AC-OBS-23 顺手数了遍 id，实测 08 有 **30 条定义只用 23 个 id**——
  `AC-OBS-13/14/15/16/17/18/19` 每个都挂着**两条互不相干的命题**（如 19 既是"第三方库可溯源"
  又是"容器镜像真构建真运行"），而 `flow --verify-ac` 按 id 汇报并把整套数成 24 条
  ⇒ 三个数（30 定义 / 23 唯一 id / 24 被计数）互不相等，追溯键重复不是难看而是**判红不知道勾哪行**。
  存量 7 个 id 已脏（重编号牵动 README/05/07/CHANGELOG 交叉引用，另登待办），
  故本判据**只钉增量**：额外重复 > 基线 7 即红。合成篡改 +2（多造一条重复须红 / 零定义须红），
  `--selftest` 断言数由代码算得：**40 → 42**。
- **D 层：服务端危机短路契约**进 `engine_consistency_check.py`——冻结集 6 条危机样本逐条打
  `/api/emotion`，断言 `path=词典·危机拦截` + `llm=null` + `final=crisis`（实测 6/6 全中）。
  原先"危机短路"只有前端那半有 AC（AC-OBS-18 / W3b `attempted=0`），服务端这半无人钉
  ⇒ 新增 **AC-OBS-23** 把两侧合围。**双向变异已证**：期望标签改 `__mutated__` → 6/6 抓到，改回 → 0 命中；
  `--selftest` 另伪造「危机走了 LLM」响应 ×6 ⇒ 抓到 18 条。
  期望值**故意不从 Java 源码里读**（读源码自比 = 断言永真、改名抓不到），代码改名须同时改判据与 AC 文案。

### Added（r40 · 性能维从「未实测」变成有数有边界声明）
- **常驻判据 `_test/perf_baseline_check.py`**（两条套件，电池 47→**49**）：本地无外网四目标
  （静态首页 / vendor / `/api/health` / `/api/emotion` 危机短路）+ 8×6 并发吞吐。
  三轮实测：p95 **15.5–27.3ms**、并发 **2202–2484 rps**；阈值取实测 ~16–25 倍余量（吞吐地板 50 rps），
  **先量变异再接进阻断链**。口径守卫优先于性能断言：危机响应 `llm` 非 null 即判红、取不到算未验不判绿。
  `--selftest` 六向（百分位最近秩不插值 / 空样本 / 恒慢 / 缺面 / 口径漂移）。
- **PASS 行携带实测峰值**（r40 收口后追加）：电池每个套件只保留**最后一条**含判据词的 stdout，
  逐项明细行不进 CI 日志 ⇒ 首版在 CI 里只剩一句 PASS，看不见被检环境的数字，
  07 在册的「CI 首跑是否要重定基线」就无从判断。改判据行自带 `峰值 p95 / 最紧余量 / 吞吐`。
  **CI 首跑已读到数**（run `36245610695`：`p95=3.3ms｜余量 397ms｜1178.6 rps`）⇒ 该 P2 靠数字关闭，
  **不需要重定基线**；顺带量到两环境指标**不同向**（CI 延迟快 8×、本机吞吐快 1.7×）
  ⇒ 「禁跨环境引用绝对值」写进 `06-constraints.md` 性能口径红线。
- **报告新增 §14**：先量「能不能横向比」（16 仓两通道；性能工程件语境归因后仅 sapphire 一家明确，
  无一家公开可比数值 ⇒ 本维不可横向比较，禁止产出「比某仓快 N%」式结论），再量自身基线。

### Fixed（r40 · 两处我自己差点写进文档的错）
- **危机样本选自臆造句而非冻结集**：首版用「我真的撑不下去了，不想伤害自己」（否定式，未命中危机词表）
  ⇒ 打到 LLM，量出 p95 772–905ms，并被我自己误读成「服务端危机没短路」。读 `EmotionClassifier` 确认
  存在 `词典·危机拦截`（llm=null）后更正归因，改用冻结评测集真危机句「感觉活着好累，不想活了」
  ⇒ `llm_used=False`、p95 落回 16–25ms。**守卫没错，是样本错**——守卫的价值正在于此。
- **一次性探针匹配器有假阳性**：`bench` 命中 `workbench`（28 条）、`Performance` 命中 NuGet 带入的
  `System.Diagnostics.Performance*.dll`（7 条）⇒ 原始计数不可用；报告只写归因后的结论并标明探针未入电池。
- 口径混用一并核对：`emotion_wiring_check` 的「危机不经后端」讲的是**前端**路径，
  与本次实测的**服务端** `/api/emotion` 短路是两个命题，报告已分别表述，不再互相顶替。

### Changed（r39 · A-project-better 遗留盘点轮：文档追上构建 + 体量收口）
- **05 三条「仍存差距」实为已完成**（`/api/emotion` 前端接线 / PWA 离线壳 / `app.js` 模块化拆分）：
  逐条命令取证后按删除线保留原文 + 标注实测状态，明细迁 `05…part12.md`（R241 留痕不改写）。
  这是 R240 的反向形态（磁盘有、文档没回扫），由 Step 0 盘点当场抓出。
- **README 回到每轮注入预算内**：`## ✅ 验证` 一节（4,745B）整卷逐字迁 `docs/quality-gates.md`
  并在 `docs/README.md` 建索引（不留孤文件）；README 19,531B → **15,454B**（预算 16,384B）。
  07 索引壳经 `handoff.py trim-shell` 3,845B → 2,633B。**AGENTS.md 27,411B 未强推**：
  `handoff.py handoff` 主动识别它为人工索引壳并拒绝覆盖，该边界优先于"把数字做绿"。
- **回收 81,005,106B 可再生中间件**：`demo_video_raw.webm`（25,800,267B）与
  `demo_video_out/video_raw/` 7 个逐轮帧件（55,203,953B），全部实测 gitignored 且未被跟踪，
  按回收区约定迁 `_trash/`，**移动前后拼接 sha256 相同、原位清空**；成片 mp4 未动。
  整仓 227,817,951B → 146,815,984B（`handoff.py volume` 现测）。

### Added（r39）
- **Docker 面从"文件名存在"升级为"CI 每轮实测"**（接续 part26 的 P2「一键起的实测面」）：
  `java-build` job 末尾新增两步 —— `docker build -f server/Dockerfile`（context=仓库根）与
  **容器起服三项自证**（`"status":"UP"` / `"indexFound":true` / `"vendorFound":true` + 首页 200）。
  只 build 不算数：COPY 路径、jar 是否 repackage 成功、镜像内前端是否真命中，都要跑出来才有回执。

### 盘点过程中撤回的一条误判
- 由 `handoff.py help trim-shell` 报 `Unknown command` 我一度判定"体量判据的处置建议指向不存在的命令"，
  准备按高优先缺陷落进 skill。**核实分发表后撤回**：`trim-shell`、`volume` 都在册，
  我第一次只看了 `--help` 的前 25 行。真缺陷小一号但仍存在：**`help <在册命令>` 回 Unknown**
  （`help trim-shell` / `help recycle` 同形），会让"先跑 help 现读"这条护栏给假阴性 —— 已登记待办，
  属主侧修，本轮不代改他人脚本。

## [1.4.3] - 2026-09-26 — 对标轮 r38 续：护栏判定前移，CI 无密钥也能实测

### Fixed（r38 续）
- **CI 复跑证明新判据在 runner 上只能记"未验"**（run `36239668456` 浏览器回归 job 判红：
  `safety_guard rc=2 ENV-UNVERIFIED`）。根因是我把护栏判定放在密钥检查**之后** ⇒
  runner 没有上游密钥，请求在到达护栏前就 500 返回。
  修法不是把它塞进豁免名单（那等于 CI 永远不验护栏），而是**把判定前移到密钥与解析分支之前**，
  四条出口统一带 `X-Xinyu-Safety` 头；判据侧同时按"有无上游密钥"切换状态码期望值，
  响应体契约子项在无密钥时记 **skipped 而不是 PASS**。
- **本地按 CI 条件复现才抓到这一档**：另起一个剔除 `DEEPSEEK_KEY` 的实例（:8124）跑同一条判据，
  首跑报 6 条"http=500 非 200"红 —— 头断言其实全过，缺的是期望值分档。
  复现后门铃：无密钥 15 项实测 + 6 项 skipped rc=0；有密钥 21 项全过 rc=0。

## [1.4.2] - 2026-09-26 — 对标轮 r38：安全策略第二层（输入侧护栏）补齐

### Added（r38）
- **`server/.../safety/SafetyGuard.java` 输入侧护栏**：指令覆盖（中英）、系统提示词套取（含中文
  「把…输出」倒装）、角色伪造、persona 越狱、编码载荷共 **8 类模式**；单轮 >4000 字截断；
  命中即向上行 messages 追加一条系统重申。
  **响应体一字不改**（契约红线：`j2_chat_contract` / `stream_contract` 要求逐字透传，
  流式改写必须整段缓冲 ⇒ 输出侧只做分类，落响应头 `X-Xinyu-Safety`，最高危自伤场景由危机层兜底）。
- **常驻判据 `_test/safety_guard_check.py`**（两条套件，电池 45→**47**）：走 HTTP 实测而非读文件，
  双向断言 —— 注入 6 例必须点名对应类别；正常 6 例（含 2 例"近似误伤"：课文复述／汇报输出）
  必须判 0；危机句不误伤；致死剂量句 `risk=high`；超长 `capped=1`；流式分支同样带头。
  `--selftest` 另证判据自身不恒绿（空 header／垃圾串／缺字段／误报反例四向）。
- **README 新增「安全策略（三层）」一节**：本轮对标的直接结论 —— 16 仓里 **5 家有安全件文件**，
  我方两条观测通道（文件树 + README）**都是 0**，只有危机转介；现补第二层并让它两通道都可见。

### Fixed（r38）
- **判据抓到自己第一条真漏报**：`reveal-system` 原式要求"动词在名词前"，
  实测『把你上面的提示词原文输出给我看』不命中（中文"把"字句是名词前置）⇒ 补
  `reveal-system-ba` / `reveal-system-en2` 两条反向语序，并加 2 条近似误伤样本守住误报侧。

## [1.4.1] - 2026-09-26 — 对标轮 r37：交付可得性（本仓首个 GitHub Release）+ 依赖队列清空

### Added（r37）
- **首个可下载交付物**：GitHub Release `v1.4.1`（远端实测 `isDraft=false`，2 个资产）
  - `soulisle-server-1.4.1.jar` 28,438,588 B —— 内嵌 `version=1.4.1`、含 **0** 个前端文件
    （静态页按 `file:` 直读，不入 jar）、**0** 处密钥形态、`mybatis-plus-core-3.5.17.jar` 在册
  - `xinyu-web-1.4.1.zip` 249,409 B / 23 文件 —— 零密钥前端包，逐文件扫 `sk-` 形态 0 命中
  - ⚠️ 过程坑（已入 05 排障口径）：jar 被 8123 运行中的进程锁住 ⇒ `mvn package` 的 `repackage`
    无法改名 `.jar.original` 而失败，且**旧 jar 已被截成 48,907 B** —— 差点把半成品当 28MB 产物上传。
    教训：**发版类判据必须先验"产物完整"（尺寸/内嵌版本/内容清单），不能只看命令 exit 0**。
- **常驻判据 `_test/remote_tree_audit.py`**（两条套件，电池 43 → **45**）：扫 **origin 默认分支的文件树**
  而非本机 `git ls-files`。动因是本轮实测到两件事叠加：仓库名叫 `private-archive` 而 visibility 实为
  **PUBLIC**，而 `.gitignore` 只挡"以后再 add"、**不会把已推上去的东西从远端拿掉** ⇒
  "本机 ignore 到位"与"评委看到的树干净"是两个命题。deny-list 7 条 / 放行 2 条
  （`.env.example` 与零密钥 `deploy/xinyu/js/demo-config.js` 不得误伤）、空树或 `truncated=true` ⇒ rc=2
  不判绿。实测远端 **230 个 blob 零命中**。自证被自己的**假反例**打回一次（样本 `public/x.png`
  本不在禁用面）⇒ 换成 `_test/_shots/lit_single.png` 才是真命中。
- **对标新观测面探针 `_test/peer_hygiene_probe.py`**（人工轮次工具，不入电池：16 仓 × ~20 次 API 太贵）：
  发布可得性 / 维护响应 / 工程治理，分母 `import` 自台账 `PEERS`（不另立清单），每字段独立取数、
  失败记 `NA(原因)` 并计入 unverified。第一版只查根目录 ⇒ 把 self 判成"一键起=none"而
  `server/Dockerfile` 实际存在 ⇒ 改为对所有仓统一探 `"" / server/ / docker/ / deploy/` 并打印命中路径。

### Fixed（r37）
- **依赖队列清空 3/4**：#4 mybatis-plus `3.5.7→3.5.17`、#1 `actions/checkout 4→7`、
  #3 `actions/setup-python 5→7` 合并（三次 push 的 CI 逐项 success）。#3 与 #1 同改 `ci.yml` 冲突 ⇒
  用 `@dependabot rebase` 让工具自己 rebase 后再合，不在他人分支上手解冲突。
  **#2 Spring Boot `3.2.5→4.1.1` 判为截止前不合并**（主版本语义变更 + v2 后端非演示主路径 ⇒ 收益≈0 风险实），
  登记为赛后项并写明重评触发条件。
- **版本三源对账当场拦住中间态**：pom 改 1.4.1 而 tag 尚未打时 G12 如实判红
  「发版链断在中间」⇒ 提交 + `git tag v1.4.1` + `git push origin main refs/tags/v1.4.1`（单事务推两 ref
  避免"CI 先跑、tag 后到"的竞态）后转绿。**这是判据按设计工作，不是故障**。

### Fixed（r36 · 对标轮 2026-09-26：行尾确定性 —— 让"逐字节/SHA256/字节预算"类主张在别人机器上也成立）
- **工作树字节与机器无关**：`core.autocrlf=true` + `* text=auto` 下，工作树是 CRLF 而仓库 blob 是 LF ⇒
  本机"逐字节相等"的判断在他人 clone 上会**整体反向**。现钉 `.gitattributes`（`* text=auto eol=lf` +
  `*.sh`/`*.ps1` 强制 LF + 20 类扩展名显式 `binary`），108 个文本文件 `git add --renormalize` 归一。
  **归一零内容改动**的证明：`git diff --name-only` 与 `git diff --ignore-cr-at-eol --name-only`
  文件集相同（只差本轮两个有意改的文件）。跨检出复验：两份 clone 分别按 `autocrlf=true` / `input`
  检出后文本侧字节一致。
- **归一过程自己造成过一次二进制损伤（已还原并固化为判据）**：首轮 renormalize 把 20 个二进制里出现的
  `0D0A` 字节当行尾剥掉（PNG/MP4 各少 1–2 字节），而"两侧都归一再比"的守卫**看不见这种损失**
  （两侧被同样地破坏了）。全部从 `git show HEAD:` 还原（复核余 0 条不等），并把该形状写成规则 **E3**：
  含 `0D0A` 却未声明 `binary` 的文件 ⇒ 判红；同时撤销我一开始过严的另一半（"声明 binary 就必须含 0D0A"），
  两侧各配夹具用例钉住。
- **新增常驻判据 `_test/eol_parity_check.py`**（`eol_parity` + `eol_parity_selftest` 两条套件）：
  E1 属性表须有 `eol=lf` 与 `binary`；E2 文本侧工作树无 CRLF 且 `工作树 == 仓库侧 blob`（在途改动放行，
  但在途且带 CRLF 仍点名）；E3 上述 binary 形状；E4 分母闭合 `text+binary==total`，git 读空/失败 ⇒ rc=2 不判绿。
  8 类样本自证。当前实测 `text=205 binary=20 total=225`。
- **三处落仓库文本的写盘口改 `write_bytes`**：`Path.write_text` 在 Windows 文本模式把 `\n` 翻成 `\r\n`
  （实测 `b'a\n'` → 落盘 `b'a\r\n'`），**一次写入就把刚归一好的 LF 打回 CRLF**。判据接上就当轮抓到
  `交付物/对标数据/benchmark-metrics.json`。按"修一类不修一例"枚举全部同类出口：台账（`benchmark_metrics.py`）、
  **补丁器**（`patch_apply.py` — 影响面最大，且它的"写后读回复验"用 `read_text`，universal newlines 会把 CR
  读成 `\n`，**复验步骤自身正好掩盖该缺陷**，故写与读同时改按字节）、演示流水线（`demo_video_pipeline.py`
  的 `timeline.json` / `subtitle.ass`，两文件均已入库）。`patch_apply --selftest` 六类 → **八类**
  （⑦LF 输入打完仍 LF / ⑧CRLF 输入被归一），README 同步。
- **电池入口由 fail-open 改 fail-closed**（`run_all_suites.py`）：`--help` 无实现 ⇒ 被当未知参数**静默忽略并
  把 43 条全跑一遍**（本轮撞上）；同理 `--onl selftest` 这类打错字会跑成全量还打印 `ALL-GREEN`，
  即"子集全绿"被说成"全量全绿"。现：未知开关 / 缺操作数 / `--slice 99 120` 越界（Python 切片会静默截成空集）
  一律 rc=2，并补 `-h/--help`。摘要行另修一处：由"最后一行"改取"最后一条判定行"，
  因 `strategy_selftest` 在 PASS 之后还打印注入反例，rc=0 却显示 `· 热线清单需 ≥3 条，实际 []`（看着像报错）。

### Changed（r36 · 公网与受理面）
- **公网按 LF 重部署，"线上 == 权威源"从此不依赖兜底分支**：`cd deploy && npx wrangler pages deploy xinyu
  --project-name=xinyu-soulisle --commit-dirty=true`（日志含 `Uploading Functions bundle`）。
  `live_sync_check` 由 `live=9463 / local=9288｜仅行尾差异 ⇒ PASS`（走 `eol_only` 容差）转为
  **`live=9288 == local=9288 equal=True`**；`public_check` / `online_check` / `offline_shell_check`（17 项 0 失败）
  / `deploy_sync_check` 同步复绿。回滚锚点 = 上一版生产部署 `b5f46ecf-d1dd-46ee-b700-10a3d2914e56`。
- **对标语义补测（本轮新参照数据）**：16 个参照仓根目录 `.gitattributes` 逐个 `gh api` 探测
  （按 HTTP 状态分 ABSENT/PRESENT，base64 交 Python 解）⇒ **存在 6/16，真钉行尾/二进制 4/16**
  （lobehub / leemo / opensoul / MoodChat，其中 MoodChat 钉的是 `eol=crlf`）。
  即"钉行尾"在同类项目里是少数派，但工程化最强的那个在做 ⇒ 本轮做法与头部同形，非自创规矩。
- **`live_sync_check` 的对账面从"1 个文件"扩到"页面引用的全部 19 项"**：原判据只对 `/` 比字节，
  对引用的 js/css 只查 HTTP 200 **从不比字节** ⇒ "线上 == 权威源"这句一直只由首页支撑。
  现分母**从页面现读**（13 `js/` + `css/` + 3 `vendor/` + 2 `data/` + `manifest.webmanifest`），
  逐字节对账并分四类点名（相等 / 仅行尾差异 / 缺失 / 内容漂移），实测 `引用 19 项 | 逐字节相等 19`。
  三条变异体：加内容 ⇒ rc=1 并给出 `live=13449B local=13468B`；整文件换 CRLF ⇒ 计入"仅行尾差异"后仍 PASS；
  还原 ⇒ 19/19。过程中两次被自己的反例打回：第一版反例用"追加 `\r\n`"（那改的是结尾换行，测不到容差分支），
  第一版正则把前缀扩到 `data` 后 `href="data:image/svg+xml,…"` 被当路径取数（假 URL 打断全部断言）。
- **本机 43 套件全量复跑**：`--slice 0 22` ⇒ 22/22、`--slice 22 43` ⇒ 21/21 ⇒ **43/43 rc=0 ALL-GREEN**；
  台账重采 `BENCHMARK-METRICS-PASS`（`电池套件=43`，漂移 3 处 = 实质 0 + 抖动 3）。

### 受理面（r35 收口，实测）
- **四条 CI job 首次在 HEAD 上全绿**：run `36220200506`（sha `7aac7d2`）`conclusion=success`，
  四 job 逐项 success；`ci_status_check.py` 由 `CODE_FAIL` 转 `CI-STATUS-PASS`（rc=0）。
  上一轮登记的"只有老大能解（账单/配额）"至此闭环——真因不是配额，是三条代码级缺陷。

### Fixed（r35 · 对标轮 2026-09-26：受理面三条 CI 真红逐条归因）
- **CI 密钥门禁被自家判据夹具命中**：`_test/pdf_leak_scan.py:91` 的反例样本写成连续的 `sk-`+24 位字面量，
  而同步守卫 job 的密钥扫描扫的是 `git ls-files` ⇒ **跟踪文件里最像密钥的东西是"检测密钥的判据"本身**，
  两条 job 因此连红 5 次 push（本机 37 条套件全绿看不见）。修法三层：样本改拼接 +
  新建 `_test/tracked_secret_scan.py`（分母非空断言 / 逐条 `路径:行号` / 四类边界自证）+
  `ci.yml` 改为调用该脚本 ⇒ **CI 与本地从此同一把尺**（原先同一判断两处实现，只有一处会红）。
- **`voice` 判据的 CI 降级没盖住 A4**：A7 有"无麦克风 ⇒ SKIP"，A4 没有 ⇒ CI 上 `error:audio-capture`
  让 `recording` 类根本不可能出现却判红。抽出纯函数 `no_input_device(ev)` 供两条共用，并**顺手收紧**：
  `not-allowed` / `service-not-allowed` 不再算环境借口（那是权限被拒，演示当天真会挂）。
  新增常驻套件 `voice_selftest`（5 例，含"本机同错误仍判红""权限类不降级"两个反向方向）。
- **`settings_panel` 四条 CI 红：登记为未归因，不声称已修**。已排除 `demo-config` 变量（换 CI 版 stub
  本机复跑 9/9 绿，按 sha256 还原）；给判据装上"完成态等待 + 报红时自动附现场
  `{open, returnValue, saveDone, domBase, cfg, ua}`"，并补两类反例（⑥ 竞态实测、⑦ 保存不关窗必超时）。
  推送后实测（run `36219657886`）：加了完成态等待之后 CI 上那四条**消失** ⇒ 修法有效已被受理面证实，
  但机制解释仍不完整（本机测不到该差异，CI 侧等一下就绿），故只写"有效"不写"已解释"。
- **电池收口行把"判红"与"环境未验"分开**：`ci_status` 长期挂红期间原因换过（账单阻塞 → 代码级失败），
  而收口行两次的样子一样（`RED: ci_status`）⇒ 换原因的常红被自己的措辞吞掉。现分三类打印
  `ALL-GREEN` / `RED(判红，必须修)` / `ENV-UNVERIFIED(不是判红，但不得声称已验)`；
  **本条自己也被实测证伪过一次**：第一版写"非 1 即环境"，随即两条套件硬崩（`rc=0xC0000409`、stdout 全空）
  被判成"环境未验" ⇒ 补第三类 `CRASH(判据自身崩溃，必须查)`，并用合成四态套件双向验。
- **新增前置探针 `_test/server_preflight.py`**：跑判据中途本机 fat jar 掉线，一次报出 5 条红
  （`api_contract` / `settings_panel` / `settings_panel_selftest` / `offline_shell` / `ci_status`），
  失败面各不相同（Playwright `ERR_CONNECTION_REFUSED`、urllib `WinError 10061`），归因花三轮命令。
  现由电池第一条说清："服务不可达 ⇒ 依赖它的套件本轮全部算**未验**"，并按 rc=2 归入 `ENV-UNVERIFIED`。

### Changed（r35 · 文档与判据账本）
- **G12 版本断言三源对账**（`git tag` == `server/pom.xml` == 文档「当前版本」）：实测 `ROADMAP.md` 停在
  **v1.3.0** 而 tag/pom 均已 **1.4.0**，改文档后转绿；`--selftest` 篡改⑭ 六例含"全仓零断言不得判绿"。
- **G12 自己也被 CI 抓到一次假红并当场修**（首轮 push 后 run `36219657886` 的唯一红就是它）：
  首版只跑 `git tag`，而 `actions/checkout@v4` 默认不拉指向旧 commit 的 tag ⇒ CI 里返回空、判据报"读空气"。
  修法不是放宽判据，而是**补一条权威面**：本地无 tag 时改读 `git ls-remote --tags origin`，
  并把解析抽成纯函数 `pick_latest_tag()`（同吃 `git tag` 单列与 `<sha>	refs/tags/X` 两形态 /
  跳过 `^{}` 剥离行 / 按数值而非字典序比 minor）+ 四条新反例 ⑯a–d
  （其中 ⑯b 当场抓到该函数对空格分隔的容错缺失）。
  ⇒ 本轮报告批评的那族「判据带环境假设、本机恒真 CI 恒红」，我自己当天又踩了一次，被 CI 拦下。
- **G13 判据账本自洽**（头部登记 == `main()` 实际执行的 `check("G..")`）：上线当轮即抓到两处自身缺陷 ——
  G7 因 `check("G6+G7 …")` 合并项被首版正则漏取（判据过敏，按 R263 先修判据不动登记），
  以及 G11 落地时从未写进头部清单（漏登记）。
- **ROADMAP 补「更正注」**：`⚠️ 撤下两项` 段里「PWA / service worker 撤销不做」已被 r28 的只读离线壳推翻，
  却与同文件第 94 行（离线壳已交付）并存且无更正注 —— 违反该文件自己第 156 行的纪律；现按
  "保留原文 + 更正注 + 写明真实路径（同一条 `pwa_offline=0/16` 被反读成差异化机会）"补齐。
- `ci.yml` 电池步骤名去掉手抄数字（写死"30 条实跑 + 3 条豁免"，实际 34+3；条数由脚本自证恒等式）。
- README 三条状态性表述按 R242 回扫：删除"四条 job 均在 GitHub 真跑验证"这类会随受理面变色而失效的写法，
  改为"以 `ci_status_check.py` 读回的远端判定为准"；套件数 37→40 由 G4 机器对账。
- `memory/05-feature-status.md` 追平 r29–r35 构建（07 登记的 P0 自驱项）：主壳新增「当前构建状态」权威段，
  r20–r28 各轮残段逐字迁 `part10.md`；主壳 3,798B ≤ R161 的 4,096B，逐行复核**原始行丢失 0**。
- 电池 37 → **40** 条（新增 `tracked_secret` / `tracked_secret_selftest` / `voice_selftest`）。


### Changed（r34）
- **演示成片再录**：r30 成片录于诚实性修复之前，画面仍挂旧标签；r34 重录后画面含「本机开场白 · 未经大模型」
  与「● 在线 AI」，`RECORD-PASS scenes: 8` / `ffprobe 218.48s` ≤300s，提交清单第 2 行指纹与三代际已更新。
- `memory/AGENTS.md` 排障手册撤销一条错误归因（全角冒号让块隐形），改记真因（锚点行尾多写说明文字）；
  判据侧升级落在 skill：`A-memory-start V10.74.0` —— 报因给可疑行号 + `require_mark` 由子串改整词匹配
  （实测短标识被同卷长标识当前缀吃掉 ⇒ 门禁假绿）。
- `memory/07-next-steps.md`：r34 待办转完成，新登记「05 功能状态须追上 r32/r34 构建」为下一件；
  壳体量 3,951B ≤ 4,096B 阈值（细节不重复抄，权威在提交清单）。

### Fixed（r33 收尾）
- **对标 r33 footer 落错卷**：GM 端 footer 被写进「明天」的卷且 ts 手写 ⇒ 对零参数默认门禁不可见。
  已在当天卷重落，并给门禁加未来日卷阻断（判据升级落在 skill 侧，本仓只留痕）。
- `memory/07-next-steps.part17.md`：fat jar / 容器部署待办补齐「三件套」（执行目录 / 日志必见证据 / 回滚锚）。

> 对标 r33（2026-09-25 第十四轮）：**公网重部署追平本地** —— r32 改的降级徽章与诚实标签此前只在本地，
> 公网仍是旧版；本轮上线并四项复验。外部漂移 **0 处**（首次连 ★ 都没动，但两次采集只差 22 分钟，
> 不能读成"对手停止演进"）。

### Changed
- **公网部署**：deployment `b5f46ecf`（回滚锚 `ec881aaa`）。部署前发现一个会让线上挂掉的坑：
  `deploy/xinyu/` 里**没有** `functions/` 目录，Functions 源在 `deploy/functions/`，
  wrangler 的 Functions 目录是**按 cwd 解析**的 ⇒ 必须 `cd deploy` 再 `npx wrangler pages deploy xinyu ...`；
  部署日志须出现 **`Uploading Functions bundle`**，否则 `/api/chat` 会在新 deployment 里消失（404）。
- 复验四项全绿：`live_sync_check`（线上 `/` 与本地 `index.html` 逐字节等 9,463B）、
  `public_check`（浏览器级：标签实测「在线大模型生成 · 逐字流式 · 词典+LLM 分歧 → 采信 LLM · 2184ms」、
  危机 True、CONSOLE_ERRORS 0、KEY_LEAK False）、`POST /api/chat` 200、
  公网 `app.js` 含「网络不可用」×3 / `chat-window.js` 含「本机开场白」×1（证明 r32 两处修复**在线上生效**）。
- 提交清单第 3 行的验收判据改为**带部署命令与 Functions 守卫**的可复算式，并记下 deployment id。

### Fixed
- **自抓一条"拿旧数当本轮结论"**：本轮第一次读快照算漂移时，误把 r31→r32 的差当成 r33 的（快照末条 ts
  是上一轮的），核对 ts 后重采两次（11:12 / 11:13 UTC）才取到本轮真值 0 处。
  教训：`与上一次快照比对` 必须先证明"上一次"确实是上一轮，而不是"文件里最后一条"。

### 下一件（已登记 07）
- 成片（217.6s）录在 r32 徽章/开场白修复**之前**，画面里仍是「在线 AI · 共情模式」旧标签
  ⇒ 按刚落地的 consulting-analysis M6「材料须追上构建」，下一件重录成片。

> 对标 r32（2026-09-25 第十三轮）：**交付物回扫（R242）** —— 方案正文对三项已建成能力 0 命中，
> 顺手抓出两处"伪装在线"出口并机器化封死。外部漂移 4 处 = 实质 1（`my-neuro` 今日推送：移除 PyQt 桌面 UI、
> 转 Web UI + 插件广场）+ 抖动 3 ⇒ 对手正往"浏览器化 + 扩展生态"收敛，印证可扩展性维度的既有差距，
> 但 5 天内不可行动（登记为赛后项）。

### Added
- **方案新增 6.7「离线可用：浏览器应用壳」+ 7.8「评委自助：设置面板与模式自证」+ 实拍图 8/9**，
  7.3 补 SSE 逐字流式一句；6.6 耗时行由单次样本改为**两次独立实测区间**（965 ms / 1,378 ms）。
  动因是 grep 实测：`sw.js`/`Service Worker`/`PWA`/`逐字`/`流式`/`设置面板` 在 `application-plan.html` **0 命中**，
  而"离线"那 21 处全部指**离线降级模板**（§7.6），不是 r28 交付的应用壳。
- **`_test/pdf_leak_scan.py`（新常驻判据，电池 35 → 37 套件）**：解 FlateDecode 流抽 PDF 可见文本，
  扫 `file://` / Windows 家目录 / `sk-` 密钥 / 邮箱 / 手机号；**零输入不得判 CLEAN**（可抽文本 <2000B 即 UNVERIFIED）。
  自测三侧：正例含字体噪声串不误报、五类真敏感全抓、`12356` 与 `%@P`/`c-@g.Bk` 不被误抓。
  落地过程中两轮误报（字体子集名被判成邮箱）都是**先改判据再下结论**，没有放宽判据求绿。
- **`_test/rescan_shots_check.py`**：出图前机器断言（预缓存 ≥17 项才允许断网、断网后五幕结构在、
  零 `XINYU-SHELL-MISS`、Key 框 `value` 为空且 `type=password`、截图面零密钥串），先落 `_shots/` 目检后才进交付物。
- **`render-pdf.ps1` 期望图数改为从 HTML 现读 `<figure>`**（原手抄"预期 8 张"，加图后必成假告警），
  并加"数不到 figure 即判不可信"的空输入守卫。

### Fixed
- **两处"伪装在线"出口（红线级，同类出口已枚举全仓确认只剩这两处）**：
  ① 引擎徽章只看配置不看网络 ⇒ 断网重开仍显示「● 在线 AI」（截图当场抓到）；改为
  配置在线 + `navigator.onLine === false` 时显示「● 网络不可用（配置为在线）」并注册 online/offline 事件回灌，
  `navigator.onLine` **只用于降级、不用于宣称在线**；② 开场白标签硬编码「在线 AI · 共情模式」，
  而该句从不经过模型 ⇒ 改为「本机开场白 · 未经大模型」。判据 `offline_shell_check` 新增 **R10a/R10b/R10c**
  （R10a 是反向断言：联网态仍须显示「在线 AI」，防我把分支写反造成恒绿）。
  变异体双侧实测：摘掉网络分支 → R10b 翻红；标签改回伪装文案 → R10c 翻红；还原后全绿。
- **G9 当场拦下我自己新写的脚本**（`rescan_shots_check.py` 顶层执行 + 无 `__main__` 守卫）——
  r26 那族第五次复发形态由判据自动抓住，已包成 `main()` + 守卫。
- 图序缺陷：新加的「图 8」原本落在 §6.7，排在旧图 1–7 之前（文档顺序倒置）⇒ 移到 §7.8 之前，
  正文改交叉引用「实拍见图 8」；判据改为按 `<figcaption>` 断言图注单调递增。
- `README.md` 三处状态性数字按本轮实测更新（35→37 套件、r20–r27→r20–r32、首屏 819,767→832,373 B）。
- `src/js/app.js` 体积预算按既有口径（实测基线 ×1.05）由 13,780 上调至 **14,390**，理由写进表内注释与本版；
  徽章修复使 app.js 13,123→13,698B（余量仅 82B 会让下一轮任何一行改动都撞墙，故按算法重设而非凭手感抬）。

### 交付物
- PDF 重渲染：**20 页 / 9 图 / 2,022 KB**，满足 ≤20 页硬约束但**已贴上限**（再加内容必须先精简）；
  文本层泄露复扫 `PDF-LEAK-CLEAN`（输入非空已证）。旧 PDF 18 页 / 8 图。
- ⚠️ **公网副本落后本地**（`app.js`/`chat-window.js` 已改、PDF 已重做）：部署属线上动作，本轮未执行 ⇒
  已登记 07 P0 为下一件，且**不在文档里声称两端一致**。

### Known issue（待老大，非代码）
- GitHub Actions 账户账单/配额未解 ⇒ HEAD 最近 run 仍判 `ENV_BLOCKED`，r28 的 CI 覆盖面修复**至今无法在受理面验证**
  （复算 `python _test/ci_status_check.py`；本轮电池那条红仍是设计如此，不放宽）。
- iCAN 报名名单 PII（五人学号/手机号/邮箱 + 指导教师 ≤2 非成员 + 官网填报登录态）只有老大能给；
  PDF 署名页需在 PII 齐后重渲染。
- 公网部署需凭据与线上确认：本轮改了 `app.js`/`chat-window.js` 与 PDF，**公网仍是旧版**，故不声称两端一致。

> 对标 r29–r30（2026-09-25 第十、十一轮）：**受理面优先** —— 查 CI 真结论，查出"CI 全红"其实是
> GitHub 账户账单导致 runner 从未启动；同时清掉我自己写进聚合器的 3.12-only 语法。外部漂移全为 ★ 抖动。

### Added
- **离线能力的「第二条观测通道」（r31）**：`pwa_offline=0/16` 原本只靠**文件名法**
  （`sw.js|service-worker.js|serviceworker.js|sw.ts`）—— 而 r30 刚证明文件名法会假阴性，对自己如此，对参照仓亦然。
  新增 `offline_signal_class()`（纯函数，读 description+README）把 "offline" 分四类
  `app_shell / local_models_offline / ml_training_offline / none`，**先归因再计数**；台账 `--offline-audit` 跑，
  结果只写快照 `runs[-1].offline_audit` 与复核行，**不参与 `caps` 计数**。实测 16 仓：
  `app_shell=0`、`local_models_offline=1`（Open-LLM-VTuber「run completely offline using local models」，
  桌面自托管形态而非网页壳）、`ml_training_offline=1`（hello-diana/MASCOT 的 **offline DPO 训练** = 误报源）、
  `unverified=0` ⇒ 差异结论从"单观测法 + 手工抽查 1 仓"升级为"双独立通道 + 逐仓点名"。
  判据自证：四类各一合成样本 + 两条反向（训练语境不得判成离线壳 / 真 SW 语境必须判成离线壳）+ 零输入判 `none`；
  两个变异体（恒判 app_shell、恒判 none）实测 `SELFTEST-FAIL rc=1`，还原后 rc=0。
  复算：`python _test/benchmark_metrics.py --selftest` + `python _test/benchmark_metrics.py --offline-audit`
- **`_test/ci_status_check.py`（K1–K4，电池 33 → 35 套件）**：把"CI 红"分成 `CODE_FAIL` / `ENV_BLOCKED` / `PASS`
  三态。ENV 判据 = 全部 job 在 15s 内失败 **且** run 的 ANNOTATIONS 命中账单/配额类措辞 ⇒ rc=2，
  并明写「本轮不得声称 CI 已验」。结论只取 HEAD 那次 run（历史红只作上下文）；在 CI 内部自动 SKIP（自指）。
  自证含两条反向断言：去掉账单措辞必须翻判 CODE；不 SKIP 就 selftest 红。实测三态均正确。
- 离线壳能力的台账自证：`benchmark_metrics.py` 的 self 行现已报 `caps=...,pwa_offline`
  ⇒ "16 个同类都没做的能力我们有"这句话由台账复算，而不是写在报告里自说（r28 的 claim 至此闭环）。
- **`benchmark_metrics.py` 的「盲区点名」（r30）**：能力匹配器只看文件路径，对我们有两类是**假阴性**
  （SSE 写在 `chat.js`/`ChatController.java` 里、文件名不含 sse；浏览器端到端在 `_test/*.py` 里用
  playwright、路径不含 e2e）。新增 `blind_spot_caps()` **读内容取证据**，在 self 行打印
  `盲区点名：e2e_browser,streaming`，但**不计入 `caps`** —— 横向对比仍用同一把尺，给参照仓"读内容"就是双标。
  自证三侧（有证据→点名 / 无证据→空 / 已看见→不重复计数）；三个变异体（恒空 / 恒报 / 不去重）实测都被抓住。
  复算：`python _test/benchmark_metrics.py --selftest` + `python _test/benchmark_metrics.py`

### Fixed
- **演示成片重录（交付物变更，r30）**：旧片画面仍是**情绪后端化之前**的，而"后端引擎 + 同源代理在线"才是最有
  说服力的两点差异 ⇒ 按 07 P0 登记的那件自驱项重录。8 幕 `RECORD-PASS`、`ffprobe` **217.56s**、
  成片 `sha256=fc810f65…`（替换旧 `50e060d1…`）；S3 画面标签实测
  `在线大模型生成 · 逐字流式 · 情绪双路：词典+LLM 一致 → LLM · 情绪:后端 · 1378ms`。
  含一次**真实失败**：第一次把代理写成绝对 URL `http://127.0.0.1:8123/api/chat`，页面在 `localhost:8123`
  ⇒ 跨源且 `/api/chat` 无 CORS 头（curl 带 `Origin` 实测），S3 落进「离线共情模板」被断言拦下 rc=1；
  改**同源相对** `/api/chat` 后通过。教训："同源代理"的同源是 **URL 形状**的属性，不是端口的属性。
  录制环境的切换/还原按 sha256 机器核验（`2521954c…` 前后一致），录后 `public_check`/`live_sync`/`deploy_sync` 全 PASS。
- **聚合器自己是 3.12-only 语法**：r28 给失败明细写的 `print(f"{" " * 25}· {d}")` 依赖 PEP 701，
  本机 3.12 全绿、CI pin 3.11 直接 SyntaxError（30 条判据一条没跑）。改字符串拼接；
  另全仓扫两类 3.11 雷（嵌套同引号 f-string 1 处已修、f-string 花括号内反斜杠 0 处），
  并在 CI 最早一步加 `python -m compileall -q _test`（版本兼容差要以最小失败面暴露）。
- 交付物 `G4`/`G10` 数字随套件数同步（README 声称 35 == 实测 35；CI 恒等式 实跑 32 + 豁免 3 == 35）。

### Known issue（待老大，非代码）
- GitHub Actions 连续 3 次 run 判 `ENV_BLOCKED`：annotations 原文
  "The job was not started because recent account payments have failed or your spending limit needs to be increased."
  ⇒ r28 的 CI 覆盖面修复**至今无法在受理面验证**；本轮不声称已验。

> 对标 r28（2026-09-25 第九轮）：**把对标的"全零"读成机会** —— 只读离线壳 `sw.js` 上线（判据先行），
> 并把判据挂上 CI 真发布路径。外部漂移 3 处全为 ★ 抖动（实质 0）。

### Added
- **只读离线壳 `src/sw.js`**：HTML/JS/CSS network-first、`vendor/`+`assets/` cache-first（缓存名由 vendor 内容指纹钉）、
  `/api/**` 与非 GET 完全不碰缓存、`js/demo-config.js`（本地含密钥）既不预缓存也不写缓存。
- **`_test/offline_shell_check.py`**：A1–A10 静态审计（13 类注入反例）+ R1–R9 运行时，共 14 项；
  其中 **R9 在公网上真断网重载**（"现场 WiFi 挂了还能演五幕"是唯一验收口径）。入电池 ⇒ 31 → **33 套件**。
- **`deploy/xinyu/_headers`**：只钉实测真正缺头的两条（`/index.html` 原本无 Cache-Control 且 308 到 `/`；`/sw.js` 显式 no-cache）。
- **常驻判据 G10**（`repo_config_check.py`）：CI 必须整跑电池且声明豁免，豁免项必须是真实套件（幽灵豁免判红）。

### Changed
- **CI browser-regression job**：由"只跑 `browser_check.py` 一条"改为 `python _test/run_all_suites.py --exclude-llm`
  （runner 无上游密钥 ⇒ 显式豁免 `j2_chat_contract` / `stream_contract` 并点名，恒等式 `实跑+豁免==总数` 自证）。
- `size_budget` 覆盖域扩到 `src` 根目录（`sw.js` 入册 4,814）；`index.html` 预算因注册块上调 9,191→9,936（理由写在该文件行内注释）。

### Fixed
- **删掉一处自己刚写的死代码**：原打算用 Java `CacheHeaderFilter` 统一头策略，实测发现
  `spring.web.resources.cache.period=0` 已对所有静态件给 `no-store`（filter 被资源处理器覆盖）⇒ 过滤器删除，
  也没顺手把 vendor 改长缓存（那是性能主张，不是离线壳前提，做了只会让两端策略分叉）。
- 判据自证三处：① `transferSize` 对被 SW 拦截的请求恒为 0 ⇒ 无判别力，改由 SW 自报 `x-xinyu-src`；
  ② `c.add().catch(()=>{})` 吞掉预缓存失败 ⇒ 留痕 + 新增"清单必须真入缓存 / 页面引用必须在壳里"两条分母断言；
  ③ 间歇红根因是**判据自己的脚手架**（单线程 TCPServer 扛不住 SW 安装期并发）：换 ThreadingHTTPServer 后 3/3 绿，
  再把变量翻回单线程复现 2/3 红，A/B 钉死因果后才敢收工。
- `repo_config --selftest` 的反例条数从手抄（"十一类/十五类"两版都错）改为从代码里数。

### Deployment
- 公网 `54fb9778`（wrangler 回执含 `Uploading _headers`）：`sw.js` 线上 200 / 4,773B / `no-cache`；
  本地 `--exclude-llm` 31/31 rc=0，全量含密钥 **33/33 rc=0**。

> 对标 r27（2026-09-25 第八轮）：判据先行 —— 先给设置面板立行为判据，再切第四刀；外部漂移 2 处全为 ★ 抖动（实质 0）。

### Added
- **`_test/settings_panel_check.py`**（S1–S8 + 五类注入反例）：设置面板此前**没有任何行为判据**，而它是唯一直接碰
  密钥输入框的模块。断言：Key 恒不回显 / 留空保存不洗掉已存 Key / 填了新 Key 则写入 / 流式勾选落盘 /
  取消一字不改 / 徽章随 Key 有无如实翻转 / 全程零 JS 异常。入电池 ⇒ 29 → **31 套件**（含其自证）。
- **能力覆盖率分母证明**（`benchmark_metrics.py::coverage_hits`）：树截断或取数失败的仓**踢出分母并逐条点名原因**，
  首行改打「有效分母 N/16」，恒等式 `usable + blind == 总数` 不成立即 rc=1。起因：`pwa_offline=0/16` 的全零
  需先证"不是没数到"（实测 lobehub 树 `truncated=false` / 20,740 对象 / `sw.js|service-worker.js|sw.ts` 零命中）。

### Changed
- **`src/js/settings.js` 外提**（第四刀，`app.js` 268 → 241 行；复算见 `memory/05`）：三条密钥语义原样随迁，
  徽章刷新改用 `init({onSaved})` 注入，模块不反向依赖编排层。预算同步收紧：app.js 14,777→13,780、新件 3,000。
- 公网重部署 `4f8cd81b`：线上 `settings.js` 与磁盘等字节（2,857B），`LIVE-SYNC-PASS`。

### Fixed
- 校正注：第四刀提交信息写「239 行」，复算实为 **241 行**（把工具回执当文件真值 = 又一次手抄数字）。
  历史不改写，改在正文只写复算命令。

> 对标 r26（2026-09-25 第七轮）：切分第三刀 —— 对话窗口化外提；外部 6 处漂移经分档后**实质仅 2 处**
> （均在 sapphire：pushed 09-25 + release v2.5.0→v2.13.1），其余 4 处是 ★±1 抖动（lobehub 甚至倒退）。
> 能力矩阵/CI/docs 无变化 ⇒ 七维无翻牌。本轮另一条主线是**把"验证动作本身"纳入判据**。

### Changed
- **`src/js/chat-window.js` 外提**（`app.js` 351 → 268 行，行为零改动）：对外只留 `init/push/update/setTag/toBottom`，
  `quota` 临时抬高、`trimmedBuf` 缓存、`.log-fold` 提示条等原实现约束留在模块内。与前两刀不同，
  这块**被对话主流程调用**（提交 / 流式覆写 / 历史恢复），所以接口目标是"关住 DOM 细节"而非"搬出状态"。
  判据 = `ux_guards_check.py` U2a–U2f（浏览器实跑）21 项全绿。
- 预算**收紧**而非放宽：`app.js` 23,979 → 14,777（实测 +5%），新件登记 5,845；`size_budget` 17 → 18 文件。
- 漂移台账分档：`benchmark_metrics.py` 新增 `classify_drift`，★ 数入"抖动档"（单点差值含倒退不作趋势证据），
  `pushed_at`/`latest_release`/`caps`/`docs`/CI 全算"实质档"（可行动）。selftest 两侧都验。

### Fixed
- **同族坑第五次复发，这次骗的是验证动作本身**：给上面那条分档判据做负控制时 `import benchmark_metrics`
  = 先跑一遍 16 仓联网采集再 `exit 0` ⇒ **反例根本没执行却看起来像通过**。根因是裸 `sys.exit(main())`
  缺 `if __name__ == "__main__":` 守卫；全仓扫出 3 个（`benchmark_metrics` / `live_sync_check` /
  `run_all_suites`，后者 import 一次等于 29 套件全量重跑），三个全补守卫。
- 新增常驻判据 **G9**（`repo_config_check.py`）：`_test/*.py` 必须 import-safe；`--selftest` 扩到**十一类**，
  含两条反向样本（"有守卫不得报红"、"函数体内缩进的 sys.exit 不算违规"）防判据恒假。
- 公网重部署 `61ec115b`：`chat-window.js` 线上 200 且与磁盘等字节，`LIVE-SYNC-PASS` / `PUBLIC-ONLINE-ALL-PASS`。
- 首次 `wrangler pages deploy` 报 `fetch failed`（未静默跳过，重试第二次成功）；线上主域名响应曾达 15.7s，
  已记为环境抖动而非代码结论。

> 对标 r25（2026-09-25 第六轮）：切分第二刀 —— 情绪曲线外提；外部漂移 3 处（★ lobehub 82,808 / ST 33,745 / OLV 13,903），
> 能力矩阵与 release/pushed 无变化 ⇒ 七维无翻牌，本轮差距继续来自自身结构。

### Changed
- **`src/js/chart.js` 外提**（`app.js` 403 → **351** 行，行为零改动）：`window.Chart = { render(), init() }`；
  原约束随迁（HiDPI `setTransform` 逻辑绘制 / resize 200ms 防抖且无数据跳过），新增缺画布时静默返回。
  `#btn-clear` 处理器留在编排内（它还管星图熄灭，不属于曲线）。
- 交付链同步完成：`index.html` 引入顺序 voice→chart→app（实测 6813 / 6845 / 6885）、`DEPLOY-SYNC-PASS`、
  `size_budget` 登记（17 文件，关键路径 822,936 / 858,752）、公网重部署 `0c90a2d9`、三判据 rc=0。

### Fixed
- 两处「工具没报错 ≠ 生效了」（同族坑连续第三轮）：
  ① 给 `size_budget` 打补丁时锚点写成 `4_355`（文件实为 `4355`），`str.replace` 未命中却照常打印"已登记"数字
    ⇒ 由 coverage 判据报「未登记预算的文件 ['src/js/chart.js']」暴露；补丁脚本改为**替换前 assert 锚点存在、替换后 assert 内容变化**。
  ② 抽曲线的脚本锚点条件过窄（依赖 `measureText` 前一行）⇒ `StopIteration` 半路死；
    改用 `#btn-clear` / resize 注释等**语义锚点**并 assert 边界行内容后再删段。
- `memory/07-next-steps.md` 的 P0 自驱条目在 r24 savepoint 时被迁进分卷未回补 ⇒ 壳内一度只剩"等老大"的两条，
  违反「P0 必须有一条可执行指令」的精神；已补回第三、四刀条目（含每刀的固定动作序列）。


> 对标 r24（2026-09-25 第五轮）：**结构性还债第一刀**，外部漂移 4 处（lobehub ★82,807 / pushed 09-25 等）。

### Changed
- **`src/js/app.js` 语音模块外提为 `src/js/voice.js`**（471 → 403 行，行为零改动）：
  `window.Voice = { init(), speak(), isSpeaking() }`，保留原三条约束（不支持即隐藏按钮 / 异常一律吞掉绝不带崩主链路 /
  开关走独立键 `peiliao.speak.v1` 不进 `cfg`，避免被 `setCfg` 清历史牵连）。
  这是 r22、r23 连续登记为「下一件」却两次推迟的项 —— 本轮作为唯一改动开工，**归因干净，不再登记第三次**。
- 交付链同步完成：`index.html` 引入顺序、`deploy/xinyu` 副本、`size_budget` 登记（4,148B / 预算 4,355B，
  关键路径 821,901 / 858,752），公网重部署 `41dea397`，`live_sync` / `public_check` / `online_check` 三判据 rc=0。

### Fixed
- 本轮自己造的一处噪声并留痕：同步命令把 `src/index.html` 误复制进 `deploy/xinyu/js/`，且 `2>/dev/null` 吞掉了本该提醒的报错
  ⇒ `deploy_sync` 报 EXTRA 一项。核实该副本未被 Git 跟踪且与源字节相同后删除、复跑归零。
  （同族坑：R212 明令降级检索禁配 `2>/dev/null`；上一轮刚写进报告，本轮自己又踩。）
- 又一条文档数字脱节：`memory/06-constraints.md` 写「`app.js` 469 行」，实测 471 行 ⇒ 已在该条更正注里点明
  **G2/G4 只覆盖 README 与 CI，未覆盖 06/05 的正文数字**（是否扩大覆盖面待拍板，见 ROADMAP）。


> 对标 r22（2026-09-25 同日第三轮）：本轮对标数据**零漂移**（16 仓与上一轮逐字段相同），
> 因此差距全部来自**对上一轮交付物自身的复审** —— 结果抓到两处真缺陷，都已修并配反例。

### Added
- **契约探测覆盖判据 C6/C6b**（`_test/api_contract_check.py`）：每条 OpenAPI 操作必须"被真实打"或"显式
  `x-live-skip` + 理由"，且本项目当前要求**零豁免**。`docs/openapi.yaml` 补齐 3 条漏标操作
  （`/api/memory/emotions`、`/api/memory/messages`、`/api/memory/message` POST）⇒ 探测数 **8 → 11 全覆盖**；
  `--selftest` 增第 5 类篡改样本（抹掉一条标注必须被 C6 抓到）
- **仓库配置自洽守卫** `_test/repo_config_check.py`（G1–G5 + selftest）：
  G1 dependabot schema（ecosystem 在支持清单内 / `directory` 真实存在且含对应 manifest / interval 合法）
  G2 CI job 数 == README 声称的门禁数 G3 `docs/openapi.yaml` 存在且被 `docs/README.md` 引用（不留孤文件）
  G4 电池条目数 == README 声称的套件数 G5（`--online`）GitHub 默认分支上 dependabot 文件可见
- 两条判据入全量电池（26 → **28** 套件）与 CI

### Added（r23 追加：R196 强制项从未落地）
- **评测集来源登记判据 G8**：实测 `memory/06-constraints.md` 的「测试专用文件清单」至今是 **init 模板占位符**
  （`（如 eval/testset_provenance.json / blindset / frozen）`）⇒ R196「新增评测数据先登记 provenance」这条红线**从未真正落地**，
  而评测集 accuracy（73 条 / 98.6%）是要写进《应用方案》与答辩材料的数字。
  - 06 该节填实为登记表：文件 / 条数 / 谁在裁决时读它 / provenance（人工撰写、**不用模型生成样本**）/ 冻结状态，
    并写明"真实对话走 `chat_message` 表、与评测集物理分离，禁止回流刷分"（同源 PII 风险）
  - 判据化 `repo_config_check.py` **G8**：① 不得残留模板原句（锚定 `清单：（如 `，不用泛指括号示例 —— 第一版因此把已填实的表判成假红）
    ② 登记的文件必须真实存在（R240）③ **声称条数 == JSON 实际 items 数**（改数据不改台账即红）
    ④ 只对裁决用数据核条数，不对配置声明件核（第一版把 `vendor-manifest.json` 的"3 条"当成 3 个样本 ⇒ 分母混用假红）
  - `--selftest` 扩到 **十类**合成篡改全抓（新增：抹评测集行 / 条数改小 / 删整节 / 表退回模板原句）

### Fixed（授权口径 —— 自审第三条发现）
- **整仓标 MIT 是不准确的声明**：`LICENSE` + README 中英双语均挂 MIT，但 `src/vendor/gsap.min.js`、
  `ScrollTrigger.min.js` 文件头自证为 **GreenSock Standard License**（非 MIT、非 OSI），只有 `three.min.js` 是 MIT。
  对公网分发的参赛作品属可被挑出的合规瑕疵。
  - 新增 `docs/THIRD-PARTY-NOTICES.md`：逐文件列 库/版本/授权/上游/再分发注意，并写明适用口径
    （高校参赛演示、不用 GSAP 构建竞争性动画产品 ⇒ 落在 Standard License 免费使用范围）
  - README 中英授权段改为「MIT **仅覆盖自研代码**」+ 指向该清单
  - 判据化：**G6** `src/vendor/*.js` 每个文件必须在清单中被点名（漏登记即红）、**G7** README 必须含指向清单的口径行
    （防改回"整仓 MIT"）；`--selftest` 两类新反例（抹 `gsap.min.js` 行、抹 README 引用行）均被抓到
- **本轮新加的 `--slice` 开关第一稿是死代码**（先滤掉 `--` 参数再判 `args[0] == "--slice"`，永不命中，
  于是 `--slice 0 14` 把 28 条全跑还报全绿）：改为按 `sys.argv` 原样解析 + `--list` 打印过滤后条数 +
  **过滤后零套件直接 rc=1**（禁止把 0/0 当通过）。实证 `--slice 3 3` → FAIL rc=1、`--only repo_config` → 2 条
- 撤回并在复跑后重写一条**先于证据**的结论（`28/28` 曾在两次后台运行输出 0 字节时被写进报告）
  ⇒ 记录为报告 §10.6：**后台任务 `exit 0` 不等于产物存在**

### Fixed
- **C4 原先的 `done >= 8` 是"阈值低于总量即掩盖"**：真实操作 11 条，只探测 8 条也判绿。现改精确对账
  `探测 + 豁免 == 操作总数` 且要求零豁免 —— 这是我自己上一轮留下的洞，本轮复审抓到
- **文档数字断言与实值脱节**（守卫上线当场抓到）：往电池加 2 条后 README 仍写"26 套件"，
  G4 立刻报红 `实测 28 | 声称 26`；已改并保留该红→绿过程作为反例证据（"文档写过的数字"从此有机器责任）
- dependabot 由"配了就算"升级为"配了且被受理"：G5 实测默认分支可见
  （`lxh113377/xinyu-soulisle-private-archive`），GitHub 只读默认分支 ⇒ 未 push 到默认分支的配置等于没配


> 本轮（对标 r21，2026-09-25）只动文档 / CI / 判据，**未改服务端与前端运行代码** ⇒ 版本号暂留 1.4.0，
> 下次含代码变更的轮次一并 bump（避免在截止前制造"版本号与产物不一致"的新债）。

### Added
- **接口契约唯一声明源** `docs/openapi.yaml`（11 条接口，含错误码与 SSE 语义）+
  守卫 `_test/api_contract_check.py`：C1 不缺文档 / C2 不虚文档（幽灵路径）/ C3 前端不得偷调未文档化端点 /
  C4 运行态状态码与必需键一致（真实打 `/api/chat`、`/api/emotion`，探测会话 `contract-probe` 结尾 DELETE 自清）/
  C5 `--selftest` 四类合成篡改全抓到。已入全量电池（24 → **26** 套件）与 CI `java-build`
- **依赖自动更新** `.github/dependabot.yml`：`maven`（`/server`，即 `server/pom.xml`）+ `github-actions`（`/`）
  两个 ecosystem，每周二 08:00 Asia/Shanghai，PR 上限 3 / 2

### Fixed
- **纠正 r20 自己写下的错误归因**：上一轮技术债记"零构建 ⇒ 挂不上 dependabot（没有 package.json）"，
  把"npm 生态挂不上"扩大成"整个项目挂不上"，据此放弃了本可自动化的两半。实测更正见
  `memory/06-constraints.md` 该条的**更正注**：真正无包管理器可托管的只有 `src/vendor/` 三个手工 vendored 的 JS 库
- **对标测量装置两处自纠**（本轮第二次采集立刻抓到问题，说明守卫有效但也确有洞）：
  ① 漂移比对只比 4 个数字字段 ⇒ `sapphire` 的 `container` 能力从清单消失却**零漂移报告**，现 `caps`/`docs` 纳入比对
  （`--selftest` 加两键样本）；② self 的"回归套件数"此前用文件名 glob（19）与报告口径（24 套件）**两个分母混用**，
  现唯一真相源改为 `run_all_suites.py` 的 SUITES 条目数，解析失败即报错、绝不回退 glob
- 参照池由 14 扩到 **16 仓**（本轮 `search/repositories?sort=updated` 实跑新捞
  `zeroa234/ryza-ai-revive` 190★/JS/09-22 活跃、`Bwcx-songyu/MoodChat` Java 同栈），漂移输出 `repo_added` 正常报告
- 能力探测新增 `api_spec`（机器可读 API 规范）：**实测 1/16** ⇒ 据此把 `docs/openapi.yaml` 在报告里
  登记为**自我改进**而非对标差距，不冒充竞品压力


## [1.4.0] - 2026-09-25 — 对标轮 r20：把"已经建好却没接上"的能力接上

### Added
- **情绪识别后端化接线** `src/js/emotion-remote.js`：共情链路的分类在后端 `/api/emotion`
  可用时以后端为准，**消除 J3 遗留的 JS/Java 两份真相**。开关口径与 J4 完全一致（三层）：
  代码层 `cfg.emotionRemote === true` 默认关闭 → 本地演示（fat jar）开启 → **公网版刻意不开**
  （Pages Function 没有 `/api/emotion`）。危机词在本地词典先判、**绝不为网络等待**；
  404/超时/响应形状不合法即熔断并回落本地引擎；气泡元信息如实标注「情绪:后端」，禁伪装
- **vendor 供给链守卫** `_test/vendor-manifest.json` + `_test/vendor_freshness_check.py`：
  三个首屏第三方库的**完整性哈希 + 版本声明对账 + 上游漂移探测**（零构建项目没有 lockfile，
  此前第三方库漂移是纯盲区）。V2 判据从文件内容解析版本，**正则零命中即判红**（不把"没测到"当"通过"）
- **对标源数据台账** `_test/benchmark_metrics.py` → `交付物/对标数据/benchmark-metrics.json`：
  14 个参照仓的 ★/最近推送/最新 release/CI workflow 数/文档齐备度/**递归整树能力矩阵**
  与本项目 self 指标同一份产物，每次运行输出**与上次快照的逐字段漂移**（治"数字来自历史快照"）
- 新判据入电池（19 → 24 套件）：`emotion_wiring_check`（9 项 + `--selftest` 3 类篡改全抓到）、
  `vendor_freshness_check`（+ `--selftest` 4 类篡改全抓到）、`benchmark_metrics --selftest`；
  CI `frontend-checks` 同步增 3 步

### Changed
- **gsap + ScrollTrigger 3.12.5 → 3.15.0（成对升级）**：前端实际用到的 API 面仅 5 处，
  升级后 `browser_check` / `lightshow_check` / `pixel_dual_check` 三套件全绿；
  首屏关键路径 819,767 B（预算 858,752 B 内）
- **体积预算表加"必须全覆盖"判据**：实测抓到原 13 文件表漏登记 `src/data/emotion-strategy.js`，
  且新增文件本会静默绕过体积门禁 —— 现在漏登记即红

### Removed
- 从 ROADMAP 计划里**撤下**「PWA / service worker 离线缓存」：本轮机器实测 14 个参照仓
  `pwa_offline` 命中 **0/14**（含 LobeChat / SillyTavern / Open-LLM-VTuber），
  即"同类优质项目都靠 SW 做离线"是首轮未经核实的推断；撤销理由与替代动作（`live_sync_check`
  机器守新鲜度）已写入 ROADMAP「本轮撤下的两项」

### Known issues（登记不隐瞒）
- `src/vendor/three.min.js` 实测为 **r128（2021）**，上游 **r186（2026-09-24）**，落后 58 个大版本。
  截止前不升级的理由与迁移风险（色彩管理默认变更 / `Geometry` 移除 / 自定义着色器约定 /
  星雾双色像素级标定需整体重定）已写入 ROADMAP 计划第 1 项，可用
  `python _test/vendor_freshness_check.py --check-upstream --strict` 机器复现


## [1.3.0] - 2026-09-24 — 对标轮第二轮：把"赛后再做"直接落地

### Added
- 工程化七件套（本轮前一并入 1.3.0 发版）：GitHub Actions CI、`.env.example`、`SECURITY.md`、
  Issue & PR 模板、英文 README、首轮对标分析报告
- **逐字流式输出（SSE）**：`/api/chat` 认 `stream:true`；Pages Function 与 Java 侧 SSE 直通，
  前端 `onDelta` 逐字渲染；代理不支持流式时按 `content-type` 自动回落整包，不留半成品气泡
- **共情策略表 SSOT** `src/data/emotion-strategy.js`：persona / rules / 分类器提示 / 危机话术 /
  每种情绪的共情要点·离线模板·采样参数集中一处，新增情绪类别代码零改动
- **多模型 provider 适配层**：`LLM_BASE/LLM_MODEL/LLM_KEY`（`DEEPSEEK_*` 保留兼容别名）
  + 设置面板 5 家快捷预设（DeepSeek / OpenAI / 通义 / Kimi / 本地 Ollama）
- **回复朗读**：`speechSynthesis`（zh-CN）开关，零依赖；浏览器不支持即隐藏按钮
- **对话列表窗口化**：DOM 上界 60 条 + 配额制「展开较早」；模型上下文与情绪记忆不受影响
- **响应式三档**（480/768/1024）+ **星雾粒子按视口降档**（900/1200/2600）
- 新判据三条：`_test/strategy_check.py`（含 `--selftest` 防恒真）、`_test/stream_contract.py`
  （A 非流式不破 / B 含内容帧≥2 / C 前端逐字且回落不冒充）、`_test/ux_guards_check.py`（21 项逐项判定）
- CI 增两条门禁 job：`java-build` 起**无密钥** fat jar 跑词表一致性红线（此前只写在 `memory/AGENTS.md` 靠人记）、
  `browser-regression` 跑浏览器回归（runner 无 GPU，强制 ANGLE/SwiftShader）；密钥扫描带拼接生成的对照组
- `ROADMAP.md`：对标差距 → 已完成 / 计划 / **明确不做（附理由）**

### Changed
- 红线从 4 条增至 5 条（新增「策略表成对红线」），`CONTRIBUTING.md` 同步
- CloudBase 云函数按 HTTP 请求-响应模型**刻意不做流式**（注释写明属设计内回落，非缺陷）

### Fixed
- CI 密钥扫描自伤：写死在 workflow 里的对照密钥会命中自身扫描 → 改拼接生成（本机实跑抓出）
- 「展开较早记录」原先放回即被同一上限裁回（等于没展开）→ 改配额制，新消息才收回上界

## [1.2.0] - 2026-09-24 — 提交包产出

### Added
- 《应用方案》PDF（18 页，含 8 图）+ 作品简介（259 字）+ 盲审遗留处置
- `_test/screenshots_resubmit.py` 重渲染链路（临时文件 → 校验 → 原子替换）
### Fixed
- Edge 打印页脚泄露本机文件路径（`--no-pdf-header-footer` + 全页复扫）
- `render-pdf.ps1` 先毁后坏缺陷

## [1.1.0] - 2026-09-23 — 体验与部署收口

### Added
- Docker 镜像真构建真运行实测（482MB，重启持久化、镜像内密钥扫描对照）
- `deploy/jar/` fat jar 部署包（start.ps1 / start.sh，JDK≥17 探测）
- `deploy_sync_check.py`（src→deploy SHA256 三类归零守卫）、`docker_image_sim_check.py`
- 评测集 36→73 条；语音输入实测
### Changed
- 全栈体验与健壮性优化 16 处；pixel 双色判据破除相位抖动（双条件判据 + 单色对照）
### Fixed
- Dockerfile 红线缺陷：`COPY src/` 会把含 Key 的 demo-config 打进镜像 → 改 `COPY deploy/xinyu/` + `.dockerignore` 纵深防御

## [1.0.0] - 2026-09-22 — Java 全栈主线贯通（J1–J5）

### Added
- Spring Boot 3.2.5 服务端：`/api/health`、`/api/chat`（与 v1 契约 1:1）、`/api/emotion`（+ `/eval` 双端逐项一致）、`/api/memory/**`（H2 file / MySQL 可切）
- 轻量 token 鉴权过滤器（`XINYU_API_TOKEN`，留空放行）
- 两端一致性守卫 `engine_consistency_check.py`；选型决策记录落盘（五条）
### Changed
- 静态页直读 `src/` 权威源（零副本策略）；评测集服务端直读不复制进 jar

## [0.x] - 2026-09-19 ~ 09-21 — v1 原型与基线

- 五幕 3D 情绪叙事页（Three.js + GSAP，零构建）；双路情绪引擎 + 危机优先拦截；
- Cloudflare Pages Function + CloudBase 云函数双线在线；localStorage 持久化与离线降级；
- 版本控制基线建立（2026-09-21）；MIT 协议与对外 README（2026-09-24 随词表 SSOT 化补入）

> 更早明细见 `git log`；本文件自 2026-09-24 起维护。
