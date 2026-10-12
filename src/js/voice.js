/* 心屿 · 语音能力层（音色目录 + 朗读队列 + 语音输入 ASR）
 *
 * 对标轮 r24 从 `app.js` 整体外提（行为零改动，纯切分）；r116 再加「多种机器人音色」与
 * 「分句朗读队列」两项能力 —— 队列是给通话层用的（边生成边念第一句），文字模式仍走单次朗读。
 *
 * 四条约束（前两条沿用切分前的原注释，未放宽）：
 *   1. 浏览器不支持即隐藏对应按钮 —— 不是报错，也不是"点了没反应"；
 *   2. 朗读/输入都是**增益功能**：任何异常一律吞掉，绝不把主对话链路带崩；
 *   3. 开关持久化走各自的独立键（`peiliao.speak.v1` / `peiliao.calltimbre.v1`），**不进 `peiliao.cfg.v1`** ——
 *      否则 `ChatAgent.setCfg()` 换模型清历史时会被牵连（当初就踩过，故留此注）；
 *   4. 音色**只在本机已装的语音里选**（`speechSynthesis.getVoices()`），零密钥零付费；
 *      引擎自带的中文音色不足时，用 rate/pitch 做「变调扩展」补足，并在标签里如实标出来，
 *      禁把变调冒充独立音色（老大裁定：浏览器自带 + 网络免费音色）。
 *
 * 判据：`_test/ux_guards_check.py` U1（注入计数器实测 utterance 真被构造且 speak、关得掉、不支持即隐藏）、
 *       `_test/voice_check.py` A1/A2（ASR 构造与按钮可见）+ A8/A9/A10（桩化退出态三条都必须复位）、
 *       `_test/voice_call_check.py` C3/C4（音色目录条数与持久化）+ C7（分句队列的出声次序）。
 *       切分前后同一套判据必须都绿。
 */
