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
  C4 半句不答（先证假上游装好了，才分得清「没答」是收句拦的还是上游挂的）
  C5 整句才答 + 边生成边念第一句：首声时刻 < 末片到达时刻，且整句最终全念出来
  C6 摄像头关着能通话（读数如实带「摄像头未开启」）
  C7 摄像头开着也能通话（注入 FaceEngine 读数；真摄像头腿归 face_check.py，本腿验**互不依赖**）
  C8 全双工可打断 / C8b 半双工讲完再听（两条都过）
  C9 退出复位：结束通话后浏览器自派 end **不得**再重启识别（先证回调已摘，再看计数）
  C10 全程零 pageerror
  C11 会话累计转写不重复收口（真机 results 留着旧句；桩按累计语义投才打得中这一类缺陷）
  C12 采集链显式声明降噪/回声抑制/自动增益 + 能量门纯函数（噪声不许把话头吊着不收口）
  C13 合成引擎**根本不在**时整轮仍跑完并回到听态（字幕是唯一出口；有码无判据的兜底腿，07 卷139 登记）
  C14 长轮次稳定性：连打 8 轮不重建识别器、不重复 start、字幕封顶、轮轮都回听
      ⚠️ 本腿是**桩化**的结构稳定性，不等于真机连说 30 分钟；本机无真麦克风，后者只能人测。
  C15 本机神经语音引擎：默认态零探测（公网红线）+ 开关开时目录/路由/通话中切说话人三件齐
  C16 收句面回声准入（wb-echo-L0）：排水后念白回读不得被当用户输入提交（尾音窗+模糊判）；异文真话对照腿必须照常提交
  C17 跨轮回读（wb-echo-L1）：轮1念白在轮2之后回读必须被丢弃（老码单槽只保最近一条 ⇒ 先验红）
  C18 barge-in 能量突增判据（wb-echo-L1）：纯函数组（基线 2× / 300ms 内 ≥2 采样 / 无读数放行）+ 降级仍可打断
  C19 尾音窗边界（wb-echo-L1）：同一边界样本（dice≈0.500）窗内 0.45 严查丢弃 / 窗外 0.6 放行提交

函数切分（r116 收口轮 / r118 补四段）：loc_guard 的 ≤150 行/函数门把原来的 run_legs（219 行）拆成
  多段（开层/音色/整轮/双工/回声准入/回声L1/摄像头/采集链/无TTS/长轮次/退出/本机引擎），每段自带前置缺失即早退，结论仍汇进同一个 legs 字典。
  等态一律走 wait_state / wait_text 的**完成态轮询**，不留装饰性定长等待
  （timing_coupling 的 C1_HARD 棘轮只认「等完直接读一个确定值」这种形状）。

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
                 srMade: 0, ev: [], llmCalls: 0, results: [], t0: 0, speakMs: 40, texts: [],
                 ttsReqs: [], audioMade: 0, audioPlayed: 0, audioPaused: 0 };
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
    this.start = function () {
      // 真机语义：一次只能有一个会话，重复 start() 抛 InvalidStateError；
      // 会话结束后 results 作废（新会话从空列表开始）。桩不照这个形状，被测代码的
      // 「会话活着就别重启」与「旧句偏移」两条都测不到（本轮一手：桩允许重复 start
      //  ⇒ 每轮结束都换会话 ⇒ 送模型的文本被拼成一长串）。
      if (self.__on) { throw new Error("InvalidStateError: recognition already started"); }
      self.__on = true; V.started += 1; fire("start");
    };
    this.stop = function () {
      if (!self.__on) return;
      self.__on = false; V.stopped += 1;
      setTimeout(function () { V.results = []; fire("end"); }, 20);
    };
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
    // 并让 C11 腿专门盯它。每个元素本身是「备选数组 + .isFinal」，与被审代码的读法同形。
    var L = V.results;
    if (L.length && !L[L.length - 1].isFinal) L.pop();
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
  /* ── TTS「引擎根本不在」态（C13 用）：patch speak 只是把声音吃掉，hasTTS() 依然为真 ⇒
        那条「队列里的句子永不消费」的缺陷照样打不中。这里把构造器摘成 undefined，
        让被测对象的 hasTTS() 自己判 false —— 前置断言读的就是它。 ── */
  var Utt = window.SpeechSynthesisUtterance;
  window.__vcKillTTS = function () {
    try {
      Object.defineProperty(window, "SpeechSynthesisUtterance", { value: undefined, configurable: true });
    } catch (e) { return "define-fail:" + e.message; }
    return "killed";
  };
  window.__vcRestoreTTS = function () {
    try {
      Object.defineProperty(window, "SpeechSynthesisUtterance", { value: Utt, configurable: true, writable: true });
    } catch (e) { return "restore-fail:" + e.message; }
    return "restored";
  };
  /* ── 本机神经引擎 sidecar 桩（C15 用）：/health 与 /tts 由桩应答，其余 fetch 原样透传。
        探测本身由被测对象按 cfg.localTts 决定 —— 默认态一次都不发，这正是公网面的红线。
        Audio 桩按真机语义投：play() 起定时器后派发 onended，否则被测对象的
        「播完才排下一句」这条永远等不到，等于拿假桩测自己。 */
  var RF = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (u, opt) {
    var s = String(u);
    if (s.indexOf("/health") >= 0) { V.probeHits = (V.probeHits || 0) + 1; }
    if (s.indexOf("/health") < 0 && s.indexOf("/tts") < 0) {
      return RF ? RF(u, opt) : Promise.reject(new Error("no-fetch"));
    }
    if (s.indexOf("/health") >= 0) {
      V.healthHits = (V.healthHits || 0) + 1;
      return Promise.resolve({ ok: true, status: 200, json: function () {
        return Promise.resolve({ status: "UP", loaded: true, numSpeakers: 174,
                                 sampleRate: 22050, engine: "stub", error: "" }); } });
    }
    var b = {}; try { b = JSON.parse((opt && opt.body) || "{}"); } catch (e) {}
    V.ttsReqs.push({ text: b.text, sid: b.sid });
    return Promise.resolve({ ok: true, status: 200, blob: function () {
      return Promise.resolve(new Blob([new Uint8Array([82, 73, 70, 70])], { type: "audio/wav" })); } });
  };
  window.Audio = function (src) {
    var el = { src: src, onended: null, onerror: null, _t: 0,
      play: function () {
        V.audioPlayed += 1;
        el._t = setTimeout(function () { if (el.onended) { try { el.onended(); } catch (e) {} } }, V.speakMs);
        return Promise.resolve();
      },
      pause: function () { clearTimeout(el._t); V.audioPaused += 1; } };
    V.audioMade += 1;
    return el;
  };
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


