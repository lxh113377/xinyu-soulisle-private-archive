# -*- coding: utf-8 -*-
"""kb_source_year_audit.py -- 来源「未来年份」审计（r178-KB46）

为什么立：N50 审计发现 PSY-PR-003 来源⑨ 年份写 2026——「年份 >= 当前年」最易是臆造，
当时是人工逐条核 Crossref 才证真。同类教训已发生过三次（N21/N25 口径漂移、N34/N44 索引漏补）：
靠人工抽查就会漂。本件把它固化成常驻机器面。

判据语义：扫描来源件里所有 (YYYY) 形态的年份，把 **> 当前年** 的（即未来年份）逐条列出，
并要求每条都带 DOI 或 URL（可核）。未来年份本身不判红——今年之后的卷期确实是预告/在线优先，
如 Bianchi 2026 在 Annals of the NYAS 1562(1) 2026-08 已由 Crossref 证真；
判红的是「未来年份且无任何可核载体」= 无法溯源的臆造高风险形态。

另一条腿：荒谬年份（> 2100）一律红——那不是文献年份，是正则咬到了卷号/被引数
（实测源件里有 3875/5643/5827/7021/7841 五个），要么修来源行要么修本件正则，不允许静默。
"""
import re, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "data" / "psych-kb-sources.js"
# 年份形态：`(YYYY)` 且**前面 40 字符内**有题录分隔（". " 或 ", " 或 "］]" 后紧接）。
# 为什么加前缀条件：直接扫 (\d{4}) 会把 `Science 316(5827)`、`302(5643)` 这类「卷(期)」
# 里的四位期号当成年份（实测 5 条假红，全是这个形态）——那些是来源本身没错，是正则咬多了。
# 年份形态：`(YYYY)`，且前面是「作者名 + 空格」或「句读 + 空格」——两种题录写法都认：
#   `Bianchi (2026). Title` （作者在前）   `Somebody, A. (2025). Title`（作者+句读在前）
# 为什么不能只认 `[.,;]\s*[(（]`：前者 `(` 前是空格，会整条漏扫 ⇒ 假绿
#   （实测 Bianchi 2026 就是这么被漏掉的）。
# 为什么不能裸扫 `(\d{4})`：会把 `Science 316(5827)`、`302(5643)` 这类「卷(期)」
#   里的四位期号当成年份（实测 5 条假红，全是这个形态）。
# 折中：认「空格或句读 + (YYYY)」，排除「字母/数字紧跟 (YYYY)」（卷期形态）。
YEAR_RE = re.compile(r"(?:[.,;]\s*|\s)[(（](\d{4})[)）]")
YEAR_MAX = 2100          # 超过它不是文献年份（正则咬到卷号/被引数的形态）


def _entries():
    """从源件 JSON 里抽出全部来源字符串。

    源件是**单行 JSON**（`window.__XINYU_PSYCH_KB_SRC__ = {…}`），按行扫会一条都扫不到
    ——首版判据按行扫出「未来年份 0 条」是**假绿**（Bianchi 2026 就在文件里）。
    改为用 JSON 解析后取每个条目的 src 列表，不用正则切分。
    """
    import json
    txt = SRC.read_text(encoding="utf-8")
    # 从赋值号之后取，不能 txt.index("{")——文件头的注释块里就有花括号
    # （实测首跑取到注释里的 {，报 Expecting property name）
    i = txt.index("__XINYU_PSYCH_KB_SRC__")
    i = txt.index("{", i)
    j = txt.rindex("}")
    data = json.loads(txt[i:j + 1])
    src = data.get("src", {})
    out = []
    for cid, rec in src.items():
        for item in (rec.get("s") or []):
            # 结构实测：s: [{l: 题录标签, u: URL}]，item 是 dict
            # l = 题录标签，u = URL。判「有可核载体」时两者都算——
            # 构建器把 URL 从 l 里拆到 u 字段（面板做成可点链接），只看 l 会漏。
            lab = item.get("l", "") if isinstance(item, dict) else str(item)
            url = item.get("u", "") if isinstance(item, dict) else ""
            out.append((cid, lab + " " + url))
    return out


