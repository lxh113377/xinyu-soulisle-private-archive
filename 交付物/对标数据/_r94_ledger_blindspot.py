# -*- coding: utf-8 -*-
"""r94：记录本轮第三个判据盲区（eol_parity 不查未入库文件），并归一收口台账。
"""
from pathlib import Path

# ── 1. 盲区记录写进 part107 ──
P = Path("memory/07-next-steps.part107.md")
src = P.read_text(encoding="utf-8")
ANCHOR = "## ③ 下一轮入口（r95）"
ADD = """## ②-1 本轮第三个判据盲区（一手，`eol_parity` 只查 HEAD 面）

- **现象**：本轮入库的一批 `_r94_*.py` 在**工作树里是 CRLF**，而提交时 git 归一为 LF 存入 blob
  ⇒ 提交后 `eol_parity` 判红「工作树字节 != blob 字节」。但**提交前跑它是绿的**。
- **根因**：`eol_parity` 的扫描面是 `git ls-tree HEAD`（git HEAD 面）⇒ **未入库的新文件在入库前完全不被检查**。
  同一分钟内我写文件 → 归一 → 提交，顺序上没问题；但**提交后**工作树与 blob 的字节关系变了，门才变红。
- **含义**：这道门有个时间窗——「刚写完、还没入库」的窗口是盲区。**入库后必须再跑一次归一**，
  否则 CI/下一次本地跑就会红，而红因看起来像「我明明归一过了」。
- **处置**：本轮已归一（归一后与 HEAD 零差异，证实**入库 blob 一直是 LF，正确的**），
  并把「写文档/脚本 → 归一 → 提交 → **再归一一次**」固化为流程。
  下轮可考虑给 `eol_parity` 加一条 `--worktree` 面（含未入库文件），或至少在门面行印出
  「本门只查 HEAD 面，未入库文件不在内」。

"""
if ANCHOR in src and "本轮第三个判据盲区" not in src:
    src = src.replace(ANCHOR, ADD + ANCHOR, 1)
    P.write_text(src, encoding="utf-8")
    print("part107 已补盲区段")
else:
    print("part107 盲区段已存在或锚点未命中")
