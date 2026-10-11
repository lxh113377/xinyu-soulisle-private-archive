# 07 - 下一步 · 卷142（r120 对标二轮收尾推荐，2026-10-12）

> 对标报告 = `交付物/对标分析报告-2026-10-12-r120.md`；会话日志 = `memory/2026-10-12-r120.md`。
> 本轮四项：①`repo_config` G8 改**两面各判一次并点名面**（量到"本机绿 / 受理面红"现行实例）
> ②CHANGELOG 按提交面补录 r118（清 `release_governance R2c`）③新增 `_test/js/memory-store.unit.test.mjs`
> 12 用例（JS 离线单测 50→62）④`CONTRIBUTING.md` 补「如何跑电池」节 + 修一处旧条数断言。
> 八维表首次由 `_test/bench_eight_dims_check.py --round r120` 供数（`维 8/8｜格 25｜NA 2`）。
> 双核心能力零增量零回退：HEAD 面 85 条/100%/危机 6-6、表情 26/26。

## 收尾推荐（带稳定 id 与可复算前提）

- [ ] 🔴 **[推荐:R120-01｜用户操作]** **切版 v1.8.3**（一次清掉 `repo_config G12` + `release_governance R1` 两条常驻红）：
      现状实测 tag=v1.8.2 而 pom=1.8.1、`git merge-base --is-ancestor v1.8.2 HEAD` = **no**（那枚 tag 在祖先面外）、
      距 v1.8.1 攒 22 个 feat（上限 5）、unreleased=174 提交 ⇒ **对外仍挂旧版本号**。
      **本轮仍没做的真实原因**（不是文件锁，实测该 jar 当前可 open-append 不报 PermissionError）：
      8123 由 pid 34412 持有（00:29:27 起，命令行即 `java -jar server/target/soulisle-server.jar`），
      按端口属主四档协议属 `foreign`；覆盖他人**正在服务的产物文件**会造成 JVM late class loading 失败，
      红会被算到并行会话头上 ⇒ 需老大点头"可以停/覆盖 8123 那台服务"才动。
      前提命令：`mvn -B -f server/pom.xml package` → 四源同步（`server/pom.xml`/`README.md`/`ROADMAP.md`/`CHANGELOG.md`）
      → `git tag v1.8.3` → `python _test/repo_config_check.py && python _test/release_governance_check.py && python _test/jar_shape_check.py`。
- [ ] 🟠 **[推荐:R120-02｜移交 r117/r118 归属轮]** **G8 的受理面红**：`emotion-eval-dataset.json` HEAD 实 85 条，
      而 06 声称 105 条（并行提交 `bb7ce5d` 把声称对齐到**工作树**实数，数据本体未进 main）。
      只有两种正解：把那 +20 条落进 main，或把声称改回与 main 一致并加更正注。
      本轮按 R263 **只把"看不见"变成"看得见"**（G8 现在两面各判一次、红因带面名），未动数据、未动声称、未降基线。
      复算：`python _test/repo_config_check.py` 看门面 `两面=` 字段。
- [ ] 🟡 **[推荐:R120-03｜agent 自动]** **peers 台账错峰重采**：16 族现龄 2–4 天、fuse=7 天 ⇒ ~10-15 起超龄。
      单族单跑勿 burst（r100/r105 实测撞限流）；断点续采只有 `peer_community_probe.py --repo o/r[,o/r] --json <既有台账>` 实现了，
      其余族只能整族重跑。判"降级"须比对 NA 相对上一份**认可**台账是否增长。
      同档另记：他人三处红本轮不代改（G16 孤儿 `quote_wiring_check.py`、`timing_coupling` 余 2 条、`loc_guard` 余 1 件 `quote_eval.py`）。

## 本轮否证/更正的两条（防下一轮抄回去）

- 「情绪评测 73 条」在 `CONTRIBUTING.md` 里活到本轮 —— 那是 2026-09-23 前的快照，HEAD 面现 85 条。
  已改为「条数以脚本自印为准，G8 两面盯着」，**不在文档里手抄第二份条数**。
- 「jar 文件被锁住所以不能重建 fat jar」这条在册说法本轮被**部分否证**：当前该文件可写。
  真实约束不是文件锁，而是**不得覆盖他人正在服务的产物**（会打断其 JVM 的 late class loading）。
  ⇒ 挂账理由要按这条改，否则下一轮会误判成"端口一空就能自动做"。
