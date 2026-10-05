# 心屿 · 语音输入（Web Speech API）真机实测  ——  L8
# 用法: python _test/voice_check.py [url]
#
# 思路：用系统 msedge（Playwright 内置 chromium 未下载）+ 假麦克风设备 + 自动授权，
#       在页面脚本执行前注入一层 SpeechRecognition 包装器，记录构造/start/stop 次数，
#       再观察按钮 DOM 的监听态（class=recording）与恢复态。
#       判据只看**真实发生过的事实**：API 存在吗？start 真被调用了吗？监听态出现过吗？能恢复吗？
import asyncio
import os
import sys

from playwright.async_api import async_playwright

URL = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8125/")

INIT_SCRIPT = """
window.__voice = { constructed: false, started: 0, stopped: 0, ev: [] };
(function () {
  var Orig = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Orig) { window.__voice.unsupported = true; return; }
  function Wrapped() {
    var r = new Orig();
    window.__voice.constructed = true;
    // 真实事件序列（假麦克风无声，但 start / error / end 一定会发生，
    // 抓出来才知道「演示当天」会卡在哪一步：授权 / 网络 / 无语音）
    var push = function (s) { window.__voice.ev.push(s); };
    r.addEventListener("start", function () { push("start"); });
    r.addEventListener("audiostart", function () { push("audiostart"); });
    r.addEventListener("result", function (e) {
      push("result:n=" + (e && e.results ? e.results.length : "?"));
    });
    r.addEventListener("error", function (e) { push("error:" + (e && e.error)); });
    r.addEventListener("end", function () { push("end"); });
    var s = r.start.bind(r);
    r.start = function () { window.__voice.started += 1; return s(); };
    var st = r.stop.bind(r);
    r.stop = function () { window.__voice.stopped += 1; return st(); };
    return r;
  }
  Wrapped.prototype = Orig.prototype;
  window.SpeechRecognition = Wrapped;
  window.webkitSpeechRecognition = Wrapped;
})();
"""

# 桩：把 window.SpeechRecognition **整体替换**掉，专门测「浏览器不配合时的退出态」。
# 与上面包装器的分工：包装器回答「真机能不能用」（CI 无麦克风只能 SKIP），
# 桩回答「浏览器不给 end 时本产品会不会把自己锁死」——这条与环境无关，任何环境都不许降级。
STUB_SCRIPT = """
window.__stub = { started: 0, stopped: 0, silent: true, startThrows: false, sendResult: false, evt: [] };
(function () {
  function SR() {
    var self = this;
    var fire = function (name, arg) {
      window.__stub.evt.push(name);
      var h = self["on" + name];
      if (typeof h === "function") {
        try { h.call(self, arg || {}); } catch (e) { window.__stub.evt.push("throw:" + name); }
      }
    };
    this.start = function () {
      window.__stub.started += 1;
      if (window.__stub.startThrows) { throw new Error("InvalidStateError: recognition already started"); }
      fire("start");
      if (window.__stub.sendResult) {
        setTimeout(function () {
          fire("result", { results: [[{ transcript: "你好", confidence: 0.9 }]] });
        }, 60);
      }
    };
    this.stop = function () {
      window.__stub.stopped += 1;
      // silent=true ⇒ 收到 stop() 后**不派发 end**（r96 实测真机 1/3 就是这个形状）。
      if (!window.__stub.silent) { setTimeout(function () { fire("end"); }, 30); }
    };
    this.abort = this.stop;
  }
  window.SpeechRecognition = SR;
  window.webkitSpeechRecognition = SR;
})();
"""


async def open_stub_page(browser, url, cfg):
    """新开一个 context 装桩并灌入本次场景的开关。返回 (ctx, page, pageerror 列表)。"""
    ctx = await browser.new_context()
    await ctx.add_init_script(STUB_SCRIPT)
    p = await ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    await p.goto(url, wait_until="load", timeout=60000)
    await p.wait_for_timeout(800)
    await p.evaluate("(c) => Object.assign(window.__stub, c)", cfg)
    return ctx, p, errs


async def class_is(page, want):
    """轮询 #btn-voice 的 class 是否达到 want（True=在监听态）。返回 (达成, 最后一次 class)。"""
    btn = page.locator("#btn-voice")
    cls = ""
    for _ in range(40):  # 最多 2s
        cls = await btn.get_attribute("class") or ""
        if ("recording" in cls) == want:
            return True, cls
        await page.wait_for_timeout(50)
    return False, cls


