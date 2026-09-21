/* 心屿 · 对话智能体
 * 共情链路：情绪识别(本地) → 策略选择 → 在线 LLM(OpenAI 兼容) 生成 → 失败降级离线共情模板
 * 降级必须显式标注，禁止把模板伪装成在线 AI。
 */
window.ChatAgent = (function () {
  const CFG_KEY = "peiliao.cfg.v1";
  const HIS_KEY = "peiliao.history.v1";
  const HISTORY_MAX = 10;
  let history = loadHistory();

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

  /* 统一 LLM 请求：proxy 模式走同源 /api/chat（密钥在云端 Function）；否则前端直连（本地演示） */
  async function llmFetch(messages, temperature, max_tokens) {
    const c = cfg();
    if (c.proxy) {
      const res = await fetch(c.proxy, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, temperature, max_tokens })
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }
    const res = await fetch(c.base.replace(/\/$/, "") + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + c.key },
      body: JSON.stringify({ model: c.model, messages, temperature, max_tokens })
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  const CRISIS_REPLY =
    "我听到了你现在真的很痛苦，谢谢你愿意说出来。这种时候你不需要一个人扛。\n\n" +
    "如果你出现了伤害自己的念头，请立刻联系专业的人：\n" +
    "· 全国心理援助热线：12356（24 小时）\n" +
    "· 北京心理危机研究与干预中心：010-82951332\n" +
    "· 生命热线：400-161-9995\n\n" +
    "我会一直在这里陪你，但请给专业的人一个帮你的机会。现在身边有可以叫一声的人吗？";

  const SYSTEM = (emo) =>
    "你是「心屿」，一个温和的大学生情感陪伴伙伴。用户刚说的话被识别为主要情绪「" +
    window.EmotionEngine.labelOf(emo) + "」。要求：" +
    "1) 先共情反映用户的感受，再轻轻陪伴展开，不说教、不评判；" +
    "2) 回复 60-120 字，口语化、有温度，可用一个具体的意象；" +
    "3) 结尾可抛出一个开放式的小问题延续对话；" +
    "4) 你不是心理咨询师，不做诊断；涉及自伤他伤风险时引导求助热线。";

  const TEMPLATES = {
    joy:    ["听起来今天是个好日子！这份开心值得被放大一点——最想庆祝的是哪一刻？", "哇，能感觉到你语气里的光。这样的好状态，想和谁分享？"],
    sadness:["难过的时候不用急着好起来。我在这儿，你想说多少，我听多少。", "心里空落落的感觉我接住了。今天发生了什么，让你这么累？"],
    anger:  ["这事儿确实让人上火。先骂出来没关系，我陪你把这口气顺一顺。", "生气说明你在意。最让你受不了的那个点是什么？"],
    fear:   ["压力大的时候，呼吸可以慢一点。你说的那几件担心的事，哪一件最大？", "慌是正常的，说明你在乎结果。我们一起把它拆小一点好不好？"],
    calm:   ["平平淡淡的一天也挺好。有没有什么小事，是你最近想做还没做的？", "安静的时候最适合想想自己。今天有什么想和我聊聊的吗？"],
    love:   ["心动这种事，藏不住也正常。想说说是谁，让你这样惦记吗？", "想念一个人的时候，心里是又甜又酸的。你们最近有联系吗？"]
  };

  async function offlineReply(text, emo) {
    const pool = TEMPLATES[emo] || TEMPLATES.calm;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  async function onlineReply(text, emo) {
    const messages = [{ role: "system", content: SYSTEM(emo) }];
    for (const h of history.slice(-HISTORY_MAX)) messages.push(h);
    messages.push({ role: "user", content: text });
    const data = await llmFetch(messages, 0.85, 220);
    const content = data?.choices?.[0]?.message?.content;
    if (!content) throw new Error("empty");
    return content.trim();
  }

  const EMOTIONS = ["joy","sadness","anger","fear","calm","love"];
  const CLASSIFY_SYS = "你是情绪分类器。从 joy(愉悦)/sadness(低落)/anger(烦躁)/fear(焦虑)/calm(平静)/love(心动) 中选一个主导情绪，只输出 JSON：{\"emotion\":\"...\",\"intensity\":0到1的小数}。示例：输入「论文被拒了三次，感觉努力全白费」输出 {\"emotion\":\"sadness\",\"intensity\":0.8}；输入「今天天气不错」输出 {\"emotion\":\"calm\",\"intensity\":0.2}。";

  async function llmClassify(text) {
    const data = await llmFetch(
      [{ role: "system", content: CLASSIFY_SYS }, { role: "user", content: text.slice(0, 200) }],
      0, 40
    );
    const raw = data?.choices?.[0]?.message?.content || "";
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

  async function respond(text) {
    const { lex, final, path } = await classifyEmotion(text);
    const emo = final.emotion, intensity = final.intensity;
    // 次情绪一并入库：星图重放要能复现「主色 n 颗 + 次色 n/2 颗」的原始点亮形态
    const secondary = window.EmotionEngine.secondaryOf(lex.all, emo);
    if (emo === "crisis") {
      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: CRISIS_REPLY });
      saveHistory();
      window.MemoryStore.record({ emotion: "crisis", intensity: 1, text: text.slice(0, 60) });
      return { reply: CRISIS_REPLY, emotion: "crisis", mode: "guard", path, latency: 0 };
    }
    const t0 = performance.now();
    let reply, mode;
    if (isOnline()) {
      try { reply = await onlineReply(text, emo); mode = "model"; }
      catch { reply = await offlineReply(text, emo); mode = "fallback"; }
    } else {
      reply = await offlineReply(text, emo); mode = "offline";
    }
    const latency = Math.round(performance.now() - t0);
    history.push({ role: "user", content: text });
    history.push({ role: "assistant", content: reply });
    saveHistory();
    window.MemoryStore.record({ emotion: emo, intensity, secondary, text: text.slice(0, 60) });
    return { reply, emotion: emo, intensity, mode, path, latency, secondary };
  }

  function setCfg(c) { saveCfg(c); history = []; saveHistory(); }
  function getHistory() { return history.slice(); }
  function getCfg() { const c = cfg(); return { base: c.base || "", key: "", model: c.model || "" }; }

  return { respond, classifyEmotion, isOnline, setCfg, getCfg, getHistory };
})();
