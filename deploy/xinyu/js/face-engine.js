/* 心屿 · 面部表情引擎（window.FaceEngine）
 * 摄像头 → MediaPipe 52 维 blendshape → 按 `data/face-smile-rules.js` 映射成既有六情绪之五，
 * 输出与 `EmotionEngine.scan` **同构**（可直接喂 `ThreeScene.setEmotion`/`colorOf`/图例）+ Duchenne 三态。
 * 红线：① 画面只在内存过一遍（不拍照/不落盘/零网络请求）② crisis 恒 false（不判也不解除危机）
 * ③ love 表情侧判不出（如实进 undetectable）④ 失败明示降级、绝不伪装成功。 */
(function () {
  "use strict";

  const R = window.__XINYU_FACE_RULES__;
  if (!R) throw new Error("face-smile-rules.js 未加载：面部判据缺失（禁静默回落）");

  const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
  /* 眼动/眨眼维（10 个）：非表情，micro 剔除之（r184） */
  const gazeRe = /^eye(?:Blink|Look)/;
  /* 区域维（r184 遮挡：眼镜/帽子）：整区长期趋零即视为被遮。阈值见 rules.quality.flatMin。 */
  const EYE_KEYS = ["eyeBlinkLeft", "eyeBlinkRight", "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft",
    "eyeWideRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight",
    "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight", "cheekSquintLeft", "cheekSquintRight"];
  const BROW_KEYS = ["browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight"];
  function regionFlat(bs, keys, min) {
    for (let i = 0; i < keys.length; i++) if ((bs[keys[i]] || 0) >= min) return false;
    return true;
  }
  const sleep = (ms, tag) => new Promise((res) => setTimeout(() => res(tag), ms));

  /* ── 纯函数层（判据与运行时共用，_test/face_check.py 复算的就是这两条）────────── */

  /** 软饱和 s = 1-(1-x)^gamma。gamma=1（默认）即恒等。
   *  r102 实测：真正修好饱和的是把归一化改成除以 peak（见 rules 的 peak），
   *  不是这条曲线 —— 曲线留着只是给 peak 将来被调错时留一道防线。 */
  function curve(x) {
    const g = (R.curve && R.curve.gamma) || 1;
    if (g === 1) return x;
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    return 1 - Math.pow(1 - x, g);
  }

  /** 一个情绪在 brow/eye/nose/mouth 各区里的正向证据数（供多线索佐证用）。 */
  function cueRegions(w, bs) {
    const hit = [];
    for (const region in R.cues) {
      let sum = 0, pos = 0;
      for (let i = 0; i < R.cues[region].length; i++) {
        const k = R.cues[region][i];
        const wt = w[k] || 0;
        if (wt <= 0) continue;
        pos += wt;
        sum += wt * (bs[k] || 0);
      }
      if (pos > 0 && sum / pos >= R.cue.min) hit.push(region);
    }
    return hit;
  }

  /** 嘴角左右不对称度 (hi-lo)/hi：0=对称（真笑），1=单侧（轻蔑）。 */
  function smileAsymmetry(bs) {
    if (!R.asym) return 0;
    const p = R.asym.mouthSmile;
    const l = bs[p[0]] || 0, r = bs[p[1]] || 0;
    const hi = Math.max(l, r), lo = Math.min(l, r);
    return hi > 0 ? (hi - lo) / hi : 0;
  }

  /** blendshape 向量 → 情绪原始分（0..1） */
  function scores(bs) {
    const out = {};
    let top = 0;
    for (const emo of R.emotions) {
      if (emo === "calm") continue;
      const w = R.weights[emo];
      if (!w) continue;
      let raw = 0, pos = 0;
      for (const k in w) {
        const wt = w[k];
        if (wt > 0) pos += wt;
        raw += wt * (bs[k] || 0);
      }
      let s = curve(clamp01((raw / pos) / R.peak));
      /* 多线索佐证：不足该情绪所需区域数 ⇒ 打折（不归零：弱信号仍是信号）。
         ⚠️ 默认 **1（不打折）**，只有 R.need 点名的情绪才要求多区。
         曾误写成默认 2，joy 也被要求两区 ⇒ 强颜欢笑（按定义只有口部参与）被判成 calm。 */
      const need = (R.need && R.need[emo]) || 1;
      if (need > 1 && cueRegions(w, bs).length < need) s *= R.cue.penalty;
      /* 轻蔑必须真的单侧，否则对称笑会被 contempt 抢走 */
      if (emo === "contempt" && smileAsymmetry(bs) < R.asym.min) s = 0;
      out[emo] = clamp01(s);
      if (out[emo] > top) top = out[emo];
    }
    // calm 是残余量：其余分量越弱，越接近平静（最高分达 baseline 时归零）
    out.calm = clamp01(1 - top / R.calm.baseline);
    return out;
  }

  /** Duchenne 三态：真笑 / 社交性微笑（含强颜欢笑嫌疑）/ 非微笑 */
  function smileKind(bs) {
    const T = R.smile;
    const mx = (a, b) => Math.max(bs[a] || 0, bs[b] || 0);
    const mouth = mx("mouthSmileLeft", "mouthSmileRight");
    const eye = mx("cheekSquintLeft", "cheekSquintRight") * 0.6
      + mx("eyeSquintLeft", "eyeSquintRight") * 0.4;
    const tension = Math.max(
      bs.mouthPressLeft || 0, bs.mouthPressRight || 0,
      bs.browInnerUp || 0, bs.browDownLeft || 0, bs.browDownRight || 0
    );
    if (mouth < T.smileOn) return { kind: "none", mouth: mouth, eye: eye, ratio: 0, tension: tension, masking: false };
    const ratio = mouth > 0 ? eye / mouth : 0;
    const kind = ratio >= T.ratioOn ? "duchenne" : "social";
    return { kind: kind, mouth: mouth, eye: eye, ratio: ratio, tension: tension,
      masking: kind === "social" && tension >= T.tensionOn };
  }

  /* ── 质量门（r113/r184）：画面靠不住 ⇒ 降置信。信号全在本机帧上算。 */
  const qCanvas = (typeof document !== "undefined") ? document.createElement("canvas") : null;
  if (qCanvas) { qCanvas.width = 24; qCanvas.height = 24; }
  const qCtx = qCanvas ? qCanvas.getContext("2d", { willReadFrequently: true }) : null;

  /** 人脸外接框 → 取样区（r184，避开背景）；无关键点 ⇒ null ⇒ 回落整帧 */
  function lumaRect(lm, vw, vh) {
    if (!lm || lm.length < 455 || !(vw > 0) || !(vh > 0)) return null;
    let x0 = 1, x1 = 0, y0 = 1, y1 = 0;
    for (const q of lm) { if (q.x < x0) x0 = q.x; if (q.x > x1) x1 = q.x; if (q.y < y0) y0 = q.y; if (q.y > y1) y1 = q.y; }
    x0 = Math.max(0, x0 - 0.06); x1 = Math.min(1, x1 + 0.06); y0 = Math.max(0, y0 - 0.06); y1 = Math.min(1, y1 + 0.06);
    if (x1 <= x0 || y1 <= y0) return null;
    return { sx: Math.round(x0 * vw), sy: Math.round(y0 * vh), sw: Math.max(1, Math.round((x1 - x0) * vw)), sh: Math.max(1, Math.round((y1 - y0) * vh)) };
  }

  /** 亮度/模糊：24×24 缩样均值与方差（方差=糊图信号）。取不到帧 ⇒ null。 */
  function lumaStats(rect) {
    if (!qCtx || !videoEl || videoEl.readyState < 2) return null;
    try {
      if (rect) qCtx.drawImage(videoEl, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, 24, 24);
      else qCtx.drawImage(videoEl, 0, 0, 24, 24);
      const d = qCtx.getImageData(0, 0, 24, 24).data;
      let sum = 0;
      const px = d.length / 4;
      for (let i = 0; i < d.length; i += 4) sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      const mean = sum / px / 255;
      let vsum = 0;
      for (let i = 0; i < d.length; i += 4) {
        const g = (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255;
        vsum += (g - mean) * (g - mean);
      }
      return { mean: mean, variance: vsum / px };
    } catch (e) { return null; }   // 取像素失败等：没有证据就不下结论
  }

  /** 侧脸：鼻尖(1) 偏离边界(234/454)中点比例，正脸≈0，越大越侧。 */
  function yawRatio(landmarks) {
    if (!landmarks || landmarks.length < 455) return 0;
    const nose = landmarks[1], l = landmarks[234], r = landmarks[454];
    const w = Math.abs(r.x - l.x);
    return w > 0.01 ? (nose.x - (l.x + r.x) / 2) / w : 0;
  }

  /** 人脸宽度占比（x 跨度）；无关键点 ⇒ 1 */
  function faceWidthRatio(lm) {
    if (!lm || lm.length < 455) return 1;
    let x0 = 1, x1 = 0;
    for (const p of lm) { if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x; }
    return x1 - x0;
  }

  /** 纯函数：五信号 → {ok, reasons[]}。阈值全在 rules.quality；unit 测的就是这条。
   *  luma 取不到（null）= 没证据 ⇒ 不判 lighting/blur，宁缺勿滥。 */
  function assessQuality(sig) {
    sig = sig || {};
    const Q = R.quality;
    if (!Q) return { ok: true, reasons: [] };
    const reasons = [];
    if (sig.luma && (sig.luma.mean < Q.brightMin || sig.luma.mean > Q.brightMax)) reasons.push("lighting");
    if (sig.luma && sig.luma.variance < Q.blurVarMin) reasons.push("blur");
    if (Math.abs(sig.yaw || 0) > Q.yawMax) reasons.push("profile");
    if ((sig.mouthFlatSamples || 0) >= Q.mouthFlatSamples) reasons.push("mouth-flat");
    if (Q.faceMin != null && sig.faceWidth != null && sig.faceWidth < Q.faceMin) reasons.push("small");
    if (Q.flatSamples != null && (sig.eyeFlatSamples || 0) >= Q.flatSamples) reasons.push("occluded-eye");
    if (Q.flatSamples != null && (sig.browFlatSamples || 0) >= Q.flatSamples) reasons.push("occluded-brow");
    return { ok: reasons.length === 0, reasons: reasons };
  }

  /** 质量门落点：命中 = 强制降置信（界面如实标「仅供参考」）；嘴部平坦再停用微笑三态。 */
  function applyQuality(view, q) {
    view.quality = q;
    if (!q.ok) {
      view.confident = false;
      if (q.reasons.indexOf("mouth-flat") >= 0 && view.smile) {
        view.smile = { kind: "none", occluded: true, mouth: 0, eye: 0, ratio: 0, tension: 0, masking: false };
      }
    }
    return view;
  }

  /** 表情侧独有三类查本判据的 colors；文本六类回落 EmotionEngine（避免两份色值漂移）。 */
  function colorOfFace(emo) {
    if (R.colors && R.colors[emo]) return R.colors[emo].slice();
    if (window.EmotionEngine) return window.EmotionEngine.colorOf(emo);
    return [0.48, 0.51, 0.68];
  }

  /** 主入口：blendshape 向量 → 与 EmotionEngine.scan 同构的读数 */
  /* ── 细分子维度（r173）─────────────────────────────────────────────────────
   * 与身份类（joy/sadness/...）**并存**的表情属性，不是新身份类 —— 理由见
   * rules.subs 的注释：身份类互斥，而这些属性可共存；缺证据的维度一字不写。
   * prev = 上一帧的**原始** blendshape（未做 EMA），由运行时层的采样循环喂进来；
   *  不传 ⇒ micro 恒 false 且标 microAvailable=false（不许假装能看，也不许假装看不见）。
   */
  const SUB_KEYS = ["neutral", "duchenne", "social", "masked", "worry", "tense",
                    "micro", "asymmetric"];
  function subsOf(bs, s, smile, prev) {
    const S = (R.subs || {});
    const mx = (a, b) => Math.max(bs[a] || 0, bs[b] || 0);
    const out = {};
    /* neutral：最强非平静成分连 weak.on 都没到 ⇒ 帧里没有任何情绪证据 ⇒ 中性。
       注意与 calm 的关系：calm 是身份类（残余量最大），neutral 是证据陈述（连残都没有）。 */
    let topNC = 0;
    for (const emo of R.emotions) {
      if (emo === "calm") continue;
      topNC = Math.max(topNC, s[emo] || 0);
    }
    out.neutral = topNC < (R.weak ? R.weak.on : 0.10);
    out.duchenne = !!(smile && smile.kind === "duchenne");
    out.social = !!(smile && smile.kind === "social");
    out.masked = !!(smile && smile.masking);
    const W = S.worry || { browInnerUp: 0.35, mouthFrownMax: 0.20, browDownMax: 0.15 };
    out.worry = (bs.browInnerUp || 0) >= W.browInnerUp
      && mx("mouthFrownLeft", "mouthFrownRight") < W.mouthFrownMax
      && mx("browDownLeft", "browDownRight") < W.browDownMax;
    const T = S.tense || { mouthPress: 0.30, browDown: 0.30, jawOpenMax: 0.10 };
    out.tense = (mx("mouthPressLeft", "mouthPressRight") >= T.mouthPress
                 || mx("browDownLeft", "browDownRight") >= T.browDown)
      && (bs.jawOpen || 0) < T.jawOpenMax;
    if (!prev) out.micro = false;
    else {
      /* 微表情的两条件：**幅度低** + **比上一帧跳得快**（短时低幅的定义即如此）。
         ⚠️ 这里的"短"受采样率限制：8fps ⇒ 相邻样本间隔 125ms，真微表情（40~200ms）
         只能取到 0~2 个样本 ⇒ 本维度在 8fps 下**只能给出存在线索，不能给时长**。
         要真抓时长，必须把 sample.fps 提到 ≥25 —— 那时要引入独立的快采集通道，
         因为整体提到 25fps 会让每条推理链的开销涨到原来的 3 倍。
         跃变量取全向量欧氏距离（不挑单个 AU），防研发阶段挑出一个好看的维度。 */
      const M = S.micro || { maxAmp: 0.30, minRise: 0.12 };
      /* r184：眨眼 rise≈1.3 > 真微表情 0.28 ⇒ 剔除眼动维（part5） */
      let sq = 0;
      for (const k in bs) {
        if (typeof bs[k] !== "number") continue;
        if (M.gazeSkip !== false && gazeRe.test(k)) continue;
        const d = (bs[k] || 0) - (prev[k] || 0);
        sq += d * d;
      }
      const rise = Math.sqrt(sq);
      const amp = Math.max(0, Math.max.apply(null,
        R.emotions.filter((e) => e !== "calm").map((e) => s[e] || 0).concat([0])));
      out.micro = rise >= M.minRise && amp <= M.maxAmp;
    }
    out.asymmetric = smileAsymmetry(bs) >= (R.asym ? R.asym.min : 0.25);
    out.microAvailable = !!prev;
    return out;
  }

  function read(bs, prev) {
    bs = bs || {};
    const s = scores(bs);
    const smile = smileKind(bs);
    const all = R.emotions.map((e) => ({ emotion: e, score: s[e] }))
      .sort((a, b) => b.score - a.score);
    let main = all[0].emotion;
    const sec = all[1];
    const secondary = (sec && sec.score >= all[0].score * R.secondary.ratio
      && sec.score >= R.secondary.floor) ? sec.emotion : null;
    /* 置信度 = 主分 − 次分（margin）。r102 加：旧版每帧都硬给一个情绪、没有"看不出来"
     * 的出口（实测强度 p25 仅 0.47 ⇒ 一半帧本就不确定却输出确定结论，表现为读数乱跳）。 */
    const margin = all[0].score - (sec ? sec.score : 0);
    /* 弱信号诚实化（r161）：最高非 calm 分量 wt 落在 [on, off) 窄区时——
     *   calm 赢身份 ⇒ 翻成 wt 并标 weak（治"轻微笑 .22 沉底还笃定显示平静"）；
     *   情绪赢身份但分数 < off ⇒ 保留情绪、标 weak。
     * 分数一个数不改（scores 原样调用），只修"笃定"语义 ⇒ F11 饱和率/单调性/序差全不动。
     * 阈值、窄缝上下界与动态分母证伪记录见 rules.weak 注释。 */
    let weak = false;
    const W = R.weak;
    if (W) {
      const wt = all.find((x) => x.emotion !== "calm");   // all 降序 ⇒ 第一个非 calm 即最高
      if (wt && wt.score >= ((W.onByEmo && W.onByEmo[wt.emotion] != null) ? W.onByEmo[wt.emotion] : W.on)) {
        const offOf = (e) => (W.offByEmo && W.offByEmo[e] != null) ? W.offByEmo[e] : W.off;
        if (main === "calm" && wt.score < offOf(wt.emotion)) { main = wt.emotion; weak = true; }
        else if (main !== "calm" && all[0].score < offOf(main)) weak = true;
      }
    }
    const scoreOf = (e) => { const x = all.find((y) => y.emotion === e); return x ? x.score : 0; };
    return {
      emotion: main,
      intensity: clamp01(scoreOf(main) * (R.gain[main] || 1)),
      all: all,
      secondary: secondary,
      confidence: clamp01(margin),
      confident: weak ? false : margin >= (R.confidence ? R.confidence.on : 0),
      weak: weak,               // r161：够真但不够强 ⇒ 界面出「轻微 X（读数仅供参考）」
      color: colorOfFace(main),
      crisis: false,            // 表情既不判危机也不解除危机
      face: true,               // 来源标记：界面/判据据此区分"表情读数"与"文本读数"
      family: R.family ? (R.family[main] || main) : main,  // 与文本六情绪的语义归属（分歧标注用）
      undetectable: R.undetectable,
      smile: smile,
      /* 细分子维度（r173）：与身份类并存，缺证据的维度为 false 或标不可用 */
      subs: subsOf(bs, s, smile, prev)
    };
  }

  /* ── 运行时层：摄像头 + 推理循环 ─────────────────────────────────────────── */

  let stream = null, timer = null, landmarker = null, videoEl = null, running = false;
  let mouthFlatRun = 0;   // 嘴部 blendshape 连续平坦样本数（质量门信号之一）
  let eyeFlatRun = 0, browFlatRun = 0;   // 眼/眉区连续平坦（r184）
  let lastTs = 0, samples = 0;
  /* 会话令牌：getUserMedia / 模型创建都是**异步**的（公网首帧实测要等十几秒），
     期间用户点了「关闭」⇒ 不能因为 await 返回晚就把摄像头又开回来。
     每次 start 领一个号，await 回来先对号，号不对说明已被 stop ⇒ 立刻释放并退出。 */
  let session = 0;
  const state = { ema: null, view: null, at: 0, err: null, tracks: 0, phase: "idle", ts: 0 };

  /* 延迟埋点（轮132·口径 memory/11-face-accuracy.part4 §五） */
  const LAT_N = 120;
  const latB = { inferMs: [], computeMs: [], e2eMs: [] };
  let latIdx = 0, latN = 0;
  function latPush(k, v) {
    latB[k][latIdx] = v;
    if (latN < LAT_N) latN++;
    latIdx = (latIdx + 1) % LAT_N;
  }
  function latPct(k) {
    if (!latN) return null;
    const s = latB[k].slice(0, latN).sort((a, b) => a - b);
    /* 取位按本通道自身长度：latN 三通道共用，越位会返 undefined ⇒ JSON 吞键假绿（轮132） */
    return s.length ? s[Math.min(s.length - 1, Math.floor(0.95 * s.length))] : null;
  }
  function latClear() { latIdx = 0; latN = 0; for (const k in latB) latB[k].length = 0; }

  /** 能力探测：只回答"这台设备/这个环境能不能用"，不启动摄像头 */
  function capability() {
    if (!window.isSecureContext) return { ok: false, reason: "insecure-context" };
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return { ok: false, reason: "no-media-devices" };
    }
    return { ok: true, reason: "" };
  }

  /* 用户级摄像头开关（r87b）：浏览器授权管不了，但"本站允不允许用"归用户管，且要记住。
     关 = 立即真停在跑的流，不是"下次刷新才生效"。 */
  const CAM_KEY = "peiliao.face.cam.v1";
  function enabled() {
    try { return localStorage.getItem(CAM_KEY) !== "off"; } catch (e) { return true; }
  }
  function setEnabled(on) {
    try {
      if (on) localStorage.removeItem(CAM_KEY);
      else localStorage.setItem(CAM_KEY, "off");
    } catch (e) { /* 隐私模式写不了就只对本页生效 */ }
    if (!on) stop();
    return enabled();
  }

  /** 环境自检（r87d）：报清「权限状态 / 设备数 / 设备名」——
      "授权过却打不开"时界面必须能分开报"被阻止 / 没设备 / 被占用"，三种病处方不同。 */
  async function diagnose() {
    const out = { secure: !!window.isSecureContext, mediaOk: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
      permission: "unknown", devices: -1, labels: [] };
    try {
      if (navigator.permissions && navigator.permissions.query) {
        const p = await navigator.permissions.query({ name: "camera" });
        out.permission = (p && p.state) || "unknown";
      }
    } catch (e) { /* Safari 等不认 camera 这个 name ⇒ 保持 unknown，不猜 */ }
    try {
      const ds = await navigator.mediaDevices.enumerateDevices();
      const vids = ds.filter((d) => d.kind === "videoinput");
      out.devices = vids.length;
      out.labels = vids.map((d) => d.label || "(未授权前浏览器不透露设备名)");
    } catch (e) { out.devices = -1; }
    return out;
  }

  /** 等 ESM 桥就绪（它 defer 执行，经典脚本只能异步等） */
  function whenReady(timeoutMs) {
    const limit = timeoutMs || 8000;
    const t0 = Date.now();
    const step = () => {
      const v = window.__XINYU_FACE_VISION__;
      if (v && (v.ensure || v.ready)) {
        // ensure() = 惰性加载（13MB 只在真要用时才下）；旧形态（只有 ready）也兼容
        const p = v.ensure ? v.ensure() : v.ready;
        return Promise.race([p, sleep(limit, "timeout")]).then((r) => {
          if (r === "timeout" && !v.ok) return { ok: false, reason: "vision-timeout" };
          return v.ok ? { ok: true, reason: "" }
            : { ok: false, reason: v.simd === false ? "no-simd" : (v.err || "vision-init-failed") };
        });
      }
      if (Date.now() - t0 > limit) return Promise.resolve({ ok: false, reason: "bridge-timeout" });
      return sleep(60).then(step);
    };
    return Promise.resolve().then(step);
  }

  /** EMA 单步内核（纯函数）：α 越大越跟手、越小越稳。拆出来供 F18 量噪声过滤。 */
  function emaStep(prev, bs, a) {
    const o = {};
    for (const k in bs) o[k] = prev ? a * bs[k] + (1 - a) * (prev[k] || 0) : bs[k];
    return o;
  }

  /** EMA 平滑：对原始 blendshape 做指数移动平均，读数才不会逐帧抖 */
  function smooth(bs) {
    state.ema = emaStep(state.ema, bs, R.smooth.alpha);
    return state.ema;
  }

  function frame() {
    if (!running || !landmarker || !videoEl) return false;
    if (videoEl.readyState < 2) return false;                  // 帧还没到
    if (document.visibilityState === "hidden") return false;   // 页面不可见即停推理
    const t0 = performance.now();
    const ts = Math.max(lastTs + 1, Math.round(t0));
    lastTs = ts;                                               // detectForVideo 要求时间戳单调递增
    const res = landmarker.detectForVideo(videoEl, ts);
    const tInfer = performance.now();
    const cats = res && res.faceBlendshapes && res.faceBlendshapes[0]
      && res.faceBlendshapes[0].categories;
    if (!cats) return false;                                   // 这一帧没检出脸：不算失败，不记样本
    const bs = {};
    for (const c of cats) bs[c.categoryName] = c.score;
    state.view = read(smooth(bs));
    /* 质量门（r113）：亮度/模糊/侧脸/嘴部平坦 —— 命中只降置信+改文案，不参与任何裁决 */
    const Q = R.quality;
    let flat = true;
    for (const k of ["mouthSmileLeft", "mouthSmileRight", "mouthPucker", "mouthFunnel", "jawOpen",
      "mouthPressLeft", "mouthPressRight", "mouthFrownLeft", "mouthFrownRight"]) {
      if ((bs[k] || 0) >= Q.mouthFlat) { flat = false; break; }
    }
    mouthFlatRun = flat ? mouthFlatRun + 1 : 0;
    /* r184：眼区/眉区各自的「连续平坦」计数（与 mouthFlat 同构） */
    const FM = Q.flatMin != null ? Q.flatMin : Q.mouthFlat;
    eyeFlatRun = regionFlat(bs, EYE_KEYS, FM) ? eyeFlatRun + 1 : 0;
    browFlatRun = regionFlat(bs, BROW_KEYS, FM) ? browFlatRun + 1 : 0;
    const lm0 = res.faceLandmarks && res.faceLandmarks[0];
    applyQuality(state.view, assessQuality({
      luma: lumaStats(lumaRect(lm0, videoEl.videoWidth, videoEl.videoHeight)),
      yaw: yawRatio(lm0),
      faceWidth: faceWidthRatio(lm0),
      mouthFlatSamples: mouthFlatRun,
      eyeFlatSamples: eyeFlatRun, browFlatSamples: browFlatRun
    }));
    /* compute 判≤100ms；infer=推理 */
    const tView = performance.now();
    latPush("inferMs", tInfer - t0);
    latPush("computeMs", tView - tInfer);
    state.ts = t0;
    state.at = Date.now();
    samples++;
    return true;
  }

  /**
   * 开启实时表情感知。
   * @param {{video:HTMLVideoElement, onRead?:Function, onError?:Function, fps?:number}} o
   * @returns {Promise<boolean>} 是否真的开起来了（false = 已明示原因，不要重试到死循环）
   */
  async function start(o) {
    const cap = capability();
    if (!cap.ok) { state.err = cap.reason; o.onError && o.onError(cap.reason); return false; }
    if (!enabled()) { state.err = "cam-disabled"; o.onError && o.onError("cam-disabled"); return false; }
    const my = ++session;
    /* ⚠️ 顺序是判据不是偏好：**授权必须是第一个 await**（r87c，用户实测"点了不弹授权窗"）。
       旧版先下 13MB 再要权限 ⇒ 十几秒不弹窗；Safari 更硬（跨 await 后 user gesture 过期 ⇒ 永不弹）。 */
    state.phase = "permission";
    let s;
    try {
      /* 带超时（r87d）：系统级拦截（Windows 隐私开关/杀软/驱动异常）时这个 promise 可能
         一直挂着不 resolve ⇒ 界面停在"等待授权…"。12s 拿不到就自报家门。 */
      s = await Promise.race([
        navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" }, audio: false }),
        sleep((o && o.gumTimeoutMs) || 12000, "TIMEOUT")
      ]);
      if (s === "TIMEOUT") { const t = new Error("timeout"); t.name = "gum-timeout"; throw t; }
    } catch (e) {
      // NotAllowedError=拒绝/被浏览器记住的阻止 / NotFoundError=无摄像头 / 其余按原名上报
      const reason = (e && e.name) || "getUserMedia-failed";
      state.phase = "idle"; state.err = reason; o.onError && o.onError(reason); return false;
    }
    if (my !== session) { s.getTracks().forEach((t) => t.stop()); return false; }  // 关了就不许再亮灯
    stream = s;
    videoEl = o.video;
    videoEl.srcObject = stream;
    /* ⚠️ 不能裸 `await videoEl.play()`：拿不到帧时它的 promise **永不 settle**
       （公网实测就这么把整条开启链吊死 60s+，按钮卡在 disabled）。
       正解是"发起即走 + 1.5s 兜底"——真正的就绪判定交给下面 tick 里的 `readyState >= 2`。 */
    await new Promise((res) => {
      let done = false;
      const fin = () => { if (!done) { done = true; res(); } };
      try { const p = videoEl.play(); if (p && p.then) p.then(fin, fin); else fin(); }
      catch (e) { fin(); }
      setTimeout(fin, 1500);
    });
    if (my !== session) { stop(); return false; }
    // 模型是**惰性**加载的（用户点开才下 13MB），首次在公网实测可达十几秒 ⇒ 默认给 60s
    state.phase = "model";
    const rdy = await whenReady((o && o.timeoutMs) || 60000);
    if (my !== session) { stop(); return false; }
    if (!rdy.ok) { stop(); state.err = rdy.reason; o.onError && o.onError(rdy.reason); return false; }
    state.phase = "warmup";
    try { landmarker = await window.__XINYU_FACE_VISION__.createLandmarker(); }
    catch (e) { stop(); state.err = "landmarker-failed"; o.onError && o.onError("landmarker-failed"); return false; }
    if (my !== session) { stop(); return false; }        // 同理：模型建完才发现已被叫停
    running = true; state.ema = null; samples = 0; mouthFlatRun = 0; eyeFlatRun = 0; browFlatRun = 0; state.err = null; state.phase = "running";
    const period = Math.round(1000 / ((o && o.fps) || R.sample.fps));
    const tick = () => {
      if (!running) return;
      timer = setTimeout(tick, period);
      try {
        if (frame() && o.onRead) { o.onRead(state.view); latPush("e2eMs", performance.now() - state.ts); }
      } catch (e) {
        /* 单帧异常不炸链路：记一次继续跑（WebGL 上下文丢失等瞬时错误属于这一类）。
           但必须**留痕**：公网排障时"一直没读数"最常见的根因就藏在这里，静默吞掉等于没线索。 */
        state.frameErr = String((e && e.message) || e).slice(0, 160);
        state.frameErrN = (state.frameErrN || 0) + 1;
      }
    };
    tick();
    return true;
  }

  /** 关闭：真停轨道（摄像头指示灯灭）+ 释放 landmarker + 停定时器 */
  function stop() {
    running = false;
    state.phase = "idle";
    session++;                      // 作废在途的 start：异步返回后不许再开回来
    if (timer) { clearTimeout(timer); timer = null; }
    if (stream) { stream.getTracks().forEach((t) => t.stop()); state.tracks = 0; stream = null; }
    if (videoEl) { try { videoEl.pause(); videoEl.srcObject = null; } catch (e) { /* 已停 */ } }
    if (landmarker && window.__XINYU_FACE_VISION__ && window.__XINYU_FACE_VISION__.closeLandmarker) {
      window.__XINYU_FACE_VISION__.closeLandmarker(landmarker);
    }
    landmarker = null; videoEl = null; state.ema = null; latClear();
  }

  /** 第二幕用：开一次摄像头，采够样本就停（单帧噪声大，EMA 收敛后的读数才对得起"我识别到了"）。 */
  async function probeOnce(o) {
    const need = Math.max(1, R.sample.minSamples);
    const period = Math.round(1000 / R.sample.fps);
    return new Promise((resolve) => {
      start({
        video: o.video, timeoutMs: o.timeoutMs,
        onRead: (v) => { o.onRead && o.onRead(v); },
        onError: (r) => resolve({ ok: false, reason: r })
      }).then((ok) => {
        if (!ok) return;                       // 失败已由 onError resolve
        const deadline = Date.now() + need * period + 2500;
        const wait = () => {
          if (!running) { resolve({ ok: false, reason: "stopped" }); return; }
          if (samples >= need && state.view) { const v = state.view; stop(); resolve({ ok: true, view: v }); return; }
          if (samples === 0 && state.view) {   // 采到脸了但还没够样本：继续等
            if (Date.now() > deadline) { const v = state.view; stop(); resolve({ ok: true, view: v }); return; }
          }
          if (Date.now() > deadline) { stop(); resolve({ ok: false, reason: samples ? "timeout" : "no-face" }); return; }
          setTimeout(wait, period);
        };
        wait();
      });
    });
  }

  /** 表情读数的中文名。独有三类查 rules，其余走 EmotionEngine（那边是双端 SSOT）。 */
  function labelOfFace(emo) {
    if (R.labels && R.labels[emo]) return R.labels[emo];
    if (window.EmotionEngine) return window.EmotionEngine.labelOf(emo);
    return "平静";
  }

  /** 最近一次有效读数（超过 freshMs 即视为没有，禁止拿旧脸去标新话） */
  function last(maxAgeMs) {
    const age = maxAgeMs == null ? R.freshMs : maxAgeMs;
    if (!state.view || !state.at) return null;
    if (Date.now() - state.at > age) return null;
    return state.view;
  }

  const REASON_TEXT = {
    "insecure-context": "当前不是安全上下文（需 https 或 localhost），摄像头不可用",
    "no-media-devices": "此浏览器不提供摄像头接口",
    "no-simd": "此浏览器不支持 WebAssembly SIMD，表情识别不可用",
    "vision-timeout": "表情模型加载超时（未联网也能用，但模型需首次加载）",
    "bridge-timeout": "表情模块加载超时",
    "vision-init-failed": "表情模型初始化失败",
    "landmarker-failed": "表情识别器创建失败",
    "cam-disabled": "摄像头开关已关闭（点「摄像头」按钮可重新打开）",
    NotAllowedError: "浏览器已阻止摄像头：点地址栏左侧的锁形图标 → 摄像头 → 允许，再点一次开启（被记住的阻止不会再弹窗）",
    "getUserMedia-failed": "摄像头启动失败：检查 Windows 设置 → 隐私和安全性 → 相机（含下方「允许桌面应用访问相机」），以及杀毒软件是否拦了摄像头",
    "gum-timeout": "等不到摄像头响应（可能被系统/杀软拦住，或授权弹窗被晾着）：关掉其它用摄像头的程序，重启浏览器后再试",
    "no-video-device": "没有检测到摄像头设备：检查设备管理器里「照相机」是否被禁用/带感叹号，或外接摄像头是否插好",
    NotReadableError: "摄像头被占用或被系统拦住：先关掉其它用摄像头的程序（会议/相机/直播/OBS），再查 Windows 相机隐私开关",
    TrackStartError: "摄像头被占用或被系统拦住：先关掉其它用摄像头的程序（会议/相机/直播/OBS）",
    AbortError: "摄像头启动被中断（多被其它程序抢占）：重试一次通常可恢复",
    NotFoundError: "没找到可用摄像头",
    NotReadableError: "摄像头被其它程序占用",
    OverconstrainedError: "摄像头不支持所需分辨率",
    "no-face": "画面里没有识别到人脸",
    timeout: "等待表情读数超时"
  };
  function reasonText(r) { return REASON_TEXT[r] || ("表情识别暂不可用（" + r + "）"); }

  window.FaceEngine = {
    read: read, scores: scores, smileKind: smileKind, cueRegions: cueRegions,
    /* r173 导出 yawRatio：它本来就是引擎里的纯函数，之前只是没挂出来。
       `_test/face-harness.html` 要用它对照片算出同一把「侧脸到什么程度」的尺 ——
       让导出的 meta 与**线上质量门同源**（同一套 R.quality 阈值），而不是另外拍一组数。
       ⚠️ 它不参与任何判定：导出脚本只把它当作样本的环境元数据存下来。 */
    yawRatio: yawRatio, faceWidthRatio: faceWidthRatio, lumaRect: lumaRect, emaStep: emaStep,
    assessQuality: assessQuality, applyQuality: applyQuality,
    labelOf: labelOfFace,
    capability: capability, whenReady: whenReady, diagnose: diagnose,
    enabled: enabled, setEnabled: setEnabled,
    start: start, stop: stop, probeOnce: probeOnce, last: last,
    reasonText: reasonText,
    isRunning: () => running,
    lastError: () => state.err,
    sampleCount: () => samples,
    stats: () => ({ running: running, samples: samples, err: state.err, phase: state.phase,
      frameErr: state.frameErr || null, frameErrN: state.frameErrN || 0,
      lat: { n: latN, window: LAT_N,
        inferMs: latPct("inferMs"), computeMs: latPct("computeMs"),
        e2eMs: latPct("e2eMs") } })
  };
})();
