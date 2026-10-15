/* 心屿 · 本机 ASR 适配器（把 SpeechRecognition 接口形状接到 /api/asr）
 *
 * 存在的理由：voice-call.js 里那套 **回声三层（wb-echo-L0/L1/L2）** 已经被
 * `_test/voice_call_check.py` 的 C16–C22 六条判据钉死，绝不能为了换引擎去重写它。
 * 于是本文件只做一件事：**造一个与 SpeechRecognition 同形状的对象**，
 * 让 voice-call.js 的上层逻辑（回声闸 / 能量门 / 打断判据 / n-best 重排）原样跑。
 *
 *   对照表（voice-call.js 的读法必须全部成立）：
 *     rec.lang / interimResults / continuous / maxAlternatives   → 属性
 *     rec.start() / rec.stop()                                   → 方法
 *     rec.onresult(e)  e.results 为**累计**列表，元素 {isFinal, [alt…]}，
 *                       alt = {transcript, confidence}           → 事件
 *     rec.onerror(e) / rec.onend()                               → 事件
 *
 * 🔴 三条红线：
 *   1. **不得伪装在线**：本机服务不可用时由 voice-call.js 回落 Web Speech，
 *      而不是让本模块自己编一句文本、或静默不出声。
 *   2. **默认态零探测**（对应 C15）：不显式开启就不发任何请求，
 *      不得在通话启动时顺手探一下 /api/asr/status（那会给公网部署凭空加一条链路）。
 *   3. **n-best 会退化**：Qwen3-ASR 是贪心解码，一次只出一条结果，
 *      故 `maxAlternatives` 在本引擎下恒为 1 —— C23（pickBest 取词表命中的那条）
 *      在本引擎上**无法成立**，这是换引擎的真实代价，交付时已如实标注。
 *
 * 音频链路：getUserMedia(AEC/NS/AGC) → AudioContext → ScriptProcessor 收 PCM
 *          → 端点切分（能量）→ 打包 16k/16bit/mono WAV → POST /api/asr → 结果回灌
 *
 * ⚠ 用 ScriptProcessorNode 而非 AudioWorklet：AudioWorklet 需要独立模块文件或
 *   Blob URL，在本仓「零构建 + 经典 script 标签」的形态下多一层异步失败面；
 *   ScriptProcessor 虽已废弃但各浏览器均可用且与本项目零构建约束一致。
 *
 * 判据：`_test/asr/asr_local_check.js` A1–A10（纯函数，不碰麦克风）
 */
