/* 心屿 · 情绪记忆存储层离线单元判据（r120 改造三）
 *
 * 为什么必须有（一手）：`memory-store.js` 的承诺写在 `src/js/memory-store.js:14-24` 的注释里 ——
 * 「默认只走本机 localStorage；`cfg.remote===true` 才把服务端当权威副本；服务端不可达则完全回落，
 * 功能不受影响，且**不制造持续网络噪音**」。此前这三条只有 `j4_remote_down_check` 与
 * `memory_recall_check` 两条**浏览器腿**在跑，而它们要打 8123 的服务 —— 共享工作树里那台服务
 * 常年被并行会话占用（本轮实测 pid 34412），于是这三条承诺在受理面上其实是**没人纯函数验过**的。
 * 对标证据：NextChat 把 store 层与 SSE 解析都做成离线单测（`app/store/*.ts` ⇄ `test/*.test.ts`）。
 *
 * 通道同仓内既有两族：`node --test` + `node:vm`（零依赖、零打包器），被测对象是浏览器全局脚本。
 * 反例腿：摘掉熔断置位 `markDown()` 后，「404 之后不再发请求」这条断言必须当场翻红。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const ROOT_URL = new URL("../../", import.meta.url);
const SRC = "src/js/memory-store.js";
const KEY = "peiliao.emotions.v1";
const CFG_KEY = "peiliao.cfg.v1";
const SID_KEY = "peiliao.session.v1";

/**
 * 造一个可重复使用的运行环境。
 * ⚠️ 每次 load() 都新建上下文：模块里 `remoteDown` 与 `mem` 都是**闭包态**，
 *    复用同一个 ctx 会让上一条用例的熔断态漏到下一条（同族：跨用例的全局激活态）。
 */
function boot({ cfg = {}, fetchImpl, storage = {}, mutate } = {}) {
  // cfg 必须以 CFG_KEY 落进存储：模块的 cfg() 只读 localStorage，
  // 直接把它当参数传给 isRemote() 会测到一个不存在的接口（首轮 4 条红就是这么来的）
  const store = new Map(Object.entries({ [CFG_KEY]: JSON.stringify(cfg), ...storage }));
  const calls = [];
  const localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  const fetchStub = async (url, opts) => {
    calls.push({ url, opts });
    return fetchImpl ? fetchImpl(url, calls.length) : { ok: true, status: 200, json: async () => [] };
  };
  let src = readFileSync(new URL(SRC, ROOT_URL), "utf8");
  if (mutate) src = mutate(src);
  const ctx = createContext({ window: {}, localStorage, fetch: fetchStub, console, Date, Math, JSON });
  runInContext(src, ctx);
  return { MS: ctx.window.MemoryStore, calls, store };
}

const ok404 = () => ({ status: 404, ok: false, json: async () => ({}) });

test("夹具自证：导出面 9 个键齐、模块真的被载入（拿不到就整族失效）", () => {
  const { MS } = boot();
  assert.equal(typeof MS, "object", "window.MemoryStore 未挂上");
  for (const k of ["record", "all", "clear", "exportAll", "hydrate", "pushMessage",
                   "isRemote", "sessionId", "recall", "count"]) {
    assert.equal(typeof MS[k], "function", `导出面缺 ${k}`);
  }
});

test("T1 键名是契约：三个 localStorage 键写死，改名等于让用户的记忆凭空消失", () => {
  const src = readFileSync(new URL(SRC, ROOT_URL), "utf8");
  for (const k of [KEY, CFG_KEY, SID_KEY]) {
    assert.ok(src.includes('"' + k + '"'), `源码里找不到键名 ${k}`);
  }
});

test("T2 默认（无 cfg）不发任何远端请求：离线即完整可用", async () => {
  const { MS, calls } = boot();
  assert.equal(MS.isRemote(), false, "未置 remote:true 却判成远端模式");
  await MS.record({ emotion: "sadness", intensity: 0.6, text: "有点难过" });
  assert.equal(calls.length, 0, "默认态发了远端请求 = 公网版会看到 404 噪音");
});

test("T3 本机持久化真落盘：record 之后 localStorage 的键里有条目、时间戳由模块补", async () => {
  const { MS, store } = boot();
  await MS.record({ emotion: "anger", intensity: 0.4 });
  const raw = JSON.parse(store.get(KEY));
  assert.equal(raw.length, 1);
  assert.equal(raw[0].emotion, "anger");
  assert.equal(typeof raw[0].ts, "number", "ts 应由存储层补齐，不依赖调用方传");
});

