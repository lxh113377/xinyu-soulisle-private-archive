# -*- coding: utf-8 -*-
"""只读离线壳（sw.js）+ 缓存头策略 判据（对标轮 r28）

为什么必须先有判据再上线：本项目同族项目实证过「SW 用 cache-first 缓存了 index.html 与旧 JS
⇒ 用户一直跑老代码」。加离线壳等于把"缓存"这件危险的事引入主链路，所以三条硬规则做成可判红的断言，
**做不到就不部署**。

实测记录（写下来是因为它改变了实现）：第一版判据在"改一个字节后下次进入是否可见"这条上**报红**，
红因不是 Service Worker，而是 HTML 从来没有 Cache-Control ⇒ 浏览器按 Last-Modified 做启发式缓存，
SW 的 network-first 白跑一趟本地缓存。因此本判据同时管两层：SW 策略（静态审计）+ HTTP 头（实测）。

静态审计（纯函数 ⇒ 可注入反例，见 --selftest）：
  A1 VENDOR_STAMP == src/vendor/*.js 内容指纹复算值（换 vendor 忘 bump ⇒ 红）
  A2 必须真的拦截（respondWith）且 activate 清旧缓存
  A3 /api/ 走 network-only（对话与情绪数据不得被缓存回放）
  A4 js/demo-config.js（本地含密钥）既不在 PRECACHE、也在 NO_STORE 内
  A5 HTML/JS/CSS 走 network-first（先 fetch 再回退缓存）
  A6 cache-first 只允许 vendor/assets 前缀
  A7 页面注册代码须有 http 协议守卫 + catch
  A8 skipWaiting 与 clients.claim 都在
  A9 Pages _headers 把入口 HTML 与 sw.js 自身钉成 no-cache（实测 Pages 只有 /index.html 缺头）

运行时实测：
  R1 SW 注册且接管（重新进入后 controller 为真）
  R2 每次进入 HTML 真回源（transferSize>0）——"改一个字节下次可见"的机器替身
  R3 断网仍能打开（离线壳真生效，结构在）
  R4 /api/** 每次真到网络（含 POST），不被缓存回放
  R5 二次进入 vendor 命中缓存（离线收益非空壳）
  R6 HTTP 头实测：两端对 /、/index.html、/sw.js、/vendor/* 都必须给'再验证'语义（no-cache / no-store / must-revalidate 三选一）
  R7 全程零 JS 异常
  R10 断网重载后徽章不得伪装在线（含联网态反向断言；红线「界面明示模式」的机器化）

用法：python _test/offline_shell_check.py [--selftest]
前置：R2/R4/R5 与 R6 的本地部分需要 Java 服务端在 8123；R6 的公网部分需可达（不可达则点名跳过，不判绿）
"""
import hashlib
import http.server
import json
import re
import shutil
import socketserver
import http.server as _hs
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "http://127.0.0.1:8123"
LIVE_BASE = "https://xinyu-soulisle.pages.dev"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))
    return bool(ok)


def vendor_stamp():
    """vendor 内容指纹 ⇒ 离线壳的 cache 名（换库忘 bump 即判红）。

    跨环境必须稳定，三条都实测踩过：① 行尾（本机 checkout 可能 CRLF、runner 是 LF）；
    ② 文件名排序（`ScrollTrigger` 与 `gsap` 大小写混排，按原样排序与按 lower() 排序给出不同拼接顺序，
    拼接哈希就不同 —— r28 CI 算出 8418cd7985 而本地是 b84ce922be，正是这类不稳定）；
    ③ 逐文件先摘要再按名字排序合并，彻底与 glob 顺序无关。
    """
    per = []
    for p in sorted((ROOT / "src" / "vendor").glob("*.js"), key=lambda q: q.name.lower()):
        per.append((p.name.lower(), hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()))
    h = hashlib.sha256()
    for name, dg in sorted(per):
        h.update(name.encode() + b"=" + dg.encode() + b";")
    return h.hexdigest()[:10]


