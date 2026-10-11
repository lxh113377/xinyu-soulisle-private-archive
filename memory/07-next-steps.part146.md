# 07 - 下一步 · 卷146（r123 对标五轮收尾推荐，2026-10-12）

> 报告 = `交付物/对标分析报告-2026-10-12-r123.md`；日志 = `memory/2026-10-12-r123.md`；G8 块 = GM 卷18（轮123-陪聊对标）。
> 本轮四项：①清我 r122 埋的**台账形状违规**（自造键 `blind_or_na` 不被龄期尺认得 ⇒ 18 族一起被打成未验），
> 键改回 `na` + 装 `shape_contract()` 契约腿 ⇒ `LEDGER-AGE-PASS` rc=0；②建 `docs/QUICKSTART.md`
> 关掉照出的唯一真差距（第 7 维教程位），并同步 `docs/README.md` 索引（G19）；
> ③表情离线腿的可证伪性固化成 `_test/js_engine_mut.mjs` 入电池（156→157）；
> ④净 CPU 仪器（`resource_net()`）**否证了 r122 自己开的收紧处方**（空载只值 ≤9.1µs/请求，抖动在负载窗口内部）
> ⇒ 地板 12000µs 保留，改走"按线程记账"。

## 收尾推荐（带稳定 id 与可复算前提）

- [ ] 🔴 **[推荐:R123-01｜用户操作]** **切版 v1.8.3**（清 `G12`+`R1`）：不是文件锁问题，而是**不得覆盖他人正在服务的产物**
      （8123=pid 34412）；整跑须排在 `git tag` 之后。前提：`mvn -B -f server/pom.xml package` → 四源同步 →
      `git tag v1.8.3` → 复跑 `repo_config_check`＋`release_governance_check`＋`jar_shape_check`。
- [ ] 🟠 **[推荐:R123-02｜移交 r117/r118]** **他人面（未代改，均带命令）**：①语意工作树 FAIL（105 条/99%）＝未提交
      +20 条，HEAD 面 archive 复算 85/100% PASS；②G8 受理面红（85 vs 声称 105，源 `bb7ce5d`）；
      ③`_test/run_all_suites.py` 里他们有两条未入库套件（`quote_wiring*`）⇒ 我方本轮只提交自己那一格，
      ⇒ `G4` 工作树面仍红（159 vs 157）但 **HEAD 面自洽**（157＝README）；
      ④`loc_guard` `quote_eval.py` 175>150；⑤`EOL-PARITY 48 项`；⑥仓根 19 个 `_tmp_*` 研究抓料待其自清。
      复算：`python _test/{repo_config,loc_guard,eol_parity,core_capability_baseline_check}.py`。
- [ ] 🟠 **[推荐:R123-03｜agent 自动]** **性能维改走"按线程记账"**：本轮实测已**否证**"扣空载能收紧"
      （净读数只比毛读数低 ≤9.1µs/请求，而毛读数本身跨 2.25 倍）。正解＝用 `ThreadMXBean`/线程池统计只数
      处理请求的线程 CPU，或让每次 Rep 的窗口长到有意义的请求数再取中位数；在此之前 `MAX_US_CPU_PER_REQ=12000`
      不动，且**禁止**对外写"每请求 X ms CPU"。前提：`python _test/perf_baseline_check.py http://127.0.0.1:8147 --reps 40`
      连跑 5 轮，净读数的档内带宽先降到 <30% 才谈收紧阈值。
- [ ] 🟡 **[推荐:R123-04｜agent 自动]** **教程手册化（第一步已完成）**：`docs/QUICKSTART.md` 已建，下一步按
      lobehub 的形状分章（离线演示/危机转介/记忆三层开关/判据体系）。前提：`docs/README.md` 索引同步（G19 双向对账），
      且 `guide` 位只认**文件名** ⇒ 分章命名要带 `quickstart|tutorial|how-to`，否则写了也记不上（本轮 3/4 的成因）。
- [ ] 🟡 **[推荐:R123-05｜agent 自动]** **形状契约推广**：`shape_contract()` 目前只护住 peer-docs 一族，
      其余 17 族仍可能"自造键名 ⇒ 龄期尺整尺降档"。正解＝生产者侧各断自己那份（尺仍只在 `ledger_age_check` 一处），
      并让 `ledger_age_check` 对全族跑 `declared_na()`、任一 unknown 即点名。
- [ ] 🟡 **[推荐:R123-06｜agent 自动]** **漂移闸第三次值守**：`--round r124` 应印「漂移=比对 r123」；
      第 4/7 维 peers 格变窄或退 NA ⇒ 当场判红。同档：peers 台账 18 族现 ≤fuse(7d)，~10-15 起超龄 ⇒ 单族错峰单跑。
- [ ] 🟡 **[推荐:R123-07｜需外部资源]** 跨机性能可比（需目标机）、站外/跨仓文档面（另开一路 `homepage`+HEAD 请求，
      **不混进现有四类位**）、`peer-hygiene` degraded 重采。
