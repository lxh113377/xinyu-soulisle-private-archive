# 07 卷36 — r42 收口阻塞登记（savepoint 被他根噪声拒）
> 换卷理由（2026-09-27 实测）：卷35 现 3675 B ＋ 本节 438 B > R161 的 4,096 B 硬限 ⇒ 整节迁出本卷；
> 卷35 已按字节还原（写后回读 len(read_bytes)）。本卷首行字节为落盘后实测，非估算。

## r42 收口阻塞（同 r41 复现，禁代处置）

`handoff.py savepoint` 被噪声散射门禁拒：`handoff.py noise` 汇总实测
`global_skills violation=0 / global_memory violation=0 / 焚诀 violation=15`
⇒ 15 项全在**焚诀根**且是他人在途（`.trae/`、`bot-comparison.md`、`ci.html` 等根部意外项），
本仓 0 违规。**不搬他人文件、不改 allowlist 求绿**，等该根自行收口后复跑。
