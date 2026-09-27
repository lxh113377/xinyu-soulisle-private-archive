# -*- coding: utf-8 -*-
"""公网版验收：评委打开即在线AI（走服务端代理），密钥零暴露，console 0

用法：默认测 Cloudflare Pages；测国内 CloudBase 版传环境变量 XINYU_URL
  $env:XINYU_URL='https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com/'; python _test/public_check.py
"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

URL = os.environ.get("XINYU_URL", "https://xinyu-soulisle.pages.dev/")
print("TARGET_URL:", URL)
errors = []
bad_res = []
with sync_playwright() as p:
    try:
        b = p.chromium.launch()
    except Exception:
        b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("response", lambda r: bad_res.append((r.status, r.url)) if r.status >= 400 else None)
    pg.goto(URL, wait_until="networkidle")
    # CloudBase 测试域名首访有「风险提醒」中间页（官方无免备案开关），自动点一次放行；
    # pages.dev 无中间页，此步自动跳过。
    passed_middle = False
    if "风险提醒" in pg.title():
        passed_middle = True
        pg.wait_for_timeout(2600)          # 按钮有 2s 倒计时
        pg.click("text=确定访问")
        pg.wait_for_timeout(2500)
        print("PASSED_MIDDLE_PAGE: True")

    title = pg.title()
    badge = pg.inner_text("#mode-badge")
    strip = pg.evaluate("() => !document.getElementById('demo-strip').hidden")
    # 前端源码零密钥
    src = pg.content()
    key_leak = "sk-900f92ac" in src or "876826a89d990d8d" in src

    # 双路情绪读数走 proxy（在线）；探针已并入底部对话坞
    pg.fill("#chat-input", "论文被导师打回来改了四遍，我真的撑不住了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    probe = pg.inner_text("#probe-result")

    # 在线对话（走 /api/chat）
    pg.fill("#chat-input", "室友保研了我还在二战，心里特别不是滋味")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    tags = pg.eval_on_selector_all(".msg.ai .tag", "els => els.map(e=>e.textContent)")
    last_tag = tags[-1] if tags else ""

    # 危机词
    pg.fill("#chat-input", "不想活了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(8000)
    probe2 = pg.inner_text("#probe-result")
    # r56 证据面：在线标签缺失时，**在页面里**补发一次同源 POST，把上游响应体取进失败文案。
    # 两条弯路都实测踩过并写在这儿免得再绕：
    #   ① 另起 urllib 直连 ⇒ Cloudflare 回 403 "error code: 1010"（非浏览器客户端被挡，r54 同族）
    #   ② 在 response 事件回调里读 text() ⇒ 同步 API 会卡在分发里
    # 正解是页内 fetch：同客户端同域，拿得到正文。断言阈值一字未动。
    quota_probe = "<未触发>"
    if "在线大模型生成" not in last_tag:
        try:
            quota_probe = pg.evaluate("""async () => {
              const r = await fetch('api/chat', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({messages: [{role: 'user', content: '在吗'}], max_tokens: 4})});
              return 'http=' + r.status + ' body=' + (await r.text()).slice(0, 96);
            }""")
        except Exception as e:
            quota_probe = "<页内探测失败 %s>" % type(e).__name__
    b.close()

print("TITLE:", title)
print("BADGE:", badge, "| STRIP:", strip, "| KEY_LEAK:", key_leak)
print("PROBE:", probe.replace("\n"," ")[:160])
print("CHAT_TAG:", last_tag[:160])
print("CRISIS:", "危机" in probe2)
print("CONSOLE_ERRORS:", len(errors), errors[:5])

assert "心屿" in title
assert "在线 AI" in badge, "公网版评委应看到在线AI（proxy）"
assert strip, "体验条应显示（proxy模式）"
assert not key_leak, "🔴 前端源码泄露密钥"
assert "LLM" in probe and "词典" in probe, "双路情绪读数未生效"
_red = quota_probe.split("sk-")[0] + ("sk-<已脱敏>" if "sk-" in quota_probe else "")
assert "在线大模型生成" in last_tag, ("对话未走在线（proxy）｜tag=%s｜console=%s｜同源直连=%s"
                                    % (last_tag[:90] or "<空>", (errors or ["<无>"])[0][:90], _red))
assert "危机" in probe2, "危机拦截失效"
# 中间页机制：CloudBase 测试域名首访那次导航本身返回 404（平台行为），
# 但**除该根路径外的任何 4xx/5xx 都算失败** —— 过滤必须有边界，不能掩盖真缺陷。
bad_non_root = [(s, u) for s, u in bad_res if u.rstrip("/") != URL.rstrip("/")]
assert not bad_non_root, f"除中间页根路径外仍有失败请求: {bad_non_root}"
real_errors = errors if not passed_middle else [e for e in errors if "status of 404" not in e]
assert len(real_errors) == 0, f"console 报错: {real_errors}"
print("PUBLIC-ONLINE-ALL-PASS")
