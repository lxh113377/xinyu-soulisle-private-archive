/* 心屿 · 本地情感引擎
 * 设计：词典 + 否定/程度修饰 + 多情绪加权 → {emotion, intensity, all}
 * 危机词表独立于情绪评分，命中即最高优先级（安全边界）。
 *
 * ⚠️ 词表不再内置在这里：唯一真相源是 `src/data/emotion-lexicon.js`
 *    （window.__XINYU_LEXICON__），Java 侧 `EmotionLexicon.java` 读的是**同一份文件**。
 *    改词表只改那一份，然后跑 `python _test/engine_consistency_check.py`。
 */
window.EmotionEngine = (function () {
  const SRC = (typeof window !== "undefined" && window.__XINYU_LEXICON__) || null;
  if (!SRC) {
    throw new Error(
      "[EmotionEngine] 词表未加载：请确认 index.html 在 emotion-engine.js 之前引入 data/emotion-lexicon.js"
    );
  }

  const LEX = {};
  for (const [emo, v] of Object.entries(SRC.lex)) {
    LEX[emo] = { w: v.weight, color: v.color, words: v.words };
  }
  const NEG = SRC.neg;
  const DEG = SRC.deg;
  const CRISIS = SRC.crisis;
  const LABELS = SRC.labels;
  const CRISIS_COLOR = SRC.crisisColor;

  /**
   * 否定判定（2026-09-23 修缺陷）：否定词的字符若**被程度副词覆盖**，则该否定词不生效。
   * - 背景：NEG 含「别」，而取词窗口是「词前 3 字」⇒「心里【特别】难受」里「特别」的「别」
   *   被当成否定词，sadness 乘 −0.7 反号后归零，最终误判成 anger（评委输入「我特别难受」必翻车）。
   * - 修正后：「特别难受」→ 程度副词占位，否定不生效（正确）；
   *           「别难过」  → 窗口内无程度副词，否定照常生效（正确，保留）。
   */
  /* 否定判定缓存：hasNegation 是 before（≤3 字窗口）的纯函数，同窗重复命中直接取缓存。
   * 同一条消息里同一窗口会被每个候选词各算一次，缓存后只算一次，结果逐字一致。 */
  const negCache = new Map();
  function hasNegation(before) {
    if (negCache.has(before)) return negCache.get(before);
    const degSpans = [];
    for (const d of Object.keys(DEG)) {
      let p = before.indexOf(d);
      while (p !== -1) { degSpans.push([p, p + d.length]); p = before.indexOf(d, p + 1); }
    }
    let hit = false;
    for (const n of NEG) {
      let q = before.indexOf(n);
      while (q !== -1) {
        const covered = degSpans.some(([a, b]) => q < b && q + n.length > a);
        if (!covered) { hit = true; break; }
        q = before.indexOf(n, q + 1);
      }
      if (hit) break;
    }
    negCache.set(before, hit);
    return hit;
  }

  function scan(text) {
    const scores = {};
    for (const [emo, cfg] of Object.entries(LEX)) {
      let s = 0;
      for (const w of cfg.words) {
        let idx = text.indexOf(w);
        while (idx !== -1) {
          const before = text.slice(Math.max(0, idx - 3), idx);
          let mult = 1;
          if (hasNegation(before)) mult = -0.7;                     // 否定反转
          for (const [d, m] of Object.entries(DEG)) if (before.includes(d)) mult *= m;
          s += cfg.w * mult;
          idx = text.indexOf(w, idx + w.length);
        }
      }
      if (s > 0) scores[emo] = s;
    }
    const crisis = CRISIS.some(w => text.includes(w));
    let emotion = "calm", intensity = 0.25;
    const entries = Object.entries(scores).sort((a, b) => b[1] - a[1]);
    if (entries.length) {
      emotion = entries[0][0];
      intensity = Math.min(1, 0.3 + entries[0][1] * 0.25);
    }
    return {
      crisis,
      emotion: crisis ? "crisis" : emotion,
      intensity: crisis ? 1 : intensity,
      all: entries.map(([e, v]) => ({ emotion: e, score: +v.toFixed(2) })),
      color: crisis ? CRISIS_COLOR.slice() : (LEX[emotion] ? LEX[emotion].color : LEX.calm.color)
    };
  }

  /** 次情绪判定：all 中除主情绪外的第一名，且强度须达到主情绪的 40%，
   *  否则按单一情绪处理（避免把噪声词渲染成第二种星雾颜色）。 */
  function secondaryOf(all, main) {
    if (!all || !all.length) return null;
    const mainItem = all.find(x => x.emotion === main);
    const rest = all.filter(x => x.emotion !== main);
    if (!mainItem || !rest.length) return null;
    return rest[0].score >= mainItem.score * 0.4 ? rest[0].emotion : null;
  }

  function colorOf(emotion) {
    if (emotion === "crisis") return CRISIS_COLOR.slice();
    return (LEX[emotion] || LEX.calm).color;
  }
  function labelOf(emotion) {
    return LABELS[emotion] || "平静";
  }
  /** 六色图例：情绪 → 实际渲染色（与 LEX.color 同源，保证图例色点和星雾一致）。
   *  六色的色相间隔已实测 ≥40°：愤怒红(3°) 愉悦金(46°) 平静青(170°) 低落蓝(224°) 焦虑紫(264°) 心动粉(321°) */
  function palette() {
    return Object.keys(LEX).map(k => ({ emotion: k, label: labelOf(k), color: LEX[k].color.slice() }));
  }

  // LEX / NEG / DEG / CRISIS 一并导出：供 `_test/engine_consistency_check.py` 与 Java 侧逐项对账
  // （一致性守卫需要比对词表**结构本身**，只比预测汇总可能因巧合相同而漏掉分叉）
  return { scan, colorOf, labelOf, secondaryOf, palette, LEX, NEG, DEG, CRISIS };
})();
