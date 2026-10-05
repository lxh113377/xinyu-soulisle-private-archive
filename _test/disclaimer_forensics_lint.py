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
# r96 增「不可测」族：立因是**这一族话在本仓能连说 74 轮而没人被要求举证**——
# r95:10-11 与 :241-242 两次写「issue 响应速度不可测 / 多数仓的已关闭 issue 无人工评论痕迹」，
# 本轮建 `_test/peer_issue_response_probe.py` 实测 12 仓：**该断言为假**（with_comments
# 30/30、27/30、26/30、28/30、25/30、29/29…）。原词表看不见"不可测"三个字 ⇒ 一句没有
# 取证的断言就这样被后续轮次当现状继承。加词是**改尺不改数据**（R263）。
BOUNDARY = re.compile(r"(不可比|无可比口径|没有可比|无法比较|不能比较|受限于|仅保证|无法做到|做不到|只能保证|物理限制"
                      r"|不可测|测不了|无法测量|无从测量)")
# 实证标记（这条结论是怎么来的）
# 实证标记（这条结论是怎么来的）。⚠ 不放裸「口径」二字：`无可比口径` 自身就是被拦的话术，
# 放进白名单会让句子自己把自己洗白（r40c 首跑即由 selftest 抓到：漏报侧桩 0 命中）。
# ⚠ r96 抓到的**同族第二形态**：`实测` 作为裸子串会被 `未实测 / 待实测` 满足 ⇒
#   一句"自称没测"的话反而拿到了取证白名单（本轮新加的 `不可测` 用例撞出来后顺藤查到，
#   该缺陷自判据建立起就在，此前无人写用例所以从未暴露）。正解是否定式前瞻，不是把
#   `未实测` 加进白名单——后者会让"未实测 + 不可测"这种组合永久隐身。
FORENSIC = re.compile(r"(?:(?<!未)(?<!待)实测|取证|命令|脚本|_test/|\.py|run[: ]?\d{6,}|workflow|逐条|逐文件|分母|样本|样例|"
                      r"\d+\s*(仓|条|个|文件|次|行)|\d+(\.\d+)?\s*(%|ms|MB|KB|B\b|rps|fps)|sha256|sha1|CRC|ls-remote|gh )")
# 诚实缺口（不是本判据的对象）
DECLARED_GAP = re.compile(r"(未实测|待实测|❌|未取|待补|待办)")
# 「只标注缺口」与「主张做不到」的界线。**不可测/测不了 属于后者**：一行里同时出现
# 「未实测」和「不可测」时，那句仍是"这维做不到"，不得借 未实测 洗白。
HARD_ASSERT = re.compile(r"(受限于|仅保证|无法做到|做不到|只能保证|物理限制|不可测|测不了|无法测量|无从测量)")


def lint_lines(lines):
    """返回 [(行号, 命中词, 该行文本)]。零输入不在此判，交调用方处理（防把空当绿）。"""
    hits = []
    for i, ln in enumerate(lines, 1):
        m = BOUNDARY.search(ln)
        if not m:
            continue
        if FORENSIC.search(ln):
            continue                    # 带取证 ⇒ 合法边界结论
        if DECLARED_GAP.search(ln) and not HARD_ASSERT.search(ln):
            continue                    # 只标注缺口，不主张"做不了" ⇒ 另一个判据管
        hits.append((i, m.group(1), ln.strip()[:120]))
    return hits


def scan_file(path):
    return lint_lines(path.read_text("utf-8", errors="replace").splitlines())


# r93（体量治理·先改判据再搬文件）：归档历史对标报告后，原来的**单目录** glob 会把分母打成 0
# ⇒ rc=2 UNVERIFIED，电池里这条从 PASS 变未验，CI 电池随之传导。
# CHANGELOG 曾明文记过「搬走即静默失去覆盖，体积只省 ~0.5MB」——那条判断在**单目录 glob** 下成立；
# 扩成双目录后，「覆盖面不缩小」与「文件可归档」就不再互斥，故本轮据此改口径并显式声明分母变化。
# 目录名 `_历史轮次-对标` 与 `deliverable_inventory_check.py` selftest 里已写死的搬卷落点同名，不另造名。
SCAN_ROOTS = ("交付物", "交付物/_历史轮次-对标")
CORPUS_GLOB = "对标分析报告-*.md"


