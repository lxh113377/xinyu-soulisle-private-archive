# 07 - 下一步 · 卷143（r121 对标三轮收尾推荐，2026-10-12）

> 报告 = `交付物/对标分析报告-2026-10-12-r121.md`；日志 = `memory/2026-10-12-r121.md`。
> 本轮四项：①八维台账装**跨轮漂移闸**（退化判红、改值只点名）②吞吐维打到词典引擎真实路径
> （emotion=2183.8 rps，spare 8147，未打他人 8123）③`/api/emotion` 模型分支进构建期 JUnit（3 例）
> ④新探针 `_test/peer_perf_probe.py` 把第 4 维 peers 格**从"从来没有分母"变成实测**
> （measured*=0/16、files-only=2、none=14、80 份 workflow 全读、失明 0）。
> 双核心能力零增量零回退：HEAD 面 85 条/100%；工作树 105 条属他人在途。

## 收尾推荐（带稳定 id 与可复算前提）

- [ ] 🔴 **[推荐:R121-01｜用户操作]** **切版 v1.8.3**（清 `G12`+`R1` 两条常驻红）：挂账理由按 r120 更正——
      不是文件锁，而是**不得覆盖他人正在服务的产物**（8123=pid 34412，`foreign`）。整跑须排在 `git tag` 之后
      （pom 已 bump/tag 未建时 G12+R2a/R2c 必红属构造中间态）。
      前提：`mvn -B -f server/pom.xml package` → 四源同步 → `git tag v1.8.3` →
      `python _test/repo_config_check.py && python _test/release_governance_check.py && python _test/jar_shape_check.py`。
- [ ] 🟠 **[推荐:R121-02｜移交 r117/r118 归属轮]** **他人面红**（已在 HEAD 面 archive 副本同尺复算＝既存，未代改）：
      ①G8「HEAD 85 条 vs 06 声称 105」（源 `bb7ce5d`；正解只有两种：+20 条落 main，或声称改回与 main 一致＋更正注）；
      ②`timing_coupling`：`quote_eval.py::wait(1500)` 未登记 ＋ `face_check.py::page.wait_for_timeout(400)` 锚点陈旧；
      ③`size_budget` 工作树 OVER `emotion-engine.js` 8924/5598、`emotion-lexicon.js` 6391/4042，HEAD 面 `wit-quotes.js` 未登记；
      ④`loc_guard` `quote_eval.py` 函数长 175>150。
      复算：`python _test/{repo_config,timing_coupling,size_budget,loc_guard}_check.py`。
- [ ] 🟠 **[推荐:R121-03｜移交归属轮]** **`quote_wiring_check.py` 接线**：工作树 rc=0／HEAD 面
      `QUOTE-WIRING-FAIL: 6 处` rc=1 ⇒ 本轮**不接线**（接了＝本机绿受理面红；G16 报孤儿是可归因的那一半）。
      前提：其改动入 main 后，`git archive HEAD` 副本内该判据 rc=0 ⇒ 再接进 SUITES（155→156）并同步 README 的 G4 行。
- [ ] 🟡 **[推荐:R121-04｜agent 自动]** **漂移闸首次真值守**：`--round r122` 应印「漂移=比对 r121」；
      第 4 维 peers 格若变窄/退成 NA ⇒ 当场判红（这是本轮装的牙，别绕过它改表）。
      同档：peers 台账 17 族 ≤fuse(7d)，~10-15 起超龄，**单族错峰单跑勿 burst**。
- [ ] 🟡 **[推荐:R121-05｜需外部资源]** **性能维由"自身棘轮"升为跨机可比**：探针已证 measured*=0/16
      ⇒ 池内无人把基准跑进 CI，横比无对象；取可比读数需一台目标机（老大侧缺口，非代码缺口）。
      要取 peers 正例必须跨出"聊天陪伴"品类。

## 本轮否证/更正三条（防下一轮抄回去）

- **「404＝那个仓没有 CI」由我写下又当场否证**：首跑 6 仓报 `workflows:gh: Not Found (HTTP 404)`，
  我判成"目录不存在"并写了折成 0 的补丁；3 分钟后同路径复核 `my-neuro`=3、`lobehub`=29 个 workflow
  ⇒ 列目录的 404 是**瞬时读不到**。现改：名册只认 git tree，读不到计入 `blind`，缺读数判 `unverified(...)`。
  **台账里的 `none` 会被下一轮抄成结论**，所以这类折叠的代价是对标结论本身。
- **面别标签也是契约**：套件数那格标「HEAD 面」而实现读工作树 `--list` ⇒ 数值没错、标签错，已如实改标＋同步文档。
- **「152 vs 155」两张嘴**：第 2 维抄 rollup、第 3 维现算 ⇒ 已按「同一事实只许一处判」让第 2 维不再重述。
