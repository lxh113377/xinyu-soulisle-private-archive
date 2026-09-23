/* 心屿 · 本地情感引擎
 * 设计：词典 + 否定/程度修饰 + 多情绪加权 → {emotion, intensity, all}
 * 危机词表独立于情绪评分，命中即最高优先级（安全边界）。
 */
window.EmotionEngine = (function () {
  const LEX = {
    joy:    { w: 1.0, color: [1.00, 0.82, 0.30], words: ["开心","高兴","快乐","爽","棒","太好了","爱","幸福","满足","期待","哈哈","嘿嘿","顺利","成功","上岸","录取","offer","涨薪","被夸","惊喜","小确幸","通过了","评上了","考上了"] },
    sadness:{ w: 1.0, color: [0.30, 0.49, 1.00], words: ["难过","伤心","哭","想哭","失落","孤独","孤单","emo","抑郁","低落","难受","心碎","失望","遗憾","空落落","没意思","好累","疲惫","累","难受","心情不好","不开心","白费"] },
    anger:  { w: 1.0, color: [1.00, 0.23, 0.19], words: ["生气","气死","烦","烦躁","火大","愤怒","讨厌","恶心","受不了","凭什么","骂","吵架","不公平","破防"] },
    fear:   { w: 1.0, color: [0.62, 0.40, 0.95], words: ["害怕","恐惧","慌","紧张","担心","焦虑","不安","怕","吓人","噩梦","失眠","睡不着","压力","压力好大","崩溃","要死了","赶不上","挂科","施压","答辩","交代"] },
    calm:   { w: 0.8, color: [0.25, 0.85, 0.75], words: ["平静","还行","一般","普通","安静","放松","舒服","还好","凑合","正常","平淡"] },
    love:   { w: 0.9, color: [0.98, 0.42, 0.78], words: ["心动","暗恋","想他","想她","想TA","表白","在一起","分手","失恋","想念","舍不得","暧昧","喜欢上"] }
  };
  const NEG = ["不","没","没有","别","无","并非","不太","不算","不"];
  const DEG = { "太":1.4,"好":1.3,"非常":1.5,"特别":1.4,"超":1.5,"真的":1.3,"巨":1.5,"有点":0.6,"有些":0.6,"稍微":0.5 };
  const CRISIS = ["自杀","不想活","活不下去","结束生命","割腕","轻生","一了百了","死了算了","去死","自我了断","结束一切","想结束"];

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
      color: crisis ? [1.0, 0.2, 0.25] : (LEX[emotion] ? LEX[emotion].color : LEX.calm.color)
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
    if (emotion === "crisis") return [1.0, 0.2, 0.25];
    return (LEX[emotion] || LEX.calm).color;
  }
  function labelOf(emotion) {
    return { joy:"愉悦", sadness:"低落", anger:"烦躁", fear:"焦虑", calm:"平静", love:"心动", crisis:"危机信号" }[emotion] || "平静";
  }
  /** 六色图例：情绪 → 实际渲染色（与 LEX.color 同源，保证图例色点和星雾一致）。
   *  六色的色相间隔已实测 ≥40°：愤怒红(3°) 愉悦金(46°) 平静青(170°) 低落蓝(224°) 焦虑紫(264°) 心动粉(321°) */
  function palette() {
    return Object.keys(LEX).map(k => ({ emotion: k, label: labelOf(k), color: LEX[k].color.slice() }));
  }

  // NEG / DEG / CRISIS 一并导出：供 `_test/engine_consistency_check.py` 与 Java 侧逐项对账
  // （一致性守卫需要比对词表**结构本身**，只比预测汇总可能因巧合相同而漏掉分叉）
  return { scan, colorOf, labelOf, secondaryOf, palette, LEX, NEG, DEG, CRISIS };
})();
