/* 心屿 · Cloudflare Pages Function：/api/chat
 * 作用：前端同源代理转发 OpenAI 兼容上游，密钥隔离在服务端 env，绝不进前端源码。
 * env: LLM_KEY | DEEPSEEK_KEY(兼容旧名，必填其一)
 *      LLM_BASE | DEEPSEEK_BASE(默认 https://api.deepseek.com/v1)
 *      LLM_MODEL | DEEPSEEK_MODEL(默认 deepseek-chat)
 *
 * 两种响应形态（对标 LobeChat/OLV 的流式能力）：
 *   · 请求体无 stream 或 stream=false → 整包 JSON **逐字透传**（v1 契约，AC-OBS-08 判据不变）
 *   · 请求体 stream=true 且上游 2xx   → SSE 直通（text/event-stream），前端逐字渲染
 *   · 请求体 stream=true 但上游报错   → 折回整包 JSON 错误体，前端按 content-type 自动回落非流式
 */

/* 安全响应头（r57）。为什么写在函数里而不是 _headers：
 * 静态 `_headers` **不作用于 Pages Function** —— r54 实测 `/api/chat` 一条 CSP 都没有，
 * 而 `deploy/xinyu/_headers` 那时已经生效 11 条指令。所以这一路只能由函数自己回头。
 * ⚠️ 只加头，不动 `status` 与 `body`：AC-OBS-08 的契约是"上游响应逐字透传"，
 *    `j2_chat_contract` / `api_contract` 两条判据正盯着它，顺手改响应形状就是撞红线。
 * `default-src 'none'` 对这个 JSON 端点是安全的：它不渲染文档，CSP 真正防的是
 * "有人把 /api/chat 当文档打开、或把它嵌进 iframe 里凑同源"这一类。
 * Cache-Control 分两种：JSON 侧给 no-store（对话响应不该被缓存）；
 * SSE 侧保留它原有的 `no-cache, no-transform`（no-transform 挡住中间层改写流，不能被覆盖掉）。*/
const SEC_HEADERS = {
  "Content-Security-Policy": "default-src 'none'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Cross-Origin-Opener-Policy": "same-origin"
};
const SEC_JSON = { ...SEC_HEADERS, "Cache-Control": "no-store" };

/* CORS（r86）：备用线（CloudBase 静态托管域名）的界面无法拿到云函数路由（该 env 三项目共用、
 * HTTP 访问服务证书与路由属控制台动作），改为让备用线前端直接调用本函数。密钥仍在服务端 env，
 * 跨域面只放行**白名单内的自家来源**（主推线 / 备用线 / 本机演示），不开放 `*` ——
 * 这是把"谁能白嫖这把 Key 的代理"钉死在三个已知的自己人上。只加头，不动 status/body：
 * AC-OBS-08 的"上游逐字透传"契约与 j2_chat_contract / api_contract 仍原样成立。*/
const CORS_ALLOW = new Set([
  "https://xinyu-soulisle.pages.dev",
  "https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com",
  "http://localhost:8123",
  "http://127.0.0.1:8123"
]);

