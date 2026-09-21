# -*- coding: utf-8 -*-
"""一键点亮验收：清屏（UI 让位）+ 六色各自可见 + 铺得够满够散 + 播完不自动跳回

判据：① 黑屏窗口内的一帧几乎全黑（清屏真的发生）；
      ② 演示期间 UI 全部隐藏（body.showtime + 坞 opacity=0）；
      ③ 每个情绪色各自的「色相 ±18° 像素占比」≥1% —— 六种都要找得到；
      ④ 4×4 网格覆盖 ≥12 格（够散），未点亮对照为 0 格；
      ⑤ **播完仍停在清屏画面**（不自动跳回），且滚动 / Esc 都不会中断它；
      ⑥ 右下角返回按钮 → UI 回来且**保留**点亮的星雾；坞里的「↺ 回到我的记忆」才清空；
      ⑦ 一键点亮**不写入**本机记忆。
用法：先起静态服务器（python -m http.server 8123 --directory src），再跑本脚本。
"""
import sys, io, math, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright
from PIL import Image

TOL_DEG = 18.0
MIN_SHARE = 0.01
GRID = 4
MIN_CELLS = 12


def rgb2hue(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return None
    if mx == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6
    elif mx == g:
        h = ((b - r) / d + 2) / 6
    else:
        h = ((r - g) / d + 4) / 6
    return h * 360.0


def sample(path, min_v=0.22, min_s=0.12):
    im = Image.open(path).convert("RGB").resize((400, 250))
    w, h = im.size
    px = im.load()
    out = []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            R, G, B = r / 255, g / 255, b / 255
            mx, mn = max(R, G, B), min(R, G, B)
            if mx < min_v or (mx - mn) / mx < min_s:
                continue
            hu = rgb2hue(R, G, B)
            if hu is not None:
                out.append((x, y, hu))
    return out, w, h


def share_near(pts, target_hue):
    if not pts:
        return 0.0
    n = 0
    for _, _, h in pts:
        d = abs(h - target_hue) % 360
        if min(d, 360 - d) <= TOL_DEG:
            n += 1
    return n / len(pts)


def coverage(pts, w, h):
    cells = [[0] * GRID for _ in range(GRID)]
    for x, y, _ in pts:
        cells[min(GRID - 1, y * GRID // h)][min(GRID - 1, x * GRID // w)] += 1
    return sum(1 for row in cells for c in row if c >= 3)


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
    page.wait_for_timeout(900)

    def overlay(hide):
        # ⚠️ #gl 是全屏画布，元素截图 = 整屏，会把浮在上面的 UI（含右下角返回按钮）一起拍进去，
        #    必须在取样时一并遮掉，否则按钮的紫边与亮字会被当成「点亮的星」
        page.evaluate("""(hide) => { const v = hide ? 'hidden' : 'visible';
                          document.getElementById('story').style.visibility = v;
                          document.getElementById('topbar').style.visibility = v;
                          document.getElementById('chat-dock').style.visibility = v;
                          document.getElementById('btn-exit-show').style.visibility = v; }""", hide)

    def ui_state():
        return page.evaluate("""() => ({
          showtime: document.body.classList.contains('showtime'),
          dockOpacity: parseFloat(getComputedStyle(document.getElementById('chat-dock')).opacity),
          exitVisible: getComputedStyle(document.getElementById('btn-exit-show')).display !== 'none'
        })""")

    shots = "c:/Users/37533/Desktop/workspace/项目/陪聊/_test/_shots"
    os.makedirs(shots, exist_ok=True)

    palette = page.evaluate("() => window.EmotionEngine.palette().map(p => ({label:p.label, color:p.color}))")
    targets = [(p["label"], rgb2hue(*p["color"])) for p in palette]
    mem_before = page.evaluate("() => window.MemoryStore.all().length")
    lit_before = page.evaluate("() => window.ThreeScene.litInfo().lit")

    # --- 对照：未点亮 ---
    overlay(True)
    page.wait_for_timeout(800)
    shot0 = f"{shots}/lightshow_before.png"
    page.locator("#gl").screenshot(path=shot0)
    pts0, w0, h0 = sample(shot0)
    before = {lab: round(share_near(pts0, h), 4) for lab, h in targets}
    cov0 = coverage(pts0, w0, h0)
    overlay(False)

    # --- 一键点亮：黑屏帧 + UI 让位 ---
    page.click("#btn-lightshow")
    # 黑屏帧必须早采：第一批星在 700ms 处开始亮，采晚了就抓到「已点亮」的画面
    page.wait_for_timeout(500)
    overlay(True)
    shot_b = f"{shots}/lightshow_blackout.png"
    page.locator("#gl").screenshot(path=shot_b)
    pts_b, _, _ = sample(shot_b)
    page.wait_for_timeout(320)   # 再等 UI 淡出（.45s）完成再读状态
    ui_hidden = ui_state()

    # --- 等点亮结束（约 3.3s） ---
    page.wait_for_timeout(6400)  # 点亮过程 ≈3.7s + 脉冲衰减
    ui_after = ui_state()        # 关键：播完应**仍**停在清屏画面
    # 演示态下继续滚动欣赏：不应被中断
    page.evaluate("window.scrollTo(0, 1200)")
    page.wait_for_timeout(900)
    scroll_y = page.evaluate("() => window.scrollY")
    ui_after_scroll = ui_state()
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    ui_after_esc = ui_state()

    overlay(True)
    shot1 = f"{shots}/lightshow_after.png"
    page.locator("#gl").screenshot(path=shot1)
    pts1, w1, h1 = sample(shot1)
    overlay(False)
    after = {lab: round(share_near(pts1, h), 4) for lab, h in targets}
    cov1 = coverage(pts1, w1, h1)
    lit_after = page.evaluate("() => window.ThreeScene.litInfo().lit")

    # --- 右下角返回按钮：UI 回来但保留星雾 ---
    page.click("#btn-exit-show")
    page.wait_for_timeout(700)
    ui_back = ui_state()
    lit_keep = page.evaluate("() => window.ThreeScene.litInfo().lit")

    # --- 坞里的「↺ 回到我的记忆」才清空 ---
    page.click("#btn-lightshow")
    page.wait_for_timeout(700)
    lit_cleared = page.evaluate("() => window.ThreeScene.litInfo().lit")
    mem_after = page.evaluate("() => window.MemoryStore.all().length")
    browser.close()

print("TARGET_HUES:", {l: round(h, 1) for l, h in targets})
print("有效像素/覆盖格: 对照 %d/%d | 黑屏帧 %d | 点亮后 %d/%d" % (len(pts0), cov0, len(pts_b), len(pts1), cov1))
print("对照(未点亮) 各色占比:", before)
print("点亮后 各色占比:", after)
print("UI: 演示期", ui_hidden, "| 播完", ui_after, "| 滚动后", ui_after_scroll, "(scrollY=%d)" % scroll_y, "| Esc 后", ui_after_esc)
print("UI: 点返回后", ui_back)
print("LIT: %d → %d → 返回后 %d → 回到记忆 %d | MEM: %d → %d" % (lit_before, lit_after, lit_keep, lit_cleared, mem_before, mem_after))
print("CONSOLE_ERRORS:", len(errors), errors[:3])

assert len(targets) == 6, f"应为六种情绪，实际 {len(targets)}"
assert len(pts1) > 800, f"点亮后有效像素过少（截图可能空白）: {len(pts1)}"
missing = [l for l, v in after.items() if v < MIN_SHARE]
assert not missing, f"这些情绪在屏幕上找不到对应颜色: {missing}"
fake = [l for l, v in before.items() if v >= MIN_SHARE]
assert not fake, f"判据失效：未点亮时也判出这些颜色: {fake}"
assert len(pts_b) < 60, f"一键点亮没有清屏（黑屏帧仍有 {len(pts_b)} 个有效像素）"
assert ui_hidden["showtime"] and ui_hidden["dockOpacity"] < 0.05, f"演示期间 UI 未隐藏: {ui_hidden}"
# 播完不自动跳回 + 只有右下角按钮能退
assert ui_after["showtime"], "播完自动跳回了（应保持清屏画面）"
assert ui_after["exitVisible"], "播完后右下角返回按钮不可见"
assert scroll_y > 100 and ui_after_scroll["showtime"], f"演示态下滚动被中断或没滚起来: scrollY={scroll_y}"
assert ui_after_esc["showtime"], "Esc 仍能退出（应只保留右下角按钮一个退出口）"
assert cov1 >= MIN_CELLS, f"点亮的星铺得不够散：只覆盖 {cov1}/16 格"
assert cov0 == 0, f"判据失效：未点亮时也覆盖了 {cov0} 格"
# 返回按钮保留星雾；清空要再点一次
assert not ui_back["showtime"] and ui_back["dockOpacity"] > 0.9, f"点返回后 UI 未恢复: {ui_back}"
assert lit_keep >= 6 * 170, f"点返回后星雾被清掉了（应保留）: {lit_keep}"
assert lit_cleared == 0, f"「回到我的记忆」未清空演示点亮: {lit_cleared}"
assert mem_after == mem_before, f"一键点亮污染了本机记忆: {mem_before} → {mem_after}"
assert len(errors) == 0, f"console 报错: {errors}"
print("LIGHTSHOW-CHECK-PASS")
