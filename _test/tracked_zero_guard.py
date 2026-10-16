#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tracked 文件被清空/蒸发守卫（r170 S2）。

**为什么今天必须有它**：2026-10-13 单日内实测到 tracked 内容在工作树里消失**四类**——
① 08:36:55 `src/css/style.css` 与 `src/css/voice-call.css` 同时 **0 字节**（wt oid = git 空块 `e69de29`，
   而 idx==HEAD 完好）；② 一枚 24,771,225 B 的入库交付 zip 从磁盘消失（由 pre-commit 撞出）；
③ 复原之后**同日再次消失**（本件首跑实测）；④ 07 台账在册的 02:08「`_test/` 177 件被并行「并轨提交」清空」。
现有覆盖只有一处：`deliverable_inventory_check.py` 盯「已入库交付件从工作树消失」，且只扫交付根 ——
**「还在盘上但被写成 0 字节」这一态它看不见**（它按存在性判），而今天毁掉全站样式表的正是这一态。
本件不重复判交付件的消失（同一事实只许一处判），只管两件事：
  A 态 `ZEROED`  ：HEAD blob 有字节 ⇒ 工作树该路径 0 字节（blob 本就 0 字节的 12 个 `.err.log` 无义务，不算红）
  B 态 `VANISHED`：HEAD blob 有字节 ⇒ 工作树该路径**不存在**，且**不在交付根内**（交付根归 deliverable_inventory）

分母 = `git ls-tree -r -l HEAD`（blob 大小在这一列里，且这是被检对象**写不进去**的量）。
取数面与判定分离：`guard(blobs, exists, size)` 是纯函数，`--selftest` 全部在合成面上跑，不碰真仓。

退出码：0=TRACKED-ZERO-PASS 1=有 A/B 态 2=环境未验（取不到 HEAD 面，不得声称已验）
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
DELIVERABLE_ROOTS = ("交付物/", "archive/")     # 这两根的「消失」由 deliverable_inventory 独家判
MIN_BLOB_BYTES = 1          # blob 为 0 字节 = 合法空件（本仓实测 12 个 .err.log），不计入义务


def parse_ls_tree(stdout: str):
    """`git ls-tree -r -l HEAD` 正文 → {path: blob 字节}；`-` 表示 blob 不可得（大文件/LFS 占位）。"""
    out = {}
    for ln in stdout.splitlines():
        if "\t" not in ln:
            continue
        meta, path = ln.split("\t", 1)
        size = meta.split()[-1]
        out[path] = -1 if size == "-" else int(size)
    return out


def in_deliverable(path: str) -> bool:
    return path.startswith(DELIVERABLE_ROOTS)


def guard(blobs, exists, size):
    """纯判定。`exists(p)` / `size(p)` 由调用方注入 ⇒ 合成面与真面共用同一条尺。"""
    zeroed, vanished, unmeasurable = [], [], []
    for p, n in sorted(blobs.items()):
        if n == 0:
            continue                     # 本就空的件：无义务
        if n < 0:
            unmeasurable.append(p)       # 取不到字节 ⇒ 不得静默当"没被清空"
            continue
        if not exists(p):
            if not in_deliverable(p):
                vanished.append(p)
            continue
        try:
            if size(p) == 0:
                zeroed.append((p, n))
        except OSError:
            unmeasurable.append(p)
    return zeroed, vanished, unmeasurable


