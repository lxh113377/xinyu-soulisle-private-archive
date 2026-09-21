# -*- coding: utf-8 -*-
"""星雾「是不是真的变彩色了」——像素级回归（判断据不看内部数组）

流程：用真实的底部对话坞连说 4 句话（每条都会点亮一簇星），对 canvas 截图，
     取有效像素做纯色方向 2-means，比两簇中心色距与少数簇占比。
       · 多样情绪历史 → 应判出两簇（画面里有明显不同的颜色）
       · 单一情绪历史 → 必须判不出两簇（否则说明判据恒真、结论作废）
用法：先起静态服务器（python -m http.server 8123 --directory src），再跑本脚本。
注：接线正确性由 _test/browser_check.py 覆盖，本脚本只管「屏幕上肉眼是否可分辨」。
"""
import sys, io, math, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright
from PIL import Image

CASES = [
    ("multi", ["今天收到offer啦，太开心了！", "其实也很难过，心里空落落的", "明天答辩好焦虑，压力好大", "有点心动也很想念那个人"]),
    ("single", ["心里空落落的很难过", "又想哭了，好难受", "今天很低落很失落", "情绪还是很低落"]),
]


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
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8123/index.html", wait_until="networkidle")
    page.evaluate("""() => { localStorage.setItem('peiliao.cfg.v1', JSON.stringify({base:'',key:'',model:''}));
                            localStorage.removeItem('peiliao.emotions.v1'); }""")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(800)

    def overlay(hide):
        page.evaluate("""(hide) => { const v = hide ? 'hidden' : 'visible';
                          document.getElementById('story').style.visibility = v;
                          document.getElementById('topbar').style.visibility = v;
                          document.getElementById('chat-dock').style.visibility = v; }""", hide)

    for name, texts in CASES:
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
        page.locator("#gl").screenshot(path=shot)
        npx, dist, minority = clusters2(shot)
        litn = page.evaluate("() => window.ThreeScene.litInfo().lit")
        out[name] = (npx, dist, minority, litn)
        print(f"[{name}] 已点亮={litn} 有效像素={npx} 两簇色距={dist} 少数簇占比={minority}")
        overlay(False)

    browser.close()

print("CONSOLE_ERRORS:", len(errors), errors[:3])
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
assert len(errors) == 0, f"console 报错: {errors}"
print("LIT-COLOR-CHECK-PASS")
