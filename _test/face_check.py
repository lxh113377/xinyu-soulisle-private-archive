# -*- coding: utf-8 -*-
"""face_check.py — 面部表情识别常驻判据（r87）

为什么单独立一件（而不是塞进 browser_check）：
  这个功能有一组**别的套件判不到**的失效形态，且每一条都能被"看起来全绿"掩盖：
    F1 vendor 完整性     —— 13MB 的 wasm/模型被换字节后，页面上只是"点开没反应"
    F2 接线面            —— ESM 桥没挂号 / CSP 没放行 wasm / 摄像头被 Permissions-Policy 掐死
    F3 判据语义          —— 真笑 vs 强颜欢笑必须可分，且阈值必须真参与计算（可证伪）
    F4 摄像头开合        —— 关掉后轨道必须真停（指示灯灭），且全程零 pageerror
    F5 真实照片实跑      —— 判据不是"自比恒等"：真照片上微笑组与中性组必须分得开
    F6 无摄像头降级      —— 入口必须消失而不是点下去报错（禁伪装红线）

浏览器一律走 `_test/browser_engine.py` 的 launch（唯一实现，禁止各套件手写回退链）。

用法：python _test/face_check.py [--selftest]
退出码：0=绿 1=红 2=没跑到（浏览器起不来 / node 不可用 / 夹具缺失 ⇒ 不静默当绿）
"""
import argparse
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from check_instrument import install_excepthook   # r113：进程级兜底——任何未捕获异常都必须印出结论行，绝不裸抛栈
install_excepthook("FACE-CHECK")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

FIX_DIR = ROOT / "_test" / "face-fixtures"
MANIFEST = ROOT / "_test" / "vendor-manifest.json"
HARNESS = ROOT / "_test" / "face-harness.html"
UNIT = ROOT / "_test" / "js" / "face-engine.unit.test.mjs"
NEW_FILES = ["js/face-engine.js", "js/face-mediapipe-bridge.js", "data/face-smile-rules.js"]
MEDIA_ARGS = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
              "--allow-file-access-from-files"]


# ── F1 · vendor 完整性 ────────────────────────────────────────────────────
def f1_bad(manifest_text=None, disk=None):
    """manifest 声明的 mediapipe 四件套必须都在且 sha256 相符。
    disk 可注入（selftest 用），默认真读磁盘。"""
    bad = []
    try:
        man = json.loads(manifest_text) if manifest_text else json.loads(MANIFEST.read_text("utf-8"))
    except Exception as e:  # noqa: BLE001
        return ["F1 vendor-manifest.json 不可解析：%s" % e]
    entries = [x for x in man.get("libs", []) if "vendor/mediapipe/" in (x.get("file") or "")]
    if len(entries) < 4:
        bad.append("F1 manifest 里 mediapipe 条目只有 %d 条（应 4 条）⇒ 新 vendor 没登记，被替换也看不见" % len(entries))
    for e in entries:
        p = ROOT / e["file"]
        if disk is not None and e["file"] in disk:
            data = disk[e["file"]]
        else:
            if not p.is_file():
                bad.append("F1 %s 不在磁盘上" % e["file"])
                continue
            data = p.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != e.get("sha256"):
            bad.append("F1 %s 校验和不符：manifest=%s 实测=%s" % (e["file"], (e.get("sha256") or "")[:12], sha[:12]))
        if len(data) < 1024:
            bad.append("F1 %s 只有 %d 字节 ⇒ 下载残缺却被当成在位" % (e["file"], len(data)))
    return bad


# ── F2 · 接线面（纯静态，可注入反例）─────────────────────────────────────
def f2_bad(html_src, html_dep, sw_text, headers_text, dep_files):
    bad = []
    if 'src="data/face-smile-rules.js"' not in html_src:
        bad.append("F2 src/index.html 未加载 data/face-smile-rules.js（判据真相源没挂号）")
    if 'src="js/face-engine.js"' not in html_src:
        bad.append("F2 src/index.html 未加载 js/face-engine.js")
    if 'type="module" src="js/face-mediapipe-bridge.js"' not in html_src:
        bad.append("F2 src/index.html 未以 type=module 挂 js/face-mediapipe-bridge.js（ESM 桥丢了 ⇒ 永远 unavailable）")
    for f in NEW_FILES:
        if 'src="%s"' % f.replace("data/", "data/") not in html_dep:
            bad.append("F2 deploy/xinyu/index.html 缺 %s ⇒ 公网副本与权威源漂移" % f)
        if not dep_files.get(f, False):
            bad.append("F2 deploy/xinyu/%s 文件不在磁盘上" % f)
    for f in NEW_FILES:
        if ('"/%s"' % f) not in sw_text:
            bad.append("F2 src/sw.js PRECACHE 缺 /%s ⇒ 断网重载会 404（r45 同族）" % f)
    # CSP：wasm 必须放行，否则 wasm 编译被拒而页面只显示"识别不了"。
    # ⚠️ 必须**按行锚定**到声明行：_headers 顶部的说明注释里也写着 "script-src" 字样，
    #    裸 `script-src ([^;]+);` 会因 `[^;]` 跨行而先匹配到注释（首跑就这么假红的）。
    line = re.search(r"^\s*Content-Security-Policy:\s*([^\n]+)", headers_text, re.M)
    csp = line.group(1) if line else ""
    m = re.search(r"script-src ([^;]*);", csp)
    if not line:
        bad.append("F2 _headers 里读不到 Content-Security-Policy 声明行")
    elif not m:
        bad.append("F2 CSP 里读不到 script-src 指令")
    else:
        src = m.group(1)
        if "'wasm-unsafe-eval'" not in src:
            bad.append("F2 script-src 缺 'wasm-unsafe-eval' ⇒ MediaPipe wasm 编译被 CSP 拒绝")
        # （旧版这里曾无条件禁裸 'unsafe-eval'；r87 公网实测推翻了它 —— MediaPipe 的 wasm 链
        #   连 eval 都要用，详见 _headers 的 CSP-EVAL-EXCEPTION 与 headers_csp H3 的具名豁免。）
    # 'unsafe-eval' 是 r87 为 MediaPipe wasm 链逼出来的**唯一放宽**，必须带具名豁免标记；
    # 没有标记却出现 ⇒ 就是"悄悄放宽"，与 headers_csp H3 同一条棘轮，这里再钉一次
    if "'unsafe-eval'" in (m.group(1) if m else ""):
        bare = re.search(r"(?<!wasm-)'unsafe-eval'", m.group(1) if m else "")
        if bare and "CSP-EVAL-EXCEPTION" not in headers_text:
            bad.append("F2 script-src 含裸 'unsafe-eval' 但 _headers 里没有 CSP-EVAL-EXCEPTION 具名豁免标记"
                       " ⇒ 悄悄放宽，headers_csp H3 也会红")
    # 摄像头策略：camera=() 会把 getUserMedia 当场掐死
    pm = re.search(r"Permissions-Policy:\s*([^\n]+)", headers_text)
    if not pm:
        bad.append("F2 _headers 里读不到 Permissions-Policy")
    elif "camera=(self)" not in pm.group(1):
        bad.append("F2 Permissions-Policy 未放行 camera=(self) ⇒ 摄像头被策略掐死，按钮点了就报错")
    return bad


