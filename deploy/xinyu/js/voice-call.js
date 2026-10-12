/* 心屿 · 语音通话层（连续听 → 听懂 → 出声 → 再听）
 *
 * r116 新增（老大裁定：引擎=浏览器自带 + 免费网络音色，零密钥零付费；打断=两种都做、通话里可切；
 * 节奏=先完整听懂再出声，但大模型边生成边念第一句）。
 *
 * 分工（P0.8 模块前置约定）：
 *   - `voice.js`      = 声音**能力层**：音色目录、分句朗读队列、一次性语音输入
 *   - `voice-call.js` = 通话**编排层**：收句判定、双工切换、打断、字幕、耗时读数
 *   - `app.js`        = 只注入 `send`（共情链路归编排层所有，本模块不认识 ChatAgent）
 *
 * 四条硬约束（沿用 voice.js 头部三条，再加通话特有的一条）：
 *   1. 能力不支持即隐藏入口，不报错、不"点了没反应"；
 *   2. 任何异常一律吞掉并复位状态，绝不把主对话链路带崩；
 *   3. 麦克风音量计是增益项，取不到也不得影响通话可用；
 *   4. **通话绝不请求摄像头**：`getUserMedia` 恒 `video:false`，界面只**只读**显示表情状态。
 *      「无论是否开启摄像头均可通话」由 `_test/voice_call_check.py` C5（摄像头关）与
 *      C6（摄像头开）正反两腿各验一次。
 *
 * 收句判据（「完整理解语义」这条不许拿半截话去问模型）：
 *   - 句末标点 → 语义完整；
 *   - 无句末标点（ASR 转写常不带标点）→ 「不以连接词结尾」且「够长」才算完整；
 *   - 完整且停顿 ≥ SILENCE_MS 才收；
 *   - 停顿到 FORCE_MS 仍判不完整 → **有界收口**（字幕如实标「停顿收口」），绝不无限等。
 *
 * 判据：`_test/voice_call_check.py` C1–C19（桩化 SpeechRecognition / speechSynthesis / getUserMedia）。
 * wb-echo-L0（2026-10-13）：回声准入闸 —— 收句面/打断面统一过 `isEchoFuzzy + TAIL_MS`，堵「念白回读误当用户输入」。
 * wb-echo-L1（2026-10-13）：跨轮回声内容日志（spokenLog）+ duplex 切换冷却 + barge-in 能量突增判据（判据 C17–C19）。
 */
