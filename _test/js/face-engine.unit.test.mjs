/* 心屿 · 面部表情引擎 JS 侧单元测试（r87）
 *
 * 与 `emotion-engine.unit.test.mjs` 同通道：`node --test` + `node:vm`（Node 自带，零依赖零打包器），
 * 被测对象是浏览器全局脚本（`window.FaceEngine`），不是 ES Module。
 *
 * 为什么这一族断言必须存在（老师提的验证难题）：
 *   「表情大笑，怎么验证是真开心还是强颜欢笑」—— 答案不能是口头保证，得是一条**可证伪**的判据：
 *     ① 真笑向量 → duchenne，强颜欢笑向量 → social + masking（语义正确）；
 *     ② 把阈值抬高 → 同一真笑向量判成 none（证明阈值真在起作用，判据不是恒真）；
 *     ③ 常量卷：crisis 恒 false、love 永不输出、intensity ∈ [0,1]。
 *   ①②合起来才叫"能验证"：只有①的话，一条 `return "duchenne"` 也能全绿。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const ROOT_URL = new URL("../../", import.meta.url);
const SRC = (rel) => readFileSync(new URL(rel, ROOT_URL), "utf8");

function makeCtx() {
  const ctx = createContext({ window: {}, console });
  runInContext(SRC("src/data/emotion-lexicon.js"), ctx);
  runInContext(SRC("src/js/emotion-engine.js"), ctx);
  runInContext(SRC("src/data/face-smile-rules.js"), ctx);
  runInContext(SRC("src/js/face-engine.js"), ctx);
  return ctx;
}
const ctx = makeCtx();
const FE = ctx.window.FaceEngine;
const RULES = ctx.window.__XINYU_FACE_RULES__;
// 跨 realm 归一（同 emotion-engine 那族的踩坑）：把返回值当数据过一道 JSON
const read = (bs) => JSON.parse(JSON.stringify(FE.read(bs)));

/** 造一个只有指定维度非零的 blendshape 向量（其余按 MediaPipe 的 52 维默认 0） */
const vec = (o) => Object.assign({}, o);

test("夹具自证：判据与引擎真的被载入了（拿不到就整族失效）", () => {
  assert.ok(RULES && Object.keys(RULES.weights || {}).length >= 7, "face-smile-rules 未载入或权重为空");
  assert.ok(FE && typeof FE.read === "function", "FaceEngine.read 不可调用");
  assert.ok(typeof FE.smileKind === "function" && typeof FE.scores === "function", "判据纯函数缺失");
  assert.ok(RULES.undetectable.includes("love"), "love 必须在 undetectable 里（表情侧判不出来要如实声明）");
  // r102：表情侧三类独有情绪必须有自持配色，且 family 必须映射到文本六情绪
  // （分歧标注靠它对齐；缺了会让"表情说 contempt、文字无此类"变成噪声）
  for (const e of ["surprise", "disgust", "contempt"]) {
    assert.ok(RULES.colors && RULES.colors[e], e + " 缺自持配色");
    assert.ok(Array.isArray(RULES.colors[e]) && RULES.colors[e].length === 3, e + " 配色必须是 RGB 三元组");
    assert.ok(RULES.family && RULES.family[e], e + " 缺 family 映射（分歧标注要用）");
  }
});

test("真笑（AU12 + AU6/AU7 眼周参与）→ joy · duchenne", () => {
  const v = read(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6,
    cheekSquintRight: 0.6, eyeSquintLeft: 0.5, eyeSquintRight: 0.5 }));
  assert.equal(v.emotion, "joy");
  assert.equal(v.smile.kind, "duchenne");
  assert.equal(v.smile.masking, false);
  assert.ok(v.intensity > 0.5, "真笑强度应显著：实测 " + v.intensity);
  assert.equal(v.crisis, false, "表情侧永不判危机");
});

