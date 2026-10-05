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
    # r80：一键点亮默认打开 ⇒ 每次加载有约 5.2s 开场演示。本套件的「刷新后星图仍点亮」读的是
    # 演示星还是真实记忆，取决于取样时刻，必须等被等对象的完成态（不是固定 sleep）。
    page.wait_for_function("() => window.__XINYU__ && window.__XINYU__.opening === 'done'", timeout=15000)
    page.wait_for_timeout(800)


def say(page):
    page.fill("#chat-input", TEXT)
    page.click("#chat-form button[type=submit]")


def wait_quiescent(sid, budget_s=25.0, poll=0.25):
    """等这一轮**写完并静止**：先看到服务端计数相对起账发生变化，再看到连续两次读数一致。
    为什么不沿用定长 sleep（旧写法 `wait_for_timeout(8000)`）：本机实测落库时刻 1.65s
    （探针逐 0.25s 采样：t=0.66s 仍 0/0，t≈1.65s 起 emotions=1 messages=2），
    固定 8s 等于把判据的成败押在机器负载上 —— CI run 37294500147 就是这样判红的，
    与 r60 在 `storage_resilience_check` 修掉的是同一形态。
    静止判据**不预设断言阈值**（只问"变了吗 / 还在变吗"），所以它不是"等自己要证的数"：
    服务端只写进 1 条时本函数照常返回 True，随后 FAIL-A 带着实测数字判红。
    到点仍没变化 ⇒ False ⇒ 调用方判**取数失败**（红因点名"回合没落地"，不是"服务端错了"）。"""
    base = stats(sid)
    t0 = time.monotonic()
    changed, prev = False, None
    while time.monotonic() - t0 < budget_s:
        cur = stats(sid)
        if not changed:
            if cur.get("messages") != base.get("messages") or cur.get("emotions") != base.get("emotions"):
                changed, prev = True, cur
        elif cur == prev:
            return True
        else:
            prev = cur
        time.sleep(poll)
    return False


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
    settled_on = wait_quiescent(SID_ON)
    lit_local = lit(page)
    a = stats(SID_ON)

    # 核心断言：抹掉本地存储后刷新，星图应靠服务端数据重建
    page.evaluate("""() => {
      localStorage.removeItem('peiliao.emotions.v1');
      localStorage.removeItem('peiliao.history.v1');
    }""")
    page.reload(wait_until="networkidle")
    page.wait_for_function("() => window.__XINYU__ && window.__XINYU__.opening === 'done'", timeout=15000)
    page.wait_for_timeout(3500)
    lit_after_wipe = lit(page)
    page.close()

    # ---- 用例 B：对照组（默认关闭） ----
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    boot(page, CFG_OFF, SID_OFF)
    say(page)
    page.wait_for_timeout(10000)   # 观察窗（不是等完成）：须明显长于 A 路径实测的 1.65s 落库时刻
    mem_off = page.evaluate("() => document.querySelectorAll('.msg').length")
    b = stats(SID_OFF)
    page.close()
    browser.close()

print("A_BEFORE:", before_on, "A_AFTER:", a)
print("A_LIT_LOCAL:", lit_local, "A_LIT_AFTER_WIPE_LOCALSTORAGE:", lit_after_wipe)
print("B_BEFORE:", before_off, "B_AFTER(须全 0):", b)

ok = True
if not settled_on:
    print("FAIL-A0: 25s 内服务端计数毫无变化 ⇒ 本轮取数失败（不是服务端判红），先查页面/引擎面")
    ok = False
if a["emotions"] < 1 or a["messages"] < 2:
    # 判据行必须自带读数：电池只保留含 FAIL 的红因行，上面 A_BEFORE/A_AFTER 那两行在 CI 上会被折掉
    # ⇒ 不带数就会把"归零"与"少写一条"两种完全不同的根因读成同一句（2026-10-05 run 37294500147 一手）
    print("FAIL-A: 远端开启后服务端应有 emotion>=1 且 message>=2｜实测 emotions=%s messages=%s"
          "（起账 %s/%s，sid=%s）" % (a["emotions"], a["messages"],
                                      before_on.get("emotions"), before_on.get("messages"), SID_ON))
    ok = False
if lit_after_wipe <= 0:
    print("FAIL-A2: 清空本地后星图未重建 ⇒ 数据没真正来自服务端")
    ok = False
if lit_after_wipe != lit_local:
    print(f"WARN-A3: 清空本地前后点亮数不一致 local={lit_local} wipe={lit_after_wipe}")
if mem_off < 2:
    print("FAIL-B0: 对照组页面里连气泡都没出现（DOM msg=%s）⇒ B 的『须全 0』没有驱动数据，不判绿" % mem_off)
    ok = False
if b["emotions"] != 0 or b["messages"] != 0:
    print("FAIL-B: 默认关闭时服务端不应收到任何记录 → 判据恒真")
    ok = False
print("J4-MEMORY-PASS" if ok else "J4-MEMORY-FAIL")
# 电池按 rc 记账，而本件此前只印结论不转退出码 ⇒ 印 FAIL 也记绿（r93 在 j2_chat_contract
# 上抓到同型并修了那一件；r94 类扫 90 套件仍只有本件漏网，AC-OBS-10 的验收判据不能报红而记绿）。
# 守卫形态 = G9 `import_safety` 的要求（顶层入口调用须在 `if __name__` 之后）。本件正文仍是顶层
# 脚本形态（与 browser_check/pixel_dual 等同族），import 会执行到 print 那行才停 —— 已知软面，
# 记在 r95 报告 §5，不假装本件已全量 import-safe。
if __name__ == "__main__":
    sys.exit(0 if ok else 1)
