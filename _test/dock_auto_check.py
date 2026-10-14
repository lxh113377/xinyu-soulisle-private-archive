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
  D7  三态循环：常规 --点--> 全屏 --点--> 收起 --点--> 常规（r108：#btn-dock 一个按钮管三态）
  D8  演示态（showtime）下不自动收起（演示期坞由 showtime 统一让位）
  D9  全程无 JS 异常
  D10 全屏态滚轮推动星雾进度（r109：虚拟滚动映射，页面滚动锁死）
  D11 退出全屏后进度回到真实滚动值（虚拟值不带出全屏）

用法：python _test/dock_auto_check.py [http://127.0.0.1:8123/index.html]
退出码：0=全过 1=判红 2=环境未验（服务起不来 ⇒ 不许判绿）
"""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123/index.html"
res = []


def launch(pw):
    # r113：手写「先 chromium 再 msedge」的回退 → browser_engine 唯一入口；
    # 并打印引擎身份 —— 不打印的话「本地全绿」无法归因（CI 跑的是另一台浏览器）。
    from browser_engine import launch as be_launch
    b, _engine_face = be_launch(pw, label="dock_auto_check")
    print("[engine] %s" % _engine_face)
    return b


def ck(name, ok, detail=""):
    res.append(bool(ok))
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, ("  -> " + detail) if detail else ""))


def is_open(pg):
    return pg.eval_on_selector("#chat-dock", "e => e.classList.contains('open')")


def _legs_scroll_focus(pg):
    """D1–D6：坞的默认展开、滚动收起、标题条展开、焦点保护、失焦后再收起。

    从 `main` 里搬出来（r178）只为过 loc 的单函数 ≤150 行门 —— 断言文案、等待时长、判定表达式
    一字未动。这一段共同的主题是「滚动/焦点会不会把坞挪走」，与后面的三态循环（D7+）不是一件事。
    """
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

            _legs_scroll_focus(pg)

            pg.evaluate("window.scrollTo(0, 0)")
            pg.click(".dock-title")
            pg.wait_for_timeout(400)
            # 三态循环（老大拍板 r108）：常规 ⛶ → 全屏 ▾ → 收起 ▴ → 常规。
            #   ⚠️ 强度不低于旧版：旧版只断言「点一下就收起」，新版断言**三跳各自到位且不跳步**
            #   （旧版第一条在新语义下会被"进了全屏但仍 open"误判为绿，新版专门堵这个洞）。
            is_full = lambda: pg.eval_on_selector("#chat-dock", "e => e.classList.contains('full')")  # noqa: E731
            pg.click("#btn-dock")
            pg.wait_for_timeout(400)
            ck("D7 常规态点 #btn-dock → 全屏（仍展开且带 .full）", is_open(pg) and is_full())
            ck("D7a 全屏态按钮写「收起 ▾」+ aria-expanded=true",
               pg.inner_text("#btn-dock") == "收起 ▾"
               and pg.get_attribute("#btn-dock", "aria-expanded") == "true",
               "%s / aria-expanded=%s" % (pg.inner_text("#btn-dock"),
                                          pg.get_attribute("#btn-dock", "aria-expanded")))
            pg.click("#btn-dock")
            pg.wait_for_timeout(400)
            ck("D7b 全屏态再点 → 收起（与点标题条两条路径共存不打架）", (not is_open(pg)) and (not is_full()))
            pg.click("#btn-dock")
            pg.wait_for_timeout(400)
            ck("D7c 收起态再点 → 回到常规展开（不跳到全屏）", is_open(pg) and not is_full())

            # r109：全屏态虚拟滚动（页面滚动已锁，星雾改由滚轮映射驱动；退出回真实进度）。
            # 取数口 = window.__XINYU_SCROLL_T__（app.js 的 onProgress / fullScrollDrive 双向写）。
            t_real = pg.evaluate("() => window.__XINYU_SCROLL_T__")
            pg.click("#btn-dock")
            pg.wait_for_timeout(400)
            in_full = is_open(pg) and is_full()
            if in_full:
                t0 = pg.evaluate("() => window.__XINYU_SCROLL_T__")
                pg.mouse.move(640, 400)          # 视口中央（全屏坞上、chat-log 日志区——日志为空时不吃滚轮）
                pg.mouse.wheel(0, 900)
                # r119 改造三：把「定长 300ms 押虚拟映射生效」换成**等被等对象本身的完成态**
                # （t 由 GSAP 逐帧写，机器慢时 300ms 不够 → D10 假红；机器快时白等 → 整跑噪声）。
                # 等不到不抛错：仍由下面的 ck 用现读值判红，证据里带 t0->t1，绝不静默放过。
                try:
                    pg.wait_for_function(
                        "(t0) => window.__XINYU_SCROLL_T__ != null"
                        " && window.__XINYU_SCROLL_T__ > t0",
                        arg=t0, timeout=3000, polling="raf")
                except Exception:                      # noqa: BLE001
                    pass
                t1 = pg.evaluate("() => window.__XINYU_SCROLL_T__")
                ck("D10 全屏态滚轮推动星雾进度（虚拟映射，页面滚动是锁死的）",
                   t1 is not None and t0 is not None and t1 > t0, "%s -> %s" % (t0, t1))
            else:
                ck("D10 全屏态滚轮推动星雾进度（虚拟映射，页面滚动是锁死的）", False, "未能进入全屏态")
            pg.click("#btn-dock")                # 全屏 → 收起（顺带复验 D7b 路径仍通）
            pg.wait_for_timeout(400)
            t2 = pg.evaluate("() => window.__XINYU_SCROLL_T__")
            ck("D11 退出全屏后进度回到真实滚动值（不把虚拟值带出全屏）",
               t2 is not None and t_real is not None and abs(t2 - t_real) < 0.02,
               "real=%s exit=%s" % (t_real, t2))

            # r172b（2026-10-14 老大报障修复）：D10 用**空日志**取证，恰好看不见本次真缺陷——
            # 全屏态 chat-log 可滚时，旧规则让日志先吃滚轮，星雾全程不动（实测复现：上滚时
            # logTop 1117→217 而 t 恒 1）。新页面预种历史日志，专钉「滚轮优先给星雾」：
            # 日志可滚且不在边缘时，上下滚都必须推动 virtT 且日志不许位移。
            pg2 = b.new_page(viewport={"width": 1280, "height": 800})
            errs2 = []
            pg2.on("pageerror", lambda e: errs2.append(str(e)[:140]))
            pg2.add_init_script("""(() => {
              const hist = [];
              for (let i = 1; i <= 14; i++) {
                hist.push({ role: "user", content: "第 " + i + " 条测试消息，今天有点累，想说说学校里的事情。" });
                hist.push({ role: "assistant", content: "我在这里听着。第 " + i + " 条回复：辛苦你了，慢慢说，不着急。" });
              }
              try { localStorage.setItem("peiliao.history.v1", JSON.stringify(hist)); } catch (e) {}
            })();""")
            pg2.goto(BASE, wait_until="load")
            pg2.wait_for_function("() => window.__XINYU__ && window.__XINYU__.opening === 'done'",
                                  timeout=25000)
            pg2.wait_for_timeout(600)
            pg2.evaluate("() => window.scrollTo(0, 0)")
            pg2.wait_for_timeout(500)
            pg2.click("#btn-dock")                # 常态 → 全屏
            pg2.wait_for_timeout(500)
            d12 = pg2.evaluate("""() => {
              const log = document.getElementById("chat-log");
              return { full: document.getElementById("chat-dock").classList.contains("full"),
                       scrollable: log.scrollHeight > log.clientHeight + 2,
                       logTop: log.scrollTop, t: window.__XINYU_SCROLL_T__ };
            }""")
            in_full12 = d12["full"] and d12["scrollable"] and d12["logTop"] > 100
            ck("D12-pre 全屏+日志可滚且停底（复现条件就位）", in_full12,
               "full=%s scrollable=%s logTop=%s" % (d12["full"], d12["scrollable"], d12["logTop"]))
            if in_full12:
                pg2.mouse.move(640, 400)           # 视口中央 = chat-log 日志区
                pg2.mouse.wheel(0, 300)
                pg2.wait_for_timeout(600)
                s1 = pg2.evaluate("() => ({ t: window.__XINYU_SCROLL_T__, logTop: document.getElementById('chat-log').scrollTop })")
                ck("D12a 全屏下滚：virtT 升且日志不位移（滚轮优先给星雾）",
                   s1["t"] is not None and s1["t"] > d12["t"] and s1["logTop"] == d12["logTop"],
                   "t %s->%s logTop %s->%s" % (d12["t"], s1["t"], d12["logTop"], s1["logTop"]))
                pg2.mouse.wheel(0, -300)
                pg2.wait_for_timeout(600)
                s2 = pg2.evaluate("() => ({ t: window.__XINYU_SCROLL_T__, logTop: document.getElementById('chat-log').scrollTop })")
                ck("D12b 全屏上滚：virtT 降且日志不抢滚轮（本次报障主症状）",
                   s2["t"] is not None and s2["t"] < s1["t"] and s2["logTop"] == d12["logTop"],
                   "t %s->%s logTop %s->%s" % (s1["t"], s2["t"], d12["logTop"], s2["logTop"]))
            else:
                ck("D12a 全屏下滚：virtT 升且日志不位移", False, "未能进入全屏+可滚日志态")
                ck("D12b 全屏上滚：virtT 降且日志不抢滚轮", False, "未能进入全屏+可滚日志态")
            ck("D12z 该页面全程无 JS 异常", not errs2, str(errs2[:2]))
            pg2.close()
            pg.click("#btn-dock")                # 收起 → 常规，恢复 D8 需要的展开态
            pg.wait_for_timeout(400)

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
