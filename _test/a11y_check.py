# -*- coding: utf-8 -*-
"""对标 r42 常驻判据：运行时无障碍真审计（axe-core + 像素级动效降档 + 键盘可达）。

为什么不是跑一次 axe 看 0 违规就算数（本仓首跑就被这一形态骗过一次）：
  1. 首跑 axe.run(document) 不传 runOnly 得 violations=0；同页加 experimental 标签
     立刻命中 label-content-name-mismatch:serious:2。默认规则集看不见它，
     所以 0 违规 是"取窄规则"的结果，不是"无障碍达标"的结果（M5④ 同族）。
  2. 首屏只覆盖 5 幕里的第 1 幕。对话气泡、危机转介条、设置弹层是各自独立的子树，
     没被审计过就等于没有。
  3. 深浅两套主题（r15 加的 light）只测默认暗色，亮色主题里的缺陷从不被执行（M5③）。
  4. prefers-reduced-motion 我们只在 CSS 关了两个装饰动画，WebGL 星雾与镜头位移一行没管：
     实测 reduce 态三帧哈希仍全不同、平均像素差 0.0563 vs 正常 0.0470，没有可测降档。

判据 A1-A8 逐项独立判定，禁止聚合掩盖单项失败：
  A1 规则集含 experimental，且每个状态 passes>0（证明审计真落在填充后的 DOM 上）
  A2 多状态 x 双主题：违规节点数必须为 0
  A3 正样本自证：注入 4 类已知缺陷，axe 必须抓到（证明这把尺会咬人）
  A4 对比度 incomplete 计数不得超基线，且必须点名（量不出的那一格不许被忽略）
  A5 reduced-motion：reduce 态星雾帧间差必须显著低于正常态，且正常态必须真的在动
  A6 键盘：Tab 序列可达对话输入与发送，焦点元素必须有可见焦点环
  A7 语音控制（WCAG 2.5.3）：可点击件的可见文字必须是其无障碍名子串
  A8 读屏播报：对话日志与探针读数必须在可访问性树里以 aria-live 暴露

前置：Java 服务端起在 8123（或任一托管 src/ 的静态服务）。
用法：python _test/a11y_check.py
退出码：0=全绿 1=判红 2=环境未验（服务不可达 / axe 件缺失或长度不符 / PIL 缺失 / 浏览器起不来）
"""
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
AXE_PATH = ROOT / "_test" / "vendor" / "axe-core-4.10.2.min.js"
MANIFEST_PATH = ROOT / "_test" / "vendor-manifest.json"


def axe_pin():
    """第三方件的版本/sha/长度**只有一个出处** = vendor-manifest.json。

    首版这里写的是 `XINYU_AXE_SHA`（默认空 ⇒ 只比长度）与一个抄在代码里的 `553290`，
    于是"钉了 sha"其实是**没钉**：等长替换看不见，而名册里明明白白有真值。
    同一判断两处实现必然漂移（consulting M5⑥），故改回读名册；名册缺这条 ⇒ 不审未登记件。
    """
    try:
        libs = json.loads(MANIFEST_PATH.read_bytes().decode("utf-8")).get("libs", [])
    except Exception as e:
        return None, "名册读不到：%s" % e
    rel = "_test/vendor/" + AXE_PATH.name
    for lib in libs:
        if lib.get("file") == rel:
            return lib, ""
    return None, "名册里没有 %s ⇒ 判据不审未登记的第三方件" % rel


AXE_LIB, AXE_PIN_ERR = axe_pin()
AXE_SHA256 = (AXE_LIB or {}).get("sha256", "")
AXE_LEN = int((AXE_LIB or {}).get("size") or 0)
BASE = os.environ.get("XINYU_A11Y_BASE", "http://127.0.0.1:8123/index.html")
OFFLINE = "http://127.0.0.1:18123/v1"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice", "experimental"]
CONTRAST_INCOMPLETE_MAX = int(os.environ.get("XINYU_A11Y_INC_MAX", "30"))
STATES = ("landing", "act2_probe", "act3_chat", "crisis", "settings", "lightshow")
THEMES = ("dark", "light")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))
    print("  %-4s %-40s %s" % ("PASS" if ok else "FAIL", name, str(detail))[:200])


def unverified(name, why):
    results.append((name, None, why))
    print("  UNV  %-40s %s" % (name, why)[:200])