def arr(text, name):
    m = re.search(r"const " + name + r" = \[(.*?)\];", text, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else None


def sw_static_audit(text, html, stamp, headers_txt=""):
    """离线壳与头策略的静态判据（纯函数，反例直接喂它）"""
    bad = []
    m = re.search(r'const VENDOR_STAMP = "([0-9a-f]{10})"', text)
    if not m:
        bad.append("A1 没有 VENDOR_STAMP 常量 ⇒ 缓存名不可复算")
    elif m.group(1) != stamp:
        bad.append(f"A1 vendor 已变但戳未 bump：sw={m.group(1)} 实算={stamp}")
    if "e.respondWith" not in text:
        bad.append("A2 没有任何 respondWith ⇒ 离线壳根本没拦截（注册了也不会离线可用）")
    if "caches.delete" not in text or "k !== CACHE" not in text:
        bad.append("A2 activate 不清旧缓存 ⇒ 用户机器上旧版本永远留着")
    no = re.search(r"const NETWORK_ONLY_PREFIX = \[(.*?)\]", text, re.S)
    if not no or "/api/" not in no.group(1):
        bad.append("A3 /api/ 未列入 network-only（对话与情绪数据可能被回放）")
    if not re.search(r"startsWithAny\(url\.pathname, NETWORK_ONLY_PREFIX\)[\s\S]{0,140}?\n\s+return;", text):
        bad.append("A3 /api 分支不是直接 return（等于仍然走缓存逻辑）")
    pre = arr(text, "PRECACHE") or []
    ns = arr(text, "NO_STORE") or []
    if "/js/demo-config.js" in pre:
        bad.append("A4 含密钥的 demo-config.js 被预缓存（密钥会落进 Cache Storage）")
    if "/js/demo-config.js" not in ns:
        bad.append("A4 demo-config.js 未列入 NO_STORE ⇒ 仍可能被顺手写进缓存")
    if not re.search(r"try \{\s*\n?\s*const res = await fetch\(req\)", text):
        bad.append("A5 HTML/JS/CSS 不是 network-first ⇒ 改了代码用户看不到新版")
    cf = arr(text, "CACHE_FIRST_PREFIX")
    if cf is None or set(cf) - {"/vendor/", "/assets/"}:
        bad.append(f"A6 cache-first 前缀越界（只允许 vendor/assets）：{cf}")
    if "serviceWorker.register" not in html:
        bad.append("A7 页面里没有注册代码 ⇒ sw.js 是死文件")
    if 'location.protocol.startsWith("http")' not in html or ".catch(" not in html:
        bad.append("A7 注册缺协议守卫或缺 catch（file:// 或异常会把主链路带崩）")
    if "self.skipWaiting()" not in text or "clients.claim()" not in text:
        bad.append("A8 缺 skipWaiting/clients.claim ⇒ 更新要等第二次访问才生效")
    if 'x-xinyu-src' not in text:
        bad.append("A10 SW 不给响应打来源标记 ⇒ 判据只能看 transferSize，而它对外层恒为 0（无判别力）")
    # A10 分母证明：页面真实引用的每个 js/css/data 都必须被壳覆盖（否则"加了新模块忘了进壳"= 离线必炸且无人报警）
    refs = ["/" + m for m in re.findall(r'(?:src|href)="((?:js|css|data)/[^"]+)"', html)]
    covered = set(pre)                    # vendor/assets 由前缀规则覆盖，且不在本页 js/css/data 引用内
    uncovered = [r for r in refs if r not in covered and r not in ns]
    if uncovered:
        bad.append(f"A10 页面引用有 {len(uncovered)} 个文件不在离线壳清单内：{uncovered}")
    for path in ("/index.html", "/sw.js"):
        if not re.search(re.escape(path) + r"\n\s+Cache-Control: no-cache", headers_txt):
            bad.append(f"A9 _headers 缺 {path} 的 no-cache（SW 脚本自身被钉住 = 更新全推迟）")
    return bad


FRESH = re.compile(r"no-cache|no-store|must-revalidate", re.I)


def header_rules(pairs):
    """pairs: {path: Cache-Control 值}。判"会不会回源校验"——缺头即不可信（启发式缓存）。
    实测来的口径：本地 jar 给 no-store（比 no-cache 更严），Pages 给 max-age=0, must-revalidate，
    两者都算合格；所以判据认的是"必须再验证"这个语义，而不是某个具体字符串。"""
    out = {}
    for p, v in (pairs or {}).items():
        out[p] = bool(v) and bool(FRESH.search(v))
    return out


def probe_headers(base, paths, timeout=25):
    """HEAD 优先、405 回落 GET；返回 {path: Cache-Control}（拿不到即 None，不猜）。

    r28 实测：Cloudflare Pages 对默认 `Python-urllib/3.12` 这个 UA 直接 403（同一时刻 curl 正常拿到 200）
    ⇒ 取数必须带浏览器 UA，否则判据会把"工具没被放行"误判成"产品头策略不合格"。
    """
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    got = {}
    for p in paths:
        val = None
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(base + p, method=method, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    val = r.headers.get("Cache-Control")
                break
            except urllib.error.HTTPError as e:
                val = f"HTTP {e.code}"
                if method == "GET":
                    break
            except Exception as e:
                val = f"ERR {str(e)[:40]}"
                break
        got[p] = val
    return got


def wait_precache(pg, want, timeout_ms=15000):
    """轮询到 PRECACHE 全部落地再断言。SW 的 install 是异步的：
    注册一 active 就去数缓存，必然数到"缺一堆" —— 那是判据的竞态，不是产品的缺件（r28 实测过）。"""
    import time
    deadline = time.time() + timeout_ms / 1000.0
    have = []
    while time.time() < deadline:
        have = pg.evaluate("""async () => {
            const ks = (await caches.keys()).filter(k => k.startsWith('xinyu-shell-'));
            if (!ks.length) return [];
            const kk = await (await caches.open(ks[0])).keys();
            return kk.map(r => new URL(r.url).pathname);
        }""")
        if set(want) <= set(have):
            return have, []
        pg.wait_for_timeout(400)
    return have, [p for p in want if p not in have]


def launch(pw):
    try:
        return pw.chromium.launch()
    except Exception:
        return pw.chromium.launch(channel="msedge")


def run_static_only():
    text = (ROOT / "src" / "sw.js").read_text("utf-8")
    html = (ROOT / "src" / "index.html").read_text("utf-8")
    hd = (ROOT / "deploy" / "xinyu" / "_headers")
    bad = sw_static_audit(text, html, vendor_stamp(), hd.read_text("utf-8") if hd.exists() else "")
    check("A1–A9 离线壳与头策略静态审计", not bad, " ; ".join(bad))
    return 0 if not bad else 1


def run_runtime():
    from playwright.sync_api import sync_playwright
    errs = []
    miss = []            # SW 侧"壳里没这件"的现场留痕，R7 报红时直接指到文件名
    pw = sync_playwright().start()
    browser = launch(pw)
    try:
        # —— 本地 jar（权威源 + 真实 /api）：R1 / R2 / R4 / R5 / R7
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(getattr(e, "stack", None) or e)))
        pg.goto(API_BASE + "/index.html")
        pg.wait_for_function("() => navigator.serviceWorker.getRegistration().then(r => !!r && !!r.active)", timeout=20000)
        want = arr((ROOT / "src" / "sw.js").read_text("utf-8"), "PRECACHE") or []
        have, missing = wait_precache(pg, want)
        check("R8 PRECACHE 清单全部真入缓存（清单复算自 sw.js 源码，缺一个就点名）",
              bool(have) and not missing, f"入缓存 {len(have)}/{len(want)} 项，缺={missing}")
        ctrl = False
        for i in range(4):                                    # SW 接管是异步的：重新进入并轮询，不靠"睡一下"
            pg.goto(API_BASE + "/index.html")
            ctrl = pg.evaluate("() => !!navigator.serviceWorker.controller")
            if ctrl:
                break
        check("R1 离线壳注册且重新进入后接管", ctrl, f"controller={ctrl}（轮询至多 4 次）")
        nav = pg.evaluate("""async () => {
            const out = [];
            for (let i = 0; i < 2; i++) {                 // 两次进入：第二次仍必须是 network（不是 cache）
                const r = await fetch('/index.html?probe=' + Date.now() + i);
                out.push(r.headers.get('x-xinyu-src') + '/' + r.status);
                await r.text();
            }
            const r3 = await fetch('/index.html');
            await r3.text();
            out.push(r3.headers.get('x-xinyu-src'));      // 不带 query 的同一 URL 也要回源
            return out.join(' | ');
        }""")
        check("R2 HTML 每次真回源（SW 自报来源，非 transferSize 猜）",
              nav.startswith("network") and "network" in nav and "cache/" not in nav and nav.endswith("network"),
              f"x-xinyu-src={nav}")
        got = pg.evaluate("""async () => {
            const a = await fetch('/api/health'); await a.json();
            const b = await fetch('/api/emotion', {method:'POST',headers:{'Content-Type':'application/json'},
                body: JSON.stringify({text:'今天有点累'})});
            await b.json();
            return performance.getEntriesByType('resource')
              .filter(e => e.name.includes('/api/'))
              .map(e => ({n: e.name.replace(location.origin,'').split('?')[0], t: e.transferSize, s: e.responseStatus}));
        }""")
        onnet = [x for x in got if x["t"] > 0]
        check("R4 /api/** 每次真到网络（含 POST，不被缓存回放）", bool(got) and len(onnet) == len(got),
              json.dumps(got, ensure_ascii=False)[:160])
        check("R4b 接口未被 SW 拦坏（状态码全 200）", bool(got) and all(x["s"] == 200 for x in got), str([x["s"] for x in got]))
        pg.goto(API_BASE + "/index.html")
        pg.wait_for_timeout(600)
        vsrc = pg.evaluate("""async () => {
            const files = ['vendor/three.min.js', 'vendor/gsap.min.js', 'vendor/ScrollTrigger.min.js'];
            const out = {};
            for (const f of files) { const r = await fetch('/' + f); out[f] = r.headers.get('x-xinyu-src'); await r.text(); }
            return JSON.stringify(out);
        }""")
        hits = vsrc.count("cache")
        check("R5 二次进入 vendor 由缓存供弹（离线收益非空壳）", hits == 3, f"{hits}/3 cache，明细={vsrc}")
        ctx.close()

        # —— 临时静态副本：R3 断网可打开（不动权威文件）
        tmp = Path(tempfile.mkdtemp(prefix="xinyu-shell-"))
        shutil.copytree(ROOT / "src", tmp / "web")

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(tmp / "web"), **kw)

            def log_message(self, *a):
                pass

        H.extensions_map = {**getattr(H, "extensions_map", {}), ".webmanifest": "application/manifest+json"}
        # 必须是**线程版**：SW 安装期会并发发 17 个 c.add()，单线程 TCPServer 会让一部分排队失败，
        # 表现为"离线时某模块 undefined"的间歇红 —— 那是脚手架的缺陷，不是产品的缺陷（r28 实测 3 跑 2 红）。
        srv = _hs.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
        try:
            c2 = browser.new_context()
            miss = []
            c2.on("console", lambda m: miss.append(m.text[:90]) if "XINYU-SHELL-MISS" in m.text else None)
            p2 = c2.new_page()
            p2.on("pageerror", lambda e: errs.append("offline: " + str(getattr(e, "stack", None) or e)))
            p2.goto(url)
            p2.wait_for_function("() => navigator.serviceWorker.getRegistration().then(r => !!r && !!r.active)", timeout=20000)
            w2 = arr((ROOT / "src" / "sw.js").read_text("utf-8"), "PRECACHE") or []
            hv, ms = wait_precache(p2, w2)
            check("R3a 断网前先确认壳已装完（否则 R3 红的是判据不是产品）", not ms, f"缺={ms}")
            p2.goto(url)
            badge_on = p2.evaluate("() => (document.querySelector('#mode-badge')||{}).textContent || ''")
            check("R10a 联网态徽章仍明示「在线 AI」（反向断言：防把分支写反致恒绿）",
                  "在线 AI" in badge_on, badge_on.strip()[:36])
            greet = p2.evaluate("""() => {
              const t = document.querySelector('#chat-log .msg .tag, #chat-log .tag');
              return t ? t.textContent : '';
            }""")
            check("R10c 开场白标签不得伪装来自大模型（本机生成＝红线「禁伪装在线」的同类出口）",
                  ("在线" not in greet) and ("本机" in greet) and ("未经大模型" in greet), greet.strip()[:36])
            c2.set_offline(True)
            try:
                p2.reload(wait_until="domcontentloaded", timeout=20000)
                ok3 = p2.evaluate("() => !!document.querySelector('#gl') && document.querySelectorAll('section').length > 0")
            except Exception as e:
                ok3, err3 = False, str(e)[:70]
            else:
                err3 = ""
            diag = p2.evaluate("""() => ({
              CA: typeof window.ChatAgent, MS: typeof window.MemoryStore, EE: typeof window.EmotionEngine,
              SW: typeof window.Settings, CW: typeof window.ChatWindow, CH: typeof window.Chart, VO: typeof window.Voice,
              zero: performance.getEntriesByType('resource').filter(e => e.responseStatus === 0).map(e => e.name.split('/').pop()),
              cached: !!navigator.serviceWorker.controller
            })""")
            check("R3 断网后可离线打开（壳真生效）", bool(ok3), f"结构在={ok3} {err3} 诊断={json.dumps(diag, ensure_ascii=False)[:230]}")
            badge_off = p2.evaluate("() => (document.querySelector('#mode-badge')||{}).textContent || ''")
            check("R10b 断网重载后徽章不得伪装在线（红线：界面明示模式，禁伪装在线）",
                  ("在线 AI" not in badge_off) and ("网络不可用" in badge_off), badge_off.strip()[:36])
            c2.close()
        finally:
            srv.shutdown()
            shutil.rmtree(tmp, ignore_errors=True)

        # —— R9 公网真断网实测（"现场 WiFi 挂了还能演五幕"是这条能力的唯一存在理由）
        try:
            c3 = browser.new_context()
            p3 = c3.new_page()
            p3.on("pageerror", lambda e: errs.append("live: " + str(getattr(e, "stack", None) or e)))
            p3.goto(LIVE_BASE + "/", wait_until="domcontentloaded", timeout=45000)
            p3.wait_for_function("() => navigator.serviceWorker.getRegistration().then(r => !!r && !!r.active)", timeout=30000)
            w3 = arr((ROOT / "src" / "sw.js").read_text("utf-8"), "PRECACHE") or []
            hv3, ms3 = wait_precache(p3, w3, timeout_ms=25000)
            check("R9a 公网壳已装完（入缓存数对得上清单）", not ms3, f"{len(hv3)}/{len(w3)} 缺={ms3[:4]}")
            c3.set_offline(True)
            try:
                p3.reload(wait_until="domcontentloaded", timeout=25000)
                ok9 = p3.evaluate("() => !!document.querySelector('#gl') && document.querySelectorAll('section').length > 0")
                err9 = ""
            except Exception as e:
                ok9, err9 = False, str(e)[:70]
            check("R9b 公网断网后可离线打开", bool(ok9), f"结构在={ok9} {err9}")
            c3.close()
        except Exception as e:
            check("R9a 公网壳已装完（入缓存数对得上清单）", False, f"公网不可达/注册超时 ⇒ 记为未验证：{str(e)[:70]}")

        # —— R6 两端 HTTP 头实测（公网不可达就点名，不判绿）
        paths = ["/", "/index.html", "/sw.js", "/vendor/three.min.js"]
        local = probe_headers(API_BASE, paths)
        weak = [f"{p}={local[p]!r}" for p, ok in header_rules(local).items() if not ok]
        check("R6a 本地 jar：入口/SW/静态都要'再验证'（缺头=可启发式缓存，不可信）", not weak,
              ("不合格项: " + "; ".join(weak)) if weak else json.dumps(local, ensure_ascii=False))
        live = probe_headers(LIVE_BASE, paths)
        if any(str(v).startswith("ERR") for v in live.values()):
            check("R6b 公网头策略（Pages _headers 真生效）", False,
                  f"不可达 ⇒ 记为未验证，不判绿：{json.dumps(live, ensure_ascii=False)[:120]}")
        else:
            weak_l = [f"{p}={live[p]!r}" for p, ok in header_rules(live).items() if not ok]
            check("R6b 公网头策略（Pages _headers 真生效）", not weak_l,
                  ("不合格项: " + "; ".join(weak_l)) if weak_l else json.dumps(live, ensure_ascii=False))
    finally:
        browser.close()
        pw.stop()
    check("R7 全程无 JS 异常", not errs,
          str(errs[:2]) + (f" ｜壳缺件={sorted(set(miss))}" if miss else ""))
    bad = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(bad)} 项")
    for n, _, d in bad:
        print("  🔴", n, d[:120])
    print("OFFLINE-SHELL-PASS" if not bad else "OFFLINE-SHELL-FAIL")
    return 1 if bad else 0


