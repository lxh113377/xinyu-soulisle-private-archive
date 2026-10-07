# 07-next-steps 分卷 · r98 续卷（踩坑逐条 + 电池面 + r99 入口）

## 本会话自己踩的坑（逐条留证，不写成「已修复」就翻篇）

1. **变异脚本污染被测源**：第一版脚本在 `write_text` 之后、`finally` 之前抛 `IndexError`
   ⇒ 没走到还原，而它打印的 `restored_equal=True` 是拿**坏版本自己**当基准比出来的。
   那一刻格式串被削短、参数仍是 9 个 ⇒ `TypeError`。已用 Edit 修回并复跑三道门。
   教训：① 还原放 `finally`；② 校验基准必须是动手前先取的字节。
2. **崩溃冒充「有牙」**：前三条变异全以 `TypeError` 结束、rc 也是 1 ——
   按「有输出且非 PASS 就算咬住」会把崩溃读成判红。同步删占位符与实参后重做，
   才有「不崩溃 + 断言点名」的真红。
3. **门面行超截断线**：第一版 187 字符 ⇒ `run_all_suites.py` 的 `line[:110]` 让受理面上
   基线/恒等式/C1 计数**全部不存在**。抽出 `face_line` + selftest 真调它（对字面量断言是装饰腿）。
4. **夹具数字没落在自己声称的区间**：正例写「±2% 内」而实算 +4.8%。
5. **一份逻辑两份拷贝**：`load_ramp` / `load_ramp_of` 合并为 `parse_ramp` 唯一实现
   （否则 selftest 走一份、普查走另一份，改一份另一份不动）。
6. **`perf-ramp-2026-10-05.json` 的 mtime 被变异脚本改了**（字节已还原，`git diff --exit-code` 实测
   内容与 HEAD 一致）。这恰好现场演示了 `ledger_age` 为什么按**文件名日期**取龄：
   mtime 被踩之后 `LEDGER-AGE-PASS 16/16` 仍成立、分歧 0。

## 电池与判定面

- 电池 **129 → 132 套件**；README 计数同步（改 md 必复跑 `repo_config_check`）。
- 判定面全绿：`REPO-CONFIG-PASS 17 项/18 判据号`、`VERDICT-EXIT-PARITY defect=0 套件=101`、
  `LOC-PASS`、`BUDGET-PASS total=849,529`、`LEDGER-AGE-PASS 16/16`、
  `RELEASE-GOV-PASS feats=1 余量 4`、`DISCLAIMER-CLEAN 51 份缺取证 0 处`。
- 全量电池整跑回执见 §「收口」行（同一条事实不两处判）。

## r99 入口（四条，按可执行性排序）

1. 🔴 **采第二份 ramp 台账** ⇒ `perf_ramp_delta` 从 rc=2 UNVERIFIED 变成有结论。
   命令：`python _test/perf_baseline_check.py http://127.0.0.1:8123 --ramp 8,16,32,64 --json …`
   （**这是让它从「诚实未验」变成「有读数」的唯一动作**；没有它本件在受理面上没有漂移结论）。
2. 🔴 `timing_coupling` 的 **16 处 C1_HARD 逐件评审**，先动 `ux_guards_check` 的 7 处。
   ⚠️ C1 只是**形状**（定长→取数→立刻消费），哪些真的等错了**判据无法知道**（它不知道被等对象
   何时算好）⇒ 逐件评审是人工判断，本轮刻意不做。
3. 🟠 `ledger_age` fuse=7 天 ⇒ ~10-12 会再超龄；重采须**错峰单跑**（r96 实测同轮 burst 撞
   GitHub secondary rate limit：hygiene 12/17 行、community 5 行取数 403）。
4. 🟢 登记不执行：`--selftest` **条数**无人对账（`ledger_age` 文档声称 27 / 实测 32；G16 只核脚本名
   不核条数）。正确形态需要先想清「文档里的条数」是断言还是描述 ⇒ 不急。
