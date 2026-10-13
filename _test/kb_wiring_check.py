# -*- coding: utf-8 -*-
"""kb_wiring_check.py — 心理学知识库注入链路判据（r129 常驻）

补齐的是目标里「响应生成环节」那一半的机器面：库建得再好，**注入链断了没人知道**。
r113 当时的 kb 探针是单腿一次性件（见 quote_wiring_check.py 头部自述），此后三轮扩库
（第 3/4/5 轮）都没再跑过它 ⇒ 「条目卡⇄数据件⇄提示词」这条链的后半段一直是零读数。

判什么（任一 FAIL 即判红；环境取不到 ⇒ rc=2 UNVERIFIED，不得读成通过）：
  K1 求解释轮有依据：用户问「为什么/什么原理」时，system 里必须出现知识条目块且 ≥1 条 [PSY-…·级]
  K2 注入的编号必须真存在且级别一致（**反臆造钉子**：模型拿到的编号若在数据件里查不到，
     就是注入面在编造引用；同理级别不符会让〔依据:编号·级〕标错可信度）
  K3 纯倾诉轮不注入（防「共情回复变心理课」，persona 禁说教的机制面）
  K4 危机轮零注入且不发 API 请求（危机由词典短路，表情/知识都不许介入）
  K5 system 总长 ≤1600 字符（继承 context_budget X3；知识块与记忆/概要/引语共享这块余量）
  K6 反臆造指令文案在位：知识块头部必须含「不要编造文献或数据」「弱化表述」「争议双方」三处约束词
     —— 这三句是「减少无依据臆造」在提示词层的钉子，被删或被改写即红
  K7 数据件面（零浏览器）：产品件里不得出现 E 级；每条必须有 title/summary/rel，
     content 的长度判据 = **「超长必须以免责短语开头」**而非裸字节上限
      —— r167-KB11b 起构建器会把医疗免责短语**前置到句首**，这批卡的 content 有意超出
      CONTENT_MAX（README §7 明文「安全优先于字节预算」），裸上限会把它们全判红。
      常量与正则一律从 psych_kb_build 导入，禁在本文件另立副本（两处副本必然漂移）。

用法：python _test/kb_wiring_check.py [--base http://127.0.0.1:8123] [--selftest]
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

KB_MARK = "可依据的心理学知识条目"
ANTI_FAB_KW = ("不要编造文献或数据", "弱化表述", "争议双方")
SYSTEM_BUDGET = 1600
# r172：截断口径与免责短语正则**从构建器导入**，不在本文件另立副本。
# 原先是裸的 CONTENT_MAX = 320，与 psych_kb_build.CONTENT_MAX 成了两份真相，
# r167-KB11b 改了构建行为而判据没跟着改 ⇒ 实测 8 张卡假红。
from psych_kb_build import CONTENT_MAX, BOUNDARY_RE
CRISIS_TEXT = "我不想活了，真的好累"
CURIOUS_TEXT = "我为什么会反复想同一件难过的事，心理学上有什么原理？"
PLAIN_TEXT = "嗯嗯"
KB_RE = re.compile(r"window\.__XINYU_PSYCH_KB__\s*=\s*(\{.*\});", re.S)
ID_RE = re.compile(r"\[(PSY-[A-Z]+-\d{3})·([A-E])\]")
REPLY_BODY = '{"choices":[{"message":{"content":"我在，慢慢说。"}}],"usage":{}}'


def load_entries():
    p = ROOT / "src" / "data" / "psych-kb.js"
    if not p.exists():
        return None
    m = KB_RE.search(p.read_text(encoding="utf-8"))
    if not m:
        return None
    try:
        return json.loads(m.group(1)).get("entries") or []
    except Exception:
        return None


def extract_ids(system):
    return ID_RE.findall(system or "")


def parse_systems(captured):
    out = []
    for body in captured or []:
        try:
            msgs = json.loads(body).get("messages") or []
        except Exception:
            continue
        out.append(" ".join(m.get("content", "") for m in msgs if m.get("role") == "system"))
    return out


def ghost_ids(ids, entries):
    """注入块里出现、但数据件里没有或级别不符的编号 —— 注入面在造引用。"""
    by_id = {e["id"]: e for e in entries}
    return ["%s·%s" % (i, lv) for i, lv in ids if i not in by_id or by_id[i]["level"] != lv]


def starts_with_boundary(text):
    """content 的**第一句**是否就是医疗免责短语（r167-KB11b 的有意超出形态）。

    判据只认「句首」，不认「句中出现」：构建器 keep_boundary 的语义就是把摘出的免责句
    **前置到句首**（前置而非后置，因后置会被下一次长度变化再截掉）。若只看句中出现，
    一条无免责句的超长条目只要在中间塞一个免责短语就能蒙混过关。
    """
    head = re.split(r"(?<=。)|(?<=；)", text or "", maxsplit=1)[0]
    return bool(BOUNDARY_RE.search(head))


def check_data_face(entries):
    bad = []
    for e in entries:
        lv = e.get("level")
        if lv not in ("A", "B", "C", "D"):
            bad.append("%s 级别 %r 不合法（E 级禁入产品件）" % (e.get("id", "?"), lv))
        for k in ("title", "summary"):
            if not e.get(k):
                bad.append("%s 缺 %s" % (e.get("id", "?"), k))
        content = e.get("content") or ""
        if len(content) > CONTENT_MAX and not starts_with_boundary(content):
            bad.append("%s 内容 %d 字超截断上限 %d，且句首不是免责短语"
                       "（有意超出只允许「免责短语前置」这一个理由）"
                       % (e.get("id", "?"), len(content), CONTENT_MAX))
    return bad


def starts_with_boundary_probe_ok():
    """造一条「超长且句首即免责短语」的样本，长度确保 > CONTENT_MAX。"""
    head = "本条目不构成医疗诊断建议。"
    return head + ("这是研究结论，用于把整条撑过截断上限。" * 20)


def selftest():
    """判据非恒真的取证：每条腿登记 (名称, 是否反例, 实际是否符合预期)，收尾实算。

    r172 起不再硬编码报数——加腿后硬编码的报数会静默说谎（判据自身失真比判据失守更难发现）。
    """
    entries = [{"id": "PSY-AX-002", "level": "B", "title": "担忧 vs 反刍", "summary": "s", "content": "c"},
               {"id": "PSY-ER-002", "level": "A", "title": "重评 vs 抑制", "summary": "s", "content": "c"}]
    head = (KB_MARK + "（回答可自然融入，不说教；句末可标〔依据:编号·级〕；"
            "条目未覆盖的专业内容不要编造文献或数据，用弱化表述；D级内容须呈现争议双方）：")
    good = head + "\n[PSY-AX-002·B]担忧 vs 反刍：s"
    ghost = head + "\n[PSY-ZX-999·B]不存在的条目：s"
    wrong_level = head + "\n[PSY-AX-002·A]级别被改：s"
    no_keywords = KB_MARK + "（随便说说）：\n[PSY-ER-002·A]重评：s"

    # (名称, 是否反例腿, 实际是否符合预期)
    legs = [
        ("正例①知识块标记在位", False, KB_MARK in good),
        ("正例②合法编号不判幽灵", False, not ghost_ids(extract_ids(good), entries)),
        ("反例①幽灵编号判红", True, bool(ghost_ids(extract_ids(ghost), entries))),
        ("反例②级别不符判红", True, bool(ghost_ids(extract_ids(wrong_level), entries))),
        ("反例③约束词被删判红", True, not all(k in no_keywords for k in ANTI_FAB_KW)),
        ("反例④E 级混入产品件判红", True,
         bool(check_data_face([{"id": "PSY-X-001", "level": "E", "title": "t",
                                "summary": "s", "content": "c"}]))),
        ("正例③合规数据面放行", False, not check_data_face(entries)),
        # r172：超长口径两腿。判定面 = check_data_face（K7 长度判据）
        ("正例④超长但句首有免责短语放行（r167-KB11b 有意超出）", False,
         not check_data_face([{"id": "PSY-ZZ-002", "level": "C", "title": "t", "summary": "s",
                               "content": starts_with_boundary_probe_ok()}])),
        ("反例⑤超长且句首无免责短语判红（证明 K7 未退化成摆设）", True,
         bool(check_data_face([{"id": "PSY-ZZ-003", "level": "C", "title": "t", "summary": "s",
                                "content": ("这是研究结论，用来把整条撑过截断上限。" * 20)}]))),
    ]
    bad = [name for (name, _is_neg, ok) in legs if not ok]
    pos = sum(1 for (_n, is_neg, ok) in legs if ok and not is_neg)
    neg = sum(1 for (_n, is_neg, ok) in legs if ok and is_neg)
    if bad:
        print("KB-WIRING-SELFTEST-FAIL: %d/%d 腿不符合预期 -> %s"
              % (len(bad), len(legs), "；".join(bad)))
        return 1
    print("KB-WIRING-SELFTEST-PASS: %d 正例过 / %d 反例红（共 %d 腿，含幽灵编号与约束词被删"
          "两条反臆造腿、r172 超长口径两腿）" % (pos, neg, len(legs)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    entries = load_entries()
    if not entries:
        print("KB-WIRING-UNVERIFIED: 数据件缺失或不可解析（src/data/psych-kb.js）⇒ 先跑构建器")
        return 2
    bad, notes = [], []
    face = check_data_face(entries)
    if face:
        bad += ["K7 " + f for f in face[:8]]
    else:
        over = [e["id"] for e in entries
                if len(e.get("content") or "") > CONTENT_MAX]
        notes.append("K7 数据件面 %d 条全部 A-D 级；%d 条超长但句首带免责短语"
                     "（r167-KB11b 有意超出，判据放行）、0 条无理由超长" % (len(entries), len(over)))

    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch as be_launch
    except Exception as e:
        print("KB-WIRING-UNVERIFIED: 浏览器环境不可达: %s" % e)
        return 2

    try:
        with sync_playwright() as p:
            b, engine = be_launch(p, label="kb-wiring")
            pg = b.new_page(viewport={"width": 1200, "height": 860})
            pg.add_init_script(
                "try{localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                "{proxy:'%s/api/chat',stream:false}))}catch(e){}" % args.base)
            try:
                pg.goto(args.base + "/index.html", wait_until="load", timeout=45000)
            except Exception as e:
                print("KB-WIRING-UNVERIFIED: 页面打不开 %s（服务没起？）: %s" % (args.base, type(e).__name__))
                b.close()
                return 2
            pg.wait_for_timeout(1200)
            pg.evaluate("localStorage.removeItem('peiliao.history.v1');"
                        "localStorage.removeItem('peiliao.emotions.v1'); 1")
            cap = {"list": [], "err": []}
            pg.on("pageerror", lambda e: cap["err"].append(str(e)[:80]))

            def handler(route):
                cap["list"].append(route.request.post_data)
                route.fulfill(status=200, content_type="application/json", body=REPLY_BODY)

            pg.route("**/api/chat*", handler)

            def send(text, want=1, wait_ms=800):
                cap["list"] = []
                pg.fill("#chat-input", text)
                pg.press("#chat-input", "Enter")
                for _ in range(60):
                    if len(cap["list"]) >= want:
                        break
                    pg.wait_for_timeout(150)
                pg.wait_for_timeout(wait_ms)
                return list(cap["list"])

            # K1/K2/K6：求解释轮
            sys_k = parse_systems(send(CURIOUS_TEXT, want=2))
            reply = [s for s in sys_k if KB_MARK in s]
            if not reply:
                bad.append("K1 求解释轮（含「为什么/原理」）system 里没有知识条目块（注入链断或触发判据失效）")
            else:
                blk = reply[-1]
                ids = extract_ids(blk)
                if not ids:
                    bad.append("K1 有块但零条 [PSY-…] 编号")
                notes.append("K1 求解释轮注入 %d 条：%s" % (len(ids), "、".join(i for i, _ in ids)))
                gh = ghost_ids(ids, entries)
                if gh:
                    bad.append("K2 注入面给出数据件里查不到的编号 %s（模型据此标注即为编造引用）" % gh)
                missing_kw = [k for k in ANTI_FAB_KW if k not in blk]
                if missing_kw:
                    bad.append("K6 反臆造约束词缺失 %s（提示词层的「不许编造文献/数据」钉子被拔掉）" % missing_kw)
            over = [len(s) for s in sys_k if len(s) > SYSTEM_BUDGET]
            if over:
                bad.append("K5 system 超 %d 字符：%s" % (SYSTEM_BUDGET, over))

            # K3：纯倾诉轮不注入
            sys_p = parse_systems(send(PLAIN_TEXT, want=2))
            if any(KB_MARK in s for s in sys_p):
                bad.append("K3 纯倾诉轮注入了知识块（共情回复会说教化）")
            else:
                notes.append("K3 纯倾诉轮零注入")

            # K4：危机轮短路
            sys_c = parse_systems(send(CRISIS_TEXT, want=1))
            if sys_c:
                bad.append("K4 危机轮发出了 %d 发 API 请求（词典危机短路应不调模型）" % len(sys_c))
            crisis_ui = pg.evaluate("document.body.innerText") or ""
            if not re.search(r"热线|希望 24|心理援助|400-161-9995|12356", crisis_ui):
                bad.append("K4 危机轮界面没有求助热线文案")
            else:
                notes.append("K4 危机轮零请求 + 热线在位")

            if cap["err"]:
                bad.append("页面报错 %s" % cap["err"][:3])
            b.close()
    except Exception as e:
        print("KB-WIRING-UNVERIFIED: 浏览器腿未跑通: %s: %s" % (type(e).__name__, str(e)[:120]))
        return 2

    for n in notes:
        print("  · " + n)
    if bad:
        for s in bad:
            print("  🔴 " + s)
        print("KB-WIRING-FAIL: %d 项判红（引擎=%s，数据件 %d 条）" % (len(bad), engine, len(entries)))
        return 1
    print("KB-WIRING-PASS: K1-K7 全过（数据件 %d 条｜引擎=%s｜求解释轮有依据/倾诉轮不注入/危机轮零请求）"
          % (len(entries), engine))
    return 0


if __name__ == "__main__":
    sys.exit(main())
