# 07-next-steps.part98.md

<!-- 本卷为 07-next-steps.part92.md 的延续 -->

## ⑦ 07 壳瘦身迁出的原文（r83；壳 4,574 B 超 4,096 ⇒ 长句迁本卷，壳只留摘要 + 指针）

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