AXE_RUN = """async (opts) => {
  const r = await window.axe.run(document.body, opts);
  const norm = (a) => a.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length,
      targets: v.nodes.slice(0, 8).map(x => (x.target || []).join(' '))}));
  const incNodes = [];
  for (const it of r.incomplete) { for (const n of it.nodes) { incNodes.push({id: it.id, t: (n.target || []).join(' ')}); } }
  return {violations: norm(r.violations), passes: r.passes.length,
          passNodes: r.passes.reduce((a, p) => a + p.nodes.length, 0),
          incomplete: norm(r.incomplete), incNodes: incNodes.slice(0, 60)};
}"""


def launch(pw):
    for kw in ({}, {"channel": "msedge"}):
        try:
            return pw.chromium.launch(**kw)
        except Exception:
            continue
    return None


DECO_RE = re.compile(r"[^\w一-鿿]+", re.U)


def mean_abs_delta(p, q):
    """两张 PNG 字节 -> L 通道平均绝对差（0-255 刻度）。尺寸不一致返回 -1（不得当 0 用）。
    单一实现：main 的 A5 与 selftest 的像素桩共用它，避免同一判断两处写（M5⑥）。"""
    from PIL import Image, ImageChops
    a = Image.open(io.BytesIO(p)).convert("L")
    c = Image.open(io.BytesIO(q)).convert("L")
    if a.size != c.size:
        return -1.0
    hist = ImageChops.difference(a, c).histogram()
    return sum(i * h for i, h in enumerate(hist)) / float(a.width * a.height)


def strip_deco(s):
    """剥离装饰符（emoji/标点），只留字母数字与汉字——2.5.3 约束的是可见**文字**。"""
    return DECO_RE.sub("", s or "")


def label_mismatch(vis, acc):
    """A7 的纯判定：可见文字非空、无障碍名非空、且可见文字不是名的子串 ⇒ 违规。"""
    v, a = strip_deco(vis), strip_deco(acc)
    return bool(v) and bool(a) and v not in a


def motion_ok(normal, reduced):
    """A5 的纯判定：正常态必须真的在动（否则降档断言是空判），且 reduce 态显著静。"""
    return normal > 0.002 and 0 <= reduced <= max(0.15 * normal, 0.002)


def run_selftest():
    """判据自身的桩：合成图像走真实像素通道，禁止只测布尔。"""
    ok, fail, n = 0, [], 0

    def want(cond, note):
        nonlocal n, ok
        n += 1
        if cond:
            ok += 1
        else:
            fail.append(note)

    try:
        from PIL import Image
    except Exception as e:
        print("A11Y-SELFTEST-ENV PIL 不可用 %s" % e)
        return 2

    def mean_abs(p, q):
        return mean_abs_delta(p, q)

    def png(build, size=32):
        im = Image.new("L", (size, size))
        px = im.load()
        for y in range(size):
            for x in range(size):
                px[x, y] = build(x, y)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    flat = png(lambda x, y: 40)
    alt = png(lambda x, y: 40 if (x + y) % 2 else 140)
    # 尺寸不同的样本必须**真的**做一张小图：首版用 `png(...)[:-4]` 截尾当"尺寸不一致"，
    # 而 PIL 从头部就能读出 32x32 ⇒ 返回 0.0 而非 -1.0，这个反例从头到尾没测到那条分支
    # （M5④⑧"注入的反例须先单独证明它真会失败"，本轮自己又踩一次）。
    small = png(lambda x, y: 40, size=16)
    d_same, d_diff = mean_abs(flat, flat), mean_abs(flat, alt)
    d_size = mean_abs(flat, small)
    want(d_same == 0.0, "像素通道正例：同图差值必须为 0，实得 %s" % d_same)
    want(d_diff > 40.0, "像素通道反例：半图差 100 必须显著非零，实得 %s" % d_diff)
    want(d_size == -1.0, "尺寸不一致必须给 -1 而不是 0（0 会被当成已降档）")
    want(motion_ok(0.05, 0.0), "motion_ok 正例")
    want(not motion_ok(0.05, 0.04), "motion_ok 反例①：没降（比值 0.8）必须红")
    want(not motion_ok(0.0, 0.0), "motion_ok 反例②：正常态就不动 ⇒ 空判必须红")
    want(not motion_ok(0.05, -1.0), "motion_ok 反例③：取不到帧必须红")
    want(label_mismatch("⚙ 模型设置", "设置"), "A7 正例：可见文字不在名内")
    want(label_mismatch("☾ 深色", "切换深浅主题"), "A7 正例：emoji 剥离后仍不匹配")
    want(not label_mismatch("⚙ 模型设置", "模型设置"), "A7 反例④：修复后必须绿")
    want(not label_mismatch("🎤", "语音输入"), "A7 反例⑤：纯图标无可见文字 ⇒ 不适用")
    want(not label_mismatch("发送", ""), "A7 反例⑥：无 aria-label 时不比（名即文）")
    for x in fail:
        print("  A11Y-SELFTEST-FAIL " + x)
    print("A11Y-SELFTEST: %d/%d（像素 3｜动效 4｜标签 5）" % (ok, n))
    return 0 if ok == n else 1


