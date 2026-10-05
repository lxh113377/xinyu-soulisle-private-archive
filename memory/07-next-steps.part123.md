# 07-next-steps.part123.md · r97 追加：`flow --sync` 写记忆卷不封顶（本轮一手，写入端未修）

- ⬜ 🔴 **共享工具缺陷（本轮一手，A-project-handoff）**：`handoff.py flow . --sync` 把 P1/P2 镜像写回 `07-next-steps.part5.md` 时**不查 R199.2 单卷 4KB 硬限** ⇒ 该卷从 ~2.7KB 被顶到 4,609B，`savepoint` 随即判 `single_block` 拒绝自动拆并整体退出（rc=1）。本轮按提示人工拆卷（新卷 `part122`，逐字节对账原文未改）解了闸，但**写入端没修**：下一次 `--sync` 还会往同一卷长。正解方向（下轮在 global_skills 侧做，先取证再动）：sync 写入前按卷档位算预算、超限时自动续卷或改道 `_partial/`。
  复算命令 = `python D:/global_skills/A-project-handoff/scripts/handoff.py flow . --sync` 之后 `wc -c memory/07-next-steps.part5.md`

补记：本轮自己也犯过同款（给 `part121` 追加这条时把它顶到 4,549B ⇒ 只能再拆一卷）—— 证明这不是偶发，而是**没有写入端封顶**的必然。正解方向：sync 写入前按卷档位算预算，超限自动续卷或改道 `_partial/`；调用方侧的临时规矩＝**脚本改写记忆卷后当场 `wc -c` 复核**（已反哺全局记忆 [[feedback-shared-memory-write-discipline]] 追加形态）。

- [x] WF-r95-契约入库 `.ci/contract.json` 未入库 ⇒ greencheck 恒 UNKNOWN ⇒ pre-push 钩子恒放行（r90 登记 5 轮未动）（由 flow 登记；状态: done）