# ── F5 · 真实照片判定的纯函数（可注入反例，浏览器只负责取数）──────────────
def f12_report(rows):
    """F12 · 真实照片逐类准确率。返回 (bad, 读数行)。
    分两类判据：
      · **可分性**（硬门）：每一类至少一张照片能**被检出脸**且**读数在动**
        —— 否则说明这条类别在真模型上根本不可达，属于夹具或模型的问题。
      · **准确率**（记账，非门）：逐类打印，供人工判断取舍。
        anger 类**已知不可达**（原因见 browser_legs 里 F12 注释），不判红也不许悄悄抹掉。
    """
    bad, out = [], []
    if not rows:
        return ["F12 零条读数 ⇒ 没跑到，不得当绿"], out
    by = {}
    for r in rows:
        by.setdefault(r["label"], []).append(r)
    for lab in sorted(by):
        rs = by[lab]
        seen = [r for r in rs if r.get("faces", 0) > 0]
        hit = [r for r in seen if r.get("got") == lab]
        acc = (100.0 * len(hit) / len(seen)) if seen else 0.0
        out.append("%s %d/%d(%.0f%%) 实得=%s" % (lab, len(hit), len(seen), acc,
                                              ",".join(sorted({r.get("got") or "-" for r in seen}))))
        if not seen:
            bad.append("F12 类别 %s 全部没检出人脸（%d 张）⇒ 这条类在真模型上不可达"
                       % (lab, len(rs)))
            continue
        # 读到脸却**一个情绪名都没有**（got 为 None/空串）⇒ 判据失灵，
        # 不能当成"这一类不可达"混过去（首版漏了这句，被 selftest 当场抓住）。
        if not any(r.get("got") for r in seen):
            bad.append("F12 类别 %s 检出人脸但读数恒为空（got=None）⇒ 判据失灵，不是类别不可达"
                       % lab)
    return bad, out


def f12_bad_injected(rows, mutate):
    """给 selftest 用：注入反例后 f12_report 必须报红。"""
    bad, _ = f12_report([mutate(dict(r)) for r in rows])
    return bad


def f5_bad(rows):
    """rows: [{file,label,faces,mouth,ratio,emotion,intensity,smile_kind}]
    判据：微笑组与中性组的口部微笑量必须**完全可分**（最小的笑 > 最大的不笑）。
    这条比"检出率 ≥ x"硬：它要求判据有排序能力，而不是碰巧对几张点头。"""
    bad = []
    if not rows:
        return ["F5 零条读数 ⇒ 没跑到，不得当绿"]
    nod = [r for r in rows if r.get("faces", 0) < 1]
    if len(nod) > 1:
        bad.append("F5 %d 张照片没检出人脸（%s）⇒ 夹具或模型有问题"
                   % (len(nod), ",".join(r["file"] for r in nod)))
    smi = [r for r in rows if r.get("label") == "smiling" and r.get("faces", 0) > 0]
    neu = [r for r in rows if r.get("label") == "neutral" and r.get("faces", 0) > 0]
    if len(smi) < 2 or len(neu) < 2:
        return bad + ["F5 有效样本不足（微笑 %d / 中性 %d）⇒ 分母太小，结论不可复核" % (len(smi), len(neu))]
    lo, hi = min(r["mouth"] for r in smi), max(r["mouth"] for r in neu)
    if not (lo > hi):
        bad.append("F5 微笑组与中性组**不可分**：微笑组最小 mouth=%.3f ≤ 中性组最大 mouth=%.3f ⇒ 判据无判别力" % (lo, hi))
    # 读数非恒等：全组同一个主情绪说明判据塌了（或照片全没检出）
    if len({r.get("emotion") for r in rows if r.get("faces", 0) > 0}) < 2:
        bad.append("F5 所有照片读数同一个主情绪 ⇒ 判据退化成常量，无法区分任何表情")
    # Duchenne 判据的**真照片对账**：标注为 candid 微笑的必须判成真笑。
    # 这一条是门槛标定的守门员 —— 第一版 ratioOn=0.45 就是被它抓出来的
    #（4 张真笑照实测 ratio 0.269~0.326 全被判成"社交性微笑"⇒ 门槛拍脑袋了）。
    wrong = [r for r in smi if r.get("smile_kind") != "duchenne"]
    if wrong:
        bad.append("F5 %d 张真笑照片被判成 %s（ratio=%s）⇒ Duchenne 门槛标定错了，不是照片的错"
                   % (len(wrong), ",".join(sorted({r["smile_kind"] for r in wrong})),
                      ",".join("%.3f" % r["ratio"] for r in wrong)))
    return bad


# ── F3 · 判据单测（跑 node --test）───────────────────────────────────────
def run_f3():
    if not UNIT.is_file():
        return 2, ["F3 _test/js/face-engine.unit.test.mjs 不存在"]
    try:
        p = subprocess.run(["node", "--test", str(UNIT)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    except Exception as e:  # noqa: BLE001
        return 2, ["F3 node 跑不起来：%s" % e]
    out = (p.stdout or "") + (p.stderr or "")
    m = {k: int(v) for k, v in re.findall(r"^\s*(?:ℹ\s*)?(tests|pass|fail)\s+(\d+)", out, re.M)}
    if not m:
        return 2, ["F3 node --test 输出里解析不到计数（套件没真跑）"]
    bad = []
    if m.get("fail", 0) != 0:
        bad.append("F3 单测有 %d 条红" % m["fail"])
    if m.get("pass", 0) < 8:
        bad.append("F3 通过用例只有 %d 条（应 ≥8）⇒ 判据面被削减" % m.get("pass", 0))
    return (1 if bad else 0), bad


# ── 浏览器腿：F4 摄像头开合 / F5 照片实跑 / F6 无摄像头降级 ───────────────
def make_fake_cam():
    """把一张真实微笑照合成 y4m 假摄像头流 —— 让**实时链路**（VIDEO 模式 + 摄像头路径）
    跑在真脸上，而不是只测"开启/关闭不报错"。

    Chromium 的 `--use-file-for-fake-video-capture` 只吃未压缩的 y4m/mjpeg，
    所以这一步必须现做（约 3MB，落在已 ignore 的 _test/_shots/ 下，不进仓库）。
    ffmpeg 不可用 ⇒ 返回 None，F4 自动降为"只测开合生命周期"，**不降为绿**。"""
    src = sorted(FIX_DIR.glob("smile-*.jpg"))
    if not src:
        return None
    out = ROOT / "_test" / "_shots" / "_face_cam.y4m"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 1024:
        return out
    try:
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(src[0]), "-t", "4", "-r", "10",
                        "-vf", "scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2",
                        "-pix_fmt", "yuv420p", "-f", "yuv4mpegpipe", str(out)],
                       capture_output=True, timeout=120)
    except Exception:  # noqa: BLE001
        return None
    return out if (out.is_file() and out.stat().st_size > 1024) else None


class _Handler(SimpleHTTPRequestHandler):
    """站点面按**部署布局**提供（deploy/xinyu 当根），判据面（/_test、/src）直落仓库根。

    为什么不能拿 src/ 当根跑浏览器腿：sw.js 的 scope 与 PRECACHE 全是根级路径
    （"/"、"/index.html"、"/css/style.css"），拿 src/ 当根时 SW 会去预缓存一批 404，
    页面侧拿到的是"壳缺件"噪声；而线上与 Pages 部署的根就是 deploy/xinyu。
    判据要测的是线上那棵树，所以这里按上线形态摆。"""

    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p.startswith("/_test/") or p.startswith("/src/"):
            return super().translate_path(path)
        rel = p.lstrip("/")
        base = ROOT / "deploy" / "xinyu"
        return str(base / rel) if rel else str(base / "index.html")

    def log_message(self, *a, **k):   # 判据输出里不需要 HTTP 访问日志
        pass


