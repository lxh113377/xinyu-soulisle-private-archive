# -*- coding: utf-8 -*-
"""移动端与触屏可达性判据（r47 新增）—— 量**真实几何**，不量"有没有写 @media"。

为什么是这一面：r47 前的十份对标报告对 `响应式|移动端|触控|44px|viewport|断点` **零命中**，
而本仓确实有 viewport meta + 5 条 @media ⇒ "有没有做响应式"是个假问题；真问题是
**手指打开时点得到、看得全、不被动放大**。这三件事只有把页面渲到真视口里才量得出，
CSS 文本里 grep 是量不出来的（也正因为如此，它此前从未被量过）。

首跑实测（修前）：
  · 7 个可点控件高 **27–35px**（btn-lightshow 87x27 / btn-dock 58x28 / btn-settings 97x35 /
    btn-theme 67x35 / btn-clear 108x35 / btn-export 108x35 / btn-demo-clear x42）
    ⇒ 低于 WCAG 2.5.8「Target Size (Minimum)」的 44x44 CSS px
  · 输入框 font-size **14–15px** ⇒ iOS Safari 聚焦时自动放大整页（用户被横向推走）
  · 横向溢出在 320/360/390/768 四档均为 False（这一条本来就是好的，也如实记）

判据（M1–M5 阻断，M0 环境）：
  M1 四档视口零横向溢出（含 320 极窄）
  M2 所有**可见**交互目标 ≥44x44 CSS px（触屏态；口径同 WCAG 2.5.8，间隔豁免未做，从严）
  M3 文本类输入控件 font-size ≥16px
  M4 viewport meta：必须有 width=device-width，且禁 user-scalable=no / maximum-scale<2
     （禁禁缩放属可访问性红线，与 r42 的 a11y 面同源但不同判据）
  M5 打开对话坞与设置面板后**复检** M2/M3（否则藏在折叠面板里的缺陷会漏判 —— 首版就漏了
     `set-provider` 的 14px，因为它在默认关闭的设置面板里）
  M0 服务不可达/浏览器起不来 ⇒ rc=2 UNVERIFIED，禁把"读不到"判成"违规"

⚠️ 关键实现事实：`(pointer: coarse)` **只在 has_touch=True 的上下文里匹配**。
探针首版没开触摸仿真 ⇒ 修完 CSS 数字一动不动，差点误判成"改错了"。
所以本判据必须 `has_touch=True`，且 selftest 的反例注入走纯函数不打浏览器。
用法：python _test/mobile_check.py [--base http://127.0.0.1:8123] [--json] [--selftest]
退出码：0=全过 1=判红 2=环境未验证
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(320, 568), (360, 640), (390, 844), (768, 1024)]
# 双层口径（首版把标准引错了，被真跑打回来才改对）：
#   · 24px = WCAG 2.5.8 Target Size (Minimum) 的 **AA 硬底线**，低于即红，无争议；
#   · 44px = iOS HIG 44pt / Material 48dp 的**平台建议**（WCAG 里对应 2.5.5 AAA，非 AA），
#     本仓是"评委用手机打开"的触屏优先场景，故把 44 设为**独占型控件**的红线。
#   · checkbox/radio 在 <label> 内时按"等效控件"豁免 44（真正可点的是整行 label），
#     但仍要求 label 自身 ≥24，且豁免数打印在 PASS 行里 —— 豁免要可见，不能静默。
MIN_TARGET = 44          # 独占型可点目标的红线（平台建议，本仓自选并钉住）
AA_FLOOR = 24            # WCAG 2.5.8 AA 硬底线：任何可见交互目标都不得低于
MIN_INPUT_FONT = 16      # iOS Safari 聚焦自动放大的阈值
TEXTY = re.compile(r"^(INPUT|SELECT|TEXTAREA)$", re.I)
SOLE = re.compile(r"^(BUTTON|A|SELECT|TEXTAREA)$|^(INPUT|TEXTAREA)$", re.I)

JS_PROBE = """() => {
  const de = document.documentElement;
  const pick = 'button,input,select,textarea,a[role=button],[role=button]';
  const els = [...document.querySelectorAll(pick)].map(e => {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    const lb = e.closest('label');
    const lr = lb ? lb.getBoundingClientRect() : {width: 0, height: 0};
    return {id: e.id || '', tag: e.tagName.toUpperCase(), type: (e.type || ''),
            w: Math.round(r.width), h: Math.round(r.height),
            fs: parseFloat(cs.fontSize) || 0, dis: cs.display, vis: cs.visibility,
            off: e.offsetParent !== null,
            inLabel: !!lb, lw: Math.round(lr.width), lh: Math.round(lr.height)};
  });
  return {sw: de.scrollWidth, cw: de.clientWidth, iw: window.innerWidth, els};
}"""


def assess(readings, meta_text):
    """纯函数：输入 = [(w,h,{sw,cw,iw,els})] 读数 + index.html 的 viewport meta 原文。

    selftest 直接打它，不依赖浏览器与本机服务。
    返回 (问题清单, 统计 dict)。
    """
    bad, stats = [], {}
    if not readings:
        return ["M0 零视口读数 ⇒ 分母为空，不判绿"], {"note": "empty"}
    tiny_all, overflow_at, exempt = [], [], []
    n_targets = 0
    for (vw, vh, d) in readings:
        if not d or d.get("cw") is None:
            bad.append("M0 %dx%d 读数取不到（服务未起或页面崩）" % (vw, vh))
            continue
        if d["sw"] > d["cw"] + 1:
            overflow_at.append("%dx%d(%d>%d)" % (vw, vh, d["sw"], d["cw"]))
        vis = [e for e in d["els"] if e["off"] and e["dis"] != "none" and e["vis"] != "hidden"
               and e["w"] > 0 and e["h"] > 0]
        n_targets += len(vis)
        for e in vis:
            ident = "%dx%d:%s%s" % (vw, vh, e["tag"], ("#" + e["id"]) if e["id"] else "")
            # 等效控件豁免：checkbox/radio 藏在 <label> 里时，真正可点的是整行 label
            if e["tag"] == "INPUT" and e["type"] in ("checkbox", "radio") and e["inLabel"]:
                if e.get("lw", 0) < AA_FLOOR or e.get("lh", 0) < AA_FLOOR:
                    tiny_all.append("%s(label %dx%d<%d 等效控件也不成立)"
                                    % (ident, e.get("lw", 0), e.get("lh", 0), AA_FLOOR))
                else:
                    exempt.append(ident)
                continue
            if e["w"] < AA_FLOOR or e["h"] < AA_FLOOR:
                tiny_all.append("%s %dx%d<%d(AA 2.5.8 底线)" % (ident, e["w"], e["h"], AA_FLOOR))
            elif e["w"] < MIN_TARGET or e["h"] < MIN_TARGET:
                tiny_all.append("%s %dx%d<%d(本仓触屏红线)" % (ident, e["w"], e["h"], MIN_TARGET))
            if TEXTY.match(e["tag"]) and e["type"] not in ("checkbox", "radio", "button",
                                                          "submit", "range", "hidden") \
                    and e["fs"] < MIN_INPUT_FONT:
                tiny_all.append("%s FONT=%.0fpx<%d(iOS 聚焦会放大整页)"
                                % (ident, e["fs"], MIN_INPUT_FONT))
    if overflow_at:
        bad.append("M1 横向溢出 %d 处 %s" % (len(overflow_at), overflow_at[:4]))
    if tiny_all:
        bad.append("M2/M3 触屏不达标 %d 条（去重后 %d 类）：%s"
                   % (len(tiny_all), len(set(tiny_all)), "; ".join(sorted(set(tiny_all))[:8])))
    stats = {"viewports": len(readings), "targets_seen": n_targets,
             "issues": len(tiny_all), "overflow": len(overflow_at), "exempt": len(set(exempt))}
    m = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*>', meta_text or "", re.I)
    if not m:
        bad.append("M4 缺 viewport meta")
    else:
        c = m.group(0)
        if "width=device-width" not in c:
            bad.append("M4 viewport 缺 width=device-width")
        if re.search(r"user-scalable\s*=\s*no", c, re.I):
            bad.append("M4 viewport 禁缩放（user-scalable=no）—— 低视力用户无法放大")
        mm = re.search(r"maximum-scale\s*=\s*([\d.]+)", c, re.I)
        if mm and float(mm.group(1)) < 2:
            bad.append("M4 viewport maximum-scale=%s 实质禁缩放" % mm.group(1))
    return bad, stats


# ---------------- selftest：正例 + 反例 + 边界（不打开浏览器） ----------------
def _el(tag="BUTTON", id="", w=60, h=48, fs=14, t="", off=True, in_label=False, lw=0, lh=0):
    return {"id": id, "tag": tag, "type": t, "w": w, "h": h, "fs": fs,
            "dis": "inline-block", "vis": "visible", "off": off,
            "inLabel": in_label, "lw": lw, "lh": lh}


def _ck(id="c", w=16, h=16, fs=16, lw=220, lh=44):
    """label 内的 checkbox：控件本身小，等效可点目标是整行 label。"""
    return _el("INPUT", id, w, h, fs, "checkbox", in_label=True, lw=lw, lh=lh)


def selftest():
    ok, fail = 0, []
    good = [(360, 640, {"sw": 360, "cw": 360, "iw": 360,
                        "els": [_el(id="btn-a", w=88, h=44),
                                _el("INPUT", "chat-input", 220, 46, 16, "text"),
                                _ck("set-stream", 16, 16)]}),
            (768, 1024, {"sw": 768, "cw": 768, "iw": 768, "els": [_el(id="btn-b", w=60, h=44)]})]
    meta = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    cases = [
        ("正例：全达标", good, meta, False),
        ("反例①：控件高 35px（首跑实测形状）",
         [(360, 640, dict(good[0][2], els=[_el(id="btn-settings", w=97, h=35)]))], meta, True),
        ("反例②：输入框 15px（iOS 放大）",
         [(360, 640, dict(good[0][2], els=[_el("INPUT", "chat-input", 220, 46, 15, "text")]))], meta, True),
        ("反例③：横向溢出",
         [(320, 568, {"sw": 412, "cw": 320, "iw": 320, "els": [_el(id="x", w=60, h=48)]})], meta, True),
        ("反例④：viewport 禁缩放",
         good, '<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">', True),
        ("反例⑤：maximum-scale=1",
         good, '<meta name="viewport" content="width=device-width,maximum-scale=1">', True),
        ("反例⑥：缺 viewport", good, "<head></head>", True),
        ("反例⑦：隐藏元素不得判（display:none 不算缺陷）",
         [(360, 640, dict(good[0][2], els=[dict(_el(id="hidden", w=10, h=10), dis="none")]))], meta, False),
        ("反例⑧：label 内 checkbox 按等效控件豁免（真跑首版误判它的形状）",
         [(360, 640, dict(good[0][2], els=[_ck("set-stream", 13, 13)]))], meta, False),
        # 豁免不能变成免死金牌：label 自己也小的时候，等效控件不成立
        ("反例⑨：label 行本身只有 20px ⇒ 等效控件不成立",
         [(360, 640, dict(good[0][2], els=[_ck("c2", 13, 13, lw=200, lh=20)]))], meta, True),
        ("反例⑩：裸 checkbox 13px（无 label）低于 AA 24 底线",
         [(360, 640, dict(good[0][2], els=[_el("INPUT", "c3", 13, 13, 16, "checkbox")]))], meta, True),
        ("反例⑪：控件 30px 高于 AA 但破本仓 44 触屏红线",
         [(360, 640, dict(good[0][2], els=[_el(id="btn-x", w=80, h=30)]))], meta, True),
    ]
    for name, rows, mt, want in cases:
        bad, _s = assess(rows, mt)
        got = bool(bad)
        if got == want:
            ok += 1
        else:
            fail.append("%s want_bad=%s got=%s bad=%s" % (name, want, got, bad))
    # 边界 A：零读数不得判绿（防"没测到 = 全过"）
    bad, _s = assess([], meta)
    if bad and "M0" in bad[0]:
        ok += 1
    else:
        fail.append("边界A 零读数未走 M0：%s" % bad)
    # 边界 B：取不到尺寸（cw=None）必须报环境未验，不得算通过
    bad, _s = assess([(360, 640, {})], meta)
    if bad and any("M0" in x for x in bad):
        ok += 1
    else:
        fail.append("边界B 空读数未报环境：%s" % bad)
    total = len(cases) + 2
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("MOBILE-SELFTEST: %d/%d" % (ok, total))
    return 0 if ok == total else 1


def probe(base):
    from playwright.sync_api import sync_playwright

    def launch(pw):
        try:
            return pw.chromium.launch()
        except Exception:
            return pw.chromium.launch(channel="msedge")

    html = (ROOT / "src" / "index.html").read_text("utf-8", errors="replace")
    rows, errs = [], []
    with sync_playwright() as p:
        b = launch(p)
        for (w, h) in VIEWPORTS:
            # has_touch=True 是**必须**的：(pointer:coarse) 只在触屏上下文匹配，
            # 不开就等于永远量不到那段 CSS（首版在此空跑一轮，误以为改动无效）
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2,
                            has_touch=True)
            pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
            try:
                pg.goto(base + "/", wait_until="load", timeout=40000)
                pg.wait_for_timeout(1200)
                rows.append((w, h, pg.evaluate(JS_PROBE)))
                # M5：把折叠面打开复检（默认隐藏的缺陷只有打开才看得见）
                for opener in ("#btn-settings", "#btn-dock"):
                    try:
                        if pg.query_selector(opener):
                            pg.click(opener)
                            pg.wait_for_timeout(450)
                            d2 = pg.evaluate(JS_PROBE)
                            rows.append((w, h, {"sw": d2["sw"], "cw": d2["cw"], "iw": d2["iw"],
                                                "els": d2["els"]}))
                    except Exception:
                        pass
            except Exception as e:
                rows.append((w, h, {}))
                errs.append("goto %dx%d: %s" % (w, h, str(e)[:100]))
            finally:
                pg.close()
        b.close()
    return rows, html, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    try:
        rows, html, errs = probe(a.base)
    except Exception as e:
        print("MOBILE-ENV-ERROR: 浏览器不可用 %s ⇒ 不判绿" % str(e)[:120])
        return 2
    bad, st = assess(rows, html)
    if not any(x.startswith("M0") for x in bad) and errs:
        st["page_errors"] = len(errs)
    if a.json:
        print(json.dumps({"stats": st, "problems": bad, "errs": errs[:5]}, ensure_ascii=False))
    for x in bad:
        print("  · FAIL " + x)
    if any("M0" in x and "读数取不到" in x for x in bad) or (not rows):
        print("MOBILE-UNVERIFIED: 服务/页面不可达 ⇒ 不算通过（%s）" % (errs[:1] or "无读数"))
        return 2
    if bad:
        print("MOBILE-FAIL: %d 项（视口 %d 档 目标 %d 个）" % (len(bad), st["viewports"],
                                                            st["targets_seen"]))
        return 1
    print("MOBILE-PASS: 读数 %d 组（%d 视口 x 默认/展开两态）零横向溢出｜交互目标 %d 个：独占型全部 ≥%dpx、"
          "等效控件豁免 %d 个（label ≥%dpx 才成立，计数不静默）｜文本输入 ≥%dpx｜viewport 允许缩放"
          % (st["viewports"], len(VIEWPORTS), st["targets_seen"], MIN_TARGET,
             st["exempt"], AA_FLOOR, MIN_INPUT_FONT))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
