# 07 卷36 — r42 收口阻塞登记（savepoint 被他根噪声拒）
> 换卷理由（2026-09-27 实测）：卷35 现 3675 B ＋ 本节 438 B > R161 的 4,096 B 硬限 ⇒ 整节迁出本卷；
> 卷35 已按字节还原（写后回读 len(read_bytes)）。本卷首行字节为落盘后实测，非估算。

## r42 收口阻塞（同 r41 复现，禁代处置）

`handoff.py savepoint` 被噪声散射门禁拒：`handoff.py noise` 汇总实测
`global_skills violation=0 / global_memory violation=0 / 焚诀 violation=15`
⇒ 15 项全在**焚诀根**且是他人在途（`.trae/`、`bot-comparison.md`、`ci.html` 等根部意外项），
本仓 0 违规。**不搬他人文件、不改 allowlist 求绿**，等该根自行收口后复跑。

## r42 未闭环缺口（复发计数在案，须交机器载体）

1. **`b"中文"` 一族第 ≥3 次**（本轮 06:1x 内联 python 又犯，导致那段脚本零执行且误以为已提交）。
   机器化路径（下一步照此做，勿再写规则文字）：在 `_test/repo_config_check.py` 的 **G9 AST 遍历同一趟**里
   增加一条——`ast.Constant` 且 `isinstance(value, bytes)` 且含非 ASCII ⇒ 计入违规；
   不新增判据号（避免牵动「实跑 13 条」恒等式），并配一条注入式反例（临时脚本写 `b"卷"` 必须判红）。
2. **记忆卷 4KB 封顶**：本轮已把 `assert len <= 4096` 放到 `write_bytes` 之前（4,099B 那版当场拒写），
   但这是**脚本内自律**，跨会话不保证照抄。正解形态＝落盘走一个统一写入器（写前量、超限即自己换卷），
   而不是每轮手写 assert。登记为 P1。
3. **savepoint 阻塞**：见上节，等他根收口。
