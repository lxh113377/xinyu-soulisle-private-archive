/* 心屿 · 语音输入质量闸（前置预处理 · 要求3）
 *
 * ⚠ 边界先写死，避免误解：本模块**不做**降噪/回声消除。
 *   AEC/NS/AGC 已由浏览器采集链原生承担 —— `voice-call.js:49` 的
 *   `AUDIO_CST = { echoCancellation, noiseSuppression, autoGainControl }`，
 *   且已有三层回声准入（`isEchoFuzzy`+`TAIL_MS` / `spokenLog` / `bumpOkFrom`）。
 *   那些是 r175/wb-echo-L0~L2 反复踩坑换来的，**重写等于回退**。
 *
 * 本模块补的是它们**没有**的那一块：**送进识别引擎之前，先判断这段音频值不值得送**。
 * 现状是噪声、断句异常、爆音一律照单全收丢给 ASR，识别结果差还分不清是
 * 「引擎不行」还是「这段音频本来就不行」—— 后者根本不该进引擎。
 *
 * 三件事：
 *   1) 质量评估：估信噪比、检出削波、检出过短/过轻；
 *   2) 准入判定：给出 {ok, code, hint}，让调用方决定重说 / 降级 / 照常送；
 *   3) 采集链自适应：把评估结果翻译成 `setAudioConstraints()` 的覆盖参数
 *      （复用既有钩子，不另开并行路径）。
 *
 * 所有阈值集中在本文件且可被 `configure()` 覆盖，便于 `_test/` 直接钉住。
 * 纯函数为主，不碰 DOM / 不碰 getUserMedia —— 没有麦克风也必须能测。
 *
 * 判据：`_test/audio_quality_check.py` Q1–Q9
 */
