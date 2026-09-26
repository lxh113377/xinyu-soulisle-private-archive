# -*- coding: utf-8 -*-
"""在线模式全链路回归：体验模式徽章 + 双路情绪探针 + 在线对话 + 危机拦截 + console 0 报错"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

errors = []


def last_ai_state(pg):
    """一次求值取回 [气泡数, 最后一条正文, 最后一条自己的 tag]。

    必须从**最后一条 .msg.ai 内部**取 tag：早先写成 `querySelectorAll('.msg.ai .tag')[-1]`，
    新气泡还没渲染出 tag 时会拿到**上一条气泡**的 tag（本机开场白），于是 4ms 就"落定"，
    读到的是空气泡 ⇒ 又是一次假红（本轮第二次实测）。
    """
    return pg.evaluate(
        "() => { const els = Array.from(document.querySelectorAll('.msg.ai'));"
        " const last = els[els.length - 1];"
        " const tg = last ? last.querySelector('.tag') : null;"
        " return [els.length, last ? last.innerText.trim() : '',"
        "         tg ? tg.textContent.trim() : '']; }")


def wait_done(pg, n_before, timeout_ms=60000, require_stream_tag=True):
    """轮询到"这一轮真的落定"：气泡数比点击前多、最后一条正文非空、（若要求）其自身 tag 已落定。

    返回 (settled, waited_ms, last_tag)。超时**不抛**——判红的权利留给调用方的断言，
    但等待事实会打印出来：否则"没等够"会被后人读成"产品坏了"。
    完成态判据（三条同时成立）替代固定 sleep：本轮实测固定 12s 会读到"逐字生成中…"中间态。
    """
    import time
    t0 = time.time()
    tag = ""
    while (time.time() - t0) * 1000 < timeout_ms:
        cnt, text, tag = last_ai_state(pg)
        done = cnt > n_before and bool(text)
        if done and require_stream_tag:
            done = bool(tag) and "逐字生成中" not in tag
        if done:
            return True, int((time.time() - t0) * 1000), tag
        pg.wait_for_timeout(400)
    return False, int((time.time() - t0) * 1000), tag


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
    n1 = pg.eval_on_selector_all(".msg.ai", "els => els.length")
    pg.click("#chat-form button[type=submit]")
    # 等待必须取**被等对象的完成态**，不是"我自己睡一觉"：流式回复的收尾标志是最后一条
    # AI 消息的 tag 从"逐字生成中…"换成落定文案。固定 sleep 在慢一点的上游上会读到中间态
    # （本轮实测就是这样红的：CHAT_TAG: 逐字生成中…），而那读的是**网络**不是产品。
    w1 = wait_done(pg, n1)
    probe = pg.inner_text("#probe-result")

    # 3) 在线对话：真实 LLM 回复 + 双路标签
    pg.fill("#chat-input", "室友保研了我还在二战，心里特别不是滋味")
    n2 = pg.eval_on_selector_all(".msg.ai", "els => els.length")
    pg.click("#chat-form button[type=submit]")
    w2 = wait_done(pg, n2)
    tags = pg.eval_on_selector_all(".msg.ai .tag", "els => els.map(e=>e.textContent)")
    last_tag = tags[-1] if tags else ""

    # 4) 危机词仍走转介（双路不破坏安全边界）：危机不经上游，落定即出，只需等气泡出现
    pg.fill("#chat-input", "感觉活着好累，不想活了")
    n3 = pg.eval_on_selector_all(".msg.ai", "els => els.length")
    pg.click("#chat-form button[type=submit]")
    w3 = wait_done(pg, n3, require_stream_tag=False)
    msgs = pg.eval_on_selector_all(".msg.ai", "els => els.map(e=>e.textContent)")
    crisis_ok = any("12356" in m for m in msgs)

    # 5) 清除配置按钮：体验模式可退出
    pg.click("#btn-demo-clear")
    badge_after = pg.inner_text("#mode-badge")

    b.close()

print("WAIT: probe=%s chat=%s crisis=%s (settled,ms)" % (w1[:2], w2[:2], w3[:2]))
print("BADGE:", badge, "| STRIP:", strip_visible, "| ENGINE:", engine)
print("PROBE:", probe.replace("\n", " ")[:200])
print("CHAT_TAG:", last_tag[:160])
print("CRISIS_OK:", crisis_ok)
print("BADGE_AFTER_CLEAR:", badge_after)
print("CONSOLE_ERRORS:", len(errors), errors[:5])

# 失败面必须自带**分类**：本轮整跑红过一次，收口只有 `CONSOLE_ERRORS: 2`，
# 看不出错在哪个对象 ⇒ 归因多花了一轮。现在按"网络类 / 产品类"分开点名，
# 两类都仍判红（不放宽），只是让读的人一眼知道该去看上游还是去看代码。
NETISH = ("net::ERR_", "ERR_CONNECTION", "ERR_NAME_NOT_RESOLVED", "ERR_TIMED_OUT",
          "ERR_INTERNET_DISCONNECTED", "502", "503", "504")
net_err = [e for e in errors if any(k in e for k in NETISH)]
prod_err = [e for e in errors if e not in net_err]
if net_err:
    print("CONSOLE_CLASS: 网络类 %d 条（样本 %r）｜产品类 %d 条"
          % (len(net_err), net_err[0][:70], len(prod_err)))

assert "在线 AI" in badge, "体验模式徽章未生效"
assert strip_visible, "体验模式提示条未显示"
assert "LLM" in probe and "词典" in probe, "双路情绪读数未生效"
assert w2[0] and "在线大模型生成" in last_tag, f"对话未走在线模型或未落定: wait={w2[:2]}"
assert "情绪双路" in last_tag, f"对话缺双路证据标签: wait={w2[:2]} tag={last_tag[:60]}"
assert w3[0] and crisis_ok, f"危机转介失效或未落定: wait={w3[:2]}"
assert "离线" in badge_after, "清除配置未退出体验模式"
assert len(errors) == 0, (f"console 报错: 网络类={len(net_err)} 产品类={len(prod_err)} "
                          f"样本={errors[:3]}")
print("ONLINE-ALL-PASS")