def run_selftest():
    """逐条改坏必须报红、原样必须零问题（每条只动一个维度，别的保持合规；条数由 muts 自己算）"""
    text0 = (ROOT / "src" / "sw.js").read_text("utf-8")
    html0 = (ROOT / "src" / "index.html").read_text("utf-8")
    hd0 = (ROOT / "deploy" / "xinyu" / "_headers").read_text("utf-8")
    stamp = vendor_stamp()
    bad = []
    if sw_static_audit(text0, html0, stamp, hd0):
        bad.append(f"原样被判失败：{sw_static_audit(text0, html0, stamp, hd0)}")

    # 每条给 (名字, 变异后的 sw/页/head 之一)；None 表示该维度不变
    muts = [
        ("A1 戳不 bump", (text0.replace(f'"{stamp}"', '"0000000000"'), None, None)),
        ("A2 不拦截", (text0.replace("e.respondWith", "e.noopWith"), None, None)),
        ("A2 不清旧缓存", (text0.replace("await caches.delete(k)", "void k"), None, None)),
        ("A3 api 进缓存", (text0.replace('const NETWORK_ONLY_PREFIX = ["/api/"];', "const NETWORK_ONLY_PREFIX = [];"), None, None)),
        ("A4 预缓存密钥件", (text0.replace('const PRECACHE = [\n  "/",', 'const PRECACHE = [\n  "/js/demo-config.js", "/",'), None, None)),
        ("A5 改成 cache-first", (text0.replace("      const res = await fetch(req);", "      const res = await caches.match(req);"), None, None)),
        ("A6 cache-first 越界", (text0.replace('"/assets/"', '"/assets/", "/js/"'), None, None)),
        ("A7 页面没注册", (None, "<html></html>", None)),
        ("A8 不 skipWaiting", (text0.replace("self.skipWaiting();", "// removed"), None, None)),
        ("A9 sw.js 头被改成 10 分钟", (None, None, hd0.replace("/sw.js\n  Cache-Control: no-cache", "/sw.js\n  Cache-Control: max-age=600"))),
        ("A10 来源标记被摘掉", (text0.replace('h.set("x-xinyu-src", src);', "// 探针被拆"), None, None)),
        ("A10′ 页面新增模块未进壳", (None, html0 + "\n<script src=\"js/brand-new.js\"></script>\n", None)),
        ("A9 头文件整份缺失", (None, None, "")),
    ]
    for name, (t, h, d) in muts:
        if not sw_static_audit(t if t is not None else text0,
                              h if h is not None else html0, stamp,
                              d if d is not None else hd0):
            bad.append(f"反例「{name}」未被抓到 ⇒ 对应判据恒真")
    # header_rules 的正反两侧（缺头与长缓存都必须判红；三种"再验证"写法都必须判绿）
    for p, v in {"/": None, "/sw.js": "max-age=86400", "/index.html": ""}.items():
        if header_rules({p: v})[p]:
            bad.append(f"header_rules 对 {p}={v!r} 判合格 ⇒ 恒真（缺头/长缓存都会被浏览器启发式缓存）")
    good = header_rules({"/": "no-store", "/sw.js": "no-cache",
                         "/index.html": "public, max-age=0, must-revalidate"})
    if not all(good.values()):
        bad.append(f"header_rules 对三种合规'再验证'写法判不合格 ⇒ 恒假：{good}")
    if bad:
        print("SELFTEST-FAIL: " + " ; ".join(bad))
        return 1
    print(f"SELFTEST-PASS: {len(muts)} 类注入反例全部被抓到、原样零问题；header_rules 正/反两侧均正确（vendor 戳复算={stamp}）")
    return 0


def main():
    if "--selftest" in sys.argv[1:]:
        return run_selftest()
    rc = run_static_only()
    return rc if rc else run_runtime()


if __name__ == "__main__":
    sys.exit(main())
