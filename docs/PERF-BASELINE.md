# 心屿 SoulIsle 性能基线（PERF-BASELINE）

> 口径：本地无外网 + 危机路径不调 LLM。这是**自身棘轮**（防退化），不是跨项目对比（全行业 0/16 公开可比数字，见对标 r87 §2 G5）。

## 1. 本轮实测（2026-10-01，jar 直读 src，端口 8123）

- 命令：起 `java -jar server/target/soulisle-server.jar --server.port=8123`，跑 `python _test/perf_baseline_check.py`。
- 结果：`PERF-BASELINE-PASS` —— p95=30.2ms（static 27.5/vendor 30.2/health 16.7/crisis 26.5，四目标全预算内，最紧余量 370ms），吞吐 1801.0 rps。
- 复算：同命令重跑即得；服务停后该脚本记 ENV-UNVERIFIED（未验证≠通过）。

## 2. 预算与判据

- 详见 `_test/perf_baseline_check.py` 内预算表；红线=任一目标超预算即 rc=1。
- CI/电池侧只保留尾行判据词，明细以本文件为准。