def vc(page):
    """读桩的累计记录（一次求值，别在断言里散落着重复取）"""
    return page.evaluate("() => window.__vc")


def state(page):
    return page.evaluate("() => window.VoiceCall.inspect().state")


def wait_state(page, want, tries=60):
    s = "?"
    for _ in range(tries):
        s = state(page)
        if s == want:
            return True, s
        page.wait_for_timeout(50)
    return False, s


def wait_text(page, sel, needle, tries=40):
    """等「文本出现」这个完成态，而不是等一段装饰性定长（timing_coupling 的 C1_HARD 形状）"""
    txt = ""
    for _ in range(tries):
        txt = page.locator(sel).inner_text()
        if needle in txt:
            return True, txt
        page.wait_for_timeout(50)
    return False, txt


def wait_js(page, expr, tries=60):
    """等「页面表达式为真」这个完成态（本机引擎的探测是异步 fetch，定长等待会飘）"""
    for _ in range(tries):
        try:
            if page.evaluate(expr):
                return True
        except Exception:  # noqa: BLE001
            return False
        page.wait_for_timeout(50)
    return False


def wait_count(page, key, want, tries=60):
    """等「桩里的计数器到数」这个完成态（utts / texts / stopped 都用它）"""
    for _ in range(tries):
        v = vc(page)[key]
        n = len(v) if isinstance(v, list) else v
        if n >= want:
            return True
        page.wait_for_timeout(50)
    return False


def wait_join(page, want, tries=60):
    """等「念出来的拼接 == 整句回复」这个完成态（第二句在流末尾才入队，等状态会抢跑）"""
    joined = ""
    for _ in range(tries):
        joined = "".join([x["text"] for x in vc(page)["utts"]]).replace(" ", "")
        if joined == want:
            return True, joined
        page.wait_for_timeout(50)
    return False, joined


def wait_texts(page, want, tries=60):
    return wait_count(page, "texts", want, tries)


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


AUDIO_FLAGS = ("echoCancellation", "noiseSuppression", "autoGainControl")


def audio_chain_ok(gum_list):
    """采集链的降噪/回声抑制必须**写进约束**，不是靠浏览器默认。
    取最近一次请求（通话里只开一次，真重启也应以最新态为准）；audio 写成布尔 = 没声明 = 判红。"""
    if not gum_list:
        return False
    audio = (gum_list[-1] or {}).get("audio")
    if not isinstance(audio, dict):
        return False
    return all(audio.get(k) is True for k in AUDIO_FLAGS)


def verdict(fails, legs, unit):
    """门面行：档位必须落在这一行本身，否则被电池折掉 = 没有读数。上限 110 字符。"""
    p = sum(1 for v in legs.values() if v == "PASS")
    return ("%s C腿=%d/%d U组=%d 浮层=%s" %
            ("VOICECALL-FAIL" if fails else "VOICECALL-PASS", p, len(legs), unit,
             "开" if legs.get("C1") == "PASS" else "未验"))


def selftest():
    """尺自己的反例：四条纯函数各配正例/反例，并做一次「摘掉守卫必须翻绿」的变异。"""
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

    cases_audio = [([], False, "一次都没请求 = 没声明，不许读成通过"),
                   ([{"audio": True, "video": False}], False, "audio 写成布尔 = 吃浏览器默认 = 判红"),
                   ([{"audio": {"noiseSuppression": True}}], False, "只声明一面旗不算声明"),
                   ([{"audio": {"echoCancellation": True, "noiseSuppression": True,
                                "autoGainControl": True}}], True, "三面旗齐 = 采集链真被声明"),
                   ([{"audio": {"echoCancellation": 1, "noiseSuppression": True,
                                "autoGainControl": True}}], False, "1 不是 true，按未声明判红")]
    for g, want, why in cases_audio:
        if audio_chain_ok(g) != want:
            bad.append("audio_chain_ok %s（期望 %s）" % (why, want))
    keep3 = globals()["audio_chain_ok"]
    globals()["audio_chain_ok"] = lambda g: True                     # 变异：把尺整个关掉
    vac_a = [audio_chain_ok(g) for g, w, _ in cases_audio if not w]
    globals()["audio_chain_ok"] = keep3
    if not vac_a or not all(vac_a):
        bad.append("变异体没让 audio_chain_ok 的反例翻绿 ⇒ 这条腿在打不存在的靶子")
    if keep3([{"audio": True}]) or keep3([]):
        bad.append("还原后「布尔 audio」或「一次没请求」仍算通过 ⇒ 动的是期望值不是尺")

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
    print("VOICECALL-SELFTEST-PASS: %d 用例（camera_clean %d 条含变异翻绿+还原回红 / audio_chain_ok %d 条含变异翻绿+还原回红 / 首声时机 %d 条含空断言变异 / 门面行 3 条）"
          % (len(cases_cam) + len(cases_audio) + len(cases_fs) + 6, len(cases_cam),
             len(cases_audio), len(cases_fs)))
    return 0


