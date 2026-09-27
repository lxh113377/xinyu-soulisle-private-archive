/* 心屿 · 情绪引擎 JS 侧单元测试（对标轮 r58）
 *
 * 为什么用 `node --test` + `node:vm` 而不是装 vitest/jest：
 *   被测对象是**浏览器全局脚本**（`window.EmotionEngine = (function(){...})()`，零构建、无 import）。
 *   `node:test` 与 `node:vm` 都是 Node 自带能力，跑起来不需要打包器，也不把 node_modules
 *   带进这个仓库（它同时被 Pages 静态部署和 `git archive` 发布物打包）。
 *   ⇒ 这不是"自己造测试框架"，是用平台自带的测试运行器给平台外的脚本补一层最小宿主替身。
 *
 * 与既有判据的边界（避免同一事实两处判）：
 *   `engine_consistency_check.py` 判的是 **JS ⇄ Java 双端同题同答**（含 36 条评测集）；
 *   本件判的是 **JS 引擎自身的算法行为单位**（否定/程度/优先级/值域/不变量），
 *   粒度更细、无需起服务端，且红面直接指到函数而不是指到"两端不一致"。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import { fileURLToPath } from "node:url";

// 基准目录 = 仓库根（本文件在 `_test/js/` 下，故相对 import.meta.url 上跳两级）。
// 直接用 import.meta.url 会把 `src/...` 解析成 `_test/src/...` —— 首跑就是这么红的。
const ROOT_URL = new URL("../../", import.meta.url);
const SRC = (rel) => readFileSync(new URL(rel, ROOT_URL), "utf8");
const ctx = createContext({ window: {} });
runInContext(SRC("src/data/emotion-lexicon.js"), ctx);
runInContext(SRC("src/js/emotion-engine.js"), ctx);
const E = ctx.window.EmotionEngine;

/** ⚠️ 跨 realm 归一（r58 实测踩到）：`node:vm` 里 `new Array()`/`{}` 的原型是** vm realm 的**，
 *  与宿主 realm 的 `Array` 不是同一个构造函数。`assert.deepEqual`（strict 版）会比较原型，
 *  于是两个逐元素 `Object.is` 全 true 的数组被判 "Values have same structure but are not reference-equal"。
 *  正解是把被测返回值当**数据**过一道 JSON 归一，而不是放宽断言或改成 loose equal。 */
const rawScan = E.scan;
const scan = (t) => JSON.parse(JSON.stringify(rawScan.call(E, t)));

test("夹具自证：引擎与词表真的被载入了（拿不到就整族失效）", () => {
  assert.ok(E && typeof E.scan === "function", "EmotionEngine.scan 不可调用");
  const lex = ctx.window.__XINYU_LEXICON__;
  assert.ok(lex && Object.keys(lex.lex || {}).length >= 5,
            "词表为空或未挂到 __XINYU_LEXICON__.lex ⇒ 后面所有断言都会假过");
  // 形状按**实测**写：neg/crisis 是数组，deg/labels/lex 是对象（首版把 deg 当数组，夹具自己判红）
  assert.ok(Array.isArray(lex.neg) && lex.neg.length >= 3, "否定词表不足");
  assert.ok(lex.deg && typeof lex.deg === "object" && Object.keys(lex.deg).length >= 3, "程度词表不足");
  assert.ok(Array.isArray(lex.crisis) && lex.crisis.length >= 3, "危机词表不足");
});

test("否定翻转：情绪词被否定后不得再报该情绪", () => {
  const pos = scan("我很开心");
  assert.equal(pos.emotion, "joy", "正向句应判为开心，实际 " + pos.emotion);
  const neg = scan("我不开心");
  assert.notEqual(neg.emotion, "joy", "「不开心」仍判成开心 ⇒ 否定没起作用");
});

test("程度加权：加强语气的强度必须严格高于裸词", () => {
  const plain = scan("我有点焦虑").intensity;
  const strong = scan("我非常焦虑").intensity;
  assert.ok(strong > plain, `程度词没抬高强度：裸 ${plain} vs 加强 ${strong}`);
});

test("危机优先级高于情绪评分，且强度钉到 1", () => {
  const r = scan("我很开心，哈哈");
  assert.equal(r.crisis, false, "无危机句被误报危机 ⇒ 会误推热线");
  const c = scan("我不想活了");
  assert.equal(c.crisis, true, "危机句未被识别 ⇒ 安全边界失效");
  assert.equal(c.emotion, "crisis", "危机时 emotion 字段应让位给 crisis");
  assert.equal(c.intensity, 1, "危机强度应钉为 1，实际 " + c.intensity);
});

test("值域不变量：intensity 恒在 [0,1]，含空串与超长串", () => {
  const samples = ["", "   ", "今天天气不错", "焦虑焦虑焦虑".repeat(400), "😡😡😡", "abc"];
  for (const s of samples) {
    const v = scan(s).intensity;
    assert.ok(Number.isFinite(v) && v >= 0 && v <= 1, `intensity 越界(${JSON.stringify(s.slice(0, 12))}=${v})`);
  }
});

test("all 排序与去重：多情绪共现时按分数降序，同名情绪只有一条", () => {
  const r = scan("又焦虑又生气，还特别疲惫");
  assert.ok(r.all.length >= 2, "共现场景只出一条 ⇒ 加权被吞");
  const scores = r.all.map((x) => x.score);
  assert.deepEqual(scores, [...scores].sort((a, b) => b - a), "all 未按分数降序");
  const names = r.all.map((x) => x.emotion);
  assert.equal(new Set(names).size, names.length, "同一情绪重复出现 ⇒ 聚合有 bug");
  assert.equal(r.emotion, names[0], "主情绪应是 all 的榜首");
});

test("无情绪线索回落平静，且不得凭空造出危机", () => {
  const r = scan("明天的课在第三教室");
  assert.equal(r.crisis, false);
  assert.equal(r.emotion, "calm", "无线索应回落平静，实际 " + r.emotion);
});
