# 07-next-steps.part167.md

<!-- 本卷为 07-next-steps.part160.md 的延续 -->

## 【r131 续做补记 · 另一会话 2026-10-13 02:2x，权威细节在报告 §8.5/§9】

四项改造的依据全部来自八维对标差距，且刻意各占一个维度：

| 项 | 闭合哪个维度 | 交付 | 回执 |
|---|---|---|---|
| S1 性能可复算尺 | 第 4 维（历轮写「不可测」） | `_test/perf_api_check.py` | selftest 18/18；PERF-API-PASS（health p95 17.49 / emotion 15.69 / 并发 8×32 全成功 rps 1526） |
| S2 成本总量闸 | 第 1 维（r128 只堵突发，总量敞口仍在） | `UsageLedger` + `QuotaFilter` + `/api/usage` | 新增 20 例单测全绿 |
| S3 记忆可携带 | 第 1+5 维（数据权只做了「能删」） | `MemoryPortService` + `MemoryPortController` | 新增 15 例；契约 12→15 路径，运行态 15/15、**C6b 零豁免** |
| S4 文档厚度与防腐烂 | 第 7 维（4 ⇄ lobe 51 篇） | `tutorial-05/06` + `docs_tutorial_check.py` | T1–T4 全绿 + 4 类篡改被抓 + 2 条防误报反向腿 |

补挂：棘轮 `server_hardening_check` **H1–H4 → H1–H6**（六条变异腿逐条打翻、还原后零红）。
接线：电池 **185 → 188**；`suite_count_sync --apply`；`REPO-CONFIG-PASS 18/18`。
测试：JUnit **134 → 169 例**；LINE **95.23%** / BRANCH **90.58%**（门 0.90 双路未红）。
核心能力：**CORE-CAP-BASELINE-PASS**（N1 105 条、回归 0/104；N2 31/31）—— 本轮未碰 `emotion-engine.js` /
`face-engine.js` / 评测集（并行会话在途面）。

## 二、r131 入口（按值排序）

1. **换新 fat jar 后重取性能基线**：当前两份台账一份打 8123（他人旧产物）、一份打 8130（本轮新代码实例）。
   `perf_api_check` 的**指纹不含版本号**（已知缺陷）⇒ 换产物必须重跑 `--calibrate` 并更新 `THRESHOLDS`。
2. **待 8123 换新后把 `api_contract_check` 的 C4 从 `--base 8130` 切回默认**：默认面下 `/api/memory/search` 仍超时（他人产物面）。
3. **判据层体量治理**（7.27:1）：本轮仍**未动**（会碰并行会话在途判据），维持 P-2。
4. `mvn test` 的 2 红（`EmotionControllerTest` 硬编码 85/100%）持续属并行会话在途（评测集 105 条），**非我方**，不修。
5. 向量语义记忆 / 渠道适配 / 插件协议 / i18n —— **需老大拍板**（命中架构决策 #1 重评条件）。

## 【r131 续做补记 · 另一会话 2026-10-13 02:2x，权威细节在报告 §8.5/§9】

上文第二节第 1、2 条**已经做完**，别重做：
- 产物身份已修：`/api/health` 加 `build`（fat jar 实测 `jar:soulisle-server.jar:071a50bf59a4:28486290`；
  **8123 实测无此字段 ⇒ 实证它跑的是旧产物**）。perf_api_check 指纹已纳入并支持 `--tag`。
- fat jar 基线已取：`交付物/对标数据/perf-api-2026-10-13-r131-fatjar.json`
  （health p95 16.86ms / emotion 24.52ms / 并发 8×32 rps 1161，PERF-API-PASS）。
- 契约判据会先报产物身份（缺失 ⇒ 点名"不可当新代码证据"；`--require-build` ⇒ rc=2 未验）；
  契约与基准都带了限流自愈（撞 429 等 22s 重打一次）。
- 提交：`5595278` `f49afa0` `8e66609` `9b9a32f` `3505725`。
**⚠️ `_test/` 曾于 02:08 被未登记清空（178 个 D）后又恢复**；恢复他人目录时用
`git restore`（索引源），别用 `--source=HEAD`（会盖掉索引里他人暂存的版本，本会话踩过已修正）。
**selftest 清点**：100 套件 97 绿，3 红全属在途面（breakpoint_scale←voice-call.css；
repo_config selftest；timing_coupling←quote_eval/face_check），待收敛勿抢修。