def serve():
    mimetypes.add_type("text/javascript", ".mjs")     # 兜底：某些宿主把 .mjs 发成 text/plain
    mimetypes.add_type("application/wasm", ".wasm")
    mimetypes.add_type("application/octet-stream", ".task")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def leg_f10(browser, base, notes, bad):
    """F10 · 侧边控制面板的开关（r87e）：开关即时生效 + 状态胶囊实时翻面 + 关掉后**面板保留**
    （否则用户没法再打开）。自带 context —— 借用别的腿的 page 会 TargetClosedError（首跑实测）。"""
    ctx = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    print("    F10: goto…", flush=True)
    pg.goto(base + "/index.html", wait_until="load")
    print("    F10: loaded, 等 UI ready…", flush=True)
    pg.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'", timeout=60000)
    print("    F10: UI ready, click btn-face…", flush=True)
    # r173：点击一律走 dispatch_event，**不用 pg.click**。
    # 原因（本轮实测取证）：CPU delegate 下 MediaPipe 多线程推理把约 25 个核打满
    # （实测 8 秒窗口 CPU 增量 202s），页面主线程被饿死 ⇒ pg.click 的 actionability
    # 检查（元素稳定/可接收事件）永远等不到，整条电池无限挂起。dispatch_event 直接
    # 派发 click 给监听器，不等布局稳定 —— 本腿验的是开关语义，不是命中率，够用且不会挂。
    def _tap(sel):
        pg.eval_on_selector(sel, "el => el.dispatchEvent(new MouseEvent('click', {bubbles: true}))")
    _tap("#btn-face")                                     # 打开面板并启动
    print("    F10: clicked, 等 isRunning…", flush=True)
    try:
        pg.wait_for_function("window.FaceEngine.isRunning()", timeout=60000)
    except Exception:  # noqa: BLE001
        bad.append("F10 点开面板后摄像头没起来")
        ctx.close()
        return
    on1 = pg.evaluate("""({hud: !document.getElementById('face-hud').hidden,
        checked: document.getElementById('face-switch').getAttribute('aria-checked'),
        word: document.getElementById('face-switch-word').textContent,
        pill: document.getElementById('face-hud-state').textContent,
        videoShown: !document.getElementById('face-hud-video').hidden})""")
    print("    F10: on1 取到", flush=True)
    notes.append("F10 开：checked=%s word=%r pill=%r 视频=%s 面板=%s"
                 % (on1["checked"], on1["word"], on1["pill"], on1["videoShown"], on1["hud"]))
    if on1["checked"] != "true" or on1["word"] != "已开启" or on1["pill"] != "已开启":
        bad.append("F10 开关打开后状态没同步：%s" % json.dumps(on1, ensure_ascii=False))
    if not on1["videoShown"]:
        bad.append("F10 开启后预览区仍在占位态（idle 没让位给视频）")
    _tap("#face-switch")                               # 关
    print("    F10: 已点关", flush=True)
    pg.wait_for_timeout(600)
    off1 = pg.evaluate("""({running: window.FaceEngine.isRunning(),
        live: Array.from(document.querySelectorAll('video')).filter(v => !!v.srcObject).length,
        checked: document.getElementById('face-switch').getAttribute('aria-checked'),
        word: document.getElementById('face-switch-word').textContent,
        pill: document.getElementById('face-hud-state').textContent,
        hud: !document.getElementById('face-hud').hidden,
        idle: !document.getElementById('face-hud-idle').hidden})""")
    notes.append("F10 关：checked=%s word=%r pill=%r 流=%d 面板仍在=%s 占位=%s"
                 % (off1["checked"], off1["word"], off1["pill"], off1["live"], off1["hud"], off1["idle"]))
    if off1["running"] or off1["live"]:
        bad.append("F10 开关关掉后摄像头没真停（running=%s live=%s）" % (off1["running"], off1["live"]))
    if off1["checked"] != "false" or off1["word"] != "已关闭" or off1["pill"] != "已关闭":
        bad.append("F10 关闭后状态没翻面：%s" % json.dumps(off1, ensure_ascii=False))
    if not off1["hud"] or not off1["idle"]:
        bad.append("F10 关闭后应保留面板并显示占位（否则用户没法再打开）：%s" % json.dumps(off1, ensure_ascii=False))
    _tap("#face-switch")                               # 再开一次：开关必须双向可反复
    print("    F10: 已点再开", flush=True)
    try:
        pg.wait_for_function("window.FaceEngine.isRunning()", timeout=60000)
    except Exception:  # noqa: BLE001
        bad.append("F10 关掉后再打开失败（开关不是双向的）")
    _tap("#face-switch")
    pg.wait_for_timeout(400)
    print("    F10: 收尾 ctx.close…", flush=True)
    ctx.close()
    print("    F10: ctx 已关", flush=True)


def _set_cam_setting(page, allow):
    """r109：总闸的家搬到设置面板（#set-face-cam）——开面板、切换、关面板。
    用 DOM click() 而非直接赋值 checked，保证 change 事件真触发（applyEnabled 才会跑）。"""
    page.click("#btn-settings")
    page.wait_for_timeout(300)
    page.evaluate("(v) => { const c = document.getElementById('set-face-cam');"
                  " if (c.checked !== v) c.click(); }", allow)
    page.wait_for_timeout(400)
    page.keyboard.press("Escape")          # 关设置面板（dialog 原生行为）
    page.wait_for_timeout(300)


