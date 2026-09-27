# -*- coding: utf-8 -*-
"""窄屏能力入口可达性判据（r48 新增）—— 盯「桌面点得到、手机整块没了」这一类静默消失

动因（一手实测，非推测）：2026-09-27 老大报「一键点亮的功能怎么没了」。
实测结论是功能代码三处全在（index.html 的按钮 / app.js 的 handler / three-scene.js 的
`lightShow()`），被 `src/css/style.css` 的 `@media(max-width:480px){#btn-lightshow{display:none}}`
整块藏掉（commit 6cae042，2026-09-24 对标轮 M6 响应式三档，行上无注释），
且 480 以下**没有任何替代入口** —— 全页只有这一处调用 `lightShow`。
而既有判据抓不到它，且是**结构上**抓不到：
  · `_test/lightshow_check.py` 视口固定 1280x800 ⇒ AC-OBS-04 一直 PASS；
  · `_test/mobile_check.py`（r47 在飞）M2 的口径是「所有**可见**交互目标 ≥44x44」，
    并且它自带一条反例断言「隐藏元素不得判（display:none 不算缺陷）」
    ⇒ 一个"从可见变不可见"的入口对它是**天然豁免**，永远不会红。
所以本判据补的是这条缝隙：能力入口的**可见性单调性** ——
基线档（1280x800）能点到的入口，任何更窄的档位都必须**仍然能点到，或有替代入口**。

取数面（分母不手抄，结构现读；承 feedback-structural-enumeration-for-counts）：
  候选入口 = `src/index.html` 里带 id 的 `<button>` **且** 该 id 以 `#id` 形态被 `src/js/*.js` 引用。
  状态门控型（设置面板内、演示态才出现的 `#btn-exit-show` 等）在基线档本就不可见 ⇒ 排除，
  但必须**点名打印**并在计数里出现，禁静默排除。
  「替代入口」按能力符号判定：从该 id 的 handler 段里取 `window.<模块>.<能力>(` 形态的能力名，
  再看是否有**别的** id 的 handler 段调用同一能力。取不到能力符号 ⇒ 记 `undetermined`，
  **保守判红**（承"取不到数不得记 PASS"）。

豁免账 `DECLARED`（承 feedback-escape-hatch-needs-meter-and-honest-first-line）：
  窄屏刻意不出现、且老大已裁定属设计内取舍的入口，逐条命名 + 缘由 + 撤账条件。
  gap 集合与本账必须**双向相等**：
    · 出现未登记的消失 ⇒ FAIL（新增的静默藏匿）
    · 登记项在当前实测里已不再消失 ⇒ FAIL（豁免账陈旧，须撤账）

rc：0=PASS 1=FAIL 2=UNVERIFIED（服务不可达/浏览器起不来/候选为空 —— 禁把"读不到"判成"违规"，
也禁把"没测到"判成"通过"）。
用法：python _test/entry_reach_check.py [--base http://127.0.0.1:8123] [--json] [--selftest]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = (1280, 800)
NARROW = [(1024, 768), (768, 1024), (480, 800), (479, 800), (390, 844), (360, 640), (320, 568)]

# 豁免账：窄屏刻意缺席、且已裁定为设计内取舍的入口。gap 集合须与本账双向相等。
DECLARED = {
    "btn-lightshow": ("老大 2026-09-27 裁定：480 档收坞标题条空间属设计内取舍，本轮样式不动。"
                      "代价=手机端「一键点亮」不可达。撤账条件=补上替代入口（收成图标或坞菜单）后删除本条"),
}

BTN_ID_RE = re.compile(r"<button[^>]*\bid=[\"']([A-Za-z0-9_-]+)[\"']")
REF_RE = re.compile(r"#([A-Za-z0-9_-]+)")
CAP_RE = re.compile(r"window\.([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def enumerate_candidates(html_text, js_texts):
    """分母：index.html 的带 id 按钮 ∩ 被 js 以 #id 引用的 id（按 DOM 出现顺序去重）"""
    in_html = []
    for m in BTN_ID_RE.finditer(html_text):
        if m.group(1) not in in_html:
            in_html.append(m.group(1))
    referenced = set()
    for text in js_texts:
        referenced.update(REF_RE.findall(text))
    return [i for i in in_html if i in referenced], in_html


