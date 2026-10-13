# 07 分卷（r179 未闭环挂账·续）

## r179 未闭环（挂账，每条带可复算前提）
- 🔴 **R179-05 基座未换**：`server_preflight` rc=1（jar 内缺 `V1__j4_baseline_schema.sql`、`application.yml` 字节不等），
  8123 跑的是 10-13 08:57 产物 `1c6703d5e2d3` ⇒ **本轮所有 C4 运行态绿都测在旧代码上**。
  阻塞 = 持有者非本工具起（租约空 ⇒ 归类 `same-artifact`，`build_jar.py` 默认档拒绝停）；
  jar 被进程锁死实测 `mv` 报 `Device or resource busy`。
  前提（复算）：`Get-NetTCPConnection -LocalPort 8123 -State Listen` 查不到 pid ⇒ 跑 `python _test/build_jar.py --restart`；
  完成标准：`server_preflight` rc=0 **且** `api_contract_check`（不带 --base）rc=0。
  已做的替代验证：仓外副本树构建 `Tests run: 203 Failures: 0` + `BUILD SUCCESS`，起 8124
  ⇒ `api_contract_check --base http://127.0.0.1:8124` = `合计 20 项，失败 0 项｜探测 16 + 豁免 0 == 操作 16`。
- 🟠 **R179-06 他方评审账**：`timing_coupling` 桩 57/58，唯一不符 = `dock_auto_check.py::pg2.wait_for_timeout(500/600)` 两条无评审结论
  ⇒ 那是他人提交的代码，评审账＝替别人判断这个等待为什么必须存在，本轮只归因不代写。
- 🟡 **R179-08 行尾存量**：`eol_parity_check` rc=1（237 项）。本轮经手 12 个文件逐一复算 `CR 行数 == 总行数` ⇒ **全文统一 CRLF，未引入混排**；
  治法是先钉 `.gitattributes`（影响所有人 clone 的字节面，待点头），不是逐文件改行尾。
- 🟡 **R179-09 peers docs 失明 2 仓**：`peer_docs_probe` rc=1 报 `letta-code / MASCOT unverified(RuntimeError)`，
  该维分母 14/16 可用。补法：`python _test/peer_docs_probe.py --repo letta-ai/letta-code,hello-diana/MASCOT --json <当日台账>`（增量合并，不整面覆盖）。
- 🟡 **R179-10 远端回执**：本地领先 `origin/main` 235 提交、落后 0（r178 的 merge 已解分叉，推送不再需要 force）。
  推送会一并发布他人 235 条提交 ⇒ 属对外共享状态，待点头。完成后才有 perf 作业的 `闸态=unguarded` 回执。
- 整跑电池本轮**未重跑**（`--only` 子集读数按在册纪律不覆盖全量台账）；最近全量仍是 r172 的 172/199，
  而套件数已 172→212 ⇒ 下一轮该分段跑一次全量，并让各段收据并集 == 212。
