# -*- coding: utf-8 -*-
"""F14 · 单帧面部情绪识别**延迟**尺（r173 新建）

为什么要单建一把延迟尺（r132 已有埋点，为什么不够）：
  r132 的埋点只在**真人开摄像头跑起来时**才产生数据 —— 它回答「那次运行慢不慢」，
  答不了「这个发布版有没有退化」。要把 ≤100ms 写成**对外可复核的承诺**，必须有一把
  不用人、（有 ci --latency 就能）产生分位数的尺。本件就是那把尺。

量什么（三个数缺一不可，只报一个就是挑好看的那个）：
  inferMs  MediaPipe detectForVideo 的单次推理耗时（模型在此，通常是大头）
  computeMs FaceEngine.read() 的规则层计算（onstr：r173 实测 p95 ≈ 0.03ms，可忽略）
  e2eMs    取帧 + 推理 + 规则 + EMA 平滑的**整链**，即「画面 → 读数」的真实延迟
  判定用 e2e 的 p95（不是 p50）：p50 好看不代表交互不卡 —— 卡的是尾部。

输入夹具：**真脸**（把 `_test/face-fixtures/smile-*.jpg` 合成 y4m 假摄像头喂给
`getUserMedia`），由 `_test/face_check.py:make_fake_cam()` 产出 —— 复用而非另Cook 一份。
为什么必须是真脸：合成图案会让 MediaPipe 的人脸检测器早退（0 人脸路径 ≈ 几 ms），
那样量出来的延迟是"没活干时的延迟"，会被当成性能证据。

退出码：
  0 = 有真脸样本且 p95 ≤ 100ms
  1 = 超预算（真实退化，必须修）
  2 = 环境不可用（浏览器/假摄像头/模型都 VOID）⇒ **不是通过**，禁止把 2 读成绿
"""
import argparse
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "_test"
sys.path.insert(0, str(TEST_DIR))            # 复用 face_check.make_fake_cam，不另 Cook 一份
from check_instrument import install_excepthook  # noqa: E402

HARNESS = "/_test/face-latency-harness.html"
BUDGET_MS = 100.0
N_RUNS = 150


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)


def _serve():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


HARNESS_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>face latency harness</title></head><body>
<!-- 与 face-harness.html 的区别：那一件跑 IMAGE 模式（照片），这一件跑 **VIDEO 模式**（摄像头），
     因为线上真实链路就是 VIDEO；用照片模式量延迟会把「不受帧率约束的那条路径」当成延迟证据。
     接 desktop Sized fake camera（Chrome --use-file-for-fake-video-capture），画面是一张真笑脸的循环。 -->
