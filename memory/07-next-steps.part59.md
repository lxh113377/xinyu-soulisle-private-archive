# 07-next-steps 卷59 — r58（质量工程面：JS 侧单元测试从零起账）

> 取号：`volume_alloc.py`（O_EXCL 独占）｜切版 v1.6.1 之后的第一轮，feats 计数从 0 重起

## 先做的事：切版（R1 逼的，不是我想发版）

- v1.6.0 之后 `feats=5/5 余量 0` ⇒ 下一个 `feat` 必被 R1 拦红 ⇒ **先手工切 v1.6.1**（`release_cut.py` 自 r45 仍挂账）。
- 切版三源同步：`pom.xml` 1.6.1 ＋ `ROADMAP.md`「当前版本：**v1.6.1**」＋ annotated tag（G12 盯这条，
  中途必红一次是正常态，不是错误）。
- `[Unreleased]` 正文**逐字节搬进** `## [1.6.1]`（断言原文在册＋bullet 数一致）；占位行刻意不做 bullet
  （否则 R2b 把"刚切版＝零 commit"判成文案先行）。
- 把滞后两个版本的发布物补上（Release 此前停在 v1.5.0，探针实测）：GitHub Release **v1.6.1** 带两个资产（`soulisle-server-1.6.1.jar` / `xinyu-web-1.6.1.zip`），
  远端 sha256 与本地逐字节相等才算交付（此前 Release 停在 **v1.5.0**，评委下载到的是旧行为）。
  jar 从 `git archive v1.6.1` 的干净导出构建 —— 本机 8123 有实例锁住 `server/target/`，直接构建在 `repackage` 处失败。

## 本轮量到的新面

- 起点实测：新探针 `--self-only` 量出 **JS 测试文件 0 个**，而 Java 侧 4 类 / 30 用例在 CI 真跑
  ⇒ README 指认的「判据清单全文」让"我们有单测"被默认成全仓事实，实际只对一半成立。

## 落地的东西

- `_test/js/emotion-engine.unit.test.mjs`：7 用例（夹具自证／否定翻转／程度加权／危机优先级＋强度钉 1／
  `intensity` 值域不变量／共现排序去重／无线索回落平静）。跑在 `node --test` + `node:vm`。
- **跨 realm 陷阱（本轮最值钱的一条）**：`node:vm` 里造的 `Array`/`Object` 原型属 vm realm，
  strict `deepEqual` 会对**逐元素 `Object.is` 全 true** 的两个数组报 "same structure but not reference-equal"。
  正解＝把返回值过一道 JSON 归一当数据比；**不是**放宽断言、不是换回 loose equal。
- `_test/js_unit_check.py`（常驻判据）：分母由 `_test/js/*.test.mjs` **文件枚举**得出；
  计数写进含判据词的那一行（电池每套件只留一行，`ℹ pass 7` 进不了 CI）。7 类桩＋恒绿守卫。
- **三态与覆盖面都用真跑取证**：注入必红用例 ⇒ rc=1 带明细；空目录 ⇒ rc=2 UNVERIFIED；真面 ⇒ rc=0 7/7。
  临时加第二个测试文件 ⇒ 判据行立刻变「8 用例／2 个文件」，删掉回落 7/1 ⇒ 枚举器不是摆设。
  变异体（抹空词表 `neg` 后重载引擎）⇒「我不开心」回判 `joy` ⇒ 否定那条断言真打在被审谓词上。
- 探针 `peer_quality_tooling_probe.py`：NOISE **有意不滤** `tests/` 目录（照抄 r54 那套会把被测对象自己滤掉，反例④钉住）；
  `unit_steps()` 逐行联合判断 —— `mvn package` 阶段（surefire 实跑处）算执行位、`package -DskipTests` 不算
  （self 首版被这条误判成"CI 无单测执行位"，是**探针自己的缺陷**，已修并补桩）。

## 台账

- 电池 88 → **91**（`js_unit` / `js_unit_selftest` / `quality_peer_selftest`）；README 的「91 套件」由 G4 钉住。
- 提交：`f27b994 feat(r58 质量工程面)`；`v1.6.1` 切版为 `4c0e623`（tag 同指）。
