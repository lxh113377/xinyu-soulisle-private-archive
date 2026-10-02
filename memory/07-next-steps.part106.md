# 07-next-steps 分卷 · r93（2026-10-02 对标轮）

> 本卷只记 r93 轮的台账变化；壳层 `07-next-steps.md` 的 P0/P1 摘要按本卷实况更新。

## ① 本轮状态（r93）

-八维对标完成，报告 `交付物/对标分析报告-2026-10-02-r93.md`（留根目录，为最新一轮）。
- **r92 遗留三项全部销账**：
  - #2 peers 全量重采 ✅（`BENCHMARK-METRICS-PASS`，产物 `benchmark-metrics-r93.json` 204,332 B，日志落工作区）
  - #4 loc 门 ✅（`_test/loc_guard_check.py`，report-only，22/156 超限，`--selftest` 9/9）
  - #5 letta → letta-code 换址 ✅（分母仍 16；补录档正确识别）
- r92 未跑的**全量电池**本轮已跑（基线 110/112，红在两条 LLM 套件，根因=服务端未注入 `DEEPSEEK_KEY`；
  带密钥重启 8123 后三条 LLM 套件全绿）。
- 顺手修掉一处**假绿**：`j2_chat_contract.py` 印 FAIL 却 rc=0（判据主动报绿）。

## ② 新增/变更的门禁与判据

| 件 | 类型 | 现状 |
|---|---|---|
| `_test/loc_guard_check.py` | 新增 | report-only；`--enforce` 才阻断；**本轮不切 enforce** |
| `_test/bench_rollup.py` | 新增 | 只读汇总；缺源 rc=2 |
| `_test/disclaimer_forensics_lint.py` | 改| 扫描面扩双目录（`交付物` ∪ `交付物/_历史轮次-对标`） |
| `_test/j2_chat_contract.py` | 改 | 补真退出码 + JS 报错参与判定 + `__main__` 守卫 |
| `_test/benchmark_metrics.py` | 改 | peers 名册换址 |
| `_test/run_all_suites.py` | 改 | SUITES 112 → **116** |
| 电池 | — | README 套件数同步为 116（`repo_config` G4）；两脚本登记 `docs/quality-gates.md`（G16） |

## ③ 体量治理：corpus 归档（含分母变化声明）

- 46 份历史报告 `git mv` 到 `交付物/_历史轮次-对标/`（目录名与 `deliverable_inventory_check`
  的搬卷 selftest 夹具一致），新增合并索引 `交付物/对标总览-合并索引-2026-10-02.md`（本轮留在根）。
- **分母变化声明**：归档前 46 份（全在 `交付物` 根），归档后 46 份（0 + 46）——**覆盖面未缩小**，
  可复核的只有门面行分母来源从单根变双根。体积收益 ≈0.5 MB（与r90 旧判断一致），
  真正的收益是「46 份散落」变「一份索引 + 一个归档目录」。
- 深链同步：`README.md` / `ROADMAP.md` / `docs/quality-gates.md` / `CHANGELOG.md` 中指向旧根路径的
  5 处深链已改指归档目录（**只改路径不改结论**；报告正文里的历史取证 glob 一律不动，改了就等于改证据链）。

## ④ 下一轮入口（r94）

1. **loc 门超限治理（P1）**：22/156 文件超限，最大 `benchmark_metrics.py`（1913 行/ 最长函数 628 行，
   成本主要是 selftest 逐腿堆叠）。清零后再切 `--enforce` 并加 CI 接线判据。
2. **两份 peers 辅助台账重采**：peer-quality-tooling / peer-repro 的分母 16 里仍是旧 `letta-ai/letta`，
   本轮已在 rollup 标 stale 但未重采。
3. **llmProxy 读数校准**：`ci_job数` 两个读数并存（workflow 文件数 4 vs job 条数 5），
   下轮统一口径或明确各自定义域。
4. 仍需老大在场的旧项不变：目标机器（IP/登录/安全组）、共享 CloudBase env 隔离决策、
   品牌一句话、曾进过会话输出的明文 Key 撤销。

## ⑤ 本轮方法论留档（值得复用）

- **判据主动报绿 > 判据漏报**：`j2_chat_contract` 印FAIL 却 rc=0，属"状态与事实相反"，
  比漏报更坏（漏报是没看见，报绿是主动说谎）。排查电池时**不要只看 rc**，要看印出的结论行。
- **取数面错误会伪造结论**：本轮第一遍peers 深挖探针硬编码 `main` 分支，
  在默认分支不同的仓上取到空清单，差点把「有 lint 门」读成「无门」。复核证据原文后确认是探针的错。
  与 r71「git 面/工作树混面」同族：**尺错了要改尺，探针错了要改探针，别急着改结论**。
