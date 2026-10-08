# -*- coding: utf-8 -*-
"""r32 交付物回扫：为「离线壳」与「评委自助设置面板」补两张实证截图。
   先落 _test/_shots/，目检通过后才由人工/agent 覆盖 交付物/提交包/img/（不直接碰交付物）。

机器断言（腿名册 LEGS 是唯一分母；任一条没被记录 = 记未验并在结论行点名）：
  S0-0 导航可达（goto 未超时未报错）——r100 新增：把它崩掉就是"无原因判红"的那条路
  S0   SW 已注册 + 预缓存 ≥17 项（未装满就断网 = 拍到"打不开"而不是"离线可开"）
  S9   断网重载：五幕结构在 / 零 XINYU-SHELL-MISS / 徽章可见 / 截图面无密钥
  S10  设置面板：已打开 / Key 框 value 为空 / type=password / 逐字流式开关可见 / 截图面无密钥

用法：python _test/rescan_shots_check.py [--nav-timeout N]
退出码：0=全绿｜1=判红（含未验腿与仪器兜底腿 SX）｜2=环境未验（playwright/浏览器不可达）
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


# 腿名册 = 唯一分母源（r100 三态纪律的结构面）。任何一条没被记录 ⇒ 记未验并在结论行点名。
# 原实现「跑到哪崩到哪就只报前几条」，于是"整条套件其实没验完"与"验完且全绿"在受理面上同形。
LEGS = ("S0-0 导航可达（goto 未超时未报错）",
        "S0-a SW 已注册", "S0-b 预缓存 ≥17 项（离线收益非空壳）",
        "S9-a 断网后五幕结构仍在", "S9-b 全程无 XINYU-SHELL-MISS（没有模块漏进壳）",
        "S9-c 徽章可见且如实降级（禁伪装在线）", "S9-d 截图面无密钥",
        "S10-a 设置面板已打开", "S10-b Key 框为空（永不回显已存密钥）",
        "S10-c Key 框 type=password", "S10-d 逐字流式开关在面板内可见",
        "S10-e 截图面无密钥")


def _why(e):
    return "%s: %s" % (type(e).__name__, str(e).splitlines()[0][:90])


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("RESCAN-SHOTS-ENV-UNVERIFIED playwright 不可用 %s" % _why(e))
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    fails, unv, seen = [], [], set()

    def ck(name, cond, info=""):
        seen.add(name)
        print(("  PASS  " if cond else "  FAIL  ") + name + (f"  -> {info}" if info else ""))
        if not cond:
            fails.append(name)

    def ck_unv(name, why):
        seen.add(name)
        print("  UNV   " + name + "  -> " + why)
        unv.append(name)

    def report():
        for n in LEGS:
            if n not in seen:
                ck_unv(n, "执行流未到达该腿（前置腿之后中断）")
        print("\nFAILS:", fails if fails else "无")
        print("UNVERIFIED:", unv if unv else "无")
        print("SHOTS:", sorted(x.name for x in OUT.glob("rescan_s*")))
        bad = bool(fails or unv)
        print("RESCAN-SHOTS-" + ("FAIL" if bad else "PASS")
              + (" 判红=%d 未验=%d 腿名册=%d" % (len(fails), len(unv), len(LEGS)) if bad else ""))
        return 1 if bad else 0

    # 演习口（真实超时，不是代码里 raise 的仿品）：`--nav-timeout 1` 让 pg.goto 必超时 ⇒
    # 证据面必须出现「S0-0 判红 + 其余腿记未验 + RESCAN-SHOTS-FAIL 结论行」，而不是 traceback。
    nav_to = 30000
    if "--nav-timeout" in sys.argv:
        nav_to = int(sys.argv[sys.argv.index("--nav-timeout") + 1])

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e_first:
            try:
                b = p.chromium.launch(channel="msedge")
            except Exception as e:
                # r100：浏览器双档全败 = **环境**未验（rc=2）。原实现在这里二次抛错逃出进程，
                # 电池只看到 rc=1 且没有任何 RESCAN-SHOTS-* 结论行（「无原因判红」）。
                print("RESCAN-SHOTS-ENV-UNVERIFIED 浏览器不可达（chromium/msedge 双档均败）%s ｜ %s"
                      % (_why(e_first), _why(e)))
                return 2
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        miss = []
        pg.on("console", lambda m: miss.append(m.text) if "XINYU-SHELL-MISS" in m.text else None)
        try:
            pg.goto(BASE, wait_until="networkidle", timeout=nav_to)
            ck("S0-0 导航可达（goto 未超时未报错）", True, "timeout=%dms" % nav_to)
        except Exception as e:
            ck("S0-0 导航可达（goto 未超时未报错）", False, "浏览器层导航异常 %s" % _why(e))
            try:
                b.close()
            except Exception:                      # noqa: BLE001
                pass
            return report()
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
        try:
            b.close()
        except Exception as e:                       # noqa: BLE001
            print("  （浏览器关闭失败 %s，不影响判据）" % _why(e))

    return report()


def guarded_main():
    """r100：判据的失败路径自己不能崩，也不能崩掉结论行。未预期异常逃出 main 时电池只看到
    rc=1 而拿不到任何 RESCAN-SHOTS-* 行 ⇒ 与真红同形。兜底腿照常印结论行并点名仪器自身异常。"""
    try:
        return main()
    except SystemExit:
        raise
    except BaseException as e:                       # noqa: BLE001
        print("  FAIL  SX 判据自身未崩溃  -> 未预期异常 %s" % _why(e))
        print("RESCAN-SHOTS-FAIL 判红=1 条 SX（仪器自身异常；上行之前是本异常前已判定项）")
        return 1


if __name__ == "__main__":
    sys.exit(guarded_main())
