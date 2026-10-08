# -*- coding: utf-8 -*-
"""公网版验收：评委打开即在线AI（走服务端代理），密钥零暴露，console 0

用法：默认测 Cloudflare Pages；测国内 CloudBase 版传环境变量 XINYU_URL
  $env:XINYU_URL='https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com/'; python _test/public_check.py
r100 起支持：python _test/public_check.py [--nav-timeout N]（`--nav-timeout 1` 逼出真实导航超时）

退出码（r100 三态纪律；原实现只有裸 assert ⇒ 实际是「0」与「traceback 崩」两态）：
  0=全绿 ｜ 1=判红（含未验腿与仪器兜底腿 PX）｜ 2=环境未验（playwright/浏览器不可达）
  原形态的一手代价有两条，都写在这儿免得再绕：
    ① `assert` 失败时抛 AssertionError，电池按"只留最后一行含判据词的 stdout"折叠后
       这条套件在 CI 里等于**没有结论行**；
    ② 导航层 TimeoutError 直接逃出进程 ⇒ rc=1 而无原因（在册叫「无原因判红」）。
  腿名册 LEGS 是唯一分母：任何一条没被记录 ⇒ 记未验并在结论行点名（禁把"没验"读成"验过且绿"）。
"""
import io
import os
import sys

URL = os.environ.get("XINYU_URL", "https://xinyu-soulisle.pages.dev/")

# 腿名册（顺序即执行顺序；P0 是 r100 新增的「导航可达」腿——把"公网挂了"与"判据崩了"分开）。
LEGS = ("P0 导航可达（goto 未超时未报错）",
        "P1 标题含「心屿」",
        "P2 徽章=在线 AI（评委打开即在线，不是离线模板）",
        "P3 体验条显示（proxy 模式）",
        "P4 前端源码零密钥",
        "P5 双路情绪读数（词典 + LLM 同屏）",
        "P6 对话走在线（/api/chat 代理）",
        "P7 危机词拦截",
        "P8 除中间页根路径外零 4xx/5xx",
        "P9 console 零报错")


def _why(e):
    return "%s: %s" % (type(e).__name__, str(e).splitlines()[0][:90])


def read_static(pg):
    """页面静态读数四项（标题 / 徽章 / 体验条 / 下发正文）。异常由调用方折成腿判红。"""
    return {"title": pg.title(),
            "badge": pg.inner_text("#mode-badge"),
            "strip": pg.evaluate("() => !document.getElementById('demo-strip').hidden"),
            "src": pg.content()}


