# 07-next-steps 分卷 · r96（2026-10-05）· 下一轮入口 r97

> 接 `part110.md`（r95③）。本轮报告 = `交付物/对标分析报告-2026-10-05-r96.md`。

## ① 本轮改判（必须先看这条再引用任何旧结论）

- r95:10-11 与 :241 的「issue 响应速度不可测 / 多数仓已关闭 issue 无人工评论痕迹」**已被实测证伪**：
  12 仓各取最近 30 条已关闭真 issue，`with_comments` = 30/30、27/30、26/30、28/30、25/30、29/29…
  唯一真零 issue = `CheaperjamRen/leemo`（人口 0）。取证 `_test/peer_issue_response_probe.py`
  台账 `交付物/对标数据/peer-issue-response-2026-10-05.json`。
- 假 NA 产地 = `peer_hygiene_probe.py:65-69`（20 条样本当人口）：`my-neuro` 实 102 条、`chibi` 实 7 条，
  旧台账两处都写 `NA(无真issue)`；r96 该类修后 NA 5→0。
- r95 §1 印 `1013.9 rps` 而 §5 称「并发无读数」= 自相矛盾，根因是数字没带口径；
  现由 `ci_perf_wiring_check` 新腿 **C-IPW-6** 常驻封口（rps 同行必须带并发档）。

## ② 本轮新增/改动的判据（8 件新套件，电池 120→128）

- `_test/ledger_age_check.py`（龄期尺，fuse 读契约不抄数字；mtime⇄文件名交叉腿；degraded 单独计数）
- `_test/browser_engine.py` + `_test/browser_engine_declare_check.py`（引擎面归因五腿，E2 棘轮基线 32）
- `_test/peer_issue_response_probe.py`（该维第一把尺，20 条自检）
- `_test/gh_cred.py`（凭据单点：三件探针此前只读 env、从不回落 `gh auth token`）
- `peer_hygiene_probe` / `peer_capability_safety_probe` 补 `--selftest` 并三个零接线探针入链
- `perf_baseline_check --ramp 8,16,32,64`（默认关；CI perf 作业显式开）
- 契约：14 blocking 不变 + deferred 7（`ledger-age-fuse` 入 deferred，理由=一次正常提交变不了绿）

## ③ r97 入口

1. **E2 棘轮降数**：把 32 个套件逐个接进 `browser_engine`（每接一个降 1，接完可把基线归零）。
   判据 `python _test/browser_engine_declare_check.py`。⚠️ 批量 Edit 撞排障手册
   「吞 def 行而 py_compile/--selftest 全过」⇒ 每改一个跑 AST 符号清点。
2. **`ledger_age` 复查节奏**：契约 fuse=7 天 ⇒ 下一轮（≈10-12 前后）15 族会再次超龄；
   重采**必须错峰单跑**，同轮 burst 已实测撞 GitHub secondary rate limit
   （r96：hygiene 12/17 行、community 5 行 403）。判"降级"要比对 NA 是否相对上一份认可台账**增长**，
   不能看 NA 个数或 rc=1（r96 就误判过一次 community 为降级）。
3. **阶梯并发第一次有了可对的上一年**：r96 是基线（8/16/32/64 = 2368/2042/2610/2631 rps，
   p95 4.8→16.1ms）。下一轮同参数复跑才能谈漂移；**不许**为了让数好看改档位或抬 400ms 预算。
4. **`MoodChat` 两腿**：r96 仍不等（2 vs 1）⇒ 继续判不可用。若某轮两腿一致则该格自动可用，零动作。
5. **`peer_issue_response_probe` 网络面仍未入电池**（承 r37 口径）。若要入链，先解决限流与耗时。
6. **维持不立项项的触发条件未变**（lint/mutation/vector/i18n + peers 并发对照）：见 r95 §3 #7/#8 与 r96 §3 #6/#7。
