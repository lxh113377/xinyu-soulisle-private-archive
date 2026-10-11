# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright
OUT = r"c:\Users\37533\Desktop\workspace\项目\陪聊\交付物\iCAN评审\截图"
import os; os.makedirs(OUT, exist_ok=True)
from browser_engine import launch as be_launch   # r113：手写回退收编为唯一入口
with sync_playwright() as p:
    b, _engine_face = be_launch(p, label="screenshots.py")
    print("[engine] %s" % _engine_face)  # r113：引擎身份必须可见，否则「本地全绿」无法归因（CI 是另一台浏览器）
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    pg.goto("http://localhost:8123/index.html", wait_until="networkidle")
    pg.screenshot(path=OUT + r"\01-第一幕-相遇.png")
    pg.fill("#chat-input", "最近总是失眠，压力好大")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(2000)
    pg.evaluate("() => document.getElementById('act2').scrollIntoView({block:'center'})")
    pg.wait_for_timeout(600)
    pg.screenshot(path=OUT + r"\02-第二幕-情绪读数.png")
    pg.fill("#chat-input", "今天被导师批评了，心情很低落")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(1200)
    pg.locator("#act3").scroll_into_view_if_needed()
    pg.wait_for_timeout(500)
    pg.screenshot(path=OUT + r"\03-第三幕-AI对话.png")
    pg.locator("#act4").scroll_into_view_if_needed()
    pg.wait_for_timeout(800)
    pg.screenshot(path=OUT + r"\04-第四幕-情绪曲线.png")
    b.close()
print("SCREENSHOTS-DONE")
