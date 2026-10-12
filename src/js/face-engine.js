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

  /* ── 质量门（r113）：画面靠不住时读数降档。四信号全在本机帧上算，零新增依赖。 */
  const qCanvas = (typeof document !== "undefined") ? document.createElement("canvas") : null;
  if (qCanvas) { qCanvas.width = 24; qCanvas.height = 24; }
  const qCtx = qCanvas ? qCanvas.getContext("2d", { willReadFrequently: true }) : null;

  /** 亮度/模糊：video 缩样到 24×24 的平均灰度与方差（方差是糊图信号）。取不到帧返回 null，不猜。 */
  function lumaStats() {
    if (!qCtx || !videoEl || videoEl.readyState < 2) return null;
    try {
      qCtx.drawImage(videoEl, 0, 0, 24, 24);
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

  /** 侧脸：鼻尖(1) 偏离左右面部边界(234/454)中点的比例，正脸≈0，越大越侧。 */
  function yawRatio(landmarks) {
    if (!landmarks || landmarks.length < 455) return 0;
    const nose = landmarks[1], l = landmarks[234], r = landmarks[454];
    const w = Math.abs(r.x - l.x);
    return w > 0.01 ? (nose.x - (l.x + r.x) / 2) / w : 0;
  }

  /** 纯函数：四信号 → {ok, reasons[]}。阈值全在 rules.quality；unit 测的就是这条。
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
  function read(bs) {
    bs = bs || {};
    const s = scores(bs);
    const all = R.emotions.map((e) => ({ emotion: e, score: s[e] }))
      .sort((a, b) => b.score - a.score);
    const main = all[0].emotion;
    const sec = all[1];
    const secondary = (sec && sec.score >= all[0].score * R.secondary.ratio
      && sec.score >= R.secondary.floor) ? sec.emotion : null;
    /* 置信度 = 主分 − 次分（margin）。r102 加：旧版每帧都硬给一个情绪、没有"看不出来"
     * 的出口（实测强度 p25 仅 0.47 ⇒ 一半帧本就不确定却输出确定结论，表现为读数乱跳）。 */
    const margin = all[0].score - (sec ? sec.score : 0);
    return {
      emotion: main,
      intensity: clamp01(all[0].score * (R.gain[main] || 1)),
      all: all,
      secondary: secondary,
      confidence: clamp01(margin),
      confident: margin >= (R.confidence ? R.confidence.on : 0),
      color: colorOfFace(main),
      crisis: false,            // 表情既不判危机也不解除危机
      face: true,               // 来源标记：界面/判据据此区分"表情读数"与"文本读数"
      family: R.family ? (R.family[main] || main) : main,  // 与文本六情绪的语义归属（分歧标注用）
      undetectable: R.undetectable,
      smile: smileKind(bs)
    };
  }

  /* ── 运行时层：摄像头 + 推理循环 ─────────────────────────────────────────── */

  let stream = null, timer = null, landmarker = null, videoEl = null, running = false;
  let mouthFlatRun = 0;   // 嘴部 blendshape 连续平坦样本数（质量门信号之一）
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

  /** EMA 平滑：对原始 blendshape 做指数移动平均，读数才不会逐帧抖 */
  function smooth(bs) {
    const a = R.smooth.alpha;
    if (!state.ema) { state.ema = {}; for (const k in bs) state.ema[k] = bs[k]; }
    else for (const k in bs) state.ema[k] = a * bs[k] + (1 - a) * (state.ema[k] || 0);
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
    applyQuality(state.view, assessQuality({
      luma: lumaStats(),
      yaw: yawRatio(res.faceLandmarks && res.faceLandmarks[0]),
      mouthFlatSamples: mouthFlatRun
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
    running = true; state.ema = null; samples = 0; mouthFlatRun = 0; state.err = null; state.phase = "running";
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
