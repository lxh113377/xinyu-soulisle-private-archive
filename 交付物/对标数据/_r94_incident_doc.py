# -*- coding: utf-8 -*-
"""r94 事故与修复落盘：报告 §2.7 + part107 台账 + CHANGELOG。

事故：`_r94_eol.py` 第二版用 `git check-attr` 判二进制，但 `subprocess.run(text=True)`
按 locale 解码 git 的 UTF-8 输出 ⇒ 中文路径乱码 ⇒ 二进制判定全失效
⇒ **15 个 PNG/ZIP/PDF/MP4 被当文本 CRLF→LF 改写**。已全部从 git 恢复（`git status` 复检 0）。
"""
from pathlib import Path

# ── 报告 §2.7 ──
P = Path("交付物/对标分析报告-2026-10-03-r94.md")
src = P.read_text(encoding="utf-8")
SEC = """
### 2.7 本轮最严重的一次事故：我自己把 15 个交付物二进制改坏了（已全部恢复）

**经过**（时间线，不修饰）：
1. 为修 `eol_parity` 的 HEAD 面盲区，我写了归一脚本 `_r94_eol.py`（把工作树 CRLF 转 LF）。
2. 第一版逐文件调 `git check-attr` ⇒ 550 次子进程 ⇒ 慢到被使用者打断（**辅助脚本自己变慢也是缺陷**）。
3. 第二版改为批量（80 一批），但**没显式指定编码**：`subprocess.run(text=True)` 按系统 locale
   解码，而 git 输出 UTF-8 ⇒ **中文路径解码成乱码** ⇒ 匹配不上 ⇒ **二进制判定全部失效**。
4. 脚本把 `交付物/iCAN评审/截图/*.png`、`心屿SoulIsle-作品提交-20260930.zip`、
   留档 PDF/MP4 等**当文本做了 CRLF→LF 改写** ⇒ **二进制交付物损坏**（PNG 头里的 `0D0A` 被改掉）。

**发现与恢复**：`git status` 里 15 个二进制呈 `M` ⇒ 逐个 `git checkout --` 恢复 ⇒
复检 0 个二进制仍是 `M`（与 HEAD 逐字节一致）。恢复脚本留在
`交付物/对标数据/_r94_restore_binaries.py`（含完整复盘）。

**根因与两条硬规矩**（比修 bug 本身更值钱）：
1. **凡「按路径匹配子进程输出」的代码，必须显式 `encoding="utf-8"`**。
   这是本仓同族坑的第三条：`gh` 走绝对路径（PATH 里有 0 字节占位文件）、
   `date -u` 跨平台不存在、本次 locale 解码乱码 —— 三条都是「子进程这条链上没被控住的假设」。
2. **破坏性批量操作必须先 dry-run**。当时脚本是「直接改」，没有清单、没有确认，
   一次手滑就改了 15 个交付物。现已改为：**默认 dry-run + `--apply` 才改盘**，
   且加两道闸（只碰文本类扩展名 / 前 8KB 含 NUL 一律跳过）—— 属性表会漏，字节不会。

**顺带的产品改进**：`eol_parity` 本身扩为**双面**（已跟踪 523 文本 / 未入库 5），
门面行分别印两个分母；`--selftest` 补 4 条未入库面腿（CRLF 必红 / LF 不红 / binary 不红 / 零输入分母为 0）。
"""
if "### 2.7" not in src:
    src = src.replace("\n## 3. 改进建议清单", SEC + "\n## 3. 改进建议清单", 1)
    P.write_text(src, encoding="utf-8")
    print("报告 §2.7 已插入")

# ── part107 ──
Q = Path("memory/07-next-steps.part107.md")
qs = Q.read_text(encoding="utf-8")
ANCH = "## ③ 下一轮入口（r95）"
ADD = """## ②-2 事故留档：15 个交付物二进制被我改坏（已全部恢复）

`_r94_eol.py` 第二版用 `git check-attr` 判二进制，`subprocess.run(text=True)` 按 locale 解码
git 的 UTF-8 输出 ⇒ 中文路径乱码 ⇒ 二进制判定失效 ⇒ 15 个 PNG/ZIP/PDF/MP4 被当文本 CRLF→LF
改写。`git status` 见 15 个二进制呈 `M` ⇒ 逐个 `git checkout --` 恢复 ⇒ 复检 0。

两条硬规矩（已落进脚本与流程）：
1. **凡「按路径匹配子进程输出」的代码必须显式 `encoding="utf-8"`**（本仓同族坑第三条：
   `gh` 0 字节占位文件 / `date -u` 跨平台 / 本次 locale 乱码）。
2. **破坏性批量操作先 dry-run**：`_r94_eol.py` 现默认 dry-run，`--apply` 才改盘；
   两道闸：只碰文本类扩展名 + 前 8KB 含 NUL 一律跳过。**属性表会漏，字节不会。**

产品面：`eol_parity` 扩为双面（已跟踪/未入库两个分母都印在门面行）+ 自检补 4 条未入库腿。

"""
if ANCH in qs and "事故留档：15 个交付物二进制" not in qs:
    qs = qs.replace(ANCH, ADD + ANCH, 1)
    Q.write_text(qs, encoding="utf-8")
    print("part107 已补事故段")

# ── CHANGELOG ──
C = Path("CHANGELOG.md")
cs = C.read_text(encoding="utf-8")
OLD = "- **loc 门第一次对真实回归亮红（门有牙的实证）**"
NEW = (
    "- **`eol_parity` 扩为双面（Fixed）**：扫描面此前是 `git ls-files`，**不含未跟踪文件** ⇒\n"
    "  「刚写完、还没入库」的脚本在本门下完全不可见 ⇒ 表现为**提交前绿、提交后红**。\n"
    "  现增一路「未入库」面（只查工作树含 CRLF，因未入库文件没有 blob 可比），门面行分别印\n"
    "  两个分母；`--selftest` 补 4 条未入库腿（CRLF 必红 / LF 不红 / binary 不红 / 零输入分母为 0）。\n"
    + OLD
)
if OLD in cs and "扩为双面" not in cs:
    cs = cs.replace(OLD, NEW, 1)
    # 事故单独成条
    ANCH2 = "- **`eol_parity` 扩为双面（Fixed）**"
    INC = (
        "- **事故留档：15 个交付物二进制被我改坏（已全部恢复）**：归一脚本用 `git check-attr` 判二进制，\n"
        "  `subprocess.run(text=True)` 按 locale 解码 git 的 UTF-8 输出 ⇒ 中文路径乱码 ⇒ 二进制判定失效\n"
        "  ⇒ 15 个 PNG/ZIP/PDF/MP4 被当文本 CRLF→LF 改写。已逐个 `git checkout --` 恢复，复检 0。\n"
        "  两条硬规矩：①凡「按路径匹配子进程输出」必须显式 `encoding=\"utf-8\"``（本仓同族坑第三条；\n"
        "  另两条是 `gh` 的 0 字节占位文件、`date -u` 跨平台不存在）②破坏性批量操作先 dry-run\n"
        "  （`_r94_eol.py` 现默认 dry-run + `--apply` 才改盘，且只碰文本类扩展名 + 内容含 NUL 一律跳过）。\n"
    )
    cs = cs.replace(ANCH2, INC + ANCH2, 1)
    C.write_text(cs, encoding="utf-8")
    print("CHANGELOG 已补（含事故条）")
