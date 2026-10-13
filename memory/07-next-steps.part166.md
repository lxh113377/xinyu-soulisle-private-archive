# 07-next-steps.part166.md

<!-- 本卷为 07-next-steps.part33.md 的延续 -->

## 受理面回执（本轮收口）

- [ ] VOL-CC6BC 体量治理[L5 自动化链] _trash/ 回收区超龄 — 人工核后清空该面 `_trash`（`handoff.py recycle --list <锚点>` 逐项看）；治理链不自作清历史 —— 里面混着人工裁决过的件（由 flow 登记；状态: todo）
- [x] WF-r96-对标轮 r96 八维对标 + 四项改造（issue响应尺/并发口径封口/龄期尺+探针接线/引擎面归因+交付卫生）（由 flow 登记；状态: done）
- [x] WF-r95-契约自身结构门 契约会被后人改坏（同名/空清单/成本虚报/列了没人跑）⇒ 需常驻门（由 flow 登记；状态: done）
- [x] WF-r95-对标轮 r95 八维对标 + 五项改进（CI 契约入库/契约结构门/30 天提交率尺/台账 SNAP 刷新/电池 120）（由 flow 登记；状态: done）
- [x] WF-r94-收口 r94 收口：五轮电池取最终绿 + 门禁面复核 + 提交推送 + CI 回执（由 flow 登记；状态: done）
- [x] WF-r93-对标轮 r93 八维对标 + 四项改进（loc 门 / rollup 两新增维度 / corpus 归档 / peers 全量重采落工作区）（由 flow 登记；状态: done）
- [x] WF-r73-接入CI契约 陪聊当前未接入 CI 全绿契约（.ci/contract.json 缺失），而 ciwatch 实扫到 1 份 workflow / run 执行面 89 行 ⇒ 未接入 ≠ 没有 CI，这 89 行里没有一条是被契约点名的 blocking 判据。一致接入四步（本引擎 wflow.adapters.sevenstep 对位）：① 生成 .ci/contract.json（把 mvn verify / 关键门禁逐条列 blocking）；② 在 .github/workflows/ci.yml 里为每条加 run step 并 --sweep 复扫到 matched==declared；③ pre-push 接线 greencheck；④ 保留本项目特性（Java/Maven 档位与 8123 回归口不并入引擎）。前提可复算命令：cd 本仓 && python D:/global_skills/A-project-handoff/scripts/handoff.py flow . --status（由 flow 登记；状态: done）
- [ ] VOL-AGG-20260928 体量治理[L1 记忆卷] 体量余量聚合（6 项） — 另有 6 项待判断，合计 139169 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
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

## 受理面回执（本轮收口）
`a75211a` 首推 → CI `RED: disclaimer_forensics`（自家新判据抓到报告 §9.4 一句裸边界结论）→ 改文案不改判据 → `6c363a0` 重推 → run `36268651657` `conclusion=success`，`ci_status_check` 回 `HEAD = PASS`。`java-build` 的 `mvn package` 在 Linux runner 上实测 `Tests run: 30, Failures: 0`（run 36268051559 原文）⇒ in-build 门禁的跨环境等价性已成实测。
