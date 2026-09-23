# -*- coding: utf-8 -*-
"""星雾「是不是真的变彩色了」——像素级回归（判断据不看内部数组）

流程：用真实的底部对话坞连说 4 句话（每条都会点亮一簇星），对 canvas 截图，
     取有效像素做纯色方向 2-means，比两簇中心色距与少数簇占比。
       · 多样情绪历史 → 应判出两簇（画面里有明显不同的颜色）
       · 单一情绪历史 → 必须判不出两簇（否则说明判据恒真、结论作废）
用法：先起静态服务器（python -m http.server 8123 --directory src）或 Java 服务端，再跑本脚本。
注：接线正确性由 _test/browser_check.py 覆盖，本脚本只管「屏幕上肉眼是否可分辨」。

可复现性（2026-09-23）：截图时画面本在自转+逐星闪烁，同一判据会因采样相位不同而时好时坏
（实测同色用例曾判出 0.338 色距的假双色）。故本脚本从测试侧做两件事，生产代码零改动：
  ① init script 用 mulberry32 定点替换 Math.random → 星位布局可复现；
  ② Playwright clock 在截图前 pause_at 固定时刻 → performance.now() 读数恒定 → 动画相位冻结。
改造后连跑实测：(色距, 少数簇占比) multi ≈ (0.53~0.57, 0.27~0.35) / single ≈ (0.02~0.11, 0.004~0.04)，
阈值仍用原值不放松（判据余量 ≥2.2×）；残余微抖动来自截图落帧时刻，双条件判据已能吞掉它
（同色用例残余色距抬到 0.11 时，少数簇占比同步塌到 0.004）。
"""
import sys, io, math, os, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright
from PIL import Image

CASES = [
    ("multi", ["今天收到offer啦，太开心了！", "其实也很难过，心里空落落的", "明天答辩好焦虑，压力好大", "有点心动也很想念那个人"]),
    ("single", ["心里空落落的很难过", "又想哭了，好难受", "今天很低落很失落", "情绪还是很低落"]),
]

# 故意注入的不可达 LLM 端点（离线隔离用，同 browser_check.py）：它的连接失败是预期噪声，
# 断言时按 URL 精确豁免；其余任何 console 报错 / 未捕获异常仍然一律致命。
OFFLINE_LLM = "http://127.0.0.1:18123/v1"

# 星位固定的伪随机源（mulberry32，同值同序）
SEED_JS = """(() => { let s = 20260923;
  Math.random = function () { s |= 0; s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; })()"""

# 相位冻结锚点：每次截图把假时钟推到「基准 + 步长×序号」的定点并暂停。
# 目标值远大于任一用例的真实耗时（约 12~15s），保证只向前跳；暂停期间定时器不再触发，
# 但截图前的交互（下一用例前会 resume）都在真实走时下完成，不影响应用自身逻辑。
CLOCK_BASE = datetime.datetime(2026, 9, 23, 10, 0, 0)
FREEZE_AT_S = [40, 100, 160]


def freeze_phase(page, k):
    page.clock.pause_at(CLOCK_BASE + datetime.timedelta(seconds=FREEZE_AT_S[k]))
    page.wait_for_timeout(300)  # 让暂停后的稳定帧落地


def clusters2(path, min_v=0.18, min_s=0.12):
    """返回 (有效像素数, 两簇中心色距, 少数簇占比)"""
    im = Image.open(path).convert("RGB").resize((320, 200))
    px = []
    for r, g, b in im.getdata():
        R, G, B = r / 255, g / 255, b / 255
        mx, mn = max(R, G, B), min(R, G, B)
        if mx < min_v or (mx - mn) / mx < min_s:  # 剔背景与加性混合吹爆的近白点
            continue
        n = math.sqrt(R * R + G * G + B * B) or 1.0
        px.append((R / n, G / n, B / n))
    if len(px) < 50:
        return len(px), 0.0, 0.0
    c1 = px[0]
    c2 = max(px, key=lambda p: math.dist(p, c1))
    for _ in range(12):
        b0, b1 = [], []
        for p in px:
            (b0 if math.dist(p, c1) <= math.dist(p, c2) else b1).append(p)
        if not b0 or not b1:
            break
        c1 = [sum(v[i] for v in b0) / len(b0) for i in range(3)]
        c2 = [sum(v[i] for v in b1) / len(b1) for i in range(3)]
    b0, b1 = [], []
    for p in px:
        (b0 if math.dist(p, c1) <= math.dist(p, c2) else b1).append(p)
    minority = min(len(b0), len(b1)) / max(1, len(px))
    return len(px), round(math.dist(c1, c2), 3), round(minority, 3)


