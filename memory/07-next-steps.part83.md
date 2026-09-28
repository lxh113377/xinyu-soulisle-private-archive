# 07 分卷 · 卷83 — r77 失败面（2026-09-29）

> 与卷82 同轮：交付记录的两侧必须都写下，这里只放失败面（成功面在卷82）。

## 失败面（同条登记，禁只写"已交付"）

- **R77-01 后台任务通知把"包装器退出"当成"子进程完成"**：第一次电池后台跑，通知回 `completed exit code 1`
  而日志 0 字节；实际子进程 **pid=29080 仍在跑**（`Get-CimInstance Win32_Process -Filter 'ProcessId=29080'` 取到
  命令行原文，CreationDate 02:53:39），10.02 分钟后自己跑完刷盘＝**93/98**。第二次跑被并发锁正确拦下
  （判得对，是通知错了）。连带坑：**同一 `>` 路径开第二次会 truncate 掉第一次未刷盘的输出**。
  通则：后台测量的完成信号要取**被等对象本身**，与 r76「async wait = completion signal」同族。
- **R76-03 的第二形态（同一条单点，换了个咬法）**：8123 上的演示进程持有 `server/target/soulisle-server.jar`
  ⇒ `mvn verify` 在 `spring-boot:repackage` 步 **rc=1**：`Unable to rename …jar to …jar.original`。
  红因**不是**覆盖率门（`jacoco:check` 绑 verify，排在 repackage 之后 ⇒ 门根本没轮到说话）。
  归因走 `wmic process where 'ProcessId=24208' get CommandLine` 取到持有者原文，再经仓内既有通道
  `python _test/build_jar.py --restart`（先 stop_holders 再 clean package）⇒ `mvn rc=0` + 验货 PASS + 服务复原。
  ⇒ **去单点这件事的优先级从"测试便利"升为"构建可用性"**。
- **我自己的尺造出一条假 drift**：第一版 jacoco 取数按"逐类求和 + 再加一次 missed"算出 `296/346=85.55%`，
  据此宣称 r76 报告 §4 的 `246/296=83.11%` 是过期手抄值——**报告那行是对的，错的是我的算法**。
  等式自证（`sum(covered)+sum(missed) == counter 属性`）改在写报告之前，GM 日志 `2026-09-29.md` 已追加自纠块。
  口径改为：**分母一律读 `<report><counter>` 自带属性，禁止由逐类求和反推**。
- **G8 时序违规一次**：锚点写成带尾巴的 `【数据流假设】轮77` ⇒ `dag_precheck` 判 `[GATE:dag-fail] rc=1`，
  而我把 cp 接在同一条链的 `||` 回退分支后面 ⇒ **门没绿就落了笔**。已按规范重落并 `[GATE:dag-pass]`。

- [x] ✅ **r39–r61 八条已完成**（05 stale 更正｜perf 常驻判据｜a11y/clean_clone/数据权利/发布治理/许可/移动端｜
      告警读回 404→204｜存在性≠能力｜JS 侧单测起账｜红须带为什么｜判据 91→97）——原文照录迁 `part81`。

- [x] ✅ **r76+r77 构建期测试面两连**：10→11 类、62→82 用例；LINE 40.06%→91.93%→**97.75%**，
      r77 换尺补分支半边：BRANCH 83.11%→**96.28%**，门 0.35→0.85→**0.90 且新挂 BRANCH 0.90**
      （变异体判红、按字节还原判绿；分母 669→666＝删死重载，是缩水不是提升）。`part79`/`part82`/`part83`

- [x] ✅ **R75-05 真红闭合 + R76-03 两形态**：8123 一退整跑 93/98→73/98（21 套件挂同一进程）；r77 又量到同一持有者
      让 `mvn verify` 在 `repackage` 步 rc=1（红因不是门，门排在它后面）。`part79`/`part82`

- [x] ✅ **r65 两面 + savepoint 链**（`stalled_stream`／第四幕清除入口可达；savepoint r54 起 rc=0）——原文照录迁 `part80`。