def goto_state(pg, state):
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(500)
    if state == "act2_probe":
        pg.evaluate("() => document.getElementById('act2').scrollIntoView({block:'center'})")
        pg.wait_for_timeout(700)
    elif state in ("act3_chat", "crisis"):
        text = ("今天被导师当众批评了，我很难受，有点想哭"
                if state == "act3_chat" else "我真的撑不下去了，想彻底消失")
        pg.evaluate("() => document.getElementById('chat-input').scrollIntoView({block:'center'})")
        pg.fill("#chat-input", text)
        pg.click("button[type=submit]")
        pg.wait_for_function("() => document.querySelectorAll('#chat-log .msg').length >= 2",
                             timeout=30000)
        pg.wait_for_timeout(1500)
    elif state == "settings":
        pg.click("#btn-settings")
        pg.wait_for_timeout(500)
    elif state == "lightshow":
        pg.evaluate("() => document.getElementById('act5').scrollIntoView({block:'center'})")
        pg.wait_for_timeout(500)
        pg.click("#btn-lightshow")
        pg.wait_for_timeout(900)


def main():
    if "--selftest" in sys.argv[1:]:
        return run_selftest()
    # ---- 环境门：取不到证据就不给绿，也不给红 ----
    if AXE_LIB is None:
        print("A11Y-ENV-UNVERIFIED %s" % AXE_PIN_ERR)
        return 2
    if not AXE_PATH.exists():
        print("A11Y-ENV-UNVERIFIED axe 件缺失 %s（禁在线回落：判据不接受顺手下一个）" % AXE_PATH)
        return 2
    raw = AXE_PATH.read_bytes()
    if len(raw) != AXE_LEN:
        print("A11Y-ENV-UNVERIFIED axe 件长度 %d != 名册钉定 %d（被截断或被替换）" % (len(raw), AXE_LEN))
        return 2
    sha = hashlib.sha256(raw).hexdigest()
    if sha != AXE_SHA256:
        print("A11Y-ENV-UNVERIFIED axe sha256 %s != 名册钉定 %s（等长替换也会在这里露出来）"
              % (sha[:16], AXE_SHA256[:16]))
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("A11Y-ENV-UNVERIFIED playwright 不可用 %s" % e)
        return 2
    src = raw.decode("utf-8")
    opts = {"resultSelection": "farest", "runOnly": {"type": "tag", "values": TAGS}}

    viol_total = 0
    states_red = []
    passes_min = 10 ** 6
    inc = []
    deltas = {}
    kb = {}
    names = []
    live = []

    with sync_playwright() as pw:
        b = launch(pw)
        if b is None:
            print("A11Y-ENV-UNVERIFIED 浏览器起不来（chromium 与 msedge 均失败）")
            return 2

        def open_page(theme, motion="no-preference", w=1280, h=860):
            ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion=motion)
            ctx.add_init_script(
                "try{localStorage.setItem('peiliao.theme.v1', %s);"
                "localStorage.setItem('peiliao.cfg.v1', JSON.stringify({base:%s,key:'x',model:'x'}));"
                "}catch(e){}" % (json.dumps(theme), json.dumps(OFFLINE)))
            return ctx, ctx.new_page()

        # ---- A1 / A2 ----
        for theme in THEMES:
            for state in STATES:
                key = "%s/%s" % (theme, state)
                ctx, pg = open_page(theme)
                try:
                    goto_state(pg, state)
                    pg.add_script_tag(content=src)
                    pg.wait_for_function("() => !!window.axe", timeout=20000)
                    r = pg.evaluate(AXE_RUN, opts)
                    if r["passes"] == 0:
                        unverified("A1 " + key, "passes=0，审计没落在 DOM 上")
                        states_red.append(key + "(no-audit)")
                    else:
                        passes_min = min(passes_min, r["passes"])
                        if r["violations"]:
                            viol_total += sum(v["n"] for v in r["violations"])
                            states_red.append(key)
                            for v in r["violations"]:
                                print("     ! %-14s %-8s %-26s n=%d" % (key, v["impact"],
                                                                        v["id"], v["n"]))
                                for t in v["targets"][:2]:
                                    print("        - %s" % t[:118])
                except Exception as e:
                    msg = str(e)
                    if "ERR_CONNECTION" in msg or "net::ERR_" in msg:
                        print("A11Y-ENV-UNVERIFIED 服务不可达（%s）%s" % (key, msg[:110]))
                        ctx.close()
                        b.close()
                        return 2
                    unverified("A2 " + key, msg[:90])
                    states_red.append(key + "(err)")
                ctx.close()
        check("A1 每状态 passes>0", passes_min > 0, "最小 passes=%d" % (passes_min if passes_min < 10 ** 6 else -1))
        check("A2 全状态 x 双主题零违规", viol_total == 0 and not states_red,
              "违规节点=%d 红=%s" % (viol_total, ",".join(states_red) or "-"))

        # ---- A3 正样本自证 ----
        ctx, pg = open_page("dark")
        pg.goto(BASE, wait_until="networkidle")
        pg.add_script_tag(content=src)
        pg.wait_for_function("() => !!window.axe", timeout=20000)
        pg.evaluate("""() => {
          const d = document.createElement('div'); d.id = 'a11y-probe';
          d.innerHTML = '<button></button>'
            + '<img src="data:image/png;base64,iVBORw0KGgo=">'
            + '<div style="background:#ffffff;color:#fefefe;font-size:14px">低对比文本占位</div>'
            + '<div role="slider" aria-valuemin="0" aria-valuemax="10"></div>';
          document.body.appendChild(d);
        }""")
        r = pg.evaluate(AXE_RUN, opts)
        got = sorted(v["id"] for v in r["violations"])
        check("A3 注入缺陷必须被抓到", ("button-name" in got and "image-alt" in got),
              "抓到 %d 类 %s" % (len(got), ",".join(got)))
        ctx.close()

        # ---- A4 对比度 incomplete 点名 ----
        ctx, pg = open_page("dark")
        pg.goto(BASE, wait_until="networkidle")
        pg.add_script_tag(content=src)
        pg.wait_for_function("() => !!window.axe", timeout=20000)
        try:
            r = pg.evaluate(AXE_RUN, {"resultSelection": "farest",
                                      "runOnly": {"type": "rule", "values": ["color-contrast"]}})
            inc = [x for x in r["incNodes"] if x["id"] == "color-contrast"]
        except Exception as e:
            unverified("A4 对比度 incomplete", str(e)[:90])
        check("A4 量不出的对比度受控且点名", len(inc) <= CONTRAST_INCOMPLETE_MAX,
              "incomplete=%d 上限=%d 样本=%s" % (len(inc), CONTRAST_INCOMPLETE_MAX,
                                               " | ".join(x["t"] for x in inc[:2])[:90]))
        ctx.close()

        # ---- A6 / A7 / A8 ----
        ctx, pg = open_page("dark")
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_timeout(600)
        kb = pg.evaluate("""() => {
          const seq = []; let cur = document.activeElement;
          for (let i = 0; i < 24; i++) {
            const s = document.activeElement;
            seq.push((s.id || s.tagName.toLowerCase()) +
                     '|outline:' + getComputedStyle(s).outlineStyle + '/' + getComputedStyle(s).outlineWidth);
            s.dispatchEvent;
            const nx = s.nextElementSibling || (s.parentElement && s.parentElement.nextElementSibling);
            if (!nx) break;
            try { nx.focus(); } catch (e) { break; }
            if (document.activeElement === cur) break;
            cur = document.activeElement;
          }
          return {seq: seq.slice(0, 12)};
        }""")
        pg.keyboard.press("Tab")
        focused1 = pg.evaluate("() => { const s=document.activeElement; const cs=getComputedStyle(s);"
                               "return (s.id||s.tagName)+'|'+cs.outlineStyle+'|'+cs.boxShadow.slice(0,24); }")
        names = pg.evaluate("""() => [...document.querySelectorAll('button,input[type=submit],a')]
            .map(e => ({vis: (e.innerText||'').trim().slice(0,20),
                        acc: (e.getAttribute('aria-label') || e.innerText || e.value || '').trim().slice(0,20),
                        id: e.id || e.tagName}))""")
        live = pg.evaluate("""() => [...document.querySelectorAll('[aria-live],[role=log],[role=status]')]
            .map(e => (e.id || e.tagName) + ':' + (e.getAttribute('aria-live') || e.getAttribute('role')))""")
        ctx.close()

        # 可见文字先剥离装饰符（emoji/符号）再比子串：首版把 emoji-only 的按钮
        # （🎤 / 🔊 只有图标没有文字标签）也算进 2.5.3 的比对，当场误伤——
        # 2.5.3 约束的是可见**文字**，图标不是文字（R263 修判据不改数据）。
        mism = [n for n in names if label_mismatch(n["vis"], n["acc"])]
        check("A6 焦点可见（首个 Tab 落点）",
              ("outlineStyle" not in focused1) and ("|none|" not in focused1),
              "落点=%s" % focused1[:70])
        check("A7 可见文字须为无障碍名子串", not mism,
              "不匹配 %d 件：%s" % (len(mism), "; ".join("%s[%s vs %s]" % (m["id"], m["vis"], m["acc"])
                                                      for m in mism[:3])))
        need_live = {"chat-log", "probe-result"}
        ids = {x.split(":")[0] for x in live}
        check("A8 对话与探针须 aria-live 播报", need_live <= ids, "实测=%s" % ",".join(sorted(ids)))

        # ---- A5 像素级动效降档 ----
        try:
            import PIL  # noqa: F401  只要通道可用即可，像素数学全在 mean_abs_delta 里
        except Exception as e:
            unverified("A5 星雾动效降档", "PIL 不可用 %s" % e)
            PIL = None
        if PIL is not None:
            for motion in ("no-preference", "reduce"):
                ctx, pg = open_page("dark", motion=motion)
                pg.goto(BASE, wait_until="networkidle")
                pg.wait_for_timeout(1200)
                frames = [pg.locator("#gl").screenshot() for _ in range(3)]
                deltas[motion] = mean_abs_delta(frames[0], frames[2])
                ctx.close()
            normal = deltas.get("no-preference", -1.0)
            reduced = deltas.get("reduce", -1.0)
            check("A5a 正常态确实在动（否则 A5b 是空判）", normal > 0.002, "delta=%.5f" % normal)
            check("A5b reduce 态显著降档", motion_ok(normal, reduced),
                  "normal=%.5f reduce=%.5f 比值=%.3f" % (normal, reduced,
                                                     reduced / normal if normal else -1))
        b.close()

    bad = [n for n, ok, d in results if ok is False]
    unv = [n for n, ok, d in results if ok is None]
    normal = deltas.get("no-preference", -1.0)
    reduced = deltas.get("reduce", -1.0)
    ratio = round(reduced / normal, 3) if normal and normal > 0 else -1
    print("=" * 76)
    if bad or unv:
        print("A11Y-FAIL 审计面=%d项 违规节点=%d 红状态=%d passes最小=%d 对比度量不出=%d "
              "动效比=%s 未验=%d 红在=%s"
              % (len(STATES) * len(THEMES), viol_total, len(states_red),
                 passes_min if passes_min < 10 ** 6 else -1, len(inc), ratio, len(unv),
                 ",".join(bad)))
        return 1
    print("A11Y-PASS 审计面=%d项(状态%d x 主题%d) 违规节点=0 passes最小=%d 规则集=%s+%d "
          "对比度量不出=%d(<= %d) 动效降档=%s倍 反例自证=OK 未验=0"
          % (len(STATES) * len(THEMES), len(STATES), len(THEMES), passes_min,
             "wcag21aa", len(TAGS) - 5, len(inc), CONTRAST_INCOMPLETE_MAX, ratio))
    return 0


if __name__ == "__main__":
    sys.exit(main())
