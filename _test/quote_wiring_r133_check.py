# -*- coding: utf-8 -*-
"""quote_wiring_r133_check.py — 语料库侧引用消费 + r133 接线判据（**不重复 kb_citation_check**）

为什么是独立一件（避免造第二把尺）：
  `_test/kb_citation_check.py`（已在电池、C1-C7 全过）已完整覆盖 verifyCitations 的
  三结局（命中保留 / 级不符更正 / 未命中标未查证）、正文零丢失、app.js typeof 守卫。
  ⇒ 本件**不复验**那些，只补两条它没有的：

  腿A 接线腿（r132 的真缺陷）：verifyCitations 定义了却**零调用点** ⇒ 输出面等于无核对，
      模型可自行标 〔依据:PSY-XX-999·A〕凭空编出处。r133 把它接进 onlineReply。
      腿A 是纯静态面（可在无浏览器环境跑），判据非恒真：还原成零调用点必转红。
  腿B 语料库侧消费面（QTE-*）：表达语料库注入的条目**从不带编号**（kbBlockFor 才有
      〔依据:PSY-XX-999·A〕那种 id·级 形态），所以 QTE-* 天然不会被 verifyCitations 核对 ——
      这本身是对的（引言句不是知识主张）。腿B 要钉住的是这个**预期**，防将来有人给 QTE
      编编号、或把 kb 的 id 形态误用到 quote 侧。

用法: python _test/quote_wiring_r133_check.py [--selftest]
退出码: 0=PASS 1=FAIL
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "src" / "js" / "chat-agent.js"

CALL_SNIPPET = "const v = verifyCitations(raw, sys.kbUsed);"


def legs():
    res = []

    def leg(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    raw = AGENT.read_text(encoding="utf-8")

    # ── 腿A 接线腿 ────────────────────────────────────────
    defs = len(re.findall(r"function verifyCitations\s*\(", raw))
    calls = len(re.findall(r"(?<!function )\bverifyCitations\s*\(", raw))
    leg("A1 verifyCitations 有且仅有一份定义（禁重复实现）", defs == 1, "defs=%d" % defs)
    leg("A2 verifyCitations 有调用点（r132 缺陷：零调用点）", calls >= 1, "calls=%d" % calls)
    leg("A3 调用点在 onlineReply 内（改写最终回复而非旁路）",
        re.search(r"onlineReply[\s\S]{0,1200}?" + re.escape(CALL_SNIPPET), raw) is not None)
    leg("A4 调用点在 llmFetch 之后（拿到的是完整回复）",
        re.search(r"llmFetch\([\s\S]{0,400}?" + re.escape(CALL_SNIPPET), raw) is not None)
    leg("A5 非流式才改写、流式只回计数（防屏幕文字与内存不一致）",
        re.search(r"streamed\s*\?\s*raw\s*:\s*v\.text", raw) is not None and "citeApplied" in raw)

    # ── 腿B 语料库侧消费面 ──────────────────────────────────
    leg("B1 引用消费遥测随 respond 返回（citeChecked/Matched/Unmatched 三键在位）",
        all(k in raw for k in ("citeChecked", "citeMatched", "citeUnmatched")))
    leg("B2 遥测在降级/离线轮恒为 0（口径同 memory/dropped，不得说谎）",
        re.search(r"citeChecked:\s*mode === \"model\" \? citeChecked : 0", raw) is not None)
    seg = re.search(r'if \(emo === "crisis"\) \{[\s\S]*?\n    \}', raw)
    leg("B3 危机分支零引用口径（危机轮不注入、不核引用）",
        seg is not None and "citeChecked" not in seg.group(0) and "verifyCitations" not in seg.group(0))
    # quote 侧注入项不带 id·级 形态 ⇒ QTE-* 不会进核对面（这是预期，防误改）
    qb = re.search(r"function quoteBlockFor\(emo, userText, budget\) \{[\s\S]*?\n  \}\n", raw)
    leg("B4 quote 候选不带〔依据:id·级〕形态（引言非知识主张，天然不入核对面）",
        qb is not None and "·" + '\" + p.e.level + \"]' in qb.group(0)
        and "usedIds" not in qb.group(0))
    leg("B5 kb 候选带 id·级 形态（与 B4 对照：两种注入面形态不同是事实）",
        re.search(r"used\.push\(\{ id: p\.e\.id, level: p\.e\.level \}\)", raw) is not None)

    return res


def main():
    res = legs()
    bad = [r for r in res if not r[1]]
    for name, ok, detail in res:
        print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, ("  <- " + detail) if (detail and not ok) else ""))
    if bad:
        print("QUOTE-WIRING-R133-FAIL: %d/%d 腿通过，失败 %d 条" % (len(res) - len(bad), len(res), len(bad)))
        return 1
    print("QUOTE-WIRING-R133-PASS: %d/%d 腿（接线 A1-A5 / 语料库消费面 B1-B5；"
          "verifyCitations 三结局由 kb_citation_check C1-C7 负责，本件不重复）" % (len(res), len(res)))
    return 0


def run_selftest():
    """可逆注入：把 r132 的缺陷（零调用点）真注入回产品面，A2/A3 必须转红。"""
    src_bytes = AGENT.read_bytes()
    src = src_bytes.decode("utf-8")
    base = dict((n, ok) for n, ok, _ in legs())
    mutant = src.replace(CALL_SNIPPET,
                         "const v = { text: raw, checked: 0, matched: 0, unmatched: 0 };")
    if mutant == src:
        print("QUOTE-WIRING-R133-SELFTEST-FAIL: 锚点 %s 未找到，自证不可做" % CALL_SNIPPET)
        return 1
    red = False
    try:
        # ⚠️ 必须走二进制读写：write_text 在 Windows 文本模式会把 "\n" 翻成 "\r\n"，
        #    还原时逐字节对不上（本仓排障手册已登记同族）。自证脚本改产品文件尤其危险。
        AGENT.write_bytes(mutant.encode("utf-8"))
        red = dict((n, ok) for n, ok, _ in legs())
    finally:
        AGENT.write_bytes(src_bytes)
    restored = AGENT.read_bytes() == src_bytes
    a2_red = not red.get("A2 verifyCitations 有调用点（r132 缺陷：零调用点）", True)
    a3_red = not red.get("A3 调用点在 onlineReply 内（改写最终回复而非旁路）", True)
    print("  %s  基线全绿" % ("PASS" if all(base.values()) else "FAIL"))
    print("  %s  变异A 零调用点→A2 红" % ("PASS" if a2_red else "FAIL"))
    print("  %s  变异A 零调用点→A3 红" % ("PASS" if a3_red else "FAIL"))
    print("  %s  磁盘还原（逐字节）" % ("PASS" if restored else "FAIL"))
    if all(base.values()) and a2_red and a3_red and restored:
        print("QUOTE-WIRING-R133-SELFTEST-PASS: 4 腿（判据非恒真）")
        return 0
    print("QUOTE-WIRING-R133-SELFTEST-FAIL: 变异腿未转红")
    return 1


if __name__ == "__main__":
    sys.exit(run_selftest() if "--selftest" in sys.argv else main())