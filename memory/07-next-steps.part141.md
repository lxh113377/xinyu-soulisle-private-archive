# 07 - 下一步 · 卷141（r119 对标轮收尾推荐，2026-10-12）

> 对标报告 = `交付物/对标分析报告-2026-10-12-r119.md`；会话日志 = `memory/2026-10-12-r119.md`。
> 本轮四项改造：①出口件离线单元判据（`_test/js/pages-function-chat.unit.test.mjs` 17 用例，js_unit 33→50）
> ②八维总览表派生化（`_test/bench_eight_dims_check.py`，套件 152→154）③时刻耦合台账自洽（C1_HARD 21→20）
> ④取数归口去重（self 侧唯一算家 = `bench_rollup`）。双核心能力本轮**零增量零回退**：HEAD 面 85 条/100%/6-6、表情 26/26。

## 收尾推荐（带稳定 id 与可复算前提）

- [ ] 🔴 **[推荐:R119-01｜用户操作]** **切版 v1.8.3 三源同步**（一次清掉 `repo_config G12` + `release_governance R1` 两条常驻红）：
      现状实测 tag=v1.8.2 而 pom=1.8.1，且 `git merge-base --is-ancestor v1.8.2 HEAD` = **no**（那枚 tag 在祖先面外）；
      距 v1.8.1 已攒 20 个 feat（上限 5）、unreleased=163 提交 ⇒ **对外仍挂旧版本号**。
      **本轮没做的原因（不是偷懒）**：切版必须重建 fat jar，而 8123 由并行会话持有
      （pid 34412 = `java -jar server/target/soulisle-server.jar`），Windows 下该文件被进程锁住，
      `mvn package` 的 repackage 步骤必失败（r112 一手 `Unable to rename … .original`）；
      且 `jar_shape` 断言 pom⇄jar 版本一致 ⇒ 只 bump pom 会立刻多一条红。
      前提命令（端口释放后照抄）：`mvn -B -f server/pom.xml package` → 改 `server/pom.xml`+`README.md`+`ROADMAP.md`+`CHANGELOG.md`
      → `git tag v1.8.3` → `python _test/repo_config_check.py && python _test/release_governance_check.py && python _test/jar_shape_check.py`。
- [ ] 🟠 **[推荐:R119-02｜agent 自动]** **peers 台账错峰重采**：16 族现全在 fuse(7d) 内（龄 2–4 天），
      ~10-15 起超龄；单族单跑勿 burst（r100/r105 实测撞限流），断点续采只有 `peer_community_probe.py --repo o/r[,o/r] --json <既有台账>` 实现了，
      其余族只能整族重跑。判「降级」须比对 NA 相对上一份认可台账是否**增长**。
- [ ] 🟡 **[推荐:R119-03｜移交归属轮]** 三条红落在并行会话的件上，本轮按纪律**不代改他人台账**：
      `timing_coupling` 的 `quote_eval.py::pg.wait_for_timeout(1500)` 未登记 + `face_check.py::page.wait_for_timeout(400)`
      锚点陈旧（由并行提交 `a25042a` 的函数拆分造成，`git log -1 -- _test/face_check.py` 归属实测）；
      `loc_guard` 余 1 条 = `quote_eval.py` 最长函数 175 > 150。
      另 `CONTRIBUTING.md` 仍缺「如何跑电池」一节（r112 起列 L3，两轮未做）；
      `memory/10-core-capabilities.md` 现 **4816B 已越 4096 硬限** ⇒ r119 轨迹行没往里堆，先拆卷再补行。

## 本轮否证的两条「常见说法」（写下来防下一轮又抄回去）

- 「API 文档缺失」**不成立**：`docs/openapi.yaml` 11 条 path ⇄ Java 11 个映射端点逐一对上（本轮 HEAD 面实测）。
- 「SSE 直通 = 同一个 body 对象引用」**不成立**：`new Response(body)` 会把 bodyInit 包装成**新的** ReadableStream，
  可观测事实是「仍是流 + 分块逐字抵达」（该断言由自己的用例证伪后改判）。