def handler_segments(js_texts):
    """把每个 js 文件按 `#id` 引用切段，返回 id -> 该 id 全部引用段拼接后的文本。
    段 = 本次 `#id` 命中处到下一次命中处（或 +1200 字符）之间 —— 粗糙但确定，
    且由 --selftest 的第 ⑦ 条用合成源码直接证明匹配器本身成立（承"探针不入链但匹配器自证"口径）。"""
    seg = {}
    for text in js_texts:
        hits = list(REF_RE.finditer(text))
        for k, m in enumerate(hits):
            start = m.end()
            stop = hits[k + 1].start() if k + 1 < len(hits) else min(len(text), start + 1200)
            seg[m.group(1)] = seg.get(m.group(1), "") + text[start:stop]
    return seg


def capability_of(id_, segments):
    """该入口的能力符号（window.<模块>.<能力> 里的能力名）+ 调用同一能力的其它入口 id"""
    caps = set()
    text = segments.get(id_, "")
    for m in CAP_RE.finditer(text):
        caps.add(m.group(2))
    if not caps:
        return set(), set(), "undetermined"
    others = set()
    for other, otext in segments.items():
        if other == id_:
            continue
        for m in CAP_RE.finditer(otext):
            if m.group(2) in caps:
                others.add(other)
                break
    return caps, others, "determined"


def assess(cands, baseline_vis, narrow_invis, declared, segments):
    """纯函数判定：baseline_vis = {id: 基线档是否可见}；narrow_invis = {id: [消失的档宽降序]}"""
    state_gated = [i for i in cands if not baseline_vis.get(i, False)]
    visible = [i for i in cands if baseline_vis.get(i, False)]
    gaps, ok, undetermined = [], [], []
    for i in visible:
        widths = narrow_invis.get(i, [])
        if not widths:
            ok.append(i)
            continue
        caps, alt_ids, mode = capability_of(i, segments)
        rec = {"id": i, "at": max(widths), "caps": sorted(caps), "alt": sorted(alt_ids), "mode": mode}
        if mode == "undetermined":
            undetermined.append(rec)
        elif alt_ids:
            rec["reachable_via"] = sorted(alt_ids)
            ok.append(i)
        else:
            gaps.append(rec)
    stale = sorted(set(declared) - set(g["id"] for g in gaps))
    unregistered = [g for g in gaps if g["id"] not in declared]
    return {
        "candidates": len(cands), "visible": len(visible), "ok": len(ok),
        "gaps": gaps, "undetermined": undetermined, "stale": stale,
        "unregistered": unregistered, "declared": sorted(declared),
        "state_gated": state_gated,
    }


def verdict_line(r):
    core = ("visible=%d/%d narrow_ok=%d gap=%d undetermined=%d declared=%d stale=%d "
            "state_gated_excluded=%d[%s]") % (
        r["visible"], r["candidates"], r["ok"], len(r["gaps"]), len(r["undetermined"]),
        len(r["declared"]), len(r["stale"]), len(r["state_gated"]),
        ",".join(r["state_gated"]) or "-")
    # 恒等式在门面行里**现算**，不信任 assess 预先算好的布尔——否则篡改 ok 计数无人能抓（⑥ 首跑即被这点放过）
    if r["ok"] + len(r["gaps"]) + len(r["undetermined"]) != r["visible"]:
        return "ENTRY-REACH-FAIL 分母恒等式不成立 ok+gap+undetermined != visible " + core, 1
    if r["undetermined"]:
        names = ", ".join("%s@<=%dpx" % (g["id"], g["at"]) for g in r["undetermined"])
        return ("ENTRY-REACH-FAIL 无法证明窄屏仍有入口（能力符号取不到，保守判红）: "
                + names + " | " + core), 1
    if r["unregistered"]:
        names = ", ".join("%s@<=%dpx 无替代入口" % (g["id"], g["at"]) for g in r["unregistered"])
        return "ENTRY-REACH-FAIL 未登记的窄屏入口消失: " + names + " | " + core, 1
    if r["stale"]:
        return "ENTRY-REACH-FAIL 豁免账陈旧（实测已不再消失，须撤账）: %s | %s" % (
            ",".join(r["stale"]), core), 1
    if r["gaps"]:
        return "ENTRY-REACH-PASS 全部消失均已登记豁免: %s | %s" % (
            ", ".join("%s@<=%dpx" % (g["id"], g["at"]) for g in r["gaps"]), core), 0
    return "ENTRY-REACH-PASS 无入口消失 " + core, 0


