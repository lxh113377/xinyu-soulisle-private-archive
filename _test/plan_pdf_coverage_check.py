# -*- coding: utf-8 -*-
"""应用方案 PDF 的九项覆盖判据（iCAN 硬截止前的交付面自证）。

要解决的问题：清单第 1 行写着「20 页 / 9 图，官方 9 项逐项齐全」，但这是**人眼对照**的结论。
`render-pdf.ps1` 随时可被重跑，HTML 里删掉一节就会静默少一项，而页数仍可能 ≤20 ⇒ 账面全绿。
本判据把这句承诺绑成机器断言。

口径（写死在代码里，不靠注释）：
  · 9 项**从 `交付物/提交包/应用方案大纲.md` 的表格现读**（唯一真相源），不手抄清单；
    大纲里第 10 行「原创与数据声明」是本方案自加的，不计入官方 9 项。
  · 页面上界 **20**（官方硬约束）由 pypdf 实数页核对；取不到 pypdf 时退回对象计数并标 UNVERIFIED。
  · 文本层必须**非空**：抽取字符数低于下限时判 UNVERIFIED（扫描版/图片版 PDF 会让「零命中」
    看起来像"缺项"，而真正的风险是反过来——把"没抽到字"当成"什么都没缺"）。
退出码：0=九项齐且页数合规 1=有缺项或超页 2=不可判（文件缺失 / 文本层空 / 分母为空）
用法：python _test/plan_pdf_coverage_check.py [--selftest]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "交付物" / "提交包" / "心屿SoulIsle-应用方案.pdf"
OUTLINE = ROOT / "交付物" / "提交包" / "应用方案大纲.md"
PAGE_CAP = 20
OFFICIAL_ITEMS = 9
MIN_TEXT_CHARS = 2000      # 20 页方案的正文物证下限；低于此说明文本层不可靠


def official_items(outline_text):
    """从大纲表格现读官方条目名（形如 `| 1 项目背景 | 1.5 | …`），只取前 9 条。"""
    got = []
    for line in outline_text.splitlines():
        m = re.match(r"\|\s*(\d{1,2})\s+([^|]{2,24})\s*\|", line)
        if m:
            got.append((int(m.group(1)), m.group(2).strip()))
    got.sort()
    return [name for _n, name in got[:OFFICIAL_ITEMS]]


def page_count(pdf_bytes):
    try:
        from pypdf import PdfReader
        import io
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages), "pypdf"
    except Exception:
        trees = len(re.findall(rb"/Type\s*/Pages", pdf_bytes))
        counts = [int(x.group(1)) for x in re.finditer(rb"/Count\s+(\d+)", pdf_bytes)]
        if counts and trees:
            return max(counts), "对象计数（pypdf 不可用，退路）"
        return None, "取不到页数"


def extract_text(pdf_bytes):
    try:
        from pypdf import PdfReader
        import io
        r = PdfReader(io.BytesIO(pdf_bytes))
        # ⚠ 必须用 "\n" 连接：首版用 "" 连接，于是**每页第一行被粘到上一页末行**，
        # 而本文档的一级章节标题**正好都是页首行** ⇒ 九章全部"查无"，判据把完好的 PDF 报成缺九章。
        # 这是"尺子错"不是"内容错"，与 M5⑧（两侧不同尺）同族；防护见下方"粘行"守卫。
        return "\n".join((pg.extract_text() or "") for pg in r.pages), "pypdf"
    except Exception as e:
        return "", "抽取失败(%s)" % type(e).__name__


def unanchored_headings(text):
    """不看行首，只数「一、…九、」这类标题串是否出现——用于区分"真缺章"与"取数形状可疑"。"""
    return len(set(re.findall(r"([一二三四五六七八九])\s*[、.．]\s*\S", text)))


CN = "一二三四五六七八九"
TOP_HEADING = re.compile(r"^([一二三四五六七八九])\s*[、.．]\s*(\S.{0,40})$")


def segments(label):
    """把大纲条目切成可比的词块（长度≥2）。

    为什么不能整串比对（r40d 实测）：大纲写「目标用户与功能需求」，PDF 写
    「四、目标用户群体及功能需求」；大纲写「功能逐项说明（AI核心作用）」，PDF 写
    「七、作品功能逐项说明（重点：AI 功能的核心作用）」——**两侧同义不同字**。
    整串相等会把已在的两项报成缺失，属"同一判断用两把尺"（M5⑧）。
    """
    parts = re.split(r"[与和（）()/／、·\s]+", label)
    return [p for p in parts if len(p) >= 2]


def top_chapters(text):
    """从 PDF 文本层现读一级章节标题（按中文数字定序）。"""
    ch = {}
    for ln in text.splitlines():
        m = TOP_HEADING.match(ln.strip())
        if m:
            ch.setdefault(CN.index(m.group(1)) + 1, m.group(2).strip())
    return ch


def check(items, text, pages):
    """纯函数：返回 (problems, stats)。缺章 / 措辞对不上 / 超页 / 空文本层 / 空分母都要出声。"""
    bad = []
    if not items:
        return ["分母为空：大纲里取不到官方 9 项 ⇒ 不得判绿"], {}
    if len(text) < MIN_TEXT_CHARS:
        return ["文本层不可用（抽到 %d 字符 < %d）⇒ UNVERIFIED，禁止把「零命中」读成「无缺项」"
                % (len(text), MIN_TEXT_CHARS)], {}
    if pages is None:
        return ["取不到页数 ⇒ 页面上界无从判定，不判绿"], {}
    if pages > PAGE_CAP:
        bad.append("页数 %d 超官方上界 %d" % (pages, PAGE_CAP))
    if len(items) < OFFICIAL_ITEMS:
        bad.append("大纲只现读到 %d 条官方项（应 ≥ %d）⇒ 分母可疑，先查大纲是否被改"
                   % (len(items), OFFICIAL_ITEMS))
    ch = top_chapters(text)
    hit = 0
    for i, label in enumerate(items[:OFFICIAL_ITEMS], start=1):
        title = ch.get(i)
        if not title:
            bad.append("第 %s 章缺失：PDF 文本层没有「%s、…」一级标题（大纲项「%s」）"
                       % (CN[i - 1], CN[i - 1], label))
            continue
        segs = segments(label)
        if label in title or title in label or any(s in title for s in segs):
            hit += 1
        else:
            bad.append("第 %s 章标题「%s」与大纲项「%s」无共同词块 ⇒ 该章可能不是这一项"
                       % (CN[i - 1], title, label))
    return bad, {"items": min(len(items), OFFICIAL_ITEMS), "found": hit,
                 "chapters": len(ch), "pages": pages, "chars": len(text)}


def selftest():
    items = ["项目背景", "痛点问题", "需求分析", "目标用户与功能需求", "开发工具",
             "技术方案", "功能逐项说明（AI核心作用）", "使用说明", "应用前景与商业模式"]
    titles = ["项目背景", "痛点问题", "需求分析", "目标用户群体及功能需求", "开发工具",
              "技术方案", "作品功能逐项说明（重点：AI 功能的核心作用）", "完整使用说明", "应用前景与商业模式"]
    body = ("填充正文以越过文本层下限。" * 200 + "\n" +
            "\n".join("%s、%s" % (CN[i], titles[i]) for i in range(9)))
    bad = []
    if check(items, body, 20)[0]:
        bad.append("①正例（九章齐 + 同义不同字）被判红 ⇒ 误伤：%s" % check(items, body, 20)[0][:1])
    少七章 = "\n".join(l for l in body.splitlines() if not l.startswith("七、"))
    if not check(items, 少七章, 20)[0]:
        bad.append("②删掉第七章仍判绿 ⇒ 恒绿（重渲染丢节没人拦）")
    if not check(items, body.replace("目标用户群体及功能需求", "附录杂项"), 20)[0]:
        bad.append("③第四章换成无关标题仍判绿 ⇒ 措辞核对形同虚设")
    if not check(items, body, 24)[0]:
        bad.append("④超页未被抓到 ⇒ 页面上界失效")
    if not check(items, "", 20)[0]:
        bad.append("⑤空文本层被判绿 ⇒ 把「没抽到字」当成「什么都没缺」")
    if not check([], body, 20)[0]:
        bad.append("⑥分母为空被判绿")
    if not check(items, body, None)[0]:
        bad.append("⑦取不到页数仍判绿")
    # ⑧⑨ 粘行守卫：让九个标题全部**不在行首**（首版 extract_text 用 "" 连页时的真实形状）
    glued = "上一页末行 " + " ".join("%s、%s" % (CN[i], titles[i]) for i in range(9)) + ("填充" * 300)
    g_bad, g_st = check(items, glued, 20)
    if not g_bad or g_st.get("found"):
        bad.append("⑧粘行形态未被暴露（found=%s）⇒ 锚定核对太松" % g_st.get("found"))
    if unanchored_headings(glued) < OFFICIAL_ITEMS:
        bad.append("⑨粘行时非锚定扫描也数不到九章 ⇒ main 的 UNVERIFIED 守卫不会触发")
    print("PLAN-PDF-COVERAGE-SELFTEST-%s（九向：误伤 1 / 漏报 4 / 读空气 2 / 取数形状 2）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad)))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if not PDF.is_file() or not OUTLINE.is_file():
        print("PLAN-PDF-COVERAGE-UNVERIFIED: 缺件（PDF=%s 大纲=%s）⇒ 不判绿"
              % (PDF.is_file(), OUTLINE.is_file()))
        return 2
    raw = PDF.read_bytes()
    items = official_items(OUTLINE.read_text("utf-8", errors="replace"))
    pages, psrc = page_count(raw)
    text, tsrc = extract_text(raw)
    bad, st = check(items, text, pages)
    # 取数形状守卫：九章全"查无"但非锚定扫描数得到 ⇒ 是**取数方式**可疑，不是内容缺失
    # （首版 extract_text 用 "" 连页，把页首的章节标题粘到上一行，就是这种形状 ⇒ 必须 UNVERIFIED，
    #   绝不能把"我数错了"报成"交付物缺九章"，也不能反过来把它悄悄放宽成绿）
    if bad and st.get("found") == 0 and len(items) >= OFFICIAL_ITEMS and unanchored_headings(text) >= OFFICIAL_ITEMS:
        print("PLAN-PDF-COVERAGE-UNVERIFIED: 九章标题在文本层里存在但都不在行首 ⇒ 取数形状可疑（分页连接/换行丢失），"
              "不判缺也不判绿（%s）" % tsrc)
        return 2
    if bad:
        for b in bad:
            print("  FAIL", b)
        print("PLAN-PDF-COVERAGE-%s: 大纲现读官方项 %d 条，PDF 命中 %s 条，页数 %s（%s），文本层 %s 字符（%s）"
              % ("FAIL", len(items), st.get("found", "?"), pages, psrc, len(text), tsrc))
        return 1
    print("PLAN-PDF-COVERAGE-PASS: 官方九项全覆盖（%d/%d）｜页数 %d ≤ %d（%s）｜文本层 %d 字符（%s）｜分母取自大纲"
          % (st["found"], st["items"], st["pages"], PAGE_CAP, psrc, st["chars"], tsrc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
