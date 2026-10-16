# -*- coding: utf-8 -*-
"""face_micro_proto_check.py — 微表情快通道（≥25fps）**原型可行性尺**（r183b 新建）。

目的（只证可行性，不进产品）：
  需求 4 要「微表情 ≥25fps 独立快通道」。线上主链（face-engine.js VIDEO 循环）归引擎轮；
  本尺只证一件事：**独立 FaceLandmarker 实例（VIDEO 模式 + GPU delegate）+ 现有规则层**，
  单帧整链耗时能否稳定 ≤40ms（=25fps 预算）。它是数字依据，不是产品代码。

判据（全部机器可判，禁拍脑袋）：
  · p95(e2e) ≤ 40ms 且 检出帧占比 ≥ 80% ⇒ FACE-MICRO-PROTO-PASS
  · p95 超 40ms ⇒ PASS 但口径标注（预算内的 fps 缺口在册，禁静默改口径）
  · harness 未就绪 ⇒ rc=2 UNVERIFIED，禁判绿

红线：零像素落盘（canvas 只在内存）、零网络请求（vendor 本地）。
用法：python _test/face_micro_proto_check.py [--frames N] [--json]
"""

import argparse, json, sys, threading, time, os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = "/_test/face-micro-harness.html"

def serve():
    os.chdir(str(ROOT))
    srv = HTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print("FACE-MICRO-PROTO-UNVERIFIED: playwright 不可用（%s）⇒ 禁判绿" % e)
        return 2
    sys.path.insert(0, str(ROOT / "_test"))
    from browser_engine import launch
    srv, port = serve()
    base = "http://127.0.0.1:%d" % port
    rows = []
    try:
        with sync_playwright() as pw:
            r = launch(pw, args=["--allow-file-access-from-files"], label="face-micro-proto")
            browser = r[0] if isinstance(r, tuple) else r
            tag = r[1] if isinstance(r, tuple) and len(r) > 1 else "?"
            try:
                pg = browser.new_page()
                pg.goto(base + HARNESS)
                pg.wait_for_function("() => { const h = window.__MICRO__; return h && (h.ready === true || h.err); }", timeout=180000)
                st = pg.evaluate("({ready: window.__MICRO__.ready, err: window.__MICRO__.err})")
                if not st.get("ready"):
                    print("FACE-MICRO-PROTO-UNVERIFIED: harness 未就绪 err=%s" % st.get("err"))
                    return 2
                for _ in range(a.frames):
                    rows.append(pg.evaluate("() => window.__MICRO__.frame()"))
            finally:
                browser.close()
    finally:
        srv.shutdown()
    return report_rows(rows, tag, a.json)


# ── r187：统计与判定抽成纯函数（此前内联在 main 里 ⇒ 无服务/无浏览器时整条判据
#    在受理面上等于不存在，G16 第五腿报它为孤儿）。抽出来才能带离线自检腿。
#    同轮修一处必崩缺陷（一手，非推断）：原代码 n=0 时 e2e[int(0.50*(n-1))]
#    即 e2e[-1] 对空表 ⇒ IndexError，而"零输入不得读成通过"是本仓三态口径的底线
#    ⇒ 现在 n=0 明确回 rc=2 UNVERIFIED。
def pct(vals, q):
    """分位数（入参必须已升序）。空表 ⇒ None，不返回 0（0 会被读成"极快"）。"""
    if not vals:
        return None
    return vals[int(q * (len(vals) - 1))]


def summarize(rows, tag):
    """纯函数：帧读数清单 → 汇总字典。零行 ⇒ None（调用方判未验，禁记绿）。"""
    if not rows:
        return None
    faces = [x for x in rows if x.get("face")]
    e2e = sorted(x["e2eMs"] for x in rows)
    inf = sorted(x["inferMs"] for x in rows)
    p95 = pct(e2e, 0.95)
    ratio = len(faces) / len(rows)
    return {"n": len(rows), "detect_ratio": round(ratio, 3),
            "e2e_p50_ms": pct(e2e, 0.50), "e2e_p95_ms": p95,
            "infer_p50_ms": pct(inf, 0.50), "infer_p95_ms": pct(inf, 0.95),
            "fps_at_p95": round(1000.0 / p95, 1) if p95 else None,
            "engine": tag}


def verdict_for(out):
    """纯函数：汇总 → 是否达 25fps 预算（p95 ≤ 40ms 且检出率 ≥ 80%）。"""
    return bool(out) and out["e2e_p95_ms"] <= 40.0 and out["detect_ratio"] >= 0.8