# ---------------- 浏览器侧 ----------------

JS_READ = """() => {
  const out = {};
  for (const b of document.querySelectorAll('button[id]')) {
    const r = b.getBoundingClientRect(), cs = getComputedStyle(b);
    out[b.id] = {dis: cs.display, vis: cs.visibility,
                 w: Math.round(r.width), h: Math.round(r.height),
                 off: b.offsetParent !== null};
  }
  return out;
}"""


def is_visible(rec):
    return bool(rec) and rec["dis"] != "none" and rec["vis"] != "hidden" and rec["off"] \
        and rec["w"] >= 1 and rec["h"] >= 1


def live_measure(base):
    from playwright.sync_api import sync_playwright
    shots = {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="msedge")
        for w, h in [BASELINE] + NARROW:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(base.rstrip("/") + "/index.html", wait_until="load")
            page.wait_for_timeout(450)
            shots[(w, h)] = page.evaluate(JS_READ)
            page.close()
        browser.close()
    baseline_vis, narrow_invis = {}, {}
    for i in shots[BASELINE]:
        baseline_vis[i] = is_visible(shots[BASELINE].get(i))
    for (w, h), m in shots.items():
        if (w, h) == BASELINE:
            continue
        for i in baseline_vis:
            if baseline_vis[i] and not is_visible(m.get(i)):
                narrow_invis.setdefault(i, []).append(w)
    return baseline_vis, narrow_invis


def read_sources():
    html = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
    js = [(f, f.read_text(encoding="utf-8")) for f in sorted((ROOT / "src" / "js").glob("*.js"))]
    return html, [t for _, t in js]


# ---------------- selftest：双向自证（既防漏报也防误报，含分母自证与零输入不判绿） ----------------

def _el(**kw):
    d = {"dis": "inline-block", "vis": "visible", "off": True, "w": 87, "h": 44}
    d.update(kw)
    return d


