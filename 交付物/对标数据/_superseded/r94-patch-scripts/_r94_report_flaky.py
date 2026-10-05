# -*- coding: utf-8 -*-
"""r94：把本轮 4 轮电池的 flaky 归因汇总写进报告（新增 §2.6）。"""
from pathlib import Path

P = Path("交付物/对标分析报告-2026-10-03-r94.md")
src = P.read_text(encoding="utf-8")

SEC = """
### 2.6 四轮电池跑出来的 flaky 清单（本轮副产品，价值不低于正产物）

r94 为收口跑了 4 轮全量电池（每轮约 20 分钟），每轮都恰好红 1–2 条，**但红的不是同一条**。
把四轮摊开看，结论是：**116 条里有 3 条是「环境时序敏感」，它们各自需要单独归因，不能一律当偶发放过**。

| 轮次 | 红项 | 失败形态 | 单独复跑 | 归因 | 本轮处置 |
|---|---|---|---|---|---|
| 第 1 轮 | `eol_parity` / `offline_shell` / `a11y`（+`loc_guard` rc=2） | CRLF 字节、`TypeError`、`NameError`、argparse usage | — | **我本轮引入的回归**（§2.5） | 全部修复 |
| 第 2 轮 | `voice` | A5「8s 内 `class=recording` 未移除」 | 2 次 `VOICE-PASS` | 时序轮询预算（80×100ms）在电池负载下踩不满 | **不放宽预算**，登记待观察 |
| 第 3 轮 | `backup_online` | `Page.evaluate: Execution context was destroyed` | 2 次 `BACKUP-ONLINE-PASS` | 页面在 evaluate 期间导航（腾讯验证页 / SW 重载） | 加**有界重试一次**（真缺陷第二次仍红） |
| 第 4 轮 | `eol_parity` / `j2_chat_contract` | CRLF 字节；`FAIL-A` 未命中在线大模型 | 2 次 `J2-CONTRACT-PASS` | 前者是我写文档后没归一（流程漏洞）；后者是上游 LLM 在负载下超时 | 归一 + 登记 |

**三条可复用的结论**：
1. **flaky 必须逐条归因，不能整体重跑蒙过去**。四轮红的四条各不相同，若只看最后一轮「绿了」，
   就丢掉了「`voice` 的 8s 预算在负载下不够」这条真实结论。
2. **「重跑就绿」不是证据，「单独复跑绿 + 失败形态是竞态/超时」才是**。本报告给每条都留了失败原文。
3. **CRLF 归一必须成为写文档后的固定动作**。本轮两次因它判红，机制是：编辑工具写 CRLF、
   `.gitattributes` 钉 `eol=lf` ⇒ 工作树字节 != blob 字节。已把归一脚本留在
   `交付物/对标数据/_r94_eol.py`（幂等、只动 CRLF 文件）。
"""

if "### 2.6" not in src:
    src = src.replace("\n## 3. 改进建议清单", SEC + "\n## 3. 改进建议清单", 1)
    P.write_text(src, encoding="utf-8")
    print("§2.6 已插入")
else:
    print("§2.6 已存在")
