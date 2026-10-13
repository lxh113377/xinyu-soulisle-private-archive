# 07-next-steps 分卷（r179 产物面线挂账）

> 取号：`volume_alloc.py` 独占建卷。日期 2026-10-14。全文与取证面见
> `交付物/对标分析报告-2026-10-14-r179-artifact-face.md`（本卷只留「下一轮不带记忆的人拿什么重跑」）。

## r179 已完成（四条，均有判据回执）
- **S1 R179-01** `/api/health/db` 补进 `docs/openapi.yaml`（15→16 paths）+ `docs/API.md` §1b；
  并把 `_test/api_contract_check.py` 的**探测成员资格**从手抄名单改成由 spec 的 `x-live-check` 决定
  （名单 `PROBE_ORDER` 只保留排序职责：先写后查再删）。反例桩五条（腿①新接口不丢／腿②序列由入参决定／
  腿③清理腿压最后／腿④已知项相对次序不变／腿⑤空入参不凭空造）。
  复算：`python _test/api_contract_check.py --selftest` ⇒ `SELFTEST-PASS`。
- **S2 R179-02** `memory/06-constraints.md` 评测集隔离表新增三行 provenance
  （`asr_eval_manifest.meta.json` = Common Voice 22.0 yue／CC0-1.0／seed 20261014／5130→4719→893→抽样 300；
  `asr_eval_baseline.json` = SenseVoice sidecar 现产汇总；`_eval_last.json` = 单次运行产物）。
  **写死一条口径**：`_eval_last.json` 禁止登记条数——它按 `.gitignore` 永不在 HEAD，
  登记条数会让 G8 的受理面腿去数一个该面根本不存在的件 ⇒ 不可满足的永红。
- **S3 R179-03** 余量位按**尺的语义**推广而非按格式套齐：
  `timing_coupling_check` 两面各印 `余量=基线-面值`（**允许负值**，折成 0 会让压线与越限同形）+ 四腿；
  `inline_style_check` 自印「欠账清单型，无余量位」的口径说明（硬套=造假）；
  `repo_config_check` G11 把红因（`判据实际 import 未登记进清单：['requests']`）补进门面行——
  原先只印计数，复现要手拼三个内部函数。
  **当场兑现**：补完第一次跑就照出 `提交面 余量=-2｜已越限`（C1=22 > 基线 20，该红此前一直在，只是不印）。
- **S4 R179-04** 两条孤儿判据入阻断链：`asr_sidecar_selftest` / `asr_eval_selftest` 进 SUITES（210→**212**），
  沿用 r130 `perf_api_check` 先例**只接 --selftest 腿**（主流程要真打 SenseVoice sidecar，服务不在回 rc=2）。
  连带暴露 G11 红 ⇒ `requests` 补进 `_test/requirements.txt`；
  连带打死一条夹具腿 ⇒ 篡改⑬c 原写死 `requests` 当幽灵依赖，它已成真依赖 ⇒
  改成由 import 面自证不在其中的候选名 + 前置断言（不满足就点名判失败，不许静默跳腿）。
  复算：`python _test/repo_config_check.py --selftest` ⇒ `91 条…（CI 实跑 212 套件 / 豁免 3）`。

