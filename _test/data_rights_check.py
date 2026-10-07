# -*- coding: utf-8 -*-
"""对标 r44 常驻判据：**数据主体权利三件事**（知情披露 / 可核验删除 / 可携导出）。

为什么开这一面：心屿存的是**情绪记录 + 原话对话**，按个保法口径属敏感个人信息，
而此前九份对标报告从未量过"用户能不能知道自己的数据在哪、能不能带走、删了有没有回执"
（✅ 实测 `grep -l 导出|可携|删除权|留存 交付物/对标分析报告-*.md` 在 r44 前 = 0 命中）。

本轮实测出的两处真缺陷（都不是推测）：
  1. 第四幕写死「所有对话情绪…**不上传**、可一键清除」，而本地/fat jar 演示层
     `src/js/demo-config.js` 置的是 `remote: true` ⇒ 数据确实进了服务端 H2 库。
     **披露语与运行模式不符** = 对用户说了一句只在最乐观那一档才成立的话。
  2. `MemoryStore.clear()` 里 DELETE 是 fire-and-forget：服务端回了 `{"ok":true,"removed":N}`，
     **N 被整个丢掉**，UI 在请求未回来时就印「星星已熄灭」⇒"帮你删干净了"没有回执支撑。

判据 D1–D4：
  D1 披露语必须随模式翻转（双向：开远端要出现"服务端"且不得出现"不上传"；关远端反之）
  D2 删除必须**当场核验归零**：先写数据 → /stats 计数>0 → 点按钮 → 回执文案含"复核为 0" → 再读 /stats 必须双 0
  D3 导出必须真含服务端 + 本机两份记录，且条数与 /stats 对得上
  D4 按钮必须在可访问性树里可达且有类型（防"加了功能忘了进壳/忘了 type"）

前置：fat jar 起在 8123（remote 演示配置）。用法：python _test/data_rights_check.py [--selftest]
退出码：0=全绿 1=判红 2=环境未验（服务不可达 / 浏览器起不来）
"""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from settle_wait import wait_quiescent, same_reading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.environ.get("XINYU_BASE", "http://127.0.0.1:8123")
PAGE = BASE + "/index.html"
API = BASE + "/api/memory"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))
    print("  %-4s %-38s %s" % ("PASS" if ok else "FAIL", name, detail)[:200])


def unverified(name, why):
    results.append((name, None, why))
    print("  UNV  %-38s %s" % (name, why)[:200])


def disclosure_ok(text, remote):
    """纯函数：披露语与模式是否一致。remote=True 必须讲清"会进服务端"，False 才准说"不上传"。"""
    t = text or ""
    if remote:
        return ("服务端" in t) and ("不上传" not in t)
    return ("只留在本机" in t or "不上传" in t)


def receipt_line(r):
    """纯函数：清除回执文案的拼装规则（与 app.js 同口径，判据靠它双向验）。"""
    bits = ["本机已清除" if r.get("local") else "本机清除失败"]
    if r.get("removed") is None and not r.get("error"):
        bits.append("未连服务端（无需服务端清除）")
    elif r.get("verified") is True:
        bits.append("服务端已删 %s 条，复核为 0" % r.get("removed"))
    elif r.get("verified") is False:
        bits.append("服务端复核未归零：%s" % r.get("error"))
    else:
        bits.append("服务端清除失败：%s" % (r.get("error") or "无回执"))
    return " ｜ ".join(bits)


from browser_engine import launch as be_launch, short_face   # r98 E2 迁移：唯一实现见 browser_engine.py