def drive_chat(pg):
    """三轮真 UI 对话：双路情绪读数 → 在线生成 → 危机词。返回三处读数原文。"""
    pg.fill("#chat-input", "论文被导师打回来改了四遍，我真的撑不住了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    probe = pg.inner_text("#probe-result")
    pg.fill("#chat-input", "室友保研了我还在二战，心里特别不是滋味")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(12000)
    tags = pg.eval_on_selector_all(".msg.ai .tag", "els => els.map(e=>e.textContent)")
    pg.fill("#chat-input", "不想活了")
    pg.click("#chat-form button[type=submit]")
    pg.wait_for_timeout(8000)
    return probe, (tags[-1] if tags else ""), pg.inner_text("#probe-result")


def quota_probe(pg):
    """r56 证据面：在线标签缺失时，**在页面里**补发一次同源 POST，把上游响应体取进失败文案。
    两条弯路都实测踩过：① 另起 urllib 直连 ⇒ Cloudflare 回 403 "error code: 1010"（非浏览器
    客户端被挡，r54 同族）；② 在 response 事件回调里读 text() ⇒ 同步 API 会卡在分发里。
    正解是页内 fetch：同客户端同域，拿得到正文。断言阈值一字未动。"""
    try:
        return pg.evaluate("""async () => {
          const r = await fetch('api/chat', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({messages: [{role: 'user', content: '在吗'}], max_tokens: 4})});
          return 'http=' + r.status + ' body=' + (await r.text()).slice(0, 96);
        }""")
    except Exception as e:
        return "<页内探测失败 %s>" % type(e).__name__


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("TARGET_URL:", URL)
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("PUBLIC-CHECK-ENV-UNVERIFIED playwright 不可用 %s" % _why(e))
        return 2

    errors, bad_res = [], []
    seen, fails, unv = set(), [], []
    nav_to = 30000
    if "--nav-timeout" in sys.argv:
        nav_to = int(sys.argv[sys.argv.index("--nav-timeout") + 1])

    def ck(name, cond, info=""):
        seen.add(name)
        print(("  PASS  " if cond else "  FAIL  ") + name + (f"  -> {info}" if info else ""))
        if not cond:
            fails.append(name)

    def ck_unv(name, why):
        seen.add(name)
        print("  UNV   " + name + "  -> " + why)
        unv.append(name)

    def report():
        for n in LEGS:
            if n not in seen:
                ck_unv(n, "执行流未到达该腿（前置腿之后中断）")
        print("\nFAILS:", fails if fails else "无")
        print("UNVERIFIED:", unv if unv else "无")
        bad = bool(fails or unv)
        # 结论行保留在册 token `PUBLIC-ONLINE-ALL-PASS`（CONTRIBUTING.md / SECURITY.md /
        # pull_request_template.md / AGENTS.md 的 AC-OBS-11 都按它取证，不得改名），并按 r40b
        # 口径把计数**折进同一行**——电池对每条套件只留最后一行含判据词的 stdout。
        print("PUBLIC-ONLINE-" + ("FAIL 判红=%d 未验=%d 腿名册=%d"
                                  % (len(fails), len(unv), len(LEGS)) if bad
                                  else "ALL-PASS 判红=0 未验=0 腿名册=%d" % len(LEGS)))
        return 1 if bad else 0

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e_first:
            try:
                b = p.chromium.launch(channel="msedge")
            except Exception as e:
                print("PUBLIC-CHECK-ENV-UNVERIFIED 浏览器不可达（chromium/msedge 双档均败）%s ｜ %s"
                      % (_why(e_first), _why(e)))
                return 2
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("response", lambda r: bad_res.append((r.status, r.url)) if r.status >= 400 else None)

        # P0：导航是**浏览器层**动作。原实现让它裸奔 ⇒ 公网挂了/超时 = traceback = 无原因判红。
        # 折成判红而非未验是有意的：公网主推面打不开正是本套件存在的理由；环境档由上面两出口 return 2。
        try:
            pg.goto(URL, wait_until="networkidle", timeout=nav_to)
            ck("P0 导航可达（goto 未超时未报错）", True,
               "timeout=%dms title=%s" % (nav_to, (pg.title() or "")[:24]))
        except Exception as e:
            ck("P0 导航可达（goto 未超时未报错）", False, "浏览器层导航异常 %s" % _why(e))
            try:
                b.close()
            except Exception:                       # noqa: BLE001
                pass
            return report()

        # CloudBase 测试域名首访有「风险提醒」中间页（官方无免备案开关），自动点一次放行；
        # pages.dev 无中间页，此步自动跳过。
        passed_middle = False
        if "风险提醒" in pg.title():
            passed_middle = True
            pg.wait_for_timeout(2600)          # 按钮有 2s 倒计时
            pg.click("text=确定访问")
            pg.wait_for_timeout(2500)
            print("PASSED_MIDDLE_PAGE: True")

        try:
            s = read_static(pg)
        except Exception as e:
            ck("P1 标题含「心屿」", False, "读数层异常 %s" % _why(e))
            return report()
        print("TITLE:", s["title"])
        # `KEY_LEAK: False` 这行是在册对外契约（同上四处取证），不得改名。
        key_leak = "sk-900f92ac" in s["src"] or "876826a89d990d8d" in s["src"]
        print("BADGE:", s["badge"], "| STRIP:", s["strip"], "| KEY_LEAK:", key_leak)
        ck("P1 标题含「心屿」", "心屿" in s["title"], s["title"][:40])
        ck("P2 徽章=在线 AI（评委打开即在线，不是离线模板）", "在线 AI" in s["badge"],
           s["badge"].strip()[:40])
        ck("P3 体验条显示（proxy 模式）", bool(s["strip"]),
           "demo-strip.hidden=%s" % (not s["strip"]))
        # 零密钥扫描面取**页面实际下发**的正文（评委看到的就是这一份）。
        ck("P4 前端源码零密钥", not key_leak,
           "页面正文 %d 字节，命中密钥片段=%s" % (len(s["src"]), key_leak))

        try:
            probe, last_tag, probe2 = drive_chat(pg)
        except Exception as e:
            ck("P5 双路情绪读数（词典 + LLM 同屏）", False, "交互层异常 %s" % _why(e))
            return report()
        qp = "<未触发>" if "在线大模型生成" in last_tag else quota_probe(pg)
        try:
            b.close()
        except Exception as e:                       # noqa: BLE001
            print("  （浏览器关闭失败 %s，不影响判据）" % _why(e))

    _red = qp.split("sk-")[0] + ("sk-<已脱敏>" if "sk-" in qp else "")
    print("PROBE:", probe.replace("\n", " ")[:160])
    print("CHAT_TAG:", last_tag[:160])
    print("CRISIS:", "危机" in probe2)
    print("CONSOLE_ERRORS:", len(errors), errors[:5])
    ck("P5 双路情绪读数（词典 + LLM 同屏）", "LLM" in probe and "词典" in probe,
       "probe=%s" % probe.replace("\n", " ")[:60])
    ck("P6 对话走在线（/api/chat 代理）", "在线大模型生成" in last_tag,
       "tag=%s｜console=%s｜同源直连=%s"
       % (last_tag[:90] or "<空>", (errors or ["<无>"])[0][:90], _red))
    ck("P7 危机词拦截", "危机" in probe2, probe2.replace("\n", " ")[:60])
    # 中间页机制：CloudBase 测试域名首访那次导航本身返回 404（平台行为），
    # 但**除该根路径外的任何 4xx/5xx 都算失败** —— 过滤必须有边界，不能掩盖真缺陷。
    bad_non_root = [(st, u) for st, u in bad_res if u.rstrip("/") != URL.rstrip("/")]
    ck("P8 除中间页根路径外零 4xx/5xx", not bad_non_root, str(bad_non_root[:2]))
    real_errors = errors if not passed_middle else [e for e in errors if "status of 404" not in e]
    ck("P9 console 零报错", not real_errors, str(real_errors[:2]))
    return report()


def guarded_main():
    """r100：判据的失败路径自己不能崩，也不能崩掉结论行。未预期异常逃出 main 时电池只看到
    rc=1 而拿不到任何 PUBLIC-ONLINE-* 行 ⇒ 与真红同形（在册：证据格式化代码也会崩）。"""
    try:
        return main()
    except SystemExit:
        raise
    except BaseException as e:                       # noqa: BLE001
        print("  FAIL  PX 判据自身未崩溃  -> 未预期异常 %s" % _why(e))
        print("PUBLIC-ONLINE-FAIL 判红=1 条 PX（仪器自身异常；上行之前是本异常前已判定项）")
        return 1


if __name__ == "__main__":
    sys.exit(guarded_main())
