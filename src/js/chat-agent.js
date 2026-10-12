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

  /* 心理学知识库注入（r113，老大定的「回答更专业有据」）：
   * 数据源 = src/data/psych-kb.js（_test/psych_kb_build.py 生成；E 级未查证条目已在构建期排除）。
   * 触发两条路：用户的话与条目标题/摘要的字符二元组重合 ≥2（聊到了库覆盖的话题），
   * 或用户在**求解释**（问号/为什么/原理…）且条目自动关联了当前情绪 —— 纯倾诉轮不注入，
   * 免得共情回复变成心理课（persona 规则禁说教）。
   * 体量硬约束：context_budget_check X3 把 system 段钉在 1600 字符 ⇒ 只用剩余量，
   * 挤不下就本轮不注入，绝不挤占记忆/概要段（那两段是判据钉死的既有能力）。 */
  function kbBlockFor(emo, userText, budget) {
    const KB = window.__XINYU_PSYCH_KB__;
    if (!KB || !KB.entries || !KB.entries.length || budget < 220) return "";
    const hay = String(userText || "");
    const grams = new Set();
    for (let i = 0; i < hay.length - 1; i++) {
      const g = hay.slice(i, i + 2);
      if (/[\u4e00-\u9fa5A-Za-z]/.test(g[0]) && /[\u4e00-\u9fa5A-Za-z]/.test(g[1])) grams.add(g);
    }
    if (!grams.size) return "";
    const curious = /[?？]|为什么|怎么|如何|原理|科学|是不是|心理学/.test(hay);
    const scored = [];
    for (const e of KB.entries) {
      const txt = e.title + "，" + e.summary;
      let hits = 0;
      grams.forEach((g) => { if (txt.indexOf(g) >= 0) hits++; });
      const relHit = e.rel && e.rel.indexOf(emo) >= 0 ? 1 : 0;
      if (hits >= 2 || (curious && relHit)) scored.push({ e: e, s: relHit * 2 + hits });
    }
    scored.sort((a, b) => b.s - a.s);
    const head = "可依据的心理学知识条目（回答可自然融入，不说教；句末可标〔依据:编号·级〕；条目未覆盖的专业内容不要编造文献或数据，用弱化表述；D级内容须呈现争议双方）：";
    let block = "", used = head.length, n = 0;
    for (const p of scored) {
      if (n >= 3) break;
      const item = "\n[" + p.e.id + "·" + p.e.level + "]" + p.e.title + "：" + p.e.summary + p.e.content;
      if (used + item.length > budget) break;
      block += item; used += item.length; n++;
    }
    return n ? head + block : "";
  }

  /* 表达语料库注入（r117，老大定的「每轮都给候选」）：
   * 数据源 = src/data/wit-quotes.js（_test/wit_quotes_build.py 生成；E 级构建期已排除）。
   * 与 kbBlockFor 的差异：KB 是「按需给」（求解释才给），quote 是「每轮都给」——候选池按
   * 当前情绪匹配（含"通用"），话题二元组命中加权排序，取 ≤5 条短句。
   * 引用规则唯一源 = emotion-strategy.js 的 quoteRules（本函数只做拼接，不复制文案）；
   * 规则缺失（quoteRules 空）⇒ 不注入（由 _test/strategy_check.py 钉住必须存在，禁静默降级双源）。 */
  function quoteBlockFor(emo, userText, budget) {
    const Q = window.__XINYU_WIT_QUOTES__;
    // rulesOnly 为评测专用旗标（_test/quote_eval.py 归因臂注入，生产数据件永不设置）：
    // true ⇒ 只注入 head+规则、零候选（归因「规则文案本身」的作用）；旗标缺省时本行
    // 与旧逻辑逐字节等价（仍要求 entries 非空）。
    if (!Q || (Q.rulesOnly !== true && (!Q.entries || !Q.entries.length)) || budget < 120) return "";
    const rules = (STR.quoteRules || []).join("；");
    if (!rules) return "";
    const hay = String(userText || "");
    const grams = new Set();
    for (let i = 0; i < hay.length - 1; i++) {
      const g = hay.slice(i, i + 2);
      if (/[\u4e00-\u9fa5A-Za-z]/.test(g[0]) && /[\u4e00-\u9fa5A-Za-z]/.test(g[1])) grams.add(g);
    }
    const scored = [];
    for (const e of (Q.rulesOnly === true ? [] : Q.entries)) {
      const emoHit = e.emo.indexOf("all") >= 0 || e.emo.indexOf(emo) >= 0;
      let hits = 0;
      grams.forEach((g) => { if (e.quote.indexOf(g) >= 0) hits++; });
      if (!emoHit && hits < 2) continue;   // 情感不匹配且话题不沾边：不进候选
      scored.push({ e: e, s: (emoHit ? 2 : 0) + hits });
    }
    scored.sort((a, b) => b.s - a.s || (a.e.id < b.e.id ? -1 : 1));
    // head 与 emotion-strategy.quoteRules 的分工：head 给"这是什么、可以怎么用"的引导，
    // rules 给边界。r117 首轮全量盲评实测：纯禁令措辞会让模型过度避险（30 轮零引用）——
    // 因此 head 明确"可化用半句/取其意"（低门槛形态）与"不必强用"（边界）。
    const head = "可化用的表达素材（恰好契合时可化用半句或取其意，给回复添一点余味；不必强用。规则：" + rules + "）：";
    let block = "", used = head.length, n = 0;
    for (const p of scored) {
      if (n >= 5) break;
      const item = "\n[" + p.e.id + "·" + p.e.level + "]" + p.e.quote;
      if (used + item.length > budget) break;
      block += item; used += item.length; n++;
    }
    return (n || Q.rulesOnly === true) ? head + block : "";
  }

  const SYSTEM = (emo, userText) => {
    const s = strategyOf(emo);
    // 长期记忆注入（r52）：MemoryStore 原本**只写不读**，"跨设备记住你"只成立在展示层。
    // 只注入聚合摘要，不注入原话。
    const mem = (window.MemoryStore && window.MemoryStore.recall) ? window.MemoryStore.recall() : "";
    const base = STR.persona + "用户刚说的话被识别为主要情绪「" + window.EmotionEngine.labelOf(emo) + "」。" +
      "当前共情要点：" + s.lead + "。要求：" + STR.rules.map((r, i) => (i + 1) + ")" + r).join("；") + "。" +
      (mem ? mem : "") + summaryOfDropped();
    /* r117 预算切分：quote 保底优先（「每轮给候选」要成立），kb 用剩余（<220 自动让位）。 */
    const remain = 1600 - base.length - 40;
    const quoteBudget = Math.min(280, Math.max(180, Math.floor(remain * 0.45)));
    const qb = remain >= 180 ? quoteBlockFor(emo, userText, quoteBudget) : "";
    return base + qb + kbBlockFor(emo, userText, remain - (qb ? qb.length : 0));
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
    const messages = [{ role: "system", content: SYSTEM(emo, text) }];
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
  // r100：轮次完成态由产品自己报数，替掉测试里的定长等待。只计数，异常也过 finally。
  let pendingTurns = 0;
  window.__pendingTurns = 0;
  async function turn(fn) {
    window.__pendingTurns = ++pendingTurns;
    try { return await fn(); } finally { window.__pendingTurns = --pendingTurns; }
  }

  async function respondCore(text, onDelta) {
    const t0 = performance.now(); // 计时起点含情绪分类：latency 如实反映整轮等待
    // 后端 /api/emotion 可用时以后端为准（消除 JS/Java 两份真相），不可用即回落本地；
    // 危机词在 EmotionRemote 内部先本地短路，不会因为网络而延迟拦截。
    const cls = window.EmotionRemote
      ? await window.EmotionRemote.classifyWithBackend(text, classifyEmotion)
      : { result: await classifyEmotion(text), from: "local" };
    const { lex, final, path } = cls.result;
    const emoSrc = cls.result.src || "local";
    const emo = final.emotion, intensity = final.intensity;
    /* r87：表情是**并列第三路**——只标注，不参与裁决。
     * 为什么不让表情覆盖 LLM/词典：表情识别的准确率低于文本双路，让它参与裁决
     * 只会把已标定的文本链路往回拖；而"如实告诉你两路不一致"本身就是价值。
     * 取数口径：只取**仍在有效期内**的读数（FaceEngine.last），拿几秒前的旧脸标新话属于说谎。
     * love 心动表情侧判不出来（见 face-smile-rules 的 undetectable）⇒ 记 n/a 而不是"不一致"。 */
    const face = (window.FaceEngine && window.FaceEngine.last) ? window.FaceEngine.last() : null;
    const divergence = !face ? "unknown" : (emo === "love" ? "n/a" : (face.emotion === emo ? "agree" : "disagree"));
    // 次情绪一并入库：星图重放要能复现「主色 n 颗 + 次色 n/2 颗」的原始点亮形态
    const secondary = window.EmotionEngine.secondaryOf(lex.all, emo);
    if (emo === "crisis") {
      remember(text, CRISIS_REPLY);
      window.MemoryStore.record({ emotion: "crisis", intensity: 1, text: text.slice(0, 60) });
      return { reply: CRISIS_REPLY, emotion: "crisis", mode: "guard", path, latency: 0, lexAll: lex.all, emoSrc,
               face, divergence };
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
             emoSrc, face, divergence, memory: mode === "model" ? memBefore : 0,
             dropped: mode === "model" ? dropBefore : 0 };
  }

  /* 对外仍叫 respond：包一层 turn()，每轮起止就成了可等的读数（r100） */
  async function respond(text, onDelta) { return turn(() => respondCore(text, onDelta)); }

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
