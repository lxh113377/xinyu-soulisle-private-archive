# -*- coding: utf-8 -*-
"""心屿原型浏览器实测：console 零报错 + 底部对话坞 / 星雾点亮 / 持久化 / 危机 / 回滚 全链路断言"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

errors = []

# CI（GitHub ubuntu runner 无 GPU）需要软件光栅化 WebGL；本机留空即走默认。
# 不加这行 → headless 里 `#gl` 起不来 → `lit1 > 0` 断言必然失败（判据环境性假红）。
LAUNCH_ARGS = [a for a in os.environ.get("XINYU_BROWSER_ARGS", "").split() if a]


def lit(pg):
    return pg.evaluate("() => window.ThreeScene.litInfo().lit")


with sync_playwright() as p:
    try:
        browser = p.chromium.launch(args=LAUNCH_ARGS)
    except Exception:
        browser = p.chromium.launch(channel="msedge", args=LAUNCH_ARGS)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8123/index.html", wait_until="networkidle")

    # 0) 降级链路：注入不可达端点（auth 失败 → 走离线模板），并清空本机情绪记忆保证初始态干净
    page.evaluate("""() => { localStorage.setItem('peiliao.cfg.v1',
      JSON.stringify({base:'http://127.0.0.1:18123/v1', key:'x', model:'x'}));
      localStorage.removeItem('peiliao.emotions.v1'); }""")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(800)

    # 1) 基础断言
    title = page.title()
    three_loaded = page.evaluate("() => typeof THREE !== 'undefined'")
    gsap_loaded = page.evaluate("() => typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined'")
    webgl_active = page.evaluate("() => !document.getElementById('gl').hidden")
    dock_visible = page.is_visible("#chat-dock") and page.is_visible("#chat-input")
    lit0 = lit(page)

    # 2) 底部对话坞说第一句话 → 应识别情绪 + 点亮星雾 + 记录曲线
    page.fill("#chat-input", "今天被导师批评了，心情很低落")
    page.click("#chat-form button[type=submit]")
    page.wait_for_timeout(3000)
    msgs = page.eval_on_selector_all(".msg.ai", "els => els.map(e=>e.textContent)")
    last_ai = msgs[-1] if msgs else ""
    chart_count = page.inner_text("#chart-count")
    readout = page.inner_text("#probe-result")
    lit1 = lit(page)

    # 3) 混合情绪 → 双色星雾标注 + 继续点亮
    page.fill("#chat-input", "考研压力好大好焦虑，但收到offer又有点开心")
    page.click("#chat-form button[type=submit]")
    page.wait_for_timeout(3000)
    mist = page.inner_text("#probe-mist")
    lit2 = lit(page)

    # 4) 持久化：刷新后按本机记忆把星图重建出来（点亮数应保持一致）
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    lit_reload = lit(page)

    # 5) 危机词 → 安全转介策略
    page.fill("#chat-input", "感觉活着好累，不想活了")
    page.click("#chat-form button[type=submit]")
    page.wait_for_timeout(2500)
    crisis_readout = page.inner_text("#probe-result")

    # 6) 坞折叠后再一键清除 → 星星熄灭（坞展开时会遮住第四幕按钮，必须能收起）
    page.click("#btn-dock")
    page.wait_for_timeout(500)
    dock_collapsed = not page.eval_on_selector("#chat-dock", "e => e.classList.contains('open')")
    page.click("#btn-clear")
    page.wait_for_timeout(600)
    lit_after_clear = lit(page)
    chart_after_clear = page.inner_text("#chart-count")

    # 7) 滚动驱动 + 回滚可见性回归（2026-09-19 修复：双补间争抢同一属性 → 回滚后文案不恢复）
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1800)
    page.evaluate("() => document.getElementById('act3').scrollIntoView({block:'center'})")
    page.wait_for_timeout(2000)
    back3 = float(page.eval_on_selector("#act3 .act-copy", "e => getComputedStyle(e).opacity"))

    # 7a2) 滚动淡入淡出：面板刚进屏要淡、居中要实、还大面积可见时就要开始变淡
    #      （旧版 trigger 挂在「幕」上，淡入淡出全落在面板看不见的空白区，实测可见期 opacity 恒 0.93~1.00）
    pt = page.evaluate("""() => { const b = document.querySelector('#act3 .act-copy').getBoundingClientRect();
        return { abs: b.top + window.scrollY, h: b.height, vh: innerHeight }; }""")
    enter = int(pt["abs"] - pt["vh"] + 40)
    center = int(pt["abs"] + pt["h"] / 2 - pt["vh"] / 2)
    # 面板还有一半留在视口内的位置：此时就应该明显变淡（不是等它快滑出屏幕才变）
    leaving = int(pt["abs"] + pt["h"] * 0.5)

    def panel_op(y):
        page.evaluate("(v) => window.scrollTo(0, v)", y)
        page.wait_for_timeout(800)
        return float(page.eval_on_selector("#act3 .act-copy", "e => getComputedStyle(e).opacity"))

    o_enter, o_center, o_leaving = panel_op(enter), panel_op(center), panel_op(leaving)

    # 8) 同色系次色必须被拉开到肉眼可分
    color_gap = page.evaluate("""() => {
      const E = window.EmotionEngine, d = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]);
      const main = E.colorOf('sadness'), raw = E.colorOf('fear');
      const applied = window.ThreeScene.setEmotion(main, 0.6, raw);
      return { raw: d(main, raw), applied: d(main, applied) };
    }""")

    browser.close()

print("TITLE:", title)
print("THREE:", three_loaded, "GSAP:", gsap_loaded, "WEBGL_ACTIVE:", webgl_active, "DOCK:", dock_visible)
print("LAST_AI:", last_ai.replace("\n", " ")[:120])
print("READOUT:", readout.replace("\n", " ")[:120])
print("MIST:", mist.replace("\n", " "))
print("LIT: init=%d after1=%d after2=%d reload=%d clear=%d" % (lit0, lit1, lit2, lit_reload, lit_after_clear))
print("CHART:", chart_count, "| after clear:", chart_after_clear)
print("CRISIS:", "危机" in crisis_readout)
print("ROLLBACK_OPACITY(act3):", back3)
print("SCROLL_FADE: enter=%.2f center=%.2f leaving=%.2f" % (o_enter, o_center, o_leaving))
print("DUAL_COLOR_GAP: raw=", round(color_gap["raw"], 3), "→ applied=", round(color_gap["applied"], 3))
print("CONSOLE_ERRORS:", len(errors), errors[:5])

real_errors = [e for e in errors if "18123" not in e and "ERR_CONNECTION_REFUSED" not in e]
assert dock_visible, "底部对话坞不可见（第二幕+第三幕融合失败）"
assert lit0 == 0, f"初始星图应全部未点亮，实际已点亮 {lit0}"
assert len(last_ai) > 5, "对话无回复"
assert lit1 > 0, "对话后星雾没有被点亮"
assert "低落" in readout, f"情绪读数未显示识别结果: {readout}"
assert "1 条" in chart_count or "2 条" in chart_count, f"情绪曲线未记录: {chart_count}"
assert "双色星雾" in mist, f"混合情绪未触发双色星雾: {mist}"
assert lit2 > lit1, f"第二次对话未继续点亮: {lit1} → {lit2}"
assert lit_reload == lit2, f"刷新后星图未重建/数量不符: {lit2} → {lit_reload}"
assert "危机" in crisis_readout, "危机词未拦截"
assert dock_collapsed, "对话坞无法收起（会遮住幕内按钮）"
assert lit_after_clear == 0, f"清除数据后星星未熄灭: {lit_after_clear}"
assert "还没有记录" in chart_after_clear, f"清除后曲线未清空: {chart_after_clear}"
assert back3 > 0.9, f"滚到底再回滚后 act3 文案未恢复（opacity={back3}）"
assert o_enter < 0.6, f"面板刚进屏不够淡（{o_enter}）——随滚动淡入未生效"
assert o_center > 0.9, f"面板居中不够实（{o_center}）——影响可读性"
assert o_leaving < 0.5 and o_leaving < o_center, f"面板还大面积可见时没明显变淡（{o_leaving}）——随滚动淡出未生效"
assert color_gap["applied"] >= 0.4 and color_gap["applied"] > color_gap["raw"], f"同色系次色未被拉开: {color_gap}"
assert len(real_errors) == 0, f"console 报错: {real_errors}"
print("ALL-ASSERT-PASS")