def selftest():
    cases, fails = 0, []

    def ck(name, cond):
        nonlocal cases
        cases += 1
        if not cond:
            fails.append(name)

    seg = handler_segments(['const a = $("#btn-lightshow").addEventListener("click", () => { '
                            'window.ThreeScene.lightShow(180); }); '
                            'const b = $("#btn-x").addEventListener("click", () => { '
                            'window.ThreeScene.cancelShow(); });'])
    base = {"btn-lightshow": True, "btn-x": True, "btn-exit-show": False}
    # ① 会红：未登记的消失 + 无替代入口
    r = assess(["btn-lightshow", "btn-x", "btn-exit-show"], base,
               {"btn-lightshow": [480, 390]}, {}, seg)
    v, rc = verdict_line(r)
    ck("反例①未登记消失必判红且点名", rc == 1 and "btn-lightshow" in v and "@<=480px" in v)
    # ② 不误报：登记后同一读数转绿
    v2, rc2 = verdict_line(assess(["btn-lightshow", "btn-x", "btn-exit-show"], base,
                                  {"btn-lightshow": [480]}, {"btn-lightshow": "x"}, seg))
    ck("对照②已登记同读数转绿", rc2 == 0 and "ENTRY-REACH-PASS" in v2)
    # ③ 会红：豁免账陈旧（实测不再消失仍挂着账）
    v3, rc3 = verdict_line(assess(["btn-lightshow", "btn-x"], base, {}, {"btn-lightshow": "x"}, seg))
    ck("反例③陈旧豁免必判红", rc3 == 1 and "豁免账陈旧" in v3)
    # ④ 零输入不得记 PASS
    v4, rc4 = verdict_line(assess([], {}, {}, {}, {}))
    ck("反例④空候选不得判绿(交调用方记 UNVERIFIED)", rc4 == 0 and v4 == "ENTRY-REACH-PASS 无入口消失 " +
       ("visible=0/0 narrow_ok=0 gap=0 undetermined=0 declared=0 stale=0 state_gated_excluded=0[-]"))
    # ⑤ 状态门控型不得计入分母，但必须点名
    r5 = assess(["btn-lightshow", "btn-x", "btn-exit-show"], base, {}, {}, seg)
    ck("⑤基线不可见者进 state_gated 且不进 visible 计数",
       r5["state_gated"] == ["btn-exit-show"] and r5["visible"] == 2)
    # ⑥ 分母恒等式被人为破坏 ⇒ 判红
    broken = assess(["btn-lightshow", "btn-x"], base, {}, {}, seg)
    broken["ok"] = 5
    v6, rc6 = verdict_line(broken)
    ck("反例⑥恒等式破坏必判红", rc6 == 1 and "恒等式" in v6)
    # ⑦ 匹配器正例：同一能力被第二个入口调用 ⇒ 有替代，不判缺口
    seg7 = handler_segments(['$("#btn-lightshow").addEventListener("c", () => window.ThreeScene.lightShow(1)); '
                             '$("#btn-menu").addEventListener("c", () => window.ThreeScene.lightShow(1));'])
    caps, alt, mode = capability_of("btn-lightshow", seg7)
    ck("⑦匹配器：共享能力符号须识别出替代入口", mode == "determined" and alt == {"btn-menu"})
    r7 = verdict_line(assess(["btn-lightshow"], {"btn-lightshow": True}, {"btn-lightshow": [480]}, {}, seg7))
    ck("⑦对偶：有替代入口时不得判红", r7[1] == 0 and "ENTRY-REACH-PASS" in r7[0])
    # ⑧ 匹配器反例：无第二处调用 ⇒ 判缺口（这条同时证明⑦不是恒真）
    caps8, alt8, mode8 = capability_of("btn-lightshow", seg)
    ck("⑧匹配器：无第二处调用时 alt 必为空", mode8 == "determined" and alt8 == set())
    # ⑨ 能力符号取不到 ⇒ undetermined ⇒ 保守判红
    r9 = assess(["btn-x"], {"btn-x": True}, {"btn-x": [390]}, {}, {"btn-x": "no window call here"})
    v9, rc9 = verdict_line(r9)
    ck("反例⑨取不到能力符号不得判绿", rc9 == 1 and "undetermined" in v9 or rc9 == 1 and "能力符号" in v9)
    # ⑩ is_visible 的四个维度各自都能把入口判没（防"可见性"退化成单条件）
    ck("⑩隐藏四形态皆不可见",
       not is_visible(_el(dis="none")) and not is_visible(_el(vis="hidden"))
       and not is_visible(_el(off=False)) and not is_visible(_el(w=0, h=0)) and is_visible(_el()))
    print("ENTRY-REACH-SELFTEST cases=%d fails=%d %s" % (
        cases, len(fails), ",".join(fails) if fails else "ALL-OK"))
    if not cases:
        return 2
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    html, js = read_sources()
    cands, _ = enumerate_candidates(html, js)
    segments = handler_segments(js)
    try:
        baseline_vis, narrow_invis = live_measure(a.base)
    except Exception as e:
        print("ENTRY-REACH-UNVERIFIED 浏览器/服务不可达: %r" % (e,))
        return 2
    if not cands or not baseline_vis:
        print("ENTRY-REACH-UNVERIFIED 候选或读数为空 cands=%d dom=%d（禁把没测到记成通过）"
              % (len(cands), len(baseline_vis)))
        return 2
    missing = [i for i in cands if i not in baseline_vis]
    if missing:
        print("ENTRY-REACH-FAIL 源码有 id 但页面上找不到: %s" % ",".join(missing))
        return 1
    r = assess(cands, baseline_vis, narrow_invis, DECLARED, segments)
    line, rc = verdict_line(r)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    print(line)
    for g in r["gaps"]:
        print("- gap %s 消失于 <=%dpx 能力=%s 替代=%s" % (
            g["id"], g["at"], ",".join(g["caps"]) or "-", ",".join(g.get("reachable_via", [])) or "无"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
