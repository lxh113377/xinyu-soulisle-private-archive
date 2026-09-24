# -*- coding: utf-8 -*-
# 重截提交包 s01/s08（去除打码模糊块的无敏感信息版本）。
# 流程：先写 _test/_shots/resubmit_*.png，人工/agent 目检通过后人工覆盖 提交包/img/，不直接碰交付物。
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\37533\Desktop\workspace\项目\陪聊\_test\_shots"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:8123/index.html"

with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception:
        b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    # s01：第一幕初始态（全新会话，星雾 0 颗）
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT + r"\resubmit_s01.png")
    # s08：与原 07-在线对话-双路证据标签 同序两句话，第二句后滚动到第三幕截图
    pg.fill("#chat-input", "论文被导师打回来改了四遍，我真的撑不住了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(8000)
    pg.fill("#chat-input", "室友保研了我还在二战，心里特别不是滋味")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    pg.locator("#act3").scroll_into_view_if_needed()
    pg.wait_for_timeout(400)
    pg.screenshot(path=OUT + r"\resubmit_s08.png")
    # 断言：在线模式证据标签确实出现在对话坞里，避免截出离线降级版冒充在线
    body = pg.inner_text("body")
    ok_online = ("在线" in body) and ("词典" in body or "LLM" in body)
    print("ONLINE-EVIDENCE:", ok_online)
    b.close()
print("RESUBMIT-SCREENSHOTS-DONE")
