# 07-next-steps.part117.md

<!-- 本卷为 07-next-steps.part116.md 的延续 -->

## ④ 收口回执

2. **破坏性批量操作先 dry-run**：`_r94_eol.py` 现默认 dry-run，`--apply` 才改盘；
   两道闸：只碰文本类扩展名 + 前 8KB 含 NUL 一律跳过。**属性表会漏，字节不会。**

产品面：`eol_parity` 扩为双面（已跟踪/未入库两个分母都印在门面行）+ 自检补 4 条未入库腿。

## ③ 下一轮入口（r95）

1. 8 个 probe 的写盘段只验了 `peer_repro_probe --self-only --json` 真落盘，其余 7 个未实跑 ——
   下轮重采用到哪几个就验哪几个，别拿「同构代码」当已验。
2. loc 阈值 2000/150 是借来的（opensoul `check:loc`，已坐实其命令行）；本仓既有更严约束是
   `size_budget` 字节预算与 Core P0.8 函数 ≤50 行，两把并存，面板已并列打印。
3. 维持不立项项触发条件不变：lint 门（2/16）、向量长记忆（7/16）、i18n（3/16）、插件协议。

## ④ 收口回执

- `loc_guard_check.py` → `LOC-PASS`（超限 0）｜`--selftest` 17/17
- `benchmark_metrics.py --selftest` 与 HEAD 版逐字相同（960 字符，rc=0）
- `BENCHMARK-METRICS-PASS`（16/16 仓，产物 `benchmark-metrics-r94.json`）
- 两份台账落盘 + `ROLLUP-PASS`（产物 `benchmark-rollup-r94.json`，轮次名自动跟随）
- 8 个 probe 的 `date -u` 修复：编译过 + `--self-only --json` 实跑落盘
- **收口全量电池：第 5 轮 `116/116 rc=0 ALL-GREEN`**（`交付物/对标数据/bench-r94-battery5.log`，合计 919s，台账指纹 `sha256=f874b118…`）。前 4 轮各红 1–2 条且**各不相同**，逐条归因见报告 §2.6。
- 门禁面复核（收口时现跑）：`LOC-PASS`（enforce 身份）｜`EOL-PARITY-PASS`（text 461 / binary 28）｜`REPO-CONFIG-PASS` 17 项 18 判据号｜`DELIVERABLE-INVENTORY-PASS`｜`DISCLAIMER-CLEAN` 48 份（交付物 2 + _历史轮次-对标 46）0 缺口｜`BRAND-PASS`。
- **提交 `1de2a9a`**（已推 `origin/main`，本地 == 远端）；CI run 在后台，收口后补回执。
- 唯一未纳入提交的三项（按铁律排除）：`memory/AGENTS.md`（并行会话在途）、`.ci/`（r90 遗留，未做 `--sweep` 复扫到 `matched==declared`，不在未验状态替他入库）、`memory/07-next-steps.part105.md`。

- [x] ✅ [r93 → r94 已收] **loc 门超限治理**：r94 先修尺（22→8，14 项为「Java 类 / JS IIFE 被当函数」的误判）
      → 拆 10 个真超限函数 → **超限 0（LOC-PASS）** → 切 `enforce` 并加接线自证（门有牙）。
      报告 `交付物/对标分析报告-2026-10-03-r94.md`；台账 `part107`

- [x] ✅ [R90 新 · r95 已收] **CI 全绿契约**：台账原文记的「须手写 `.ci/contract.json` blocking 清单，再加 step 并
      `--sweep` 复扫」在 r95 查清**两处不成立**——`greencheck bootstrap` 实测 `checks=[]`（自写电池不是标准配置）、
      `greencheck.py` **无 `--sweep` 子命令**（`--help` 实测仅 panel/run/show/bootstrap/ledger/--selftest）。
      真因不是「没写清单」而是**契约从未入库** ⇒ `greencheck run` 恒 UNKNOWN ⇒ pre-push 钩子恒放行。
      已改手写 blocking 14 条（实测 10021ms/20s）**并入库**，回执 `[greencheck] GREEN` rc=0 10.1s；
      另立 `_test/ci_contract_check.py`（9 腿/自检 15 条）盯契约自身。`part108` §①②

- [x] ✅ [r96 已收] **两处「没有取证的话」被实测换掉**：「issue 响应速度不可测」被 12 仓实测证伪
      （假 NA 产地 `peer_hygiene_probe.py:65-69` 已类修，NA 5→0）；r95 §1 印 rps / §5 称并发无读数的矛盾
      由 C-IPW-6 封口 + `--ramp 8/16/32/64` 出曲线。报告 `交付物/对标分析报告-2026-10-05-r96.md`；详述 `part111`

- [x] ✅ **推平完成**（本轮代收口）：补r91小节R2c转绿→`1354466`→直推`2d34e7b..1354466`
      →`CI-WATCH-GREEN（2条）`。本地==远端。
