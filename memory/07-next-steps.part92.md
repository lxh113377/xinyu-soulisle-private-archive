# 07-next-steps.part92 — r83 轮完整记录（2026-09-30）

> 从 07 壳迁出的长段落全文。壳只留一行摘要 + 本卷指针。

## ① 交付面在位这条腿「建好了，但站在没人经过的出口」（R82-01 的下一刀，本轮闭环）

r82 补的第 4 条取数面（分母 = `git ls-tree -r -l HEAD -- 交付物`，本轮 90 条）方向对，但它只在电池/CI 跑，
而 09-28 与 09-29 两次事故都发生在**两次提交之间** ⇒ r82 那一轮仍要靠会话开场才看见 7 条 ` D`。

本轮落点（两件，都被跟踪、都可复算）：
- `_test/hooks/pre-commit`（源，2,347 B）：只拦「已入库交付件从工作树消失」；
  **fail-open 是设计** —— 判据 rc=2（取不到数）或找不到 python ⇒ 放行并报警；
  rc 不在 {0,1,2} 一律按 CRASH 报警但不拦（r82 把硬崩判成「环境未验」= 通行证，这条不再犯）。
  逃生门 `XINYU_SKIP_DELIV_HOOK=1` **带计量**：每次跳过往 `.git/xinyu-hook-skip.log` 追加一行并打印累计次数。
  **不动 `core.hooksPath`** —— 本仓 `.git/hooks/` 里已有 `post-checkout`/`post-commit`（Mimosa 占位），
  改 hooksPath 会让它们静默失效，那是拿别人的工具链换我的闸。
- `_test/hook_wiring_check.py`（新判据，接入电池两条 ⇒ 套件 103→**105**）：
  W1 源在位且 `sh -n` 解析得动；W2 `.git/hooks/pre-commit` **按字节 == 源**（改源没重装就红）；
  W3 被拦判据的三态（pass/block/unverified）与 `tracked_missing_check`/`committed_blobs`/`parse_ls_tree` 仍在位。
  `--install` 唯一装法：异版先备份 `pre-commit.bak-<sha>`，写后**读回**断言等值。
  `--selftest` **12 腿**，反向方向含：副本漂**一个字节**必须红、CI 面（新克隆）**不得**判红、
  源被截成一行必须红、零输入绝不 ok、硬崩 rc 不并入未验；
  **端到端腿**在 `tempfile` 里建一个真 git 仓、装真源、真删一件入库件 ⇒ 钩子真回 rc=1 且点名。
  真面演习（本轮实测）：靶 = `交付物/提交包/demo_video_out/timeline.json`（354 B，**未写进声明面**），
  删 ⇒ `rc=1 且点名`，按字节复原（sha `c277581073f9`）⇒ `rc=0`。
  靶子取数直接 `import deliverable_inventory_check` 复用 `committed_blobs()` —— 本仓另写一份 `ls-tree` 解析
  第一次就把 CJK 路径读成 `"\344\272\244..."` 那种**根本不是路径**的串（0 候选 ⇒ 判未验，没蒙绿）。

## ② 在册的国内备用链接已经不是心屿的页面（一手取证 + 加法修复）

`tcb hosting list --json` 现场读数：该环境静态托管**根目录由三个项目共用**
（24 个 `NN_*.html` 是 iCAN 门店快照集，`zhengwen-api` 是医项目的云函数，`__auth/`、`cloud-admin/` 是平台件）。
心屿那批 `js/*`、`css/style.css` 停在 **09-19 18:54**；根上 `index.html` 的 `lastModified = 2026-09-24 21:01:07`，
**与 iCAN 那 24 件同一批次**；现场 `curl` 取到 `<title>iCAN 演示快照集</title>`，
而本地 `deploy/xinyu/index.html` 是 `<title>心屿 · AI 情感陪伴 — 滚轮驱动的 3D 情绪叙事</title>`。
⇒ 《提交清单》第 3 行「双线」里那条评委真可能打开的备用链接，从 09-24 起给评委看的是**另一个作品**。

