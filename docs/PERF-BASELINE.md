# 心屿 MindIsle 性能基线（PERF-BASELINE）

> 口径：本地无外网 + 危机路径不调 LLM。这是**自身棘轮**（防退化），不是跨项目对比（全行业 0/16 公开可比数字，见对标 r87 §2 G5）。

## 1. 本轮实测（2026-10-02 r91，jar 直读 src，端口 8123）

- 命令：起 `java -jar server/target/soulisle-server.jar --server.port=8123`，跑 `python _test/perf_baseline_check.py`。
- 结果：`PERF-BASELINE-PASS` —— p95=28.6ms（static 16.2/vendor 28.6/health 17.0/crisis 15.8，四目标全预算内，最紧余量 371ms），吞吐 1013.9 rps。
- 与上一轮（10-01：p95=30.2ms / 1801.0 rps）相差属**同机抖动量级**：吞吐那格受并发窗口与本机负载影响大，
  判据盯的是 400ms 预算与 50 rps 地板（数量级退化），不是名次。
- 复算：同命令重跑即得；服务停后该脚本记 ENV-UNVERIFIED（未验证≠通过）。
- CI 复跑位（r91 起）：`.github/workflows/perf-baseline.yml`（周常 + `server/`/`src/` 变动触发），
  接线与「README 数字 ⇄ 本文件数字」的一致性由 `_test/ci_perf_wiring_check.py` 常驻盯。

## 2. 预算与判据

- 详见 `_test/perf_baseline_check.py` 内预算表；红线=任一目标超预算即 rc=1。
- CI/电池侧只保留尾行判据词，明细以本文件为准。