def future_rows():
    """**当年及以后**（>= 当前年）的来源。

    用 >= 而不是 >：Bianchi (2026) 这类「今年卷期」正是最需要逐条有可核载体的形态
    （实测它就是靠 DOI 才证真）。只盯 > 会把今年全部漏掉 ⇒ 假绿。
    """
    this_year = datetime.date.today().year
    out = []
    for cid, item in _entries():
        for m in YEAR_RE.finditer(item):
            if int(m.group(1)) >= this_year:
                out.append((cid, int(m.group(1)), item))
                break
    return this_year, out


def absurd_rows():
    """荒谬年份（> YEAR_MAX）。"""
    out = []
    for cid, item in _entries():
        for m in YEAR_RE.finditer(item):
            if int(m.group(1)) > YEAR_MAX:
                out.append((cid, int(m.group(1)), item[:150]))
                break
    return out

def main():
    this_year, fut = future_rows()
    absu = absurd_rows()
    # 可核载体形态：URL、DOI、PMID、以及裸 DOI 前缀 10.xxxx/。
    # 为什么认这么宽：实测 3 条「无载体」全是误判——PMID:40449414、
    # 「Crossref 实取 10.3389/fpsyg.2026.1950163」、PMID:41918113 都是可核的，
    # 只是不带 doi.org 前缀。判据要认**可核性**，不是认某一种写法。
    proof_re = re.compile(r"(doi\.org/|DOI|https?://|PMID|\b10\.\d{4,9}/)", re.I)
    no_proof = [row for cid, y, row in fut if not proof_re.search(row)]
    print("  当前年 %d ｜未来年份来源行 %d 条 ｜荒谬年份 %d 条 ｜其中无可核载体 %d 条"
          % (this_year, len(fut), len(absu), len(no_proof)))
    for cid, y, row in fut[:6]:
        print("  · %s %d 年来源：%s" % (cid, y, row[:120]))
    for cid, y, row in absu[:6]:
        print("  · %s 荒谬年份 %d：%s" % (cid, y, row[:120]))
    ok = (not no_proof) and (not absu)
    print("KB-SOURCE-YEAR-AUDIT-" + ("PASS" if ok else "FAIL")
          + ": 未来年份 %d 条全部带可核载体、荒谬年份 %d 条" % (len(fut), len(absu)))
    return 0 if ok else 1


def _audit(entries, this_year):
    """对给定的 [(cid, row)] 跑同一套判定。抽出来供 selftest 做内存态变异——
    不写文件（写文件会破坏源件 JSON，实测报 Extra data）。"""
    absu = []
    fut = []
    for cid, row in entries:
        for m in YEAR_RE.finditer(row):
            y = int(m.group(1))
            if y >= this_year:
                fut.append((cid, y, row))
                break
        for m in YEAR_RE.finditer(row):
            if int(m.group(1)) > YEAR_MAX:
                absu.append((cid, int(m.group(1)), row))
                break
    proof_re = re.compile(r"(doi\.org/|DOI|https?://|PMID|\b10\.\d{4,9}/)", re.I)
    no_proof = [row for cid, y, row in fut if not proof_re.search(row)]
    return fut, absu, no_proof


def selftest():
    """两腿：真面 PASS + 变异腿（注入「当年份且无可核载体」的来源）必须 FAIL。

    变异腿走**内存态**（直接往 entries 里塞一条），不写源件——
    首版把伪造行 append 到文件尾，破坏了 JSON 结构，报 Extra data。
    """
    this_year = datetime.date.today().year
    real = _entries()
    fut, absu, no_proof = _audit(real, this_year)
    rc1 = 0 if (not no_proof and not absu) else 1
    # 变异腿：注入一条「当年份、无 DOI/URL/PMID」的捏造来源
    fake = real + [("PSY-ZZ-999", "[捏造来源] Somebody (%d) Fabricated Journal" % this_year)]
    fut2, absu2, no_proof2 = _audit(fake, this_year)
    rc2 = 0 if (not no_proof2 and not absu2) else 1
    legs = [
        ("真面（当前来源件）", rc1),
        ("变异腿：注入 %d 年且无可核载体的来源行" % this_year, rc2),
    ]
    allok = (rc1 == 0 and rc2 != 0)
    for name, rc in legs:
        print("  " + ("OK  " if rc == 0 else "FAIL") + " " + name)
    print("KB-SOURCE-YEAR-AUDIT-SELFTEST-" + ("PASS" if allok else "FAIL") + ": 2 腿")
    return 0 if allok else 1

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())