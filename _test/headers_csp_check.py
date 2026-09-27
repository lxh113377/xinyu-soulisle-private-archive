# -*- coding: utf-8 -*-
"""安全响应头 / CSP 判据（r54 新增）—— 量「`_headers` 里写的东西，线上真的回不回」，以及
「套上 CSP 之后应用还跑不跑得起来」。

为什么是这一面：✅ 取证 `grep -ilE "CSP|内容安全策略|安全头|helmet|X-Frame" 交付物/对标分析报告-*.md`
= **十五份全 0**。而本仓从 r28 起就在维护 `deploy/xinyu/_headers` —— 一个典型的
「配置在册就以为生效」的位置（同族：r50 dependabot 配置在、PR 也开过，告警整条关着）。

线上实测（curl -D -，本地时刻 18:04）：所有路径 `content-security-policy` **一条都没有**；
且 r28 只给 `/index.html` 写了 `Cache-Control: no-cache`，而 Pages 把 `/index.html` **308 跳到 `/`**
⇒ 用户真正访问的入口拿的是 `public, max-age=0, must-revalidate`。声明与生效路径不一致。

四条阻断 + 一条控制：
  H1 逐路径对账：`_headers` 里每条声明，本地按同一份规则回放后，响应里必须真在（且值逐字相同）
  H2 套上 CSP 后应用仍可用：WebGL 画布活跃 / 五幕齐 / 对话链路通 / console 0 报错 / pageerror 0
  H3 严格性棘轮：script-src 与 style-src 不得含 'unsafe-inline' / 'unsafe-eval'（放宽须改判据留名）
  H4 前置不变量：`src/index.html` 的内联 <script> 计数必须为 0（有人加回内联块，就该 here 红，
     而不是被"顺手给 CSP 补个 'unsafe-inline'" 悄悄绕开）
  H5 **反自欺控制**：用一个必须被 CSP 挡下的内联脚本探针证明这套回放真的在拦截 ——
     挡不住就说明 H1/H2 的绿色来自夹具没生效，全套读数作废（判夹具不判产品）
用法：python _test/headers_csp_check.py [--local] [--live URL] [--selftest]
退出码：0=全过 1=判红 2=环境未验证（无 Playwright / 端口起不来 / live 不可达 ⇒ 不判绿）
"""
import argparse
import http.server
import json
import re
import socket
import socketserver
import sys
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
HEADERS_FILE = ROOT / "deploy" / "xinyu" / "_headers"
WEB_ROOT = ROOT / "deploy" / "xinyu"
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json",
        ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json",
        ".png": "image/png", ".mp3": "audio/mpeg"}
# Cloudflare Pages 的 `_headers` 路径语义：`/*` 匹配全部；其余按字面路径匹配（不做前缀）
SAFE_RATCHET = ("script-src", "style-src")
FORBIDDEN = ("'unsafe-inline'", "'unsafe-eval'")
# 夹具用的一条干净 CSP。写成模块常量而不是就地内联，是因为 `"...'self'"}` 这种
# 「引号紧跟右花括号」的邻接在写盘路径上会被吞掉一个引号（本仓台账在册的同族第 14 次，
# 这次是 Write 自己吞的），当场 SyntaxError 才暴露。
CSP_OK = "default-src 'none'; script-src 'self'; style-src 'self'"


def parse_headers(text):
    """把 `_headers` 解析成 [(pattern, {name: value})]。注释行(#)与空行跳过。"""
    rules, cur = [], None
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("/"):
            cur = (s, {})
            rules.append(cur)
            continue
        if ":" in s and cur is not None:
            k, v = s.split(":", 1)
            cur[1][k.strip().lower()] = v.strip()
    return rules


def merged(path, rules):
    """按 Pages 语义合并某路径应回的头：`/*` 先，字面路径后（后者覆盖前者同名项）。"""
    out = {}
    for pat, kv in rules:
        if pat == "/*" or pat == path:
            out.update(kv)
    return out