async def stub_legs(browser, url):
    """A8/A9/A10：退出态三腿。每条腿都自带前置断言，防止「桩没生效却判通过」的白过。"""
    out = []

    # --- A8：stop() 被调用但浏览器**没派发 end**（真机 1/3）⇒ 按钮仍必须复位
    ctx8, p8, errs8 = await open_stub_page(browser, url, {"silent": True})
    b8 = p8.locator("#btn-voice")
    await b8.click(timeout=5000)
    entered, cls = await class_is(p8, True)
    if not entered:
        out.append("A8 前置缺失：桩里第一次点击后从未进入监听态（class=%r）" % cls)
    else:
        await b8.click(timeout=5000)          # 再点一次 = 用户请求退出
        s8 = await p8.evaluate("() => window.__stub")
        if s8["stopped"] < 1:
            out.append("A8 前置缺失：第二次点击没调用 rec.stop()（stub=%s）" % s8)
        else:
            ok, cls = await class_is(p8, False)
            s8 = await p8.evaluate("() => window.__stub")
            if not ok:
                out.append("A8 卡在监听态：stop() 已调用、浏览器没派发 end ⇒ 按钮永不复位，"
                           "之后每次点击只会再调 stop()（ASR 到刷新前点不回来）class=%r evt=%s"
                           % (cls, s8["evt"]))
            elif "end" in s8["evt"]:
                out.append("A8 判据失效：桩竟然派发到了 end（evt=%s）⇒ 本腿没在「无 end」路径上做断言"
                           % s8["evt"])
            else:
                print("A8 PASS  stop() 后没有 end 事件也复位（evt=%s class=%r）" % (s8["evt"], cls))
                await b8.click(timeout=5000)   # 复位后必须能再次启动
                await p8.wait_for_timeout(200)
                s8b = await p8.evaluate("() => window.__stub")
                if s8b["started"] >= 2:
                    print("A8b PASS  复位后再次点击重新 start（started=%d）" % s8b["started"])
                else:
                    out.append("A8b 复位后第三次点击没有重新 start（stub=%s）⇒ 退出态把识别器锁死了" % s8b)
    if errs8:
        out.append("A8 未捕获异常逃逸到页面 %d 条: %s" % (len(errs8), errs8[:2]))
    await ctx8.close()

    # --- A9 对照腿：正常派发 end 时同样必须复位，且 onresult 链路没被改坏
    ctx9, p9, errs9 = await open_stub_page(browser, url, {"silent": False, "sendResult": True})
    b9 = p9.locator("#btn-voice")
    await b9.click(timeout=5000)
    entered, cls = await class_is(p9, True)
    if not entered:
        out.append("A9 前置缺失：正常桩里点击后未进入监听态（class=%r）" % cls)
    else:
        await p9.wait_for_timeout(300)
        t9 = await p9.evaluate("() => { var e = document.querySelector('#chat-input'); return e ? e.value : null; }")
        await b9.click(timeout=5000)
        # 对照腿必须先确认桩真派发到了 end，再断言复位 —— 修好后 class 是**同步**复位的，
        # 先读 class 就会抢在 30ms 定时器前面，把这条腿判成「没走正常路径」（实测踩过一次）。
        s9 = {"evt": []}
        for _ in range(40):  # 最多 2s
            s9 = await p9.evaluate("() => window.__stub")
            if "end" in s9["evt"]:
                break
            await p9.wait_for_timeout(50)
        ok, cls = await class_is(p9, False)
        if not ok:
            out.append("A9 对照腿判红：正常派发 end 时也没复位（class=%r stub=%s）" % (cls, s9))
        elif "end" not in s9["evt"]:
            out.append("A9 判据失效：这条本该走「派发 end」的正常路径，2s 内没等到 end（evt=%s）" % s9["evt"])
        else:
            print("A9 PASS  正常路径（stop→end）同样复位（evt=%s）" % s9["evt"])
        if "result" not in s9["evt"]:
            out.append("A9b 判据失效：桩没派发 result，输入框那条断言是白断（evt=%s）" % s9["evt"])
        elif t9 and "你好" in t9:
            print("A9b PASS  onresult 仍写回输入框（value=%r）" % t9)
        else:
            out.append("A9b onresult 链路被改坏：桩派发了 result 但输入框没收到文本（value=%r evt=%s）"
                       % (t9, s9["evt"]))
    if errs9:
        out.append("A9 未捕获异常逃逸到页面 %d 条: %s" % (len(errs9), errs9[:2]))
    await ctx9.close()

    # --- A10：rec.start() 抛异常 ⇒ 按钮不得留在监听态，异常不得逃逸（voice.js 头部约束 2）
    ctx10, p10, errs10 = await open_stub_page(browser, url, {"startThrows": True})
    b10 = p10.locator("#btn-voice")
    await b10.click(timeout=5000)
    s10 = await p10.evaluate("() => window.__stub")
    if s10["started"] < 1:
        out.append("A10 前置缺失：点击没有调用 rec.start()（stub=%s）" % s10)
    else:
        ok, cls = await class_is(p10, False)
        if not ok:
            out.append("A10 卡在监听态：rec.start() 抛异常后按钮仍留在 class=%r" % cls)
        else:
            print("A10 PASS  start() 抛异常后按钮复位（class=%r）" % cls)
        if errs10:
            out.append("A10 约束2 违背：start() 的异常未被吞掉、逃逸成 pageerror：%s" % errs10[:2])
        else:
            print("A10b PASS  start() 异常未逃逸（pageerror=0）")
    await ctx10.close()
    return out