def run() -> int:
    try:
        # r187 修（一手：CI 全新 clone 上 476 个中文路径全部误判 VANISHED）：
        #   git 默认 core.quotepath=true 会把非 ASCII 路径输出成带引号的八进制转义
        #   （"\344\272\244..."），本判据拿这个假路径去工作树 os.path.exists ⇒ 永远 False
        #   ⇒ 中文路径文件全部误判「蒸发」。本地源仓库恰好配了 core.quotepath=false 所以
        #   一直是绿的——典型「本地配置掩盖判据缺陷」。修法 = 判据自己显式传 -c，
        #   不再依赖任何机器的本地配置（同族教训：r35 密钥扫描只有 CI 红、本地全绿）。
        r = subprocess.run(["git", "-c", "core.quotepath=false", "ls-tree", "-r", "-l", "HEAD"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    except Exception as exc:
        print("TRACKED-ZERO-UNVERIFIED: 取不到 HEAD 面（%s）⇒ 不得声称已验" % type(exc).__name__)
        return 2
    if r.returncode != 0:
        print("TRACKED-ZERO-UNVERIFIED: git ls-tree rc=%s ⇒ 分母取不到，不判绿也不判红" % r.returncode)
        return 2
    blobs = parse_ls_tree(r.stdout or "")
    if not blobs:
        print("TRACKED-ZERO-UNVERIFIED: HEAD 面解析到 0 条 ⇒ 分母为空，不得读成「没有文件被清空」")
        return 2
    zeroed, vanished, unmeasurable = guard(blobs, os.path.exists, os.path.getsize)
    for p, n in zeroed:
        print("  ZEROED   %s（HEAD blob %d B ⇒ 工作树 0 字节）" % (p, n))
    for p in vanished:
        print("  VANISHED %s（HEAD blob %s B ⇒ 工作树不存在，且不在交付根内）"
              % (p, blobs.get(p, -1)))
    for p in unmeasurable:
        print("  UNVERIFIED %s（blob 字节不可得或 stat 失败 ⇒ 单列，不并入「干净」）" % p)
    if zeroed or vanished:
        print("TRACKED-ZERO-FAIL: 清空 %d 条｜蒸发 %d 条｜未验 %d 条｜分母 %d 个 tracked 文件"
              % (len(zeroed), len(vanished), len(unmeasurable), len(blobs)))
        return 1
    print("TRACKED-ZERO-PASS: 分母 %d 个 tracked 文件（blob 有字节的 %d 个）无「工作树 0 字节」与非交付面「消失」"
          "｜未验 %d 条单列｜交付根的消失由 deliverable_inventory 独家判"
          % (len(blobs), sum(1 for v in blobs.values() if v > 0), len(unmeasurable)))
    return 0


def selftest() -> int:
    """四腿：正例抓到、合法空件不误伤、交付根不双判、零分母不判绿。全部跑合成面。"""
    bad = []
    fs = {"src/css/style.css": 40041, "docs/a.md": 300, "x.err.log": 0,
          "交付物/big.zip": 24771225, "memory/gone.md": 120}

    def mk(sizes, present):
        return (lambda p: p in present), (lambda p: sizes[p])

    # ① 正例：style.css 被清空 + memory/gone.md 蒸发 + 交付 zip 消失（后者不归本件判）
    ex, sz = mk({"src/css/style.css": 0, "docs/a.md": 300, "x.err.log": 0,
                 "memory/gone.md": 1, "交付物/big.zip": 5},
                ["src/css/style.css", "docs/a.md", "x.err.log"])
    z, v, u = guard(fs, ex, sz)
    if [p for p, _ in z] != ["src/css/style.css"]:
        bad.append("①「blob 有字节而工作树 0 字节」未被抓到：%s" % (z,))
    if v != ["memory/gone.md"]:
        bad.append("①非交付面蒸发未被抓到：%s" % (v,))
    if any(p.startswith("交付物/") for p in v):
        bad.append("①交付根的消失被本件重复判了（同一事实两处判 ⇒ 双源）：%s" % (v,))
    # ② 反向：全部合规 ⇒ 必须零红（防「把一切判红」的恒假尺）
    ok_ex, ok_sz = mk({p: max(n, 1) for p, n in fs.items() if n >= 0}, list(fs))
    z2, v2, u2 = guard(fs, ok_ex, ok_sz)
    if z2 or v2:
        bad.append("②合规面被判红（假阳性，会永久拦下所有人的提交）：%s %s" % (z2, v2))
    # ③ 未验态：blob 不可得必须单列，不得并入「干净」
    z3, v3, u3 = guard({"bin/model.bin": -1}, lambda p: True, lambda p: 99)
    if (z3, v3) != ([], []) or u3 != ["bin/model.bin"]:
        bad.append("③blob 字节不可得的件没被单列成未验：%s" % ((z3, v3, u3),))
    # ④ 零分母：空名册必须由调用方拦下（这里验 parse 层给出空 dict，run() 据此判 2）
    if parse_ls_tree("") != {}:
        bad.append("④空正文解析不出空名册 ⇒ 零输入被读成「有分母」")
    # ⑤ 合法 0 字节件：blob==0 不产生义务（本仓实测 12 个 .err.log，误伤就是永红闸）
    z5, v5, _ = guard({"a.err.log": 0}, lambda p: True, lambda p: 0)
    if z5 or v5:
        bad.append("⑤本就 0 字节的 tracked 件被判成清空：%s %s" % (z5, v5))
    print("TRACKED-ZERO-SELFTEST-%s（5 腿：抓到清空/蒸发 + 不误伤合规面 + 交付根不双判 + 未验单列 + 合法空件免义务）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad)))
    for x in bad:
        print("  ✗ " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