处置（**加法，零覆盖**：不删他人任何一件）：`tcb hosting deploy deploy/xinyu /xinyu`（25 件），
验收走**独立通道**（不采信 CLI 自带校验，见 ④）：逐文件 `curl` 回读，**25/25 字节数与内容全等**；
`XINYU_URL=https://qwer-…tcloudbaseapp.com/xinyu/ python _test/public_check.py` 现场过
中间页放行 True、标题对、`CRISIS: True`、`KEY_LEAK: False`，但断言「对话未走在线」判红 ——
该 404 体是对象存储的 `NoSuchKey` ⇒ **静态托管域名不代理云函数**，`chat` 函数本身在役（`tcb fn list` 实测），
路由改动属控制台动作且该 env 三项目共享 ⇒ 本轮**未擅动**，清单行改为「该线现为界面如实标注的离线降级」。

## ③ 覆盖率换尺：从「还差几支」到「逐支说明为什么差」

jacoco 逐行 `mb>0` 读数（本轮 11 支 → 修后 8 支）与归类：
- **补测 3 支真分支** ⇒ BRANCH 285→**288 / 296 = 97.30%**（用例 83→88）：
  `MemoryController:48`（`intensity` 键**不存在** 与「给了但不是数字」是两条不同短路）、
  `MemoryController:93`（`ChatMessage.createdAt` 为空 ⇒ 字段在、值为 null，不伪造当前时间）、
  `EmotionLexicon:129`（`e <= s` 为真）。
- **8 支结构不可达，每支给了机器载体**（散文不变量升为用例，红了会被看见）：
  `mapper.readTree("")` 实测返回 **`MissingNode` 而非 null**（对照探针跑的是项目实际依赖 jackson 2.15.4）
  ⇒ `MemoryController:118` / `ChatController:55` / `EmotionController:54` 的 null 侧是死代码，
  本轮写了「`readTree` 永不返回 java null」的断言同时钉住这三处；
  `BodyHandlers.ofString` 对零字节响应给 `""` ⇒ `LlmProxy:103` 的 `body == null` 死；
  `lastUserText` 对非数组先给空串 ⇒ `harden` 在上一道门就 return ⇒ `SafetyGuard:131` 的 `isArray` 支死；
  `LlmProxy:94/125`（`payload == null`）沿用 r82 归因；`ChatController:112` false 侧沿用 r77（`headerValue()` 恒非 null）。
- **两处自纠由新用例当场测出**（不是事后追认）：
  ① 我假设「把 `}` 写在 `{` 前面」能触发定位守卫 ⇒ 用例回「实际静默通过」：`lastIndexOf('}')` 取**全文最后一个**，
  而旧 `unbalanced.js` 夹具 `{"lex":{}` 末尾自带 `}` ⇒ **它一直是被 Jackson 解析异常抓住的，守卫那一支从没被走过**。
  这是「看起来在测这条」的假覆盖。
  ② 桩脚本是**队列**：只 `script` 一条空体时，第二次请求掉进桩的默认响应，断言拿到「兜底」而非 `upstream-nonjson`。
- LINE 97.75 / METHOD 96.43 **未动** ⇒ 不虚报「本轮把覆盖率全面推高」。

## ④ 本轮三次踩同一族（已进 `memory/AGENTS.md` 排障表）

1. **退出码在管道里死掉**（本仓第三次）：删除循环写 `out=$(tcb … 2>&1 | tail -1); rc=$?` ⇒ `rc` 是 `tail` 的，
   25 次失败全被吞，`git`/`tcb hosting list` 复算才发现托管面还是 68 件。
2. **Python 调 npm shim**：`subprocess.run(["tcb", …])` 报 `FileNotFoundError`（WinError 2）——
   `tcb` 是 `D:\npm-global\tcb.cmd`，Windows `CreateProcess` 不走 PATHEXT ⇒ 必须给 `.cmd` 全路径。
3. **MSYS 改写斜杠开头的参数**：`tcb hosting deploy deploy/xinyu /xinyu` 被改写成 `C:/Program Files/Git/xinyu`
   ⇒ 25 件误上传到错误 cloudPath。修法 `MSYS_NO_PATHCONV=1`。误上传已逐件删除并双向对账
   （原始 43 件面 → 现在 43 件面，`新增 0 / 缺失 0`，他人件一根没动）。