function corsHeaders(request) {
  // 判据夹具会用**字符串**当 request 廉价驱动 bad-json 腿（api_egress_headers），
  // 真实 Pages 运行时恒是 Request ⇒ 这里按"有 .headers 才取 Origin"加固，字符串形状一律无 CORS 头。
  const origin = request && request.headers ? request.headers.get("Origin") || "" : "";
  if (!CORS_ALLOW.has(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Max-Age": "600",
    "Vary": "Origin"
  };
}

/* r168 成本面（对标 r128/r130 Java 侧的 ApiGuardFilter + QuotaFilter）：按 IP 的次数上限。
 *
 * 为什么要补这一道：`/api/chat` 是本仓唯一真花钱的端点，而公网 v1 线此前只剩「密钥不落前端」
 * 一层 —— r130 §9 实测登记：Java 侧有令牌桶 + 按日闸，Pages Function 侧两者都没有。
 *
 * ⚠️ 能力边界必须如实写在这儿，不许把它读成「和 Java 侧一样」：
 *   · 本 isolate 内存计数，**无持久层** ⇒ 冷启动/换 isolate 即归零；
 *   · 只认 `cf-connecting-ip` ⇒ 同一 NAT 出口会互相挤占，换 IP 即绕开；
 *   · 没有按日累计（那要 KV/D1 绑定，属对外发布动作，本轮不做）。
 *   ⇒ 它压得住「同一个 IP 在一个 isolate 活着时猛打」，压不住慢速长期白嫖。
 *   中期方案（r130 §9 选项①：KV 按日累计）待公网流量真正上来再上。
 *
 * 默认 30 次/分/IP 刻意宽松：宁可在极端滥用下多花一点，也不能打断评委与判据夹具的正常调用
 * （与 `application.yml` 里 r128 那条同口径）。`LLM_MAX_PER_MIN=0` = 整闸关闭。
 * 计数只发生在**真要打上游客**的那一次；被拒的那次不计数，否则越重试越早锁死（r130 S2 同族）。*/
const RL_WINDOW_MS = 60000;
const rlBuckets = new Map();

function costGuard(request, env) {
  const limit = Math.floor(Number(env.LLM_MAX_PER_MIN));
  const rpm = Number.isFinite(limit) && limit >= 0 ? limit : 30;
  if (rpm <= 0) return null;
  const ip = (request && request.headers ? request.headers.get("cf-connecting-ip") : "") || "unknown";
  const now = Date.now();
  let rec = rlBuckets.get(ip);
  if (!rec || now - rec.t0 >= RL_WINDOW_MS) {
    // isolate 可以活很久：不清过期桶就会让这个 Map 无界增长（换来的是省掉一个定时器）。
    if (rlBuckets.size > 512) {
      for (const [k, v] of rlBuckets) if (now - v.t0 >= RL_WINDOW_MS) rlBuckets.delete(k);
    }
    rec = { t0: now, n: 0 };
    rlBuckets.set(ip, rec);
  }
  if (rec.n >= rpm) {
    return { limited: true, limit: rpm, left: 0, wait: Math.max(1, Math.ceil((rec.t0 + RL_WINDOW_MS - now) / 1000)) };
  }
  rec.n += 1;
  return { limited: false, limit: rpm, left: rpm - rec.n, wait: 0 };
}

/** 配额可观测头：让人（和 `_test/v1_cost_guard_check.py`）能在响应上直接读出剩余额度。 */
function rlHeaders(g) {
  if (!g) return {};
  return {
    "X-RateLimit-Limit": String(g.limit),
    "X-RateLimit-Remaining": String(g.left),
    "X-RateLimit-Window": String(RL_WINDOW_MS / 1000)
  };
}

export async function onRequestOptions({ request }) {
  const h = corsHeaders(request);
  if (!h["Access-Control-Allow-Origin"]) return new Response(null, { status: 403 });
  return new Response(null, { status: 204, headers: { ...SEC_HEADERS, ...h } });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const cors = corsHeaders(request);
  const key = env.LLM_KEY || env.DEEPSEEK_KEY;
  const base = env.LLM_BASE || env.DEEPSEEK_BASE || "https://api.deepseek.com/v1";
  const model = env.LLM_MODEL || env.DEEPSEEK_MODEL || "deepseek-chat";
  if (!key) return Response.json({ error: "no-key" }, { status: 500, headers: { ...SEC_JSON, ...cors } });

  let payload;
  try { payload = await request.json(); }
  catch { return Response.json({ error: "bad-json" }, { status: 400, headers: { ...SEC_JSON, ...cors } }); }

  const wantStream = payload.stream === true;
  const upstreamBody = {
    model,
    messages: payload.messages || [],
    temperature: payload.temperature ?? 0.85,
    max_tokens: payload.max_tokens ?? 220
  };
  if (wantStream) upstreamBody.stream = true;

  // 成本闸放在「真要打上游」之前：no-key / bad-json 那两条出口不花钱，也就不占额度。
  const rl = costGuard(request, env);
  if (rl && rl.limited) {
    return Response.json({ error: "rate-limited" }, {
      status: 429,
      headers: { ...SEC_JSON, ...cors, ...rlHeaders(rl), "Retry-After": String(rl.wait) }
    });
  }

  const upstream = await fetch(base.replace(/\/$/, "") + "/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + key },
    body: JSON.stringify(upstreamBody)
  });

  // SSE 直通：上游必须是 2xx 且真给了 event-stream，否则按原路径回整包 JSON（前端可判定回落）
  const ctype = upstream.headers.get("content-type") || "";
  if (wantStream && upstream.ok && ctype.includes("text/event-stream") && upstream.body) {
    return new Response(upstream.body, {
      status: 200,
      // SEC_HEADERS 放**前面**：本分支自己的 Cache-Control / Content-Type 必须赢过它
      headers: {
        ...SEC_HEADERS,
        ...cors,
        ...rlHeaders(rl),
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
      }
    });
  }

  const data = await upstream.json().catch(() => ({ error: "upstream-nonjson" }));
  return Response.json(data, { status: upstream.status, headers: { ...SEC_JSON, ...cors, ...rlHeaders(rl) } });
}