window.Voice = (function () {
  const $ = (s) => document.querySelector(s);
  const SPEAK_KEY = "peiliao.speak.v1";
  const TIMBRE_KEY = "peiliao.calltimbre.v1";
  let speakOn = false;
  try { speakOn = localStorage.getItem(SPEAK_KEY) === "1"; } catch { /* 内存态 */ }

  /* ── 音色目录 ───────────────────────────────────────────────────── */
  // 语调档：natural 用引擎原声，其余在同一发声者上做变调（标签如实标「变调」）
  const TONES = [
    { k: "natural", label: "原声", rate: 1.0, pitch: 1.0 },
    { k: "warm", label: "温柔", rate: 0.94, pitch: 1.14 },
    { k: "brisk", label: "利落", rate: 1.14, pitch: 0.96 },
    { k: "deep", label: "沉稳低音", rate: 0.88, pitch: 0.7 },
    { k: "electron", label: "电子机器人", rate: 1.0, pitch: 0.5 }
  ];
  const VOICE_CAP = 4;            // 独立发声者上限（× 5 档 = 最多 20 个可选音色）
  let catalog = [];
  let chosen = loadTimbre();

  function hasTTS() { return "speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function"; }
  function voiceScore(v) {
    return (/natural|online|神经|premium|enhanced/i.test(v.name) ? 2 : 0)
      + (/^zh/i.test(v.lang || "") ? 1 : 0);
  }
  function rawVoices() {
    if (!hasTTS()) return [];
    let vs = [];
    try { vs = window.speechSynthesis.getVoices() || []; } catch { vs = []; }
    const zh = vs.filter((v) => /^zh/i.test(v.lang || ""));
    const pool = zh.length ? zh : vs;
    return pool.slice().sort((a, b) => voiceScore(b) - voiceScore(a)).slice(0, VOICE_CAP);
  }
  const shortName = (n) => String(n || "系统音色")
    .replace(/Microsoft |Google |Online( Natural)?| \(Natural\)| - Chinese.*|TTS.*$/gi, "").trim() || "系统音色";
  const voiceListeners = [];
  function buildCatalog() {
    const vs = rawVoices();
    const out = ltOn() ? ltCatalog() : [];      // 本机引擎在位时排最前，浏览器音色随后作兜底
    const base = vs.length ? vs : [null];
    base.forEach((v, i) => {
      TONES.forEach((t) => {
        const who = v ? shortName(v.name) : "系统默认";
        out.push({
          id: i + "/" + t.k,
          label: who + " · " + t.label + (t.k === "natural" ? (v ? "（独立音色）" : "（默认发声者）") : "（变调）"),
          voiceURI: v ? v.voiceURI : "", rate: t.rate, pitch: t.pitch,
          kind: t.k === "natural" ? (v ? "独立音色" : "默认发声者") : "变调扩展"
        });
      });
    });
    catalog = out;
    return out;
  }
  /** 音色表变化时通知订阅者（getVoices() 首帧常为空，异步到位后下拉框必须跟着刷新） */
  function onVoices(cb) { if (typeof cb === "function") voiceListeners.push(cb); }
  function emitVoices() { voiceListeners.forEach((cb) => { try { cb(); } catch { /* 订阅者是观测项 */ } }); }
  function loadTimbre() {
    try {
      const s = JSON.parse(localStorage.getItem(TIMBRE_KEY) || "null");
      if (s && typeof s.rate === "number" && typeof s.pitch === "number") return s;
    } catch { /* 隐私模式/脏值：回落默认 */ }
    return null;
  }
  function timbre() {
    const c = catalog.length ? catalog : buildCatalog();
    if (chosen) { const hit = c.filter((t) => t.id === chosen.id); if (hit.length) return hit[0]; }
    const local = c.filter((t) => t.local)[0];
    const neural = c.filter((t) => /独立音色/.test(t.label))[0];
    return local || neural || c[0];
  }
  function setTimbre(id) {
    const hit = (catalog.length ? catalog : buildCatalog()).filter((t) => t.id === id)[0];
    if (!hit) return false;
    chosen = hit;
    if (hit.local) setLtSid(hit.sid);
    try { localStorage.setItem(TIMBRE_KEY, JSON.stringify(hit)); } catch { /* 内存态 */ }
    return true;
  }
  /** 把当前音色写进 utterance（单一构造点：U1 的注入计数器盯的就是这一处） */
  function applyTimbre(u, t) {
    u.lang = "zh-CN";
    u.rate = t.rate;
    u.pitch = t.pitch;
    if (t.voiceURI) {
      const v = rawVoicesFull().filter((x) => x.voiceURI === t.voiceURI)[0];
      if (v) u.voice = v;
    }
    return u;
  }
  function rawVoicesFull() {
    if (!hasTTS()) return [];
    try { return window.speechSynthesis.getVoices() || []; } catch { return []; }
  }

  /* ── 本机开源神经引擎（r118 决策 #11：sherpa-onnx sidecar，零密钥零付费）──────────
   * 三层开关口径与 emotion-remote / J4 记忆完全一致，不得混为一谈：
   *   1) 代码层：`cfg.localTts === true` 才探测 —— 默认关，公网面一次网络请求都不发
   *      （否则 ERR_CONNECTION_REFUSED 会打破 public_check 的 CONSOLE_ERRORS:0）；
   *   2) 本地演示层：src/js/demo-config.js 置 localTts: true（sidecar 起在 127.0.0.1:8320）；
   *   3) 公网部署层：deploy/xinyu/js/demo-config.js 刻意不含。
   * 探测失败/引擎不在 → 全链路按改动前的浏览器路径走，零回归。 */
  const LT_BASE = "http://127.0.0.1:8320";
  const LT_SID_KEY = "peiliao.localtts.sid.v1";
  const LT_SHOW = 8;                 // 目录里放前 8 个说话人（模型实测 174 人，全列会把下拉撑爆）
  let lt = { probed: false, up: false, busy: false, speakers: 0, err: "" };
  let ltAudio = null, ltSeq = 0;
  let ltSid = 0;
  try { ltSid = Math.max(0, parseInt(localStorage.getItem(LT_SID_KEY) || "0", 10) || 0); } catch { ltSid = 0; }
  function cfgLocalTts() {
    try { return JSON.parse(localStorage.getItem("peiliao.cfg.v1") || "{}").localTts === true; } catch { return false; }
  }
  const ltOn = () => lt.up;
  function ltCatalog() {
    const out = [];
    for (let i = 0; i < Math.min(LT_SHOW, lt.speakers); i++) {
      out.push({ id: "lt/" + i, label: "本机神经引擎 · 说话人 " + (i < 10 ? "0" : "") + i,
        local: true, sid: i, rate: 1, pitch: 1, kind: "本机开源引擎" });
    }
    return out;
  }
  function probe() {
    if (lt.busy || lt.up || !cfgLocalTts()) return;      // 每次都按当前 cfg 重判：demo-config 在 init 之后才写开关
    lt.busy = true; lt.probed = true;
    const ctl = new AbortController();
    const timer = setTimeout(() => { try { ctl.abort(); } catch { /* 已了结 */ } }, 1500);
    fetch(LT_BASE + "/health", { signal: ctl.signal })
      .then((r) => r.json())
      .then((j) => {
        clearTimeout(timer); lt.busy = false;
        lt.up = !!(j && j.loaded && j.numSpeakers > 0);
        lt.speakers = (j && j.numSpeakers) || 0; lt.err = (j && j.error) || "";
        if (ltSid >= lt.speakers) ltSid = 0;
        buildCatalog(); emitVoices();
      })
      .catch((e) => { clearTimeout(timer); lt.busy = false; lt.up = false; lt.err = String((e && e.name) || e).slice(0, 60); });
  }
  /** 一句话 → WAV → 播完 resolve。发不出声也必须 resolve，否则队列会挂死（同 C13 那一类）。
   *  onPlay 在**真的要开口那一刻**回调（不是请求发出时）——首声延迟要量的是这个。 */
  function ltSpeak(text, sid, onPlay) {
    const seq = ++ltSeq;
    return fetch(LT_BASE + "/tts", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: text, sid: sid, speed: 1 })
    }).then((r) => { if (!r.ok) throw new Error("tts-" + r.status); return r.blob(); })
      .then((b) => new Promise((done) => {
        if (seq !== ltSeq) { done(); return; }             // 已被更新的一句话顶掉
        const el = new Audio(URL.createObjectURL(b));
        ltAudio = el;
        let settled = false, watch = 0;
        const settle = () => {
          if (settled) return;
          settled = true; clearTimeout(watch);
          if (ltAudio === el) ltAudio = null;
          try { URL.revokeObjectURL(el.src); } catch { /* 已释放 */ }
          done();
        };
        el.onended = el.onerror = settle;
        watch = setTimeout(settle, 30000);   // 播放事件丢了也不许把朗读队列挂死
        if (onPlay) { try { onPlay(); } catch { /* 回调是观测项 */ } }
        el.play().catch(() => settle());
      }));
  }
  function ltStop() { ltSeq++; if (ltAudio) { try { ltAudio.pause(); } catch { /* 已停 */ } ltAudio = null; } }
  function setLtSid(sid) {
    ltSid = Math.max(0, Math.min(Number(sid) || 0, Math.max(0, lt.speakers - 1)));
    try { localStorage.setItem(LT_SID_KEY, String(ltSid)); } catch { /* 内存态 */ }
    return ltSid;
  }

  /* ── 朗读队列（分句出声）────────────────────────────────────────── */
  let queue = [], talking = false;
  const clean = (t) => String(t == null ? "" : t).replace(/\s+/g, " ").slice(0, 400);
  const canSpeak = () => ltOn() || hasTTS();
  /** wb-echo-L1：统一收尾 —— onEnd 回调（观测项，吞异常）→ 释放队列 → 排下一句。 */
  function settle(item) {
    if (item && item.onEnd) { try { item.onEnd(); } catch { /* 回调是观测项 */ } }
    talking = false;
    pump();
  }
  function pump() {
    if (talking || !canSpeak()) return;
    const item = queue.shift();
    if (!item) return;
    talking = true;
    const t = timbre();
    if (t.local) {                                  // 本机神经引擎：一句话一个 WAV，播完再排下一句
      ltSpeak(clean(item.text), t.sid, item.onStart).then(() => settle(item),
        () => { if (ltOn()) lt.err = "net"; settle(item); });
      return;
    }
    let u;
    try {
      u = new window.SpeechSynthesisUtterance(clean(item.text));
      applyTimbre(u, t);
      if (item.onStart) u.onstart = () => { try { item.onStart(); } catch { /* 回调是观测项 */ } };
      u.onend = () => settle(item);                 // 正常播完 → 记 t1（wb-echo-L1）
      u.onerror = () => { talking = false; pump(); };
      window.speechSynthesis.speak(u);
    } catch { talking = false; queue = []; }        // 约束 2：朗读失败不许把队列挂死
  }
  /** 送一句进队列；onStart 在该句真正开口时回调（通话层用它记「首声延迟」/念白 t0）；
   *  onEnd 在播完时回调（wb-echo-L1 念白 t1，观测项；取消/异常路径可不回调）。
   *  返回 false = 这引擎根本发不出声（调用方据此别把状态翻成「在说」，见 C13）。 */
  function enqueue(text, onStart, onEnd) {
    if (!canSpeak()) return false;      // 引擎缺失即拒收：队列里留项 = queueBusy 恒真 = 通话卡死
    queue.push({ text: text, onStart: onStart, onEnd: onEnd }); pump();
    return true;
  }
  function cancelSpeech() {
    queue = [];
    talking = false;
    ltStop();
    if (hasTTS()) { try { window.speechSynthesis.cancel(); } catch { /* 忽略 */ } }
  }
  const queueBusy = () => talking || queue.length > 0;
  function preview() {
    const t = timbre();
    cancelSpeech();
    enqueue("我是" + t.label.replace(/（.*/, "") + "，心屿会这样陪你说话。", null);
  }

  /* ── 文字模式：朗读开关 ─────────────────────────────────────────── */
  function speakInit() {
    const btn = $("#btn-speak");
    if (!btn) return;
    btn.setAttribute("aria-pressed", String(speakOn));
    if (!hasTTS()) { btn.style.display = "none"; btn.disabled = true; return; }
    const paint = () => {
      btn.classList.toggle("on", speakOn);
      btn.setAttribute("aria-pressed", String(speakOn));
      btn.textContent = speakOn ? "🔊" : "🔇";
      btn.title = speakOn ? "正在朗读回复，点击关闭" : "点击开启回复朗读";
    };
    paint();
    btn.addEventListener("click", () => {
      speakOn = !speakOn;
      try { localStorage.setItem(SPEAK_KEY, speakOn ? "1" : "0"); } catch { /* 内存态 */ }
      if (!speakOn) cancelSpeech();
      paint();
    });
  }
  /** 朗读一条回复。任何异常一律吞掉：朗读是增益功能，绝不能把主对话链路带崩。 */
  function speak(text) {
    if (!speakOn || !hasTTS()) return;
    cancelSpeech();                 // 文字模式仍是「新回复顶掉旧朗读」，与切分前行为一致
    enqueue(text, null);
  }

  /* ── 文字模式：一次性语音输入（Web Speech API，zh-CN）───────────── */
  function voiceInit() {
    const btn = $("#btn-voice");
    if (!btn) return;
    btn.setAttribute("aria-pressed", "false");
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { btn.style.display = "none"; return; }
    const rec = new SR();
    rec.lang = "zh-CN";
    rec.interimResults = true;
    rec.continuous = false;
    let listening = false;
    /** 退出监听态（幂等：事件与点击两条路都走这里） */
    const leaveListening = () => {
      listening = false;
      btn.classList.remove("recording");
      btn.setAttribute("aria-pressed", "false");
      btn.textContent = "🎤";
    };
    btn.addEventListener("click", () => {
      if (listening) {
        // 退出态不等 `end`：真机实测 stop() 后可能不派发 ⇒ 等它就把按钮永久卡在监听态，后续点击只再调 stop()
        try { rec.stop(); } catch { /* 识别已自行结束，照常复位 */ }
        leaveListening();
        return;
      }
      listening = true;
      btn.classList.add("recording");
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "●";
      try {
        rec.start();
      } catch {
        leaveListening();  // start 抛错不得留在监听态（约束 2）
      }
    });
    rec.onresult = (e) => {
      let t = "";
      for (const res of e.results) t += res[0].transcript;
      const input = $("#chat-input");
      if (input) input.value = t.slice(0, 500);
    };
    rec.onend = rec.onerror = leaveListening;
  }

  return {
    init() {
      speakInit();
      voiceInit();
      buildCatalog();
      probe();                       // cfg.localTts 不为 true 时零请求（公网面/默认态行为一字不变）
      if (hasTTS()) {
        // 部分浏览器 getVoices() 首帧为空，音色表稍后异步到位 ⇒ 到位后重建目录，
        // 用户没手动选过就跟着升级到更好的音色（选过的一律尊重用户选择）
        try {
          window.speechSynthesis.addEventListener("voiceschanged", () => {
            buildCatalog();
            emitVoices();     // 通知订阅者刷新下拉框（不刷就会一直显示首帧那一条"系统默认"）
          });
        } catch { /* 不支持该事件：目录已按首帧建好 */ }
      }
    },
    speak,
    /** 供守卫读取：开关当前状态（不影响业务路径） */
    isSpeaking() { return speakOn; },
    /** 供通话层与设置面使用 */
    timbreCatalog: buildCatalog,
    timbre, setTimbre, preview, enqueue, cancelSpeech, queueBusy, onVoices,
    ttsReady: hasTTS, probeLocal: probe,
    /** 供判据与设置面读取本机引擎状态；不驱动业务路径 */
    localStatus: () => ({ probed: lt.probed, up: lt.up, speakers: lt.speakers, err: lt.err, sid: ltSid })
  };
})();
