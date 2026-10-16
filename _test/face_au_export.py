# -*- coding: utf-8 -*-
"""face_au_export.py — 真实照片 → 52 维 AU JSON 导出腿（S4 工程地基，轮132）

为什么要有这件：
  F11/F12 两把尺量的是**合成 AU 向量**，`face_lowintensity_check.py` 的 docstring 已写明
  「不能当成真实场景准确率」；而真照片那一层（F5）只有 12 张、覆盖 4 类，fear/disgust/
  contempt 零真照 ⇒ **真实流至今没有常驻尺子**。这是 `memory/11-face-accuracy.part4` §五
  里「真照片 AU 回放」那一行的实现。

隐私红线（与既有红线同族，**不得放宽**）：
  落盘**只有 52 维 blendshape 参数 + 标注 + 文件名**，**不落任何图像像素**。
  照片本体留在 `_test/face-fixtures/`（既有夹具，本就入库），本件不复制、不转存、不外发。

用法：
  python _test/face_au_export.py            # 导出/刷新 _test/face-au/*.json
  python _test/face_au_export.py --check    # 只校验语料与名册一致，不跑浏览器
退出码：0=导出/校验完成 1=名册不一致（判红） 2=环境未验（浏览器起不来 / 模型没就绪，禁判绿）

⚠️ 本件**不进电池**（需 Chrome + 数十秒）；进电池的是 `face_au_replay_check.py`（纯 node）。
浏览器一律走 `_test/browser_engine.py` 的 launch（唯一实现，禁止手写回退链）。
"""
import argparse
import json
import mimetypes
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from check_instrument import install_excepthook   # r113：进程级兜底，绝不裸抛栈
install_excepthook("FACE-AU-EXPORT")

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "_test" / "face-fixtures"
LABELS = FIX / "labels.json"
OUT = ROOT / "_test" / "face-au"
HARNESS = "/_test/face-harness.html"