test("强颜欢笑（嘴笑 + 眼周不参与 + 抿唇/眉心上提）→ social + masking", () => {
  const v = read(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.05,
    cheekSquintRight: 0.05, mouthPressLeft: 0.5, mouthPressRight: 0.5, browInnerUp: 0.4 }));
  assert.equal(v.emotion, "joy", "嘴在笑 ⇒ 主情绪仍是愉悦（表情只报它看到的）");
  assert.equal(v.smile.kind, "social", "眼周没参与 ⇒ 不是真笑");
  assert.equal(v.smile.masking, true, "伴紧张线索 ⇒ 标强颜欢笑嫌疑");
  // 关键对照：与真笑向量同嘴部幅度，只有眼周不同 ⇒ 判据必须给出不同结论
  const real = read(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6,
    cheekSquintRight: 0.6, eyeSquintLeft: 0.5, eyeSquintRight: 0.5 }));
  assert.notEqual(v.smile.kind, real.smile.kind, "真笑/强颜欢笑必须可分，否则判据无判别力");
});

test("社交性微笑（双侧对称、嘴在笑）→ joy，且不得被轻蔑抢走", () => {
  const v = read(vec({ mouthSmileLeft: 0.6, mouthSmileRight: 0.6,
    cheekSquintLeft: 0.05, cheekSquintRight: 0.05 }));
  assert.equal(v.emotion, "joy", "对称的笑不是轻蔑");
  assert.equal(v.smile.kind, "social");
  const ct = v.all.find((x) => x.emotion === "contempt");
  assert.equal(ct.score, 0, "对称笑时轻蔑必须严格为 0（非对称门生效）：实测 " + ct.score);
});

test("低落（嘴角下拉 + 眉心上提）→ sadness，且不误报微笑", () => {
  const v = read(vec({ mouthFrownLeft: 0.8, mouthFrownRight: 0.8, browInnerUp: 0.6,
    mouthSmileLeft: 0.05, mouthSmileRight: 0.05 }));
  assert.equal(v.emotion, "sadness");
  assert.equal(v.smile.kind, "none");
  assert.ok(v.intensity > 0.4, "低落强度应显著：实测 " + v.intensity);
});

test("烦躁（压眉 + 鼻翼上提）→ anger", () => {
  const v = read(vec({ browDownLeft: 0.85, browDownRight: 0.85, noseSneerLeft: 0.6, noseSneerRight: 0.6 }));
  assert.equal(v.emotion, "anger");
  assert.equal(v.crisis, false);
});

/* r102：以下三条是把 disgust / surprise / contempt 从「判不出来」修成「能判」的核心用例。
   修之前它们分别被判成 anger 0.47 / fear 1.00 / joy —— 即「情绪种类单一」的一手证据。 */
test("厌恶（鼻翼上提 + 上唇上提）→ disgust，且不被 anger 抢走", () => {
  const v = read(vec({ noseSneerLeft: 0.7, noseSneerRight: 0.7,
    mouthUpperUpLeft: 0.6, mouthUpperUpRight: 0.6 }));
  assert.equal(v.emotion, "disgust", "口鼻区组合是厌恶，不是愤怒");
  const an = v.all.find((x) => x.emotion === "anger");
  assert.ok(v.all[0].score - an.score > 0, "disgust 必须压过 anger（靠上唇上提区分）");
});

test("惊讶（眉平滑上抬 + 竖直张口）→ surprise，且不被 fear 抢走", () => {
  const v = read(vec({ jawOpen: 0.8, browInnerUp: 0.8, browOuterUpLeft: 0.7,
    browOuterUpRight: 0.7, eyeWideLeft: 0.5, eyeWideRight: 0.5 }));
  assert.equal(v.emotion, "surprise", "眉毛平滑上抬是惊讶，不是恐惧");
});

test("焦虑恐惧（睁大眼 + 横向拉唇 + **眉头皱起**）→ fear", () => {
  // 与上一条 surprise 的唯一分水岭就是 browDown：恐惧皱眉(AU1+2+4)，惊讶只上抬(AU1+2)
  const v = read(vec({ eyeWideLeft: 0.8, eyeWideRight: 0.8, jawOpen: 0.6,
    browInnerUp: 0.5, browDownLeft: 0.3, browDownRight: 0.3 }));
  assert.equal(v.emotion, "fear", "眉头皱起是恐惧的关键证据");
  const sp = v.all.find((x) => x.emotion === "surprise");
  assert.ok(v.all[0].score - sp.score > 0.1, "fear 必须明显压过 surprise：实测差 "
    + (v.all[0].score - sp.score).toFixed(3));
});