def _leg_f4_f5(browser, base, notes, bad, cam, rows):
    """F4 真实摄像头路径（假设备）+ 关闭后必须真停 + 摄像头总闸开关；F5 真实照片实跑。
    F4/F5 共用同一 context/page（F5 在 F4 的页面里切到 harness），故同腿拆出。
    返回 (labels, hs)：labels 供 F12 复用；hs=None 表夹具缺失、F5 未跑。"""
    labels, hs = {}, None
    ctx = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(base + "/index.html", wait_until="load")   # 部署布局：根即 deploy/xinyu
    try:
        page.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'",
                               timeout=90000)
    except Exception as e:  # noqa: BLE001
        bad.append("F4 页面迟迟不给表情能力状态（%s）" % type(e).__name__)
    st = page.evaluate("window.__XINYU_FACE_UI__")
    notes.append("face_ui=%s/%s" % ((st or {}).get("state"), (st or {}).get("reason") or "-"))
    if (st or {}).get("state") != "ready":
        bad.append("F4 表情能力未就绪：state=%s reason=%s ⇒ 真机上按钮会消失"
                   % ((st or {}).get("state"), (st or {}).get("reason")))
    else:
        page.click("#btn-face")
        try:
            page.wait_for_function("!document.getElementById('face-hud').hidden", timeout=40000)
        except Exception:  # noqa: BLE001
            bad.append("F4 点了实时表情感知，小窗没出现")
        # 等**状态**而不是等固定秒数：模型首帧要过 wasm 初始化，慢机器上 2.5s 不够
        try:
            page.wait_for_function(
                "document.getElementById('btn-face').getAttribute('aria-pressed') === 'true'", timeout=30000)
        except Exception:  # noqa: BLE001
            pass
        diag = page.evaluate("""({
            pressed: document.getElementById('btn-face').getAttribute('aria-pressed'),
            err: window.FaceEngine.lastError(), note: (document.getElementById('face-note')||{}).textContent || ''
        })""")
        pressed = diag["pressed"]
        if pressed != "true":
            bad.append("F4 开启后 aria-pressed=%r ≠ true（引擎原因=%s）" % (pressed, diag["err"]))
        else:
            # 真脸流：必须真的出读数，且星雾底色被驱动起来（可视化那一半）
            if cam:
                try:
                    page.wait_for_function(
                        "window.FaceEngine.sampleCount() > 0 && !!window.FaceEngine.last()", timeout=30000)
                except Exception:  # noqa: BLE001
                    bad.append("F4 假摄像头喂的是真人脸，却一帧读数都没出来（samples=%s）"
                               % page.evaluate("window.FaceEngine.sampleCount()"))
                else:
                    got = page.evaluate("""({v: window.FaceEngine.last(),
                        tag: document.getElementById('face-hud-emo').textContent,
                        badge: document.getElementById('face-hud-smile').textContent,
                        mist: window.ThreeScene.mistInfo().on})""")
                    v = got.get("v") or {}
                    notes.append("F4 实时读数：%s/%s 强度=%.2f 徽章=%r 星雾底色=%s"
                                 % (v.get("emotion"), (v.get("smile") or {}).get("kind"),
                                    v.get("intensity", 0), got.get("badge"), got.get("mist")))
                    if v.get("emotion") != "joy":
                        bad.append("F4 真笑照片喂进实时链路，主情绪=%r ≠ joy ⇒ 映射链有问题" % v.get("emotion"))
                    if not got.get("mist"):
                        bad.append("F4 读数已出但星雾底色没被驱动 ⇒ 可视化那一半没接上")
                    # 留一张取证截图（_shots 已 ignore，不进仓库）
                    try:
                        shot = ROOT / "_test" / "_shots" / "face_hud_live.png"
                        shot.parent.mkdir(parents=True, exist_ok=True)
                        page.locator("#face-hud").screenshot(path=str(shot))
                        notes.append("截图=%s" % shot.name)
                    except Exception:  # noqa: BLE001
                        pass
        page.wait_for_timeout(1500)
        page.click("#btn-face-close")
        page.wait_for_timeout(600)
        st2 = page.evaluate("""({
            running: window.FaceEngine.isRunning(),
            pressed: document.getElementById('btn-face').getAttribute('aria-pressed'),
            hudHidden: document.getElementById('face-hud').hidden,
            liveStreams: Array.from(document.querySelectorAll('video')).filter(v => !!v.srcObject).length,
            mist: window.ThreeScene.mistInfo ? window.ThreeScene.mistInfo().on : null
        })""")
        if st2["running"]:
            bad.append("F4 关闭后 FaceEngine 仍在跑 ⇒ 摄像头没真停")
        if st2["liveStreams"] != 0:
            bad.append("F4 关闭后仍有 %d 个 video 挂着流 ⇒ 指示灯不灭（隐私红线）" % st2["liveStreams"])
        if st2["pressed"] != "false" or not st2["hudHidden"]:
            bad.append("F4 关闭后状态未复位：pressed=%s hudHidden=%s" % (st2["pressed"], st2["hudHidden"]))
        if st2["mist"]:
            bad.append("F4 关闭后星雾底色没收回 ⇒ 表情色留在了星云上")
        # 摄像头总闸（r87b）：关 = 入口全隐 + 状态 unavailable + 选择被记住；
        # 再开 = 入口恢复（能否真用仍由能力探测说了算）。开关按钮必须永远可点。
        _set_cam_setting(page, False)
        off = page.evaluate("""({allowed: document.getElementById('set-face-cam').checked,
            faceHidden: document.getElementById('btn-face').hidden,
            scanHidden: document.getElementById('btn-face-scan').hidden,
            ui: window.__XINYU_FACE_UI__, running: window.FaceEngine.isRunning(),
            live: Array.from(document.querySelectorAll('video')).filter(v => !!v.srcObject).length,
            stored: localStorage.getItem('peiliao.face.cam.v1')})""")
        if off["allowed"] or off["stored"] != "off":
            bad.append("F4 摄像头开关关闭未生效：aria-pressed=%s stored=%r" % (off["pressed"], off["stored"]))
        if not (off["faceHidden"] and off["scanHidden"]) or (off["ui"] or {}).get("reason") != "cam-disabled":
            bad.append("F4 关总闸后摄像头入口没消失/原因没写明：%s" % json.dumps(off, ensure_ascii=False))
        if off["running"] or off["live"]:
            bad.append("F4 关总闸后摄像头还在跑（running=%s live=%s）⇒ 开关是假的" % (off["running"], off["live"]))
        _set_cam_setting(page, True)
        on = page.evaluate("""({allowed: document.getElementById('set-face-cam').checked,
            faceHidden: document.getElementById('btn-face').hidden,
            ui: window.__XINYU_FACE_UI__})""")
        if (not on["allowed"]) or on["faceHidden"] or (on["ui"] or {}).get("state") != "ready":
            bad.append("F4 重开总闸后入口没恢复：%s" % json.dumps(on, ensure_ascii=False))
    if errs:
        bad.append("F4 页面运行时异常 %d 条：%s" % (len(errs), " | ".join(errs[:2])[:180]))

    # ── F5：真实照片实跑 ──
    if not FIX_DIR.is_dir() or not list(FIX_DIR.glob("*.jpg")):
        notes.append("F5 UNVERIFIED：夹具目录为空（_test/face-fixtures）")
    else:
        lp = FIX_DIR / "labels.json"
        if lp.is_file():
            labels = {x["file"]: x for x in json.loads(lp.read_text("utf-8"))}
        h = page.goto(base + "/_test/face-harness.html", wait_until="load")
        try:
            page.wait_for_function("window.__HARNESS__ && (window.__HARNESS__.ready || window.__HARNESS__.err)",
                                   timeout=90000)
        except Exception:  # noqa: BLE001
            bad.append("F5 宿主机迟迟不就绪")
        hs = page.evaluate("window.__HARNESS__")
        if not (hs or {}).get("ready"):
            bad.append("F5 推理器起不来：%s" % ((hs or {}).get("err") or "unknown"))
        else:
            for img in sorted(FIX_DIR.glob("*.jpg")):
                r = page.evaluate("u => window.__HARNESS__.detect(u)", "/_test/face-fixtures/" + img.name)
                v = r.get("view") or {}
                sm = v.get("smile") or {}
                rows.append({
                    "file": img.name,
                    "label": (labels.get(img.name) or {}).get("label", "unknown"),
                    "faces": r.get("faces", 0),
                    "mouth": round(sm.get("mouth", 0), 3),
                    "ratio": round(sm.get("ratio", 0), 3),
                    "emotion": v.get("emotion"),
                    "intensity": round(v.get("intensity", 0), 3),
                    "smile_kind": sm.get("kind"),
                })
    ctx.close()
    return labels, hs


def _leg_f12(browser, base, bad, rows12, labels, hs):
    """F12：真实照片**逐类准确率**（r102 补）——每张照片的标注类 vs 实得主情绪，按类汇总。
    F5 只验「微笑组 vs 中性组口部分离」，从不问"判对没有"；F12 问的就是这个。
    hs=宿主机状态（F5 产物）；未 ready 或夹具缺失时整腿跳过。"""
    if not (hs or {}).get("ready"):
        return
    ctx12 = browser.new_context(viewport={"width": 1280, "height": 900})
    pg12 = ctx12.new_page()
    pg12.goto(base + "/_test/face-harness.html", wait_until="load")
    try:
        pg12.wait_for_function(
            "window.__HARNESS__ && window.__HARNESS__.ready === true", timeout=90000)
    except Exception:  # noqa: BLE001
        bad.append("F12 宿主机迟迟不就绪")
    else:
        for img in sorted(FIX_DIR.glob("*.jpg")):
            lab = (labels.get(img.name) or {}).get("label", "unknown")
            if lab in ("smiling", "neutral"):
                continue          # 那两类由 F5 验，不在 F12 重复计数
            r = pg12.evaluate("u => window.__HARNESS__.detect(u)",
                              "/_test/face-fixtures/" + img.name)
            v = r.get("view") or {}
            rows12.append({
                "file": img.name, "label": lab, "faces": r.get("faces", 0),
                "got": v.get("emotion"),
                "intensity": round(v.get("intensity", 0), 3),
                "margin": round(v.get("confidence", 0), 3),
            })
    ctx12.close()


