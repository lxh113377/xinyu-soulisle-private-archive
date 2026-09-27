#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""持久层异常面行为判据（r60）：storage 被禁用 / 内容损坏 / 写满 / 删不掉 时，应用说不说真话。

为什么这一格此前是盲区（存在性 vs 行为，同 r51「气泡说降级」族）
------------------------------------------------------------
`src/js/memory-store.js` 对 localStorage 的每一处读写**都包了 try/catch**（实测 8 处），
47 条常驻判据里却没有任何一条**把这条异常路径走一遍**：
`grep -rn "QuotaExceeded|SecurityError" _test/*.py` → **0 命中**（2026-09-28 01:35 实测），
已有测试只做「写进去再读出来」的正向路径。于是「有 catch」长期被当成「降级是对的」——
而 catch 之后界面显示什么、计数是否还等于数据源，从来没有物证。

真实触发条件不是假想：无痕模式（Safari 直接抛 SecurityError）、企业策略禁用站点数据、
配额写满（本仓把整段对话历史写进一个 key）、以及旧版本写坏一半的 JSON。

四个出口 + 一个对照组（每条都真开浏览器）
------------------------------------------------------------
F0 对照组   不注错：必须全绿，否则说明是 harness 坏了而不是应用坏了
F1 禁用     getItem/setItem/removeItem 全抛 SecurityError
F2 损坏     所有 peiliao.* 键塞进非法 JSON
F3 写满     setItem 抛 QuotaExceededError（读仍可用）
F4 删不掉   removeItem 抛错，然后点「清空」按钮 —— 回执必须说「失败」，不得说「已清除」

每条断言四件（缺一不叫行为回执）：
A1 零未捕获异常（pageerror）；A2 应用骨架可用（#chat-dock 可见）；
A3 **界面计数 == 数据源计数**（#mem-count ⇄ MemoryStore.count()，两把尺对账，防"UI 自己编一个数"）；
A4 说一句情绪话后星雾仍点亮（lit > 0）——存储坏了不能把体验一起带走。

输入不可达 ⇒ rc=2 UNVERIFIED（不判绿也不判红）；自测见 --selftest。
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("XINYU_BASE", "http://127.0.0.1:8123")
LAUNCH_ARGS = [a for a in os.environ.get("XINYU_BROWSER_ARGS", "").split() if a]

FAULT = {
    "denied": """
      const boom = () => { throw new DOMException('denied', 'SecurityError'); };
      Storage.prototype.getItem = boom; Storage.prototype.setItem = boom;
      Storage.prototype.removeItem = boom; Storage.prototype.clear = boom;
    """,
    "corrupt": """
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k && k.indexOf('peiliao.') === 0) localStorage.setItem(k, '{"broken": [1,');
        }
      } catch (e) { window.__armError = String(e); }
    """,
    "quota": """
      const real = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k, v) {
        throw new DOMException('quota', 'QuotaExceededError');
      };
      void real;
    """,
    "remove_denied": """
      const real = Storage.prototype.removeItem;
      Storage.prototype.removeItem = function (k) {
        throw new DOMException('denied', 'SecurityError');
      };
      void real;
    """,
    "baseline": "void 0;",
}

CASES = [
    ("F0-baseline", "baseline", False),
    ("F1-denied", "denied", False),
    ("F2-corrupt", "corrupt", False),
    ("F3-quota", "quota", False),
    ("F4-remove-denied", "remove_denied", True),
]


def row_line(case, res):
    """门面行渲染单独成函数：上一版它内联在 run() 里，占位符比实参少一个 ⇒
    自测 10 腿全过而真面 `TypeError` 崩在打印上（自测覆盖纯函数、没覆盖输出面 = 又一条假绿）。"""
    return ("  · %-18s dock=%s ui=%s src=%s lit=%s errs=%d msgs=%s cons=%s write=%s 末条=「%s」%s%s"
            % (case, bool(res.get("dock")), res.get("ui_count"), res.get("src_count"),
               res.get("lit"), len(res.get("pageerrors") or []), res.get("msgs"),
               res.get("cons", 0), res.get("write"), res.get("last"),
               (" 回执=「%s」" % (res.get("receipt") or "")[:44]) if res.get("receipt") else "",
               (" 〔" + res["degraded"] + "〕") if res.get("degraded") else ""))


def diag(res):
    """稀有间歇红的自证快照：变红时必须当场说清"这句话到底走到哪一步"。"""
    return ("气泡 %s 条｜console 错 %s 条｜本机写盘 %s｜数据源 %s｜界面 %s｜末条「%s」"
            % (res.get("msgs"), res.get("cons", 0), res.get("write"),
               res.get("src_count"), res.get("ui_count"), res.get("last")))