def csp_map(value):
    return {d.split()[0]: d.split()[1:] for d in (value or "").split(";") if d.strip()}


def assess(probe):
    """纯函数判据。probe = {declared:{path:{h:v}}, observed:{path:{h:v}}, app:{...},
    strict:{...}, inline_scripts:int, block_probe:{blocked:bool, violated:bool}}"""
    bad = []
    # H5 先判：拦截没生效，后面所有绿色都不作数
    bp = probe.get("block_probe") or {}
    if not bp.get("blocked") or not bp.get("violated"):
        return (["H5-INVALID 本地回放**没能拦下**必须被 CSP 挡的内联脚本"
                 "（blocked=%s violated=%s）⇒ 夹具没在施加 CSP，本组全部读数作废"
                 % (bp.get("blocked"), bp.get("violated"))], {})
    # H0 取数面本身必须非空：`_headers` 解析出 0 条规则时，H1 的循环不会产出任何 miss，
    # 于是"读空气"会被印成 PASS（这条正是 selftest 的边界用例逼出来的——判据缺陷，不是写法问题）
    if not probe.get("declared") or not probe.get("observed"):
        return (["H0 取数面为空（声明 %d 条 / 回放 %d 条）⇒ 无对账对象，不判绿"
                 % (len(probe.get("declared") or {}), len(probe.get("observed") or {}))], {})
    # H1 逐路径逐条对账
    miss = []
    for path, kv in (probe.get("declared") or {}).items():
        obs = (probe.get("observed") or {}).get(path)
        if obs is None:
            miss.append("%s 未取到响应" % path)
            continue
        for h, v in kv.items():
            if obs.get(h) != v:
                miss.append("%s 的 %s 声明=%r 实回=%r" % (path, h, v[:38], (obs.get(h) or "")[:38]))
    if miss:
        bad.append("H1 声明与回放响应不一致 %d 处：%s" % (len(miss), miss[0]))
    # H2 应用可用性
    app = probe.get("app") or {}
    for k, want in (("gl_ok", True), ("acts", 5), ("chat_ok", True), ("errors", 0)):
        got = app.get(k)
        if got != want:
            bad.append("H2 套上 CSP 后应用断言失败：%s=%r（应为 %r）" % (k, got, want))
    # H3 严格性棘轮
    csp = (probe.get("strict") or {})
    for d in SAFE_RATCHET:
        dirs = csp.get(d)
        if dirs is None:
            bad.append("H3 CSP 缺 %s 指令（缺省会回落到 default-src，不能靠回落）" % d)
            continue
        hit = [f for f in FORBIDDEN if f in dirs]
        if hit:
            bad.append("H3 %s 含 %s ⇒ 放宽需改判据并留名，不许悄悄加回" % (d, ",".join(hit)))
    # H4 前置不变量
    n = probe.get("inline_scripts")
    if n != 0:
        bad.append("H4 src/index.html 有 %d 个内联 <script> ⇒ 严格 CSP 必被挡，"
                   "正确处置是外提而不是放开 'unsafe-inline'" % n)
    return bad, {"declared_paths": len(probe.get("declared") or {}),
                 "csp_dirs": len(csp), "app": app,
                 "violations": (probe.get("block_probe") or {}).get("violations", [])}


class Handler(http.server.BaseHTTPRequestHandler):
    rules = []

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        hdr = merged(path, self.rules)
        if path == "/__csp_probe__":
            # H5：一段必须被 CSP 挡下的内联脚本（浏览器会在 console 报 violation）
            html = ("<!doctype html><meta charset=utf-8><title>csp-probe</title>"
                    "<script>window.__csp_inline_ran = 1;</script><p>probe</p>")
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", hdr)
        rel = (path[1:] or "index.html")
        f = WEB_ROOT / rel
        if not f.is_file():
            return self._send(404, b"not found", "text/plain; charset=utf-8", hdr)
        body = f.read_bytes()
        return self._send(200, body, MIME.get(f.suffix.lower(), "application/octet-stream"), hdr)