def _leg_f7(browser, base, notes, bad):
    """F7：**授权必须排在模型加载之前**（r87c；老大实测"点了不弹授权窗"的根因）。
    判据用"把 getUserMedia 拖慢 800ms + 记录调用时刻 + 记录首个 mediapipe 资源请求时刻"
    来复算顺序，而不是读注释。顺序错了（先下 13MB 再要权限）会在这里红。"""
    ctx7 = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 900})
    ctx7.add_init_script("""
        window.__ORDER__ = [];
        const md = navigator.mediaDevices, g = md.getUserMedia.bind(md);
        md.getUserMedia = async (...a) => {
            window.__ORDER__.push(['gum-called', performance.now()]);
            await new Promise(r => setTimeout(r, 800));   // 模拟"弹窗等用户点"的耗时
            return g(...a);
        };
        const f = window.fetch;
        window.fetch = (...a) => {
            const u = String(a[0]);
            if (u.indexOf('mediapipe') >= 0) window.__ORDER__.push(['fetch', performance.now()]);
            return f(...a);
        };
    """)
    p7 = ctx7.new_page()
    errs7 = []
    p7.on("pageerror", lambda e: errs7.append(str(e)))
    p7.goto(base + "/index.html", wait_until="load")
    p7.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'", timeout=60000)
    p7.click("#btn-face")
    seen = []
    for _ in range(80):                      # 最多 12s：把阶段顺序采样下来
        st7 = p7.evaluate("({p: window.FaceEngine.stats().phase, run: window.FaceEngine.isRunning()})")
        if st7["p"] and (not seen or seen[-1] != st7["p"]):
            seen.append(st7["p"])
        if st7["run"] or st7["p"] == "idle":
            break
        p7.wait_for_timeout(150)
    order = p7.evaluate("window.__ORDER__")
    gum_t = next((t for k, t in order if k == "gum-called"), None)
    mp_t = next((t for k, t in order if k == "fetch"), None)
    notes.append("F7 阶段顺序=%s｜gum@%s mediapipe_fetch@%s"
                 % ("→".join(seen) or "-", "-" if gum_t is None else round(gum_t),
                    "未走 fetch" if mp_t is None else round(mp_t)))
    if gum_t is None:
        bad.append("F7 开启时没有调用 getUserMedia ⇒ 授权根本没被请求")
    elif mp_t is not None and mp_t < gum_t:
        bad.append("F7 模型资源先于摄像头授权被请求（fetch@%.0f < gum@%.0f）"
                   " ⇒ 用户会先等十几秒才看到授权弹窗" % (mp_t, gum_t))
    if seen[:1] and seen[0] not in ("permission", "model", "warmup", "running"):
        bad.append("F7 首次采样到的阶段=%r 不是预期阶段" % seen[0])
    if errs7:
        bad.append("F7 顺序腿页面异常 %d 条：%s" % (len(errs7), " | ".join(errs7[:2])[:160]))
    ctx7.close()


def _leg_f8(browser, base, notes, bad):
    """F8 病①：一个摄像头设备都没有（enumerateDevices 空）⇒ 入口消失 + 说"检查驱动"。
    设备层/权限层的两种真实病，界面必须分开报（r87d）。"""
    ctx8 = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx8.add_init_script("navigator.mediaDevices.enumerateDevices = async () => [];")
    p8 = ctx8.new_page()
    p8.goto(base + "/index.html", wait_until="load")
    try:
        p8.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'", timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    p8.wait_for_timeout(600)
    st8 = p8.evaluate("""({ui: window.__XINYU_FACE_UI__,
        faceHidden: document.getElementById('btn-face').hidden,
        scanHidden: document.getElementById('btn-face-scan').hidden,
        status: (document.getElementById('face-status')||{}).textContent || ''})""")
    if (st8["ui"] or {}).get("reason") != "no-video-device":
        bad.append("F8 无摄像头设备时 reason=%r ≠ no-video-device（会把设备问题糊成权限问题）"
                   % (st8["ui"] or {}).get("reason"))
    if not (st8["faceHidden"] and st8["scanHidden"]):
        bad.append("F8 无设备时摄像头入口没隐藏")
    if "设备" not in st8["status"]:
        bad.append("F8 无设备时状态行没点明设备问题：%r" % st8["status"][:60])
    else:
        notes.append("F8 无设备面：入口已隐藏 + 状态行=%r" % st8["status"][:40])
    ctx8.close()


def _leg_f9(browser, base, notes, bad):
    """F9 病②：浏览器记住了"阻止"（不再弹窗，getUserMedia 直接 NotAllowedError）
    ⇒ 必须给出"锁形图标 → 摄像头 → 允许"的可行路径，而不是一句"暂不可用"。"""
    ctx9 = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx9.add_init_script("""
        navigator.mediaDevices.getUserMedia = async () => {
            const e = new Error('Permission denied'); e.name = 'NotAllowedError'; throw e;
        };
    """)
    p9 = ctx9.new_page()
    p9.goto(base + "/index.html", wait_until="load")
    try:
        p9.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'", timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    p9.wait_for_timeout(400)
    p9.click("#btn-face")
    p9.wait_for_timeout(1200)
    st9 = p9.evaluate("(document.getElementById('face-status')||{}).textContent || ''")
    if "锁形图标" not in st9:
        bad.append("F9 被阻止时状态行没给可行路径（应含「锁形图标」指引）：%r" % st9[:80])
    else:
        notes.append("F9 被阻止面：状态行=%r" % st9[:56])
    ctx9.close()


def _leg_f6(browser, base, bad):
    """F6：无 mediaDevices ⇒ 入口必须消失，不是点了报错。"""
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx2.add_init_script("Object.defineProperty(navigator,'mediaDevices',{get:()=>undefined,configurable:true});")
    p2 = ctx2.new_page()
    errs2 = []
    p2.on("pageerror", lambda e: errs2.append(str(e)))
    p2.goto(base + "/index.html", wait_until="load")
    try:
        p2.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'", timeout=60000)
    except Exception:  # noqa: BLE001
        pass
    st3 = p2.evaluate("""({ui: window.__XINYU_FACE_UI__,
        btnHidden: document.getElementById('btn-face').hidden,
        scanHidden: document.getElementById('btn-face-scan').hidden,
        note: (document.getElementById('face-note')||{}).textContent || ''})""")
    ui = st3.get("ui") or {}
    if ui.get("state") != "unavailable":
        bad.append("F6 无摄像头时 state=%r ≠ unavailable ⇒ 会把不可用伪装成可用" % ui.get("state"))
    if not (st3.get("btnHidden") and st3.get("scanHidden")):
        bad.append("F6 无摄像头时入口按钮没隐藏（btn=%s scan=%s）⇒ 用户点了只会有报错"
                   % (st3.get("btnHidden"), st3.get("scanHidden")))
    if not st3.get("note"):
        bad.append("F6 无摄像头时没有一句人话说明原因（静默降级=伪装）")
    if errs2:
        bad.append("F6 降级路径仍抛 %d 条异常：%s" % (len(errs2), " | ".join(errs2[:2])[:160]))
    ctx2.close()


BROWSER_LEGS_TIMEOUT = 900     # 秒。整段浏览器腿的硬上限（r173 新增，理由见 browser_legs_guarded）