window.AsrLocal = (function () {
  const DIALECTS = ["mandarin", "yue", "chuan", "wu", "dongbei", "minnan", "teochew", "en"];

  /* ── 采集与切分参数 ─────────────────────────────────────────────────── */
  const SR = 16000;              // ASR 统一要求 16k；服务端对非 16k 直接拒（不静默重采样）
  const FRAME = 4096;            // ScriptProcessor 缓冲
  const MAX_SECONDS = 6;         // 单次上限：256KiB 体闸 ÷ 32KB/s ≈ 8s，留 2s 余量
  const MIN_MS = 280;            // 短于此不发（多半是咳嗽/误触发）
  const SIL_START_MS = 160;      // 连续有声多久算「开始说话」
  const SIL_END_MS = 420;        // 静音多久算「这句说完了」→ 切块送识别
  const START_RMS = 0.012;       // 绝对起始门
  const REL_MULT = 2.2;          // 相对底噪倍数（与 voice-call 的 NOISE_MULT 同量级）
  const REL_CAP = 0.12;          // 上界：再吵也不把噪声当话头
  const KEY = "peiliao.asrlocal.v1";   // 独立持久化键：默认关（红线2）

  /* ── 领域热词（零训练成本的方言专名纠偏）────────────────────────────
   * 🔴 这是**偏置**不是强制：模型命中不了就按原样输出，绝不在前端替换文本。
   *   前端改写识别结果 = 伪造识别结果，比识别不准严重得多。
   *   词表由服务端持有（asr-service/app.py 的 DEFAULT_VOCAB），
   *   前端只发 vocab=on|off，不自定义 —— 避免把任意内容塞进偏置管线。*/
  const VOCAB_KEY = "peiliao.asrvocab.v1";
  let vocabOn = true;
  try { vocabOn = localStorage.getItem(VOCAB_KEY) !== "0"; } catch { /* 隐私模式 */ }

  function isVocabOn() { return !!vocabOn; }
  function setVocabOn(on) {
    vocabOn = !!on;
    try { localStorage.setItem(VOCAB_KEY, vocabOn ? "1" : "0"); } catch { /* 只影响本次会话 */ }
    return vocabOn;
  }

  const defaults = () => ({
    endpoint: "/api/asr",
    dialect: "mandarin",
    timeoutMs: 15000,
    enabled: false,
  });

  /* ── 状态与配置 ─────────────────────────────────────────────────────── */
  let cfg = defaults();
  let enabled = false;
  try { enabled = localStorage.getItem(KEY) === "1"; } catch { /* 隐私模式等 */ }
  cfg.enabled = enabled;

  function isEnabled() { return !!cfg.enabled; }
  function setEnabled(on) {
    cfg.enabled = !!on;
    enabled = cfg.enabled;
    try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* 只影响本次会话 */ }
    return cfg.enabled;
  }
  function configure(patch) {
    if (patch && typeof patch === "object") {
      Object.keys(cfg).forEach((k) => {
        if (typeof patch[k] !== "undefined") cfg[k] = patch[k];
      });
    }
    return Object.assign({}, cfg);
  }
  function setDialect(d) { cfg.dialect = DIALECTS.indexOf(d) >= 0 ? d : "mandarin"; return cfg.dialect; }

  /* ── 纯函数：能量门（供判据与自检，不依赖麦克风）────────────────────── */
  /**
   * speechGate(rms, base) → bool
   * 与 voice-call.js 的 gateOpen 同口径：底噪估不出来就退回绝对门，
   * 宁可放行也不误伤（误拦会让人说的话凭空消失，比多收噪声严重）。
   */
  function speechGate(v, base) {
    if (v == null || !isFinite(v)) return true;          // 读数不可得 → 放行
    if (!(base > 0)) return v >= START_RMS;
    const thr = Math.min(Math.max(base * REL_MULT, START_RMS), REL_CAP);
    return v >= thr;
  }

  /** 噪声底：非语音帧能量的滑动中位数（分位数比均值抗尖峰）。 */
  function noiseFloor(levels) {
    const v = (levels || []).filter((x) => isFinite(x) && x >= 0).sort((a, b) => a - b);
    if (v.length < 5) return 0;
    return v[Math.floor(v.length * 0.3)];
  }

  /** 切分状态机（纯逻辑，便于判据说清边界）。 */
  function segment(prev, v, base, dtMs) {
    const st = { on: !!prev.on, voicedMs: prev.voicedMs || 0, silenceMs: prev.silenceMs || 0 };
    const hot = speechGate(v, base);
    if (!st.on) {
      if (hot) { st.voicedMs += dtMs; st.silenceMs = 0; }
      else st.voicedMs = 0;
      if (st.voicedMs >= SIL_START_MS) { st.on = true; st.silenceMs = 0; }
      return st;
    }
    if (hot) { st.silenceMs = 0; st.voicedMs += dtMs; }
    else { st.silenceMs += dtMs; }
    if (st.silenceMs >= SIL_END_MS) { st.on = false; st.voicedMs = 0; st.silenceMs = 0; }
    return st;
  }

  /** 请求 URL 拼装（纯函数，判据直接比字符串，不依赖网络）。 */
  function buildUrl(dialect) {
    const base = cfg.endpoint || "/api/asr";
    return base + "?dialect=" + encodeURIComponent(dialect || cfg.dialect || "mandarin")
      + (isVocabOn() ? "&vocab=on" : "&vocab=off");
  }

  /* ── Float32 PCM → 16k/16bit/mono WAV ───────────────────────────────── */
  function encodeWav(pcm) {
    const n = pcm.length;
    const buf = new ArrayBuffer(44 + n * 2);
    const v = new DataView(buf);
    const wr = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    wr(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); wr(8, "WAVE");
    wr(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, SR, true);
    v.setUint32(28, SR * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    wr(36, "data"); v.setUint32(40, n * 2, true);
    let o = 44;
    for (let i = 0; i < n; i++) {
      let s = Math.max(-1, Math.min(1, pcm[i]));
      v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      o += 2;
    }
    return new Blob([buf], { type: "audio/wav" });
  }

  /* ── 识别器 ─────────────────────────────────────────────────────────── */
  function createRecognizer() {
    // 与 SpeechRecognition 同形状：属性 + 方法 + 三个事件
    const rec = {
      lang: "zh-CN",
      interimResults: false,     // 本机引擎是端点式的，拿不到真 interim（见文件头退化说明）
      continuous: true,
      maxAlternatives: 1,        // 贪心解码 ⇒ 恒 1（C23 在本引擎上不成立）
      onresult: null, onerror: null, onend: null,
      /* 供上层与判据读取，不参与 SpeechRecognition 契约 */
      _engine: "local",
    };

    let stream = null, actx = null, src = null, proc = null, alive = false;
    let results = [];            // 累计列表（Web Speech 同语义，见文件头对照表）
    let seq = 0;
    let chunks = [], nSamples = 0;
    let seg = { on: false, voicedMs: 0, silenceMs: 0 };
    let levels = [], pending = 0;

    const elapsed = () => (chunks.length ? nSamples / SR * 1000 : 0);

    function emit(text, meta) {
      if (!text) return;
      const idx = results.length;
      results.push({
        isFinal: true,
        length: 1,
        0: { transcript: String(text), confidence: 0.9 },
        _meta: meta || null,
      });
      // 与真 SpeechRecognition 同形：results 是**整个会话的累计列表**
      if (typeof rec.onresult === "function") {
        rec.onresult({ resultIndex: idx, results });
      }
    }
    function fail(code) {
      if (typeof rec.onerror === "function") rec.onerror({ error: code });
    }

    function resetBuf() { chunks = []; nSamples = 0; }

    function send(final) {
      if (!final && elapsed() < 400) return;          // 太短不发，别浪费一次推理
      if (!chunks.length) return;
      let take = chunks, n = nSamples;
      if (final && n > MAX_SECONDS * SR) {             // 超长截断（体闸余量）
        take = chunks.slice(); let acc = 0; const keep = [];
        for (const c of take) {
          if (acc + c.length > MAX_SECONDS * SR) break;
          keep.push(c); acc += c.length;
        }
        take = keep; n = acc;
      }
      if (n < MIN_MS / 1000 * SR) { resetBuf(); return; }
      const flat = new Float32Array(n);
      let o = 0;
      for (const c of take) { flat.set(c, o); o += c.length; }
      const mySeq = ++seq;
      const secs = n / SR;
      const blob = encodeWav(flat);
      const url = buildUrl(cfg.dialect);
      const ctl = (typeof AbortController !== "undefined") ? new AbortController() : null;
      const timer = setTimeout(() => { if (ctl) ctl.abort(); }, cfg.timeoutMs || 15000);
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "audio/wav" },
        body: blob,
        signal: ctl ? ctl.signal : undefined,
      }).then((r) => r.json().catch(() => ({})).then((j) => ({ ok: r.ok, j })))
        .then((res) => {
          clearTimeout(timer);
          if (mySeq !== seq && !res.ok) return;         // 已被更新的请求覆盖
          if (!res.ok) { fail((res.j && res.j.error) || ("asr-http-" + 0)); return; }
          // 🔴 红线1：本机服务失败 → 报错让上层回落 Web Speech，绝不在这里编文本
          emit(res.j.text, { engine: "local", inferMs: res.j.inferMs,
                         audioSeconds: res.j.audioSeconds || secs,
                         vocab: !!res.j.vocab });   // 🔴 原样透传，不做任何文本改写
        }).catch(() => {
          clearTimeout(timer);
          fail("asr-unavailable");                      // 网络/服务不可达 → 上层降级
        });
      resetBuf();
    }

    function onAudio(ev) {
      if (!alive) return;
      const inp = ev.inputBuffer.getChannelData(0);
      const dt = (inp.length / ev.sampleRate) * 1000;
      let sum = 0;
      const out = new Float32Array(inp.length);
      for (let i = 0; i < inp.length; i++) { out[i] = inp[i]; sum += inp[i] * inp[i]; }
      const rms = Math.sqrt(sum / inp.length);
      if (!seg.on) levels.push(rms);                    // 只用「未在说话」时估底噪
      if (levels.length > 200) levels.shift();
      const wasOn = seg.on;
      seg = segment(seg, rms, noiseFloor(levels), dt);
      if (seg.on) { chunks.push(out); nSamples += out.length; }
      else if (wasOn) { send(true); }                   // 静音够久 → 切块送识别
      else resetBuf();                                 // 从没开口 ⇒ 丢噪声，不发
    }

    function teardown() {
      alive = false;
      try { if (proc) { proc.onaudioprocess = null; proc.disconnect(); } } catch { /* 已断开 */ }
      try { if (src) src.disconnect(); } catch { /* 已断开 */ }
      try { if (stream) stream.getTracks().forEach((t) => t.stop()); } catch { /* 已停 */ }
      try { if (actx && actx.state !== "closed") actx.close(); } catch { /* 已关 */ }
      proc = null; src = null; stream = null; actx = null;
      chunks = []; nSamples = 0; levels = [];
      seg = { on: false, voicedMs: 0, silenceMs: 0 };
    }

    rec.start = function () {
      if (alive) return;
      const md = navigator.mediaDevices;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!md || !md.getUserMedia || !AC) { fail("unsupported"); return; }
      const vc = window.VoiceCall;
      const cst = (vc && typeof vc.audioConstraints === "function")
        ? vc.audioConstraints() : { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
      md.getUserMedia({ audio: cst }).then((s) => {
        stream = s;
        actx = new AC();
        // 🔴 采样率必须 16k：服务端对非 16k 直接拒（不静默重采样，避免二次失真掩盖问题）
        if (Math.abs(actx.sampleRate - SR) > 1) {
          teardown(); fail("sample-rate-unsupported"); return;
        }
        src = actx.createMediaStreamSource(s);
        proc = actx.createScriptProcessor(FRAME, 1, 1);
        proc.onaudioprocess = onAudio;
        src.connect(proc);
        proc.connect(actx.destination);                // 必须连出去，否则部分浏览器不派发数据
        alive = true;
      }).catch(() => { teardown(); fail("mic-denied"); });
    };

    rec.stop = function () {
      if (!alive) { if (typeof rec.onend === "function") rec.onend(); return; }
      teardown();
      if (typeof rec.onend === "function") rec.onend();
    };
    rec.abort = rec.stop;

    return rec;
  }

  /** 探针：只在用户**显式开启**时调（红线2 默认态零请求）。 */
  function probe() {
    if (!isEnabled()) return Promise.resolve({ probed: false, ready: false, reason: "disabled" });
    return fetch((cfg.endpoint || "/api/asr").replace(/\/transcribe$/, "") + "/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => ({ probed: true, ready: !!(j && j.ready), dialects: j && j.dialects }))
      .catch(() => ({ probed: true, ready: false, reason: "unreachable" }));
  }

  return {
    createRecognizer, isEnabled, setEnabled, setDialect, configure, probe,
    isVocabOn, setVocabOn, buildUrl,
    DIALECTS, speechGate, noiseFloor, segment, encodeWav,
    SR, MAX_SECONDS,
    _unit: { speechGate, noiseFloor, segment, encodeWav, defaults, DIALECTS },
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = window.AsrLocal;