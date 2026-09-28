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
   * 超时取值的一手实测与归因（60s→15s、分类腿单列 6s、两腿串行 30.2s→21s）记在 CHANGELOG r51/r52。
   * 这里约束的是"对端多久之内理我"；响应体阶段的停滞由 BODY_IDLE_MS 逐分片续期兜住。 */
  const LLM_TIMEOUT_MS = 15000;
  const CLASSIFY_TIMEOUT_MS = 6000;
  const BODY_IDLE_MS = 6000;    // 分片之间的停滞上界（r64：半开流曾完全无界）；首包仍各按自己那条腿的预算
  let llmBad = false;                      // r51：最近一次是否"配了在线却降级了"（徽章要跟着翻）
  async function fetchWithTimeout(url, opts, ms) {
    const ctl = new AbortController();
    const w = { t: null };
    w.arm = (v) => { clearTimeout(w.t); w.t = setTimeout(() => ctl.abort(), v); };
    w.arm(ms || LLM_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(url, { ...opts, signal: ctl.signal });
    } catch (e) { clearTimeout(w.t); throw e; }
    res.arm = w.arm;   // 交回消费方续期：整轮不限长，只有"停滞"才熔断
    return res;
  }
  const readJson = (res) => { if (res.arm) res.arm(BODY_IDLE_MS); return res.json(); };

  function endpoint(c, body, ms) {
    if (c.proxy) {
      return fetchWithTimeout(c.proxy, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }, ms);
    }
    return fetchWithTimeout(c.base.replace(/\/$/, "") + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + c.key },
      body: JSON.stringify({ model: c.model, ...body })
    }, ms);
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
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        if (res.arm) res.arm(BODY_IDLE_MS);   // 每片续期：长回答不限总时长，只有停滞才熔断
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
    } catch (e) {
      // 停滞熔断且已吐过字 → 保留半句（换成离线模板会抹掉用户已看到的逐字内容），尾 … 就地示意未收完
      if (e && e.name === "AbortError" && full.trim()) return full.trim() + "…";
      throw e;
    }
    if (!full.trim()) throw new Error("empty-stream");
    return full.trim();
  }

  /**
   * 一次 LLM 调用。给了 onDelta 就尝试流式（`cfg.stream !== false` 时）；
   * 代理/上游不支持流式（响应不是 text/event-stream）或流式请求失败 → **自动回落整包 JSON**，
   * 调用方无需感知，也不会因为回落而丢回复。
   */
  async function llmFetch(messages, temperature, max_tokens, onDelta, ms) {
    const c = cfg();
    const wantStream = !!onDelta && c.stream !== false;
    const body = { messages, temperature, max_tokens };
    if (!wantStream) {
      const res = await endpoint(c, body, ms);
      if (!res.ok) throw new Error("HTTP " + res.status);
      return contentOf(await readJson(res));
    }
    try {
      const res = await endpoint(c, { ...body, stream: true }, ms);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("text/event-stream") && res.body) return await readSSE(res, onDelta);
      return contentOf(await readJson(res));      // 代理回落成整包：按非流式解析
    } catch (e) {
      if (e && e.name === "AbortError") throw e;
      const res = await endpoint(c, body, ms);       // 流式路径任何异常 → 再走一次原整包路径
      if (!res.ok) throw new Error("HTTP " + res.status);
      return contentOf(await readJson(res));
    }
  }

  const CRISIS_REPLY = STR.crisis.reply;

  const strategyOf = (emo) => (STR.strategy[emo] || STR.strategy[FALLBACK_EMO]);

  const SYSTEM = (emo) => {
    const s = strategyOf(emo);
    // 长期记忆注入（r52）：MemoryStore 原本**只写不读**，"跨设备记住你"只成立在展示层。
    // 只注入聚合摘要，不注入原话。
    const mem = (window.MemoryStore && window.MemoryStore.recall) ? window.MemoryStore.recall() : "";
    return STR.persona + "用户刚说的话被识别为主要情绪「" + window.EmotionEngine.labelOf(emo) + "」。" +
      "当前共情要点：" + s.lead + "。要求：" + STR.rules.map((r, i) => (i + 1) + ")" + r).join("；") + "。" +
      (mem ? mem : "") + summaryOfDropped();
  };

  /**
   * 早前对话概要（r53）：把**滑出上下文窗口**的那段历史压成一行结构化摘要。
   * 动因实测：HISTORY_MAX=10 ⇒ 14 轮对话有 16 条消息对模型永久不可见（context_budget_check 拦
   * /api/chat 取证），而"陪伴感"恰建立在模型看不见的部分上。只扫情绪标签、不抄原话（X5 盯），
   * 零截断时返回 ""（X4 反向腿：常量注入会被当场抓红）。
   */
  function summaryOfDropped() {
    const drop = history.slice(0, Math.max(0, history.length - HISTORY_MAX));
    if (!drop.length) return "";
    const cnt = {};
    let crisis = 0;
    for (const m of drop) {
      if (m.role !== "user") continue;
      const e = window.EmotionEngine.scan(String(m.content || ""));
      if (e.crisis) { crisis += 1; continue; }
      const k = window.EmotionEngine.labelOf(e.emotion);
      cnt[k] = (cnt[k] || 0) + 1;
    }
    const top = Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a] || (a < b ? -1 : 1)).slice(0, 3);
    return "早前对话概要：此前 " + drop.length + " 条消息未逐条送入上下文；" +
      "情绪分布 " + (top.length ? top.map(k => k + "×" + cnt[k]).join("、") : "无词典命中") +
      "；其间危机信号 " + crisis + " 次。请勿复述本概要，自然承接即可。";
  }
  /** 本轮被概要替代的条数（供界面标注，与 SYSTEM 内同一次计算口径一致） */
  function droppedCount() { return Math.max(0, history.length - HISTORY_MAX); }

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
      cs.temperature ?? 0, cs.maxTokens ?? 40, null, CLASSIFY_TIMEOUT_MS
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
    // 后端 /api/emotion 可用时以后端为准（消除 JS/Java 两份真相），不可用即回落本地；
    // 危机词在 EmotionRemote 内部先本地短路，不会因为网络而延迟拦截。
    const cls = window.EmotionRemote
      ? await window.EmotionRemote.classifyWithBackend(text, classifyEmotion)
      : { result: await classifyEmotion(text), from: "local" };
    const { lex, final, path } = cls.result;
    const emoSrc = cls.result.src || "local";
    const emo = final.emotion, intensity = final.intensity;
    // 次情绪一并入库：星图重放要能复现「主色 n 颗 + 次色 n/2 颗」的原始点亮形态
    const secondary = window.EmotionEngine.secondaryOf(lex.all, emo);
    if (emo === "crisis") {
      remember(text, CRISIS_REPLY);
      window.MemoryStore.record({ emotion: "crisis", intensity: 1, text: text.slice(0, 60) });
      return { reply: CRISIS_REPLY, emotion: "crisis", mode: "guard", path, latency: 0, lexAll: lex.all, emoSrc };
    }
    let reply, mode, streamed = false;
    // 记录"本轮发给模型前已存在的记忆条数"：record 在之后才写，所以这里取到的是**此前**的条数
    const memBefore = (window.MemoryStore && window.MemoryStore.count) ? window.MemoryStore.count() : 0;
    const dropBefore = droppedCount();   // 同理：概要替代掉的条数要在 remember 之前取
    if (isOnline()) {
      try {
        reply = await onlineReply(text, emo, onDelta);
        mode = "model";
        llmBad = false;
        streamed = !!onDelta;
      } catch { reply = offlineReply(emo); mode = "fallback"; llmBad = true; }
    } else {
      reply = offlineReply(emo); mode = "offline";
    }
    const latency = Math.round(performance.now() - t0);
    remember(text, reply);
    window.MemoryStore.record({ emotion: emo, intensity, secondary, text: text.slice(0, 60) });
    // memory/dropped 只在**真的带着它们发给了模型**时才非零：降级/离线模板没走 LLM，标了就是说谎
    return { reply, emotion: emo, intensity, mode, path, latency, secondary, lexAll: lex.all, streamed,
             emoSrc, memory: mode === "model" ? memBefore : 0,
             dropped: mode === "model" ? dropBefore : 0 };
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

  return { respond, classifyEmotion, isOnline, setCfg, getCfg, getHistory, droppedCount, strategyInfo,
           llmBad: () => llmBad };   // r51：徽章要能反映"配了在线但刚降级过"，否则会说谎
})();