test("轻蔑（单侧嘴角上提 + 眼周不参与）→ contempt", () => {
  const v = read(vec({ mouthSmileLeft: 0.85, mouthSmileRight: 0.10,
    mouthDimpleLeft: 0.9, mouthDimpleRight: 0.10 }));
  assert.equal(v.emotion, "contempt", "单侧笑是轻蔑，不是对称的笑");
});

test("负样本（r103 拍板「乙」后的已知代价）：专注轻皱会判 anger，但必须比真愤怒弱", () => {
  // r102 时这条断言是「专注轻皱必须判 calm」。r103 用真实愤怒照（face-api.js）实测发现：
  // 真人发怒的 AU 只有 browDown 0.64/0.59 而**其余全 0**，与专注轻皱 0.40 结构完全相同、
  // 只有幅度差 —— 要求多区佐证就必然漏判真愤怒（F12 实测 anger 0/2）。
  // ⇒ 拍板「保真怒」。代价就是这里：专注时会判 anger。
  // 断言从「不许误报」改成「**误报可以，但必须比真愤怒弱**」——
  // 否则「在想事情」和「真发火」读数一样，代价就从"闪一下红"升级成"骗人"。
  const conc = read(vec({ browDownLeft: 0.4, browDownRight: 0.4 }));
  const real = read(vec({ browDownLeft: 0.64, browDownRight: 0.59 }));
  assert.equal(conc.emotion, "anger", "专注轻皱会误报 anger —— 这是 r103 拍板接受的代价");
  assert.ok(real.intensity > conc.intensity + 0.1,
    "真愤怒必须明显强于专注轻皱：实测 " + real.intensity + " vs " + conc.intensity);
});

test("负样本：说话（张口 + 说话唇形）必须判 calm", () => {
  const v = read(vec({ jawOpen: 0.5, mouthFunnel: 0.3 }));
  assert.equal(v.emotion, "calm", "张嘴说话不是恐惧");
});

test("无表情 → calm（残余量），且 gain 把它压到 0.6 附近", () => {
  const v = read(vec({}));
  assert.equal(v.emotion, "calm");
  assert.ok(Math.abs(v.intensity - 0.6) < 0.02, "calm 增益应把满残余压到 0.6：实测 " + v.intensity);
  assert.equal(v.smile.kind, "none");
});

test("强度不饱和：同一真笑向量分三档，强度必须递增", () => {
  // r102：旧版 (raw/(pos*norm)) 在 norm=0.45 下 25% 的帧顶满 1.0，中高段无分辨力
  const weak = read(vec({ mouthSmileLeft: 0.4, mouthSmileRight: 0.4, cheekSquintLeft: 0.3, cheekSquintRight: 0.3 }));
  const mid = read(vec({ mouthSmileLeft: 0.6, mouthSmileRight: 0.6, cheekSquintLeft: 0.45, cheekSquintRight: 0.45 }));
  const full = read(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6, cheekSquintRight: 0.6 }));
  assert.ok(weak.intensity < mid.intensity && mid.intensity < full.intensity,
    "强度必须随真实强度递增：实测 " + [weak.intensity, mid.intensity, full.intensity].join(" < "));
  assert.ok(full.intensity < 0.99, "中等强度的笑不该顶满（饱和）：实测 " + full.intensity);
});

