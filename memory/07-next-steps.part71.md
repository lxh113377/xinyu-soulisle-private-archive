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
