/* 心屿 · 对话智能体
 * 共情链路：情绪识别(本地) → 策略选择 → 在线 LLM(OpenAI 兼容) 生成 → 失败降级离线共情模板
 * 降级必须显式标注，禁止把模板伪装成在线 AI。
 *
 * 共情模板 / SYSTEM 提示 / 危机话术的唯一真相源 = `src/data/emotion-strategy.js`
 * （`window.__XINYU_STRATEGY__`，守卫：`_test/strategy_check.py`）。本文件只做编排，不再内置文案。
 */
window.ChatAgent = (function () {
  const CFG_KEY = "peiliao.cfg.v1";
  const HIS_KEY = "peiliao.history.v1";
  const HISTORY_MAX = 10;
  let history = loadHistory();

  const STR = (typeof window !== "undefined" && window.__XINYU_STRATEGY__) || null;
  if (!STR) {
    throw new Error(
      "[ChatAgent] 共情策略表未加载：请确认 index.html 在 chat-agent.js 之前引入 data/emotion-strategy.js"
    );
  }
  const FALLBACK_EMO = STR.fallback || "calm";

  function loadHistory() {
    try { return JSON.parse(localStorage.getItem(HIS_KEY) || "[]"); } catch { return []; }
  }
  function saveHistory() {
    try { if (history.length > 40) history = history.slice(-40); localStorage.setItem(HIS_KEY, JSON.stringify(history)); } catch { /* 内存态 */ }
  }

  function cfg() {
    try { return JSON.parse(localStorage.getItem(CFG_KEY) || "{}"); } catch { return {}; }
  }
  function saveCfg(c) { localStorage.setItem(CFG_KEY, JSON.stringify(c)); }
  function isOnline() { const c = cfg(); return !!c.proxy || !!(c.base && c.key && c.model); }

  /* 统一 LLM 请求：proxy 模式走同源 /api/chat（密钥在云端 Function）；否则前端直连（本地演示）。
   * 60s 超时（与 Java 侧 LlmProxy 请求超时同值）：超时即抛错走离线兜底，避免 thinking 常转。 */
  const LLM_TIMEOUT_MS = 60000;
  async function fetchWithTimeout(url, opts, ms) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), ms || LLM_TIMEOUT_MS);
    try {
      return await fetch(url, { ...opts, signal: ctl.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  function endpoint(c, body) {
    if (c.proxy) {
      return fetchWithTimeout(c.proxy, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
    }
    return fetchWithTimeout(c.base.replace(/\/$/, "") + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + c.key },
      body: JSON.stringify({ model: c.model, ...body })
    });
  }

  function contentOf(data) {
    const content = data?.choices?.[0]?.message?.content;
    if (!content) throw new Error("empty");
    return content.trim();
  }

  /** SSE 解析：逐块喂 `data:` 行的 delta.content，返回整段文本。
   *  只认标准 OpenAI 分片（choices[0].delta.content）；无法解析的行直接跳过，不让流式因噪声中断。 */
  async function readSSE(res, onDelta) {
    const reader = res.body.getReader();
    const dec = new TextDecoder("utf-8");
    let buf = "", full = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) !== -1) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") continue;
        try {
          const j = JSON.parse(payload);
          const piece = j?.choices?.[0]?.delta?.content;
          if (typeof piece === "string" && piece) {
            full += piece;
            if (onDelta) onDelta(full);
          }
        } catch { /* 分片不完整或非 JSON 噪声行：跳过 */ }
      }
    }
    if (!full.trim()) throw new Error("empty-stream");
    return full.trim();
  }

  /**
   * 一次 LLM 调用。给了 onDelta 就尝试流式（`cfg.stream !== false` 时）；
   * 代理/上游不支持流式（响应不是 text/event-stream）或流式请求失败 → **自动回落整包 JSON**，
   * 调用方无需感知，也不会因为回落而丢回复。
   */
  async function llmFetch(messages, temperature, max_tokens, onDelta) {
    const c = cfg();
    const wantStream = !!onDelta && c.stream !== false;
    const body = { messages, temperature, max_tokens };
    if (!wantStream) {
      const res = await endpoint(c, body);
      if (!res.ok) throw new Error("HTTP " + res.status);
      return contentOf(await res.json());
    }
    try {
      const res = await endpoint(c, { ...body, stream: true });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("text/event-stream") && res.body) return await readSSE(res, onDelta);
      return contentOf(await res.json());        // 代理回落成整包：按非流式解析
    } catch (e) {
      if (e && e.name === "AbortError") throw e;
      const res = await endpoint(c, body);       // 流式路径任何异常 → 再走一次原整包路径
      if (!res.ok) throw new Error("HTTP " + res.status);
      return contentOf(await res.json());
    }
  }

  const CRISIS_REPLY = STR.crisis.reply;

  const strategyOf = (emo) => (STR.strategy[emo] || STR.strategy[FALLBACK_EMO]);

  const SYSTEM = (emo) => {
    const s = strategyOf(emo);
    return STR.persona + "用户刚说的话被识别为主要情绪「" + window.EmotionEngine.labelOf(emo) + "」。" +
      "当前共情要点：" + s.lead + "。要求：" + STR.rules.map((r, i) => (i + 1) + ")" + r).join("；") + "。";
  };

  function offlineReply(emo) {
    const pool = strategyOf(emo).templates;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  async function onlineReply(text, emo, onDelta) {
    const messages = [{ role: "system", content: SYSTEM(emo) }];
    for (const h of history.slice(-HISTORY_MAX)) messages.push(h);
    messages.push({ role: "user", content: text });
    const s = strategyOf(emo);
    return llmFetch(messages,
      s.temperature ?? STR.defaultTemperature ?? 0.85,
      s.maxTokens ?? STR.defaultMaxTokens ?? 220,
      onDelta);
  }

  const EMOTIONS = Object.keys(STR.strategy);

  async function llmClassify(text) {
    const cs = STR.classify;
    const data = await llmFetch(
      [{ role: "system", content: cs.sys }, { role: "user", content: text.slice(0, cs.maxInputChars || 200) }],
      cs.temperature ?? 0, cs.maxTokens ?? 40
    );
    const raw = data || "";
    const m = raw.match(/\{[\s\S]*\}/);
    if (!m) throw new Error("no-json");
    const j = JSON.parse(m[0]);
    if (!EMOTIONS.includes(j.emotion)) throw new Error("bad-emotion");
    return { emotion: j.emotion, intensity: Math.max(0, Math.min(1, +j.intensity || 0.5)) };
  }

  /** 双路情绪识别：词典快判 + LLM 精判（LLM 失败回落词典），返回含两路结果供证据展示 */
  async function classifyEmotion(text) {
    const lex = window.EmotionEngine.scan(text);
    if (lex.crisis) return { lex, final: { emotion: "crisis", intensity: 1 }, path: "词典·危机拦截" };
    if (!isOnline()) return { lex, final: lex, path: "仅词典（离线）" };
    try {
      const llm = await llmClassify(text);
      const agree = llm.emotion === lex.emotion;
      return { lex, llm, final: llm, path: agree ? "词典+LLM 一致 → LLM" : "词典+LLM 分歧 → 采信 LLM" };
    } catch {
      return { lex, final: lex, path: "LLM 精判失败 → 词典兜底" };
    }
  }

  // 次情绪判定统一走 EmotionEngine.secondaryOf（单一真相源），用于双色星雾

  /** respond(text, onDelta?)：onDelta 存在且在线时逐字回调已生成文本（流式），否则一次性返回 */
  async function respond(text, onDelta) {
    const t0 = performance.now(); // 计时起点含情绪分类：latency 如实反映整轮等待
    const { lex, final, path } = await classifyEmotion(text);
    const emo = final.emotion, intensity = final.intensity;
    // 次情绪一并入库：星图重放要能复现「主色 n 颗 + 次色 n/2 颗」的原始点亮形态
    const secondary = window.EmotionEngine.secondaryOf(lex.all, emo);
    if (emo === "crisis") {
      remember(text, CRISIS_REPLY);
      window.MemoryStore.record({ emotion: "crisis", intensity: 1, text: text.slice(0, 60) });
      return { reply: CRISIS_REPLY, emotion: "crisis", mode: "guard", path, latency: 0, lexAll: lex.all };
    }
    let reply, mode, streamed = false;
    if (isOnline()) {
      try {
        reply = await onlineReply(text, emo, onDelta);
        mode = "model";
        streamed = !!onDelta;
      } catch { reply = offlineReply(emo); mode = "fallback"; }
    } else {
      reply = offlineReply(emo); mode = "offline";
    }
    const latency = Math.round(performance.now() - t0);
    remember(text, reply);
    window.MemoryStore.record({ emotion: emo, intensity, secondary, text: text.slice(0, 60) });
    return { reply, emotion: emo, intensity, mode, path, latency, secondary, lexAll: lex.all, streamed };
  }

  /** 记住一轮问答：本地 history 为主，远端（J4，默认关闭）尽力而为 */
  function remember(userText, aiText) {
    history.push({ role: "user", content: userText });
    history.push({ role: "assistant", content: aiText });
    saveHistory();
    if (window.MemoryStore && window.MemoryStore.pushMessage) {
      window.MemoryStore.pushMessage("user", userText);
      window.MemoryStore.pushMessage("assistant", aiText);
    }
  }

  /* setCfg 做合并写入：调用方没传的键（Key 为空不传 / proxy 由运行环境持有）一律保留，
   * 避免"开一次设置面板就把已存 Key/proxy 洗掉"。历史照常清空（换模型上下文不混用）。 */
  function setCfg(c) { saveCfg({ ...cfg(), ...c }); history = []; saveHistory(); }
  function getHistory() { return history.slice(); }
  function getCfg() { const c = cfg(); return { base: c.base || "", key: "", model: c.model || "", proxy: c.proxy || "", stream: c.stream !== false }; }
  /** 策略表对外只读视图：供设置面板的 provider 预设与文档展示，禁外部改写 */
  function strategyInfo() {
    return { version: STR.version, emotions: EMOTIONS.slice(), rules: STR.rules.slice(), fallback: FALLBACK_EMO };
  }

  return { respond, classifyEmotion, isOnline, setCfg, getCfg, getHistory, strategyInfo };
})();
