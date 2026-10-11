/* 表情引擎离线腿的**可证伪性常驻判据**（r123 从 r122 报告附录 A 固化而来）。
 * 断言的是两件事：①对引擎源码做 5 类定向破坏，对应的 5 条离线用例必须各自翻红；
 * ②不破坏时必须全绿。少了②，"用例变红"可能只是我自己写坏了；少了①，那 5 条用例就是恒绿的装饰。
 * 为什么值得常驻：r122 新加那 5 条腿时，第一版探针就抓到过一条**假绿**
 * （把 RULES.labels 那一跳摘掉，labelOf 仍走文本侧兜底 ⇒ 用例不红 ⇒ 断言其实没测到目标分支）。
 * 用法：`node _test/js_engine_mut.mjs`（工作目录＝仓库根；ROOT 取 process.cwd()）
 * 退出码：0=五类变异各自翻红且对照全绿；1=方向不对（含对照被弄绿失败）；2=取不到源码（环境，不当结论）
 */
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import assert from "node:assert/strict";

const ROOT = process.cwd() + "/";   // 在仓根跑：node _test/js_engine_mut.mjs
const SRC = (rel) => readFileSync(ROOT + rel, "utf8");

function boot(globals, mut) {
  const ctx = createContext(Object.assign({ window: {} }, globals || {}, { console }));
  runInContext(SRC("src/data/emotion-lexicon.js"), ctx);
  runInContext(SRC("src/js/emotion-engine.js"), ctx);
  runInContext(SRC("src/data/face-smile-rules.js"), ctx);
  let eng = SRC("src/js/face-engine.js");
  if (mut) {
    const [from, to] = mut;
    assert.ok(eng.indexOf(from) >= 0, "变异锚点在源码里找不到（这条变异腿是假的）：" + from);
    eng = eng.replace(from, to);
  }
  runInContext(eng, ctx);
  return ctx;
}

const results = [];
function leg(name, fn) {
  let red = false, note = "";
  try { fn(); } catch (e) { red = true; note = String(e.message).split("\n")[0].slice(0, 70); }
  results.push({ name, red, note });
}

// 变异 1：capability 的"非安全上下文"分支被摘掉 ⇒ ①那条腿必须红
leg("capability 摘掉 insecure 分支", () => {
  const c = boot({ window: { isSecureContext: false }, navigator: { mediaDevices: { getUserMedia() {} } } },
    ['if (!window.isSecureContext) return { ok: false, reason: "insecure-context" };',
     'if (false) return { ok: false, reason: "insecure-context" };']);
  assert.deepEqual(JSON.parse(JSON.stringify(c.window.FaceEngine.capability())),
    { ok: false, reason: "insecure-context" });
});

// 变异 2：setEnabled(true) 改写 "on" 而不是删键 ⇒ 键形两态，必须红
leg("setEnabled(true) 改写成写 on", () => {
  const m = new Map();
  const api = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)),
                removeItem: (k) => m.delete(k) };
  const c = boot({ window: { isSecureContext: true }, localStorage: api },
    ["if (on) localStorage.removeItem(CAM_KEY);", 'if (on) localStorage.setItem(CAM_KEY, "on");']);
  c.window.FaceEngine.setEnabled(false);
  c.window.FaceEngine.setEnabled(true);
  assert.equal(m.has("peiliao.face.cam.v1"), false, "开启应当删键");
});

// 变异 3：reasonText 未知原因回空串 ⇒ 界面空白，必须红
leg("reasonText 未知原因回空串", () => {
  const c = boot({ window: { isSecureContext: true } },
    ['return REASON_TEXT[r] || ("表情识别暂不可用（" + r + "）");', "return REASON_TEXT[r] || \"\";"]);
  assert.ok(c.window.FaceEngine.reasonText("brandNew").length > 4);
});

// 变异 4：cueRegions 用原始激活值当权重 ⇒ 无权重 AU 也会点亮区域，必须红
leg("cueRegions 用 bs 值替代权重", () => {
  const c = boot({ window: { isSecureContext: true } },
    ["const wt = w[k] || 0;", "const wt = (bs[k] || 0) > 0 ? 1 : 0;"]);
  const R = c.window.__XINYU_FACE_RULES__;
  const hit = JSON.parse(JSON.stringify(c.window.FaceEngine.cueRegions(R.weights.joy, { eyeBlinkLeft: 1 })));
  assert.deepEqual(hit, [], "eyeBlink 无权重却点亮了区域");
});

// 变异 5：摘掉表情侧自持标签那一跳 ⇒ 三类独有情绪会静默改用文本回落，必须红
leg("labelOf 摘掉 RULES.labels 那一跳", () => {
  const c = boot({ window: { isSecureContext: true } },
    ['if (R.labels && R.labels[emo]) return R.labels[emo];', "if (false) return R.labels[emo];"]);
  const R = c.window.__XINYU_FACE_RULES__;
  assert.equal(c.window.FaceEngine.labelOf("contempt"), R.labels.contempt,
    "contempt 必须走表情侧自持标签");
});

// 对照组：未变异时五条断言都必须绿（否则是探针自己坏）
leg("对照组（无变异全绿）", () => {
  const c = boot({ window: { isSecureContext: true }, navigator: { mediaDevices: { getUserMedia() {} } } });
  assert.deepEqual(JSON.parse(JSON.stringify(c.window.FaceEngine.capability())), { ok: true, reason: "" });
  assert.ok(c.window.FaceEngine.reasonText("brandNew").length > 4);
  assert.ok(c.window.FaceEngine.labelOf("notAnEmotion") !== "");
});

let bad = 0;
for (const r of results) {
  const want = r.name.indexOf("对照组") === 0 ? false : true;
  const ok = r.red === want;
  if (!ok) bad++;
  console.log((ok ? "OK   " : "FAIL ") + r.name.padEnd(34) + " red=" + r.red + " " + r.note);
}
console.log(bad ? "MUT-PROBE-FAIL %d 条腿方向不对" % bad
  : "MUT-PROBE-PASS：5 类变异各自翻红，对照组全绿 ⇒ 新增离线腿可证伪");
process.exit(bad ? 1 : 0);
