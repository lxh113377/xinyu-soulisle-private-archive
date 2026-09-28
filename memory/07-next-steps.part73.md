# 07-next-steps 卷73 — r71 续（收尾推荐）

> 换卷理由：卷72 追加本段后实测 4,220 B > 4,096 B 硬限（R161 零豁免）⇒ 按「先算和后换卷」当轮拆卷。
> 旧卷（卷72）拆出后字节=3211 ｜ 本批字节=1008 ｜ 载体=volume_alloc 独占取号

## 六、收尾推荐（Step 2.6，本轮新列）

- [ ] 🟢 **agent 自动** [推荐:R71-01] 在 `repo_config_check.py` 加一条等值对账：台账末次 run 的 `self.self_face`
      必须是 `HEAD`，且 `regression_suites` 必须等于 `git show HEAD:_test/run_all_suites.py` 现算值
      （防后人把工作树面重新接回）；验收=该腿在合成"工作树面"样本上判红、在真面判绿
- [ ] 🔴 **需老大（二选一，都能开环）** [推荐:R71-02] ① 解冻对外发布 ⇒ `live_sync`/`ci_status` 转绿 ⇒ 按
      `part40:32` 链条切 v1.6.2 消 R1；② 或授权把 R1 降为 advisory（须写明"为什么可以不拦"，禁静默放宽）。
      前提复算：`python _test/release_governance_check.py`（现 `feats=6/5`）
- [ ] 🟡 **P2 可选** [推荐:R71-03] 并行第一刀：census 已 `CENSUS-PASS 101/101`，按"是否共享 8123"分桶，
      只并非共享桶；验收=`耗时 top5` 合计（现 566s）下降**且**红名单不减一条