def report_rows(rows, tag, as_json):
    """落盘 + 打印 + 给退出码（主流程与自检共用同一条判定，禁两处写）。"""
    out = summarize(rows, tag)
    if out is None:
        print("FACE-MICRO-PROTO-UNVERIFIED: 零帧读数 ⇒ 不得读成通过")
        return 2
    ok = verdict_for(out)
    out["pass"] = ok
    dst = ROOT / "_test" / ("face-micro-proto-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    print("微表情快通道原型（n=%d，engine=%s）" % (out["n"], tag))
    print("  整链 e2e p50 %.2f ms ｜ p95 %.2f ms ｜ p95 对应 fps %.1f（预算 40ms=25fps）"
          % (out["e2e_p50_ms"], out["e2e_p95_ms"], 1000.0 / out["e2e_p95_ms"]))
    print("  推理 infer p50 %.2f ms ｜ p95 %.2f ms" % (out["infer_p50_ms"], out["infer_p95_ms"]))
    print("  检出帧 %d/%d = %.1f%%" % (round(out["detect_ratio"] * out["n"]), out["n"], 100 * out["detect_ratio"]))
    print("  机器件已落盘：" + str(dst.relative_to(ROOT)))
    print("FACE-MICRO-PROTO-PASS ≥25fps 预算内" if ok else
          "FACE-MICRO-PROTO-GAP: p95 %.2fms 超预算或检出率低 ⇒ 缺口在册（原型面，不影响线上）"
          % out["e2e_p95_ms"])
    return 0


def selftest():
    """离线腿：零浏览器零网络，验"这把尺量得动被审对象"。

    为什么这条腿有信息量：本件主流程要真起浏览器 + MediaPipe，CI/本机常不可达；
    若判定式被改坏（比如把 <= 写成 >=、或把检出率门删了），主流程在有 GPU 的机器上
    照样打 PASS ⇒ 必须有一把不依赖环境的尺钉住判定式本身。四类定向破坏各自必须翻红。
    """
    def mk(n, e2e, infer, face_n):
        rows = []
        for i in range(n):
            rows.append({"face": i < face_n, "e2eMs": e2e, "inferMs": infer})
        return rows
    bad = []
    good = mk(20, 30.0, 20.0, 20)
    s = summarize(good, "cpu")
    if not s or s["e2e_p95_ms"] != 30.0 or s["detect_ratio"] != 1.0:
        bad.append("正例 汇总读数不自洽: %r" % s)
    if not verdict_for(s):
        bad.append("正例 30ms/100%% 必须判达预算")
    # 反向腿 1：p95 超预算 ⇒ 必须不通过
    if verdict_for(summarize(mk(20, 41.0, 20.0, 20), "cpu")):
        bad.append("反例1 p95=41ms 仍判通过")
    # 反向腿 2：检出率 79% ⇒ 必须不通过（门是 80%）
    if verdict_for(summarize(mk(100, 30.0, 20.0, 79), "cpu")):
        bad.append("反例2 检出率 79% 仍判通过")
    # 反向腿 3：零帧 ⇒ summarize 必须给 None（禁把空表读成"极快"）
    if summarize([], "cpu") is not None:
        bad.append("反例3 零帧未被拒")
    # 反向腿 4：分位数取空表必须 None 而非 0
    if pct([], 0.95) is not None:
        bad.append("反例4 空表分位数不是 None")
    # 反向腿 5：尾部延迟必须被 p95 抓到（p50 好看、p95 爆表 ⇒ 判不过）。
    #   ⚠ 现行分位数定义 = vals[int(q*(n-1))]（沿用本件 r183b 原口径，本轮**不改测量口径**）：
    #   n=20 时 p95 落在 index 18 ⇒ **单个**离群点（index 19）抓不到，这是该定义的固有性质，
    #   不是本件的缺陷；默认 --frames 60 时 index 57 ⇒ 容忍 2 个离群点。故本腿用 3 个慢帧
    #   （跨过该边界）来验"尾部真能被抓到"，并把边界如实钉在这里，供下一轮判断是否抬 frames。
    tail = [{"face": True, "e2eMs": (30.0 if i < 17 else 500.0), "inferMs": 20.0} for i in range(20)]
    st = summarize(tail, "cpu")
    if st["e2e_p95_ms"] != 500.0 or verdict_for(st):
        bad.append("反例5 尾部延迟未被 p95 抓到: %r" % st)
    if bad:
        print("FACE-MICRO-PROTO-SELFTEST:FAIL %d 项" % len(bad))
        for x in bad:
            print("  FAIL " + x)
        return 1
    print("FACE-MICRO-PROTO-SELFTEST-PASS: 7 腿（2 正例 + 5 反向）")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
