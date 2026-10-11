# -*- coding: utf-8 -*-
"""心屿 · 语音通话判据（r116 新增）—— 盯「听得懂、能打断、不靠摄像头、出得快」四件事

用法：python _test/voice_call_check.py [url] [--selftest]
默认 url = http://127.0.0.1:8123 （Java 服务端直读 src/；也可指向 python -m http.server 8125）

为什么必须桩化（一手理由，不是图省事）：
  · 真机麦克风与真实大模型把「收句时机」和「首声延迟」变成两个不可复现的量 ⇒ 判据当天绿、
    下周绿不绿看网络和天气。本套件把**两个边界**桩掉：SpeechRecognition（由测试决定何时给出
    什么转写）与 ChatAgent.respond（由测试决定分片节奏与时刻）；被测对象是 r116 新写的
    **通话编排层本身**（voice-call.js），不是这两个边界。
  · 桩化必须有前置断言，否则「桩没生效却判通过」= 空断言（本仓 r98 为 A5 踩过一次，
    见 voice_check.py 的 a5_status 注释）。每条腿都先证桩被调用过，再下结论。
  · 朗读侧不整体替换 speechSynthesis：只 patch speak/cancel 做**记录 + 定时回调**，
    utterance 与 voice 对象仍是浏览器真的那些（把假 voice 赋给真 utterance 会当场抛，
    那样「音色选上了」这条就变成在测我自己的桩）。
  · getUserMedia 走「记录约束后拒绝」：既要拿到「有没有要过视频」的硬证据，又要顺带验
    「音频腿取不到时通话照常用」这条降级。真音频路径由浏览器实环境决定，本套件不谎称验过。

腿：
  U1 语义收句纯函数（半截话不答 / 完整句答 / 永不完整有界收口 / 分句切点）
  C1 入口存在且**真点得开**（浮层出现 —— 本仓两次同族缺陷：存在≠可达）
  C2 通话不请求摄像头（getUserMedia 全部约束 video 为空/假；没请求也算干净）
  C3 多种音色：目录 ≥4 档 + 选择持久化 + 该音色真进了 utterance（rate/pitch/lang 实测）
  C4 半句不答（先证假上游装好了，才谈得上「没答」是收句判据拦的）
  C5 整句才答 + 边生成边念第一句：首声时刻 < 末片到达时刻，且整句最终全念出来
  C6 摄像头关着能通话（读数如实带「摄像头未开启」）
  C7 摄像头开着也能通话（注入 FaceEngine 读数；真摄像头腿归 face_check.py，本腿验**互不依赖**）
  C8 全双工可打断 / C8b 半双工讲完再听（两条都过）
  C9 退出复位：结束通话后浏览器自派 end **不得**再重启识别（否则退出态把通话锁死）
  C10 全程零 pageerror
  C11 会话累计转写不重复收口（真机 results 留着旧句；桩按累计语义投才打得中这一类缺陷）

门面行自带档位（电池只留末条判定行，档位不上那一行 = 受理面上不存在）。
rc：0=PASS 1=FAIL 2=UNVERIFIED（浏览器起不来 / 页面打不开 / 桩未就位 —— 「没测到」绝不判绿）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_engine import launch  # noqa: E402  唯一 launch 实现（r96 立，走 sync API）

URL = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8123")

STUB = r"""
window.__vc = { utts: [], deltas: [], cancels: 0, gum: [], started: 0, stopped: 0,
                 srMade: 0, ev: [], llmCalls: 0, results: [], t0: 0, speakMs: 40, texts: [] };
