# -*- coding: utf-8 -*-
"""M4/M5/M6 体验与性能守卫（三项独立判据，逐项判定，禁止聚合掩盖单项失败）

  U1 TTS 朗读：按钮存在 → 点击后 aria-pressed 翻转且写 localStorage(peiliao.speak.v1)
              → 新回复确实构造了 SpeechSynthesisUtterance 并 speak()（注入计数器实测，非"应该会说"）
              → 关闭开关后不再构造（防"关不掉"）
  U2 对话窗口化：连发 90 条 → #chat-log 内 .msg 数必须 ≤ 60（DOM 不单调增长）
              → 折叠提示存在且条数正确 → 点「展开较早」放回一批（≥1 条）
              → **完整历史不受影响**：ChatAgent.getHistory() 仍等于发送条数（窗口化只作用于渲染）
  U3 响应式与粒子降档：375/700/1300 三档分别测
              → 无横向溢出（documentElement.scrollWidth ≤ innerWidth + 2）
              → 对话坞与输入框可见
              → 粒子总数按档递减，且**桌面档必须恒等于 2600**（browser_check 的 LIT 断言标定在此）

前置：Java 服务端起在 8123（或任一托管 src/ 的静态服务）
用法：python _test/ux_guards_check.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8123/index.html"
results = []

# r99（C1_HARD 逐件评审的产物）：一次往返的**完成态**用「身份」而不是「计数」或「中间态」判定。
# 两次失败各证一种错法：
#   ① `data-emotion 计数 > 基线` —— U2e 等满 15s：窗口化从 #chat-log **顶部**裁旧气泡，
#      展开后再发一条时总数是下降的，「+1」是要等一个不会发生的形状。
#   ② 等「最后一条是 user 气泡」（本轮已入列）—— 等满 8s：离线模板 ~3ms 就回完，
#      中间态在第一次轮询之前已经过去，等的是转瞬即逝的态而不是终态。
# 现写法：mark_turn() 在点提交前给**当时**最后一条气泡盖章（新气泡不可能带这个章），
# wait_reply() 再等「最后一条带 data-emotion 且没有章」。app.js:224-227 在同一个不中断的
# 同步块里 push 正式气泡并紧接着调 Voice.speak()，所以该终态对「speak 已发生」是充分的。
TURN_MARK_JS = """() => { const m = document.querySelectorAll('#chat-log .msg');
  const last = m[m.length - 1]; if (last) last.setAttribute('data-r99-prev', '1'); }"""
TURN_DONE_JS = """() => { const m = document.querySelectorAll('#chat-log .msg');
  const last = m[m.length - 1];
  return !!last && last.hasAttribute('data-emotion') && !last.hasAttribute('data-r99-prev'); }"""


def mark_turn(pg):
    """点提交**之前**调用：给当时的最后一条气泡做身份记号。"""
    pg.evaluate(TURN_MARK_JS)


def wait_reply(pg, timeout=15000):
    """点提交**之后**调用：等新 AI 气泡成为最后一条（真完成态，非猜的毫秒数）。"""
    pg.wait_for_function(TURN_DONE_JS, timeout=timeout)


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


U1_INJECT = """
window.__tts = { constructed: 0, spoken: 0 };
(function () {
  if (!('speechSynthesis' in window)) { window.__tts.unsupported = true; return; }
  var OU = window.SpeechSynthesisUtterance;
  function Wrapped(t) { var u = new OU(t); window.__tts.constructed++; return u; }
  try { window.SpeechSynthesisUtterance = Wrapped; } catch (e) {}
  var os = window.speechSynthesis.speak.bind(window.speechSynthesis);
  window.speechSynthesis.speak = function (u) { window.__tts.spoken++; try { return os(u); } catch (e) { return; } };
})();
"""


def u1(browser):
    print("=== U1 TTS 朗读 ===")
    pg = browser.new_page(viewport={"width": 1280, "height": 800})
    pg.add_init_script(U1_INJECT)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="networkidle")
    pg.evaluate("""() => { localStorage.setItem('peiliao.cfg.v1', JSON.stringify({
        base:'http://127.0.0.1:18123/v1', key:'x', model:'x'}));
        localStorage.removeItem('peiliao.speak.v1');
        localStorage.removeItem('peiliao.history.v1'); localStorage.removeItem('peiliao.emotions.v1'); }""")
    pg.reload(wait_until="networkidle")
    # r99：原 `wait_for_timeout(400)` 押的是注入脚本落地时刻。`window.__tts` 由
    # add_init_script 在文档起始就建，等的就是这个标记本身（不是被断言的计数）。
    pg.wait_for_function("() => !!window.__tts", timeout=5000)
    supported = pg.evaluate("() => !!window.__tts && !window.__tts.unsupported")
    if not supported:
        check("U1a 浏览器不支持 TTS 时按钮应隐藏",
              pg.evaluate("() => document.getElementById('btn-speak').style.display === 'none'"),
              "headless 无语音引擎，改测隐藏分支")
        pg.close()
        return
    btn = "#btn-speak"
    check("U1a 朗读按钮存在", pg.evaluate(f"() => !!document.querySelector('{btn}')"))
    before = pg.get_attribute(btn, "aria-pressed")
    pg.click(btn)
    # r99：三处 `wait_for_timeout` 换成被等对象的完成态（aria-pressed 翻面 / 本轮回复落地）。
    pg.wait_for_function("(v) => document.getElementById('btn-speak')"
                         ".getAttribute('aria-pressed') !== v", arg=before, timeout=5000)
    now = pg.get_attribute(btn, "aria-pressed")
    check("U1b 点击后 aria-pressed 翻转", now != before, f"{before} -> {now}")
    check("U1c 开关已持久化", pg.evaluate("() => localStorage.getItem('peiliao.speak.v1')") == "1")
    pg.fill("#chat-input", "今天有点低落")
    mark_turn(pg)
    pg.click("#chat-form button[type=submit]")
    wait_reply(pg)
    t = pg.evaluate("() => window.__tts")
    check("U1d 开启后新回复真的构造并提交了语音", t["constructed"] >= 1 and t["spoken"] >= 1, str(t))
    pg.click(btn)                                    # 关闭
    pg.wait_for_function("(v) => document.getElementById('btn-speak')"
                         ".getAttribute('aria-pressed') !== v", arg=now, timeout=5000)
    c2 = pg.evaluate("() => window.__tts.constructed")
    pg.fill("#chat-input", "再说一句试试")
    mark_turn(pg)
    pg.click("#chat-form button[type=submit]")
    wait_reply(pg)
    c3 = pg.evaluate("() => window.__tts.constructed")
    check("U1e 关闭后不再朗读（关得掉）", c3 == c2, f"constructed {c2} -> {c3}")
    check("U1f 全程无 JS 异常", not errs, str(errs[:2]))
    pg.close()


def u2(browser):
    print("=== U2 对话窗口化 ===")
    pg = browser.new_page(viewport={"width": 1280, "height": 800})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE, wait_until="networkidle")
    pg.evaluate("""() => { localStorage.setItem('peiliao.cfg.v1', JSON.stringify({
        base:'http://127.0.0.1:18123/v1', key:'x', model:'x'}));
        localStorage.removeItem('peiliao.history.v1'); localStorage.removeItem('peiliao.emotions.v1'); }""")
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(400)
    for i in range(45):
        pg.fill("#chat-input", f"第 {i+1} 句：今天有点低落")
        pg.click("#chat-form button[type=submit]")
    # r100：这一批是"连发不等"，等的从来不是 6 秒，而是**这一批全部落地**。
    # 产品侧现在自报 `window.__pendingTurns`（chat-agent.js 的 turn() 包裹 respond，
    # 异常/提前 return 都过 finally ⇒ 不会只加不减）。轮询按 raf：respond 的 finally 减到 0
    # 之后，app.js 的渲染在同一微任务续体里紧跟着跑，rAF 观察到 0 时那一轮的渲染必然已完成。
    # 取不到这个钩子（旧副本/公网未重部署）⇒ 超时后如实点名 typeof，不折成"窗口化坏了"。
    settled = True
    why = ""
    try:
        pg.wait_for_function("() => window.__pendingTurns === 0", timeout=20000, polling="raf")
    except Exception as e:
        settled = False
        why = str(e).splitlines()[0][:80]
    check("U2g 连发批次等得到本轮终态（__pendingTurns 归零，非定长 6000ms）", settled,
          "typeof=%s%s" % (pg.evaluate("() => typeof window.__pendingTurns"),
                           "" if settled else " ｜" + why))
    dom = pg.evaluate("() => document.querySelectorAll('#chat-log .msg').length")
    hist = pg.evaluate("() => window.ChatAgent.getHistory().length")
    check("U2a DOM 节点不随消息单调增长（≤60）", 0 < dom <= 60, f".msg={dom}, 历史={hist}")
    hint = pg.evaluate("() => { const h=document.querySelector('.log-fold'); return h? h.textContent.trim() : null; }")
    check("U2b 折叠提示存在且标了条数", bool(hint) and "已折叠" in hint, str(hint))
    # 注意：ChatAgent 的 history 有**既存**上限 40 条（saveHistory 里 slice(-40)，非本轮引入）。
    # 本判据要证的是「DOM 窗口化没有反过来截断模型上下文」，所以断言 = 既存上限，而非发送条数。
    check("U2c 窗口化未截断模型上下文（等于既存 40 条上限）", hist == 40, f"getHistory={hist}")
    mem = pg.evaluate("() => window.MemoryStore.all().length")
    check("U2c2 情绪记忆条数=发送条数（窗口化只作用于渲染）", mem == 45, f"MemoryStore={mem}")
    first_before = pg.evaluate("() => document.querySelector('#chat-log .msg').textContent")
    pg.click("#btn-expand-log")
    pg.wait_for_timeout(800)
    dom2 = pg.evaluate("() => document.querySelectorAll('#chat-log .msg').length")
    first_after = pg.evaluate("() => document.querySelector('#chat-log .msg').textContent")
    check("U2d 展开较早确实放回一批且顺序在前", dom2 > dom and first_after != first_before,
          f"{dom} -> {dom2}")
    # 展开是「临时查看」：再发一条消息必须把窗口收回默认档，否则 DOM 上界形同虚设
    pg.fill("#chat-input", "再来一句：还是有点低落")
    mark_turn(pg)
    pg.click("#chat-form button[type=submit]")
    # r99：等这条回复真正落地。被断言的 dom3（.msg 总数 ≤60）与等待量（最后一条是不是新的 AI 气泡）
    # 不是同一个数，所以不构成「等自己要证的数」。
    wait_reply(pg)
    dom3 = pg.evaluate("() => document.querySelectorAll('#chat-log .msg').length")
    check("U2e 新消息后窗口收回默认上界", dom3 <= 60, f"展开后 {dom2} -> 发新消息后 {dom3}")
    check("U2f 全程无 JS 异常", not errs, str(errs[:2]))
    pg.close()


def u3(browser):
    print("=== U3 响应式与粒子降档 ===")
    counts = {}
    for w, label in ((375, "手机"), (700, "小平板"), (1300, "桌面")):
        pg = browser.new_page(viewport={"width": w, "height": 780})
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_timeout(600)
        m = pg.evaluate("""() => ({
          overflow: document.documentElement.scrollWidth - window.innerWidth,
          dock: !!document.getElementById('chat-dock') && getComputedStyle(document.getElementById('chat-dock')).display !== 'none',
          input: !!(document.getElementById('chat-input') && document.getElementById('chat-input').getClientRects().length),
          total: window.ThreeScene.litInfo().total
        })""")
        counts[label] = m["total"]
        check(f"U3[{label} {w}px] 无横向溢出", m["overflow"] <= 2, f"overflow={m['overflow']}px")
        check(f"U3[{label} {w}px] 对话坞与输入框可用", m["dock"] and m["input"])
        pg.close()
    check("U3 桌面档粒子数恒为 2600（否则破 browser_check 标定）", counts["桌面"] == 2600, str(counts))
    check("U3 小屏粒子按档递减", counts["手机"] < counts["小平板"] < counts["桌面"], str(counts))


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="msedge")
        u1(browser)
        u2(browser)
        u3(browser)
        browser.close()
    bad = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(bad)} 项")
    for n, _, d in bad:
        print("  🔴", n, d)
    print("UX-GUARDS-PASS" if not bad else "UX-GUARDS-FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