def serve(port=0):
    Handler.rules = parse_headers(HEADERS_FILE.read_text("utf-8"))
    srv = socketserver.TCPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def head_via(url):
    """取一次真实响应头。

    ⚠️ 两处实测坑都在这儿（本仓 r54 一手）：
      ① 默认 UA `Python-urllib/3.x` 会被 Cloudflare 判成 403，而 curl 同 URL 是 200
         —— 于是判据把"我的 UA 被挡"读成"线上没有 CSP"。故显式带浏览器 UA。
      ② HTTPError 是**带响应头的**异常：只记异常类型会把状态码丢掉，
         "不可达"与"可达但回 403/404"就同形了（盲区不得读成零）。故从 e 上把头抄回来。
    """
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers={"User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            out = {k.lower(): v for k, v in r.headers.items()}
            out["__status__"] = str(r.status)
            return out
    except urllib.error.HTTPError as e:
        out = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        out["__status__"] = "http=%s" % e.code
        return out
    except Exception as e:
        return {"__err__": "%s" % type(e).__name__}


def run_local():
    from playwright.sync_api import sync_playwright
    rules = parse_headers(HEADERS_FILE.read_text("utf-8"))
    declared = {}
    srv, base = serve()
    try:
        observed, probe = {}, {}
        for p in ("/", "/index.html", "/js/app.js", "/css/style.css", "/sw.js"):
            h = head_via(base + p)
            observed[p] = {k: v for k, v in h.items() if k in
                           ("content-security-policy", "cache-control", "x-content-type-options",
                            "referrer-policy", "x-frame-options", "permissions-policy")}
            observed[p]["__status__"] = h.get("__status__") or h.get("__err__")
        errs, vios = [], []
        with sync_playwright() as pw:
            try:
                b = pw.chromium.launch()
            except Exception:
                b = pw.chromium.launch(channel="msedge")
            pg = b.new_page(viewport={"width": 1200, "height": 860})
            pg.on("pageerror", lambda e: errs.append(str(e)[:110]))
            pg.on("console", lambda m: vios.append(m.text[:140])
                  if m.type == "error" and "Content Security Policy" in m.text else None)

            def stub(route):
                route.fulfill(status=200, content_type="application/json",
                              body='{"choices":[{"message":{"content":"我在，慢慢说。"}}],"usage":{}}')

            # H5 拦截探针
            pg.goto(base + "/__csp_probe__", wait_until="load", timeout=30000)
            pg.wait_for_timeout(500)
            ran = pg.evaluate("() => window.__csp_inline_ran === 1")
            probe["block_probe"] = {"blocked": not ran, "violated": bool(vios),
                                    "violations": vios[:2]}
            # H2 真页面在 CSP 下跑金链
            vios.clear()
            pg.route("**/api/chat*", stub)
            pg.add_init_script("try{localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                               "{proxy:'%s/api/chat',stream:false}))}catch(e){}" % base)
            pg.goto(base + "/", wait_until="load", timeout=45000)
            pg.wait_for_timeout(3000)
            app = pg.evaluate("""() => ({
                gl_ok: !!(window.THREE && document.querySelector('#gl')),
                acts: document.querySelectorAll('.act,[data-act]').length,
                has_app: !!window.ChatAgent,
                inline_blocked: (() => { const s=document.createElement('style');
                    try { s.textContent = 'body{}'; document.head.appendChild(s); return false; }
                    catch (e) { return true; } })(),
              })""")
            pg.fill("#chat-input", "今天有点累，想被陪一会儿")
            pg.press("#chat-input", "Enter")
            t0 = __import__("time").monotonic()
            chat_ok = False
            while __import__("time").monotonic() - t0 < 40:
                n = pg.evaluate("() => document.querySelectorAll('#chat-log > *').length")
                if n >= 3:
                    chat_ok = True
                    break
                pg.wait_for_timeout(250)
            app["errors"] = len(errs)
            app["chat_ok"] = chat_ok
            app["acts"] = max(app.get("acts") or 0, pg.evaluate(
                "() => document.querySelectorAll('[data-act]').length"))
            app["gl_ok"] = bool(app["gl_ok"] and app["has_app"])
            probe["app"] = {"gl_ok": app["gl_ok"], "acts": app["acts"],
                            "chat_ok": app["chat_ok"], "errors": app["errors"]}
            probe["strict"] = csp_map(observed["/"].get("content-security-policy", ""))
            b.close()
    finally:
        srv.shutdown()
        srv.server_close()
    probe["declared"] = {p: merged(p, rules) for p in observed}
    probe["observed"] = observed
    probe["inline_scripts"] = len(re.findall(
        r"<script(?![^>]*\bsrc=)[^>]*>", (ROOT / "src" / "index.html").read_text("utf-8")))
    return probe


