// 心屿情绪引擎评测：词典层准确率（技术实现维度的可复现数字）
// 用法: node emotion_eval.js  → 输出 JSON 指标
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const sandbox = { window: {}, console };
vm.createContext(sandbox);
// SSOT（2026-09-24 e79025b 后）：词表唯一真相源是 src/data/emotion-lexicon.js，须先于引擎注入
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "src", "data", "emotion-lexicon.js"), "utf8"), sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "src", "js", "emotion-engine.js"), "utf8"), sandbox);
const E = sandbox.window.EmotionEngine;

const ds = JSON.parse(fs.readFileSync(path.join(__dirname, "emotion-eval-dataset.json"), "utf8"));
let correct = 0;
const misses = [];
const perClass = {};
for (const it of ds.items) {
  const pred = E.scan(it.text).emotion;
  perClass[it.expect] = perClass[it.expect] || { n: 0, ok: 0 };
  perClass[it.expect].n++;
  if (pred === it.expect) { correct++; perClass[it.expect].ok++; }
  else misses.push({ text: it.text, expect: it.expect, pred });
}
const total = ds.items.length;
console.log(JSON.stringify({
  total,
  accuracy: +(correct / total * 100).toFixed(1) + "%",
  crisis_recall: (() => {
    const c = ds.items.filter(i => i.expect === "crisis");
    const hit = c.filter(i => E.scan(i.text).crisis).length;
    return hit + "/" + c.length;
  })(),
  per_class: Object.fromEntries(Object.entries(perClass).map(([k, v]) => [k, v.ok + "/" + v.n])),
  misses
}, null, 2));
