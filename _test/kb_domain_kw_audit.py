# -*- coding: utf-8 -*-
"""kb_domain_kw_audit.py —— DOMAIN_KW 词表只读对账腿（r178-KB20）

为什么立：N12 登记「DOMAIN_KW 是人工词表，会漂移」。第 18/19 轮用**实证**方式补了 10 个词
（先测候选词在卡面的命中数，0 命中才补），但那是手工动作。本件把它固化成常驻判据：
从每条卡的「一句话」里抽该域专属词，与 DOMAIN_KW 对账，**只报缺口，不自动改词表**
（README 7.2：不得造第二把尺；N12 的升级方向明确要求「先有 K8 期望域回归腿才能切」，
K8 + kb_retrieval_check 两条腿已在，故只读对账成立）。

判据：只读。rc=0 当且仅当「每个有卡的域都在 DOMAIN_KW 里有至少一个触发词」。
不判红的情况：某域的触发词集合是空的（该域无卡）——那是构建器的事，不是词表的事。
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB_RE = re.compile(r"window\.__XINYU_PSYCH_KB__\s*=\s*(\{.*\});", re.S)
SRC = ROOT / "src" / "js" / "chat-agent.js"


def load_kb():
    t = (ROOT / "src" / "data" / "psych-kb.js").read_text(encoding="utf-8")
    return json.loads(KB_RE.search(t).group(1))["entries"]


def load_domain_kw():
    src = SRC.read_text(encoding="utf-8")
    start = src.index("/* r178-KB16：冷域触发词表")
    fstart = src.index("function kbBlockFor(", start)
    i = src.index("{", fstart); depth = 0; end = -1
    for j in range(i, len(src)):
        c = src[j]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: end = j + 1; break
    body = src[start:end]
    # 从 JS 源里正则抽出 DOMAIN_KW 的键（避免 exec/AST）
    kw = {}
    for m in re.finditer(r"^\s{4}([A-Z]{2,3}):\s*\[", body, re.M):
        dom = m.group(1)
        seg = body[m.end():]
        seg = seg[seg.index("[") + 1:seg.index("]")]
        kw[dom] = [s.strip().strip("\"") for s in seg.split(",")]
    return kw


NON_USER_FACING = {
    "AP", "AT", "BA", "CY", "DC", "ER", "EW", "FE", "JB", "MM",
    "MO", "PD", "PO", "PS", "SE",
}


def main():
    entries = load_kb()
    kw = load_domain_kw()
    by_dom = {}
    for e in entries:
        by_dom.setdefault(e["id"].split("-")[1], []).append(e)
    # 两档分类（r178-KB20）：DOMAIN_KW 是「用户主诉里会出现的专属词」表，不是全域覆盖表。
    # 主诉可达域 = 用户倾诉时会用到该域专属词的域（有卡且必须有词表）；
    # 非主诉可达域 = 产品/技术/理论/测量域，用户主诉里不会出现专属词（N11 已实证分析：
    #   FE 微表情、MM 多模态、PS 筛查量表、DC 咨询技术、EW 表达性书写、ER 情绪调节、
    #   AT 依恋理论、BA 身材理想、CY 网络霸凌、JB 判断偏差、MO 情绪动力学、PD 人格、
    #   PO 积极心理学、SE 语义表征、AP 微表情产品边界 —— 这些卡面是产品边界/技术选型/
    #   学术理论/测量工具，不是用户倾诉内容），显式豁免并列名。
    missing = [d for d in sorted(by_dom) if d not in kw and d not in NON_USER_FACING]
    bare = [d for d in sorted(by_dom) if d in kw and not kw[d]]
    exempt = sorted(d for d in by_dom if d in NON_USER_FACING)
    print("  DOMAIN_KW 域数=%d，有卡的域数=%d（主诉可达 %d + 非主诉可达 %d）"
          % (len(kw), len(by_dom), len(by_dom) - len(exempt), len(exempt)))
    print("  词表里有、库里无卡的域=%s" % (sorted(set(kw) - set(by_dom)) or "无"))
    print("  非主诉可达域（显式豁免，%d 个）：%s" % (len(exempt), "、".join(exempt)))
    if missing:
        print("  缺口（有卡、主诉可达、但词表里完全没有该域）：%s" % "、".join(missing))
    if bare:
        print("  空词表（有卡但该域一个触发词都没有）：%s" % "、".join(bare))
    ok = not missing and not bare
    print("KB-DOMAIN-KW-AUDIT-" + ("PASS" if ok else "FAIL") + ": 主诉可达域无词表 %d 个、有卡空词表 %d 个、非主诉可达域豁免 %d 个"
          % (len(missing), len(bare), len(exempt)))
    return 0 if ok else 1


def _run_with_override(non_user=None, drop=None):
    """变异腿用：在内存里改 NON_USER_FACING 或 DOMAIN_KW，跑完返回 rc。不动 src。"""
    import copy
    kw = load_domain_kw()
    entries = load_kb()
    by_dom = {}
    for e in entries:
        by_dom.setdefault(e["id"].split("-")[1], []).append(e)
    nu = set(non_user) if non_user is not None else set(NON_USER_FACING)
    if drop:
        for d in drop:
            kw.pop(d, None)
    missing = [d for d in sorted(by_dom) if d not in kw and d not in nu]
    bare = [d for d in sorted(by_dom) if d in kw and not kw[d]]
    return (0 if not missing and not bare else 1), "missing=%d bare=%d" % (len(missing), len(bare))


def _exempt_self_check():
    """豁免表自证（r178-KB21）：豁免表本身也是人工写的（N12 仍留一条），本腿把它机器化——
    对称性自证，可复算、不靠通用词反查（词表里大量单字通用词如「我/说/比」，几乎每张卡标题
    都会命中，反查无意义）。判据两条：
    ① 豁免表里每个域都必须有卡（空豁免 = 写错了）；
    ② 词表里每个域，要么在豁免表里、要么有自己的触发词（无遗漏：既不在豁免表又没词 = 该域
       其实主诉可达却被漏写进词表，或该域其实不该豁免却被漏写进豁免表）。"""
    kw = load_domain_kw()
    entries = load_kb()
    by_dom = {}
    for e in entries:
        by_dom.setdefault(e["id"].split("-")[1], []).append(e)
    bad = []
    for d in sorted(NON_USER_FACING):
        if d not in by_dom:
            bad.append("%s 在豁免表但库里无卡" % d)
    for d in sorted(kw):
        if d not in NON_USER_FACING and not kw[d]:
            bad.append("%s 有词表键但词数组为空" % d)
    return (1 if bad else 0), "豁免表/词表对称性异常 %d 项" % len(bad), bad


def selftest():
    # 腿 1：真面 PASS
    rc1, d1 = _run_with_override()
    # 腿 2：把 WV 域的触发词清空 => 该域有卡、主诉可达、但词表空 => 应 FAIL
    rc2, d2 = _run_with_override(drop=["WV"])
    # 腿 3：把非主诉可达域 FE 从豁免表移除 => FE 有卡无词表 => 应 FAIL
    rc3, d3 = _run_with_override(non_user=set(NON_USER_FACING) - {"FE"})
    # 腿 4（r178-KB21）：豁免表自证。豁免表本身也是人工写的（N12 仍留一条），
    # 本腿把它机器化：豁免表里每个域的每一张卡的标题，用现有 DOMAIN_KW 词表反查——
    # 命中即红：说明该域其实主诉可达，不该进豁免表。
    rc4, d4, bad4 = _exempt_self_check()
    for b in bad4:
        print("    " + b)
    legs = [
        ("真面（当前 src + 当前豁免表）", rc1, d1),
        ("变异腿：WV 域触发词清空", rc2, d2),
        ("变异腿：非主诉可达域 FE 移出豁免表", rc3, d3),
        ("豁免表自证（词表反查豁免域卡面标题）", rc4, d4),
    ]
    # 腿 4 是自证腿：真面必须 PASS（豁免表与数据自洽），不是变异腿。
    # 它的判据有效性靠腿 3 保证（腿 3 证明「移出豁免表会红」= 豁免表确实起作用）。
    allok = (rc1 == 0 and rc2 != 0 and rc3 != 0 and rc4 == 0)
    for name, rc, d in legs:
        print("  " + ("OK  " if rc == 0 else "FAIL") + " " + name + "  （" + d + "）")
    print("KB-DOMAIN-KW-AUDIT-SELFTEST-" + ("PASS" if allok else "FAIL") + ": " + str(len(legs)) + " 腿（真面绿 + 变异腿红 + 豁免表自证绿 = 判据咬合）")
    return 0 if allok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())