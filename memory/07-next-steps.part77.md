# 07-next-steps 卷77 — r75（2026-09-28）

> 取号由 `volume_alloc.py` 独占（dry-run n=77）；卷76 是 r74 的账（`feats=9/5` 时期），本轮另起一卷避免同卷混写。
> 本节所有数字为当轮实测，`前提=` 均可复算；**未闭合四态不折叠**（有／无／未验／待授权分开写）。

## 本轮已落地（不再挂账，只留复算入口）

- **Java 覆盖率门**：`mvn -B -ntp -f server/pom.xml test jacoco:check@jacoco-check-line-coverage`
  ⇒ `BUILD SUCCESS`（阈值 0.35，实测 LINE **268/669 = 40.06%**，余量 5.06 个点）。
  反例（打在**副本** `server/pom_r75_mutation.xml`，真 pom sha `aa1d4886…` 前后未变）阈值改 0.45
  ⇒ `Rule violated for bundle soulisle-server: lines covered ratio is 0.40, but expected minimum is 0.45` rc=1。
- **门禁在链上**：`.github/workflows/ci.yml` java job `package` → **`verify`**（`check` 绑 verify 相位，
  跑 package 时这行 pom 永不执行）；守卫 `java_test_guard` 加 **T6/T7**，`--selftest` **10/10 → 18/18**，
  收口行带值：`… 覆盖率门 在位｜LINE 阈值 0.35｜链上 是`。
- **质量门同址尺**（`--quality-gates`，peers 与 self 同一套 `qg_classify`）现采 10:14 UTC 16/16：
  `coverage_gate 0/16`｜`mutation_gate 0/16`｜`lint_gate 1/16`（SillyTavern；**另有 1 家未验**）｜
  `typecheck_gate 0/16`（1 家未验）｜`secret_scan_gate 1/16`（opensoul）；
  self＝coverage ✅有／其余 ❌无，但 **8 道自写门**（体积·vendor·评测·策略表·密钥·fat-jar·双端一致·compileall）
  由 `ci_steps_homegrown` 列出且**不参与两侧对照**（文件名尺结构性看不见自写门＝已写进判据天花板行）。
  首跑两处自造错都修成永久反例：中文步骤名假阴、jacoco 的 `coverage` 字样被判成"变异门"。

## 仍挂账

- [ ] 🔴 **R70-01 / R74-01 他方在途第 6 轮**：`jar_shape` 两条 SUITES 名额＋README 计数＋`docs/quality-gates.md`
      两格证据行。`前提=git cat-file -e HEAD:_test/suite_resource_census.py` ⇒ 仍 **NOT in HEAD**；
      `README.md`/`run_all_suites.py`/`docs/quality-gates.md` 仍 ` M` ⇒ 继续避让（不覆盖、不代提交）。
- [ ] 🔴 **R75-01 发布裁决**（接续 R70-03/R71-02）：`前提=python _test/release_governance_check.py`
      ⇒ `RELEASE-GOV-FAIL: 1 项（v1.6.1｜feats=10/5 unreleased=97）` rc=1；r73/r74 的"本轮 feat 后到 10/5"命中
      ⇒ **锁每轮自紧一格**。动作只有两个：授权切版+发布（同时消 `live_sync`/`ci_status`），或授权把 R1 降 advisory。
- [ ] 🟠 **R75-02 覆盖率补四类 0% 缺口**（本轮 jacoco 现算）：`EmotionController` 0/117、`MemoryController` 0/63、
      `ChatController` 0/50、`MemoryService` 0/47 ＝ 未覆盖 401 行里的 **277 行（69%）**。
      验收＝`mvn -f server/pom.xml test` 后 `jacoco.xml` LINE ≥ **0.60**，**届时**才改 `<minimum>`；
      红线：**禁止先抬阈值再补测试**。
- [ ] 🟠 **R74-02 07 摘要层**：分母已量（**76 卷 / 217,965 B**；壳内 4 条未勾、末 6 卷 11 条）。
      形态限制：只能由**生成器**产出＋配"与末卷等值"判据；手写摘要＝又一处会腐烂的抄件（G17 同族）。