def browser_legs_guarded():
    """带硬上限地跑浏览器腿（r173）。

    为什么要子进程看门狗（而不是给每个 wait 加 timeout）：
      本轮实测：无 GPU 的 headless 环境里 MediaPipe 走 CPU delegate，多线程 XNNPACK 把
      **约 25 个核打满**（8 秒窗口 CPU 增量 202s）。页面主线程被饿死 ⇒
      `wait_for_function` 的轮询脚本根本插不进去，**它自带的 timeout 也一起失效**
      （F10「再开」那一等实测超过 4 分钟仍不返回）。这不是判据写错，是仪器被饿死。
      A/B 对照（HEAD 版 vs 工作树版同一序列）表现完全一致 ⇒ **既有问题，非本轮引入**；
      且仅在本机无 GPU 时复现，有 GPU 的机器未必如此（未实测，不外推成产品缺陷）。
    做法：把整段浏览器腿丢进子进程跑，超时就杀 ⇒ 本轮读数记 **UNVERIFIED** 而不是
      让整锅电池无限挂起、连个结论行都没有（那比红更糟：红至少能被看见）。
    """
    import json as _json
    import subprocess
    import tempfile
    from pathlib import Path as _Path
    with tempfile.TemporaryDirectory() as td:
        out = _Path(td) / "legs.json"
        cmd = [sys.executable, "-u", __file__, "--browser-legs-only", str(out)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=BROWSER_LEGS_TIMEOUT, cwd=str(ROOT))
        except subprocess.TimeoutExpired:
            print("  [4/5] 浏览器腿超过 %ds 硬上限 ⇒ 本轮记 **UNVERIFIED**（判据未出结论，禁读成绿）"
                  % BROWSER_LEGS_TIMEOUT, flush=True)
            raise
        if (p.stdout or "").strip():
            for line in (p.stdout or "").strip().splitlines():
                print("    " + line, flush=True)
        if p.returncode != 0 or not out.is_file():
            raise RuntimeError("浏览器腿子进程 rc=%s：%s" % (p.returncode, (p.stderr or "")[:200]))
        data = _json.loads(out.read_text(encoding="utf-8"))
        return data["rows"], data["bad"], data["notes"], data["rows12"]


def _browser_legs_entry(out_path):
    """--browser-legs-only 的入口：只跑浏览器腿并把结果写 JSON 给父进程。"""
    rows, bad, notes, rows12 = browser_legs()
    Path(out_path).write_text(json.dumps({"rows": rows, "bad": bad, "notes": notes,
                                          "rows12": rows12}, ensure_ascii=False), encoding="utf-8")
    return 0


def browser_legs():
    """返回 (rows_F5, bad, notes)。bad 为空即绿。"""
    from playwright.sync_api import sync_playwright
    from browser_engine import launch

    bad, notes = [], []
    srv, port = serve()
    base = "http://127.0.0.1:%d" % port
    rows = []
    rows12 = []
    try:
        with sync_playwright() as pw:
            args = list(MEDIA_ARGS)
            cam = make_fake_cam()
            if cam:
                args.append("--use-file-for-fake-video-capture=" + str(cam))
            notes.append("假摄像头=%s" % ("真脸 y4m" if cam else "无脸滚动图案（降级：只测开合生命周期）"))
            browser, face = launch(pw, args=args, label="face_check")
            notes.append("engine=%s" % face.split(" 原因=")[0])
            try:
                labels, hs = _leg_f4_f5(browser, base, notes, bad, cam, rows)
                print("  [4/5] · F4/F5 完", flush=True)

                _leg_f12(browser, base, bad, rows12, labels, hs)
                print("  [4/5] · F12 完", flush=True)

                _leg_f7(browser, base, notes, bad)
                print("  [4/5] · F7 完", flush=True)

                # ── F10：侧边控制面板的开关（实现见 leg_f10，可被 --leg F10 单独调起）──
                # r113：删掉残留的 ctx10.close() —— leg_f10 自建自关 context，此处 ctx10 从未定义，
                # 执行到必 NameError 崩掉整条浏览器腿（本轮静态确证后作为跑通验证链的前提移除）。
                leg_f10(browser, base, notes, bad)
                print("  [4/5] · F10 完", flush=True)

                _leg_f8(browser, base, notes, bad)
                print("  [4/5] · F8 完", flush=True)

                _leg_f9(browser, base, notes, bad)
                print("  [4/5] · F9 完", flush=True)

                _leg_f6(browser, base, bad)
                print("  [4/5] · F6 完", flush=True)
            finally:
                browser.close()
    finally:
        srv.shutdown()
    return rows, bad, notes, rows12


