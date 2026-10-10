- **卷40** `07-next-steps.part135.md` — **r105 收口（受理面「假门 / 上升的棘轮 / 崩了的仪器」四项改造；与并行会话的 r102/r104 产品面零交集，本轮零 `src/` 改动）**：
  ①**G16 孤儿判据接线**：`_test/dock_auto_check.py` 在提交面却两头不执行（电池 0 处、CI 0 处）⇒ 接进 SUITES +
  `docs/quality-gates.md` 同笔登记。**接线前两侧先测**：HEAD 面（`git archive` 抽出 + 零密钥 stub + 静态服务 8213）11/11 PASS、
  工作树面 15/15 PASS。一条真红同时压着 `repo_config` 与 `repo_config_selftest`，接线后一起转绿。
  ②**E2 棘轮降数**：现读未接入 24 > 基线 23（新增套件又抄了一遍手写 launch 回退）。收编 `ux_guards_check` /
  `settings_panel_check` / `public_check` 到 `browser_engine` 唯一入口，并把**引擎身份写进判定行**
  （`引擎=msedge(channel)(155.0.4283.45)`）⇒ `BROWSER-ENGINE-PASS: 回退余量 21（基线 23｜起点 31 已接 10）`。
  这是 `07` 从 r97 挂到今天的 P0 第一次真降数（不是抬基线）。
  ③**仪器崩溃面收口**：`vendor_freshness_check.py:58` 假设名册每条都有字符串 `detect`，在途台账新增 4 条 mediapipe 条目写
  `"detect": null` ⇒ `re.search(None,…)` 抛 TypeError，`--selftest` 同死 ⇒ 电池只能记 **BLIND-RED(判红零结论行)**。
  修类不修例：新增 `field_problems()` 五字段门（缺失/类型/非法正则各点名），`null` 定为**一档合法声明**（只关 V2 那条腿，V1 照查），
  V2 参与数折进判定行。`SELFTEST-PASS: 10 类样本`；变异体（摘门）当场 `KeyError: 'detect'` 复现旧崩溃。
  ④**端口 8123 属主协议**：`build_jar.stop_holders()` 原按端口逐个 `Stop-Process -Force`（r104 实测把并行会话验证服务杀 3 次）。
  改四档归类 `ours/same-artifact/foreign/unknown`（**取不到命令行归 unknown，绝不升格成可杀**），默认只停本工具起的
  （租约 `%TEMP%/xinyu-port-lease.json`），`--takeover` 才是人授权的接管口；拒绝时 rc=2 不构建（jar 被锁时硬构建=r37 那枚 48,907B 截断件）。
  真面只读探测 pid 23828 判 `same-artifact`、默认 kill=[]；`BUILD-JAR-SELFTEST-PASS（11 条）`，桩已进电池。
  **改变对外口径的一手事实**：`v1.8.2` tag **不在 main 祖先面上** —— `git log -1 v1.8.2`=e8462ca（正文「三源同步」，
  `git show e8462ca:server/pom.xml`=1.8.2），`git merge-base --is-ancestor e8462ca HEAD` 回非零，`ls-remote --tags` 已有该 tag
  ⇒ G12 不是「还没切版」是「切了没落地」。
  **自己的漏改被自己的尺抓到**：改 SUITES 后 `G4 电池条目数==README 声称数` 报红（实测 146｜README 仍 144）——
  找硬编码计数时只 grep 了 `_test/ docs/ .github/`，**没扫 README**。
  **合并索引停在 r96**：轮次表止于 r96（根目录实有 r98…r104）⇒ 补 r98–r105 行 + 「最新」指针改 r105；
  **r97、r103 两侧实测无报告文件**，只写清这件事，不补造。**未推**。
