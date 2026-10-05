# -*- coding: utf-8 -*-
"""r94：把「首跑电池 + 三处修复」两行回执写进 r94 报告的 §0 取证表。"""
from pathlib import Path

P = Path("交付物/对标分析报告-2026-10-03-r94.md")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
NEW = (
    "| 收口电池（首跑） | `run_all_suites.py`（日志 `bench-r94-battery.log`） | **112/116 rc=1**：红在 `eol_parity`（工具写出 CRLF，工作树字节 != blob）、"
    "`offline_shell`（**我的回归**：搬块时漏 `return results` ⇒ 收尾 `for r in results` TypeError）、"
    "`a11y`（**我的回归**：`from playwright…import sync_playwright` 是 `main` 的局部名，随 with 块搬走后不可见 ⇒ NameError）；"
    "`loc_guard` 报 rc=2（argparse 不认新参数名 `--enforce` ⇒ usage 退出，门静默失声） |\n"
    "| 三处修复 | 见 §2.5 | ① `loc_guard` 保留 `--enforce` 为 no-op 兼容参数（默认已 enforce）"
    "② `offline_shell._run_checks` 补 `return results` ③ `a11y` 的 playwright import 提到模块级、main 保留 rc=2 环境门；"
    "另把 15 个 CRLF 文件按字节归一（`EOL-PARITY-PASS`） |\n"
    "| 收口电池（重跑） | `run_all_suites.py`（日志 `bench-r94-battery2.log`） | 见 §5 收口行 |\n")
out, hit = [], 0
for ln in lines:
    if ln.startswith("| 收口电池 |") and hit == 0:
        out.append(NEW)
        hit = 1
        continue
    out.append(ln)
P.write_text("".join(out), encoding="utf-8")
print("插入 %d 处" % hit)
