# -*- coding: utf-8 -*-
"""对标 r43 常驻判据：**干净克隆可跑性**（评委/他人拿到这份代码时到底看见什么）。

为什么开这条：AGENTS.md 的验收口径写着"本地实测 console 0 报错"，而它**只在作者这台机器上成立**——
`src/js/demo-config.js` 按红线被 .gitignore 掉，可 `src/index.html:157` 又硬引用它。
2026-09-27 r43 把仓库干净克隆到临时目录实测（✅ 07:2x，`python _test/clean_clone_check.py` 的前身探针）：
  HTTP 200 / THREE+gsap+ScrollTrigger 全在 / 5 幕齐 / 离线降级链路可用（气泡 3 条）
  **console errors = 1**：`Failed to load resource: 404` ← `js/demo-config.js`
⇒ "0 报错"这条断言的成立条件里藏着"本机有一份不入库的文件"，属于**只在单机成立的主张**（与 r36 行尾族同族）。

判据（C1–C5）：
  C1 从 **HEAD** 克隆（不是工作树）⇒ 证明的是"提交出去的那份"能跑，未提交改动不得参与
  C2 页面必须真加载：THREE / gsap / ScrollTrigger 到位、5 幕齐、#gl 在、对话输入在
  C3 离线降级链路必须真能走通（发一句话要出用户气泡 + AI 气泡）
  C4 console/pageerror 必须 ⊆ 显式登记的已知缺口集，**计数逐条打印**；任何新面孔一律判红
  C5 已登记缺口一旦消失（比如日后改成不 404），也要**点名报"该销账了"**——不许留成永久豁免

已知缺口（唯一一条，带理由与计数，不扩表）：
  js/demo-config.js 404 —— 该文件含本机演示用明文 Key，按密钥红线永不入库；改法要么"引用改为
  存在性探测"、要么"该路径提交零密钥版 + Key 另存不入库文件"，两者都动密钥面 ⇒ 需老大在场。
用法：python _test/clean_clone_check.py [--keep]
退出码：0=全绿 1=判红 2=环境未验（git/浏览器不可用、克隆失败、端口占用）
"""
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
REPO = str(ROOT)
KNOWN_GAPS = {"js/demo-config.js": "含本机明文 Key，按密钥红线永不入库（详见文件头 C4 注）"}
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))
    print("  %-4s %-34s %s" % ("PASS" if ok else "FAIL", name, detail)[:200])


def unverified(name, why):
    results.append((name, None, why))
    print("  UNV  %-34s %s" % (name, why)[:200])


def classify_errors(console_errs, failed_urls, known=None):
    """把浏览器两类信号合成一个可判结论。单一实现：main 与 selftest 共用。

    ⚠️ 不能拿 console 文本去匹文件名——Chrome 打的是
    `Failed to load resource: the server responded with a status of 404 (File not found)`，
    **整句里没有 URL**（✅ 07:3x 实测）。URL 只在 `requestfailed` 事件里。
    所以：已知缺口由 requestfailed 的 URL 定性；console 里那条通用 404 行
    按"一条已知失败请求吸收一行"配对，吸收不掉的才算新面孔。
    """
    known = KNOWN_GAPS if known is None else known
    hits = {k: 0 for k in known}
    unknown_req = []
    for u in failed_urls:
        tail = u.split("/")[-1]
        m = next((k for k in known if k.endswith(tail) or tail in k), None)
        if m:
            hits[m] += 1
        else:
            unknown_req.append(tail)
    generic = sum(1 for e in console_errs if "status of 404" in e or "net::ERR" in e)
    explained = sum(hits.values())
    # 非 404 类的 console 报错一定算新面孔；404 类的允许被已知失败请求"吸收"
    non404 = [e for e in console_errs if "status of 404" not in e and "net::ERR" not in e]
    unknown = non404 + ([] if generic <= explained else ["%d 条 404 未被已知缺口解释" % (generic - explained)])
    return hits, unknown, unknown_req


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