def assess(case, res):
    """纯判定：输入一条用例的实测结果，返回违规列表。抽出来是为了让 --selftest 能喂坏读数。"""
    bad = []
    if res.get("arm_error"):
        bad.append("%s 注错脚本自身抛错：%s" % (case, res["arm_error"]))
    if res.get("harness_error"):
        bad.append("%s 取数失败（harness 侧，不是应用崩）⇒ 该条不作数、必须查: %s ｜诊断 %s"
                   % (case, res["harness_error"], diag(res)))
    if res.get("pageerrors"):
        bad.append("%s 有 %d 条未捕获异常（catch 没兜住或被绕过）: %s"
                   % (case, len(res["pageerrors"]), res["pageerrors"][0][:90]))
    if not res.get("dock"):
        bad.append("%s 应用骨架不可用（#chat-dock 不存在/不可见）" % case)
    if res.get("ui_count") is None or res.get("src_count") is None:
        bad.append("%s 计数取不到 ⇒ 该项未验，不得当通过（UI=%r 源=%r）"
                   % (case, res.get("ui_count"), res.get("src_count")))
    elif res["ui_count"] != res["src_count"]:
        bad.append("%s 界面计数 %s ≠ 数据源计数 %s（界面上报了一个没有出处的数）"
                   % (case, res["ui_count"], res["src_count"]))
    if res.get("lit") is None:
        bad.append("%s 星雾点亮读数取不到 ⇒ 未验" % case)
    elif res["lit"] <= 0:
        bad.append("%s 说了一句情绪话后星雾没点亮（lit=%s）⇒ 存储故障把体验一起带走了 ｜诊断 %s"
                   % (case, res["lit"], diag(res)))
    if case.startswith("F4"):
        rec = res.get("receipt") or ""
        if "失败" not in rec:
            bad.append("%s 清空按钮在 removeItem 抛错时没报失败，回执=「%s」" % (case, rec[:70]))
        if "已清除" in rec:
            bad.append("%s 清空失败却显示「本机已清除」（界面撒谎）：「%s」" % (case, rec[:70]))
    return bad


def settle(page, expr, budget_ms=15000, step_ms=400):
    """轮询到「被等对象自己给出的完成信号」，不再猜固定时长。

    立此函数的一手证据：首版用固定 2600ms / 1500ms 等待，**单跑 rc=0，接进电池后同一条 F4 翻红**
    （并发下服务端 DELETE→/stats 往返更慢，回执还停在「正在清除…」）。固定时长等于把判据的
    成败押在机器负载上 ⇒ 改成有界轮询；到点仍未定则由调用方记成"取数失败"，不判绿。
    """
    waited = 0
    while waited < budget_ms:
        got = page.evaluate(expr)
        if got:
            return got
        page.wait_for_timeout(step_ms)
        waited += step_ms
    return page.evaluate(expr)


