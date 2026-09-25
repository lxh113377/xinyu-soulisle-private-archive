/* 心屿 · 语音模块（回复朗读 TTS + 语音输入 ASR）
 *
 * 对标轮 r24 从 `app.js` 整体外提（行为零改动，纯切分）：
 * `app.js` 此前把「对话编排 / 星图 / 曲线 / 语音 / 窗口化 / 设置」六件事塞在一个 IIFE 里（471 行），
 * 加任何一项都要在同一个作用域里改，回归失败时也无法定位。语音这块与其余部分零耦合
 * （只读写 DOM 与 localStorage 两个独立键），因此先切它。
 *
 * 三条约束（沿用切分前的原注释，未放宽）：
 *   1. 浏览器不支持即隐藏对应按钮 —— 不是报错，也不是"点了没反应"；
 *   2. 朗读/输入都是**增益功能**：任何异常一律吞掉，绝不把主对话链路带崩；
 *   3. 开关持久化走各自的独立键（`peiliao.speak.v1`），**不进 `peiliao.cfg.v1`** ——
 *      否则 `ChatAgent.setCfg()` 换模型清历史时会被牵连（当初就踩过，故留此注）。
 *
 * 判据：`_test/ux_guards_check.py` U1（构造计数实测 speak 真被调用 + 关得掉 + 不支持即隐藏）、
 *       `_test/voice_check.py` A1/A2（ASR 构造与按钮可见）。切分前后同一套判据必须都绿。
 */
window.Voice = (function () {
  const $ = (s) => document.querySelector(s);
  const SPEAK_KEY = "peiliao.speak.v1";
  let speakOn = false;
  try { speakOn = localStorage.getItem(SPEAK_KEY) === "1"; } catch { /* 内存态 */ }

  function speakInit() {
    const btn = $("#btn-speak");
    if (!btn) return;
    btn.setAttribute("aria-pressed", String(speakOn));
    if (!("speechSynthesis" in window) || typeof window.SpeechSynthesisUtterance !== "function") {
      btn.style.display = "none";
      btn.disabled = true;
      return;
    }
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
      if (!speakOn) { try { window.speechSynthesis.cancel(); } catch { /* 忽略 */ } }
      paint();
    });
  }

  /** 朗读一条回复。任何异常一律吞掉：朗读是增益功能，绝不能把主对话链路带崩。 */
  function speak(text) {
    if (!speakOn || !("speechSynthesis" in window)) return;
    try {
      window.speechSynthesis.cancel();
      const u = new window.SpeechSynthesisUtterance(String(text).replace(/\s+/g, " ").slice(0, 400));
      u.lang = "zh-CN";
      u.rate = 1.02;
      window.speechSynthesis.speak(u);
    } catch { /* 无可用语音/被浏览器策略拦截 → 静默 */ }
  }

  /** 语音输入（Web Speech API，zh-CN；不支持则隐藏按钮） */
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
    btn.addEventListener("click", () => {
      if (listening) { rec.stop(); return; }
      listening = true;
      btn.classList.add("recording");
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "●";
      rec.start();
    });
    rec.onresult = (e) => {
      let t = "";
      for (const res of e.results) t += res[0].transcript;
      const input = $("#chat-input");
      if (input) input.value = t.slice(0, 500);
    };
    rec.onend = rec.onerror = () => {
      listening = false;
      btn.classList.remove("recording");
      btn.setAttribute("aria-pressed", "false");
      btn.textContent = "🎤";
    };
  }

  return {
    init() { speakInit(); voiceInit(); },
    speak,
    /** 供守卫读取：开关当前状态（不影响业务路径） */
    isSpeaking() { return speakOn; }
  };
})();
