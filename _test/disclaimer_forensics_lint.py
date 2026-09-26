#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""边界声明取证判据（M5⑫ 的执行器）：免责声明不得顶替一整维的测量。

要拦的形态：报告里写「不可比 / 无可比口径 / 受限于 X / 仅保证 Y / 无法做到」这类**边界结论**，
却拿不出这条结论是怎么来的（比对口径、样本数、取证命令、差异定位）。
这类句子会把"我没测"包装成"这事做不了"，代价是整维长期停在原地（一手实证见 SKILL.md 1.16.0 条）。

**不拦**的形态（写清楚就别误伤，误报一次就有人把判据关掉）：
  · 诚实标注的缺口：`未实测` / `❌` / `待办` —— 那是"知道没测"，不是"宣称做不了"；
  · 带取证的边界结论：同句内出现 命令 / 口径 / 计数 / 单位 / run 号 / sha / CRC 等任一实证标记。

用法：
    python disclaimer_forensics_lint.py --file <报告.md>      # 0=干净 1=点名到行 2=输入不可用
    python disclaimer_forensics_lint.py --selftest            # 8 类桩：漏报侧 + 误报侧 + 边界
输入为空 / 读不到文件 → 判 `UNVERIFIED` 并退 2（禁止把"没读到"印成通过，R247）。
"""
import argparse
import re
import sys
from pathlib import Path

# 边界结论词（主张"这维做不到/只能这样"）
BOUNDARY = re.compile(r"(不可比|无可比口径|没有可比|无法比较|不能比较|受限于|仅保证|无法做到|做不到|只能保证|物理限制)")
# 实证标记（这条结论是怎么来的）
# 实证标记（这条结论是怎么来的）。⚠ 不放裸「口径」二字：`无可比口径` 自身就是被拦的话术，
# 放进白名单会让句子自己把自己洗白（r40c 首跑即由 selftest 抓到：漏报侧桩 0 命中）。
FORENSIC = re.compile(r"(实测|取证|命令|脚本|_test/|\.py|run[: ]?\d{6,}|workflow|逐条|逐文件|分母|样本|样例|"
                      r"\d+\s*(仓|条|个|文件|次|行)|\d+(\.\d+)?\s*(%|ms|MB|KB|B\b|rps|fps)|sha256|sha1|CRC|ls-remote|gh )")
# 诚实缺口（不是本判据的对象）
DECLARED_GAP = re.compile(r"(未实测|待实测|❌|未取|待补|待办)")


def lint_lines(lines):
    """返回 [(行号, 命中词, 该行文本)]。零输入不在此判，交调用方处理（防把空当绿）。"""
    hits = []
    for i, ln in enumerate(lines, 1):
        m = BOUNDARY.search(ln)
        if not m:
            continue
        if FORENSIC.search(ln):
            continue                    # 带取证 ⇒ 合法边界结论
        if DECLARED_GAP.search(ln) and not re.search(r"(受限于|仅保证|无法做到|做不到|只能保证|物理限制)", ln):
            continue                    # 只标注缺口，不主张"做不了" ⇒ 另一个判据管
        hits.append((i, m.group(1), ln.strip()[:120]))
    return hits


def scan_file(path):
    return lint_lines(path.read_text("utf-8", errors="replace").splitlines())


STUBS = [
    # (名称, 行列表, 期望命中数)
    ("漏报侧 裸边界结论", ["### 3.3 性能表现", "- 各参照仓公开性能数字仍无可比口径 ⇒ 只讲机制有无。"], 1),
    ("漏报侧 受限于环境", ["- 受限于本机无浏览器，交付面未核。"], 1),
    ("漏报侧 仅保证", ["- 因此本产物仅保证同环境可复现。"], 1),
    ("不误伤 同句带取证", ["- 16 仓实测两通道零命中可比数值（run 36244999012）⇒ 不可比，改走自身基线 49 条。"], 0),
    ("不误伤 带计数与单位", ["- 逐文件 CRC 对账：122/122 全等 ⇒ 差异 100% 是行尾，不存在跨环境不可比。"], 0),
    ("不误伤 诚实缺口标注", ["- 心屿真机帧率与 iOS 表现 ❌未实测（headless 数字不作性能结论）。"], 0),
    ("边界 空输入", [], 0),
    ("边界 无可疑词正文", ["# 报告", "- 首页直读 src/，零副本同步点。"], 0),
]


def selftest():
    bad = []
    for name, lines, expect in STUBS:
        got = len(lint_lines(lines))
        if got != expect:
            bad.append("%s：期望 %d 命中，实得 %d" % (name, expect, got))
    # 反向自证：判据若恒不命中（正则被改坏），必须被"漏报侧"用例抓到 ⇒ 上面 3 条即其守卫
    if not lint_lines(["- 受限于 X，无法做到 Y。"]):
        bad.append("判据恒绿：最裸的边界结论都没命中，正则已失效")
    print("DISCLAIMER-SELFTEST-%s（%d 类桩 + 恒绿守卫）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    p = Path(a.file) if a.file else None
    if p is None or not p.is_file():
        print("DISCLAIMER-UNVERIFIED: 未指定可读文件（不得把「没读到」印成通过）")
        return 2
    lines = p.read_text("utf-8", errors="replace").splitlines()
    if not [x for x in lines if x.strip()]:
        print("DISCLAIMER-UNVERIFIED: 输入为空文件 ⇒ 不判绿")
        return 2
    hits = lint_lines(lines)
    for no, word, text in hits:
        print("  %s:%d [%s] %s" % (p.name, no, word, text))
    print("DISCLAIMER-%s: 正文 %d 行，边界声明缺取证 %d 处"
          % ("CLEAN" if not hits else "FAIL", len(lines), len(hits)))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