def public_check(base):
    """公网验收（--public <URL>）：拿假摄像头喂的**真人脸**去打线上那一棵树。

    为什么不能只靠本地那条腿：本地是我自己起的服务（MIME、CSP、SW 全是我配的），
    线上是 Cloudflare Pages 的真实托管面 —— 这三个恰恰是最容易"本地绿、线上死"的地方：
      · `.wasm` 在托管侧发什么 MIME（发错 → wasm 起不来，功能静默消失）
      · `script-src 'wasm-unsafe-eval'` 有没有真生效（没生效 → CSP 拒编译）
      · `Permissions-Policy: camera=(self)` 有没有放行（没放行 → getUserMedia 当场被掐）
    这三条任何一条挂掉，页面表现都是"按钮不见了"，所以必须真跑一遍。
    """
    from playwright.sync_api import sync_playwright
    from browser_engine import launch
    bad, notes = [], []
    base = base.rstrip("/")
    with sync_playwright() as pw:
        args = list(MEDIA_ARGS)
        cam = make_fake_cam()
        if cam:
            args.append("--use-file-for-fake-video-capture=" + str(cam))
        browser, face = launch(pw, args=args, label="face_check_public")
        notes.append("engine=%s" % face.split(" 原因=")[0])
        try:
            ctx = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 900})
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(getattr(e, "stack", None) or e)))
            logs = []
            pg.on("console", lambda m: logs.append(m.type + ":" + m.text[:200]))
            net = []
            pg.on("response", lambda r: net.append("resp %s %s" % (r.status, r.url.split("/")[-1]))
                  if "mediapipe" in r.url else None)
            pg.on("requestfailed", lambda r: net.append("FAIL %s %s" % ((r.failure or "-"), r.url.split("/")[-1]))
                  if "mediapipe" in r.url else None)
            pg.goto(base + "/", wait_until="load")
            # ① 托管面：wasm 与模型真的可取且类型正确
            asset = pg.evaluate("""async () => {
                const out = {};
                for (const u of ['/vendor/mediapipe/vision_wasm_internal.wasm',
                                 '/vendor/mediapipe/face_landmarker.task',
                                 '/vendor/mediapipe/vision_bundle.js']) {
                    try { const r = await fetch(u); out[u] = r.status + '/' + (r.headers.get('content-type') || '-'); }
                    catch (e) { out[u] = 'ERR ' + e; }
                }
                return out;
            }""")
            for u, v in asset.items():
                notes.append("%s → %s" % (u.split('/')[-1], v))
                if not str(v).startswith("200"):
                    bad.append("公网 %s 取不到（%s）⇒ 懒加载资产没上线" % (u, v))
            # ② 功能面：能力就绪 + 真脸出读数 + 关闭真停
            try:
                pg.wait_for_function("window.__XINYU_FACE_UI__ && window.__XINYU_FACE_UI__.state !== 'boot'", timeout=90000)
            except Exception:  # noqa: BLE001
                bad.append("公网页面迟迟不给表情能力状态")
            st = pg.evaluate("window.__XINYU_FACE_UI__")
            notes.append("face_ui=%s/%s" % ((st or {}).get("state"), (st or {}).get("reason") or "-"))
            # ① b 摄像头授权面：直接问一次并**限时**（挂起跟拒绝是两种病，必须分开看）
            gum = pg.evaluate("""async () => {
                const t0 = performance.now();
                const r = await Promise.race([
                    navigator.mediaDevices.getUserMedia({video: {width: 320, height: 240}})
                        .then(s => { const n = s.getTracks().length; s.getTracks().forEach(t => t.stop()); return 'ok:' + n; })
                        .catch(e => 'ERR ' + (e && e.name)),
                    new Promise(res => setTimeout(() => res('TIMEOUT'), 15000))
                ]);
                return r + ' in ' + Math.round(performance.now() - t0) + 'ms';
            }""")
            notes.append("getUserMedia(公网源) → %s" % gum)
            perm = pg.evaluate("navigator.permissions ? navigator.permissions.query({name:'camera'}).then(p=>p.state).catch(e=>'ERR') : 'n/a'")
            notes.append("camera permission=%s" % perm)
            if (st or {}).get("state") != "ready":
                bad.append("公网上表情能力未就绪：state=%s reason=%s" % ((st or {}).get("state"), (st or {}).get("reason")))
            else:
                pg.click("#btn-face")
                # 公网首帧比本地慢一档（授权 + 设备枚举 + 13MB 模型都在这条链上）：
                # 先等「真的开起来了」，再等「真的出读数」——两个状态分开等，超时才知道卡在哪一环
                try:
                    pg.wait_for_function(
                        "document.getElementById('btn-face').getAttribute('aria-pressed') === 'true'", timeout=180000)
                except Exception:  # noqa: BLE001
                    notes.append("公网开启未在 60s 内完成（aria-pressed 未置 true）")
                try:
                    pg.wait_for_function("window.FaceEngine.sampleCount() > 0 && !!window.FaceEngine.last()", timeout=90000)
                except Exception:  # noqa: BLE001
                    # 诊断面必须自己带：单帧异常在引擎里是"记一次继续跑"，不留读数就查不出是卡在哪一环
                    diag = pg.evaluate("""({vidReady: (document.getElementById('face-hud-video')||{}).readyState,
                        vidW: (document.getElementById('face-hud-video')||{}).videoWidth,
                        visionOk: window.__XINYU_FACE_VISION__ && window.__XINYU_FACE_VISION__.ok,
                        visionErr: (window.__XINYU_FACE_VISION__ && window.__XINYU_FACE_VISION__.err) || '-',
                        vis: document.visibilityState, running: window.FaceEngine.isRunning(),
                        engErr: window.FaceEngine.lastError(),
                        stats: window.FaceEngine.stats(),
                        samples: window.FaceEngine.sampleCount()})""")
                    notes.append("诊断 %s" % json.dumps(diag, ensure_ascii=False))
                    notes.append("点击后 UI=%s" % json.dumps(pg.evaluate(
                        "({hudHidden: document.getElementById('face-hud').hidden,"
                        " pressed: document.getElementById('btn-face').getAttribute('aria-pressed'),"
                        " disabled: document.getElementById('btn-face').disabled,"
                        " btnHidden: document.getElementById('btn-face').hidden})"), ensure_ascii=False))
                    for m in logs[:8]:
                        notes.append("console " + m)
                    for m in net[:10]:
                        notes.append("net " + m)
                    bad.append("公网开启后没出读数（samples=%s）⇒ 线上链路断了" % diag["samples"])
                else:
                    got = pg.evaluate("""({v: window.FaceEngine.last(),
                        badge: document.getElementById('face-hud-smile').textContent,
                        tag: document.getElementById('face-hud-emo').textContent,
                        mist: window.ThreeScene.mistInfo().on})""")
                    v = got.get("v") or {}
                    notes.append("公网实时读数：%s/%s 强度=%.2f 标签=%r 徽章=%r 星雾=%s"
                                 % (v.get("emotion"), (v.get("smile") or {}).get("kind"), v.get("intensity", 0),
                                    got.get("tag"), got.get("badge"), got.get("mist")))
                    try:
                        shot = ROOT / "_test" / "_shots" / "face_public_live.png"
                        shot.parent.mkdir(parents=True, exist_ok=True)
                        pg.locator("#face-hud").screenshot(path=str(shot))
                        notes.append("公网截图=%s" % shot.name)
                    except Exception:  # noqa: BLE001
                        pass
                pg.click("#btn-face-close")
                pg.wait_for_timeout(800)
                st2 = pg.evaluate("""({running: window.FaceEngine.isRunning(),
                    live: Array.from(document.querySelectorAll('video')).filter(v => !!v.srcObject).length})""")
                if st2["running"] or st2["live"]:
                    bad.append("公网关闭后摄像头没真停（running=%s live=%s）" % (st2["running"], st2["live"]))
            if errs:
                bad.append("公网页面异常 %d 条：%s" % (len(errs), " | ".join(errs[:2])[:200]))
            ctx.close()
        finally:
            browser.close()
    print("FACE-PUBLIC %s（%s）" % ("FAIL" if bad else "PASS", base))
    for n in notes:
        print("  · " + n)
    for b in bad:
        print("  FAIL " + b)
    return 1 if bad else 0


def run_one_leg(name):
    """开发期单腿模式（本仓老规矩：**子集读数不得冒充全量**，故恒返回 2 = UNVERIFIED，
    哪怕这条腿全过 —— 免得"只跑了 F10"被下一轮读成"面部识别全绿"）。"""
    from playwright.sync_api import sync_playwright
    from browser_engine import launch
    legs = {"F10": leg_f10}
    fn = legs.get(name.upper())
    if not fn:
        print("FACE-LEG: 未知腿 %r（可选：%s）" % (name, ",".join(sorted(legs))))
        return 2
    srv, port = serve()
    base = "http://127.0.0.1:%d" % port
    notes, bad = [], []
    try:
        with sync_playwright() as pw:
            args = list(MEDIA_ARGS)
            cam = make_fake_cam()
            if cam:
                args.append("--use-file-for-fake-video-capture=" + str(cam))
            browser, face = launch(pw, args=args, label="face_check_leg")
            notes.append("engine=%s" % face.split(" 原因=")[0])
            try:
                fn(browser, base, notes, bad)
            finally:
                browser.close()
    finally:
        srv.shutdown()
    for n in notes:
        print("  · " + n)
    for b in bad:
        print("  FAIL " + b)
    print("FACE-LEG-%s %s（单腿模式 ⇒ 无论结果一律 UNVERIFIED，不得读成全量绿）"
          % (name.upper(), "有红" if bad else "无红"))
    return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--public", metavar="URL", default="",
                    help="对公网 URL 做真脸验收（需假摄像头；不带则只跑本地六条腿）")
    ap.add_argument("--leg", metavar="NAME", default="",
                    help="开发期只跑单腿（如 F10 开关腿）；**子集永不返回绿**，恒返回 2（UNVERIFIED）")
    ap.add_argument("--browser-legs-only", metavar="OUT", default="",
                    help="内部用：只跑浏览器腿并把结果写到 OUT（由 browser_legs_guarded 调用）")
    a = ap.parse_args()
    if a.browser_legs_only:
        return _browser_legs_entry(a.browser_legs_only)
    if a.leg:
        return run_one_leg(a.leg)
    if a.public:
        return public_check(a.public)

    if a.selftest:
        return selftest()

    bad = []
    # r173 进度打印：本脚本此前**全程零输出**直到最后，一轮跑几十分钟看不出卡在哪条腿
    #   （r166 台账的仪器债）。加打印只为定位，不改变任何判定；每行都 flush 便于重定向观察。
    print("  [1/5] F1 vendor 完整性…", flush=True)
    bad += f1_bad()
    print("  [2/5] F2 接线面…", flush=True)
    dep_files = {f: (ROOT / "deploy" / "xinyu" / f).is_file() for f in NEW_FILES}
    html_src = (ROOT / "src" / "index.html").read_text("utf-8")
    html_dep = (ROOT / "deploy" / "xinyu" / "index.html").read_text("utf-8")
    sw_text = (ROOT / "src" / "sw.js").read_text("utf-8")
    hd = (ROOT / "deploy" / "xinyu" / "_headers").read_text("utf-8")
    bad += f2_bad(html_src, html_dep, sw_text, hd, dep_files)

    print("  [3/5] F3 判据单测(node)…", flush=True)
    rc3, bad3 = run_f3()
    bad += bad3

    print("  [4/5] F4/F5/F6 浏览器腿（含假摄像头与 MediaPipe 模型加载，最慢的一段）…", flush=True)
    rows, badb, notes, rows12 = [], [], [], []
    try:
        rows, badb, notes, rows12 = browser_legs_guarded()
    except Exception as e:  # noqa: BLE001
        print("FACE-CHECK-UNVERIFIED: 浏览器腿没跑起来（%s: %s）" % (type(e).__name__, str(e).splitlines()[0][:120]))
        return 2
    bad += badb
    if rows:
        bad += f5_bad(rows)
    bad12, rep12 = f12_report(rows12)

    print("  F1 vendor 完整性 / F2 接线面 / F3 判据单测(node) / F4 摄像头开合 / F5 照片实跑 / F6 无摄像头降级 / F12 真实照片逐类准确率")
    for n in notes:
        print("  · " + n)
    for r in rows:
        print("    %-26s label=%-8s faces=%d mouth=%.3f ratio=%.3f → %s/%s %.2f (%s)"
              % (r["file"], r["label"], r["faces"], r["mouth"], r["ratio"],
                 r["emotion"], r["smile_kind"], r["intensity"], "真笑" if r["smile_kind"] == "duchenne" else ""))
    if rows:
        smi = [r for r in rows if r["label"] == "smiling" and r["faces"] > 0]
        neu = [r for r in rows if r["label"] == "neutral" and r["faces"] > 0]
        if smi and neu:
            print("  可分性：微笑组 mouth∈[%.3f, %.3f] ｜ 中性组 mouth∈[%.3f, %.3f] ｜ 间隙=%.3f"
                  % (min(r["mouth"] for r in smi), max(r["mouth"] for r in smi),
                     min(r["mouth"] for r in neu), max(r["mouth"] for r in neu),
                     min(r["mouth"] for r in smi) - max(r["mouth"] for r in neu)))
    if rows12:
        print("  F12 真实照片逐类准确率（分母=能检出人脸的张数）：")
        for line in rep12:
            print("    " + line)
        print("    · anger 已修（r103 老大拍板「保真怒」）：真实照实测 browDown 0.64 而其余全 0，")
        print("      旧权重要求第二区佐证 ⇒ 漏判成 calm；去掉后 2/2，代价是专注轻皱会误报成烦躁。")
    if bad12:
        for b in bad12:
            print("  FAIL " + b)
        bad += bad12
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print("FACE-CHECK-FAIL: %d 条" % len(bad))
        return 1
    print("FACE-CHECK-PASS  (F1–F6 全绿，腿数=6)")
    return 0


