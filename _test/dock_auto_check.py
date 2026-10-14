# -*- coding: utf-8 -*-
"""对话坞自动收起行为判据（r104 立）。

判据版本：V1.182.0

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
  D11 退出全屏后虚拟行程被**提交**回真实滚动（r182 语义反转：旧版是「丢弃」，
      那正是本次报障里的「丢失」—— 全屏里走完的星雾行程，一点退出就没了）
  D11a 提交后的真实滚动位置与 ScrollTrigger 自身进度自洽（progress↔scrollY 映射不许偏）
  D13 非全屏态滚轮归属：星雾/页面 → 日志 → 拦掉（r182。r172b 只钉了全屏，非全屏无判据，
      于是同一个根因在非全屏原样存活：指针停在 chat-log 上时星雾与页面同时零响应）
  D14 星雾到端点后日志接管（读历史的活路不许被星雾优先级顺手弄丢）
  D15 指针在坞外一律不拦截（原生滚动链路零变更）

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


def _legs_nonfull_wheel(pg):
    """D13-D15（r182）：非全屏态滚轮归属 —— 本次报障真正的漏网处。

    r172b 只钉了全屏（见 D12），非全屏一条判据都没有，于是同一个根因在非全屏原样存活：
    指针停在 #chat-log 上时，嵌套滚动容器先把滚轮吃掉，星雾与页面同时零响应
    （修复前实测：四个刻度 scrollY 恒 600、__XINYU_SCROLL_T__ 恒 0.1436、logTop 0→669）。
    判据按「滚轮归属顺序」逐条独立钉死：星雾 → 日志 → 拦掉。
    """
    def probe():
        return pg.evaluate("""() => {
          const l = document.getElementById('chat-log');
          return { t: window.__XINYU_SCROLL_T__, y: Math.round(window.scrollY),
                   lt: Math.round(l.scrollTop),
                   lm: Math.round(l.scrollHeight - l.clientHeight) };
        }""")

    # 焦点放进输入框以免「滚下去 → 自动收起坞」把日志挪出视口（既有护栏①，非本次引入）
    pg.focus("#chat-input")
    pg.evaluate("() => { document.getElementById('chat-log').scrollTop = 0; window.scrollTo(0, 900); }")
    pg.wait_for_timeout(600)
    c = pg.evaluate("""() => { const r = document.getElementById('chat-log').getBoundingClientRect();
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }; }""")
    pg.mouse.move(c["x"], c["y"])
    pg.wait_for_timeout(200)
    a = probe()
    ck("D13-pre 非全屏+日志可滚且指针停在日志上（复现条件就位）",
       a["lm"] > 100, "logMax=%s cursor=%s,%s" % (a["lm"], c["x"], c["y"]))

    pg.mouse.wheel(0, 300)
    pg.wait_for_timeout(700)
    b = probe()
    ck("D13 非全屏下滚：星雾/页面推进，日志不抢滚轮（本次报障主症状）",
       b["t"] is not None and a["t"] is not None and b["t"] > a["t"]
       and b["y"] > a["y"] and b["lt"] == a["lt"],
       "t %s->%s y %s->%s logTop %s->%s" % (a["t"], b["t"], a["y"], b["y"], a["lt"], b["lt"]))

    # 页面滚到底 ⇒ 星雾到端点 ⇒ 日志接管（读历史的活路不许被星雾优先级顺手弄丢）
    # ⚠️ 必须 instant + 等落定：既有 html{scroll-behavior:smooth}，两参 scrollTo 会走一段补间，
    #    滚轮落在补间中途时 scrollY 还没到底，fogCanGo 仍为真 ⇒ 假红（r182 实测踩到）。
    pg.evaluate("() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })")
    pg.wait_for_function(
        "() => Math.round(window.scrollY) >="
        " Math.round(document.documentElement.scrollHeight - window.innerHeight) - 2",
        timeout=5000)
    pg.wait_for_timeout(300)
    d0 = probe()
    pg.mouse.wheel(0, 300)
    pg.wait_for_timeout(700)
    d1 = probe()
    ck("D14 非全屏滚到页面底部后日志接管（星雾优先级不吞掉读历史）",
       d1["lt"] > d0["lt"] and abs(d1["t"] - d0["t"]) < 0.02,
       "t %s->%s logTop %s->%s" % (d0["t"], d1["t"], d0["lt"], d1["lt"]))

    # 指针在坞外 ⇒ 一律不拦截，原生滚动链路零变更
    pg.evaluate("() => document.activeElement.blur()")
    pg.evaluate("() => window.scrollTo(0, 600)")
    pg.wait_for_timeout(600)
    out = pg.evaluate("""() => {
      const ev = new WheelEvent('wheel', { deltaY: 300, bubbles: true, cancelable: true });
      document.getElementById('story').dispatchEvent(ev);
      return ev.defaultPrevented;
    }""")
    ck("D15 指针在坞外时不拦截滚轮（原生滚动不受本次改动影响）", out is False,
       "defaultPrevented=%s" % out)


def _legs_full_wheel(pg, b, base):
    """D10-D12（r109/r172b/r182）：全屏态的虚拟滚动、退出提交、以及「日志可滚时滚轮优先给星雾」。

    从 `main` 里搬出（r182）只为过 loc 的单函数 ≤150 行门 —— 断言文案、等待时长、判定表达式
    一字未动。这一段共同的主题是「全屏下滚轮归谁」，与 _legs_nonfull_wheel 的非全屏归属是
    同一条规则的两端，刻意分开放：两段都要先复现条件再断言，堆在一起会让复现步骤互相污染
    （D13 把日志拨到顶，D12-pre 要求日志停底）。
    """
    is_full = lambda: pg.eval_on_selector("#chat-dock", "e => e.classList.contains('full')")  # noqa: E731

    # r109：全屏态虚拟滚动（页面滚动已锁，星雾改由滚轮映射驱动；退出提交虚拟行程）。
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
    # r182：语义反转 —— 旧 D11 断言「退出全屏回到进入前的真实值」，而那正是本次报障里的
    # 「丢失」：全屏里把星雾走完再退出，行程被整段丢弃。现改为**提交**虚拟行程，
    # 判据随之从「等于进入前的 real」翻成「保留驱动态 + 与 ScrollTrigger 自身进度自洽」。
    ck("D11 退出全屏后虚拟行程被提交（不弹回进入前的真实值＝不丢）",
       t2 is not None and t_real is not None and t1 is not None and t2 > t_real + 0.02,
       "real=%s driven=%s exit=%s" % (t_real, t1, t2))
    stp = pg.evaluate(
        "() => { const s = window.ScrollTrigger.getAll()"
        ".filter((x) => x.trigger && x.trigger.id === 'story')[0];"
        "return s ? s.progress : null; }")
    ck("D11a 提交后的真实滚动位置与 ScrollTrigger 自身进度自洽（映射不许偏）",
       stp is not None and t2 is not None and abs(stp - t2) < 0.02,
       "app=%s scrollTrigger=%s" % (t2, stp))

    _legs_full_wheel_seeded(b, base)


def _legs_full_wheel_seeded(b, base):
    """D12（r172b）：D10 用**空日志**取证，恰好看不见真缺陷——全屏态 chat-log 可滚时，
    旧规则让日志先吃滚轮，星雾全程不动（实测复现：上滚时 logTop 1117→217 而 t 恒 1）。
    新页面预种历史日志，专钉「滚轮优先给星雾」：日志可滚且不在边缘时，上下滚都必须推动
    virtT 且日志不许位移。进全屏前先在同页跑非全屏归属（D13-D15），因为一旦进全屏就回不去了。
    """
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
    pg2.goto(base, wait_until="load")
    pg2.wait_for_function("() => window.__XINYU__ && window.__XINYU__.opening === 'done'",
                          timeout=25000)
    pg2.wait_for_timeout(600)
    pg2.evaluate("() => window.scrollTo(0, 0)")
    pg2.wait_for_timeout(500)
    _legs_nonfull_wheel(pg2)
    # 收尾必须把日志复位到停底：D13 会把它拨到顶，而 D12-pre 的复现条件要求 logTop>100
    # （真实聊天里日志默认停底），不复位就是 D12 假红。
    pg2.evaluate("""() => {
              const d = document.getElementById('chat-dock');
              const l = document.getElementById('chat-log');
              while (!d.classList.contains('open')) document.getElementById('btn-dock').click();
              l.scrollTop = l.scrollHeight;
              window.scrollTo({ top: 0, behavior: 'instant' });
            }""")
    pg2.wait_for_timeout(600)
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

            _legs_full_wheel(pg, b, BASE)   # D10-D12：全屏虚拟滚动 + 退出提交 + 日志可滚时滚轮优先给星雾
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
