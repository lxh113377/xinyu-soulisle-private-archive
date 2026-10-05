# -*- coding: utf-8 -*-
"""r94：在报告里补 §2.5（三处修复的归因）与 §5 收口/遗留条目。"""
from pathlib import Path

P = Path("交付物/对标分析报告-2026-10-03-r94.md")
src = P.read_text(encoding="utf-8")

SEC25 = """
### 2.5 首跑电池抓到的三处「我自己引入的回归」（本轮第二手发现）

首跑 112/116，红的三条里有**两条是我这轮拆分造成的**，一条是工作树字节问题：

| 套件 | 现象 | 根因 | 修法 |
|---|---|---|---|
| `offline_shell` | `TypeError: 'NoneType' object is not iterable` | 搬 `try` 体的脚本只做了「搬 + 调用」，**没生成 `return`** ⇒ `results = _run_checks(...)` 拿到 None | `_run_checks` 末尾补 `return results`（`results`/`check` 本就模块级，闭包无碍） |
| `a11y` | `NameError: name 'sync_playwright' is not defined` | `from playwright.sync_api import sync_playwright` 是 **`main` 的局部 import**，随 with 块搬进 `_run_audit()` 后不可见 | import 提到模块级；`main` 保留 rc=2 的环境门（缺依赖仍记未验） |
| `loc_guard` | rc=2 + argparse usage | 默认从 report-only 改成 enforce 后，`--enforce` 这个参数名消失了，而电池条目还在传它 ⇒ argparse 直接 usage 退出，**门静默失声** | 保留 `--enforce` 为 no-op 兼容参数（默认已是 enforce） |
| `eol_parity` | 15 项 | 编辑工具在 Windows 写出 CRLF，工作树字节 != blob 字节 | 按字节归一（`git status` 干净、`git checkout` 不重写，两个反直觉点同 r93） |

**教训两条**：
1. **搬块前要问「这个名字原来从哪来」**——函数内的 import、闭包变量、模块级常量，三者随块搬走的命运不同。
   本轮 `sync_playwright` 与 `return` 都属于「搬走后就没人认领」的那一类。
2. **改门禁的 CLI 契约要一起改调用方**。参数名一改，历史调用点立刻 usage 退出；
   若该门在电池里，这条会以 ENV-UNVERIFIED 出现——**看起来像环境问题，其实是接线断了**。
"""

SEC5_OLD = "- **收口全量电池**：见 §0 收口行（loc 门首次以 enforce 进电池，若有超限会直接红）。"
SEC5_NEW = ("- **收口全量电池（重跑）**：见 §0 收口行。首跑抓到的三处回归已修（§2.5），重跑为最终回执。\n"
            "- **loc 门抓到了我自己的回归**（本轮最讽刺也最有价值的一条）：给 `offline_shell` 补 `return results` 时，"
            "那 5 行注释把 `_run_checks` 顶到 155 行 ⇒ `loc_guard` 当场 `LOC-FAIL` rc=1。"
            "这是本门转 enforce 后**第一次对真实回归亮红**——此前它只会印读数。压缩注释后恢复 `LOC-PASS`。\n"
            "- **8 个 probe 的写盘段只验了 1 个**：`peer_repro_probe --self-only --json` 实跑落盘已验；"
            "其余 7 个只过了编译（代码同构，判低风险但**不等于已验**），下轮重采用到哪个验哪个。")

if "### 2.5" not in src:
    src = src.replace("\n## 3. 改进建议清单", SEC25 + "\n## 3. 改进建议清单", 1)
if SEC5_OLD in src:
    src = src.replace(SEC5_OLD, SEC5_NEW, 1)
P.write_text(src, encoding="utf-8")
print("§2.5:", "### 2.5" in P.read_text(encoding="utf-8"), "§5:", SEC5_NEW[:20] in P.read_text(encoding="utf-8"))
