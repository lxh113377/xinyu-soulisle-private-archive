/* 心屿 · Cloudflare Pages Function `/api/chat` 离线单元判据（r119 改造一）
 *
 * 为什么必须有这一族（一手读数）：`_test/run_all_suites.py:464` 的 `LLM_SUITES` 把
 * `j2_chat_contract` / `stream_contract` / `online_check` 三条在 CI 整跑里**豁免**
 * （runner 无上游密钥，G10 实测「实跑 149 + 豁免 3 == 152」）。于是公网真身
 * `src/functions/api/chat.js` 在**受理面上一条判据都没执行过** —— 只有本机活体能跑到它。
 * 对标证据：NextChat 把同一个 Cloudflare Pages Function 做成纯函数离线单测
 * （`test/cloudflare.test.ts`），SSE 分块解析也离线测（`test/format-chunks.test.ts`）。
 * 本件按同一形态补这条缺口：不触网、不要密钥，桩 fetch 驱动全部契约分支。
 *
 * 与 face-engine/emotion-engine 两族同通道：`node --test` + `node:vm`，零依赖零打包器。
 * 被测对象是 ES Module 源文（Cloudflare 侧原样吃 ESM），本仓没有 package.json
 * `type:"module"` ⇒ node 会把 `.js` 当 CJS 解析、`import()` 直接语法错，
 * 所以这里**读原文 + 剥行首 `export `** 再进 vm：测的仍是仓库里那串字节，不另抄一份实现。
 *
 * 反例腿（判据不许恒真）：最后一条 `变异腿` 把「先查 key」那道守卫在源码文本里摘掉，
 * 断言行为当场翻案 ⇒ 证明 T2/T3 的绿是被守卫撑住的，不是桩自己造出来的。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const ROOT_URL = new URL("../../", import.meta.url);
const FN_PATH = "src/functions/api/chat.js";

/** 取函数源码（权威源）。剥掉行首 export 是为了能在 vm 里拿到 onRequestPost/onRequestOptions。 */
function source(mutate) {
  let s = readFileSync(new URL(FN_PATH, ROOT_URL), "utf8");
  if (mutate) s = mutate(s);
  return s.replace(/^export\s+/gm, "");
}

/**
 * 建一个可调用被测函数的上下文。
 * ⚠️ 跨 realm：Response 用**外层真身**注入，被测代码造出的就是本 realm 对象，
 *    `res.json()/res.status/res.headers` 直接可用；若改用 vm 里自造的影子类，
 *    `instanceof` 与 `res.json` 会一起变成假象（本仓在册的跨 realm 坑）。
 */
function load({ fetchImpl, mutate } = {}) {
  const calls = [];
  const stubFetch = async (url, init) => {
    calls.push({ url, init });
    if (fetchImpl && fetchImpl.error) throw fetchImpl.error;
    return (fetchImpl && fetchImpl.respond) ? fetchImpl.respond(url, init) : mkUpstream({});
  };
  const ctx = createContext({ Response, console, fetch: stubFetch });
  runInContext(source(mutate), ctx);
  return { ctx, api: { post: ctx.onRequestPost, options: ctx.onRequestOptions }, calls };
}

/** 上游响应桩：headers 走小写取键（与 undici 一致），body 缺省给一个可辨识对象 */
function mkUpstream({ status = 200, ok, ctype = "application/json", json, text, body = null } = {}) {
  const isOk = ok === undefined ? status >= 200 && status < 300 : ok;
  return {
    status,
    ok: isOk,
    body,
    headers: { get: (k) => (String(k).toLowerCase() === "content-type" ? ctype : null) },
    json: async () => {
      if (json === undefined) {
        const e = new Error("not json");
        e.name = "SyntaxError";
        throw e;                              // 走 .catch(() => ({error:"upstream-nonjson"})) 那条腿
      }
      return json;
    },
    text: async () => text ?? "",
  };
}

