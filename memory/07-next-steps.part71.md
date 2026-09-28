# 07-next-steps 卷71 — r70 续（收尾推荐）

> 换卷理由：卷70 追加本段后实测 4,701 B > 4,096 B 硬限（R161 零豁免）⇒ 按「先算和后换卷」当轮拆卷。
> 旧卷（卷70）拆出后字节=3748 ｜ 本批字节=953 ｜ 载体=volume_alloc 独占取号

## 五、收尾推荐（Step 2.6，本轮新列）

- [ ] 🟢 **agent 自动** [推荐:R70-01] 把 `jar_shape` 与 `jar_shape_selftest` 补进 SUITES，README 计数同步 +2
      （前提=`python _test/run_all_suites.py --list` 与 `git show HEAD:_test/run_all_suites.py` 两口径先对齐，
      并行会话那笔 101 套件入库后再动，避免同一 hunk）；验收=`repo_config_check` G4 当场等值通过
- [ ] 🟢 **agent 自动** [推荐:R70-02] 按 `suite_census` 的"是否共享 8123"分桶做**第一刀并行**（只并非共享桶）；
      验收=耗时 top5 的合计下降**且**电池红名单不减一条（并行制造假红即回退）
- [ ] 🔴 **需老大** [推荐:R70-03] 二选一即可消 `live_sync`+`ci_status`：解冻对外发布（现受 09-24「先不办」裁决约束），
      或认可"公网停在旧版"进 09-30 提交；另 PII（五人学号/手机/邮箱+指导教师）仍只有老大能给
- [ ] 🔴 **需老大** [推荐:R70-04] `release_governance` 现判红 **R1：距 v1.6.1 已攒 6 个 feat（上限 5）⇒ 该切版**
      （本轮 r70 的 feat 是第 6 个；R2c 已由 CHANGELOG 补记消掉）。**不擅自切**的理由是在册规矩本身：
      `memory/07-next-steps.part40.md:32` 定的是「push → 等 CI 绿 → `gh release create` → 远端回读 size/sha」，
      而 CI 现在因 `live_sync` 红着 ⇒ 前置不成立，而 `live_sync` 只能由 R70-03 的发布授权消。
      前提（可复算）：`python _test/release_governance_check.py`（现输出 `RELEASE-GOV-FAIL: 1 项 feats=6/5`）；
      解冻后正解 = 按 part40 那条链切 v1.6.2 并 `gh release view --json assets` 回读，**任一步失败不产生对外可见物**
- [ ] 🟡 **agent 自动（自觉型缺口，本轮未机器化）** [推荐:R70-05] 本轮我自己复现了 `memory/AGENTS.md`
      排障手册第 3 行那条已立规的坑：**用既有条目行当 Edit 锚点、替换文本里没把它回写**
      ——改 CHANGELOG 时把 `### Fixed（r69 · …）` 整行吃掉，是 `git diff --numstat` 的 `20/1`（新建段本该零删除）暴露的，
      已按原字恢复（标题集 119→120，missing 0）。**当前仍是"人眼看 numstat"的自觉型**。
      机器化路径（下轮做，零 SUITES 改动）：在既有已接线的 `release_governance_check.py` 加一条判据
      「CHANGELOG 的 `### ` 标题集必须是 `HEAD~n` 的**超集**（只许增不许消）」，反例＝拿本轮那次吞行当样本
      （先证它会红，再证恢复后转绿）；前提可复算：`python - <<'PY'` 版标题集差集打印。