(function () {
  var V = window.__vc;
  var now = function () { return performance.now(); };
  /* ── SpeechRecognition：整体替换。start/stop 计数 + 由测试投喂转写 ── */
  function SR() {
    var self = this;
    V.srMade += 1;
    this.lang = ""; this.continuous = false; this.interimResults = false; this.maxAlternatives = 1;
    var fire = function (name, arg) {
      V.ev.push(name);
      var h = self["on" + name];
      if (typeof h === "function") { try { h.call(self, arg || {}); } catch (e) { V.ev.push("throw:" + name + ":" + e.message); } }
    };
    this.start = function () { V.started += 1; fire("start"); };
    this.stop = function () { V.stopped += 1; setTimeout(function () { fire("end"); }, 20); };
    this.abort = this.stop;
  }
  window.SpeechRecognition = SR; window.webkitSpeechRecognition = SR;
  /* 编排层每轮只会挂一个 onresult ⇒ 用 defineProperty 把它接进共享槽，投喂才打得中 */
  Object.defineProperty(SR.prototype, "onresult", {
    configurable: true,
    get: function () { return this.__onr; },
    set: function (f) { this.__onr = f; SR.__sink = f; }
  });
  window.__vcSay = function (text, isFinal) {
    // 真机 results 是**会话级累计列表**，临时结果在原位更新、已定稿的句子不会消失。
    // 桩早先只投一条扁平结果，把「上一句被重新拼进下一句」这类缺陷整个藏住 ⇒ 按累计语义投，
    // 并让 C11 腿专门盯它。
    var L = V.results;
    if (L.length && !L[L.length - 1].isFinal) L.pop();        // 临时结果被自己的下一版覆盖
    L.push({ transcript: text, isFinal: !!isFinal, 0: { transcript: text, confidence: 0.9 }, length: 1 });
    var s = SR.__sink;
    if (s) s({ results: L });
  };
  window.__vcClearResults = function () { V.results = []; };

  /* ── speechSynthesis：只 patch speak/cancel，utterance/voice 保持真实对象 ── */
  if (window.SpeechSynthesis && window.SpeechSynthesis.prototype) {
    var P = window.SpeechSynthesis.prototype;
    P.speak = function (u) {
      V.utts.push({ text: u.text, rate: u.rate, pitch: u.pitch, lang: u.lang,
                    voice: u.voice ? String(u.voice.name) : "(默认)", at: V.t0 ? now() - V.t0 : 0 });
      var ms = V.speakMs;
      setTimeout(function () { if (u.onstart) { try { u.onstart(); } catch (e) {} } }, 5);
      setTimeout(function () { if (u.onend) { try { u.onend(); } catch (e) {} } }, ms);
    };
    P.cancel = function () { V.cancels += 1; };
  }
  /* ── getUserMedia：记录约束后拒绝（音频腿取不到时通话必须照常用）── */
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia = function (c) {
      V.gum.push(JSON.parse(JSON.stringify(c || {})));
      return Promise.reject(new Error("stub-denied"));
    };
  }
  /* ── ChatAgent.respond：可控节奏的流式假上游（只桩这一个边界，其余链路全真）── */
  var tail = { reply: "第一句先抱住你。第二句给你一个小方法。",
               chunks: ["第一句先抱住你。", "第一句先抱住你。第二句给你一个小方法。"] };
  window.__vcReply = tail.reply;
  window.VC_STUB_READY = true;
  window.__vcInstallFake = function () {
    window.ChatAgent.respond = function (text, onDelta) {
      V.llmCalls += 1;
      V.t0 = now();
      V.lastText = text;
      V.texts.push(text);
      return new Promise(function (res) {
        setTimeout(function () { if (onDelta) onDelta(tail.chunks[0]); V.deltas.push({ n: 1, at: now() - V.t0 }); }, 90);
        setTimeout(function () {
          if (onDelta) onDelta(tail.chunks[1]);
          V.deltas.push({ n: 2, at: now() - V.t0 });
          res({ reply: tail.reply, emotion: "sad", intensity: 0.7, mode: "model", path: "桩",
                latency: 180, streamed: true, lexAll: {}, emoSrc: "local", divergence: "unknown" });
        }, 300);
      });
    };
    window.ChatAgent.isOnline = function () { return true; };
  };
})();
"""


def wait_state(page, want, tries=60):
    s = "?"
    for _ in range(tries):
        s = page.evaluate("() => window.VoiceCall.inspect().state")
        if s == want:
            return True, s
        page.wait_for_timeout(50)
    return False, s


# ── 纯函数（可注入反例 ⇒ --selftest 打的是尺，不是运气）──────────────────
def camera_clean(gum_list):
    """通话期间一次视频设备都不许要。没请求也算干净（音频腿取不到不影响通话）。"""
    for c in gum_list or []:
        if c.get("video"):
            return False
    return True


def first_sound_before_stream_end(utt_ts, delta_ts):
    """「边生成边念第一句」的判据：首声必须早于**末片**到达；任一列为空一律不成立。"""
    if not utt_ts or not delta_ts:
        return False
    return min(utt_ts) < max(delta_ts)


def verdict(fails, legs, unit):
    """门面行：档位必须落在这一行本身，否则被电池折掉 = 没有读数。上限 110 字符。"""
    p = sum(1 for v in legs.values() if v == "PASS")
    return ("%s C腿=%d/%d U组=%d 浮层=%s" %
            ("VOICECALL-FAIL" if fails else "VOICECALL-PASS", p, len(legs), unit,
             "开" if legs.get("C1") == "PASS" else "未验"))


def selftest():
    """尺自己的反例：三条纯函数各配正例/反例，并做一次「摘掉守卫必须翻绿」的变异。"""
    bad = []
    cases_cam = [([], True, "没请求过音频也算干净"),
                 ([{"audio": True, "video": False}], True, "显式 video:false 干净"),
                 ([{"audio": True}], True, "只写 audio 也算干净"),
                 ([{"video": True}], False, "要视频必须判红"),
                 ([{"audio": True}, {"video": {"facingMode": "user"}}], False, "对象形态视频约束同样判红")]
    for g, want, why in cases_cam:
        if camera_clean(g) != want:
            bad.append("camera_clean %s（期望 %s）" % (why, want))
    keep = globals()["camera_clean"]
    globals()["camera_clean"] = lambda g: True                      # 变异：把尺关掉
    flipped = [camera_clean(g) for g, w, _ in cases_cam if not w]
    globals()["camera_clean"] = keep
    if not flipped or not all(flipped):
        bad.append("变异体没让反例翻绿 ⇒ camera_clean 这条腿在打不存在的靶子")
    if keep([{"video": True}]):
        bad.append("还原后同一反例没回判红 ⇒ 动的是期望值不是尺")

    cases_fs = [([], [1.0], False, "没出声不得判通过"),
                ([1.0], [], False, "没有流式末片不得判通过"),
                ([50.0], [90.0, 300.0], True, "首声早于末片 = 真边生成边念"),
                ([310.0], [90.0, 300.0], False, "憋到流完才开口 = 判红")]
    for u, d, want, why in cases_fs:
        if first_sound_before_stream_end(u, d) != want:
            bad.append("first_sound %s（期望 %s）" % (why, want))
    keep2 = globals()["first_sound_before_stream_end"]
    globals()["first_sound_before_stream_end"] = lambda u, d: bool(d)   # 变异：只查末片存在 = 空断言
    vac = globals()["first_sound_before_stream_end"]([], [1.0])
    globals()["first_sound_before_stream_end"] = keep2
    if vac is not True:
        bad.append("变异体没造出空断言 ⇒ 这条反例腿没有判别力")
    if keep2([], [1.0]):
        bad.append("还原后空读数仍算通过 ⇒ 尺已被改松")

    ok_line = verdict([], {"C1": "PASS", "C5": "PASS"}, 11)
    bad_line = verdict(["C5 出声不边生成"], {"C1": "PASS", "C5": "FAIL"}, 9)
    if "VOICECALL-PASS" not in ok_line or "C腿=2/2" not in ok_line or len(ok_line) > 110:
        bad.append("门面行缺档位或超电池截断线 110：%s" % ok_line)
    if "VOICECALL-FAIL" not in bad_line or "C腿=1/2" not in bad_line or len(bad_line) > 110:
        bad.append("FAIL 分支丢了同款字段：%s" % bad_line)
    if "C腿=0/0" not in verdict([], {}, 0):
        bad.append("空档位集被读成全过")

    if bad:
        print("VOICECALL-SELFTEST-FAIL: " + " ; ".join(bad))
        return 1
    print("VOICECALL-SELFTEST-PASS: %d 用例（camera_clean %d 条含变异翻绿+还原回红 / 首声时机 %d 条含空断言变异 / 门面行 3 条）"
          % (len(cases_cam) + len(cases_fs) + 6, len(cases_cam), len(cases_fs)))
    return 0


def unit_legs(page):
    """U1：语义收句与分句的纯函数组（确定性最高，先把尺钉死再看行为）。"""
    js = """() => {
      const U = window.VoiceCall._unit, o = [];
      const ck = (name, got, want) => o.push([name, String(got) === String(want), got, want]);
      ck("半截不算完整", U.semanticallyComplete("我今天"), false);
      ck("够长且非连接词收尾算完整", U.semanticallyComplete("我今天被导师骂了"), true);
      ck("以「然后」收尾不算完整", U.semanticallyComplete("我想一下然后"), false);
      ck("句末问号算完整", U.semanticallyComplete("真的吗？"), true);
      ck("完整句 700ms 停顿即收", U.shouldCommit("我今天被导师骂了", 700), "语义收句");
      ck("半截句 700ms 不收", U.shouldCommit("我想一下然后", 700), "");
      ck("半截句到 1900ms 有界收口", U.shouldCommit("我想一下然后", 2000), "停顿收口");
      ck("空文本不收", U.shouldCommit("", 3000), "");
      const c1 = U.cutSentences("第一句完了。第二句还挂着", 0);
      ck("分句切点", c1[0].length === 1 && c1[1] === 6, true);
      const c2 = U.cutSentences("没有标点的一句很长的话", 0);
      ck("无标点不误切", c2[0].length === 0, true);
      return o;
    }"""
    rows = page.evaluate(js)
    fails = []
    for name, ok, got, want in rows:
        if ok:
            print("U1 PASS  %s" % name)
        else:
            fails.append("U1 %s 期望 %r 实得 %r" % (name, want, got))
    return fails, len(rows)


def run_legs(page):
    """返回 (fails, legs)。每条腿先证前置，再下结论。"""
    f = []
    legs = {}

    def v():
        return page.evaluate("() => window.__vc")

    # C1 入口存在且真点得开
    btn = page.locator("#btn-call")
    if not btn.is_visible():
        legs["C1"] = "FAIL"
        return ["C1 #btn-call 不可见（入口被藏 = 通话功能等于没有）"], legs
    btn.click(timeout=5000)
    opened = False
    for _ in range(30):
        if not page.evaluate("() => document.querySelector('#call-layer').hidden"):
            opened = True
            break
        page.wait_for_timeout(50)
    ok_state, st = wait_state(page, "listening")
    d = v()
    if opened and ok_state and d["srMade"] >= 1 and d["started"] >= 1:
        legs["C1"] = "PASS"
        print("C1 PASS  点得开：浮层出现 state=%s srMade=%d started=%d" % (st, d["srMade"], d["started"]))
    else:
        legs["C1"] = "FAIL"
        return [("C1 点开后没进入通话态 opened=%s state=%s srMade=%d started=%d（存在≠可达，本仓两次同族）"
                 % (opened, st, d["srMade"], d["started"]))], legs

    # C2 通话不请求摄像头
    g = v()["gum"]
    if camera_clean(g):
        legs["C2"] = "PASS"
        print("C2 PASS  未请求摄像头（gUM 约束=%s）" % (json.dumps(g, ensure_ascii=False) if g else "无"))
    else:
        legs["C2"] = "FAIL"
        f.append("C2 通话请求了视频设备：%s" % g)

    # C6 摄像头关着时的状态读数
    face_txt = page.locator("#call-face").inner_text()
    if "摄像头未开启" in face_txt:
        legs["C6"] = "PASS"
        print("C6 PASS  摄像头关着照样通话，读数如实：%r" % face_txt)
    else:
        legs["C6"] = "FAIL"
        f.append("C6 摄像头关着但读数不说实话：%r" % face_txt)

    # C3 多种音色：目录 ≥4 + 选择持久化 + 真进 utterance
    opts = page.evaluate("() => Array.from(document.querySelector('#call-timbre').options).map(o => o.value)")
    if len(opts) < 4:
        legs["C3"] = "FAIL"
        f.append("C3 可选音色只有 %d 档（要求 ≥4 才谈得上「多种音色」）" % len(opts))
    else:
        pick = opts[1]
        page.select_option("#call-timbre", pick)
        saved = page.evaluate("() => localStorage.getItem('peiliao.calltimbre.v1')")
        page.evaluate("() => { window.__vc.utts = []; window.Voice.preview(); }")
        page.wait_for_timeout(300)
        u = v()["utts"]
        want = json.loads(saved) if saved else {}
        ok = bool(u) and u[0]["lang"] == "zh-CN" and abs(u[0]["rate"] - want.get("rate", -1)) < 1e-6 \
            and abs(u[0]["pitch"] - want.get("pitch", -1)) < 1e-6
        if ok:
            legs["C3"] = "PASS"
            print("C3 PASS  %d 档音色；选中 %s 已持久化并进了 utterance（rate=%s pitch=%s voice=%s）"
                  % (len(opts), pick, u[0]["rate"], u[0]["pitch"], u[0]["voice"]))
        else:
            legs["C3"] = "FAIL"
            f.append("C3 音色选择没落到发声上 saved=%s utts=%s" % (saved, u))

    # C4 半句不答（先装假上游，才分得清「没答」是收句拦的还是上游挂的）
    page.evaluate("() => window.__vcInstallFake()")
    page.evaluate("() => window.__vcSay('我今天', false)")
    page.wait_for_timeout(900)
    if v()["llmCalls"] == 0:
        legs["C4"] = "PASS"
        print("C4 PASS  半截话「我今天」停顿 900ms 未送模型（真听懂再答）")
    else:
        legs["C4"] = "FAIL"
        f.append("C4 半截话就被送去回答了（llmCalls=%d）⇒ 「完整理解语义」不成立" % v()["llmCalls"])

    # C5 整句才答 + 边生成边念第一句
    page.evaluate("() => { window.__vc.utts = []; window.__vc.deltas = []; window.__vc.t0 = performance.now(); }")
    page.evaluate("() => window.__vcSay('我今天被导师骂了', true)")
    got_s, st = wait_state(page, "speaking", 60)
    d = v()
    if d["llmCalls"] < 1:
        legs["C5"] = "FAIL"
        f.append("C5 前置缺失：完整句也没把模型叫起来（llmCalls=0）state=%s" % st)
    elif not d["utts"]:
        legs["C5"] = "FAIL"
        f.append("C5 没有出声（utts 空）state=%s" % st)
    elif not first_sound_before_stream_end([x["at"] for x in d["utts"]], [x["at"] for x in d["deltas"]]):
        legs["C5"] = "FAIL"
        f.append("C5 出声不「边生成边念」：首声=%.1fms 末片=%.1fms" % (d["utts"][0]["at"], d["deltas"][-1]["at"]))
    else:
        page.wait_for_timeout(300)
        d = v()
        joined = "".join([x["text"] for x in d["utts"]]).replace(" ", "")
        tail_norm = page.evaluate("() => window.__vcReply").replace(" ", "")
        if joined != tail_norm:
            legs["C5"] = "FAIL"
            f.append("C5 整句没念全：念出=%r 应有=%r" % (joined, tail_norm))
        else:
            legs["C5"] = "PASS"
            got_s2, _ = wait_state(page, "listening", 20)
            print("C5 PASS  首声 %.1fms < 末片 %.1fms，整句全念出（%d 次出声，念完自动回听=%s）"
                  % (d["utts"][0]["at"], d["deltas"][-1]["at"], len(d["utts"]), got_s2))

    # C8 全双工可打断（先把出声时长调到 1.5s，确保打断发生在「它还在说」的窗口里）
    page.evaluate("() => { window.__vc.speakMs = 1500; window.__vc.cancels = 0; window.__vc.utts = []; }")
    page.evaluate("() => window.__vcSay('今天有点累想早点睡', true)")
    got_sp, st = wait_state(page, "speaking", 60)
    if not got_sp:
        legs["C8"] = "FAIL"
        f.append("C8 前置缺失：新一轮没能进入出声态（state=%s），打断腿没靶子" % st)
    else:
        page.evaluate("() => { window.__vc.cancels = 0; }")
        if v()["cancels"] != 0:
            legs["C8"] = "FAIL"
            f.append("C8 前置缺失：cancels 清零没生效")
        else:
            page.evaluate("() => window.__vcSay('先别说了我想静静', true)")
            ok_i, st = wait_state(page, "listening", 40)
            c = v()["cancels"]
            if c >= 1 and ok_i:
                legs["C8"] = "PASS"
                print("C8 PASS  全双工：用户插话即闭嘴（cancels=%d state=%s）" % (c, st))
            else:
                legs["C8"] = "FAIL"
                f.append("C8 插话没打断：cancels=%d state=%s" % (c, st))

    # C8b 半双工：切档后它开口即停识别
    page.locator("#btn-call-duplex").click(timeout=5000)
    word = page.locator("#btn-call-duplex").inner_text()
    if "讲完再听" not in word:
        legs["C8b"] = "FAIL"
        f.append("C8b 双工切换按钮文案没翻面：%r" % word)
    else:
        page.evaluate("() => { window.__vc.stopped = 0; window.__vc.utts = []; window.__vc.speakMs = 1500; }")
        page.evaluate("() => window.__vcSay('今天过得怎么样', true)")
        got_h, st = wait_state(page, "speaking", 60)
        if not got_h:
            legs["C8b"] = "FAIL"
            f.append("C8b 前置缺失：半双工下没进入出声态（state=%s）" % st)
        else:
            page.wait_for_timeout(150)
            s = v()["stopped"]
            if s >= 1:
                legs["C8b"] = "PASS"
                print("C8b PASS  半双工：它开口即停识别（stopped=%d）" % s)
            else:
                legs["C8b"] = "FAIL"
                f.append("C8b 半双工没停识别（stopped=0）⇒ 会把自家念白当用户插话")
    page.evaluate("() => { window.__vc.speakMs = 40; }")
    page.locator("#btn-call-duplex").click(timeout=5000)

    # C7 摄像头开着也能通话（注入 FaceEngine 读数）
    page.evaluate("() => { window.FaceEngine = window.FaceEngine || {}; window.FaceEngine.last = function () { return {emotion: 'sad', intensity: 0.6}; }; window.VoiceCall._repaint(); }")
    page.wait_for_timeout(150)
    face_txt = page.locator("#call-face").inner_text()
    page.evaluate("() => { window.__vc.llmCalls = 0; window.__vcSay('现在摄像头开着也能聊', true); }")
    page.wait_for_timeout(1300)
    if "表情随聊已开启" not in face_txt:
        legs["C7"] = "FAIL"
        f.append("C7 摄像头开着但通话层读数没反映：%r" % face_txt)
    elif v()["llmCalls"] < 1:
        legs["C7"] = "FAIL"
        f.append("C7 摄像头开着时通话链路断了（llmCalls=0）")
    else:
        legs["C7"] = "PASS"
        print("C7 PASS  摄像头开着照旧通话（读数=%r llmCalls=%d）" % (face_txt, v()["llmCalls"]))

    # C11 会话累计转写不得把上一句重新拼进下一句（真机 results 会一直留着旧句）
    n_text_before = len(v()["texts"])
    page.evaluate("() => window.__vcSay('第一句已经收口了', true)")
    page.wait_for_timeout(1400)
    page.evaluate("() => window.__vcSay('第二句单独成句', true)")
    page.wait_for_timeout(1400)
    texts = v()["texts"]
    if len(texts) < n_text_before + 2:
        legs["C11"] = "FAIL"
        f.append("C11 前置缺失：两句只起了 %d 轮（应有 2 轮）⇒ 收口没跑起来，本腿无靶子"
                 % (len(texts) - n_text_before))
    elif texts[-1] != "第二句单独成句":
        legs["C11"] = "FAIL"
        f.append("C11 旧句被重拼：本轮送模型的是 %r（应只有「第二句单独成句」）" % texts[-1])
    else:
        legs["C11"] = "PASS"
        print("C11 PASS  收过口的旧句不再参与下一句（本轮送模型=%r）" % texts[-1])

    # C9 退出复位
    page.locator("#btn-call-end").click(timeout=5000)
    page.wait_for_timeout(250)
    before = v()["started"]
    hidden = page.evaluate("() => document.querySelector('#call-layer').hidden")
    st = page.evaluate("() => window.VoiceCall.inspect().state")
    # 先证「回调真被摘掉」，再看 start 计数有没有涨（否则 sink 已为 null，计数不涨是白断）
    sink_after_exit = page.evaluate("() => String(window.SpeechRecognition.__sink)")
    if "function" in sink_after_exit:
        legs["C9"] = "FAIL"
        f.append("C9 退出后 onresult 回调还在（sink=%s）⇒ 判红不给绿，防白断" % sink_after_exit[:60])
        return f, legs
    page.evaluate("() => { var s = window.SpeechRecognition.__sink; if (s) s({ results: [] }); }")
    page.wait_for_timeout(400)
    after = v()["started"]
    if not hidden or st != "idle":
        legs["C9"] = "FAIL"
        f.append("C9 结束通话没收回：hidden=%s state=%s" % (hidden, st))
    elif after > before:
        legs["C9"] = "FAIL"
        f.append("C9 退出后识别又被重启（started %d→%d）⇒ 没摘回调，会空转到刷新" % (before, after))
    else:
        legs["C9"] = "PASS"
        print("C9 PASS  退出复位：浮层收起 state=idle 且 end 事件不再重启识别（started 保持 %d）" % after)
    return f, legs


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("VOICECALL-UNVERIFIED playwright 不可用")
        return 2
    fails, legs, unit_n = [], {}, 0
    try:
        with sync_playwright() as p:
            browser, face = launch(p, args=["--autoplay-policy=no-user-gesture-required"],
                                   label="voice_call_check")
            ctx = browser.new_context(permissions=["microphone"])
            ctx.add_init_script(STUB)
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            try:
                page.goto(URL, wait_until="load", timeout=30000)
            except Exception as e:  # noqa: BLE001
                browser.close()
                print("VOICECALL-UNVERIFIED 页面打不开 %s（%s）—— 没测到不得判绿" % (URL, str(e)[:80]))
                return 2
            page.wait_for_timeout(1200)
            if not page.evaluate("() => !!window.VC_STUB_READY && !!window.VoiceCall"):
                browser.close()
                print("VOICECALL-UNVERIFIED 桩或 VoiceCall 模块未就位（build 面缺件）")
                return 2
            uf, unit_n = unit_legs(page)
            fails += uf
            lf, legs = run_legs(page)
            fails += lf
            if errs:
                fails.append("C10 未捕获异常逃逸到页面 %d 条: %s" % (len(errs), errs[:2]))
            else:
                print("C10 PASS  全程零 pageerror")
            print("引擎=%s" % (face,))
            browser.close()
    except Exception as e:  # noqa: BLE001
        print("VOICECALL-UNVERIFIED 浏览器不可用：%s" % str(e)[:140])
        return 2
    print()
    print(verdict(fails, legs, unit_n))
    for x in fails:
        print("  -", x)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