def selftest():
    """逐条改坏必须报红、原样必须零问题（每条只动一个维度）。"""
    html_src = (ROOT / "src" / "index.html").read_text("utf-8")
    html_dep = (ROOT / "deploy" / "xinyu" / "index.html").read_text("utf-8")
    sw_text = (ROOT / "src" / "sw.js").read_text("utf-8")
    hd = (ROOT / "deploy" / "xinyu" / "_headers").read_text("utf-8")
    dep = {f: (ROOT / "deploy" / "xinyu" / f).is_file() for f in NEW_FILES}
    man = MANIFEST.read_text("utf-8")
    fail, ok = [], 0

    if f2_bad(html_src, html_dep, sw_text, hd, dep):
        fail.append("原样 F2 被判失败：%s" % f2_bad(html_src, html_dep, sw_text, hd, dep))
    else:
        ok += 1
    if f1_bad(man):
        fail.append("原样 F1 被判失败：%s" % f1_bad(man))
    else:
        ok += 1
    good_rows = [
        {"file": "a.jpg", "label": "smiling", "faces": 1, "mouth": 0.72, "ratio": 0.6, "emotion": "joy", "intensity": 0.8, "smile_kind": "duchenne"},
        {"file": "b.jpg", "label": "smiling", "faces": 1, "mouth": 0.61, "ratio": 0.28, "emotion": "joy", "intensity": 0.7, "smile_kind": "duchenne"},
        {"file": "c.jpg", "label": "neutral", "faces": 1, "mouth": 0.09, "ratio": 0.0, "emotion": "calm", "intensity": 0.6, "smile_kind": "none"},
        {"file": "d.jpg", "label": "neutral", "faces": 1, "mouth": 0.15, "ratio": 0.0, "emotion": "calm", "intensity": 0.6, "smile_kind": "none"},
    ]
    # F12 夹具： Anger 故意取"实得 calm"，因为那是**实测真值**（见 browser_legs 的 F12 注释）——
    # 若这里写成 anger，F12 的反例腿就失去了"如实反映现状"的性质。
    good_rows12 = [
        {"file": "ag1.jpg", "label": "anger", "faces": 1, "got": "calm", "intensity": 0.23, "margin": 0.30},
        {"file": "ag2.jpg", "label": "anger", "faces": 1, "got": "calm", "intensity": 0.24, "margin": 0.31},
        {"file": "su1.jpg", "label": "surprise", "faces": 1, "got": "surprise", "intensity": 0.68, "margin": 0.06},
        {"file": "su2.jpg", "label": "surprise", "faces": 1, "got": "surprise", "intensity": 0.67, "margin": 0.05},
    ]
    b12, _r12 = f12_report(good_rows12)
    if b12:
        fail.append("原样 F12 被判失败：%s" % b12)
    else:
        ok += 1
    for tag, mut in (
        ("F12 全类没检出人脸", lambda r: dict(r, faces=0)),
        ("F12 读数恒为空", lambda r: dict(r, got=None)),
    ):
        if not f12_bad_injected(good_rows12, mut):
            fail.append("反例未被抓住：%s" % tag)
        else:
            ok += 1
    if f5_bad(good_rows):
        fail.append("原样 F5 被判失败：%s" % f5_bad(good_rows))
    else:
        ok += 1

    muts = [
        ("F1 模型被换字节", lambda: f1_bad(man, disk={"src/vendor/mediapipe/face_landmarker.task": b"x" * 4096})),
        ("F2 拔掉 ESM 桥", lambda: f2_bad(html_src.replace('type="module" src="js/face-mediapipe-bridge.js"', ""), html_dep, sw_text, hd, dep)),
        ("F2 CSP 不放行 wasm", lambda: f2_bad(html_src, html_dep, sw_text, hd.replace("'wasm-unsafe-eval'", ""), dep)),
        ("F2 摄像头被策略掐死", lambda: f2_bad(html_src, html_dep, sw_text, hd.replace("camera=(self)", "camera=()"), dep)),
        ("F2 新 js 没进 SW 预缓存", lambda: f2_bad(html_src, html_dep, sw_text.replace('"/js/face-engine.js",', ""), hd, dep)),
        ("F2 公网副本缺件", lambda: f2_bad(html_src, html_dep, sw_text, hd, dict(dep, **{"js/face-engine.js": False}))),
        ("F5 两组不可分", lambda: f5_bad([dict(r, mouth=0.4) for r in good_rows])),
        ("F5 全没检出人脸", lambda: f5_bad([dict(r, faces=0) for r in good_rows])),
        ("F5 读数恒等", lambda: f5_bad([dict(r, emotion="calm", mouth=(0.7 if r["label"] == "smiling" else 0.1)) for r in good_rows])),
        ("F5 真笑照片被判成社交笑（门槛标定错）", lambda: f5_bad([dict(r, smile_kind="social") for r in good_rows])),
        ("F5 零读数", lambda: f5_bad([])),
    ]
    for name, fn in muts:
        if fn():
            ok += 1
        else:
            fail.append("反例未被抓到：" + name)
    print("FACE-SELFTEST %s（反例 %d 条全部判红，原样 3 条全绿）" % ("PASS" if not fail else "FAIL", len(muts)))
    for f in fail:
        print("  " + f)
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
