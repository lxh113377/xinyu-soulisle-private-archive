# -*- coding: utf-8 -*-
"""r94 收口：把最终回执（BATTERY 116/116、提交 SHA、CI run 号）写进 part107 与 09 任务表。"""
from pathlib import Path

P = Path("memory/07-next-steps.part107.md")
src = P.read_text(encoding="utf-8")
OLD = "- 收口全量电池：见 r94 报告 §0 收口行"
NEW = (
    "- **收口全量电池：第 5 轮 `116/116 rc=0 ALL-GREEN`**（`交付物/对标数据/bench-r94-battery5.log`，合计 919s，"
    "台账指纹 `sha256=f874b118…`）。前 4 轮各红 1–2 条且**各不相同**，逐条归因见报告 §2.6。\n"
    "- 门禁面复核（收口时现跑）：`LOC-PASS`（enforce 身份）｜`EOL-PARITY-PASS`（text 461 / binary 28）｜"
    "`REPO-CONFIG-PASS` 17 项 18 判据号｜`DELIVERABLE-INVENTORY-PASS`｜`DISCLAIMER-CLEAN` 48 份"
    "（交付物 2 + _历史轮次-对标 46）0 缺口｜`BRAND-PASS`。\n"
    "- **提交 `1de2a9a`**（已推 `origin/main`，本地 == 远端）；CI run 在后台，收口后补回执。\n"
    "- 唯一未纳入提交的三项（按铁律排除）：`memory/AGENTS.md`（并行会话在途）、`.ci/`（r90 遗留，"
    "未做 `--sweep` 复扫到 `matched==declared`，不在未验状态替他入库）、`memory/07-next-steps.part105.md`。"
)
if OLD in src:
    P.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("part107 收口已写")
else:
    print("part107 锚点未命中")

W = Path("memory/09-workflow-state.md")
ws = W.read_text(encoding="utf-8")
OLDW = "| WF-r93-loc超限治理 | P2 | loc 门 22/156 文件超限（最大 benchmark_metrics.py 1913 行/最长函数 628 行）⇒ 清零后切 --enforce 并加 CI 接线判据 | done | WF-r93-对标轮 | - | 2026-10-03 01:40 | r94：先修尺（22→8，14 项为类/IIFE 误判）→ 拆 10 个真超限函数 → **超限 0（LOC-PASS）** → 切 enforce + 接线自证 wiring_report()；selftest 9→17 条 |"
NEWW = OLDW + "\n| WF-r94-收口 | P1 | r94 收口：五轮电池取最终绿 + 门禁面复核 + 提交推送 + CI 回执 | doing | - | - | 2026-10-03 02:40 | BATTERY 第5轮 116/116 ALL-GREEN（919s）｜LOC/eol/repo_config/inventory/disclaimer/brand 六门全绿｜提交 1de2a9a 已推 |"
if OLDW in ws and "WF-r94-收口" not in ws:
    W.write_text(ws.replace(OLDW, NEWW, 1), encoding="utf-8")
    print("09 收口行已写")
else:
    print("09 锚点未命中或已存在")