test("T4 500 条封顶是**截头留尾**：灌 505 条后仍是 500 条且最早那批被丢掉", async () => {
  const seed = JSON.stringify(
    Array.from({ length: 500 }, (_, i) => ({ ts: i, emotion: "calm", seq: i })));
  const { MS, store } = boot({ storage: { [KEY]: seed } });
  for (let i = 0; i < 5; i++) await MS.record({ emotion: "calm", seq: 500 + i });
  const arr = JSON.parse(store.get(KEY));
  assert.equal(arr.length, 500, "封顶没生效");
  assert.equal(arr[0].seq, 5, "应丢掉最旧的 5 条");
  assert.equal(arr[499].seq, 504, "最新那条必须还在");
});

test("T5 remote:true → 写本机同时推 /api/memory/emotion，且是同源相对路径", async () => {
  const { MS, calls } = boot({ cfg: { remote: true } });
  await MS.record({ emotion: "fear", text: "慌" });
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.startsWith("/api/memory/"), `必须是同源相对路径，实际=${calls[0].url}`);
  assert.equal(calls[0].url, "/api/memory/emotion");
  const body = JSON.parse(calls[0].opts.body);
  assert.equal(body.emotion, "fear");
  assert.ok(body.sessionId, "推送必须带 sessionId，否则服务端记不到是哪个会话");
  assert.equal(calls[0].opts.method, "POST");
});

test("T6 熔断（承诺的核心）：404 之后本会话不再尝试，且回落路径仍写本机", async () => {
  const { MS, calls, store } = boot({ cfg: { remote: true }, fetchImpl: ok404 });
  await MS.record({ emotion: "sadness" });
  assert.equal(calls.length, 1, "第一次应当尝试");
  assert.equal(MS.isRemote(), false, "404 之后必须判成已熔断");
  for (let i = 0; i < 4; i++) await MS.record({ emotion: "sadness", i });
  assert.equal(calls.length, 1, "熔断后仍在发请求 = 「不制造持续网络噪音」这条承诺是空的");
  assert.equal(JSON.parse(store.get(KEY)).length, 5, "熔断不得影响本机写入");
});

test("T7 熔断态由 markDown 决定 —— 变异腿：摘掉置位后 T6 必须翻红", async () => {
  const mutate = (s) => {
    const m = s.replace("function markDown() { remoteDown = true; }",
                        "function markDown() { remoteDown = false; }");
    assert.notEqual(m, s, "变异点没命中 ⇒ 源码形状变了，本条必须红");
    return m;
  };
  const { MS, calls } = boot({ cfg: { remote: true }, fetchImpl: ok404, mutate });
  await MS.record({ emotion: "sadness" });
  await MS.record({ emotion: "sadness" });
  assert.equal(calls.length, 2, "摘掉熔断却仍只发一次 ⇒ T6 没有区分力");
});

test("T8 sessionId 稳定：同一存储内两次取同值，且首次会落盘", () => {
  const { MS, store } = boot();
  const a = MS.sessionId();
  const b = MS.sessionId();
  assert.equal(a, b, "会话号每次变 ⇒ 服务端按 sessionId 聚合的记忆会被切碎");
  assert.equal(store.get(SID_KEY), a, "首次生成的会话号必须持久化");
});

test("T9 clear 两侧都清：本机键移除，远端走 DELETE /api/memory/<sid>", async () => {
  const { MS, calls, store } = boot({ cfg: { remote: true }, storage: { [KEY]: "[{\"e\":1}]" } });
  store.set(SID_KEY, "s-fixed");
  const { MS: MS2 } = { MS };
  await MS2.clear();
  assert.equal(store.has(KEY), false, "本机条目没被清掉");
  const del = calls.find((c) => c.opts && c.opts.method === "DELETE");
  assert.ok(del, "远端侧必须发 DELETE");
  assert.equal(del.url, "/api/memory/s-fixed");
});

test("T10 exportAll 的本机面不依赖远端：远端 404 时仍能把本地条目交出去", async () => {
  const { MS } = boot({ cfg: { remote: true }, fetchImpl: ok404,
                        storage: { [KEY]: "[{\"emotion\":\"joy\"}]" } });
  const out = await MS.exportAll();
  assert.ok(out && out.source, "exportAll 必须带 source 结构（数据权利面板读它）");
  assert.deepEqual(out.source.local, [{ emotion: "joy" }], "远端不可用时本机那份必须还在");
});

test("T11 存储不可用（隐私模式）不得抛穿：load/persist 的 catch 是这条链的地板", async () => {
  const { MS } = boot({ storage: {} });
  const broken = createContext({ window: {}, console, Date, Math, JSON });
  broken.localStorage = { getItem() { throw new Error("blocked"); },
                          setItem() { throw new Error("blocked"); },
                          removeItem() { throw new Error("blocked"); } };
  runInContext(readFileSync(new URL(SRC, ROOT_URL), "utf8"), broken);
  const M = broken.window.MemoryStore;
  await M.record({ emotion: "calm" });          // 不许抛
  assert.equal(typeof M.sessionId(), "string", "localStorage 被挡时也要有会话标识");
  assert.ok(Array.isArray(M.all()), "all() 在坏存储上必须回数组而不是崩");
  void MS;
});
