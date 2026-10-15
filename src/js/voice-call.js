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
 *
 * wb-echo-L2（2026-10-13，打断跟手 + 识别准确率）：三条根因的成因与取舍见 CHANGELOG 同日条目。
 *   一句话：**打断判据必须排在回声闸之前**（旧码顺序反了 ⇒ 插话被判成回声 ⇒ bargeIn 永远走不到）；
 *   打断基线取**念白前冻结的底噪**（不是念白响度）；能量采样从 tick 的 10Hz 提到 rAF 的 60Hz；
 *   n-best 用情绪词表重排（`rec.maxAlternatives` 旧码写死 1 = 主动丢掉更好的那条）。
 *   为什么不引 AEC3 wasm：Web Speech 的识别跑在浏览器内部、拿不到它那条流；打断触发改用我们
 *   自己那条已开 `echoCancellation` 的流，识别层残留回声由内容闸 + 打断瞬间的偏移重置治。
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
  // r175/A3-2 自适应噪声门：固定门在嘈杂环境下**形同虚设**（底噪 0.05 > 门 0.012 ⇒ 噪声永远"在说话"，
  // 话头被一直吊着）。门 = clamp(底噪 × NOISE_MULT, NOISE_FLOOR, NOISE_CAP)；底噪估不出来就退回固定门。
  const NOISE_MULT = 2.5;        // 说话声至少得是底噪的这么多倍
  const NOISE_CAP = 0.12;        // 上界：再吵也不许把真人说话判成噪声（宁漏勿误，误拦只是晚一帧更新）
  const AMB_LO = 800, AMB_HI = 5000, AMB_MIN = 8;  // 底噪估计窗口：排除最近 800ms（那可能正是说话声）
  const TAIL_MS = 600;           // wb-echo-L0 尾音软窗：念白结束后这么久内的转写用更低回声阈值严查（不硬拦快答）
  const LOG_MAX = 10;            // wb-echo-L1 念白日志条数上界（跨轮回声判据的容量约束）
  const DUPLEX_MS = 300;         // wb-echo-L1 切回全双工后延迟再开麦（防残留念白被收进来）
  // wb-echo-L2：打断跟手三参数。基线取念白前冻结的底噪、倍数放宽到 2.2（自建流的 AEC3 已经
  // 吃掉大部分回声，剩下的底噪与真人插话差距远大于 2×）、窗内至少 3 个采样过阈（防单帧噪声）。
  const BARGE_MULT = 2.2, BARGE_WIN = 240, BARGE_MIN = 3, HIST_MAX = 400;
  const TAIL_GRACE = 1.7;        // 连接词收尾的宽限倍率：宽限到即当完整句收，不再死等 FORCE_MS
  const ALTS = 5;                // n-best 候选数（rec.maxAlternatives）
  const CRISIS_HINT = /自杀|自残|不想活|活不下去|结束生命|跳楼|割腕|伤害自己/;

  let deps = null, rec = null, SR = null;
  let fellBack = false;         // J6：本机引擎→Web Speech 的降级只做一次（防止两个引擎来回抖）
  let state = "idle";           // idle | listening | thinking | speaking
  let duplex = "full";          // full=可随时打断  half=讲完再听
  let micOn = true, watch = 0;
  let pending = "", lastSpeech = 0, turnAt = 0, ttf = 0, turnMs = 0;
  let speakEndAt = 0;             // 末次念白结束时刻（wb-echo-L0 软窗起点）
  let spokenLog = [];             // wb-echo-L1 最近念白 {text,t0,t1} 日志（替代单槽 recentSpoken）
  let lvlHist = [];               // wb-echo-L1 能量读数历史（barge-in 突增判据；空历史=读数不可得=放行）
  let noiseBase = null;           // wb-echo-L2 念白开口那一刻冻结的底噪（打断判据的基线；null=没冻结到=交文本面兜底）
  let baseLen = 0, lastLen = 0;   // 已收过口的转写条数 / 本会话累计转写条数（防旧句被重新拼进新句）
  let recAlive = false;           // 识别会话是否还活着：活着就不该再 start()（真机 start 会抛，白折腾一次重启）
  let consumed = 0, speakingBuf = "", tailQueued = false, aiLine = null, lastGum = null;
  let stallT = 0;             // 上游挂起兜底计时器（0=未在等）
  const clearStall = () => { if (stallT) { clearTimeout(stallT); stallT = 0; } };
  let lvl = null;               // 音量计实时能量读数；null = 取不到（判据桩/无权限），取不到就不拦
  let vad = null;               // {stop()} 或 null
  const metric = { user: "", reply: "", mode: "", ttfb: 0 };

  /* ── 能力探测 ───────────────────────────────────────────────────── */
  /* 引擎选择（J6）：本机 ASR 优先，Web Speech 保留为降级路径。
   *
   * 🔴 两条不可退让的约束：
   *   1. **默认态零探测**（C15 同款红线）：AsrLocal 未显式开启时，本模块**不发任何请求**，
   *      也不许顺手探一下 /api/asr/status —— 公网部署下那是一条凭空多出来的链路。
   *   2. **不得伪装在线**：本机引擎构造失败/中途报错，一律**回落 Web Speech**，
   *      而不是让用户对着不出声的麦克风讲话。界面上如实显示当前用的是哪个引擎。
   *
   * 两个引擎返回**同形状**对象（见 asr-local.js 文件头的对照表），
   * 所以下面 buildRec 之后的所有逻辑（回声三层 / 能量门 / 打断判据）完全共用，一行不改。 */
  function webSpeechCtor() { return window.SpeechRecognition || window.webkitSpeechRecognition; }
  function asrReady() {
    const L = window.AsrLocal;
    if (L && L.isEnabled()) return true;      // 本机引擎已显式开启 ⇒ 不依赖 Web Speech 存在
    return !!webSpeechCtor();
  }
  function engineName() {
    const L = window.AsrLocal;
    if (L && L.isEnabled()) return "local";
    return webSpeechCtor() ? "webspeech" : "none";
  }
  /** 造一个识别器：本机优先，构造失败静默回落 Web Speech。返回 null 表示一个都没有。 */
  function pickRecognizer() {
    const L = window.AsrLocal;
    if (L && L.isEnabled()) {
      try {
        const r = L.createRecognizer();
        if (r) { r._engine = "local"; return r; }
      } catch { /* 构造失败 → 回落，绝不因此让通话开不起来 */ }
    }
    const S = webSpeechCtor();
    if (!S) return null;
    const r = new S();
    r._engine = "webspeech";
    return r;
  }

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
    // wb-echo-L2：连接词收尾的句子旧码只能死等 FORCE_MS（体感=卡住）。给一截宽限窗，
    // 宽限到即当完整句收，内容一字不截；完整句判据仍在前面，两者同真时同返回。
    if (silenceMs >= SILENCE_MS * TAIL_GRACE && String(t).trim().length >= MIN_COMPLETE) return "语义收句";
    return "";
  }
  /** 环境底噪估计：窗口内读数的**下四分位**（宁低不高 ⇒ 门偏松 ⇒ 宁漏勿误）。
   *  样本不足（刚开麦/桩里没历史）返 null ⇒ 调用方退回固定门。 */
  function ambientFloor(hist, now) {
    if (!Array.isArray(hist) || typeof now !== "number") return null;
    const w = hist.filter((r) => { const d = now - r.t; return d >= AMB_LO && d <= AMB_HI; });
    if (w.length < AMB_MIN) return null;
    const vs = w.map((r) => r.v).sort((a, b) => a - b);
    const v = vs[Math.floor(vs.length * 0.25)];
    return typeof v === "number" && v > 0 ? v : null;
  }
  /** 采集链参数（r175/A3-3）：默认三面旗，可由演示态按环境覆盖（如嘈杂环境关 AGC）。
   *  ⚠ 边界写死在这里防误解：本函数只作用于**我们自己的 getUserMedia 流**（音量计/打断判据），
   *  Web Speech 的内部采集 JS 管不到 —— 它不是"给识别引擎降噪"的开关。 */
  let cstOverride = null;
  function audioConstraints() { return Object.assign({}, AUDIO_CST, cstOverride || {}); }
  function setAudioConstraints(p) {
    cstOverride = (p && typeof p === "object") ? p : null;
    return audioConstraints();
  }

  /** 能量门：噪声不该被当成「还在说话」。读数取不到（无权限/桩）一律放行，宁降级不误伤。
   *  ⚠ **单参调用必须保持改动前的固定门行为** —— voice_call_check 的 4 条 GATE 腿钉的就是这条：
   *  底噪估不出来（floor 非正）时走 `l >= NOISE_FLOOR`，一个字都不许变。 */
  function gateOpen(l, floor) {
    if (l == null) return true;
    if (typeof floor !== "number" || !(floor > 0)) return l >= NOISE_FLOOR;
    const thr = Math.min(Math.max(floor * NOISE_MULT, NOISE_FLOOR), NOISE_CAP);
    return l >= thr;
  }
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
  /* wb-echo-L2：声学打断判据 —— 与回声**内容**面互不依赖，这是跟手的唯一来源。
     base = 念白开口前冻结的底噪（拿念白响度当基线会让「念得越响越打不断」）。
     读数不可得（无麦克风/桩拒了 getUserMedia/底噪没冻结到）⇒ false，交文本面兜底。 */
  function bargeOk(hist, now, base) {
    if (!(typeof base === "number" && base > 0)) return false;
    const win = hist.filter((r) => now - r.t <= BARGE_WIN);
    if (win.length < BARGE_MIN) return false;                 // 采样不足宁漏勿误
    const thr = Math.max(base * BARGE_MULT, NOISE_FLOOR * 2);
    return win.filter((r) => r.v >= thr).length >= BARGE_MIN;
  }
  /** 念白开口前的底噪（近 300ms 中位数，取**下中位** —— 宁可把基线压低也不被说话起始那一下抬高）。
      样本不足返 null —— 宁可降级也不猜。 */
  function baseOf(hist, t0) {
    const w = hist.filter((r) => t0 - r.t > 0 && t0 - r.t <= 300).map((r) => r.v).sort((a, b) => a - b);
    return w.length < BARGE_MIN ? null : w[Math.floor((w.length - 1) / 2)];
  }
  /* n-best 重排：用全仓唯一情绪词表（SSOT）给候选打分 —— 通用模型把「抑郁/失眠/倾诉」
     听错时，词表命中的那条赢；危机词命中额外加权（宁可误召回，安全侧）。
     两项权重刻意同量级（conf×1.5 ≈ 0~1.5，词表命中 +1.5）：旧口径 conf×10 会让置信度
     单项压过整个词表面，重排等于没接（同一次改判据把这条从 C23 里抓出来）。
     词表取不到就纯按置信度，零回归。 */
  function altScore(a, t) {
    let s = (a && typeof a.confidence === "number" ? a.confidence : 0) * 1.5, hit = 0;
    const E = window.EmotionEngine;
    if (E && E.LEX) {
      for (const k in E.LEX) {
        // ⚠️ LEX[k] 的形状是 `{w, color, words}` 不是数组（写错这一层会静默跳过整个词表，
        //   重排退化成「纯按置信度」—— 本轮 C23 就是这么红出来的）
        const ws = Array.isArray(E.LEX[k]) ? E.LEX[k] : (E.LEX[k] || {}).words;
        if (!ws || !ws.length) continue;
        for (const w of ws) if (w && w.length >= 2 && t.indexOf(w) >= 0 && hit < 4) hit++;
      }
    }
    /* 方言形态加分（r176 / A4）：只影响【选哪条候选】，绝不改写文本（asr-normalize.js 红线七）。
       权重 **+1.0 < 词表直接命中 +1.5**（红线九）：方言映射是人工表的间接证据，不得压过强证据。
       模块缺失/抛异常 ⇒ dia=0 ⇒ 与本轮改动前**逐字同分**（沿用约束 2：任何异常吞掉）。 */
    let dia = 0;
    try {
      const N = window.ASRNormalize;
      if (N && typeof N.dialectHits === "function") dia = N.dialectHits(t) || 0;
    } catch (e) { dia = 0; }
    s += hit * 1.5 + dia * 1.0;
    return CRISIS_HINT.test(t) ? s + 3 : s;
  }
  /** n-best 里挑最好的一条。入参 [{transcript, confidence}]，取不到返 ""。 */
  function pickBest(list) {
    const c = [];
    (list || []).forEach((a) => { if (a && typeof a.transcript === "string" && a.transcript.trim()) c.push(a); });
    if (!c.length) return "";
    let b = c[0];
    for (let i = 1; i < c.length; i++) if (altScore(c[i], c[i].transcript) > altScore(b, b.transcript)) b = c[i];
    return b.transcript;
  }

  /** 转写归一化（r174 / A2）：委托 `asr-normalize.js` 的 ASRNormalize。
   *  模块缺失或抛异常一律原样返回 —— 沿用本模块约束 2「任何异常吞掉，绝不把通话打崩」：
   *  归一化是增益项，取不到就退化成改动前的原文，不能反过来变成新的故障面。 */
  function normalizeUtterance(t) {
    try {
      const N = window.ASRNormalize;
      return N && typeof N.normalize === "function" ? N.normalize(t) : t;
    } catch (e) { return t; }
  }

  /** 断句碎片合并（r175 / A3-1）：补投重复与互相包含的片段在这里被吃掉。
   *  ⚠ 入参必须是 **pickBest 的原文**，不是清洗过的文本 —— 清洗在 mergeFragments 内部做一次，
   *  喂进去前先洗会导致二次清洗不幂等（asr-normalize.js 红线六）。
   *  ASRNormalize 缺失/抛异常 ⇒ 降级成「逐段清洗后直接拼」，与改动前逐字同行为。 */
  function mergeUtterance(parts) {
    try {
      const N = window.ASRNormalize;
      if (N && typeof N.mergeFragments === "function") return N.mergeFragments(parts);
    } catch (e) { /* 增益项，见下 */ }
    return (parts || []).map(normalizeUtterance).join("");
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
      // J6：如实标出当前用的是哪个识别引擎（本机 / 浏览器）—— 不许让用户以为
      // 在用「更强的那个」而其实早已降级。降级后文案会从「本机识别」变成「浏览器识别」。
      const engTag = state === "listening"
        ? (rec && rec._engine === "local" ? " · 本机识别" : (fellBack ? " · 浏览器识别" : ""))
        : "";
      pill.textContent = state === "thinking" ? "心屿正在听懂你说的…"
        : state === "speaking" ? (duplex === "full" ? "心屿在说 · 你可以随时打断" : "心屿在说 · 讲完就轮到你")
          : state === "listening" ? (micOn ? "在听 · 说完自然停顿就行" + engTag : "麦克风已静音")
            : "";
      pill.className = "call-pill s-" + state;
      if (pill.dataset) pill.dataset.engine = rec ? (rec._engine || "webspeech") : "none";
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
    if (rec) return;
    rec = pickRecognizer();
    if (rec) bindRec(rec);
  }

  /** 绑定识别器回调。**本机引擎与 Web Speech 共用同一套** ——
   *  下面这一大段（回声三层 / 能量门 / 打断判据 / n-best 重排）一个字都没改，
   *  靠的就是两个引擎返回同形状对象。抽成独立函数是为了中途降级时能重新绑一遍。 */
  function bindRec(r) {
    if (r._engine === "webspeech") {
      // Web Speech 专有属性；本机引擎的默认值已在 asr-local.js 工厂里设好，
      // 且 maxAlternatives 恒 1（贪心解码，C23 的 n-best 重排在本引擎上不成立）。
      r.lang = "zh-CN";
      r.interimResults = true;
      r.continuous = true;       // 通话态：一次启动持续听；浏览器自行 end 时靠重启兜住
      r.maxAlternatives = ALTS;  // wb-echo-L2：旧码写死 1 = 主动丢掉 n-best 里更好的那条
    }
    rec = r;
    r.onresult = (e) => {
      // r175/A3-1：改成先收【片段数组】再合并 —— 原来 `said += t` 直接拼，引擎补投的
      // 重复/包含片段会被拼成整句重复（「我今天有点崩溃我今天有点崩溃了」）。
      const finals = [], interims = [];
      const list = e.results || [];
      if (list.length < lastLen) baseLen = 0;      // 列表变短 = 换了新会话，旧偏移作废
      lastLen = list.length;
      // 真 SpeechRecognition 的 results 是**整个会话的累计列表**（旧句不会消失）⇒ 已收过口的
      // 前 baseLen 条必须跳过，否则下一句的转写会把上一句重新拼进去 = 重复回答（桩若只投一条会藏住这个缺陷）
      for (let k = baseLen; k < list.length; k++) {
        const r = list[k], alts = [];
        if (r) for (let m = 0; m < (r.length || 0); m++) if (r[m]) alts.push(r[m]);
        if (!alts.length && r && typeof r.transcript === "string") alts.push({ transcript: r.transcript, confidence: 0 });
        // r175/A3-1：这里**只挑候选、不清洗**（清洗统一在 mergeUtterance 里做一次，防二次清洗不幂等）
        const t = pickBest(alts);                       // wb-echo-L2 重排，取不到自然回落 ""
        if (r && r.isFinal) finals.push(t); else interims.push(t);
      }
      const got = (mergeUtterance(finals) + mergeUtterance(interims)).trim();
      if (!micOn) { pending = ""; return; }              // 静音键：不采集也不收句
      const now = performance.now();
      // r175/A3-2：门随环境底噪走 —— 固定门在嘈杂环境里等于没设门（底噪比门还高，噪声一直"在说话"）
      if (!gateOpen(lvl, ambientFloor(lvlHist, now))) return;   // 能量门：这一帧没人在说话，噪声不配当话头
      // wb-echo-L2 顺序修正（根因①）+ 分层回声判：**打断判据必须排在回声闸之前**。旧码先 return 掉
      // 回声，真人插话与念白混录时必然被判成回声 ⇒ 这一行永远走不到，这就是「豆包能打断、我们
      // 打不断」的根因。但也不能无脑放行 —— 机器人念白漏进麦克风会自打断成自激励循环。
      // 故这里只挡**精确面**（isEcho = 整句互含/前缀重叠，即纯念白），模糊面（diceWin≥0.6）
      // 仍留在下面的内容闸里。声学面（bargeOk）另有电平把关，不依赖文本。
      if (state !== "listening" && duplex === "full" && got.length >= 2 && !isEcho(got)
          && (state !== "speaking" || bargeOk(lvlHist, now, noiseBase) || bumpOkFrom(lvlHist, now))) bargeIn();
      // 回声准入闸 + 逐句软窗（含打断瞬间手动起算的尾音窗）：回声先丢弃，丢弃同时推进消费位，
      // 防「被丢的念白残句」留在累计列表里拼进下一句用户话
      const softWin = now - speakEndAt < TAIL_MS
        || spokenLog.some((x) => { const c = x.t1 || x.t0; return c && now - c < TAIL_MS; });
      if (isEchoFuzzy(got, softWin)) { baseLen = lastLen; return; }
      pending = got;
      lastSpeech = now;
      paint();
    };
    r.onerror = (e) => {
      const code = (e && e.error) ? e.error : "asr-error";
      // 🔴 本机引擎不可用 → **当场回落 Web Speech**，而不是让用户对着不出声的麦克风讲话。
      //    只在「还在通话、且本机引擎真的在用、且 Web Speech 还在」时才降级；
      //    降级后本局不再切回本机（避免和本机/浏览器两个引擎来回抖）。
      if (r._engine === "local" && state !== "idle" && webSpeechCtor() && !fellBack) {
        fellBack = true;
        try { r.stop(); } catch { /* 已停 */ }
        try { r.onresult = null; r.onerror = null; r.onend = null; } catch { /* 已摘 */ }
        recAlive = false;
        const alt = new (webSpeechCtor())();
        alt._engine = "webspeech";
        bindRec(alt);
        baseLen = 0; lastLen = 0;
        if (state === "listening" && micOn) startRec();
        paint();                    // 立刻重绘：不然界面还挂着「本机识别」，等于对用户撒谎
        const n = $("#call-note");
        if (n) n.textContent = "本机识别暂时用不了，已切回浏览器识别";
        return;
      }
      const n = $("#call-note");
      if (n) n.textContent = "识别中断（" + code + "）—— 接着说就行，或点「说完啦」";
    };
    r.onend = () => {
      // 一次 end = 一个会话结束：转写列表随之作废 ⇒ 偏移归零（真机重启后 results 是空的）。
      // 只在「正该听」的时候接手重启：半双工念话期间 end 到了不能抢着开麦（那会把自家念白收进去）。
      // 退出态不等 end（voice_check A8 一手教训）——重启条件写的是状态，不是"等谁先回来"。
      baseLen = 0; lastLen = 0; recAlive = false;
      if (state === "listening" && micOn && rec && rec._engine === r._engine) startRec();
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
    lastGum = { audio: audioConstraints(), video: false };   // r175/A3-3：走参数化入口（默认与旧常量逐字同）
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
          // wb-echo-L2 根因③：旧码把 lvlHist.push 放在 tick() 里（100ms 一采），
          // 而 lvl 本身是 60Hz 更新的 —— 时间分辨率被砍到 1/6，打断延迟全丢在这。改到这里直接记。
          lvlHist.push({ t: performance.now(), v: lvl });
          if (lvlHist.length > HIST_MAX) lvlHist.shift();   // 400 × ~16ms ≈ 6.4s，够基线窗+近端窗
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
    // wb-echo-L2：打断瞬间必须把话头与消费位一起清零 —— 累计列表里已混了念白残句，
    // 不清则下一句会把残句拼进去（真机连打两次即复现）。cancelSpeech 不派发 onend，
    // 尾音软窗起点只能手动改写，否则扬声器物理残响会被当话头收进来。
    pending = ""; lastSpeech = 0;
    baseLen = lastLen;
    speakEndAt = performance.now();
    paint();
  }
  /** 声学打断面：唯一跟手的来源（文本面被回声闸挡着，见 onresult 注释）。
      读数不可得即静默返 false，交文本面按 C18 的降级腿接管。 */
  function bargeWatch(now) {
    if (duplex !== "full" || state !== "speaking" || !micOn) return false;
    if (!bargeOk(lvlHist, now, noiseBase)) return false;
    bargeIn();
    return true;
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
      noiseBase = baseOf(lvlHist, entry.t0);   // wb-echo-L2：打断判据的基线只在真正开口那一刻冻结
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
    // wb-echo-L2：lvlHist 已移到 rAF 里记（60Hz），这里不再重复采；只跑判定
    if (bargeWatch(performance.now())) return;          // 声学面已接管：本帧不再走收句/念完回听
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
    // J6：SR 不再决定用哪个引擎（改由 pickRecognizer 挑），仅保留给 asrReady 之外的旧读法
    SR = webSpeechCtor();
    fellBack = false;                     // 新的一通重新允许降级
    if (window.AsrLocal && window.AsrLocal.isEnabled()) {
      // 只在**显式开启**时探一次（红线2：默认态零请求）。探不到不阻断通话 ——
      // 本机引擎会自己报错，届时 onerror 里当场回落 Web Speech。
      window.AsrLocal.probe();
    }
    state = "listening";
    pending = ""; ttf = 0; turnMs = 0; consumed = 0; speakingBuf = ""; aiLine = null; lastSpeech = 0;
    speakEndAt = 0; spokenLog = []; lvlHist = [];
    noiseBase = null;                       // wb-echo-L2：底噪随会话重置（上一通的值不带到下一通）
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
    noiseBase = null;                       // wb-echo-L2：退出后不留上一通的底噪
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
        gum: lastGum, videoAsked: !!(lastGum && lastGum.video), lines: $("#call-captions") ? $("#call-captions").children.length : 0,
        noiseBase: noiseBase, histN: lvlHist.length, alts: rec ? rec.maxAlternatives : 0,
        // J6：把当前引擎如实暴露给判据 —— 降级必须可观测，否则「以为在用本机」会被判成绿
        engine: rec ? (rec._engine || "webspeech") : "none", fellBack: fellBack };   // wb-echo-L2：判据读底噪/采样数/候选数
    },
    /** 判据专用注入点：往能量历史灌采样 + 冻结底噪，**不参与业务路径**
     *  （等价于 Analyser 读到真人插话 / 念白前房间安静）。仅供 _test 用。 */
    _injectLevel(v, t) { lvlHist.push({ t: t == null ? performance.now() : t, v: v }); },
    _injectBase(v) { noiseBase = v; },
    _unit: { semanticallyComplete, shouldCommit, cutSentences, isEcho, isEchoFuzzy, gateOpen,
      bumpOkFrom, bargeOk, baseOf, altScore, pickBest,
      // J6：引擎选择缝（判据 A 组用）—— 必须在 _unit 里暴露，否则判据只能靠桩 SpeechRecognition 间接猜
      pickRecognizer, webSpeechCtor, asrReady, engineName,
      // r175/A3：新增三条缝 —— 断句合并、自适应底噪、采集链参数（判据 E7/E8/C24 用）
      mergeUtterance, ambientFloor, audioConstraints, setAudioConstraints, lastGum: () => lastGum }
  };
})();