out = {}
errors = []
with sync_playwright() as p:
    try:
        browser = p.chromium.launch()
    except Exception:
        browser = p.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(SEED_JS)  # 星位布局可复现（不改生产代码）
    page = ctx.new_page()
    page.clock.install(time=CLOCK_BASE)  # 假时钟：交互期照常走时，截图前再冻结相位
    # 记 (文本, 来源URL)：URL 用于精确排除「本脚本故意注入的不可达端点」的连接失败噪声
    page.on("console", lambda m: errors.append((m.text, (m.location or {}).get("url", ""))) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append((str(e), "")))
    page.goto("http://localhost:8123/index.html", wait_until="networkidle")
    # 离线隔离（同 browser_check.py）：不可达端点 → 词典兜底。一举两得：
    # ① 断在线 LLM 分类的跨跑方差；② base 非空 → demo-config 不回填 remote:true →
    # 服务端 hydrate 不触发，上个用例的星不会经同一 sessionId 重播进本用例（单色污染根因）。
    page.evaluate("""(base) => { localStorage.setItem('peiliao.cfg.v1',
      JSON.stringify({base, key:'x', model:'x'}));
      localStorage.removeItem('peiliao.emotions.v1'); }""", OFFLINE_LLM)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(800)
    shots = "c:/Users/37533/Desktop/workspace/项目/陪聊/_test/_shots"
    os.makedirs(shots, exist_ok=True)
    # 负对照（R236 两层含对照）：空白星图必须判不出双色，否则判据恒真、结论作废
    blank = f"{shots}/lit_blank.png"
    freeze_phase(page, 0)
    page.locator("#gl").screenshot(path=blank)
    bn, bdist, bminority = clusters2(blank)
    print(f"[blank] 有效像素={bn} 两簇色距={bdist} 少数簇占比={bminority}")
    assert not (bdist > 0.25 and bminority > 0.10), f"判据恒真：空白星图也被判多彩: {(bn, bdist, bminority)}"

    def overlay(hide):
        page.evaluate("""(hide) => { const v = hide ? 'hidden' : 'visible';
                          document.getElementById('story').style.visibility = v;
                          document.getElementById('topbar').style.visibility = v;
                          document.getElementById('chat-dock').style.visibility = v; }""", hide)

    for idx, (name, texts) in enumerate(CASES):
        page.clock.resume()  # 恢复走时：本用例的交互必须在活时钟下完成
        overlay(False)
        # 清空历史，保证每个用例从干净星图开始
        page.evaluate("() => localStorage.removeItem('peiliao.emotions.v1')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        overlay(False)
        for t in texts:
            page.fill("#chat-input", t)
            page.click("#chat-form button[type=submit]")
            page.wait_for_timeout(2200)
        overlay(True)
        page.wait_for_timeout(1800)  # 等点亮脉冲衰减到常态再取样本
        shots = "c:/Users/37533/Desktop/workspace/项目/陪聊/_test/_shots"
        os.makedirs(shots, exist_ok=True)
        shot = f"{shots}/lit_{name}.png"
        freeze_phase(page, idx + 1)  # 冻结相位再取样：同一画面每次跑都得到同一判据值
        page.locator("#gl").screenshot(path=shot)
        npx, dist, minority = clusters2(shot)
        litn = page.evaluate("() => window.ThreeScene.litInfo().lit")
        out[name] = (npx, dist, minority, litn)
        print(f"[{name}] 已点亮={litn} 有效像素={npx} 两簇色距={dist} 少数簇占比={minority}")
        overlay(False)

    browser.close()

print("CONSOLE_ERRORS:", len(errors), errors[:2])
mi = out["multi"]
sg = out["single"]
# R247：结论为「通过」前先证明输入非空
# 阈值依据实测：4 句话点亮约 27 颗星 → 有效像素约两百量级；低于 120 视为截图空白
assert mi[0] > 120 and sg[0] > 120, f"有效像素过少（截图可能为空白）: {out}"
# 双条件：色距够大 且 少数簇占比够高。只比色距会被「1 个像素的抗锯齿噪点」骗过
# （实测单一情绪用例里出现过 色距 0.21 但少数簇占比仅 0.4% 的假双色）
def multicolor(x):
    return x[1] > 0.25 and x[2] > 0.10

assert multicolor(mi), f"多样情绪历史在屏幕上没分成双色簇: {mi}"
# 对照：单一情绪历史必须判不出两簇，否则判据恒真
assert not multicolor(sg), f"判据失效：单一情绪历史也被判成多彩: {sg}"
# 离线隔离注入的端点必然连接失败：只豁免该 URL（含端口）的报错，其余报错仍然致命——
# 不做「ERR_CONNECTION_REFUSED 一律放行」的宽豁免，否则真实断链会被吞掉
real_errors = [(txt, url) for (txt, url) in errors if "127.0.0.1:18123" not in url]
print("REAL_CONSOLE_ERRORS:", len(real_errors), real_errors[:3])
assert len(real_errors) == 0, f"console 报错: {real_errors}"
print("LIT-COLOR-CHECK-PASS")
