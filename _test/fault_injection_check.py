# -*- coding: utf-8 -*-
"""故障注入判据（r51 新增）—— 把上游打挂，看界面**说的是不是真话**。

为什么是这一面：十二份对标报告里，故障注入/错误可见性**从没被量过**
（✅ 取证：`grep -lEi "故障注入|错误可见|error boundary|错误监控|Sentry|错误上报|可观测"` 的命中
 排除掉各报告自己写的"这组 0 命中"声明行后，只剩 09-24 一句建议
 「4. 错误监控（Sentry 免费版；先靠 CI 兜底）」—— 而 `grep Sentry memory/07*` 为空
 ⇒ 那条建议既没做也没挂账，就地蒸发了。这正是本仓"建议必须有归宿"的同族缺口）。
选它的另一个理由：这是**演示现场唯一不可控的变量**（评委手机热点抖动）。

开轮实测（修前，route 注入四类故障）：
  500 / 非 JSON / 断连 三类：回落正确、气泡如实写「大模型暂不可用 · 离线共情模板」
  ⇒ **但全局徽章仍停在「● 在线 AI」**：同一屏两句话互相打脸，且撞本仓红线"禁伪装在线"
  挂起型：`LLM_TIMEOUT_MS=60000` ⇒ 气泡自己印出 **60,604ms** 才降级（现场等于死掉一分钟）
修后实测：徽章随故障翻成「● 大模型暂不可用（已降级本机模板）」、一次成功后翻回「● 在线 AI」；
超时 15s 后挂起型 **15,748ms** 降级（3.9× 改善）。四类故障 pageerror 恒 0。

判据（F1–F5 阻断，F0 环境）：
  F1 上游 500 ⇒ 界面出现降级标注 + 徽章不得仍称"在线 AI" + 输入框可用
  F2 响应体非 JSON（200）⇒ 同上（真实形态：网关吐 HTML 错误页）
  F3 连接被断（abort）⇒ 同上
  F4 挂起不返回 ⇒ 必须在 **≤ 25s** 内出现兜底（不是"最终会好"，是"多快好"）
  F5 故障后一次成功 ⇒ 徽章必须**翻回**在线（否则我只是把开关焊死在另一个方向）
  F6 全程 pageerror 必须为 0（降级路径自己崩了是最坏形态）
  F7 半开流（**响应头已到、体永不发**）⇒ 同样吃 25s 预算。它与 F4 的区别就是缺陷本体：
     黑洞不回任何字节，首包定时器管得住；头一旦到达，旧实现的定时器即被解除，
     此后 readSSE/res.json() 完全无界（r64 实测：界面永停「正在感受」、徽章谎称在线、该句静默丢失）。
     首次真跑曾被**自己的夹具**骗过一遍（跨源缺 CORS 头 ⇒ 浏览器 4ms 就 Failed to fetch），
     故本文件把"夹具真打到了那条路径"写成硬前置：见 half_open_stream 文档与 hit_count 纪律。
⚠️ 取数纪律：每条 case 都带 `hit_count`（注入通道被打到几次）。
   **`hit_count==0` 时该 case 判 INVALID 而不是 PASS** —— r51 首版探针用了不存在的 `#chat-send`，
   消息根本没发出去，却报出"0.0s 恢复、无异常"的漂亮假读数（无效夹具第 6 次，见 selftest 边界 B）。
用法：python _test/fault_injection_check.py [--base http://127.0.0.1:8123] [--json] [--selftest]
退出码：0=全过 1=判红 2=环境未验证（服务/浏览器不可达 ⇒ 不判绿）
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ("**/*chat/completions*", "**/api/chat*")
HANG_BUDGET_S = 25.0          # F4：挂起型兜底上界。修前 60.6s → r51 改 15s 超时后 30.2s
#    → r52 归因（两腿各吃满一个熔断、串行相加）后给分类腿单独 6s ⇒ 实测 **21.3s**（=6+15+0.3 轮询粒度）。
#    预算 = 实测上界 + 17% 余量（与 r51 定 35s 时同一把尺：30.2 → 35）。
#    ⚠️ 收紧的前提是**机制已归因**：未归因前不得抬/压这条线（r51 §5-P1-2 挂了一轮就是这个原因）。
FINGERPRINT = "先坐下歇会儿"      # recover 用例的正对照指纹（必须出现在 GOOD_BODY 里）
GOOD_BODY = ('{"choices":[{"message":{"content":"听起来今天真的把你累坏了，先坐下歇会儿。"}}],'
             '"usage":{}}')
CASES = ("http500", "garbage", "abort", "hang", "stalled_stream", "recover")
CFG_KEY = "peiliao.cfg.v1"          # 与 src/js/chat-agent.js 同源，改键必须两处同改
HANG_WAIT_S = HANG_BUDGET_S + 14.0  # 黑洞用例的等待窗（客户端 15s 超时 ⇒ 25s 预算内应见兜底）
# r65：半开流与黑洞**共用同一条 25s 兜底预算**（不另立第二把尺：两者对用户是同一件事——"等多久"）。
# 实测两条路径的构成不同但同界：黑洞 = classify 腿 6s + reply 腿 15s；
# 半开流 = classify 腿落到 BODY_IDLE_MS 6s + reply 腿首包 15s。
LOCAL_INJECT = ("hang", "stalled_stream")   # 这两类走真 socket，不经 route 回调（见 black_hole 文档）


def black_hole():
    """真·挂起：accept 后一个字节都不回。

    为什么不用 route 回调里 time.sleep(400)：playwright **同步 API 的回调跑在分发绿点上**，
    睡 400s 会把分发循环一起占住 ⇒ 我自己的轮询取数也拿不到结果，读数是 None 而不是"慢"。
    那等于用坏夹具去测产品（本轮实测踩过）。黑洞服务器还给一个诚实的 hit：连接被 accept 几次。

    ⚠️ r52 改：hit 从「连接数」改成**请求数**（`POST ` 出现次数）。原口径在 keep-alive 下
    把两条串行请求算成 1 次 accept，正是它让 r51 写出"只 accept 到 1 次 ⇒ 30.2s 无法归因"——
    不是机制神秘，是**计数单位取错了**（同族：R268 度量对象错）。
    """
    import socket
    import threading
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    port, box = srv.getsockname()[1], {"n": 0, "conn": 0, "buf": b""}

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except Exception:
                return
            box["conn"] += 1

            def serve(conn):
                conn.settimeout(None)
                try:
                    while True:
                        data = conn.recv(65536)
                        if not data:
                            return
                        box["buf"] += data
                        box["n"] = box["buf"].count(b"POST ")   # 只增不减：整条流的请求数
                except Exception:
                    return
            threading.Thread(target=serve, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv, port, box


def half_open_stream():
    """半开流：**响应头正常返回**，随后一个字节体都不发且连接不关。

    与 black_hole() 的分工（这条分工就是缺陷本体）：黑洞 accept 后不回任何字节 ⇒ 客户端的
    `await fetch()` 永不 resolve ⇒ **首包**超时管得住它。本注入器故意让 fetch() 立刻成功，
    于是"定时器在响应头到达时就被解除"的写法完全失效 —— 只有覆盖**响应体**的看门狗拦得住。
    r64 hunt 抓到的正是这一类，而当时 F4 全绿：不是判据松了，是它压根没测这条路径。
    """
    import socket
    import threading
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    port, box = srv.getsockname()[1], {"n": 0, "conn": 0}
    # ⚠️ 夹具坑（r65 一手，首次真跑被自己骗过一次）：注入器是**跨源**端口，浏览器对
    #    `Content-Type: application/json` 的 POST 先发 OPTIONS 预检；响应缺 CORS 头时
    #    Chromium 4ms 就抛 `TypeError: Failed to fetch` ⇒ 客户端"快速降级"，半开流根本没被测到，
    #    未修版照样判 PASS。黑洞注入器之所以没暴露这条，是因为它**一个字节都不回**，
    #    CORS 评估永不发生。判据的牙齿取决于夹具是否真打到了那条路径——先证夹具再下结论。
    pre = (b"HTTP/1.1 204 No Content\r\nAccess-Control-Allow-Origin: *\r\n"
           b"Access-Control-Allow-Methods: POST, OPTIONS\r\n"
           b"Access-Control-Allow-Headers: Content-Type\r\nAccess-Control-Max-Age: 600\r\n\r\n")
    hdr = (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\n"
           b"Access-Control-Allow-Origin: *\r\nTransfer-Encoding: chunked\r\n\r\n")

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except Exception:
                return
            box["conn"] += 1

            def serve(conn):
                conn.settimeout(None)
                try:
                    buf = b""
                    while True:
                        d = conn.recv(65536)
                        if not d:
                            return
                        buf += d
                        while b"\r\n\r\n" in buf:
                            head, buf = buf.split(b"\r\n\r\n", 1)
                            if head.startswith(b"OPTIONS"):
                                conn.sendall(pre)          # 放行预检，连接继续留着
                                continue
                            box["n"] += 1                  # 只数 POST：与 black_hole 同一计数口径
                            conn.sendall(hdr)              # 头给足，让 await fetch() resolve
                            time.sleep(600)                # 体永不发，也不关连接 = 半开
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
            threading.Thread(target=serve, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv, port, box


def js_state():
    return """() => {
      const msgs=[...document.querySelectorAll('#chat-log > *')];
      const last=msgs.length?msgs[msgs.length-1].innerText.replace(/\\s+/g,' ').slice(0,160):'';
      const inp=document.querySelector('#chat-input');
      const badge=document.querySelector('#mode-badge');
      return {n:msgs.length, last, badge: badge?badge.innerText.trim():'',
              disabled: !!inp && inp.disabled,
              thinking: !!document.querySelector('.thinking,.streaming')};
    }"""


def assess(cases):
    """纯函数：输入 = [{kind, hit_count, settled_s, badge, last, disabled, errors}]。
    selftest 直接打它；不碰浏览器也不碰本机服务，故反例注入是确定的。"""
    bad = []
    if not cases:
        return ["F0 零用例 ⇒ 分母为空，不判绿"], {}
    for c in cases:
        k = c.get("kind")
        if not c.get("hit_count"):
            bad.append("F-INVALID %s：注入通道未被打到（hit_count=0）⇒ 该读数不构成证据" % k)
            continue
        if k == "recover":
            if "在线 AI" not in c.get("badge", ""):
                bad.append("F5 成功后徽章未翻回在线：%r（开关被焊死在降级方向）" % c.get("badge"))
            continue
        txt = c.get("last", "") + " " + c.get("badge", "")
        if not any(w in txt for w in ("离线共情模板", "大模型暂不可用")):
            bad.append("F1-F4 %s：界面无降级标注，气泡尾标=%r" % (k, c.get("last", "")[-46:]))
        if "在线 AI" in c.get("badge", ""):
            bad.append("F1-F4 %s：徽章仍称「● 在线 AI」而本轮 LLM 未成功 ⇒ 伪装在线（红线）" % k)
        if c.get("disabled"):
            bad.append("F1-F4 %s：输入框停在 disabled，用户无法继续" % k)
        if k == "hang" and (c.get("settled_s") is None or c["settled_s"] > HANG_BUDGET_S):
            bad.append("F4 hang：兜底耗时 %s > %.0fs 预算（现场等于死掉）"
                       % (c.get("settled_s"), HANG_BUDGET_S))
        if k == "stalled_stream" and (c.get("settled_s") is None
                                      or c["settled_s"] > HANG_BUDGET_S):
            bad.append("F7 stalled_stream：响应头已到、体停滞 ⇒ 兜底耗时 %s（预算 %.0fs）。"
                       "首包定时器在头到达时就解除了，这一类只有覆盖响应体的看门狗拦得住"
                       % (c.get("settled_s"), HANG_BUDGET_S))
    rec = [c for c in cases if c.get("kind") == "recover"]
    if not rec:
        bad.append("F0 缺 recover 用例 ⇒ 没有『注入确实生效』的正对照，本判据不可信")
    elif rec[0].get("hit_count") and FINGERPRINT not in (rec[0].get("last") or ""):
        bad.append("F0 正对照失败：recover 未见 GOOD_BODY 指纹（%r）⇒ 注入器接线坏了，"
                   "所有故障读数作废（判夹具不判产品）" % (rec[0].get("last") or "")[:60])
    errs = sum(len(c.get("errors") or []) for c in cases)
    if errs:
        bad.append("F6 全程未捕获异常 %d 条：%s" % (errs, (cases[0].get("errors") or [""])[0][:80]))
    # F4b（r52 新增归因腿）：兜底总耗时超过**单腿**熔断预算的 1.5 倍时，必须观测到第二腿的发出时刻；
    # 否则只准登记"未归因"，不准写机制。r51 就是缺这条，才把 30.2s 挂成"归属未定"整整一轮。
    h = next((c for c in cases if c.get("kind") == "hang"), None)
    extra = {}
    if h and h.get("settled_s") is not None and h.get("timeout_s"):
        ts, ph = float(h["timeout_s"]), (h.get("phases") or [])
        # 分相**总是**算（只要观测到两条腿）：它是读数不是裁决，裁决只在"超出单腿预算却无第二腿"时判红。
        # 首版把计算塞进 `settled > 1.5×ts` 分支里 ⇒ 修快之后 PASS 行反而印不出归因（自废读数）。
        if len(ph) >= 2:
            gap = round((ph[1][0] - ph[0][0]) / 1000.0, 1)
            extra = {"hang_legs": len(ph), "hang_gap_s": gap,
                     "hang_explained_s": round(gap + ts, 1)}
        elif h["settled_s"] > ts * 1.5:
            bad.append("F4b hang：兜底 %.1fs > 单腿预算 %.0fs 的 1.5 倍，却只观测到 %d 次 fetch"
                       " ⇒ 多出的 %0.1fs **未归因**，本判据拒收未归因的解释"
                       % (h["settled_s"], ts, len(ph), h["settled_s"] - ts))
            extra = {"hang_legs": len(ph)}
    return bad, dict({"cases": len(cases),
                      "valid": sum(1 for c in cases if c.get("hit_count")),
                      "errors": errs}, **extra)


def llm_timeout_s():
    """从**权威源**取单腿熔断预算（不抄常量：抄了就会和 chat-agent.js 漂移）。
    取不到 → 0，assess 的 F4b 分支随即跳过（宁可不判，也不拿猜想的预算去判红）。"""
    try:
        src = (ROOT / "src" / "js" / "chat-agent.js").read_text("utf-8", errors="replace")
    except Exception:
        return 0.0
    m = re.search(r"LLM_TIMEOUT_MS\s*=\s*(\d+)", src)
    return int(m.group(1)) / 1000.0 if m else 0.0


def run(base):
    from playwright.sync_api import sync_playwright

    def launch(pw):
        try:
            return pw.chromium.launch()
        except Exception:
            return pw.chromium.launch(channel="msedge")

    out = []
    with sync_playwright() as p:
        b = launch(p)
        for mode in CASES:
            hits, errs = [], []
            pg = b.new_page(viewport={"width": 1200, "height": 800})
            pg.on("pageerror", lambda e: errs.append(str(e)[:110]))

            # ⚠️ 夹具坑（本轮实测两次才修对）：playwright-python 会**按回调的参数个数**决定传几个实参。
            #    首版 `def handler(route, m=mode, st=...)` 三参数 ⇒ 收到 (route, request)，
            #    `m` 被 request 对象顶掉 ⇒ 五类故障全掉进 else 分支被喂了成功响应，
            #    判据随即报"四类故障都没降级、徽章都说在线"—— 那是**夹具坏了不是产品坏了**。
            #    闭包工厂只收 route，参数个数无歧义；配套的"recover 必须见 GOOD_BODY 指纹"正对照
            #    就是为这类事故准备的（它本轮确实把假读数拦住了）。
            def make(m, hs):
                def h(route):
                    hs.append(route.request.url[-30:])
                    if m == "http500":
                        route.fulfill(status=500, content_type="application/json",
                                      body='{"error":{"message":"upstream boom"}}')
                    elif m == "garbage":
                        route.fulfill(status=200, content_type="application/json",
                                      body="<html>gateway not json</html>")
                    elif m == "abort":
                        route.abort("connectionrefused")
                    elif m == "hang":
                        time.sleep(400)
                    else:
                        route.fulfill(status=200, content_type="application/json", body=GOOD_BODY)
                return h
            handler = make(mode, hits)
            for u in PATTERNS:
                pg.route(u, handler)
            rec = {"kind": mode}
            hole = None
            if mode in LOCAL_INJECT:
                hole = black_hole() if mode == "hang" else half_open_stream()
                # stream 位按用例分岔：黑洞测"对端理不理我"（整包即可）；
                # 半开流必须**走流式**才进得来 readSSE —— 那才是 r64 卡死的那条腿。
                st = "false" if mode == "hang" else "true"
                # 分相计时（r52 归因用）：把每次 fetch 的**发出时刻**记在页面内，
                # 于是"总耗时里多出来的那一段"要么落到某条腿上，要么当场承认没归因。
                pg.add_init_script(
                    "try{localStorage.setItem('%s',JSON.stringify({proxy:'http://127.0.0.1:%d/',"
                    "stream:%s}))}catch(e){}" % (CFG_KEY, hole[1], st))
                pg.add_init_script(
                    "window.__PH={calls:[]};"
                    "const _f=window.fetch;"
                    "window.fetch=function(u,o){try{window.__PH.calls.push("
                    "[Math.round(performance.now()),String(u).slice(-22)])}catch(e){};"
                    "return _f.apply(this,arguments);};")
            try:
                pg.goto(base + "/", wait_until="load", timeout=45000)
                pg.wait_for_timeout(2200)
                n0 = len(hits)
                pg.fill("#chat-input", "今天有点累，想被陪一会儿")
                pg.press("#chat-input", "Enter")
                t0 = time.monotonic()
                settled = None
                while time.monotonic() - t0 < (HANG_WAIT_S if mode == "hang" else 45):
                    st = pg.evaluate(js_state())
                    if st["n"] >= 3 and not st["thinking"] and not st["disabled"]:
                        settled = round(time.monotonic() - t0, 1)
                        rec.update({"badge": st["badge"], "last": st["last"],
                                    "disabled": st["disabled"]})
                        break
                    time.sleep(0.4)
                else:
                    st = pg.evaluate(js_state())
                    rec.update({"badge": st["badge"], "last": st["last"],
                                "disabled": st["disabled"], "settled_s": None})
                rec["settled_s"] = settled if settled is not None else rec.get("settled_s")
                rec["hit_count"] = (hole[2]["n"] if hole else len(hits) - n0)
                if hole:
                    rec["phases"] = pg.evaluate("() => (window.__PH||{calls:[]}).calls")
                    rec["conns"] = hole[2]["conn"]
                    rec["timeout_s"] = llm_timeout_s()
            except Exception as e:
                rec["env_err"] = str(e)[:110]
            finally:
                rec["errors"] = errs[:]
                if hole:
                    hole[0].close()
                pg.close()
            out.append(rec)
        b.close()
    return out


def selftest():
    ok, fail = 0, []
    good = {"http500": {"kind": "http500", "hit_count": 2, "settled_s": 0.6, "disabled": False,
                        "badge": "● 大模型暂不可用（已降级本机模板）",
                        "last": "…大模型暂不可用 · 离线共情模板 · 情绪：低落", "errors": []},
            "recover": {"kind": "recover", "hit_count": 2, "settled_s": 0.5, "disabled": False,
                        "badge": "● 在线 AI", "last": "听起来今天真的把你累坏了，先坐下歇会儿。 在线大模型生成 · 逐字流式", "errors": []}}
    base = [dict(good["http500"]), dict(good["recover"])]
    cases = [
        ("正例：故障有标注且徽章不谎称在线", base, False),
        ("反例①：徽章仍写「● 在线 AI」（r51 修前真实形状）",
         [dict(good["http500"], badge="● 在线 AI"), dict(good["recover"])], True),
        ("反例②：气泡无任何降级标注（静默伪装成功）",
         [dict(good["http500"], last="今天辛苦了，我懂你。", badge="● 已离线"),
          dict(good["recover"])], True),
        ("反例③：输入框卡在 disabled", [dict(good["http500"], disabled=True),
                                       dict(good["recover"])], True),
        ("反例④：挂起 60s 才兜底（修前 60.6s 形状）",
         [dict(good["http500"]), {"kind": "hang", "hit_count": 1, "settled_s": 60.6,
                                  "disabled": False, "badge": "● 大模型暂不可用（已降级本机模板）",
                                  "last": "离线共情模板", "errors": []}, dict(good["recover"])], True),
        ("反例⑤：有未捕获异常", [dict(good["http500"], errors=["TypeError: x"]),
                                 dict(good["recover"])], True),
        ("反例⑥：成功后徽章没翻回（开关焊死在另一侧）",
         [dict(good["http500"]), dict(good["recover"], badge="● 大模型暂不可用（已降级本机模板）")], True),
        # F4b（r52）：超过单腿预算 1.5 倍却没观测到第二腿 ⇒ 归因缺失必须判红。
        # 这正是 r51 挂了一整轮的那个形状：30.2s 被写成"归属未定"，因为**没人被要求**解释。
        ("反例⑦：30.2s 兜底但只见 1 次 fetch（未归因，r51 真实形状）",
         [dict(good["http500"]), {"kind": "hang", "hit_count": 1, "settled_s": 30.2,
                                  "disabled": False, "timeout_s": 15.0, "phases": [[120, "/api/"]],
                                  "badge": "● 大模型暂不可用（已降级本机模板）",
                                  "last": "离线共情模板", "errors": []}, dict(good["recover"])], True),
        ("正例②：21.3s 且两腿都有时刻（classify 腿 6.0s + reply 腿 15s ⇒ 已归因 21.0s）",
         [dict(good["http500"]), {"kind": "hang", "hit_count": 2, "settled_s": 21.3,
                                  "disabled": False, "timeout_s": 15.0,
                                  "phases": [[180, "/api/"], [6180, "/api/"]],
                                  "badge": "● 大模型暂不可用（已降级本机模板）",
                                  "last": "离线共情模板", "errors": []}, dict(good["recover"])], False),
        # 反例⑧：修快了不代表判据可以闭眼——**归因缺失**这一维在 25s 预算下仍须由 F4b 拦住：
        # 单腿 15s 却量到 24.5s（未超 25s 总预算，所以 F4 不报），必须靠"只见 1 条腿"报红。
        ("反例⑧：24.5s 兜底但只见 1 次 fetch（总预算内、归因缺失）",
         [dict(good["http500"]), {"kind": "hang", "hit_count": 1, "settled_s": 24.5,
                                  "disabled": False, "timeout_s": 15.0, "phases": [[180, "/api/"]],
                                  "badge": "● 大模型暂不可用（已降级本机模板）",
                                  "last": "离线共情模板", "errors": []}, dict(good["recover"])], True),
        # F7（r65）：半开流——头到了、体永不到。修前形状是**永远不收敛**（settled=None），
        # 而 F4 对它是绿的（黑洞注入器压根不触发这条路径），所以必须单列一类故障。
        ("反例⑨：stalled_stream 永不收敛（r64 修前真实形状：界面停在「正在感受」）",
         [dict(good["http500"]), {"kind": "stalled_stream", "hit_count": 2, "settled_s": None,
                                  "disabled": False, "badge": "● 在线 AI",
                                  "last": "心屿正在感受你的话…", "errors": []},
          dict(good["recover"])], True),
        ("正例③：stalled_stream 21.4s 收敛并如实降级",
         [dict(good["http500"]), {"kind": "stalled_stream", "hit_count": 2, "settled_s": 21.4,
                                  "disabled": False, "badge": "● 大模型暂不可用（已降级本机模板）",
                                  "last": "离线共情模板", "errors": []}, dict(good["recover"])], False),
    ]
    for name, cs, want in cases:
        bad, _s = assess(cs)
        got = bool(bad)
        if got == want:
            ok += 1
        else:
            fail.append("%s want_bad=%s got=%s bad=%s" % (name, want, got, bad))
    # 边界 A：零用例不得判绿
    bad, _s = assess([])
    ok += 1 if bad and "F0" in bad[0] else 0
    if not (bad and "F0" in bad[0]):
        fail.append("边界A 零用例未走 F0")
    # 边界 B：hit_count=0 的"漂亮读数"必须判 INVALID，不得当通过（r51 首版就吃过）
    bad, s = assess([{"kind": "http500", "hit_count": 0, "settled_s": 0.0, "disabled": False,
                      "badge": "● 在线 AI", "last": "本机开场白", "errors": []}])
    if bad and any("INVALID" in x for x in bad):
        ok += 1
    else:
        fail.append("边界B 未打到注入通道却判通过：%s" % bad)
    total = len(cases) + 2
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("FAULT-SELFTEST: %d/%d" % (ok, total))
    return 0 if ok == total else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    try:
        recs = run(a.base)
    except Exception as e:
        print("FAULT-ENV-ERROR: 浏览器/服务不可用 %s ⇒ 不判绿" % str(e)[:120])
        return 2
    if any(r.get("env_err") for r in recs) and all(r.get("env_err") for r in recs):
        print("FAULT-UNVERIFIED: 全部用例取数失败（%s）" % recs[0]["env_err"][:100])
        return 2
    bad, st = assess(recs)
    for x in bad:
        print("  · FAIL " + x)
    if a.json:
        print(json.dumps({"stats": st, "cases": recs, "problems": bad}, ensure_ascii=False)[:1800])
    if bad:
        print("FAULT-FAIL: %d 项（用例 %d，有效 %d）" % (len(bad), st["cases"], st["valid"]))
        return 1
    h = next((r for r in recs if r["kind"] == "hang"), {})
    print("FAULT-PASS: 注入 %d 类故障全部如实降级且徽章同帧（hang 兜底 %.1fs ≤ %.0fs 预算；"
          "分相：fetch %s 腿、两腿间隔 %ss、已归因 %.1fs／实测 %.1fs）｜"
          "输入框未卡死｜未捕获异常 %d 条｜hit_count 全非零（证明注入真打到通道）"
          % (st["cases"], h.get("settled_s") or -1, HANG_BUDGET_S,
             st.get("hang_legs", len(h.get("phases") or [])), st.get("hang_gap_s", "-"),
             st.get("hang_explained_s", -1), h.get("settled_s") or -1, st["errors"]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
