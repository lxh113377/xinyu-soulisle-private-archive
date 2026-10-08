# 任务卡 · 对标 r101（2026-10-09，QD 端自动执行轮）

> 建卡时刻：动手前（早于首个源码写盘），符合致命纪律 #15。计划权威源 = `C:\Users\37533\.qoder-cn\plans\still-flint-eagle.md`；G8 数据流假设块 = GM `memory/2026-10-09.part5.md`（`dag_precheck --require-mark 轮101` ⇒ `[GATE:dag-pass]`）。

## 本轮目标
接续 r100 §4「r101 入口」，按优先级完成**四项工程改造**并出增量对标报告；四项全部落在**判据层**（受理面失真 > 产品功能），产品源码零新增功能。

## 验收判据（二元，逐条附复算命令）
1. 耦合尺跨函数扩面：`python _test/timing_coupling_check.py` 门面行 `C1=` 从现测 6 回升至实测值，且 `--baseline <现测-1>` ⇒ rc=1（棘轮仍咬）；`--selftest` 含正例/两反例/变异四腿全过。
2. `ledger_age` 件内 NA 面：当日真面**必须 FAIL 一次并点名 `peer-memory`**（声明 `blind=0` 而件内 5 处 `"NA`）；未知 schema ⇒ rc=2；waive 机器可读 + 带到期条件。
3. 按档定阈：`compare` 走 per-tier 阈（分子取 `adjacent_worst_pct×2`），三向反例腿证明「检测能力变强而非调小掩盖」；t8/t16 记 `NA(noise-floor)` 且可比档面数同步减少。
4. 假理由普查：孤儿判据腿进 `repo_config_check`（不新建重复尺）+ 新件 `claim_face_check.py` 名册制（权威函数 import，禁第二份 grep）；三条在册声称销账后 rc=0。
5. 收口：`python _test/run_all_suites.py --exclude-llm` 全绿 ⇒ 才走 `push_and_watch.sh` 并取 CI job 回执；任一红 ⇒ 停下报「未推 + 红在哪」。

## 备选方案与取舍（≥2）
- A. **顺位①改用「把等待逻辑内联回驱动件」** —— 弃：`_test/loc_guard_check.py` 门 150 行，实测 `public_check.main=130`（余 20）、`clean_clone.main=89`+`drive_page=77`（内联必超）；且 LOC 取数面是 `git ls-tree HEAD`，未入库件根本不被看见 ⇒ 内联等于在册反例「没锁住的余量，不是成绩」。
- B. **假理由普查新建一把独立尺同时判「接线面 + 读数声称」** —— 弃：`repo_config_check` 已握 G16/G19/⑰、`ci_contract_check` 握契约接线面、`ci_perf_wiring_check` 握性能步接线，同事实两处判必漂移 ⇒ 拆两半，孤儿腿并进既有 `gate_doc_audit()`，只把「读数声称」这块无人持有的新建。
- C. **本轮一并做 peers 侧 SNAP 重采 + 403 补采** —— 弃：`peer_community_probe.py:278-280` 无 `--repo`、无断点续采，`--repo` 语义是替换名册会把 denominator 16 缩成 5；裸补采必再造分母失真，且限流窗口不可控 ⇒ 登记 r102 并写明前置。
- D. **选定**：S0 先分级复验并把 r100 欠账补入库（否则 ①②③ 在受理面无数据），再按 ④a→①→③→②→④b 顺序执行。

## to-do
① S0 复验+补入库 ② ④a 孤儿腿 ③ ① 耦合尺扩面 ④ ③ 按档定阈+台账补字段 ⑤ ② NA 面 ⑥ ④b/④c 声称件与勘误 ⑦ 整跑+推送+CI 回执 ⑧ r101 报告 + 07 分卷 + CHANGELOG + 反哺

## checkpoint / 回滚预案
每项改完即 `--selftest` + 真面各取一次 rc（rc 不接管道取，防「退出码死在管道里」）；提交一律 pathspec 限定（本仓 53 件未跟踪项含他人 `交付物/AIC/*` 21 件、`task-card-r98*`，**禁 `git add -A`**）；回滚锚 = 本轮首个提交前的 HEAD `ae9b384`（`git revert` 逐提交回退，不动他人提交）。破坏性双前提：本仓在 Git 版本控制内 + 远端已有可载回副本 ⇒ 满足；本轮不删除任何文件，产物只增不改名（除已登记的旧件名回写）。

## 决策记录
- 阈值口径与 r100 入口原文**分叉**：入口写「相邻轮最坏差×2」却引了 `cross_round_band_pct` 的数（16.6/9.2）；本轮按被比对象（`books[-2]/books[-1]`）取 `adjacent_worst_pct` 为分子，分叉理由与两口径对照表写入 r101 报告 §2，不静默改数。
- 耦合尺基线 9 → 实测值属**口径变更**（旧新读数不可比），登记进 CHANGELOG 与 `docs/quality-gates.md`，不当成绩。
- 对外动作零：不向上游提 issue/PR、不发版、不打 tag、不改 pom 版本（沿用 r100 §2.6 裁决）。