def stats(sid):
    import urllib.request
    with urllib.request.urlopen(API + "/stats?sessionId=" + urllib.parse.quote(sid), timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("DATA-RIGHTS-ENV-UNVERIFIED playwright 不可用 %s" % e)
        return 2
    import urllib.parse  # noqa: F401
    try:
        s0 = stats("r44-probe")
    except Exception as e:
        print("DATA-RIGHTS-ENV-UNVERIFIED 服务不可达 %s（%s）" % (API, str(e)[:90]))
        return 2

    with sync_playwright() as pw:
        try:
            b, face = be_launch(pw, label="data_rights_check")
        except Exception as e:                                # noqa: BLE001
            print("DATA-RIGHTS-ENV-UNVERIFIED 浏览器起不来（三档全败）%s"
                  % (str(e).splitlines()[0][:90] if str(e) else type(e).__name__))
            return 2
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        # 开远端演示模式，并固定 sessionId 便于读服务端
        pg.add_init_script("localStorage.setItem('peiliao.cfg.v1', JSON.stringify("
                           "{base:'%s/v1',key:'demo',model:'demo',remote:true}));"
                           "localStorage.setItem('peiliao.session.v1','r44-probe');" % BASE)
        try:
            pg.goto(PAGE, wait_until="networkidle")
            # r99：披露语是前端按 cfg 渲染的，等它「渲染出来」（非空）而不是等 700ms。
            # 等的是有没有，断言的是讲的是不是去向（disclosure_ok）——不是同一个数，
            # 所以不构成「等自己要证的数」（settle_wait 那条约束）。
            pg.wait_for_function("() => { const d = document.querySelector('#data-disclosure');"
                                 " return !!d && d.textContent.trim().length > 0; }", timeout=8000)
            # D1 正向：remote=true
            txt = pg.locator("#data-disclosure").inner_text()
            check("D1a 开远端时披露语讲清去向", disclosure_ok(txt, True), txt[:78])
            # D2 先造数据
            base0 = stats("r44-probe")   # 动作**之前**的起账：静止判定要拿它当基线（见 settle_wait 文档）
            pg.fill("#chat-input", "今天被导师批评了，我很难受")
            pg.click("button[type=submit]")
            pg.wait_for_function("() => document.querySelectorAll('#chat-log .msg').length >= 2",
                                 timeout=30000)
            # 旧写法是 `wait_for_timeout(1500)` 后立刻 stats() —— CI run 37299161773 因此拿到
            # `server.messages 实得 2 / 期望 1`：快照与导出取自**两个不同时刻**，比的不是同一个状态。
            # 改法与同轮 `j4_memory` 一致：先等"变化后静止"，再取这对必须同刻的读数（唯一实现 settle_wait.py）。
            settled, last_q = wait_quiescent(lambda: stats("r44-probe"), budget_s=20.0, baseline=base0)
            if not settled:
                unverified("D2a/D3 服务端写入静止", "20s 内计数毫无变化，末次读数=%s" % (last_q,))
            st1 = stats("r44-probe")
            check("D2a 写入后服务端确有记录", st1["emotions"] > 0 and st1["messages"] > 0, str(st1))
            # D3 导出（在删除之前）
            bundle = pg.evaluate("() => window.MemoryStore.exportAll()")
            st2 = stats("r44-probe")   # 导出之后再取一次：两次不同 ⇒ 这一对读数不可比，记未验而非判产品红
            srv = (bundle.get("source") or {}).get("server") or {}
            n_local = len((bundle.get("source") or {}).get("local") or [])
            if same_reading(st1, st2, keys=("emotions", "messages")):
                check("D3 导出含服务端与本机两份且与计数对齐",
                      len(srv.get("emotions") or []) == st1["emotions"]
                      and len(srv.get("messages") or []) == st1["messages"] and n_local > 0,
                      "server.emotions=%s/%s messages=%s/%s local=%s mode=%s（快照同刻：是）"
                      % (len(srv.get("emotions") or []), st1["emotions"],
                         len(srv.get("messages") or []), st1["messages"], n_local, bundle.get("mode")))
            else:
                # 快照与导出之间服务端又动了 ⇒ 这一对数本来就不可比；判产品红是冤枉，判绿是自欺
                unverified("D3 导出⇄快照同刻性",
                           "取数期间服务端状态漂移 %s→%s ⇒ 本轮 D3 不作数" % (st1, st2))
            check("D4 导出/清除按钮均存在且 type=button",
                  pg.evaluate("() => ['btn-clear','btn-export'].every(i => {"
                              "const e=document.getElementById(i);"
                              "return !!e && e.getAttribute('type')==='button'})"))
            # D2 删除 + 回执 + 复核
            # 本页是滚动驱动叙事：第四幕的卡片按 SCROLL_FADE 规则淡入淡出，
            # 不先滚到它就直接点会卡在 actionability 上（实测 Page.click Timeout）
            pg.locator("#btn-clear").scroll_into_view_if_needed()
            pg.wait_for_timeout(600)
            pg.locator("#btn-clear").click(timeout=15000)
            pg.wait_for_function("() => { const e=document.getElementById('chart-receipt');"
                                 "return /复核|失败|未连服务端/.test(e.textContent); }", timeout=20000)
            rcpt = pg.locator("#chart-receipt").inner_text()
            check("D2b 清除回执写明服务端删了几条并复核", "复核为 0" in rcpt and "服务端已删" in rcpt,
                  rcpt[:88])
            st2 = stats("r44-probe")
            check("D2c 服务端复核双归零（独立于 UI 的第二条通道）",
                  st2["emotions"] == 0 and st2["messages"] == 0, str(st2))
            # D1 反向：**另开一个不带 remote 预置的上下文**再进页面。
            # 不能用 reload + 覆写 localStorage：add_init_script 每次导航都会重跑，
            # 会把刚设的 cfg 冲回 remote:true ⇒ 测不到反向那一腿（r44 实测踩中）。
            ctx2 = b.new_context(viewport={"width": 1280, "height": 900})
            ctx2.add_init_script("localStorage.setItem('peiliao.cfg.v1', JSON.stringify("
                                 "{base:'%s/v1',key:'demo',model:'demo'}));"
                                 "localStorage.setItem('peiliao.session.v1','r44-local');" % BASE)
            pg2 = ctx2.new_page()
            pg2.goto(PAGE, wait_until="networkidle")
            pg2.wait_for_function("() => { const d = document.querySelector('#data-disclosure');"
                                  " return !!d && d.textContent.trim().length > 0; }", timeout=8000)
            txt2 = pg2.locator("#data-disclosure").inner_text()
            ctx2.close()
            check("D1b 关远端时披露语翻回不留服务端", disclosure_ok(txt2, False), txt2[:78])
            check("全程无 pageerror", not errs, str(errs[:2])[:120])
        except Exception as e:
            msg = str(e)
            if "ERR_CONNECTION" in msg or "net::ERR_" in msg:
                print("DATA-RIGHTS-ENV-UNVERIFIED 服务/页面不可达 %s" % msg[:110])
                b.close()
                return 2
            unverified("D1-D4 运行通道", msg[:110])
        b.close()

    bad = [n for n, ok, d in results if ok is False]
    unv = [n for n, ok, d in results if ok is None]
    print("=" * 74)
    # rc 口径与本件头注一致：0=全绿 1=判红 2=未验。
    # 一手（r96）：原来写成 `if bad or unv: … return 1`，于是"判红=（空）未验=X"也回 1 ——
    # 把没验过的面折算成判红，既污染红因归因，又让 CI 的 rc=1 名单里混进根本不是红的项。
    if bad:
        print("DATA-RIGHTS-FAIL 判红=%s 未验=%s" % (",".join(bad), ",".join(unv)))
        return 1
    if unv:
        print("DATA-RIGHTS-UNVERIFIED 判红= 未验=%s（不得据其声称已验）" % ",".join(unv))
        return 2
    print("DATA-RIGHTS-PASS 引擎=%s 披露随模式翻转+删除有回执并复核归零+导出含两份且与计数对齐 全绿"
          % short_face(face))
    return 0


def selftest():
    """两个纯函数的双向桩：漏报侧必须命中，误报侧必须不命中。"""
    ok, fail, n = 0, [], 0

    def want(cond, note):
        nonlocal n, ok
        n += 1
        if cond:
            ok += 1
        else:
            fail.append(note)

    want(disclosure_ok("情绪与对话会同步到本演示实例的服务端", True), "正例①开远端披露语")
    want(not disclosure_ok("所有情绪只留在本机浏览器（不上传）", True),
         "反例①开远端却写不上传，必须判不一致")
    want(disclosure_ok("所有情绪只留在本机浏览器（不上传）", False), "正例②关远端")
    want(not disclosure_ok("会同步到服务端数据库", False), "反例②关远端却写进服务端")
    want("复核为 0" in receipt_line({"local": True, "removed": 7, "verified": True}),
         "回执正例：删 7 条并复核")
    want("失败" in receipt_line({"local": True, "removed": None, "verified": None,
                                 "error": "HTTP 500"}), "回执反例③：服务端报错必须显影")
    want("复核未归零" in receipt_line({"local": True, "removed": 3, "verified": False,
                                        "error": "emotions=3"}), "回执反例④：没归零不得说成功")
    want("未连服务端" in receipt_line({"local": True, "removed": None, "verified": None}),
         "回执边界⑤：离线态不得谎称已核验")
    # 反向守卫：把 verified=True 且 removed=0 也当成成功（必须仍是"复核为 0"，不许因 0 条而消失）
    want("复核为 0" in receipt_line({"local": True, "removed": 0, "verified": True}),
         "回执边界⑥：删 0 条但已复核，文案不得缺项")
    for x in fail:
        print("  DATA-RIGHTS-SELFTEST-FAIL " + x)
    print("DATA-RIGHTS-SELFTEST: %d/%d（披露 4｜回执 5）" % (ok, n))
    return 0 if ok == n else 1


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    sys.exit(main())