UNIT_JS = """() => {
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


def unit_legs(page):
    """U1：语义收句与分句的纯函数组（确定性最高，先把尺钉死再看行为）。"""
    rows = page.evaluate(UNIT_JS)
    fails = []
    for name, ok, got, want in rows:
        if ok:
            print("U1 PASS  %s" % name)
        else:
            fails.append("U1 %s 期望 %r 实得 %r" % (name, want, got))
    return fails, len(rows)


# ── 行为腿：按段切分（loc_guard ≤150 行/函数），结论统一汇进 legs ──────────
def legs_open(page, f, legs):
    """C1 真点得开 / C2 不请求摄像头 / C6 摄像头关着的读数。返回 False = 后续腿无靶子。"""
    btn = page.locator("#btn-call")
    if not btn.is_visible():
        legs["C1"] = "FAIL"
        f.append("C1 #btn-call 不可见（入口被藏 = 通话功能等于没有）")
        return False
    btn.click(timeout=5000)
    ok_state, st = wait_state(page, "listening")
    d = vc(page)
    opened = not page.evaluate("() => document.querySelector('#call-layer').hidden")
    if opened and ok_state and d["srMade"] >= 1 and d["started"] >= 1:
        legs["C1"] = "PASS"
        print("C1 PASS  点得开：浮层出现 state=%s srMade=%d started=%d" % (st, d["srMade"], d["started"]))
    else:
        legs["C1"] = "FAIL"
        f.append("C1 点开后没进入通话态 opened=%s state=%s srMade=%d started=%d（存在≠可达，本仓两次同族）"
                 % (opened, st, d["srMade"], d["started"]))
        return False
    g = d["gum"]
    if camera_clean(g):
        legs["C2"] = "PASS"
        print("C2 PASS  未请求摄像头（gUM 约束=%s）" % (json.dumps(g, ensure_ascii=False) if g else "无"))
    else:
        legs["C2"] = "FAIL"
        f.append("C2 通话请求了视频设备：%s" % g)
    ok_face, face_txt = wait_text(page, "#call-face", "摄像头未开启")
    if ok_face:
        legs["C6"] = "PASS"
        print("C6 PASS  摄像头关着照样通话，读数如实：%r" % face_txt)
    else:
        legs["C6"] = "FAIL"
        f.append("C6 摄像头关着但读数不说实话：%r" % face_txt)
    return True


def legs_timbre(page, f, legs):
    """C3 多种音色：目录 ≥4 档 + 选择持久化 + 真进了 utterance 的 rate/pitch/lang。"""
    opts = page.evaluate("() => Array.from(document.querySelector('#call-timbre').options).map(o => o.value)")
    if len(opts) < 4:
        legs["C3"] = "FAIL"
        f.append("C3 可选音色只有 %d 档（要求 ≥4 才谈得上「多种音色」）" % len(opts))
        return
    pick = opts[1]
    page.select_option("#call-timbre", pick)
    saved = page.evaluate("() => localStorage.getItem('peiliao.calltimbre.v1')")
    page.evaluate("() => { window.__vc.utts = []; window.Voice.preview(); }")
    got = wait_count(page, "utts", 1)              # 等「试听真的开口」这个完成态
    u = vc(page)["utts"]
    want = json.loads(saved) if saved else {}
    ok = bool(u) and u[0]["lang"] == "zh-CN" and abs(u[0]["rate"] - want.get("rate", -1)) < 1e-6 \
        and abs(u[0]["pitch"] - want.get("pitch", -1)) < 1e-6
    if ok:
        legs["C3"] = "PASS"
        print("C3 PASS  %d 档音色；选中 %s 已持久化并进了 utterance（rate=%s pitch=%s voice=%s）"
              % (len(opts), pick, u[0]["rate"], u[0]["pitch"], u[0]["voice"]))
    else:
        legs["C3"] = "FAIL"
        f.append("C3 音色选择没落到发声上 saved=%s utts=%s got=%s" % (saved, u, got))


def legs_turn(page, f, legs):
    """C4 半句不答 / C5 整句才答 + 边生成边念第一句 / C11 旧句不重拼。"""
    page.evaluate("() => window.__vcInstallFake()")
    page.evaluate("() => window.__vcSay('我今天', false)")
    # C4 是「确认没发生」：观察窗就是判据本身（无完成态可等），取 3×SILENCE_MS 的界
    page.wait_for_timeout(900)
    if vc(page)["llmCalls"] == 0:
        legs["C4"] = "PASS"
        print("C4 PASS  半截话「我今天」停顿 900ms 未送模型（真听懂再答）")
    else:
        legs["C4"] = "FAIL"
        f.append("C4 半截话就被送去回答了（llmCalls=%d）⇒ 「完整理解语义」不成立" % vc(page)["llmCalls"])

    page.evaluate("() => { window.__vc.utts = []; window.__vc.deltas = []; window.__vc.t0 = performance.now(); }")
    n0 = len(vc(page)["texts"])
    page.evaluate("() => window.__vcSay('我今天被导师骂了', true)")
    # 先等「第一声真的出口」这个完成态：假上游在 respond 被调那一刻就记 texts，
    # 拿 texts 当"出声了"的凭据会抢在 90ms 首片之前读空（本轮一手实测踩过）。
    wait_count(page, "utts", 1)
    d = vc(page)
    if d["llmCalls"] <= n0:
        legs["C5"] = "FAIL"
        f.append("C5 前置缺失：完整句没把模型叫起来（llmCalls=%d 应有>%d）state=%s" % (d["llmCalls"], n0, state(page)))
        return
    if not d["utts"]:
        legs["C5"] = "FAIL"
        f.append("C5 没有出声（utts 空）state=%s" % state(page))
        return
    ok_turn = wait_texts(page, n0 + 1)          # 整轮 resolve（两片都到）后才谈得上首声早于末片
    d = vc(page)
    if not ok_turn:
        legs["C5"] = "FAIL"
        f.append("C5 前置缺失：这一轮没跑完（texts=%d 应有>%d）" % (len(d["texts"]), n0))
        return
    if not first_sound_before_stream_end([x["at"] for x in d["utts"]], [x["at"] for x in d["deltas"]]):
        legs["C5"] = "FAIL"
        f.append("C5 出声不「边生成边念」：首声=%.1fms 末片=%.1fms" % (d["utts"][0]["at"], d["deltas"][-1]["at"]))
        return
    tail_norm = page.evaluate("() => window.__vcReply").replace(" ", "")
    ok_join, joined = wait_join(page, tail_norm)      # 第二句在流末尾才入队 ⇒ 等拼接而不是等状态
    back, _ = wait_state(page, "listening", 60)       # 念完自动回听
    if not ok_join:
        legs["C5"] = "FAIL"
        f.append("C5 整句没念全：念出=%r 应有=%r" % (joined, tail_norm))
    else:
        legs["C5"] = "PASS"
        d2 = vc(page)                                  # 出声次数要按念全之后的读数印，别拿旧快照
        print("C5 PASS  首声 %.1fms < 末片 %.1fms，整句全念出（%d 次出声，念完自动回听=%s）"
              % (d["utts"][0]["at"], d["deltas"][-1]["at"], len(d2["utts"]), back))

    # C11 真机 results 是会话级累计列表 ⇒ 收过口的旧句不得再拼进下一句
    before = len(d["texts"])
    page.evaluate("() => window.__vcSay('第一句已经收口了', true)")
    if not wait_texts(page, before + 1):
        legs["C11"] = "FAIL"
        f.append("C11 前置缺失：第一句没起轮（texts 停在 %d）⇒ 本腿无靶子" % before)
        return
    page.evaluate("() => window.__vcSay('第二句单独成句', true)")
    ok2 = wait_texts(page, before + 2)
    texts = vc(page)["texts"]
    if not ok2:
        legs["C11"] = "FAIL"
        f.append("C11 前置缺失：第二句没起轮（texts=%s）" % texts)
    elif texts[-1] != "第二句单独成句":
        legs["C11"] = "FAIL"
        f.append("C11 旧句被重拼：本轮送模型的是 %r（应只有「第二句单独成句」）" % texts[-1])
    else:
        legs["C11"] = "PASS"
        print("C11 PASS  收过口的旧句不再参与下一句（本轮送模型=%r）" % texts[-1])


def legs_duplex(page, f, legs):
    """C8 全双工可打断 / C8b 半双工讲完再听（两条都要过）。"""
    # 把出声时长撑到 1.5s，保证「打断」发生在它真的还在说的时候（否则这条腿在打空靶）
    page.evaluate("() => { window.__vc.speakMs = 1500; window.__vc.cancels = 0; window.__vc.utts = []; }")
    page.evaluate("() => window.__vcSay('今天有点累想早点睡', true)")
    got_sp, st = wait_state(page, "speaking", 60)
    if not got_sp:
        legs["C8"] = "FAIL"
        f.append("C8 前置缺失：新一轮没能进入出声态（state=%s），打断腿没靶子" % st)
    else:
        page.evaluate("() => { window.__vc.cancels = 0; }")
        if vc(page)["cancels"] != 0:
            legs["C8"] = "FAIL"
            f.append("C8 前置缺失：cancels 清零没生效")
        else:
            page.evaluate("() => window.__vcSay('先别说了我想静静', true)")
            ok_i, st = wait_state(page, "listening", 40)
            c = vc(page)["cancels"]
            if c >= 1 and ok_i:
                legs["C8"] = "PASS"
                print("C8 PASS  全双工：用户插话即闭嘴（cancels=%d state=%s）" % (c, st))
            else:
                legs["C8"] = "FAIL"
                f.append("C8 插话没打断：cancels=%d state=%s" % (c, st))

    page.locator("#btn-call-duplex").click(timeout=5000)
    ok_half, word = wait_text(page, "#btn-call-duplex", "讲完再听")
    if not ok_half:
        legs["C8b"] = "FAIL"
        f.append("C8b 双工切换按钮文案没翻面：%r" % word)
    else:
        page.evaluate("() => { window.__vc.stopped = 0; window.__vc.utts = []; window.__vc.speakMs = 1500; }")
        page.evaluate("() => window.__vcSay('今天过得怎么样', true)")
        got_h, st = wait_state(page, "speaking", 60)
        if not got_h:
            legs["C8b"] = "FAIL"
            f.append("C8b 前置缺失：半双工下没进入出声态（state=%s）" % st)
        elif wait_count(page, "stopped", 1):
            legs["C8b"] = "PASS"
            print("C8b PASS  半双工：它开口即停识别（stopped=%d）" % vc(page)["stopped"])
        else:
            legs["C8b"] = "FAIL"
            f.append("C8b 半双工没停识别（stopped=0）⇒ 会把自家念白当用户插话")
    page.evaluate("() => { window.__vc.speakMs = 40; }")
    page.locator("#btn-call-duplex").click(timeout=5000)


def legs_echo_admit(page, f, legs):
    """C16 收句面回声准入（wb-echo-L0）：排水后把「刚念过的念白」回读投给 ASR —— 正确行为是
    丢弃（不写 pending、不起新一轮）；再投异文真话作对照腿（必须照常提交）。"""
    ok_l, st0 = wait_state(page, "listening", 60)
    if not ok_l:
        legs["C16"] = "FAIL"
        f.append("C16 前置缺失：没在听态（state=%s），准入腿没靶子" % st0)
        return
    page.evaluate("() => { window.__vc.speakMs = 400; window.__vc.cancels = 0; }")
    page.evaluate("() => window.__vcSay('今天有点累想早点睡', true)")
    ok_sp, st = wait_state(page, "speaking", 80)
    ok_ls, st2 = wait_state(page, "listening", 80)
    if not ok_sp or not ok_ls:
        legs["C16"] = "FAIL"
        f.append("C16 前置缺失：一轮没走完（speaking=%s listening=%s）" % (st, st2))
        page.evaluate("() => { window.__vc.speakMs = 40; }")
        return
    n0 = len(vc(page)["texts"])     # 基线在 setup 轮提交之后取：此后条数再涨才是回声污染（wb-echo-L0 修的就是它）
    # 上半段：排水后立刻回读念白（与回复逐字相同）——老码此处 pending 被污染，620ms 后误提交
    page.evaluate("() => window.__vcSay('第一句先抱住你。第二句给你一个小方法。', true)")
    page.wait_for_timeout(1200)
    n1 = len(vc(page)["texts"])
    pend = page.evaluate("() => window.VoiceCall.inspect().pending")
    ok_back, st3 = wait_state(page, "listening", 80)
    # 下半段：异文真话——必须照常提交（证明上半段不是「反正都不收」的空靶）
    ok_ok = False
    if ok_back:
        n2 = len(vc(page)["texts"])
        page.evaluate("() => window.__vcSay('我其实想聊聊工作上的事', true)")
        ok_ok = wait_texts(page, n2 + 1)
    page.evaluate("() => { window.__vc.speakMs = 40; }")
    if n1 != n0 or pend:
        legs["C16"] = "FAIL"
        f.append("C16 念白回声被当用户输入：texts %d→%d pending=%r ⇒ 自触发管道未堵" % (n0, n1, pend))
    elif not ok_ok:
        legs["C16"] = "FAIL"
        f.append("C16 对照腿失效：异文真话没被提交（texts 停在 %d，state=%s）⇒ 上半段可能是空断言"
                 % (len(vc(page)["texts"]), st3))
    else:
        legs["C16"] = "PASS"
        print("C16 PASS  排水后念白回读被丢弃（pending 空、零新轮次）；异文真话照常提交")
    wait_state(page, "listening", 80)


def _leg_echo_cross(page, f, legs):
    """C17 跨轮回读（wb-echo-L1）：轮1念白在轮2之后回读 —— 老码单槽只保最近一条，此路必漏。"""
    ok_l, st = wait_state(page, "listening", 60)
    if not ok_l:
        legs["C17"] = "FAIL"
        f.append("C17 前置缺失：没在听态（state=%s）" % st)
        return
    page.evaluate("""() => {
      window.__vc1n = 0;
      window.ChatAgent.respond = function (text, onDelta) {
        window.__vc.llmCalls += 1; window.__vc.texts.push(text); window.__vc1n += 1;
        const rep = window.__vc1n === 1 ? "今晚的月色真温柔。" : "热水已经帮你续上啦。";
        if (onDelta) onDelta(rep);
        return Promise.resolve({ reply: rep, mode: "model" });
      };
    }""")
    page.evaluate("() => { window.__vc.speakMs = 300; }")
    n0 = len(vc(page)["texts"])
    page.evaluate("() => window.__vcSay('先说第一件事', true)")
    ok1 = wait_texts(page, n0 + 1)
    _, st1 = wait_state(page, "listening", 80)
    n1 = len(vc(page)["texts"])
    page.evaluate("() => window.__vcSay('再补第二件事', true)")
    ok2 = wait_texts(page, n1 + 1)
    _, st2 = wait_state(page, "listening", 80)
    if not (ok1 and ok2 and st1 == "listening" and st2 == "listening"):
        legs["C17"] = "FAIL"
        f.append("C17 前置缺失：两轮没走完（ok=%s/%s st=%s/%s）" % (ok1, ok2, st1, st2))
        return
    n2 = len(vc(page)["texts"])
    page.evaluate("() => window.__vcSay('今晚的月色真温柔。', true)")   # 轮1念白的迟到回读
    page.wait_for_timeout(1300)
    n3 = len(vc(page)["texts"])
    pend = page.evaluate("() => window.VoiceCall.inspect().pending")
    _, st3 = wait_state(page, "listening", 80)
    if n3 == n2 and not pend and st3 == "listening":
        legs["C17"] = "PASS"
        print("C17 PASS  跨轮回读被丢弃（轮1念白在轮2后回读：texts 停 %d、pending 空）" % n2)
    else:
        legs["C17"] = "FAIL"
        f.append("C17 跨轮回读漏网：texts %d→%d pending=%r（单槽只保最近一条）" % (n2, n3, pend))


BUMP_JS = """() => {
  const U = window.VoiceCall._unit, o = [];
  const ck = (name, got, want) => o.push([name, String(got) === String(want), got, want]);
  if (typeof U.bumpOkFrom !== "function") return [["bumpOkFrom 缺失（老码）", false, "undefined", "function"]];
  const mk = (a) => a.map((p) => ({ t: p[0], v: p[1] }));
  ck("无历史=放行（降级）", U.bumpOkFrom([], 10000), true);
  ck("样本不足=放行", U.bumpOkFrom(mk([[9800, 0.02]]), 10000), true);
  ck("平铺基线上无突增=不放行", U.bumpOkFrom(mk([[8400,0.02],[8800,0.02],[9200,0.02],[9600,0.02],[9800,0.02],[9900,0.02],[9950,0.02]]), 10000), false);
  ck("低基线人声过噪声地板=放行", U.bumpOkFrom(mk([[8400,0.002],[8800,0.002],[9200,0.002],[9600,0.002],[9800,0.02],[9900,0.025]]), 10000), true);
  ck("基线2×且300ms内≥2采样=放行", U.bumpOkFrom(mk([[8400,0.02],[8800,0.02],[9200,0.02],[9600,0.02],[9800,0.06],[9900,0.08],[9950,0.07]]), 10000), true);
  ck("不到2×=不放行", U.bumpOkFrom(mk([[8400,0.02],[8800,0.02],[9200,0.02],[9600,0.02],[9800,0.035],[9900,0.035],[9950,0.035]]), 10000), false);
  return o;
}"""


def _leg_barge_energy(page, f, legs):
    """C18 barge-in 能量突增判据（wb-echo-L1）：纯函数组 + 无读数降级路径仍可打断。"""
    rows = page.evaluate(BUMP_JS)
    bad = [r for r in rows if not r[1]]
    page.evaluate("() => { window.__vc.speakMs = 1200; window.__vc.cancels = 0; }")
    page.evaluate("() => window.__vcSay('能量判据这条先起一轮', true)")
    got_sp, st = wait_state(page, "speaking", 80)
    integ, why = False, "没能进入出声态（state=%s）" % st
    if got_sp:
        page.evaluate("() => window.__vcSay('我插一句打断试试', true)")
        ok_i, st2 = wait_state(page, "listening", 60)
        integ = ok_i and vc(page)["cancels"] >= 1
        why = "cancels=%d state=%s" % (vc(page)["cancels"], st2)
    if bad:
        legs["C18"] = "FAIL"
        f.append("C18 能量判据不符: %s" % [[r[0], r[2], r[3]] for r in bad])
    elif not integ:
        legs["C18"] = "FAIL"
        f.append("C18 降级路径失效：无能量读数时打断不再生效（%s）⇒ 宁漏勿误被做成了宁可误伤" % why)
    else:
        legs["C18"] = "PASS"
        print("C18 PASS  能量判据 %d 例（含降级/边界）；桩环境无读数下打断仍生效（%s）" % (len(rows), why))


def _leg_tail_window(page, f, legs):
    """C19 尾音窗边界（wb-echo-L1）：同一边界样本，窗内（0.45）严查丢弃 / 窗外（0.6）放行提交。"""
    spoken = "我今天心情还不错呢"
    probe = "今天心情不太好"
    ok_l, st = wait_state(page, "listening", 60)
    if not ok_l:
        legs["C19"] = "FAIL"
        f.append("C19 前置缺失：没在听态（state=%s）" % st)
        return
    page.evaluate("""(rep) => {
      window.ChatAgent.respond = function (text, onDelta) {
        window.__vc.llmCalls += 1; window.__vc.texts.push(text);
        if (onDelta) onDelta(rep);
        return Promise.resolve({ reply: rep, mode: "model" });
      };
    }""", spoken + "。")
    page.evaluate("() => { window.__vc.speakMs = 300; window.__vc.utts = []; }")
    n0 = len(vc(page)["texts"])
    page.evaluate("() => window.__vcSay('先听我完整说一句', true)")
    ok1 = wait_texts(page, n0 + 1)
    _, st1 = wait_state(page, "listening", 80)
    joined = "".join([x["text"] for x in vc(page)["utts"]]).replace(" ", "")
    if not (ok1 and st1 == "listening" and spoken in joined):
        legs["C19"] = "FAIL"
        f.append("C19 前置缺失：样本轮没走完或没念出（ok=%s st=%s joined=%r）" % (ok1, st1, joined[:60]))
        return
    n1 = len(vc(page)["texts"])
    page.evaluate("(t) => window.__vcSay(t, true)", probe + "。")
    page.wait_for_timeout(1300)
    n2 = len(vc(page)["texts"])
    pend = page.evaluate("() => window.VoiceCall.inspect().pending")
    _, st2 = wait_state(page, "listening", 80)
    ok_ok = False
    if n2 == n1 and not pend and st2 == "listening":
        n3 = len(vc(page)["texts"])
        page.evaluate("(t) => window.__vcSay(t, true)", probe + "。")
        ok_ok = wait_texts(page, n3 + 1)
    if n2 != n1 or pend:
        legs["C19"] = "FAIL"
        f.append("C19 窗内边界回读没被严查丢弃：texts %d→%d pending=%r" % (n1, n2, pend))
    elif not ok_ok:
        legs["C19"] = "FAIL"
        f.append("C19 窗外放行失败：同一样本过窗后仍被拦或没提交（texts 停 %d）⇒ 软窗退化成硬拦" % len(vc(page)["texts"]))
    else:
        legs["C19"] = "PASS"
        print("C19 PASS  边界样本（dice≈0.500）：窗内 0.45 严查丢弃 / 窗外 0.6 放行提交")


def legs_echo_l1(page, f, legs):
    """C17-C19（wb-echo-L1）：跨轮回读 / 打断能量判据 / 尾音窗边界；收尾复位假上游与语速。"""
    _leg_echo_cross(page, f, legs)
    _leg_barge_energy(page, f, legs)
    _leg_tail_window(page, f, legs)
    page.evaluate("() => { window.__vc.speakMs = 40; window.__vcInstallFake(); }")


def legs_camera(page, f, legs):
    """C7 摄像头开着也能通话（注入 FaceEngine 读数；真摄像头腿归 face_check.py）。"""
    page.evaluate("() => { window.FaceEngine = window.FaceEngine || {}; window.FaceEngine.last = function () { return {emotion: 'sad', intensity: 0.6}; }; window.VoiceCall._repaint(); }")
    ok_face, face_txt = wait_text(page, "#call-face", "表情随聊已开启")
    n0 = len(vc(page)["texts"])
    page.evaluate("() => window.__vcSay('现在摄像头开着也能聊', true)")
    ok_turn = wait_texts(page, n0 + 1)
    if not ok_face:
        legs["C7"] = "FAIL"
        f.append("C7 摄像头开着但通话层读数没反映：%r" % face_txt)
    elif not ok_turn:
        legs["C7"] = "FAIL"
        f.append("C7 摄像头开着时通话链路断了（送模型 0 轮）")
    else:
        legs["C7"] = "PASS"
        print("C7 PASS  摄像头开着照旧通话（读数=%r 送模型=%r）" % (face_txt, vc(page)["texts"][-1]))


GATE_JS = """() => {
  const U = window.VoiceCall._unit, o = [];
  const ck = (name, got, want) => o.push([name, String(got) === String(want), got, want]);
  ck("取不到能量读数就放行（无权限/桩）", U.gateOpen(null), true);
  ck("低于门限不续命", U.gateOpen(0.005), false);
  ck("高于门限放行", U.gateOpen(0.05), true);
  ck("0 是纯静音，同样不许当话头", U.gateOpen(0), false);
  return o;
}"""


def legs_noise(page, f, legs):
    """C12 采集链显式声明降噪 + 能量门纯函数（噪声不许把话头一直吊着）。"""
    d = vc(page)
    if not audio_chain_ok(d["gum"]):
        legs["C12"] = "FAIL"
        f.append("C12 采集约束没显式声明 echoCancellation/noiseSuppression/autoGainControl（最近一次=%s）"
                 "⇒ 「有降噪」只是浏览器默认，不能算实现" %
                 json.dumps(d["gum"][-1] if d["gum"] else {}, ensure_ascii=False))
        return
    rows = page.evaluate(GATE_JS)
    bad = [r for r in rows if not r[1]]
    if bad:
        legs["C12"] = "FAIL"
        f.append("C12 能量门判据不符: %s" % bad)
        return
    legs["C12"] = "PASS"
    print("C12 PASS  采集链三面旗齐 + 能量门 %d 例（无读数不拦 / 低能量不续命）；"
          "Web Speech 内部采集 JS 管不到，此项只声明到音量计这一路" % len(rows))


def last_ai_line(page):
    return page.evaluate(
        "() => { const l = document.querySelectorAll('#call-captions .call-line.ai');"
        " return l.length ? (l[l.length-1].querySelector('.call-line-text') || {}).textContent || '' : ''; }")


def legs_no_tts(page, f, legs):
    """C13 合成引擎根本不在时，通话必须跑完整轮并回听（字幕是唯一出口）。"""
    if page.evaluate("() => window.__vcKillTTS()") != "killed":
        legs["C13"] = "FAIL"
        f.append("C13 前置不成立：TTS 摘不掉，本腿无靶子（不是通过）")
        return
    if page.evaluate("() => window.Voice.ttsReady()"):
        legs["C13"] = "FAIL"
        f.append("C13 前置不成立：摘掉构造器后 ttsReady 仍为真 ⇒ 被测对象的能力探测没在跑")
        return
    n0 = len(vc(page)["texts"])
    page.evaluate("() => { window.__vc.utts = []; }")
    page.evaluate("() => window.__vcSay('这把椅子好像有点晃', true)")
    ok_turn = wait_texts(page, n0 + 1)
    back, st = wait_state(page, "listening", 40)
    ai_txt = last_ai_line(page)
    heard = len(vc(page)["utts"])
    page.evaluate("() => window.__vcRestoreTTS()")
    if not ok_turn:
        legs["C13"] = "FAIL"
        f.append("C13 没有合成引擎时整轮没跑完（送模型停在 %d）" % len(vc(page)["texts"]))
    elif heard:
        legs["C13"] = "FAIL"
        f.append("C13 引擎已摘却仍有 %d 次出声 ⇒ 桩没生效，本腿白跑" % heard)
    elif not back:
        legs["C13"] = "FAIL"
        f.append("C13 无 TTS 时卡在 %s 不回听 ⇒ 队列留了永不消费的项，通话就此哑掉" % st)
    elif page.evaluate("() => window.__vcReply") not in ai_txt:
        legs["C13"] = "FAIL"
        f.append("C13 无 TTS 且字幕没兜住回复：%r" % ai_txt[:60])
    else:
        legs["C13"] = "PASS"
        print("C13 PASS  无合成引擎：整轮跑完、0 次出声、字幕兜住、%s 回听态" % st)


def legs_marathon(page, f, legs):
    """C14 长轮次稳定性：连打 8 轮不许漏定时器 / 重建识别器 / 字幕爆量 / 轮次退化。"""
    n0 = len(vc(page)["texts"])
    made0, start0 = vc(page)["srMade"], vc(page)["started"]
    stuck = ""
    for i in range(8):
        before = len(vc(page)["texts"])
        page.evaluate("(t) => window.__vcSay('第' + t + '轮我想再确认一件事', true)", i + 1)
        if not wait_texts(page, before + 1):
            stuck = "第 %d 轮没起轮（texts 停在 %d）" % (i + 1, len(vc(page)["texts"]))
            break
        ok_back, st = wait_state(page, "listening", 40)
        if not ok_back:
            stuck = "第 %d 轮没回到听态（state=%s）" % (i + 1, st)
            break
    d = vc(page)
    lines = page.evaluate("() => window.VoiceCall.inspect().lines")
    done = len(d["texts"]) - n0
    if stuck:
        legs["C14"] = "FAIL"
        f.append("C14 长轮次中途退化：%s" % stuck)
    elif done < 8:
        legs["C14"] = "FAIL"
        f.append("C14 8 轮只跑完 %d 轮" % done)
    elif d["srMade"] != made0:
        legs["C14"] = "FAIL"
        f.append("C14 识别器被重建（srMade %d→%d）⇒ 每轮换会话，长时间必累积泄漏" % (made0, d["srMade"]))
    elif d["started"] > start0:
        legs["C14"] = "FAIL"
        f.append("C14 全双工下识别被重复 start（%d→%d）⇒ 30 分钟会空转到页面崩溃" % (start0, d["started"]))
    elif lines > 12:
        legs["C14"] = "FAIL"
        f.append("C14 字幕没封顶（%d 行 > 12）⇒ DOM 无限涨" % lines)
    else:
        legs["C14"] = "PASS"
        print("C14 PASS  连打 8 轮全跑完；srMade=%d started=%d 字幕=%d 行封顶（真机 30 分钟归人测，本机无真麦）"
              % (d["srMade"], d["started"], lines))


def legs_exit(page, f, legs):
    """C9 退出复位：浮层收起 + 回调已摘 + 自派 end 不再重启识别。"""
    page.locator("#btn-call-end").click(timeout=5000)
    ok_idle, st = wait_state(page, "idle", 40)
    before = vc(page)["started"]
    hidden = page.evaluate("() => document.querySelector('#call-layer').hidden")
    # 先证「回调真被摘掉」，再看 start 计数有没有涨（否则 sink 已为 null，计数不涨是白断）
    sink = page.evaluate("() => String(window.SpeechRecognition.__sink)")
    page.evaluate("() => { var s = window.SpeechRecognition.__sink; if (s) s({ results: [] }); }")
    page.wait_for_timeout(400)
    after = vc(page)["started"]
    if not hidden or not ok_idle:
        legs["C9"] = "FAIL"
        f.append("C9 结束通话没收回：hidden=%s state=%s" % (hidden, st))
    elif "function" in sink:
        legs["C9"] = "FAIL"
        f.append("C9 退出后 onresult 回调还在（sink=%s）⇒ 前置不成立，计数断言是白断" % sink[:60])
    elif after > before:
        legs["C9"] = "FAIL"
        f.append("C9 退出后识别又被重启（started %d→%d）⇒ 没摘回调，会空转到刷新" % (before, after))
    else:
        legs["C9"] = "PASS"
        print("C9 PASS  退出复位：浮层收起 state=idle 且 end 事件不再重启识别（started 保持 %d）" % after)


def legs_local(page, browser, url, f, legs):
    """C15 本机神经引擎：默认态零探测（公网红线）+ 开关开时目录/路由/通话中切说话人三件都成立。"""
    hits = vc(page).get("probeHits") or 0
    probed = page.evaluate("() => window.Voice.localStatus().probed")
    if hits or probed:
        legs["C15"] = "FAIL"
        f.append("C15 默认态（未置 cfg.localTts）就去探了本机引擎：probeHits=%d probed=%s"
                 "⇒ 公网面会吃一条 ERR_CONNECTION_REFUSED，CONSOLE_ERRORS:0 判据会被打破" % (hits, probed))
        return
    ctx = browser.new_context(permissions=["microphone"])
    ctx.add_init_script(STUB)
    p2 = ctx.new_page()
    e2 = []
    p2.on("pageerror", lambda e: e2.append(str(e)))
    try:
        p2.goto(url, wait_until="load", timeout=30000)
    except Exception as e:  # noqa: BLE001
        ctx.close()
        legs["C15"] = "FAIL"
        f.append("C15 本机引擎页打不开（%s）—— 没测到不判绿" % str(e)[:70])
        return
    # 开关走真实门（cfg.localTts），且必须在 demo-config 落完它自己那份 cfg 之后合着写 ——
    # 覆盖式写会把 remote/emotionRemote 抹掉，那就不是在测「本机引擎在位」而是在测一个不存在的配置态。
    p2.evaluate("() => { const k='peiliao.cfg.v1'; const c=JSON.parse(localStorage.getItem(k)||'{}');"
                " c.localTts = true; localStorage.setItem(k, JSON.stringify(c)); }")
    p2.locator("#btn-call").click(timeout=5000)          # 开通话才探（默认态零请求那条在上半段已钉）
    up = wait_js(p2, "() => window.Voice.localStatus().up === true")
    st = p2.evaluate("() => window.Voice.localStatus()") if up else {}
    ids = p2.evaluate("() => Array.from(document.querySelector('#call-timbre').options).map(o => o.value)")
    ltids = [i for i in ids if str(i).startswith("lt/")]
    if not up or not ltids:
        ctx.close()
        legs["C15"] = "FAIL"
        f.append("C15 引擎在位却没进目录：up=%s status=%s 本机档位数=%d" % (up, st, len(ltids)))
        return
    p2.evaluate("() => window.__vcInstallFake()")
    wait_state(p2, "listening")
    n0 = len(vc(p2)["texts"])
    p2.evaluate("() => { window.__vc.utts = []; window.__vc.ttsReqs = []; window.__vc.audioPlayed = 0; }")
    p2.evaluate("() => window.__vcSay('我今天被导师骂了', true)")
    ok_turn = wait_texts(p2, n0 + 1)
    back, state_txt = wait_state(p2, "listening", 60)
    d = vc(p2)
    first_sid = d["ttsReqs"][0]["sid"] if ok_turn and d["ttsReqs"] else None
    p2.select_option("#call-timbre", "lt/5")
    heard0 = d["audioPlayed"]
    p2.evaluate("() => window.__vcSay('换个声音再说一次', true)")
    ok_swap = wait_texts(p2, n0 + 2)
    d2 = vc(p2)
    last_sid = d2["ttsReqs"][-1]["sid"] if ok_swap and d2["ttsReqs"] else None
    ctx.close()
    texts = [r["text"] for r in d2["ttsReqs"]]
    if not ok_turn:
        legs["C15"] = "FAIL"
        f.append("C15 前置缺失：本机态整轮没跑完（texts=%d 应有>%d）" % (len(d["texts"]), n0))
    elif not d["ttsReqs"]:
        legs["C15"] = "FAIL"
        f.append("C15 一次都没找本机引擎要音频（ttsReqs 空）⇒ 引擎在位却没被用上，等于白接")
    elif d["utts"]:
        legs["C15"] = "FAIL"
        f.append("C15 选了本机引擎却仍走了浏览器合成（utts=%d）⇒ 路由没切过来" % len(d["utts"]))
    elif not d["audioPlayed"]:
        legs["C15"] = "FAIL"
        f.append("C15 拿到音频却没播（audioPlayed=0）⇒ 存在性≠可达性")
    elif last_sid == first_sid:
        legs["C15"] = "FAIL"
        f.append("C15 通话中切说话人没生效：切前 sid=%s 切后 sid=%s（应不同）" % (first_sid, last_sid))
    elif not back or not ok_swap:
        legs["C15"] = "FAIL"
        f.append("C15 本机态没回到听态或第二轮没起轮：back=%s state=%s ok_swap=%s" % (back, state_txt, ok_swap))
    elif e2:
        legs["C15"] = "FAIL"
        f.append("C15 本机态页面有未捕获异常 %d 条: %s" % (len(e2), e2[:2]))
    else:
        legs["C15"] = "PASS"
        print("C15 PASS  默认态 0 探测；本机态 %d 档进目录、%d 次找 sidecar 要音频、0 次浏览器合成、"
              "通话中切说话人 %s→%s 生效（播%d 次，真机音质归人测）"
              % (len(ltids), len(d2["ttsReqs"]), first_sid, last_sid, d2["audioPlayed"] - heard0))
        print("        送 sidecar 的文本：%s" % " | ".join(texts[:4])[:100])


def run_legs(page, browser, url):
    """十段行为腿依次跑；C1 失败即整体早退（后面每条腿都依赖通话层已打开）。"""
    f, legs = [], {}
    if not legs_open(page, f, legs):
        return f, legs
    legs_timbre(page, f, legs)
    legs_turn(page, f, legs)
    legs_duplex(page, f, legs)
    legs_echo_admit(page, f, legs)
    legs_echo_l1(page, f, legs)
    legs_camera(page, f, legs)
    legs_noise(page, f, legs)
    legs_no_tts(page, f, legs)
    legs_marathon(page, f, legs)
    legs_exit(page, f, legs)
    legs_local(page, browser, url, f, legs)
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
            lf, legs = run_legs(page, browser, URL)
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
