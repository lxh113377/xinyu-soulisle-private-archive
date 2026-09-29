# 07-next-steps.part96.md

<!-- 本卷为 07-next-steps.part91.md 的延续 -->

## ⑥ 取数入口前置自证（r81 建议 5 落地）

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