<script src="../src/data/emotion-lexicon.js"></script>
<script src="../src/js/emotion-engine.js"></script>
<script src="../src/data/face-smile-rules.js"></script>
<script src="../src/js/face-engine.js"></script>
<script type="module">
import { FaceLandmarker, FilesetResolver } from "../src/vendor/mediapipe/vision_bundle.js";
const BASE = new URL("../src/vendor/mediapipe/", import.meta.url).href;
const MODEL = new URL("../src/vendor/mediapipe/face_landmarker.task", import.meta.url).href;
window.__LAT__ = { ready: false, err: null, delegate: null };
(async () => {
  try {
    const fileset = await FilesetResolver.forVisionTasks(BASE);
    let lm, delegate = "GPU";
    try {
      lm = await FaceLandmarker.createFromOptions(fileset, { baseOptions: { modelAssetPath: MODEL, delegate: "GPU" }, runningMode: "VIDEO", numFaces: 1, outputFaceBlendshapes: true, outputFacialTransformationMatrixes: false });
    } catch (e) {
      delegate = "CPU";
      lm = await FaceLandmarker.createFromOptions(fileset, { baseOptions: { modelAssetPath: MODEL, delegate: "CPU" }, runningMode: "VIDEO", numFaces: 1, outputFaceBlendshapes: true, outputFacialTransformationMatrixes: false });
    }
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    const v = document.createElement("video");
    v.playsInline = true; v.muted = true; v.srcObject = stream;
    await v.play();
    window.__LAT__ = {
      ready: true, err: null, delegate: delegate,
      run: async (n) => {
        // 与 face-engine.js 的采样循环同构：取帧 → detectForVideo → read → EMA 平滑
        let prev = null, ema = null;
        const infer = [], comp = [], e2e = [];
        let faces = 0;
        for (let i = 0; i < n; i++) {
          const t0 = performance.now();
          const ts = performance.now();
          const r = lm.detectForVideo(v, ts);
          const t1 = performance.now();
          const cats = (r && r.faceBlendshapes && r.faceBlendshapes[0]) ? r.faceBlendshapes[0].categories : null;
          if (cats) faces++;
          const bs = {};
          if (cats) for (const c of cats) bs[c.categoryName] = c.score;
          const view = window.FaceEngine.read(bs, prev);
          const t2 = performance.now();
          // EMA 平滑（与运行时同一条 α=0.3 的口径）
          const curve = view.all.map(x => x.score);
          ema = ema === null ? curve : curve.map((x, k) => ema[k] * 0.7 + x * 0.3);
          const t3 = performance.now();
          prev = bs;
          infer.push(t1 - t0); comp.push(t2 - t1); e2e.push(t3 - t0);
          await new Promise(res => requestAnimationFrame(() => res()));
        }
        return { infer, comp, e2e, faces, n };
      }
    };
  } catch (e) {
    window.__LAT__ = { ready: false, err: String((e && e.message) || e) };
  }
})();
</script>
</body></html>
"""


def _pct(vals, q):
    s = sorted(vals)
    if not s:
        return None
    return s[min(len(s) - 1, int(q * (len(s) - 1)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=N_RUNS)
    ap.add_argument("--json", default="", help="机器件落盘路径（默认 _test/face-latency-<stamp>.json）")
    ap.add_argument("--ci", action="store_true", help="CI 面：受管 chromium，不改检验口径")
    args = ap.parse_args()
    install_excepthook("face_latency_check")

    cam = None
    try:
        from face_check import make_fake_cam, MEDIA_ARGS
    except Exception as e:  # noqa: BLE001
        print("FACE-LATENCY-UNVERIFIED 取不到 face_check.make_fake_cam：%s" % e)
        return 2
    cam = make_fake_cam()
    if not cam or not Path(cam).is_file():
        print("FACE-LATENCY-UNVERIFIED 假摄像头合成失败（ffmpeg 或缺源图）⇒ "
              "**未验**，禁止把本行读成通过")
        return 2

    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch                       # E2 唯一入口，禁止裸 chromium.launch
    except Exception as e:  # noqa: BLE001
        print("FACE-LATENCY-UNVERIFIED 浏览器通道不可用：%s" % e)
        return 2

    srv, base = _serve()
    # 宿主页采用 face_discrim/lowintensity 同款的「脚本自带、运行时现给」手法（此处由路由
    # 在内存里 fulfill，不落盘）：好处是原型与本件永远同 revision，不出现
    # 「磁盘上的宿主页比脚本旧」这种双份真相，也不会在仓库里留下派生件。
    try:
        with sync_playwright() as pw:
            largs = list(MEDIA_ARGS) + ["--use-file-for-fake-video-capture=" + str(cam)]
            browser, face = launch(pw, args=largs, label="face_latency_check")
            print("引擎=%s ｜ 夹具=%s（真面孔 y4m 循环）" % (face.split(" 原因=")[0], Path(cam).name))
            try:
                ctx = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 900})
                pg = ctx.new_page()
                pg.route("**/face-latency-harness.html",
                         lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8",
                                                     body=HARNESS_HTML))
                pg.goto(base + HARNESS, wait_until="load")
                try:
                    pg.wait_for_function(
                        "() => window.__LAT__ && (window.__LAT__.ready === true || window.__LAT__.err)",
                        timeout=180000)
                except Exception:  # noqa: BLE001
                    pass
                st = pg.evaluate("({ready: window.__LAT__.ready, err: window.__LAT__.err,"
                                 " run: typeof window.__LAT__.run})")
                if not st.get("ready") or st.get("run") != "function":
                    print("FACE-LATENCY-UNVERIFIED FaceLandmarker 没起来：%s ⇒ **未验**"
                          % st.get("err"))
                    return 2
                delegate = pg.evaluate("window.__LAT__.delegate")
                res = pg.evaluate("async (n) => window.__LAT__.run(n)", args.runs)
            finally:
                try:
                    browser.close()
                except Exception:  # noqa: BLE001
                    pass
    finally:
        srv.shutdown()

    faces = res.get("faces", 0)
    n = res.get("n", 0)
    if not n or faces == 0:
        print("FACE-LATENCY-UNVERIFIED %d 帧里检出人脸 %d 次 ⇒ 量到的是「没有脸时的推理」"
              % (n, faces))
        return 2

    rep = {"runs": n, "faces_detected": faces, "delegate": delegate, "budget_ms": BUDGET_MS}
    for k, key in (("infer", "inferMs"), ("comp", "computeMs"), ("e2e", "e2eMs")):
        vals = res.get(k) or []
        rep[key] = {"p50": _pct(vals, 0.50), "p95": _pct(vals, 0.95), "max": max(vals) if vals else None}
    print("\n单帧面部情绪识别延迟（n=%d，其中 %d 帧检出人脸，delegate=%s）" % (n, faces, delegate))
    for key in ("inferMs", "computeMs", "e2eMs"):
        d = rep[key]
        print("  %-10s p50 %6.2f ms ｜ p95 %6.2f ms ｜ max %6.2f ms"
              % (key, d["p50"], d["p95"], d["max"]))

    dst = Path(args.json) if args.json else (
        TEST_DIR / ("face-latency-%s.json" % _stamp()))
    dst.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  机器件：" + str(dst.relative_to(ROOT)))

    p95 = rep["e2eMs"]["p95"]
    if p95 > BUDGET_MS:
        print("\nFACE-LATENCY-FAIL 单帧整链 p95 %.1f ms > 预算 %.0f ms ⇒ 真实退化"
              % (p95, BUDGET_MS))
        return 1
    print("\nFACE-LATENCY-PASS 单帧整链 p95 %.1f ms ≤ 预算 %.0f ms（每 %d 帧里有 %d 帧检出人脸）"
          % (p95, BUDGET_MS, n, faces))
    return 0


def _stamp():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print("FACE-LATENCY-ERROR %s：%s" % (type(e).__name__, e))
        sys.exit(2)
