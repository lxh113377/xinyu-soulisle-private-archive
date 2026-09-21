/* 心屿 · 导出 JS 侧情绪引擎的「词表结构 + 逐条预测」供一致性守卫比对
 *
 * 用法: node _test/engine_lexicon_dump.js   → stdout 输出 JSON
 * 与 Java 侧 `GET /api/emotion/lexicon` + `GET /api/emotion/eval?detail=1` **同构**。
 *
 * 为什么单独成文件（不内嵌进 python）：PowerShell 里内嵌带引号的脚本会破坏整条命令，
 * 且同条命令中排在它前面的动作会被一起丢弃（本项目实测踩过的坑，见 memory 速查 ①）。
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const sandbox = { window: {}, console };
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "..", "src", "js", "emotion-engine.js"), "utf8"),
  sandbox
);
const E = sandbox.window.EmotionEngine;

const lex = {};
for (const [k, cfg] of Object.entries(E.LEX)) {
  lex[k] = { weight: cfg.w, color: cfg.color, words: cfg.words };
}

const ds = JSON.parse(
  fs.readFileSync(path.join(__dirname, "emotion-eval-dataset.json"), "utf8")
);
const results = ds.items.map((it) => ({
  text: it.text,
  expect: it.expect,
  pred: E.scan(it.text).emotion,
}));

/* 汇总指标：与 Java 侧 `GET /api/emotion/eval` 的算法逐项对齐
 * （写法必须同构，否则会比出"假分叉"—— 例如 JS 用 toFixed(1) 而 Java 用 Math.round(x*10)/10，
 *  两者对 94.4 这种值等价；但顺序、空值语义必须一致） */
let correct = 0;
const perClass = {};
const misses = [];
for (const r of results) {
  perClass[r.expect] = perClass[r.expect] || [0, 0];
  perClass[r.expect][1]++;
  if (r.pred === r.expect) {
    correct++;
    perClass[r.expect][0]++;
  } else {
    misses.push({ text: r.text, expect: r.expect, pred: r.pred });
  }
}
const crisisItems = results.filter((r) => r.expect === "crisis");
const crisisHit = crisisItems.filter((r) => E.scan(r.text).crisis).length;

const total = results.length;
const summary = {
  total,
  accuracy: ((correct / total) * 100).toFixed(1) + "%",
  crisis_recall: crisisHit + "/" + crisisItems.length,
  per_class: Object.fromEntries(
    Object.entries(perClass).map(([k, v]) => [k, v[0] + "/" + v[1]])
  ),
  misses,
};

process.stdout.write(
  JSON.stringify(
    { lex, neg: E.NEG, deg: E.DEG, crisis: E.CRISIS, results, ...summary },
    null,
    2
  )
);