window.VoiceCall = (function () {
  const $ = (s) => document.querySelector(s);
  const SILENCE_MS = 620;      // 停顿多久算「这句说完了」
  const FORCE_MS = 1900;       // 收句上限：到点必收，否则用户等不到回应
  const MIN_COMPLETE = 6;      // 无标点时，至少这么多字才谈得上「一句完整的话」
  const HARD_BREAK = 30;       // 单句超这么多字仍无句号 → 逗号处先出声（首声延迟优先）
  const STALL_MS = 12000;      // 上游 12s 不吐字就兜底回听（否则 thinking 哑死，S2/S3 钉住）
  const DUPLEX_KEY = "peiliao.callduplex.v1";
  const END_RE = /[。！？!?…]+$/;
  const TAIL_RE = /(然后|还有|而且|以及|或者|因为|但是|所以|就是|那个|可以|需要|应该|比较|特别|非常|一点|一些|的话|可是|不过|要是|如果|跟|和|与|、|，|,)$/;
  const SENT_SPLIT = /[。！？!?…；;]/;
  // 采集侧显式声明处理链（不再吃浏览器默认）：Web Speech 的内部采集 JS 管不到，能管的是
  // 这一路音量计流 + 下面的能量门 —— 后者才是「背景噪声不许把话头一直吊着」的那道闸。
  const AUDIO_CST = { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
  const NOISE_FLOOR = 0.012;     // 能量门下限：低于此不刷新 lastSpeech（取不到读数时不拦）
  const TAIL_MS = 600;           // wb-echo-L0 尾音软窗：念白结束后这么久内的转写用更低回声阈值严查（不硬拦快答）
  const LOG_MAX = 10;            // wb-echo-L1 念白日志条数上界（跨轮回声判据的容量约束）
  const DUPLEX_MS = 300;         // wb-echo-L1 切回全双工后延迟再开麦（防残留念白被收进来）

  let deps = null, rec = null, SR = null;
  let state = "idle";           // idle | listening | thinking | speaking
  let duplex = "full";          // full=可随时打断  half=讲完再听
  let micOn = true, watch = 0;
  let pending = "", lastSpeech = 0, turnAt = 0, ttf = 0, turnMs = 0;
  let speakEndAt = 0;             // 末次念白结束时刻（wb-echo-L0 软窗起点）
  let spokenLog = [];             // wb-echo-L1 最近念白 {text,t0,t1} 日志（替代单槽 recentSpoken）
  let lvlHist = [];               // wb-echo-L1 能量读数历史（barge-in 突增判据；空历史=读数不可得=放行）
  let baseLen = 0, lastLen = 0;   // 已收过口的转写条数 / 本会话累计转写条数（防旧句被重新拼进新句）
  let recAlive = false;           // 识别会话是否还活着：活着就不该再 start()（真机 start 会抛，白折腾一次重启）
  let consumed = 0, speakingBuf = "", tailQueued = false, aiLine = null, lastGum = null;
  let stallT = 0;             // 上游挂起兜底计时器（0=未在等）
  const clearStall = () => { if (stallT) { clearTimeout(stallT); stallT = 0; } };
  let lvl = null;               // 音量计实时能量读数；null = 取不到（判据桩/无权限），取不到就不拦
  let vad = null;               // {stop()} 或 null
  const metric = { user: "", reply: "", mode: "", ttfb: 0 };

  /* ── 能力探测 ───────────────────────────────────────────────────── */
  function asrReady() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition); }

  /* ── 语义收句（纯函数 ⇒ 可单测，见 _unit）───────────────────────── */
  /** 这句在语义上收得住吗：有句末标点，或「不以连接词结尾且够长」 */
  function semanticallyComplete(t) {
    const s = String(t || "").trim();
    if (!s) return false;
    if (END_RE.test(s)) return true;
    if (TAIL_RE.test(s)) return false;
    return s.length >= MIN_COMPLETE;
  }
  /** 停顿多久该收口：完整句走 SILENCE_MS；永不完整走 FORCE_MS 有界收口 */
  function shouldCommit(t, silenceMs) {
    if (!String(t || "").trim()) return "";
    if (silenceMs >= FORCE_MS) return "停顿收口";
    if (silenceMs >= SILENCE_MS && semanticallyComplete(t)) return "语义收句";
    return "";
  }
  /** 能量门：噪声不该被当成「还在说话」。读数取不到（无权限/桩）一律放行，宁降级不误伤。 */
  function gateOpen(l) { return l == null || l >= NOISE_FLOOR; }
  /* wb-echo-L1：barge-in 能量突增判据 —— 近端相对播放前基线 ≥2× 且 300ms 窗内 ≥2 个超阈采样；
     读数不可得（历史不足）一律放行，宁漏勿误（与 gateOpen 同口径）。 */
  function bumpOkFrom(hist, now) {
    const recent = hist.filter((r) => now - r.t <= 300);
    const base = hist.filter((r) => now - r.t > 400 && now - r.t <= 2000);
    if (recent.length < 2 || base.length < 2) return true;
    const bm = base.reduce((a, r) => a + r.v, 0) / base.length;
    const thr = Math.max(2 * bm, NOISE_FLOOR);
    return recent.filter((r) => r.v >= thr).length >= 2;
  }

  /* ── 分句（首声延迟的关键：一句收住就送进朗读队列）──────────────── */
  /** 从累计文本里切出「新增且已收住」的句子。返回 [句子数组, 新的消费位置] */
  function cutSentences(full, from) {
    const out = [];
    let i = from, seg = "";
    for (let k = from; k < full.length; k++) {
      seg += full[k];
      if (SENT_SPLIT.test(full[k])) {
        const s = seg.trim();
        if (s.length >= 2) out.push(s);
        i = k + 1;
        seg = "";
      }
    }
    // 长句迟迟不出标点：在逗号处切一刀，先出声再等后半
    if (full.length - i > HARD_BREAK) {
      const k = Math.max(full.lastIndexOf("，", full.length - 1), full.lastIndexOf("、", full.length - 1));
      if (k >= i + 8) { out.push(full.slice(i, k + 1).trim()); i = k + 1; }
    }
    return [out, i];
  }

  /* ── 回声过滤（全双工时别把自己念的字当插话）──────────────────── */
  const norm = (s) => String(s || "").replace(/[\s，。、！？!?…；;,.]/g, "");
  function isEcho(t) {
    const a = norm(t);
    if (a.length < 2) return false;
    const b = norm(speakingBuf);
    if (!b) return false;
    if (b.indexOf(a) >= 0 || a.indexOf(b) >= 0) return true;   // 整句互含 = 念白被转写回来
    // 前缀重叠须扣掉念白没剩内容才算回声；否则同头插话会被误判打不断
    const rest = a.replace(b, "").replace(a.slice(0, 6), "");
    return b.indexOf(a.slice(0, 6)) >= 0 && rest.length < 2;  }
  /* wb-echo-L0：模糊回声判 —— 对 ASR 错字变体、只听到半句的念白回读兜底。
     以 a 的近似长度窗扫 b，取字符 bigram Dice 最大值；≥0.6 视为回声。 */
  function diceWin(a, b) {
    if (b.indexOf(a) >= 0) return 1;
    const bg = (s) => { const m = new Set(); for (let i = 0; i + 1 < s.length; i++) m.add(s.slice(i, i + 2)); return m; };
    const A = bg(a);
    if (!A.size) return 0;
    let best = 0;
    for (const w of [a.length, Math.ceil(a.length * 1.4)]) {
      for (let i = 0; i + w <= b.length; i += Math.max(1, w - 2)) {
        const B = bg(b.slice(i, i + w));
        if (!B.size) continue;
        let hit = 0;
        A.forEach((g) => { if (B.has(g)) hit++; });
        const d = (2 * hit) / (A.size + B.size);
        if (d > best) best = d;
      }
    }
    return best;
  }
  /** 准入判定：当前念白 + 跨轮念白日志两面查；精确面优先、模糊面兜底（wb-echo-L0/L1）。
      soft=尾音软窗内（含逐句 t1 软窗）：模糊阈值 0.6→0.45 更严打念白拖尾，但不硬拦真人快答。 */
  function isEchoFuzzy(t, soft) {
    const a = norm(t);
    if (a.length < 3) return false;
    if (isEcho(t)) return true;
    const cut = soft ? 0.45 : 0.6;
    return [speakingBuf].concat(spokenLog.map((e) => e.text)).some((raw) => {
      const b = norm(raw);
      return b.length >= 3 && diceWin(a, b) >= cut;
    });
  }

  /* ── 字幕 ───────────────────────────────────────────────────────── */
  function clearBox(box) { while (box && box.firstChild) box.removeChild(box.firstChild); }
  function caption(cls, text, meta) {
    const box = $("#call-captions");
    if (!box) return null;
    const el = document.createElement("div");
    el.className = "call-line " + cls;
    const t = document.createElement("span");
    t.className = "call-line-text";
    t.textContent = text;
    el.appendChild(t);
    if (meta) {
      const s = document.createElement("span");
      s.className = "call-line-meta";
      s.textContent = meta;
      el.appendChild(s);
    }
    box.appendChild(el);
    while (box.children.length > 12) box.removeChild(box.firstChild);
    box.scrollTop = box.scrollHeight;
    return el;
  }
  function showAi(text, meta) {
    if (!text) return;
    if (!aiLine) aiLine = caption("ai", "");
    const t = aiLine.querySelector(".call-line-text");
    if (t) t.textContent = text;
    if (meta) {
      let s = aiLine.querySelector(".call-line-meta");
      if (!s) { s = document.createElement("span"); s.className = "call-line-meta"; aiLine.appendChild(s); }
      s.textContent = meta;
    }
    metric.reply = text;
  }

  /* ── 状态渲染 ───────────────────────────────────────────────────── */
  function paint() {
    const layer = $("#call-layer");
    if (layer) layer.classList.toggle("on", state !== "idle");
    const pill = $("#call-state");
    if (pill) {
      pill.textContent = state === "thinking" ? "心屿正在听懂你说的…"
        : state === "speaking" ? (duplex === "full" ? "心屿在说 · 你可以随时打断" : "心屿在说 · 讲完就轮到你")
          : state === "listening" ? (micOn ? "在听 · 说完自然停顿就行" : "麦克风已静音")
            : "";
      pill.className = "call-pill s-" + state;
    }
    const live = $("#call-live");
    if (live) live.textContent = pending;
        const nb = $("#btn-call");
    if (nb) { nb.classList.toggle("on", state !== "idle"); nb.setAttribute("aria-pressed", String(state !== "idle")); }
    const mb = $("#btn-call-mic");
    if (mb) { mb.setAttribute("aria-pressed", String(micOn)); mb.classList.toggle("is-off", !micOn); }
    const db = $("#btn-call-duplex");
    if (db) { db.setAttribute("aria-checked", String(duplex === "full")); db.textContent = duplex === "full" ? "可随时打断" : "讲完再听"; }
    const mt = $("#call-metrics");
    if (mt) mt.textContent = ttf ? "首声 " + ttf + "ms · 整轮 " + turnMs + "ms" : (turnMs ? "整轮 " + turnMs + "ms" : "");
    const face = $("#call-face");
    if (face) {
      // 只读显示，不提供开关：通话与摄像头是两条独立能力（约束 4）
      const last = (window.FaceEngine && window.FaceEngine.last) ? window.FaceEngine.last() : null;
      face.textContent = last ? "表情随聊已开启（可选）· 与通话互不影响" : "摄像头未开启 · 不影响语音通话";
    }
  }

  /* ── 识别器 ─────────────────────────────────────────────────────── */
  function buildRec() {
    if (!SR || rec) return;
    rec = new SR();
    rec.lang = "zh-CN";
    rec.interimResults = true;
    rec.continuous = true;       // 通话态：一次启动持续听；浏览器自行 end 时靠重启兜住
    rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      let interim = "", said = "";
      const list = e.results || [];
      if (list.length < lastLen) baseLen = 0;      // 列表变短 = 换了新会话，旧偏移作废
      lastLen = list.length;
      // 真 SpeechRecognition 的 results 是**整个会话的累计列表**（旧句不会消失）⇒ 已收过口的
      // 前 baseLen 条必须跳过，否则下一句的转写会把上一句重新拼进去 = 重复回答（桩若只投一条会藏住这个缺陷）
      for (let k = baseLen; k < list.length; k++) {
        const r = list[k];
        const t = r && r[0] && r[0].transcript ? r[0].transcript : "";
        if (r && r.isFinal) said += t; else interim += t;
      }
      const got = (said + interim).trim();
      if (!micOn) { pending = ""; return; }              // 静音键：不采集也不收句
      if (!gateOpen(lvl)) return;                        // 能量门：这一帧没人在说话，噪声不配当话头
      // wb-echo-L0 准入闸 + wb-echo-L1 逐句软窗：回声先丢弃（软窗内阈值放宽更严打）；丢弃同时推进消费位，
      // 防「被丢的念白残句」留在累计列表里拼进下一句用户话
      const softWin = performance.now() - speakEndAt < TAIL_MS
        || spokenLog.some((e) => { const c = e.t1 || e.t0; return c && performance.now() - c < TAIL_MS; });
      if (isEchoFuzzy(got, softWin)) { baseLen = lastLen; return; }
      pending = got;
      lastSpeech = performance.now();
      // 含 thinking：思考中插话也要能接管（旧码只认 speaking）；wb-echo-L1：念白期加能量突增判据（读数不可得时放行）
      if (state !== "listening" && duplex === "full" && got.length >= 2
          && (state !== "speaking" || bumpOkFrom(lvlHist, performance.now()))) bargeIn();
      paint();
    };
    rec.onerror = (e) => {
      const n = $("#call-note");
      if (n) n.textContent = "识别中断（" + (e && e.error ? e.error : "asr-error") + "）—— 接着说就行，或点「说完啦」";
    };
    rec.onend = () => {
      // 一次 end = 一个会话结束：转写列表随之作废 ⇒ 偏移归零（真机重启后 results 是空的）。
      // 只在「正该听」的时候接手重启：半双工念话期间 end 到了不能抢着开麦（那会把自家念白收进去）。
      // 退出态不等 end（voice_check A8 一手教训）——重启条件写的是状态，不是"等谁先回来"。
      baseLen = 0; lastLen = 0; recAlive = false;
      if (state === "listening" && micOn && rec) startRec();
    };
  }
  function startRec() {
    if (!rec || recAlive) return;                     // 已在听就别再 start()：真机只会抛，然后被重试路径换掉整条会话
    try { rec.start(); recAlive = true; baseLen = 0; lastLen = 0; }
    catch { recAlive = false; }                       // 抛错多半是上一路还在收尾，onend 会接手重启
  }
  function pauseRec() { if (rec) { try { rec.stop(); } catch (e) { /* 已停 */ } } }
  /** 回到「听」：识别器还在就重新起。退出态不等 end（voice_check A8 一手教训） */
  function resume() {
    if (state !== "listening" || !rec || !micOn) return;
    startRec();
  }

  /* ── 音量计（增益项：失败不得影响通话；恒 video:false）────────── */
  function startVad() {
    const md = navigator.mediaDevices;
    if (!md || !md.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) return;
    lastGum = { audio: AUDIO_CST, video: false };
    md.getUserMedia(lastGum)
      .then((stream) => {
        const AC = window.AudioContext || window.webkitAudioContext;
        const ctx = new AC();
        const an = ctx.createAnalyser();
        an.fftSize = 512;
        ctx.createMediaStreamSource(stream).connect(an);
        const buf = new Uint8Array(an.frequencyBinCount);
        const meter = $("#call-level");
        const self = { timer: 0, stop: null };
        self.stop = () => { stream.getTracks().forEach((t) => t.stop()); ctx.close().catch(() => {}); };
        vad = self;
        const loop = () => {
          if (vad !== self) return;
          an.getByteTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) { const d = (buf[i] - 128) / 128; sum += d * d; }
          lvl = Math.sqrt(sum / buf.length);
          if (meter) meter.style.setProperty("--lvl", String(Math.min(1, lvl * 3.2)));
          self.timer = requestAnimationFrame(loop);
        };
        loop();
      })
      .catch(() => { const m = $("#call-level"); if (m) m.classList.add("is-na"); });
  }
  function stopVad() { lvl = null; if (vad) { try { vad.stop(); } catch (e) { /* 已释放 */ } vad = null; } }

  /* ── 一轮问答 ───────────────────────────────────────────────────── */
  function bargeIn() {
    clearStall();                       // 思考期被打断：兜底计时器一并清
    if (window.Voice) window.Voice.cancelSpeech();
    // wb-echo-L1：念白已在 spokenLog（入队时记录），无需再搬移
    speakingBuf = "";
    state = "listening";
    turnAt = 0;
    aiLine = null;
    paint();
  }
  /** 上游挂起兜底：到点清场回听。 */
  function stallOut() {
    if (state !== "thinking") return;
    stallT = 0;
    caption("sys", "这句我想得有点久（网络不太稳），再说一次试试。");    state = "listening";
    turnAt = 0;
    aiLine = null;
    resume();
    paint();
  }
  function queueSpeech(s) {
    speakingBuf += s;                 // 回声过滤按字面比对，发不出声也得记下我说过什么
    const entry = { text: s, t0: 0, t1: 0 };     // wb-echo-L1 念白日志（跨轮回声的内容面与时间面）
    if (spokenLog.length >= LOG_MAX) spokenLog.shift();
    spokenLog.push(entry);
    const heard = !!window.Voice && window.Voice.enqueue(s, () => {
      if (!ttf && turnAt) { ttf = Math.round(performance.now() - turnAt); metric.ttfb = ttf; paint(); }
      entry.t0 = performance.now();
    }, () => { entry.t1 = performance.now(); });
    if (!heard) { paint(); return; }  // 发不出声就别把状态翻成「在说」，否则永远等不到回听（判据 C13）
    if (state === "thinking") state = "speaking";
    if (state === "speaking" && duplex === "half") pauseRec();
    paint();
  }
  function commit(text, how) {
    const mine = String(text || "").trim();
    pending = "";
    lastSpeech = 0;
    baseLen = lastLen;          // 这句已收口：它之前的转写不再参与下一句的拼装
    if (!mine || state !== "listening") return;
    if (isEchoFuzzy(mine)) { pending = ""; lastSpeech = 0; return; }   // wb-echo-L0 双保险：漏网回声不许出门
    if (!deps || typeof deps.send !== "function") { state = "listening"; paint(); return; }
    caption("you", mine, how === "停顿收口" ? "停顿收口" : (how === "手动收句" ? "手动收句" : ""));
    metric.user = mine;
    state = "thinking";
    turnAt = performance.now();
    consumed = 0; tailQueued = false; speakingBuf = ""; aiLine = null;
    stallT = setTimeout(stallOut, STALL_MS);
    paint();
    const onDelta = (full) => {
      clearStall();
      const cut = cutSentences(full, consumed);
      consumed = cut[1];
      cut[0].forEach(queueSpeech);
      showAi(full);
    };
    Promise.resolve(deps.send(mine, onDelta)).then((r) => {
      clearStall();
      const reply = (r && r.reply) || "";
      if (!tailQueued) {
        const rest = reply.slice(consumed).trim();     // 尾句常不带标点：补进队列，别念半截
        if (rest) queueSpeech(rest);
        tailQueued = true;
      }
      turnMs = Math.round(performance.now() - turnAt);
      metric.mode = (r && r.mode) || "";
      const label = metric.mode === "guard" ? "危机转介 · 热线优先"
        : metric.mode === "model" ? "在线大模型"
          : metric.mode === "fallback" ? "大模型暂不可用 · 离线模板" : "离线共情模板";
      showAi(reply, label + (turnMs ? " · " + turnMs + "ms" : ""));
      if (state === "thinking") {
        if (window.Voice && window.Voice.queueBusy()) state = "speaking";
        else { state = "listening"; resume(); }
      }
      paint();
    }).catch(() => {
      clearStall();
      caption("sys", "刚才我走神了一下（网络不稳定），你可以再说一次。");
      state = "listening";
      resume();
      paint();
    });
  }

  /* ── 节拍器：收句 + 念完回听 ────────────────────────────────────── */
  function tick() {
    if (lvl != null) { lvlHist.push({ t: performance.now(), v: lvl }); if (lvlHist.length > 60) lvlHist.shift(); }
    if (state === "listening" && pending && lastSpeech) {
      const how = shouldCommit(pending, performance.now() - lastSpeech);
      if (how) commit(pending, how);
    } else if (state === "speaking" && window.Voice && !window.Voice.queueBusy()) {
      speakEndAt = performance.now();          // wb-echo-L0 尾音窗起点：刚念完的拖尾不算话头
      state = "listening";                     // 队列空了 → 轮到用户
      turnAt = 0;
      if (duplex === "half") resume();
      paint();
    }
  }

  /* ── 开 / 收 ────────────────────────────────────────────────────── */
  function startCall() {
    if (state !== "idle" || !asrReady() || !$("#call-layer")) return;
    if (window.Voice) window.Voice.probeLocal();   // 开了本机引擎就在开口前探一次；默认关 ⇒ 零请求
    SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    state = "listening";
    pending = ""; ttf = 0; turnMs = 0; consumed = 0; speakingBuf = ""; aiLine = null; lastSpeech = 0;
    speakEndAt = 0; spokenLog = []; lvlHist = [];
    baseLen = 0; lastLen = 0;
    metric.ttfb = 0; metric.user = ""; metric.reply = "";
    clearBox($("#call-captions"));
    const layer = $("#call-layer");
    layer.hidden = false;
    const nb = $("#btn-call");
    if (nb) nb.setAttribute("aria-pressed", "true");
    paint();
    buildRec();
    startRec();
    startVad();
    watch = setInterval(tick, 100);
    caption("sys", "通话开始 · 说完整一句话，自然停顿我就接；摄像头开不开都不影响。");
  }
  function endCall() {
    if (state === "idle") return;
    clearInterval(watch);
    watch = 0;
    clearStall();                       // 挂起的兜底不许在退出后还开火
    if (rec) {
      rec.onresult = null; rec.onerror = null; rec.onend = null;   // 摘掉回调，退出后不得再重启
      try { rec.stop(); } catch (e) { /* 已停 */ }
      rec = null;
    }
    recAlive = false;
    if (window.Voice) window.Voice.cancelSpeech();
    stopVad();
    state = "idle";
    pending = ""; speakingBuf = ""; turnAt = 0; lastSpeech = 0;
    speakEndAt = 0; spokenLog = []; lvlHist = [];
    $("#call-layer").hidden = true;
    const nb = $("#btn-call");
    if (nb) nb.setAttribute("aria-pressed", "false");
    paint();
    if (deps && deps.onEnd) deps.onEnd();
  }

  /* ── 接线 ───────────────────────────────────────────────────────── */
  function fillTimbres() {
    const sel = $("#call-timbre");
    if (!sel || !window.Voice) return;
    clearBox(sel);
    window.Voice.timbreCatalog().forEach((t) => {
      const o = document.createElement("option");
      o.value = t.id;
      o.textContent = t.label;
      sel.appendChild(o);
    });
    sel.value = window.Voice.timbre().id;
  }
  function wire() {
    const btn = $("#btn-call");
    if (!btn) return false;
    if (!asrReady()) { btn.style.display = "none"; btn.disabled = true; return false; }   // 约束 1
    try { duplex = localStorage.getItem(DUPLEX_KEY) === "half" ? "half" : "full"; } catch (e) { /* 默认全双工 */ }
    btn.addEventListener("click", () => (state === "idle" ? startCall() : endCall()));
    const end = $("#btn-call-end");
    if (end) end.addEventListener("click", endCall);
    const mic = $("#btn-call-mic");
    if (mic) mic.addEventListener("click", () => {
      micOn = !micOn;
      if (!micOn) { pauseRec(); pending = ""; } else { lastSpeech = 0; resume(); }
      paint();
    });
    const dx = $("#btn-call-duplex");
    if (dx) dx.addEventListener("click", () => {
      duplex = duplex === "full" ? "half" : "full";
      try { localStorage.setItem(DUPLEX_KEY, duplex); } catch (e) { /* 隐私模式 */ }
      // wb-echo-L1：切回全双工先冷却 300ms 再开麦，防残留念白马上被收进来
      if (duplex === "full" && state === "listening") {
        setTimeout(() => { if (duplex === "full" && state === "listening") resume(); }, DUPLEX_MS);
      }
      paint();
    });
    const done = $("#btn-call-done");           // 「说完啦」：停顿判据失灵时的手动出口
    if (done) done.addEventListener("click", () => { if (state === "listening" && pending) commit(pending, "手动收句"); });
    const sel = $("#call-timbre");
    if (sel) sel.addEventListener("change", () => { if (window.Voice) { window.Voice.setTimbre(sel.value); paint(); } });
    const pv = $("#btn-timbre-preview");
    if (pv) pv.addEventListener("click", () => { if (window.Voice) window.Voice.preview(); });
    return true;
  }

  return {
    /** @param {{send: function, onEnd?: function}} d 由 app.js 注入共情链路 */
    init(d) { deps = d || {}; const ok = wire(); if (ok) { fillTimbres(); if (window.Voice && window.Voice.onVoices) window.Voice.onVoices(fillTimbres); } paint(); return ok; },
    startCall, endCall,
    /** 只重绘读数，不改状态：判据与外部状态源（如表情读数注入）用 */
    _repaint: paint,
    isCalling() { return state !== "idle"; },
    supported: asrReady,
    /** 供判据/守卫读取，不参与业务路径 */
    inspect() {
      return { state: state, duplex: duplex, micOn: micOn, pending: pending, ttfb: ttf, turnMs: turnMs,
        complete: semanticallyComplete(pending || metric.user), metrics: metric,
        gum: lastGum, videoAsked: !!(lastGum && lastGum.video), lines: $("#call-captions") ? $("#call-captions").children.length : 0 };
    },
    _unit: { semanticallyComplete, shouldCommit, cutSentences, isEcho, isEchoFuzzy, gateOpen, bumpOkFrom }
  };
})();