from browser_engine import launch as be_launch, short_face   # r98 E2 迁移：唯一实现见 browser_engine.py


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    r = run(["git", "--version"])
    if r.returncode:
        print("CLEAN-CLONE-ENV-UNVERIFIED git 不可用")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="xinyu_clone_"))
    clone = tmp / "repo"
    keep = "--keep" in sys.argv[1:]
    try:
        # 从 HEAD 克隆：`file://` 关掉本地硬链接优化，逼它真走对象传输，
        # 否则 local clone 会直接读工作树，"未提交的改动"会混进来冒充已交付状态。
        src = Path(REPO).as_uri()
        g = run(["git", "clone", "--no-hardlinks", src, str(clone)])
        if g.returncode:
            print("CLEAN-CLONE-ENV-UNVERIFIED 克隆失败：%s" % (g.stderr or "")[:180])
            return 2
        head = run(["git", "-C", str(clone), "rev-parse", "HEAD"]).stdout.strip()
        local_head = run(["git", "-C", REPO, "rev-parse", "HEAD"]).stdout.strip()
        check("C1 克隆自 HEAD（提交态而非工作树）", head == local_head and bool(head),
              "clone=%s HEAD=%s" % (head[:7], local_head[:7]))
        # 未跟踪件不得出现在克隆里（反向证明：gitignore 掉的敏感件确实没被带走）
        leak = [p for p in (clone / "src" / "js").glob("*.js") if "demo-config" in p.name]
        check("C1b 被忽略的密钥件未被带走", not leak, "克隆内 demo-config* = %s" % [p.name for p in leak])

        web = clone / "src"
        if not web.exists():
            print("CLEAN-CLONE-ENV-UNVERIFIED 克隆里没有 src/ 目录")
            return 2
        port = free_port()
        old_cwd = os.getcwd()
        os.chdir(str(web))
        try:
            # 线程化托管：单线程 TCPServer 会把浏览器并发的 6 条连接串成队列，
            # 是"哪两个 js 恰好报失败"这种**不可归因抖动**的候选源之一（r65 先摘掉变量再归因）。
            httpd_cls = socketserver.ThreadingTCPServer
            httpd_cls.daemon_threads = True
            with httpd_cls(("127.0.0.1", port), Quiet) as httpd:
                threading.Thread(target=httpd.serve_forever, daemon=True).start()
                try:
                    from playwright.sync_api import sync_playwright
                except Exception as e:
                    unverified("C2/C3/C4 浏览器通道", "playwright 不可用 %s" % e)
                    httpd.shutdown()
                    os.chdir(old_cwd)
                    return 2
                with sync_playwright() as pw:
                    try:
                        b, face = be_launch(pw, label="clean_clone_check")
                    except Exception as e:                    # noqa: BLE001
                        print("CLEAN-CLONE-ENV-UNVERIFIED 浏览器起不来（三档全败）%s"
                              % (str(e).splitlines()[0][:90] if str(e) else type(e).__name__))
                        return 2
                    pg = b.new_page(viewport={"width": 1280, "height": 860})
                    errs, failed = [], []
                    failed_why = []   # r65：原实现只留 URL 末段，把 `failure` 原因丢了 ⇒
                    # 良性中止与真缺件在证据上不可分（同族：测量须带状态码）。C4 判红时必须能自证是哪一类。
                    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                    pg.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)))
                    pg.on("requestfailed", lambda x: (failed.append(x.url.split("/")[-1]),
                                                      failed_why.append("%s<-%s" % (
                                                          x.url.split("/")[-1], x.failure))))
                    resp = pg.goto("http://127.0.0.1:%d/index.html" % port,
                                   wait_until="networkidle")
                    pg.wait_for_timeout(2500)
                    st = pg.evaluate("""() => ({
                        three: typeof THREE, gsap: typeof gsap, st: typeof ScrollTrigger,
                        acts: document.querySelectorAll('section.act').length,
                        gl: !!document.querySelector('#gl'),
                        input: !!document.querySelector('#chat-input')})""")
                    ok2 = (resp and resp.status == 200 and st["three"] == "object"
                           and st["gsap"] == "object" and st["st"] == "function"
                           and st["acts"] == 5 and st["gl"] and st["input"])
                    check("C2 干净克隆里页面真加载", ok2,
                          "http=%s %s" % (resp.status if resp else None, st))
                    ok3 = False
                    try:
                        pg.fill("#chat-input", "今天有点难过")
                        pg.click("button[type=submit]")
                        pg.wait_for_function(
                            "() => document.querySelectorAll('#chat-log .msg').length >= 2",
                            timeout=20000)
                        ok3 = True
                    except Exception as e:
                        detail3 = str(e)[:90]
                    check("C3 离线降级链路真走通", ok3, "" if ok3 else detail3)

                    hits, unknown, unknown_req = classify_errors(errs, failed)
                    check("C4 报错必须 ⊆ 已知缺口（新面孔即红）", not unknown and not unknown_req,
                          "未解释 console %d 条 %s；未登记失败请求 %s；失败原因 %s"
                          % (len(unknown), unknown[:1], unknown_req[:2], failed_why[:4]))
                    closed = [g for g, c in hits.items() if c == 0]
                    check("C5 已知缺口不得变成永久豁免", not closed,
                          "登记 %d 条，实测命中 %s%s"
                          % (len(KNOWN_GAPS),
                             ",".join("%s=%d" % (k.split("/")[-1], v)
                                      for k, v in hits.items() if v) or "无",
                             "；0 命中须销账：" + ",".join(x.split("/")[-1] for x in closed)
                             if closed else ""))
                    if closed:
                        print("     ⚠️ 缺口已不存在，请从 KNOWN_GAPS 删掉：%s"
                              % [x.split("/")[-1] for x in closed])
                    b.close()
                httpd.shutdown()
        finally:
            os.chdir(old_cwd)
    finally:
        if keep:
            print("（--keep）克隆留在：%s" % clone)
        else:
            shutil.rmtree(str(tmp), ignore_errors=True)

    bad = [n for n, ok, d in results if ok is False]
    unv = [n for n, ok, d in results if ok is None]
    print("=" * 72)
    if bad or unv:
        print("CLEAN-CLONE-FAIL 克隆态=%s 判红=%s 未验=%s"
              % (head[:7] if 'head' in dir() else "?", ",".join(bad), ",".join(unv)))
        return 1
    print("CLEAN-CLONE-PASS 引擎=%s 从 HEAD(%s) 克隆可跑：页面真加载+离线链路通+未知报错0；"
          "已登记缺口 %d 条（命中 %s）"
          % (short_face(face), head[:7], len(KNOWN_GAPS), ",".join("%s=%d" % (k, v) for k, v in hits.items())))
    return 0


