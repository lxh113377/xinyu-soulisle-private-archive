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

export async function onRequestPost(context) {
  const { request, env } = context;
  const key = env.LLM_KEY || env.DEEPSEEK_KEY;
  const base = env.LLM_BASE || env.DEEPSEEK_BASE || "https://api.deepseek.com/v1";
  const model = env.LLM_MODEL || env.DEEPSEEK_MODEL || "deepseek-chat";
  if (!key) return Response.json({ error: "no-key" }, { status: 500, headers: SEC_JSON });

  let payload;
  try { payload = await request.json(); }
  catch { return Response.json({ error: "bad-json" }, { status: 400, headers: SEC_JSON }); }

  const wantStream = payload.stream === true;
  const upstreamBody = {
    model,
    messages: payload.messages || [],
    temperature: payload.temperature ?? 0.85,
    max_tokens: payload.max_tokens ?? 220
  };
  if (wantStream) upstreamBody.stream = true;

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
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
      }
    });
  }

  const data = await upstream.json().catch(() => ({ error: "upstream-nonjson" }));
  return Response.json(data, { status: upstream.status, headers: SEC_JSON });
}