def probe_case(browser, case, fault, click_clear):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    res = {"pageerrors": [], "arm_error": "", "harness_error": ""}
    page.on("pageerror", lambda e: res["pageerrors"].append(str(e)))
    page.on("console", lambda m: res.setdefault("console_errors", []).append(m.text[:90])
            if m.type == "error" else None)
    try:
        page.add_init_script(FAULT[fault])
        page.goto(BASE + "/index.html", wait_until="networkidle", timeout=45000)
        res["arm_error"] = page.evaluate("() => window.__armError || ''")
        res["dock"] = page.is_visible("#chat-dock")
        page.fill("#chat-input", "今天被导师批评了，心情很低落")
        page.click("#chat-form button[type=submit]")
        settle(page, "() => (window.MemoryStore && MemoryStore.count()) > 0")
        page.wait_for_timeout(600)          # 计数槽由 rAF/事件回写，给一拍
        res["ui_count"] = page.evaluate(
            "() => { const el = document.getElementById('mem-count');"
            " return el ? Number(el.textContent) : null; }")
        res["src_count"] = page.evaluate(
            "() => (window.MemoryStore && typeof MemoryStore.count === 'function')"
            " ? MemoryStore.count() : null")
        res["lit"] = page.evaluate(
            "() => (window.ThreeScene && ThreeScene.litInfo) ? ThreeScene.litInfo().lit : null")
        # 稀有间歇红的正解是"下次变红自带红因"：这四件都是**被等对象自己产出的证据**，
        # 不引入第二份真相 —— 气泡数（有没有走完对话）、console error 数（被谁吞了）、
        # 本机写盘能力（setItem 真能不能写）、末条气泡头（在线/离线/降级哪一种）。
        res["msgs"] = page.evaluate(
            "() => document.querySelectorAll('#chat-log .msg').length")
        res["cons"] = len(res.get("console_errors") or [])
        # 分开报两个动作：只报一个名字会把"removeItem 被注错"读成"写不进去"（首版实测即如此）
        res["write"] = page.evaluate(
            "() => { const o = {};"
            " try { localStorage.setItem('peiliao.write-probe', '1'); o.set = 'ok'; }"
            " catch (e) { o.set = String(e && e.name || e); }"
            " try { localStorage.removeItem('peiliao.write-probe'); o.rm = 'ok'; }"
            " catch (e) { o.rm = String(e && e.name || e); }"
            " return 'set=' + o.set + ' rm=' + o.rm; }")
        res["last"] = (page.evaluate(
            "() => { const m = document.querySelectorAll('#chat-log .msg');"
            " return m.length ? m[m.length - 1].innerText : ''; }") or "")[:56]
        if click_clear:
            # 这个按钮在第四幕（滚动叙事里默认还没进场）。真点击拿不到就把**触发方式**降级成
            # JS dispatch，但绝不解绑成"没测"：降级必须留痕并印出来 —— 可达性是
            # `entry_reach_check` 的地盘，本判据只管"清不掉时回执说不说真话"。
            reached = True
            try:
                page.evaluate("() => document.getElementById('btn-clear')"
                              ".scrollIntoView({block:'center'})")
                page.wait_for_timeout(700)
                page.click("#btn-clear", timeout=8000)
            except Exception as exc:
                reached = False
                res["degraded"] = "真点击未生效(%s)，改 JS dispatch" % type(exc).__name__
                page.evaluate("() => document.getElementById('btn-clear').click()")
            res["reach"] = reached
            # 完成信号 = 回执离开「正在清除…」。15s 内没离开就是**没测到**，记 harness_error，
            # 绝不允许把"还在进行中"读成"报失败了"或"报成功了"。
            res["receipt"] = settle(page, """() => {
                const el = document.getElementById('chart-count');
                const t = el ? (el.textContent || '') : '';
                return (t && t.indexOf('正在清除') !== 0) ? t : ''; }""")
            if not (res.get("receipt") or "").strip():
                res["harness_error"] = "清除回执 15s 未定（槽里仍是「正在清除…」或空）"
            res["ui_count"] = page.evaluate(
                "() => { const el = document.getElementById('mem-count');"
                " return el ? Number(el.textContent) : null; }")
            res["src_count"] = page.evaluate(
                "() => (window.MemoryStore && typeof MemoryStore.count === 'function')"
                " ? MemoryStore.count() : null")
    except Exception as exc:
        res["harness_error"] = "%s:%s" % (type(exc).__name__, str(exc)[:120])
    finally:
        ctx.close()
    return res


def server_up():
    import urllib.request
    try:
        with urllib.request.urlopen(BASE + "/api/health", timeout=6) as r:
            return r.status == 200
    except Exception:
        return False


def run() -> int:
    if not server_up():
        print("STORAGE-RESILIENCE-UNVERIFIED: %s/api/health 取不到 200 ⇒ 被测服务不在，"
              "不判绿也不判红（定版 jar 起法：java -jar server/target/soulisle-server.jar "
              "--server.port=8123）" % BASE)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print("STORAGE-RESILIENCE-UNVERIFIED: playwright 不可用（%s）" % type(exc).__name__)
        return 2
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=LAUNCH_ARGS)
        except Exception:
            browser = p.chromium.launch(channel="msedge", args=LAUNCH_ARGS)
        bad = []
        rows = []
        for case, fault, click in CASES:
            r = probe_case(browser, case, fault, click)
            rows.append((case, r))
            bad += assess(case, r)
        browser.close()
    if not rows:
        print("STORAGE-RESILIENCE-UNVERIFIED: 零用例实跑，不判绿")
        return 2
    for case, r in rows:
        print(row_line(case, r))
    for x in bad:
        print("  ✗ " + x)
    if bad:
        print("STORAGE-RESILIENCE-FAIL: %d 条违规（用例 %d 条实跑）" % (len(bad), len(rows)))
        return 1
    print("STORAGE-RESILIENCE-PASS: %d 种存储故障下均零未捕获异常、界面计数==数据源计数、"
          "星雾仍点亮、清空回执如实报失败（用例 %d 条）" % (len(CASES) - 1, len(rows)))
    return 0


