# -*- coding: utf-8 -*-
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright
from browser_engine import launch as be_launch   # r113：手写回退收编为唯一入口
OUT = r"c:\Users\37533\Desktop\workspace\项目\陪聊\交付物\iCAN评审\截图"
os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    b, _engine_face = be_launch(p, label="screenshots_online.py")
    print("[engine] %s" % _engine_face)  # r113：引擎身份必须可见，否则「本地全绿」无法归因（CI 是另一台浏览器）
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto("http://localhost:8123/index.html", wait_until="networkidle")
    pg.screenshot(path=OUT + r"\05-在线模式-徽章与体验条.png")
    pg.fill("#chat-input", "论文被导师打回来改了四遍，我真的撑不住了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(6000)
    pg.locator("#act2").scroll_into_view_if_needed()
    pg.wait_for_timeout(400)
    pg.screenshot(path=OUT + r"\06-双路情绪探针-词典与LLM分歧.png")
    pg.fill("#chat-input", "室友保研了我还在二战，心里特别不是滋味")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    pg.locator("#act3").scroll_into_view_if_needed()
    pg.wait_for_timeout(400)
    pg.screenshot(path=OUT + r"\07-在线对话-双路证据标签.png")
    b.close()
print("ONLINE-SCREENSHOTS-DONE")
