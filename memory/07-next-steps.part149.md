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
- [x] 🟠 **[作废:R126-04｜r127 实测否证]** ~~把"改前扫一面"固化成判据~~：r127 复核发现**现有尺已经覆盖这一类**——
      `_test/eol_parity_check.py` 的红因形态之一就是「工作树字节 != blob 字节（且该文件没有待提交改动）」
      （本轮实测点名 `交付物/微表情识别-理论与应用综述-2026-10-11.md` 等）。⇒ 再建一条"比字节闸"就是
      **同一事实两把尺**（违 r123 立的『同一事实只许一处判』）。真正的缺口不是缺尺，是**我没在动手前查现成的尺**：
      正解＝编辑任何 tracked 件前先跑 `python _test/eol_parity_check.py` 并在其红项里查该路径
      （口径已写进 `docs/tutorial-04-running-the-checks.md` §5）。一手观察仍保留：`bench_eight_dims_check.py`
      当时与 HEAD 差 24/14 行而 `git status` 报"干净"（内容过滤器已配置），本轮 11 目标 10 SAME、1 DIFF 被避开。
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
