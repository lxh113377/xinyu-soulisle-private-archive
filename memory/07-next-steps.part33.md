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
1. `@SpringBootTest` 上下文冒烟：断言 `/api/health` 三项自证 + 词表加载条数（对标 MoodChat 脚手架，
   但补上"Spring 上下文真的起得来"这一层——现在只有带外 HTTP 判据在验，jar 起不来在构建期内无人知）。
2. `voice` / `public_check` 失败面补「网络类 / 产品类」分档（同 `online_check` 本轮做法，别只改一条）。
3. 整跑累计上游限流的显影：第 N 次起记 `NET-FLAKE(n)` 并保留 rc=1，**不放宽**但要能一眼看出该查上游还是查代码
   （实证：并发窗口 55/58 三条红 vs 独占 58/58 全绿，同一份代码）。
4. `@ParameterizedTest` 按 SSOT 逐情绪生成用例（覆盖面按结构单位算，不按人肉句子算）。
5. 沿用排期：three.js r128→r186、Playwright 假媒体设备、persona 维度记忆、真机帧率。

## 本轮方法论补一条（进 M5 清单候选）
**账面指标看不见的维度要定期换面量**：`in-build 用例数` 这一维，★/停更/workflow 数/文档件全都不是零，
唯一 ★1 的 Java 同栈对手反而**有**脚手架 ⇒ "能力矩阵"式对标对本维完全失明。
与 r37「dependabot 在册但 PR 没人处理」同族：**配置在册 ≠ 行为发生**，能力位 ≠ 使用。