test("置信度：margin 低时必须自报「读数不稳」，不是假装确定", () => {
  // 弱恐惧：fear 0.423 vs surprise 0.333，两类本就难分（实测 margin=0.090）
  // 这正是置信度该派上用场的场景 —— 承认"看不出来"，而不是假装确定。
  const v = read(vec({ eyeWideLeft: 0.5, eyeWideRight: 0.5, jawOpen: 0.4,
    browInnerUp: 0.3, browDownLeft: 0.2, browDownRight: 0.2 }));
  assert.ok(v.confidence < RULES.confidence.on, "该样本 margin 应低于门槛：实测 " + v.confidence);
  assert.equal(v.confident, false, "margin 低必须标 confident=false");
  // 对照：厌恶的主次分拉得开 ⇒ confident=true
  const clean = read(vec({ noseSneerLeft: 0.7, noseSneerRight: 0.7,
    mouthUpperUpLeft: 0.6, mouthUpperUpRight: 0.6 }));
  assert.equal(clean.confident, true, "厌恶主次分拉开，应判 confident：margin " + clean.confidence);
});

test("常量卷：crisis 恒 false · love 永不输出 · intensity ∈ [0,1] · 八类齐全", () => {
  const samples = [
    {}, { mouthSmileLeft: 1, mouthSmileRight: 1 }, { mouthFrownLeft: 1, mouthFrownRight: 1 },
    { browDownLeft: 1, browDownRight: 1, noseSneerLeft: 1, noseSneerRight: 1 },
    { eyeWideLeft: 1, eyeWideRight: 1, jawOpen: 1 }, { mouthSmileLeft: 1, mouthFrownRight: 1 },
    { noseSneerLeft: 1, noseSneerRight: 1, mouthUpperUpLeft: 1, mouthUpperUpRight: 1 },
    { mouthSmileLeft: 1, mouthDimpleLeft: 1 }
  ];
  for (const s of samples) {
    const v = read(s);
    assert.equal(v.crisis, false, "表情侧永不判危机（也永不解除危机）");
    assert.notEqual(v.emotion, "love", "love 不由表情判定");
    assert.ok(v.intensity >= 0 && v.intensity <= 1, "intensity 越界：" + v.intensity);
    assert.ok(Array.isArray(v.all) && v.all.length === RULES.emotions.length, "all 必须覆盖全部可判情绪");
    assert.ok(RULES.emotions.length >= 8, "表情侧应至少 8 类（r102 扩容目标）：实测 " + RULES.emotions.length);
  }
});

test("可证伪性：抬高阈值后同一真笑向量必须翻成 none（判据不是恒真）", () => {
  const c2 = makeCtx();
  c2.window.__XINYU_FACE_RULES__.smile.smileOn = 0.99;         // 只动一个维度
  runInContext(SRC("src/js/face-engine.js"), c2);
  const v = JSON.parse(JSON.stringify(c2.window.FaceEngine.read(
    { mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6, cheekSquintRight: 0.6 })));
  assert.equal(v.smile.kind, "none", "阈值抬到 0.99 还判微笑 ⇒ 阈值根本没参与计算");
  // 反向：把比值门槛抬到 0.99 ⇒ 真笑也要翻成 social（证明 ratio 真的在判）
  const c3 = makeCtx();
  c3.window.__XINYU_FACE_RULES__.smile.ratioOn = 0.99;
  runInContext(SRC("src/js/face-engine.js"), c3);
  const v3 = JSON.parse(JSON.stringify(c3.window.FaceEngine.read(
    { mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6, cheekSquintRight: 0.6 })));
  assert.equal(v3.smile.kind, "social", "比值门槛抬到 0.99 还判真笑 ⇒ 眼周参与根本没参与计算");
});

test("空/畸形输入不炸：read(undefined) 与未知维度都按 0 处理", () => {
  const v = read(undefined);
  assert.equal(v.emotion, "calm");
  const v2 = read({ notABlendshape: 1, mouthSmileLeft: 0.9, mouthSmileRight: 0.9 });
  assert.equal(v2.emotion, "joy");
});

/* ── r113 质量门（assessQuality/applyQuality）：画面靠不住时读数必须降档 ────────── */
// 跨 realm 归一：assessQuality/applyQuality 的返回值一律过一道 JSON（同本文件开头约定，
// 否则 deepEqual 会拿 vm realm 的 Array 原型说事）
const q = (r) => JSON.parse(JSON.stringify(r));