window.AudioQuality = (function () {
  /* ── 阈值（可 configure 覆盖）───────────────────────────────────────── */
  const DEF = {
    snrRejectDb: 5,      // 低于此值：噪声已淹没语音，识别结果无参考价值
    snrWarnDb: 12,       // 低于此值：勉强可识别，但主动收紧采集链
    clipRejectRate: 0.01,// 削波采样占比 >1%：爆音，会削掉音头，识别必错
    minDurMs: 300,       // 短于此：多半是误触发/咳嗽，不值得送
    quietRms: 0.004,     // 绝对能量过低（AGC 没开或离麦太远）
    loudRms: 0.55,       // 持续过响：削波风险
    fs: 32768            // AudioWorklet/Analyser 满量程刻度，按驱动实际值覆盖
  };
  let T = Object.assign({}, DEF);

  function configure(patch) {
    if (patch && typeof patch === "object") {
      const next = Object.assign({}, T);
      Object.keys(next).forEach((k) => {
        const v = patch[k];
        if (typeof v === "number" && isFinite(v)) next[k] = v;
      });
      T = next;
    }
    return Object.assign({}, T);
  }
  function reset() { T = Object.assign({}, DEF); return Object.assign({}, T); }

  /* ── 1) 质量度量（纯函数）────────────────────────────────────────────── */

  /** 一帧的 RMS。samples 允许任意长度，空/非有限值返回 0（宁降级不抛错）。 */
  function rms(samples) {
    if (!samples || !samples.length) return 0;
    let s = 0, n = 0;
    for (let i = 0; i < samples.length; i++) {
      const v = +samples[i];
      if (!isFinite(v)) continue;
      s += v * v; n++;
    }
    return n ? Math.sqrt(s / n) : 0;
  }

  /** 削波采样占比：|x| ≥ 满量程 98.5% 记为削波。 */
  function clipRate(samples, fs) {
    if (!samples || !samples.length) return 0;
    const full = (fs || T.fs) || 32768;
    const thr = full * 0.985;
    let c = 0, n = 0;
    for (let i = 0; i < samples.length; i++) {
      const v = Math.abs(+samples[i]);
      if (!isFinite(v)) continue;
      n++;
      if (v >= thr) c++;
    }
    return n ? c / n : 0;
  }

  /**
   * 信噪比估计（dB）。
   * frames: [{r: 该帧RMS, speech: bool}]，speech 由调用方 VAD 标。
   * 取「语音帧 RMS 中位数」与「非语音帧 RMS 中位数」之比；
   * 非语音帧不足 3 帧时返回 null（估不出就交由调用方按未知处理，不假装有数）。
   */
  function snrDb(frames) {
    if (!frames || !frames.length) return null;
    const sp = [], ns = [];
    for (const f of frames) {
      if (f == null) continue;
      // frames 允许两种形态：{r, speech} 或裸数字。
      // ⚠ 旧码写的是 `+f && +f.r` —— `+f` 对普通对象得 NaN（falsy），
      //   整个 && 短路 ⇒ v 恒为 NaN ⇒ 所有帧被跳过 ⇒ snrDb 恒返回 null，
      //   噪声判定整条链路静默失效（实测踩过，判据 Q3/Q8/Q9/Q10 全红）。
      const isObj = typeof f === "object";
      const v = isObj ? +f.r : +f;
      if (!isFinite(v) || v <= 0) continue;
      (isObj && f.speech ? sp : ns).push(v);
    }
    if (sp.length < 3 || ns.length < 3) return null;
    sp.sort((a, b) => a - b);
    ns.sort((a, b) => a - b);
    const med = (a) => a[Math.floor(a.length / 2)];
    const s = med(sp), n = med(ns);
    if (!(s > 0) || !(n > 0)) return null;
    return 20 * Math.log10(s / n);
  }

  /* ── 2) 准入判定（纯函数）────────────────────────────────────────────── */

  /**
   * assess({frames, samples, durMs, fs}) → {ok, code, snrDb, clip, level, hint}
   * ok=false 时 code 说明原因，hint 是可直接展示给用户的中文短句。
   * 判定顺序固定：削波 → 时长 → 绝对电平 → 信噪比（先硬后软）。
   */
  function assess(m) {
    m = m || {};
    const samples = m.samples || null;
    const fs = m.fs || T.fs;
    const durMs = typeof m.durMs === "number" ? m.durMs
      : (samples ? (samples.length / (fs || 32768)) * 1000 : 0);
    const clip = samples ? clipRate(samples, fs) : 0;
    const level = samples ? rms(samples) : 0;
    const snr = snrDb(m.frames);

    const bad = (code, hint) => ({ ok: false, code, hint, snrDb: snr, clip, level, durMs });

    if (clip > T.clipRejectRate)
      return bad("clipped", "麦克风好像被碰了或离嘴太近，麻烦再说一遍？");
    if (durMs > 0 && durMs < T.minDurMs)
      return bad("too_short", "我没听清，再靠近说一次好吗？");
    if (level > 0 && level < T.quietRms)
      return bad("too_quiet", "声音有点小，能再说一遍吗？");
    if (level > T.loudRms && clip <= T.clipRejectRate)
      return bad("too_loud", "声音有点大，稍微离远一点说？");
    if (snr !== null && snr < T.snrRejectDb)
      return bad("too_noisy", "这里有点吵，能不能换个安静点的地方？");

    return {
      ok: true,
      code: (snr !== null && snr < T.snrWarnDb) ? "ok_noisy" : "ok",
      hint: (snr !== null && snr < T.snrWarnDb)
        ? "环境有点杂，我会尽力听清" : "",
      snrDb: snr, clip, level, durMs
    };
  }

  /* ── 3) 采集链自适应（喂给既有 setAudioConstraints 钩子）─────────────── */

  /**
   * adapt(quality, base) → constraints 覆盖对象
   * 与 voice-call.js 的 `setAudioConstraints()` 语义一致：返回要覆盖的字段，
   * 未提及的字段沿用 AUDIO_CST。三条取舍：
   *   - 噪声大 → 关 AGC。AGC 会把噪声一起抬上来，放大稳态底噪反而更糟。
   *   - 偏安静 → 开 AGC。免得用户刻意压低音量导致识别没东西可认。
   *   - 削波 → 显式要求更保守的自动增益（回落到 false，交 AEC 处理）。
   * 判据不可得（snrDb===null）时返回 {}，绝不瞎猜。
   */
  function adapt(q, base) {
    const out = Object.assign({}, base && typeof base === "object" ? base : {});
    if (!q || typeof q !== "object") return out;
    if (q.code === "clipped" || q.code === "too_loud") {
      out.autoGainControl = false;
    } else if (typeof q.snrDb === "number" && q.snrDb < T.snrWarnDb) {
      out.autoGainControl = false;
    } else if (typeof q.level === "number" && q.level > 0 && q.level < T.quietRms * 3) {
      out.autoGainControl = true;
    }
    return out;
  }

  /** 对接既有通话层：一条命令走完 评估→适配。返回评估结果供调用方展示 hint。 */
  function assessAndAdapt(m) {
    const q = assess(m);
    return { quality: q, constraints: adapt(q, (m && m.base) || null) };
  }

  return {
    assess, adapt, assessAndAdapt, rms, clipRate, snrDb,
    configure, reset, thresholds: () => Object.assign({}, T), DEFAULTS: Object.assign({}, DEF)
  };
})();

/* 无浏览器环境（node 直接 require 本文件做纯函数自检）时的最小导出兜底 */
if (typeof module !== "undefined" && module.exports) module.exports = window.AudioQuality;