def no_input_device(ev):
    """纯函数：本环境的"识别失败"是否属于**环境不具备音频输入设备**（而非产品坏了）。

    成立条件（两条同时满足，缺一即判红）：
      1) 确在 CI（`CI` 环境变量由 Actions 自动置）；
      2) 出现的错误**全部**是 `audio-capture`（容器里没有采集设备）。
    ⚠️ `not-allowed` / `service-not-allowed` **不再**算环境借口（r35 收紧）：那是麦克风权限被拒，
    正是演示当天会真发生的阻断，把它一并降级等于把缺陷藏进"CI 允许"里。
    """
    errs = [e for e in ev if e.startswith("error:")]
    return bool(os.environ.get("CI")) and bool(errs) and all("audio-capture" in e for e in errs)


def selftest() -> int:
    """判据非恒真自证：`no_input_device` 的五个边界（含两个反向方向）。"""
    cases = [
        # (ev, CI 环境, 期望, 说明)
        (["start", "error:audio-capture", "end"], "1", True, "CI + 仅无设备 ⇒ 降级"),
        (["start", "error:audio-capture", "end"], None, False, "本机同错误 ⇒ 仍判红（不许拿 CI 当挡箭牌）"),
        (["start", "error:not-allowed", "end"], "1", False, "CI + 权限被拒 ⇒ 真阻断，不降级"),
        (["start", "error:audio-capture", "error:not-allowed"], "1", False, "混合 ⇒ 含权限问题就不降级"),
        (["start", "end"], "1", False, "无任何错误 ⇒ 不该拿环境当理由"),
    ]
    bad = []
    saved = os.environ.get("CI")
    try:
        for ev, ci, want, why in cases:
            if ci is None:
                os.environ.pop("CI", None)
            else:
                os.environ["CI"] = ci
            got = no_input_device(ev)
            print("  %s  %s" % ("OK  " if got == want else "BAD ", why))
            if got != want:
                bad.append(f"{why}（期望 {want} 实得 {got}）")
        # 反向：若把判定改成恒真/恒假，上述用例必须整批改判 ⇒ 用例真的有判别力
        os.environ["CI"] = "1"
        if no_input_device([]) or no_input_device(["error:not-allowed"]):
            bad.append("恒真退化未被抓到")
    finally:
        if saved is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = saved
    if bad:
        print("VOICE-SELFTEST-FAIL: " + " ; ".join(bad))
        return 1
    print("VOICE-SELFTEST-PASS: %d 个边界用例全过（含本机不降级与权限类不降级两个反向方向）" % len(cases))
    return 0


