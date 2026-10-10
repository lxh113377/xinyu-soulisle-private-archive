# -*- coding: utf-8 -*-
"""对话坞自动收起行为判据（r104 立）。

立此判据的动因：r104 按老大拍板加了「滚进幕内容自动收起坞 / 点标题条展开」，这类
**滚动耦合**交互最容易被后人"顺手"改坏且无人察觉——旧版只有「点幕内区域收起」，
没有任何判据覆盖滚动路径，所以它坏了也只是"感觉坞有点烦"。

判据（D1-D9，逐项独立，禁止聚合掩盖）：
  D1  初始态仍展开（既有默认行为不许被顺手改掉）
  D2  向下滚动后自动收起；D2b 收起后标题条文案与 aria-expanded 同步
  D3  向上滚回顶部**不自动展开**（只收不放，否则来回抖两下坞会反复弹）
  D4  点标题条展开
  D5  **焦点在坞内时不收起**（正在打字/翻记录——话没打完坞不能跑）
  D6  失焦后再向下滚仍会收起
  D7  标题条展开与 #btn-dock 收起两条路径共存且互不打架
  D8  演示态（showtime）下不自动收起（演示期坞由 showtime 统一让位）
  D9  全程无 JS 异常

用法：python _test/dock_auto_check.py [http://127.0.0.1:8123/index.html]
退出码：0=全过 1=判红 2=环境未验（服务起不来 ⇒ 不许判绿）
"""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123/index.html"
res = []


def launch(pw):
    try:
        return pw.chromium.launch()
    except Exception:
        return pw.chromium.launch(channel="msedge")


def ck(name, ok, detail=""):
    res.append(bool(ok))
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, ("  -> " + detail) if detail else ""))


def is_open(pg):
    return pg.eval_on_selector("#chat-dock", "e => e.classList.contains('open')")


def main():
    try:
        with sync_playwright() as p:
            b = launch(p)
            pg = b.new_page(viewport={"width": 1280, "height": 800})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:140]))
            pg.goto(BASE, wait_until="load")
            pg.wait_for_function("() => window.__XINYU__ && window.__XINYU__.opening === 'done'",
                                 timeout=25000)
            pg.wait_for_timeout(600)

            ck("D1 初始态对话坞展开（既有默认行为未变）", is_open(pg))

            pg.evaluate("window.scrollBy(0, 240)")
            pg.wait_for_timeout(700)
            ck("D2 向下滚动后自动收起", not is_open(pg))
            ck("D2b 收起后标题条文案与 aria-expanded 同步",
               pg.inner_text("#btn-dock") == "展开 ▴"
               and pg.get_attribute("#btn-dock", "aria-expanded") == "false",
               "%s / aria-expanded=%s" % (pg.inner_text("#btn-dock"),
                                          pg.get_attribute("#btn-dock", "aria-expanded")))

            pg.evaluate("window.scrollTo(0, 0)")
            pg.wait_for_timeout(700)
            ck("D3 向上滚回顶部不自动展开（只收不放，防抖动）", not is_open(pg))

            pg.click(".dock-title")           # 点标题条空白处（避开里面三个按钮）
            pg.wait_for_timeout(500)
            ck("D4 点标题条展开", is_open(pg))

            pg.focus("#chat-input")
            pg.evaluate("window.scrollBy(0, 240)")
            pg.wait_for_timeout(700)
            ck("D5 焦点在坞内时不自动收起（话没打完坞不能跑）", is_open(pg))

            pg.evaluate("() => document.activeElement.blur()")
            pg.evaluate("window.scrollBy(0, 240)")
            pg.wait_for_timeout(700)
            ck("D6 失焦后再向下滚仍会收起", not is_open(pg))

            pg.evaluate("window.scrollTo(0, 0)")
            pg.click(".dock-title")
            pg.wait_for_timeout(400)
            pg.click("#btn-dock")             # 用既有按钮收起，确认两条路径不打架
            pg.wait_for_timeout(400)
            ck("D7 标题条展开与 #btn-dock 收起两条路径共存", not is_open(pg))
            pg.click("#btn-dock")
            pg.wait_for_timeout(400)
            ck("D7b #btn-dock 仍能展开", is_open(pg))

            pg.click("#btn-lightshow")        # 进演示态
            pg.wait_for_timeout(900)
            in_show = pg.evaluate("() => document.body.classList.contains('showtime')")
            before = is_open(pg)
            pg.evaluate("window.scrollBy(0, 300)")
            pg.wait_for_timeout(600)
            ck("D8 演示态下不自动收起（演示期坞由 showtime 统一让位）",
               (not in_show) or (is_open(pg) == before),
               "showtime=%s open %s->%s" % (in_show, before, is_open(pg)))
            ck("D9 全程无 JS 异常", not errs, str(errs[:2]))
            b.close()
    except Exception as e:
        print("DOCK-AUTO-ENV-ERROR: 服务/浏览器不可用 %s ⇒ 不判绿" % str(e)[:140])
        return 2

    bad = len([x for x in res if not x])
    print("%s 合计 %d 项，失败 %d 项" % ("DOCK-AUTO-FAIL" if bad else "DOCK-AUTO-PASS",
                                        len(res), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