test("质量门四信号：暗光/糊图/侧脸/嘴部平坦各命中对应 reason，干净画面全过", () => {
  const Q = RULES.quality;
  assert.ok(Q && typeof Q.brightMin === "number", "rules.quality 缺失：质量门没有阈值就形同虚设");
  const good = q(FE.assessQuality({ luma: { mean: 0.5, variance: 0.03 }, yaw: 0.05, mouthFlatSamples: 0 }));
  assert.deepEqual(good, { ok: true, reasons: [] });
  const dark = q(FE.assessQuality({ luma: { mean: Q.brightMin - 0.01, variance: 0.03 }, yaw: 0, mouthFlatSamples: 0 }));
  assert.ok(dark.reasons.includes("lighting"));
  const bright = q(FE.assessQuality({ luma: { mean: Q.brightMax + 0.01, variance: 0.03 }, yaw: 0, mouthFlatSamples: 0 }));
  assert.ok(bright.reasons.includes("lighting"), "过曝也走 lighting");
  const blur = q(FE.assessQuality({ luma: { mean: 0.5, variance: Q.blurVarMin - 0.0001 }, yaw: 0, mouthFlatSamples: 0 }));
  assert.ok(blur.reasons.includes("blur"));
  const profile = q(FE.assessQuality({ luma: { mean: 0.5, variance: 0.03 }, yaw: Q.yawMax + 0.01, mouthFlatSamples: 0 }));
  assert.ok(profile.reasons.includes("profile"));
  const flat = q(FE.assessQuality({ luma: { mean: 0.5, variance: 0.03 }, yaw: 0, mouthFlatSamples: Q.mouthFlatSamples }));
  assert.ok(flat.reasons.includes("mouth-flat"));
  const below = q(FE.assessQuality({ luma: { mean: 0.5, variance: 0.03 }, yaw: 0, mouthFlatSamples: Q.mouthFlatSamples - 1 }));
  assert.deepEqual(below, { ok: true, reasons: [] }, "平坦样本数差一档必须放行（边界腿）");
});

test("质量门可证伪：brightMax 抬到 0 后干净画面也必须被拦（阈值真在参与计算）", () => {
  const c2 = makeCtx();
  c2.window.__XINYU_FACE_RULES__.quality.brightMax = 0.0;
  runInContext(SRC("src/js/face-engine.js"), c2);
  const r = q(c2.window.FaceEngine.assessQuality(
    { luma: { mean: 0.5, variance: 0.03 }, yaw: 0, mouthFlatSamples: 0 }));
  assert.ok(r.reasons.includes("lighting"), "brightMax=0 还判光线正常 ⇒ 阈值没参与计算");
});

test("质量门缺证据不乱报：luma 取不到（null）时不得报 lighting/blur", () => {
  const r = q(FE.assessQuality({ luma: null, yaw: 0, mouthFlatSamples: 0 }));
  assert.deepEqual(r, { ok: true, reasons: [] });
});

test("质量门落点：命中强制 confident=false；嘴部平坦 ⇒ 微笑三态停用并标 occluded", () => {
  const base = read(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6, cheekSquintRight: 0.6 }));
  assert.equal(base.confident, true, "干净真笑本应自信（对照组）");
  const dark = FE.assessQuality({ luma: { mean: 0.05, variance: 0.03 }, yaw: 0, mouthFlatSamples: 0 });
  const v1 = q(FE.applyQuality(base, dark));
  assert.equal(v1.confident, false, "质量门命中必须强制降置信");
  assert.ok(v1.quality && !v1.quality.ok, "quality 字段必须随读数带出（界面据此改文案）");
  const smiley = read(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8 }));
  const flat = FE.assessQuality({ luma: { mean: 0.5, variance: 0.03 }, yaw: 0, mouthFlatSamples: 999 });
  const v2 = q(FE.applyQuality(smiley, flat));
  assert.equal(v2.smile.kind, "none", "嘴部平坦 ⇒ 微笑判读停用");
  assert.equal(v2.smile.occluded, true, "停用必须标 occluded（界面说明被遮挡），不是冒充「未检出微笑」");
});

