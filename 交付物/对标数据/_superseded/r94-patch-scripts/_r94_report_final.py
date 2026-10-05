# -*- coding: utf-8 -*-
"""r94：回填报告的最终收口回执（第 5 轮 116/116 ALL-GREEN）+ §5 收口条目。"""
from pathlib import Path

P = Path("交付物/对标分析报告-2026-10-03-r94.md")
src = P.read_text(encoding="utf-8")

OLD = "| 收口电池（重跑） | `run_all_suites.py`（日志 `bench-r94-battery2.log`） | 见 §5 收口行 |"
NEW = ("| 收口电池（第 2–4 轮） | `bench-r94-battery2/3/4.log` | 115/116 → 115/116 → 114/116，红项各不相同（`voice` / `backup_online` / `eol_parity`+`j2`）⇒ 逐条归因见 §2.6 |\n"
       "| **收口电池（最终回执）** | `run_all_suites.py`（日志 `bench-r94-battery5.log`） | ✅ **`BATTERY: 116/116 rc=0 ALL-GREEN`**（合计 919s；台账指纹 `sha256=f874b118…`）——loc 门首次以 enforce 身份在电池里全绿 |")
if OLD in src:
    src = src.replace(OLD, NEW, 1)

OLD5 = "- **收口全量电池（重跑）**：见 §0 收口行。首跑抓到的三处回归已修（§2.5），重跑为最终回执。"
NEW5 = ("- **收口全量电池**：第 5 轮 **`116/116 rc=0 ALL-GREEN`**（`bench-r94-battery5.log`，合计 919s）。"
        "第 1 轮抓到的三处回归已修（§2.5）；第 2–4 轮各自暴露一条 flaky，归因见 §2.6。")
if OLD5 in src:
    src = src.replace(OLD5, NEW5, 1)

P.write_text(src, encoding="utf-8")
print("回填完成：final row=%s, sec5=%s" % ("battery5" in P.read_text(encoding="utf-8"),
                                          "116/116 rc=0 ALL-GREEN" in P.read_text(encoding="utf-8")))
