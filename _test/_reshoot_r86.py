# -*- coding: utf-8 -*-
"""r86 改版重截：以**当前 UI + MindIsle 品牌**重出提交包 9 张图。

先落 _test/_shots/r86/ 目检，通过后再覆盖 交付物/提交包/img/（不直接碰交付物）。
前置：fat jar 在 8123（同源代理 /api/chat + /api/emotion），src/js/demo-config.js 处于 proxy 模式。
构图对齐现状图：s01 初始态（含坞）/ s06 收起坞的纯第一幕 / s03 一轮在线对话 /
s04 两轮在线对话·双路证据标签 / s05 第四幕曲线 / s07 双路分歧（词典+LLM 分歧 → 采信 LLM）/
s02 离线共情模板态 / s09 断网应用壳（网络不可用徽章）/ s10 设置面板（Key 框为空）。
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_test" / "_shots" / "r86"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8123/index.html"

DUAL_CANDIDATES = [
    "论文被导师打回来改了四遍，我真的撑不住了",
    "室友保研了我还在二战，心里特别不是滋味",
]


def shot(pg, name):
    pg.screenshot(path=str(OUT / (name + ".png")))
    print("shot", name)


def scroll_act(pg, act, block="center"):
    pg.evaluate(f"() => document.getElementById('{act}').scrollIntoView({{block:'{block}'}})")
    pg.wait_for_timeout(700)


def send_and_wait(pg, text, ms=13000):
    pg.fill("#chat-input", text)
    # GSAP 滚动位会让固定坞的按钮 bounding box 落到视口外，指针点击不可靠 ⇒ 用真实表单提交
    pg.evaluate("() => document.getElementById('chat-form').requestSubmit()")
    pg.wait_for_timeout(ms)


def last_label(pg):
    js = ("() => { const b=[...document.querySelectorAll('#chat-window .msg-meta,"
          "#chat-window .meta,#chat-window [class*=meta]')]; "
          "return b.length ? b[b.length-1].textContent : ''; }")
    return pg.evaluate(js)


NEED = set(sys.argv[1:]) or {"s01", "s06", "s03", "s04", "s05", "s07", "s02", "s09", "s10"}

with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception:
        b = p.chromium.launch(channel="msedge")

    # --- s01 初始态（含对话坞与开场白；等「一键点亮」开场动画播完再拍） ---
    if "s01" in NEED or "s06" in NEED:
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_timeout(11000)
        if "s01" in NEED:
            shot(pg, "s01")

        # --- s06 收起坞的纯第一幕 ---
        pg.click("#btn-dock")
        pg.wait_for_timeout(900)
        pg.evaluate("() => window.scrollTo(0, 0)")
        pg.wait_for_timeout(1200)
        if "s06" in NEED:
            shot(pg, "s06")
        ctx.close()

    # --- s03 / s04 / s05 / s07：同一会话推进 ---
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(2000)
    send_and_wait(pg, "最近总是失眠，压力好大")
    scroll_act(pg, "act3")
    shot(pg, "s03")
    send_and_wait(pg, "今天被导师批评了，心情很低落")
    scroll_act(pg, "act3")
    shot(pg, "s04")
    scroll_act(pg, "act4")
    shot(pg, "s05")
    # act4 滚动位会让固定坞的提交按钮落在视口外（GSAP transform），刷新后从顶部继续
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(2500)
    # s07：找一条「词典+LLM 分歧 → 采信 LLM」的回复（独立会话，坞默认展开）
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(2000)
    got_dual = False
    for cand in DUAL_CANDIDATES:
        send_and_wait(pg, cand)
        visible = pg.evaluate(
            "() => document.getElementById('chat-log').innerText.includes('分歧')")
        print("dual visible:", visible)
        scroll_act(pg, "act3")
        shot(pg, "s07")
        if visible:
            got_dual = True
            break
    print("s07 dual =", got_dual)
    ctx.close()

    # --- s02 离线共情模板（评委体验模式条 → 清除本机配置 → 无凭据 ⇒ 本地引擎，如实标注） ---
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(2000)
    pg.click("#btn-demo-clear")
    pg.wait_for_timeout(800)
    send_and_wait(pg, "最近总是失眠，压力好大", ms=4000)
    scroll_act(pg, "act2")
    shot(pg, "s02")
    ctx.close()

    # --- s09 断网应用壳（网络不可用徽章） ---
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(3000)
    ctx.set_offline(True)
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    shot(pg, "s09")
    ctx.close()

    # --- s10 设置面板（Key 框为空、type=password、逐字流式开关可见；等开场动画播完） ---
    if "s10" in NEED:
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_timeout(11000)
        pg.click("#btn-settings")
        pg.wait_for_timeout(900)
        shot(pg, "s10")
        ctx.close()
    b.close()

print("RESHOOT-R86-DONE ->", OUT)
