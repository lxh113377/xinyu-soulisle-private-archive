# 07 卷33 — r41 对标轮（测试资产与质量内建）台账 2026-09-27

## 本轮闭合（均有当场证据）
- ✅ **in-build 单测从 0 到 30**：`server/src/test/java/`（EmotionLexiconTest 6 / EmotionEngineTest 11 /
  EmotionClassifierTest 4 / SafetyGuardTest 9）+ `spring-boot-starter-test` + surefire `workingDirectory`
  → `Tests run: 30, Failures: 0` / `BUILD SUCCESS`。闭合 AGENTS.md 决策 #1 第②条的空头主张（已补更正注）。
- ✅ 常驻判据 `_test/java_test_guard.py`（T1 用例下限 / T2 依赖在位 / T3 CWD 前提 / **T4 CI 构建步未跳测** /
  T5 分母非空）+ `--selftest` 10 桩 + 3 变异体。
- ✅ 新观测面 `_test/peer_test_asset_probe.py`：16 仓双通道，`in-build=9/16、覆盖率配置=6/16、self=0`
  → 快照 `交付物/对标数据/peer-testassets-2026-09-27.json`。探针本体不入电池（承 r37 口径），其 `--selftest` 入电池。
- ✅ 聚合器折叠规则补 `-` 续行与 stderr 兜底（`FOLD-SELFTEST` 5 桩 + 3 变异体）；`online_check` 固定 sleep
  改完成态轮询（实测 probe 4.2s / chat 2.1s 落定）；整跑加**并发锁**（第二条 rc=2 未验）。
- ✅ `disclaimer_forensics` 分母改「从目录现读」（`--all`）：首跑即抓到新报告一句裸「不可比」。
- ✅ 电池 54 → **58**，定版整跑独占 **58/58 ALL-GREEN**；README/`docs/quality-gates.md` 声称值由 G4/G10 复算。

## P1（截止后立即，按此序）
- [ ] WF-voice-echo-guard voice 回声误触发收口：念白期转写污染 pending + 缺尾音窗（voice-call.js 收句侧无过滤）（由 flow 登记；状态: todo）
- [x] QTE-V1 表达语料库·核对与审读（五维质检+修订闭环）（由 flow 登记；状态: done）
- [x] QTE-R4 表达语料库·哲学思辨组（研究员）（由 flow 登记；状态: done）
- [x] QTE-R3 表达语料库·网络热句与流行文化组（研究员）（由 flow 登记；状态: done）
- [x] QTE-R2 表达语料库·名家名句组（研究员）（由 flow 登记；状态: done）
- [x] QTE-R1 表达语料库·文言与古诗词组（研究员：搜集+考据+条目卡落盘）（由 flow 登记；状态: done）
- [x] WF-r101-对标轮 r101 八维对标 + 四项改造（耦合尺跨函数扩面／ledger_age 件内NA／按档定阈机制+负面结论／G20 声称对账与孤儿判据接线）（由 flow 登记；状态: done）
- [x] WF-r100-对标轮 r100 八维对标 + 四项改造（判据三态纪律/性能中位数口径/__pendingTurns 完成态/peers 错峰重采）（由 flow 登记；状态: done）
- [x] WF-r97-voice退出态 voice 退出态真缺陷修复 + v1.8.1 切版（r94/r95/r96 三轮挂账项）（由 flow 登记；状态: done）