/** 前端请求桩：origin 只影响 CORS；badBody=true 时 json() 抛（模拟坏 JSON） */
function mkReq(payload, { origin = "", badBody = false } = {}) {
  return {
    headers: { get: (k) => (String(k).toLowerCase() === "origin" ? origin : null) },
    json: async () => {
      if (badBody) throw new SyntaxError("bad json");
      return payload;
    },
  };
}

const KEY = "sk-test-DO-NOT-LEAK-1234567890";
const ENV = { DEEPSEEK_KEY: KEY };

async function callPost(api, req, env = ENV) {
  return api.post({ request: req, env });
}

// ── 夹具自证 ────────────────────────────────────────────────────────────────
test("夹具自证：函数体真被载入，两个出口可调用（拿不到就整族失效）", () => {
  const { api } = load();
  assert.equal(typeof api.post, "function", "onRequestPost 未载入");
  assert.equal(typeof api.options, "function", "onRequestOptions 未载入");
});

// ── 契约与判定顺序（AC-OBS-08 的「先查 key 再解析 body」） ──────────────────
test("T2 无密钥 → 500 no-key，且安全头在场（JSON 侧 no-store）", async () => {
  const { api } = load();
  const res = await callPost(api, mkReq({ messages: [] }), {});
  assert.equal(res.status, 500);
  assert.deepEqual(await res.json(), { error: "no-key" });
  assert.equal(res.headers.get("content-security-policy"), "default-src 'none'");
  assert.equal(res.headers.get("x-content-type-options"), "nosniff");
  assert.equal(res.headers.get("cache-control"), "no-store");
});

test("T3 判定顺序：既无密钥又是坏 JSON ⇒ 仍回 500，不许抢跑成 400", async () => {
  const { api } = load();
  const res = await callPost(api, mkReq(null, { badBody: true }), {});
  assert.equal(res.status, 500);
  assert.deepEqual(await res.json(), { error: "no-key" });
});

test("T4 有密钥但坏 JSON → 400 bad-json", async () => {
  const { api } = load();
  const res = await callPost(api, mkReq(null, { badBody: true }));
  assert.equal(res.status, 400);
  assert.deepEqual(await res.json(), { error: "bad-json" });
});

test("T5 字符串形 request（判据夹具形状）→ 400 且不带 CORS 头", async () => {
  // 在册注释：api_egress_headers 用**字符串**当 request 廉价驱动 bad-json 腿，
  // 真实 Pages 运行时恒是 Request。此处钉住该加固不退化。
  const { api } = load();
  const res = await callPost(api, "plain-string-request");
  assert.equal(res.status, 400);
  assert.equal(res.headers.get("access-control-allow-origin"), null, "字符串形状不该产出 CORS 头");
});

// ── 整包逐字透传 ────────────────────────────────────────────────────────────
const UP = { id: "cmpl-1", choices: [{ index: 0, message: { role: "assistant", content: "我在听" } }] };

test("T6 非流式：上游 status 与响应体逐字透传（含 201 这种非 200 成功码）", async () => {
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ status: 201, json: UP }) } });
  const res = await callPost(api, mkReq({ messages: [{ role: "user", content: "有点难过" }] }));
  assert.equal(res.status, 201, "上游 status 必须原样带出");
  assert.deepEqual(await res.json(), UP);
});

test("T7 上游错误码也逐字透传（502 + 上游自己的错误体，不许被换成自家文案）", async () => {
  const upErr = { error: { message: "upstream quota", type: "insufficient_quota" } };
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ status: 502, ok: false, json: upErr }) } });
  const res = await callPost(api, mkReq({ messages: [] }));
  assert.equal(res.status, 502);
  assert.deepEqual(await res.json(), upErr);
});

test("T8 上游返回非 JSON → upstream-nonjson，status 仍取上游码", async () => {
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ status: 503, ok: false }) } });
  const res = await callPost(api, mkReq({ messages: [] }));
  assert.equal(res.status, 503);
  assert.deepEqual(await res.json(), { error: "upstream-nonjson" });
});