4. 另记一条：**CLI 自带的一致性校验不可信** —— 第二次尝试用 `--verify --safe`，它把**全部 25 件**报成
   `missing` 并触发自动回滚（回滚正确、托管面回到 43 零残留），但那份读数是假的。
   ⇒ 远端在位性一律走独立通道（本地字节 vs 远端字节）自取。

## ⑤ R1 切版（当轮命令构成授权）与三源对账

`release_governance` 本轮实测 `FAIL R1 feats=17/5 unreleased=143 提交通道=git-log`。
r74–r82 连续六轮把它挂为「等切版授权」；老大本轮明令「按优先级直接开工、严禁询问」⇒ 执行：
- `CHANGELOG.md`：`[Unreleased]` 的 640 行**逐字节搬运**进 `## [1.7.0] - 2026-09-30 — 对标轮 r53–r83 收口`，
  上方重新起一个空 `[Unreleased]`（占位行不带 bullet，防 R2b 判「文案先行」）；
- `server/pom.xml` `1.6.1 → 1.7.0`；`ROADMAP.md` 当前版本行同步；
- 三源（tag == pom == 文档）由 `repo_config_check` **G12** 当场对账；R6 段落标题只增不减；
- `mvn -B -ntp -f server/pom.xml verify` BUILD SUCCESS（覆盖率门 LINE 0.90 ∧ BRANCH 0.90 仍过），
  fat jar 重建 28,448,572 B（01:35）⇒ 电池 `preflight` 的「jar 新于源码」不会因 pom 改动而假红。
- **不放宽任何阈值**：R1 是靠真切版变绿，不是把上限 5 改大。

## ⑥ 本轮没做成的两件（不折叠）

- **pages.dev 发版（R82-02 延续）**：三条可能入口全部实测取空 ——
  环境变量 `CLOUDFLARE_API_TOKEN`/`CF_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` 未设；
  `~/.wrangler` 与 `%LOCALAPPDATA%/.wrangler` 不存在；**CI 侧 `gh secret list` 为空**（新增的一条取证面：
  以前只查过本机，本轮查了受理面也没有）；全局 wrangler 仍坏在 `miniflare → require workerd`。
  ⇒ `live_sync`/`public_check`/`ci_status` 三条红不解，公网仍是 r79 之前的构建，
  评委打开 pages.dev 会看到 `Applying inline style violates … style-src 'self'` 那条 console 报错。
  **老大只欠一个 Cloudflare API Token**（或一次交互式 `wrangler login`），配方 `part89` + `part91` §⑨，
  **先记回滚锚 deployment id 再 deploy**。
- **备用链接的常驻判据（G6）**：本轮 `/xinyu/` 是**人眼 curl** 抓出来的，`live_sync_check.py` 的取数面只有 pages.dev。
  下一刀：给 `live_sync` 加第二个 URL 面或独立一条 suite，把「逐文件字节回读」做成常驻；
  写断言前先决定这条线算「在线」还是「如实离线降级」—— 后者才与磁盘实况相符。

## ⑦ 07 壳瘦身迁出的原文（r83；壳 4,574 B 超 4,096 ⇒ 长句迁本卷，壳只留摘要 + 指针）

- R83-01 原文：`live_sync` 只盯 pages.dev ⇒ 「`/xinyu/` 这条是不是又被别人覆盖或变旧」在本仓无人看守；
  本轮是人眼 curl 抓出来的。该线 `/api/chat` 回 404（静态域名不代理云函数；`chat` 函数在役，
  路由属控制台动作且该 env 三项目共用 ⇒ 未擅动），所以它现在只能算**界面如实标注的离线降级**。
- R77-01 原文：包装器报 `completed (exit code 0)` 而真 rc=1 只在被重定向的 stdout 里；
  本轮四处读数一律从日志自报行取（`PEERS_RC=0`、`BATTERY_RC=1`、`MVN_RC=0`、`VERIFY_RC=0`），
  并把同族第三次复发写进 `memory/AGENTS.md` 排障表；**机器载具仍未落地**（下一刀候选：
  任何后台测量都经一个自己写 rc 行的包装件，且判据只读那一行）。
- 覆盖率换尺原文：`mvn test` 83→**88 用例**，jacoco BRANCH **285/296 → 288/296 = 97.30%**，
  补的是三支真分支；余 8 支逐行归为结构不可达并各给断言（详见 §③）。LINE 97.75 / METHOD 96.43 未动。
