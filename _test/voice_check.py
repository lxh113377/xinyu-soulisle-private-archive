# 心屿 · 语音输入（Web Speech API）真机实测  ——  L8
# 用法: python _test/voice_check.py [url]
#
# 思路：用系统 msedge（Playwright 内置 chromium 未下载）+ 假麦克风设备 + 自动授权，
#       在页面脚本执行前注入一层 SpeechRecognition 包装器，记录构造/start/stop 次数，
#       再观察按钮 DOM 的监听态（class=recording）与恢复态。
#       判据只看**真实发生过的事实**：API 存在吗？start 真被调用了吗？监听态出现过吗？能恢复吗？
import asyncio
import sys

from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8125/"

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
        if blocking:
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
    raise SystemExit(asyncio.run(main()))