def collect(root_map):
    """纯函数：{面名: [Path,...]} → [(面名, path)]，跨面**去重**后按 (面名, 文件名) 排序。
    去重是必需的：两个面若有交集（未来把归档目录挪进交付物根就会交），同一份报告只能计一次，
    否则「份数」会虚高——那正是本判据分母最容易被悄悄改坏的地方。"""
    seen, out = set(), []
    for label, paths in root_map.items():
        for p in paths:
            key = str(p.resolve()) if p.exists() else str(p)
            if key in seen:
                continue
            seen.add(key)
            out.append((label, p))
    return sorted(out, key=lambda t: (t[0], t[1].name))


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
    # r96 新增一族：「不可测」此前不在词表里 ⇒ 一句没有取证的断言连说 74 轮不被举证
    ("漏报侧 不可测裸断言", ["- 维度 6「issue 响应速度」在公开数据上不可测。"], 1),
    ("漏报侧 测不了", ["- 该这一维没有可比对象，测不了。"], 1),
    ("漏报侧 不可测 借「未实测」洗白 ⇒ 仍须红", ["- 该维未实测，也判不可测。"], 1),
    ("不误伤 不可测但同句给了取证",
     ["- 原判不可测，本轮 _test/peer_issue_response_probe.py 实测 16 仓后改判有读数。"], 0),
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
    # r96 变异腿：把 BOUNDARY 换回**加词之前**的形态 ⇒ 「不可测」那条必须漏报。
    # 没有这条腿，"我加了词"与"词真的在咬"是两件事（本仓 r95 §2.5 原话：只有正例腿抓不到尺恒假，
    # 反过来也只有变异腿抓不到"加了个不生效的词"）。
    keep = globals()["BOUNDARY"]
    globals()["BOUNDARY"] = re.compile(
        r"(不可比|无可比口径|没有可比|无法比较|不能比较|受限于|仅保证|无法做到|做不到|只能保证|物理限制)")
    if lint_lines(["- 维度 6 在公开数据上不可测。"]):
        bad.append("变异体失效：换回旧词表却仍命中「不可测」⇒ 期望值写死了")
    globals()["BOUNDARY"] = keep
    if not lint_lines(["- 维度 6 在公开数据上不可测。"]):
        bad.append("还原后「不可测」仍漏报：加词没生效（改的是副本不是全局名）")
    # r96 第二条变异腿：`未实测` 里的裸子串 `实测` 曾把无取证断言洗白（判据建立起就在的缺陷，
    # 本轮由新加用例撞出）。把前瞻摘掉 ⇒ 那条组合必须重新漏报 ⇒ 证明摘的是尺不是期望值。
    keep_f = globals()["FORENSIC"]
    globals()["FORENSIC"] = re.compile(r"实测|取证|命令|脚本|_test/|\.py|workflow|分母")
    if lint_lines(["- 该维未实测，也判不可测。"]):
        bad.append("变异体失效：摘掉否定前瞻后该行仍被拦 ⇒ 它红的原因不是这条前瞻，期望值写死了")
    globals()["FORENSIC"] = keep_f
    if not lint_lines(["- 该维未实测，也判不可测。"]):
        bad.append("否定前瞻未生效：`未实测` 仍把 `不可测` 洗白")
    # r93：双面分母的两条腿（缺了它们，「扩面」这件事本身是恒真的）
    two = collect({"交付物": [Path("a.md"), Path("b.md")],
                   "交付物/_历史轮次-对标": [Path("c.md")]})
    if len(two) != 3 or [p.name for _, p in two] != ["a.md", "b.md", "c.md"]:
        bad.append("双面收集失真：%r" % (two,))
    if collect({}) != []:
        bad.append("空面不得凭空收出文件（零分母必须由主流程判 UNVERIFIED）")
    print("DISCLAIMER-SELFTEST-%s（%d 类桩 + 恒绿守卫 + 双面分母 2 腿）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--all", action="store_true",
                    help="扫 对标报告全集（分母从目录现读：%s，不手抄清单）" % " + ".join(SCAN_ROOTS))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.all:
        # 为什么要有这条：判据原先钉死单个文件名，出新报告后**它扫的还是上一份**
        # ⇒ "报告都有取证"这句话对新产物不成立（r41 发现自己踩的正是这一族）。
        repo = Path(__file__).resolve().parents[1]
        root_map = {}
        for r in SCAN_ROOTS:
            root_map[r] = sorted((repo / r).glob(CORPUS_GLOB)) if (repo / r).is_dir() else []
        pairs = collect(root_map)
        if not pairs:
            print("DISCLAIMER-UNVERIFIED: 两个面都没有对标报告（%s）⇒ 空分母不判绿" % " + ".join(SCAN_ROOTS))
            return 2
        bad, rows = [], []
        for label, f in pairs:
            hits = scan_file(f)
            rows.append((f.name, len(hits)))
            for no, word, text in hits:
                bad.append("%s:%d [%s] %s" % (f.name, no, word, text))
        for line in bad:
            print("  " + line)
        detail = "、".join("%s=%d" % r for r in rows)
        per_face = " + ".join("%s %d" % (r, len(root_map[r])) for r in SCAN_ROOTS)
        print("DISCLAIMER-%s: 报告 %d 份（分母从目录现读：%s），缺取证 %d 处｜%s"
              % ("CLEAN" if not bad else "FAIL", len(pairs), per_face, len(bad), detail))
        return 0 if not bad else 1
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