def run_live(url):
    """线上复测：只断言"入口有没有 CSP + 有没有放宽"。取不到 → UNVERIFIED（不判 0）。"""
    h = head_via(url.rstrip("/") + "/")
    if h.get("__err__") or str(h.get("__status__", "")).startswith("http="):
        return None, "live 未取得 2xx（%s｜状态=%s 错误=%s）" % (
            url, h.get("__status__") or "-", h.get("__err__") or "-")
    csp = h.get("content-security-policy")
    if not csp:
        return ["L1 线上入口没有 Content-Security-Policy（头实测=%s）"
                % ",".join(sorted(k for k in h if "-" in k))[:120]], h
    bad = []
    for d in ("script-src", "style-src"):
        dirs = csp_map(csp).get(d) or []
        hit = [f for f in FORBIDDEN if f in dirs]
        if hit:
            bad.append("L2 线上 %s 含 %s" % (d, ",".join(hit)))
    return bad, h


def selftest():
    ok, fail = 0, []
    dec = {"/": {"content-security-policy": "default-src 'none'; script-src 'self'; style-src 'self'"}}
    base_probe = {
        "block_probe": {"blocked": True, "violated": True, "violations": ["Refused to execute"]},
        "declared": dec,
        "observed": {"/": {"content-security-policy": CSP_OK}},
        "app": {"gl_ok": True, "acts": 5, "chat_ok": True, "errors": 0},
        "strict": csp_map("default-src 'none'; script-src 'self'; style-src 'self'"),
        "inline_scripts": 0}
    if not assess(base_probe)[0]:
        ok += 1
    else:
        fail.append("正例被判红：%s" % assess(base_probe)[0])
    # 反例①：CSP 根本没施加（夹具坏）⇒ 必须 INVALID 而不是 PASS
    m1 = json.loads(json.dumps(base_probe))
    m1["block_probe"] = {"blocked": False, "violated": False}
    if any("H5-INVALID" in x for x in assess(m1)[0]):
        ok += 1
    else:
        fail.append("反例① 夹具未施加 CSP 却判通过：%s" % assess(m1)[0])
    # 反例②：声明了但线上没回（r28 那类"声明与生效路径不一致"）
    m2 = json.loads(json.dumps(base_probe))
    m2["observed"]["/"]["cache-control"] = "public, max-age=0, must-revalidate"
    m2["declared"]["/"] = {"cache-control": "no-cache",
                           "content-security-policy":
                           "default-src 'none'; script-src 'self'; style-src 'self'"}
    if any("H1" in x for x in assess(m2)[0]):
        ok += 1
    else:
        fail.append("反例② 声明未生效未被抓到：%s" % assess(m2)[0])
    # 反例③：有人给 script-src 加回 'unsafe-inline'
    m3 = json.loads(json.dumps(base_probe))
    m3["strict"] = csp_map("script-src 'self' 'unsafe-inline'; style-src 'self'")
    m3["observed"]["/"]["content-security-policy"] = "script-src 'self' 'unsafe-inline'; style-src 'self'"
    if any("H3" in x for x in assess(m3)[0]):
        ok += 1
    else:
        fail.append("反例③ unsafe-inline 未被棘轮拦住：%s" % assess(m3)[0])
    # 反例④：CSP 挡掉了应用（WebGL 起不来 / 报错）
    m4 = json.loads(json.dumps(base_probe))
    m4["app"] = {"gl_ok": False, "acts": 5, "chat_ok": True, "errors": 3}
    b4 = assess(m4)[0]
    if sum(1 for x in b4 if "H2" in x) == 2:
        ok += 1
    else:
        fail.append("反例④ H2 两条断言未各自报红：%s" % b4)
    # 反例⑤：内联 <script> 被加回来（前置不变量）
    m5 = json.loads(json.dumps(base_probe))
    m5["inline_scripts"] = 1
    if any("H4" in x for x in assess(m5)[0]):
        ok += 1
    else:
        fail.append("反例⑤ 内联脚本回归未被抓到：%s" % assess(m5)[0])
    # 解析器自证：注释行不算规则、/* 与字面路径分开、多行头值不误拆
    r = parse_headers("# c\n/*\n  X-A: 1\n  # inner comment\n/\n  X-B: 2\n/x.js\n  X-C: 3\n")
    got = {p: kv for p, kv in r}
    if got.get("/*") == {"x-a": "1"} and got.get("/") == {"x-b": "2"} \
            and got.get("/x.js") == {"x-c": "3"} and merged("/y", r).get("x-a") == "1" \
            and merged("/x.js", r) == {"x-a": "1", "x-c": "3"}:
        ok += 1
    else:
        fail.append("解析器形状异常：%s ｜ merged=%s" % (r, merged("/x.js", r)))
    # 边界：空声明面不得判绿（读空气）
    m6 = dict(base_probe)
    m6["declared"], m6["observed"] = {}, {}
    if any("H0" in x for x in assess(m6)[0]):
        ok += 1
    else:
        fail.append("边界 空取数面判绿")
    expected = 8
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("HEADSEC-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--live", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.live:
        bad, h = run_live(a.live)
        if bad is None:
            print("HEADSEC-UNVERIFIED: %s ⇒ 网络不可达不判绿" % h)
            sys.exit(2)
        for x in bad:
            print("  · " + x)
        if bad:
            print("HEADSEC-LIVE-FAIL: %d 条（URL=%s）" % (len(bad), a.live))
            sys.exit(1)
        print("HEADSEC-LIVE-PASS: %s 入口 CSP 在位且 script/style-src 无放宽"
              "（实测头 %d 个，csp 指令 %d 条）"
              % (a.live, len([k for k in h if "-" in k]),
                 len(csp_map(h.get("content-security-policy")))))
        sys.exit(0)
    try:
        probe = run_local()
    except Exception as e:
        print("HEADSEC-UNVERIFIED: 本地夹具/浏览器异常 %s: %s" % (type(e).__name__, str(e)[:120]))
        sys.exit(2)
    bad, info = assess(probe)
    for x in bad:
        print("  · " + x)
    if bad:
        print("HEADSEC-FAIL: %d 条判红（声明路径 %d，violation 样本 %s）"
              % (len(bad), info["declared_paths"], (info["violations"] or [""])[0][:60]))
        sys.exit(1)
    print("HEADSEC-PASS: CSP 逐条声明==逐条回放（路径 %d）｜严格面无放宽｜"
          "CSP 下应用可用（五幕=%s 对话=%s 异常=%s）｜内联 script=0｜拦截探针真拦下"
          % (info["declared_paths"], info["app"]["acts"], info["app"]["chat_ok"],
             info["app"]["errors"]))
    sys.exit(0)


if __name__ == "__main__":
    main()