class _Handler(SimpleHTTPRequestHandler):
    """只读、只服务项目根、静音访问日志。

    ⚠️ 必须走 HTTP 不能用 file://：face-harness.html 是 ESM + MediaPipe wasm，
       file:// 下 ESM 被 Chrome 按 CORS 拦、wasm fetch 也失败 ⇒ 实测报
       `Aborted(both async and sync fetching of the wasm failed)`。
       （本仓 `face_check.py` 的 serve() 是同一坑的既有正解，照抄其 mimetypes 三行。）
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a, **k):
        pass


def serve():
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("application/wasm", ".wasm")
    mimetypes.add_type("application/octet-stream", ".task")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)   # 0 = 自动分配，守端口属主协议
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]

# labels.json 的标注值 → 引擎 8 类输出的期望主情绪。（r183：新增 sadness/disgust 两类真照片）
# ⚠️ 这是**人工映射**（照片名册用的是 smiling/neutral 这类词，引擎输出 joy/calm），
#   映射表落在这里是为了让「改映射」等于一次可审计的代码改动，而不是藏在数据里。
WANT = {"smiling": "joy", "neutral": "calm", "anger": "anger", "surprise": "surprise",
        "sadness": "sadness", "disgust": "disgust", "fear": "fear"}


def roster():
    """(labels.json 条目, 磁盘实有 jpg) 的双向差集——任一方向缺项即判红。

    为什么要双向：只查「labels 有而 jpg 没有」会漏掉「jpg 多出来没人标注」，
    而后者会让复算腿的分母悄悄变大（拿没标注的照去判对错）。
    """
    if not LABELS.is_file():
        return None, ["labels.json 不存在：%s" % LABELS]
    try:
        labs = json.loads(LABELS.read_text("utf-8"))
    except Exception as e:  # noqa: BLE001
        return None, ["labels.json 不可解析：%s" % e]
    if not isinstance(labs, list) or not labs:
        return None, ["labels.json 不是非空列表 ⇒ 语料无名册，禁当空集合判绿"]
    labeled = set()
    bad = []
    for e in labs:
        f, lab = e.get("file"), e.get("label")
        if not f or not lab:
            bad.append("labels.json 有条目缺 file/label：%r" % (e,))
            continue
        if lab not in WANT:
            bad.append("labels.json 出现未映射标注 %r（映射表见本文件 WANT）" % lab)
        if not (FIX / f).is_file():
            bad.append("labels.json 列了 %s 但磁盘没有该照" % f)
        labeled.add(f)
    # r183t+：provenance 结构守卫——名册条目必须带 prov/sha1/license 三键（A/B/derived 级之外
    #   不得有裸条目）。这是 R196「新增评测数据先登记 provenance」的机器化延伸：只查 file/label
    #   会放过「有标注没出处」的半登记态，而半登记态正是 r183 之前 14 张照的成因。
    for e in labs:
        f = e.get("file", "?")
        if not e.get("prov") or not e.get("sha1") or not e.get("license"):
            bad.append("%s 名册条目缺 prov/sha1/license（半登记态，R196 红线）" % f)
    disk = {p.name for p in FIX.glob("*.jpg")}
    for extra in sorted(disk - labeled):
        bad.append("磁盘有 %s 但 labels.json 没登记（会虚增复算腿分母）" % extra)
    return (labs, []) if not bad else (None, bad)


def check_only():
    labs, bad = roster()
    if bad:
        return ["名册双向对账失败（%d 项）：%s" % (len(bad), "；".join(bad[:6]))]
    n_json = len(list(OUT.glob("*.json"))) if OUT.is_dir() else 0
    print("AU-EXPORT-CHECK: 名册 %d 条双向一致｜语料目录 _test/face-au/ 现有 %d 个 JSON" % (len(labs), n_json))
    return []


def export():
    """一律返回 (errors, fatal)：errors 恒为 list（判红面），fatal 为 None 或 list（未验面）。
    ⚠️ 禁再出现 `(None, [...])` 这种 errors=None 的形态——v1 就是失败路径自己抛
    TypeError 把真实原因（harness 为何未就绪）吞掉，判据没出结论行。
    """
    labs, bad = roster()
    if bad:
        return ["名册双向对账失败（%d 项）：%s" % (len(bad), "；".join(bad[:6]))], None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return [], ["playwright 不可用：%s ⇒ 导出未验（禁判绿）" % e]
    sys.path.insert(0, str(ROOT / "_test"))
    from browser_engine import launch

    OUT.mkdir(parents=True, exist_ok=True)
    srv, port = serve()
    base = "http://127.0.0.1:%d" % port
    written, skipped = 0, []
    try:
        with sync_playwright() as pw:
            r = launch(pw, args=["--allow-file-access-from-files"], label="face-au-export")
            browser = r[0] if isinstance(r, tuple) else r
            tag = (r[1] if isinstance(r, tuple) and len(r) > 1 else "?")
            try:
                pg = browser.new_page()
                pg.goto(base + HARNESS)
                # ⚠️ 模型是异步懒加载的：__HARNESS__ 一挂上只有 {ready,err}，
                #    detect 要等 FaceLandmarker 建完才挂上 ⇒ 等 ready 且等 detect 出现。
                pg.wait_for_function(
                    "() => { const h = window.__HARNESS__;"
                    "  return h && (h.ready === true || h.err); }", timeout=180000)
                st = pg.evaluate("({ready: window.__HARNESS__.ready, err: window.__HARNESS__.err,"
                                 "  detect: typeof window.__HARNESS__.detect})")
                if not st.get("ready") or st.get("detect") != "function":
                    return [], ["harness 未就绪（ready=%s detect=%s err=%s）⇒ 导出未验，禁判绿"
                                % (st.get("ready"), st.get("detect"), st.get("err"))]
                for e in labs:
                    f = e["file"]
                    d = pg.evaluate("u => window.__HARNESS__.detect(u)", "/_test/face-fixtures/" + f)
                    if not d or int(d.get("faces") or 0) < 1 or not d.get("bs"):
                        skipped.append("%s(faces=%s)" % (f, (d or {}).get("faces")))
                        continue
                    bs = {k: round(float(v), 6) for k, v in d["bs"].items()}
                    missing_dims = [k for k in WANT_LABELS_DIMENSIONS if k not in bs]
                    # meta 由 harness 现算（luma / yaw / faceSize），r173 起写进 fixture。
                    # ⚠️ meta 缺失时必须存 None 而不是空字典：空字典会被下游读成「有 meta 但全空」，
                    #    而 F16 的分层切片正是靠 meta 有无来决定出数字还是出「不可测」——
                    #    这两件事必须分得开，否则「没测」又会被当成「测了」。
                    rec = {"file": f, "label": e["label"], "want": WANT[e["label"]],
                           "faces": int(d["faces"]), "dim": len(bs),
                           "missing_dims": missing_dims, "bs": bs,
                           # r183b：age_group/gender 两轴由名册（labels.json，唯一人工标注源）随 meta 带出，
                           #   F16 的切片据此出数字；名册没标就是 None ⇒ 切片如实报「未标注」，不造数。
                           "meta": (lambda m: (m.update({"age_group": e.get("age_group"),
                                                         "gender": e.get("gender"),
                                                         "prov": e.get("prov"),
                                                         "license": e.get("license")}) or m)
                                     if isinstance(m, dict) else m)(d.get("meta") or None),
                           "view": {"emotion": d["view"]["emotion"],
                                    "intensity": d["view"]["intensity"],
                                    "confidence": d["view"]["confidence"],
                                    "confident": d["view"]["confident"]},
                           "source": e.get("source", ""), "note": e.get("note", "")}
                    (OUT / (Path(f).stem + ".json")).write_text(
                        json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                    written += 1
            finally:
                browser.close()
    finally:
        srv.shutdown()
    print("AU-EXPORT: 引擎=%s｜落盘 %d 条 → _test/face-au/（只存 52 维参数，不存图）" % (tag, written))
    if skipped:
        print("AU-EXPORT-SKIPPED: %d 张没检出人脸（单列，不混进「判错」）：%s"
              % (len(skipped), ", ".join(skipped)))
    return [], None


# MediaPipe FaceLandmarker 的 52 维标准名（缺项只报不判红：版本间可能增删）
WANT_LABELS_DIMENSIONS = [
    "_neutral", "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft",
    "browOuterUpRight", "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight",
    "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
    "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft", "jawOpen", "jawRight",
    "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft",
    "mouthFrownRight", "mouthFunnel", "mouthLeft", "mouthLowerDownLeft",
    "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight", "mouthPucker",
    "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower",
    "mouthShrugUpper", "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft",
    "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight", "noseSneerLeft",
    "noseSneerRight",
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验名册，不跑浏览器")
    a = ap.parse_args()
    if a.check:
        errs, fatal = check_only(), None
    else:
        errs, fatal = export()
    for m in errs or []:
        print("  " + m)
    for m in fatal or []:
        print("  " + m)
    if fatal:
        print("FACE-AU-EXPORT-UNVERIFIED: %s" % fatal[0][:90])
        sys.exit(2)
    if errs:
        print("FACE-AU-EXPORT-FAIL")
        sys.exit(1)
    if not a.check:
        print("FACE-AU-EXPORT-PASS")
    sys.exit(0)