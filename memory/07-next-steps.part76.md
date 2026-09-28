# 07-next-steps 卷76 — r74（2026-09-28）

> 换卷理由：卷75 是 r73 的账（`feats=8/5` 时期），本轮 r74 另起一卷，避免同卷混写；
> 取号由 `volume_alloc.py` 独占（dry-run 实测 n=76，existing_matched=75）。
> 本卷条数与数字均为当轮实测，复算命令逐条附在 `前提=`。

## 本轮已落地（不再挂账，只留复算入口）

- 同址尺（文档维/性能维）：`python _test/benchmark_metrics.py --selftest` ⇒ `SELFTEST-PASS … r74 同址尺…`；
  外部变异对照 ⇒ `MUTATION-OK: 10 条新规则各自绑定一条只有它能使其翻红的腿`。
  现采读数（08:59 UTC，16/16）：`docs_site 9/16`｜`agent_facing_doc 7/16`｜`readme_thorough 6/16`｜
  `changelog_root 3/16`｜`bench_script 3/16`｜`ci_perf_step 0/16`｜`published_numbers 0/16`；self 四项全有、两项无。
- 聚合器收口行假 `rc=0` 已修 + 回归锁 G18：`python _test/repo_config_check.py` ⇒
  `合计 16 项，失败 0 项`；`--selftest` ⇒ 71 条合成篡改断言（64→71）。
  二元对照实测：`--only js_syntax_selftest` ⇒ `BATTERY: 1/1 rc=0`/shell 0；`--only release_governance` ⇒
  `BATTERY: 1/2 rc=1 RED(判红): release_governance`/shell 1。

## 仍挂账（四态不折叠；`前提=` 均可复算）

- [ ] 🔴 **R74-01 发布授权二选一**（接续 R70-03/R71-02/R73 同源）：`前提=python _test/release_governance_check.py`
      ⇒ 现印 `feats=9/5 unreleased=89`，本轮 feat 提交落盘后将到 **10/5** ⇒ 这把锁每轮自紧一格。
      处置只有两条：授权切版+发布（同时消 `live_sync`/`ci_status`），或授权把 R1 降 advisory。**我不擅自放宽、也不擅自发布。**
- [ ] 🟠 **R70-01 `jar_shape` 两条 SUITES 名额 + README 计数 + `docs/quality-gates.md` 证据行**（第 5 轮未动）：
      `前提=git cat-file -e HEAD:_test/suite_resource_census.py` ⇒ 仍 NOT in HEAD；`README.md`/`run_all_suites.py`/
      `docs/quality-gates.md` 三处仍 ` M`（他人在途）⇒ 避让原则不变，他人入库后同批改。
- [ ] 🟠 **R74-02 07 的"当前态摘要层"**（本轮 §1b 派生）：peers 把 agent 说明做成单文件直读（`agent_facing_doc 7/16`），
      我方 07 已 76+ 卷、入口靠壳指针 + 分卷目录 ⇒ 检索成本是我方独有负担。验收：给 07 加一层
      "只含未完成 P0/P1 + 复算命令"的 ≤1 屏摘要，并由判据钉住其与末卷等值。**禁**把手抄计数写进摘要（G17 同族）。
- [ ] 🟡 **R74-03 README 公开性能数字**（低优先，peers 亦 0/16 ⇒ 非差距）：若做，**顺序不能反**——
      先在 `perf_baseline_check.py` 加"引用值 ⇄ `BUDGETS` 常量等值"腿，再改文案；且 `README.md` 现为他人在途。
- [ ] ⚠️ **G18 的前提风险（如实记）**：本轮对 `run_all_suites.py` 的修复走 HEAD-blob 隔离，
      他人工作树里那份**没有**我的修复 ⇒ 若他们直接整文件提交，收口行会被覆盖回硬印。
      兜底＝G18 在 HEAD 面判红并点名（红因原文含"硬印 rc 字面量"），一次正常提交即可变绿 ⇒ 属可自愈闸。
- [ ] ⏳ iCAN 报名 PII（截止 **2026-09-30**，剩 2 天）：非我方可推进，唯一动作在老大侧。
- [ ] ⏳ 真机复跑、flake 对标原文、8123 旧 jar 进程刷新（`python _test/build_jar.py` 前先查占用者）。

## 推荐下一步（≤3 条，带稳定 id）

- `[推荐:R74-A]` agent 自动：他人三件入库后补 SUITES/README/quality-gates 三处（R70-01 同批）。
- `[推荐:R74-B]` 用户操作：发布裁决（R74-01）——决定 `live_sync`/`ci_status`/R1 三条红的一次性清零。
- `[推荐:R74-C]` P2 可选：R74-02 摘要层（先量"下一轮不带记忆的人要读几卷才能知道当前态"作分母，再动笔）。
