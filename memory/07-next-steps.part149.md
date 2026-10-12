# 07 - 下一步 · 卷149（r126 收尾推荐与他人面；入场与回执见卷148）

> 承卷：轮126-陪聊对标｜报告 = `交付物/对标分析报告-2026-10-12-r126.md`｜日志 = `memory/2026-10-12-r126.md`（+.part2）

## 收尾推荐（带稳定 id 与可复算前提）

- [ ] 🔴 **[推荐:R126-01｜用户操作]** **切版 v1.8.3**（清 `G12`）——前六轮同一件事，前提仍未解除：
      重建 fat jar 会覆盖他人正在 8123 服务的产物。前提：`mvn -B -f server/pom.xml package` → 四源同步 →
      `git tag v1.8.3` → 复跑 `repo_config_check`＋`release_governance_check`＋`jar_shape_check`；整跑排在 tag 之后。
- [ ] 🔴 **[推荐:R126-02｜用户拍板]** **`origin/main` 分叉 18/72**（本轮入场实测，上轮 18/69 ⇒ 他人又推 3 次）。
      三条路代价见 `07` 卷138；不收则每轮"全绿"只对工作树成立。
- [ ] 🟠 **[推荐:R126-03｜agent 自动]** **第二通道的重采节律与活链复核**：`cap-channel-<date>.json` 现在只有一份，
      且**不入电池**（走 gh api）。下一轮该做两件事：①按 fuse(7d) 节律错峰重采，让漂移尺能比"通道读数"而不是只比文件名法；
      ②`_test/bench_eight_dims_check.py` 里该格的补法死链由 `remedy_audit` 盯，接线路径若变要**先活链再落笔**。
      前提：`python _test/benchmark_metrics.py --cap-channel --out 交付物/对标数据/cap-channel-<date>.json`（单跑勿 burst）。
- [ ] 🟠 **[推荐:R126-04｜agent 自动]** **`git status` 在本仓不可信**（本轮一手）：`bench_eight_dims_check.py`
      与 HEAD 差 24/14 行却报"干净"（内容过滤器已配置）。正解＝**每个要编辑的文件先 sha256 ⇄ `git show HEAD:<path>`
      比字节**（本轮 11 个目标里 10 个 SAME、1 个 DIFF 被避开）。把这条固化成判据：改前先扫"我打算动的面"。
- [ ] 🟡 **[推荐:R126-05｜agent 自动]** **性能维按线程记账**（接续 #R123-03，前提未动）：
      `MAX_US_CPU_PER_REQ=12000` 不动；净读数档内带宽先降到 <30% 才谈收紧。**禁止**再提"扣空载能收紧"。
- [ ] 🟡 **[推荐:R126-06｜agent 自动]** **漂移闸第四次值守**：`--round r127` 应印「漂移=比对 r126」。
- [ ] 🟡 **[推荐:R126-07｜需用户拍板]** **注入壳体量**：AGENTS.md 33,916B、README.md 22,134B 均 >16,384B
      （`handoff.py volume` advisory）。动 AGENTS.md 影响全部并行会话读到的绑定表 ⇒ 不擅自 trim-shell。
- [ ] 🟡 **[推荐:R126-08｜agent 自动]** peers 5 族 blind 重采 + `peer-hygiene` degraded 件重采（错峰单跑）。

## 他人面（未代改，均带复算命令）

G8 受理面红（HEAD 评测集 85 条 ⇄ 06 声称 105，他人 +20 条未入库）；`EOL-PARITY 48 项`；
`loc_guard_check.py` 的 `quote_eval.py` 175>150；仓根 `_tmp_*` 研究抓料 **28 件**（上轮 19）；
`_test/{emotion-eval-dataset.json,emotion_eval.js,live_sync_check.py}` 与 `src/**`、`deploy/xinyu/**` 在途。
复算：`python _test/{repo_config_check,eol_parity_check,loc_guard_check}.py`。
