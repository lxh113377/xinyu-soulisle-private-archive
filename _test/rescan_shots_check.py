# -*- coding: utf-8 -*-
"""r32 交付物回扫：为「离线壳」与「评委自助设置面板」补两张实证截图。
   先落 _test/_shots/，目检通过后才由人工/agent 覆盖 交付物/提交包/img/（不直接碰交付物）。

机器断言（任一失败即 rc=1，不出图）：
  S0  SW 已注册 + 预缓存 ≥17 项（未装满就断网 = 拍到"打不开"而不是"离线可开"）
  S9  断网重载：五幕结构在 / 零 XINYU-SHELL-MISS / 徽章可见 / 截图面无密钥
  S10 设置面板：已打开 / Key 框 value 为空 / type=password / 逐字流式开关可见 / 截图面无密钥

用法：python _test/rescan_shots_check.py
前置：fat jar 在 8123（工作目录 = 项目根），本机有 chromium 或 msedge。
"""
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_test" / "_shots"
BASE = "http://localhost:8123/index.html"
KEY_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    fails = []

    def ck(name, cond, info=""):
        print(("  PASS  " if cond else "  FAIL  ") + name + (f"  -> {info}" if info else ""))
        if not cond:
            fails.append(name)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        miss = []
        pg.on("console", lambda m: miss.append(m.text) if "XINYU-SHELL-MISS" in m.text else None)
        pg.goto(BASE, wait_until="networkidle")
        pg.evaluate("() => localStorage.clear()")
        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(2500)
        reg = pg.evaluate("""async () => {
          const r = await navigator.serviceWorker.getRegistration();
          return !!r && !!(r.active || r.installing || r.waiting);
        }""")
        ck("S0-a SW 已注册", bool(reg))
        cached = []
        for _ in range(40):
            cached = pg.evaluate("""async () => {
              const ks = (await caches.keys()).filter(k => k.startsWith('xinyu-shell-'));
              if (!ks.length) return [];
              const kk = await (await caches.open(ks[0])).keys();
              return kk.map(r => new URL(r.url).pathname);
            }""")
            if len(cached) >= 17:
                break
            pg.wait_for_timeout(400)
        ck("S0-b 预缓存 ≥17 项（离线收益非空壳）", len(cached) >= 17, f"{len(cached)} 项")

        ctx.set_offline(True)
        pg.reload(wait_until="domcontentloaded", timeout=25000)
        pg.wait_for_timeout(2500)
        ok_struct = pg.evaluate("() => !!document.querySelector('#gl') "
                                "&& document.querySelectorAll('section').length >= 5")
        badge = pg.inner_text("#mode-badge") if pg.query_selector("#mode-badge") else ""
        ck("S9-a 断网后五幕结构仍在", bool(ok_struct), f"结构在={ok_struct}")
        ck("S9-b 全程无 XINYU-SHELL-MISS（没有模块漏进壳）", not miss, "; ".join(miss[:2]))
        ck("S9-c 徽章可见且如实降级（禁伪装在线）",
           ("网络不可用" in badge) and ("在线 AI" not in badge), badge.strip()[:34])
        ck("S9-d 截图面无密钥", not KEY_RE.search(pg.inner_text("body")))
        pg.screenshot(path=str(OUT / "rescan_s09_offline.png"))
        ctx.set_offline(False)

        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(1500)
        pg.click("#btn-settings")
        pg.wait_for_timeout(700)
        dlg_open = pg.evaluate("() => { const d = document.querySelector('#dlg-settings'); return !!d && d.open; }")
        key_val = pg.evaluate("() => document.querySelector('#set-key').value")
        key_type = pg.evaluate("() => document.querySelector('#set-key').type")
        stream_row = pg.evaluate("() => !!document.querySelector('#set-stream')")
        ck("S10-a 设置面板已打开", bool(dlg_open))
        ck("S10-b Key 框为空（永不回显已存密钥）", key_val == "", f"value 长度={len(key_val)}")
        ck("S10-c Key 框 type=password", key_type == "password", key_type)
        ck("S10-d 逐字流式开关在面板内可见", bool(stream_row))
        ck("S10-e 截图面无密钥", not KEY_RE.search(pg.inner_text("body")))
        pg.screenshot(path=str(OUT / "rescan_s10_settings.png"))
        b.close()

    print("\nFAILS:", fails if fails else "无")
    print("SHOTS:", sorted(x.name for x in OUT.glob("rescan_s*")))
    print("RESCAN-SHOTS-" + ("PASS" if not fails else "FAIL"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