// ── 出网形状：默认值、env 别名、URL 拼接 ───────────────────────────────────
test("T9 上游请求体默认值与 URL 拼接（尾斜杠吃掉，只加 /chat/completions）", async () => {
  const { api, calls } = load({ fetchImpl: { respond: () => mkUpstream({ json: UP }) } });
  await callPost(api, mkReq({ messages: [{ role: "user", content: "hi" }] }),
    { DEEPSEEK_KEY: KEY, DEEPSEEK_BASE: "https://example.test/v1/" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://example.test/v1/chat/completions");
  const sent = JSON.parse(calls[0].init.body);
  assert.equal(sent.model, "deepseek-chat");
  assert.equal(sent.temperature, 0.85, "temperature 缺省须为 0.85");
  assert.equal(sent.max_tokens, 220, "max_tokens 缺省须为 220");
  assert.equal(sent.stream, undefined, "非流式不许把 stream 带给上游");
  assert.equal(calls[0].init.headers.Authorization, "Bearer " + KEY);
});

test("T10 env 别名优先级：LLM_* 压过 DEEPSEEK_*（新名可用、旧名不删）", async () => {
  const { api, calls } = load({ fetchImpl: { respond: () => mkUpstream({ json: UP }) } });
  await callPost(api, mkReq({ temperature: 0.1, max_tokens: 9 }), {
    LLM_KEY: "newkey", DEEPSEEK_KEY: KEY,
    LLM_BASE: "https://alt.test/v1", DEEPSEEK_BASE: "https://example.test/v1",
    LLM_MODEL: "alt-model", DEEPSEEK_MODEL: "deepseek-chat",
  });
  assert.equal(calls[0].url, "https://alt.test/v1/chat/completions");
  assert.equal(calls[0].init.headers.Authorization, "Bearer newkey");
  const sent = JSON.parse(calls[0].init.body);
  assert.equal(sent.model, "alt-model");
  assert.equal(sent.temperature, 0.1, "前端显式参数不许被默认值覆盖");
  assert.equal(sent.max_tokens, 9);
});

test("T16 密钥零外泄：响应头与响应体都不许出现 Key", async () => {
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ json: UP }) } });
  const res = await callPost(api, mkReq({ messages: [] }));
  const body = await res.text();
  const headers = [...res.headers].map(([k, v]) => k + ":" + v).join("|");
  assert.ok(!body.includes(KEY) && !headers.includes(KEY), "响应面出现明文密钥 = 红线");
});

// ── 流式分支 ────────────────────────────────────────────────────────────────
test("T11 stream=true 且上游 2xx + event-stream → SSE 直通，分块内容不被重包吃掉", async () => {
  // 断言口径的来由：`new Response(body)` 会把 bodyInit **包装成一条新的 ReadableStream**，
  // 所以「同一个对象引用」不是可观测事实（实测失败在这一点上）。真正要钉的是
  // **内容原样抵达且仍是流** —— 重包成 JSON 会让分块边界与增量渲染一起失效。
  const CHUNKS = ['data: {"choices":[{"delta":{"content":"我"}}]}\n\n',
                  'data: {"choices":[{"delta":{"content":"在"}}]}\n\n',
                  "data: [DONE]\n\n"];
  const streamBody = new ReadableStream({
    start(c) { CHUNKS.forEach((x) => c.enqueue(new TextEncoder().encode(x))); c.close(); },
  });
  const { api } = load({
    fetchImpl: { respond: () => mkUpstream({ ctype: "text/event-stream; charset=utf-8", json: {}, body: streamBody }) },
  });
  const res = await callPost(api, mkReq({ stream: true, messages: [] }));
  assert.equal(res.status, 200);
  assert.ok(res.body && typeof res.body.getReader === "function", "SSE 侧必须仍是流，不许被 res.json() 收整");
  assert.equal(await res.text(), CHUNKS.join(""), "直通 = 分块逐字抵达");
  assert.match(res.headers.get("content-type") || "", /^text\/event-stream/);
  assert.equal(res.headers.get("cache-control"), "no-cache, no-transform", "no-transform 不许被 no-store 覆盖");
  assert.equal(res.headers.get("x-accel-buffering"), "no");
  assert.equal(res.headers.get("connection"), "keep-alive");
  assert.equal(res.headers.get("content-security-policy"), "default-src 'none'");
});