def selftest():
    """登记表与配对规则的桩：误报侧不得判红，漏报侧必须点名，且必须用**真实形状**的输入。

    console 文本按真机原文写（里面没有 URL）——首版就是拿"含文件名的假想文本"喂桩，
    于是"已知缺口命中 1"这件事在测试里成立、在真机上永远不成立（M5④⑧ 又一次）。
    """
    ok, fail, n = 0, [], 0

    def want(cond, note):
        nonlocal n, ok
        if cond:
            ok += 1
        else:
            fail.append(note)
        n += 1

    C404 = "Failed to load resource: the server responded with a status of 404 (File not found)"
    U_KNOWN = "http://127.0.0.1:9/js/demo-config.js"

    h, u, ur = classify_errors([C404], [U_KNOWN])
    want(h["js/demo-config.js"] == 1 and not u and not ur,
         "误报侧：已知缺口被当成新面孔 unknown=%s req=%s" % (u, ur))
    h, u, ur = classify_errors([], ["http://x/js/ghost.js"])
    want(ur == ["ghost.js"], "漏报侧①：未登记的失败请求未被点名（取 url 末段）")
    h, u, ur = classify_errors(["TypeError: x is undefined"], [])
    want(len(u) == 1, "漏报侧②：非 404 类 console 报错被放过")
    h, u, ur = classify_errors([C404, C404], [U_KNOWN])
    want(len(u) == 1 and "未被已知缺口解释" in u[0], "漏报侧③：两条 404 只有一条被吸收，另一条必须显影")
    h, u, ur = classify_errors([], [])
    want(all(v == 0 for v in h.values()) and not u and not ur, "边界：零输入须全 0 且无未解释项")
    for x in fail:
        print("  FAIL " + x)
    print("CLEAN-CLONE-SELFTEST: %d/%d（误报 1｜漏报 3｜边界 1）" % (ok, n))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
