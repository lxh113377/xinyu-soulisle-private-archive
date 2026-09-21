# -*- coding: utf-8 -*-
"""J4 持久化验验收：记忆从 localStorage 迁到服务端数据库（并保留本地降级）。

用法：先起 Java 服务端在 8123（工作目录=项目根），再跑本脚本。

用例：
  A（远端开启）：cfg.remote=true → 对话后服务端应有 emotion/message 记录；
     **核心断言**：清空 localStorage 的情绪记忆并刷新，星图仍能被点亮
     ⇒ 证明数据来自服务端数据库，而不是浏览器本地存储（真"替代"而非"双写"）。
  B（对照组，默认关闭）：不设 remote → 服务端记录数必须为 0，判据非恒真。
"""
import sys, io, json, time, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8123/index.html"
API = "http://127.0.0.1:8123/api/memory"
TEXT = "今天被导师批评了，心情很低落"
SID_ON = "j4-py-test-on"
SID_OFF = "j4-py-test-off"


def http(method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def stats(sid):
    return http("GET", f"{API}/stats?sessionId={sid}")


def boot(page, cfg, sid):
    page.goto(BASE, wait_until="networkidle")
    page.evaluate("""([cfg, sid]) => {
      localStorage.setItem('peiliao.cfg.v1', JSON.stringify(cfg));
      localStorage.setItem('peiliao.session.v1', sid);
      localStorage.removeItem('peiliao.emotions.v1');
      localStorage.removeItem('peiliao.history.v1');
    }""", [cfg, sid])
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(800)


def say(page):
    page.fill("#chat-input", TEXT)
    page.click("#chat-form button[type=submit]")
    page.wait_for_timeout(8000)


def lit(page):
    return page.evaluate("() => window.ThreeScene.litInfo().lit")


# 直连凭据故意无效：只让 proxy 生效（否则 demo-config 会覆盖 cfg 走浏览器直连）
CFG_ON = {"proxy": "/api/chat", "remote": True, "base": "http://127.0.0.1:18123/v1",
          "key": "invalid", "model": "x"}
CFG_OFF = {"proxy": "/api/chat", "base": "http://127.0.0.1:18123/v1",
           "key": "invalid", "model": "x"}

http("DELETE", f"{API}/{SID_ON}")
http("DELETE", f"{API}/{SID_OFF}")
before_on, before_off = stats(SID_ON), stats(SID_OFF)

with sync_playwright() as p:
    try:
        browser = p.chromium.launch()
    except Exception:
        browser = p.chromium.launch(channel="msedge")

    # ---- 用例 A：远端开启 ----
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    boot(page, CFG_ON, SID_ON)
    say(page)
    lit_local = lit(page)
    a = stats(SID_ON)

    # 核心断言：抹掉本地存储后刷新，星图应靠服务端数据重建
    page.evaluate("""() => {
      localStorage.removeItem('peiliao.emotions.v1');
      localStorage.removeItem('peiliao.history.v1');
    }""")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3500)
    lit_after_wipe = lit(page)
    page.close()

    # ---- 用例 B：对照组（默认关闭） ----
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    boot(page, CFG_OFF, SID_OFF)
    say(page)
    b = stats(SID_OFF)
    page.close()
    browser.close()

print("A_BEFORE:", before_on, "A_AFTER:", a)
print("A_LIT_LOCAL:", lit_local, "A_LIT_AFTER_WIPE_LOCALSTORAGE:", lit_after_wipe)
print("B_BEFORE:", before_off, "B_AFTER(须全 0):", b)

ok = True
if a["emotions"] < 1 or a["messages"] < 2:
    print("FAIL-A: 远端开启后服务端应有 emotion>=1 且 message>=2")
    ok = False
if lit_after_wipe <= 0:
    print("FAIL-A2: 清空本地后星图未重建 ⇒ 数据没真正来自服务端")
    ok = False
if lit_after_wipe != lit_local:
    print(f"WARN-A3: 清空本地前后点亮数不一致 local={lit_local} wipe={lit_after_wipe}")
if b["emotions"] != 0 or b["messages"] != 0:
    print("FAIL-B: 默认关闭时服务端不应收到任何记录 → 判据恒真")
    ok = False
print("J4-MEMORY-PASS" if ok else "J4-MEMORY-FAIL")
