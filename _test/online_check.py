# -*- coding: utf-8 -*-
"""在线模式全链路回归：体验模式徽章 + 双路情绪探针 + 在线对话 + 危机拦截 + console 0 报错"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

errors = []
with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception:
        b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": 1280, "height": 800})  # 全新 profile = 无配置，触发体验模式
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://localhost:8123/index.html", wait_until="networkidle")

    # 1) 体验模式：徽章应为"在线 AI"，提示条可见
    badge = pg.inner_text("#mode-badge")
    strip_visible = pg.evaluate("() => !document.getElementById('demo-strip').hidden")
    engine = pg.inner_text("#chat-engine")

    # 2) 双路情绪读数（探针已并入底部对话坞）：对话后第二幕读数面板应含双路结论
    pg.fill("#chat-input", "论文被导师打回来改了四遍，我真的撑不住了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(9000)
    probe = pg.inner_text("#probe-result")

    # 3) 在线对话：真实 LLM 回复 + 双路标签
    pg.fill("#chat-input", "室友保研了我还在二战，心里特别不是滋味")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    tags = pg.eval_on_selector_all(".msg.ai .tag", "els => els.map(e=>e.textContent)")
    last_tag = tags[-1] if tags else ""

    # 4) 危机词仍走转介（双路不破坏安全边界）
    pg.fill("#chat-input", "感觉活着好累，不想活了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(4000)
    msgs = pg.eval_on_selector_all(".msg.ai", "els => els.map(e=>e.textContent)")
    crisis_ok = any("12356" in m for m in msgs)

    # 5) 清除配置按钮：体验模式可退出
    pg.click("#btn-demo-clear")
    badge_after = pg.inner_text("#mode-badge")

    b.close()

print("BADGE:", badge, "| STRIP:", strip_visible, "| ENGINE:", engine)
print("PROBE:", probe.replace("\n", " ")[:200])
print("CHAT_TAG:", last_tag[:160])
print("CRISIS_OK:", crisis_ok)
print("BADGE_AFTER_CLEAR:", badge_after)
print("CONSOLE_ERRORS:", len(errors), errors[:5])

assert "在线 AI" in badge, "体验模式徽章未生效"
assert strip_visible, "体验模式提示条未显示"
assert "LLM" in probe and "词典" in probe, "双路情绪读数未生效"
assert "在线大模型生成" in last_tag, "对话未走在线模型"
assert "情绪双路" in last_tag, "对话缺双路证据标签"
assert crisis_ok, "危机转介失效"
assert "离线" in badge_after, "清除配置未退出体验模式"
assert len(errors) == 0, f"console 报错: {errors}"
print("ONLINE-ALL-PASS")
