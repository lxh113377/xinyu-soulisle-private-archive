# -*- coding: utf-8 -*-
"""r20 情绪识别后端化接线守卫（逐项独立判定，禁止聚合掩盖单项失败）

背景：J3 把词典+LLM 双路情绪引擎搬到了 Java（/api/emotion），但前端仍只跑本地 JS 引擎
      ⇒ 「两份真相」未消除（07 P0「J3/J4 变现」第①件）。本轮接线并配本守卫。

判据（W1–W6 实跑，W7 自证判据非恒真）：
  W1 静态接线：index.html 在 chat-agent.js **之前**引入 js/emotion-remote.js；
              chat-agent.respond 经 EmotionRemote.classifyWithBackend；本地演示配置置 emotionRemote
  W2 部署副本红线：deploy/xinyu 与 src 逐字节相同，且**公网版配置刻意不含 emotionRemote**
              （Pages Function 只有 /api/chat，开了会让评委看到 404）
  W3 危机短路顺序：源码里危机分支必须位于 fetch 之前（危机拦截绝不为网络等待）
  W4 端到端生效：浏览器实测 —— 后端路径被使用（stats.ok≥1）且气泡如实标注「情绪:后端」
  W5 降级不伪装：拦掉 /api/emotion ⇒ 熔断（isDown）+ 回复照常产出 + **不出现**后端标注
  W6 词典层双端对账：同句 后端 lex.emotion == 本地 EmotionEngine.scan().emotion（不受 LLM 抖动影响）
  W7 --selftest：三类篡改样本（删接线 / 公网版误开 / 危机分支后置）必须各自报红，
              原样文本必须零问题 —— 证明 W1/W2/W3 不是恒真判据

前置：Java fat jar 起在 8123（托管 src/ 且带 /api/emotion）
退出码：0=WIRING-PASS 1=任一判据失败 2=环境异常（jar 不可达 / playwright 缺失）
"""
import argparse
import hashlib
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PUB = ROOT / "deploy" / "xinyu"
BASE = "http://127.0.0.1:8123"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def read(p):
    return Path(p).read_text("utf-8", errors="replace")


def static_wiring(html, agent, cfgjs):
    """返回问题清单（纯函数，供 W1–W3 与 W7 自证复用）。"""
    bad = []
    i_engine = html.find("js/emotion-engine.js")
    i_remote = html.find("js/emotion-remote.js")
    i_agent = html.find("js/chat-agent.js")
    if i_remote < 0:
        bad.append("index.html 未引入 js/emotion-remote.js")
    elif not (0 <= i_engine < i_remote < i_agent):
        bad.append(f"脚本顺序不成立 engine={i_engine} remote={i_remote} agent={i_agent}")
    if "EmotionRemote.classifyWithBackend" not in agent:
        bad.append("chat-agent.js 未走 EmotionRemote.classifyWithBackend")
    if "emotionRemote" not in cfgjs:
        bad.append("本地演示配置未置 emotionRemote")
    return bad


def crisis_shortcircuit(remote_src):
    """危机分支是否先于**同一函数体内**对后端的调用。

    判据口径（第一版踩坑后更正）：不能用「整个文件里 `fetch(` 的字符位置」——
    `fetchEmotion()` 定义在 `classifyWithBackend()` 之前，文件级字符序与执行序无关，
    那样写会把正确实现误判为红（假红同样是缺陷）。此处只在 classifyWithBackend 的
    函数体内比较：危机 return 必须早于 `fetchEmotion(` 调用点。
    """
    body_at = remote_src.find("async function classifyWithBackend")
    if body_at < 0:
        return False
    body = remote_src[body_at:]
    nxt = body.find("\n  window.EmotionRemote")          # 函数体结束（导出处）
    if nxt > 0:
        body = body[:nxt]
    c = body.find("if (lex.crisis)")
    f = body.find("fetchEmotion(text)")
    return 0 <= c < f


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def w1_w3():
    html = read(SRC / "index.html")
    agent = read(SRC / "js" / "chat-agent.js")
    cfgjs = read(SRC / "js" / "demo-config.js")
    remote = read(SRC / "js" / "emotion-remote.js")
    bad = static_wiring(html, agent, cfgjs)
    check("W1 静态接线（引入顺序 + 编排改道 + 开关）", not bad, "; ".join(bad))
    check("W2 公网副本零密钥开关（deploy 不含 emotionRemote）",
          "emotionRemote" not in read(PUB / "js" / "demo-config.js"),
          "deploy/xinyu/js/demo-config.js 出现 emotionRemote（公网无 /api/emotion，会 404）")
    same = []
    for rel in ["index.html", "js/emotion-remote.js", "js/chat-agent.js", "js/app.js"]:
        a, b = SRC / rel, PUB / rel
        if not b.exists():
            same.append(f"{rel} 缺公网副本")
        elif sha(a) != sha(b):
            same.append(f"{rel} 与 src 逐字节不同")
    check("W2b src↔deploy 关键副本一致（同步红线）", not same, "; ".join(same))
    check("W3 危机短路先于后端调用", crisis_shortcircuit(remote),
          "classifyWithBackend 体内：lex.crisis 分支须在 fetchEmotion(text) 调用之前")
    return html, agent, cfgjs, remote