BROKEN_PAGE = """<!doctype html><meta charset="utf-8"><div id="chat-dock"><b id="mem-count">3</b></div>
<script>
  // 反向腿专用：一个"没有 try/catch"的存储写入者。配额注错必须让它冒未捕获异常，
  // 否则说明注错没打到被审谓词（判据恒绿的常见成因）。
  localStorage.setItem("peiliao.emotions.v1", "[]");
  window.MemoryStore = { count: function () { return 3; } };
</script>
"""


def selftest() -> int:
    """三层：①纯函数五形（含对照组不假红）②真浏览器驱动坏页必须翻红（注错真打到对象）
    ③零输入不判绿。"""
    bad = []
    good = {"dock": True, "ui_count": 2, "src_count": 2, "lit": 5, "pageerrors": [],
            "arm_error": "", "receipt": "本机清除失败 ｜ 未连服务端（无需服务端清除）"}
    if assess("F1-denied", dict(good)):
        bad.append("①合规读数被判红（假阳性）: %s" % assess("F1-denied", dict(good)))
    forms = [
        ("②未捕获异常必须红", assess("F1-denied", dict(good, pageerrors=["SecurityError: boom"])), "未捕获异常"),
        ("③计数不一致必须红", assess("F3-quota", dict(good, ui_count=7, src_count=2)), "界面计数"),
        ("④星雾不点亮必须红", assess("F3-quota", dict(good, lit=0)), "星雾"),
        ("⑤清空谎报必须红", assess("F4-remove-denied", dict(good, receipt="本机已清除 ｜ 未连服务端")), "界面撒谎"),
        ("⑥计数取不到判未验不得当通过", assess("F2-corrupt", dict(good, ui_count=None)), "未验"),
        ("⑦注错脚本自己崩必须红", assess("F2-corrupt", dict(good, arm_error="SecurityError")), "自身抛错"),
        ("⑩取数失败必须归因到 harness，不得混进「应用未捕获异常」",
         assess("F4-remove-denied", dict(good, harness_error="TimeoutError:click")), "harness 侧"),
    ]
    for name, out, needle in forms:
        if not any(needle in x for x in out):
            bad.append("%s：实测红因里没有「%s」，实际=%s" % (name, needle, out))
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        bad.append("⑧playwright 不可用 ⇒ 端到端反例腿未验: %s" % type(exc).__name__)
        print("STORAGE-RESILIENCE-SELFTEST-FAIL: " + "; ".join(bad))
        return 1
    with tempfile.TemporaryDirectory() as td:
        p_html = Path(td) / "broken.html"
        p_html.write_text(BROKEN_PAGE, encoding="utf-8", newline="\n")
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(args=LAUNCH_ARGS)
            except Exception:
                browser = pw.chromium.launch(channel="msedge", args=LAUNCH_ARGS)
            ctx = browser.new_context()
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.add_init_script(FAULT["quota"])
            page.goto(p_html.as_uri())
            res = {"dock": page.is_visible("#chat-dock"), "ui_count": 3, "src_count": 3,
                   "lit": None, "pageerrors": errs, "arm_error": ""}
            ctx.close()
            browser.close()
        out = assess("F3-quota", res)
        if not any("未捕获异常" in x for x in out):
            bad.append("⑧坏页真崩而判据没红 ⇒ 注错没打到被审对象，这条反例是假的：%s" % out)
    full = {"dock": True, "ui_count": 1, "src_count": 1, "lit": 5, "msgs": 2, "cons": 0,
            "write": "ok", "last": "在线", "receipt": "本机清除失败", "pageerrors": []}
    try:
        line = row_line("F4-remove-denied", full)
        if "本机清除失败" not in line or "F4-remove-denied" not in line:
            bad.append("⑪行渲染内容不对（缺回执或缺用例名）: %s" % line[:90])
        sparse = row_line("F0-baseline", {})          # 空读数也不许崩：崩了就是假红
        if "F0-baseline" not in sparse:
            bad.append("⑪空读数行渲染没点用例名")
    except Exception as exc:
        bad.append("⑪行渲染抛错（自测覆盖不到输出面的代价就在这）: %s" % exc)
    zero = assess("F0-baseline", {"dock": True, "ui_count": None, "src_count": None,
                                  "lit": None, "pageerrors": []})
    if len(zero) < 2:
        bad.append("⑨零读数应当成「未验」堆红，实到 %d 条" % len(zero))
    print("STORAGE-RESILIENCE-SELFTEST-%s（11 腿：合规正例 + 六形必红 + 坏页端到端 + 零读数 + 门面行渲染）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad)))
    for x in bad:
        print("  ✗ " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(run())