async def main() -> int:
    fails = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            args=[
                "--use-fake-ui-for-media-stream",      # 自动同意麦克风授权
                "--use-fake-device-for-media-stream",  # 提供假音频输入设备
            ],
        )
        ctx = await browser.new_context(permissions=["microphone"])
        await ctx.add_init_script(INIT_SCRIPT)
        page = await ctx.new_page()

        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append("pageerror: " + str(e)))

        await page.goto(URL, wait_until="load", timeout=60000)
        await page.wait_for_timeout(1500)

        v = await page.evaluate("() => window.__voice")
        print("voice hook:", v)

        btn = page.locator("#btn-voice")

        # A1 Web Speech API 存在（页面构造了识别器 => 按钮不会被隐藏）
        if not v.get("constructed"):
            fails.append("A1 未构造 SpeechRecognition（浏览器不支持或脚本未跑）")
        else:
            print("A1 PASS  SpeechRecognition 已构造 -> 语音按钮不会被隐藏")

        # A2 按钮可见且可点击（未被其它浮层遮挡）
        try:
            visible = await btn.is_visible()
        except Exception as exc:  # noqa: BLE001
            visible = False
            fails.append("A2 #btn-voice 定位失败: %s" % exc)
        if visible:
            print("A2 PASS  #btn-voice 可见")
        else:
            fails.append("A2 #btn-voice 不可见（display:none 或被遮挡）")

        # A3 点击 -> start() 真被调用
        await btn.click(timeout=5000)
        await page.wait_for_timeout(800)
        v = await page.evaluate("() => window.__voice")
        if v.get("started", 0) >= 1:
            print("A3 PASS  rec.start() 被调用 %d 次" % v["started"])
        else:
            fails.append("A3 点击后 rec.start() 未被调用（按钮事件没接上）")

        # A4 监听态出现过（class=recording），且 stop 后能恢复
        saw_recording = False
        for _ in range(40):  # 最多 4s
            cls = await btn.get_attribute("class") or ""
            if "recording" in cls:
                saw_recording = True
                break
            await page.wait_for_timeout(100)
        if saw_recording:
            print("A4 PASS  进入监听态（class=recording）")
        elif no_input_device((await page.evaluate("() => window.__voice")).get("ev", [])):
            print("A4  SKIP  CI 无音频输入设备（audio-capture）⇒ 监听态不可能出现（本机跑同一条仍判红）")
        else:
            fails.append("A4 未观察到监听态（class=recording 从未出现）")

        # A5 恢复：再点一次走 stop()（或识别自然结束）-> recording 移除、文案还原
        if saw_recording:
            try:
                await btn.click(timeout=5000)
            except Exception:  # noqa: BLE001
                pass
        recovered = False
        for _ in range(80):  # 最多 8s
            cls = await btn.get_attribute("class") or ""
            txt = (await btn.inner_text() or "").strip()
            if "recording" not in cls:
                recovered = True
                print("A5 PASS  退出监听态，按钮还原 -> text=%r class=%r" % (txt, cls))
                break
            await page.wait_for_timeout(100)
        if not recovered:
            fails.append("A5 卡在监听态，未恢复（8s 内 class=recording 未移除）")

        v = await page.evaluate("() => window.__voice")
        print("voice hook(final):", v)

        # A7 真实事件序列：start 必须发生；授权类错误是演示级阻断，其余（无语音/网络）只提示
        ev = v.get("ev", [])
        print("A7 事件序列:", ev)
        if "start" not in ev:
            fails.append("A7 识别未真正 start（事件序列=%s）" % ev)
        else:
            print("A7 PASS  识别已 start")
        blocking = [e for e in ev if e.startswith("error:") and
                    any(k in e for k in ("not-allowed", "service-not-allowed", "audio-capture"))]
        # CI 容器里没有音频输入设备，recognize() 只会回 audio-capture ⇒
        # 那是**环境不具备**、不是产品坏了（本机跑同一条会真断言；权限类错误不适用此降级，见 no_input_device）。
        if blocking and no_input_device(ev):
            print("A7  SKIP  本环境无麦克风输入（CI），阻断项仅这类：", blocking)
        elif blocking:
            fails.append("A7 阻断性错误（演示当天会直接不可用）: %s" % blocking)
        elif any(e.startswith("error:") for e in ev):
            print("A7  NOTE  非阻断错误（假麦克风无声/联网服务）:",
                  [e for e in ev if e.startswith("error:")])

        # A6 无新增 console 错误（过滤掉离线降级探测那类网络错误）
        noise = ("ERR_CONNECTION_REFUSED", "Failed to load resource", "net::")
        real = [e for e in console_errors if not any(n in e for n in noise)]
        if real:
            fails.append("A6 console 错误 %d 条: %s" % (len(real), real[:3]))
        else:
            print("A6 PASS  无 console 错误（已过滤网络探测噪声 %d 条）" % len(console_errors))

        # A8/A9/A10：桩化退出态三腿（同一浏览器另开 context，不干扰上面的真机腿）
        fails.extend(await stub_legs(browser, URL))

        await browser.close()

    print()
    if fails:
        print("VOICE-FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("VOICE-PASS")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(selftest())
    raise SystemExit(asyncio.run(main()))