test("T12 stream=true 但上游报错 → 折回整包 JSON，前端可按 content-type 回落非流式", async () => {
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ status: 429, ok: false, json: { error: "rate" } }) } });
  const res = await callPost(api, mkReq({ stream: true, messages: [] }));
  assert.equal(res.status, 429);
  assert.equal(res.headers.get("cache-control"), "no-store", "回落 JSON 侧应恢复 no-store");
  assert.match(res.headers.get("content-type") || "", /application\/json/);
  assert.deepEqual(await res.json(), { error: "rate" });
});

test("T13 stream=true 但上游给的是普通 JSON → 不许冒充流", async () => {
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ json: UP, body: { tag: "x" } }) } });
  const res = await callPost(api, mkReq({ stream: true, messages: [] }));
  assert.match(res.headers.get("content-type") || "", /application\/json/);
  assert.equal(res.headers.get("x-accel-buffering"), null);
});

// ── CORS 白名单 ─────────────────────────────────────────────────────────────
test("T14 CORS 只放行白名单自家来源：命中回显 + Vary，未列来源一个头都不给", async () => {
  const ok = load({ fetchImpl: { respond: () => mkUpstream({ json: UP }) } });
  const r1 = await callPost(ok.api, mkReq({ messages: [] }, { origin: "https://xinyu-soulisle.pages.dev" }));
  assert.equal(r1.headers.get("access-control-allow-origin"), "https://xinyu-soulisle.pages.dev");
  assert.equal(r1.headers.get("vary"), "Origin");

  const bad = load({ fetchImpl: { respond: () => mkUpstream({ json: UP }) } });
  const r2 = await callPost(bad.api, mkReq({ messages: [] }, { origin: "https://evil.example" }));
  assert.equal(r2.headers.get("access-control-allow-origin"), null, "白名单外不得发头");
  assert.notEqual(r2.headers.get("access-control-allow-origin"), "*", "禁止开放 *");
});

test("T15 OPTIONS 预检：白名单 204，非白名单 403", async () => {
  const { api } = load();
  const a = await api.options({ request: mkReq({}, { origin: "http://127.0.0.1:8123" }) });
  assert.equal(a.status, 204);
  assert.equal(a.headers.get("access-control-allow-methods"), "POST, OPTIONS");
  const b = await api.options({ request: mkReq({}, { origin: "https://evil.example" }) });
  assert.equal(b.status, 403);
});

// ── 变异腿（反例控制：证明上面的绿不是恒真） ───────────────────────────────
test("变异腿：摘掉「先查 key」守卫后，无密钥请求当场不再回 500 —— 否则本族判据是装饰", async () => {
  const mutated = (s) => {
    const guarded = s.replace("if (!key) return", "if (false) return");
    assert.notEqual(guarded, s, "变异点没命中 ⇒ 源码形状变了，本条必须红，不许静默跳过");
    return guarded;
  };
  const { api } = load({ fetchImpl: { respond: () => mkUpstream({ json: UP }) }, mutate: mutated });
  const res = await callPost(api, mkReq({ messages: [] }), {});   // 无 key
  assert.notEqual(res.status, 500, "守卫被摘掉却仍回 500 ⇒ T2 没有区分力");
  assert.equal(res.status, 200, "摘守卫后无密钥请求会打到上游（这正是缺陷形态）");
});