def jar_up():
    try:
        with urllib.request.urlopen(BASE + "/api/health", timeout=6) as r:
            return json.loads(r.read().decode("utf-8")).get("status") == "UP"
    except Exception:
        return False


def emotion_api_ok():
    try:
        req = urllib.request.Request(BASE + "/api/emotion",
                                     data=json.dumps({"text": "我今天很难过"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
        return isinstance(j.get("lex"), dict) and "emotion" in (j.get("final") or {})
    except Exception:
        return False


E2E_SEED = """(cfg) => { localStorage.setItem('peiliao.cfg.v1', JSON.stringify(cfg));
  localStorage.removeItem('peiliao.emotions.v1'); localStorage.removeItem('peiliao.history.v1'); }"""


def send(page, text, timeout=90000):
    """发一句并等**终态气泡**。

    踩坑固化（两版假红的真根因）：app.js 在等待期会先插一个 `.msg.ai.thinking` 占位泡，
    流式期再换成 `.msg.ai.streaming` —— **两者都是 .msg.ai**。
    只判 `.msg.ai` 出现 ⇒ 读到 "心屿正在感受你的话…"；只排除 .streaming ⇒ 仍读到 thinking 占位泡。
    故终态选择器必须同时排除 .streaming 与 .thinking，且要求不再有 streaming 泡在飞。
    """
    TERM = "#chat-log .msg.ai:not(.streaming):not(.thinking)"
    count_js = "() => document.querySelectorAll('" + TERM + "').length"
    before = page.evaluate(count_js)
    page.fill("#chat-input", text)
    page.click("#chat-form button[type=submit]")
    page.wait_for_function(
        "(n) => document.querySelectorAll('" + TERM + "').length > n"
        " && !document.querySelector('#chat-log .msg.ai.streaming')", arg=before, timeout=timeout)
    page.wait_for_timeout(300)
    return page.evaluate("() => { const m=document.querySelectorAll('" + TERM + "');"
                         "return m.length? m[m.length-1].textContent : ''; }")


def e2e(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))

    # W4 后端路径生效
    page.goto(BASE + "/index.html", wait_until="networkidle")
    page.evaluate(E2E_SEED, {"proxy": "/api/chat", "emotionRemote": True})
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(600)
    meta = send(page, "今天被导师批评了，心情很低落")
    st = page.evaluate("() => window.EmotionRemote.stats()")
    last = page.evaluate("() => window.EmotionRemote.last()")
    check("W4 端到端：后端情绪被使用且如实标注",
          st.get("ok", 0) >= 1 and "情绪:后端" in meta,
          f"stats={st} backend_emotion={(last or {}).get('final', {}).get('emotion') if last else None} "
          f"meta_tail={meta[-70:]}")

    # W6 词典层双端对账（同句：后端 lex 与本地引擎结论必须一致）
    probe = "我最近特别焦虑，晚上睡不着觉，心里发慌"
    loc = page.evaluate("(t) => window.EmotionEngine.scan(t).emotion", probe)
    remote_lex = page.evaluate("async (t) => { const r = await fetch('/api/emotion',"
                               "{method:'POST',headers:{'Content-Type':'application/json'},"
                               "body:JSON.stringify({text:t})}); return (await r.json()).lex.emotion; }", probe)
    check("W6 词典层双端一致（JS 引擎 == /api/emotion）", loc == remote_lex and bool(loc),
          f"local={loc} backend={remote_lex}")

    # W5 降级：拦掉 /api/emotion ⇒ 熔断 + 回复照常 + 不冒充后端
    page.evaluate("() => window.EmotionRemote.reset()")
    page.route("**/api/emotion", lambda r: r.abort())
    meta2 = send(page, "突然有点生气，说不上来的烦")
    st2 = page.evaluate("() => window.EmotionRemote.stats()")
    down = page.evaluate("() => window.EmotionRemote.isDown()")
    reply_ok = len(meta2.strip()) > 20 and "情绪:后端" not in meta2
    check("W5 不可达即熔断且不伪装在线", down and st2.get("failed", 0) >= 1 and reply_ok,
          f"down={down} stats={st2} meta_tail={meta2[-60:]}")

    # W3b 危机短路实测：后端可用时也不得为网络等待——本地词典命中即拦截
    page.unroute("**/api/emotion")
    page.evaluate("() => window.EmotionRemote.reset()")
    meta3 = send(page, "我不想活了，活着真的没有意义", timeout=30000)
    st3 = page.evaluate("() => window.EmotionRemote.stats()")
    check("W3b 危机拦截即时（短路计数≥1 且未发起后端请求）",
          st3.get("crisisShortCircuit", 0) >= 1 and ("危机" in meta3 or "求助" in meta3 or "热线" in meta3),
          f"stats={st3} meta_tail={meta3[-70:]}")
    page.close()
    return errs


def selftest():
    """判据非恒真自证：三类篡改样本必须各自报红，原样必须零问题。"""
    html0 = read(SRC / "index.html")
    agent0 = read(SRC / "js" / "chat-agent.js")
    cfg0 = read(SRC / "js" / "demo-config.js")
    remote0 = read(SRC / "js" / "emotion-remote.js")
    bad = []
    if static_wiring(html0, agent0, cfg0):
        bad.append(f"原样文本被判为有问题：{static_wiring(html0, agent0, cfg0)}")
    if static_wiring(html0.replace('js/emotion-remote.js', 'js/nope.js'), agent0, cfg0):
        pass
    else:
        bad.append("篡改样本①（删 remote 引入）未被抓到 —— W1 恒真")
    if static_wiring(html0, agent0.replace("EmotionRemote.classifyWithBackend", "zzz"), cfg0):
        pass
    else:
        bad.append("篡改样本②（编排改道被抹掉）未被抓到 —— W1 恒真")
    if crisis_shortcircuit(remote0):
        pass
    else:
        bad.append("原样危机顺序被判失败")
    moved = remote0.replace("if (lex.crisis) {", "if (false) {", 1)
    if crisis_shortcircuit(moved) is False:
        pass
    else:
        bad.append("篡改样本③（危机短路被挪走）未被抓到 —— W3 恒真")
    if "emotionRemote" in read(PUB / "js" / "demo-config.js"):
        bad.append("公网副本居然含 emotionRemote —— W2 真红")
    print("SELFTEST-PASS: 3 类篡改全部被抓到、原样零问题" if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())

    w1_w3()
    if not jar_up():
        print("EMOTION-WIRING-ENV-ERROR: fat jar 未在 8123 运行（先起服务再跑本判据）")
        return 2
    if not emotion_api_ok():
        print("EMOTION-WIRING-ENV-ERROR: /api/emotion 不可用（jar 构建过旧？重新 mvn package）")
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"EMOTION-WIRING-ENV-ERROR: playwright 不可用 {e}")
        return 2
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="msedge")
        errs = e2e(browser)
        browser.close()
    check("W7 全程零 pageerror", not errs, "; ".join(errs[:3]))

    bad = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(bad)} 项")
    for n, _, d in bad:
        print("  🔴", n, d)
    print("EMOTION-WIRING-PASS" if not bad else "EMOTION-WIRING-FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
