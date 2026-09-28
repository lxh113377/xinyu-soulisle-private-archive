# 07 分卷 · 卷83 — r77 失败面（2026-09-29）

> 与卷82 同轮：交付记录的两侧必须都写下，这里只放失败面（成功面在卷82）。

## 失败面（同条登记，禁只写"已交付"）

- **R77-01 后台任务通知把"包装器退出"当成"子进程完成"**：第一次 `run_all_suites.py` 后台跑，
  通知回 `completed exit code 1` 而日志 0 字节；实际子进程 **pid=29080 仍在跑**
  （`Get-CimInstance Win32_Process -Filter 'ProcessId=29080'` ⇒ `python.exe _test/run_all_suites.py --exclude-llm`，
  CreationDate 02:53:39）。第二次跑被并发锁正确拦下（`BATTERY-UNVERIFIED(并发)` rc=2，
  且它按 `OpenProcess` 判属主"活着"——判得对，是通知错了）。
  通则：**后台测量的完成信号要取被等对象本身**（子进程还在 ≠ 任务完成），与 r76"async wait = completion signal"同族。
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