/* ── r112 微笑三态的阈值邻域：真笑 vs 强颜欢笑的判别力边界 ────────────────────── */
// 上面「真笑 / 强颜欢笑」两条用的是极端向量（眼周 0.6 vs 0.05），只证明**两端可分**：
// 阈值若从 0.20 漂到 0.10 或 0.50，那两条照样全绿。下面四条把向量压到
// ratioOn = 0.20 / tensionOn = 0.30 的邻域上，钉住阈值本身与 masking 的分支条件。
const smile = (bs) => JSON.parse(JSON.stringify(FE.smileKind(bs)));
const T = RULES.smile;

test("真笑/强颜欢笑在 ratioOn 邻域内可分（同嘴幅，只差眼周）", () => {
  const hi = smile(vec({ mouthSmileLeft: 0.5, mouthSmileRight: 0.5, cheekSquintLeft: 0.175, cheekSquintRight: 0.175 }));
  const lo = smile(vec({ mouthSmileLeft: 0.5, mouthSmileRight: 0.5, cheekSquintLeft: 0.15, cheekSquintRight: 0.15 }));
  assert.ok(hi.ratio > T.ratioOn && lo.ratio < T.ratioOn,
    "两条必须落在门槛两侧，否则这条腿没压到边界：hi=" + hi.ratio + " lo=" + lo.ratio + " 门槛=" + T.ratioOn);
  assert.equal(hi.kind, "duchenne", "眼周比值刚过门槛 ⇒ 真笑");
  assert.equal(lo.kind, "social", "眼周比值刚掉到门槛下 ⇒ 社交性微笑");
});

test("强颜欢笑嫌疑随 tension 翻转，不是对所有社交笑一律报警", () => {
  const base = { mouthSmileLeft: 0.6, mouthSmileRight: 0.6, cheekSquintLeft: 0.05, cheekSquintRight: 0.05 };
  const tense = smile(Object.assign(vec(base), { mouthPressLeft: 0.5, mouthPressRight: 0.5 }));
  const relax = smile(Object.assign(vec(base), { mouthPressLeft: 0.1, mouthPressRight: 0.1 }));
  assert.equal(tense.kind, "social");
  assert.equal(relax.kind, "social", "两者都是社交笑，唯一变量是紧张线索");
  assert.ok(tense.tension >= T.tensionOn && relax.tension < T.tensionOn,
    "两条必须跨过 tensionOn，否则测不到 masking 分支：" + tense.tension + " / " + relax.tension);
  assert.equal(tense.masking, true, "伴紧张线索 ⇒ 标强颜欢笑嫌疑");
  assert.equal(relax.masking, false, "无紧张线索却仍报强颜欢笑 ⇒ 该标签恒真、失去判别力");
});

test("眼周充分参与时，抿唇也不得扣「强颜欢笑」帽子", () => {
  const v = smile(vec({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8, cheekSquintLeft: 0.6, cheekSquintRight: 0.6,
    mouthPressLeft: 0.8, mouthPressRight: 0.8 }));
  assert.ok(v.tension >= T.tensionOn, "这条向量必须真的带紧张线索，否则测不到 masking 分支");
  assert.equal(v.kind, "duchenne", "眼周参与 ⇒ 仍是真笑");
  assert.equal(v.masking, false, "masking 只在 social 分支为真，真笑不得被标强颜欢笑");
});

test("嘴部不达 smileOn ⇒ 判 none，高眼周也不得单独撑出微笑", () => {
  const v = smile(vec({ mouthSmileLeft: T.smileOn - 0.01, mouthSmileRight: T.smileOn - 0.01,
    cheekSquintLeft: 0.9, cheekSquintRight: 0.9 }));
  assert.equal(v.kind, "none", "嘴没笑到阈值却判微笑 ⇒ 光靠眼周也会误报");
  assert.equal(v.ratio, 0, "未成笑时 ratio 必须归零（界面不得拿它渲染真笑文案）");
  const r = read(vec({ mouthSmileLeft: 0.34, mouthSmileRight: 0.34, cheekSquintLeft: 0.9, cheekSquintRight: 0.9 }));
  assert.equal(r.smile.kind, "none", "整链路 read() 同样不得报微笑");
});
