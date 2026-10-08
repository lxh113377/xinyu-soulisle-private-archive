## r100 收口（2026-10-08 对标增量轮 · 四项改造，含一条负面结论）

> 全文回执与实测表：`交付物/对标分析报告-2026-10-08-r100.md`（§2.2 带宽表、§3 六字段清单、§6 遗留）；
> 权威面数字与命名纪律：`docs/PERF-BASELINE.md §1b`。

### 本轮落了什么（每条给复算命令）

- **① 判据三态纪律封口（P0）**：`clean_clone_check`/`rescan_shots_check`/`public_check` 三处的 Playwright
  导航与求值此前裸奔 ⇒ 超时逃出进程 = rc=1 而**没有任何判据结论行**（「仪器崩了」与「产品坏了」同形）。
  三段修法：超时折成**判红 + 原因**（不折 UNVERIFIED；环境档由各前置出口 `return 2`）＋ 未走到的腿逐条记
  未验（两件建腿名册 `LEGS` 作唯一分母：12 / 10 条）＋ `guarded_main()` 兜底腿（`C6`/`SX`/`PX`）。
  电池另加 **`BLIND-RED` 档**（`blind_reds()` + 双向 7 向桩）＝修类不修例。
  复算：`python _test/clean_clone_check.py --nav-timeout 1` ⇒ rc=1 点名 `TimeoutError: Page.goto: Timeout 1ms exceeded`。
- **② 性能仪器中位数口径（高）⇒ 负面结论：检测限没下压**。每档 5 次取中位数 + 丢 1 次冷启到位
  （`reduce_reps()`、台账自报 `band_rps`/`worst_band_pct`），但 10 份同口径台账实测 t8/t16 **跨轮带宽
  55.9%~76.7%**（同轮 5 次共享同一机器状态 ⇒ 噪声相关，重复不产生独立性），比 r99 单次口径的 38.4% 还大。
  ⇒ **阈值一字未动（仍 ±50%）**——没资格下压就调小阈值＝逼下一轮虚报。到手的是仪器自报噪声底
  + `noise_floor()`（带宽 ≥ 阈值的档面点名成噪声档，红照判、rc 不放宽）。
- **③ 完成态可观测（中）**：`src/js/chat-agent.js` 的 `respond` 外包 `turn()`，暴露 `window.__pendingTurns`
  （进轮 +1、`finally` −1）；`ux_guards` U2 的 45 条连发不再 `wait_for_timeout(6000)`，新增腿 **U2g** 等它归零
  ⇒ `timing_coupling` 在册唯一那条 `unobservable` **真销账**。复算 `python _test/ux_guards_check.py` ⇒ 22 项全绿。
  代价：公网差距由 1 件变 2 件（见 ⏸）。
- **④ peers 错峰重采（中）**：16 族逐个单跑（族间 sleep 20s，禁 burst）⇒ **16/16 落盘，龄全为 0 天**
  （`LEDGER-AGE-PASS 线内 16｜超 fuse 0`）。5 族 rc=1 逐条归因，不折成"重采失败"也不折成"全绿"：
  `community` 5 仓 403（`usable 11 + blind 5 == 16`）、`hygiene` 6/17 字段 NA（PROBE-PARTIAL）、
  `issue-response` 9 格 NA（多为本就无已关 issue，恒等式 8+8==16 成立）、`maintenance` 2 格两腿不等判不可用、
  `mobile` 2 NA + 4 范围外。**口径缺口登记 r101**：`ledger_age` 的 degraded 面按**文件位置**判（`_partial/`），
  所以本轮这批 PARTIAL 件在它眼里是"新鲜"——**按日期新鲜 ≠ 按取数完整**。

