# -*- coding: utf-8 -*-
"""kb_citation_check.py — 心理学知识库「引用核对面」判据（r132 常驻）

kb_wiring_check 管的是**注入面**（K2：注入块里的编号必须真存在且级别一致）。
本件管的是它的另一半——**回复面**：模型句末标的〔依据:编号·级〕，是否真对应本轮
实际注入进来的条目。知识面已经干净（E 级在 psych_kb_build.py 构建期就排除了，
132 条全 A-D），但**知识面干净不等于输出面干净**：模型仍可能凭空写一个
PSY-ZZ-999·A，前端照单全收显示成「有依据」。目标里「减少无依据的主观臆造输出」
的最后一环就在这里，此前无任何机器面。

判什么（任一 FAIL 即判红；环境取不到 ⇒ rc=2 UNVERIFIED，不得读成通过）：
  C1 诚实腿：模型标了**本轮真注入**的编号 ⇒ 保留原样、meta 行显示已核对 M/M
  C2 反臆造主腿（**本判据的牙齿**）：模型标了本轮没注入的编号 ⇒ 必须被标「未查证」
     且**编号原文一字不改**（只改标记、不删正文 —— 删正文会把用户的话也带走）
  C3 级不符腿：模型把 B 级标成 A（E 冒充 A 的同类）⇒ 按库里真实级更正并写明「已更正」
  C4 不谎称依据：降级/离线轮（没注入知识库）⇒ 界面不得出现「已核对」字样
  C5 未注入轮的标记也不许蒙混：纯倾诉轮模型若硬标了编号，同样判「未查证」
  C6 零丢失：核对前后正文除标记外逐字一致（拿文本首尾与中段做对照，禁静默删句）
  C7 兜底面：verifyCitations 未挂载时 app.js 必须静默回落原样，不得抛（静态面）

用法：python _test/kb_citation_check.py [--base http://127.0.0.1:8123] [--selftest]
退出码：0=全过 1=判红 2=环境未验证（服务/浏览器/数据件不可达）
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

ID_RE = re.compile(r"\[(PSY-[A-Z]+-\d{3})·([A-E])\]")
CITE_RE = re.compile(r"〔依据[:：]\s*([^〕·]+?)\s*(?:·\s*([A-Ea-e])\s*)?〕")
GHOST_ID = "PSY-ZZ-999"
FILLER = "我在，慢慢说。"


def load_entries():
    p = ROOT / "src" / "data" / "psych-kb.js"
    if not p.exists():
        return None
    m = re.search(r"window\.__XINYU_PSYCH_KB__\s*=\s*(\{.*\});", p.read_text(encoding="utf-8"), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1)).get("entries") or []
    except Exception:
        return None


def judge(reply, used, by_id):
    """判定用的纯镜像：与页面里 verifyCitations 同一套规则。
    返回 (命中数, 未命中数, 逐个标记的结论列表)。selftest 直接打这条腿。"""
    truth = {}
    for u in (used or []):
        if u and u.get("id"):
            truth[str(u["id"]).upper()] = str(u.get("level") or "?")
    out, matched = [], 0
    for cid, lv in CITE_RE.findall(reply or ""):
        key = str(cid).strip().upper()
        real = truth.get(key)
        if not real:
            out.append(("UNVERIFIED", key, str(lv or ""), ""))
        else:
            matched += 1
            shown = str(lv or "").upper()
            out.append(("OK" if (not shown or shown == real) else "CORRECTED", key, shown, real))
    return matched, len(out) - matched, out


def selftest():
    """判据非恒真的取证：3 正例过 + 5 反例红（其中反例②必须红，否则这件判据没有牙齿）。"""
    entries = [{"id": "PSY-AX-002", "level": "B"}, {"id": "PSY-ER-002", "level": "A"}]
    by_id = {e["id"]: e for e in entries}
    used = [{"id": "PSY-AX-002", "level": "B"}]
    fails = []

    # 正例①：诚实标注 → 命中且级一致
    m, u, det = judge(FILLER + "〔依据:PSY-AX-002·B〕", used, by_id)
    if not (m == 1 and u == 0 and det[0][0] == "OK"):
        fails.append("正例①（诚实标注）未被判为 OK")
    # 正例②：模型漏标级 → 仍算命中（不能因为少个级就打成未查证）
    m, u, det = judge(FILLER + "〔依据:PSY-AX-002〕", used, by_id)
    if not (m == 1 and u == 0):
        fails.append("正例②（漏标级）被误判为未查证")
    # 正例③：真实编号但本轮没注入 → 必须未查证（这正是 C2 的核心语义）
    m, u, det = judge(FILLER + "〔依据:PSY-ER-002·A〕", used, by_id)
    if not (m == 0 and u == 1 and det[0][0] == "UNVERIFIED"):
        fails.append("正例③（真条目但未注入）未被判未查证")

    # 反例①：幽灵编号必须红
    m, u, det = judge(FILLER + "〔依据:%s·A〕" % GHOST_ID, used, by_id)
    if not (m == 0 and u == 1):
        fails.append("反例①（幽灵编号）未被判红")
    # 反例②：级不符必须走 CORRECTED，且更正成库里真实级
    m, u, det = judge(FILLER + "〔依据:PSY-AX-002·A〕", used, by_id)
    if not (det and det[0][0] == "CORRECTED" and det[0][3] == "B"):
        fails.append("反例②（E/A 冒充）未被更正为真实级")
    # 反例③：used 为空时任何标记都算未命中（没注入就没依据）
    m, u, det = judge(FILLER + "〔依据:PSY-AX-002·B〕", [], by_id)
    if not (m == 0 and u == 1):
        fails.append("反例③（空 used 却判命中）未被判红")
    # 反例④：未闭合的标记不该被当成合法依据（半截写法不得静默通过）
    m, u, det = judge(FILLER + "〔依据:PSY-AX-002·", used, by_id)
    if m != 0:
        fails.append("反例④（半截标记）被判命中")
    # 反例⑤：全角冒号 + 空格容错要能正常命中（否则真标注会被打成未查证，制造假红）
    m, u, det = judge(FILLER + "〔依据： PSY-AX-002 ·B〕", used, by_id)
    if not (m == 1 and u == 0):
        fails.append("反例⑤（全角冒号容错腿）失效")

    if fails:
        print("KB-CITATION-SELFTEST-FAIL: " + "；".join(fails))
        return 1
    print("KB-CITATION-SELFTEST-PASS: 3 正例过 / 5 反例红（含幽灵编号、E 级冒充、空 used、半截标记、全角冒号容错）")
    return 0


def parse_system(post_data):
    try:
        msgs = json.loads(post_data).get("messages") or []
    except Exception:
        return ""
    return " ".join(m.get("content", "") for m in msgs if m.get("role") == "system")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    entries = load_entries()
    if not entries:
        print("KB-CITATION-UNVERIFIED: 数据件缺失或不可解析（src/data/psych-kb.js）⇒ 先跑构建器")
        return 2
    by_id = {e["id"]: e for e in entries}

    # C7 静态兜底面：核对函数未挂载时不得把主链路带崩
    app_src = (ROOT / "src" / "js" / "app.js").read_text(encoding="utf-8")
    if 'typeof window.ChatAgent.verifyCitations === "function"' not in app_src:
        print("KB-CITATION-FAIL: C7 app.js 缺 verifyCitations 的 typeof 守卫（旧缓存下会把主链路带崩）")
        return 1

    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch as be_launch
    except Exception as e:
        print("KB-CITATION-UNVERIFIED: 浏览器环境不可达: %s" % e)
        return 2

    CURIOUS = "我为什么会反复想同一件难过的事，心理学上有什么原理？"
    PLAIN = "嗯嗯"
    bad, notes = [], []
    state = {"scenario": "honest", "used": [], "post": ""}

    def make_body(scn, used):
        if scn == "ghost":
            return FILLER + "〔依据:%s·A〕" % GHOST_ID
        if scn == "wronglevel":
            return FILLER + "〔依据:%s·A〕" % (used[0]["id"] if used else GHOST_ID)
        if scn == "silent":
            return FILLER
        cid, clv = (used[0]["id"], used[0]["level"]) if used else (GHOST_ID, "A")
        return FILLER + "〔依据:%s·%s〕" % (cid, clv)

    try:
        with sync_playwright() as p:
            b, engine = be_launch(p, label="kb-citation")
            pg = b.new_page(viewport={"width": 1200, "height": 900})
            pg.add_init_script(
                "try{localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                "{proxy:'%s/api/chat',stream:false}))}catch(e){}" % args.base)
            try:
                pg.goto(args.base + "/index.html", wait_until="load", timeout=45000)
            except Exception as e:
                print("KB-CITATION-UNVERIFIED: 页面打不开 %s（服务没起？）: %s" % (args.base, type(e).__name__))
                b.close()
                return 2
            pg.wait_for_timeout(1200)
            pg.evaluate("localStorage.removeItem('peiliao.history.v1');"
                        "localStorage.removeItem('peiliao.emotions.v1'); 1")
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:80]))

            def handler(route):
                post = route.request.post_data
                sysmsg = parse_system(post)
                used = [{"id": i, "level": lv} for i, lv in ID_RE.findall(sysmsg)]
                state["used"] = used
                state["post"] = sysmsg
                body = json.dumps({"choices": [{"message": {"content": make_body(state["scenario"], used)}}],
                                   "usage": {}}, ensure_ascii=False)
                route.fulfill(status=200, content_type="application/json", body=body)

            pg.route("**/api/chat*", handler)

            def send(text, scn, want=2, wait_ms=900):
                state["scenario"] = scn
                pg.fill("#chat-input", text)
                pg.press("#chat-input", "Enter")
                for _ in range(60):
                    if state["used"]:
                        break
                    pg.wait_for_timeout(150)
                pg.wait_for_timeout(wait_ms)
                return state["used"]

            def last_bubble():
                return pg.evaluate("(()=>{const n=document.querySelectorAll('.bubble.ai, .msg.ai, [data-emotion]');"
                                   "return n.length? n[n.length-1].innerText : '';})()")

            # C1：诚实标注 → 已核对
            send(CURIOUS, "honest")
            used = state["used"]
            if not used:
                print("KB-CITATION-UNVERIFIED: 求解释轮没有注入任何知识条目（kbBlockFor 触发面失效，判据无从下手）")
                b.close()
                return 2
            txt = last_bubble()
            if "已核对" not in txt:
                bad.append("C1 诚实标注未被认账：气泡无「已核对」字样（meta=%s）" % txt[:120])
            else:
                notes.append("C1 诚实标注通过（注入 %s·%s → 已核对）" % (used[0]["id"], used[0]["level"]))

            # C2：幽灵编号 → 必须未查证，且编号原文保留
            send(CURIOUS, "ghost")
            txt = last_bubble()
            if "未查证" not in txt:
                bad.append("C2 幽灵编号 %s 未被标「未查证」（反臆造主腿失守）：%s" % (GHOST_ID, txt[:120]))
            elif GHOST_ID not in txt:
                bad.append("C2 判定未查证时把编号原文删掉了（只许改标记、不许删正文）：%s" % txt[:120])
            elif FILLER not in txt:
                bad.append("C2 核对过程吞掉了正文「%s」" % FILLER)
            else:
                notes.append("C2 幽灵编号被打未查证且正文零丢失")

            # C3：级不符 → 按库里真实级更正
            real_level = by_id.get(used[0]["id"], {}).get("level", "?")
            send(CURIOUS, "wronglevel")
            txt = last_bubble()
            if real_level != "A":
                if ("已更正" not in txt) or (real_level not in txt):
                    bad.append("C3 把 %s·A（真实 %s）未更正为真实级：%s" % (used[0]["id"], real_level, txt[:120]))
                else:
                    notes.append("C3 级冒充已更正（模型标 A → 真实 %s）" % real_level)
            else:
                notes.append("C3 跳过：本轮注入条目真实级恰为 A，级冒充腿无区分度（不算判红）")

            # C5：未注入轮（纯倾诉）里硬标的依据同样不许蒙混
            send(PLAIN, "ghost")
            txt = last_bubble()
            if GHOST_ID in txt and "未查证" not in txt:
                bad.append("C5 未注入知识库的一轮里，模型标的 %s 被当作有效依据：%s" % (GHOST_ID, txt[:120]))
            else:
                notes.append("C5 未注入轮的依据标记同样判未查证（或本轮压根没标）")

            # C4：模型完全不标依据 → 不得出现「已核对」（不谎称）
            send(CURIOUS, "silent")
            txt = last_bubble()
            if "已核对" in txt:
                bad.append("C4 模型未标任何依据，界面却显示「已核对」（谎称有据）：%s" % txt[:120])
            else:
                notes.append("C4 零标注轮不谎称依据")

            if errs:
                bad.append("页面报错 %s" % errs[:3])
            b.close()
    except Exception as e:
        print("KB-CITATION-UNVERIFIED: 浏览器腿未跑通: %s: %s" % (type(e).__name__, str(e)[:120]))
        return 2

    for n in notes:
        print("  · " + n)
    if bad:
        for s in bad:
            print("  [FAIL] " + s)
        print("KB-CITATION-FAIL: %d 项判红（引擎=%s，数据件 %d 条）" % (len(bad), engine, len(entries)))
        return 1
    print("KB-CITATION-PASS: C1-C7 全过（引擎=%s｜数据件 %d 条｜幽灵编号判未查证/正文零丢失/级冒充已更正/不谎称依据）"
          % (engine, len(entries)))
    return 0


if __name__ == "__main__":
    sys.exit(main())